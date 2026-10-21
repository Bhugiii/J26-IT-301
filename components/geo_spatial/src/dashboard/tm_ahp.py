"""TravelMind Component 02: experimental AHP tourism infrastructure potential.

The grid is Overture-derived and NOT a measurement of visitors or observed tourism
potential. Pairwise comparisons start with illustrative, editable judgments; they
must not be described as expert-elicited. No learned/validated weights are claimed.
"""
from __future__ import annotations

from pathlib import Path
import math
from html import escape
from urllib.parse import urlencode
import numpy as np
import pandas as pd
import folium
import streamlit as st
from streamlit_folium import st_folium

CRITERIA = [
    ("Attractions", "attraction_count"),
    ("Accommodation", "service_group_accommodation_count"),
    ("Food and drink", "service_group_food_and_drink_count"),
    ("Travel support", "service_group_travel_support_count"),
]
RI = {1: 0., 2: 0., 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24}
# Conservative illustrative comparisons, not expert survey responses.
DEFAULT_COMPARISONS = {(0, 1): 3., (0, 2): 3., (0, 3): 5.,
                       (1, 2): 1., (1, 3): 3., (2, 3): 3.}
CHOICES = [1/9, 1/7, 1/5, 1/3, 1., 3., 5., 7., 9.]


def ahp_weights(matrix: np.ndarray):
    vals, vecs = np.linalg.eig(matrix)
    i = int(np.argmax(vals.real))
    eigmax = float(vals[i].real)
    weights = np.abs(vecs[:, i].real)
    weights /= weights.sum()
    n = len(weights)
    ci = max(0., (eigmax - n) / (n - 1)) if n > 2 else 0.
    cr = ci / RI.get(n, 1.49) if n > 2 else 0.
    return weights, cr, eigmax


def build_matrix(values: dict):
    n = len(CRITERIA)
    m = np.ones((n, n), dtype=float)
    for (i, j), value in values.items():
        m[i, j] = float(value)
        m[j, i] = 1 / float(value)
    return m


def load_grid(path: Path):
    df = pd.read_csv(path, low_memory=False)
    required = ['grid_id', 'grid_x', 'grid_y', 'center_latitude', 'center_longitude',
                'center_inside_boundary', 'boundary_overlap_fraction'] + [c for _, c in CRITERIA]
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"Grid columns missing: {', '.join(missing)}")
    if df.grid_id.isna().any() or df.grid_id.duplicated().any():
        raise ValueError('Grid IDs must be non-null and unique.')
    numbers = ['grid_x', 'grid_y', 'center_latitude', 'center_longitude',
               'boundary_overlap_fraction'] + [c for _, c in CRITERIA]
    for col in numbers:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    if df[numbers].isna().any().any():
        raise ValueError('Some necessary GIS grid values are missing or non-numeric.')
    if (df[[c for _, c in CRITERIA]] < 0).any().any():
        raise ValueError('Negative POI counts are not valid.')
    df['center_inside_boundary'] = df['center_inside_boundary'].astype(str).str.lower().eq('true')
    if not df.center_latitude.between(5, 11).all() or not df.center_longitude.between(79, 83).all():
        raise ValueError('Unexpected grid coordinates; verify CSV projection.')
    return df


def score_grid(df, weights, minimum_overlap=0.5):
    out = df.copy()
    eligible = out.center_inside_boundary & out.boundary_overlap_fraction.ge(minimum_overlap)
    out['eligible_for_tpi'] = eligible
    detail = []
    for k, (label, col) in enumerate(CRITERIA):
        vals = np.log1p(out[col].clip(lower=0).astype(float))
        # The original p95 cap forced many different high-count cells to score 100.
        # Use the observed eligible maximum to preserve separation among high-count cells.
        denom = float(vals[eligible].max()) if eligible.any() else 0.
        normalized = np.clip(vals / denom, 0, 1) if denom > 0 else vals * 0
        normalized = pd.Series(normalized, index=out.index)
        out[f'{col}_normalized'] = normalized
        out[f'{col}_contribution'] = normalized * float(weights[k]) * 100
        detail.append(out[f'{col}_contribution'])
    out['experimental_tpi'] = sum(detail).round(2)
    out.loc[~eligible, 'experimental_tpi'] = np.nan
    return out


