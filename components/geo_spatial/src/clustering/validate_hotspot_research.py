"""TravelMind research validation, without changing existing model outputs.

Run from project root:
    python src/clustering/validate_hotspot_research.py
Dependencies: pandas, numpy, scikit-learn
"""
from pathlib import Path
import argparse
import math
import re

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.metrics import adjusted_rand_score

EARTH_RADIUS_KM = 6371.0088
REQUIRED = ["attraction_id", "attraction_name", "district", "latitude", "longitude", "dbscan_cluster"]


def positive_flag(series):
    return series.fillna("").astype(str).str.strip().str.lower().isin(
        ["yes", "true", "1", "y", "flagged"]
    )


def names_valid(series):
    vals = series.fillna("").astype(str).str.strip()
    placeholders = vals.str.casefold().isin(["", "unknown", "unnamed", "none", "nan", "#temple"])
    alpha = vals.map(lambda s: any(c.isalpha() for c in s))
    return (~placeholders) & alpha


def haversine_km(lat1, lon1, lats, lons):
    a, b, c, d = map(np.radians, [lat1, lon1, lats, lons])
    h = np.sin((c - a) / 2) ** 2 + np.cos(a) * np.cos(c) * np.sin((d - b) / 2) ** 2
    return EARTH_RADIUS_KM * 2 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def make_flags(df):
    review = positive_flag(df["review_required"]) if "review_required" in df else pd.Series(False, index=df.index)
    duplicate = positive_flag(df["suspected_duplicate"]) if "suspected_duplicate" in df else pd.Series(False, index=df.index)
    invalid = ~names_valid(df["attraction_name"])
    unverified = (
        ~df["verification_status"].fillna("").astype(str).str.lower().isin(["verified", "manually_verified"])
        if "verification_status" in df else pd.Series(True, index=df.index)
    )
    return review, duplicate, invalid, unverified


def cluster_report(df, labels, review, duplicate, invalid):
    work = df.copy()
    work["_label"] = labels
    work["_review"] = review.to_numpy()
    work["_duplicate"] = duplicate.to_numpy()
    work["_invalid"] = invalid.to_numpy()
    rows = []
    for cluster, part in work.loc[work["_label"] != -1].groupby("_label"):
        center_lat = float(part["latitude"].median())
        center_lon = float(part["longitude"].median())
        distances = haversine_km(center_lat, center_lon, part["latitude"].to_numpy(), part["longitude"].to_numpy())
        primary = part["district"].fillna("Unknown").astype(str).value_counts()
        n = len(part)
        rows.append({
            "cluster_id": int(cluster), "record_count": n,
            "main_district": primary.index[0] if len(primary) else "Unknown",
            "district_count": int(part["district"].nunique()),
            "center_latitude": round(center_lat, 6), "center_longitude": round(center_lon, 6),
            "median_radius_km": round(float(np.median(distances)), 3),
            "p90_radius_km": round(float(np.percentile(distances, 90)), 3),
            "max_radius_km": round(float(np.max(distances)), 3),
            "review_flag_pct": round(float(part["_review"].mean() * 100), 2),
            "suspected_duplicate_pct": round(float(part["_duplicate"].mean() * 100), 2),
            "invalid_name_pct": round(float(part["_invalid"].mean() * 100), 2),
            "category_count": int(part["tourism_category"].nunique()) if "tourism_category" in part else None,
            "interpretation_warning": (
                "wide_spread_or_multiple_districts" if np.percentile(distances, 90) > 10 or part["district"].nunique() > 1
                else "high_review_flags" if part["_review"].mean() >= 0.4
                else "candidate_requires_validation"
            ),
        })
    return pd.DataFrame(rows).sort_values("record_count", ascending=False) if rows else pd.DataFrame(columns=["cluster_id", "record_count"])


def fit_dbscan(df, eps_km, min_samples):
    coordinates = np.radians(df[["latitude", "longitude"]].to_numpy(dtype=float))
    return DBSCAN(
        eps=eps_km / EARTH_RADIUS_KM,
        min_samples=min_samples,
        metric="haversine",
        algorithm="ball_tree",
        n_jobs=-1,
    ).fit_predict(coordinates)


