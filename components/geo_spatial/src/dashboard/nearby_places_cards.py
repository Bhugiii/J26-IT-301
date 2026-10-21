"""TravelMind: visual nearby-place cards for Streamlit.

Usage:
    from nearby_places_cards import render_nearby_places
    render_nearby_places(nearby_df)

Expected columns (aliases supported): attraction_name/place/name,
 district, tourism_category/category, distance_km/distance,
 latitude/lat, longitude/lon. Optional attraction_id.

All records remain labeled as OSM candidates; this does not verify sites.
"""
from html import escape
from urllib.parse import urlencode
import pandas as pd
import streamlit as st


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

    st.caption("Distances are straight-line estimates, not travel distance or time. Listings are unverified OpenStreetMap candidates.")
    view = df.head(max_cards)
    for start in range(0, len(view), 3):
        cols = st.columns(3, gap="medium")
        for col, (_, item) in zip(cols, view.iloc[start:start + 3].iterrows()):
            name = str(item[name_col])
            category = str(item[category_col]) if category_col else "Other"
            district = str(item[district_col]) if district_col else "Sri Lanka"
            dist = float(item["_distance"])
            icon = _icon_for(category)
            with col:
                with st.container(border=True):
                    st.markdown(f"### {icon} {name}")
                    st.caption(f"📍 {district} · {category}")
                    st.markdown(f"**{dist:.2f} km away** · straight line")
                    if lat_col and lon_col:
                        lat = pd.to_numeric(item[lat_col], errors="coerce")
                        lon = pd.to_numeric(item[lon_col], errors="coerce")
                        if pd.notna(lat) and pd.notna(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
                            url = "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": f"{lat:.7f},{lon:.7f}"})
                            st.link_button("📍 View on Google Maps", url, use_container_width=True)
                    st.caption("Unverified mapped place")
    if len(df) > max_cards:
        st.info(f"Showing {max_cards} of {len(df)} places. Narrow your categories to see more relevant results.")
