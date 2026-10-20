
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data" / "processed"
REPORT_DIR = ROOT / "results" / "reports"

DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

source = pd.read_csv(
    DATA_DIR / "travelmind_combined_clusters.csv"
)

required = [
    "attraction_id",
    "attraction_name",
    "latitude",
    "longitude",
    "district",
    "dbscan_cluster",
]

missing = [c for c in required if c not in source.columns]

if missing:
    raise ValueError(f"Missing required columns: {missing}")

source["dbscan_cluster"] = pd.to_numeric(
    source["dbscan_cluster"], errors="raise"
).astype(int)

source["latitude"] = pd.to_numeric(
    source["latitude"], errors="coerce"
)

source["longitude"] = pd.to_numeric(
    source["longitude"], errors="coerce"
)

# Validate geographic coordinates.
valid_coordinates = (
    source["latitude"].between(-90, 90)
    & source["longitude"].between(-180, 180)
)

if not valid_coordinates.all():
    raise ValueError(
        "Some records have missing or invalid coordinates."
    )

# Normalize previous review flags.
def to_boolean_flags(frame, column):
    if column not in frame.columns:
        return pd.Series(
            False, index=frame.index, dtype=bool
        )

    return (
        frame[column]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes"])
    )


source["needs_review_flag"] = to_boolean_flags(
    source, "review_required"
)

source["duplicate_warning_flag"] = to_boolean_flags(
    source, "suspected_duplicate"
)

# Start with all clustered records.
clustered = source[
    source["dbscan_cluster"] != -1
].copy()

# Haversine distance from each point to
# the approximate center of its cluster.
def haversine_km(lat1, lon1, lat2, lon2):
    earth_radius = 6371.0088

    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2) ** 2
    )

    return (
        2 * earth_radius
        * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    )


# Summarize all clusters.
summary = (
    clustered.groupby("dbscan_cluster")
    .agg(
        attraction_count=("attraction_id", "size"),
        review_required_count=("needs_review_flag", "sum"),
        duplicate_warning_count=(
            "duplicate_warning_flag", "sum"
        ),
        district_count=("district", "nunique"),
        center_latitude=("latitude", "mean"),
        center_longitude=("longitude", "mean"),
    )
    .reset_index()
)

summary["review_required_percentage"] = (
    100
    * summary["review_required_count"]
    / summary["attraction_count"]
).round(2)

summary["duplicate_warning_percentage"] = (
    100
    * summary["duplicate_warning_count"]
    / summary["attraction_count"]
).round(2)

# Add a representative district.
def most_common(series):
    counts = (
        series.dropna()
        .astype(str)
        .value_counts()
    )
    return counts.index[0] if len(counts) else "Unknown"


districts = (
    clustered.groupby("dbscan_cluster")["district"]
    .agg(most_common)
    .reset_index(name="main_district")
)

summary = summary.merge(
    districts, on="dbscan_cluster", validate="one_to_one"
)

# Measure approximate spatial spread.
points = clustered.merge(
    summary[
        [
            "dbscan_cluster",
            "center_latitude",
            "center_longitude",
        ]
    ],
    on="dbscan_cluster",
    validate="many_to_one",
)

points["distance_from_center_km"] = haversine_km(
    points["latitude"].to_numpy(),
    points["longitude"].to_numpy(),
    points["center_latitude"].to_numpy(),
    points["center_longitude"].to_numpy(),
)

spread = (
    points.groupby("dbscan_cluster")[
        "distance_from_center_km"
    ]
    .max()
    .reset_index(name="max_center_distance_km")
)

summary = summary.merge(
    spread, on="dbscan_cluster", validate="one_to_one"
)

summary["max_center_distance_km"] = (
    summary["max_center_distance_km"].round(2)
)

# Candidate priority reflects record count only.
# It does not indicate validated tourism potential.
summary = summary.sort_values(
    ["attraction_count", "dbscan_cluster"],
    ascending=[False, True]
).reset_index(drop=True)

summary["candidate_count_rank"] = (
    np.arange(len(summary)) + 1
)

# Data quality labels are advisory, not verification.
def quality_warning(row):
    if row["review_required_percentage"] >= 50:
        return "High review workload"
    if row["review_required_percentage"] > 0:
        return "Some records need review"
    return "No existing review flags"

summary["quality_warning"] = summary.apply(
    quality_warning, axis=1
)

# Add cluster summary to individual attraction records.
map_data = source.merge(
    summary[
        [
            "dbscan_cluster",
            "attraction_count",
            "main_district",
            "candidate_count_rank",
            "quality_warning",
            "max_center_distance_km",
        ]
    ],
    on="dbscan_cluster",
    how="left",
    validate="many_to_one"
)

map_data["map_status"] = np.where(
    map_data["dbscan_cluster"] == -1,
    "Isolated / DBSCAN noise",
    "Candidate attraction cluster"
)

# Export two files:
summary_file = (
    REPORT_DIR / "travelmind_hotspot_summary.csv"
)

map_file = (
    DATA_DIR / "travelmind_hotspot_map_data.csv"
)

summary.to_csv(summary_file, index=False)
map_data.to_csv(map_file, index=False)

print("\nTRAVELMIND - HOTSPOT MAP DATA")
print("=" * 65)

print("All attraction records:", len(map_data))
print("Candidate clusters:", len(summary))
print(
    "Clustered records:",
    (map_data["dbscan_cluster"] != -1).sum()
)
print(
    "Noise records:",
    (map_data["dbscan_cluster"] == -1).sum()
)

print("\nTOP 10 CLUSTER CANDIDATES")
print(
    summary[
        [
            "candidate_count_rank",
            "dbscan_cluster",
            "main_district",
            "attraction_count",
            "review_required_percentage",
            "max_center_distance_km",
            "quality_warning",
        ]
    ].head(10).to_string(index=False)
)

print("\nSaved:", summary_file)
print("Saved:", map_file)
print("\nStep 11.5 completed successfully!")
