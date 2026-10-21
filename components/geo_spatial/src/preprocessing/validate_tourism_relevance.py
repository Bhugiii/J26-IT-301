"""TravelMind tourism relevance screening (no API, no extra dependencies).

Run from project root:
    python src/preprocessing/validate_tourism_relevance.py

IMPORTANT: A flag requests manual review; it is not evidence a site is invalid.
All input rows are preserved in the validated output. No machine-learning
features or labels are fabricated.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data" / "processed" / "travelmind_attractions_cleaned.csv"
OUTPUT = ROOT / "data" / "processed" / "travelmind_attractions_validated.csv"
REVIEW = ROOT / "data" / "processed" / "tourism_relevance_review.csv"
REPORT = ROOT / "data" / "processed" / "tourism_relevance_report.csv"

# Generic labels are review candidates, not automatic exclusions.
GENERIC_NAMES = {
    "park", "temple", "museum", "tank", "lake", "waterfall", "beach",
    "church", "shrine", "ruin", "hall", "bank", "garden", "viewpoint",
    "monument", "arch", "bridge", "forest", "bats"
}
BROAD_CATEGORIES = {"tourist attractions", "religious sites"}


def clean_text(value: str) -> str:
    return " ".join((value or "").strip().split())


def main() -> None:
    parser = argparse.ArgumentParser(description="Flag possible tourism relevance issues; retain all records")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--review", type=Path, default=REVIEW)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    if not args.input.is_file():
        sys.exit(f"Input not found: {args.input}\nRun clean_attractions.py first.")

    with args.input.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        needed = {"attraction_name", "tourism_category", "district"}
        missing = needed - set(fields)
        if missing:
            sys.exit(f"Missing required CSV columns: {', '.join(sorted(missing))}")
        rows = list(reader)

    # A repeated name alone does NOT mean two records are duplicates.
    name_district_counts = Counter(
        (clean_text(r.get("district", "")).casefold(),
         clean_text(r.get("attraction_name", "")).casefold())
        for r in rows if clean_text(r.get("attraction_name", ""))
    )

    output_fields = list(fields)
    for new_field in ["review_required", "review_reasons", "relevance_status"]:
        if new_field not in output_fields:
            output_fields.append(new_field)

    counts = Counter()
    reviewed = []
    validated = []
    for row in rows:
        row = dict(row)
        name = clean_text(row.get("attraction_name", ""))
        category = clean_text(row.get("tourism_category", ""))
        district = clean_text(row.get("district", ""))
        reasons = []
        if not name:
            reasons.append("missing_name")
        elif re.fullmatch(r"[0-9]+", name):
            reasons.append("numeric_only_name")
        elif len(name) < 5:
            reasons.append("short_name")
        if name.casefold() in GENERIC_NAMES:
            reasons.append("generic_name")
        if name and name[0] in "#@":
            reasons.append("symbol_prefixed_name")
        if category.casefold() in BROAD_CATEGORIES:
            reasons.append("broad_category_verify_osm_tags")
        if not category:
            reasons.append("missing_category")
        if name and name_district_counts[(district.casefold(), name.casefold())] > 1:
            reasons.append("name_repeated_in_district_verify_not_duplicate")

        row["review_required"] = "yes" if reasons else "no"
        row["review_reasons"] = "; ".join(reasons)
        row["relevance_status"] = "needs_manual_review" if reasons else "not_flagged_unverified"
        validated.append(row)
        if reasons:
            reviewed.append(row)
            counts.update(reasons)

    for path in (args.output, args.review, args.report):
        path.parent.mkdir(parents=True, exist_ok=True)
    for path, records in ((args.output, validated), (args.review, reviewed)):
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=output_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)

    with args.report.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "count"])
        writer.writerow(["total_input", len(rows)])
        writer.writerow(["not_flagged_unverified", len(rows) - len(reviewed)])
        writer.writerow(["needs_manual_review", len(reviewed)])
        for reason, count in sorted(counts.items()):
            writer.writerow([f"flag_{reason}", count])

    print(f"Input records: {len(rows)}")
    print(f"Review candidates: {len(reviewed)}")
    print(f"Not flagged (still unverified): {len(rows) - len(reviewed)}")
    print(f"Validated CSV (all records kept): {args.output}")
    print(f"Manual review CSV: {args.review}")
    print(f"Quality report CSV: {args.report}")
    print("No records were deleted or automatically declared valid tourism attractions.")


if __name__ == "__main__":
    main()
