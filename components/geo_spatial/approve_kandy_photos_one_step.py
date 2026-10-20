"""Approve user-checked Kandy Commons photos in TravelMind.

Run from TravelMind project root:
    python approve_kandy_photos_one_step.py

Reads config/photo_candidates/kandy_download_review.csv.
Preserves existing photo rows, skips existing attraction IDs, backs up before writing.
Only use after visually checking the five images and Commons attribution/usage terms.
"""
import csv
import html
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / 'config/photo_candidates/kandy_download_review.csv'
ACTIVE = ROOT / 'config/attraction_image_final_review.csv'
IMAGES = ROOT / 'assets/images/attractions'

EXPECTED = {
    'osm_way_191377765': ('Temple of the Sacred Tooth Relic', 'Temple of the Sacred Tooth Relic'),
    'osm_node_10862211785': ('Bahirawakanda Buddha Statue', 'Bahirawakanda Buddha'),
    'osm_node_1743126596': ('Gadaladeniya Temple', 'Gadaladeniya Temple'),
    'osm_node_1743126531': ('Lankatilaka Temple', 'Lankatilaka Raja Maha Viharaya'),
    'osm_node_1743126585': ('Embekka Devalaya', 'Embekka Devale'),
}

REQUIRED_REGISTER = {'attraction_id', 'image_file', 'district', 'final_image_decision',
                     'creator', 'license', 'source_page'}
REQUIRED_REPORT = {'attraction_id', 'target_name', 'attraction_name', 'image_file',
                   'download_status', 'creator', 'license', 'license_url', 'source_page'}


def read_csv(path):
    if not path.is_file():
        raise SystemExit(f'Missing file: {path}')
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit(f'Empty or invalid CSV: {path}')
        return list(reader), list(reader.fieldnames)


def clean_credit(raw):
    return ' '.join(html.unescape(re.sub(r'<[^>]*>', ' ', raw or '')).split())


def safe_commons_source(url):
    parts = urlparse(url)
    return (parts.scheme == 'https' and parts.netloc.lower() == 'commons.wikimedia.org'
            and parts.path.startswith('/wiki/File:'))


def acceptable_license(name, url):
    label = re.sub(r'\s+', ' ', name or '').strip().upper()
    uri = urlparse(url or '')
    if uri.scheme != 'https' or uri.netloc.lower() not in ('creativecommons.org', 'www.creativecommons.org'):
        return False
    if re.fullmatch(r'CC BY(?:-SA)? [1-9](?:\.\d+)?', label):
        return uri.path.startswith('/licenses/by/') if 'BY-SA' not in label else uri.path.startswith('/licenses/by-sa/')
    if label in ('CC0', 'CC0 1.0'):
        return uri.path.startswith('/publicdomain/zero/')
    return False  # Other rights labels require manual evaluation.


def main():
    existing, cols = read_csv(ACTIVE)
    report, report_cols = read_csv(REPORT)
    if not REQUIRED_REGISTER.issubset(cols):
        raise SystemExit(f'Register missing columns: {sorted(REQUIRED_REGISTER - set(cols))}')
    if not REQUIRED_REPORT.issubset(report_cols):
        raise SystemExit(f'Kandy report missing columns: {sorted(REQUIRED_REPORT - set(report_cols))}')
    existing_ids = [r['attraction_id'].strip() for r in existing]
    if not all(existing_ids) or len(existing_ids) != len(set(existing_ids)):
        raise SystemExit('Register has blank or duplicate attraction IDs; refusing to edit.')
    if len(report) != len(EXPECTED) or {r['attraction_id'].strip() for r in report} != set(EXPECTED):
        raise SystemExit('Kandy report does not contain exactly the five expected OSM IDs. No changes made.')

    new_rows = []
    already = []
    issues = []
    for r in report:
        aid = r['attraction_id'].strip()
        target, dataset_name = EXPECTED[aid]
        if aid in existing_ids:
            already.append(target + ' (existing record preserved)')
            continue
        filename = r['image_file'].strip()
        creator = clean_credit(r['creator'])
        license_name = clean_credit(r['license'])
        license_url = r['license_url'].strip()
        source = r['source_page'].strip()
        checks = []
        if r['target_name'].strip() != target or r['attraction_name'].strip() != dataset_name:
            checks.append('unexpected target or dataset name')
        if r['download_status'].strip().upper() not in ('DOWNLOADED', 'EXISTS'):
            checks.append('download status is not DOWNLOADED/EXISTS')
        if not filename.startswith('kandy_') or Path(filename).name != filename or not re.fullmatch(r'[A-Za-z0-9_.-]+', filename):
            checks.append('invalid/unexpected filename')
        elif not (IMAGES / filename).is_file() or (IMAGES / filename).stat().st_size < 1024:
            checks.append('image missing or unusually small')
        if not creator or creator.lower() in ('unknown', 'none', 'nan'):
            checks.append('creator missing')
        if not acceptable_license(license_name, license_url):
            checks.append('license or license URL needs manual confirmation')
        if not safe_commons_source(source):
            checks.append('source is not a Wikimedia Commons File page')
        if checks:
            issues.append(f'{target}: {", ".join(checks)}')
            continue

        row = {col: '' for col in cols}
        values = {
            'attraction_id': aid,
            'dataset_attraction_name': dataset_name,
            'district': 'Kandy',
            'photo_attraction_name': target,
            'image_file': filename,
            'match_type': 'verified_dataset_id_and_user_visual_check',
            'review_status': 'user_confirmed_visual_match; Commons metadata recorded; license not independently audited',
            'source_page': source,
            'creator': creator,
            'license': license_name,
            'license_url': license_url,
            'location_match_status': 'user_confirmed_visual_match',
            'dashboard_image_approved': 'True',
            'final_image_decision': 'approved',
        }
        for key, value in values.items():
            if key in row:
                row[key] = value
        new_rows.append(row)

    if issues:
        print('STOPPED: no register changes made. Fix these Kandy report issues:')
        for issue in issues:
            print(' -', issue)
        raise SystemExit(1)
    if not new_rows:
        print('Nothing to add: all five Kandy attraction IDs already exist. Register unchanged.')
        for item in already:
            print(' -', item)
        return

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup = ACTIVE.with_name('attraction_image_final_review_backup_before_kandy_' + stamp + '.csv')
    shutil.copy2(ACTIVE, backup)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8-sig', newline='',
                                         dir=ACTIVE.parent, prefix='_kandy_register_',
                                         suffix='.tmp', delete=False) as f:
            tmp_path = Path(f.name)
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(existing)
            writer.writerows(new_rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, ACTIVE)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()

    print('SUCCESS: Kandy register updated.')
    print('Original records preserved:', len(existing))
    print('New Kandy photos approved:', len(new_rows))
    print('Already registered and untouched:', len(already))
    print('Total register records:', len(existing) + len(new_rows))
    print('Backup:', backup)
    print('Register:', ACTIVE)
    print('Keep the creator, license, license URL and Commons source with each public photo.')
    for item in already:
        print(' -', item)


if __name__ == '__main__':
    main()
