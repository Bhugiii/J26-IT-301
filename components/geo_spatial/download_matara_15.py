"""TravelMind Matara: download Wikimedia Commons candidates for 15 real dataset IDs.
Run from TravelMind project root: python download_matara_15.py
Outputs candidates only: DOES NOT modify the approved photo register.
"""
from pathlib import Path
import csv, html, re, time, unicodedata
from urllib.parse import quote
import requests
import certifi

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/processed/travelmind_combined_clusters.csv'
PHOTOS = ROOT / 'assets/images/attractions'
OUT = ROOT / 'config/photo_candidates'
OUT.mkdir(parents=True, exist_ok=True)
PHOTOS.mkdir(parents=True, exist_ok=True)

# All IDs and place names were taken from the user's Matara dataset CSV.
TARGETS = [
 ('osm_node_5764539554','Coconut Tree Hill','Coconut Tree Hill Mirissa Sri Lanka'),
 ('osm_way_170181121','Polhena Beach','Polhena Beach Matara Sri Lanka'),
 ('osm_way_573467082','Secret Beach','Secret Beach Mirissa Sri Lanka'),
 ('osm_way_497744372','Madiha Beach','Madiha Beach Matara Sri Lanka'),
 ('osm_node_6620896189','Dondra Point','Dondra Point Sri Lanka'),
 ('osm_node_10779464806','Blowhole','Hummanaya blowhole Dikwella Sri Lanka'),
 ('osm_node_11595481269','Blue Beach Island','Blue Beach Island Nilwella Sri Lanka'),
 ('osm_node_1745489040','Kushtarajagala Statue','Kushtarajagala Weligama Sri Lanka'),
 ('osm_way_388413308','Devinuwara Sri Vishnu Maha Devalaya','Devinuwara Vishnu Devalaya Sri Lanka'),
 ('osm_way_1166309032','Weherahena Viharaya','Weherahena temple Matara Sri Lanka'),
 ('osm_way_1006310931','Wewurukannala Raja Maha Viharaya','Wewurukannala temple Dikwella Sri Lanka'),
 ('osm_way_286366417','Old Dutch Market','Old Dutch Market Matara Sri Lanka'),
 ('osm_way_496970157','Dutch Church','Dutch Reformed Church Matara Sri Lanka'),
 ('osm_node_5521783765','Patna Sliding','Patna Sliding Deniyaya Sri Lanka'),
 ('osm_node_2176947342','Hathmale Ella','Hathmale Ella waterfall Deniyaya Sri Lanka'),
]

API = 'https://commons.wikimedia.org/w/api.php'
SESSION = requests.Session()
SESSION.verify = certifi.where()
SESSION.headers.update({'User-Agent':'TravelMindResearchPhotoReview/1.0 (educational Wikimedia Commons attribution workflow; Python requests)', 'Accept':'application/json'})

STOP = {'sri','lanka','matara','mirissa','temple','beach','falls','waterfall','the','of','and','view','old','point','devalaya','viharaya','raja','maha','dutch','near'}

def tokens(value):
    value = unicodedata.normalize('NFKD', value.lower())
    return {t for t in re.findall(r'[a-z]{3,}', value) if t not in STOP}

def plain(value):
    return re.sub(r'<[^>]*>', '', html.unescape(str(value or ''))).strip()

def safe_filename(value):
    s = re.sub(r'[^a-z0-9]+','_',value.lower()).strip('_')
    return 'matara_' + s[:65] + '.jpg'

def get_json(params):
    for n in range(4):
        try:
            r = SESSION.get(API, params=params, timeout=45)
            if r.status_code in (429, 500, 502, 503, 504):
                delay = min(90, int(r.headers.get('Retry-After','15') or 15) if r.headers.get('Retry-After','').isdigit() else 15*(n+1))
                print(f'    Commons busy ({r.status_code}); waiting {delay}s')
                time.sleep(delay)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            if n == 3: raise
            time.sleep(8*(n+1))
    raise RuntimeError('Commons search rate-limited; retry later')

def commons_candidates(query):
    params = {'action':'query','format':'json','formatversion':2, 'generator':'search',
      'gsrsearch': f'filetype:bitmap {query}', 'gsrnamespace':6,'gsrlimit':10,
      'prop':'imageinfo','iiprop':'url|mime|size|extmetadata','iiurlwidth':1400}
    return get_json(params).get('query',{}).get('pages',[])

