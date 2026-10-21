"""TravelMind | Tourism Intelligence 2.0
Copy to src/dashboard/app.py.
Run: python -m streamlit run src/dashboard/app.py --server.port 8501
Dependencies: streamlit pandas folium streamlit-folium
All analytics are from saved model outputs. No fake TPI or visitor counts.
"""
from pathlib import Path
from html import escape
from urllib.parse import urlencode
import json
import math
import re

import folium
import pandas as pd
import numpy as np
import streamlit as st
from streamlit_folium import st_folium
import streamlit.components.v1 as components
from tm_trip_features import render_my_trip, trip_button, build_place_description, describe_record
from tm_home_dashboard import render_home
from tm_theme import (inject_theme, render_sidebar_nav, render_sidebar_status,
                      render_page_header, render_quick_actions, source_badge)

st.set_page_config(page_title="TravelMind | Tourism Intelligence", page_icon="🌴", layout="wide", initial_sidebar_state="expanded")
ROOT = Path(__file__).resolve().parents[2]
RECORDS = ROOT / "data/processed/travelmind_combined_clusters.csv"
MODEL_CSV = ROOT / "results/reports/model_comparison.csv"
DISTRICTS_GEOJSON = ROOT / "data/boundaries/sri_lanka_districts.geojson"
IMAGE_MAP = ROOT / "config/attraction_image_final_review.csv"
IMAGE_DIR = ROOT / "assets/images/attractions"
SHORTLIST_FILE = ROOT / "results/reports/hotspot_stability_analysis/hotspot_quality_shortlist.csv"
CATALOG_FILE = ROOT / "data/processed/travelmind_enhanced_attraction_catalog.csv"
SERVICES_FILE = ROOT / "data/processed/overture_tourism/overture_tourist_services.csv"
INFRA_DIR = ROOT / "results/reports/infrastructure_clustering"
INFRA_GRID = INFRA_DIR / "tourism_infrastructure_clustered_grid.csv"
INFRA_PROFILES = INFRA_DIR / "tourism_infrastructure_cluster_profiles.csv"
INFRA_EVALUATION = INFRA_DIR / "tourism_infrastructure_k_evaluation.csv"

# Bright controls and high-contrast text even when Streamlit uses dark mode.
inject_theme()

