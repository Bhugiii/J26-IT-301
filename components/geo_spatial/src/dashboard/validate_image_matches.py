
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    ROOT / "config"
    / "attraction_image_matches.csv"
)

OUTPUT_FILE = (
    ROOT / "config"
    / "attraction_image_matches_validated.csv"
)

# Expected districts for selected attractions.
# Extend this dictionary as new matches are reviewed.
EXPECTED_DISTRICTS = {
    "Gangaramaya Temple": {"Colombo"},
    "Galle Face Green": {"Colombo"},
    "Negombo Dutch Fort": {"Gampaha"},
    "Kalutara Bodhiya": {"Kalutara"},
    "Hummanaya Blow Hole": {"Hambantota"},
    "Dambulla Cave Temple": {"Matale"},
    "Ravana Falls": {"Badulla"},
    "Little Adam's Peak": {"Badulla"},
    "Ella Rock": {"Badulla"},
    "Diyaluma Falls": {"Badulla"},
    "Dunhinda Falls": {"Badulla"},
    "Hakgala Botanical Garden": {"Nuwara Eliya"},
    "Pinnawala Elephant Orphanage": {"Kegalle"},
    "Jaya Sri Maha Bodhi": {"Anuradhapura"},
    "Medirigiriya Vatadage": {"Polonnaruwa"},
}

df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig"
).fillna("")

def validate_match(row):
    name = str(row["photo_attraction_name"]).strip()
    district = str(row["district"]).strip()

    allowed = EXPECTED_DISTRICTS.get(name)

    if allowed is None:
        return "needs_location_review"

    if district in allowed:
        return "district_consistent"

    return "district_mismatch"


df["location_match_status"] = df.apply(
    validate_match,
    axis=1
)

# Even if a district is consistent, identical
# attraction names can refer to multiple locations.
# Therefore, retain matching as a candidate until
# an attraction ID/location is individually verified.
df["dashboard_image_approved"] = False

df.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig"
)

print("\nTRAVELMIND - IMAGE LOCATION VALIDATION")
print("=" * 60)

print(
    df["location_match_status"]
    .value_counts()
    .to_string()
)

print("\nMATCHES REQUIRING MORE REVIEW")
print(
    df[df["location_match_status"] != "district_consistent"][
        [
            "dataset_attraction_name",
            "district",
            "image_file",
            "location_match_status",
        ]
    ].to_string(index=False)
)

print("\nSaved:", OUTPUT_FILE)
print(
    "\nDistrict consistency is a screening check, "
    "not proof of an exact location match."
)
