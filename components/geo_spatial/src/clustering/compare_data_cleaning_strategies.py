"""TravelMind Step 17: baseline / conservative / strict clustering experiment.

Run from project root:
    python src/clustering/step17_compare_cleaning_strategies.py

No original dataset or model file is overwritten.
All CSVs created by this script are experimental research outputs.
"""
from pathlib import Path
import json
import re
import warnings

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score, davies_bouldin_score

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / 'data/processed/travelmind_combined_clusters.csv'
REVIEW = ROOT / 'results/reports/hotspot_research_validation/manual_hotspot_validation_reviewed.csv'
OUT = ROOT / 'results/reports/step17_cleaning_comparison'
OUT.mkdir(parents=True, exist_ok=True)

EARTH_RADIUS_KM = 6371.0088
DBSCAN_EPS_KM = 2.0
DBSCAN_MIN_SAMPLES = 5
KMEANS_K = 6
SEED = 42

# Only unmistakable placeholders; do not exclude ordinary religious sites,
# unverified entries, or suspected duplicates in the conservative experiment.
PLACEHOLDER_NAMES = {'', '#temple', 'unknown', 'unnamed', 'none', 'nan', 'null', 'n/a'}


def yes(value):
    return str(value).strip().casefold() in {'yes', 'true', '1'}


def normalized(value):
    return str(value).strip().casefold()


def load_inputs():
    if not INPUT.is_file():
        raise FileNotFoundError(f'Missing input CSV: {INPUT}')
    df = pd.read_csv(INPUT, low_memory=False)
    required = {'attraction_id', 'attraction_name', 'latitude', 'longitude',
                'district', 'projected_x_m', 'projected_y_m',
                'dbscan_cluster', 'kmeans_cluster', 'review_required'}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f'Input missing columns: {missing}')
    if df['attraction_id'].isna().any() or df['attraction_id'].duplicated().any():
        raise ValueError('attraction_id must be unique and non-null.')
    coords = ['latitude', 'longitude', 'projected_x_m', 'projected_y_m']
    for field in coords:
        df[field] = pd.to_numeric(df[field], errors='coerce')
    invalid = (df[coords].isna().any(axis=1)
               | ~df['latitude'].between(5.5, 10.2)
               | ~df['longitude'].between(79.4, 82.2))
    if invalid.any():
        raise ValueError(f'{invalid.sum()} invalid/missing coordinates. '
                         'Resolve separately before this controlled experiment.')
    df['attraction_id'] = df['attraction_id'].astype(str)
    return df


def review_decisions():
    if not REVIEW.exists():
        print('WARNING: reviewed sample not found; no manual decisions applied.')
        return {}, {}
    rev = pd.read_csv(REVIEW, low_memory=False).fillna('')
    if 'attraction_id' not in rev.columns:
        raise ValueError('Reviewed sample must contain attraction_id.')
    exclude, reasons = {}, {}
    for rec in rev.to_dict('records'):
        aid = str(rec['attraction_id']).strip()
        if not aid:
            continue
        r = []
        if normalized(rec.get('is_real_tourist_attraction', '')) == 'no':
            r.append('manual_review_tourism_relevance_no')
        if normalized(rec.get('duplicate_assessment', '')) in {'duplicate', 'confirmed_duplicate'}:
            r.append('manual_review_confirmed_duplicate')
        # An uncertain assessment is NOT a confirmed exclusion.
        if r:
            exclude[aid] = True
            reasons[aid] = ';'.join(sorted(set(r)))
    return exclude, reasons


def make_datasets(original):
    manually_excluded, manual_reasons = review_decisions()
    name_bad = original['attraction_name'].fillna('').map(normalized).isin(PLACEHOLDER_NAMES)
    manual_bad = original['attraction_id'].isin(manually_excluded)
    conservative_drop = name_bad | manual_bad
    strict_drop = original['review_required'].map(yes)

    # Strict deliberately tests the review flag only, so it is comparable to
    # the user-requested 4,523-record exclusion scenario. It can retain
    # placeholder names not flagged by the original review process.
    log = original[['attraction_id', 'attraction_name', 'district', 'review_required']].copy()
    log['excluded_conservative'] = conservative_drop
    log['excluded_strict'] = strict_drop
    log['conservative_reason'] = ''
    log.loc[name_bad, 'conservative_reason'] = 'obvious_placeholder_name'
    for ix, row in log.loc[manual_bad].iterrows():
        reason = manual_reasons.get(row['attraction_id'], '')
        prior = log.at[ix, 'conservative_reason']
        log.at[ix, 'conservative_reason'] = ';'.join(p for p in (prior, reason) if p)
    log['strict_reason'] = np.where(strict_drop, 'review_required_flag_yes', '')
    log.to_csv(OUT / 'record_inclusion_audit.csv', index=False, encoding='utf-8-sig')

    return {
        'baseline': original.copy(),
        'conservative': original.loc[~conservative_drop].copy(),
        'strict': original.loc[~strict_drop].copy(),
    }, log


