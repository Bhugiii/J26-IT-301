# TravelMind — Structured Project Folder

This is a **folder scaffold only**. It does **not** contain `sri-lanka-latest.osm.pbf`, downloaded datasets, or operational collection scripts.

## What is included
- `config/districts.json`: all 25 districts, provinces, and requested search categories.
- `config/csv_columns.json`: TravelMind CSV schema.
- `data/raw/`: source files, if added later.
- `data/processed/`: cleaned research records.
- `data/exports/`: exported CSVs.
- `src/collection/`: future data collection code.
- `src/preprocessing/`: future cleaning/validation code.
- `src/gis/`: spatial features and district boundaries.
- `src/clustering/`: K-Means / DBSCAN.
- `src/tpi/`: AHP weights / tourism potential index.
- `src/dashboard/`: interactive dashboard.
- `notebooks/`, `models/`, `results/`, `docs/`, `tests/`: supporting work.

Create or copy code into the appropriate folders as your project develops. No API calls or billing are made by this template.
