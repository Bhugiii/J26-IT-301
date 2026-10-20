"""TravelMind: find Kegalle Wikimedia Commons photo candidates (manual approval required).
Run from project root: python download_kegalle_15.py
Dependencies: requests, certifi (usually already installed).
"""
from pathlib import Path
import csv
import html
import json
import re
import time
import unicodedata
from urllib.parse import quote

import certifi
import requests

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/processed/travelmind_combined_clusters.csv'
IMAGES = ROOT / 'assets/images/attractions'
OUT = ROOT / 'config/photo_candidates'
API = 'https://commons.wikimedia.org/w/api.php'
USER_AGENT = 'TravelMindResearchPhotoReview/1.0 (educational research; Wikimedia Commons image attribution review)'

# Exact attraction ID and matching name MUST exist in the Kegalle dataset.
TARGETS = [
    ('Pinnawala Elephant Orphanage', 'osm_node_1105822183', ['Pinnawala Elephant Orphanage']),
    ('Pinnawela Zoo', 'osm_node_3497082508', ['Pinnawala Open Zoo', 'Pinnawala Zoo']),
    ('Bible Rock', 'osm_node_2361172725', ['Bible Rock Sri Lanka', 'Bathalegala']),
    ('Uthuwankanda', 'osm_node_5640135447', ['Uthuwankanda', 'Uthuwan Kanda']),
    ('Beli-Lena Caves', 'osm_node_1186176594', ['Belilena Kitulgala', 'Beli Lena cave']),
    ('Berendi Kovil', 'osm_node_3105036388', ['Berendi Kovil', 'Barandi Kovil']),
    ('Dedigama Kota Vehera', 'osm_node_1733717444', ['Dedigama Kota Vehera', 'Dedigama Kotavehera']),
    ('Devanagala Temple', 'osm_node_2339010101', ['Devanagala Raja Maha Viharaya', 'Dewanagala']),
    ('Olu Ella Waterfall', 'osm_node_5085639924', ['Olu Ella waterfall', 'Olu Ella']),
    ('Nalangana Falls', 'osm_node_4402350579', ['Nalangana Falls', 'Nalangana Ella']),
    ('Ruwanwella Suspension Bridge', 'osm_node_5166957625', ['Ruwanwella suspension bridge']),
    ('Millennium Elephant Foundation', 'osm_node_5404930955', ['Millennium Elephant Foundation']),
    ('Aluthnuwara Raja Maha Viharaya', 'osm_node_2411173073', ['Aluthnuwara Dedimunda Devalaya', 'Aluthnuwara Raja Maha Viharaya']),
    ('Kadugannawa Ambalama', 'osm_node_3412364960', ['Kadugannawa Ambalama']),
    ('Rukmal Ella Waterfall', 'osm_node_4794908615', ['Rukmal Ella waterfall', 'Rukmal Ella']),
]
# Higher bar than loose keyword search: require these distinctive identifying tokens
# in the Commons file title. All downloads remain pending for human checking.
IDENTIFIERS = [
    ('pinnawala', 'orphanage'), ('pinnawala', 'zoo'), ('bible rock', 'bathalegala'),
    ('uthuwankanda', 'uthuwan kanda'), ('belilena', 'beli lena'),
    ('berendi', 'barandi'), ('dedigama', 'kotavehera'), ('devanagala', 'dewanagala'),
    ('olu ella',), ('nalangana',), ('ruwanwella', 'suspension'),
    ('millennium elephant',), ('aluthnuwara',), ('kadugannawa', 'ambalama'),
    ('rukmal ella',),
]


def normal(s):
    s = unicodedata.normalize('NFKD', str(s)).lower().replace('_', ' ')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', s)).strip()


def plain(s):
    return html.unescape(re.sub(r'<[^>]+>', ' ', str(s or ''))).strip()


def getmeta(meta, key):
    v = (meta or {}).get(key, {})
    return v.get('value', '') if isinstance(v, dict) else ''


def allowed_license(name, url):
    val = normal(name)
    if any(x in val for x in ('noncommercial', 'non commercial', 'no derivatives', 'fair use', 'copyrighted')):
        return False
    return bool(re.search(r'\bcc\s*(?:by|zero|0)\b|creative commons attribution|public domain|\bpd\b', val) or
                'creativecommons.org/licenses/by' in url.lower() or
                'creativecommons.org/publicdomain/' in url.lower())


def safe_slug(s):
    return re.sub(r'[^a-z0-9]+', '_', normal(s)).strip('_')[:90]


def api_query(session, params):
    for attempt in range(4):
        try:
            resp = session.get(API, params=params, timeout=35)
            if resp.status_code in (429, 500, 502, 503, 504):
                delay = min(90, int(resp.headers.get('Retry-After', 0) or 0) or 15 * (attempt + 1))
                print(f'    Commons response {resp.status_code}; waiting {delay}s...')
                time.sleep(delay)
                continue
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as ex:
            if attempt == 3:
                raise RuntimeError(f'Commons request failed: {ex}') from ex
            time.sleep(8 * (attempt + 1))
    raise RuntimeError('Commons rate limit persisted after retries')


def search(session, phrase):
    params = {
        'action': 'query', 'format': 'json', 'formatversion': '2',
        'generator': 'search', 'gsrsearch': f'filetype:bitmap {phrase}',
        'gsrnamespace': 6, 'gsrlimit': 12,
        'prop': 'imageinfo', 'iiprop': 'url|mime|size|extmetadata', 'iiurlwidth': 1400,
    }
    js = api_query(session, params)
    return js.get('query', {}).get('pages', [])


