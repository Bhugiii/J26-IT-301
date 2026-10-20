"""TravelMind Ratnapura photo discovery. Run from the project root.
Downloads candidate imagery only: NOTHING gets approved or merged automatically.
Dependencies: requests, certifi (already used in earlier district scripts).
"""
from __future__ import annotations
import csv
import html
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote
import requests
import certifi

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / 'data/processed/travelmind_combined_clusters.csv'
OUTDIR = ROOT / 'config/photo_candidates'
IMAGES = ROOT / 'assets/images/attractions'
API = 'https://commons.wikimedia.org/w/api.php'
# Exact IDs from the user's Ratnapura dataset. Searches are only suggestions, not identity proof.
TARGETS = [
 ('osm_node_3658042915','Sri Pada Temple (Sri Pada Buddhist Temple)','Sri Pada Adam Peak summit Sri Lanka','Sri Pada;Adam Peak;Sri Pada Temple'),
 ('osm_node_2640665069','Bopath Falls','Bopath Ella waterfall Sri Lanka','Bopath Falls;Bopath Ella'),
 ('osm_node_1797915552','Sabaragamu Maha Saman Dewalaya','Maha Saman Devalaya Ratnapura','Saman Devalaya;Maha Saman Dewalaya'),
 ('osm_way_710421256','Elephant Transit Home','Udawalawe Elephant Transit Home Sri Lanka','Elephant Transit Home;Udawalawe'),
 ('osm_node_4512854289','Sinharaja National Park','Sinharaja rainforest Sri Lanka','Sinharaja'),
 ('osm_way_561752812','Batadombalena','Batadombalena cave Ratnapura','Batadombalena;Batadomba Lena'),
 ('osm_way_364257554','Maduwanwela Walawwa','Maduwanwela Walawwa Sri Lanka','Maduwanwela Walawwa;Maduwanwela'),
 ('osm_node_2151514497','National Museum Ratnapura','Ratnapura National Museum Sri Lanka','Ratnapura Museum'),
 ('osm_node_7684607839',"Baker's Bend","Bakers Bend Nonpareil Estate Balangoda",'Bakers Bend;Baker Bend;Nonpareil'),
 ('osm_node_891639918','Mini World\'s End','Mini Worlds End Belihuloya Ratnapura','Mini Worlds End;Worlds End Belihuloya'),
 ('osm_node_4502013947','Kirindi Ella Waterfall Pelmadulla','Kirindi Ella waterfall Pelmadulla','Kirindi Ella'),
 ('osm_node_2804314660','Pahanthudawa Waterfall','Pahanthudawa waterfall Belihuloya','Pahanthudawa'),
 ('osm_node_4462731780','Surathali Ella','Surathali Ella waterfall Sri Lanka','Surathali Ella;Surathali Falls'),
 ('osm_node_3726925126','Duli ella','Duli Ella waterfall Ratnapura','Duli Ella'),
 ('osm_node_4145874147','Kuragala Ancient Buddhist Monastry','Kuragala archaeological monastery Balangoda','Kuragala Ancient Buddhist Monastery;Kuragala'),
]
OUTDIR.mkdir(parents=True, exist_ok=True)
IMAGES.mkdir(parents=True, exist_ok=True)


def clean(value):
    return re.sub(r'<[^>]+>','',html.unescape(str(value or ''))).strip()

def norm(s):
    s=unicodedata.normalize('NFKD',str(s)).casefold()
    return re.sub(r'[^a-z0-9]+',' ',s).strip()

def textmeta(metadata,key):
    return clean((metadata.get(key) or {}).get('value',''))

def license_ok(short, url):
    s=(short+' '+url).lower()
    if any(x in s for x in ['noncommercial','non-commercial','-nc','no derivatives','-nd','all rights reserved','copyrighted','fair use']): return False
    return any(x in s for x in ['cc by','cc-by','cc0','public domain','pd-old','creativecommons.org/licenses/by/','creativecommons.org/publicdomain/'])

def get(session, params=None, url=None):
    for retry in range(5):
        try:
            res=session.get(url or API,params=params,timeout=45)
            if res.status_code in (429,500,502,503,504):
                wait=min(90,12*(retry+1)**2)
                print(f'    Commons HTTP {res.status_code}; waiting {wait}s')
                time.sleep(wait)
                continue
            res.raise_for_status()
            return res
        except requests.RequestException as exc:
            if retry==4: raise
            time.sleep(8*(retry+1))
    raise RuntimeError('Commons requests repeatedly rate-limited')

def writecsv(path,rows,fields):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

with DATASET.open(newline='',encoding='utf-8-sig') as f:
    dataset={r['attraction_id'].strip():r for r in csv.DictReader(f)}
for aid,name,*_ in TARGETS:
    record=dataset.get(aid)
    if not record or norm(record['attraction_name'])!=norm(name) or norm(record['district']).replace(' ','')!='ratnapura':
        raise SystemExit(f'Dataset ID/name/district mismatch: {aid} {name}. Nothing downloaded.')

