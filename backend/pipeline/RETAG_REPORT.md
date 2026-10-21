# Aspect re-tagging report

**What changed:** `tag_aspects.py` used to tag a review if a keyword appeared anywhere as a substring, so `"bus" in "business"` counted as a match. It now uses word-boundary regexes. Words that are ambiguous on their own only count inside a phrase ("too many people", "long queue", "by train", "far from"). Each keyword choice is explained in the comment block at the top of `tag_aspects.py`.

**How it was applied:** `retag_scored_data.py` re-ran the new tagger on `Clean_Review_Text` in `backend/ai_scored_data.csv` and rewrote only `Mentioned_Aspects`. All other columns are byte-for-byte unchanged, including the SBERT `Base_Reality_Score`. `destination_summary.csv` was then regenerated with `aggregate_scores.py`.

## Per-aspect totals (13,943 reviews)

| Aspect | Before (substring) | After (word-boundary + phrases) | Change |
|---|---:|---:|---:|
| Crowding | 2,841 | 1,623 | −1,218 |
| Facilities | 1,479 | 2,028 | +549 |
| Commercialization | 2,474 | 3,684 | +1,210 |
| Accessibility | 5,285 | 3,934 | −1,351 |
| General (no aspect) | 5,565 | 5,944 | +379 |

"Before" counts come from the original `ai_scored_data.csv`, before any changes.

### Why each number moved

- **Crowding went down.** In the old tagging, 1,380 Crowding tags came only from the substrings "people" and/or "line". Most of those were "friendly people", "local people", "online" or "palm-lined".
- **Accessibility went down.** The main causes were "far" matching inside "safari", "farm", "so far" and "by far"; "road" inside "abroad" and "broad"; "train" inside "trainers"; "bus" inside "business"; and generic "walk along the beach". A walk along the beach is an activity, not an access issue, so walking now counts only in effort or distance phrases such as "walking distance", "steep walk" and "walk up". On the other side, "tuk-tuk" had never matched at all, because the cleaning step removed hyphens and the text says "tuktuk" or "tuk tuk". Both spellings now match.
- **Commercialization went up.** The new tagger adds money vocabulary specific to Sri Lankan sites: "entrance fee" and "entry fee", "rupees" and "LKR", "donation" at temples, "stalls", "touristy", "tourist trap" and "overpriced". It also drops the false matches "workshop" and "cornershop" from "shop".
- **Facilities went up.** The new tagger adds sanitation and upkeep vocabulary: "well maintained", "rubbish", "litter", "trash", "garbage", "car park", "restroom", "washroom", "signage", "benches" and "drinking water". "shade" and "broken" were dropped because they were ambiguous.

## Five previous false positives that are now fixed

| # | Destination (row) | Old tag | Trigger | Review excerpt |
|---|---|---|---|---|
| 1 | Arugam Bay (row 11) | Crowding | "people" | "Great restaurants too. The **people** are all very friendly and happy to provide information…" (this is about hospitality, not crowds) |
| 2 | Arugam Bay (row 0) | Accessibility | "bus" | "They also have s **bus**iness in Hikkaduwa when you head South." |
| 3 | Bentota Beach (row 384) | Accessibility | "road" | "Very long and b**road** strip of sand with warm and beautiful ocean…" |
| 4 | Arugam Bay (row 48) | Accessibility | "far" | "…good surfing places, National sa**far**i park, nature reserves, lakes…" |
| 5 | Kalutara Beach (row 917) | Crowding | "rush" | "…a strong mix of tiny pebbles, sand and c**rush**ed shells." |

Another fixed case: Arugam Bay (row 110), where "You can also get **train**ers here for surf" was tagged Accessibility. In every one of these rows, the listed keyword was the only reason for the old tag. The new tagger does not assign that aspect to any of them.

## Known limitations (to raise in the viva)

- The tagger detects whether a review talks about an aspect, not whether it is positive or negative about it. "Not crowded at all" still counts as a Crowding mention. Sentiment is reported separately through `Rating` (`positive_pct` in the API).
- Keyword rules are transparent and easy to audit, but they will miss paraphrases such as "we had the place to ourselves". A zero-shot or embedding-based aspect classifier would be the natural next step.
- The 3 destinations that are newly joined (Lipton's Seat, Lover's Leap Falls, St Clair's Falls) appear only after you rerun the full pipeline, including the SBERT step (`python run_pipeline.py`).
