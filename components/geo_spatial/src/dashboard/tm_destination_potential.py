"""District-based destination discovery from provisional mapped POI neighbourhoods.

Not the 5 km cell AHP index. This is a separate provisional destination-surroundings
model: 5 km straight-line counts and illustrative AHP weights, NOT attraction quality,
visitor popularity, demand, road accessibility, or expert-validated rankings.
"""
from pathlib import Path
from html import escape
from urllib.parse import urlencode
import re
import unicodedata
import numpy as np
import pandas as pd
import streamlit as st
from scipy.spatial import cKDTree
from tm_ahp import CRITERIA, DEFAULT_COMPARISONS, build_matrix, ahp_weights

RADIUS_KM = 5.0
NEARBY_FEATURES = ["nearby_attractions", "nearby_accommodation", "nearby_food", "nearby_travel"]
DISPLAY = ["Nearby attractions", "Places to stay", "Food and drink", "Travel support"]

def _xy(lat,lon):
    """Approximate planar coordinates in kilometres; exact haversine distance filters follow."""
    return np.column_stack([np.asarray(lat,float)*111.195, np.asarray(lon,float)*110.1])

def _haversine(lat, lon, arr):
    a1=np.radians(lat); o1=np.radians(lon)
    a2=np.radians(arr[:,0]); o2=np.radians(arr[:,1])
    h=np.sin((a2-a1)/2)**2+np.cos(a1)*np.cos(a2)*np.sin((o2-o1)/2)**2
    return 12742*np.arcsin(np.sqrt(np.clip(h,0,1)))

@st.cache_data(show_spinner="Comparing mapped places near destinations...")
def _calculate(csv_attractions, csv_assignments):
    a=pd.read_csv(csv_attractions,low_memory=False)
    b=pd.read_csv(csv_assignments,low_memory=False)
    for col in ('latitude','longitude'):
        a[col]=pd.to_numeric(a[col],errors='coerce')
        b[col]=pd.to_numeric(b[col],errors='coerce')
    required={'attraction_id','attraction_name','district','tourism_category','latitude','longitude'}
    if not required.issubset(a.columns):raise ValueError('Attraction dataset lacks required columns.')
    if not {'dataset_role','tourism_group','latitude','longitude'}.issubset(b.columns):raise ValueError('POI assignment dataset lacks required columns.')
    a=a.dropna(subset=['latitude','longitude']).copy()
    a=a[a.latitude.between(5.5,10.2)&a.longitude.between(79.3,82.3)]
    a['review_required']=a.get('review_required',pd.Series('no',index=a.index)).astype(str).str.lower()
    a['suspected_duplicate']=a.get('suspected_duplicate',pd.Series('no',index=a.index)).astype(str).str.lower()
    a=a[(a.review_required!='yes')&(a.suspected_duplicate!='yes')].copy()
    a=a[a.attraction_name.fillna('').astype(str).str.len().ge(4)]
    a=a[~a.attraction_name.astype(str).str.match(r'^\s*[#\"\']')]
    a=a.sort_values('attraction_id').drop_duplicates(['attraction_name','district'],keep='first').reset_index(drop=True)
    b=b.dropna(subset=['latitude','longitude'])
    b=b[b.latitude.between(5.5,10.2)&b.longitude.between(79.3,82.3)].copy()
    role=b.dataset_role.fillna('').astype(str).str.lower()
    group=b.tourism_group.fillna('').astype(str).str.lower()
    role_groups=[role.eq('attraction'),role.eq('service') & group.eq('accommodation'),role.eq('service') & group.eq('food_and_drink'),role.eq('service') & group.eq('travel_support')]
    coords=_xy(a.latitude,a.longitude)
    features=np.zeros((len(a),4),dtype=float)
    for j,mask in enumerate(role_groups):
        subset=b[mask]
        if subset.empty:continue
        entries=subset[['latitude','longitude']].to_numpy(dtype=float)
        tree=cKDTree(_xy(entries[:,0],entries[:,1]))
        candidates=tree.query_ball_point(coords,r=RADIUS_KM*1.12)
        for i,ids in enumerate(candidates):
            if ids:
                within=np.sum(_haversine(a.iloc[i].latitude,a.iloc[i].longitude,entries[ids])<=RADIUS_KM)
                features[i,j]=within
    for j,name in enumerate(NEARBY_FEATURES):a[name]=features[:,j]
    # Normalize all valid attractions against a common national reference, not per district.
    normalized=np.zeros_like(features)
    for j in range(4):
        values=np.log1p(features[:,j]); maximum=values.max()
        if maximum>0:normalized[:,j]=values/maximum
    weights,cr,_=ahp_weights(build_matrix(DEFAULT_COMPARISONS))
    a['experimental_destination_score']=np.round(100*normalized@weights,2)
    a['flagged']=False
    a['source_label']='Original OSM mapped candidate'
    for j,name in enumerate(NEARBY_FEATURES):a[name+'_contribution']=np.round(normalized[:,j]*weights[j]*100,2)
    return a,weights,float(cr)

