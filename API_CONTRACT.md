# TravelMind Component 03 — API contract (v2)

Base URL (dev): `http://127.0.0.1:8000`. All API routes live under `/api`.
Original v1 endpoints and fields are kept unchanged (backward compatible); v2 adds fields.

Number conventions: percentages are 0–100 floats rounded to 1 decimal. Ratings are 1–5 floats rounded to 2 decimals.
Aspect keys (fixed order): `Crowding`, `Facilities`, `Commercialization`, `Accessibility`.

## GET /api/health
`{"status": "ok", "destinations": 57, "reviews": 13943}`

## GET /api/destinations   (v1, unchanged)
`{"destinations": ["Arugam Bay", ...]}`  — sorted A–Z.

## GET /api/overview   (new)
```json
{
  "total_destinations": 57,
  "total_reviews": 13943,
  "avg_score": 53.2, "min_score": 38.6, "max_score": 64.1, "median_score": 52.8,
  "aspect_avg_pct": {"Crowding": 12.2, "Facilities": 15.5, "Commercialization": 25.4, "Accessibility": 28.9},
  "types": ["Beaches", "..."],
  "provinces": ["Central Province", "..."],
  "destinations": [
    {
      "name": "Galle Fort",
      "type": "Historic Sites", "province": "Southern Province", "district": "Galle", "city": "Galle",
      "total_reviews": 283,
      "score": 59.5,
      "percentile": 89.3,
      "rank": 7,
      "band": "spot_on",
      "avg_rating": 4.52,
      "positive_pct": 91.2,
      "aspects_pct": {"Crowding": 13.1, "Facilities": 8.8, "Commercialization": 44.5, "Accessibility": 56.9},
      "top_aspect": "Accessibility"
    }
  ]
}
```
- `percentile` = % of the other destinations with a strictly lower score.
- `rank` = 1 for highest score.
- `band`: `"spot_on"` (score > 60), `"unique_vibe"` (45 < score <= 60), `"authentic"` (<= 45). Same thresholds as v1 Alignment_Status.
- `positive_pct` = % of that destination's reviews with Rating >= 4.
- `aspects_pct[a]` = % of that destination's reviews tagged with aspect a.
- `aspect_avg_pct[a]` = mean over destinations of `aspects_pct[a]` (same averaging as `avg_score`).
- `top_aspect` = aspect with highest `aspects_pct / aspect_avg_pct` ratio.
- Examples in this file are illustrative; real values come from the data. Ties share a rank.

## GET /api/destination/{destination_name}
Matching: case-insensitive exact match first; otherwise literal (non-regex) substring match, choosing the most-reviewed match. 404 `{"detail": "..."}` if none.

v1 fields (unchanged names/meaning): `Location_Name, Total_Reviews, Average_Reality_Score, Crowding_Mentions, Facilities_Mentions, Commercialization_Mentions, Accessibility_Mentions, Marketing_Promise, Best_Reality_Review, Alignment_Status, Recommendations` (list of markdown strings).

v2 additions:
```json
{
  "Location_Type": "Historic Sites", "Province": "...", "District": "...", "City": "...",
  "Score_Percentile": 89.3, "Score_Rank": 7, "Score_Band": "spot_on",
  "Dataset_Avg_Score": 53.2,
  "Average_Rating": 4.52, "Positive_Pct": 91.2,
  "Best_Review_Title": "...", "Best_Review_Rating": 5, "Best_Review_Similarity": 78.4,
  "Score_Distribution": [ {"bin": "30-40", "count": 12}, ... ],
  "Aspects": [
    {
      "key": "Crowding",
      "mentions": 104,
      "share_pct": 36.5,
      "dataset_avg_pct": 20.4,
      "relative": "above",
      "positive_pct": 84.6,
      "snippet": {"text": "...", "rating": 5, "title": "..."}
    }
  ],
  "Tips": [
    {"aspect": "Crowding", "icon": "sunrise", "title": "A popular favourite", "body": "plain text, no markdown"},
    {"aspect": null, "icon": "sparkles", "title": "Its own unique character", "body": "..."}
  ]
}
```
- `Score_Distribution`: histogram of per-review similarity (0–100) in 10-point bins "0-10"…"90-100" (negative values clipped to 0).
- `relative`: `"above"` if share_pct >= 1.25 × dataset_avg_pct, `"below"` if <= 0.75 ×, else `"typical"`.
- `positive_pct`: % of reviews mentioning that aspect that have Rating >= 4 (null if mentions == 0).
- `snippet`: one short, real review sentence-window (<= 280 chars) mentioning that aspect, preferring Rating >= 4 and highest Helpful_Votes; null if none. Text is real review text, only trimmed (add "…" when trimmed).
- `Tips`: positive, constructive. Always 2–4 items. Triggered by `relative == "above"` per aspect (not raw counts), plus a fallback "hidden gem"/"peaceful" tip when Crowding is "below". Icons from: `sunrise, leaf, bag, boot, backpack, sparkles, camera, map`.
- `Alignment_Status` keeps the original v1 wording for compatibility; the UI shows its own, more precise band descriptions.
- Tone rule: no negative/alarming wording anywhere ("warning", "avoid", "scam", "bad", "risk"…).

## GET /api/compare?a={name}&b={name}
`{"a": <destination object>, "b": <destination object>}` — same shape as /api/destination.
