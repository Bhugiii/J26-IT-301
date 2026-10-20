"""Download Badulla photo candidates from Wikimedia Commons using its MediaWiki API.

Run from the TravelMind project root:
    python download_badulla_commons.py

This script never edits attraction_image_final_review.csv and never approves an image.
"""
import csv
import html
import json
import re
import ssl
import time

import certifi
from pathlib import Path
from urllib.parse import unquote, urlparse, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / 'config' / 'photo_candidates' / 'badulla_photo_matches.csv'
OUTPUT_DIR = ROOT / 'assets' / 'images' / 'attractions'
REPORT = ROOT / 'config' / 'photo_candidates' / 'badulla_download_review.csv'
API = 'https://commons.wikimedia.org/w/api.php'
AGENT = 'TravelMindStudentPhotoReview/1.0 (educational Wikimedia Commons client)'
MAX_BYTES = 18 * 1024 * 1024


def fetch(url):
    req = Request(url, headers={'User-Agent': AGENT, 'Accept': 'application/json,image/*,*/*'})
    with urlopen(req, timeout=40, context=ssl.create_default_context(cafile=certifi.where())) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('File exceeds 18 MB download limit')
    return data


def plain(value):
    value = re.sub(r'<[^>]*>', ' ', html.unescape(str(value or '')))
    return ' '.join(html.unescape(value).split())


def metadata(info, key):
    return plain(info.get('extmetadata', {}).get(key, {}).get('value', ''))


def main():
    if not INPUT.is_file():
        raise SystemExit('Input CSV missing: ' + str(INPUT) + '\nDownload the Badulla matching CSV and save it at that path.')
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with INPUT.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    results = []
    for index, row in enumerate(rows, 1):
        record = {
            'district': row.get('district', ''),
            'attraction_id': row.get('attraction_id', ''),
            'attraction_name': row.get('attraction_name', ''),
            'commons_file_page': row.get('commons_file_page', ''),
            'image_file': '', 'creator_from_commons': '', 'license_from_commons': '',
            'license_url': '', 'width_pixels': '', 'height_pixels': '',
            'download_status': 'failed', 'review_status': 'pending_manual_visual_and_license_review',
            'error': '',
        }
        try:
            page = row.get('commons_file_page', '').strip()
            parsed = urlparse(page)
            if parsed.scheme != 'https' or parsed.netloc != 'commons.wikimedia.org' or not parsed.path.startswith('/wiki/File:'):
                raise ValueError('Not a Wikimedia Commons file page URL')
            title = unquote(parsed.path[len('/wiki/'):]).replace('_', ' ')
            params = urlencode({'action':'query','titles':title,'prop':'imageinfo','iiprop':'url|size|extmetadata',
                                'iiurlwidth':1920,'format':'json','formatversion':2})
            result = json.loads(fetch(API + '?' + params).decode('utf-8'))
            pages = result.get('query', {}).get('pages', [])
            info = pages[0].get('imageinfo', [{}])[0] if pages else {}
            if not info.get('url'):
                raise ValueError('Image metadata unavailable (file may be missing)')
            record['creator_from_commons'] = metadata(info, 'Artist') or metadata(info, 'Credit')
            record['license_from_commons'] = metadata(info, 'LicenseShortName')
            record['license_url'] = metadata(info, 'LicenseUrl')
            record['width_pixels'] = info.get('width', '')
            record['height_pixels'] = info.get('height', '')
            license_name = record['license_from_commons'].lower()
            if not any(word in license_name for word in ('cc by', 'cc0', 'public domain')):
                raise ValueError('License not recognized as CC BY/CC0/public domain; review manually: ' + record['license_from_commons'])
            image_url = info.get('thumburl') or info['url']
            extension = Path(unquote(urlparse(image_url).path)).suffix.lower()
            if extension not in ('.jpg', '.jpeg', '.png', '.webp'):
                extension = Path(unquote(urlparse(info['url']).path)).suffix.lower()
            if extension not in ('.jpg', '.jpeg', '.png', '.webp'):
                raise ValueError('Unsupported image format: ' + extension)
            image_name = 'badulla_' + re.sub(r'[^a-z0-9]+', '_', record['attraction_name'].lower()).strip('_') + extension
            path = OUTPUT_DIR / image_name
            if not path.exists():
                path.write_bytes(fetch(image_url))
            record['image_file'] = image_name
            record['download_status'] = 'downloaded'
            print(f'[{index}/{len(rows)}] OK: {image_name}')
        except Exception as exc:
            record['error'] = str(exc)
            print(f'[{index}/{len(rows)}] REVIEW/ERROR: {record["attraction_name"]}: {exc}')
        results.append(record)
        time.sleep(0.4)
    with REPORT.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]) if results else [])
        if results:
            writer.writeheader()
            writer.writerows(results)
    print('\nSaved review report:', REPORT)
    print('Downloaded:', sum(r['download_status'] == 'downloaded' for r in results), 'of', len(results))
    print('No photos were automatically approved. Inspect images and Commons pages before entering them into attraction_image_final_review.csv.')


if __name__ == '__main__':
    main()
