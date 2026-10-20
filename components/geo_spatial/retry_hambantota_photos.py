"""TravelMind: conservative second-pass Wikimedia Commons photo search for Hambantota.
Run from project root: python retry_hambantota_photos.py
Needs: requests, certifi (already installed for earlier batches).
Never modifies config/attraction_image_final_review.csv.
"""
from __future__ import annotations
import csv
import html
import re
import time
from pathlib import Path
from urllib.parse import quote

import certifi
import requests

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / 'config/photo_candidates/hambantota_download_review.csv'
OUT = ROOT / 'config/photo_candidates/hambantota_download_review_retry.csv'
SUGGESTIONS = ROOT / 'config/photo_candidates/hambantota_commons_alternatives.csv'
IMAGE_DIR = ROOT / 'assets/images/attractions'
API = 'https://commons.wikimedia.org/w/api.php'
# Only these dataset IDs (from the previously reviewed Matara/Hambantota batch) are handled.
SEARCHES = {
 'osm_node_917949443': ('Hummanaya Blowhole Sri Lanka', 'Kudawella Blowhole Sri Lanka'),
 'osm_way_276217774': ('Tissamaharama Dagoba Sri Lanka', 'Tissamaharama stupa'),
 'osm_way_403504647': ('Yatala Vehera Sri Lanka', 'Yatala dagoba Tissamaharama'),
 'osm_node_3963028579': ('Sithulpawwa Temple Sri Lanka', 'Situlpawwa Raja Maha Viharaya'),
 'osm_node_1727709341': ('Kirinda Viharaya Sri Lanka', 'Kirinda temple Sri Lanka'),
 'osm_node_4439432082': ('Marakolliya Beach Tangalle', 'Marakoliya Beach Sri Lanka'),
 'osm_way_187932863': ('Kalametiya Bird Sanctuary', 'Kalamatiya lagoon Sri Lanka'),
 'osm_way_816769045': ('Ridiyagama Safari Park', 'Ridiyagama Sri Lanka safari'),
 'osm_node_1818567443': ('Madunagala hot springs', 'Madunagala thermal springs Sri Lanka'),
 'osm_node_5627298468': ('Katuwana Dutch Fort', 'Katuwana fort Sri Lanka'),
 'osm_node_1727709368': ('Sandagiri Stupa Tissamaharama', 'Sandagiri dagoba Sri Lanka'),
 'osm_node_1818503804': ('Girihadu Raja Maha Viharaya Hambantota', 'Girihadu temple Hambantota'),
 'osm_node_1841305519': ('Kasagala Raja Maha Viharaya', 'Kasagala temple Sri Lanka'),
 'osm_way_432124821': ('Christ Church Tangalle', 'Christ Church Tangalla Sri Lanka'),
}
# A filename alone must identify the particular place, not merely the village/region.
CHECKS = {
 'osm_node_917949443': (('hummanaya',), ('kudawella','blowhole')),
 'osm_way_276217774': (('tissamaharama','dagoba'), ('tissamaharama','stupa'), ('tissamaharama','temple')),
 'osm_way_403504647': (('yatala',),),
 'osm_node_3963028579': (('sithulpawwa',), ('situlpawwa',), ('sithulpauwa',)),
 'osm_node_1727709341': (('kirinda','temple'), ('kirinda','viharaya')),
 'osm_node_4439432082': (('marakolliya',), ('marakoliya',)),
 'osm_way_187932863': (('kalametiya',), ('kalamatiya',)),
 'osm_way_816769045': (('ridiyagama','safari'), ('ridiyagama','park')),
 'osm_node_1818567443': (('madunagala',),),
 'osm_node_5627298468': (('katuwana','fort'),),
 'osm_node_1727709368': (('sandagiri',),),
 'osm_node_1818503804': (('girihadu',),),
 'osm_node_1841305519': (('kasagala',),),
 'osm_way_432124821': (('christ','church','tangalle'), ('christ','church','tangalla')),
}
EXT = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}

