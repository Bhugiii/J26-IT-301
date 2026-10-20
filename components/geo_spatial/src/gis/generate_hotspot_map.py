
from pathlib import Path
from html import escape
import math
import json

import pandas as pd
import folium

from folium.plugins import HeatMap, FastMarkerCluster
from branca.element import Element


# ============================================================
# TRAVELMIND - INTERACTIVE GIS HOTSPOT MAP
# No Google Maps API key
# No OpenStreetMap or CARTO background tile requests
# ============================================================


# ------------------------------------------------------------
# STEP 1: Project paths
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ATTRACTIONS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "travelmind_hotspot_map_data.csv"
)

HOTSPOTS_FILE = (
    PROJECT_ROOT
    / "results"
    / "reports"
    / "travelmind_hotspot_summary.csv"
)

DISTRICTS_FILE = (
    PROJECT_ROOT
    / "data"
    / "boundaries"
    / "sri_lanka_districts.geojson"
)

OUTPUT_DIR = PROJECT_ROOT / "results" / "maps"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_FILE = (
    OUTPUT_DIR / "travelmind_interactive_hotspots.html"
)


# ------------------------------------------------------------
# STEP 2: Verify required files
# ------------------------------------------------------------

required_files = [
    ATTRACTIONS_FILE,
    HOTSPOTS_FILE,
    DISTRICTS_FILE,
]

for file_path in required_files:
    if not file_path.exists():
        raise FileNotFoundError(
            f"Required file not found: {file_path}"
        )

print("\nLoading TravelMind GIS data...")


# ------------------------------------------------------------
# STEP 3: Load attraction and hotspot datasets
# ------------------------------------------------------------

attractions = pd.read_csv(
    ATTRACTIONS_FILE,
    low_memory=False
)

hotspots = pd.read_csv(
    HOTSPOTS_FILE,
    low_memory=False
)

with open(
    DISTRICTS_FILE,
    "r",
    encoding="utf-8"
) as f:
    district_geojson = json.load(f)

print("Total attraction records:", len(attractions))
print("Total candidate clusters:", len(hotspots))


# ------------------------------------------------------------
# STEP 4: Validate coordinates
# ------------------------------------------------------------

for col in ["latitude", "longitude"]:
    attractions[col] = pd.to_numeric(
        attractions[col],
        errors="coerce"
    )

for col in [
    "center_latitude",
    "center_longitude",
    "attraction_count",
    "review_required_percentage",
    "max_center_distance_km",
]:
    hotspots[col] = pd.to_numeric(
        hotspots[col],
        errors="coerce"
    )

attractions["dbscan_cluster"] = pd.to_numeric(
    attractions["dbscan_cluster"],
    errors="raise"
).astype(int)

valid_attractions = (
    attractions["latitude"].between(-90, 90)
    & attractions["longitude"].between(-180, 180)
)

if not valid_attractions.all():
    print(
        "Warning: Skipping",
        int((~valid_attractions).sum()),
        "records with invalid coordinates."
    )

attractions = attractions.loc[
    valid_attractions
].copy()

hotspots = hotspots.dropna(
    subset=[
        "center_latitude",
        "center_longitude"
    ]
).copy()

hotspots = hotspots[
    hotspots["center_latitude"].between(-90, 90)
    & hotspots["center_longitude"].between(-180, 180)
].copy()


# ------------------------------------------------------------
# STEP 5: Create map WITHOUT online basemap tiles
# ------------------------------------------------------------

m = folium.Map(
    location=[7.8731, 80.7718],
    zoom_start=8,
    tiles=None,
    control_scale=True,
    prefer_canvas=True
)

# Background color. Does not request any map tiles.
m.get_root().header.add_child(
    Element(
        """
        <style>
            .leaflet-container {
                background: #eef4f8 !important;
            }
        </style>
        """
    )
)


# ------------------------------------------------------------
# STEP 6: Sri Lanka district polygons
# ------------------------------------------------------------