def _cell_bounds(df):
    """Produce actual 5km-square WGS84 polygons from UTM zone 44N, if pyproj installed."""
    from pyproj import Transformer
    transform = Transformer.from_crs('EPSG:32644', 'EPSG:4326', always_xy=True)
    # Grid indices are constructed by floor(easting / 5000), floor(northing / 5000).
    bounds = []
    for x, y in zip(df.grid_x.to_numpy(dtype=int), df.grid_y.to_numpy(dtype=int)):
        west, south = x * 5000, y * 5000
        p = [(west, south), (west + 5000, south),
             (west + 5000, south + 5000), (west, south + 5000), (west, south)]
        bounds.append([[lat, lon] for lon, lat in (transform.transform(a, b) for a, b in p)])
    return bounds


def map_grid(view, max_cells=3000, focus=None):
    # Explicit OSM tile URL avoids the CARTO basemap's API-key-required placeholder.
    m = folium.Map(location=[7.86, 80.77], zoom_start=7, tiles=None, control_scale=True)
    folium.TileLayer(tiles='https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                     attr='© OpenStreetMap contributors', name='Street map',
                     max_zoom=19).add_to(m)
    if focus is not None:
        m.location = [float(focus.center_latitude), float(focus.center_longitude)]
        m.options['zoom'] = 10
    valid = view[view.eligible_for_tpi].copy()
    # Full national grid is under this guard; use rectangles rather than misleading circular bins.
    if len(valid) > max_cells:
        valid = valid.nlargest(max_cells, 'experimental_tpi')
    try:
        polygons = _cell_bounds(valid)
    except ImportError:
        polygons = None
    for idx, (_, r) in enumerate(valid.iterrows()):
        v = float(r.experimental_tpi)
        color = ('#DCEEE8' if v < 20 else '#A8DBC7' if v < 40 else
                 '#56B6A7' if v < 60 else '#188E89' if v < 80 else '#145374')
        tooltip = f'Mapped area · Relative score {v:.1f}/100 · {int(r.attraction_count)} candidate attractions'
        if polygons is not None:
            folium.Polygon(polygons[idx], color='#fff', weight=.45, fill=True,
                           fill_color=color, fill_opacity=.78, tooltip=tooltip).add_to(m)
        else:
            folium.CircleMarker([r.center_latitude, r.center_longitude], radius=4,
                                color=color, fill=True, fill_color=color, fill_opacity=.8,
                                tooltip=tooltip).add_to(m)
    if focus is not None:
        folium.Marker([float(focus.center_latitude), float(focus.center_longitude)],
                      tooltip='Selected geographic area (5 km grid cell)',
                      icon=folium.Icon(color='blue', icon='info-sign')).add_to(m)
    return m, polygons is not None


@st.cache_data(show_spinner=False)
def load_place_assignments(path: str):
    p = Path(path)
    if not p.is_file():
        return pd.DataFrame(columns=['grid_id','place_name','dataset_role','tourism_group','latitude','longitude'])
    a = pd.read_csv(p, low_memory=False)
    required = {'grid_id','place_name','dataset_role','tourism_group','latitude','longitude'}
    if not required.issubset(a.columns):
        return pd.DataFrame(columns=sorted(required))
    a = a[list(required)].copy()
    a['grid_id'] = a['grid_id'].astype(str)
    a['place_name'] = a['place_name'].fillna('').astype(str).str.strip()
    a['latitude'] = pd.to_numeric(a.latitude, errors='coerce')
    a['longitude'] = pd.to_numeric(a.longitude, errors='coerce')
    a = a[a.place_name.str.len().ge(3) & a.latitude.between(5.5,10.3) & a.longitude.between(79.3,82.4)]
    a = a.drop_duplicates(['grid_id','place_name','dataset_role'])
    return a