def norm(t):
    return re.sub(r'[^a-z0-9]+', ' ', html.unescape(str(t)).lower()).strip()

def clean_html(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value or ''))).strip()

def meta(info, key):
    return str((info.get('extmetadata') or {}).get(key, {}).get('value') or '').strip()

def licensed(info):
    short = clean_html(meta(info, 'LicenseShortName'))
    url = meta(info, 'LicenseUrl')
    creator = clean_html(meta(info, 'Artist'))
    # Metadata can mention source agencies without identifying a photographer; keep for manual checking.
    valid = bool(re.match(r'^(CC0|CC BY(?:-SA)?(?:\s|[-0-9.]|$)|Public domain)', short, re.I))
    return valid and bool(url and creator), creator, short, url

def get(session, url, *, params=None, stream=False):
    for attempt in range(4):
        try:
            resp = session.get(url, params=params, timeout=40, stream=stream, verify=certifi.where())
            if resp.status_code in (429, 500, 502, 503, 504):
                delay = min(100, 15 * (attempt + 1))
                header = resp.headers.get('Retry-After', '')
                if header.isdigit(): delay = min(180, max(delay, int(header)))
                resp.close()
                print(f'    Server rate limit/temporary error; waiting {delay}s...', flush=True)
                time.sleep(delay)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            if attempt == 3: raise
            time.sleep(8 * (attempt + 1))
    raise RuntimeError('Commons remained rate-limited; retry later')

def search(session, query):
    params = {
        'action': 'query', 'format': 'json', 'formatversion': '2',
        'generator': 'search', 'gsrsearch': 'filetype:bitmap ' + query,
        'gsrnamespace': 6, 'gsrlimit': 20,
        'prop': 'imageinfo', 'iiprop': 'url|size|mime|extmetadata', 'iiurlwidth': 1500,
    }
    response = get(session, API, params=params)
    try: data = response.json()
    finally: response.close()
    if 'error' in data: raise RuntimeError(str(data['error']))
    return data.get('query', {}).get('pages', [])

def title_match(uid, title):
    value = norm(title.removeprefix('File:'))
    return any(all(re.search(r'\b'+re.escape(part)+r'\b', value) for part in group) for group in CHECKS[uid])

