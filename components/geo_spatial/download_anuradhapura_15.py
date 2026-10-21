"""TravelMind Anuradhapura photo candidates. Run from project root: python download_anuradhapura_15.py
This script NEVER approves photos or edits the existing approval CSV.
Photos and attributions need human review before they are used.
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
DATA = ROOT / 'data/processed/travelmind_combined_clusters.csv'
IMG_DIR = ROOT / 'assets/images/attractions'
OUT = ROOT / 'config/photo_candidates'
REGISTER = ROOT / 'config/attraction_image_final_review.csv'
API = 'https://commons.wikimedia.org/w/api.php'
HEADERS = {'User-Agent': 'TravelMindPhotoResearch/1.0 (educational project; Wikimedia Commons file attribution review; contact via Wikimedia Commons)'}
# target name, dataset ID, display name, Commons searches, distinctive filename terms
TARGETS = [
 ('Ruwanwelisaya Dagoba','osm_way_247453300','Ruwanwelisaya','Ruwanwelisaya Anuradhapura|Ruwanweli Seya Sri Lanka','ruwanwelisaya|ruwanweli'),
 ('Sri Maha Bodhi','osm_way_398907394','Jaya Sri Maha Bodhi','Sri Maha Bodhi Anuradhapura|Jaya Sri Maha Bodhi','maha bodhi|jaya sri maha bodhi'),
 ('Jethavana Dagoba','osm_way_115767725','Jetavanaramaya','Jetavanaramaya Sri Lanka|Jetavana stupa Anuradhapura','jetavan|jethavan'),
 ('Abhayagiriya Dagoba','osm_way_278865152','Abhayagiri Stupa','Abhayagiri Dagoba Anuradhapura|Abhayagiriya Sri Lanka','abhayagir'),
 ('Thuparamaya Dagoba','osm_way_247453305','Thuparamaya','Thuparamaya Anuradhapura','thuparam'),
 ('Isurumuni Viharaya','osm_node_567004213','Isurumuniya Temple','Isurumuniya Anuradhapura|Isurumuni Viharaya','isurumun'),
 ('Samadhi Buddha Statue','osm_node_567004191','Samadhi Buddha','Samadhi Buddha Statue Anuradhapura','samadhi buddha'),
 ('Mihintale Sacred City','osm_way_1356595422','Mihintale','Mihintale Sri Lanka','mihintal'),
 ('Ritigala Ancient Buddhist Monastery','osm_node_3723220027','Ritigala Monastery','Ritigala ruins Sri Lanka|Ritigala ancient monastery','ritigala'),
 ('Aukana Buddha Statue','osm_node_4081329203','Aukana Buddha Statue','Aukana Buddha Sri Lanka|Avukana Buddha','aukana|avukana'),
 ('Twin Pond','osm_way_550562510','Kuttam Pokuna','Kuttam Pokuna Anuradhapura|Twin Ponds Anuradhapura','kuttam pokuna|twin pond'),
 ('Mirisavatiya Dagoba','osm_way_247452367','Mirisawetiya','Mirisawetiya stupa Anuradhapura|Mirisavatiya Dagoba','mirisav|mirisaw'),
 ('Lankaramaya Dagoba','osm_way_278865150','Lankarama','Lankaramaya Anuradhapura','lankaram'),
 ('Ranmasu Uyana','osm_way_1236602451','Ranmasu Uyana','Ranmasu Uyana Anuradhapura','ranmasu'),
 ('Jathika Namal Uyana','osm_node_4726751890','Jathika Namal Uyana','Jathika Namal Uyana Sri Lanka|Namal Uyana rose quartz','namal uyana'),
]

def norm(x):
 return re.sub(r'[^a-z0-9]+',' ',str(x).casefold()).strip()

def clean(x):
 return re.sub('<[^>]+>', '', html.unescape(str(x or ''))).strip()

def meta(info,field):
 return clean(info.get('extmetadata',{}).get(field,{}).get('value',''))

def get(session, url, **kw):
 for attempt in range(4):
  try:
   response=session.get(url,timeout=45,verify=certifi.where(),**kw)
   if response.status_code in (429,500,502,503,504):
    seconds = min(75, 12 * (attempt + 1))
    print(f'    HTTP {response.status_code}; waiting {seconds}s')
    time.sleep(seconds)
    continue
   response.raise_for_status()
   return response
  except requests.RequestException as e:
   if attempt==3: raise
   time.sleep(10*(attempt+1))
 raise RuntimeError('Commons temporarily unavailable after retries')

def license_ok(name,url):
 s=(str(name)+' '+str(url)).casefold()
 if any(v in s for v in ['-nc','-nd','noncommercial','non-commercial','no derivatives','all rights reserved']):return False
 return any(v in s for v in ['cc by','cc-by','cc0','public domain','pd-', 'creativecommons.org/licenses/by/', 'creativecommons.org/publicdomain/'])

def suggest(session, query, tokens):
 params={'action':'query','format':'json','formatversion':2,'generator':'search',
         'gsrsearch':'filetype:bitmap '+query,'gsrnamespace':6,'gsrlimit':18,
         'prop':'imageinfo','iiprop':'url|mime|size|extmetadata','iiurlwidth':1600}
 data=get(session, API,params=params).json()
 pages=data.get('query',{}).get('pages',[])
 results=[]
 for p in pages:
  title=p.get('title','')
  if not p.get('imageinfo'):continue
  info=p['imageinfo'][0]
  if info.get('mime') not in ('image/jpeg','image/png'):continue
  if info.get('width',0)<850:continue
  license_name=meta(info,'LicenseShortName') or meta(info,'License')
  license_url=meta(info,'LicenseUrl')
  if not license_ok(license_name,license_url):continue
  fname=norm(title.removeprefix('File:'))
  match=next((t for t in tokens if norm(t) in fname),None)
  if not match:continue
  source=info.get('descriptionurl') or 'https://commons.wikimedia.org/wiki/'+quote(title.replace(' ','_'),safe=':/_')
  file_url=info.get('thumburl') or info.get('url')
  if not file_url:continue
  results.append({'commons_title':title,'source_page':source,'creator':meta(info,'Artist'),
    'license':license_name,'license_url':license_url,'image_url':file_url,
    'matched_token':match,'width':info.get('width',0),'mime':info['mime']})
 return results

def main():
 if not DATA.exists():raise SystemExit('Run from project root; data CSV not found: '+str(DATA))
 with DATA.open(encoding='utf-8-sig',newline='') as f:
  dataset={r['attraction_id']:r for r in csv.DictReader(f)}
 IMG_DIR.mkdir(parents=True,exist_ok=True)
 OUT.mkdir(parents=True,exist_ok=True)
 existing=set()
 if REGISTER.is_file():
  with REGISTER.open(encoding='utf-8-sig',newline='') as f:
   existing={r['attraction_id'] for r in csv.DictReader(f) if str(r.get('final_image_decision','')).strip().lower()=='approved'}
 session=requests.Session();session.headers.update(HEADERS)
 output=[];alternatives=[];target_rows=[]
 for idx,(dataset_name,aid,display,querystring,tokens) in enumerate(TARGETS,1):
  print(f'[{idx}/15] {display}',flush=True)
  r=dataset.get(aid)
  base={'district':'Anuradhapura','attraction_id':aid,'attraction_name':display,
    'dataset_name':dataset_name,'image_file':'','download_status':'','final_image_decision':'pending',
    'creator':'','license':'','source_page':'','license_url':'','commons_title':'','notes':''}
  target_rows.append({'attraction_id':aid,'dataset_name':dataset_name,'display_name':display,'search_terms':querystring})
  if not r or norm(r.get('attraction_name',''))!=norm(dataset_name) or norm(r.get('district',''))!='anuradhapura':
   base.update(download_status='SKIPPED',notes='Dataset ID/name/district did not match');output.append(base);continue
  if aid in existing:
   base.update(download_status='ALREADY_APPROVED',notes='Existing approved photo preserved');output.append(base);continue
  slug=re.sub(r'[^a-z0-9]+','_',norm(display)).strip('_')
  preexisting=[p for p in IMG_DIR.glob(f'anuradhapura_{slug}.*') if p.suffix.lower() in ('.jpg','.png') and p.stat().st_size>10000]
  if preexisting:
   base.update(download_status='EXISTING_NEEDS_METADATA',image_file=preexisting[0].name,notes='Local image exists; verify metadata manually before approving');output.append(base);continue
  found=[];error=None
  for query in querystring.split('|')[:2]:
   try:
    got=suggest(session,query,tokens.split('|'))
    for p in got:
     if p['source_page'] not in {x['source_page'] for x in found}:found.append(p)
   except Exception as e:
    error=str(e)
   time.sleep(3.5)
   if len(found)>=3:break
  for c in found[:8]:alternatives.append({'attraction_id':aid,'attraction_name':display,**c})
  if not found:
   base.update(download_status='NO_CONFIDENT_MATCH' if not error else 'NO_MATCH_OR_NETWORK_ERROR',notes=error or 'No file title with distinctive place name and acceptable license');output.append(base);continue
  # Only choose automatically if distinctive place tokens appear in title. Still pending visual review.
  pick=found[0]
  suffix='.png' if pick['mime']=='image/png' else '.jpg'
  filename=f'anuradhapura_{slug}{suffix}'
  try:
   response=get(session,pick['image_url'])
   content=response.content
   if len(content)<10000:raise ValueError('File too small to be a valid photo')
   (IMG_DIR/filename).write_bytes(content)
   base.update(download_status='DOWNLOADED',image_file=filename,creator=pick['creator'],license=pick['license'],
               source_page=pick['source_page'],license_url=pick['license_url'],commons_title=pick['commons_title'],
               notes='Pending manual image/location attribution and license verification')
   print('    DOWNLOADED:',filename,flush=True)
  except Exception as e:
   base.update(download_status='DOWNLOAD_ERROR',notes=str(e))
   print('    ERROR:',e,flush=True)
  output.append(base)
  time.sleep(3.5)
 def write(name,rows,fields):
  with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
 write('anuradhapura_download_review.csv',output,list(output[0]))
 write('anuradhapura_commons_alternatives.csv',alternatives,['attraction_id','attraction_name','commons_title','source_page','creator','license','license_url','image_url','matched_token','width','mime'])
 write('anuradhapura_15_targets.csv',target_rows,list(target_rows[0]))
 print('\nDownloaded:',sum(r['download_status']=='DOWNLOADED' for r in output),'of 15')
 print('Review:',OUT/'anuradhapura_download_review.csv')
 print('No photos approved and no existing register changed.')

if __name__=='__main__':main()
