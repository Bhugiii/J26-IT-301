# 🌴 TravelMind
### Component 02 — Geo-Spatial Tourism Intelligence & Attraction Discovery

**Explore Sri Lanka through intelligent geospatial analysis.**

TravelMind Component 02 is a GIS-based tourism intelligence system developed to help travellers discover attractions, explore attraction-rich geographic areas, find nearby tourism services, and organize places they want to visit.

The system combines **geospatial data processing, machine-learning clustering, and interactive mapping** to support tourism exploration across Sri Lanka.

![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?logo=streamlit)
![GIS](https://img.shields.io/badge/GIS-Geospatial_Analysis-168B72)
![Machine Learning](https://img.shields.io/badge/ML-DBSCAN_%7C_K--Means-7952B3)
![Status](https://img.shields.io/badge/Status-Research_Prototype-orange)

---

## ✨ Key Features

### 🧭 01. Discover Places
- Search Sri Lankan attractions by name and district.
- Filter by tourism category.
- Browse approved attraction photographs.
- Find nearby mapped attractions using distance-based search.
- Explore destinations on interactive maps.
- Open selected locations in Google Maps.

### 📍 02. Attraction-Rich Areas
- Explore geographic concentrations of attractions identified through **DBSCAN**.
- View research-screened candidate areas.
- Discover mapped attractions within selected areas.
- Explore geographic relationships through interactive map visualization.

### 🏨 03. Stay, Eat & Travel Services
- Find mapped accommodation options.
- Discover food and drink locations.
- Explore available travel-support service categories.
- Search for facilities around selected destinations.
- View nearby services and straight-line distances.

### 🧳 04. My Trip
- Save attractions of interest.
- Organize selected destinations.
- Review places for an upcoming trip.
- Open map links for travel planning.

---

## 🗺️ Interactive GIS Visualization

The application uses **MapLibre GL JS** and **Folium** to visualize tourism-related geographic data.

Mapping features include:

- Interactive attraction markers
- District-based exploration
- Street and satellite map views
- Optional 3D terrain visualization
- Nearby-location exploration
- Research-screened attraction-rich areas

Google Maps is used as an external location and navigation service. The spatial analysis is performed using the project's own GIS processing and clustering workflows.

---

## 🧠 Machine Learning & Research

### Spatial Clustering

The research investigates geographic attraction patterns using:

**DBSCAN**
- Identifies density-based geographic groups.
- Handles isolated records as noise.
- Supports the discovery of attraction-rich candidate areas.

**K-Means**
- Provides an alternative geographic grouping method.
- Supports comparison of different clustering approaches.

### Research Evaluation

The analysis includes:

- Silhouette score
- Davies–Bouldin index
- DBSCAN noise analysis
- Data-quality review
- Duplicate screening
- Cluster stability and cleaning-sensitivity analysis

### Research Outcome

**18 research-screened attraction-rich candidate areas** were shortlisted from the spatial clustering analysis.

> **Research limitation:** These areas represent concentrations of mapped attraction records. They are not verified tourist-popularity rankings or measured visitor-crowd hotspots.

---

## 🛠️ Technology Stack

| Area | Technologies |
|---|---|
| Programming | Python |
| Dashboard | Streamlit |
| Data processing | Pandas, NumPy |
| Machine learning | K-Means, DBSCAN |
| GIS visualization | MapLibre GL JS, Folium |
| Spatial data | GeoJSON, latitude/longitude coordinates |
| Data sources | OpenStreetMap, Overture Maps |
| Navigation links | Google Maps |
| Version control | Git, GitHub |

---

## 📁 Project Structure

```text
components/
└── geo_spatial/
    ├── assets/
    │   └── images/          # Attraction photos and branding
    ├── config/              # Districts and photo review metadata
    ├── data/
    │   ├── boundaries/      # District GeoJSON
    │   └── processed/       # Processed GIS datasets
    ├── results/
    │   ├── maps/            # Generated visualizations
    │   └── reports/         # Research and evaluation results
    ├── src/
    │   ├── collection/      # Data collection
    │   ├── preprocessing/   # Cleaning and validation
    │   ├── gis/             # Spatial feature preparation
    │   ├── clustering/      # ML clustering and evaluation
    │   └── dashboard/
    │       ├── app.py       # Main Streamlit application
    │       ├── tm_theme.py  # UI styling and navigation
    │       └── ...          # Dashboard support modules
    └── README.md
```

---

## 🚀 Getting Started

### 1. Clone the repository and select the Component 02 branch

```bash
git clone https://github.com/Bhugiii/J26-IT-301.git
cd J26-IT-301
git switch feature/IT23444096-component02-only
```

### 2. Navigate to Component 02

```bash
cd components/geo_spatial
```

### 3. Install the main dashboard dependencies

```bash
python -m pip install streamlit pandas numpy folium streamlit-folium
```

### 4. Prepare the required data

The dashboard requires:

```text
data/processed/travelmind_combined_clusters.csv
```

This processed dataset is not included in the current GitHub upload and must be supplied or generated separately.

The complete tourism-services functionality also requires the associated processed Overture service dataset.

### 5. Run the application

```bash
python -m streamlit run src/dashboard/app.py --server.port 8501
```

Open the dashboard at:

**http://localhost:8501**

---

## 🔬 Research Scope & Limitations

This is a research prototype focused on GIS-based tourism attraction intelligence.

- Mapped places may contain incomplete or inaccurate information.
- Distances are great-circle estimates, not road-travel distances.
- Attraction concentration does not measure visitor demand.
- Service listings are not verified real-time availability.
- An AHP-based Tourism Potential Index is not currently presented as a completed, validated output.

The project prioritizes transparent interpretation of geographic data rather than unsupported tourism-popularity predictions.

---

## 🤝 TravelMind Group Project

This is **Component 02** of the J26-IT-301 TravelMind research project.

The wider TravelMind system includes:

| Component | Research Area |
|---|---|
| C01 | Explainable tourism recommendations |
| **C02** | **Geo-spatial tourism intelligence** |
| C03 | Tourist expectation–reality gap analysis |
| C04 | Traveller behaviour segmentation |

Component 02 is currently available as a standalone Streamlit research dashboard. Integration with the group's React frontend and FastAPI backend is a separate development activity.

---

## 📷 Data & Photo Attribution

The project uses community-mapped geographic data and selected attraction photographs.

Photo approval records, creator information, source links, and available licence details are maintained in:

```text
components/geo_spatial/config/attraction_image_final_review.csv
```

Individual image reuse must follow the applicable licence and attribution requirements.

---

**🌴 TravelMind — Discover Sri Lanka through geospatial intelligence.**
