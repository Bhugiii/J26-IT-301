"""TravelMind Kandy Commons candidates: run from project root.
Uses five strong dataset matches; never edits the approved photo register.
All downloaded images are candidates requiring visual and license review.
"""
import csv
import html
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

import certifi

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / 'config/photo_candidates/kandy_photo_match_suggestions.csv'
OUT_DIR = ROOT / 'assets/images/attractions'
REPORT = ROOT / 'config/photo_candidates/kandy_download_review.csv'
API = 'https://commons.wikimedia.org/w/api.php'
CTX = ssl.create_default_context(cafile=certifi.where())
HEADERS = {'User-Agent': 'TravelMindEducationalProject/1.0 (Wikimedia Commons metadata and attribution research)'}

# Strict names from actual dataset. Do not auto-map approximate locations to another site.
TARGETS = [
 ('Temple of the Sacred Tooth Relic','osm_way_191377765','Temple of the Sacred Tooth Relic','Temple of the Tooth Kandy Sri Lanka','kandy_temple_of_tooth'),
 ('Bahirawakanda Buddha Statue','osm_node_10862211785','Bahirawakanda Buddha','Bahirawakanda Buddha Kandy','kandy_bahirawakanda_buddha'),
 ('Gadaladeniya Temple','osm_node_1743126596','Gadaladeniya Temple','Gadaladeniya temple Sri Lanka','kandy_gadaladeniya_temple'),
 ('Lankatilaka Temple','osm_node_1743126531','Lankatilaka Raja Maha Viharaya','Lankatilaka temple Kandy Sri Lanka','kandy_lankatilaka_temple'),
 ('Embekka Devalaya','osm_node_1743126585','Embekka Devale','Embekka Devalaya Kandy Sri Lanka','kandy_embekka_devale'),
]

def request_api(params):
    url = API + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, context=CTX, timeout=35) as resp:
        return json.load(resp)

def clean(value):
    return html.unescape(re.sub(r'<[^>]+>', ' ', str(value or ''))).strip()

def search_candidates(phrase):
    payload = request_api({'action':'query','generator':'search','gsrsearch':phrase,'gsrnamespace':6,
       'gsrlimit':15,'prop':'imageinfo','iiprop':'url|size|mime|extmetadata','iiurlwidth':1600,'format':'json'})
    pages = list(payload.get('query',{}).get('pages',{}).values())
    return [p for p in pages if p.get('imageinfo')]

def score_page(page, phrase, target):
    name = page['title'].replace('File:', '').replace('_',' ').lower()
    tokens = [x for x in re.findall(r'[a-z]+',phrase.lower()) if x not in ('sri','lanka','kandy','temple','the','of')]
    matches = sum(1 for x in tokens if x in name)
    label = {'Temple of the Sacred Tooth Relic':['tooth','dalada'],
             'Bahirawakanda Buddha Statue':['bahirawakanda'],
             'Gadaladeniya Temple':['gadaladeniya'],
             'Lankatilaka Temple':['lankatilaka','lankathilaka'],
             'Embekka Devalaya':['embekka','embekke']}.get(target,[])
    if not any(word in name for word in label):
        return -1
    return matches * 10 + (5 if any(word in name for word in label) else 0)

def meta(info, field):
    return clean(info.get('extmetadata',{}).get(field,{}).get('value',''))

def main():
    if not INPUT.is_file():
        raise SystemExit(f'Missing input: {INPUT}\nCopy your uploaded matching CSV to this project path first.')
    with INPUT.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    review=[]
    for i,(target, osm_id, dataset_name, query, stem) in enumerate(TARGETS,1):
        print(f'[{i}/{len(TARGETS)}] {target}',flush=True)
        actual=next((r for r in rows if r.get('attraction_id')==osm_id and r.get('target_name')==target),None)
        record={'target_name':target,'attraction_id':osm_id,'attraction_name':dataset_name,
           'image_file':'','download_status':'','review_status':'pending_visual_and_license_review',
           'creator':'','license':'','license_url':'','source_page':'','commons_description':'','notes':''}
        if not actual:
            record['download_status']='SKIPPED'; record['notes']='Expected dataset record absent or changed in matching CSV';review.append(record);continue
        try:
            pages=search_candidates(query)
            best=max(pages,key=lambda p:score_page(p,query,target),default=None)
            if not best or score_page(best,query,target)<0:
                record['download_status']='NOT_FOUND';record['notes']='No filename with matching location name';review.append(record);continue
            info=best['imageinfo'][0]
            mime=info.get('mime','')
            license_name=meta(info,'LicenseShortName')
            license_url=meta(info,'LicenseUrl')
            if not (mime in ('image/jpeg','image/png','image/webp') and license_name and license_url):
                record['download_status']='SKIPPED';record['notes']='Missing supported image format or explicit license metadata';review.append(record);continue
            url=info.get('thumburl') or info.get('url')
            if not url:
                record['download_status']='SKIPPED';record['notes']='Image URL missing';review.append(record);continue
            extension={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}[mime]
            filename=stem+extension
            req=urllib.request.Request(url,headers=HEADERS)
            with urllib.request.urlopen(req,context=CTX,timeout=60) as response:
                img=response.read(12*1024*1024+1)
            if len(img)>12*1024*1024: raise ValueError('Image file exceeds 12 MB')
            # Never overwrite a previous image when rerun.
            dst=OUT_DIR/filename
            if dst.exists():
                record['download_status']='EXISTS';record['notes']='Existing local file was not overwritten; compare its Commons source manually'
            else:
                dst.write_bytes(img);record['download_status']='DOWNLOADED'
            record.update({'image_file':filename,'creator':meta(info,'Artist'),
             'license':license_name,'license_url':license_url,
             'source_page':info.get('descriptionurl',''),
             'commons_description':meta(info,'ImageDescription')[:240]})
            print('    '+record['download_status']+': '+filename,flush=True)
        except Exception as ex:
            record['download_status']='ERROR';record['notes']=str(ex)[:300]
            print('    ERROR: '+str(ex)[:140],flush=True)
        review.append(record)
        time.sleep(0.5)
    with REPORT.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=review[0].keys());writer.writeheader();writer.writerows(review)
    print('\nSaved:',REPORT)
    print('Downloaded or existing:',sum(r['download_status'] in ('DOWNLOADED','EXISTS') for r in review),'of',len(review))
    print('Nothing was approved or merged into attraction_image_final_review.csv.')
    print('Open the pictures, review Commons sources and licenses, then share this report.')

if __name__=='__main__': main()