district_layer = folium.FeatureGroup(
    name="District boundaries",
    show=True
)

folium.GeoJson(
    district_geojson,
    name="Sri Lanka district boundaries",
    style_function=lambda feature: {
        "fillColor": "#dcefe1",
        "color": "#526577",
        "weight": 1.1,
        "opacity": 0.9,
        "fillOpacity": 0.75
    },
    highlight_function=lambda feature: {
        "fillColor": "#c2dfcb",
        "color": "#1d4ed8",
        "weight": 2,
        "fillOpacity": 0.9
    }
).add_to(district_layer)

district_layer.add_to(m)


# ------------------------------------------------------------
# STEP 7: Fit map to Sri Lanka's attraction coordinates
# ------------------------------------------------------------

if not attractions.empty:

    min_lat = attractions["latitude"].min()
    max_lat = attractions["latitude"].max()

    min_lon = attractions["longitude"].min()
    max_lon = attractions["longitude"].max()

    m.fit_bounds(
        [
            [min_lat, min_lon],
            [max_lat, max_lon]
        ],
        padding=(25, 25)
    )


# ------------------------------------------------------------
# STEP 8: Prepare DBSCAN data
# ------------------------------------------------------------

clustered = attractions[
    attractions["dbscan_cluster"] != -1
].copy()

noise = attractions[
    attractions["dbscan_cluster"] == -1
].copy()

print("Clustered attraction records:", len(clustered))
print("DBSCAN noise records:", len(noise))


# ------------------------------------------------------------
# STEP 9: Add attraction density heatmap
# ------------------------------------------------------------

heatmap_layer = folium.FeatureGroup(
    name="Clustered attraction heatmap",
    show=False
)

heatmap_coordinates = clustered[
    ["latitude", "longitude"]
].values.tolist()

if heatmap_coordinates:

    HeatMap(
        data=heatmap_coordinates,
        radius=14,
        blur=16,
        min_opacity=0.2,
        max_zoom=12
    ).add_to(heatmap_layer)

heatmap_layer.add_to(m)


# ------------------------------------------------------------
# STEP 10: Add DBSCAN hotspot candidate markers
# ------------------------------------------------------------

hotspot_layer = folium.FeatureGroup(
    name="DBSCAN hotspot candidates",
    show=True
)

for row in hotspots.itertuples():

    cluster_id = int(row.dbscan_cluster)
    attraction_count = int(row.attraction_count)

    main_district = escape(
        str(row.main_district)
    )

    quality_warning = escape(
        str(row.quality_warning)
    )

    review_percentage = float(
        row.review_required_percentage
    )

    max_distance = float(
        row.max_center_distance_km
    )

    # Orange = many records need review.
    # Blue = lower review workload.
    # These colors do not represent tourism quality.
    if review_percentage >= 50:
        marker_color = "#f97316"
    else:
        marker_color = "#2563eb"

    marker_radius = min(
        22,
        5 + 3 * math.log1p(attraction_count)
    )

    popup_html = f"""
    <div style="
        width:270px;
        font-family:Arial,sans-serif;
        font-size:13px;
        line-height:1.6;
    ">

        <h3 style="margin-top:0;">
            TravelMind Cluster {cluster_id}
        </h3>

        <b>Main district:</b>
        {main_district}

        <br>

        <b>Mapped attractions:</b>
        {attraction_count:,}

        <br>

        <b>Records requiring review:</b>
        {review_percentage:.2f}%

        <br>

        <b>Maximum center distance:</b>
        {max_distance:.2f} km

        <br>

        <b>Quality warning:</b>
        {quality_warning}

        <hr>

        <small>
            DBSCAN candidate attraction concentration.
            This is not a confirmed visitor-demand hotspot
            or Tourism Potential Index ranking.
        </small>

    </div>
    """

    folium.CircleMarker(
        location=[
            float(row.center_latitude),
            float(row.center_longitude)
        ],
        radius=marker_radius,
        color=marker_color,
        weight=2,
        fill=True,
        fill_color=marker_color,
        fill_opacity=0.68,
        tooltip=(
            f"Cluster {cluster_id} - "
            f"{attraction_count} attractions"
        ),
        popup=folium.Popup(
            popup_html,
            max_width=330
        )
    ).add_to(hotspot_layer)

