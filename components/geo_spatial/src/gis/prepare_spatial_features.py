"""TravelMind: spatial feature preparation from the ML-ready attraction CSV.

Run from anywhere:
    python src/gis/prepare_spatial_features.py

Dependencies: pandas numpy scikit-learn
Input: data/processed/travelmind_ml_ready.csv
Output: data/processed/travelmind_spatial_features.csv
        results/reports/spatial_feature_report.json

Distances are great-circle (haversine) in kilometres. Nearby counts exclude
self and include other records, even suspected duplicates; compare with a
reviewed dataset later to assess sensitivity to duplicate mapping.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

ROOT = Path(__file__).resolve().parents[2]
EARTH_RADIUS_KM = 6371.0088


def prepare(input_path: Path, output_path: Path, report_path: Path, radius_km: float):
    if not input_path.is_file():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")
    df = pd.read_csv(input_path, dtype={"attraction_id": "string"}, low_memory=False)
    required = {"attraction_id", "latitude", "longitude", "district"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError("Missing required CSV columns: " + ", ".join(sorted(missing)))
    original_count = len(df)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    valid = (df["latitude"].between(5.8, 9.9) & df["longitude"].between(79.5, 82.1)
             & df["district"].notna() & df["district"].astype(str).str.strip().ne(""))
    invalid_count = int((~valid).sum())
    df = df.loc[valid].copy().reset_index(drop=True)
    if df.empty:
        raise ValueError("No records with usable Sri Lankan coordinates and district names.")
    if df["attraction_id"].duplicated().any():
        raise ValueError("Duplicate attraction IDs detected; inspect source before feature engineering.")

    coords_rad = np.radians(df[["latitude", "longitude"]].to_numpy(dtype=float))
    tree = BallTree(coords_rad, metric="haversine")
    # Subtract the current observation only, not neighboring observations at identical coordinates.
    radius_rad = radius_km / EARTH_RADIUS_KM
    df[f"nearby_count_{str(radius_km).replace('.', '_')}km"] = (
        tree.query_radius(coords_rad, r=radius_rad, count_only=True) - 1
    ).astype(int)
    if len(df) > 1:
        distance, index = tree.query(coords_rad, k=2)
        df["nearest_neighbor_km"] = distance[:, 1] * EARTH_RADIUS_KM
        df["nearest_neighbor_attraction_id"] = df.iloc[index[:, 1]]["attraction_id"].to_numpy()
    else:
        df["nearest_neighbor_km"] = np.nan
        df["nearest_neighbor_attraction_id"] = ""

    # These are spatial descriptors, not proxies for visitor numbers.
    df["spatial_feature_radius_km"] = radius_km
    df["spatial_feature_method"] = "haversine_BallTree"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    count_column = f"nearby_count_{str(radius_km).replace('.', '_')}km"
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_file": str(input_path),
        "output_file": str(output_path),
        "original_records": original_count,
        "valid_spatial_records": len(df),
        "invalid_or_unassigned_records": invalid_count,
        "districts_present": int(df["district"].nunique()),
        "radius_km": radius_km,
        "average_neighbors_within_radius": round(float(df[count_column].mean()), 3),
        "median_neighbors_within_radius": float(df[count_column].median()),
        "method": "Haversine distance via BallTree; all valid provisional records retained",
        "caution": "Counts represent mapped OSM features, not tourists or verified distinct attractions; possible duplicates may inflate local density."
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Saved CSV: {output_path}")
    print(f"Saved report: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Prepare TravelMind geographical features")
    parser.add_argument("--input", type=Path, default=ROOT / "data/processed/travelmind_ml_ready.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/travelmind_spatial_features.csv")
    parser.add_argument("--report", type=Path, default=ROOT / "results/reports/spatial_feature_report.json")
    parser.add_argument("--radius-km", type=float, default=2.0)
    args = parser.parse_args()
    if not np.isfinite(args.radius_km) or args.radius_km <= 0:
        parser.error("--radius-km must be a positive number")
    prepare(args.input, args.output, args.report, args.radius_km)


if __name__ == "__main__":
    main()