@st.cache_data(show_spinner=False)
def load_approved_photo_register(path: str):
    p = Path(path)
    if not p.is_file(): return pd.DataFrame()
    try:
        a = pd.read_csv(p, dtype=str, low_memory=False).fillna('')
    except (OSError, pd.errors.ParserError):
        return pd.DataFrame()
    needed = {'latitude','longitude','image_file','final_image_decision'}
    if not needed.issubset(a.columns): return pd.DataFrame()
    a = a[a.final_image_decision.str.strip().str.casefold().eq('approved')].copy()
    a['latitude'] = pd.to_numeric(a.latitude, errors='coerce')
    a['longitude'] = pd.to_numeric(a.longitude, errors='coerce')
    return a.dropna(subset=['latitude','longitude'])


def area_places(assignments, grid_id, limit=6):
    part = assignments[assignments.grid_id.eq(str(grid_id))]
    attractions = part[part.dataset_role.astype(str).str.casefold().eq('attraction')].copy()
    if attractions.empty: return attractions
    # Display actual dataset candidate names, not invented towns or individual AHP scores.
    attractions = attractions.sort_values(['place_name','latitude'])
    return attractions.head(limit)


def place_label(assignments, grid_id):
    matches = area_places(assignments, grid_id, 1)
    if matches.empty: return 'Mapped geographic area'
    return 'Near mapped place: ' + str(matches.iloc[0].place_name)[:60]


def nearby_approved_photo(register, folder, lat, lon):
    if register.empty or not folder.is_dir(): return None
    # Place is illustrative of local surroundings, NOT AHP-ranked. Use a strict 5 km check.
    delta_lat = (register.latitude - float(lat)) * 111.0
    delta_lon = (register.longitude - float(lon)) * 111.0 * math.cos(math.radians(float(lat)))
    matches = register[(delta_lat**2+delta_lon**2).le(25.0)].copy()
    if matches.empty: return None
    matches['_distance'] = (delta_lat**2+delta_lon**2)**.5
    for _, r in matches.sort_values('_distance').iterrows():
        f = str(r.image_file)
        if Path(f).name != f: continue
        fp = folder / f
        if fp.is_file(): return fp, r
    return None


def preview_photo(register, folder, record):
    found = nearby_approved_photo(register, folder, record.center_latitude, record.center_longitude)
    if not found: return False
    fp, meta = found
    st.image(str(fp), width='stretch')
    creator = str(meta.get('creator','')).strip() or 'Creator not listed'
    licence = str(meta.get('license','')).strip() or 'License not listed'
    st.caption('Nearby approved attraction photograph (not an image of the whole grid area).')
    url = str(meta.get('source_page','')).strip()
    licurl = str(meta.get('license_url','')).strip()
    text = f'Photo: {escape(creator)} · {escape(licence)}'
    if url.startswith('https://'): text += f' · [Source]({url})'
    if licurl.startswith('https://'): text += f' · [License]({licurl})'
    st.markdown(text)
    return True


def _score_gauge(score: float):
    """A compact responsive visual, never a customer-satisfaction rating."""
    value = max(0.0, min(100.0, float(score)))
    return f"""<div style="text-align:center;margin:10px auto 6px;max-width:340px">
      <svg role="img" aria-label="Experimental mapped-infrastructure index {value:.1f} out of 100"
           viewBox="0 0 300 182" style="display:block;width:100%">
        <path d="M40 144 A110 110 0 0 1 260 144" fill="none" stroke="#dcf3e8" stroke-width="24" stroke-linecap="round"/>
        <path d="M40 144 A110 110 0 0 1 260 144" fill="none" stroke="#0e9b75" stroke-width="24"
              stroke-linecap="round" pathLength="100" stroke-dasharray="{value:.1f} 100"/>
        <text x="150" y="125" text-anchor="middle" fill="#123b5d" font-size="47" font-weight="800">{value:.1f}</text>
        <text x="150" y="150" text-anchor="middle" fill="#547086" font-size="13" font-weight="700">EXPERIMENTAL INDEX / 100</text>
        <text x="32" y="177" fill="#718096" font-size="12">0</text>
        <text x="252" y="177" fill="#718096" font-size="12">100</text>
      </svg></div>"""


