"""Photo-first TravelMind home dashboard. Uses ONLY locally approved images."""
from pathlib import Path
import base64
from html import escape
from types import SimpleNamespace
from PIL import Image, ImageOps
import streamlit as st
import pandas as pd

GROUPS = {
    "All places": (),
    "🏖️ Beaches": ("beach", "coast", "bay", "surf", "marine"),
    "🏛️ Heritage": ("fort", "heritage", "historic", "ruin", "archaeolog", "museum", "monument", "palace"),
    "🌿 Nature": ("nature", "waterfall", "forest", "mountain", "hill", "garden", "wildlife", "park", "lake", "rock", "viewpoint"),
    "🛕 Religious": ("temple", "church", "mosque", "kovil", "shrine", "vihara", "religious", "stupa"),
    "🎡 Recreation": ("recreation", "adventure", "leisure", "zoo", "aquarium", "activity", "entertainment"),
}
REGIONS = {
    "Whole island": (),
    "Hill Country": ("Kandy", "Nuwara Eliya", "Badulla", "Ratnapura"),
    "South Coast": ("Galle", "Matara", "Hambantota"),
    "Cultural Triangle": ("Anuradhapura", "Polonnaruwa", "Matale"),
    "North": ("Jaffna", "Kilinochchi", "Mullaitivu", "Mannar", "Vavuniya"),
    "East": ("Trincomalee", "Batticaloa", "Ampara"),
    "West Coast": ("Colombo", "Gampaha", "Puttalam", "Kalutara"),
}


@st.cache_data(show_spinner=False)
def _banner_base64(path: str, modified_ns: int) -> str:
    """Cache the local, user-supplied hero photo for reliable Streamlit rendering."""
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


@st.cache_data(show_spinner=False)
def _card_photo(path: str, modified_ns: int):
    """Create a uniform 16:10 cover crop without changing the original file."""
    with Image.open(path) as source:
        oriented = ImageOps.exif_transpose(source)
        return ImageOps.fit(
            oriented.convert("RGB"),
            (960, 600),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )


def _go(page, *, name="", district="", category=""):
    st.session_state["travelmind_page"] = page
    st.session_state["tm_sidebar_search"] = name
    st.session_state["tm_sidebar_district"] = district or "All Districts"
    st.session_state["tm_sidebar_category"] = category or "All tourism types"


def _filter_group(df, selected):
    words = GROUPS.get(selected, ())
    if not words:
        return df
    series = df["tourism_category"].fillna("").astype(str).str.casefold()
    if "tourism_group" in df.columns:
        series = series + " " + df["tourism_group"].fillna("").astype(str).str.casefold()
    mask = pd.Series(False, index=df.index)
    for word in words:
        mask |= series.str.contains(word, regex=False)
    return df[mask]


def _photos(df, approved_images):
    if not approved_images:
        return df.iloc[0:0]
    shown = df[df.attraction_id.astype(str).isin(approved_images)].copy()
    if shown.empty:
        return shown
    shown["_featured_name"] = shown.attraction_name.str.lower().str.contains(
        r"sigiriya|ella|galle|dambulla|kandy|temple|fort|beach|waterfall|bridge|national park", regex=True
    ).astype(int)
    shown = shown.sort_values(["_featured_name", "duplicate_flag", "attraction_name"],
                              ascending=[False, True, True])
    shown = shown.drop_duplicates(["attraction_name", "district"])
    # Choose a diverse mix of locations before filling the remaining slots.
    first = shown.drop_duplicates("district")
    remaining = shown[~shown.attraction_id.isin(first.attraction_id)]
    return pd.concat([first, remaining], ignore_index=True).head(9)


def _approved_image(item, approved_images, image_dir):
    info = approved_images.get(str(item.attraction_id))
    if not info:
        return None
    filename = str(info.get("image_file", ""))
    if filename != Path(filename).name:
        return None
    f = Path(image_dir) / filename
    return (f, info) if f.is_file() else None


def _photo_credit(meta):
    creator = str(meta.get("creator", "")).strip() or "Creator not listed"
    license_name = str(meta.get("license", "")).strip() or "License not specified"
    return f"Photo: {creator} · {license_name}"


