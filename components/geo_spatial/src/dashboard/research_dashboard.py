from pathlib import Path
from html import escape
import json

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title='TravelMind | ML Research', page_icon='🧭', layout='wide')
ROOT = Path(__file__).resolve().parents[2]
COMBINED = ROOT / 'data/processed/travelmind_combined_clusters.csv'
COMPARISON = ROOT / 'results/reports/model_comparison.csv'
HOTSPOTS = ROOT / 'results/reports/dbscan_hotspot_candidates.csv'
BOUNDARIES = ROOT / 'data/boundaries/sri_lanka_districts.geojson'

@st.cache_data(show_spinner=False)
def read_csv(path):
    if not path.is_file():
        raise FileNotFoundError(f'Missing required file: {path}')
    return pd.read_csv(path, low_memory=False)

@st.cache_data(show_spinner=False)
def read_boundaries(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None

try:
    data = read_csv(COMBINED).copy()
    comparison = read_csv(COMPARISON).copy()
    boundaries = read_boundaries(BOUNDARIES)
except (FileNotFoundError, pd.errors.ParserError, UnicodeError) as error:
    st.error(str(error))
    st.stop()

required = {'attraction_id', 'attraction_name', 'district', 'tourism_category', 'latitude', 'longitude', 'kmeans_cluster', 'dbscan_cluster'}
missing = required - set(data.columns)
if missing:
    st.error('Missing combined-cluster columns: ' + ', '.join(sorted(missing)))
    st.stop()
required_metrics = {'model', 'parameters', 'n_clusters', 'noise_points', 'coverage_percentage', 'silhouette_score', 'davies_bouldin_index'}
if not required_metrics.issubset(comparison.columns):
    st.error('model_comparison.csv does not contain the expected metric columns.')
    st.stop()
for col in ['latitude', 'longitude', 'kmeans_cluster', 'dbscan_cluster']:
    data[col] = pd.to_numeric(data[col], errors='coerce')
data = data.loc[data.latitude.between(5.5, 10.2) & data.longitude.between(79.4, 82.2)].copy()
for col in ['attraction_name', 'district', 'tourism_category']:
    data[col] = data[col].fillna('Unknown').astype(str)
data['dbscan_is_clustered'] = data.dbscan_cluster.ge(0)
data['needs_review'] = data.get('review_required', pd.Series('no', index=data.index)).astype(str).str.lower().eq('yes')
data['suspected_duplicate_flag'] = data.get('suspected_duplicate', pd.Series('no', index=data.index)).astype(str).str.lower().eq('yes')

st.title('🧭 TravelMind — Geo-Spatial Tourism Intelligence')
st.caption('Machine-learning research dashboard | K-Means and DBSCAN clustering of OpenStreetMap-derived candidate attraction records')
st.warning('Research limitation: These are unverified OSM-derived attraction candidates, not observed visitor counts. Clusters are spatial concentrations of records, not validated tourist demand or confirmed high-potential destinations.')

with st.sidebar:
    st.header('Research filters')
    districts = sorted(x for x in data.district.unique() if x and x != 'Unknown')
    district = st.selectbox('District', ['All districts'] + districts)
    categories = sorted(data.tourism_category.dropna().unique())
    category = st.selectbox('Tourism category', ['All categories'] + categories)
    map_model = st.radio('Map model', ['DBSCAN', 'K-Means'], horizontal=True)
    include_noise = st.checkbox('Include DBSCAN noise points', value=True)
    max_markers = st.slider('Map sample size', 100, 3000, 800, 100)
    show_districts = st.checkbox('Draw district boundaries', True)
    st.caption('Markers are sampled for browser performance; research summaries use all filtered records.')

filtered = data.copy()
if district != 'All districts':
    filtered = filtered.loc[filtered.district.eq(district)]
if category != 'All categories':
    filtered = filtered.loc[filtered.tourism_category.eq(category)]

c1, c2, c3, c4 = st.columns(4)
c1.metric('OSM candidates (filtered)', f'{len(filtered):,}')
c2.metric('DBSCAN clusters in view', f'{filtered.loc[filtered.dbscan_is_clustered, "dbscan_cluster"].nunique():,}')
c3.metric('DBSCAN noise in view', f'{(~filtered.dbscan_is_clustered).sum():,}')
c4.metric('Records flagged for review', f'{filtered.needs_review.sum():,}')

ov, model_tab, map_tab, hotspots_tab, quality_tab = st.tabs([
    '📌 Research overview', '📊 ML model results', '🗺️ Cluster GIS map', '🔥 Hotspot candidates', '🔎 Data quality'
])

with ov:
    st.subheader('Research workflow')
    st.write('OpenStreetMap collection → spatial data preparation → K-Means / DBSCAN clustering → model evaluation → candidate hotspot screening → GIS visualization.')
    st.write('The full combined dataset contains **8,590 rows** in your current experiment.' if len(read_csv(COMBINED)) == 8590 else f'The source combined dataset contains **{len(read_csv(COMBINED)):,} rows**.')
    st.write('**K-Means:** geographically partitions all records into broad groups; **DBSCAN:** identifies density-connected groups and noise records.')
    st.write('**Interpretation warning:** the number of geographic clusters is not a direct measure of attraction quality, tourism demand, or economic potential.')
    st.subheader('Records by district (filtered)')
    if not filtered.empty:
        st.bar_chart(filtered.district.value_counts().head(20), horizontal=True)
    else:
        st.info('No records match the filters.')

with model_tab:
    st.subheader('Your actual trained-model evaluation')
    st.dataframe(comparison, hide_index=True, width='stretch')
    left, right = st.columns(2)
    metrics = comparison.set_index('model')
    with left:
        st.markdown('**Silhouette score (higher is usually better)**')
        st.bar_chart(metrics[['silhouette_score']])
    with right:
        st.markdown('**Davies–Bouldin index (lower is usually better)**')
        st.bar_chart(metrics[['davies_bouldin_index']])
    st.info('Important: Your DBSCAN silhouette and Davies–Bouldin were calculated on non-noise records, whereas K-Means covers all records. The model metrics are therefore not strictly like-for-like comparisons.')
    st.markdown('**Coverage of input records**')
    st.bar_chart(metrics[['coverage_percentage']])
    st.markdown('**Cluster membership distribution (filtered records)**')
    choice = st.selectbox('Distribution model', ['DBSCAN', 'K-Means'], key='dist_model')
    cluster_col = 'dbscan_cluster' if choice == 'DBSCAN' else 'kmeans_cluster'
    if not filtered.empty:
        sizes = filtered[cluster_col].value_counts().head(25)
        st.bar_chart(sizes)
    st.caption('Cluster IDs are arbitrary labels; K-Means and DBSCAN labels do not represent equivalent regions.')

@st.cache_data(show_spinner=False)
def sampled_map_rows(df, model, noise, limit):
    col = 'dbscan_cluster' if model == 'DBSCAN' else 'kmeans_cluster'
    selected = df if noise or model != 'DBSCAN' else df.loc[df.dbscan_cluster.ge(0)]
    if len(selected) > limit:
        return selected.sample(n=limit, random_state=42).copy()
    return selected.copy()

with map_tab:
    st.subheader('Interactive geographic clustering')
    st.caption('Offline tile-free Folium map with district boundary polygons. The background is intentionally plain to avoid third-party map tile errors.')
    points = sampled_map_rows(filtered, map_model, include_noise, max_markers)
    m = folium.Map(location=[7.87, 80.77], zoom_start=8, tiles=None, control_scale=True, prefer_canvas=True)
    m.get_root().header.add_child(folium.Element('<style>.leaflet-container {background:#e6f3fa !important;}</style>'))
    if boundaries and show_districts:
        folium.GeoJson(boundaries, name='Districts', style_function=lambda f: {'fillColor':'#d4eadb', 'color':'#718096','weight':1,'fillOpacity':0.77}).add_to(m)
    palette = ['#2563eb','#ef4444','#16a34a','#9333ea','#d97706','#0891b2','#db2777','#65a30d','#7c3aed','#b45309','#0f766e','#dc2626']
    col = 'dbscan_cluster' if map_model == 'DBSCAN' else 'kmeans_cluster'
    for row in points.itertuples(index=False):
        cluster = getattr(row, col)
        is_noise = pd.isna(cluster) or int(cluster) == -1
        color = '#64748b' if is_noise else palette[int(cluster) % len(palette)]
        name = escape(str(row.attraction_name))
        district_name = escape(str(row.district))
        label = 'Noise' if is_noise else str(int(cluster))
        content = f'<b>{name}</b><br>District: {district_name}<br>{map_model} cluster: {label}<br>Unverified OSM candidate'
        folium.CircleMarker([float(row.latitude), float(row.longitude)], radius=3 if is_noise else 5,
                            color=color, fill=True, fill_color=color, fill_opacity=0.75,
                            weight=1, tooltip=name, popup=folium.Popup(content, max_width=270)).add_to(m)
    if not points.empty:
        southwest = [points.latitude.min(), points.longitude.min()]
        northeast = [points.latitude.max(), points.longitude.max()]
        if southwest != northeast:
            m.fit_bounds([southwest, northeast], padding=(20, 20))
    st_folium(m, height=630, width=None, key='research_cluster_map')
    st.caption(f'Showing {len(points):,} markers sampled from {len(filtered):,} filtered candidate records. Colors repeat for DBSCAN clusters because there are many clusters; use the popup for the cluster ID.')

with hotspots_tab:
    st.subheader('DBSCAN candidate hotspot screening')
    st.caption('A DBSCAN cluster is not automatically a valid hotspot; large connected clusters can span multiple districts.')
    clustered = filtered.loc[filtered.dbscan_is_clustered]
    if clustered.empty:
        st.info('No clustered records for these filters.')
    else:
        summary = (clustered.groupby('dbscan_cluster').agg(
            candidate_records=('attraction_id','size'),
            districts=('district', lambda s: ', '.join(sorted(set(s))[:5])),
            review_flagged=('needs_review','sum'),
            suspected_duplicates=('suspected_duplicate_flag','sum'),
            mean_lat=('latitude','mean'),
            mean_lon=('longitude','mean')
        ).reset_index().sort_values('candidate_records', ascending=False))
        summary['review_flag_percent'] = (100 * summary.review_flagged / summary.candidate_records).round(1)
        summary['dbscan_cluster'] = summary.dbscan_cluster.astype(int)
        st.dataframe(summary.head(100), hide_index=True, width='stretch')
        st.download_button('Download filtered cluster summaries', summary.to_csv(index=False).encode('utf-8'), 'travelmind_cluster_summary.csv', 'text/csv')
        st.caption('Candidate counts and percentages are computed from current sidebar filters; these are not externally validated popularity rankings.')
    if HOTSPOTS.exists():
        with st.expander('Original hotspot candidate report'):
            st.dataframe(read_csv(HOTSPOTS).head(100), hide_index=True, width='stretch')

with quality_tab:
    st.subheader('Dataset limitations and quality indicators')
    a, b, c = st.columns(3)
    a.metric('Flagged for review', f'{filtered.needs_review.sum():,}')
    b.metric('Suspected duplicates', f'{filtered.suspected_duplicate_flag.sum():,}')
    if 'verification_status' in filtered.columns:
        verified_count = filtered.verification_status.astype(str).str.lower().isin(['verified', 'confirmed']).sum()
        c.metric('Verified by status', f'{verified_count:,}')
    else:
        c.metric('Verified by status', 'Not supplied')
    st.write('The model currently clusters unverified OpenStreetMap features. Religious sites and other tagged features may not all represent visitable tourism attractions. Duplicate tags and dense areas can inflate apparent hotspots.')
    st.write('Before making claims about tourism potential, review candidate attractions, duplicate locations, cluster radius/sprawl, category balance, and external tourism evidence.')
    cols = [x for x in ['attraction_id','attraction_name','district','tourism_category','review_required','suspected_duplicate','verification_status','kmeans_cluster','dbscan_cluster'] if x in filtered.columns]
    st.dataframe(filtered[cols].head(500), hide_index=True, width='stretch')

st.divider()
st.caption('TravelMind research prototype • Clustering results generated outside Streamlit using scikit-learn • This dashboard reads saved experiment outputs; it does not retrain the models.')