def main():
    parser = argparse.ArgumentParser(description="Audit Sri Lankan candidate attractions and DBSCAN hotspot robustness")
    parser.add_argument("--input", type=Path, default=Path("data/processed/travelmind_combined_clusters.csv"))
    parser.add_argument("--output", type=Path, default=Path("results/reports/hotspot_research_validation"))
    parser.add_argument("--fast", action="store_true", help="Only 2 DBSCAN runs, for initial testing")
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f"Cannot find dataset: {args.input}. Run this from your TravelMind project root.")
    df = pd.read_csv(args.input, low_memory=False)
    missing = [col for col in REQUIRED if col not in df.columns]
    if missing:
        parser.error(f"Missing required columns: {missing}")
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["dbscan_cluster"] = pd.to_numeric(df["dbscan_cluster"], errors="coerce")
    before = len(df)
    df = df.loc[df["latitude"].between(5.5, 10.2) & df["longitude"].between(79.4, 82.2) & df["dbscan_cluster"].notna()].copy()
    if len(df) == 0:
        parser.error("No valid coordinates and DBSCAN labels")
    if df["attraction_id"].duplicated().any():
        parser.error("Duplicate attraction IDs detected; resolve before model stability comparison.")
    df["dbscan_cluster"] = df["dbscan_cluster"].astype(int)
    args.output.mkdir(parents=True, exist_ok=True)

    review, duplicate, invalid, unverified = make_flags(df)
    labels = df["dbscan_cluster"].to_numpy()
    existing = cluster_report(df, labels, review, duplicate, invalid)
    existing.to_csv(args.output / "original_hotspot_quality_audit.csv", index=False)

    quality = pd.DataFrame([{
        "original_rows": before, "rows_with_valid_coordinates_and_cluster": len(df),
        "review_required_count": int(review.sum()), "suspected_duplicate_count": int(duplicate.sum()),
        "invalid_name_count": int(invalid.sum()), "unverified_count": int(unverified.sum()),
        "clustered_count": int(np.sum(labels != -1)), "noise_count": int(np.sum(labels == -1)),
        "original_cluster_count": int(len(set(labels) - {-1})),
    }])
    quality.to_csv(args.output / "dataset_quality_summary.csv", index=False)

    # Baseline reimplementation test: equal eps/min_samples should reproduce saved labels
    # up to permutation; discrepancies may indicate changed data or another algorithm setup.
    configs = [(2.0, 5)] if args.fast else [(1.0, 5), (1.5, 5), (2.0, 5), (3.0, 5), (5.0, 5), (2.0, 10), (3.0, 10)]
    stability_rows = []
    for eps, minimum in configs:
        predicted = fit_dbscan(df, eps, minimum)
        cluster_ids = set(predicted) - {-1}
        largest = max((int(np.sum(predicted == c)) for c in cluster_ids), default=0)
        stability_rows.append({
            "eps_km": eps, "min_samples": minimum,
            "number_of_clusters": len(cluster_ids), "noise_count": int(np.sum(predicted == -1)),
            "coverage_pct": round(100 * np.mean(predicted != -1), 2),
            "largest_cluster_records": largest,
            "largest_cluster_pct_total": round(100 * largest / len(df), 2),
            "adjusted_rand_vs_saved_dbscan": round(float(adjusted_rand_score(labels, predicted)), 5),
        })
        print(f"eps={eps} km, min_samples={minimum}: {len(cluster_ids)} clusters, {np.sum(predicted == -1)} noise points")
    sensitivity = pd.DataFrame(stability_rows)
    sensitivity.to_csv(args.output / "dbscan_parameter_sensitivity.csv", index=False)

    # Sensitivity to suspected duplicates: rerun on the exact retained subset.
    keep = (~duplicate).to_numpy()
    if keep.sum() >= 5 and duplicate.any():
        clean_df = df.loc[keep].copy()
        clean_labels = fit_dbscan(clean_df, 2.0, 5)
        baseline_subset = labels[keep]
        duplicate_study = pd.DataFrame([{
            "removed_suspected_duplicate_rows": int(duplicate.sum()),
            "remaining_rows": len(clean_df),
            "remaining_clusters": int(len(set(clean_labels) - {-1})),
            "remaining_noise": int(np.sum(clean_labels == -1)),
            "adjusted_rand_vs_original_labels_on_same_records": round(float(adjusted_rand_score(baseline_subset, clean_labels)), 5),
            "note": "Removing flags is a sensitivity experiment, not validated deduplication.",
        }])
    else:
        duplicate_study = pd.DataFrame([{"removed_suspected_duplicate_rows": int(duplicate.sum()), "note": "No flagged duplicates or too few retained rows"}])
    duplicate_study.to_csv(args.output / "duplicate_sensitivity.csv", index=False)

    # Review template: examples from largest, most heavily flagged groups, and noise.
    selected = []
    cluster_targets = existing.head(10)["cluster_id"].tolist() if len(existing) else []
    if len(existing):
        cluster_targets += existing.sort_values("review_flag_pct", ascending=False).head(5)["cluster_id"].tolist()
    cluster_targets = list(dict.fromkeys(cluster_targets))
    for cluster in cluster_targets:
        part = df.loc[df["dbscan_cluster"] == cluster]
        selected.extend(part.sample(n=min(4, len(part)), random_state=42)["attraction_id"].tolist())
    noise = df.loc[df["dbscan_cluster"] == -1]
    if not noise.empty:
        selected.extend(noise.sample(n=min(15, len(noise)), random_state=42)["attraction_id"].tolist())
    sample = df.loc[df["attraction_id"].isin(set(selected))].copy()
    cols = [c for c in ["attraction_id", "attraction_name", "district", "tourism_category", "latitude", "longitude", "dbscan_cluster", "review_required", "suspected_duplicate", "source_url"] if c in sample]
    sample = sample[cols]
    sample["google_maps_location"] = sample.apply(lambda r: f"https://www.google.com/maps?q={r['latitude']:.7f},{r['longitude']:.7f}", axis=1)
    sample["is_real_tourist_attraction"] = "pending"
    sample["coordinates_correct"] = "pending"
    sample["duplicate_assessment"] = "pending"
    sample["independent_evidence_url"] = ""
    sample["reviewer_notes"] = ""
    path = args.output / "manual_hotspot_validation_sample.csv"
    if path.exists():
        path = args.output / "manual_hotspot_validation_sample_NEW.csv"
    sample.to_csv(path, index=False, encoding="utf-8-sig")

    print("\n=== TRAVELMIND VALIDATION SUMMARY ===")
    print(quality.to_string(index=False))
    print("\nSaved reports to:", args.output.resolve())
    print("Manual validation sample:", path.name)
    print("CAUTION: Geographic clustering does not establish tourist popularity, demand, or tourism potential.")


if __name__ == "__main__":
    main()
