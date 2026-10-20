"""TravelMind Step 16.4: descriptive research validation report.

Run from project root:
  python src/clustering/step16_4_validation_report.py
Optional:
  python src/clustering/step16_4_validation_report.py --input PATH --output-dir PATH

Uses reviewer-entered judgments only; does not independently authenticate sources.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / 'results/reports/hotspot_research_validation/manual_hotspot_validation_reviewed.csv'
DEFAULT_OUTPUT = PROJECT_ROOT / 'results/reports/hotspot_research_validation/step16_4_report'

CHOICES = {
    'is_real_tourist_attraction': {'yes', 'no', 'uncertain', 'pending'},
    'coordinates_correct': {'yes', 'no', 'uncertain', 'pending'},
    'duplicate_assessment': {'unique', 'duplicate', 'uncertain', 'pending'},
}

def normalize(value: object) -> str:
    if pd.isna(value):
        return 'pending'
    value = str(value).strip().lower()
    return value if value else 'pending'

def pct(n: int, total: int) -> float:
    return round(100 * n / total, 2) if total else 0.0

def escaped_md(value: object) -> str:
    return str(value).replace('|', '\\|').replace('\n', ' ')

def build_report(source_file: Path, out_dir: Path) -> None:
    if not source_file.is_file():
        raise FileNotFoundError(f'Reviewed CSV not found: {source_file}')
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(source_file, encoding='utf-8-sig', dtype={'attraction_id': str}, low_memory=False)
    required = {'attraction_id', 'attraction_name', 'district', 'dbscan_cluster', 'review_required',
                'suspected_duplicate', 'is_real_tourist_attraction', 'coordinates_correct',
                'duplicate_assessment', 'independent_evidence_url', 'reviewer_notes'}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError('Missing columns in review CSV: ' + ', '.join(missing))
    if df['attraction_id'].duplicated().any():
        print('WARNING: repeated attraction_id values in the review sample. Interpret record counts carefully.')
    n = len(df)
    for c, opts in CHOICES.items():
        df[c] = df[c].map(normalize)
        invalid = sorted(set(df[c]) - opts)
        if invalid:
            raise ValueError(f'Unexpected values in {c}: {invalid}. Allowed: {sorted(opts)}')
    df['has_evidence_url'] = df['independent_evidence_url'].fillna('').astype(str).str.strip().str.match(r'^https?://', case=False)
    df['review_flagged'] = df['review_required'].map(normalize).eq('yes')
    df['duplicate_flagged'] = df['suspected_duplicate'].map(normalize).eq('yes')
    df['cluster_label'] = df['dbscan_cluster'].fillna(-1).astype(str).str.replace(r'\.0$', '', regex=True)
    df['cluster_label'] = df['cluster_label'].replace({'-1': 'noise (-1)'})

    # Overall field-level distributions, including unresolved cases.
    summary = []
    descriptions = {'is_real_tourist_attraction': 'Tourism relevance',
                    'coordinates_correct': 'Coordinate accuracy',
                    'duplicate_assessment': 'Duplicate assessment'}
    for col, label in descriptions.items():
        for status in sorted(CHOICES[col]):
            count = int((df[col] == status).sum())
            summary.append({'assessment': label, 'status': status, 'count': count,
                            'percentage_of_sample': pct(count, n)})
    overall = pd.DataFrame(summary)
    overall.to_csv(out_dir / 'review_status_summary.csv', index=False)

    # Per-cluster descriptive audit; small sample groups should not be interpreted as population rates.
    group_rows = []
    for label, part in df.groupby('cluster_label', sort=True):
        m = len(part)
        group_rows.append({
            'dbscan_cluster': label,
            'sample_records': m,
            'tourism_yes': int(part['is_real_tourist_attraction'].eq('yes').sum()),
            'tourism_no': int(part['is_real_tourist_attraction'].eq('no').sum()),
            'tourism_uncertain_or_pending': int(part['is_real_tourist_attraction'].isin(['uncertain','pending']).sum()),
            'coordinate_yes': int(part['coordinates_correct'].eq('yes').sum()),
            'coordinate_no': int(part['coordinates_correct'].eq('no').sum()),
            'duplicate_confirmed': int(part['duplicate_assessment'].eq('duplicate').sum()),
            'review_flagged': int(part['review_flagged'].sum()),
            'suspected_duplicate': int(part['duplicate_flagged'].sum()),
            'evidence_urls_recorded': int(part['has_evidence_url'].sum()),
        })
    clusters = pd.DataFrame(group_rows).sort_values('sample_records', ascending=False)
    clusters.to_csv(out_dir / 'sample_cluster_review_summary.csv', index=False)

    districts = df.groupby('district', dropna=False).agg(
        sample_records=('attraction_id', 'size'),
        tourism_yes=('is_real_tourist_attraction', lambda s: int(s.eq('yes').sum())),
        tourism_no=('is_real_tourist_attraction', lambda s: int(s.eq('no').sum())),
        evidence_urls_recorded=('has_evidence_url', 'sum'),
    ).reset_index().sort_values('sample_records', ascending=False)
    districts.to_csv(out_dir / 'sample_district_review_summary.csv', index=False)

    concerns = df[(df['is_real_tourist_attraction'].isin(['uncertain','pending'])) |
                  (df['coordinates_correct'].isin(['uncertain','pending'])) |
                  (df['duplicate_assessment'].isin(['uncertain','pending']))].copy()
    concerns[['attraction_id', 'attraction_name', 'district', 'dbscan_cluster',
              'is_real_tourist_attraction', 'coordinates_correct', 'duplicate_assessment',
              'independent_evidence_url', 'reviewer_notes']].to_csv(
                  out_dir / 'unresolved_validation_records.csv', index=False, encoding='utf-8-sig')

    yes = int(df['is_real_tourist_attraction'].eq('yes').sum())
    no = int(df['is_real_tourist_attraction'].eq('no').sum())
    uncertain = int(df['is_real_tourist_attraction'].isin(['uncertain','pending']).sum())
    coord_yes = int(df['coordinates_correct'].eq('yes').sum())
    dupe_confirmed = int(df['duplicate_assessment'].eq('duplicate').sum())
    evidence = int(df['has_evidence_url'].sum())
    lines = [
        '# TravelMind – Step 16.4 Research Validation Report',
        '',
        f'**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        f'**Input:** `{source_file.name}`',
        f'**Sample records:** {n}',
        '',
        '## 1. Purpose and method',
        '',
        'This is a **descriptive audit of reviewer-entered assessments** in a sample of '
        'OpenStreetMap-derived candidate tourism locations. It does not independently '
        'verify the reviewer’s cited sources, establish tourist visitation, or measure tourism potential.',
        '',
        'Three separate dimensions are recorded: tourism relevance, coordinate accuracy, '
        'and duplicate status. A missing or uncertain judgment is **not** equivalent to a negative judgment.',
        '',
        '## 2. Tourism relevance assessments',
        '',
        '| Judgment | Sample records | Percentage of sample |',
        '|---|---:|---:|',
        f'| Yes (reviewer-assessed) | {yes} | {pct(yes,n):.2f}% |',
        f'| No (reviewer-assessed) | {no} | {pct(no,n):.2f}% |',
        f'| Uncertain or pending | {uncertain} | {pct(uncertain,n):.2f}% |',
        '',
        f'{evidence} records contain a syntactically valid HTTP(S) evidence URL. '
        'The presence of a link alone does not demonstrate that its content supports the precise claim.',
        '',
        f'**Do not report {yes}/{n} ({pct(yes,n):.2f}%) as dataset tourism accuracy.** '
        'This fraction counts affirmative judgments among all sampled records, including unresolved cases; '
        'the sample selection is not established as representative of all 8,590 records.',
        '',
        '## 3. Location and duplicate assessments',
        '',
        f'- Coordinate accuracy marked `yes`: **{coord_yes}/{n}**.',
        f'- Duplicate assessment marked `duplicate`: **{dupe_confirmed}/{n}**.',
        f'- Originally flagged as possible duplicates: **{int(df["duplicate_flagged"].sum())}/{n}**.',
        f'- Originally marked `review_required=yes`: **{int(df["review_flagged"].sum())}/{n}**.',
        '',
        'An OSM `suspected_duplicate=yes` flag is a screening signal, not independent confirmation. '
        'Avoid converting unresolved coordinate or duplicate judgments into positive or negative cases.',
        '',
        '## 4. Sample composition by DBSCAN cluster',
        '',
        '| DBSCAN group | Sampled records | Tourism yes | Tourism no | Unresolved tourism |',
        '|---|---:|---:|---:|---:|',
    ]
    for _, row in clusters.head(15).iterrows():
        lines.append(f'| {escaped_md(row["dbscan_cluster"])} | {int(row["sample_records"])} | '
                     f'{int(row["tourism_yes"])} | {int(row["tourism_no"])} | '
                     f'{int(row["tourism_uncertain_or_pending"])} |')
    lines += [
        '',
        '**Caution:** Counts above describe reviewed sample entries, not estimated cluster-wide '
        'tourism relevance rates. A stratified or probability sampling plan and more independently '
        'resolved cases are needed to estimate rates with uncertainty intervals.',
        '',
        '## 5. Interpretation and limitations',
        '',
        '1. These records were derived from OpenStreetMap and are not all verified tourist attractions.',
        '2. Reviewer judgments and URLs have not been independently authenticated by this script.',
        '3. An ordinary school, religious building, or settlement may be geographically real without '
        'meeting the project’s definition of a tourist attraction.',
        '4. Reviewing a name or location does not automatically confirm a particular attraction ID.',
        '5. Sampling and unresolved-case bias prevent generalization to the full database.',
        '6. DBSCAN detects spatial concentrations of mapped features, not tourist popularity or demand.',
        '',
        '## 6. Recommended research actions',
        '',
        '1. Resolve uncertainty using specific, independent, place-level evidence; record access dates and rationale.',
        '2. Inspect OSM tags and coordinates for records suspected to be miscoded schools or generic places.',
        '3. Verify near-identical attraction records using original OSM objects before deduplicating.',
        '4. Reassess hotspot candidate quality after a documented cleaning pass, keeping original outputs for comparison.',
        '5. Report sensitivity to DBSCAN `eps` and `min_samples` as an empirical limitation.',
        '6. Implement AHP/TPI only when independent tourism criteria and justified weights are available.',
        '',
        '## 7. Generated files',
        '',
        '- `review_status_summary.csv` – counts for all review fields.',
        '- `sample_cluster_review_summary.csv` – sample results grouped by saved DBSCAN cluster.',
        '- `sample_district_review_summary.csv` – sample district composition.',
        '- `unresolved_validation_records.csv` – records needing further review.',
        '- `step16_4_validation_report.md` – this report.',
        '',
    ]
    (out_dir / 'step16_4_validation_report.md').write_text('\n'.join(lines), encoding='utf-8')
    print('\nTRAVELMIND - STEP 16.4 REPORT')
    print('=' * 48)
    print('Sample records:', n)
    print('Tourism relevance yes:', yes)
    print('Tourism relevance no:', no)
    print('Tourism relevance unresolved:', uncertain)
    print('Evidence URLs recorded (not verified):', evidence)
    print('Coordinate confirmations:', coord_yes)
    print('Confirmed duplicates:', dupe_confirmed)
    print('Saved reports to:', out_dir)
    print('NOTE: This is a descriptive sample report, not a population accuracy estimate.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build_report(args.input, args.output_dir)
