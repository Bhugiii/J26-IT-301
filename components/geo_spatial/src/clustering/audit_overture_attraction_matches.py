"""Screen Overture attraction candidates against TravelMind's existing OSM layer.

This does not automatically validate places, remove originals, or publish a merge.
Run from the project root:
    python src/clustering/audit_overture_attraction_matches.py
"""
from pathlib import Path
import json
import re
import unicodedata

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

ROOT = Path.cwd()
OLD_PATH = ROOT / 'data/processed/travelmind_combined_clusters.csv'
NEW_PATH = ROOT / 'data/processed/overture_tourism/overture_attraction_candidates.csv'
OUT = ROOT / 'results/reports/overture_attraction_audit'
OUT.mkdir(parents=True, exist_ok=True)
EARTH_RADIUS_M = 6_371_008.8


def normalize(value):
    if pd.isna(value):
        return ''
    text = unicodedata.normalize('NFKC', str(value)).casefold()
    text = re.sub(r'[^\w\s]', ' ', text, flags=re.UNICODE)
    return ' '.join(text.split())


def valid_geo(data):
    data = data.copy()
    data['latitude'] = pd.to_numeric(data['latitude'], errors='coerce')
    data['longitude'] = pd.to_numeric(data['longitude'], errors='coerce')
    mask = (data['latitude'].between(-90, 90) & data['longitude'].between(-180, 180))
    return data[mask].reset_index(drop=True), int((~mask).sum())


def main():
    if not OLD_PATH.is_file() or not NEW_PATH.is_file():
        raise FileNotFoundError(f'Expected input files:\n{OLD_PATH}\n{NEW_PATH}')
    old = pd.read_csv(OLD_PATH, low_memory=False)
    new = pd.read_csv(NEW_PATH, low_memory=False)
    required_old = {'attraction_name', 'latitude', 'longitude'}
    required_new = {'overture_id', 'place_name', 'basic_category', 'latitude', 'longitude'}
    for label, df, cols in [('OSM', old, required_old), ('Overture', new, required_new)]:
        absent = cols - set(df.columns)
        if absent:
            raise ValueError(f'{label} file missing columns: {sorted(absent)}')
    old, bad_old = valid_geo(old)
    new, bad_new = valid_geo(new)
    if old.empty or new.empty:
        raise ValueError('No valid point coordinates in one of the source files.')
    old['normalized_name'] = old['attraction_name'].map(normalize)
    new['normalized_name'] = new['place_name'].map(normalize)
    old_coords = np.radians(old[['latitude', 'longitude']].to_numpy(dtype=float))
    new_coords = np.radians(new[['latitude', 'longitude']].to_numpy(dtype=float))
    tree = BallTree(old_coords, metric='haversine')
    distances, indices = tree.query(new_coords, k=1)
    new['nearest_osm_name'] = old['attraction_name'].iloc[indices[:, 0]].to_numpy()
    new['nearest_osm_distance_m'] = (distances[:, 0] * EARTH_RADIUS_M).round(1)
    new['nearest_osm_latitude'] = old['latitude'].iloc[indices[:, 0]].to_numpy()
    new['nearest_osm_longitude'] = old['longitude'].iloc[indices[:, 0]].to_numpy()
    new['nearest_osm_same_normalized_name'] = (new['normalized_name'].to_numpy() == old['normalized_name'].iloc[indices[:, 0]].to_numpy()) & new['normalized_name'].ne('').to_numpy()

    # Exact normalized name anywhere may correspond to distinct locations.
    known_names = set(old.loc[old['normalized_name'].ne(''), 'normalized_name'])
    new['name_found_anywhere_in_osm'] = new['normalized_name'].ne('') & new['normalized_name'].isin(known_names)

    # Check nearest OSM entry with the *same* name (which need not be nearest overall).
    name_to_positions = {}
    for pos, name in enumerate(old['normalized_name']):
        if name:
            name_to_positions.setdefault(name, []).append(pos)
    same_name_distances = np.full(len(new), np.nan)
    same_name_positions = np.full(len(new), -1, dtype=int)
    for name, positions in name_to_positions.items():
        rows = np.flatnonzero(new['normalized_name'].to_numpy() == name)
        if not len(rows):
            continue
        sub_tree = BallTree(old_coords[positions], metric='haversine')
        d, idx = sub_tree.query(new_coords[rows], k=1)
        same_name_distances[rows] = d[:, 0] * EARTH_RADIUS_M
        same_name_positions[rows] = np.asarray(positions)[idx[:, 0]]
    new['same_name_nearest_distance_m'] = np.round(same_name_distances, 1)
    new['same_name_nearest_osm_name'] = [old.at[p, 'attraction_name'] if p >= 0 else '' for p in same_name_positions]

    # Conservative automatic screening; NONE of these states is verified identity.
    same_name_close = new['name_found_anywhere_in_osm'] & new['same_name_nearest_distance_m'].le(150)
    near_other = new['nearest_osm_distance_m'].le(75)
    same_name_far = new['name_found_anywhere_in_osm'] & ~same_name_close
    new['screening_status'] = np.select(
        [same_name_close, near_other, same_name_far],
        ['possible_duplicate_name_within_150m',
         'manual_review_near_existing_within_75m',
         'same_name_but_not_within_150m'],
        default='candidate_unmatched_not_verified'
    )

    new['recommended_dashboard_action'] = 'hold_for_review'
    new['needs_manual_review'] = True
    new['source_system'] = 'Overture Places'
    audit_file = OUT / 'overture_attraction_match_audit.csv'
    new.to_csv(audit_file, index=False, encoding='utf-8-sig')
    summary = {
        'original_osm_rows_valid_coordinates': len(old),
        'overture_attraction_rows_valid_coordinates': len(new),
        'invalid_coordinate_rows_in_original': bad_old,
        'invalid_coordinate_rows_in_overture': bad_new,
        'name_matches_anywhere': int(new['name_found_anywhere_in_osm'].sum()),
        'screening_status_counts': {str(k): int(v) for k,v in new['screening_status'].value_counts().items()},
        'screening_rules': {
            'same_name_close_meters': 150,
            'nearby_different_name_meters': 75,
            'earth_radius_meters': EARTH_RADIUS_M,
            'notes': 'Distance is point-to-point great-circle distance, not road distance. Matching is not verification.'
        },
        'data_quality_note': 'Overture candidate names and category labels may be inaccurate or point to incorrect coordinates; all unreviewed records are held from public destination display.'
    }
    (OUT / 'overture_attraction_match_summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    new[['overture_id','place_name','basic_category','latitude','longitude','nearest_osm_name','nearest_osm_distance_m','same_name_nearest_distance_m','screening_status']].sort_values('nearest_osm_distance_m').head(100).to_csv(OUT/'closest_100_review.csv',index=False,encoding='utf-8-sig')
    print('OSM records with coordinates:', len(old))
    print('Overture attraction candidates:', len(new))
    print('Name matches somewhere in OSM:', summary['name_matches_anywhere'])
    print('\nSCREENING STATUS COUNTS (NOT VERIFIED):')
    print(new['screening_status'].value_counts().to_string())
    print('\nOUTPUTS:')
    print(audit_file)
    print(OUT / 'overture_attraction_match_summary.json')
    print(OUT / 'closest_100_review.csv')
    print('\nNo original source file or dashboard file was changed.')

if __name__ == '__main__':
    main()
