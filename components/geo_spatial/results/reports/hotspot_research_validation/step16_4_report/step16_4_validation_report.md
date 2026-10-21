# TravelMind – Step 16.4 Research Validation Report

**Generated:** 2026-10-18 00:08
**Input:** `manual_hotspot_validation_reviewed.csv`
**Sample records:** 75

## 1. Purpose and method

This is a **descriptive audit of reviewer-entered assessments** in a sample of OpenStreetMap-derived candidate tourism locations. It does not independently verify the reviewer’s cited sources, establish tourist visitation, or measure tourism potential.

Three separate dimensions are recorded: tourism relevance, coordinate accuracy, and duplicate status. A missing or uncertain judgment is **not** equivalent to a negative judgment.

## 2. Tourism relevance assessments

| Judgment | Sample records | Percentage of sample |
|---|---:|---:|
| Yes (reviewer-assessed) | 5 | 6.67% |
| No (reviewer-assessed) | 0 | 0.00% |
| Uncertain or pending | 70 | 93.33% |

5 records contain a syntactically valid HTTP(S) evidence URL. The presence of a link alone does not demonstrate that its content supports the precise claim.

**Do not report 5/75 (6.67%) as dataset tourism accuracy.** This fraction counts affirmative judgments among all sampled records, including unresolved cases; the sample selection is not established as representative of all 8,590 records.

## 3. Location and duplicate assessments

- Coordinate accuracy marked `yes`: **0/75**.
- Duplicate assessment marked `duplicate`: **0/75**.
- Originally flagged as possible duplicates: **10/75**.
- Originally marked `review_required=yes`: **57/75**.

An OSM `suspected_duplicate=yes` flag is a screening signal, not independent confirmation. Avoid converting unresolved coordinate or duplicate judgments into positive or negative cases.

## 4. Sample composition by DBSCAN cluster

| DBSCAN group | Sampled records | Tourism yes | Tourism no | Unresolved tourism |
|---|---:|---:|---:|---:|
| noise (-1) | 15 | 1 | 0 | 14 |
| 0 | 4 | 0 | 0 | 4 |
| 10 | 4 | 0 | 0 | 4 |
| 1 | 4 | 0 | 0 | 4 |
| 162 | 4 | 0 | 0 | 4 |
| 17 | 4 | 1 | 0 | 3 |
| 182 | 4 | 0 | 0 | 4 |
| 13 | 4 | 0 | 0 | 4 |
| 2 | 4 | 1 | 0 | 3 |
| 22 | 4 | 0 | 0 | 4 |
| 3 | 4 | 2 | 0 | 2 |
| 29 | 4 | 0 | 0 | 4 |
| 53 | 4 | 0 | 0 | 4 |
| 59 | 4 | 0 | 0 | 4 |
| 8 | 4 | 0 | 0 | 4 |

**Caution:** Counts above describe reviewed sample entries, not estimated cluster-wide tourism relevance rates. A stratified or probability sampling plan and more independently resolved cases are needed to estimate rates with uncertainty intervals.

## 5. Interpretation and limitations

1. These records were derived from OpenStreetMap and are not all verified tourist attractions.
2. Reviewer judgments and URLs have not been independently authenticated by this script.
3. An ordinary school, religious building, or settlement may be geographically real without meeting the project’s definition of a tourist attraction.
4. Reviewing a name or location does not automatically confirm a particular attraction ID.
5. Sampling and unresolved-case bias prevent generalization to the full database.
6. DBSCAN detects spatial concentrations of mapped features, not tourist popularity or demand.

## 6. Recommended research actions

1. Resolve uncertainty using specific, independent, place-level evidence; record access dates and rationale.
2. Inspect OSM tags and coordinates for records suspected to be miscoded schools or generic places.
3. Verify near-identical attraction records using original OSM objects before deduplicating.
4. Reassess hotspot candidate quality after a documented cleaning pass, keeping original outputs for comparison.
5. Report sensitivity to DBSCAN `eps` and `min_samples` as an empirical limitation.
6. Implement AHP/TPI only when independent tourism criteria and justified weights are available.

## 7. Generated files

- `review_status_summary.csv` – counts for all review fields.
- `sample_cluster_review_summary.csv` – sample results grouped by saved DBSCAN cluster.
- `sample_district_review_summary.csv` – sample district composition.
- `unresolved_validation_records.csv` – records needing further review.
- `step16_4_validation_report.md` – this report.