@st.cache_data(show_spinner="Loading your clustering results...")
def load_data():
    if not RECORDS.exists():
        raise FileNotFoundError(f"Missing data file: {RECORDS}")
    d = pd.read_csv(RECORDS, low_memory=False)
    mandatory = ["attraction_id", "attraction_name", "district", "tourism_category", "latitude", "longitude", "kmeans_cluster", "dbscan_cluster"]
    missing = [c for c in mandatory if c not in d.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    for col in ["latitude", "longitude", "kmeans_cluster", "dbscan_cluster"]:
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d[d.latitude.between(5.5, 10.2) & d.longitude.between(79.3, 82.3)].copy()
    for col in ["attraction_id", "attraction_name", "district", "tourism_category"]:
        d[col] = d[col].fillna("").astype(str).str.strip()
    d = d[d.attraction_name.map(lambda t: len(t) > 2 and any(c.isalpha() for c in t) and not t.startswith("#"))].copy()
    d["district"] = d.district.replace("", "Unknown")
    d["tourism_category"] = d.tourism_category.replace("", "Other")
    d["flagged"] = d.get("review_required", pd.Series("no", index=d.index)).fillna("no").astype(str).str.lower().eq("yes")
    d["duplicate_flag"] = d.get("suspected_duplicate", pd.Series("no", index=d.index)).fillna("no").astype(str).str.lower().eq("yes")
    return d

@st.cache_data
def load_comparison():
    return pd.read_csv(MODEL_CSV) if MODEL_CSV.exists() else pd.DataFrame()

@st.cache_data
def load_boundary():
    return json.loads(DISTRICTS_GEOJSON.read_text(encoding="utf8")) if DISTRICTS_GEOJSON.exists() else None

@st.cache_data
def load_photos():
    if not IMAGE_MAP.exists(): return {}
    d = pd.read_csv(IMAGE_MAP, dtype=str).fillna("")
    required = {"attraction_id", "image_file", "final_image_decision"}
    if not required.issubset(d.columns):return {}
    d = d[d.final_image_decision.str.strip().str.lower().eq("approved")]
    result = {}
    for _, row in d.iterrows():
        fname = str(row.image_file)
        if fname == Path(fname).name and (IMAGE_DIR / fname).is_file():
            result.setdefault(row.attraction_id, row.to_dict())
    return result

try:
    data, comparison, boundaries, images = load_data(), load_comparison(), load_boundary(), load_photos()
except Exception as exc:
    st.error(f"Unable to load TravelMind data: {exc}")
    st.stop()

@st.cache_data(show_spinner=False)
def load_overture_candidates():
    if not CATALOG_FILE.exists():
        return pd.DataFrame()
    d = pd.read_csv(CATALOG_FILE, low_memory=False)
    required = {"catalog_id", "source", "place_name", "basic_category", "tourism_group", "latitude", "longitude", "screening_status", "category_name_review"}
    if not required.issubset(d.columns):
        st.warning("Enhanced attraction catalog has missing required columns.")
        return pd.DataFrame()
    d = d[d["source"].eq("overture") | d["source"].astype(str).str.contains("overture", case=False, na=False)].copy()
    d["latitude"] = pd.to_numeric(d["latitude"], errors="coerce")
    d["longitude"] = pd.to_numeric(d["longitude"], errors="coerce")
    d = d.dropna(subset=["latitude", "longitude"])
    d = d[d.latitude.between(5.5, 10.2) & d.longitude.between(79.3, 82.3)]
    return d


LOCATION_REVIEW_FILE = ROOT / "results/reports/overture_attraction_audit/major_destination_location_review.csv"

@st.cache_data(show_spinner=False)
def flagged_location_catalog_ids():
    """Known severe location mismatches in the manually scoped 107-row shortlist.

    This is NOT a full verification of the rest of the Overture catalog.
    """
    if not LOCATION_REVIEW_FILE.exists():
        return set()
    try:
        audit = pd.read_csv(LOCATION_REVIEW_FILE, low_memory=False)
        if not {"catalog_id", "review_priority"}.issubset(audit.columns):
            return set()
        return set(audit.loc[
            audit["review_priority"].eq("high_location_mismatch"), "catalog_id"
        ].dropna().astype(str))
    except (OSError, ValueError, pd.errors.ParserError):
        return set()


def screen_extra_attractions(candidates):
    """Conservative preview filter; never asserts verification."""
    if candidates.empty:
        return candidates
    frame = candidates.copy()
    conflict = frame["category_name_review"].fillna(False).astype(str).str.lower().isin(("true", "1", "yes"))
    # Records near original OSM points and matching names are held back
    # to reduce duplicates; others still remain provisional.
    eligible = frame["screening_status"].eq("candidate_unmatched_not_verified")
    known_mismatch = frame["catalog_id"].astype(str).isin(flagged_location_catalog_ids())
    plausible_name = frame["place_name"].fillna("").astype(str).str.strip().str.len().ge(3)
    return frame[~conflict & eligible & ~known_mismatch & plausible_name].copy()


@st.cache_data(show_spinner=False)
def load_tourism_services():
    if not SERVICES_FILE.exists():
        return pd.DataFrame()
    d = pd.read_csv(SERVICES_FILE, low_memory=False)
    required = {"overture_id", "place_name", "basic_category", "tourism_group", "latitude", "longitude"}
    if not required.issubset(d.columns):
        st.warning("Tourism service file has missing required columns.")
        return pd.DataFrame()
    for c in ("latitude", "longitude"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["latitude", "longitude"])
    d = d[d.latitude.between(5.5, 10.2) & d.longitude.between(79.3, 82.3)]
    return d


@st.cache_data(show_spinner=False)
def load_infra_results():
    result = []
    for p in (INFRA_GRID, INFRA_PROFILES, INFRA_EVALUATION):
        result.append(pd.read_csv(p, low_memory=False) if p.exists() else pd.DataFrame())
    return tuple(result)


def distances_km(frame, latitude, longitude):
    """Vectorized great-circle distance; distances are not road travel distances."""
    lat1, lon1 = np.radians(float(latitude)), np.radians(float(longitude))
    lat2 = np.radians(frame["latitude"].to_numpy(dtype=float))
    lon2 = np.radians(frame["longitude"].to_numpy(dtype=float))
    a = np.sin((lat2-lat1)/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin((lon2-lon1)/2)**2
    return 12742*np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def as_map_records(frame, *, id_col):
    """Adapt additional POI layers to the existing MapLibre dashboard interface."""
    out = frame.copy()
    out["attraction_id"] = out[id_col].astype(str)
    out["attraction_name"] = out["place_name"].fillna("Unnamed mapped place").astype(str)
    out["tourism_category"] = out["basic_category"].fillna("Other").astype(str)
    out["district"] = "Sri Lanka (district not assigned)"
    out["flagged"] = True
    out["source_label"] = "Overture (unverified)"
    return out


CATEGORY_COLORS = {"beach":"#16a0b3", "waterfall":"#238dc0", "nature":"#3c9b80", "forest":"#2d9377", "garden":"#42a27a", "temple":"#6b77b9", "heritage":"#d09b37", "fort":"#d09b37", "wildlife":"#4c9770", "mountain":"#548ba4"}
GROUP_COLORS = ["#1a6a9f", "#d89b32", "#3d9279", "#7c6cb2", "#c45d79", "#1e9eb0", "#c16c42", "#657aab"]

def color_for(r, mode):
    if mode == "Regional groups":
        return GROUP_COLORS[int(r.kmeans_cluster) % len(GROUP_COLORS)] if pd.notna(r.kmeans_cluster) else "#96a5b1"
    if mode == "Density groups":
        return "#adb6bf" if pd.isna(r.dbscan_cluster) or r.dbscan_cluster < 0 else GROUP_COLORS[int(r.dbscan_cluster) % len(GROUP_COLORS)]
    cat = str(r.tourism_category).lower()
    return next((val for term,val in CATEGORY_COLORS.items() if term in cat), "#267f9b")

def haversine_km(lat1, lon1, lat2, lon2):
    a1 = math.radians(float(lat1))
    a2 = math.radians(float(lat2))
    dlat = a2 - a1
    dlon = math.radians(float(lon2)-float(lon1))
    h = math.sin(dlat/2)**2 + math.cos(a1)*math.cos(a2)*math.sin(dlon/2)**2
    return 12742 * math.asin(min(1.0, math.sqrt(max(0.0, h))))

def display_image(record):
    meta = images.get(str(record.attraction_id))
    if meta:
        st.image(str(IMAGE_DIR / meta["image_file"]), width="stretch")
        name = str(meta.get("creator", "")).strip() or "Creator not listed"
        lic = str(meta.get("license", "")).strip() or "Check license"
        st.caption(f"Photo: {name} · {lic}")
        source = str(meta.get("source_page", ""))
        lic_url = str(meta.get("license_url", ""))
        if source.startswith("https://"):st.markdown(f"[Photo source]({source})")
        if lic_url.startswith("https://"):st.markdown(f"[License details]({lic_url})")
    else:
        st.info("📷 Exact-location photograph not yet approved.")

def destination_view(r, show_photo=True):
    if show_photo:display_image(r)
    st.markdown(f"**{r.attraction_name}**")
    st.caption(f"{r.district} · {r.tourism_category}")
    st.write(describe_record(r))
    st.markdown(f"[📍 Open location in Google Maps](https://www.google.com/maps?q={float(r.latitude):.6f},{float(r.longitude):.6f})")
    trip_button(unique_id=str(r.attraction_id), name=str(r.attraction_name),
                lat=r.latitude, lon=r.longitude, warning=True,
                key=f"selected_trip_{str(r.attraction_id)}")


# Responsive visual nearby-place cards (embedded; no extra Python file required).
def _column(df, *names):
    for name in names:
        if name in df.columns:
            return name
    return None


def _icon_for(category):
    s = str(category).lower()
    if any(w in s for w in ("beach", "coast", "marine", "surf")):
        return "🏖️"
    if any(w in s for w in ("temple", "religious", "shrine", "church", "mosque")):
        return "🛕"
    if any(w in s for w in ("waterfall", "falls")):
        return "💧"
    if any(w in s for w in ("mountain", "hill", "scenic", "viewpoint", "hiking")):
        return "⛰️"
    if any(w in s for w in ("park", "garden", "forest", "nature")):
        return "🌿"
    if any(w in s for w in ("museum", "heritage", "fort", "historical", "archaeological")):
        return "🏛️"
    if any(w in s for w in ("wildlife", "animal", "bird")):
        return "🦋"
    return "📍"


def render_nearby_places(nearby_df: pd.DataFrame, *, max_cards=18, key="nearby"):
    """Render existing GIS distance results as responsive tourist-friendly cards."""
    if nearby_df is None or nearby_df.empty:
        st.info("No mapped places found within this distance. Try a larger radius.")
        return

    df = nearby_df.copy()
    name_col = _column(df, "attraction_name", "place", "Place", "name", "Attraction")
    district_col = _column(df, "district", "District")
    category_col = _column(df, "tourism_category", "category", "Category")
    distance_col = _column(df, "distance_km", "distance", "Distance (km)")
    lat_col = _column(df, "latitude", "lat", "Latitude")
    lon_col = _column(df, "longitude", "lon", "lng", "Longitude")

    if not name_col or not distance_col:
        st.error("Nearby results need attraction_name/place and distance_km columns.")
        st.caption(f"Available columns: {', '.join(df.columns)}")
        return

    df["_distance"] = pd.to_numeric(df[distance_col], errors="coerce")
    df = df.dropna(subset=["_distance"])
    df = df[df["_distance"] >= 0].sort_values("_distance")
    if df.empty:
        st.info("No nearby places with valid distances were found.")
        return

    st.markdown("### 🧭 Places near your selected destination")
    m1, m2, m3 = st.columns(3)
    m1.metric("Mapped places nearby", f"{len(df):,}")
    m2.metric("Nearest place", f"{df['_distance'].min():.1f} km")
    categories = df[category_col].nunique() if category_col else 0
    m3.metric("Types of places", int(categories))

    controls = st.columns([2, 1])
    types = sorted(df[category_col].dropna().astype(str).unique()) if category_col else []
    with controls[0]:
        chosen = st.multiselect("Show categories", types, default=[], key=f"{key}_categories", placeholder="All categories")
    with controls[1]:
        order = st.selectbox("Sort by", ["Nearest first", "Name A–Z"], key=f"{key}_sort")
    if chosen and category_col:
        df = df[df[category_col].astype(str).isin(chosen)]
    if order == "Name A–Z":
        df = df.sort_values(name_col, key=lambda s: s.astype(str).str.casefold())

    st.caption("Distances are straight-line estimates, not travel distances. All mapped candidates are provisional; Overture preview records are not independently verified.")
    view = df.head(max_cards)
    for start in range(0, len(view), 3):
        cols = st.columns(3, gap="medium")
        for offset, (col, (_, item)) in enumerate(zip(cols, view.iloc[start:start + 3].iterrows())):
            name = str(item[name_col])
            category = str(item[category_col]) if category_col else "Other"
            district = str(item[district_col]) if district_col else "Sri Lanka"
            dist = float(item["_distance"])
            icon = _icon_for(category)
            with col:
                with st.container(border=True):
                    st.markdown(f"### {icon} {name}")
                    st.caption(f"📍 {district} · {category}")
                    st.caption(build_place_description(name, district, category, item.get("tourism_group", "")))
                    st.markdown(f"**{dist:.2f} km away** · straight line")
                    if lat_col and lon_col:
                        lat = pd.to_numeric(item[lat_col], errors="coerce")
                        lon = pd.to_numeric(item[lon_col], errors="coerce")
                        if pd.notna(lat) and pd.notna(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
                            url = "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": f"{lat:.7f},{lon:.7f}"})
                            st.link_button("📍 View on Google Maps", url, width="stretch")
                            trip_button(unique_id=str(item.get("attraction_id", f"nearby:{lat:.7f},{lon:.7f}")),
                                        name=name, lat=lat, lon=lon, key=f"nearby_trip_{key}_{start + offset}",
                                        warning=True)

    if len(df) > max_cards:
        st.info(f"Showing {max_cards} of {len(df)} places. Narrow your categories to see more relevant results.")


with st.sidebar:
    page = render_sidebar_nav()
    st.divider()
    st.caption("TravelMind · Sri Lanka")
    st.caption("GIS and ML insights are research outputs; mapped records require independent verification.")

# Only Component 02 pages show GIS controls; the main menu is shared across the group.
render_page_header(page)
search = st.session_state.get("tm_sidebar_search", "")
district = st.session_state.get("tm_sidebar_district", "All Districts")
category = st.session_state.get("tm_sidebar_category", "All tourism types")
show_flagged = st.session_state.get("tm_gis_show_flagged", False)
show_markers = st.session_state.get("tm_gis_show_markers", True)
show_hotspots = st.session_state.get("tm_gis_show_hotspots", True)
show_districts = st.session_state.get("tm_gis_show_districts", True)
color_mode = st.session_state.get("tm_gis_color_mode", "Tourism types")
max_markers = st.session_state.get("tm_gis_max_markers", 450)

if page in {"Dashboard", "Discover Places", "Hotspots", "Tourism Facilities", "Analytics"}:
    with st.expander("☷  Explore & Map Filters", expanded=False):
        st.caption("Search and district selection apply to the GIS explorer. Map settings control the research map layers.")
        find_tab, map_tab = st.tabs(["🔎 Find places", "🗺️ Map layers & advanced"])
        with find_tab:
            c_search, c_district, c_category = st.columns([2, 1, 1], gap="medium")
            with c_search:
                search = st.text_input("Search destinations", placeholder="e.g. Ella, Sigiriya, Galle Fort", key="tm_sidebar_search")
            with c_district:
                district_options = ["All Districts"] + sorted(x for x in data.district.unique() if x)
                district = st.selectbox("District", district_options, key="tm_sidebar_district")
            with c_category:
                category_options = ["All tourism types"] + sorted(data.tourism_category.unique().tolist())
                category = st.selectbox("Tourism type", category_options, key="tm_sidebar_category")
        with map_tab:
            a, b = st.columns(2)
            with a:
                show_markers = st.checkbox("Attraction markers", value=True, key="tm_gis_show_markers")
                show_hotspots = st.checkbox("Attraction concentration areas", value=True, key="tm_gis_show_hotspots")
                show_districts = st.checkbox("District boundaries", value=True, key="tm_gis_show_districts")
                show_flagged = st.checkbox("Include records flagged for review", value=False, key="tm_gis_show_flagged")
            with b:
                color_mode = st.radio("Color markers by", ["Tourism types", "Regional groups", "Density groups"],
                                      key="tm_gis_color_mode")
                max_markers = st.slider("Maximum markers", 100, 1500, 450, 50, key="tm_gis_max_markers")
        st.caption("Mapped records are OSM-derived candidates, not independently verified visitor destinations.")

filtered = data.copy()
if search.strip():
    matched_name = filtered.attraction_name.str.contains(search.strip(), case=False, regex=False, na=False)
    matched_district = filtered.district.str.contains(search.strip(), case=False, regex=False, na=False)
    filtered = filtered[matched_name | matched_district]
if district != "All Districts":filtered=filtered[filtered.district.eq(district)]
if category != "All tourism types":filtered=filtered[filtered.tourism_category.eq(category)]
if not show_flagged:filtered=filtered[~filtered.flagged]
clustered = filtered[filtered.dbscan_cluster.ge(0)]
cluster_sizes = clustered.groupby("dbscan_cluster").size().sort_values(ascending=False)
district_sizes = filtered.groupby("district").size().sort_values(ascending=False)

# Stable destination ordering and one representative card per same-name district.
destinations = filtered.copy()
destinations["photo_ok"] = destinations.attraction_id.isin(images.keys())
destinations = destinations.sort_values(["photo_ok", "duplicate_flag", "attraction_name"], ascending=[False, True, True])
destinations = destinations.drop_duplicates(["attraction_name", "district"])

# Research data sources remain internal; no technical data-layer status card.


@st.cache_data(show_spinner=False)
def geojson_cached():
    return boundaries

@st.cache_data(show_spinner=False)
def load_shortlist():
    if not SHORTLIST_FILE.is_file():
        return pd.DataFrame()
    return pd.read_csv(SHORTLIST_FILE, low_memory=False)


def maplibre_panel(points, *, height=560, center_record=None, nearby=None, nearby_radius_km=None, areas_visible=True, force_whole_island=False, show_legend=True, hide_map_panels=False):
    """MapLibre 3D view using the same research inputs and map engine as the standalone explorer."""
    if show_markers:
        map_points = points if len(points) <= max_markers else points.sample(n=max_markers, random_state=42)
    else:
        map_points = points.head(0)
    # Avoid overlapping standard (blue) markers with highlighted nearby (green) markers.
    nearby_ids = set(nearby.attraction_id.astype(str)) if nearby is not None and not nearby.empty else set()
    if nearby_ids:
        map_points = map_points[~map_points.attraction_id.astype(str).isin(nearby_ids)]
    # Only a selected attraction has an ID. Hotspot centres contain coordinates only.
    selected_attraction_id = getattr(center_record, "attraction_id", None)
    if selected_attraction_id is not None:
        map_points = map_points[~map_points.attraction_id.astype(str).eq(str(selected_attraction_id))]
    features = []
    for r in map_points.itertuples():
        features.append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": [float(r.longitude), float(r.latitude)]},
            "properties": {"id":str(r.attraction_id), "name":str(r.attraction_name)[:150],
                           "district":str(r.district), "category":str(r.tourism_category),
                           "review":bool(r.flagged), "approved_photo":str(r.attraction_id) in images,
                           "source_label":str(getattr(r, "source_label", "Original OSM candidate"))}
        })
    # Separate GeoJSON layers for clearly visible green nearby markers and a purple origin.
    nearby_features = []
    if nearby is not None and not nearby.empty:
        for r in nearby.head(75).itertuples():
            nearby_features.append({
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [float(r.longitude), float(r.latitude)]},
                "properties": {"id": str(r.attraction_id), "name": str(r.attraction_name)[:150],
                               "district": str(r.district), "category": str(r.tourism_category),
                               "distance_km": round(float(r.distance_km), 2),
                               "review": bool(r.flagged),
                                "source_label":str(getattr(r, "source_label", "Original OSM candidate"))}
            })
    origin_features = []
    # Purple origin marker is reserved for Discover Places, not hotspot centroids.
    if selected_attraction_id is not None:
        origin_features.append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": [float(center_record.longitude), float(center_record.latitude)]},
            "properties": {"name": str(center_record.attraction_name), "district": str(center_record.district)}
        })
    shortlist = load_shortlist()
    areas = []
    if areas_visible and show_hotspots and not shortlist.empty:
        needed = {"center_latitude","center_longitude","baseline_records","main_district"}
        if needed.issubset(shortlist.columns):
            for a in shortlist.to_dict("records"):
                try:
                    lat, lon = float(a["center_latitude"]), float(a["center_longitude"])
                    if not (5.5 <= lat <= 10.2 and 79.3 <= lon <= 82.3):
                        continue
                    if district != "All Districts" and str(a["main_district"]) != district:
                        continue
                    count = int(float(a["baseline_records"]))
                    spread = float(a.get("p90_radius_km",0) or 0)
                except (ValueError, TypeError):
                    continue
                areas.append({"type":"Feature", "geometry":{"type":"Point","coordinates":[lon,lat]},
                    "properties":{"name":str(a["main_district"]) + " attraction-rich area",
                                  "count":count,"radius":round(spread,2),
                                  "retention":str(a.get("strict_retained_pct","")),
                                  "review_flag":str(a.get("review_flag_pct",""))}})
    start = []
    if center_record is not None:
        start = [float(center_record.longitude),float(center_record.latitude)]
    elif not force_whole_island and district != "All Districts" and not points.empty:
        start = [float(points.longitude.median()),float(points.latitude.median())]
    boundary_payload = boundaries if show_districts and boundaries else {"type":"FeatureCollection","features":[]}
    page_html = (MAP_TEMPLATE.replace("__POINTS__",json.dumps({"type":"FeatureCollection","features":features},ensure_ascii=False))
        .replace("__AREAS__",json.dumps({"type":"FeatureCollection","features":areas},ensure_ascii=False))
        .replace("__NEARBY__",json.dumps({"type":"FeatureCollection","features":nearby_features},ensure_ascii=False))
        .replace("__ORIGIN__",json.dumps({"type":"FeatureCollection","features":origin_features},ensure_ascii=False))
        .replace("__NEARBY_RADIUS__",json.dumps(float(nearby_radius_km) if nearby_radius_km else None))
        .replace("__BOUNDARIES__",json.dumps(boundary_payload,ensure_ascii=False))
        .replace("__START__",json.dumps(start))
        .replace("__LEGEND_DISPLAY__", "none" if hide_map_panels else ("block" if show_legend else "none"))
        .replace("__INFO_DISPLAY__", "none" if hide_map_panels else "block"))
    components.html(page_html,height=height,scrolling=False)
    st.caption(f"{len(map_points):,} regular markers · {len(nearby_features):,} highlighted nearby places · {len(areas)} research-screened area centres. "
               "Map tiles and elevation require internet access. Candidate areas are not verified visitor hotspots.")

