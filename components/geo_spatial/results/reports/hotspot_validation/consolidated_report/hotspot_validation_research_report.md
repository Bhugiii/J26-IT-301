# TravelMind — Consolidated Hotspot Candidate Validation Report

Generated: 2026-10-19

## Scope and provenance

This is a summary of the existing baseline DBSCAN hotspot shortlist, source-membership audit, and manually recorded preliminary review statuses. It does not re-train models, review sources automatically, or assert that candidate areas represent actual tourist visits or demand.

## Consistency checks

- Research-screened candidate areas: **18**.
- Baseline records assigned to these areas (sum of area memberships): **790**.
- Area-membership checks passed: **18/18**.
- Review rows: **216** (manual sample; not a full audit of all mapped records).

## Preliminary tourism-relevance review

- Evidence-supported `yes` in working CSV: **7** (3.24% of sampled records).
- `no`: **0**.
- `uncertain`: **209**.
- Blank/unreviewed: **0**.
- Coordinate-correct confirmations in working CSV: **0**.
- Confirmed duplicate statuses in working CSV: **0**.

**Interpretation:** `yes` means the working file records support for a named place’s tourism or heritage relevance; it does not independently verify its coordinates, distinct OSM feature identity, accessibility, current operating status, or visitor demand. All evidence links and reviewer notes require source scrutiny. Uncertain does not mean incorrect.

## Shortlisted-area review summary

| District | DBSCAN ID | Members | Sample | Relevance yes | Uncertain | Membership OK |
|---|---:|---:|---:|---:|---:|---|
| Ampara | 63 | 22 | 12 | 4 | 8 | Yes |
| Anuradhapura | 17 | 110 | 12 | 3 | 9 | Yes |
| Anuradhapura | 48 | 39 | 12 | 0 | 12 | Yes |
| Badulla | 41 | 46 | 12 | 0 | 12 | Yes |
| Galle | 26 | 54 | 12 | 0 | 12 | Yes |
| Kandy | 69 | 27 | 12 | 0 | 12 | Yes |
| Kegalle | 35 | 35 | 12 | 0 | 12 | Yes |
| Kurunegala | 67 | 53 | 12 | 0 | 12 | Yes |
| Matale | 39 | 47 | 12 | 0 | 12 | Yes |
| Matara | 19 | 28 | 12 | 0 | 12 | Yes |
| Matara | 66 | 76 | 12 | 0 | 12 | Yes |
| Nuwara Eliya | 32 | 45 | 12 | 0 | 12 | Yes |
| Nuwara Eliya | 4 | 25 | 12 | 0 | 12 | Yes |
| Nuwara Eliya | 45 | 31 | 12 | 0 | 12 | Yes |
| Nuwara Eliya | 52 | 20 | 12 | 0 | 12 | Yes |
| Polonnaruwa | 36 | 72 | 12 | 0 | 12 | Yes |
| Ratnapura | 108 | 27 | 12 | 0 | 12 | Yes |
| Ratnapura | 58 | 33 | 12 | 0 | 12 | Yes |

## Existing model comparison

| model | n_clusters | silhouette_score | davies_bouldin_index |
|---|---|---|---|
| K-Means | 6 | 0.4855053619222449 | 0.6697637536961616 |
| DBSCAN | 225 | 0.3240562214726949 | 0.4482301230477037 |

## Methodological limitations

1. Crowdsourced OSM features are provisional and can be mislabeled, missing, or represent parts of the same destination.
2. Cluster stability and geographic concentration do not establish tourism popularity or visitor counts.
3. Review samples are selected subsets. Do not extrapolate the supported proportion to all 8,590 records without a defensible probability sampling design.
4. Same-name, closely situated OSM nodes and ways need geometry-level inspection before being confirmed as duplicates.
5. A tourism relevance label is distinct from coordinate verification and accessibility.
6. AHP/Tourism Potential Index has not been calculated and is not inferred here.

## Recommended next steps

1. Preserve the original baseline dataset and preliminary review files.
2. Check evidence URLs, coordinate correctness, and OSM geometry for priority cases.
3. Test dashboard functionality separately (map styles, filtering, highlighting, navigation and missing tile services).
4. Report cluster stability, duplicate sensitivity and validation uncertainty as separate analyses.

Unexpected status labels: none.
