"""Approve the seven Ratnapura photo candidates after human review.
Run from anywhere: python approve_ratnapura_photos_one_step.py
Never overwrites existing attraction photo records. Keeps the temple mural pending.
"""
from __future__ import annotations

import csv
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / 'config' / 'photo_candidates' / 'ratnapura_download_review.csv'
REGISTER = ROOT / 'config' / 'attraction_image_final_review.csv'
IMAGES = ROOT / 'assets' / 'images' / 'attractions'

# Seven location-appropriate candidates. The Saman Dewalaya mural is NOT in this list.
ALLOWED_IDS = {
    'osm_node_2640665069',  # Bopath Falls
    'osm_way_710421256',    # Elephant Transit Home
    'osm_node_4512854289',  # Sinharaja National Park
    'osm_way_364257554',    # Maduwanwela Walawwa
    'osm_node_4502013947',  # Kirindi Ella
    'osm_node_2804314660',  # Pahanthudawa
    'osm_node_4462731780',  # Surathali Ella
}
REQUIRED = {'attraction_id', 'image_file', 'final_image_decision',
            'creator', 'license', 'source_page', 'license_url'}
PERMITTED_LICENSES = {
    'CC0', 'CC BY 2.0', 'CC BY 3.0', 'CC BY 4.0',
    'CC BY-SA 2.0', 'CC BY-SA 3.0', 'CC BY-SA 4.0',
}

def load_csv(path):
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f'No CSV header: {path}')
        return list(reader), list(reader.fieldnames)

def valid_https(value, domain):
    parsed = urlparse(value)
    return parsed.scheme == 'https' and (parsed.hostname == domain or parsed.hostname.endswith('.' + domain))

def main():
    if not REPORT.is_file() or not REGISTER.is_file():
        raise SystemExit(f'Missing input file. Need both:\n  {REPORT}\n  {REGISTER}')
    candidates, candidate_fields = load_csv(REPORT)
    existing, fields = load_csv(REGISTER)
    if not REQUIRED.issubset(fields):
        raise SystemExit(f'Register missing fields: {sorted(REQUIRED-set(fields))}')
    required_report = {'attraction_id', 'attraction_name', 'image_file', 'download_status',
                       'creator', 'license', 'source_page', 'license_url'}
    if not required_report.issubset(candidate_fields):
        raise SystemExit(f'Review missing fields: {sorted(required_report-set(candidate_fields))}')
    existing_ids = {r['attraction_id'].strip() for r in existing}
    staged = []
    skipped = []
    seen = set()
    errors = []
    for r in candidates:
        aid = r['attraction_id'].strip()
        if aid not in ALLOWED_IDS:
            continue
        if aid in seen:
            errors.append(f'Duplicate candidate in report: {aid}')
            continue
        seen.add(aid)
        if aid in existing_ids:
            skipped.append(f'{r["attraction_name"]}: existing register record preserved')
            continue
        if r['download_status'].strip() not in ('downloaded_pending', 'already_downloaded_pending'):
            skipped.append(f'{r["attraction_name"]}: not successfully downloaded')
            continue
        filename = r['image_file'].strip()
        if not filename or filename != Path(filename).name or not (IMAGES / filename).is_file():
            errors.append(f'{r["attraction_name"]}: photo file missing/unsafe: {filename}')
            continue
        if (IMAGES / filename).stat().st_size < 1024:
            errors.append(f'{r["attraction_name"]}: unexpectedly small image: {filename}')
        if not r['creator'].strip():
            errors.append(f'{r["attraction_name"]}: missing creator')
        lic = r['license'].strip()
        if lic not in PERMITTED_LICENSES:
            errors.append(f'{r["attraction_name"]}: license needs manual review: {lic}')
        if not valid_https(r['source_page'].strip(), 'commons.wikimedia.org'):
            errors.append(f'{r["attraction_name"]}: invalid Commons source')
        if not valid_https(r['license_url'].strip(), 'creativecommons.org'):
            errors.append(f'{r["attraction_name"]}: license URL missing/invalid')
        entry = {f: '' for f in fields}
        for field in fields:
            if field in r:
                entry[field] = r[field]
        entry['final_image_decision'] = 'approved'
        staged.append(entry)
    if seen != ALLOWED_IDS:
        errors.append(f'Report missing required IDs: {sorted(ALLOWED_IDS - seen)}')
    if errors:
        print('Approval STOPPED; original register unchanged:')
        for error in errors:
            print(' -', error)
        return
    print(f'Existing register entries: {len(existing)}')
    print(f'New photos ready: {len(staged)}')
    for entry in staged:
        print(' +', entry['attraction_id'], entry['image_file'])
    for msg in skipped:
        print(' SKIP', msg)
    print('HOLD: Sabaragamu Maha Saman Dewalaya mural (separate visual choice needed).')
    if not staged:
        print('Nothing new to approve. Original register unchanged.')
        return
    print('\nReview the actual pictures and their Commons file/license pages before approving.')
    answer = input('Type APPROVE only if all listed photos are correct and reusable: ').strip()
    if answer != 'APPROVE':
        print('Cancelled. Original register unchanged.')
        return
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = REGISTER.with_name(f'{REGISTER.stem}_backup_{timestamp}{REGISTER.suffix}')
    shutil.copy2(REGISTER, backup)
    fd, tempname = tempfile.mkstemp(prefix='photo_approval_', suffix='.csv', dir=REGISTER.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(existing + staged)
        os.replace(tempname, REGISTER)
    finally:
        if os.path.exists(tempname):
            os.unlink(tempname)
    print(f'Approved new Ratnapura records: {len(staged)}')
    print(f'Total register records: {len(existing)+len(staged)}')
    print(f'Backup: {backup}')
    print(f'Updated: {REGISTER}')

if __name__ == '__main__':
    main()
