"""TravelMind navy / teal branded UI theme with the user-supplied project logo.

Saved as src/dashboard/tm_theme.py. Imported by app.py.
Only styling and navigation helpers live here; no data or model logic.
"""
from html import escape
from pathlib import Path
import base64

import streamlit as st

NAV_PAGES = ["Dashboard", "Discover Places", "Hotspots", "Tourism Facilities", "My Trip", "Analytics"]
NAV_LABELS = {
    "Dashboard": "Dashboard",
    "Discover Places": "Discover Places",
    "Hotspots": "Attraction-Rich Areas",
    "Tourism Facilities": "Stay & Eat Nearby",
    "My Trip": "My Trip",
    "Analytics": "Research & Methodology",
}
NAV_ICONS = {
    "Dashboard": "🏠",
    "Discover Places": "🧭",
    "Hotspots": "📍",
    "Tourism Facilities": "🏨",
    "My Trip": "🧳",
    "Analytics": "📈",
}
PAGE_INFO = {
    "Dashboard": ("EXPLORE SRI LANKA", "Your Sri Lanka adventure starts here",
                  "Discover attractions, explore scenic places and build your trip."),
    "Discover Places": ("EXPLORE SRI LANKA", "Find places to visit",
                        "Pick a starting attraction and see mapped places around it. Distances are straight-line estimates."),
    "Hotspots": ("GEOGRAPHIC RESEARCH", "Attraction-rich areas",
                 "Areas where many mapped attractions sit close together. This shows map concentration, not tourist popularity."),
    "Tourism Facilities": ("TRAVEL SUPPORT", "Stay & eat nearby",
                           "Find mapped accommodation, food and travel services around a destination."),
    "My Trip": ("TRIP PLANNER", "My Sri Lanka trip", "Save places, change visit order and open your route in Google Maps."),
    "Analytics": ("MODEL INSIGHTS", "Research & methodology",
                  "Clustering results, data-quality findings and the limitations behind TravelMind."),
}

