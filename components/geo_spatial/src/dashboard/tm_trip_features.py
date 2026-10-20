"""TravelMind discovery enhancements: nearby alternative areas, resource cards, trip list.

No persistent storage; no crowd, tourism-potential or attraction-verification claims.
"""
from pathlib import Path
from urllib.parse import urlencode
import math
import json
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import streamlit as st
from html import escape

ROOT = Path(__file__).resolve().parents[2]
GRID_FILE = ROOT / 'data/processed/tourism_infrastructure/tourism_infrastructure_grid_5km.csv'

# Reference centres serve as approximate search origins, NOT independently verified entries.
ORIGINS = {
    'Sigiriya area': (7.95735, 80.75699),
    'Ella / Nine Arch Bridge area': (6.87681, 81.06086),
    'Galle Fort area': (6.0264, 80.2168),
    'Dambulla Cave Temple area': (7.85660, 80.64839),
    'Polonnaruwa ancient city area': (7.94876, 81.00250),
    'Anuradhapura sacred city area': (8.35243, 80.39991),
}
FIELDS = {
    'Things to explore': 'attraction_count',
    'Places to stay': 'service_group_accommodation_count',
    'Places to eat': 'service_group_food_and_drink_count',
    'Travel services': 'service_group_travel_support_count',
}

def _valid_coords(lat, lon):
    try:
        a, b = float(lat), float(lon)
        return math.isfinite(a) and math.isfinite(b) and 5.5 <= a <= 10.2 and 79.3 <= b <= 82.3
    except (ValueError, TypeError):
        return False

def distance_km(lat, lon, y, x):
    a = np.radians(np.asarray(y, dtype=float) - float(lat)) / 2
    b = np.radians(np.asarray(x, dtype=float) - float(lon)) / 2
    c = np.cos(np.radians(float(lat))) * np.cos(np.radians(np.asarray(y, dtype=float)))
    return 12742 * np.arcsin(np.sqrt(np.clip(np.sin(a)**2 + c*np.sin(b)**2, 0, 1)))

@st.cache_data(show_spinner=False)
def load_area_grid():
    if not GRID_FILE.exists():
        return pd.DataFrame()
    d = pd.read_csv(GRID_FILE, low_memory=False)
    required = {'grid_id', 'center_latitude', 'center_longitude', 'boundary_overlap_fraction', *FIELDS.values()}
    if not required.issubset(d.columns):
        return pd.DataFrame()
    for c in required - {'grid_id'}:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d.dropna(subset=list(required - {'grid_id'})).copy()
    for c in FIELDS.values():
        d[c] = d[c].clip(lower=0)
    # Most partial-coast cells are retained for discovery but marked separately.
    d = d[d['boundary_overlap_fraction'].gt(0)].copy()
    d['mapped_total'] = d[list(FIELDS.values())].sum(axis=1)
    return d[d.mapped_total.gt(0)]

def trip_items():
    if 'tm_trip_saved' not in st.session_state:
        st.session_state.tm_trip_saved = []
    return st.session_state.tm_trip_saved

def add_item(item):
    entries = trip_items()
    if not any(x['id'] == item['id'] for x in entries):
        st.session_state.tm_trip_saved = entries + [item]

def trip_button(*, unique_id, name, lat, lon, kind='place', key, warning=False):
    if not _valid_coords(lat, lon):
        return
    item = {'id': str(unique_id), 'name': str(name)[:120], 'lat': float(lat),
            'lon': float(lon), 'kind': kind, 'caution': bool(warning)}
    already = any(x['id'] == item['id'] for x in trip_items())
    if st.button('✓ In My Trip' if already else '＋ Add to My Trip',
                 key=key, disabled=already, width="stretch"):
        add_item(item)
        st.toast(f"Added {item['name']} to My Trip")

def maps_search(lat, lon):
    return 'https://www.google.com/maps/search/?' + urlencode({'api': 1, 'query': f'{float(lat):.6f},{float(lon):.6f}'})

def _route_url(items):
    # Google Maps URL supports only a limited number of waypoints on some devices.
    coords = [f"{p['lat']:.6f},{p['lon']:.6f}" for p in items]
    if len(coords) == 1:
        return maps_search(items[0]['lat'], items[0]['lon'])
    args = {'api': 1, 'origin': coords[0], 'destination': coords[-1], 'travelmode': 'driving'}
    if len(coords) > 2:
        args['waypoints'] = '|'.join(coords[1:-1])
    return 'https://www.google.com/maps/dir/?' + urlencode(args)

