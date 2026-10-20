"""TravelMind: safely stage Matale Commons photographs for review.

Run from the main TravelMind project folder:
    python merge_matale_photos_pending.py

Does NOT change config/attraction_image_final_review.csv or approve photos.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
REGISTER = ROOT / 'config' / 'attraction_image_final_review.csv'
REPORT = ROOT / 'config' / 'photo_candidates' / 'matale_download_review.csv'
IMAGE_DIR = ROOT / 'assets' / 'images' / 'attractions'
OUTPUT = ROOT / 'config' / 'photo_candidates' / 'attraction_image_final_review_with_matale_pending.csv'


def main():
    for path in (REGISTER, REPORT):
        if not path.is_file():
            raise SystemExit(f'Missing required CSV: {path}')

    existing = pd.read_csv(REGISTER, dtype=str).fillna('')
    report = pd.read_csv(REPORT, dtype=str).fillna('')
    needed = {'attraction_id', 'attraction_name', 'image_file', 'download_status',
              'commons_file_page', 'creator_from_commons', 'license_from_commons', 'license_url'}
    if not needed.issubset(report.columns):
        raise SystemExit(f'Download report missing fields: {sorted(needed - set(report.columns))}')
    if 'attraction_id' not in existing.columns or 'final_image_decision' not in existing.columns:
        raise SystemExit('The original register does not contain expected ID/decision fields.')

    matches = ROOT / 'data' / 'processed' / 'travelmind_combined_clusters.csv'
    locations = {}
    if matches.is_file():
        df = pd.read_csv(matches, low_memory=False,
                         usecols=['attraction_id', 'attraction_name', 'district', 'latitude', 'longitude'],
                         dtype={'attraction_id': str})
        locations = {str(r['attraction_id']): r for _, r in df.iterrows()}

    existing_ids = set(existing['attraction_id'].astype(str))
    additions = []
    skipped = []
    for _, photo in report.iterrows():
        aid = photo['attraction_id'].strip()
        filename = photo['image_file'].strip()
        if photo['download_status'].strip().lower() != 'downloaded':
            skipped.append(f"{photo['attraction_name']}: not downloaded")
            continue
        if not aid or aid in existing_ids:
            skipped.append(f"{photo['attraction_name']}: existing attraction ID (preserved)")
            continue
        if not filename or Path(filename).name != filename or not (IMAGE_DIR / filename).is_file():
            skipped.append(f"{photo['attraction_name']}: image file not found")
            continue
        if not photo['commons_file_page'].startswith('https://commons.wikimedia.org/wiki/File:'):
            skipped.append(f"{photo['attraction_name']}: Commons file page not valid")
            continue
        if not photo['creator_from_commons'] or not photo['license_from_commons']:
            skipped.append(f"{photo['attraction_name']}: missing creator or license")
            continue

        location = locations.get(aid, {})
        lat, lon = str(location.get('latitude', '') or ''), str(location.get('longitude', '') or '')
        name = str(location.get('attraction_name', '') or photo['attraction_name'])
        row = {col: '' for col in existing.columns}
        row.update({
            'attraction_id': aid,
            'dataset_attraction_name': name,
            'district': str(location.get('district', '') or photo.get('district', 'Matale')),
            'photo_attraction_name': photo['attraction_name'],
            'image_file': filename,
            'match_type': 'selected_dataset_id_pending_check',
            'review_status': 'pending_manual_review',
            'source_page': photo['commons_file_page'],
            'creator': photo['creator_from_commons'],
            'license': photo['license_from_commons'],
            'license_url': photo['license_url'],
            'location_match_status': 'pending_manual_check',
            'dashboard_image_approved': 'False',
            'latitude': lat,
            'longitude': lon,
            'google_maps_location': f'https://www.google.com/maps?q={lat},{lon}' if lat and lon else '',
            'final_image_decision': 'pending',
        })
        additions.append(row)
        existing_ids.add(aid)

    merged = pd.concat([existing, pd.DataFrame(additions, columns=existing.columns)], ignore_index=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUTPUT, index=False, encoding='utf-8-sig')
    print(f'Original register: {len(existing)} records (unchanged)')
    print(f'New Matale candidates staged: {len(additions)}')
    print(f'New CSV created: {OUTPUT}')
    print('The new candidates are PENDING, not approved for the Dashboard.')
    if skipped:
        print('\nSkipped:')
        for item in skipped:
            print(' -', item)


if __name__ == '__main__':
    main()
