"""TravelMind | Island-wide tourist exploration.
Place at src/dashboard/island_wide_explorer.py
Run: python -m streamlit run src/dashboard/island_wide_explorer.py --server.port 8504
Uses local district GeoJSON, model clustering CSV and optional stability / photo reviews.
All POIs remain provisional unless individually verified. No external basemap tiles.
"""
from pathlib import Path
from html import escape
import json
import math
import re

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title="TravelMind | Explore Sri Lanka", page_icon="🌴", layout="wide")
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/processed/travelmind_combined_clusters.csv"
BOUNDARIES = ROOT / "data/boundaries/sri_lanka_districts.geojson"
STABILITY = ROOT / "results/reports/hotspot_stability_analysis/hotspot_stability_summary.csv"
PHOTO_REVIEW = ROOT / "config/attraction_image_final_review.csv"
PHOTOS = ROOT / "assets/images/attractions"

st.markdown("""<style>
.stApp {background: #f4f8fc; color: #183750;}
.block-container {max-width: 1570px; padding-top: 1.1rem;}
header[data-testid=stHeader] {background: #fff;}
div[data-testid=stMetric] {background:white; border:1px solid #d9e5ee; border-radius:14px; padding:12px;}
[data-testid=stMetricValue] {color:#14547d!important;}
.tm-hero {background:linear-gradient(105deg,#e2f5fa,#eaf6ed); padding:20px 24px; border:1px solid #cee5ec; border-radius:19px; margin-bottom:12px;}
.tm-hero h1 {margin:0;color:#124969;font-size:1.75rem;}
.tm-hero p {margin:7px 0 0;color:#375d70;}
.tm-title {font-weight:800;color:#1c526f;font-size:1.12rem; margin:3px 0 12px;}
.tm-pill {background:#e2f1f6;color:#155774;border-radius:30px;padding:3px 9px;font-size:.77rem;}
</style>""", unsafe_allow_html=True)


def meaningful_name(value):
    s = str(value).strip()
    return (len(s) >= 3 and s.casefold() not in
            {"nan", "none", "unknown", "unnamed", "#temple", "temple", "church"}
            and any(ch.isalpha() for ch in s))


def marked_yes(value):
    return str(value).strip().casefold() in {"yes", "true", "1"}


