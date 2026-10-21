"""TravelMind: exploratory clustering of mapped tourism infrastructure.

Run from the TravelMind project root:
    python src/clustering/train_tourism_infrastructure_clusters.py

Requires: pandas numpy scikit-learn
Input:
    data/processed/tourism_infrastructure/tourism_infrastructure_grid_5km.csv
Outputs:
    results/reports/infrastructure_clustering/

This model describes categories/counts of mapped POIs, NOT tourist demand,
quality, accessibility, popularity, verified sites, or AHP tourism potential.
Original 8,590-record clustering outputs and dashboard are not modified.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/processed/tourism_infrastructure/tourism_infrastructure_grid_5km.csv"
OUT = ROOT / "results/reports/infrastructure_clustering"
SEED = 42
K_VALUES = range(2, 9)
FEATURES = [
    "attraction_group_attraction_and_recreation_count",
    "attraction_group_heritage_count",
    "attraction_group_nature_and_outdoors_count",
    "attraction_group_religious_and_cultural_count",
    "service_group_accommodation_count",
    "service_group_food_and_drink_count",
    "service_group_travel_support_count",
]


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(f"Grid CSV not found: {INPUT}")
    OUT.mkdir(parents=True, exist_ok=True)
    grid = pd.read_csv(INPUT, low_memory=False)
    required = ["grid_id", "boundary_overlap_fraction", "attraction_count", "service_count", *FEATURES]
    missing = [x for x in required if x not in grid.columns]
    if missing:
        raise ValueError(f"Missing expected grid columns: {missing}")
    if grid.grid_id.isna().any() or grid.grid_id.duplicated().any():
        raise ValueError("grid_id must be present and unique")
    for col in required[1:]:
        grid[col] = pd.to_numeric(grid[col], errors="coerce")
    if grid[required[1:]].isna().any().any():
        raise ValueError("Missing or nonnumeric feature/count/overlap values")
    if (grid[FEATURES + ["attraction_count", "service_count"]] < 0).any().any():
        raise ValueError("Negative POI counts found")

    # Avoid poorly defined coastline slivers in the training sample.
    # Retain every original cell in the output for visualization/QA.
    enough_land = grid.boundary_overlap_fraction >= 0.50
    occupied = (grid.attraction_count + grid.service_count) > 0
    fit_mask = enough_land & occupied
    excluded_coastal = (~enough_land) & occupied
    empty = ~occupied
    X_raw = grid.loc[fit_mask, FEATURES].to_numpy(dtype=float)
    if X_raw.shape[0] < max(K_VALUES) + 1:
        raise ValueError(f"Only {len(X_raw)} training cells, too few for K range")
    if not np.isfinite(X_raw).all():
        raise ValueError("Nonfinite feature values")
    if (X_raw.sum(axis=1) == 0).any():
        raise ValueError("Some occupied cells have no category-group features; check preprocessing")

    # Count magnitudes are severely skewed (service max 1191, median 0).
    X_log = np.log1p(X_raw)
    scaler = StandardScaler()
    X = scaler.fit_transform(X_log)
    variable_columns = [FEATURES[i] for i in range(len(FEATURES)) if scaler.var_[i] > 0]
    if len(variable_columns) < 2:
        raise ValueError("Insufficient variation in training features")

    evaluations = []
    models = {}
    labels_by_k = {}
    for k in K_VALUES:
        model = KMeans(n_clusters=k, n_init=20, random_state=SEED, max_iter=400)
        labels = model.fit_predict(X)
        if len(np.unique(labels)) != k:
            print(f"Skipping k={k}: model produced fewer than k distinct clusters")
            continue
        silhouette = float(silhouette_score(X, labels, sample_size=min(len(X), 1200), random_state=SEED))
        dbi = float(davies_bouldin_score(X, labels))
        ch = float(calinski_harabasz_score(X, labels))
        # Seed sensitivity: identical input features, different initializations.
        # High ARI here indicates initialisation stability, not validity.
        stability_aris = []
        for other_seed in (17, 103, 211):
            comparison = KMeans(n_clusters=k, n_init=10, random_state=other_seed, max_iter=400)
            comparison_labels = comparison.fit_predict(X)
            stability_aris.append(float(adjusted_rand_score(labels, comparison_labels)))
        row = {
            "k": k,
            "training_cells": len(X),
            "silhouette_sampled": round(silhouette, 6),
            "davies_bouldin": round(dbi, 6),
            "calinski_harabasz": round(ch, 4),
            "initialization_ari_mean": round(float(np.mean(stability_aris)), 6),
            "initialization_ari_min": round(float(np.min(stability_aris)), 6),
            "smallest_cluster_cells": int(np.bincount(labels).min()),
            "largest_cluster_cells": int(np.bincount(labels).max()),
        }
        evaluations.append(row)
        models[k] = model
        labels_by_k[k] = labels
        print(f"k={k}: silhouette={silhouette:.3f}, DBI={dbi:.3f}, seed-ARI={np.mean(stability_aris):.3f}")
    if not evaluations:
        raise RuntimeError("No K-Means solutions were valid")
    evaluation = pd.DataFrame(evaluations)
    # Prefer a stable solution among near-best silhouettes, avoiding a fragile sole-metric choice.
    peak = evaluation.silhouette_sampled.max()
    near_best = evaluation.loc[evaluation.silhouette_sampled >= peak - 0.03].copy()
    near_best = near_best.sort_values(
        ["initialization_ari_mean", "silhouette_sampled", "k"],
        ascending=[False, False, True],
    )
    selected_k = int(near_best.iloc[0].k)
    grid["infrastructure_cluster"] = pd.Series(pd.NA, index=grid.index, dtype="Int64")
    grid.loc[fit_mask, "infrastructure_cluster"] = labels_by_k[selected_k]
    grid["infrastructure_analysis_status"] = np.select(
        [fit_mask, empty, excluded_coastal],
        ["clustered_occupied_cell", "no_selected_overture_pois", "coastal_sliver_excluded"],
        default="excluded_other",
    )
    # Keep all 2862 cells, including empty ones, for mapping and spatial QA.
    out_grid = OUT / "tourism_infrastructure_clustered_grid.csv"
    grid.to_csv(out_grid, index=False, encoding="utf-8")
    evaluation.to_csv(OUT / "tourism_infrastructure_k_evaluation.csv", index=False, encoding="utf-8")

    profiles = (
        grid.loc[fit_mask]
        .groupby("infrastructure_cluster")
        .agg(
            grid_cells=("grid_id", "size"),
            avg_attractions=("attraction_count", "mean"),
            median_attractions=("attraction_count", "median"),
            avg_services=("service_count", "mean"),
            median_services=("service_count", "median"),
            **{f"mean_{col}": (col, "mean") for col in FEATURES},
        )
        .reset_index()
    )
    profiles.to_csv(OUT / "tourism_infrastructure_cluster_profiles.csv", index=False, encoding="utf-8")

    info = {
        "source": str(INPUT.relative_to(ROOT)),
        "total_grid_cells": int(len(grid)),
        "occupied_cells": int(occupied.sum()),
        "empty_cells": int(empty.sum()),
        "occupied_coastal_slivers_excluded_from_fit": int(excluded_coastal.sum()),
        "training_cells": int(fit_mask.sum()),
        "minimum_boundary_overlap_for_fit": 0.5,
        "selected_k": selected_k,
        "selection_rule": "Among k with sampled silhouette within 0.03 of max, maximize mean seed ARI, then silhouette, then smaller k",
        "features": FEATURES,
        "transform": "log1p on counts, then StandardScaler fitted to training cells only",
        "silhouette_sample_size_max": 1200,
        "limitation": (
            "Clusters describe mapped Overture POI category counts, not verified attraction quality, "
            "tourist demand, popularity, accessibility or an AHP Tourism Potential Index. "
            "Empty cells reflect selected-source mapping coverage and excluded categories. "
            "Service and attraction candidate records may contain duplicates or errors."
        ),
    }
    (OUT / "tourism_infrastructure_model_summary.json").write_text(
        json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\nSelected K:", selected_k)
    print("Total cells:", len(grid))
    print("Training cells:", int(fit_mask.sum()))
    print("Empty cells (not model-fitted):", int(empty.sum()))
    print("Occupied coastal slivers excluded:", int(excluded_coastal.sum()))
    print("Outputs:", OUT)
    print("\nCluster profiles are numeric until interpreted against actual data; do not label them 'popular'.")


if __name__ == "__main__":
    main()
