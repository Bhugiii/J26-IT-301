
from pathlib import Path
import pandas as pd
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[2]

PHOTO_CSV = (
    ROOT / "config"
    / "attraction_image_candidates.csv"
)

ATTRACTION_CSV = (
    ROOT / "data"
    / "processed"
    / "travelmind_hotspot_map_data.csv"
)

OUTPUT_CSV = (
    ROOT / "config"
    / "attraction_image_matches.csv"
)

IMAGE_DIR = (
    ROOT / "assets"
    / "images"
    / "attractions"
)


def normalize_name(name):
    name = unicodedata.normalize(
        "NFKC", str(name)
    ).casefold().strip()

    return re.sub(
        r"[^\w]+", " ", name
    ).strip()


photos = pd.read_csv(
    PHOTO_CSV, encoding="utf-8-sig"
).fillna("")

attractions = pd.read_csv(
    ATTRACTION_CSV, low_memory=False
).fillna("")

required_photo_cols = [
    "attraction_name",
    "image_file",
    "review_status",
]

required_attraction_cols = [
    "attraction_id",
    "attraction_name",
    "district",
]

for col in required_photo_cols:
    if col not in photos.columns:
        raise ValueError(f"Photo CSV missing: {col}")

for col in required_attraction_cols:
    if col not in attractions.columns:
        raise ValueError(f"Attraction CSV missing: {col}")

photos = photos[
    photos["review_status"]
    .astype(str)
    .str.lower()
    .str.strip()
    == "approved"
].copy()

photos["normalized_name"] = (
    photos["attraction_name"].map(normalize_name)
)

attractions["normalized_name"] = (
    attractions["attraction_name"].map(normalize_name)
)

matched_rows = []

for photo in photos.itertuples():

    image_filename = str(photo.image_file)

    if Path(image_filename).name != image_filename:
        continue

    if not (IMAGE_DIR / image_filename).is_file():
        continue

    matches = attractions[
        attractions["normalized_name"]
        == photo.normalized_name
    ]

    for attraction in matches.itertuples():

        matched_rows.append({
            "attraction_id": attraction.attraction_id,
            "dataset_attraction_name":
                attraction.attraction_name,
            "district": attraction.district,
            "photo_attraction_name":
                photo.attraction_name,
            "image_file": image_filename,
            "match_type": "normalized_exact_name",
            "review_status": "approved",
            "source_page": getattr(
                photo, "source_page", ""
            ),
            "creator": getattr(
                photo, "creator", ""
            ),
            "license": getattr(
                photo, "license", ""
            ),
            "license_url": getattr(
                photo, "license_url", ""
            ),
        })


columns = [
    "attraction_id",
    "dataset_attraction_name",
    "district",
    "photo_attraction_name",
    "image_file",
    "match_type",
    "review_status",
    "source_page",
    "creator",
    "license",
    "license_url",
]

results = pd.DataFrame(
    matched_rows, columns=columns
)

results.to_csv(
    OUTPUT_CSV,
    index=False,
    encoding="utf-8-sig"
)

print("\nTRAVELMIND - IMAGE MATCHING")
print("=" * 55)

print("Approved photographs:", len(photos))
print("Dataset attractions:", len(attractions))
print("Exact-name matches:", len(results))

print("\nMATCHED ATTRACTIONS")

if not results.empty:
    print(
        results[
            [
                "dataset_attraction_name",
                "district",
                "image_file",
            ]
        ].head(20).to_string(index=False)
    )

print("\nSaved:", OUTPUT_CSV)

print(
    "\nOnly exact normalized names have been matched. "
    "Different-name aliases require manual checking."
)
