# TravelMind — Component 02: Geospatial Tourism Intelligence

## Overview

Component 02 of the TravelMind project provides GIS-based attraction discovery and tourism intelligence for Sri Lanka.

The component helps tourists explore mapped attractions, identify areas with concentrations of attractions, find nearby tourism services, and organize places they want to visit.

It combines geospatial data processing, machine-learning clustering, and interactive map visualization.

## Main Features

### 1. Discover Places
- Search attractions by name or district.
- Explore attractions by tourism category.
- View available approved attraction photographs.
- Discover nearby mapped attractions.
- Explore locations using interactive maps and Google Maps links.

### 2. Attraction-Rich Areas
- Identify geographic concentrations of mapped attractions using DBSCAN clustering.
- Explore research-screened attraction-rich areas.
- View the attractions belonging to selected areas.
- Explore attraction locations on interactive maps.

### 3. Stay, Eat & Travel Services
- Find mapped accommodation, food and drink, and travel-support services.
- Explore services near a selected destination.
- Filter by service category and distance.
- View service locations on maps.

### 4. My Trip
- Save selected destinations.
- Organize places to visit.
- Review saved locations and open map routes.

## Technologies Used

- Python
- Streamlit
- Pandas and NumPy
- Folium and MapLibre GL JS
- GeoJSON and GIS datasets
- DBSCAN and K-means clustering
- OpenStreetMap and Overture Maps data

## Project Structure

```text
components/geo_spatial/
├── assets/             # Attraction images and branding
├── config/             # Districts and photo approval records
├── data/               # GIS boundaries and processed datasets
├── results/            # Clustering evaluation and research reports
├── src/
│   ├── collection/     # Data collection
│   ├── preprocessing/  # Data cleaning and validation
│   ├── gis/            # Spatial data preparation
│   ├── clustering/     # DBSCAN and K-means analysis
│   └── dashboard/      # Streamlit application
└── README.md
```

## Running the Dashboard

From the Component 02 folder:

```bash
python -m pip install streamlit pandas numpy folium streamlit-folium
python -m streamlit run src/dashboard/app.py --server.port 8501
```

Open http://localhost:8501 in your browser.

**Data requirement:** The application requires the processed clustering dataset at `data/processed/travelmind_combined_clusters.csv`. Some additional tourism-service and attraction-catalog datasets are optional or may need to be generated locally. Large raw downloads are not included in the repository.

## Research Methodology

The research uses DBSCAN to identify geographic concentrations of mapped attraction records. K-means is also used in clustering experiments, including a separate tourism-infrastructure analysis.

Research outputs and evaluation reports are preserved in the `results/` directory.

**Important limitation:** Mapped attraction and service records are not all independently verified. Geographic concentration does not represent tourist popularity, visitor numbers, or real-time crowd levels.

## Team Integration

This component is maintained on the branch:

`feature/IT23444096-geo-spatial-v2`

The standalone Streamlit dashboard is available for development and demonstration. Integration with the broader TravelMind frontend and backend is a separate team activity.