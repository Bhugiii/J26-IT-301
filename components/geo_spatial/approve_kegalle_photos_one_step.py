"""Approve reviewed Kegalle Commons photos without disturbing existing TravelMind approvals.
Run from the TravelMind project root: python approve_kegalle_photos_one_step.py
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from shutil import copy2
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / 'config/photo_candidates/kegalle_download_review.csv'
REGISTER = ROOT / 'config/attraction_image_final_review.csv'
IMAGES = ROOT / 'assets/images/attractions'
DATA = ROOT / 'data/processed/travelmind_combined_clusters.csv'
# Dedigama image in report is an elephant lamp, not the exterior of Kota Vehera.
HOLD_IDS = {'osm_node_1733717444'}
REQUIRED = {'attraction_id', 'image_file', 'final_image_decision', 'creator', 'license', 'source_page', 'license_url'}
ALLOWED_LICENSES = {'CC BY 3.0', 'CC BY 4.0', 'CC BY-SA 3.0', 'CC BY-SA 4.0', 'CC0', 'CC0 1.0', 'Public domain'}


def read_csv(path: Path):
    if not path.is_file():
        raise RuntimeError(f'Missing required CSV: {path}')
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def valid_url(value: str, host: str) -> bool:
    p = urlparse(value.strip())
    return p.scheme == 'https' and (p.hostname or '').lower() in (host, 'www.' + host)


def main():
    report_fields, report = read_csv(REPORT)
    if not REQUIRED.issubset(report_fields) or 'download_status' not in report_fields:
        raise RuntimeError('Kegalle report lacks required columns.')
    existing_fields, existing = read_csv(REGISTER)
    if not REQUIRED.issubset(existing_fields):
        raise RuntimeError('Main approval register lacks required columns.')
    data_fields, data_rows = read_csv(DATA)
    if not {'attraction_id', 'district'}.issubset(data_fields):
        raise RuntimeError('Research dataset lacks attraction_id or district.')
    kegalle_ids = {r['attraction_id'].strip() for r in data_rows if r['district'].strip().casefold() == 'kegalle'}
    if not kegalle_ids:
        raise RuntimeError('No Kegalle district attraction IDs found. No changes made.')

    known_ids = {r['attraction_id'].strip() for r in existing}
    candidates, errors, skipped = [], [], []
    seen = set()
    for r in report:
        aid = r.get('attraction_id', '').strip()
        name = r.get('attraction_name', '').strip()
        if r.get('download_status', '').strip().lower() not in {'downloaded', 'existing', 'already_downloaded'}:
            skipped.append(f'{name}: not downloaded')
            continue
        if aid in HOLD_IDS:
            skipped.append(f'{name}: photo depicts an artifact; held for review')
            continue
        if aid in seen:
            errors.append(f'{name}: duplicate ID inside review report')
            continue
        seen.add(aid)
        if aid in known_ids:
            skipped.append(f'{name}: existing register ID preserved')
            continue
        fn = r.get('image_file', '').strip()
        if aid not in kegalle_ids:
            errors.append(f'{name}: attraction ID not assigned to Kegalle in dataset')
        elif not fn or Path(fn).name != fn or not (IMAGES / fn).is_file():
            errors.append(f'{name}: local image missing or invalid filename ({fn})')
        elif not r.get('creator', '').strip():
            errors.append(f'{name}: missing photographer/creator')
        elif r.get('license', '').strip() not in ALLOWED_LICENSES:
            errors.append(f'{name}: unsupported or missing license ({r.get("license")})')
        elif not valid_url(r.get('source_page', ''), 'commons.wikimedia.org'):
            errors.append(f'{name}: invalid Commons file page')
        elif not (valid_url(r.get('license_url', ''), 'creativecommons.org') or (r['license'].strip() == 'Public domain' and r.get('license_url', '').startswith('https://'))):
            errors.append(f'{name}: missing/invalid license URL')
        else:
            candidates.append(r)

    print(f'Current register entries: {len(existing)}')
    print(f'Kegalle entries eligible for visual approval: {len(candidates)}')
    for r in candidates:
        print(f'  - {r["attraction_name"]}: {r["image_file"]}')
    for s in skipped:
        print(f'SKIP: {s}')
    if errors:
        for e in errors:
            print(f'ERROR: {e}')
        raise RuntimeError('Approval aborted; fix the errors above before retrying.')
    if not candidates:
        print('No new eligible photos. The register is unchanged.')
        return
    print('\nPlease visually verify EACH listed photograph represents its exact attraction,')
    print('and check the attribution and license on each linked Wikimedia Commons file page.')
    confirmation = input('Type APPROVE to add these photos, or press Enter to cancel: ').strip()
    if confirmation != 'APPROVE':
        print('Canceled. Your register is unchanged.')
        return

    # Preserve original field order and all existing row values; append only new IDs.
    new_fields = existing_fields + [f for f in report_fields if f not in existing_fields]
    additions = []
    for r in candidates:
        new_r = {f: '' for f in new_fields}
        for field in report_fields:
            if field in new_r:
                new_r[field] = r.get(field, '')
        new_r['final_image_decision'] = 'approved'
        additions.append(new_r)

    backup = REGISTER.with_name(f'{REGISTER.stem}_backup_{datetime.now():%Y%m%d_%H%M%S}.csv')
    copy2(REGISTER, backup)
    temp_path = REGISTER.with_name(REGISTER.name + '.tmp')
    try:
        with temp_path.open('w', encoding='utf-8-sig', newline='') as out:
            writer = csv.DictWriter(out, fieldnames=new_fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(existing)
            writer.writerows(additions)
        temp_path.replace(REGISTER)
    finally:
        temp_path.unlink(missing_ok=True)
    print(f'Approved new Kegalle photos: {len(additions)}')
    print(f'Total register entries: {len(existing) + len(additions)}')
    print(f'Backup: {backup}')
    print(f'Updated: {REGISTER}')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError) as exc:
        print(f'STOPPED SAFELY: {exc}')
        raise SystemExit(1)
