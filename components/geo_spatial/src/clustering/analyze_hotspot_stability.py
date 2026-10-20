"""TravelMind: compare geographically persistent DBSCAN attraction concentrations.

Run from the *inner* TravelMind project root:
    python src/clustering/analyze_hotspot_stability.py

Uses Step 17 baseline, conservative and strict datasets / DBSCAN labels.
Never changes the input CSVs. Cluster IDs are NOT assumed comparable between runs.
"""
from pathlib import Path
import math
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'results' / 'reports' / 'step17_cleaning_comparison'
OUTPUT = ROOT / 'results' / 'reports' / 'hotspot_stability_analysis'
EARTH_RADIUS_KM = 6371.0088

REQUIRED = ['attraction_id', 'latitude', 'longitude', 'district', 'attraction_name',
            'review_required', 'suspected_duplicate', 'tourism_category']
STRATEGIES = ('baseline', 'conservative', 'strict')


def true_flag(s):
    return s.fillna('').astype(str).str.strip().str.casefold().isin(['true', 'yes', '1'])


def read_models(strategy):
    ds_path = SOURCE / f'{strategy}_dataset.csv'
    lbl_path = SOURCE / f'{strategy}_model_labels.csv'
    if not ds_path.is_file() or not lbl_path.is_file():
        raise FileNotFoundError(f'Missing Step 17 output: {ds_path} or {lbl_path}')
    data = pd.read_csv(ds_path, low_memory=False)
    labels = pd.read_csv(lbl_path, low_memory=False)
    missing = set(REQUIRED) - set(data.columns)
    if missing:
        raise ValueError(f'{ds_path.name} is missing {sorted(missing)}')
    if not {'attraction_id', 'dbscan_cluster_experiment'}.issubset(labels.columns):
        raise ValueError(f'{lbl_path.name} needs attraction_id and dbscan_cluster_experiment')
    if data.attraction_id.isna().any() or data.attraction_id.duplicated().any():
        raise ValueError(f'Duplicate/missing attraction_id in {ds_path.name}')
    if labels.attraction_id.isna().any() or labels.attraction_id.duplicated().any():
        raise ValueError(f'Duplicate/missing attraction_id in {lbl_path.name}')
    combined = data.merge(labels[['attraction_id', 'dbscan_cluster_experiment']],
                          on='attraction_id', how='left', validate='one_to_one')
    if combined.dbscan_cluster_experiment.isna().any():
        raise ValueError(f'Missing model labels for {strategy}')
    combined['dbscan_cluster_experiment'] = pd.to_numeric(
        combined['dbscan_cluster_experiment'], errors='raise').astype(int)
    if strategy == 'baseline':
        for c in ['latitude', 'longitude']:
            combined[c] = pd.to_numeric(combined[c], errors='coerce')
        if combined[['latitude', 'longitude']].isna().any().any():
            raise ValueError('Baseline contains missing coordinates')
    return combined


def angular_distance_km(latitudes, longitudes, center_lat, center_lon):
    a, b = np.radians(np.asarray(latitudes, dtype=float)), np.radians(np.asarray(longitudes, dtype=float))
    c, d = np.radians(float(center_lat)), np.radians(float(center_lon))
    h = np.sin((a - c) / 2)**2 + np.cos(a) * np.cos(c) * np.sin((b - d) / 2)**2
    return EARTH_RADIUS_KM * 2 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def area_summary(group):
    lat = group.latitude.to_numpy(dtype=float)
    lon = group.longitude.to_numpy(dtype=float)
    center_lat, center_lon = float(np.mean(lat)), float(np.mean(lon))
    distances = angular_distance_km(lat, lon, center_lat, center_lon)
    districts = group.district.fillna('Unknown').astype(str).str.strip().replace('', 'Unknown')
    main_district = districts.value_counts().index[0]
    return {
        'main_district': main_district,
        'district_count': int(districts.nunique()),
        'district_names': '; '.join(districts.value_counts().index[:6]),
        'center_latitude': round(center_lat, 6),
        'center_longitude': round(center_lon, 6),
        'median_radius_km': round(float(np.median(distances)), 2),
        'p90_radius_km': round(float(np.percentile(distances, 90)), 2),
        'max_radius_km': round(float(np.max(distances)), 2),
        'review_flag_pct': round(100 * float(true_flag(group.review_required).mean()), 2),
        'suspected_duplicate_pct': round(100 * float(true_flag(group.suspected_duplicate).mean()), 2),
        'distinct_names': int(group.attraction_name.fillna('').astype(str).str.strip().str.casefold().nunique()),
    }


