"""TravelMind: approve seven visually reviewed Matale photos safely.

Run from the project root: python approve_matale_photos.py
Does not download photos or overwrite existing approved attraction IDs.
"""
from pathlib import Path
from datetime import datetime
import shutil
import pandas as pd

ROOT = Path(__file__).resolve().parent
ACTIVE = ROOT / 'config' / 'attraction_image_final_review.csv'
STAGED = ROOT / 'config' / 'photo_candidates' / 'attraction_image_final_review_with_matale_pending.csv'
IMAGE_DIR = ROOT / 'assets' / 'images' / 'attractions'
EXPECTED = {
    'osm_way_217591865': 'matale_sigiriya.jpg',
    'osm_way_258787124': 'matale_pidurangala.jpg',
    'osm_way_316427428': 'matale_nalanda_gedige.jpg',
    'osm_node_5589539521': 'matale_ibbankatuwa_megalithic_burial_site.jpg',
    'osm_node_4112028263': 'matale_riverston.jpg',
    'osm_node_5043038322': 'matale_sera_ella_water_fall.jpg',
    'osm_node_6127982022': 'matale_kaludiya_pokuna.jpg',
}


def main():
    for p in (ACTIVE, STAGED):
        if not p.is_file():
            raise SystemExit(f'Missing file: {p}')
    active = pd.read_csv(ACTIVE, dtype=str, keep_default_na=False)
    staged = pd.read_csv(STAGED, dtype=str, keep_default_na=False)
    required = {'attraction_id', 'image_file', 'final_image_decision', 'creator', 'license', 'source_page'}
    for label, df in [('active', active), ('staged', staged)]:
        if not required.issubset(df.columns):
            raise SystemExit(f'{label} register missing columns: {sorted(required - set(df.columns))}')
        if df.attraction_id.duplicated().any():
            raise SystemExit(f'{label} register has duplicate attraction IDs; inspect before continuing.')
    if list(active.columns) != list(staged.columns):
        raise SystemExit('Register columns differ. Stop rather than risk losing data.')

    original = active.set_index('attraction_id')
    proposed = staged.set_index('attraction_id')
    missing_original = set(original.index) - set(proposed.index)
    if missing_original:
        raise SystemExit(f'Staged CSV omits existing records: {sorted(missing_original)[:5]}')
    # Ensure absolutely no active record is changed in the staged CSV.
    for aid in original.index:
        if not original.loc[aid].equals(proposed.loc[aid]):
            raise SystemExit(f'Staged CSV modifies an existing record ({aid}); stop and review.')

    if any(aid in original.index for aid in EXPECTED):
        raise SystemExit('Some Matale IDs are already in the active register. No changes made.')
    for aid, filename in EXPECTED.items():
        if aid not in proposed.index:
            raise SystemExit(f'Missing staged Matale ID: {aid}')
        row = proposed.loc[aid]
        if row['image_file'] != filename or row.get('district', '').strip().lower() != 'matale':
            raise SystemExit(f'Incorrect photo/district pairing for {aid}')
        if row['final_image_decision'].strip().lower() != 'pending':
            raise SystemExit(f'Expected pending decision for {aid}')
        if any(not row[col].strip() for col in ('creator', 'license', 'source_page')):
            raise SystemExit(f'Missing photo credit/license/source for {aid}')
        if not row['source_page'].startswith('https://commons.wikimedia.org/wiki/File:'):
            raise SystemExit(f'Unexpected photo source for {aid}')
        if not (IMAGE_DIR / filename).is_file():
            raise SystemExit(f'Image file not found: {IMAGE_DIR / filename}')

    if set(proposed.index) - set(original.index) != set(EXPECTED):
        raise SystemExit('Staged CSV contains unexpected extra IDs. No changes made.')

    approved = staged.copy()
    mask = approved.attraction_id.isin(EXPECTED)
    approved.loc[mask, 'final_image_decision'] = 'approved'
    if 'review_status' in approved.columns:
        approved.loc[mask, 'review_status'] = (
            'user_confirmed_visual_match; Commons metadata recorded; '
            'license/coordinates not independently rechecked'
        )
    if 'dashboard_image_approved' in approved.columns:
        approved.loc[mask, 'dashboard_image_approved'] = 'True'

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = ACTIVE.with_name(f'attraction_image_final_review_backup_before_matale_{timestamp}.csv')
    shutil.copy2(ACTIVE, backup)
    temp = ACTIVE.with_name('_photo_register_matale_update.tmp')
    try:
        approved.to_csv(temp, index=False)
        temp.replace(ACTIVE)
    finally:
        if temp.exists():
            temp.unlink()
    print(f'Backup created: {backup}')
    print(f'Updated register: {ACTIVE}')
    print(f'Matale photo approvals added: {len(EXPECTED)}')
    print(f'Total register records: {len(approved)}')
    print('Previously approved photos preserved. Dambulla Cave Temple unchanged.')
    print('Keep Commons creator/license attribution and verify publication rights before public release.')


if __name__ == '__main__':
    main()
