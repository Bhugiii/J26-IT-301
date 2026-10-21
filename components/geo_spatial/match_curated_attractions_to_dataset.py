"""TravelMind — match curated district photo targets to the local OSM catalog.
Run from the project root: python match_curated_attractions_to_dataset.py
Only suggests matches; never edits the approved-photo CSV or downloads images.
"""
from pathlib import Path
from difflib import SequenceMatcher
from urllib.parse import quote
import re
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/processed/travelmind_combined_clusters.csv'
TARGETS = ROOT / 'config/photo_candidates/travelmind_24_districts_curated_photo_targets.csv'
OUT = ROOT / 'config/photo_candidates'

ALIASES = {
    'sigiriya rock fortress': ['sigiriya', 'lion rock'],
    'dambulla cave temple': ['dambulla cave', 'golden temple of dambulla', 'rangiri dambulla'],
    'pidurangala rock': ['pidurangala'],
    'nalanda gedige': ['nalanda'],
    'ibbankatuwa megalithic tombs': ['ibbankatuwa'],
    'riverston peak': ['riverston', 'riverstone'],
    'pitawala pathana': ['pitawala pathana', 'pitawala patana'],
    'sera ella waterfall': ['sera ella', 'sera falls'],
    'aluvihare rock temple': ['aluvihare', 'alu vihare'],
    'knuckles mountain range': ['knuckles'],
}

def normalize(text):
    text = str(text).casefold().replace('&', ' and ')
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return ' '.join(text.split())

def score(query, name):
    q, n = normalize(query), normalize(name)
    if not q or not n: return 0
    if q == n: return 100
    if q in n or n in q:
        return 89 if len(min((q,n), key=len)) >= 6 else 55
    return round(100 * SequenceMatcher(None, q, n).ratio())

if not DATA.is_file():
    raise SystemExit(f'Missing dataset: {DATA}')
if not TARGETS.is_file():
    raise SystemExit(f'Missing curated list: {TARGETS}\nDownload the CSV into config/photo_candidates/ first.')

attractions = pd.read_csv(DATA, dtype={'attraction_id': str}, low_memory=False).fillna('')
targets = pd.read_csv(TARGETS, dtype=str).fillna('')
for c in ('attraction_id','attraction_name','district','tourism_category'):
    if c not in attractions: raise SystemExit(f'Dataset missing column: {c}')
for c in ('district','proposed_attraction'):
    if c not in targets: raise SystemExit(f'Curated list missing column: {c}')
rows = []
for _, target in targets.iterrows():
    district = str(target['district']).strip()
    proposal = str(target['proposed_attraction']).strip()
    pool = attractions.loc[attractions.district.astype(str).str.strip().str.casefold().eq(district.casefold())]
    terms = [proposal] + ALIASES.get(normalize(proposal), [])
    scored = []
    for _, place in pool.iterrows():
        name = str(place.attraction_name)
        best = max(score(x, name) for x in terms)
        if best >= 46:
            scored.append((best, place))
    scored.sort(key=lambda x: (-x[0], str(x[1].attraction_name)))
    top = scored[:3]
    result = {
        'district': district,
        'priority': target.get('priority_within_district',''),
        'proposed_attraction': proposal,
        'suggested_match_name': str(top[0][1].attraction_name) if top else '',
        'suggested_attraction_id': str(top[0][1].attraction_id) if top else '',
        'suggested_category': str(top[0][1].tourism_category) if top else '',
        'match_score': int(top[0][0]) if top else 0,
        'match_status': 'REVIEW — possible match' if top else 'NOT FOUND — manual search needed',
        'other_dataset_options': ' | '.join(f'{p.attraction_name} [{p.attraction_id}] ({s})' for s,p in top[1:]),
        'commons_search': 'https://commons.wikimedia.org/w/index.php?search=' + quote(proposal + ' Sri Lanka') + '&title=Special:MediaSearch&type=image',
        'selected_photo_url': '', 'photographer': '', 'license': '',
        'photo_review_status': 'PENDING',
        'notes': 'Review district and exact place identity; do not auto-approve or infer popularity.'
    }
    rows.append(result)
result_df = pd.DataFrame(rows)
OUT.mkdir(parents=True,exist_ok=True)
all_path=OUT/'curated_24_district_dataset_match_suggestions.csv'
matale_path=OUT/'matale_photo_match_suggestions.csv'
result_df.to_csv(all_path,index=False,encoding='utf-8-sig')
result_df.loc[result_df.district.str.casefold().eq('matale')].to_csv(matale_path,index=False,encoding='utf-8-sig')
print(f'Created {all_path} ({len(result_df)} photo targets)')
print(f'Created {matale_path} ({sum(result_df.district.str.casefold().eq("matale"))} Matale targets)')
print('Matches are suggestions ONLY; please inspect each place before choosing photographs.')
