"""Find Kandy photo-target candidates in the TravelMind attraction dataset.
Run from the project root: python match_kandy_attractions.py
This produces review suggestions only; it does not alter photo approvals.
"""
import csv
import difflib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / 'data/processed/travelmind_combined_clusters.csv'
OUTDIR = ROOT / 'config/photo_candidates'
OUTPUT = OUTDIR / 'kandy_photo_match_suggestions.csv'

TARGETS = [
    ('Temple of the Sacred Tooth Relic', ['Sri Dalada Maligawa', 'Temple of the Tooth', 'Dalada Maligawa']),
    ('Royal Botanical Gardens Peradeniya', ['Peradeniya Botanical Garden', 'Royal Botanic Gardens', 'Botanical Gardens']),
    ('Kandy Lake', ['Bogambara Lake', 'Kiri Muhuda']),
    ('Ambuluwawa Tower', ['Ambuluwawa', 'Ambuluwawa Biodiversity Complex']),
    ('Bahirawakanda Buddha Statue', ['Bahirawakanda', 'Bahirawa Kanda', 'Bahirawakanda Vihara']),
    ('Udawattakele Forest Reserve', ['Udawatta Kele', 'Udawattakelle', 'Udawattakele Sanctuary']),
    ('Gadaladeniya Temple', ['Gadaladeniya Viharaya', 'Gadaladeniya']),
    ('Lankatilaka Temple', ['Lankathilaka', 'Lankatilaka Viharaya', 'Lankatilake']),
    ('Embekka Devalaya', ['Embekke', 'Embekka', 'Embekke Devalaya']),
    ('Commonwealth War Cemetery Kandy', ['Kandy War Cemetery', 'War Cemetery']),
]

def normal(s):
    return ' '.join(re.findall(r'[a-z0-9]+', str(s).casefold()))

def main():
    if not INPUT.exists():
        raise SystemExit(f'Dataset not found: {INPUT}\nRun the script from your TravelMind project folder.')
    with INPUT.open('r', encoding='utf-8-sig', newline='') as fh:
        data = list(csv.DictReader(fh))
    needed = {'attraction_id', 'attraction_name', 'district', 'tourism_category', 'latitude', 'longitude'}
    if not data or not needed.issubset(data[0]):
        raise SystemExit(f'Missing required dataset columns: {sorted(needed - set(data[0] if data else []))}')
    kandy = [r for r in data if normal(r['district']) == 'kandy']
    if not kandy:
        raise SystemExit('No district=Kandy rows found; check district names in your dataset.')
    OUTDIR.mkdir(parents=True, exist_ok=True)
    cols = ['target_name', 'candidate_rank', 'attraction_id', 'attraction_name', 'district',
            'tourism_category', 'latitude', 'longitude', 'name_similarity', 'review_status']
    with OUTPUT.open('w', encoding='utf-8-sig', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for target, aliases in TARGETS:
            names = [normal(x) for x in [target] + aliases]
            scored = []
            for record in kandy:
                actual = normal(record['attraction_name'])
                if not actual:
                    continue
                score = max(difflib.SequenceMatcher(None, actual, n).ratio() for n in names)
                if actual in names:
                    score = 1.0
                scored.append((score, record))
            scored.sort(key=lambda x: (-x[0], x[1]['attraction_name']))
            for rank, (score, record) in enumerate(scored[:3], 1):
                writer.writerow({
                    'target_name': target, 'candidate_rank': rank,
                    **{k: record[k] for k in ['attraction_id', 'attraction_name', 'district',
                                               'tourism_category', 'latitude', 'longitude']},
                    'name_similarity': f'{score:.3f}', 'review_status': 'NEEDS_MANUAL_REVIEW'
                })
    print(f'Kandy records in dataset: {len(kandy)}')
    print(f'Created: {OUTPUT}')
    print('30 suggestions for 10 targets. Name scores are NOT confirmations of place identity.')
    print('Please upload the output CSV to review OSM IDs and coordinates before downloading photos.')

if __name__ == '__main__':
    main()
