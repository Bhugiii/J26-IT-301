"""Safely approve selected Colombo photos for TravelMind, after human review.
Run from project root: python approve_colombo_photos_one_step.py
"""
from pathlib import Path
from datetime import datetime
import csv
import shutil
import os

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / 'config/photo_candidates/colombo_download_review.csv'
REGISTER = ROOT / 'config/attraction_image_final_review.csv'
IMAGES = ROOT / 'assets/images/attractions'
DATASET = ROOT / 'data/processed/travelmind_combined_clusters.csv'
# These are location-focused photos based on their Commons file titles.
# The zoo photo shows a bear, and Diyasaru's shows a bird; don't automatically
# treat these as general destination illustrations.
HOLD_IDS = {'osm_way_48893708', 'osm_way_963176277'}
ALLOWED_LICENSES = {
    'CC0', 'CC BY 2.0', 'CC BY 3.0', 'CC BY 4.0',
    'CC BY-SA 2.0', 'CC BY-SA 3.0', 'CC BY-SA 4.0',
}

def read_csv(path):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return list(reader), (reader.fieldnames or [])

def main():
    for p in (REPORT, REGISTER, DATASET):
        if not p.is_file():
            raise SystemExit(f'Missing required file: {p}')
    report, report_fields = read_csv(REPORT)
    previous, fields = read_csv(REGISTER)
    dataset, _ = read_csv(DATASET)
    district_ids = {str(r.get('attraction_id', '')).strip() for r in dataset
                    if str(r.get('district', '')).strip().casefold() == 'colombo'}
    required = {'attraction_id','image_file','final_image_decision'}
    if not required.issubset(fields):
        raise SystemExit('Existing register is missing required columns; no changes made.')
    required_report = {'district','attraction_id','attraction_name','image_file',
                       'download_status','creator','license','license_url','source_page'}
    if not required_report.issubset(report_fields):
        raise SystemExit('Download report missing required columns; no changes made.')
    seen = {str(r.get('attraction_id','')).strip() for r in previous}
    staged, held, skipped, problems = [], [], [], []
    batch_ids = set()
    for r in report:
        aid = r['attraction_id'].strip()
        name = r['attraction_name'].strip()
        status = r['download_status'].strip().upper()
        if r['district'].strip().casefold() != 'colombo':
            problems.append(f'{name}: unexpected district')
            continue
        if not aid or aid in batch_ids:
            problems.append(f'{name}: duplicate or blank report attraction ID')
            continue
        batch_ids.add(aid)
        if status not in ('DOWNLOADED', 'EXISTING'):
            skipped.append(f'{name}: {status}')
            continue
        if aid in HOLD_IDS:
            held.append(f'{name}: place-detail photo requires separate review')
            continue
        if aid in seen:
            skipped.append(f'{name}: already in register (left unchanged)')
            continue
        filename = r['image_file'].strip()
        licence = r['license'].strip()
        creator = r['creator'].strip()
        source = r['source_page'].strip()
        licence_url = r['license_url'].strip()
        if aid not in district_ids:
            problems.append(f'{name}: attraction ID not in Colombo dataset')
        elif not filename or Path(filename).name != filename or not (IMAGES / filename).is_file():
            problems.append(f'{name}: photo file missing or unsafe filename: {filename}')
        elif not creator or licence not in ALLOWED_LICENSES:
            problems.append(f'{name}: missing creator or unrecognized license: {licence}')
        elif not source.startswith('https://commons.wikimedia.org/wiki/File:'):
            problems.append(f'{name}: missing/invalid Commons file source')
        elif not licence_url.startswith('https://creativecommons.org/'):
            problems.append(f'{name}: missing/invalid license URL')
        else:
            entry = {k: '' for k in fields}
            entry.update({k:r[k].strip() for k in ('attraction_id','image_file','creator','license','license_url','source_page') if k in fields})
            if 'attraction_name' in fields:
                entry['attraction_name'] = name
            if 'district' in fields:
                entry['district'] = 'Colombo'
            if 'commons_title' in fields:
                entry['commons_title'] = r.get('commons_title','').strip()
            entry['final_image_decision'] = 'approved'
            staged.append(entry)
    print(f'Existing register records: {len(previous)}')
    print(f'Colombo photos eligible for confirmation: {len(staged)}')
    print(f'Held (not eligible): {len(held)}')
    print(f'Skipped: {len(skipped)}')
    for msg in held + skipped:
        print(' -', msg)
    if problems:
        print('\nVALIDATION PROBLEMS (nothing changed):')
        for msg in problems: print(' -', msg)
        raise SystemExit('Resolve problems before trying to approve.')
    if not staged:
        print('Nothing new to approve. Register unchanged.')
        return
    print('\nConfirm EACH listed image depicts its exact attraction and check Commons license/attribution conditions:')
    names = {r['attraction_id'].strip():r['attraction_name'].strip() for r in report}
    for r in staged: print(' -', names[r['attraction_id']], '=>', r['image_file'])
    print('\nType APPROVE to add only the photos listed above. Anything else cancels.')
    if input('Confirmation: ').strip() != 'APPROVE':
        print('Cancelled. Existing register unchanged.')
        return
    now = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = REGISTER.with_name(f'{REGISTER.stem}_backup_before_colombo_{now}.csv')
    shutil.copy2(REGISTER, backup)
    temp = REGISTER.with_name(REGISTER.name + '.tmp')
    try:
        with temp.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(previous + staged)
        os.replace(temp, REGISTER)
    finally:
        if temp.exists(): temp.unlink()
    print(f'Approved NEW Colombo photos: {len(staged)}')
    print(f'Total register records: {len(previous) + len(staged)}')
    print(f'Backup: {backup}')
    print(f'Updated: {REGISTER}')

if __name__ == '__main__':
    main()