def _photo_name_key(value):
    """Conservative normalized name matching; never match by district alone."""
    plain = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


@st.cache_data(show_spinner=False)
def _approved_photo_rows(register_path):
    """Only photographs explicitly approved in the project's review CSV."""
    path = Path(register_path)
    if not path.is_file():
        return pd.DataFrame()
    rows = pd.read_csv(path, dtype=str).fillna("")
    if not {"final_image_decision", "image_file"}.issubset(rows.columns):
        return pd.DataFrame()
    return rows.loc[
        rows["final_image_decision"].str.strip().str.casefold().eq("approved")
    ].copy()


def _photo(r, images, image_dir):
    """Use registered, approved photos only, with same-place name matching.

    A photo from a different attraction in the same district is never used.
    """
    image_dir = Path(image_dir)
    meta = images.get(str(r.attraction_id))
    if meta:
        filename = str(meta.get("image_file", ""))
        path = image_dir / filename
        if filename and path.name == filename and path.is_file():
            return path, meta

    register = image_dir.parents[2] / "config" / "attraction_image_final_review.csv"
    approved = _approved_photo_rows(str(register))
    if approved.empty:
        return None, None

    requested = _photo_name_key(r.attraction_name)
    district = _photo_name_key(r.district)
    if not requested:
        return None, None

    for _, row in approved.iterrows():
        if _photo_name_key(row.get("district", "")) != district:
            continue
        names = (row.get("dataset_attraction_name", ""), row.get("photo_attraction_name", ""))
        if requested not in {_photo_name_key(n) for n in names}:
            continue
        # If both coordinates are recorded, rule out same-name distant places.
        try:
            image_lat = float(row.get("latitude", ""))
            image_lon = float(row.get("longitude", ""))
            if float(_haversine(float(r.latitude), float(r.longitude),
                                np.array([[image_lat, image_lon]]))[0]) > 1.0:
                continue
        except (ValueError, TypeError):
            # Coordinates unavailable: exact attraction name + district still required.
            pass
        filename = str(row.get("image_file", ""))
        path = image_dir / filename
        if filename and path.name == filename and path.is_file():
            return path, row.to_dict()
    return None, None

def _credit(meta):
    if not meta:return
    creator=escape(str(meta.get('creator','Creator not listed')))
    licence=escape(str(meta.get('license','License not specified')))
    src=str(meta.get('source_page',''))
    lnk=str(meta.get('license_url',''))
    credit=f'Photo: {creator} · {licence}'
    if src.startswith('https://'):credit+=f' · [Source]({src})'
    if lnk.startswith('https://'):credit+=f' · [License]({lnk})'
    st.caption(credit)

