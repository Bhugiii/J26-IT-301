"""TravelMind: conservative Wikimedia Commons candidates for 15 actual Hambantota OSM records.
Run in project root: python download_hambantota_15.py
Requires: requests, certifi. Never alters the approved image register.
"""
from __future__ import annotations
import csv
import html
import random
import re
import time
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests
import certifi

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / 'data/processed/travelmind_combined_clusters.csv'
OUT = ROOT / 'config/photo_candidates'
PHOTOS = ROOT / 'assets/images/attractions'
OUT.mkdir(parents=True, exist_ok=True)
PHOTOS.mkdir(parents=True, exist_ok=True)

# Exact names / IDs from the uploaded Hambantota dataset.
TARGETS = [
 ('osm_node_917949443', 'Hummanaya Blow Hole', 'Hummanaya blowhole Sri Lanka', 'hummanaya', 'blowhole'),
 ('osm_node_1841305525', 'Mulkirigala Rock Monastery', 'Mulkirigala Rock Temple Sri Lanka', 'mulkirigala', 'mulkirigala'),
 ('osm_way_276217774', 'Tissamaharama Dagoba', 'Tissamaharama stupa Sri Lanka', 'tissamaharama', 'tissamaharama'),
 ('osm_way_403504647', 'Yatala Vehera', 'Yatala Vehera Tissamaharama Sri Lanka', 'yatala', 'yatala'),
 ('osm_node_3963028579', 'Sithulpawwa Raja Maha Viharaya', 'Sithulpawwa temple Sri Lanka', 'sithulpawwa', 'sithulpawwa'),
 ('osm_node_1727709341', 'Kirinda Viharaya', 'Kirinda temple Sri Lanka', 'kirinda', 'kirinda'),
 ('osm_node_4439432082', 'Marakolliya Beach', 'Marakolliya Beach Tangalle Sri Lanka', 'marakolliya', 'marakolliya'),
 ('osm_way_187932863', 'kalamatiya Bird Sanctuary', 'Kalametiya bird sanctuary Sri Lanka', 'kalametiya', 'kalamatiya'),
 ('osm_way_816769045', 'Ridiyagama Safari Park', 'Ridiyagama safari park Sri Lanka', 'ridiyagama', 'ridiyagama'),
 ('osm_node_1818567443', 'Madunagala Hot Water Springs', 'Madunagala hot water springs Sri Lanka', 'madunagala', 'madunagala'),
 ('osm_node_5627298468', 'Katuwana Dutch Fort', 'Katuwana Dutch Fort Sri Lanka', 'katuwana', 'katuwana'),
 ('osm_node_1727709368', 'Sandagiri Stupa', 'Sandagiri stupa Tissamaharama Sri Lanka', 'sandagiri', 'sandagiri'),
 ('osm_node_1818503804', 'Girihadu Raja Maha Viharaya', 'Girihadu Raja Maha Viharaya Hambantota', 'girihadu', 'girihadu'),
 ('osm_node_1841305519', 'Kasagala Raja Maha Viharaya', 'Kasagala Raja Maha Viharaya Sri Lanka', 'kasagala', 'kasagala'),
 ('osm_way_432124821', 'Christ Church Tangalla', 'Christ Church Tangalle Sri Lanka', 'tangalle', 'church'),
]

API = 'https://commons.wikimedia.org/w/api.php'
session = requests.Session()
session.verify = certifi.where()
session.headers.update({'User-Agent': 'TravelMindTourismPhotoResearch/1.0 (educational research; Wikimedia Commons photo metadata)', 'Accept': 'application/json'})
ALLOWED = ('cc-by-sa-', 'cc-by-', 'cc0', 'public domain', 'pd-')
REVIEW_FIELDS = ['attraction_id','attraction_name','district','image_file','download_status','review_note','creator','license','source_page','license_url','commons_title','image_width','image_height','final_image_decision']

def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', str(value or '')))).strip()

def api_query(params):
    for attempt in range(5):
        try:
            r = session.get(API, params=params, timeout=35)
            if r.status_code in (429, 500, 502, 503, 504):
                wait = min(100, 12 * 2 ** attempt) + random.uniform(0, 3)
                print(f'    Commons HTTP {r.status_code}; waiting {wait:.0f}s')
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == 4: raise
            print(f'    Request issue: {e}; retrying')
            time.sleep(min(60, 8 * (attempt + 1)))
    raise RuntimeError('Commons API requests were rate limited after retries')

