"""Generate a reproducible TravelMind hotspot validation summary.

Run from the project root:
    python src/clustering/generate_hotspot_validation_report.py

Reads existing research outputs only. Never modifies original training datasets or
manual reviews. Preliminary relevance evidence is NOT coordinate verification.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SHORTLIST = ROOT / 'results/reports/hotspot_stability_analysis/hotspot_quality_shortlist.csv'
AREA_SUMMARY = ROOT / 'results/reports/hotspot_validation/shortlisted_area_validation_summary.csv'
REVIEWS = ROOT / 'results/reports/hotspot_validation/manual_attraction_validation_working.csv'
MODEL = ROOT / 'results/reports/model_comparison.csv'
OUT = ROOT / 'results/reports/hotspot_validation/consolidated_report'


def load_csv(path: Path, required: set[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f'Missing required input: {path}')
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f'{path.name} missing columns: {sorted(missing)}')
    return df


def number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors='coerce')


def percentage(part: int, total: int) -> str:
    return f'{100 * part / total:.2f}%' if total else 'N/A'


def main() -> None:
    shortlist = load_csv(SHORTLIST, {'baseline_cluster_id', 'main_district', 'baseline_records',
                                     'strict_retained_pct', 'review_flag_pct', 'p90_radius_km'})
    areas = load_csv(AREA_SUMMARY, {'baseline_cluster_id', 'matched_source_records',
                                    'member_count_matches_shortlist'})
    reviews = load_csv(REVIEWS, {'baseline_cluster_id', 'attraction_id', 'review_tourism_relevance',
                                 'review_coordinate_correctness', 'review_duplicate_status'})

    if shortlist.baseline_cluster_id.duplicated().any():
        raise ValueError('Shortlist contains repeated baseline cluster IDs.')
    if areas.baseline_cluster_id.duplicated().any():
        raise ValueError('Area summary contains repeated baseline cluster IDs.')
    if reviews.attraction_id.duplicated().any():
        raise ValueError('Manual review contains repeated attraction IDs; inspect before reporting.')

    shortlist['baseline_records'] = number(shortlist['baseline_records'])
    areas['matched_source_records'] = number(areas['matched_source_records'])
    joined = shortlist.merge(areas, on='baseline_cluster_id', how='left', validate='one_to_one',
                             suffixes=('', '_audit'))
    if joined['matched_source_records'].isna().any():
        raise ValueError('Some shortlisted clusters have no area validation summary.')

    joined['membership_match_checked'] = (joined['baseline_records'] == joined['matched_source_records'])
    true_values = {'true', 'yes', '1'}
    joined['reported_membership_match'] = joined['member_count_matches_shortlist'].str.strip().str.casefold().isin(true_values)

    status_cols = {
        'review_tourism_relevance': 'relevance',
        'review_coordinate_correctness': 'coordinates',
        'review_duplicate_status': 'duplicates',
    }
    for col in status_cols:
        reviews[col] = reviews[col].str.strip().str.casefold().replace('', 'unreviewed')

    rows = []
    for item in joined.to_dict('records'):
        cluster = str(item['baseline_cluster_id'])
        sample = reviews[reviews.baseline_cluster_id.eq(cluster)]
        relevance = sample.review_tourism_relevance.value_counts()
        coords = sample.review_coordinate_correctness.value_counts()
        dupl = sample.review_duplicate_status.value_counts()
        rows.append({
            'baseline_cluster_id': cluster,
            'main_district': item['main_district'],
            'baseline_records': int(item['baseline_records']),
            'matched_source_records': int(item['matched_source_records']),
            'membership_match': bool(item['membership_match_checked'] and item['reported_membership_match']),
            'sampled_records': len(sample),
            'relevance_yes': int(relevance.get('yes', 0)),
            'relevance_no': int(relevance.get('no', 0)),
            'relevance_uncertain': int(relevance.get('uncertain', 0)),
            'relevance_unreviewed': int(relevance.get('unreviewed', 0)),
            'coordinate_correct': int(coords.get('correct', 0)),
            'coordinate_incorrect': int(coords.get('incorrect', 0)),
            'coordinate_uncertain_or_unreviewed': int(coords.get('uncertain', 0) + coords.get('unreviewed', 0)),
            'duplicate_confirmed': int(dupl.get('duplicate', 0)),
            'unique_confirmed': int(dupl.get('unique', 0)),
            'duplicate_uncertain_or_unreviewed': int(dupl.get('uncertain', 0) + dupl.get('unreviewed', 0)),
            'strict_retained_pct': item['strict_retained_pct'],
            'review_flag_pct_from_screening': item['review_flag_pct'],
            'p90_radius_km': item['p90_radius_km'],
        })

    result = pd.DataFrame(rows).sort_values(['main_district', 'baseline_cluster_id'])
    all_clusters = set(shortlist.baseline_cluster_id)
    orphan_reviews = reviews[~reviews.baseline_cluster_id.isin(all_clusters)]
    if not orphan_reviews.empty:
        raise ValueError(f'{len(orphan_reviews)} review rows refer to clusters outside the shortlist.')

    n_areas = len(result)
    n_members = int(result.baseline_records.sum())
    n_reviews = len(reviews)
    n_yes = int(result.relevance_yes.sum())
    n_no = int(result.relevance_no.sum())
    n_unknown = int(result.relevance_uncertain.sum())
    n_unreviewed = int(result.relevance_unreviewed.sum())
    n_matches = int(result.membership_match.sum())
    n_correct = int(result.coordinate_correct.sum())
    n_duplicates = int(result.duplicate_confirmed.sum())
    unexpected = {}
    allowed = {
        'review_tourism_relevance': {'yes','no','uncertain','unreviewed'},
        'review_coordinate_correctness': {'correct','incorrect','uncertain','unreviewed'},
        'review_duplicate_status': {'duplicate','unique','uncertain','unreviewed'},
    }
    for col, values in allowed.items():
        other = sorted(set(reviews[col]) - values)
        if other:
            unexpected[col] = other

    model_md = 'Model comparison CSV not present; no model metrics included.'
    if MODEL.exists():
        model_df = pd.read_csv(MODEL)
        safe_cols = [c for c in ('model', 'n_clusters', 'silhouette_score', 'davies_bouldin_index') if c in model_df.columns]
        if safe_cols:
            model_md = '\n'.join(['| ' + ' | '.join(safe_cols) + ' |', '|' + '|'.join(['---'] * len(safe_cols)) + '|'] + ['| ' + ' | '.join(str(row[col]) for col in safe_cols) + ' |' for _, row in model_df[safe_cols].iterrows()])

    date = datetime.now().strftime('%Y-%m-%d')
    lines = [
        '# TravelMind — Consolidated Hotspot Candidate Validation Report', '',
        f'Generated: {date}', '',
        '## Scope and provenance', '',
        'This is a summary of the existing baseline DBSCAN hotspot shortlist, source-membership audit, and manually recorded preliminary review statuses. It does not re-train models, review sources automatically, or assert that candidate areas represent actual tourist visits or demand.', '',
        '## Consistency checks', '',
        f'- Research-screened candidate areas: **{n_areas}**.',
        f'- Baseline records assigned to these areas (sum of area memberships): **{n_members:,}**.',
        f'- Area-membership checks passed: **{n_matches}/{n_areas}**.',
        f'- Review rows: **{n_reviews:,}** (manual sample; not a full audit of all mapped records).', '',
        '## Preliminary tourism-relevance review', '',
        f'- Evidence-supported `yes` in working CSV: **{n_yes}** ({percentage(n_yes,n_reviews)} of sampled records).',
        f'- `no`: **{n_no}**.',
        f'- `uncertain`: **{n_unknown}**.',
        f'- Blank/unreviewed: **{n_unreviewed}**.',
        f'- Coordinate-correct confirmations in working CSV: **{n_correct}**.',
        f'- Confirmed duplicate statuses in working CSV: **{n_duplicates}**.', '',
        '**Interpretation:** `yes` means the working file records support for a named place’s tourism or heritage relevance; it does not independently verify its coordinates, distinct OSM feature identity, accessibility, current operating status, or visitor demand. All evidence links and reviewer notes require source scrutiny. Uncertain does not mean incorrect.', '',
        '## Shortlisted-area review summary', '',
        '| District | DBSCAN ID | Members | Sample | Relevance yes | Uncertain | Membership OK |',
        '|---|---:|---:|---:|---:|---:|---|',
    ]
    for r in result.itertuples(index=False):
        lines.append(f'| {r.main_district} | {r.baseline_cluster_id} | {r.baseline_records} | {r.sampled_records} | {r.relevance_yes} | {r.relevance_uncertain} | {"Yes" if r.membership_match else "**NO**"} |')
    lines.extend(['', '## Existing model comparison', '', model_md, '',
                  '## Methodological limitations', '',
                  '1. Crowdsourced OSM features are provisional and can be mislabeled, missing, or represent parts of the same destination.',
                  '2. Cluster stability and geographic concentration do not establish tourism popularity or visitor counts.',
                  '3. Review samples are selected subsets. Do not extrapolate the supported proportion to all 8,590 records without a defensible probability sampling design.',
                  '4. Same-name, closely situated OSM nodes and ways need geometry-level inspection before being confirmed as duplicates.',
                  '5. A tourism relevance label is distinct from coordinate verification and accessibility.',
                  '6. AHP/Tourism Potential Index has not been calculated and is not inferred here.', '',
                  '## Recommended next steps', '',
                  '1. Preserve the original baseline dataset and preliminary review files.',
                  '2. Check evidence URLs, coordinate correctness, and OSM geometry for priority cases.',
                  '3. Test dashboard functionality separately (map styles, filtering, highlighting, navigation and missing tile services).',
                  '4. Report cluster stability, duplicate sensitivity and validation uncertainty as separate analyses.', '',
                  f'Unexpected status labels: {json.dumps(unexpected) if unexpected else "none"}.', '',
    ])
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / 'hotspot_validation_by_area.csv'
    md_path = OUT / 'hotspot_validation_research_report.md'
    json_path = OUT / 'validation_summary.json'
    result.to_csv(csv_path, index=False, encoding='utf-8-sig')
    md_path.write_text('\n'.join(lines), encoding='utf-8')
    json_path.write_text(json.dumps({
        'generated_date': date, 'shortlisted_areas': n_areas,
        'baseline_members': n_members, 'membership_checks_passed': n_matches,
        'review_rows': n_reviews, 'relevance_yes': n_yes, 'relevance_no': n_no,
        'relevance_uncertain': n_unknown, 'relevance_unreviewed': n_unreviewed,
        'coordinate_correct_confirmations': n_correct,
        'confirmed_duplicate_statuses': n_duplicates, 'unexpected_status_labels': unexpected,
    }, indent=2), encoding='utf-8')
    print(f'Shortlisted areas: {n_areas}')
    print(f'Baseline members: {n_members}')
    print(f'Membership checks passed: {n_matches}/{n_areas}')
    print(f'Sampled review rows: {n_reviews}')
    print(f'Relevance: yes={n_yes}, no={n_no}, uncertain={n_unknown}, unreviewed={n_unreviewed}')
    print(f'Coordinate correct={n_correct}; duplicates confirmed={n_duplicates}')
    print(f'Area CSV: {csv_path}')
    print(f'Research report: {md_path}')
    print(f'Summary JSON: {json_path}')
    if unexpected:
        print(f'WARNING: unrecognized review status values found: {unexpected}', file=sys.stderr)

if __name__ == '__main__':
    try:
        main()
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