@st.cache_data(show_spinner="Loading Sri Lanka attraction data...")
def load_data():
    if not DATA.is_file():
        raise FileNotFoundError(f"Missing dataset: {DATA}")
    df = pd.read_csv(DATA, low_memory=False)
    needed = {"attraction_id", "attraction_name", "district", "tourism_category", "latitude", "longitude", "dbscan_cluster"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"Missing CSV columns: {sorted(missing)}")
    for col in ["latitude", "longitude", "dbscan_cluster"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[df.latitude.between(5.5, 10.2) & df.longitude.between(79.4, 82.2)].copy()
    for col in ["attraction_id", "attraction_name", "district", "tourism_category"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    df = df[df.attraction_name.map(meaningful_name)].copy()
    df["flagged"] = df.get("review_required", pd.Series("no", index=df.index)).map(marked_yes)
    df["suspected_dup"] = df.get("suspected_duplicate", pd.Series("no", index=df.index)).map(marked_yes)
    return df.drop_duplicates(subset="attraction_id", keep="first")


@st.cache_data
def load_boundary():
    if not BOUNDARIES.is_file():
        return None
    with open(BOUNDARIES, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_areas():
    if not STABILITY.is_file():
        return pd.DataFrame()
    d = pd.read_csv(STABILITY).fillna("")
    for c in ["center_latitude", "center_longitude", "baseline_records", "strict_retained_pct", "review_flag_pct", "p90_radius_km"]:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    return d


@st.cache_data
def load_photos():
    if not PHOTO_REVIEW.is_file():
        return {}
    d = pd.read_csv(PHOTO_REVIEW).fillna("")
    if not {"attraction_id", "image_file", "final_image_decision"}.issubset(d.columns):
        return {}
    photos = {}
    for _, r in d.iterrows():
        if str(r["final_image_decision"]).strip().casefold() != "approved":
            continue
        name = str(r["image_file"])
        if Path(name).name == name and (PHOTOS / name).is_file():
            photos[str(r["attraction_id"])] = {"path": PHOTOS / name, "creator": str(r.get("creator", "")),
                                                  "license": str(r.get("license", "")), "source": str(r.get("source_page", ""))}
    return photos


def district_from_feature(feature):
    p = feature.get("properties", {})
    for k in ["district", "DISTRICT", "name", "NAME", "NAME_2", "ADM2_EN", "admin2Name", "district_name", "District"]:
        v = p.get(k)
        if v and str(v).strip():
            return str(v).strip()
    return ""


def valid_geojson(feature):
    return feature.get("geometry") is not None


def format_distance(lat1, lon1, lat2, lon2):
    a, b, c, d = map(math.radians, [lat1, lon1, lat2, lon2])
    h = math.sin((c-a)/2)**2 + math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(max(0.0, h))))


def google_link(row):
    return f"https://www.google.com/maps/search/?api=1&query={float(row['latitude']):.7f}%2C{float(row['longitude']):.7f}"


def category_icon(category):
    c = str(category).lower()
    if any(x in c for x in ("beach", "marine", "surf")): return "🏖️"
    if any(x in c for x in ("waterfall", "mountain", "viewpoint", "hiking")): return "🏞️"
    if any(x in c for x in ("temple", "religious", "kovil", "church", "mosque")): return "🛕"
    if any(x in c for x in ("heritage", "historical", "archaeological", "fort", "museum")): return "🏛️"
    if any(x in c for x in ("wildlife", "national park", "bird")): return "🦜"
    if any(x in c for x in ("park", "forest", "garden")): return "🌳"
    return "📍"


try:
    data = load_data()
    geo = load_boundary()
    areas = load_areas()
    photo_map = load_photos()
except Exception as exc:
    st.error(str(exc))
    st.stop()

if "district_choice" not in st.session_state:
    st.session_state.district_choice = "All Sri Lanka"
if "requested_district" in st.session_state:
    st.session_state.district_choice = st.session_state.pop("requested_district")
    st.session_state.picker_view = st.session_state.district_choice

st.markdown('<div class="tm-hero"><h1>🌴 TravelMind · Explore Sri Lanka</h1><p>Discover places across the island, select a district on the map, and explore nearby mapped attractions.</p></div>', unsafe_allow_html=True)

all_districts = sorted(x for x in data.district.unique() if x and x != "Unknown")
choices = ["All Sri Lanka"] + all_districts
if st.session_state.district_choice not in choices:
    st.session_state.district_choice = "All Sri Lanka"

ctl1, ctl2, ctl3, ctl4 = st.columns([1.25, 1.15, 1.2, .8])
with ctl1:
    chosen = st.selectbox("Explore district", choices, index=choices.index(st.session_state.district_choice), key="picker_view")
    st.session_state.district_choice = chosen
with ctl2:
    cat_options = ["All interests"] + sorted(data.tourism_category.dropna().unique().tolist())
    category = st.selectbox("Attraction type", cat_options)
with ctl3:
    keyword = st.text_input("Find a place", placeholder="e.g. Sigiriya, Ella, Galle...")
with ctl4:
    display_unreviewed = st.checkbox("Include flagged records", value=False,
                                    help="All OSM records are provisional; this option also shows records flagged for review.")

view = data if chosen == "All Sri Lanka" else data[data.district.eq(chosen)]
if not display_unreviewed:
    view = view[~view.flagged]
if category != "All interests":
    view = view[view.tourism_category.eq(category)]
if keyword.strip():
    view = view[view.attraction_name.str.contains(keyword.strip(), regex=False, case=False, na=False)]

m1,m2,m3,m4 = st.columns(4)
m1.metric("Mapped places", f"{len(view):,}")
m2.metric("Districts", view.district.nunique())
m3.metric("Attraction categories", view.tourism_category.nunique())
m4.metric("Approved photo matches", sum(str(i) in photo_map for i in view.attraction_id))

left, right = st.columns([1.65, 1], gap="large")
with left:
    st.markdown('<div class="tm-title">🗺️ Explore the island</div>', unsafe_allow_html=True)
    st.caption("Click a district label on the map or use the district selector above. The map works without online basemap tiles.")
    district_center = data.groupby("district", as_index=False).agg(lat=("latitude", "median"), lon=("longitude", "median"), count=("attraction_id", "size"))
    f_map = folium.Map(location=[7.8731, 80.7718], zoom_start=7, tiles=None, control_scale=True, prefer_canvas=True)
    f_map.get_root().header.add_child(folium.Element("<style>.leaflet-container{background:#e8f1fa!important}</style>"))
    selected_district = chosen
    if geo and isinstance(geo.get("features"), list):
        for ft in geo["features"]:
            if not valid_geojson(ft):
                continue
            name = district_from_feature(ft)
            color = "#7ac6ad" if name == selected_district else "#d9eae1"
            folium.GeoJson(ft, style_function=lambda _f, fc=color: {"fillColor":fc, "fillOpacity":.77, "color":"#7c96a2", "weight":1},
                           highlight_function=lambda _f: {"fillColor":"#a5d6d8", "fillOpacity":.95, "weight":2, "color":"#176d92"},
                           tooltip=f"District: {escape(name)}" if name else "District boundary",
                           popup=folium.Popup(f"District: {escape(name)}", max_width=240) if name else None).add_to(f_map)
    for _, r in district_center.iterrows():
        if r.district not in all_districts: continue
        folium.CircleMarker([float(r.lat),float(r.lon)],radius=5 if chosen != r.district else 8,
                            color="#15628a",fill=True,fill_color="#1779a8",fill_opacity=.9,
                            tooltip=f"{r.district} · {int(r['count'])} candidate records",
                            popup=folium.Popup(f"District: {escape(r.district)}", max_width=250)).add_to(f_map)
    # Only draw a limited number of points for map performance; the table shows all matches.
    show_points = st.checkbox("Show attraction markers", value=(chosen != "All Sri Lanka"))
    max_markers = st.slider("Maximum markers", 50, 800, 200, 50) if show_points else 0
    if show_points:
        for _, r in view.head(max_markers).iterrows():
            folium.CircleMarker([float(r.latitude),float(r.longitude)],radius=3,color="#ee9961",
                                fill=True,fill_color="#e58c4e",fill_opacity=.85,
                                tooltip=escape(r.attraction_name),
                                popup=folium.Popup(f"{escape(r.attraction_name)} · {escape(r.district)}", max_width=280)).add_to(f_map)
    if chosen != "All Sri Lanka":
        subset = data[data.district.eq(chosen)]
        if not subset.empty:
            la,lb,lo,hi = subset.latitude.min(),subset.latitude.max(),subset.longitude.min(),subset.longitude.max()
            f_map.fit_bounds([[float(la),float(lo)],[float(lb),float(hi)]],padding=(25,25))
    map_output = st_folium(f_map, height=550, width=None, key="travelmind_island_map",
                           returned_objects=["last_object_clicked_popup"])
    clicked = (map_output or {}).get("last_object_clicked_popup")
    if isinstance(clicked,str):
        clean_clicked = re.sub(r"<[^>]+>", "", clicked).strip()
        if clean_clicked.startswith("District:"):
            district_name = clean_clicked.split(":",1)[1].strip()
            if district_name in all_districts and district_name != chosen:
                st.session_state.requested_district = district_name
                st.rerun()
    if chosen != "All Sri Lanka":
        if st.button("↩ Back to the whole island"):
            st.session_state.requested_district = "All Sri Lanka"
            st.rerun()

with right:
    st.markdown('<div class="tm-title">✨ Discover this area</div>', unsafe_allow_html=True)
    st.write(f"**{chosen}**" if chosen != "All Sri Lanka" else "**Island-wide exploration**")
    st.caption("These are OpenStreetMap-derived candidate places, not independently verified attractions or visitor rankings.")
    show_data = view.sort_values(["flagged", "attraction_name"]).drop_duplicates(["district", "attraction_name"]).head(12)
    if show_data.empty:
        st.info("No mapped places match these filters. Try another district or category.")
    else:
        for _, r in show_data.iterrows():
            with st.container(border=True):
                aa,bb = st.columns([.7,2.3])
                with aa:
                    photo = photo_map.get(str(r.attraction_id))
                    if photo:
                        st.image(str(photo["path"]), width="stretch")
                    else:
                        st.markdown(f"<div style='font-size:2rem;text-align:center;padding:12px'>{category_icon(r.tourism_category)}</div>",unsafe_allow_html=True)
                with bb:
                    st.markdown(f"**{r.attraction_name}**")
                    st.caption(f"{r.district} · {r.tourism_category}")
                    st.link_button("📍 Open location", google_link(r), use_container_width=True)
                if str(r.attraction_id) in photo_map:
                    p = photo_map[str(r.attraction_id)]
                    label = "Photo attribution: " + (p["creator"] or "Creator listed on source") + " · " + (p["license"] or "check license")
                    if p["source"].startswith("http"):
                        st.caption(f"{label} · [Wikimedia source]({p['source']})")
                    else:
                        st.caption(label)
    st.caption("Cards show a short sample. Use filters or download the full results below.")

st.divider()
near_tab, hotspot_tab, list_tab = st.tabs(["📍 Nearby exploration", "🌿 Attraction-rich areas", "📋 Full results"])
with near_tab:
    st.subheader("Find other places near an attraction")
    eligible = view.drop_duplicates(["district", "attraction_name"]).sort_values("attraction_name")
    if eligible.empty:
        st.info("Select a district or broaden your filters to find a starting point.")
    else:
        keyids = eligible.attraction_id.tolist()
        pretty_names = {str(r.attraction_id):f"{r.attraction_name} · {r.district}" for _,r in eligible.iterrows()}
        c1,c2 = st.columns([3,1])
        with c1:
            start_id = st.selectbox("Start at",keyids,format_func=lambda x:pretty_names.get(x,x))
        with c2:
            radius = st.select_slider("Search radius",options=[2,5,10,20],value=5,format_func=lambda x:f"{x} km")
        origin = eligible[eligible.attraction_id.eq(start_id)].iloc[0]
        # Proximity is searched island-wide rather than within district bounds.
        pool = data[~data.flagged] if not display_unreviewed else data
        out = pool[pool.attraction_id.ne(start_id)].copy()
        out["distance_km"] = out.apply(lambda r: format_distance(float(origin.latitude),float(origin.longitude),float(r.latitude),float(r.longitude)),axis=1)
        out = out[out.distance_km.le(radius)].sort_values("distance_km").drop_duplicates(["district","attraction_name"]).head(24)
        st.caption(f"{len(out)} nearby mapped candidates displayed within {radius} km (straight-line distance; not road travel time).")
        if out.empty: st.info("No other mapped places found. Try a larger radius.")
        for a in range(0,len(out),3):
            cols = st.columns(3)
            for col,(_,r) in zip(cols,out.iloc[a:a+3].iterrows()):
                with col:
                    with st.container(border=True):
                        st.markdown(f"### {category_icon(r.tourism_category)} {r.attraction_name}")
                        st.caption(f"{r.district} · {r.tourism_category}")
                        st.metric("Straight-line distance",f"{r.distance_km:.2f} km")
                        st.link_button("📍 Google Maps",google_link(r),use_container_width=True)
with hotspot_tab:
    st.subheader("Explore mapped attraction concentrations")
    st.caption("From island-wide DBSCAN research. These are candidate concentrations of OSM records—not verified hotspots, popularity measures or tourist demand.")
    if areas.empty:
        st.warning(f"No hotspot stability report found at {STABILITY}. Run analyze_hotspot_stability.py first.")
    else:
        stable = areas[areas.stable_geographic_candidate.astype(str).str.casefold().eq("true")].copy()
        if chosen != "All Sri Lanka":
            stable = stable[stable.main_district.eq(chosen)]
        stable = stable.sort_values("baseline_records",ascending=False)
        st.metric("Preliminary screening passes in view",len(stable))
        for _, r in stable.head(15).iterrows():
            with st.container(border=True):
                st.markdown(f"**{r.main_district} · Attraction-rich area**")
                st.caption(f"{int(r.baseline_records)} candidate records · {r.p90_radius_km:.1f} km 90th-percentile radius · {r.strict_retained_pct:.1f}% retained in strict experiment")
                st.caption(f"{r.review_flag_pct:.1f}% require review. Geographic screening only; tourism relevance not confirmed.")
                st.link_button("📍 Inspect area on Google Maps",f"https://www.google.com/maps?q={r.center_latitude},{r.center_longitude}")
with list_tab:
    cols = ["attraction_name","district","tourism_category","latitude","longitude","flagged"]
    st.dataframe(view[cols].rename(columns={"attraction_name":"Place","district":"District","tourism_category":"Category","flagged":"Review flagged"}),hide_index=True,width="stretch",height=450)
    st.download_button("Download filtered records",view[cols].to_csv(index=False).encode("utf-8"),file_name="travelmind_island_explorer.csv",mime="text/csv")

st.caption("TravelMind · Island-wide GIS prototype. Records are provisional and may contain incorrect categories, duplications, or coordinate errors. The 38 screened geographic concentrations require independent validation.")
