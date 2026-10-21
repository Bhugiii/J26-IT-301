"""Prepare a transparent, manual-review package for TravelMind's screened DBSCAN areas.

Run from the TravelMind project root:
  python src/clustering/validate_shortlisted_hotspots.py

Reads existing source data only; never changes trained models or source CSVs.
No automated checks in this script establish independent tourism relevance,
coordinate correctness, or hotspot popularity.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def find_root(script: Path) -> Path:
    for directory in (script.parent, *script.parents):
        if (directory / 'data/processed/travelmind_combined_clusters.csv').is_file():
            return directory
    raise FileNotFoundError('Could not find project root with data/processed/travelmind_combined_clusters.csv')


def text(value: object) -> str:
    if pd.isna(value):
        return ''
    return str(value).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample-per-area', type=int, default=12, help='Maximum representative records per area for the review sample (default: 12)')
    args = parser.parse_args()
    if args.sample_per_area < 1:
        parser.error('--sample-per-area must be at least 1')

    root = find_root(Path(__file__).resolve())
    source_file = root / 'data/processed/travelmind_combined_clusters.csv'
    shortlist_file = root / 'results/reports/hotspot_stability_analysis/hotspot_quality_shortlist.csv'
    out = root / 'results/reports/hotspot_validation'
    out.mkdir(parents=True, exist_ok=True)
    if not shortlist_file.is_file():
        raise FileNotFoundError(f'Shortlist missing: {shortlist_file}')

    source = pd.read_csv(source_file, low_memory=False)
    shortlist = pd.read_csv(shortlist_file, low_memory=False)
    required_source = {'attraction_id','attraction_name','district','tourism_category','latitude','longitude','dbscan_cluster'}
    required_short = {'baseline_cluster_id','main_district','baseline_records'}
    for label, df, required in [('records',source,required_source),('shortlist',shortlist,required_short)]:
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f'Missing {label} columns: {sorted(missing)}')

    source['dbscan_cluster'] = pd.to_numeric(source['dbscan_cluster'], errors='coerce')
    shortlist['baseline_cluster_id'] = pd.to_numeric(shortlist['baseline_cluster_id'], errors='raise').astype(int)
    if shortlist['baseline_cluster_id'].duplicated().any():
        raise ValueError('Duplicate baseline_cluster_id values in shortlist; verify source')
    for c in ['attraction_id','attraction_name','district','tourism_category']:
        source[c] = source[c].fillna('').astype(str).str.strip()
    for c in ['latitude','longitude']:
        source[c] = pd.to_numeric(source[c], errors='coerce')
    for c in ['review_required','suspected_duplicate']:
        if c not in source:
            source[c] = 'unknown'
        source[c] = source[c].fillna('unknown').astype(str).str.strip().str.lower()

    ids = shortlist['baseline_cluster_id'].tolist()
    member = source[source['dbscan_cluster'].isin(ids)].copy()
    member['baseline_cluster_id'] = member['dbscan_cluster'].astype(int)
    member = member.merge(shortlist[['baseline_cluster_id','main_district','baseline_records']], on='baseline_cluster_id', how='left', validate='many_to_one')
    member['name_key'] = member['attraction_name'].str.casefold()
    member['is_name_repeated_in_area'] = member.duplicated(['baseline_cluster_id','name_key'], keep=False)
    member['coordinates_present'] = member['latitude'].between(5.5,10.2) & member['longitude'].between(79.3,82.3)

    all_columns = ['baseline_cluster_id','main_district','baseline_records','attraction_id','attraction_name',
                   'district','tourism_category','latitude','longitude','review_required',
                   'suspected_duplicate','is_name_repeated_in_area','coordinates_present']
    for extra in ('verification_status','ml_inclusion_status'):
        if extra in member:
            all_columns.append(extra)
    members_out = member[all_columns].sort_values(['baseline_cluster_id','district','attraction_name','attraction_id'])
    members_out.to_csv(out / 'shortlisted_area_all_records.csv', index=False, encoding='utf-8-sig')

    summaries = []
    review_samples = []
    for area in shortlist.to_dict('records'):
        cid = int(area['baseline_cluster_id'])
        group = member[member['baseline_cluster_id'].eq(cid)].copy()
        expected = int(float(area['baseline_records']))
        flagged = int(group['review_required'].eq('yes').sum())
        duplicates = int(group['suspected_duplicate'].eq('yes').sum())
        most_common = group['tourism_category'].replace('', 'Unknown').value_counts().head(3)
        summaries.append({
            'baseline_cluster_id':cid,
            'main_district':text(area['main_district']),
            'expected_baseline_records':expected,
            'matched_source_records':len(group),
            'member_count_matches_shortlist':len(group)==expected,
            'flagged_for_review':flagged,
            'suspected_duplicates':duplicates,
            'repeated_name_records':int(group['is_name_repeated_in_area'].sum()),
            'invalid_or_missing_coordinates':int((~group['coordinates_present']).sum()),
            'unique_attraction_names':int(group['name_key'].nunique()),
            'top_categories':' | '.join(f'{name}: {count}' for name,count in most_common.items()),
            'strict_retained_pct':area.get('strict_retained_pct',''),
            'review_flag_pct_from_screening':area.get('review_flag_pct',''),
            'p90_radius_km':area.get('p90_radius_km',''),
            'manual_area_verdict':'',
            'manual_area_evidence_links':'',
            'manual_area_notes':'',
        })
        # Prioritize flagged, duplicate, repeated-name, then category-diverse records.
        if not group.empty:
            group['_risk'] = (group['review_required'].eq('yes').astype(int)*4 +
                              group['suspected_duplicate'].eq('yes').astype(int)*3 +
                              group['is_name_repeated_in_area'].astype(int)*2 +
                              (~group['coordinates_present']).astype(int)*4)
            group = group.sort_values(['_risk','tourism_category','attraction_name','attraction_id'],
                                      ascending=[False,True,True,True])
            chosen = []
            seen_categories = set()
            # Take one from each category first to avoid an all-temple/all-mountain sample.
            for ix, row in group.iterrows():
                if row['tourism_category'] not in seen_categories:
                    chosen.append(ix)
                    seen_categories.add(row['tourism_category'])
                if len(chosen) >= args.sample_per_area:
                    break
            for ix in group.index:
                if len(chosen) >= args.sample_per_area:
                    break
                if ix not in chosen:
                    chosen.append(ix)
            sample = group.loc[chosen, all_columns].copy()
            sample['review_tourism_relevance'] = ''  # yes / no / uncertain
            sample['review_coordinate_correctness'] = ''  # yes / no / uncertain
            sample['review_duplicate_status'] = ''  # yes / no / uncertain
            sample['review_evidence_url'] = ''
            sample['review_notes'] = ''
            sample['reviewer'] = ''
            sample['review_date'] = ''
            review_samples.append(sample)

    summary = pd.DataFrame(summaries)
    summary.to_csv(out / 'shortlisted_area_validation_summary.csv', index=False, encoding='utf-8-sig')
    if review_samples:
        pd.concat(review_samples, ignore_index=True).to_csv(out / 'manual_attraction_validation_template.csv', index=False, encoding='utf-8-sig')
    else:
        pd.DataFrame(columns=all_columns+['review_tourism_relevance','review_coordinate_correctness',
                         'review_duplicate_status','review_evidence_url','review_notes','reviewer','review_date']).to_csv(
                             out / 'manual_attraction_validation_template.csv', index=False, encoding='utf-8-sig')

    disagreements = summary[~summary.member_count_matches_shortlist]
    report = [
        '# TravelMind — shortlisted area validation preparation',
        '',
        '## Scope',
        f'- Shortlisted geographic candidates: **{len(shortlist)}**',
        f'- Matched baseline DBSCAN member rows: **{len(member):,}**',
        f'- Manual review template records: **{sum(len(g) for g in review_samples)}**',
        f'- Area membership count discrepancies: **{len(disagreements)}**',
        '',
        'These are *preliminary geographic concentration candidates*, not independently verified tourist hotspots.',
        'No tourism relevance, coordinate correctness, tourist arrivals, or popularity has been independently verified by this script.',
        'The review sample is **purposefully selected for diversity and potential issues**, not a statistically representative random sample.',
        '',
        '## Review workflow',
        '1. Check the membership count match column before relying on the results. If there is a mismatch, investigate whether the source labels differ from the baseline run.',
        '2. Open `manual_attraction_validation_template.csv` and check each attraction against credible independent evidence.',
        '3. Fill tourism relevance (yes/no/uncertain), coordinate correctness (yes/no/uncertain), and duplicate status (yes/no/uncertain).',
        '4. Record an actual reviewed source URL, reviewer, date, and notes. Do not treat the presence of an URL as automatic evidence verification.',
        '5. Review all source members of concerning areas via `shortlisted_area_all_records.csv`.',
        '6. Decide area-level verdicts separately and document the evidence and limitations.',
        '',
        '## Screening-to-source membership checks',
        '',
        '| Cluster | District | Shortlist size | Source matches | Status |',
        '|---:|---|---:|---:|---|',
    ]
    for rec in summaries:
        report.append(f"| {rec['baseline_cluster_id']} | {rec['main_district']} | {rec['expected_baseline_records']} | {rec['matched_source_records']} | {'MATCH' if rec['member_count_matches_shortlist'] else 'CHECK'} |")
    report += ['', '## Files', '',
               '- `shortlisted_area_validation_summary.csv`: area-level automatic quality signals with blank manual verdict fields.',
               '- `shortlisted_area_all_records.csv`: all matching baseline DBSCAN members for the shortlisted areas.',
               '- `manual_attraction_validation_template.csv`: reviewable, deliberately chosen sample of up to the selected number per area.',
               '', 'Do not overwrite completed manual reviews by rerunning this script without first making a backup.', '']
    (out / 'shortlisted_area_validation_report.md').write_text('\n'.join(report), encoding='utf-8')
    print(f'Project: {root}')
    print(f'Shortlisted areas: {len(shortlist)}')
    print(f'Matched baseline cluster members: {len(member)}')
    print(f'Area membership mismatches: {len(disagreements)}')
    print(f'Manual review rows: {sum(len(g) for g in review_samples)}')
    print(f'Reports saved to: {out}')
    if len(disagreements):
        print('WARNING: Some baseline cluster sizes do not match current source. Inspect summary before claiming membership.')


if __name__ == '__main__':
    main()
