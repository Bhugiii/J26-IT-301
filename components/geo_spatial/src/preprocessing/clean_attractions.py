"""TravelMind Step 3: clean OSM attractions without modifying the source CSV.
Run from project root: python src/preprocessing/clean_attractions.py
No extra packages required (Python standard library).
"""
import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / 'data' / 'processed' / 'travelmind_attractions_with_districts.csv'
DEFAULT_OUTPUT_DIR = ROOT / 'data' / 'processed'

REQUIRED = {'attraction_name', 'latitude', 'longitude', 'district', 'province'}
VALID_STATUSES = {'assigned'}


def tidy(value):
    return re.sub(r'\s+', ' ', str(value or '').strip())


def normalize_categories(text):
    # Keep original OSM-derived labels, just make separators/spacing consistent.
    categories = [tidy(item) for item in re.split(r'[;,|]', text or '')]
    unique = []
    seen = set()
    for category in categories:
        if category and category.casefold() not in seen:
            seen.add(category.casefold())
            unique.append(category)
    return '; '.join(unique)


def valid_point(row):
    try:
        lat = float(tidy(row.get('latitude')))
        lon = float(tidy(row.get('longitude')))
    except (TypeError, ValueError):
        return False
    return math.isfinite(lat) and math.isfinite(lon) and 5.5 <= lat <= 10.1 and 79.3 <= lon <= 82.2


def dedup_key(row):
    # Different OSM elements can share a name and coordinates: never merge on those alone.
    # Only deduplicate when a persistent, explicit identifier exists.
    for key in ('attraction_id', 'osm_id', 'place_id'):
        value = tidy(row.get(key))
        if value:
            return (key, value)
    return None


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description='Clean TravelMind district-classified OSM attractions')
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if not args.input.exists():
        parser.error(f'Input not found: {args.input}')
    with args.input.open('r', encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        columns = list(reader.fieldnames or [])
        if not REQUIRED.issubset(columns):
            parser.error(f'Missing required CSV columns: {sorted(REQUIRED - set(columns))}')
        raw_rows = list(reader)

    output_columns = list(columns)
    if 'cleaning_status' not in output_columns:
        output_columns.append('cleaning_status')
    if 'review_reason' not in output_columns:
        output_columns.append('review_reason')

    kept = []
    review = []
    reasons = Counter()
    seen_ids = set()
    district_counts = Counter()

    for raw in raw_rows:
        row = {key: tidy(raw.get(key, '')) for key in columns}
        row['tourism_category'] = normalize_categories(row.get('tourism_category', '')) if 'tourism_category' in row else ''
        why = []
        if not row.get('attraction_name'):
            why.append('missing_name')
        if not row.get('tourism_category'):
            why.append('missing_category')
        if not valid_point(row):
            why.append('missing_or_out_of_range_coordinates')
        if row.get('district_assignment_status') and row['district_assignment_status'] not in VALID_STATUSES:
            why.append('district_assignment_needs_review')
        if not row.get('district') or not row.get('province'):
            why.append('missing_district_or_province')

        key = dedup_key(row)
        if key is not None:
            if key in seen_ids:
                why.append('duplicate_identifier')
            else:
                seen_ids.add(key)

        if why:
            row['cleaning_status'] = 'needs_review'
            row['review_reason'] = '; '.join(why)
            review.append(row)
            reasons.update(why)
        else:
            row['cleaning_status'] = 'clean'
            row['review_reason'] = ''
            kept.append(row)
            district_counts[row['district']] += 1

    out = args.output_dir
    cleaned_file = out / 'travelmind_attractions_cleaned.csv'
    review_file = out / 'attractions_needing_review.csv'
    report_file = out / 'data_quality_report.csv'
    write_csv(cleaned_file, kept, output_columns)
    write_csv(review_file, review, output_columns)
    summary = [
        {'metric': 'input_records', 'count': len(raw_rows)},
        {'metric': 'clean_records', 'count': len(kept)},
        {'metric': 'needs_review_records', 'count': len(review)},
    ]
    summary.extend({'metric': 'reason_' + name, 'count': count} for name, count in sorted(reasons.items()))
    write_csv(report_file, summary, ['metric', 'count'])
    print(f'Input: {len(raw_rows)} records')
    print(f'Clean: {len(kept)} records -> {cleaned_file}')
    print(f'Needs review: {len(review)} records -> {review_file}')
    print(f'Data quality report: {report_file}')
    print('Note: duplicate checks use explicit IDs only; no records are merged by name/location.')
    print('Note: district labels come from the previous spatial-join step; manual validation is still recommended.')


if __name__ == '__main__':
    main()