def _styles():
    st.markdown('''<style>
    .tm-potential-hero {border-radius:18px;padding:26px 28px;background:linear-gradient(115deg,#103b59,#0c8276);color:white;margin:5px 0 18px}
    .tm-potential-hero h2{color:#fff!important;margin:4px 0 8px;font-size:1.9rem}
    .tm-potential-hero p{color:#e4f6f1;margin:0;font-size:.94rem}
    .tm-potential-eyebrow{font-size:.70rem;letter-spacing:.14em;font-weight:800;color:#aaf3df}
    .tm-potential-section{font-size:1.35rem;font-weight:800;color:#123b5d;margin:18px 0 5px}
    .tm-potential-sub{font-size:.85rem;color:#687b86;margin:0 0 12px}
    .tm-potential-name{font-size:1.25rem;line-height:1.3;color:#14384e;font-weight:800;margin:8px 0 4px}
    .tm-potential-meta{font-size:.8rem;color:#638080;margin-bottom:10px}
    .tm-potential-photo-placeholder{height:172px;display:flex;align-items:center;justify-content:center;border-radius:12px;background:linear-gradient(145deg,#dbece8,#eaf3f9);color:#5f817e;font-weight:650;text-align:center;padding:12px}
    .tm-potential-statrow{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:10px 0}
    .tm-potential-stat{background:#f0f7f6;padding:10px 11px;border-radius:11px;color:#37576a;font-size:.76rem}
    .tm-potential-stat b{display:block;color:#173f5b;font-size:1.15rem}
    .tm-potential-score{font-size:1.65rem;font-weight:850;color:#0b826a}
    .tm-potential-score small{font-size:.8rem;color:#627e8b;font-weight:600}
    .tm-potential-bar{height:9px;border-radius:20px;background:#e5eee9;overflow:hidden;margin:7px 0 8px}
    .tm-potential-fill{height:100%;border-radius:20px;background:linear-gradient(90deg,#10a88c,#2183aa)}
    .tm-potential-chip{display:inline-block;background:#e8f6f2;color:#16715d;font-size:.75rem;font-weight:700;padding:5px 9px;border-radius:20px;margin:0 5px 5px 0}
    .tm-potential-note{background:#edf7f4;padding:14px 16px;border-radius:12px;color:#224f57;line-height:1.6;font-size:.90rem}
    .tm-potential-weight{margin:10px 0}
    .tm-potential-weight>div:first-child{display:flex;justify-content:space-between;gap:12px;font-size:.84rem;color:#375669;font-weight:600}
    .tm-potential-weight .tm-potential-bar{margin-top:5px}
    .tm-potential-image img{border-radius:12px;object-fit:cover;max-height:310px}
    </style>''',unsafe_allow_html=True)


def _stats_html(r):
    items=[('Nearby attractions','nearby_attractions'),('Places to stay','nearby_accommodation'),
           ('Food & drink','nearby_food'),('Travel support','nearby_travel')]
    return '<div class="tm-potential-statrow">'+''.join(
        f'<div class="tm-potential-stat"><b>{int(r[key]):,}</b>{label}</div>' for label,key in items
    )+'</div>'


def _score_html(score):
    score=float(np.clip(score,0,100))
    return (f'<div class="tm-potential-score">{score:.1f}<small> / 100</small></div>'
            f'<div class="tm-potential-bar"><div class="tm-potential-fill" style="width:{score:.2f}%"></div></div>')


def _photo_display(r,images,image_dir,*,large=False):
    file,meta=_photo(r,images,image_dir)
    if file:
        st.image(str(file),use_container_width=True)
    else:
        st.markdown('<div class="tm-potential-photo-placeholder">📷<br>Location photo not yet approved</div>',unsafe_allow_html=True)
    return meta


def _insight(r):
    vals={
        'nearby_attractions':int(r.nearby_attractions),
        'nearby_accommodation':int(r.nearby_accommodation),
        'nearby_food':int(r.nearby_food),
        'nearby_travel':int(r.nearby_travel),
    }
    text=f"Within 5 km of this mapped destination, the dataset lists {vals['nearby_attractions']:,} other or nearby attraction records, {vals['nearby_accommodation']:,} accommodation records, {vals['nearby_food']:,} food-and-drink records, and {vals['nearby_travel']:,} travel-support records."
    return text+' These are unverified map listings, not visitor ratings, travel-time estimates or guarantees of service availability.'


