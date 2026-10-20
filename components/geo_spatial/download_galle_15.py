"""TravelMind Galle: 15 exact dataset targets -> conservative Commons photo candidates.
Run from the project root: python download_galle_15.py
No photo is automatically approved; no existing approval register is modified.
"""
from pathlib import Path
import csv, html, re, time, datetime
from urllib.parse import quote
import requests
import certifi

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data/processed/travelmind_combined_clusters.csv'
OUTDIR=ROOT/'config/photo_candidates'
IMAGE_DIR=ROOT/'assets/images/attractions'
TARGETS=OUTDIR/'galle_15_photo_targets.csv'
REPORT=OUTDIR/'galle_download_review.csv'
API='https://commons.wikimedia.org/w/api.php'
HEADERS={'User-Agent':'TravelMindPhotoResearch/1.0 (educational prototype; Commons attribution review)'}
SESSION=requests.Session(); SESSION.headers.update(HEADERS); SESSION.verify=certifi.where()
OUTDIR.mkdir(parents=True,exist_ok=True); IMAGE_DIR.mkdir(parents=True,exist_ok=True)
TARGET_ROWS=[
('Dutch Reformed Church (1755)','osm_way_398146186','Dutch Reformed Church Galle Sri Lanka'),
('Old Dutch Hospital (Shopping Precint)','osm_way_137294929','Galle Dutch Hospital Sri Lanka'),
('Dutch Warehouse (National Maritime Museum)','osm_way_28239945','Galle National Maritime Museum Dutch warehouse'),
('Flag Rock Bastion','osm_way_449260368','Flag Rock Bastion Galle Fort'),
('Point Utrecht Bastion','osm_node_3377399097','Point Utrecht Bastion Galle Fort'),
('The Moon Bastion','osm_node_3377394539','Moon Bastion Galle Fort'),
('Peace Pagoda','osm_way_431413175','Japanese Peace Pagoda Rumassala Galle'),
('Wijaya Beach','osm_way_481558075','Wijaya Beach Dalawella Sri Lanka'),
('Bentota','osm_way_128600427','Bentota beach Sri Lanka'),
('Koggala Beach Park','osm_way_259026853','Koggala beach Sri Lanka'),
('Ahangama Beach','osm_way_1564820321','Ahangama beach Sri Lanka'),
('Martin Wickramasinghe Folk Museum Complex','osm_node_3053343646','Martin Wickramasinghe Folk Museum Koggala'),
('Kanneliya Rainforest Reserve','osm_node_2616147812','Kanneliya rainforest reserve Sri Lanka'),
('Kosgoda Sea Turtle Conservation Project','osm_node_2788326672','Kosgoda turtle conservation Sri Lanka'),
('Handunugoda Tea Estate','osm_way_1030601255','Handunugoda tea estate Sri Lanka'),
]

with TARGETS.open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.writer(f);w.writerow(['attraction_name','attraction_id','commons_search']);w.writerows(TARGET_ROWS)

with DATA.open(newline='',encoding='utf-8-sig') as f:
 dataset={r['attraction_id']:r for r in csv.DictReader(f)}

def clean_html(s):
 return re.sub(r'\\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',str(s or '')))).strip()

def call_commons(params):
 for attempt in range(3):
  response=SESSION.get(API,params=params,timeout=35)
  if response.status_code==429:
   delay=min(60,int(response.headers.get('Retry-After','20') or 20))
   print(f'    Commons rate-limited (429); waiting {delay}s...')
   time.sleep(delay);continue
  response.raise_for_status()
  return response.json()
 raise RuntimeError('Wikimedia Commons rate limit persists (429); stop and retry later')

def accepted_license(ext):
 value=clean_html(ext.get('LicenseShortName',{}).get('value',''))
 url=str(ext.get('LicenseUrl',{}).get('value','')).strip()
 normalized=value.lower().replace(' ','')
 ok=normalized.startswith(('ccby-','ccby-sa-','cc0')) or normalized=='cc0'
 return (value,url) if ok else ('','')