def render_my_trip():
    st.markdown('### 🧳 My Sri Lanka Trip')
    st.write('Save places as you explore, arrange the order, then open your trip in Google Maps.')
    items = trip_items()
    if not items:
        st.info('Your trip is empty. In Discover Places or Stay & Eat Nearby, choose **Add to My Trip**.')
        return
    st.caption('Places are saved only for this active session. The list may reset when your session ends.')
    for idx, item in enumerate(list(items)):
        with st.container(border=True):
            a, b, c, d = st.columns([7, 1, 1, 1], gap='small')
            with a:
                st.markdown(f"**{idx+1}. {item['name']}**")
                st.caption('Approximate 5 km area centre' if item['kind'] == 'area' else 'Mapped place coordinates')
                if item['caution']:
                    st.caption('Location should be checked before travel.')
            with b:
                if st.button('↑', key=f'trip_up_{idx}', disabled=idx == 0):
                    items[idx-1], items[idx] = items[idx], items[idx-1]
                    st.rerun()
            with c:
                if st.button('↓', key=f'trip_down_{idx}', disabled=idx == len(items)-1):
                    items[idx+1], items[idx] = items[idx], items[idx+1]
                    st.rerun()
            with d:
                if st.button('✕', key=f'trip_remove_{idx}'):
                    items.pop(idx)
                    st.rerun()
    st.caption('Route order follows the list above. This is not an optimized itinerary; check road accessibility and opening times.')
    if len(items) > 10:
        st.warning('Google Maps may limit intermediate stops. The link includes the first 10 saved items; create a second route for the rest.')
    st.link_button('🗺️ Open trip in Google Maps', _route_url(items[:10]), width="stretch")
    export = {
        'title': 'My TravelMind Trip',
        'note': 'Mapped locations are provisional; visit order is user-selected, not optimized.',
        'stops': [dict(order=i+1, name=x['name'], latitude=x['lat'], longitude=x['lon'],
                       kind=x.get('kind','place'), location_check_recommended=x.get('caution',True))
                  for i,x in enumerate(items)]
    }
    st.download_button('⬇️ Download my trip (JSON)', json.dumps(export, indent=2, ensure_ascii=False),
                       file_name='my_travelmind_trip.json', mime='application/json',
                       key='download_my_trip', width='stretch')
    if st.button('Clear My Trip', key='trip_clear'):
        st.session_state.tm_trip_saved = []
        st.rerun()



def _named_attractions(osm_places):
    needed = {'attraction_name','district','latitude','longitude'}
    if osm_places is None or osm_places.empty or not needed.issubset(osm_places.columns):
        return pd.DataFrame(columns=list(needed))
    d = osm_places.copy()
    for c in ('attraction_name','district'):
        d[c] = d[c].fillna('').astype(str).str.strip()
    for c in ('latitude','longitude'):
        d[c] = pd.to_numeric(d[c],errors='coerce')
    d = d.dropna(subset=['latitude','longitude'])
    d = d[d.attraction_name.str.len().ge(3) & d.latitude.between(5.5,10.2) & d.longitude.between(79.3,82.3)]
    if 'flagged' in d.columns:
        d = d[~d.flagged.fillna(False).astype(bool)]
    return d.drop_duplicates(['attraction_name','district']).reset_index(drop=True)

@st.cache_data(show_spinner=False)
def _labelled_grid(grid, places):
    '''Cache expensive nearest-place district approximation after dataset changes.'''
    g = grid.copy().reset_index(drop=True)
    g['nearby_name']=''; g['approx_district']='Sri Lanka'; g['nearest_km']=np.inf
    if places.empty: return g
    loc_lat=places.latitude.to_numpy(dtype=float)
    loc_lon=places.longitude.to_numpy(dtype=float)
    nearest=np.zeros(len(g),dtype=np.int64); distances_min=np.full(len(g),np.inf)
    for start in range(0,len(g),64):
        end=min(start+64,len(g))
        yy=g.center_latitude.to_numpy(dtype=float)[start:end,None]
        xx=g.center_longitude.to_numpy(dtype=float)[start:end,None]
        a=np.sin(np.radians(loc_lat[None,:]-yy)/2)**2+np.cos(np.radians(yy))*np.cos(np.radians(loc_lat[None,:]))*np.sin(np.radians(loc_lon[None,:]-xx)/2)**2
        dist=12742*np.arcsin(np.sqrt(np.clip(a,0,1)))
        ids=dist.argmin(axis=1)
        nearest[start:end]=ids
        distances_min[start:end]=dist[np.arange(end-start),ids]
    g['nearby_name']=places.attraction_name.iloc[nearest].to_numpy()
    g['approx_district']=places.district.iloc[nearest].to_numpy()
    g['nearest_km']=distances_min
    return g

