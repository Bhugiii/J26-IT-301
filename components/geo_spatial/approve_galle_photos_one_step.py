"""Approve visually confirmed Galle photo candidates without replacing existing records.

Run from the TravelMind project root:
    python approve_galle_photos_one_step.py

Reads: config/photo_candidates/galle_download_review.csv
Writes: config/attraction_image_final_review.csv (backup first)
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
REPORT = ROOT / 'config/photo_candidates/galle_download_review.csv'
REGISTER = ROOT / 'config/attraction_image_final_review.csv'
IMAGES = ROOT / 'assets/images/attractions'
ALLOWED_IDS = {
    'osm_way_398146186', 'osm_way_137294929', 'osm_way_431413175',
    'osm_way_128600427', 'osm_way_259026853', 'osm_way_1564820321',
}
REQUIRED_REGISTER = ['attraction_id', 'image_file', 'final_image_decision',
                     'creator', 'license', 'source_page', 'license_url']
LICENSE_PREFIXES = ('CC BY ', 'CC BY-SA ', 'CC0', 'Public domain')


def read_csv(path):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f'CSV has no headers: {path}')
        return list(reader.fieldnames), list(reader)


def main():
    if not REPORT.is_file() or not REGISTER.is_file():
        raise FileNotFoundError('Missing Galle review CSV or existing photo register. No changes made.')
    report_fields, report_rows = read_csv(REPORT)
    register_fields, old_rows = read_csv(REGISTER)
    missing = set(REQUIRED_REGISTER) - set(register_fields)
    if missing:
        raise ValueError(f'Existing register missing columns: {sorted(missing)}. No changes made.')
    needed = {'attraction_id', 'image_file', 'download_status', 'creator', 'license', 'source_page', 'license_url'}
    if not needed.issubset(report_fields):
        raise ValueError(f'Report missing columns: {sorted(needed - set(report_fields))}. No changes made.')

    already = {r['attraction_id'].strip() for r in old_rows}
    image_names = {r.get('image_file', '').strip().casefold() for r in old_rows}
    staged = []
    errors = []
    skipped = []
    seen = set()
    for r in report_rows:
        aid = r['attraction_id'].strip()
        status = r['download_status'].strip().casefold()
        if status not in {'downloaded_pending_review', 'existing_pending_review'}:
            skipped.append(f'{aid}: not downloaded')
            continue
        if aid not in ALLOWED_IDS:
            errors.append(f'{aid}: unexpected attraction ID (not on the verified six-photo list)')
            continue
        if aid in seen:
            errors.append(f'{aid}: duplicate in download report')
            continue
        seen.add(aid)
        if aid in already:
            skipped.append(f'{aid}: already in register (preserved)')
            continue
        name = r['image_file'].strip()
        if not name or Path(name).name != name or name in {'.', '..'}:
            errors.append(f'{aid}: invalid image filename')
            continue
        if name.casefold() in image_names:
            errors.append(f'{aid}: image filename already registered under another attraction')
            continue
        p = IMAGES / name
        if not p.is_file() or p.stat().st_size == 0:
            errors.append(f'{aid}: missing/empty image: {name}')
            continue
        creator, license_name = r['creator'].strip(), r['license'].strip()
        source, license_url = r['source_page'].strip(), r['license_url'].strip()
        if not creator or not license_name.startswith(LICENSE_PREFIXES):
            errors.append(f'{aid}: missing creator or unsupported license label')
            continue
        if not (source.startswith('https://commons.wikimedia.org/wiki/File:') and
                license_url.startswith('https://creativecommons.org/licenses/')):
            errors.append(f'{aid}: missing/invalid Commons source or CC license URL')
            continue
        if license_name.startswith('CC BY-SA ') and '/by-sa/' not in license_url:
            errors.append(f'{aid}: license label and URL disagree')
            continue
        if license_name.startswith('CC BY ') and not license_name.startswith('CC BY-SA ') and '/by/' not in license_url:
            errors.append(f'{aid}: license label and URL disagree')
            continue
        new = {col: r.get(col, '') for col in register_fields}
        new['attraction_id'] = aid
        new['image_file'] = name
        new['final_image_decision'] = 'approved'
        for col in ('creator', 'license', 'source_page', 'license_url'):
            new[col] = r[col].strip()
        staged.append(new)
        image_names.add(name.casefold())

    if errors:
        print('Validation errors — register NOT changed:')
        for error in errors:
            print('  -', error)
        raise SystemExit(1)
    print(f'Existing register: {len(old_rows)} records')
    print(f'New Galle photos to approve: {len(staged)}')
    for r in staged:
        print('  +', r['attraction_id'], r['image_file'])
    for item in skipped:
        print('  -', item)
    if not staged:
        print('Nothing new to add. Register unchanged.')
        return
    confirm = input('Have you checked the photos AND their Commons license pages? Type APPROVE: ').strip()
    if confirm != 'APPROVE':
        print('Cancelled. Register unchanged.')
        return
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = REGISTER.with_name(f'{REGISTER.stem}_backup_before_galle_{timestamp}{REGISTER.suffix}')
    shutil.copy2(REGISTER, backup)
    fd, tmp_path = tempfile.mkstemp(prefix='galle_register_', suffix='.csv', dir=REGISTER.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=register_fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(old_rows + staged)
        os.replace(tmp_path, REGISTER)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    print(f'APPROVED: {len(staged)} new Galle photos')
    print(f'Total photo register records: {len(old_rows) + len(staged)}')
    print(f'Backup: {backup}')
    print(f'Updated: {REGISTER}')


if __name__ == '__main__':
    main()