def render_home(*, data, filtered, images, image_dir, shortlist,
                maplibre_panel, destination_view, describe_record):
    """Render without modifying the existing Discover, Hotspots or My Trip pages."""
    # The visual homepage banner is deliberately separate from the approved
    # attraction-specific photo register. Do not use it as a verified photo
    # for any particular OSM attraction.
    hero_file = Path(__file__).resolve().parents[2] / "assets" / "images" / "banners" / "galle_fort_lighthouse.png"
    st.markdown("""<style>
    .tm-hero-shell{display:grid;grid-template-columns:1fr 1.06fr;min-height:335px;
        border-radius:20px;overflow:hidden;border:1px solid #D9E2EA;
        background:#EAF4F6;box-shadow:0 8px 24px rgba(18,59,93,.09);margin:12px 0 4px}
    .tm-hero-copy{padding:clamp(26px,3.2vw,50px);display:flex;flex-direction:column;
        justify-content:center;gap:16px;min-width:0}
    .tm-hero-kicker{font-size:12px;letter-spacing:.17em;color:#0D9488;font-weight:800}
    .tm-hero-copy h2{font-size:clamp(28px,3vw,44px)!important;color:#123B5D!important;
        line-height:1.13!important;margin:0!important;letter-spacing:-.035em;font-weight:800!important}
    .tm-hero-copy p{font-size:15px;color:#475569;line-height:1.65;margin:0;max-width:480px}
    .tm-hero-photo{width:100%;height:335px;object-fit:cover;object-position:50% 52%;display:block}
    .tm-hero-caption{font-size:12px;color:#64748B;margin:4px 0 25px}
    @media(max-width:780px){.tm-hero-shell{grid-template-columns:1fr}
        .tm-hero-copy{padding:25px}.tm-hero-photo{height:245px}}
    </style>""",unsafe_allow_html=True)
    if hero_file.is_file():
        encoded = _banner_base64(str(hero_file), hero_file.stat().st_mtime_ns)
        image_html = ('<img class="tm-hero-photo" alt="Galle Fort lighthouse and coastline at sunset" '
                      f'src="data:image/png;base64,{encoded}">')
        caption = 'Galle Fort Lighthouse · Banner image supplied by the user. Confirm reuse permission before publishing.'
    else:
        image_html = '<div style="height:335px;background:linear-gradient(120deg,#8DD5D1,#CCE8E7);"></div>'
        caption = 'Add assets/images/banners/galle_fort_lighthouse.png to display your chosen hero photograph.'
    st.markdown("""<div class="tm-hero-shell"><div class="tm-hero-copy">
        <div class="tm-hero-kicker">🌴 WELCOME TO TRAVELMIND</div>
        <h2>Discover the beauty of Sri Lanka</h2>
        <p>Explore remarkable landmarks, scenic escapes and tropical coastlines.
        Find places to visit and start planning your own journey.</p>
        </div>""" + image_html + '</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="tm-hero-caption">📷 {escape(caption)}</div>', unsafe_allow_html=True)

    st.markdown("### 🔎 Where do you want to go?")
    query = st.text_input("Search destinations across Sri Lanka", placeholder="Try Sigiriya, Ella, Galle, or an attraction name...", key="tm_home_search")
    interest = st.radio("Explore by interest", list(GROUPS), horizontal=True, key="tm_home_interest")
    pool = _filter_group(filtered, interest)
    if query.strip():
        q = query.strip()
        # Tourists can type either an attraction name ("Ella Rock")
        # or a district name ("Badulla") into the homepage search.
        matches = (
            pool.attraction_name.str.contains(q, case=False, regex=False, na=False)
            | pool.district.str.contains(q, case=False, regex=False, na=False)
        )
        pool = pool[matches]
    pool = pool.drop_duplicates(["attraction_name", "district"])

    # Keep the photo cards synchronized with the active homepage search and
    # interest chips as well as the sidebar's district selection.
    featured = _photos(pool, images)
    if query.strip() or interest != "All places":
        st.caption(f"{len(pool):,} mapped places match your choices.")
        if pool.empty:
            st.info("No matching places. Try another name, interest or sidebar district.")
        else:
            for row_num, record in enumerate(pool.head(4).itertuples()):
                c1,c2 = st.columns([5,1], vertical_alignment="center")
                with c1:
                    st.markdown(f"**{escape(str(record.attraction_name))}** · {escape(str(record.district))}")
                    st.caption(describe_record(record))
                with c2:
                    st.button("Explore →", key=f"tm_home_match_{row_num}", width="stretch",
                              on_click=_go, args=("Discover Places",),
                              kwargs={"name":str(record.attraction_name), "district":str(record.district)})
            if len(pool)>4:
                st.caption("Showing the first four matches. Narrow the name to find a specific place.")

    st.markdown("### ✨ Featured places to discover")
    st.caption("Showing approved attraction photographs matching your district and search filters.")
    if featured.empty:
        st.info("No approved attraction photos match the current district or search. Try another district, clear the search, or check your photo approvals.")
    else:
        for start in range(0, min(9,len(featured)), 3):
            columns=st.columns(3, gap="medium")
            for col, record in zip(columns, featured.iloc[start:start+3].itertuples()):
                with col:
                    with st.container(border=True):
                        item = _approved_image(record, images, image_dir)
                        if item:
                            try:
                                path = Path(item[0])
                                st.image(_card_photo(str(path), path.stat().st_mtime_ns), width="stretch")
                            except (OSError, ValueError):
                                st.info("Photo preview unavailable.")
                        st.markdown(f"**{escape(str(record.attraction_name))}**")
                        st.caption(f"📍 {record.district} · {record.tourism_category}")
                        st.write(describe_record(record))
                        if item:
                            st.caption(_photo_credit(item[1]))
                        st.button("🧭 Explore place", key=f"tm_feature_{str(record.attraction_id)}", width="stretch",
                                  on_click=_go, args=("Discover Places",),
                                  kwargs={"name":str(record.attraction_name), "district":str(record.district)})

    st.markdown("### 🇱🇰 Sri Lanka at a glance")
    n_hotspots = len(shortlist) if shortlist is not None and not shortlist.empty else 0
    m = st.columns(4, gap="small")
    m[0].metric("Mapped attractions", f"{len(filtered):,}")
    m[1].metric("Districts covered", f"{filtered.district.nunique():,}")
    m[2].metric("Attraction-rich areas", f"{n_hotspots:,}")
    m[3].metric("Places with photos", f"{filtered.attraction_id.astype(str).isin(images).sum():,}")

    st.markdown("### 🗺️ Explore Sri Lanka in 3D")
    st.caption("Street, satellite and terrain views. Blue pins are mapped attractions; orange markers identify shortlisted attraction-rich areas.")
    region = st.selectbox("Pick a region", list(REGIONS), key="tm_home_region")
    region_districts = REGIONS[region]
    map_places = filtered if not region_districts else filtered[filtered.district.isin(region_districts)]
    if map_places.empty:
        st.info("No mapped destinations in that region with the current sidebar filters.")
    else:
        # Render the same MapLibre panel as all other TravelMind map pages.
        center = None
        if region_districts:
            center = SimpleNamespace(latitude=float(map_places.latitude.median()),
                                     longitude=float(map_places.longitude.median()))
        maplibre_panel(map_places, height=530, center_record=center,
                       areas_visible=True, force_whole_island=(region=="Whole island"), show_legend=True)

    st.markdown("### 📍 Explore by district")
    grouped=(data[~data.flagged].groupby("district", observed=True)
             .agg(places=("attraction_id", "size")).reset_index()
             .sort_values("district"))
    valid=grouped[grouped.district.ne("Unknown")]
    chosen_district = st.selectbox("Choose your district", valid.district.tolist(),
                                   index=None, placeholder="Choose a district in Sri Lanka", key="tm_home_district")
    if chosen_district:
        n = int(valid.loc[valid.district.eq(chosen_district),"places"].iloc[0])
        st.write(f"**{chosen_district}** · {n:,} mapped attraction candidates")
        st.button(f"Explore places in {chosen_district} →", key="tm_home_open_district",
                  on_click=_go, args=("Discover Places",), kwargs={"district":chosen_district})

    st.markdown("### 🧳 Plan your Sri Lanka trip")
    steps=st.columns(3, gap="medium")
    for col, icon,title,subtitle,target in zip(steps,
           ["🔎","📍","🧳"],
           ["1. Find a place","2. Explore nearby","3. Save your trip"],
           ["Search destinations by name or type", "See nearby attractions and facilities", "Save stops and open your route"],
           ["Discover Places","Tourism Facilities","My Trip"]):
        with col:
            with st.container(border=True):
                st.markdown(f"**{icon} {title}**")
                st.caption(subtitle)
                st.button("Open →", key=f"tm_home_step_{target}", width="stretch",
                          on_click=_go, args=(target,))
    saved = st.session_state.get("tm_trip_saved", [])
    with st.container(border=True):
        c1,c2=st.columns([4,1], vertical_alignment="center")
        with c1:
            st.markdown(f"**🧳 My Trip · {len(saved)} saved places**")
            st.caption("Build your route as you discover destinations.")
        with c2:
            st.button("Open My Trip →", key="tm_home_trip", width="stretch",
                      on_click=_go, args=("My Trip",))
    with st.expander("ℹ️ About the map and destination information"):
        st.write("Place locations are from OpenStreetMap and optional Overture Maps listings. "
                 "They are community-mapped candidates, not independently confirmed recommendations. "
                 "Photo approvals concern image matching and licensing, not attraction quality or safety. "
                 "Maps and area counts do not measure tourist popularity, opening times or live availability.")
        st.button("Read Research & Methodology →", key="tm_home_research", on_click=_go, args=("Analytics",))