def _bands(grid):
    result={}
    for col in FIELDS.values():
        positive=pd.to_numeric(grid[col],errors='coerce').fillna(0)
        positive=positive[positive>0]
        result[col]=tuple(positive.quantile([.33,.67]).tolist()) if len(positive) else (0,0)
    return result

def _level(value, thresholds):
    if value<=0: return ('None',0)
    q1,q2=thresholds
    if value<=q1: return ('Few',1)
    if value<=q2: return ('Some',2)
    return ('Many',3)

def _nearby_real_places(area, places, limit=3):
    distances=distance_km(area.center_latitude, area.center_longitude,places.latitude.to_numpy(),places.longitude.to_numpy())
    nearby=places.iloc[np.flatnonzero(distances<=3.6)].copy()
    if nearby.empty:return nearby
    nearby['distance_from_centre_km']=distances[distances<=3.6]
    nearby=nearby[nearby.attraction_name.str.len().ge(4)]
    return nearby.sort_values(['distance_from_centre_km','attraction_name']).drop_duplicates('attraction_name').head(limit)

def _map_html(areas, selected_grid_id):
    '''MapLibre GL JS matching dashboard map basemaps.'''
    features=[]
    for r in areas.itertuples(index=False):
        features.append({'type':'Feature','geometry':{'type':'Point','coordinates':[float(r.center_longitude),float(r.center_latitude)]},
                        'properties':{'name':str(r.approx_district),'grid':str(r.grid_id),
                                      'selected':str(r.grid_id)==str(selected_grid_id)}})
    selected=next((f for f in features if f['properties']['selected']),None)
    cx,cy=(selected['geometry']['coordinates'] if selected else
           [float(areas.center_longitude.median()),float(areas.center_latitude.median())])
    zoom=10 if selected else (8.0 if areas.approx_district.nunique()==1 else 6.7)
    template='''<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="https://unpkg.com/maplibre-gl@6.14.0/dist/maplibre-gl.css"><style>
    html,body,#map{height:100%;width:100%;margin:0;font-family:Inter,Arial,sans-serif}#map{position:absolute;inset:0}
    .controls{position:absolute;top:12px;left:12px;z-index:3;display:flex;gap:6px}
    button{border:1px solid #bbd9ca;border-radius:10px;background:white;color:#245e47;padding:9px 12px;font-weight:700;cursor:pointer}
    .maplibregl-popup-content{border-radius:12px;color:#183c2c}
    </style></head><body><div id="map"></div><div class="controls"><button id="street">🗺️ Street</button><button id="sat">🛰️ Satellite</button></div>
    <script type="module">import * as maplibregl from 'https://unpkg.com/maplibre-gl@6.14.0/dist/maplibre-gl.mjs';
    const points=__FEATURES__, selectedId=__SELECTED__;
    const street={version:8,sources:{osm:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,attribution:'© OpenStreetMap contributors'}},layers:[{id:'osm',type:'raster',source:'osm'}]};
    const sat={version:8,sources:{imagery:{type:'raster',tiles:['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],tileSize:256,attribution:'© Esri'}},layers:[{id:'imagery',type:'raster',source:'imagery'}]};
    const map=new maplibregl.Map({container:'map',style:street,center:__CENTER__,zoom:__ZOOM__,maxZoom:17});
    map.addControl(new maplibregl.NavigationControl(),'top-right');
    function attach(){map.addSource('areas',{type:'geojson',data:points});
      map.addLayer({id:'halos',type:'circle',source:'areas',filter:['==',['get','selected'],true],paint:{'circle-color':'#7c3aed','circle-radius':20,'circle-opacity':.22}});
      map.addLayer({id:'pins',type:'circle',source:'areas',paint:{'circle-color':['case',['get','selected'],'#7c3aed','#2F6F55'],'circle-radius':['case',['get','selected'],11,6],'circle-stroke-color':'#fff','circle-stroke-width':2}});
      map.on('click','pins',e=>{const f=e.features[0],p=f.properties,ll=f.geometry.coordinates;
        const url='https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(ll[1]+','+ll[0]);
        const card=document.createElement('div');card.textContent='Mapped discovery area near '+p.name+' · approx. 5 km area';
        const link=document.createElement('a');link.href=url;link.target='_blank';link.rel='noopener noreferrer';link.textContent='  Open approximate area in Google Maps ↗';card.appendChild(document.createElement('br'));card.appendChild(link);
        new maplibregl.Popup().setLngLat(ll).setDOMContent(card).addTo(map);
      });
      map.on('mouseenter','pins',()=>map.getCanvas().style.cursor='pointer');map.on('mouseleave','pins',()=>map.getCanvas().style.cursor='');
    }
    map.on('style.load',attach);
    document.getElementById('street').onclick=()=>map.setStyle(street);
    document.getElementById('sat').onclick=()=>map.setStyle(sat);
    </script></body></html>'''
    payload={'type':'FeatureCollection','features':features}
    return template.replace('__FEATURES__',json.dumps(payload,ensure_ascii=True).replace('</','<\\/'))\
        .replace('__SELECTED__',json.dumps(str(selected_grid_id)))\
        .replace('__CENTER__',json.dumps([cx,cy])).replace('__ZOOM__',str(zoom))

