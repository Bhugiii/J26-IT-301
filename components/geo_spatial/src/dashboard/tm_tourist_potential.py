"""Tourist-facing Sri Lanka tourism resource explorer; no experimental AHP scoring."""
from pathlib import Path
import json
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
GRID = ROOT / 'data/processed/tourism_infrastructure/tourism_infrastructure_grid_5km.csv'
BOUNDARY = ROOT / 'data/boundaries/sri_lanka_districts.geojson'
OPTIONS = {
    '🌿 Attractions': 'attraction_count',
    '🏨 Accommodation': 'service_group_accommodation_count',
    '🍴 Food & drink': 'service_group_food_and_drink_count',
    '🚕 Travel services': 'service_group_travel_support_count',
}

def _label(props):
    for k in ('district','District','DISTRICT','name','Name','NAME','ADM2_EN','ADM2_NAME','district_name'):
        if props.get(k):
            return str(props[k])
    return None

@st.cache_data(show_spinner=False)
def get_areas():
    frame = pd.read_csv(GRID, low_memory=False)
    required = {'grid_id','center_latitude','center_longitude','boundary_overlap_fraction',*OPTIONS.values()}
    if not required.issubset(frame.columns):
        raise ValueError('Required tourism-grid columns are missing')
    cols = ['center_latitude','center_longitude','boundary_overlap_fraction',*OPTIONS.values()]
    for c in cols:
        frame[c] = pd.to_numeric(frame[c],errors='coerce')
    frame = frame.dropna(subset=cols).copy()
    frame = frame[frame.boundary_overlap_fraction.ge(.5)].copy()
    for c in OPTIONS.values():
        frame[c] = frame[c].clip(lower=0)
    frame = frame[frame[list(OPTIONS.values())].sum(axis=1).gt(0)].copy()
    frame['district_name'] = 'Sri Lanka'
    if BOUNDARY.exists():
        try:
            from shapely.geometry import Point,shape
            features=json.loads(BOUNDARY.read_text(encoding='utf-8')).get('features',[])
            districts=[(shape(f['geometry']),_label(f.get('properties') or {})) for f in features]
            districts=[(poly,name) for poly,name in districts if name and not poly.is_empty]
            labels=[]
            for lat,lon in zip(frame.center_latitude,frame.center_longitude):
                point=Point(float(lon),float(lat))
                label=next((name for poly,name in districts if poly.covers(point)),None)
                if label is None and districts:
                    label=min(districts,key=lambda item:item[0].distance(point))[1]
                labels.append(label or 'Sri Lanka')
            frame['district_name']=labels
        except Exception:
            pass
    return frame

def render_tourist_potential():
    st.markdown('### 🌴 Find an area that suits your trip')
    st.write('Explore mapped attractions, accommodation, food and travel services across Sri Lanka.')
    st.caption('Compare what is mapped in different areas — not visitor popularity, safety, or an official tourism-potential score.')
    if not GRID.exists():
        st.info('The tourism resource map is not available at the moment.')
        return
    try:
        areas=get_areas()
    except Exception as exc:
        st.error('Unable to open the tourism resource map.')
        st.caption(str(exc))
        return
    if areas.empty:
        st.info('No mapped resource areas available.')
        return
    left,right=st.columns([3,2])
    with left:
        interest=st.selectbox('What matters most for your trip?',list(OPTIONS),key='tourist_interest')
    with right:
        names=sorted(set(areas.district_name)-{'Sri Lanka'})
        district=st.selectbox('Where do you want to explore?', ['Anywhere in Sri Lanka']+names,key='tourist_district')
    focus=OPTIONS[interest]
    matches=areas if district=='Anywhere in Sri Lanka' else areas[areas.district_name.eq(district)]
    matches=matches[matches[focus].gt(0)].sort_values([focus,'grid_id'],ascending=[False,True]).copy()
    if matches.empty:
        st.info('No mapped places match this choice. Try another destination area or interest.')
        return
    st.markdown('#### 🗺️ Explore the map')
    st.caption('Markers show approximate 5 km areas — not exact attraction or hotel locations.')
    try:
        import pydeck as pdk
        visible=matches.head(450).copy()
        visible['info']=[f'{r.district_name}: {int(getattr(r,focus))} mapped options' for r in visible.itertuples()]
        layer=pdk.Layer('ScatterplotLayer', data=visible,
                        get_position='[center_longitude, center_latitude]',
                        get_radius=1900, radius_min_pixels=3,radius_max_pixels=9,
                        get_fill_color=[47,111,85,190],pickable=True)
        deck=pdk.Deck(layers=[layer],map_style='https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
                      initial_view_state=pdk.ViewState(
                          latitude=float(visible.center_latitude.median()),
                          longitude=float(visible.center_longitude.median()),
                          zoom=8 if district!='Anywhere in Sri Lanka' else 6.8),
                      tooltip={'text':'{info}'})
        st.pydeck_chart(deck,height=430)
    except Exception:
        st.map(matches.head(450).rename(columns={'center_latitude':'latitude','center_longitude':'longitude'}),
               latitude='latitude',longitude='longitude',size=40,color='#2F6F55',zoom=7)
    st.markdown('#### 📍 Explore a mapped area')
    choices=matches.head(150).copy()
    labels={str(row.grid_id):f'Near {row.district_name} · option {i+1}'
            for i,row in enumerate(choices.itertuples())}
    gid=st.selectbox('Choose an area',list(labels),format_func=lambda x:labels[x],key='tourist_area')
    row=choices.loc[choices.grid_id.astype(str).eq(gid)].iloc[0]
    st.markdown(f'**Around {row.district_name}**')
    for column,(label,key) in zip(st.columns(4),[
        ('Attractions','attraction_count'),('Places to stay','service_group_accommodation_count'),
        ('Places to eat','service_group_food_and_drink_count'),('Travel services','service_group_travel_support_count')]):
        column.metric(label, f'{int(row[key]):,}')
    st.caption('Numbers are mapped place records, not confirmed open businesses or visitor numbers.')
    st.link_button('📍 View approximate area on Google Maps',
                   f'https://www.google.com/maps/search/?api=1&query={row.center_latitude:.6f}%2C{row.center_longitude:.6f}')
    st.info('This explorer compares existing map information. TravelMind does not yet publish a validated AHP Tourism Potential Index.')
