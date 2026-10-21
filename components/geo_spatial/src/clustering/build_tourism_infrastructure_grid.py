"""Build a reproducible 5 km Sri Lanka tourism infrastructure grid from Overture outputs.

Run from TravelMind project root:
    python src/clustering/build_tourism_infrastructure_grid.py

Inputs are provisional mapped POIs, not verified tourist demand.
Does not modify existing 8,590-record baseline or model results.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
from pyproj import Transformer
from shapely.geometry import box, shape
from shapely.ops import transform, unary_union
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/processed/overture_tourism"
BOUNDARIES = ROOT / "data/boundaries/sri_lanka_districts.geojson"
OUTPUT = ROOT / "data/processed/tourism_infrastructure"
CELL_SIZE_M = 5000

ATTRACTION_GROUPS = {
    "heritage": "heritage_count",
    "religious_and_cultural": "religious_cultural_count",
    "nature": "nature_count",
    "recreation": "recreation_count",
    "wildlife": "wildlife_count",
}
SERVICE_GROUPS = {
    "accommodation": "accommodation_count",
    "food_and_drink": "food_drink_count",
    "travel_services": "travel_services_count",
    "travel_and_transport": "travel_transport_count",
}


def read_points(path: Path, dataset: str, to_projected: Transformer) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required file: {path}")
    frame = pd.read_csv(path, low_memory=False)
    required = {"overture_id", "place_name", "tourism_group", "latitude", "longitude"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{path.name} missing columns: {sorted(missing)}")
    total = len(frame)
    frame["latitude"] = pd.to_numeric(frame["latitude"], errors="coerce")
    frame["longitude"] = pd.to_numeric(frame["longitude"], errors="coerce")
    frame = frame[frame.latitude.between(5.5, 10.2) & frame.longitude.between(79.3, 82.3)].copy()
    frame["overture_id"] = frame.overture_id.fillna("").astype(str).str.strip()
    frame = frame[frame.overture_id.ne("")].drop_duplicates("overture_id", keep="first").copy()
    frame["tourism_group"] = frame.tourism_group.fillna("unknown").astype(str).str.strip()
    x, y = to_projected.transform(frame.longitude.to_numpy(), frame.latitude.to_numpy())
    frame["x_m"] = x
    frame["y_m"] = y
    frame["grid_x"] = (frame.x_m // CELL_SIZE_M).astype(int)
    frame["grid_y"] = (frame.y_m // CELL_SIZE_M).astype(int)
    frame["grid_id"] = frame.grid_x.astype(str) + "_" + frame.grid_y.astype(str)
    frame["dataset_role"] = dataset
    print(f"{dataset}: {total:,} input; {len(frame):,} unique valid-ID/coordinate records")
    return frame


def main():
    if not BOUNDARIES.is_file():
        raise FileNotFoundError(f"Missing Sri Lanka district geometry: {BOUNDARIES}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with BOUNDARIES.open(encoding="utf-8-sig") as f:
        features = json.load(f).get("features", [])
    polygons = [shape(f["geometry"]) for f in features if f.get("geometry")]
    if not polygons:
        raise ValueError("District GeoJSON contains no usable geometries")

    forward = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True)
    backward = Transformer.from_crs("EPSG:32644", "EPSG:4326", always_xy=True)
    country = unary_union(polygons)
    projected_country = transform(forward.transform, country)
    prepared = prep(projected_country)
    xmin, ymin, xmax, ymax = projected_country.bounds
    ix_min = math.floor(xmin / CELL_SIZE_M)
    iy_min = math.floor(ymin / CELL_SIZE_M)
    ix_max = math.ceil(xmax / CELL_SIZE_M)
    iy_max = math.ceil(ymax / CELL_SIZE_M)

    cells = []
    for ix in range(ix_min, ix_max):
        for iy in range(iy_min, iy_max):
            cell = box(ix * CELL_SIZE_M, iy * CELL_SIZE_M, (ix + 1) * CELL_SIZE_M, (iy + 1) * CELL_SIZE_M)
            if not prepared.intersects(cell):
                continue
            cx, cy = (ix + 0.5) * CELL_SIZE_M, (iy + 0.5) * CELL_SIZE_M
            lon, lat = backward.transform(cx, cy)
            # A cell can intersect the shoreline even when its centre is offshore.
            # Keep its centre for stable reproducibility; annotate the distinction.
            cells.append({
                "grid_id": f"{ix}_{iy}", "grid_x": ix, "grid_y": iy,
                "center_latitude": round(lat, 7), "center_longitude": round(lon, 7),
                "center_inside_boundary": bool(projected_country.covers(cell.centroid)),
                "boundary_overlap_fraction": round(cell.intersection(projected_country).area / cell.area, 6),
            })
    grid = pd.DataFrame(cells)
    if grid.empty:
        raise RuntimeError("Could not build grid from country geometry")

    att = read_points(SOURCE / "overture_attraction_candidates.csv", "attraction", forward)
    srv = read_points(SOURCE / "overture_tourist_services.csv", "service", forward)
    attr_group_names = sorted(att.tourism_group.unique().tolist())
    serv_group_names = sorted(srv.tourism_group.unique().tolist())
    print("Attraction groups:", ", ".join(attr_group_names))
    print("Service groups:", ", ".join(serv_group_names))

    for prefix, frame in (("attraction", att), ("service", srv)):
        counts = frame.groupby("grid_id", observed=True).size().rename(f"{prefix}_count")
        grid = grid.join(counts, on="grid_id")

    # All observed categories retained individually, with prefixes to avoid collisions.
    for prefix, frame in (("attraction", att), ("service", srv)):
        counts = pd.crosstab(frame.grid_id, frame.tourism_group)
        counts.columns = [f"{prefix}_group_{str(c).lower().replace(' ', '_').replace('-', '_')}_count" for c in counts.columns]
        grid = grid.join(counts, on="grid_id")

    feature_cols = [c for c in grid.columns if c.endswith("_count")]
    grid[feature_cols] = grid[feature_cols].fillna(0).astype("int64")
    grid["attraction_category_diversity"] = (grid[[c for c in feature_cols if c.startswith("attraction_group_")]] > 0).sum(axis=1)
    grid["service_category_diversity"] = (grid[[c for c in feature_cols if c.startswith("service_group_")]] > 0).sum(axis=1)
    grid["has_any_mapped_place"] = (grid.attraction_count + grid.service_count) > 0
    grid = grid.sort_values(["grid_x", "grid_y"]).reset_index(drop=True)
    grid_path = OUTPUT / "tourism_infrastructure_grid_5km.csv"
    grid.to_csv(grid_path, index=False, encoding="utf-8-sig")

    # Record-to-grid assignments for investigation and dashboard drill-down.
    assignment_cols = ["grid_id", "overture_id", "place_name", "tourism_group", "latitude", "longitude", "dataset_role"]
    assignments = pd.concat([att[assignment_cols], srv[assignment_cols]], ignore_index=True)
    valid_ids = set(grid.grid_id)
    assignments = assignments[assignments.grid_id.isin(valid_ids)].copy()
    assignment_path = OUTPUT / "tourism_place_grid_assignments.csv"
    assignments.to_csv(assignment_path, index=False, encoding="utf-8-sig")

    summary = {
        "grid_projection": "EPSG:32644 (WGS84 / UTM zone 44N)",
        "cell_size_m": CELL_SIZE_M,
        "boundary_source": str(BOUNDARIES.relative_to(ROOT)),
        "attraction_source": str((SOURCE / "overture_attraction_candidates.csv").relative_to(ROOT)),
        "service_source": str((SOURCE / "overture_tourist_services.csv").relative_to(ROOT)),
        "grid_cells_intersecting_country": len(grid),
        "grid_cells_with_any_mapped_places": int(grid.has_any_mapped_place.sum()),
        "empty_grid_cells": int((~grid.has_any_mapped_place).sum()),
        "attraction_records_read_unique": len(att),
        "service_records_read_unique": len(srv),
        "assigned_records": len(assignments),
        "unassigned_records": len(att) + len(srv) - len(assignments),
        "feature_columns": feature_cols + ["attraction_category_diversity", "service_category_diversity"],
        "observed_attraction_groups": attr_group_names,
        "observed_service_groups": serv_group_names,
        "limitations": [
            "POI records are provisional and have not been independently verified.",
            "Boundary-intersecting coastal cell centres may fall offshore.",
            "Counts reflect mapped POI coverage, not visitors, tourism demand, revenue, service quality, or operating status.",
            "Input may contain duplicate or misclassified records; no geographic record was automatically removed as a suspected duplicate.",
            "Spatial grid profiles may correlate with general urban density and mapping completeness.",
            "Model features should be audited for skew, scaling, leakage and redundant total-versus-subcategory counts before training.",
            "Original 8,590-record clustering baseline is not modified.",
        ],
    }
    summary_path = OUTPUT / "tourism_infrastructure_grid_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"5 km cells intersecting Sri Lanka: {len(grid):,}")
    print(f"Cells with mapped POIs: {int(grid.has_any_mapped_place.sum()):,}")
    print(f"Cells without mapped POIs: {int((~grid.has_any_mapped_place).sum()):,}")
    print(f"Grid assignments: {len(assignments):,}; unassigned rows: {summary['unassigned_records']:,}")
    print(f"Grid: {grid_path}")
    print(f"Assignments: {assignment_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