def candidate_matches(title, search):
 # Require specific meaningful words in file title, not just 'Sri Lanka' or 'Galle'.
 title=title.lower().replace('_',' ')
 words=[x for x in re.findall(r'[a-z]+',search.lower()) if x not in {'sri','lanka','galle','fort','beach','the','and','museum','national'}]
 if not words:return False
 return any(x in title for x in words[:3]) and (sum(x in title for x in words)>=min(2,len(words)) or len(words)==1)

fields=['attraction_id','attraction_name','image_file','download_status','creator','license','source_page','license_url','commons_title','notes']
results=[]
for idx,(name,aid,query) in enumerate(TARGET_ROWS,1):
 print(f'[{idx}/15] {name}',flush=True)
 entry=dict.fromkeys(fields,'');entry.update(attraction_id=aid,attraction_name=name,download_status='pending')
 try:
  record=dataset.get(aid)
  if not record or record.get('district','').strip().lower()!='galle' or record.get('attraction_name','').strip()!=name:
   entry.update(download_status='dataset_mismatch',notes='Exact ID/name/district mismatch: manual inspection required')
  else:
   data=call_commons({'action':'query','format':'json','formatversion':2,'generator':'search',
    'gsrsearch':'filetype:bitmap '+query,'gsrnamespace':6,'gsrlimit':12,
    'prop':'imageinfo','iiprop':'url|mime|size|extmetadata','iiurlwidth':1400})
   found=None
   for page in data.get('query',{}).get('pages',[]):
    info=(page.get('imageinfo') or [{}])[0];ext=info.get('extmetadata') or {}
    license_name,license_url=accepted_license(ext)
    if not license_name or not candidate_matches(page.get('title',''),query):continue
    if info.get('mime') not in ('image/jpeg','image/png'):continue
    if info.get('width',0)<700 or info.get('height',0)<450:continue
    imgurl=info.get('thumburl') or info.get('url')
    creator=clean_html(ext.get('Artist',{}).get('value',''))
    if not imgurl or not creator:continue
    found=(page,info,license_name,license_url,creator,imgurl);break
   if not found:
    entry.update(download_status='no_eligible_candidate',notes='No appropriately titled, attributed CC image returned; manually search Commons')
   else:
    page,info,lic,licurl,creator,imgurl=found
    suffix='.png' if info.get('mime')=='image/png' else '.jpg'
    filename='galle_'+re.sub(r'[^a-z0-9]+','_',name.lower()).strip('_')[:55]+suffix
    dest=IMAGE_DIR/filename
    if dest.exists() and dest.stat().st_size>5000:
     status='existing_unverified'
    else:
     downloaded=SESSION.get(imgurl,timeout=90);downloaded.raise_for_status()
     content_type=downloaded.headers.get('Content-Type','').lower()
     if 'image/' not in content_type or len(downloaded.content)<5000:raise ValueError('Response was not a valid-sized image payload')
     dest.write_bytes(downloaded.content);status='downloaded_pending_review'
    entry.update(image_file=filename,download_status=status,creator=creator[:500],license=lic,
      source_page='https://commons.wikimedia.org/wiki/'+quote(page['title'].replace(' ','_'),safe=':_()'),
      license_url=licurl,commons_title=page['title'],
      notes='PENDING: confirm photo depicts this exact attraction and inspect Commons credit/license terms')
    print('    '+status+': '+filename,flush=True)
 except Exception as e:
  msg=str(e)
  entry.update(download_status='error',notes=msg[:250]);print('    ERROR: '+msg[:140],flush=True)
  if 'rate limit persists' in msg.lower():
   results.append(entry)
   for nextname,nextid,_ in TARGET_ROWS[idx:]:
    nextrow=dict.fromkeys(fields,'');nextrow.update(attraction_id=nextid,attraction_name=nextname,
      download_status='not_attempted_rate_limit',notes='Retry later; do not make more API requests now')
    results.append(nextrow)
   break
 results.append(entry)
 # Commons is a public resource: pace both search and downloads.
 time.sleep(3.5)

with REPORT.open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(results)
print('\nReview report:',REPORT.resolve())
print('Download candidates:',sum(r['download_status'] in ('downloaded_pending_review','existing_unverified') for r in results),'of 15')
print('Do not add to config/attraction_image_final_review.csv until visually and legally reviewed.')