hotspot_layer.add_to(m)


# ------------------------------------------------------------
# STEP 11: Add DBSCAN isolated / noise points
# ------------------------------------------------------------

noise_layer = folium.FeatureGroup(
    name="Isolated attractions (DBSCAN noise)",
    show=False
)

noise_coordinates = noise[
    ["latitude", "longitude"]
].values.tolist()

if noise_coordinates:

    FastMarkerCluster(
        noise_coordinates
    ).add_to(noise_layer)

noise_layer.add_to(m)


# ------------------------------------------------------------
# STEP 12: Add a title
# ------------------------------------------------------------

title_html = """
<div style="
    position:fixed;
    top:20px;
    left:65px;
    z-index:9999;
    background:rgba(255,255,255,0.95);
    border-radius:10px;
    padding:12px 18px;
    font-family:Arial,sans-serif;
    box-shadow:0 2px 10px rgba(0,0,0,0.15);
    max-width:360px;
">

    <div style="
        font-size:20px;
        font-weight:bold;
        color:#17365d;
    ">
        TravelMind
    </div>

    <div style="
        font-size:12px;
        color:#475569;
        margin-top:4px;
    ">
        Sri Lanka Tourism Attraction Hotspot Map
    </div>

    <div style="
        font-size:11px;
        color:#64748b;
        margin-top:5px;
    ">
        DBSCAN clustering | 225 candidate clusters
    </div>

</div>
"""

m.get_root().html.add_child(
    Element(title_html)
)


# ------------------------------------------------------------
# STEP 13: Add legend
# ------------------------------------------------------------

legend_html = """
<div style="
    position:fixed;
    bottom:30px;
    left:30px;
    z-index:9999;
    width:260px;
    background:rgba(255,255,255,0.97);
    border:1px solid #cbd5e1;
    border-radius:10px;
    padding:14px;
    font-family:Arial,sans-serif;
    font-size:12px;
    line-height:1.8;
    box-shadow:0 2px 10px rgba(0,0,0,0.15);
">

    <b style="font-size:14px;color:#17365d;">
        TravelMind GIS Legend
    </b>

    <hr>

    <span style="color:#2563eb;font-size:19px;">
        ●
    </span>
    Candidate cluster - lower review workload

    <br>

    <span style="color:#f97316;font-size:19px;">
        ●
    </span>
    Candidate cluster - high review workload

    <br>

    <span style="color:#64748b;font-size:19px;">
        ●
    </span>
    DBSCAN isolated attraction points

    <br>

    <span style="
        display:inline-block;
        width:13px;
        height:13px;
        background:#dcefe1;
        border:1px solid #526577;
    "></span>
    Sri Lanka district boundaries

    <hr>

    <small>
        Circle size reflects mapped attraction count.
        Cluster markers show approximate centers.
        Results are provisional and require validation.
    </small>

</div>
"""

m.get_root().html.add_child(
    Element(legend_html)
)


# ------------------------------------------------------------
# STEP 14: Layer controls
# ------------------------------------------------------------

folium.LayerControl(
    collapsed=False
).add_to(m)


# ------------------------------------------------------------
# STEP 15: Save interactive HTML map
# ------------------------------------------------------------

m.save(str(OUTPUT_FILE))

print("\n" + "=" * 65)
print("TRAVELMIND - INTERACTIVE GIS HOTSPOT MAP")
print("=" * 65)

print("Total mapped attractions:", len(attractions))
print("Candidate hotspot markers:", len(hotspots))
print("Clustered records:", len(clustered))
print("Noise records:", len(noise))

print("\nMap saved successfully:")
print(OUTPUT_FILE)

print("\nNo online basemap tile provider is required.")
print("Step 12 completed successfully!")