def pick(pages, name, query):
    # Conservative matching: distinctive target tokens must appear in title or description.
    significant = tokens(name)
    context = tokens(query)
    options=[]
    for p in pages:
        ii=(p.get('imageinfo') or [{}])[0]
        mime=ii.get('mime','')
        if mime not in ('image/jpeg','image/png','image/webp'):continue
        ext=ii.get('extmetadata') or {}
        license_name=plain(ext.get('LicenseShortName',{}).get('value',''))
        license_url=plain(ext.get('LicenseUrl',{}).get('value',''))
        # Exclude NC, ND, and ambiguous licenses; public-domain files allowed.
        l=license_name.lower().strip()
        if not (l.startswith('cc by') or l=='cc0' or 'public domain' in l or l.startswith('pd-')):continue
        title=plain(p.get('title',''))
        description=plain(ext.get('ImageDescription',{}).get('value',''))
        title_tokens=tokens(title)
        all_tokens=tokens(title+' '+description)
        if not significant or not (significant & title_tokens):continue
        # For multiword names require at least 2 matches in title/description unless target is 1 token.
        if len(significant)>1 and len(significant & all_tokens)<min(2,len(significant)):continue
        score = 5*len(significant & title_tokens) + len(context & all_tokens)
        if 'sri' in title.lower() or 'lanka' in title.lower():score+=1
        url=ii.get('thumburl') or ii.get('url','')
        if not url.startswith('https://'):continue
        options.append((score, title, p, ii, ext, license_name, license_url, url))
    return max(options,default=None,key=lambda r:r[0])

if not DATA.exists():
    raise SystemExit(f'Missing dataset: {DATA}')
with DATA.open(encoding='utf-8-sig',newline='') as fh:
    reader=csv.DictReader(fh)
    matched={r['attraction_id']:r for r in reader if r.get('district','').strip().casefold()=='matara'}

output=[]
for idx,(aid,name,query) in enumerate(TARGETS,1):
    print(f'[{idx}/15] {name}',flush=True)
    row={'attraction_id':aid,'attraction_name':name,'district':'Matara','image_file':'',
         'download_status':'','creator':'','license':'','license_url':'','source_page':'','commons_title':'',
         'review_note':'Visual and license-page review required before approval'}
    found=matched.get(aid)
    if not found or found.get('attraction_name','').strip().casefold()!=name.casefold():
        row['download_status']='SKIPPED_DATASET_ID_OR_NAME_MISMATCH'
        output.append(row);continue
    path=PHOTOS/safe_filename(name)
    if path.exists() and path.stat().st_size>5000:
        row['download_status']='EXISTING_FILE_REVIEW_METADATA_REQUIRED'
        row['image_file']=path.name
        output.append(row);continue
    try:
        pages=commons_candidates(query)
        choice=pick(pages,name,query)
        if not choice:
            row['download_status']='NO_CONFIDENT_LICENSED_CANDIDATE'
            output.append(row)
            time.sleep(6)
            continue
        _,title,p,ii,ext,license_name,license_url,url=choice
        creator=plain(ext.get('Artist',{}).get('value',''))
        source=ii.get('descriptionurl') or ('https://commons.wikimedia.org/wiki/'+quote(title.replace(' ','_'),safe='():,_-'))
        if not creator or not source.startswith('https://'):
            row['download_status']='MISSING_CREATOR_OR_SOURCE'
            output.append(row);time.sleep(6);continue
        # Save original MIME-compatible extension instead of renaming PNG/WebP to JPEG.
        extension={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}[ii['mime']]
        path=path.with_suffix(extension)
        response=SESSION.get(url,timeout=80)
        response.raise_for_status()
        if len(response.content)<5000 or not response.headers.get('content-type','').startswith('image/'):
            raise ValueError('invalid or very small image response')
        path.write_bytes(response.content)
        row.update(image_file=path.name,download_status='DOWNLOADED_PENDING_VISUAL_REVIEW',
           creator=creator,license=license_name,license_url=license_url,
           source_page=source,commons_title=title)
        print(f'    DOWNLOADED: {path.name}',flush=True)
    except Exception as exc:
        row['download_status']='ERROR'
        row['review_note']=str(exc)[:250]
        print(f'    ERROR: {exc}',flush=True)
    output.append(row)
    time.sleep(8)  # Be considerate of Commons API rate limits.

review_path=OUT/'matara_download_review.csv'
with review_path.open('w',encoding='utf-8-sig',newline='') as fh:
    writer=csv.DictWriter(fh,fieldnames=list(output[0]));writer.writeheader();writer.writerows(output)
targets_path=OUT/'matara_15_targets.csv'
with targets_path.open('w',encoding='utf-8-sig',newline='') as fh:
    w=csv.writer(fh);w.writerow(['attraction_id','attraction_name','commons_search_query']);w.writerows(TARGETS)
print(f'\nDownloaded: {sum(x["download_status"]=="DOWNLOADED_PENDING_VISUAL_REVIEW" for x in output)}/15')
print(f'Review CSV: {review_path}')
print('NO PHOTOS APPROVED. Existing approval register unchanged.')