def compare_to_other(baseline_ids, other_labels, full_other_sizes, prefix):
    """Find overlap on attraction IDs; do not match numeric cluster IDs across runs."""
    n = len(baseline_ids)
    shared = other_labels.reindex(baseline_ids).dropna()
    retained = len(shared)
    clustered = shared[shared != -1]
    result = {
        f'{prefix}_retained_records': retained,
        f'{prefix}_retained_pct': round(100 * retained / n, 2),
        f'{prefix}_clustered_retained_records': len(clustered),
        f'{prefix}_clustered_pct_of_retained': round(100 * len(clustered) / retained, 2) if retained else 0.0,
        f'{prefix}_dominant_cluster_id': '',
        f'{prefix}_dominant_overlap_records': 0,
        f'{prefix}_dominant_overlap_pct_of_retained': 0.0,
        f'{prefix}_dominant_overlap_pct_of_baseline': 0.0,
        f'{prefix}_dominant_cluster_purity_pct': 0.0,
    }
    if len(clustered):
        counts = clustered.value_counts()
        cluster_id = int(counts.index[0])
        overlap = int(counts.iloc[0])
        group_size = int(full_other_sizes.loc[cluster_id])
        result.update({
            f'{prefix}_dominant_cluster_id': cluster_id,
            f'{prefix}_dominant_overlap_records': overlap,
            f'{prefix}_dominant_overlap_pct_of_retained': round(100 * overlap / retained, 2),
            f'{prefix}_dominant_overlap_pct_of_baseline': round(100 * overlap / n, 2),
            f'{prefix}_dominant_cluster_purity_pct': round(100 * overlap / group_size, 2),
        })
    return result


def assess(row):
    """Transparent review-priority rules, NOT a scientific tourism potential score."""
    warnings = []
    if row['p90_radius_km'] > 10 or row['district_count'] > 1:
        warnings.append('wide_or_multi_district')
    if row['review_flag_pct'] > 50:
        warnings.append('many_records_flagged')
    if row['strict_retained_pct'] < 40:
        warnings.append('large_fraction_excluded_in_strict')
    if row['strict_dominant_overlap_pct_of_retained'] < 60:
        warnings.append('strict_area_fragmented_or_noise')
    if row['strict_dominant_cluster_purity_pct'] < 60:
        warnings.append('strict_area_merged_with_other_areas')
    if row['baseline_records'] < 10:
        warnings.append('small_cluster')
    return ';'.join(warnings) if warnings else 'none_detected'