def _choose_destination(aid):
    st.session_state["tm_potential_focus_id"] = str(aid)
    st.session_state["tm_potential_destination_v3"] = str(aid)


def render_destination_potential(root, images, image_dir, maplibre_panel, trip_button):
    _styles()
    src=Path(root)/'data/processed/travelmind_combined_clusters.csv'
    candidates=Path(root)/'data/processed/tourism_infrastructure/tourism_place_grid_assignments.csv'
    st.markdown('''<div class="tm-potential-hero"><div class="tm-potential-eyebrow">TRAVELMIND · COMPONENT 02</div>
        <h2>Discover destinations around Sri Lanka</h2>
        <p>Explore places by district, see what is mapped nearby, and plan your next stop.</p></div>''',unsafe_allow_html=True)
    if not src.exists() or not candidates.exists():
        st.warning('Destination discovery requires the attraction dataset and tourism_place_grid_assignments.csv.')
        st.code(str(candidates));return
    try:
        places,weights,cr=_calculate(str(src),str(candidates))
    except Exception as exc:
        st.error(f'Cannot load district destinations: {exc}');return
    if places.empty:st.info('No mapped destinations available.');return
    opts=sorted(places.district.dropna().astype(str).unique().tolist())
    f1,f2,f3=st.columns([1,1,1.5],gap='medium')
    with f1: district=st.selectbox('Choose a district',opts,index=opts.index('Badulla') if 'Badulla' in opts else 0,key='tm_dest_district')
    with f2: interest=st.selectbox('Tourism type',['All types']+sorted(places.tourism_category.dropna().astype(str).unique().tolist()),key='tm_dest_category')
    with f3: name=st.text_input('Find a destination',placeholder='e.g. Ella Rock',key='tm_dest_name')
    photo_only=st.checkbox('📷 Show destinations with approved photos only', value=False,
        key='tm_dest_approved_photos_only',
        help='Only changes which destinations are displayed. The infrastructure scores are not recalculated.')
    show=places[places.district.eq(district)].copy()
    if interest!='All types':show=show[show.tourism_category.eq(interest)]
    if name.strip():show=show[show.attraction_name.astype(str).str.contains(name.strip(),case=False,regex=False,na=False)]
    show=show.sort_values(['experimental_destination_score','attraction_name'],ascending=[False,True]).reset_index(drop=True)
    if show.empty:
        st.info('No matching destinations. Try another district or tourism type.')
        return
    if photo_only:
        # Keep score calculation and ranking order unchanged; only select exact approved photo matches.
        photo_flags = [bool(_photo(row, images, image_dir)[0]) for row in show.itertuples(index=False)]
        total_before = len(show)
        show = show.loc[photo_flags].reset_index(drop=True)
        if show.empty:
            st.info(f'No destinations with approved, correctly matched photos were found among the {total_before} matching mapped destinations. Turn off the photo filter to see all destinations.')
            return
        st.info(f'📷 Photo-filtered selection: {len(show)} of {total_before} matching destinations have approved photos. The original infrastructure scores are unchanged; these are **not** the overall Top 5 in {district}.')
    else:
        st.caption('Showing all matching mapped destinations, including places without approved photos.')
    # Only assign rankings among the visible filtered results; do not imply expert validation.
    ids=show.attraction_id.astype(str).tolist()
    old=st.session_state.get('tm_potential_focus_id')
    if old not in ids:old=ids[0]
    if st.session_state.get('tm_potential_destination_v3') not in ids:
        st.session_state['tm_potential_destination_v3']=old
    idx=ids.index(st.session_state['tm_potential_destination_v3'])
    selected=st.selectbox('Select a destination to explore',ids,index=idx,
        format_func=lambda aid:str(show.loc[show.attraction_id.astype(str).eq(aid),'attraction_name'].iloc[0]),
        key='tm_potential_destination_v3')
    st.session_state['tm_potential_focus_id']=str(selected)
    r=show.loc[show.attraction_id.astype(str).eq(str(selected))].iloc[0]
    # SELECTED HERO - genuine available photo with attribution, never assume attraction quality.
    st.markdown('<div class="tm-potential-section">📍 Your selected destination</div>',unsafe_allow_html=True)
    with st.container(border=True):
        photo_col,info_col=st.columns([1.05,1.35],gap='large')
        with photo_col:
            meta=_photo_display(r,images,image_dir,large=True)
            _credit(meta)
        with info_col:
            st.markdown(f'<div class="tm-potential-name">{escape(str(r.attraction_name))}</div>',unsafe_allow_html=True)
            st.markdown(f'<div class="tm-potential-meta">📍 {escape(str(r.district))} · {escape(str(r.tourism_category))}</div>',unsafe_allow_html=True)
            st.markdown('<span class="tm-potential-chip">Mapped destination</span><span class="tm-potential-chip">5 km nearby search</span>',unsafe_allow_html=True)
            st.markdown('**Nearby tourism support score**')
            st.markdown(_score_html(r.experimental_destination_score),unsafe_allow_html=True)
            st.caption('Experimental relative infrastructure score — not a review, safety rating or attraction-quality assessment.')
            st.markdown(_stats_html(r),unsafe_allow_html=True)
            target='https://www.google.com/maps/search/?'+urlencode({'api':1,'query':f'{r.latitude:.7f},{r.longitude:.7f}'})
            st.link_button('📍 Open location in Google Maps',target,use_container_width=True)
            trip_button(unique_id=str(r.attraction_id),name=str(r.attraction_name),lat=r.latitude,
                        lon=r.longitude,key='tm_potential_trip_save',warning=True)
    # TOP THREE PODIUM CARDS
    st.markdown(f'<div class="tm-potential-section">🏅 {"Featured destinations with approved photos" if photo_only else "Featured destinations"} in {escape(district)}</div>',unsafe_allow_html=True)
    st.markdown('<div class="tm-potential-sub">' + ('Top three among photo-approved matches only — not the overall district Top 3.' if photo_only else 'Top three among your current filters, ordered by experimental nearby mapped infrastructure.') + ' Scores are not tourism popularity.</div>',unsafe_allow_html=True)
    top3=show.head(3)
    medals=['🥇','🥈','🥉']
    columns=st.columns(3,gap='medium')
    for i,(col,(_,v)) in enumerate(zip(columns,top3.iterrows())):
        with col:
            with st.container(border=True):
                st.markdown(f'**{medals[i]}  #{i+1} · {"Photo selection" if photo_only else "Mapped destination"}**')
                meta=_photo_display(v,images,image_dir)
                st.markdown(f'<div class="tm-potential-name">{escape(str(v.attraction_name))}</div>',unsafe_allow_html=True)
                st.markdown(f'<div class="tm-potential-meta">{escape(str(v.tourism_category))} · {escape(str(v.district))}</div>',unsafe_allow_html=True)
                st.markdown(_score_html(v.experimental_destination_score),unsafe_allow_html=True)
                st.caption('Nearby infrastructure score')
                st.button('Explore →',key=f'tm_top3_explore_{i}',use_container_width=True,
                          on_click=_choose_destination,args=(str(v.attraction_id),))
                _credit(meta)
    # MAP & EXPLANATION
    st.markdown('<div class="tm-potential-section">🗺️ Explore the area</div>',unsafe_allow_html=True)
    map_col,why_col=st.columns([1.65,1],gap='large')
    with map_col:
        maplibre_panel(show.head(250),height=490,center_record=r,areas_visible=False,show_legend=False)
    with why_col:
        with st.container(border=True):
            st.markdown('#### 💡 Why this place stands out')
            st.markdown(f'<div class="tm-potential-note">{escape(_insight(r))}</div>',unsafe_allow_html=True)
            st.markdown('#### What is mapped nearby?')
            st.markdown(_stats_html(r),unsafe_allow_html=True)
            st.caption('Distance is straight-line; actual routes and opening status are unknown.')
            st.markdown('**Relative contribution to this score**')
            for i,(label,col) in enumerate(zip(DISPLAY,NEARBY_FEATURES)):
                contrib=float(r[col+'_contribution'])
                st.markdown(f'<div class="tm-potential-weight"><div><span>{escape(label)}</span><span>{contrib:.1f} points</span></div><div class="tm-potential-bar"><div class="tm-potential-fill" style="width:{min(100,contrib):.2f}%"></div></div></div>',unsafe_allow_html=True)
            st.caption('Contributions are score points under illustrative AHP weights, not tourist opinions.')
    # FIVE COMPACT RANK CARDS - with all requested feature counts and CTA
    st.markdown(f'<div class="tm-potential-section">🏆 {"Top 5 with approved photos" if photo_only else "Top 5 destinations"} in {escape(district)}</div>',unsafe_allow_html=True)
    st.markdown('<div class="tm-potential-sub">' + ('Photo-filtered Top 5; higher-ranked places without approved photos are hidden. ' if photo_only else '') + 'Calculated from mapped infrastructure within 5 km, not visitor ratings.</div>',unsafe_allow_html=True)
    for i,(_,v) in enumerate(show.head(5).iterrows()):
        with st.container(border=True):
            ph,details,action=st.columns([1,2.1,.85],gap='medium',vertical_alignment='center')
            with ph:
                meta=_photo_display(v,images,image_dir)
                _credit(meta)
            with details:
                st.markdown(f'<div class="tm-potential-name">{medals[i] if i<3 else "🌿"} #{i+1} · {escape(str(v.attraction_name))}</div>',unsafe_allow_html=True)
                st.markdown(f'<span class="tm-potential-chip">{escape(str(v.tourism_category))}</span><span class="tm-potential-chip">{escape(district)}</span>',unsafe_allow_html=True)
                st.markdown(_stats_html(v),unsafe_allow_html=True)
            with action:
                st.markdown(_score_html(v.experimental_destination_score),unsafe_allow_html=True)
                st.caption('Infrastructure score')
                st.button('Explore →',key=f'tm_top5_explore_{i}',use_container_width=True,
                          on_click=_choose_destination,args=(str(v.attraction_id),))
    # RESEARCH TRANSPARENCY
    with st.expander('🔬 About these scores · AHP methodology',expanded=False):
        st.write('This separate destination-surroundings model uses nearby Overture-mapped POI counts within a straight-line 5 km radius. Counts are log-scaled, normalized against nationwide maxima, and combined using illustrative AHP comparisons.')
        st.markdown('**Illustrative AHP criteria weights**')
        for label,w in zip(DISPLAY,weights):
            pct=100*float(w)
            st.markdown(f'<div class="tm-potential-weight"><div><span>{escape(label)}</span><span>{pct:.1f}%</span></div><div class="tm-potential-bar"><div class="tm-potential-fill" style="width:{pct:.2f}%"></div></div></div>',unsafe_allow_html=True)
        st.write(f'Pairwise comparison consistency ratio: **{cr:.3f}**. The matrix is illustrative, not collected from experts. A low CR does not validate destination rankings.')
        st.warning('The model does not assess scenery, accessibility, safety, visitor popularity, service quality, opening hours, or actual travel times. Candidate map records and photos must be independently checked; mapping completeness and possible duplicates can bias scores.')
        st.write('This destination-level model is separate from the 5 km grid AHP index and your DBSCAN attraction-rich area shortlist.')
        export=show[['attraction_id','attraction_name','district','tourism_category','experimental_destination_score']+NEARBY_FEATURES]
        st.download_button('Download district infrastructure results (CSV)',export.to_csv(index=False).encode('utf-8'),file_name='travelmind_destination_infrastructure_preview.csv',mime='text/csv')
