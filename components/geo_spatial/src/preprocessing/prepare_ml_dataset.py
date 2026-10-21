"""TravelMind: reproducible, conservative ML dataset preparation (Python standard library).

Never treats AI review suggestions as confirmed manual decisions.
Preserves all provisional records unless an explicit, authorized manual exclusion exists.
"""
import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'data' / 'processed'
VALIDATION = BASE / 'validation'
VALID_STATUSES = {'verified', 'corrected', 'exclude', 'pending'}


def read_rows(path, required=False):
    if not path.exists():
        if required:
            raise FileNotFoundError(f'Required input missing: {path}')
        print(f'Optional input not found: {path.name} (continuing)')
        return []
    with path.open(newline='', encoding='utf-8-sig') as fp:
        return list(csv.DictReader(fp))


def unique_by_id(rows, source):
    result = {}
    for row in rows:
        ident = row.get('attraction_id', '').strip()
        if not ident:
            raise ValueError(f'{source} includes a blank attraction_id')
        if ident in result:
            raise ValueError(f'{source} has repeated attraction_id: {ident}')
        result[ident] = row
    return result


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8-sig') as fp:
        writer = csv.DictWriter(fp, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def main():
    p = argparse.ArgumentParser(description='Build reproducible TravelMind ML inputs')
    p.add_argument('--input', type=Path, default=VALIDATION / 'travelmind_review_prioritized.csv')
    p.add_argument('--review', type=Path, default=VALIDATION / 'TravelMind_reviewed_457.csv')
    p.add_argument('--pairs', type=Path, default=VALIDATION / 'travelmind_potential_duplicate_pairs.csv')
    p.add_argument('--decisions', type=Path, default=VALIDATION / 'manual_review_decisions.csv')
    args = p.parse_args()

    original = read_rows(args.input, required=True)
    if not original:
        raise ValueError('Source file has no rows')
    source = unique_by_id(original, 'main input')
    ai_review = unique_by_id(read_rows(args.review), 'review suggestions')
    manual = unique_by_id(read_rows(args.decisions), 'manual decisions')
    pairs = read_rows(args.pairs)

    unknown_manual = set(manual) - set(source)
    if unknown_manual:
        raise ValueError(f'Manual decision IDs not in source: {sorted(unknown_manual)[:5]}')
    suspected = set()
    for pair in pairs:
        for col in ('attraction_id_1', 'attraction_id_2'):
            ident = pair.get(col, '').strip()
            if ident in source:
                suspected.add(ident)

    fields = list(original[0].keys())
    extras = ['ai_recommended_action', 'ai_review_notes', 'suspected_duplicate',
              'manual_review_status', 'corrected_name', 'corrected_category',
              'manual_review_notes', 'ml_inclusion_status', 'ml_inclusion_reason',
              'ml_name', 'ml_category']
    fields += [field for field in extras if field not in fields]

    output, training, exclusions = [], [], []
    counts = Counter()
    for ident, record in source.items():
        row = dict(record)
        suggestion = ai_review.get(ident, {})
        decision = manual.get(ident, {})
        # An AI-generated pending_external_verification is NOT a manual decision.
        status = decision.get('manual_review_status', '').strip().lower() or 'pending'
        if status not in VALID_STATUSES:
            raise ValueError(f'Invalid manual_review_status for {ident}: {status}')
        corrected_name = decision.get('corrected_name', '').strip()
        corrected_category = decision.get('corrected_category', '').strip()
        if status == 'corrected' and not (corrected_name or corrected_category):
            raise ValueError(f'Corrected status requires a corrected field: {ident}')
        if status == 'exclude' and not decision.get('review_notes', '').strip():
            raise ValueError(f'Exclude status requires review_notes: {ident}')

        row['ai_recommended_action'] = suggestion.get('recommended_action', '')
        row['ai_review_notes'] = suggestion.get('review_notes', '')
        row['suspected_duplicate'] = 'yes' if ident in suspected else 'no'
        row['manual_review_status'] = status
        row['corrected_name'] = corrected_name
        row['corrected_category'] = corrected_category
        row['manual_review_notes'] = decision.get('review_notes', '').strip()
        row['ml_name'] = corrected_name if status == 'corrected' and corrected_name else record.get('attraction_name', '')
        row['ml_category'] = corrected_category if status == 'corrected' and corrected_category else record.get('tourism_category', '')
        if status == 'exclude':
            row['ml_inclusion_status'] = 'excluded_confirmed'
            row['ml_inclusion_reason'] = 'manual_exclude_with_reason'
            exclusions.append(row)
            counts['excluded_confirmed'] += 1
        else:
            try:
                lat, lon = float(record['latitude']), float(record['longitude'])
                valid = math.isfinite(lat) and math.isfinite(lon) and 5.7 <= lat <= 10.1 and 79.3 <= lon <= 82.3
            except (KeyError, ValueError, TypeError):
                valid = False
            if not valid or not record.get('district', '').strip():
                row['ml_inclusion_status'] = 'hold_data_issue'
                row['ml_inclusion_reason'] = 'invalid_coordinates_or_missing_district'
                counts['hold_data_issue'] += 1
            else:
                row['ml_inclusion_status'] = 'provisional_unverified' if status == 'pending' else 'manual_reviewed'
                row['ml_inclusion_reason'] = ('review_flags_pending' if status == 'pending' and
                     (ident in suspected or record.get('review_priority', '') not in ('', 'not_flagged'))
                     else 'no_confirmed_exclusion')
                training.append(row)
                counts[row['ml_inclusion_status']] += 1
        output.append(row)

    write_csv(BASE / 'travelmind_ml_audit.csv', output, fields)
    write_csv(BASE / 'travelmind_ml_ready.csv', training, fields)
    write_csv(VALIDATION / 'confirmed_exclusions.csv', exclusions, fields)
    report = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'source_file': str(args.input), 'source_records': len(source),
        'review_recommendations_matched': len(set(ai_review) & set(source)),
        'suspected_duplicate_records': len(suspected),
        'explicit_manual_decisions': len(manual),
        'counts_by_inclusion_status': dict(counts),
        'ml_ready_records': len(training),
        'note': 'ML ready means eligible for exploratory analysis, NOT tourism verified; AI suggestions never trigger exclusion.'
    }
    (BASE / 'ml_preparation_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    print('Saved:', BASE / 'travelmind_ml_ready.csv')
    print('Saved:', BASE / 'travelmind_ml_audit.csv')
    print('Saved:', BASE / 'ml_preparation_report.json')

if __name__ == '__main__':
    main()