def _comparison_bars(cell, reference):
    """Two bars show count relative to a reference cell median; not an AHP weight."""
    rows = []
    names = {"attraction_count":"Attractions", "service_group_accommodation_count":"Places to stay",
             "service_group_food_and_drink_count":"Food & drink", "service_group_travel_support_count":"Travel support"}
    for key, name in names.items():
        value = int(cell[key])
        typical = float(reference[key].median())
        top = max(value, typical, 1.)
        a = min(100, value/top*100)
        b = min(100, typical/top*100)
        rows.append(f"""<div style="margin:14px 0">
          <div style="display:flex;justify-content:space-between;font-weight:700;color:#234151;font-size:14px;margin-bottom:6px"><span>{name}</span><span>{value:,} mapped</span></div>
          <div style="height:11px;background:#edf2f6;border-radius:9px;overflow:hidden;margin:4px 0"><div style="width:{a:.1f}%;height:100%;background:#0e9b85;border-radius:9px"></div></div>
          <div style="height:9px;background:#edf2f6;border-radius:9px;overflow:hidden"><div style="width:{b:.1f}%;height:100%;background:#8ba4b5;border-radius:9px"></div></div>
          <div style="color:#72859a;font-size:11px;margin-top:3px">Median comparable cell: {typical:.0f} mapped</div></div>""")
    return """<div style="display:flex;gap:18px;font-size:12px;margin:8px 0 4px;color:#556a7c">
      <span><span style="color:#0e9b85">●</span> Selected area</span><span><span style="color:#8ba4b5">●</span> Median eligible area with places</span></div>""" + ''.join(rows)


def _nearby_description(cell, reference):
    names = [("attraction_count", "mapped attractions"),
             ("service_group_accommodation_count", "places to stay"),
             ("service_group_food_and_drink_count", "food and drink listings"),
             ("service_group_travel_support_count", "travel-support listings")]
    higher = [(float(cell[key]) / max(float(reference[key].median()), 1.), name)
              for key, name in names]
    higher.sort(reverse=True)
    chosen = [name for ratio, name in higher if ratio > 1.5][:2]
    if not chosen:
        return 'This area has mapped attractions and visitor facilities. Open the map to explore its candidate locations.'
    return 'This area has relatively many ' + ' and '.join(chosen) + ' compared with a typical eligible cell containing mapped places.'


