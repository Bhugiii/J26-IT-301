"""TravelMind: non-destructive geographic triage of major-destination candidates.

This is a SCREENING tool. Approximate anchors are manually provided reference
areas, not proof that an individual point is correct. No original file is changed.
"""
from pathlib import Path
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[2] if Path(__file__).resolve().parent.name == 'clustering' else Path.cwd()
SOURCE = ROOT / 'results/reports/overture_attraction_audit/major_destination_review_shortlist.csv'
OUT = ROOT / 'results/reports/overture_attraction_audit'

# Approximate area anchors, for anomaly screening only. Researcher must verify
# coordinates against authoritative maps, particularly for large parks/regions.
ANCHORS = {
    'Sigiriya': (7.957, 80.760, 8),
    'Pidurangala': (7.966, 80.762, 5),
    'Dambulla Cave Temple': (7.856, 80.649, 7),
    'Nine Arch Bridge': (6.877, 81.061, 5),
    'Galle Fort': (6.027, 80.217, 5),
    'Mirissa Beach': (5.949, 80.456, 5),
    'Unawatuna Beach': (6.008, 80.246, 6),
    'Horton Plains': (6.809, 80.805, 25),
    'Yala National Park': (6.36, 81.45, 60),
    'Temple of the Tooth': (7.294, 80.642, 5),
    'Polonnaruwa': (7.945, 81.000, 12),
    'Anuradhapura': (8.35, 80.40, 18),
}

def distance_km(lat1, lon1, lat2, lon2):
    a1, a2 = math.radians(lat1), math.radians(lat2)
    dlat = a2 - a1
    dlon = math.radians(lon2-lon1)
    h = math.sin(dlat/2)**2 + math.cos(a1)*math.cos(a2)*math.sin(dlon/2)**2
    return 12742*math.asin(min(1,math.sqrt(max(0,h))))

def main():
    if not SOURCE.exists():
        raise SystemExit(f'Missing shortlist: {SOURCE}\nRun the previous shortlist command first.')
    df = pd.read_csv(SOURCE, low_memory=False)
    required = {'destination_search','catalog_id','place_name','source','latitude','longitude'}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f'Shortlist is missing columns: {sorted(missing)}')
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    def classify(row):
        dest = str(row['destination_search'])
        if dest not in ANCHORS or pd.isna(row['latitude']) or pd.isna(row['longitude']):
            return pd.Series({'distance_from_area_km':float('nan'), 'review_priority':'unknown_location'})
        lat, lon, radius = ANCHORS[dest]
        km = distance_km(lat,lon,float(row['latitude']),float(row['longitude']))
        return pd.Series({'distance_from_area_km':round(km,2),
                          'review_priority':'high_location_mismatch' if km>radius else 'within_approximate_area_review'})
    df = pd.concat([df,df.apply(classify,axis=1)],axis=1)
    # Potential duplicate or category conflict remains a review condition even if near anchor.
    df['needs_manual_review'] = True
    df['reference_area_note'] = 'Approximate destination anchor only; not a verified landmark coordinate.'
    OUT.mkdir(parents=True,exist_ok=True)
    output = OUT / 'major_destination_location_review.csv'
    df.sort_values(['review_priority','destination_search','distance_from_area_km'],ascending=[True,True,False]).to_csv(output,index=False,encoding='utf-8-sig')
    print('REVIEW OUTPUT:',output)
    print('ROWS:',len(df))
    print('\nLOCATION SCREENING:')
    print(df['review_priority'].value_counts(dropna=False).to_string())
    print('\nBY DESTINATION:')
    print(pd.crosstab(df['destination_search'],df['review_priority']).to_string())
    bad = df[df['review_priority'].eq('high_location_mismatch')].sort_values('distance_from_area_km',ascending=False)
    print('\nTOP 15 LOCATION MISMATCHES:')
    print(bad[['destination_search','place_name','source','distance_from_area_km']].head(15).to_string(index=False))
    print('\nCAUTION: No record was independently verified or made visible to tourists.')

if __name__=='__main__':
    main()
