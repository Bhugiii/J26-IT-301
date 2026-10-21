"""Prepare reproducible Overture tourism place layers for TravelMind.

Usage from the *inner* TravelMind project root:
    python src/clustering/prepare_tourism_infrastructure_features.py

The original 8,590-record baseline and ML models are never changed.
Requires: pip install pandas pyarrow shapely
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
import math

import pandas as pd
from shapely import wkb
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/external/overture/sri_lanka_places.parquet"
BOUNDARY = ROOT / "data/boundaries/sri_lanka_districts.geojson"
OUTPUT = ROOT / "data/processed/overture_tourism"

# Only *exact* basic_category values. No substring matching: for example,
# 'garden' must not accidentally include 'hardware_home_and_garden_store'.
ATTRACTION_CATEGORIES = {
    "historic_site": "heritage", "museum": "heritage",
    "archaeological_site": "heritage", "cultural_attraction": "heritage",
    "buddhist_place_of_worship": "religious_and_cultural",
    "hindu_place_of_worship": "religious_and_cultural",
    "christian_place_of_worship": "religious_and_cultural",
    "muslim_place_of_worship": "religious_and_cultural",
    "place_of_worship": "religious_and_cultural",
    "beach": "nature_and_outdoors", "park": "nature_and_outdoors",
    "national_park": "nature_and_outdoors", "nature_reserve": "nature_and_outdoors",
    "mountain": "nature_and_outdoors", "waterfall": "nature_and_outdoors",
    "lake": "nature_and_outdoors", "garden": "nature_and_outdoors",
    "geographic_entities": "nature_and_outdoors",
    "animal_attraction": "attraction_and_recreation", "aquarium": "attraction_and_recreation",
    "zoo": "attraction_and_recreation", "amusement_park": "attraction_and_recreation",
    "amusement_attraction": "attraction_and_recreation",
}
SERVICE_CATEGORIES = {
    "hotel": "accommodation", "resort": "accommodation",
    "lodging": "accommodation", "private_lodging": "accommodation",
    "bed_and_breakfast": "accommodation", "hostel": "accommodation",
    "guest_house": "accommodation", "campground": "accommodation",
    "rv_park": "accommodation",
    "restaurant": "food_and_drink", "fast_food_restaurant": "food_and_drink",
    "casual_eatery": "food_and_drink", "cafe": "food_and_drink",
    "coffee_shop": "food_and_drink", "tea_house": "food_and_drink",
    "travel_service": "travel_support", "travel_and_transportation": "travel_support",
    "tour_operator": "travel_support", "tourist_information_center": "travel_support",
}


def primary_name(value):
    if isinstance(value, dict):
        return str(value.get("primary") or "").strip()
    return ""


def source_datasets(value):
    if not isinstance(value, (list, tuple)):
        return ""
    names = sorted({str(row.get("dataset", "")).strip() for row in value if isinstance(row, dict) and row.get("dataset")})
    return " | ".join(names)


def source_licenses(value):
    if not isinstance(value, (list, tuple)):
        return ""
    licenses = sorted({str(row.get("license", "")).strip() for row in value if isinstance(row, dict) and row.get("license")})
    return " | ".join(licenses)


def load_boundary():
    if not BOUNDARY.is_file():
        raise FileNotFoundError(f"Required district boundary file missing: {BOUNDARY}")
    obj = json.loads(BOUNDARY.read_text(encoding="utf-8-sig"))
    features = obj.get("features", [])
    polygons = [shape(f["geometry"]) for f in features if f.get("geometry")]
    if not polygons:
        raise ValueError("No geometries in the district boundaries GeoJSON")
    union = unary_union(polygons)
    if not union.is_valid:
        union = union.buffer(0)
    return prep(union), union


def safe_location(blob):
    if blob is None:
        return None
    try:
        geom = wkb.loads(blob)
        if geom.is_empty:
            return None
        point = geom if geom.geom_type == "Point" else geom.representative_point()
        x, y = float(point.x), float(point.y)
        if not (79.0 <= x <= 83.0 and 5.0 <= y <= 11.0):
            return None
        return point
    except (ValueError, TypeError, Exception):
        return None


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Missing Overture input: {SOURCE}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    country, _ = load_boundary()
    df = pd.read_parquet(SOURCE, columns=["id", "geometry", "names", "basic_category", "confidence", "sources", "operating_status"])
    original_count = len(df)
    df["basic_category"] = df["basic_category"].fillna("").astype(str).str.strip().str.lower()
    df["place_role"] = df["basic_category"].map(lambda c: "attraction_candidate" if c in ATTRACTION_CATEGORIES else ("tourist_service" if c in SERVICE_CATEGORIES else "other"))
    role_counts = df["place_role"].value_counts().to_dict()
    selected = df[df["place_role"].ne("other")].copy()
    selected["tourism_group"] = selected.apply(lambda r: (ATTRACTION_CATEGORIES if r["place_role"] == "attraction_candidate" else SERVICE_CATEGORIES).get(r["basic_category"], "other"), axis=1)
    selected["place_name"] = selected["names"].map(primary_name)
    selected = selected[selected["place_name"].str.len().ge(3)].copy()
    selected["location_point"] = selected["geometry"].map(safe_location)
    selected = selected[selected["location_point"].notna()].copy()
    selected = selected[selected["location_point"].map(country.covers)].copy()
    selected["latitude"] = selected["location_point"].map(lambda p: p.y)
    selected["longitude"] = selected["location_point"].map(lambda p: p.x)
    selected["source_datasets"] = selected["sources"].map(source_datasets)
    selected["source_licenses"] = selected["sources"].map(source_licenses)
    selected["confidence"] = pd.to_numeric(selected["confidence"], errors="coerce")
    selected["operating_status"] = selected["operating_status"].fillna("unknown").astype(str)
    # Duplicate indicators are for investigation only; don't automatically merge names.
    selected["name_key"] = selected["place_name"].str.casefold().str.replace(r"\s+", " ", regex=True).str.strip()
    selected["nearby_same_name_review"] = selected.duplicated(["name_key", "basic_category"], keep=False)
    columns = ["id", "place_name", "basic_category", "tourism_group", "latitude", "longitude", "confidence", "operating_status", "source_datasets", "source_licenses", "nearby_same_name_review"]
    a = selected[selected["place_role"].eq("attraction_candidate")][columns].rename(columns={"id": "overture_id"})
    s = selected[selected["place_role"].eq("tourist_service")][columns].rename(columns={"id": "overture_id"})
    a.to_csv(OUTPUT / "overture_attraction_candidates.csv", index=False, encoding="utf-8-sig")
    s.to_csv(OUTPUT / "overture_tourist_services.csv", index=False, encoding="utf-8-sig")
    group_counts = selected.groupby(["place_role", "tourism_group"]).size().sort_values(ascending=False)
    group_counts.rename("records").reset_index().to_csv(OUTPUT / "overture_tourism_category_summary.csv", index=False)
    info = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "input_file": str(SOURCE.relative_to(ROOT)),
        "input_records": int(original_count),
        "role_counts_before_name_geometry_boundary_checks": {k:int(v) for k,v in role_counts.items()},
        "attraction_candidates_after_checks": len(a),
        "services_after_checks": len(s),
        "boundary_source": str(BOUNDARY.relative_to(ROOT)),
        "boundary_method": "representative_point within union of district polygons",
        "deduplication": "none; same-name indicator is an audit flag only",
        "interpretation": "Mapped place candidates, not verified attractions, business operations, popularity or visitation",
        "provenance_warning": "Check per-record source_licenses and Overture publication terms before redistribution."
    }
    (OUTPUT / "processing_summary.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"Source records: {original_count:,}")
    print(f"Category-matched (before location checks): {len(df[df.place_role.ne('other')]):,}")
    print(f"Attraction candidates inside Sri Lanka boundaries: {len(a):,}")
    print(f"Tourist services inside Sri Lanka boundaries: {len(s):,}")
    print(f"Output folder: {OUTPUT}")
    print("Important: Counts are provisional and these rows are NOT independently verified.")


if __name__ == "__main__":
    main()
