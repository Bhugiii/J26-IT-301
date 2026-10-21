"""TravelMind — island-wide MapLibre 3D explorer.
Run: python -m streamlit run src/dashboard/maplibre_explorer.py --server.port 8505
No modification of original data or trained models.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data/processed/travelmind_combined_clusters.csv'
BOUNDARIES = ROOT / 'data/boundaries/sri_lanka_districts.geojson'
SHORTLIST = ROOT / 'results/reports/hotspot_stability_analysis/hotspot_quality_shortlist.csv'
APPROVAL = ROOT / 'config/attraction_image_final_review.csv'
PHOTOS = ROOT / 'config/attraction_image_candidates.csv'

st.set_page_config(page_title='TravelMind | 3D Sri Lanka Explorer', page_icon='🌴', layout='wide')
st.markdown('''<style>
.block-container {padding-top:1.0rem;max-width:1600px}
[data-testid="stMetric"] {border:1px solid #cedce5;padding:12px;border-radius:12px}
.stTabs [data-baseweb="tab"] {font-weight:650;font-size:1rem}
.stTabs [data-baseweb="tab-highlight"] {background:#05749b}
</style>''', unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def load_data():
    if not DATA.is_file():
        raise FileNotFoundError(f'Missing: {DATA}')
    df = pd.read_csv(DATA,low_memory=False)
    necessary = {'attraction_id','attraction_name','district','tourism_category','latitude','longitude','dbscan_cluster'}
    missing = necessary - set(df.columns)
    if missing: raise ValueError(f'Missing required columns: {sorted(missing)}')
    for k in ('latitude','longitude'):
        df[k]=pd.to_numeric(df[k],errors='coerce')
    df=df[df.latitude.between(5.5,10.2) & df.longitude.between(79.4,82.2)].copy()
    for k in ('attraction_id','attraction_name','district','tourism_category'):
        df[k]=df[k].fillna('').astype(str).str.strip()
    invalid={'','unnamed','unknown','nan','none','#temple'}
    df=df[df.attraction_name.str.casefold().map(lambda x: x not in invalid and any(c.isalpha() for c in x))].copy()
    df['review_required'] = df.get('review_required',pd.Series('no',index=df.index)).fillna('no').astype(str).str.lower().eq('yes')
    df['dbscan_cluster'] = pd.to_numeric(df.dbscan_cluster,errors='coerce').fillna(-1).astype(int)
    df=df.drop_duplicates('attraction_id')
    return df

@st.cache_data(show_spinner=False)
def load_boundaries():
    if BOUNDARIES.is_file():
        with BOUNDARIES.open(encoding='utf-8') as f: return json.load(f)
    return {'type':'FeatureCollection','features':[]}

@st.cache_data(show_spinner=False)
def load_shortlist():
    if SHORTLIST.is_file(): return pd.read_csv(SHORTLIST).fillna('')
    return pd.DataFrame()

@st.cache_data(show_spinner=False)
def load_photo_approvals():
    if not APPROVAL.is_file() or not PHOTOS.is_file(): return set()
    a=pd.read_csv(APPROVAL).fillna('')
    if not {'attraction_id','final_image_decision','image_file'}.issubset(a.columns):return set()
    a=a[a.final_image_decision.astype(str).str.strip().str.lower().eq('approved')]
    return set(a.attraction_id.astype(str))

try:
    records=load_data(); boundaries=load_boundaries(); shortlist=load_shortlist(); approved_ids=load_photo_approvals()
except Exception as exc:
    st.error(str(exc)); st.stop()

st.title('🌴 TravelMind · Explore Sri Lanka in 3D')
st.caption('Rotate, tilt, and zoom around Sri Lanka. Research-derived attraction concentrations are **candidates**, not verified visitor-popularity hotspots.')

with st.sidebar:
    st.header('🧭 Map controls')
    district = st.selectbox('Explore district', ['All districts']+sorted(records.district.unique().tolist()))
    category = st.selectbox('Attraction category',['All categories']+sorted(records.tourism_category.unique().tolist()))
    search = st.text_input('Search attraction',placeholder='e.g. Ella, Sigiriya, Fort')
    include_review = st.checkbox('Include review-flagged records', value=False)
    marker_cap = st.slider('Maximum attraction markers',100,2500,900,step=100)
    show_areas = st.checkbox('Show 18 research-screened areas',value=True)
    st.divider()
    st.caption('Map layers: street / satellite. Terrain needs an internet connection to a DEM tile service. 3D buildings depend on available map data.')

filtered = records
if district!='All districts':filtered=filtered[filtered.district.eq(district)]
if category!='All categories':filtered=filtered[filtered.tourism_category.eq(category)]
if search.strip():filtered=filtered[filtered.attraction_name.str.contains(search.strip(),regex=False,case=False,na=False)]
if not include_review:filtered=filtered[~filtered.review_required]
filtered=filtered.copy()

# Render a deterministic sample to keep browser performance reasonable; actual count remains visible.
map_rows=filtered.sort_values(['attraction_name','attraction_id']).head(marker_cap)
features=[]
for r in map_rows.itertuples(index=False):
    features.append({'type':'Feature','geometry':{'type':'Point','coordinates':[float(r.longitude),float(r.latitude)]},
      'properties':{'id':str(r.attraction_id),'name':str(r.attraction_name)[:160],
        'district':str(r.district)[:80],'category':str(r.tourism_category)[:100],
        'review':bool(r.review_required),'approved_photo':str(r.attraction_id) in approved_ids}})
point_geo={'type':'FeatureCollection','features':features}
areas=[]
if not shortlist.empty and show_areas:
    needed={'center_latitude','center_longitude','baseline_records','main_district','baseline_cluster_id'}
    if needed.issubset(shortlist.columns):
        for r in shortlist.to_dict('records'):
            try:
                lat=float(r['center_latitude']); lon=float(r['center_longitude'])
                if not(5.5<=lat<=10.2 and 79.4<=lon<=82.2):continue
                n=int(float(r['baseline_records'])); spread=float(r.get('p90_radius_km',0) or 0)
            except (ValueError,TypeError):continue
            areas.append({'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':{
                'name':str(r.get('main_district','Sri Lanka'))+' attraction-rich area',
                'count':n,'radius':round(spread,2),
                'retention':str(r.get('strict_retained_pct','')),
                'review_flag':str(r.get('review_flag_pct',''))}})
area_geo={'type':'FeatureCollection','features':areas}

m1,m2,m3,m4=st.columns(4)
m1.metric('Matching mapped records',f'{len(filtered):,}')
m2.metric('Map attraction markers',f'{len(map_rows):,}')
m3.metric('Districts represented',filtered.district.nunique())
m4.metric('Shortlisted candidate areas',len(areas))

st.markdown('''<style>
/* Make the main navigation visible in both Streamlit light and dark themes. */
[data-testid="stRadio"] > label {color: #f1f5f9 !important; font-size: 1.05rem !important; font-weight: 750 !important;}
[data-testid="stRadio"] [role="radiogroup"] {background:#14283b; padding:14px; border:2px solid #33b3dd; border-radius:14px; gap:14px;}
[data-testid="stRadio"] [role="radiogroup"] label {background:#f8fafc !important; border-radius:9px; padding:10px 15px !important;}
[data-testid="stRadio"] [role="radiogroup"] label p {color:#102b42 !important; font-size:0.98rem !important; font-weight:750 !important;}
</style>''', unsafe_allow_html=True)
st.markdown('### 🧭 TravelMind Navigation')
section = st.radio(
    'Choose a section',
    ['🌍 3D Tourism Map', '🧭 Discover Places Nearby', '✨ Attraction-Rich Areas'],
    horizontal=True,
    key='travelmind_main_navigation',
)
if section == '🌍 3D Tourism Map':
    st.caption('Right-drag or Ctrl + drag to rotate/tilt. Select attractions or orange research-screened areas on the map.')

# Entire browser interaction happens inside this map iframe. Streamlit filters affect the next render.
# District boundary click updates the map-side summary, not the Streamlit sidebar widget.
style = r'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@6.14.0/dist/maplibre-gl.css">
<style>
html,body{margin:0;height:100%;font-family:Inter,Arial,sans-serif;background:#e5eff5;color:#102b42}
#map{position:absolute;inset:0} #toolbar{position:absolute;z-index:5;left:12px;top:12px;display:flex;gap:8px;flex-wrap:wrap}
#toolbar button{background:white;border:1px solid #d5e1e9;border-radius:9px;padding:10px 13px;color:#133852;font-weight:700;cursor:pointer;box-shadow:0 2px 6px #102b4220}
#toolbar button.active{background:#0b5f8f;color:white}
#info{position:absolute;left:12px;bottom:24px;z-index:5;max-width:350px;background:#fffffff2;padding:14px 16px;border:1px solid #dbe4ed;border-radius:12px;box-shadow:0 3px 12px #0002;font-size:13px;line-height:1.55}
#info b{font-size:15px} #info small{color:#537085} #info a{color:#076ba2;font-weight:700}
#terrainStatus{position:absolute;top:68px;left:12px;z-index:5;background:#ffffffd9;border-radius:6px;padding:6px 9px;font-size:12px;color:#48687a}
.maplibregl-popup-content{border-radius:10px;line-height:1.6;max-width:300px}
@media(max-width:640px){#toolbar button{padding:8px 9px}#info{max-width:250px}}
</style></head><body>
<div id="map"></div><div id="toolbar">
<button id="street" class="active">🗺️ Street</button><button id="satellite">🛰️ Satellite</button>
<button id="terrain">⛰️ 3D terrain: off</button><button id="reset">🇱🇰 Whole island</button>
</div><div id="terrainStatus">Terrain uses third-party elevation tiles; availability may vary.</div>
<div id="info"><b>Explore the map</b><div>Click a mapped attraction, district polygon, or orange candidate-area marker.</div><small>Blue = mapped candidate · orange = research-screened area</small></div>
<script type="module">
import * as maplibregl from 'https://unpkg.com/maplibre-gl@6.14.0/dist/maplibre-gl.mjs';
const POINTS=__POINTS__, AREAS=__AREAS__, DISTRICTS=__BOUNDARIES__, START=__START__;
const street={version:8,sources:{'osm':{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,maxzoom:19,attribution:'© OpenStreetMap contributors'}},layers:[{id:'osm',type:'raster',source:'osm'}]};
const sat={version:8,sources:{'imagery':{type:'raster',tiles:['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],tileSize:256,maxzoom:18,attribution:'Tiles © Esri and its data providers'}},layers:[{id:'imagery',type:'raster',source:'imagery'}]};
let mode='street', terrainOn=false;
let map;
try {map=new maplibregl.Map({container:'map',style:street,center:[80.77,7.86],zoom:7.0,pitch:0,bearing:0,antialias:true,maxPitch:85});}
catch(e){document.getElementById('info').textContent='3D map could not start: '+e.message;throw e;}
map.addControl(new maplibregl.NavigationControl({visualizePitch:true}), 'top-right');
map.addControl(new maplibregl.ScaleControl({maxWidth:120,unit:'metric'}),'bottom-right');
const info=document.getElementById('info');
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function districtLabel(p){for(const k of ['district','District','DISTRICT','name','Name','NAME','ADM2_EN','admin2Name','ADM2_NAME','district_name'])if(p[k])return String(p[k]);return 'District';}
function attach(){
map.addSource('districts',{type:'geojson',data:DISTRICTS});
map.addLayer({id:'district-fill',type:'fill',source:'districts',paint:{'fill-color':'#83bb9c','fill-opacity':0.09}});
map.addLayer({id:'district-lines',type:'line',source:'districts',paint:{'line-color':'#0d6d8f','line-width':1.5,'line-opacity':0.8}});
map.addSource('attractions',{type:'geojson',data:POINTS});
map.addLayer({id:'attractions',type:'circle',source:'attractions',paint:{'circle-color':['case',['get','review'],'#8f9aa5','#166ba6'],'circle-radius':['interpolate',['linear'],['zoom'],6,3.5,12,7.5],'circle-stroke-width':1,'circle-stroke-color':'#fff','circle-opacity':0.9}});
map.addSource('areas',{type:'geojson',data:AREAS});
map.addLayer({id:'areas-glow',type:'circle',source:'areas',paint:{'circle-color':'#f6a122','circle-opacity':0.17,'circle-radius':['interpolate',['linear'],['zoom'],6,12,12,35]}});
map.addLayer({id:'areas',type:'circle',source:'areas',paint:{'circle-color':'#ee941b','circle-radius':9,'circle-stroke-color':'#fff','circle-stroke-width':2}});
for(const layer of ['attractions','areas','district-fill'])map.on('mouseenter',layer,()=>map.getCanvas().style.cursor='pointer');
for(const layer of ['attractions','areas','district-fill'])map.on('mouseleave',layer,()=>map.getCanvas().style.cursor='');
map.on('click','attractions',e=>{const p=e.features[0].properties;const ll=e.features[0].geometry.coordinates;
const url='https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(ll[1]+','+ll[0]);
const html='<b>'+esc(p.name)+'</b><br>'+esc(p.district)+' · '+esc(p.category)+'<br>'+(p.approved_photo?'Photo-match approved for this record':'Record not independently verified')+'<br><a href="'+url+'" target="_blank" rel="noopener noreferrer">Open Google Maps ↗</a>';
info.innerHTML=html;
new maplibregl.Popup({maxWidth:'310px'}).setLngLat(ll).setHTML(html).addTo(map);
});
map.on('click','areas',e=>{const p=e.features[0].properties;const ll=e.features[0].geometry.coordinates;
info.innerHTML='<b>'+esc(p.name)+'</b><div>'+esc(p.count)+' mapped candidate records · p90 spread '+esc(p.radius)+' km</div><small>Research screened; not a verified tourism hotspot.</small>';
map.flyTo({center:ll,zoom:10,pitch:terrainOn?55:20,duration:900});});
map.on('click','district-fill',e=>{const p=e.features[0].properties;info.innerHTML='<b>'+esc(districtLabel(p))+'</b><div>District selected on map. Use the Streamlit district dropdown above to filter destination records.</div>';});
}
async function enableTerrain(){try{
 if(!map.getSource('terrain-dem'))map.addSource('terrain-dem',{type:'raster-dem',url:'https://tiles.mapterhorn.com/tilejson.json',tileSize:256});
 map.setTerrain({source:'terrain-dem',exaggeration:1.25}); terrainOn=true;
 map.easeTo({pitch:65,zoom:Math.max(9,map.getZoom()),duration:1100});
 document.getElementById('terrainStatus').textContent='3D terrain on · elevation tiles provided by Mapterhorn';
 document.getElementById('terrain').textContent='⛰️ 3D terrain: on';
}catch(err){terrainOn=false;document.getElementById('terrainStatus').textContent='Terrain unavailable: '+err.message;}}
function setMode(next){mode=next;map.setStyle(next==='street'?street:sat);setActive();}
function setActive(){for(const x of ['street','satellite'])document.getElementById(x).classList.toggle('active',x===mode);document.getElementById('terrain').classList.toggle('active',terrainOn);}
map.on('style.load',()=>{attach();if(terrainOn)enableTerrain();if(START && START.length===2)map.flyTo({center:START,zoom:10,duration:900});});
map.on('error',e=>{const msg=String(e.error?.message||'map tiles unavailable');document.getElementById('terrainStatus').textContent='Some online map tiles may be unavailable: '+msg.slice(0,95);});
document.getElementById('street').onclick=()=>setMode('street');
document.getElementById('satellite').onclick=()=>setMode('satellite');
document.getElementById('terrain').onclick=()=>{if(terrainOn){map.setTerrain(null);terrainOn=false;map.easeTo({pitch:0,duration:600});document.getElementById('terrain').textContent='⛰️ 3D terrain: off';document.getElementById('terrainStatus').textContent='3D terrain off';}else enableTerrain();setActive();};
document.getElementById('reset').onclick=()=>{map.flyTo({center:[80.77,7.86],zoom:7,pitch:0,bearing:0,duration:1200});};
</script></body></html>'''

start=[]
if district!='All districts' and len(filtered):
    start=[float(filtered.longitude.median()),float(filtered.latitude.median())]

html_map=(style.replace('__POINTS__',json.dumps(point_geo,ensure_ascii=False))
    .replace('__AREAS__',json.dumps(area_geo,ensure_ascii=False))
    .replace('__BOUNDARIES__',json.dumps(boundaries,ensure_ascii=False))
    .replace('__START__',json.dumps(start)))
if section == '🌍 3D Tourism Map':
    components.html(html_map, height=710, scrolling=False)
    st.caption('Basemap and elevation need access to third-party tile services. Orange markers are approximate candidate-area centres, not hotspot boundaries.')
    with st.expander('📋 Full matching attraction records'):
        display_cols=['attraction_name','district','tourism_category','latitude','longitude','review_required','dbscan_cluster']
        st.dataframe(filtered[display_cols],hide_index=True,width='stretch',height=340)
        st.download_button('Download filtered records',filtered[display_cols].to_csv(index=False).encode('utf-8'),file_name='travelmind_3d_filtered.csv',mime='text/csv')


def haversine_km(lat1, lon1, lat2, lon2):
    """Vectorized great-circle distance (straight line) in kilometres."""
    p1=math.radians(float(lat1))
    q1=math.radians(float(lon1))
    p2=pd.to_numeric(lat2,errors='coerce').apply(lambda v: math.radians(float(v)))
    q2=pd.to_numeric(lon2,errors='coerce').apply(lambda v: math.radians(float(v)))
    a=((p2-p1)/2).map(math.sin)**2+math.cos(p1)*p2.map(math.cos)*((q2-q1)/2).map(math.sin)**2
    return 6371.0088*2*a.clip(0,1).map(lambda v: math.asin(math.sqrt(v)))


def google_maps_url(lat,lon):
    return f'https://www.google.com/maps/search/?api=1&query={float(lat):.7f},{float(lon):.7f}'


def category_emoji(category):
    text=str(category).casefold()
    if any(word in text for word in ('beach','coast','surf','marine')):return '🏖️'
    if any(word in text for word in ('temple','religious','church','mosque','kovil')):return '🛕'
    if any(word in text for word in ('forest','wildlife','national park','nature')):return '🌿'
    if any(word in text for word in ('waterfall','scenic','hill','mountain','view')):return '🏞️'
    if any(word in text for word in ('fort','museum','historical','archaeolog','heritage')):return '🏛️'
    return '📍'


if section == '🧭 Discover Places Nearby':
    st.subheader('🧭 Discover places around a destination')
    st.caption('Select a mapped starting place. Nearby places are geographic candidates, not verified visitor recommendations.')
    # Use the currently filtered records, falling back to all display-eligible records.
    origins=filtered.sort_values(['attraction_name','district','attraction_id'])
    if origins.empty:
        st.warning('No starting places match your current filters. Change the sidebar filters.')
    else:
        origin_options=origins.head(3000)
        origin_ids=origin_options.attraction_id.astype(str).tolist()
        lookup=origin_options.set_index('attraction_id',drop=False)
        left,right=st.columns([3,1])
        with left:
            origin_id=st.selectbox('Starting destination',origin_ids,
                format_func=lambda aid:f"{lookup.loc[aid,'attraction_name']} — {lookup.loc[aid,'district']}",
                key='nearby_origin')
        with right:
            radius=st.select_slider('Radius (km)',options=[2,5,10,20],value=5,key='nearby_radius')
        origin=lookup.loc[origin_id]
        # Nearby search uses all records, not the current search/name filter.
        pool=records.copy()
        if not include_review:pool=pool[~pool.review_required]
        pool=pool[pool.attraction_id.ne(origin_id)].copy()
        pool['distance_km']=haversine_km(origin.latitude,origin.longitude,pool.latitude,pool.longitude)
        nearby=pool[pool.distance_km.le(radius)].copy()
        # Do not show multiple OSM features for the same named destination in same district.
        nearby['dedupe_key']=nearby.attraction_name.str.casefold().str.strip()+'|'+nearby.district.str.casefold()
        nearby=nearby.sort_values(['distance_km','attraction_name']).drop_duplicates('dedupe_key')
        cats=sorted(nearby.tourism_category.dropna().unique().tolist())
        f1,f2=st.columns([2,1])
        with f1:
            chosen=st.selectbox('Nearby attraction type',['All categories']+cats,key='nearby_category')
        with f2:
            order=st.selectbox('Sort nearby places',['Nearest first','Name A–Z'],key='nearby_sort')
        if chosen!='All categories':nearby=nearby[nearby.tourism_category.eq(chosen)]
        if order=='Name A–Z':nearby=nearby.sort_values('attraction_name')
        n1,n2,n3=st.columns(3)
        n1.metric('Nearby places',len(nearby))
        n2.metric('Search radius',f'{radius} km')
        n3.metric('Nearest',f'{nearby.distance_km.min():.2f} km' if len(nearby) else '—')
        st.caption('Distances are straight-line approximations, not road routes or journey times.')
        if nearby.empty:st.info('No matching nearby records. Try a larger radius or a different category.')
        for offset in range(0,min(len(nearby),24),3):
            cols=st.columns(3)
            for col,(_,r) in zip(cols,nearby.iloc[offset:offset+3].iterrows()):
                with col:
                    with st.container(border=True):
                        st.markdown(f'### {category_emoji(r.tourism_category)} {r.attraction_name}')
                        st.caption(f'{r.district} · {r.tourism_category}')
                        st.metric('Straight-line distance',f'{r.distance_km:.2f} km')
                        st.caption('Unverified OSM candidate' + (' · Flagged for review' if bool(r.review_required) else ''))
                        st.link_button('📍 Open Google Maps',google_maps_url(r.latitude,r.longitude),use_container_width=True)
        if len(nearby)>24:st.caption(f'Showing the first 24 of {len(nearby)} results. Download the full nearby list below.')
        st.download_button('Download nearby places (CSV)',nearby.drop(columns='dedupe_key').to_csv(index=False).encode('utf-8'),
            file_name='travelmind_nearby_places.csv',mime='text/csv',key='download_nearby')

if section == '✨ Attraction-Rich Areas':
    st.subheader('✨ Explore research-screened attraction-rich areas')
    st.caption('These are preliminary geographic concentrations identified by DBSCAN and additional screening, not verified tourism-demand hotspots.')
    if shortlist.empty:
        st.warning('Hotspot shortlist not found. Create hotspot_quality_shortlist.csv using your PowerShell quality-screening command, then refresh this page.')
        st.code(str(SHORTLIST))
    else:
        required={'center_latitude','center_longitude','main_district','baseline_records'}
        if not required.issubset(shortlist.columns):
            st.error('Shortlist is missing columns: '+', '.join(sorted(required-set(shortlist.columns))))
        else:
            areas_df=shortlist.copy()
            for field in ('center_latitude','center_longitude','baseline_records','p90_radius_km','strict_retained_pct','review_flag_pct'):
                if field in areas_df:areas_df[field]=pd.to_numeric(areas_df[field],errors='coerce')
            areas_df=areas_df.dropna(subset=['center_latitude','center_longitude','baseline_records'])
            areas_df=areas_df[areas_df.center_latitude.between(5.5,10.2)&areas_df.center_longitude.between(79.4,82.2)]
            districts=['All districts']+sorted(areas_df.main_district.dropna().astype(str).unique().tolist())
            c1,c2=st.columns([2,1])
            with c1:area_dist=st.selectbox('Find attraction-rich areas by district',districts,key='area_district')
            with c2:min_records=st.slider('Minimum mapped records',min_value=0,max_value=100,value=0,step=5,key='area_min')
            shown=areas_df[areas_df.baseline_records.ge(min_records)].copy()
            if area_dist!='All districts':shown=shown[shown.main_district.eq(area_dist)]
            shown=shown.sort_values(['baseline_records','main_district'],ascending=[False,True])
            st.metric('Research-screened candidate areas',len(shown))
            if shown.empty:st.info('No areas match these filters.')
            for offset in range(0,len(shown),2):
                cols=st.columns(2)
                for col,(_,area) in zip(cols,shown.iloc[offset:offset+2].iterrows()):
                    with col:
                        with st.container(border=True):
                            st.markdown(f'### 📍 {area.main_district} attraction-rich area')
                            st.caption('Preliminary research candidate · Not independently verified')
                            a,b,c=st.columns(3)
                            a.metric('Mapped records',int(area.baseline_records))
                            b.metric('Retained',f"{float(area.get('strict_retained_pct',0)):.1f}%")
                            c.metric('P90 spread',f"{float(area.get('p90_radius_km',0)):.1f} km")
                            st.caption(f"Records flagged for review: {float(area.get('review_flag_pct',0)):.1f}%")
                            st.link_button('📍 View approximate centre',google_maps_url(area.center_latitude,area.center_longitude),use_container_width=True)
                            # Show places close to the approximate centre, without implying an exact boundary.
                            sample=records.copy()
                            sample['distance_km']=haversine_km(area.center_latitude,area.center_longitude,sample.latitude,sample.longitude)
                            sample=sample[sample.distance_km.le(5)].sort_values('distance_km')
                            sample=sample[~sample.review_required].drop_duplicates(['attraction_name','district']).head(5)
                            if not sample.empty:
                                with st.expander('See mapped places around this area'):
                                    for _,place in sample.iterrows():
                                        st.write(f"{category_emoji(place.tourism_category)} {place.attraction_name} — {place.distance_km:.1f} km")
            st.download_button('Download research-screened areas (CSV)',shown.to_csv(index=False).encode('utf-8'),
                file_name='travelmind_research_screened_areas.csv',mime='text/csv',key='download_areas')
            st.caption('The area centres are approximate and the 5 km examples do not represent precise cluster membership.')