def _approved_photo(nearby, approved_images, image_dir):
    if not approved_images or image_dir is None or nearby.empty or 'attraction_id' not in nearby.columns:
        return None
    for rec in nearby.itertuples():
        meta=approved_images.get(str(rec.attraction_id))
        if meta:
            candidate=Path(image_dir)/str(meta.get('image_file',''))
            if candidate.is_file() and candidate.name==str(meta.get('image_file','')):
                return candidate
    return None

def build_place_description(place_name, district="", category="", group=""):
    """Short category-based description, not a verified historical or travel claim.

    Works with original OSM tourism_category and Overture basic_category / tourism_group.
    Avoids automatically inferring detailed history, access or reputation.
    """
    name = str(place_name or "").strip().casefold()
    category_text = str(category or "").strip().casefold().replace("_", " ")
    group_text = str(group or "").strip().casefold().replace("_", " ")
    where = str(district or "Sri Lanka").strip()
    if not where or where.lower() in ("nan", "unknown", "none"):
        where = "Sri Lanka"

    combined = " ".join((name, category_text))
    def contains(*words):
        return any(word in combined for word in words)

    # Apply narrow and explicit place types first: a named temple should not
    # become a generic park merely because its category contains "nature".
    if contains("fort", "fortress", "archaeolog", "ruins", "ruin", "historic", "heritage site"):
        return f"A historic attraction in {where}."
    if contains("temple", "mosque", "church", "kovil", "vihara", "viharaya", "shrine", "religious"):
        return f"A religious and cultural site in {where}."
    if contains("beach", "seaside", "coast", "bay"):
        return f"A coastal attraction in {where}."
    if contains("waterfall", "waterfalls", "falls"):
        return f"A natural waterfall attraction in {where}."
    if contains("mountain", "peak", "rock", "viewpoint", "hill", "lookout"):
        return f"A scenic natural attraction in {where}."
    if contains("museum"):
        return f"A museum and heritage attraction in {where}."
    if contains("park", "garden", "reserve", "forest", "botanical"):
        return f"A nature-focused place to explore in {where}."
    if "heritage" in group_text:
        return f"A heritage attraction in {where}."
    if "religious" in group_text or "cultural" in group_text:
        return f"A cultural place of interest in {where}."
    if "nature" in group_text or "outdoor" in group_text:
        return f"A nature-based attraction in {where}."
    return f"A mapped attraction in {where}."


def describe_record(record):
    """Accept a pandas Series, dict, or namedtuple with any available columns."""
    if hasattr(record, "get"):
        getter = record.get
    else:
        getter = lambda k, default=None: getattr(record, k, default)
    name = getter("attraction_name", None) or getter("place_name", "")
    district = getter("district", "Sri Lanka")
    category = getter("tourism_category", None) or getter("basic_category", "")
    group = getter("tourism_group", "")
    return build_place_description(name, district, category, group)


