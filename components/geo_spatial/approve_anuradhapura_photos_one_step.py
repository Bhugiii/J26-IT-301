"""TravelMind: safely approve selected Anuradhapura photos after manual review.
Run from the project root: python approve_anuradhapura_photos_one_step.py
"""
from __future__ import annotations

import csv
import os
import shutil
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / 'config/photo_candidates/anuradhapura_download_review.csv'
REGISTER = ROOT / 'config/attraction_image_final_review.csv'
IMAGE_DIR = ROOT / 'assets/images/attractions'

# Deliberately held: rights/attribution or site-vs-image content needs separate review.
HELD = {
    'osm_way_398907394': 'Jaya Sri Maha Bodhi: review rights/permission wording on Commons',
    'osm_way_1356595422': 'Mihintale: selected Buddha statue rather than clear site-wide view',
    'osm_node_3723220027': 'Ritigala: selected photograph depicts a schoolgirl',
    'osm_node_4081329203': 'Aukana Buddha: recorded creator is unknown; inspect Commons attribution',
}
APPROVE_IDS = {
    'osm_way_247453300',  # Ruwanwelisaya
    'osm_way_115767725',  # Jetavanaramaya
    'osm_way_278865152',  # Abhayagiri Stupa
    'osm_way_247453305',  # Thuparamaya
    'osm_node_567004213', # Isurumuniya Temple
    'osm_node_567004191', # Samadhi Buddha
    'osm_way_550562510', # Kuttam Pokuna
    'osm_way_247452367', # Mirisawetiya
    'osm_node_4726751890', # Jathika Namal Uyana
}
FIELDS = ('attraction_id', 'image_file', 'final_image_decision', 'creator', 'license', 'source_page', 'license_url')

def read_csv(path: Path):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])

def valid_url(url):
    return urlparse(url.strip()).scheme == 'https' and bool(urlparse(url.strip()).netloc)

def main():
    if not REPORT.is_file() or not REGISTER.is_file():
        raise SystemExit('Missing review CSV or main register. Run from the TravelMind project root.')
    report, report_cols = read_csv(REPORT)
    current, current_cols = read_csv(REGISTER)
    if any(k not in report_cols for k in FIELDS + ('download_status',)):
        raise SystemExit('Review CSV is missing required columns. No changes made.')
    if any(k not in current_cols for k in ('attraction_id','image_file','final_image_decision')):
        raise SystemExit('Main photo register has unexpected columns. No changes made.')
    by_id = {r['attraction_id'].strip(): r for r in report}
    if len(by_id) != len(report):
        raise SystemExit('Duplicate attraction IDs in review report. No changes made.')
    missing = APPROVE_IDS - set(by_id)
    if missing:
        raise SystemExit('Review CSV missing expected IDs: ' + ', '.join(sorted(missing)))
    existing_ids = {r.get('attraction_id','').strip() for r in current}
    pending = []
    issues = []
    for attraction_id in sorted(APPROVE_IDS):
        r = by_id[attraction_id]
        if attraction_id in existing_ids:
            print(f'SKIP existing record: {r.get("attraction_name", attraction_id)}')
            continue
        name = r.get('attraction_name', attraction_id)
        fname = r['image_file'].strip()
        if r['download_status'].strip().upper() not in {'DOWNLOADED', 'EXISTS', 'EXISTING'}:
            issues.append(f'{name}: not successfully downloaded')
        if not fname or fname != Path(fname).name or not (IMAGE_DIR / fname).is_file():
            issues.append(f'{name}: image file missing/invalid: {fname}')
        for col in ('creator','license','source_page','license_url'):
            if not r[col].strip(): issues.append(f'{name}: missing {col}')
        if not valid_url(r['source_page']) or 'commons.wikimedia.org' not in urlparse(r['source_page']).netloc:
            issues.append(f'{name}: source is not a Commons HTTPS page')
        if r['license_url'].strip().startswith('http://creativecommons.org/'):
            r['license_url'] = 'https://' + r['license_url'].strip()[len('http://'):]
        if not valid_url(r['license_url']):
            issues.append(f'{name}: license URL invalid')
        if not (r['license'].strip().upper().startswith(('CC BY', 'CC0')) or r['license'].strip().lower() in {'public domain', 'pd'}):
            issues.append(f'{name}: license not recognized: {r["license"]}')
        pending.append(r)
    if issues:
        print('\nCannot approve; fix these issues first:')
        for issue in issues: print(' - ' + issue)
        raise SystemExit('No changes made.')
    print(f'Existing register records: {len(current)}')
    print(f'New approval candidates: {len(pending)}')
    print('\nHeld for manual review:')
    for aid, why in HELD.items(): print(' - ' + why)
    print('\nThis script cannot check what each image depicts or independently verify licenses.')
    print('Only approve if you inspected the image and the corresponding Commons source/license pages.')
    if not pending:
        print('Nothing new to approve. Register unchanged.')
        return
    if input('Type APPROVE to add these photographs (anything else cancels): ').strip() != 'APPROVE':
        print('Cancelled. No changes made.')
        return
    columns = list(dict.fromkeys(current_cols + [c for c in report_cols if c not in current_cols]))
    new_rows = list(current)
    for r in pending:
        updated = dict(r)
        updated['final_image_decision'] = 'approved'
        new_rows.append(updated)
    backup = REGISTER.with_name(REGISTER.stem + '_backup_' + datetime.now().strftime('%Y%m%d_%H%M%S') + REGISTER.suffix)
    if backup.exists(): raise SystemExit('Backup filename already exists. Try again in a second.')
    shutil.copy2(REGISTER, backup)
    fd, tmp = tempfile.mkstemp(prefix='._photo_register_', suffix='.csv', dir=REGISTER.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(new_rows)
        os.replace(tmp, REGISTER)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    print(f'Approved {len(pending)} Anuradhapura photographs.')
    print(f'Total register rows: {len(new_rows)}')
    print(f'Backup: {backup}')
    print(f'Updated: {REGISTER}')

if __name__ == '__main__':
    main()