MAP_TEMPLATE = r'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@6.14.0/dist/maplibre-gl.css">
<style>
html,body{margin:0;height:100%;font-family:Inter,Arial,sans-serif;background:#e5eff5;color:#102b42}
#map{position:absolute;inset:0} #toolbar{position:absolute;z-index:5;left:12px;top:12px;display:flex;gap:8px;flex-wrap:wrap}
#toolbar button{background:white;border:1px solid #d5e1e9;border-radius:9px;padding:10px 13px;color:#133852;font-weight:700;cursor:pointer;box-shadow:0 2px 6px #102b4220}
#toolbar button.active{background:#2F6F55;color:white}
#info{display:__INFO_DISPLAY__;position:absolute;left:12px;bottom:24px;z-index:5;max-width:350px;background:#fffffff2;padding:14px 16px;border:1px solid #dbe4ed;border-radius:12px;box-shadow:0 3px 12px #0002;font-size:13px;line-height:1.55}
#info b{font-size:15px} #info small{color:#537085} #info a{color:#2F6F55;font-weight:700}
#legend{display:__LEGEND_DISPLAY__;position:absolute;top:115px;right:12px;z-index:6;background:#fffffff5;border:1px solid #d5e1e9;border-radius:10px;padding:10px 12px;font-size:12px;box-shadow:0 2px 10px #102b4220;line-height:1.8}
#legend .dot{display:inline-block;width:12px;height:12px;border:2px solid white;border-radius:50%;box-shadow:0 0 0 1px #657786;vertical-align:middle;margin-right:6px}
#terrainStatus{position:absolute;top:68px;left:12px;z-index:5;background:#ffffffd9;border-radius:6px;padding:6px 9px;font-size:12px;color:#48687a}
.maplibregl-popup-content{border-radius:10px;line-height:1.6;max-width:300px}
@media(max-width:640px){#toolbar button{padding:8px 9px}#info{max-width:250px}}
</style></head><body>
<div id="map"></div><div id="toolbar">
<button id="street" class="active">🗺️ Street</button><button id="satellite">🛰️ Satellite</button>
<button id="terrain">⛰️ 3D terrain: off</button><button id="reset">🇱🇰 Whole island</button>
</div><div id="terrainStatus">Terrain uses third-party elevation tiles; availability may vary.</div>
<div id="legend"><b>Map legend</b><div><span class="dot" style="background:#7c3aed"></span>Selected attraction</div><div><span class="dot" style="background:#17b759"></span>Nearby places</div><div><span class="dot" style="background:#166ba6"></span>Other mapped places</div><div><span class="dot" style="background:#ee941b"></span>Screened research areas</div></div>
<div id="info"><b>Explore the map</b><div>Click a mapped attraction, district polygon, or orange candidate-area marker.</div><small>Blue = mapped candidate · orange = research-screened area</small></div>
<script type="module">
import * as maplibregl from 'https://unpkg.com/maplibre-gl@6.14.0/dist/maplibre-gl.mjs';
const POINTS=__POINTS__, AREAS=__AREAS__, NEARBY=__NEARBY__, ORIGIN=__ORIGIN__, NEARBY_RADIUS=__NEARBY_RADIUS__, DISTRICTS=__BOUNDARIES__, START=__START__;
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
// Research areas render below the selected and nearby pins.
map.addSource('areas',{type:'geojson',data:AREAS});
map.addLayer({id:'areas-glow',type:'circle',source:'areas',paint:{'circle-color':'#f6a122','circle-opacity':0.17,'circle-radius':['interpolate',['linear'],['zoom'],6,12,12,35]}});
map.addLayer({id:'areas',type:'circle',source:'areas',paint:{'circle-color':'#ee941b','circle-radius':9,'circle-stroke-color':'#fff','circle-stroke-width':2}});
map.addSource('nearby',{type:'geojson',data:NEARBY});
map.addLayer({id:'nearby-halo',type:'circle',source:'nearby',paint:{'circle-color':'#17b759','circle-radius':['interpolate',['linear'],['zoom'],6,12,12,20],'circle-opacity':0.20}});
map.addLayer({id:'nearby-pins',type:'circle',source:'nearby',paint:{'circle-color':'#17b759','circle-radius':['interpolate',['linear'],['zoom'],6,7,12,10],'circle-stroke-color':'#ffffff','circle-stroke-width':2.5,'circle-opacity':1}});
map.addSource('origin',{type:'geojson',data:ORIGIN});
map.addLayer({id:'origin-halo',type:'circle',source:'origin',paint:{'circle-color':'#7c3aed','circle-radius':21,'circle-opacity':0.20}});
map.addLayer({id:'origin-pin',type:'circle',source:'origin',paint:{'circle-color':'#7c3aed','circle-radius':11,'circle-stroke-width':3,'circle-stroke-color':'#fff'}});
for(const layer of ['attractions','areas','district-fill','nearby-pins','origin-pin'])map.on('mouseenter' ,layer,()=>map.getCanvas().style.cursor='pointer');
for(const layer of ['attractions','areas','district-fill','nearby-pins','origin-pin'])map.on('mouseleave',layer,()=>map.getCanvas().style.cursor='');
map.on('click','attractions',e=>{const p=e.features[0].properties;const ll=e.features[0].geometry.coordinates;
const url='https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(ll[1]+','+ll[0]);
const html='<b>'+esc(p.name)+'</b><br>'+esc(p.district)+' · '+esc(p.category)+'<br>'+(p.approved_photo?'Photo-match approved for this record':'Record not independently verified')+'<br>'+esc(p.source_label||'Mapped candidate')+'<br><a href="'+url+'" target="_blank" rel="noopener noreferrer">Open Google Maps ↗</a>';
info.innerHTML=html;
new maplibregl.Popup({maxWidth:'310px'}).setLngLat(ll).setHTML(html).addTo(map);
});
map.on('click','nearby-pins',e=>{const f=e.features[0], p=f.properties,ll=f.geometry.coordinates;
const url='https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(ll[1]+','+ll[0]);
const html='<b>🟢 Nearby: '+esc(p.name)+'</b><br>'+esc(p.district)+' · '+esc(p.category)+'<br><strong>'+esc(p.distance_km)+' km (straight-line)</strong><br><small>Mapped candidate; tourism relevance not verified.</small><br><a href="'+url+'" target="_blank" rel="noopener noreferrer">Open Google Maps ↗</a>';
info.innerHTML=html;new maplibregl.Popup({maxWidth:'310px'}).setLngLat(ll).setHTML(html).addTo(map);
});
map.on('click','origin-pin',e=>{const p=e.features[0].properties,ll=e.features[0].geometry.coordinates;
const html='<b>🟣 Starting place: '+esc(p.name)+'</b><br>'+esc(p.district);
info.innerHTML=html;new maplibregl.Popup({maxWidth:'310px'}).setLngLat(ll).setHTML(html).addTo(map);
});
map.on('click','areas',e=>{const p=e.features[0].properties;const ll=e.features[0].geometry.coordinates;
info.innerHTML='<b>'+esc(p.name)+'</b><div>'+esc(p.count)+' mapped candidate records · p90 spread '+esc(p.radius)+' km</div><small>Research screened; not a verified tourism hotspot.</small>';
map.flyTo({center:ll,zoom:10,pitch:terrainOn?55:20,duration:900});});
map.on('click','district-fill',e=>{const p=e.features[0].properties;info.innerHTML='<b>'+esc(districtLabel(p))+'</b><div>District selected on map. Use Explore & Map Filters to select a district.</div>';});
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
map.on('style.load',()=>{attach();if(terrainOn)enableTerrain();
if(START && START.length===2){
 if(NEARBY_RADIUS){const lat=START[1],lon=START[0],deltaLat=NEARBY_RADIUS/111.0,deltaLon=NEARBY_RADIUS/(111.0*Math.max(0.2,Math.cos(lat*Math.PI/180)));
 map.fitBounds([[lon-deltaLon*1.35,lat-deltaLat*1.35],[lon+deltaLon*1.35,lat+deltaLat*1.35]],{padding:45,maxZoom:13,duration:850});
 }else{map.flyTo({center:START,zoom:10,duration:900});}
}});
map.on('error',e=>{const msg=String(e.error?.message||'map tiles unavailable');document.getElementById('terrainStatus').textContent='Some online map tiles may be unavailable: '+msg.slice(0,95);});
document.getElementById('street').onclick=()=>setMode('street');
document.getElementById('satellite').onclick=()=>setMode('satellite');
document.getElementById('terrain').onclick=()=>{if(terrainOn){map.setTerrain(null);terrainOn=false;map.easeTo({pitch:0,duration:600});document.getElementById('terrain').textContent='⛰️ 3D terrain: off';document.getElementById('terrainStatus').textContent='3D terrain off';}else enableTerrain();setActive();};
document.getElementById('reset').onclick=()=>{map.flyTo({center:[80.77,7.86],zoom:7,pitch:0,bearing:0,duration:1200});};
</script></body></html>'''

def make_map(points, focus=None, nearby=None):
    m = folium.Map(location=[7.85,80.75], zoom_start=8, tiles=None, prefer_canvas=True, control_scale=False)
    m.get_root().header.add_child(folium.Element("<style>.leaflet-container{background:#e7f1f7!important}</style>"))
    if boundaries:
        folium.GeoJson(boundaries, name="Sri Lanka districts", style_function=lambda x: {
            "color":"#53859e", "weight": 1 if show_districts else .55,
            "fillColor":"#e3eee9", "fillOpacity":.85
        }).add_to(m)
    if show_hotspots and not clustered.empty:
        for cluster_id, count in cluster_sizes.head(25).items():
            group = clustered[clustered.dbscan_cluster.eq(cluster_id)]
            lat,lon=group.latitude.median(),group.longitude.median()
            folium.CircleMarker([lat,lon], radius=min(21,5+math.sqrt(count)*.45),
                color="#e3a13f", weight=2, fill=True, fill_color="#f7c977", fill_opacity=.18,
                tooltip=f"Area with {count} mapped candidate records (not a visitor count)").add_to(m)
    if show_markers:
        # Evenly sample across the filtered dataset to avoid drawing only early CSV rows.
        selected = points if len(points)<=max_markers else points.sample(n=max_markers,random_state=42)
        for r in selected.itertuples():
            nm,di,ca=escape(str(r.attraction_name)),escape(str(r.district)),escape(str(r.tourism_category))
            loc=f"https://www.google.com/maps?q={r.latitude:.6f},{r.longitude:.6f}"
            content=f'<b>{nm}</b><br>{di} · {ca}<br><a href="{loc}" target="_blank" rel="noopener">Open location</a><br><small>Unverified OSM candidate</small>'
            col=color_for(r,color_mode)
            folium.CircleMarker([r.latitude,r.longitude],radius=4.5,color=col,weight=1,fill=True,fill_color=col,
                fill_opacity=.82,tooltip=nm,popup=folium.Popup(content,max_width=290)).add_to(m)
    if nearby is not None and not nearby.empty:
        for r in nearby.head(25).itertuples():
            folium.CircleMarker([r.latitude,r.longitude],radius=7,color="#1e8970",weight=2,fill=True,fill_color="#65ceb1",fill_opacity=.95,
                                tooltip=f"Nearby: {r.attraction_name}").add_to(m)
    if focus is not None:
        folium.Marker([float(focus.latitude),float(focus.longitude)],icon=folium.Icon(color="red",icon="star"),tooltip=str(focus.attraction_name)).add_to(m)
        m.fit_bounds([[float(focus.latitude)-.12,float(focus.longitude)-.14],[float(focus.latitude)+.12,float(focus.longitude)+.14]])
    elif district!="All Districts" and not points.empty:
        m.fit_bounds([[float(points.latitude.min())-.09,float(points.longitude.min())-.09],[float(points.latitude.max())+.09,float(points.longitude.max())+.09]])
    else:m.fit_bounds([[5.75,79.55],[9.95,82.05]])
    return m

def map_panel(height=545,focus=None,nearby=None):
    maplibre_panel(filtered,height=height,center_record=focus,nearby=nearby,areas_visible=False,show_legend=False)
    st.caption(f"Up to {min(max_markers,len(filtered)):,} filtered mapped attraction markers. Locations are provisional OSM-derived candidates.")

if page == "Dashboard":
    render_home(
        data=data, filtered=filtered, images=images, image_dir=IMAGE_DIR,
        shortlist=load_shortlist(), maplibre_panel=maplibre_panel,
        destination_view=destination_view, describe_record=describe_record,
    )

elif page == "Discover Places":
    st.markdown("### ✨ Find attractions you'll enjoy")
    st.caption("Choose a place, explore nearby mapped locations, and open navigation links. No itinerary or visitor-popularity predictions.")
    if destinations.empty:st.info("Try changing your Explore & Map Filters.")
    else:
        c1,c2=st.columns([4,6],gap="medium")
        with c1:
            options=destinations.assign(label=lambda d:d.attraction_name+" — "+d.district)
            destid=st.selectbox("Start exploring from",options.attraction_id.tolist(),format_func=lambda a:options.loc[options.attraction_id.eq(a),'label'].iloc[0])
            center=options.loc[options.attraction_id.eq(destid)].iloc[0]
            radius=st.select_slider("Nearby radius (straight line)",options=[2,5,10,20],value=5,format_func=lambda n:f"{n} km")
            with st.container(border=True):destination_view(center)
        include_overture_nearby = st.checkbox(
            "Include extra mapped attractions (unreviewed preview)", value=False,
            key="discovery_extra_overture",
            help="Research preview only. Excludes known severe location mismatches, category conflicts and matching-name duplicates; remaining locations are not verified.",
        )
        nearby=data[data.attraction_id.ne(center.attraction_id)].copy()
        if not show_flagged:nearby=nearby[~nearby.flagged]
        # This nearby search is NOT restricted by district, so border areas still work.
        nearby['distance_km']=nearby.apply(lambda r:haversine_km(center.latitude,center.longitude,r.latitude,r.longitude),axis=1)
        nearby=nearby[nearby.distance_km.le(radius)].sort_values('distance_km')
        nearby["source_label"] = "Original OSM candidate"
        if include_overture_nearby:
            extra = screen_extra_attractions(load_overture_candidates())
            if not extra.empty:
                extra["distance_km"] = distances_km(extra, center.latitude, center.longitude)
                extra = extra[extra.distance_km.le(radius)]
                extra = as_map_records(extra, id_col="catalog_id")
                nearby = pd.concat([nearby, extra], ignore_index=True, sort=False)
            st.warning("Additional mapped attractions are unreviewed research candidates. Check the destination name and location independently before travel.")
        # Deduplicate only obvious name + close-coordinate collisions in preview;
        # avoid discarding distinct sites sharing a common name across districts.
        nearby["_name_key"] = nearby.attraction_name.fillna("").str.casefold().str.strip()
        nearby["_lat_bucket"] = (pd.to_numeric(nearby.latitude, errors="coerce") * 1000).round().astype("Int64")
        nearby["_lon_bucket"] = (pd.to_numeric(nearby.longitude, errors="coerce") * 1000).round().astype("Int64")
        nearby = (nearby.sort_values(["distance_km", "source_label"], kind="stable")
                 .drop_duplicates(["_name_key", "_lat_bucket", "_lon_bucket"])
                 .head(30).drop(columns=["_name_key", "_lat_bucket", "_lon_bucket"]))
        with c2:
            st.markdown(f"**{len(nearby)} nearby mapped destinations within {radius} km**")
            st.caption("🟣 Purple = your selected attraction  ·  🟢 Green = nearby places  ·  🔵 Blue = other mapped records")
            maplibre_panel(filtered,height=450,center_record=center,nearby=nearby,nearby_radius_km=radius, hide_map_panels=True)
        if nearby.empty:st.info("No other mapped places found in this radius.")
        else:
            render_nearby_places(nearby, max_cards=18, key="travelmind_nearby")

elif page == "Hotspots":
    st.markdown("### ✨ Explore attraction-rich areas")
    st.caption("Discover places grouped by geography. These are OpenStreetMap-derived candidate attractions, not verified popular destinations.")
    area_data = load_shortlist()
    if area_data.empty:
        st.warning("Your research shortlist is missing. Check hotspot_quality_shortlist.csv.")
        st.code(str(SHORTLIST_FILE))
    else:
        required = {"baseline_cluster_id", "main_district", "center_latitude", "center_longitude", "baseline_records"}
        if not required.issubset(area_data.columns):
            st.error(f"The shortlist is missing: {sorted(required-set(area_data.columns))}")
        else:
            area_data = area_data.copy()
            for field in ("baseline_cluster_id", "baseline_records", "center_latitude", "center_longitude",
                          "strict_retained_pct", "p90_radius_km", "review_flag_pct"):
                if field in area_data.columns:
                    area_data[field] = pd.to_numeric(area_data[field], errors="coerce")
            area_data = area_data.dropna(subset=["baseline_cluster_id", "center_latitude", "center_longitude", "baseline_records"])
            area_data["baseline_cluster_id"] = area_data["baseline_cluster_id"].astype(int)
            if district != "All Districts":
                area_data = area_data[area_data.main_district.astype(str).eq(district)]
            area_data = area_data.sort_values(["main_district", "baseline_cluster_id"]).copy()
            if not area_data.empty:
                st.caption(f"{len(area_data)} screened candidate areas match your district selection.")
            if area_data.empty:
                st.info("No research-shortlisted attraction-rich area is available for this district. You can still explore mapped places here.")
                # Fallback is ordinary OSM-derived places, NOT a new or inferred hotspot.
                if district == "All Districts":
                    st.caption("No shortlisted research areas are available. Check the saved shortlist file.")
                else:
                    # Reuse the same experience as shortlisted areas, but do not call
                    # these ordinary district records a hotspot or an ML cluster.
                    ordinary = data.loc[data.district.eq(district)].copy()
                    if not show_flagged:
                        ordinary = ordinary.loc[~ordinary.flagged]
                    ordinary = ordinary.sort_values(["attraction_name", "attraction_id"]).drop_duplicates(
                        ["attraction_name", "district"]
                    )
                    st.markdown(f"#### Explore mapped places in {escape(str(district))}")
                    st.caption("These are ordinary mapped candidates in this district, not shortlisted hotspot areas.")
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Mapped places in district", len(ordinary))
                    k2.metric("Currently viewable", len(ordinary))
                    k3.metric("Place categories", ordinary.tourism_category.nunique())
                    cats = sorted(ordinary.tourism_category.dropna().astype(str).unique().tolist())
                    fc1, fc2 = st.columns([2, 1])
                    with fc1:
                        type_choice = st.selectbox("Explore by type", ["All categories"] + cats,
                                                   key="district_fallback_category")
                    with fc2:
                        name_query = st.text_input("Find a place in this area", placeholder="Type attraction name...",
                                                   key="district_fallback_search")
                    shown_members = ordinary
                    if type_choice != "All categories":
                        shown_members = shown_members[shown_members.tourism_category.eq(type_choice)]
                    if name_query.strip():
                        shown_members = shown_members[
                            shown_members.attraction_name.str.contains(name_query.strip(), case=False, regex=False, na=False)
                        ]
                    if search.strip():
                        shown_members = shown_members[
                            shown_members.attraction_name.str.contains(search.strip(), case=False, regex=False, na=False)
                        ]
                    if category != "All tourism types":
                        shown_members = shown_members[shown_members.tourism_category.eq(category)]
                    shown_members = shown_members.sort_values(["attraction_name", "attraction_id"])
                    st.caption(f"{len(shown_members)} matching mapped records in the selected district.")
                    if shown_members.empty:
                        st.info("No matching mapped places. Clear the place searches, change tourism type, or include review-flagged records.")
                    else:
                        place_lookup = shown_members.set_index("attraction_id", drop=False)
                        selected_id = st.selectbox(
                            "Highlight a place on the map", shown_members.attraction_id.tolist(),
                            format_func=lambda aid: f"{place_lookup.loc[aid, 'attraction_name']} · {place_lookup.loc[aid, 'tourism_category']}",
                            key=f"district_fallback_place_{district}"
                        )
                        selected_place = place_lookup.loc[selected_id]
                        map_col, details_col = st.columns([7, 3], gap="medium")
                        with map_col:
                            st.markdown("**🗺️ Explore on the 3D map**")
                            maplibre_panel(shown_members, height=520, center_record=selected_place,
                                           areas_visible=False, show_legend=False)
                            st.caption("Purple marker = selected place; blue = other candidate places. Locations require confirmation.")
                        with details_col:
                            with st.container(border=True):
                                st.markdown("**📍 Selected destination**")
                                destination_view(selected_place)

            else:
                id_options = area_data.baseline_cluster_id.tolist()
                area_lookup = area_data.set_index("baseline_cluster_id", drop=False)
                choice = st.selectbox(
                    "Choose an area to explore", id_options,
                    format_func=lambda cid: f"{area_lookup.loc[cid, 'main_district']} · attraction-rich area {cid}",
                    key="tourist_hotspot_area"
                )
                area = area_lookup.loc[choice]
                cluster_members = data[data.dbscan_cluster.eq(choice)].copy()
                display_members = cluster_members if show_flagged else cluster_members[~cluster_members.flagged].copy()
                display_members = display_members.copy()
                total_area_records = len(cluster_members)
                st.markdown(f"#### Explore mapped places in {escape(str(area.main_district))}")
                st.write("Select a mapped place below to highlight it on the 3D map. Open Google Maps to plan how to reach its coordinates.")
                k1, k2, k3 = st.columns(3)
                k1.metric("Mapped records in area", total_area_records)
                k2.metric("Currently viewable", len(display_members))
                k3.metric("Place categories", int(display_members.tourism_category.nunique()))
                st.caption("The first number represents original DBSCAN membership; 'Currently viewable' may exclude records flagged for review.")
                cats = sorted(display_members.tourism_category.dropna().astype(str).unique().tolist())
                fc1, fc2 = st.columns([2, 1])
                with fc1:
                    type_choice = st.selectbox("Explore by type", ["All categories"] + cats, key="hotspot_tourist_category")
                with fc2:
                    name_query = st.text_input("Find a place in this area", placeholder="Type attraction name...", key="hotspot_tourist_search")
                shown_members = display_members
                if type_choice != "All categories":
                    shown_members = shown_members[shown_members.tourism_category.eq(type_choice)]
                if name_query.strip():
                    shown_members = shown_members[shown_members.attraction_name.str.contains(name_query.strip(), case=False, regex=False, na=False)]
                shown_members = shown_members.sort_values(["attraction_name", "attraction_id"]).copy()
                st.caption(f"{len(shown_members)} matching mapped records in the selected cluster.")
                # Keep the map selection and cards tied to the actual baseline DBSCAN cluster IDs.
                if not shown_members.empty:
                    place_lookup = shown_members.set_index("attraction_id", drop=False)
                    selected_id = st.selectbox(
                        "Highlight a place on the map",
                        shown_members.attraction_id.astype(str).tolist(),
                        format_func=lambda aid: f"{place_lookup.loc[aid, 'attraction_name']} · {place_lookup.loc[aid, 'tourism_category']}",
                        key=f"hotspot_place_{choice}"
                    )
                    selected_place = place_lookup.loc[selected_id]
                    left, right = st.columns([7, 3], gap="medium")
                    with left:
                        st.markdown("**🗺️ Explore on the 3D map**")
                        # The selected record has an attraction_id, so the MapLibre panel
                        # draws it as a distinct purple pin, without changing Discover Places.
                        maplibre_panel(
                            shown_members, height=520, center_record=selected_place,
                            areas_visible=False, show_legend=False
                        )
                        st.caption("Purple marker = your selected place; blue markers = other places matching the area filters. Click a marker for details.")
                    with right:
                        with st.container(border=True):
                            st.markdown("**📍 Selected destination**")
                            destination_view(selected_place, show_photo=True)
                            st.caption("Mapped place, not independently verified. Check access and opening hours before travel.")
                    st.download_button("Download matching area records (CSV)", shown_members.to_csv(index=False).encode("utf-8"),
                                       file_name=f"travelmind_area_{choice}_places.csv", mime="text/csv", key="hotspot_download")
                else:
                    st.info("No places match those filters. Try All categories, remove the search term, or include review-flagged records in the sidebar.")

elif page == "Tourism Facilities":
    st.markdown("### 🏨 Stay, Eat & Travel Services")
    st.caption("Find Overture-mapped accommodation, food and drink, and travel-support services near a destination. Listings, opening status, and coordinates are not independently verified.")
    services = load_tourism_services()
    if services.empty:
        st.warning(f"The tourism service dataset is missing or invalid: {SERVICES_FILE}")
    elif destinations.empty:
        st.info("No starting destinations match the current GIS filters. Try changing the district or category.")
    else:
        left, right = st.columns([3, 2], gap="medium")
        with left:
            start_places = destinations.head(3000)
            lookup = start_places.set_index("attraction_id", drop=False)
            selected_id = st.selectbox("Start from an existing attraction", start_places.attraction_id.astype(str).tolist(),
                format_func=lambda aid: f"{lookup.loc[aid, 'attraction_name']} — {lookup.loc[aid, 'district']}", key="facility_destination")
            origin = lookup.loc[selected_id]
        with right:
            radius = st.select_slider("Facility search radius (straight line)", options=[2, 5, 10, 20], value=5, key="facility_radius")
        kinds = sorted(services.tourism_group.dropna().astype(str).unique())
        selected_kinds = st.multiselect("Facility types", kinds, default=kinds, key="facility_types")
        subset = services[services.tourism_group.isin(selected_kinds)].copy()
        subset["distance_km"] = distances_km(subset, origin.latitude, origin.longitude)
        subset = subset[subset.distance_km.le(radius)].sort_values("distance_km")
        a, b, c = st.columns(3)
        a.metric("Mapped nearby facilities", f"{len(subset):,}")
        b.metric("Accommodation", f"{int(subset.tourism_group.eq('accommodation').sum()):,}")
        c.metric("Food and drink", f"{int(subset.tourism_group.eq('food_and_drink').sum()):,}")
        st.caption("Purple = selected original attraction; green = mapped nearby facilities. Distances are straight-line estimates, not road routes.")
        nearby_map = as_map_records(subset.head(75), id_col="overture_id")
        origin_labelled = origin.copy()
        origin_labelled["source_label"] = "Original OSM candidate"
        # Empty regular layer keeps facilities distinct from the normal Dashboard layer.
        maplibre_panel(data.iloc[0:0], height=500, center_record=origin_labelled,
                       nearby=nearby_map, nearby_radius_km=radius, areas_visible=False)
        if subset.empty:
            st.info("No services in the selected groups and radius. Try 10 or 20 km.")
        else:
            st.markdown("#### Nearby facilities")
            for _, r in subset.head(24).iterrows():
                with st.container(border=True):
                    a, b = st.columns([4, 1])
                    with a:
                        st.markdown(f"**{escape(str(r.place_name))}**")
                        st.caption(f"{r.tourism_group} · {r.basic_category} · {r.distance_km:.2f} km straight line · Overture candidate")
                    with b:
                        link = "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": f"{r.latitude:.7f},{r.longitude:.7f}"})
                        st.link_button("📍 Map", link, width="stretch")
                        trip_button(unique_id=f"service:{r.overture_id}", name=str(r.place_name),
                                    lat=r.latitude, lon=r.longitude, kind='service', warning=True,
                                    key=f"service_trip_{r.overture_id}")
            if len(subset)>24:
                st.caption(f"Showing 24 of {len(subset)} matching facilities.")
            st.download_button("Download nearby facilities (CSV)", subset.to_csv(index=False).encode("utf-8"),
                               file_name="travelmind_nearby_tourism_facilities.csv", mime="text/csv")

elif page == "My Trip":
    render_my_trip()

elif page == "Analytics":
    st.markdown("### 📈 Machine-learning research results")
    if comparison.empty:st.warning("Missing results/reports/model_comparison.csv")
    else:
        st.dataframe(comparison,hide_index=True,width="stretch")
        a,b=st.columns(2)
        with a:
            st.markdown("**Silhouette score — higher is better**")
            st.bar_chart(comparison.set_index('model')['silhouette_score'])
        with b:
            st.markdown("**Davies–Bouldin index — lower is better**")
            st.bar_chart(comparison.set_index('model')['davies_bouldin_index'])
    st.warning("K-Means and DBSCAN have different cluster counts and coverage; DBSCAN evaluation excluded noise records. Direct numerical comparison needs care.")
    a,b=st.columns(2)
    with a:
        st.markdown("**K-Means cluster distribution**")
        st.bar_chart(data.kmeans_cluster.value_counts().sort_index())
    with b:
        st.markdown("**DBSCAN: grouped vs noise**")
        counts=pd.Series({'Assigned to group':int(data.dbscan_cluster.ge(0).sum()),'Noise':int(data.dbscan_cluster.eq(-1).sum())})
        st.bar_chart(counts)
    st.markdown("**Data quality summary**")
    c1,c2,c3=st.columns(3)
    c1.metric('Records in research dataset',f'{len(data):,}')
    c2.metric('Flagged for review',f'{int(data.flagged.sum()):,}')
    c3.metric('Suspected duplicates',f'{int(data.duplicate_flag.sum()):,}')
    st.caption("All records are provisional/unverified until independently checked; even unflagged records are not guaranteed true attractions.")

    st.divider()
    st.markdown("### 🧠 Tourism Infrastructure K-Means (separate experiment)")
    grid_results, profiles, k_results = load_infra_results()
    if grid_results.empty or profiles.empty or k_results.empty:
        st.info(f"Infrastructure clustering results are not yet available in {INFRA_DIR}.")
    else:
        st.caption("5 km grid cells · Overture-mapped attraction and tourism-service counts · Not visitor numbers or AHP tourism potential.")
        cols = st.columns(3)
        cols[0].metric("Sri Lanka grid cells", f"{len(grid_results):,}")
        assigned = pd.to_numeric(grid_results.get("infrastructure_cluster", pd.Series(dtype=float)), errors="coerce")
        cols[1].metric("Model-classified cells", f"{int(assigned.notna().sum()):,}")
        cols[2].metric("Unclassified cells", f"{int(assigned.isna().sum()):,}")
        st.markdown("**K-value evaluation (do not compare directly with coordinate-only models)**")
        st.dataframe(k_results, hide_index=True, width="stretch")
        st.markdown("**Infrastructure cluster profiles — observed mean mapped counts per cell**")
        st.dataframe(profiles, hide_index=True, width="stretch")
        st.info("The selected K=2 model primarily separates higher-count and lower-count mapped infrastructure areas. The 1,137 unclassified cells include 1,015 empty cells and 122 excluded coastal slivers; some coastal cells have substantial POI counts. This is not a validated tourism-popularity or development-potential classification.")
        available = [c for c in ("grid_id", "infrastructure_cluster", "attraction_count", "service_count", "center_latitude", "center_longitude", "boundary_overlap_fraction") if c in grid_results.columns]
        st.markdown("**Inspect mapped infrastructure cells**")
        view = grid_results[available].copy()
        if "service_count" in view.columns:
            view = view.sort_values("service_count", ascending=False)
        st.dataframe(view.head(100), hide_index=True, width="stretch")
        st.download_button("Download infrastructure grid with cluster labels", grid_results.to_csv(index=False).encode("utf-8"),
                           file_name="travelmind_infrastructure_clustered_grid.csv", mime="text/csv")


elif page in {
    "Recommendations", "Saved Places", "Traveller Profile", "Itinerary Planner", "Account",
    "Crowd Prediction", "Weather Intelligence", "Traveller Segments", "Expectation–Reality",
}:
    with st.container(border=True):
        st.info("Integration-ready placeholder — this group component is not connected yet.")
        st.write("The unified menu is ready for integration. This page does not simulate results or claim that its model is running.")
        if page in ("Saved Places", "Itinerary Planner"):
            if st.button("Open the existing My Trip feature", key=f"goto_my_trip_{page}"):
                st.session_state["travelmind_page"] = "My Trip"
                st.rerun()

st.divider()
st.caption("TravelMind · Sri Lanka geospatial tourism research prototype · OSM and optional Overture candidate records · No fabricated tourist demand, AHP scores, or destination ratings.")