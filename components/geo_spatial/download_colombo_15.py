"""TravelMind Colombo: download Wikimedia Commons photo *candidates* (never auto-approve).
Run from TravelMind project root: python download_colombo_15.py
Requires: requests, certifi, pandas. Respects 429 rate limits and existing image files.
"""
from pathlib import Path
import html
import json
import re
import time
from urllib.parse import quote
import requests
import certifi
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/processed/travelmind_combined_clusters.csv'
OUT = ROOT / 'config/photo_candidates'
IMAGES = ROOT / 'assets/images/attractions'
OUT.mkdir(parents=True, exist_ok=True)
IMAGES.mkdir(parents=True, exist_ok=True)
API = 'https://commons.wikimedia.org/w/api.php'
TARGETS = [
    ('osm_node_3307527165', 'Lotus Tower', 'Colombo Lotus Tower', ['Colombo Lotus Tower','Nelum Kuluna']),
    ('osm_way_27712165', 'Galle Face Green', 'Galle Face Green', ['Galle Face Green Colombo']),
    ('osm_way_1078848223', 'Independence Memorial Hall', 'Independence Memorial Hall', ['Independence Memorial Hall Colombo']),
    ('osm_way_138991604', 'National Museum of Colombo', 'Colombo National Museum', ['Colombo National Museum','National Museum Colombo']),
    ('osm_way_22323428', 'Vihara Maha Devi Park', 'Viharamahadevi Park', ['Viharamahadevi Park Colombo','Victoria Park Colombo']),
    ('osm_node_269366454', 'Gangaramaya Temple', 'Gangaramaya Temple Colombo', ['Gangaramaya Temple Colombo']),
    ('osm_node_3416931209', 'Seethawaka Wet Zone Botanical Garden', 'Seethawaka Botanical Garden', ['Seethawaka Botanical Garden','Seethawaka Wet Zone Botanical Garden']),
    ('osm_way_48893708', 'National Zoological Gardens', 'Dehiwala Zoological Gardens', ['Dehiwala Zoo Sri Lanka','National Zoological Gardens Dehiwala']),
    ('osm_node_4354445603', 'Dutch Colonial Museum', 'Colombo Dutch Museum', ['Colombo Dutch Museum','Dutch Period Museum Colombo']),
    ('osm_way_303907118', 'Pettah Floating Market', 'Pettah Floating Market', ['Pettah Floating Market Colombo']),
    ('osm_way_1465741240', 'Old Colombo Lighthouse;Chatham Street Clock Tower', 'Chatham Street Clock Tower', ['Old Colombo Lighthouse Chatham Street','Chatham Street Clock Tower']),
    ('osm_way_669628774', 'Beddagana Wetland park', 'Beddagana Wetland Park', ['Beddagana Wetland Park Sri Lanka']),
    ('osm_way_963176277', 'Diyasaru Park', 'Diyasaru Park', ['Diyasaru Park Thalawathugoda']),
    ('osm_way_381878144', 'National Planetarium', 'Sri Lanka Planetarium Colombo', ['Sri Lanka Planetarium Colombo','Colombo Planetarium']),
    ('osm_way_741823188', 'Crow Island Beach Park', 'Crow Island Beach Park', ['Crow Island Beach Park Colombo']),
]

# The name should correspond to the photo subject, not merely mention the city.
STOP = {'colombo','sri','lanka','the','of','and','at','in','view','image','photo','photograph','with','from','national','park','temple','museum','old','building','gardens'}
LICENSES = ('cc by', 'cc-by', 'cc0', 'public domain', 'pdm', 'cc sa', 'cc-by-sa', 'cc by-sa')

def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', str(s or '')))).strip()

def tokens(s):
    return {t for t in re.findall(r'[a-z0-9]+', str(s).lower()) if len(t) > 2 and t not in STOP}

def verified_license(meta):
    code = clean(meta.get('LicenseShortName', {}).get('value', ''))
    link = clean(meta.get('LicenseUrl', {}).get('value', ''))
    usage = clean(meta.get('UsageTerms', {}).get('value', ''))
    combined = (code + ' ' + usage).lower()
    allowed = ('cc by', 'cc-by', 'cc0', 'public domain')
    # Exclude noncommercial/no-derivatives, which are not suitable for this workflow.
    return bool(any(v in combined for v in allowed) and not any(x in combined for x in ('-nc', '-nd', 'noncommercial', 'no derivatives'))), code, link

session = requests.Session()
session.verify = certifi.where()
session.headers.update({'User-Agent': 'TravelMindResearchPhotoReview/1.0 (educational photo candidate review; respectful API use)', 'Accept': 'application/json'})

def get(url, params=None, binary=False):
    for attempt in range(5):
        try:
            response = session.get(url, params=params, timeout=40)
            if response.status_code in (429, 500, 502, 503, 504):
                delay = min(90, int(response.headers.get('Retry-After', '0') or 0) or 8*(attempt+1)**2)
                print(f'    HTTP {response.status_code}: pausing {delay}s')
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response.content if binary else response.json()
        except (requests.RequestException, ValueError) as exc:
            if attempt == 4: raise
            time.sleep(6 * (attempt + 1))
    raise RuntimeError('Commons rate limit persisted after retries; try later')

def search(query):
    params = {'action':'query','format':'json','formatversion':'2',
              'generator':'search','gsrnamespace':'6', 'gsrsearch':'filetype:bitmap ' + query,
              'gsrlimit':12,'prop':'imageinfo','iiprop':'url|mime|size|extmetadata',
              'iiurlwidth':1400}
    obj = get(API, params)
    return obj.get('query', {}).get('pages', [])