session=requests.Session()
session.verify=certifi.where()
session.headers.update({'User-Agent':'TravelMindSriLankaResearch/1.0 (educational Commons image attribution collection; contact: local project developer)', 'Accept':'application/json'})
report=[]; alternatives=[]
for idx,(aid,name,query,aliases) in enumerate(TARGETS,1):
    print(f'[{idx}/{len(TARGETS)}] {name}',flush=True)
    slug=re.sub(r'[^a-z0-9]+','_',norm(name)).strip('_')[:48]
    existing=next((p for p in IMAGES.glob(f'ratnapura_{slug}.*') if p.is_file() and p.stat().st_size>5000),None)
    selected=None; dest=None; reason='No confidently identifiable licensed Commons image found'
    try:
        params={'action':'query','format':'json','formatversion':'2','generator':'search',
                'gsrsearch':f'filetype:bitmap {query}','gsrnamespace':6,'gsrlimit':20,
                'prop':'imageinfo','iiprop':'url|mime|size|extmetadata','iiurlwidth':1500}
        response=get(session,params=params).json()
        pages=response.get('query',{}).get('pages',[])
        aliaslist=[norm(x) for x in aliases.split(';') if norm(x)]
        words=set(norm(name).split())
        options=[]
        for p in pages:
            inf=(p.get('imageinfo') or [{}])[0]
            title=p.get('title',''); nt=norm(title.replace('File:',''))
            mime=inf.get('mime','')
            if mime not in ('image/jpeg','image/png','image/webp'): continue
            ext=inf.get('extmetadata') or {}
            lic=textmeta(ext,'LicenseShortName'); licurl=textmeta(ext,'LicenseUrl')
            if not license_ok(lic,licurl): continue
            if int(inf.get('width') or 0)<650 or int(inf.get('height') or 0)<400: continue
            creator=textmeta(ext,'Artist')
            source=inf.get('descriptionurl','')
            if not source.startswith('https://commons.wikimedia.org/wiki/File:'): continue
            matched=any(a in nt for a in aliaslist if len(a)>=8)
            overlap=len(set(nt.split()) & words)
            score=(5 if matched else 0)+ min(overlap,3)
            option={'attraction_id':aid,'attraction_name':name,'commons_title':title,
                    'source_page':source,'creator':creator,'license':lic,'license_url':licurl,
                    'score':score,'candidate_url':inf.get('thumburl') or inf.get('url'),
                    'original_url':inf.get('url'),'mime':mime,'name_match':matched}
            options.append(option)
        options.sort(key=lambda x:x['score'],reverse=True)
        alternatives.extend([{k:v for k,v in op.items() if k not in ('candidate_url','original_url','mime','name_match')} for op in options[:5]])
        # Conservative auto-select: require a clear site-specific name in filename.
        selected=next((op for op in options if op['name_match'] and op['score']>=6),None)
        if not selected and options: reason='Commons candidates need manual title/location confirmation (see alternatives CSV)'
        if selected:
            ext='.png' if selected['mime']=='image/png' else '.webp' if selected['mime']=='image/webp' else '.jpg'
            dest=existing or (IMAGES/f'ratnapura_{slug}{ext}')
            if not existing:
                time.sleep(3)
                img=get(session,url=selected['candidate_url'])
                if not img.headers.get('Content-Type','').lower().startswith('image/'):
                    raise ValueError('Response was not an image')
                if len(img.content)<5000: raise ValueError('Image suspiciously small')
                dest.write_bytes(img.content)
                print(f'    DOWNLOADED: {dest.name}',flush=True)
            else: print(f'    EXISTS: {dest.name}',flush=True)
            reason='Downloaded - pending visual and Commons license review'
    except Exception as exc:
        reason=f'ERROR: {type(exc).__name__}: {str(exc)[:170]}'
        print('    '+reason,flush=True)
    report.append({'attraction_id':aid,'attraction_name':name,
                   'district':'Ratnapura','image_file':dest.name if selected and dest is not None and dest.is_file() else '',
                   'download_status':'downloaded_pending' if selected and dest is not None and dest.is_file() else 'not_downloaded',
                   'creator':selected['creator'] if selected else '',
                   'license':selected['license'] if selected else '',
                   'source_page':selected['source_page'] if selected else '',
                   'license_url':selected['license_url'] if selected else '',
                   'note':reason})
    time.sleep(5)  # Respect the Commons service; no rapid-fire retries.

review=OUTDIR/'ratnapura_download_review.csv'
writecsv(review,report,list(report[0]))
writecsv(OUTDIR/'ratnapura_commons_alternatives.csv',alternatives,
         ['attraction_id','attraction_name','commons_title','source_page','creator','license','license_url','score'])
writecsv(OUTDIR/'ratnapura_15_targets.csv',
         [{'attraction_id':a,'attraction_name':n,'search_query':q,'aliases':al} for a,n,q,al in TARGETS],
         ['attraction_id','attraction_name','search_query','aliases'])
print(f'\nDownloaded or existing: {sum(r["download_status"]=="downloaded_pending" for r in report)}/{len(report)}')
print(f'Review CSV: {review}')
print('All photos remain PENDING. Existing approvals untouched.')