def fit_models(data):
    # Existing projected feature coordinates provide metre-based Euclidean inputs
    # for K-Means; keep the same inputs and k for all three experiments.
    xy = data[['projected_x_m', 'projected_y_m']].to_numpy(dtype='float64')
    if len(data) < KMEANS_K:
        raise ValueError('Not enough rows for K-Means.')
    km = KMeans(n_clusters=KMEANS_K, random_state=SEED, n_init=20)
    klabels = km.fit_predict(xy)

    # Haversine expects radians and uses a geodesic neighbourhood radius.
    latlon_rad = np.radians(data[['latitude', 'longitude']].to_numpy(dtype='float64'))
    db = DBSCAN(eps=DBSCAN_EPS_KM / EARTH_RADIUS_KM,
                min_samples=DBSCAN_MIN_SAMPLES, metric='haversine', algorithm='ball_tree')
    dlabels = db.fit_predict(latlon_rad)
    return klabels, dlabels, xy, float(km.inertia_)


def metrics(data, klabels, dlabels, xy, inertia, name):
    labels = pd.DataFrame({'attraction_id': data['attraction_id'].to_numpy(),
                           'kmeans_cluster_experiment': klabels,
                           'dbscan_cluster_experiment': dlabels})
    labels.to_csv(OUT / f'{name}_model_labels.csv', index=False, encoding='utf-8-sig')
    # Preserve all source columns to make the three experimental subsets auditable.
    data.to_csv(OUT / f'{name}_dataset.csv', index=False, encoding='utf-8-sig')

    n = len(data)
    clustered = dlabels != -1
    n_db = len(set(dlabels) - {-1})
    largest = int(pd.Series(dlabels[clustered]).value_counts().max()) if clustered.any() else 0
    row = {'strategy': name, 'records': n,
           'excluded_from_baseline': 0,  # patched in main
           'kmeans_clusters': len(np.unique(klabels)),
           'dbscan_clusters': n_db,
           'dbscan_noise': int((~clustered).sum()),
           'dbscan_coverage_pct': round(100 * clustered.mean(), 2),
           'largest_dbscan_cluster_size': largest,
           'largest_cluster_pct_all_records': round(100 * largest / n, 2),
           'review_required_remaining': int(data['review_required'].map(yes).sum()),
           'suspected_duplicates_remaining': int(data.get('suspected_duplicate', pd.Series(index=data.index, dtype=object)).map(yes).sum()),
           'kmeans_inertia_projected_m2': round(inertia, 2),
           }
    # Deliberately do not compare inertia across unequal sample sizes as if
    # lower meant a better model. Silhouette samples are exploratory only.
    # Distances are in projected metres for K-Means.
    sample_n = min(1500, n)
    if sample_n > 10 and len(np.unique(klabels)) >= 2:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            row['kmeans_silhouette_sample'] = round(float(silhouette_score(
                xy, klabels, sample_size=sample_n, random_state=SEED)), 5)
    else:
        row['kmeans_silhouette_sample'] = np.nan
    # DBSCAN internal index not computed: noise exclusion and numerous spatial
    # clusters make direct comparisons with K-Means misleading.
    district = data.groupby('district', dropna=False).size().rename('record_count').reset_index()
    district.insert(0, 'strategy', name)
    return labels, row, district


def ari_shared(base_labels, other_labels, name):
    both = base_labels.merge(other_labels, on='attraction_id', validate='one_to_one', suffixes=('_baseline', '_new'))
    return {'strategy': name, 'shared_records': len(both),
            'kmeans_ari_vs_baseline_on_shared_records': round(float(adjusted_rand_score(
                both['kmeans_cluster_experiment_baseline'], both['kmeans_cluster_experiment_new'])), 5),
            'dbscan_ari_vs_baseline_on_shared_records': round(float(adjusted_rand_score(
                both['dbscan_cluster_experiment_baseline'], both['dbscan_cluster_experiment_new'])), 5)}


