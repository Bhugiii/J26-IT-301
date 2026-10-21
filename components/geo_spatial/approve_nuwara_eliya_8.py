"""Approve visually checked Nuwara Eliya Commons photos; keep prior records safe.
Run from TravelMind project root: python approve_nuwara_eliya_8.py
"""
from pathlib import Path
from datetime import datetime
import csv
import shutil
import os
import tempfile

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / 'config/photo_candidates/nuwara_eliya_download_review.csv'
REGISTER = ROOT / 'config/attraction_image_final_review.csv'
IMAGES = ROOT / 'assets/images/attractions'
LICENSES = {'CC0', 'CC BY 2.0', 'CC BY 2.5', 'CC BY 3.0', 'CC BY 4.0',
            'CC BY-SA 2.0', 'CC BY-SA 2.5', 'CC BY-SA 3.0', 'CC BY-SA 4.0'}
REQUIRED = ('attraction_id', 'image_file', 'final_image_decision',
            'creator', 'license', 'source_page', 'license_url')

def read_csv(path):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f'CSV lacks header: {path}')
        return list(reader), list(reader.fieldnames)

def main():
    if not REPORT.is_file() or not REGISTER.is_file():
        raise SystemExit('Missing CSV: check config/photo_candidates/nuwara_eliya_download_review.csv and config/attraction_image_final_review.csv')
    incoming, _ = read_csv(REPORT)
    current, cols = read_csv(REGISTER)
    missing = set(REQUIRED) - set(cols)
    if missing:
        raise SystemExit(f'Register missing required columns: {sorted(missing)}')
    existing_ids = {r['attraction_id'].strip() for r in current}
    candidates = []
    problems = []
    for r in incoming:
        if r.get('download_status', '').strip().upper() not in ('DOWNLOADED', 'EXISTS', 'EXISTING'):
            continue
        aid = r.get('attraction_id', '').strip()
        filename = r.get('image_file', '').strip()
        if aid in existing_ids:
            print(f'PRESERVE existing record: {r.get("attraction_name", aid)} [{aid}]')
            continue
        issue = []
        if not aid or not filename or filename != Path(filename).name:
            issue.append('invalid ID or image filename')
        elif not (IMAGES / filename).is_file():
            issue.append('local image not found')
        if r.get('license', '').strip() not in LICENSES:
            issue.append('license not on permitted list')
        for field in ('creator', 'source_page', 'license_url'):
            if not r.get(field, '').strip():
                issue.append(f'missing {field}')
        if not r.get('source_page', '').startswith('https://commons.wikimedia.org/wiki/File:'):
            issue.append('invalid Wikimedia Commons file-page URL')
        if not r.get('license_url', '').startswith(('https://creativecommons.org/', 'http://creativecommons.org/')):
            issue.append('unexpected license URL')
        if issue:
            problems.append((r.get('attraction_name', aid), ', '.join(issue)))
        else:
            candidates.append(r)
    if problems:
        for name, reason in problems:
            print(f'REVIEW NEEDED: {name}: {reason}')
        raise SystemExit('Stopped without changes: resolve metadata or file problems first.')
    if not candidates:
        print('No new eligible photos. Register unchanged.')
        return
    print('\nNew photos eligible for approval:')
    for r in candidates:
        print(f'  {r.get("attraction_name", "")}: {r["image_file"]} ({r["license"]})')
    print('\nOnly continue if you have OPENED all listed image files, checked that each photo depicts the named attraction, and checked its Commons file-page license.')
    if input('Type APPROVE to confirm all listed images: ').strip() != 'APPROVE':
        print('Cancelled. Nothing was changed.')
        return
    new_columns = list(cols)
    # Keep existing schema, while ensuring credits from the report are stored.
    for c in REQUIRED:
        if c not in new_columns:
            new_columns.append(c)
    appended = []
    for r in candidates:
        entry = {k: r.get(k, '') for k in new_columns}
        entry['final_image_decision'] = 'approved'
        appended.append(entry)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = REGISTER.with_name(f'{REGISTER.stem}_backup_before_nuwara_{timestamp}.csv')
    shutil.copy2(REGISTER, backup)
    fd, tmpname = tempfile.mkstemp(prefix='travelmind_photo_', suffix='.csv', dir=REGISTER.parent)
    try:
        with os.fdopen(fd, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=new_columns, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(current)
            writer.writerows(appended)
        os.replace(tmpname, REGISTER)
    finally:
        if os.path.exists(tmpname):
            os.unlink(tmpname)
    print(f'Approved new Nuwara Eliya photos: {len(appended)}')
    print(f'Register now has {len(current) + len(appended)} records.')
    print(f'Backup: {backup}')
    print('Restart Streamlit or clear cached data if photos do not immediately appear.')

if __name__ == '__main__':
    main()
