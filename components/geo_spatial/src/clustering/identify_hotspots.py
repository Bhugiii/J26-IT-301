
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "travelmind_combined_clusters.csv"
)

OUTPUT_DIR = PROJECT_ROOT / "results" / "reports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(INPUT_FILE)

# Keep DBSCAN clustered records only.
# DBSCAN label -1 means noise, not a hotspot.
df["dbscan_cluster"] = pd.to_numeric(
    df["dbscan_cluster"],
    errors="raise"
)

clusters = df[df["dbscan_cluster"] != -1].copy()

# Convert coordinates to numeric values.
clusters["latitude"] = pd.to_numeric(
    clusters["latitude"],
    errors="coerce"
)

clusters["longitude"] = pd.to_numeric(
    clusters["longitude"],
    errors="coerce"
)

if clusters[["latitude", "longitude"]].isna().any().any():
    raise ValueError("Some clustered records have missing coordinates.")

# Summarize geographical and tourism characteristics.
summary = (
    clusters.groupby("dbscan_cluster")
    .agg(
        attraction_count=("attraction_id", "size"),
        district_count=("district", "nunique"),
        category_count=("tourism_category", "nunique"),
        center_latitude=("latitude", "mean"),
        center_longitude=("longitude", "mean"),
        min_latitude=("latitude", "min"),
        max_latitude=("latitude", "max"),
        min_longitude=("longitude", "min"),
        max_longitude=("longitude", "max"),
    )
    .reset_index()
)

# Most frequently occurring district in each cluster.
def most_common_value(series):
    values = series.dropna().astype(str)
    if values.empty:
        return "Unknown"
    return values.value_counts().index[0]

main_districts = (
    clusters.groupby("dbscan_cluster")["district"]
    .agg(most_common_value)
    .reset_index(name="main_district")
)

main_categories = (
    clusters.groupby("dbscan_cluster")["tourism_category"]
    .agg(most_common_value)
    .reset_index(name="main_category")
)

summary = summary.merge(
    main_districts,
    on="dbscan_cluster"
)

summary = summary.merge(
    main_categories,
    on="dbscan_cluster"
)

# Count records already flagged as suspected duplicates.
if "suspected_duplicate" in clusters.columns:
    duplicate_flags = (
        clusters["suspected_duplicate"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes"])
    )

    clusters["duplicate_flag"] = duplicate_flags

    duplicate_counts = (
        clusters.groupby("dbscan_cluster")["duplicate_flag"]
        .sum()
        .reset_index(name="suspected_duplicate_records")
    )

    summary = summary.merge(
        duplicate_counts,
        on="dbscan_cluster"
    )
else:
    summary["suspected_duplicate_records"] = 0

summary["suspected_duplicate_percentage"] = (
    100
    * summary["suspected_duplicate_records"]
    / summary["attraction_count"]
).round(2)

# Sort by mapped attraction count.
# This is a provisional concentration ranking,
# not a validated tourism potential ranking.
summary = summary.sort_values(
    "attraction_count",
    ascending=False
).reset_index(drop=True)

summary["record_count_rank"] = range(1, len(summary) + 1)

# Put the useful columns first.
first_columns = [
    "record_count_rank",
    "dbscan_cluster",
    "main_district",
    "attraction_count",
    "district_count",
    "main_category",
    "category_count",
    "suspected_duplicate_records",
    "suspected_duplicate_percentage",
    "center_latitude",
    "center_longitude",
]

other_columns = [
    col for col in summary.columns
    if col not in first_columns
]

summary = summary[first_columns + other_columns]

output_file = OUTPUT_DIR / "dbscan_hotspot_candidates.csv"

summary.to_csv(output_file, index=False)

print("\nTRAVELMIND - HOTSPOT CANDIDATE ANALYSIS")
print("=" * 70)

print("Total clustered attractions:", len(clusters))
print("Total candidate clusters:", len(summary))
print("Noise records:", len(df) - len(clusters))

print("\nTOP 15 CLUSTERS BY ATTRACTION COUNT")
print(
    summary[
        [
            "record_count_rank",
            "dbscan_cluster",
            "main_district",
            "attraction_count",
            "district_count",
            "main_category",
            "suspected_duplicate_percentage",
        ]
    ].head(15).to_string(index=False)
)

print("\nSaved:", output_file)
print("\nStep 11.1 completed successfully!")