def _card(area, places, grid, bands, approved_images, image_dir, highlighted):
    """Attraction-led presentation; area counts remain nearby context, not place ratings."""
    id = str(area.grid_id)
    nearby = _nearby_real_places(area, places, limit=5)
    if nearby.empty:
        # Avoid a false named-attraction recommendation if nothing mapped is local.
        return
    anchor = nearby.iloc[0]
    name = str(anchor.attraction_name)
    district_name = str(anchor.district or area.approx_district)
    # Show only an image approved for THIS attraction, never a neighbouring landmark.
    photo = _approved_photo(nearby.iloc[:1], approved_images, image_dir)
    source_id = str(anchor.get('attraction_id', f'{id}_{name}'))
    with st.container(border=True):
        if photo:
            st.image(str(photo), width='stretch')
        else:
            st.markdown(
                '<div style="background:linear-gradient(115deg,#d5ebdf,#f1f8f3);'
                'border-radius:12px;min-height:86px;display:flex;align-items:center;'
                'padding:16px;color:#226348;font-size:18px;font-weight:800">'
                '📍 Discover a place</div>', unsafe_allow_html=True)
        st.caption(f'📍 {district_name} · nearby mapped attraction')
        st.markdown(f'### {escape(name)}')
        st.caption(describe_record(anchor))
        st.link_button('📍 Open this place in Google Maps', maps_search(anchor.latitude, anchor.longitude), width='stretch')
        trip_button(unique_id='place:'+source_id, name=name,
                    lat=anchor.latitude, lon=anchor.longitude,
                    kind='place', warning=True, key=f'primary_trip_{id}')
        with st.expander('What else is around here?', expanded=False):
            st.caption('Nearby tourism resources (approximate 5 km area)')
            for label, field, emoji in [
                ('Things to see','attraction_count','🏛️'),
                ('Places to stay','service_group_accommodation_count','🏨'),
                ('Places to eat','service_group_food_and_drink_count','🍽️'),
                ('Travel services','service_group_travel_support_count','🚌'),
            ]:
                count=int(area[field]); word, dots=_level(count,bands[field])
                active='●'*dots+'○'*(3-dots)
                st.markdown(f'<div title="{count} mapped candidate places in this approximate area" '
                            f'style="padding:3px 0;color:#26493a">{emoji} {label}'
                            f'<span style="float:right;color:#2F6F55">{active} {word}</span></div>',
                            unsafe_allow_html=True)
            others=nearby.iloc[1:]
            if not others.empty:
                st.markdown('**Other mapped places close by**')
                for j, (_, place) in enumerate(others.iterrows()):
                    st.markdown(f'📍 **{escape(str(place.attraction_name))}**')
                    st.caption(describe_record(place))
                    st.link_button('Open in Google Maps',maps_search(place.latitude, place.longitude),
                                   width='stretch')
                    trip_button(unique_id='place:'+str(place.get('attraction_id',f'{id}_{j}')),
                                name=str(place.attraction_name),lat=place.latitude,lon=place.longitude,
                                key=f'other_trip_{id}_{j}',warning=True)
            st.caption('Places and facilities are map records, not confirmed opening status or quality.')
        if st.button('🟣 Selected on area map' if highlighted else '🗺️ Show surrounding area on map',
                     key=f'beyond_focus_{id}',width='stretch',disabled=highlighted):
            st.session_state.beyond_map_focus=id
            st.rerun()

