"""Approve visually verified Hambantota Commons photos without replacing previous approvals.
Run from the TravelMind project root: python approve_hambantota_photos_one_step.py
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
REVIEW = ROOT / 'config/photo_candidates/hambantota_download_review_retry.csv'
REGISTER = ROOT / 'config/attraction_image_final_review.csv'
IMAGES = ROOT / 'assets/images/attractions'
DATASET = ROOT / 'data/processed/travelmind_combined_clusters.csv'
REQUIRED = ('attraction_id', 'image_file', 'final_image_decision')
ATTRIBUTION = ('creator', 'license', 'source_page', 'license_url')
ALLOWED = {'CC0', 'CC BY 2.0', 'CC BY 3.0', 'CC BY 4.0', 'CC BY-SA 2.0', 'CC BY-SA 3.0', 'CC BY-SA 4.0'}


def read_csv(path):
    if not path.is_file():
        raise FileNotFoundError(f'Missing file: {path}')
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or ()), list(reader)


def valid_url(value, host):
    try:
        u = urlparse(value.strip())
        return u.scheme == 'https' and (u.hostname == host or u.hostname == 'www.' + host)
    except (TypeError, ValueError):
        return False


def main():
    review_columns, report = read_csv(REVIEW)
    reg_columns, existing = read_csv(REGISTER)
    data_columns, dataset = read_csv(DATASET)
    for label, cols in [('review report', review_columns), ('photo register', reg_columns)]:
        missing = (set(REQUIRED) | set(ATTRIBUTION)) - set(cols)
        if missing:
            raise ValueError(f'{label} missing columns: {sorted(missing)}')
    if not {'attraction_id', 'district'}.issubset(data_columns):
        raise ValueError('Dataset is missing attraction_id or district.')
    dataset_district = {r['attraction_id'].strip(): r['district'].strip().lower() for r in dataset}
    existing_ids = {r['attraction_id'].strip() for r in existing}
    seen = set()
    accepted, skipped, problems = [], [], []
    for r in report:
        aid = (r.get('attraction_id') or '').strip()
        name = (r.get('attraction_name') or aid).strip()
        if (r.get('download_status') or '').strip().lower() not in {'downloaded', 'existing'}:
            skipped.append(f'{name}: not downloaded')
            continue
        if aid in seen:
            problems.append(f'{name}: duplicate attraction ID in review report')
            continue
        seen.add(aid)
        if aid in existing_ids:
            skipped.append(f'{name}: existing register entry preserved')
            continue
        fname = (r.get('image_file') or '').strip()
        if not fname or fname != Path(fname).name or not (IMAGES / fname).is_file():
            problems.append(f'{name}: local image file missing or unsafe filename')
            continue
        if dataset_district.get(aid) != 'hambantota':
            problems.append(f'{name}: attraction ID not found in Hambantota dataset')
            continue
        if not all((r.get(c) or '').strip() for c in ATTRIBUTION):
            problems.append(f'{name}: missing creator/license/source/license URL')
            continue
        lic = r['license'].strip().upper()
        if lic not in ALLOWED:
            problems.append(f'{name}: unsupported or unrecognized license {r["license"]!r}')
            continue
        if not valid_url(r['source_page'], 'commons.wikimedia.org') or '/wiki/File:' not in r['source_page']:
            problems.append(f'{name}: invalid Commons file-page link')
            continue
        license_link = urlparse(r['license_url'].strip())
        if license_link.scheme not in {'http', 'https'} or license_link.hostname not in {'creativecommons.org', 'www.creativecommons.org'}:
            problems.append(f'{name}: invalid Creative Commons license URL')
            continue
        item = {col: (r.get(col) or '') for col in reg_columns}
        item['attraction_id'] = aid
        item['image_file'] = fname
        item['final_image_decision'] = 'approved'
        accepted.append((name, item))

    print(f'Existing register entries: {len(existing)} (will preserve them all)')
    print(f'New eligible Hambantota images: {len(accepted)}')
    for name, _ in accepted:
        print(f'  + {name}')
    for note in skipped:
        print('  SKIP:', note)
    if problems:
        print('\nApproval stopped. Resolve these issues first:')
        for issue in problems:
            print('  ERROR:', issue)
        raise SystemExit(1)
    if not accepted:
        print('Nothing new to approve. Register unchanged.')
        return
    print('\nIMPORTANT: This script cannot inspect the photographs or verify live Commons pages.')
    print('Open all listed photos, verify place identity, and check each Commons file page/license.')
    response = input('After completing these checks, type APPROVE to update the register: ').strip()
    if response != 'APPROVE':
        print('Cancelled. Register unchanged.')
        return
    backup = REGISTER.with_name(REGISTER.stem + '_backup_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + REGISTER.suffix)
    shutil.copy2(REGISTER, backup)
    with tempfile.NamedTemporaryFile(mode='w', newline='', encoding='utf-8-sig', suffix='.csv', prefix='hambantota_', dir=REGISTER.parent, delete=False) as f:
        temporary = Path(f.name)
        writer = csv.DictWriter(f, fieldnames=reg_columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(existing)
        writer.writerows(item for _, item in accepted)
    try:
        os.replace(temporary, REGISTER)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'APPROVED new Hambantota photographs: {len(accepted)}')
    print(f'Photo register records: {len(existing) + len(accepted)}')
    print(f'Backup: {backup}')
    print(f'Updated: {REGISTER}')
    print('Restart or refresh Streamlit to see approved photos.')


if __name__ == '__main__':
    main()
