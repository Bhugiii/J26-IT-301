
from pathlib import Path
import json

import pandas as pd

# Find the project folder automatically.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "results" / "reports"

REPORT_DIR.mkdir(parents=True, exist_ok=True)

# Load the four model output files.
kmeans_data = pd.read_csv(
    DATA_DIR / "travelmind_kmeans_results.csv"
)

dbscan_data = pd.read_csv(
    DATA_DIR / "travelmind_dbscan_results.csv"
)

kmeans_eval = pd.read_csv(
    REPORT_DIR / "kmeans_evaluation.csv"
)

dbscan_eval = pd.read_csv(
    REPORT_DIR / "dbscan_evaluation.csv"
)

# Check that model predictions exist.
if "kmeans_cluster" not in kmeans_data.columns:
    raise ValueError(
        "K-Means CSV does not contain kmeans_cluster."
    )

if "dbscan_cluster" not in dbscan_data.columns:
    raise ValueError(
        "DBSCAN CSV does not contain dbscan_cluster."
    )

# Verify that both files refer to the same attractions.
id_column = "attraction_id"

for data, model_name in [
    (kmeans_data, "K-Means"),
    (dbscan_data, "DBSCAN"),
]:
    if id_column not in data.columns:
        raise ValueError(
            f"{model_name} CSV is missing attraction_id."
        )

    if data[id_column].isna().any():
        raise ValueError(
            f"{model_name} has missing attraction IDs."
        )

    if data[id_column].duplicated().any():
        raise ValueError(
            f"{model_name} has duplicate attraction IDs."
        )

km_ids = set(kmeans_data[id_column].astype(str))
db_ids = set(dbscan_data[id_column].astype(str))

if km_ids != db_ids:
    raise ValueError(
        "The two models do not contain the same "
        "attraction IDs. Review the input files."
    )


# Combine predictions using attraction IDs.
# Remove any previously saved DBSCAN labels from
# the K-Means file to avoid duplicate column names.

combined = kmeans_data.drop(
    columns=["dbscan_cluster"],
    errors="ignore"
).copy()

combined = combined.merge(
    dbscan_data[
        [id_column, "dbscan_cluster"]
    ],
    on=id_column,
    how="inner",
    validate="one_to_one"
)

print("Merged cluster columns:")
print(
    combined[
        ["attraction_id", "kmeans_cluster", "dbscan_cluster"]
    ].head()
)


combined["kmeans_cluster"] = pd.to_numeric(
    combined["kmeans_cluster"],
    errors="raise"
).astype(int)

combined["dbscan_cluster"] = pd.to_numeric(
    combined["dbscan_cluster"],
    errors="raise"
).astype(int)

# Compare the actual saved cluster assignments.
kmeans_clusters = combined["kmeans_cluster"].nunique()

dbscan_clusters = combined.loc[
    combined["dbscan_cluster"] != -1,
    "dbscan_cluster"
].nunique()

dbscan_noise = int(
    (combined["dbscan_cluster"] == -1).sum()
)

total_records = len(combined)

dbscan_coverage = (
    (total_records - dbscan_noise)
    / total_records * 100
)

# Reference rows from the evaluation tables.
km_selected = kmeans_eval.loc[
    kmeans_eval["k"] == 6
]

db_selected = dbscan_eval.loc[
    (dbscan_eval["eps_km"] == 2)
    & (dbscan_eval["min_samples"] == 5)
]

if km_selected.empty or db_selected.empty:
    raise ValueError(
        "The expected evaluation configuration is missing."
    )

km_metrics = km_selected.iloc[0]
db_metrics = db_selected.iloc[0]

# Check whether the saved predictions match the
# parameter configurations selected for comparison.
if kmeans_clusters != 6:
    raise ValueError(
        "Saved K-Means predictions do not have six clusters. "
        "Check which K was used to export the CSV."
    )

if (
    dbscan_clusters != int(db_metrics["n_clusters"])
    or dbscan_noise != int(db_metrics["noise_points"])
):
    raise ValueError(
        "Saved DBSCAN predictions do not match the "
        "2 km / min_samples=5 evaluation. "
        "Check which parameters were used to export the CSV."
    )

# Create model comparison table.
comparison = pd.DataFrame([
    {
        "model": "K-Means",
        "parameters": "k=6",
        "n_clusters": kmeans_clusters,
        "noise_points": 0,
        "coverage_percentage": 100.0,
        "silhouette_score": km_metrics["silhouette_score"],
        "davies_bouldin_index":
            km_metrics["davies_bouldin_index"],
    },
    {
        "model": "DBSCAN",
        "parameters": "eps=2km, min_samples=5",
        "n_clusters": dbscan_clusters,
        "noise_points": dbscan_noise,
        "coverage_percentage": round(dbscan_coverage, 2),
        "silhouette_score": db_metrics["silhouette_score"],
        "davies_bouldin_index":
            db_metrics["davies_bouldin_index"],
    }
])

# Summarize the size of every cluster.
kmeans_sizes = (
    combined.groupby("kmeans_cluster")
    .size()
    .reset_index(name="attraction_count")
    .rename(columns={"kmeans_cluster": "cluster_id"})
)
kmeans_sizes.insert(0, "model", "K-Means")

dbscan_sizes = (
    combined.loc[combined["dbscan_cluster"] != -1]
    .groupby("dbscan_cluster")
    .size()
    .reset_index(name="attraction_count")
    .rename(columns={"dbscan_cluster": "cluster_id"})
)
dbscan_sizes.insert(0, "model", "DBSCAN")

cluster_sizes = pd.concat(
    [kmeans_sizes, dbscan_sizes],
    ignore_index=True
)

# Export results.
comparison.to_csv(
    REPORT_DIR / "model_comparison.csv",
    index=False
)

cluster_sizes.to_csv(
    REPORT_DIR / "cluster_size_comparison.csv",
    index=False
)

combined.to_csv(
    DATA_DIR / "travelmind_combined_clusters.csv",
    index=False
)

# Display results.
print("\nTRAVELMIND - MODEL COMPARISON")
print("=" * 60)
print(comparison.to_string(index=False))

print("\nTOP 10 LARGEST DBSCAN CLUSTERS")
print(
    dbscan_sizes.sort_values(
        "attraction_count",
        ascending=False
    ).head(10).to_string(index=False)
)

print("\nSaved:")
print(REPORT_DIR / "model_comparison.csv")
print(REPORT_DIR / "cluster_size_comparison.csv")
print(DATA_DIR / "travelmind_combined_clusters.csv")

print("\nStep 10 model comparison completed!")