def score_title(title, aliases):
    file_tokens = tokens(title.replace('File:', '').replace('_',' '))
    scores = []
    for alias in aliases:
        sig = tokens(alias)
        if sig:
            overlap = len(sig & file_tokens)
            scores.append((overlap/len(sig), overlap))
    return max(scores, default=(0.0,0))

def safe_ext(mime):
    return {'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}.get(mime)

records = pd.read_csv(DATA, dtype={'attraction_id':str}, low_memory=False)
records['district_norm'] = records['district'].fillna('').astype(str).str.strip().str.casefold()
by_id = records.set_index('attraction_id', drop=False)
rows, alternatives = [], []

for index, (aid, name, query, aliases) in enumerate(TARGETS, 1):
    print(f'[{index}/15] {name}', flush=True)
    row = {'district':'Colombo','attraction_id':aid,'attraction_name':name,
           'image_file':'','download_status':'','creator':'','license':'',
           'license_url':'','source_page':'','commons_title':'','note':''}
    if aid not in by_id.index:
        row['download_status'] = 'SKIPPED_ID_NOT_FOUND'
        row['note'] = 'Dataset ID absent; cannot link a photo safely'
        rows.append(row); continue
    actual = by_id.loc[aid]
    if isinstance(actual, pd.DataFrame): actual = actual.iloc[0]
    if actual['district_norm'] != 'colombo' or str(actual['attraction_name']).strip() != name:
        row['download_status'] = 'SKIPPED_DATASET_MISMATCH'
        row['note'] = f"Actual dataset: {actual['district']} / {actual['attraction_name']}"
        rows.append(row); continue
    candidates = []
    try:
        for term in [query] + aliases[:1]:
            for p in search(term):
                info = (p.get('imageinfo') or [{}])[0]
                ext = safe_ext(info.get('mime'))
                if not ext or int(info.get('width', 0)) < 640 or int(info.get('height', 0)) < 400:
                    continue
                meta = info.get('extmetadata') or {}
                ok, lic, lic_url = verified_license(meta)
                title = p.get('title', '')
                similarity, overlap = score_title(title, [query] + aliases)
                source = info.get('descriptionurl') or ('https://commons.wikimedia.org/wiki/' + quote(title.replace(' ', '_')))
                cand = {'title':title,'url':info.get('thumburl') or info.get('url', ''),
                        'source':source,'license':lic,'license_url':lic_url,
                        'creator':clean(meta.get('Artist',{}).get('value','')),
                        'score':similarity,'overlap':overlap,'license_ok':ok,'ext':ext}
                if not any(c['title'] == title for c in candidates):candidates.append(cand)
            time.sleep(4)
    except Exception as exc:
        row['download_status'] = 'ERROR'
        row['note'] = str(exc)[:200]
        rows.append(row)
        continue
    candidates.sort(key=lambda c: (c['license_ok'], c['score'], c['overlap']), reverse=True)
    for cand in candidates[:6]:
        alternatives.append({'attraction_id':aid,'attraction_name':name,'commons_title':cand['title'],
            'source_page':cand['source'],'license':cand['license'],'license_url':cand['license_url'],
            'creator':cand['creator'],'name_match_score':round(cand['score'],2),
            'license_eligible':cand['license_ok']})
    # Conservative: title must strongly identify the actual destination, and license must permit reuse.
    qualified = [c for c in candidates if c['license_ok'] and c['creator'] and c['url'] and c['license_url']
                 and c['score'] >= 0.80 and c['overlap'] >= 1]
    if not qualified:
        row['download_status']='REVIEW_NO_CONFIDENT_FILE'
        row['note']='Check alternatives CSV; no eligible photo filename confidently identified the site'
        rows.append(row); print('    No confident photo (see alternatives CSV)'); continue
    picked = qualified[0]
    slug = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:70]
    filename = 'colombo_' + slug + picked['ext']
    path = IMAGES / filename
    try:
        if path.exists() and path.stat().st_size > 10000:
            status='EXISTING'
        elif path.exists():
            status='SKIPPED_FILE_CONFLICT'
            row['note']='Existing filename is too small; refusing to overwrite'
        else:
            binary = get(picked['url'], binary=True)
            if len(binary) < 10000:raise ValueError('Downloaded image suspiciously small')
            path.write_bytes(binary)
            status='DOWNLOADED'
    except Exception as exc:
        status='ERROR';row['note']=str(exc)[:200]
    row.update({'download_status':status,'image_file':filename if status in ('EXISTING','DOWNLOADED') else '',
                'creator':picked['creator'],'license':picked['license'],
                'license_url':picked['license_url'],'source_page':picked['source'],
                'commons_title':picked['title']})
    rows.append(row)
    print(f'    {status}: {filename}')
    time.sleep(5)

report = OUT / 'colombo_download_review.csv'
alts = OUT / 'colombo_commons_alternatives.csv'
targetfile = OUT / 'colombo_15_targets.csv'
pd.DataFrame(rows).to_csv(report, index=False, encoding='utf-8-sig')
pd.DataFrame(alternatives, columns=['attraction_id','attraction_name','commons_title','source_page','license','license_url','creator','name_match_score','license_eligible']).to_csv(alts, index=False, encoding='utf-8-sig')
pd.DataFrame([{'attraction_id':a,'attraction_name':n,'search_query':q} for a,n,q,_ in TARGETS]).to_csv(targetfile,index=False,encoding='utf-8-sig')
print('\nDownloaded or existing:',sum(r['download_status'] in ('DOWNLOADED','EXISTING') for r in rows),'/15')
print('Review CSV:',report)
print('Alternatives CSV:',alts)
print('No photos were approved. Inspect each image and Commons page before approval.')
