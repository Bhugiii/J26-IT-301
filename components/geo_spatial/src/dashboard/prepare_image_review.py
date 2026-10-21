
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

MATCHES_FILE = (
    ROOT / "config"
    / "attraction_image_matches_validated.csv"
)

ATTRACTIONS_FILE = (
    ROOT / "data" / "processed"
    / "travelmind_hotspot_map_data.csv"
)

OUTPUT_FILE = (
    ROOT / "config"
    / "attraction_image_final_review.csv"
)

matches = pd.read_csv(
    MATCHES_FILE,
    encoding="utf-8-sig"
)

attractions = pd.read_csv(
    ATTRACTIONS_FILE,
    low_memory=False
)

required = [
    "attraction_id",
    "latitude",
    "longitude",
]

for column in required:
    if column not in attractions.columns:
        raise ValueError(
            f"Missing attraction column: {column}"
        )

if "attraction_id" not in matches.columns:
    raise ValueError(
        "Matched photographs must include attraction_id."
    )

# Join coordinates to the matched attraction IDs.
locations = attractions[
    ["attraction_id", "latitude", "longitude"]
].copy()

if locations["attraction_id"].duplicated().any():
    raise ValueError(
        "Duplicate attraction IDs in source dataset."
    )

review = matches.merge(
    locations,
    on="attraction_id",
    how="left",
    validate="many_to_one"
)

review["latitude"] = pd.to_numeric(
    review["latitude"],
    errors="coerce"
)

review["longitude"] = pd.to_numeric(
    review["longitude"],
    errors="coerce"
)

def make_maps_url(row):
    if pd.isna(row["latitude"]) or pd.isna(row["longitude"]):
        return ""

    return (
        "https://www.google.com/maps?q="
        f"{row['latitude']},{row['longitude']}"
    )

review["google_maps_location"] = review.apply(
    make_maps_url,
    axis=1
)

# Preserve previous review decisions if the file exists.
if OUTPUT_FILE.exists():
    previous = pd.read_csv(
        OUTPUT_FILE,
        encoding="utf-8-sig"
    ).fillna("")

    if "final_image_decision" in previous.columns:
        previous_decisions = previous[
            [
                "attraction_id",
                "image_file",
                "final_image_decision",
            ]
        ].drop_duplicates(
            subset=["attraction_id", "image_file"],
            keep="last"
        )

        review = review.merge(
            previous_decisions,
            on=["attraction_id", "image_file"],
            how="left"
        )

if "final_image_decision" not in review.columns:
    review["final_image_decision"] = ""

review["final_image_decision"] = (
    review["final_image_decision"].fillna("")
)

# Blank decisions require manual verification.
review["final_image_decision"] = (
    review["final_image_decision"]
    .astype(str)
    .str.strip()
    .str.lower()
)

allowed = ["", "approved", "rejected"]

if not review["final_image_decision"].isin(allowed).all():
    raise ValueError(
        "Final decisions must be blank, approved or rejected."
    )

review = review.sort_values(
    ["location_match_status", "dataset_attraction_name"]
)

review.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig"
)

print("\nTRAVELMIND - FINAL IMAGE MATCH REVIEW")
print("=" * 60)

print("Attraction-image candidates:", len(review))

print("\nLocation validation:")
print(
    review["location_match_status"]
    .value_counts()
    .to_string()
)

print("\nFinal image decisions:")
print(
    review["final_image_decision"]
    .replace("", "pending")
    .value_counts()
    .to_string()
)

print("\nReview file saved:")
print(OUTPUT_FILE)

