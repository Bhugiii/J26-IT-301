# TravelMind — shortlisted area validation preparation

## Scope
- Shortlisted geographic candidates: **18**
- Matched baseline DBSCAN member rows: **790**
- Manual review template records: **216**
- Area membership count discrepancies: **0**

These are *preliminary geographic concentration candidates*, not independently verified tourist hotspots.
No tourism relevance, coordinate correctness, tourist arrivals, or popularity has been independently verified by this script.
The review sample is **purposefully selected for diversity and potential issues**, not a statistically representative random sample.

## Review workflow
1. Check the membership count match column before relying on the results. If there is a mismatch, investigate whether the source labels differ from the baseline run.
2. Open `manual_attraction_validation_template.csv` and check each attraction against credible independent evidence.
3. Fill tourism relevance (yes/no/uncertain), coordinate correctness (yes/no/uncertain), and duplicate status (yes/no/uncertain).
4. Record an actual reviewed source URL, reviewer, date, and notes. Do not treat the presence of an URL as automatic evidence verification.
5. Review all source members of concerning areas via `shortlisted_area_all_records.csv`.
6. Decide area-level verdicts separately and document the evidence and limitations.

## Screening-to-source membership checks

| Cluster | District | Shortlist size | Source matches | Status |
|---:|---|---:|---:|---|
| 63 | Ampara | 22 | 22 | MATCH |
| 19 | Matara | 28 | 28 | MATCH |
| 66 | Matara | 76 | 76 | MATCH |
| 4 | Nuwara Eliya | 25 | 25 | MATCH |
| 58 | Ratnapura | 33 | 33 | MATCH |
| 45 | Nuwara Eliya | 31 | 31 | MATCH |
| 17 | Anuradhapura | 110 | 110 | MATCH |
| 32 | Nuwara Eliya | 45 | 45 | MATCH |
| 67 | Kurunegala | 53 | 53 | MATCH |
| 69 | Kandy | 27 | 27 | MATCH |
| 48 | Anuradhapura | 39 | 39 | MATCH |
| 39 | Matale | 47 | 47 | MATCH |
| 41 | Badulla | 46 | 46 | MATCH |
| 26 | Galle | 54 | 54 | MATCH |
| 35 | Kegalle | 35 | 35 | MATCH |
| 52 | Nuwara Eliya | 20 | 20 | MATCH |
| 36 | Polonnaruwa | 72 | 72 | MATCH |
| 108 | Ratnapura | 27 | 27 | MATCH |

## Files

- `shortlisted_area_validation_summary.csv`: area-level automatic quality signals with blank manual verdict fields.
- `shortlisted_area_all_records.csv`: all matching baseline DBSCAN members for the shortlisted areas.
- `manual_attraction_validation_template.csv`: reviewable, deliberately chosen sample of up to the selected number per area.

Do not overwrite completed manual reviews by rerunning this script without first making a backup.