def main():
    models = {name: read_models(name) for name in STRATEGIES}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    baseline = models['baseline']
    other_lookup = {}
    for name in ['conservative', 'strict']:
        other = models[name]
        label_series = other.set_index('attraction_id')['dbscan_cluster_experiment']
        cluster_sizes = other.loc[other.dbscan_cluster_experiment >= 0, 'dbscan_cluster_experiment'].value_counts()
        other_lookup[name] = (label_series, cluster_sizes)

    rows = []
    points = []
    clustered = baseline[baseline.dbscan_cluster_experiment >= 0]
    for cluster_id, group in clustered.groupby('dbscan_cluster_experiment', sort=True):
        ids = group.attraction_id.tolist()
        result = {'baseline_cluster_id': int(cluster_id), 'baseline_records': len(group)}
        result.update(area_summary(group))
        for name, (labels, sizes) in other_lookup.items():
            result.update(compare_to_other(ids, labels, sizes, name))
        result['research_review_flags'] = assess(result)
        # Pragmatic screening only: retaining a sufficiently large stable subset,
        # but WITHOUT asserting tourism relevance or verified hotspot quality.
        result['stable_geographic_candidate'] = bool(
            result['baseline_records'] >= 10
            and result['strict_retained_records'] >= 5
            and result['strict_dominant_overlap_records'] >= 5
            and result['strict_dominant_overlap_pct_of_retained'] >= 60
            and result['strict_dominant_cluster_purity_pct'] >= 60
            and result['p90_radius_km'] <= 10
            and result['district_count'] == 1
        )
        result['area_display_label'] = f"{result['main_district']} attraction concentration {int(cluster_id)}"
        rows.append(result)

        # Record-level support for dashboard GIS and follow-up manual review.
        row_points = group[['attraction_id', 'attraction_name', 'district', 'tourism_category',
                            'latitude', 'longitude', 'review_required', 'suspected_duplicate', 'tourism_category']].copy()
        row_points.insert(0, 'baseline_cluster_id', int(cluster_id))
        for name, (labels, _) in other_lookup.items():
            row_points[f'{name}_dbscan_label'] = labels.reindex(row_points.attraction_id).to_numpy()
        row_points['remains_clustered_in_strict'] = row_points['strict_dbscan_label'].notna() & (row_points['strict_dbscan_label'] != -1)
        points.append(row_points)

    summary = pd.DataFrame(rows)
    summary = summary.sort_values(['stable_geographic_candidate', 'baseline_records'], ascending=[False, False])
    summary.to_csv(OUTPUT / 'hotspot_stability_summary.csv', index=False, encoding='utf-8-sig')
    pd.concat(points, ignore_index=True).to_csv(OUTPUT / 'hotspot_record_support.csv', index=False, encoding='utf-8-sig')
    review_columns = ['baseline_cluster_id', 'area_display_label', 'main_district',
                      'center_latitude', 'center_longitude', 'baseline_records',
                      'strict_retained_records', 'strict_dominant_overlap_pct_of_retained',
                      'strict_dominant_cluster_purity_pct', 'p90_radius_km', 'review_flag_pct',
                      'research_review_flags', 'stable_geographic_candidate']
    review = summary[review_columns].copy()
    review['tourism_relevance_verified'] = 'pending'
    review['independent_evidence_url'] = ''
    review['reviewer_notes'] = ''
    review.to_csv(OUTPUT / 'hotspot_manual_review_queue.csv', index=False, encoding='utf-8-sig')
    report = [
        '# TravelMind – Geographic hotspot stability screening', '',
        f'- Baseline clustered areas: **{len(summary)}**',
        f'- Stable geographic candidates under screening rules: **{int(summary.stable_geographic_candidate.sum())}**', '',
        '## Method',
        '- Matched records using `attraction_id`; DBSCAN numeric labels were never assumed comparable.',
        '- Each original DBSCAN cluster was compared with its largest-overlap cluster in the conservative and strict experimental partitions.',
        '- `dominant_overlap_pct_of_retained` measures how much of an original area\'s retained records stay together.',
        '- `dominant_cluster_purity_pct` measures how much of the new cluster comes from that original area.',
        '- Spatial radius is haversine distance to a simple latitude/longitude mean center; it is descriptive, not a formal polygon or optimal geographic center.',
        '- Screening rules: baseline >=10 records; >=5 retained and clustered in a matching strict group; overlap and purity >=60%; p90 radius <=10km; one district.',
        '- Thresholds are exploratory heuristics, **not validated tourism quality weights**.', '',
        '## Interpretation limits',
        '- A stable concentration of mapped OSM records is **not** evidence of visitor demand, destination quality, or tourism potential.',
        '- Neither `review_required=no` nor high strict-run survival means independent verification.',
        '- The strict experiment removed all review-flagged records (not necessarily incorrect locations).',
        '- Each area still requires independent attraction and coordinate validation.',
        '- Large DBSCAN clusters can merge multiple destinations; use smaller-scale exploration before tourist-facing display.', '',
        '## Example candidates (first 15 by screening and cluster size)',
        '```', review.head(15).to_string(index=False), '```',
    ]
    (OUTPUT / 'hotspot_stability_research_report.md').write_text('\n'.join(report), encoding='utf-8')
    print('\nTRAVELMIND – HOTSPOT STABILITY ANALYSIS')
    print('=' * 58)
    print('Baseline DBSCAN concentrations:', len(summary))
    print('Stable geographic candidates (screening only):', int(summary.stable_geographic_candidate.sum()))
    print('Flagged for further review:', int((summary.research_review_flags != 'none_detected').sum()))
    print('Original inputs unchanged: yes')
    print('Saved outputs to:', OUTPUT)
    print('\nLargest 10 baseline clusters:')
    print(summary.sort_values('baseline_records', ascending=False)[
        ['baseline_cluster_id', 'main_district', 'baseline_records',
         'strict_retained_pct', 'strict_dominant_overlap_pct_of_retained',
         'strict_dominant_cluster_purity_pct', 'p90_radius_km', 'stable_geographic_candidate']
    ].head(10).to_string(index=False))


if __name__ == '__main__':
    main()