def candidate(page, needles):
    title = str(page.get('title', ''))
    tt = normal(title.replace('File:', ''))
    # Deliberately reject filenames with no place-identifying term.
    if not any(normal(term) in tt for term in needles):
        return None
    info = (page.get('imageinfo') or [{}])[0]
    ext = info.get('extmetadata', {})
    mime = info.get('mime', '')
    if mime not in ('image/jpeg', 'image/png', 'image/webp'):
        return None
    if int(info.get('width') or 0) < 700 or int(info.get('height') or 0) < 450:
        return None
    lic = plain(getmeta(ext, 'LicenseShortName'))
    licurl = plain(getmeta(ext, 'LicenseUrl'))
    artist = plain(getmeta(ext, 'Artist'))
    if not allowed_license(lic, licurl) or not artist:
        return None
    url = info.get('thumburl') or info.get('url') or ''
    page_url = info.get('descriptionurl') or ('https://commons.wikimedia.org/wiki/' + quote(title.replace(' ', '_'), safe=':/_'))
    if not url.startswith('https://') or not page_url.startswith('https://'):
        return None
    return {'title': title, 'url': url, 'source_page': page_url,
            'creator': artist, 'license': lic, 'license_url': licurl,
            'width': info.get('width', ''), 'height': info.get('height', ''), 'mime': mime}


def main():
    if not DATA.is_file():
        raise SystemExit(f'Missing project data: {DATA}')
    with DATA.open(encoding='utf-8-sig', newline='') as fh:
        rows = {row['attraction_id']: row for row in csv.DictReader(fh)}
    for name, aid, _ in TARGETS:
        row = rows.get(aid)
        if not row or normal(row.get('district', '')) != 'kegalle':
            raise SystemExit(f'Wrong or missing Kegalle OSM ID: {name} / {aid}')
    OUT.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(parents=True, exist_ok=True)
    with (OUT / 'kegalle_15_targets.csv').open('w', newline='', encoding='utf-8-sig') as fh:
        writer = csv.DictWriter(fh, fieldnames=['attraction_id', 'attraction_name', 'district', 'tourism_category', 'latitude', 'longitude'])
        writer.writeheader()
        for _, aid, _ in TARGETS:
            r = rows[aid]
            writer.writerow({k: r.get(k, '') for k in writer.fieldnames})

    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    session.verify = certifi.where()
    report, alternatives = [], []
    for i, (label, aid, queries) in enumerate(TARGETS):
        print(f'[{i+1}/15] {label}', flush=True)
        slug = safe_slug(label)
        found = []
        errors = []
        for query in queries[:2]:
            try:
                pages = search(session, query + ' Sri Lanka')
                for page in pages:
                    c = candidate(page, IDENTIFIERS[i])
                    if c and c['source_page'] not in {v['source_page'] for v in found}:
                        found.append(c)
            except Exception as exc:
                errors.append(str(exc))
            time.sleep(5)
            if found:
                break
        found.sort(key=lambda r: (sum(x in normal(r['title']) for x in IDENTIFIERS[i]), int(r['width'] or 0)), reverse=True)
        for c in found[:6]:
            alternatives.append({'attraction_id': aid, 'attraction_name': label,
                                 'commons_title': c['title'], 'source_page': c['source_page'],
                                 'creator': c['creator'], 'license': c['license'], 'license_url': c['license_url']})
        record = {'attraction_id': aid, 'attraction_name': label, 'image_file': '',
                  'download_status': 'no_suitable_candidate', 'final_image_decision': 'pending',
                  'creator': '', 'license': '', 'source_page': '', 'license_url': '',
                  'commons_title': '', 'notes': ''}
        if found:
            c = found[0]
            extension = '.png' if c['mime'] == 'image/png' else '.webp' if c['mime'] == 'image/webp' else '.jpg'
            filename = 'kegalle_' + slug + extension
            target = IMAGES / filename
            if target.exists() and target.stat().st_size > 1000:
                record['download_status'] = 'already_downloaded'
            else:
                try:
                    response = session.get(c['url'], timeout=75)
                    response.raise_for_status()
                    body = response.content
                    if len(body) < 5000 or not response.headers.get('Content-Type', '').lower().startswith('image/'):
                        raise ValueError('download response was not a valid-sized image')
                    target.write_bytes(body)
                    record['download_status'] = 'downloaded'
                    print('    DOWNLOADED:', filename, flush=True)
                except Exception as ex:
                    record['download_status'] = 'download_error'
                    record['notes'] = str(ex)
            if record['download_status'] in ('downloaded', 'already_downloaded'):
                record.update({k: c[k] for k in ('creator', 'license', 'license_url', 'source_page', 'title') if k != 'title'})
                record['commons_title'] = c['title']
                record['image_file'] = filename
        if record['download_status'] == 'no_suitable_candidate':
            record['notes'] = '; '.join(errors) if errors else 'No exact named, licensed Commons photo found; do not substitute a generic image'
            print('    SKIPPED:', record['notes'][:110], flush=True)
        report.append(record)
        time.sleep(4)

    for filename, records, fields in [
        ('kegalle_download_review.csv', report, list(report[0].keys())),
        ('kegalle_commons_alternatives.csv', alternatives,
         ['attraction_id', 'attraction_name', 'commons_title', 'source_page', 'creator', 'license', 'license_url']),
    ]:
        with (OUT / filename).open('w', newline='', encoding='utf-8-sig') as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)
    successes = sum(r['download_status'] in ('downloaded', 'already_downloaded') for r in report)
    print(f'\nDownloaded or existing: {successes}/15')
    print('Review CSV:', OUT / 'kegalle_download_review.csv')
    print('Alternatives:', OUT / 'kegalle_commons_alternatives.csv')
    print('All images are PENDING; the main approved register was NOT changed.')


if __name__ == '__main__':
    main()
