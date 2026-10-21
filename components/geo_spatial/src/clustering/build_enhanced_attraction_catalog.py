"""Build a review-ready TravelMind attraction catalog without altering original files.
Run from TravelMind project root: python src/clustering/build_enhanced_attraction_catalog.py
"""
from pathlib import Path
import json
import re
import unicodedata
import pandas as pd

ROOT = Path.cwd()
OLD = ROOT / 'data/processed/travelmind_combined_clusters.csv'
NEW = ROOT / 'data/processed/overture_tourism/overture_attraction_candidates.csv'
AUDIT = ROOT / 'results/reports/overture_attraction_audit/overture_attraction_match_audit.csv'
OUT = ROOT / 'data/processed/travelmind_enhanced_attraction_catalog.csv'
SUMMARY = ROOT / 'results/reports/overture_attraction_audit/enhanced_catalog_summary.json'

for p in [OLD, NEW, AUDIT]:
    if not p.is_file():
        raise SystemExit(f'Missing input: {p}')
old, new, audit = (pd.read_csv(p, low_memory=False) for p in [OLD, NEW, AUDIT])
for field in ['attraction_name','latitude','longitude']:
    if field not in old.columns: raise SystemExit(f'OSM missing {field}')
for field in ['overture_id','place_name','latitude','longitude','basic_category','tourism_group']:
    if field not in new.columns: raise SystemExit(f'Overture missing {field}')
if 'screening_status' not in audit.columns:
    raise SystemExit(f'Audit missing screening_status; columns: {list(audit.columns)}')

# Audit joins MUST be based on stable IDs, not row order. Refuse ambiguity.
if 'overture_id' not in audit.columns:
    raise SystemExit(f'Audit missing overture_id; columns: {list(audit.columns)}')
if audit['overture_id'].duplicated().any():
    raise SystemExit('Audit has duplicate overture_id entries; inspect before continuing.')
if new['overture_id'].duplicated().any():
    raise SystemExit('Overture attraction file has duplicate overture_id entries; inspect before continuing.')
status_by_id = audit.set_index('overture_id')['screening_status']
new['screening_status'] = new['overture_id'].map(status_by_id)
if new['screening_status'].isna().any():
    raise SystemExit(f'{new.screening_status.isna().sum()} Overture rows lack audit status. Stop.')

# All Overture records are provisional, even when no OSM record matched.
def norm(s):
    return ' '.join(re.sub(r'[^\w\s]', ' ', unicodedata.normalize('NFKC', str(s)).casefold()).split())

# Conservative string-only flags intended to queue human checks, not prove bad coordinates.
SUSPICIOUS_NAME_CATEGORY = {
    'historic_site': r'\b(apartment|short stay|guesthouse|guest house|hotel|restaurant|salon|shop)\b',
    'beach': r'\b(fort|museum|hotel|restaurant|resort)\b',
}

def category_name_conflict(row):
    pattern = SUSPICIOUS_NAME_CATEGORY.get(str(row['basic_category']), '')
    return bool(pattern and re.search(pattern, norm(row['place_name'])))

flagged = new.apply(category_name_conflict, axis=1)

# A plain unified schema: every row has a source, source ID, category, geometry and review status.
old_ids = old['attraction_id'].astype('string') if 'attraction_id' in old.columns else pd.Series([str(i) for i in old.index],index=old.index)
old_records = pd.DataFrame({
    'catalog_id': 'osm:' + old_ids.fillna('unknown').astype(str),
    'source': 'original_osm_research',
    'source_record_id': old_ids.fillna('').astype(str),
    'place_name': old['attraction_name'].fillna('').astype(str),
    'basic_category': old['tourism_category'].fillna('').astype(str) if 'tourism_category' in old.columns else '',
    'tourism_group': 'original_tourism_attraction',
    'latitude': pd.to_numeric(old['latitude'], errors='coerce'),
    'longitude': pd.to_numeric(old['longitude'], errors='coerce'),
    'screening_status': 'original_research_record',
    'review_required': old['review_required'].fillna(True).astype(str).str.lower().isin(['true','1','yes']) if 'review_required' in old.columns else True,
    'potential_duplicate': old['suspected_duplicate'].fillna(False).astype(str).str.lower().isin(['true','1','yes']) if 'suspected_duplicate' in old.columns else False,
    'category_name_review': False,
    'dashboard_default_visible': True,  # Mirrors previous dataset, not validation.
    'verification_status': 'original_provisional',
})
new_records = pd.DataFrame({
    'catalog_id': 'overture:' + new['overture_id'].astype(str),
    'source': 'overture_places',
    'source_record_id': new['overture_id'].astype(str),
    'place_name': new['place_name'].fillna('').astype(str),
    'basic_category': new['basic_category'].fillna('').astype(str),
    'tourism_group': new['tourism_group'].fillna('').astype(str),
    'latitude': pd.to_numeric(new['latitude'], errors='coerce'),
    'longitude': pd.to_numeric(new['longitude'], errors='coerce'),
    'screening_status': new['screening_status'].astype(str),
    'review_required': True,
    'potential_duplicate': new['screening_status'].eq('possible_duplicate_name_within_150m') | new['screening_status'].eq('manual_review_near_existing_within_75m'),
    'category_name_review': flagged.to_numpy(),
    'dashboard_default_visible': False, # Explicit opt-in after manual/authoritative review.
    'verification_status': 'overture_unverified',
})
combined = pd.concat([old_records, new_records], ignore_index=True)
if combined['catalog_id'].duplicated().any():
    raise SystemExit('Duplicate catalog IDs found; no output saved.')
if combined[['latitude','longitude']].isna().any().any():
    raise SystemExit('Missing coordinates detected; review source before saving.')
OUT.parent.mkdir(parents=True, exist_ok=True)
SUMMARY.parent.mkdir(parents=True, exist_ok=True)
combined.to_csv(OUT, index=False, encoding='utf-8-sig')
counts = new['screening_status'].value_counts().to_dict()
summary = {
    'original_records_preserved': int(len(old_records)),
    'overture_review_candidates': int(len(new_records)),
    'catalog_rows': int(len(combined)),
    'overture_status_counts': {k:int(v) for k,v in counts.items()},
    'category_name_conflict_flags': int(flagged.sum()),
    'overture_dashboard_default_visible': 0,
    'warning': 'Staging catalog only. Unmatched is not verified. Original OSM records remain provisional too. Do not treat as cleaned deduplicated destination list.'
}
SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False),encoding='utf-8')
print('CATALOG CREATED:', OUT)
print('Original OSM:', len(old_records))
print('Overture review candidates:', len(new_records))
print('Combined staging rows:', len(combined))
print('Category-name conflict flags:', int(flagged.sum()))
print('Overture visibility default: OFF (review required)')
print('SUMMARY:', SUMMARY)