def render_ahp(root: Path):
    st.markdown("""<div style="border-radius:17px;padding:27px 30px;background:linear-gradient(110deg,#123B5D,#0D807E);color:white;margin-bottom:18px">
      <div style="font-size:12px;letter-spacing:2px;font-weight:750;color:#B5F3E2">TRAVELMIND · COMPONENT 02</div>
      <div style="font-size:32px;font-weight:800;margin:5px 0">🗺️ Tourism Potential Explorer</div>
      <div style="font-size:14px;color:#E1F5F0">Explore Sri Lanka's mapped tourism infrastructure through a transparent, experimental AHP model.</div>
      </div>""", unsafe_allow_html=True)
    st.caption('A simple guide to mapped attractions and visitor services across Sri Lanka. Scores are **experimental** and do not measure popularity, safety or actual tourism demand.')

    file = root / 'data/processed/tourism_infrastructure/tourism_infrastructure_grid_5km.csv'
    if not file.is_file():
        st.error('Required 5 km grid CSV was not found.')
        st.code(str(file))
        return
    try:
        df = load_grid(file)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.error(f'Unable to read the grid safely: {exc}')
        return

    # Keep all technical settings below the tourist-first overview. Streamlit widget state
    # still governs scoring, even when settings are collapsed.
    compare = {}
    with st.expander('⚖️ Research settings · AHP comparisons and methodology', expanded=False):
        st.warning('Default comparisons are illustrative, not obtained from tourism experts. Do not present them as validated research weights.')
        st.caption('A comparison of 3 means the first criterion is moderately more important; 1/3 means the second is moderately more important.')
        if st.button('Restore consistent illustrative defaults', key='tm_ahp_reset'):
            for (i, j), default in DEFAULT_COMPARISONS.items():
                st.session_state[f'tm_ahp_pair_{i}_{j}'] = default
            st.rerun()
        for (i, j), default in DEFAULT_COMPARISONS.items():
            a, b = CRITERIA[i][0], CRITERIA[j][0]
            key = f'tm_ahp_pair_{i}_{j}'
            if key not in st.session_state:
                st.session_state[key] = default
            compare[(i,j)] = st.selectbox(f'{a} compared with {b}', CHOICES,
                format_func=lambda x: f'{x:g} (equal)' if x == 1 else
                    (f'{x:g} ({a} more important)' if x > 1 else f'1/{int(round(1/x))} ({b} more important)'),
                key=key)
        matrix = build_matrix(compare)
        weights, cr, eig = ahp_weights(matrix)
        st.dataframe(pd.DataFrame({'Criterion': [a for a, _ in CRITERIA],
                                   'Illustrative AHP weight': np.round(weights, 4)}),
                     hide_index=True, width='stretch')
        st.metric('Consistency ratio (CR)', f'{cr:.3f}')
        st.caption('CR < 0.10 is a consistency screening rule, not proof of expert validity.')
        st.markdown('**Scoring:** log(1 + mapped count) per criterion, normalized to the maximum among eligible cells, multiplied by the AHP criterion weight, then summed to a 0–100 relative index.')
        st.markdown('**Limitations:** Overture records are provisional, may contain duplicates, and may reflect mapping coverage and urban density. Roads, verified accessibility, environmental impacts, visitor demand and service quality are not measured.')
    # Evaluate using the same controls even when collapsed.
    if not compare:
        compare = DEFAULT_COMPARISONS
    matrix = build_matrix(compare)
    weights, cr, eig = ahp_weights(matrix)
    if cr >= 0.1:
        st.error(f'Current comparisons are inconsistent (CR = {cr:.3f}, threshold 0.10). Open Research settings and restore illustrative defaults or revise judgments. Rankings are exploratory only.')
    else:
        st.caption(f'Illustrative AHP comparison consistency ratio: {cr:.3f} · internally consistent, not expert-validated.')

    view = score_grid(df, weights)
    eligible = view[view.eligible_for_tpi].copy()
    if eligible.empty:
        st.error('No grid cells satisfy the geographic eligibility criteria.')
        return
    nonempty = eligible[[c for _, c in CRITERIA]].sum(axis=1).gt(0)
    with st.expander('About the map data', expanded=False):
        metrics = st.columns(4)
        metrics[0].metric('Mapped grid cells', f'{len(df):,}')
        metrics[1].metric('Geographically eligible', f'{len(eligible):,}')
        metrics[2].metric('With mapped places', f'{int(nonempty.sum()):,}')
        metrics[3].metric('Criteria assessed', str(len(CRITERIA)))
        st.caption('Eligible cells have their centre inside the country and at least 50% land-boundary overlap. Empty cells score zero. These are map-data counts, not verified tourism statistics.')

    assignments = load_place_assignments(str(root / 'data/processed/tourism_infrastructure/tourism_place_grid_assignments.csv'))
    photos = load_approved_photo_register(str(root / 'config/attraction_image_final_review.csv'))
    photo_folder = root / 'assets/images/attractions'
    st.markdown('### 🌴 Find areas to explore')
    st.write('Choose a mapped area to see nearby **candidate attractions and tourism facilities**. TravelMind compares infrastructure; it does not rank individual attractions.')
    sorted_cells = eligible[eligible[[c for _, c in CRITERIA]].sum(axis=1).gt(0)].sort_values(
        ['experimental_tpi','grid_id'], ascending=[False,True]).reset_index(drop=True)
    if sorted_cells.empty:
        st.info('There are no mapped places in geographically eligible cells.')
        return
    shortlist = sorted_cells.head(40).copy()
    labelled = assignments[assignments.dataset_role.astype(str).str.casefold().eq('attraction')].sort_values(['place_name','latitude']).drop_duplicates('grid_id')
    name_by_grid = labelled.set_index('grid_id').place_name.to_dict()
    def label_for_id(gid):
        name = name_by_grid.get(str(gid))
        return ('Near mapped place: ' + str(name)[:60]) if name else 'Mapped geographic area'
    choice1, choice2 = st.columns([2, 1])
    with choice1:
        query = st.text_input('Find a mapped place or area', placeholder='Try a place name, e.g. a museum or waterfall', key='tm_ahp_tourist_query')
    with choice2:
        mode = st.selectbox('Explore', ['Featured areas','Search all mapped areas'], key='tm_ahp_tourist_mode')
    if query.strip():
        match_ids = set(assignments.loc[assignments.place_name.str.contains(query.strip(),case=False,regex=False,na=False),'grid_id'])
        candidates = sorted_cells[sorted_cells.grid_id.astype(str).isin(match_ids)].head(100)
        if candidates.empty:
            st.info('No matching mapped places in eligible grid areas. Try a different place name.')
            return
    else:
        candidates = shortlist if mode == 'Featured areas' else sorted_cells
    st.markdown('#### Discover featured areas')
    st.caption('Each card represents a 5 km geographic area, not an individual attraction. Place names below come from provisional map records.')
    cards = st.columns(3, gap='medium')
    for i, (_, rec) in enumerate(candidates.head(3).iterrows()):
        with cards[i]:
            with st.container(border=True):
                shown = preview_photo(photos, photo_folder, rec)
                if not shown:
                    st.markdown('<div style="height:110px;border-radius:10px;background:linear-gradient(125deg,#d6f5e6,#c9e3f4);display:flex;align-items:center;justify-content:center;font-size:36px">🌿 🗺️</div>',unsafe_allow_html=True)
                st.markdown('**' + escape(label_for_id(rec.grid_id)) + '**')
                st.caption(f'🏞️ {int(rec.attraction_count):,} mapped attractions · 🏨 {int(rec.service_group_accommodation_count):,} stays')
                st.markdown(f'<div style="font-size:13px;color:#0b8063;font-weight:750">Mapped infrastructure index: {rec.experimental_tpi:.1f}/100</div>',unsafe_allow_html=True)
    candidate_ids = candidates.grid_id.astype(str).tolist()
    lookup = candidates.set_index('grid_id', drop=False)
    selected_id = st.selectbox('Choose an area to explore', candidate_ids,
        format_func=lambda x: f'{label_for_id(x)} · {lookup.loc[x,"experimental_tpi"]:.1f}/100',
        key='tm_ahp_tourist_selected')
    sel = lookup.loc[selected_id]
    reference = eligible[eligible[[c for _, c in CRITERIA]].sum(axis=1).gt(0)]
    st.markdown('### Understand this area')
    left, right = st.columns(2, gap='large')
    with left:
        with st.container(border=True):
            st.markdown('#### Tourism infrastructure index')
            st.caption('A relative indicator based on mapped attractions and visitor facilities — not visitor satisfaction or actual tourism demand.')
            st.markdown(_score_gauge(float(sel.experimental_tpi)), unsafe_allow_html=True)
            st.info(_nearby_description(sel, reference))
            st.caption('Scores use illustrative AHP weights. They are not verified tourism ratings.')
    with right:
        with st.container(border=True):
            st.markdown('#### What this area offers')
            st.caption('Real mapped listing counts versus the median eligible area with mapped places.')
            st.markdown(_comparison_bars(sel, reference), unsafe_allow_html=True)
    st.markdown('### Explore on the map')
    with st.container(border=True):
        st.markdown('**' + escape(label_for_id(selected_id)) + '**')
        st.caption('Map focuses on the geographic area you selected. The marker shows its grid-cell centre, not a precise attraction entrance.')
        try:
            m, squares = map_grid(view, focus=sel)
            st_folium(m, height=540, width=None, returned_objects=[], key='tm_ahp_tourist_map')
            if not squares: st.caption('Install pyproj to view square grid boundaries instead of centre markers.')
        except Exception as exc:
            st.error(f'Unable to display map: {exc}')
        st.caption('Darker cells indicate higher experimental mapped-infrastructure index values. Map data and POIs may be incomplete.')
        maps_url = 'https://www.google.com/maps/search/?' + urlencode({'api':1,'query':f'{float(sel.center_latitude):.6f},{float(sel.center_longitude):.6f}'})
        st.link_button('📍 Open selected area centre in Google Maps', maps_url)
    st.markdown('### Why explore this area?')
    strongest = max([(float(sel[f'{col}_contribution']),label) for label,col in CRITERIA])[1]
    st.success(_nearby_description(sel, reference) + f' **{strongest}** makes the largest contribution to the illustrative AHP score.')
    with st.expander('See the mapped counts and technical grid ID', expanded=False):
        st.caption(f'Grid ID: {sel.grid_id} · Centre: {float(sel.center_latitude):.5f}, {float(sel.center_longitude):.5f}')
        a,b,c,d = st.columns(4)
        a.metric('Attractions',int(sel.attraction_count))
        b.metric('Accommodation',int(sel.service_group_accommodation_count))
        c.metric('Food & drink',int(sel.service_group_food_and_drink_count))
        d.metric('Travel support',int(sel.service_group_travel_support_count))
    st.markdown('### Plan your visit: mapped places in this area')
    local_places = area_places(assignments,selected_id,9)
    if local_places.empty:
        st.info('No individually named attraction candidates were found for this area in the uploaded assignment dataset.')
    else:
        st.caption('These are Overture-derived candidate names assigned to this grid, not individually scored or independently verified attractions. Confirm opening hours and access before travelling.')
        gridcols = st.columns(3,gap='medium')
        for i,(_,r) in enumerate(local_places.iterrows()):
            with gridcols[i%3]:
                with st.container(border=True):
                    st.markdown('📍 **' + escape(str(r.place_name)) + '**')
                    st.caption(str(r.tourism_group).replace('_',' ').title() + ' · candidate listing')
                    url='https://www.google.com/maps/search/?' + urlencode({'api':1,'query':f'{float(r.latitude):.6f},{float(r.longitude):.6f}'})
                    st.link_button('Open location ↗',url,width='stretch',key=f'ahp_tourist_place_{i}')
    st.caption('The area cards summarize mapped places. The underlying AHP scores are experimental; the method and data have not been independently validated.')

    with st.expander('How does TravelMind compare areas? (Experimental method)', expanded=False):
        st.write('We count four types of mapped tourism places, scale the counts so very large values do not dominate, then combine them using provisional AHP criterion weights.')
        st.caption('These weights are illustrative—not judgments collected from tourism experts.')
        weight_series = pd.Series({name: round(float(w) * 100, 2) for (name, _), w in zip(CRITERIA, weights)})
        st.bar_chart(weight_series, horizontal=True)

    with st.expander('See the detailed geographic area comparison table', expanded=False):
        st.markdown('#### Compare mapped areas')
        st.caption('These are 5 km geographic cells, not individual destinations. Scores are experimental and depend on assumptions.')
        columns = ['grid_id', 'experimental_tpi', 'attraction_count',
               'service_group_accommodation_count', 'service_group_food_and_drink_count',
               'service_group_travel_support_count', 'boundary_overlap_fraction']
        display = sorted_cells[columns].head(25).copy()
        display.columns = ['Grid ID', 'Experimental score /100', 'Mapped attractions',
                       'Accommodation', 'Food & drink', 'Travel support', 'Land overlap']
        st.dataframe(display, hide_index=True, width='stretch')

    with st.expander('🔬 Advanced research · preliminary sensitivity and export', expanded=False):
        st.caption('Increase each weight by 20% in turn and renormalize. This is a limited diagnostic, not independent validation.')
        baseline_top = set(eligible.nlargest(min(10, len(eligible)), 'experimental_tpi').grid_id.astype(str))
        diagnostics = []
        for i, (label, _) in enumerate(CRITERIA):
            revised = weights.copy()
            revised[i] *= 1.2
            revised /= revised.sum()
            alternative = score_grid(df, revised)
            alt = alternative[alternative.eligible_for_tpi]
            alt_top = set(alt.nlargest(min(10,len(alt)), 'experimental_tpi').grid_id.astype(str))
            diagnostics.append({'Criterion adjusted': label, 'New weight (%)': round(revised[i]*100, 1),
                                'Top-10 retained': len(baseline_top & alt_top)})
        st.dataframe(pd.DataFrame(diagnostics), hide_index=True, width='stretch')
        st.download_button('Download experimental AHP grid scores (CSV)',
                           view.to_csv(index=False).encode('utf-8'),
                           file_name='travelmind_experimental_ahp_grid.csv', mime='text/csv',
                           key='tm_ahp_export')
        st.info('Next research tasks: obtain independent expert comparisons, audit correlated criteria, validate POIs and assess the index against external evidence before reporting tourism potential.')