def photo_candidate(query, required_a, required_b):
    args = {'action':'query','format':'json','formatversion':2,'generator':'search',
            'gsrsearch':f'filetype:bitmap {query}','gsrnamespace':6,'gsrlimit':12,
            'prop':'imageinfo','iiprop':'url|mime|size|extmetadata','iiurlwidth':1600}
    data = api_query(args)
    candidates = []
    for p in data.get('query',{}).get('pages',[]):
        title = p.get('title','')
        infos = p.get('imageinfo') or []
        if not infos: continue
        info = infos[0]
        if info.get('mime','') not in ('image/jpeg','image/png','image/webp'): continue
        title_lower = title.casefold()
        # A conservative requirement on the file TITLE, not just Commons search ranking.
        if required_a not in title_lower and required_b not in title_lower: continue
        meta = info.get('extmetadata') or {}
        license_name = clean(meta.get('LicenseShortName',{}).get('value',''))
        license_url = str(meta.get('LicenseUrl',{}).get('value','')).strip()
        if not any(w in (license_name + ' ' + license_url).casefold() for w in ALLOWED): continue
        creator = clean(meta.get('Artist',{}).get('value',''))
        if not creator: continue
        imgurl = info.get('thumburl') or info.get('url')
        if not imgurl: continue
        width = int(info.get('width',0) or 0)
        height = int(info.get('height',0) or 0)
        if width < 700 or height < 400: continue
        score = (4 if required_a in title_lower else 0) + (2 if required_b in title_lower else 0) + min(width, 2500)/2500
        candidates.append((score, {'title': title, 'creator': creator, 'license': license_name,
            'license_url': license_url, 'source_page': 'https://commons.wikimedia.org/wiki/' + quote(title.replace(' ', '_'), safe=':_()/'),
            'url': imgurl,'width':width,'height':height,'mime':info['mime']}))
    return max(candidates, key=lambda pair: pair[0])[1] if candidates else None

def main():
    d = pd.read_csv(DATASET, dtype={'attraction_id':str},low_memory=False)
    lookup = d.drop_duplicates('attraction_id').set_index('attraction_id')
    targets = []
    for aid,name,query,word1,word2 in TARGETS:
        if aid not in lookup.index: raise RuntimeError(f'Missing attraction ID: {aid}')
        r = lookup.loc[aid]
        if str(r['district']).strip().casefold() != 'hambantota' or str(r['attraction_name']).strip().casefold() != name.casefold():
            raise RuntimeError(f'Dataset mismatch for {aid}: {r["attraction_name"]} / {r["district"]}')
        targets.append({'attraction_id':aid,'attraction_name':name,'district':'Hambantota','tourism_category':r['tourism_category'],
                        'latitude':r['latitude'],'longitude':r['longitude'],'commons_search':query})
    with (OUT/'hambantota_15_targets.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=targets[0].keys());w.writeheader();w.writerows(targets)
    results=[]
    for i,(aid,name,query,word1,word2) in enumerate(TARGETS,1):
        print(f'[{i}/15] {name}', flush=True)
        row=dict.fromkeys(REVIEW_FIELDS,'')
        row.update(attraction_id=aid,attraction_name=name,district='Hambantota',final_image_decision='pending')
        try:
            candidate = photo_candidate(query,word1,word2)
            if not candidate:
                row.update(download_status='skipped',review_note='No conservatively named, licensed Commons candidate with creator metadata')
            else:
                ext = '.png' if candidate['mime']=='image/png' else '.webp' if candidate['mime']=='image/webp' else '.jpg'
                filename = 'hambantota_' + re.sub(r'[^a-z0-9]+','_',name.lower()).strip('_') + ext
                filepath = PHOTOS / filename
                # Never replace existing local photo files silently.
                if filepath.exists() and filepath.stat().st_size > 15000:
                    status='existing'
                else:
                    resp=session.get(candidate['url'],timeout=75);resp.raise_for_status()
                    if not resp.headers.get('Content-Type','').startswith('image/') or len(resp.content)<15000:
                        raise ValueError('Download response was not a usable image')
                    filepath.write_bytes(resp.content)
                    status='downloaded'
                row.update(image_file=filename,download_status=status,review_note='PHOTO PENDING: verify depicted location and Commons license on source page',
                    creator=candidate['creator'],license=candidate['license'],source_page=candidate['source_page'],license_url=candidate['license_url'],
                    commons_title=candidate['title'],image_width=candidate['width'],image_height=candidate['height'])
                print(f'    {status.upper()}: {filename}')
        except (requests.RequestException,ValueError,RuntimeError) as e:
            row.update(download_status='error',review_note=str(e)[:250]);print('    ERROR:',str(e)[:180])
        results.append(row)
        # Avoid Commons API hammering, including after unsuccessful searches.
        if i < len(TARGETS): time.sleep(5 + random.uniform(0,2))
        # Persist after each attraction, including when later requests fail.
        with (OUT/'hambantota_download_review.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=REVIEW_FIELDS);w.writeheader();w.writerows(results)
    good=sum(r['download_status'] in ('downloaded','existing') for r in results)
    print(f'\nDownloaded or existing: {good}/15')
    print('Review CSV:',(OUT/'hambantota_download_review.csv').resolve())
    print('NO photos approved. The main attraction_image_final_review.csv was not changed.')

if __name__=='__main__':
    main()
