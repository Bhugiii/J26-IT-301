"""TravelMind: assign Sri Lanka district/province by polygon containment.

Run from project root:
    python src/preprocessing/assign_districts.py --download-boundaries

Requires: pip install requests shapely
Input: data/processed/travelmind_attractions.csv
Output: data/processed/travelmind_attractions_with_districts.csv
        data/processed/district_assignment_summary.csv
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import requests
from shapely.geometry import Point, shape
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parents[2]
INPUT_DEFAULT = ROOT / "data" / "processed" / "travelmind_attractions.csv"
BOUNDARIES_DEFAULT = ROOT / "data" / "boundaries" / "sri_lanka_districts.geojson"
OUTPUT_DEFAULT = ROOT / "data" / "processed" / "travelmind_attractions_with_districts.csv"
SUMMARY_DEFAULT = ROOT / "data" / "processed" / "district_assignment_summary.csv"
METADATA_API = "https://www.geoboundaries.org/api/current/gbOpen/LKA/ADM2/"

PROVINCES = {
    "Ampara": "Eastern", "Anuradhapura": "North Central", "Badulla": "Uva",
    "Batticaloa": "Eastern", "Colombo": "Western", "Galle": "Southern",
    "Gampaha": "Western", "Hambantota": "Southern", "Jaffna": "Northern",
    "Kalutara": "Western", "Kandy": "Central", "Kegalle": "Sabaragamuwa",
    "Kilinochchi": "Northern", "Kurunegala": "North Western", "Mannar": "Northern",
    "Matale": "Central", "Matara": "Southern", "Monaragala": "Uva",
    "Mullaitivu": "Northern", "Nuwara Eliya": "Central",
    "Polonnaruwa": "North Central", "Puttalam": "North Western",
    "Ratnapura": "Sabaragamuwa", "Trincomalee": "Eastern", "Vavuniya": "Northern"
}

# Only spelling variants of district names, not cities or neighboring locations.
ALIASES = {
    "kegalla": "Kegalle", "kilinochchi": "Kilinochchi",
    "kilinochchi district": "Kilinochchi", "mullaittivu": "Mullaitivu",
    "mullaitivu": "Mullaitivu", "moneragala": "Monaragala",
    "nuwaraeliya": "Nuwara Eliya", "nuwara eliya": "Nuwara Eliya",
    "polonnaruwa": "Polonnaruwa", "trincomalee": "Trincomalee",
    "vavuniya": "Vavuniya"
}

def normalize(value):
    s = str(value or "").strip().lower()
    s = re.sub(r"\b(district|distric|administrative district)\b", "", s)
    s = re.sub(r"[^a-z]+", " ", s)
    return " ".join(s.split())

NAME_LOOKUP = {normalize(n): n for n in PROVINCES}
NAME_LOOKUP.update({normalize(a): n for a, n in ALIASES.items()})


def download_boundaries(path):
    print("Downloading Sri Lanka ADM2 boundary metadata from geoBoundaries...")
    response = requests.get(METADATA_API, timeout=45, headers={"User-Agent": "TravelMindResearch/1.0"})
    response.raise_for_status()
    metadata = response.json()
    if int(metadata.get("admUnitCount", 0)) != 25:
        raise RuntimeError(f"Expected 25 districts; provider reports {metadata.get('admUnitCount')}")
    url = metadata.get("gjDownloadURL")
    if not url:
        raise RuntimeError("geoBoundaries metadata did not provide gjDownloadURL")
    data_response = requests.get(url, timeout=120, headers={"User-Agent": "TravelMindResearch/1.0"})
    data_response.raise_for_status()
    data = data_response.json()
    if data.get("type") != "FeatureCollection" or not data.get("features"):
        raise RuntimeError("Downloaded file is not valid feature-based GeoJSON")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"Downloaded {len(data['features'])} polygons to: {path}")
    print("Source: geoBoundaries gbOpen LKA ADM2. Verify research license and cite source.")


def load_polygons(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Use --download-boundaries first.")
    geojson = json.loads(path.read_text(encoding="utf-8"))
    result = []
    unknown = []
    for feat in geojson.get("features", []):
        props = feat.get("properties") or {}
        raw = props.get("shapeName") or props.get("name") or props.get("NAME_2") or ""
        name = NAME_LOOKUP.get(normalize(raw))
        if not name:
            unknown.append(raw)
            continue
        geom = shape(feat["geometry"])
        if geom.is_empty:
            continue
        if not geom.is_valid:
            geom = geom.buffer(0)
        result.append((name, PROVINCES[name], geom, prep(geom)))
    found = {r[0] for r in result}
    missing = set(PROVINCES) - found
    if missing or unknown:
        raise RuntimeError(
            "Boundary naming requires review before assignment.\n"
            f"Unrecognized shapes: {unknown}\nMissing districts: {sorted(missing)}\n"
            "Check 'shapeName' in the boundary GeoJSON; update ALIASES only for confirmed spellings."
        )
    if len(result) != 25:
        raise RuntimeError(f"Expected exactly 25 district polygons; found {len(result)}")
    return result


def assign(point, polygons):
    # covers includes locations lying exactly on a district boundary.
    matches = [(name, province) for name, province, geom, prepared in polygons if prepared.covers(point)]
    return matches[0] if len(matches) == 1 else ("", "")


def main():
    parser = argparse.ArgumentParser(description="Assign TravelMind district & province using GeoJSON polygon containment")
    parser.add_argument("--download-boundaries", action="store_true", help="Download open ADM2 GeoJSON once (requires internet)")
    parser.add_argument("--input", type=Path, default=INPUT_DEFAULT)
    parser.add_argument("--boundaries", type=Path, default=BOUNDARIES_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    if args.download_boundaries:
        download_boundaries(args.boundaries)
    polygons = load_polygons(args.boundaries)
    if not args.input.exists():
        sys.exit(f"Missing input CSV: {args.input}")
    with args.input.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {"latitude", "longitude"}.issubset(reader.fieldnames):
            sys.exit("CSV must contain latitude and longitude columns")
        columns = list(reader.fieldnames)
        for c in ("district", "province", "district_assignment_status"):
            if c not in columns:
                columns.append(c)
        rows = []
        count = Counter()
        for row in reader:
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError("coordinates outside valid range")
            except (TypeError, ValueError):
                row["district"], row["province"] = "", ""
                row["district_assignment_status"] = "invalid_coordinates"
                count["invalid_coordinates"] += 1
            else:
                district, province = assign(Point(lon, lat), polygons)
                row["district"], row["province"] = district, province
                row["district_assignment_status"] = "assigned" if district else "unassigned_review"
                count[row["district_assignment_status"]] += 1
                if district:
                    count[district] += 1
            rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    summary_path = args.output.parent / "district_assignment_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["district", "province", "attraction_count"])
        for d in sorted(PROVINCES):
            writer.writerow([d, PROVINCES[d], count[d]])
    print(f"Processed: {len(rows)} attraction records")
    print(f"Assigned: {count['assigned']}")
    print(f"Needs review (outside/multiple polygons): {count['unassigned_review']}")
    print(f"Invalid coordinates: {count['invalid_coordinates']}")
    print(f"CSV: {args.output}")
    print(f"District summary: {summary_path}")
    print("Review unmatched records and accuracy of input OSM way points before GIS analysis.")

if __name__ == "__main__":
    main()