THEME_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{--tm-primary:#123B5D;--tm-secondary:#0D9488;--tm-secondary-hover:#0F766E;--tm-success:#16A34A;--tm-accent:#F5B942;--tm-background:#F5F8FA;--tm-card:#FFFFFF;--tm-text:#172B3A;--tm-muted:#64748B;--tm-border:#D9E2EA;--tm-radius:12px;--g:#0D9488;--g-dark:#123B5D;--g-pale:#E2F4F1;--g-line:#B5E2DA;--bg:#F5F8FA;--ink:#172B3A;--muted:#64748B;--line:#D9E2EA;}
.stApp{background:var(--bg);color:var(--ink);font-family:'Inter','Segoe UI',Arial,sans-serif;}
.block-container{padding-top:1.2rem;padding-bottom:2.5rem;max-width:1500px;}
header[data-testid="stHeader"]{background:#ffffff;border-bottom:1px solid var(--line);}
.stAppDeployButton{display:none;}

/* Sidebar */
section[data-testid="stSidebar"]{background:#ffffff;border-right:1px solid var(--line);}
section[data-testid="stSidebar"] label,section[data-testid="stSidebar"] p{color:#172B3A;}
section[data-testid="stSidebar"] [data-baseweb="select"] > div,
section[data-testid="stSidebar"] input{background:#fff;border:1px solid #D9E2EA;border-radius:10px;}
.tm-logo{display:flex;align-items:center;gap:10px;margin:2px 0 14px;}
.tm-logo-ic{width:40px;height:40px;border-radius:12px;background:var(--g-pale);display:flex;align-items:center;justify-content:center;font-size:1.3rem;}
.tm-logo-t{font-weight:800;font-size:1.05rem;color:var(--ink);line-height:1.1;}
.tm-logo-s{font-size:.72rem;color:var(--muted);}
.tm-side-label{font-size:.68rem;letter-spacing:.16em;font-weight:700;color:#64748B;margin:14px 0 6px;}
.st-key-tm_nav [role="radiogroup"]{gap:3px;}
.st-key-tm_nav [role="radiogroup"] label{width:100%;margin:0;padding:10px 12px;border-radius:10px;border:1px solid transparent;cursor:pointer;}
.st-key-tm_nav [role="radiogroup"] label > div:first-child{display:none;}
.st-key-tm_nav [role="radiogroup"] label:hover{background:#EDF7F5;}
.st-key-tm_nav [role="radiogroup"] label:has(input:checked){background:var(--g-pale);border-color:var(--g-line);}
.st-key-tm_nav [role="radiogroup"] label p{font-size:.9rem;font-weight:500;color:#172B3A;}
.st-key-tm_nav [role="radiogroup"] label:has(input:checked) p{color:var(--g);font-weight:700;}
.tm-status{border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:#F7FAFC;font-size:.78rem;color:#64748B;line-height:1.7;margin-top:10px;}
.tm-status b{color:var(--g);}

/* Page header */
.tm-crumb{font-size:.78rem;color:var(--muted);margin-bottom:14px;}
.tm-crumb b{color:var(--ink);font-weight:600;}
.tm-eyebrow{font-size:.72rem;letter-spacing:.16em;font-weight:700;color:var(--g);}
.tm-h1{font-size:2.05rem;font-weight:800;letter-spacing:-.02em;color:var(--ink);margin:2px 0 4px;line-height:1.15;}
.tm-lead{font-size:.92rem;color:var(--muted);margin-bottom:16px;max-width:760px;}

/* Quick-action cards */
.tm-qa{display:flex;align-items:center;gap:12px;}
.tm-qa-ic{width:38px;height:38px;border-radius:10px;background:var(--g-pale);display:flex;align-items:center;justify-content:center;font-size:1.15rem;flex:none;}
.tm-qa-t{font-weight:700;color:var(--g-dark);font-size:.92rem;}
.tm-qa-s{font-size:.76rem;color:var(--muted);}

/* Cards, metrics, controls */
div[data-testid="stVerticalBlockBorderWrapper"]{border:1px solid var(--line);background:#ffffff;border-radius:var(--tm-radius);box-shadow:0 1px 3px rgba(22,51,42,.05);}
div[data-testid="stMetric"]{background:#ffffff;border:1px solid var(--line);border-radius:var(--tm-radius);padding:12px 14px;}
[data-testid="stMetricLabel"],[data-testid="stMetricLabel"] *{color:var(--muted);}
[data-testid="stMetricValue"],[data-testid="stMetricValue"] *{color:var(--g-dark);}
.stButton>button,.stLinkButton a,.stDownloadButton>button{border-radius:var(--tm-radius);border:1px solid var(--g-line);color:var(--g);background:#ffffff;font-weight:600;}
.stButton>button:hover,.stLinkButton a:hover,.stDownloadButton>button:hover{background:var(--g-pale);border-color:var(--tm-secondary-hover);color:var(--tm-secondary-hover);}
.stButton>button[kind="primary"]{background:var(--tm-secondary);border-color:var(--tm-secondary);color:#ffffff;}
[data-baseweb="select"] > div,.stTextInput input{border-radius:10px;}
.stTabs [data-baseweb="tab"]{font-weight:700;}
iframe{border-radius:14px;}

/* Form controls: always dark text on white, whatever the browser theme is */
:root,.stApp{color-scheme:light;}
.stApp input,.stApp textarea{color:#172B3A !important;-webkit-text-fill-color:#172B3A !important;background:#ffffff !important;caret-color:#172B3A;}
.stApp input::placeholder,.stApp textarea::placeholder{color:#64748B !important;-webkit-text-fill-color:#64748B !important;opacity:1 !important;}
[data-baseweb="select"] div,[data-baseweb="select"] input{background-color:#ffffff !important;color:#172B3A !important;-webkit-text-fill-color:#172B3A !important;}
[data-baseweb="select"] > div{border:1px solid #D9E2EA !important;border-radius:10px !important;}
[data-baseweb="select"] svg{fill:#0D9488 !important;color:#0D9488 !important;}
[data-baseweb="popover"] ul,[data-baseweb="menu"]{background:#ffffff !important;}
[data-baseweb="popover"] li,[data-baseweb="menu"] li,[data-baseweb="popover"] li *{color:#172B3A !important;background:#ffffff;}
[data-baseweb="popover"] li:hover,[data-baseweb="popover"] li[aria-selected="true"]{background:#E2F4F1 !important;}
[data-baseweb="tag"]{background:#E2F4F1 !important;}
[data-baseweb="tag"] *{color:#123B5D !important;}
label[data-baseweb="checkbox"] > span:first-child{background:#ffffff !important;border:1.5px solid #94A3B8 !important;}
label[data-baseweb="checkbox"]:has(input:checked) > span:first-child{background:#0D9488 !important;border-color:#0D9488 !important;}
.stApp label,.stApp [data-testid="stWidgetLabel"] p{color:#172B3A !important;}
.stApp .stMarkdown,.stApp .stMarkdown p,.stApp [data-testid="stCaptionContainer"]{color:inherit;}
[data-testid="stDataFrame"]{background:#ffffff;border-radius:12px;}

/* TravelMind Navy/Teal refinements */
.stApp a{color:var(--tm-secondary);}
.stApp a:hover{color:var(--tm-secondary-hover);}
.stApp h1,.stApp h2,.stApp h3{color:var(--tm-primary);}
.stApp [data-testid="stSidebar"] [data-testid="stMarkdownContainer"]{line-height:1.5;}
.stButton>button:focus-visible,.stLinkButton a:focus-visible{outline:3px solid var(--tm-accent);outline-offset:2px;}
[data-testid="stMetricValue"],[data-testid="stMetricValue"] *{color:var(--tm-primary);}
/* Notes and badges */
.tm-note{color:#123B5D;background:var(--g-pale);border-left:3px solid var(--g);border-radius:8px;padding:10px 12px;font-size:.82rem;}
.tm-badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:.72rem;font-weight:700;}
.tm-badge.curated{background:#DCFCE7;color:#166534;}
.tm-badge.osm{background:#fdf3d4;color:#8a6a12;}
.tm-badge.overture{background:#fde5d2;color:#9a4d12;}
.tm-muted{color:var(--muted);font-size:.82rem;}
"""

_BADGES = {
    "curated": ("curated", "🟢 Curated"),
    "osm": ("osm", "🟡 Community-mapped (unverified)"),
    "overture": ("overture", "🟠 Additional listing (unreviewed)"),
}


# Unified group navigation. Unconnected components are explicitly marked as previews.
GROUP_NAV = [
    ("MAIN MENU", [
        ("Dashboard", "▦", "Dashboard"),
        ("Recommendations", "◈", "Recommendations"),
        ("Saved Places", "♡", "Saved Places"),
        ("Traveller Profile", "♙", "Traveller Profile"),
        ("Itinerary Planner", "⇄", "Itinerary Planner"),
        ("Account", "◉", "Account"),
        ("Crowd Prediction", "▥", "Crowd Prediction"),
        ("Weather Intelligence", "☼", "Weather Intelligence"),
        ("Traveller Segments", "♧", "Traveller Segments"),
        ("Expectation–Reality", "◎", "Expectation–Reality"),
    ]),
    ("GEOSPATIAL INTELLIGENCE · COMPONENT 02", [
        ("Discover Places", "◈", "Discover Places"),
        ("Hotspots", "⌖", "Attraction-Rich Areas"),
        ("Tourism Facilities", "▤", "Stay & Eat Nearby"),
        ("My Trip", "♧", "My Trip"),
        ("Analytics", "▤", "Research & Methodology"),
    ]),
]
GIS_PAGES = {"Dashboard", "Discover Places", "Hotspots", "Tourism Facilities", "Analytics"}
INTEGRATION_PAGES = {
    "Recommendations": ("COMPONENT 01 · INTEGRATION", "Recommendations", "This group component has not been connected to the GIS prototype yet."),
    "Saved Places": ("SHARED PLATFORM · INTEGRATION", "Saved places", "Shared saved-place functionality is planned for group integration. Use My Trip to save places in the current prototype."),
    "Traveller Profile": ("SHARED PLATFORM · INTEGRATION", "Traveller profile", "The group traveller-profile component is not connected to this prototype."),
    "Itinerary Planner": ("COMPONENT 01 · INTEGRATION", "Itinerary planner", "The group's itinerary planner has not been integrated. My Trip currently supports manual trip organization."),
    "Account": ("SHARED PLATFORM · INTEGRATION", "Account", "Sign-in and account features are planned for integration; this prototype does not manage accounts."),
    "Crowd Prediction": ("COMPONENT 01 · INTEGRATION", "Crowd prediction", "Live crowd prediction is not connected. GIS attraction concentrations are not visitor crowd estimates."),
    "Weather Intelligence": ("SHARED PLATFORM · INTEGRATION", "Weather intelligence", "Real-time weather functionality is not connected to this prototype."),
    "Traveller Segments": ("COMPONENT 04 · INTEGRATION", "Traveller segments", "The traveller segmentation component is not connected yet. This page will be linked during group integration."),
    "Expectation–Reality": ("COMPONENT 03 · INTEGRATION", "Expectation–reality", "The expectation–reality component is not connected yet. No disappointment index is calculated on this page."),
}
NAV_LABELS.update({page: label for _, entries in GROUP_NAV for page, _, label in entries})
PAGE_INFO.update(INTEGRATION_PAGES)


THEME_CSS += """
/* Refined unified sidebar. Overrides global button styling only within menu rows. */
section[data-testid="stSidebar"] {background:#ffffff !important; border-right:1px solid #E5EAE8 !important;}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {padding-top:16px;}
section[data-testid="stSidebar"] .tm-logo {margin:0 0 18px !important; padding:0 !important;}
section[data-testid="stSidebar"] .tm-side-label {
  margin:17px 0 8px !important; font-size:11px !important;
  font-weight:750 !important; letter-spacing:.14em !important; color:#899792 !important;
}
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] {
  padding:0 !important; margin:0 0 3px !important;
  border:0 !important; background:transparent !important; box-shadow:none !important;
}
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button {
  display:flex !important; align-items:center !important; justify-content:flex-start !important;
  gap:12px !important; width:100% !important;
  min-height:43px !important; padding:9px 13px !important;
  border:0 !important; border-left:3px solid transparent !important;
  border-radius:10px !important; background:transparent !important;
  box-shadow:none !important; color:#53625C !important;
  font-size:14px !important; font-weight:600 !important;
  transition:background-color .12s ease !important;
}
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button p,
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button [data-testid="stMarkdownContainer"] {
  margin:0 !important; text-align:left !important; color:inherit !important;
  font-size:14px !important; font-weight:inherit !important;
}
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button [data-testid="stIconMaterial"],
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button span.material-symbols-rounded {
  font-size:20px !important; flex:none !important;
}
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button:hover {
  background:#F0F8F4 !important; color:#147559 !important;
}
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button[kind="primary"] {
  background:#E2F4EB !important; color:#136B4E !important;
  border-left:3px solid #0F956F !important; font-weight:750 !important;
}
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button[kind="primary"] p {
  font-weight:750 !important; color:#136B4E !important;
}
/* Force a consistent LEFT START for the entire button content, not just the label. */
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button {
  justify-content:flex-start !important;
  text-align:left !important;
  padding-left:16px !important;
}
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button > div,
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button > span,
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button [data-testid="stMarkdownContainer"] {
  justify-content:flex-start !important;
  text-align:left !important;
  margin-left:0 !important;
  margin-right:0 !important;
}
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button > div {
  display:flex !important;
  align-items:center !important;
  gap:12px !important;
  width:100% !important;
}
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button svg,
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button [data-testid="stIconMaterial"] {
  flex:0 0 20px !important;
  width:20px !important;
  margin:0 !important;
}
section[data-testid="stSidebar"] [class*="st-key-tm_menu_"] button p {
  text-align:left !important;
  margin:0 !important;
}
/* Compact group-style logo: icon left, stacked name and tagline right. */
section[data-testid="stSidebar"] .tm-sidebar-brand {
  display:flex; align-items:center; justify-content:flex-start;
  gap:10px; width:100%; min-height:68px; padding:2px 4px;
}
section[data-testid="stSidebar"] .tm-sidebar-brand > img {
  display:block; width:46px; height:55px; object-fit:contain; flex:none;
}
section[data-testid="stSidebar"] .tm-sidebar-brand-copy {display:flex; flex-direction:column; gap:3px;}
section[data-testid="stSidebar"] .tm-sidebar-brand-name {
  color:#354F49; font-size:14px; font-weight:750; line-height:1.32;
}
section[data-testid="stSidebar"] .tm-sidebar-brand-tagline {
  color:#85918B; font-size:12px; font-weight:400; white-space:nowrap;
}
/* Compact, visually separated GIS section lower down the scrollable menu. */
.st-key-travelmind_gis_filters {border:1px solid #D9E2EA; border-radius:12px; background:#FFF;}
"""

# Built-in Streamlit Material icons, for a consistent outlined sidebar appearance.
MENU_MATERIAL_ICONS = {
    "Dashboard": ":material/dashboard:",
    "Recommendations": ":material/explore:",
    "Saved Places": ":material/favorite:",
    "Traveller Profile": ":material/person_outline:",
    "Itinerary Planner": ":material/route:",
    "Account": ":material/account_circle:",
    "Crowd Prediction": ":material/groups:",
    "Weather Intelligence": ":material/wb_sunny:",
    "Traveller Segments": ":material/group:",
    "Expectation–Reality": ":material/verified_user:",
    "Discover Places": ":material/travel_explore:",
    "Hotspots": ":material/location_on:",
    "Tourism Facilities": ":material/hotel:",
    "My Trip": ":material/luggage:",
    "Analytics": ":material/monitoring:",
}


def inject_theme():
    st.markdown("<style>" + THEME_CSS + "</style>", unsafe_allow_html=True)


def source_badge(kind="osm"):
    css, label = _BADGES.get(kind, _BADGES["osm"])
    return f'<span class="tm-badge {css}">{escape(label)}</span>'


def _brand_logo_html():
    """Show the supplied project logo from assets/images/branding."""
    logo = Path(__file__).resolve().parents[2] / "assets" / "images" / "branding" / "travelmind_logo.png"
    # Prefer the compact icon created from the existing TravelMind artwork.
    # Preserve the original full logo for other uses throughout the app.
    icon = logo.with_name("travelmind_sidebar_icon.png")
    if icon.is_file():
        try:
            encoded = base64.b64encode(icon.read_bytes()).decode("ascii")
            return (
                '<div class="tm-sidebar-brand">'
                f'<img src="data:image/png;base64,{encoded}" alt="TravelMind symbol" />'
                '<div class="tm-sidebar-brand-copy">'
                '<div class="tm-sidebar-brand-name">Travel<br>Mind</div>'
                '<div class="tm-sidebar-brand-tagline">Sri Lanka, your way.</div>'
                '</div></div>'
            )
        except OSError:
            pass
    # Keep the sidebar usable if the optional compact icon was not installed.
    return ('<div class="tm-sidebar-brand">'
            '<div class="tm-sidebar-brand-name">Travel Mind</div>'
            '<div class="tm-sidebar-brand-tagline">Sri Lanka, your way.</div>'
            '</div>')


def render_sidebar_nav():
    """Shared group-style navigation; existing GIS page IDs stay unchanged."""
    st.markdown(
        '<div class="tm-logo" style="justify-content:flex-start;padding:0">'
        + _brand_logo_html() + '</div>', unsafe_allow_html=True,
    )
    st.session_state.setdefault("travelmind_page", "Dashboard")
    known = {entry[0] for _, entries in GROUP_NAV for entry in entries}
    if st.session_state["travelmind_page"] not in known:
        st.session_state["travelmind_page"] = "Dashboard"

    for heading, entries in GROUP_NAV:
        # Keep every Component 02 link, but omit its technical group heading.
        if heading != "GEOSPATIAL INTELLIGENCE · COMPONENT 02":
            st.markdown(f'<div class="tm-side-label">{escape(heading)}</div>', unsafe_allow_html=True)
        for page_id, _old_icon, label in entries:
            active = st.session_state["travelmind_page"] == page_id
            safe_key = page_id.lower().replace(" ", "_").replace("–", "_")
            with st.container(key=f"tm_menu_{safe_key}"):
                if st.button(
                    label,
                    icon=MENU_MATERIAL_ICONS.get(page_id, ":material/chevron_right:"),
                    key=f"tm_nav_btn_{page_id}",
                    use_container_width=True,
                    type="primary" if active else "secondary",
                    help=("Awaiting group integration" if page_id in INTEGRATION_PAGES else None),
                ):
                    st.session_state["travelmind_page"] = page_id
                    st.rerun()
    return st.session_state["travelmind_page"]


def render_sidebar_status(items):
    """items: list of (label, bool_loaded). Shown at the bottom of the sidebar."""
    rows = "".join(
        f"<div>{'✅' if ok else '⚠️'} {escape(label)}</div>" for label, ok in items
    )
    with st.sidebar:
        st.markdown(
            f'<div class="tm-status"><b>Data layers</b>{rows}</div>',
            unsafe_allow_html=True,
        )


def render_page_header(page):
    eyebrow, title, lead = PAGE_INFO.get(page, ("TRAVELMIND", page, ""))
    st.markdown(
        f'<div class="tm-crumb">TravelMind &nbsp;/&nbsp; <b>{escape(NAV_LABELS.get(page, page))}</b></div>'
        f'<div class="tm-eyebrow">{escape(eyebrow)}</div>'
        f'<div class="tm-h1">{escape(title)}</div>'
        f'<div class="tm-lead">{escape(lead)}</div>',
        unsafe_allow_html=True,
    )


def _go(target):
    st.session_state["travelmind_page"] = target


def render_quick_actions():
    items = [
        ("🧭", "Find places", "Search and see what is nearby", "Discover Places"),
        ("🏨", "Stay & eat nearby", "Hotels, food, travel services", "Tourism Facilities"),
        ("📍", "Attraction-rich areas", "Mapped concentrations", "Hotspots"),
        ("📈", "Research results", "Models and data quality", "Analytics"),
    ]
    cols = st.columns(4, gap="medium")
    for col, (icon, title, sub, target) in zip(cols, items):
        with col:
            with st.container(border=True):
                st.markdown(
                    f'<div class="tm-qa"><span class="tm-qa-ic">{icon}</span>'
                    f'<div><div class="tm-qa-t">{escape(title)}</div><div class="tm-qa-s">{escape(sub)}</div></div></div>',
                    unsafe_allow_html=True,
                )
                st.button("Open  →", key=f"qa_{target}", on_click=_go, args=(target,), width="stretch")