def render_beyond(osm_places, *, approved_images=None, image_dir=None):
    st.markdown('### 🌿 Explore More of Sri Lanka')
    st.write('Discover other mapped areas across Sri Lanka, or find places near a destination you choose.')
    with st.popover('ℹ️ About this data'):
        st.write('Suggestions come from mapped attractions and visitor facilities. They do not measure quality, popularity or crowding. The map uses approximate 5 km areas; confirm locations before visiting. District labels are estimates based on nearby mapped places.')
    grid=load_area_grid()
    if grid.empty:
        st.info('The tourism area data is not available yet.');return
    places=_named_attractions(osm_places)
    if places.empty:
        st.info('No mapped places are available for discovery.');return
    labelled=_labelled_grid(grid,places)
    districts=sorted(set(places.district.dropna())-{'','Unknown','Sri Lanka'})
    modes=['Across Sri Lanka','A district','Near a place']
    interest_names=['🏛️ Things to see','🏨 Stay','🍽️ Eat','🚌 Travel services']
    fields=list(FIELDS.values())
    st.markdown('**1 · Where would you like to explore?**')
    mode=st.segmented_control('Explore mode',modes,default='Across Sri Lanka',key='beyond_mode_v3',label_visibility='collapsed') or modes[0]
    st.markdown('**2 · What matters to you?**')
    choice=st.segmented_control('Travel interest',interest_names,default=interest_names[0],key='beyond_interest_v3',label_visibility='collapsed') or interest_names[0]
    focus_lat=focus_lon=None; radius=None; chosen_district=None
    if mode=='A district':
        chosen_district=st.selectbox('Choose a district',districts,key='beyond_district_v3')
    elif mode=='Near a place':
        term=st.text_input('Search for a starting place',placeholder='Sigiriya, Ella, Galle Fort, Jaffna…',key='beyond_search_v3')
        radius=st.segmented_control('Explore within (straight-line distance)',[10,20,50,100],default=20,key='beyond_radius_v3') or 20
        if len(term.strip())<2:
            st.info('Enter two or more characters to find a starting place.');return
        matches=places[places.attraction_name.str.contains(term.strip(),case=False,regex=False,na=False)]
        matches=matches.sort_values(['attraction_name','district']).head(100).reset_index(drop=True)
        if matches.empty:
            st.info('No matching mapped places. Try another search.');return
        pos=st.selectbox('Select the starting place',list(range(len(matches))),format_func=lambda i:f'{matches.iloc[i].attraction_name} · {matches.iloc[i].district}',key='beyond_found_v3')
        r=matches.iloc[int(pos)];focus_lat=float(r.latitude);focus_lon=float(r.longitude)
    selected_field=fields[interest_names.index(choice)]
    candidates=labelled.copy()
    if chosen_district: candidates=candidates[candidates.approx_district.eq(chosen_district)].copy()
    if focus_lat is not None:
        candidates['distance_km']=distance_km(focus_lat,focus_lon,candidates.center_latitude,candidates.center_longitude)
        candidates=candidates[candidates.distance_km.between(4,radius)].copy()
    candidates=candidates[candidates.attraction_count.gt(0) & candidates.nearest_km.le(3.6)].copy()
    candidates=candidates.sort_values([selected_field,'attraction_count','grid_id'],ascending=[False,False,True])
    if mode=='Across Sri Lanka' and not candidates.empty:
        candidates['_rank']=candidates.groupby('approx_district').cumcount()
        candidates=candidates.sort_values(['_rank',selected_field],ascending=[True,False]).drop(columns='_rank')
    # Avoid repeating the same nearest named attraction across adjacent grid cells.
    # This is a presentation filter only: the 5 km grid and research counts are unchanged.
    candidates['_name_district_key'] = (candidates['nearby_name'].fillna('').astype(str).str.casefold().str.strip()
        + '|' + candidates['approx_district'].fillna('').astype(str).str.casefold().str.strip())
    candidates = candidates.drop_duplicates('_name_district_key').drop(columns='_name_district_key')
    candidates=candidates.reset_index(drop=True)
    if candidates.empty:
        st.info('No matching areas. Try changing your search.');return
    st.markdown('#### 🗺️ Explore areas on the map')
    if 'beyond_map_focus' not in st.session_state:st.session_state.beyond_map_focus=None
    focus_id=st.session_state.beyond_map_focus
    if focus_id not in set(candidates.grid_id.astype(str)):
        focus_id=None
    show_map=st.toggle('Show the interactive map',value=True,key='beyond_map_toggle_v3')
    if show_map:
        # Plot current results, with the selected card highlighted in purple.
        mapped=candidates.head(700).copy()
        if focus_id and focus_id not in set(mapped.grid_id.astype(str)):
            mapped=pd.concat([mapped,candidates[candidates.grid_id.astype(str).eq(focus_id)].head(1)],ignore_index=True)
        components.html(_map_html(mapped,focus_id),height=440,scrolling=False)
    st.markdown('#### 📍 Places you can explore')
    st.caption('Each card highlights a named mapped attraction. The map and optional details describe its surrounding area.')
    per_page=st.select_slider('Areas per page',options=[9,18,30],value=9,key='beyond_size_v3')
    total_pages=math.ceil(len(candidates)/per_page)
    # No keyed number_input stale-max problem when changing region/filter.
    page=st.number_input('Page',min_value=1,max_value=total_pages,value=1,step=1,key=f'beyond_page_v3_{mode}_{chosen_district}_{selected_field}_{per_page}_{len(candidates)}')
    subset=candidates.iloc[(page-1)*per_page:page*per_page]
    thresholds=_bands(grid)
    for start in range(0,len(subset),3):
        cols=st.columns(3,gap='medium')
        for col,(_,area) in zip(cols,subset.iloc[start:start+3].iterrows()):
            with col:
                _card(area,places,grid,thresholds,approved_images,image_dir,str(area.grid_id)==str(focus_id))