def main():
    base = load_inputs()
    datasets, inclusion = make_datasets(base)
    summaries, districts, labels = [], [], {}
    for name, df in datasets.items():
        print(f'Training {name:12s} : {len(df):,} records ...', flush=True)
        km, db, xy, inertia = fit_models(df)
        labels[name], summary, district = metrics(df, km, db, xy, inertia, name)
        summary['excluded_from_baseline'] = len(base) - len(df)
        summaries.append(summary)
        districts.append(district)
        print(f'  K-Means: {summary["kmeans_clusters"]} clusters | '
              f'DBSCAN: {summary["dbscan_clusters"]} clusters, '
              f'{summary["dbscan_noise"]} noise points', flush=True)

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUT / 'strategy_model_comparison.csv', index=False, encoding='utf-8-sig')
    pd.concat(districts, ignore_index=True).to_csv(
        OUT / 'strategy_district_distribution.csv', index=False, encoding='utf-8-sig')
    ari = [ari_shared(labels['baseline'], labels[s], s) for s in ['conservative', 'strict']]
    pd.DataFrame(ari).to_csv(OUT / 'strategy_cluster_stability.csv', index=False, encoding='utf-8-sig')

    # Refit baseline consistency check against saved labels. Non-identical
    # model settings (or software versions) can produce different partitions.
    baseline = datasets['baseline'][['attraction_id', 'kmeans_cluster', 'dbscan_cluster']].merge(
        labels['baseline'], on='attraction_id', validate='one_to_one')
    checks = {
        'baseline_kmeans_ari_vs_saved': float(adjusted_rand_score(
            baseline['kmeans_cluster'], baseline['kmeans_cluster_experiment'])),
        'baseline_dbscan_ari_vs_saved': float(adjusted_rand_score(
            baseline['dbscan_cluster'], baseline['dbscan_cluster_experiment'])),
    }
    with (OUT / 'baseline_reproducibility.json').open('w', encoding='utf-8') as f:
        json.dump(checks, f, indent=2)

    strict_excluded = int(inclusion['excluded_strict'].sum())
    conservative_excluded = int(inclusion['excluded_conservative'].sum())
    report = [
        '# Step 17 – Data-cleaning strategy comparison', '',
        '## Research method',
        f'- Source: `{INPUT.relative_to(ROOT)}` (original input preserved).',
        '- Baseline: all coordinate-valid records.',
        '- Conservative: exclude exact placeholder names and records explicitly assessed as '
        '`no` for tourism relevance or as `duplicate` in the reviewed sample. '
        'Unverified, flagged, and suspected-duplicate records are otherwise retained.',
        '- Strict: exclude every record marked `review_required = yes` in the original data. '
        'Unflagged does **not** mean independently verified.',
        f'- DBSCAN: haversine metric, eps={DBSCAN_EPS_KM} km, '
        f'min_samples={DBSCAN_MIN_SAMPLES}.',
        f'- K-Means: projected coordinate columns, k={KMEANS_K}, '
        f'random_state={SEED}, n_init=20.',
        '- Each strategy trains new models on its subset; originals are untouched.', '',
        '## Dataset exclusions',
        f'- Conservative: {conservative_excluded} rows excluded.',
        f'- Strict: {strict_excluded} rows excluded.', '',
        '## Model comparison',
        '```', summary_df.to_string(index=False), '```', '',
        '## Partition stability (ARI on shared attraction IDs)',
        '```', pd.DataFrame(ari).to_string(index=False), '```', '',
        '## Baseline reproducibility',
        f'- K-Means ARI compared with previously saved labels: {checks["baseline_kmeans_ari_vs_saved"]:.5f}',
        f'- DBSCAN ARI compared with previously saved labels: {checks["baseline_dbscan_ari_vs_saved"]:.5f}', '',
        '## Interpretation cautions',
        '- Filtering changes density and sample composition; more/fewer clusters is not '
        'evidence that one strategy has better tourism relevance.',
        '- ARI measures clustering agreement, not ground-truth tourism accuracy.',
        '- K-Means inertia and sampled silhouette may not be directly compared '
        'against historical experiments if inputs, scales, or sample populations differ.',
        '- False negatives are especially possible in strict filtering, because review flags '
        'signal uncertainty rather than confirmed errors.',
        '- External attraction verification and duplicate checks are still required.', '',
    ]
    (OUT / 'step17_research_report.md').write_text('\n'.join(report), encoding='utf-8')
    print('\n=== STEP 17 COMPARISON ===')
    print(summary_df[['strategy', 'records', 'excluded_from_baseline',
                      'dbscan_clusters', 'dbscan_noise', 'dbscan_coverage_pct']].to_string(index=False))
    print('\nBaseline reproducibility:', checks)
    print('Saved to:', OUT)


if __name__ == '__main__':
    main()