def main():
    if not REPORT.is_file():
        raise SystemExit('Missing ' + str(REPORT) + '\nRun the original Hambantota downloader first.')
    with REPORT.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if not {'attraction_id','attraction_name','image_file','download_status'}.issubset(fields):
        raise SystemExit('Unexpected review CSV columns. Original file left unchanged.')
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({'User-Agent': 'TravelMindPhotoResearch/1.1 (educational Sri Lanka tourism dataset; Wikimedia Commons metadata; contact: https://commons.wikimedia.org/wiki/Commons:Help_desk)', 'Accept':'application/json,image/*;q=0.8'})
    suggestions = []
    found = 0
    for idx, row in enumerate(rows, 1):
        uid = row['attraction_id'].strip()
        name = row['attraction_name'].strip()
        print(f'[{idx}/{len(rows)}] {name}', flush=True)
        if row.get('download_status', '').lower() in ('downloaded', 'existing') and row.get('image_file') and (IMAGE_DIR / Path(row['image_file']).name).is_file():
            print('    KEPT existing image; no download needed', flush=True)
            continue
        if uid not in SEARCHES:
            print('    No configured search: skipping', flush=True)
            continue
        candidates = {}
        for query in SEARCHES[uid]:
            time.sleep(4)  # Respect rate limits; no aggressive parallel requests.
            try:
                pages = search(session, query)
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                row['review_note'] = 'Commons search delayed/failed: ' + str(exc)[:180]
                print('    API error:', str(exc)[:150], flush=True)
                break
            for page in pages:
                title = str(page.get('title', ''))
                if not title.startswith('File:'): continue
                info = (page.get('imageinfo') or [{}])[0]
                mime = info.get('mime', '')
                if mime not in EXT: continue
                if int(info.get('width') or 0) < 850: continue
                creator, license_name, license_url = '', '', ''
                ok, creator, license_name, license_url = licensed(info)
                if not ok: continue
                source = info.get('descriptionurl', '') or 'https://commons.wikimedia.org/wiki/' + quote(title.replace(' ', '_'), safe=':_()')
                verified_title = title_match(uid, title)
                candidates[title] = {'title':title,'info':info,'creator':creator,'license':license_name,
                    'license_url': license_url,'source':source,'exact_name_in_title':verified_title}
            if any(c['exact_name_in_title'] for c in candidates.values()): break
        viable = list(candidates.values())
        viable.sort(key=lambda c:(not c['exact_name_in_title'], -int(c['info'].get('width') or 0)))
        for c in viable[:5]:
            suggestions.append({'attraction_id':uid,'attraction_name':name,'commons_title':c['title'],
                'title_matches_place': 'yes' if c['exact_name_in_title'] else 'no - manual check',
                'source_page': c['source'], 'creator': c['creator'], 'license':c['license'],
                'license_url':c['license_url']})
        matches = [c for c in viable if c['exact_name_in_title']]
        if not matches:
            print('    SKIPPED: no sufficiently specific licensed filename; see alternatives CSV', flush=True)
            if not row.get('review_note', '').startswith('Commons search'):
                row['review_note'] = 'No clearly named image found on second pass; see alternatives CSV'
            continue
        best = matches[0]
        info = best['info']
        url = info.get('thumburl') or info.get('url')
        if not url:
            print('    SKIPPED: candidate has no download URL', flush=True)
            continue
        filename = 'hambantota_' + re.sub(r'[^a-z0-9]+', '_', norm(name)).strip('_') + EXT[info['mime']]
        path = IMAGE_DIR / filename
        if path.exists():
            print('    KEPT file already on disk', flush=True)
        else:
            try:
                time.sleep(3)
                response = get(session, url, stream=True)
                temp = path.with_name(path.name + '.part')
                try:
                    content_type = response.headers.get('Content-Type','').split(';')[0].strip().lower()
                    if content_type != info['mime']:
                        raise ValueError('Wrong Content-Type: ' + content_type)
                    with temp.open('wb') as f:
                        for part in response.iter_content(128 * 1024):
                            if part: f.write(part)
                    if temp.stat().st_size < 15000:
                        raise ValueError('Downloaded file suspiciously small')
                    temp.replace(path)
                finally:
                    response.close()
                    if temp.exists(): temp.unlink()
            except (requests.RequestException, OSError, ValueError, RuntimeError) as exc:
                row['review_note'] = 'Download error: ' + str(exc)[:180]
                print('    DOWNLOAD ERROR:', str(exc)[:150], flush=True)
                continue
        row.update({'image_file':filename, 'download_status':'downloaded',
            'review_note':'PENDING: exact image identity and Commons attribution/license must be visually checked',
            'creator':best['creator'], 'license':best['license'], 'source_page':best['source'],
            'license_url':best['license_url'], 'commons_title':best['title'],
            'image_width':str(info.get('width') or ''), 'image_height':str(info.get('height') or ''),
            'final_image_decision':'pending'})
        found += 1
        print('    DOWNLOADED/PRESERVED:', filename, flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('w', newline='', encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); writer.writeheader(); writer.writerows(rows)
    with SUGGESTIONS.open('w', newline='', encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f, fieldnames=['attraction_id','attraction_name','commons_title','title_matches_place','source_page','creator','license','license_url']);writer.writeheader();writer.writerows(suggestions)
    count=sum(1 for row in rows if row.get('download_status','').lower() in ('downloaded','existing') and (IMAGE_DIR/Path(row.get('image_file') or '__missing__').name).is_file())
    print('\nPhotos available:',count,'/',len(rows))
    print('New matches this run:',found)
    print('Review report:', OUT)
    print('Alternative Commons pages:', SUGGESTIONS)
    print('All images remain PENDING. Existing main photo register was NOT modified.')

if __name__ == '__main__':
    main()
