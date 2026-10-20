
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

DATA_FILE = (
    ROOT / "data" / "processed"
    / "travelmind_combined_clusters.csv"
)

REPORT_DIR = ROOT / "results" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA_FILE)

df["dbscan_cluster"] = pd.to_numeric(
    df["dbscan_cluster"], errors="raise"
).astype(int)

# Exclude DBSCAN noise (-1).
clustered = df[df["dbscan_cluster"] != -1].copy()

# Identify the 15 largest clusters.
top_clusters = (
    clustered["dbscan_cluster"]
    .value_counts()
    .head(15)
    .index
    .tolist()
)

report_rows = []

for cluster_id in top_clusters:

    group = clustered[
        clustered["dbscan_cluster"] == cluster_id
    ].copy()

    # District distribution.
    district_counts = (
        group["district"]
        .fillna("Unknown")
        .value_counts()
    )

    district_summary = "; ".join(
        f"{name}: {count}"
        for name, count in district_counts.items()
    )

    # Tourism category distribution.
    category_counts = (
        group["tourism_category"]
        .fillna("Unknown")
        .value_counts()
    )

    category_summary = "; ".join(
        f"{name}: {count}"
        for name, count in category_counts.head(5).items()
    )

    # Previously flagged suspected duplicates.
    if "suspected_duplicate" in group.columns:
        duplicate_mask = (
            group["suspected_duplicate"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(["true", "1", "yes"])
        )
        duplicate_count = int(duplicate_mask.sum())
    else:
        duplicate_count = 0

    # Records needing review.
    if "review_required" in group.columns:
        review_mask = (
            group["review_required"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(["true", "1", "yes"])
        )
        review_count = int(review_mask.sum())
    else:
        review_count = 0

    report_rows.append({
        "cluster_id": cluster_id,
        "attraction_count": len(group),
        "district_count": district_counts.size,
        "district_distribution": district_summary,
        "top_categories": category_summary,
        "suspected_duplicate_count": duplicate_count,
        "review_required_count": review_count,
        "review_required_percentage": round(
            review_count / len(group) * 100, 2
        ),
    })

report = pd.DataFrame(report_rows)

report = report.sort_values(
    "attraction_count", ascending=False
)

output_path = (
    REPORT_DIR / "hotspot_validation_report.csv"
)

report.to_csv(output_path, index=False)

print("\nTRAVELMIND - HOTSPOT VALIDATION REPORT")
print("=" * 75)

print(
    report[
        [
            "cluster_id",
            "attraction_count",
            "district_count",
            "suspected_duplicate_count",
            "review_required_count",
            "review_required_percentage",
        ]
    ].to_string(index=False)
)

print("\nDISTRICT AND CATEGORY DETAILS")
print("=" * 75)

for row in report.itertuples():
    print(f"\nCluster {row.cluster_id}")
    print(f"Attractions: {row.attraction_count}")
    print(f"Districts: {row.district_distribution}")
    print(f"Top categories: {row.top_categories}")

print("\nSaved:", output_path)
print("Step 11.4 completed successfully!")
