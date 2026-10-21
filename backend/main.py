"""
TravelMind Component 03 - NLP-Based Destination Trust Engine (Reality Match API).

Run from the backend folder:   uvicorn main:app --reload
Spec: ../API_CONTRACT.md (v2, backward compatible with v1).

All data is loaded and every response object is precomputed once at startup;
requests only do a dictionary lookup / name match.
"""
from __future__ import annotations

import math
import os
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "pipeline"))
from tag_aspects import ASPECT_PATTERNS, ASPECTS, aspect_flags  # noqa: E402

SCORED_CSV = BASE_DIR / "ai_scored_data.csv"
DEFAULT_DIST_DIR = Path(os.environ.get("TRAVELMIND_FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
SNIPPET_MAX = 280

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_APOS_TABLE = str.maketrans({c: "'" for c in "’‘ʼ′´`\x92\x91"})


def _norm(name: str) -> str:
    """Case/whitespace/apostrophe-insensitive form of a destination name."""
    s = unicodedata.normalize("NFKC", str(name)).translate(_APOS_TABLE)
    return " ".join(s.split()).casefold()


def _norm_loose(name: str) -> str:
    return _norm(name).replace("'", "")


def _num(x, nd: int):
    """JSON-native rounded float, or None for NaN/None."""
    if x is None:
        return None
    x = float(x)
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x, nd)


def _pct(part, whole):
    return _num(100.0 * part / whole, 1) if whole else None


def _str(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return str(x)


def _band(score: float) -> str:
    if score > 60:
        return "spot_on"
    if score > 45:
        return "unique_vibe"
    return "authentic"


ALIGNMENT_STATUS = {  # v1 strings, unchanged
    "spot_on": "🌟 The marketing is spot on! What you see is exactly what you get.",
    "unique_vibe": "✨ A destination with its own unique vibe! Expect a mix of the serene marketing and a lively local atmosphere.",
    "authentic": "🌍 An authentic, bustling travel experience! Come with an open mind to enjoy the real local energy.",
}

# ---------------------------------------------------------------------------
# Snippets
# ---------------------------------------------------------------------------
# Words that make a snippet a poor fit for the "helpful local friend" tone.
# Snippets containing them are only used when nothing else is available.
_SNIPPET_AVOID = re.compile(
    r"\b(?:warn\w*|avoid\w*|scam\w*|bad|worst|risk\w*|danger\w*|dirty|filthy|terrible|awful|"
    r"horrible|rip\s?off|ripped|rude|waste|disappoint\w*|overpriced|hate|idiots?|stupid|"
    r"never|unsafe|disgust\w*|crap|sucks?|pathetic|annoy\w*|cheat\w*|beware|worse|poor|"
    r"problem\w*|unfortunate\w*|broken|challeng\w*|nightmare|chaos|chaotic)\b",
    re.IGNORECASE,
)
_SENT_END = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str):
    spans, start = [], 0
    for m in _SENT_END.finditer(text):
        spans.append((start, m.start()))
        start = m.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def extract_snippet(text: str, aspect: str):
    """Sentence window (<= 280 chars) around the first keyword of `aspect`.
    Real text only; '…' marks a cut made inside a sentence."""
    text = str(text).strip()
    m = ASPECT_PATTERNS[aspect].search(text)
    if not m:
        return None
    spans = _sentences(text)
    i = next((k for k, (s, e) in enumerate(spans) if s <= m.start() < e + 1), 0)
    s, e = spans[i]
    lo, hi = i, i
    # Grow very short windows with neighbouring sentences while they fit.
    while e - s < 100:
        grown = False
        if hi + 1 < len(spans) and spans[hi + 1][1] - s <= SNIPPET_MAX:
            hi += 1
            e = spans[hi][1]
            grown = True
        elif lo - 1 >= 0 and e - spans[lo - 1][0] <= SNIPPET_MAX:
            lo -= 1
            s = spans[lo][0]
            grown = True
        if not grown:
            break
    if e - s <= SNIPPET_MAX:
        return text[s:e].strip()
    # Sentence too long: cut a window around the match at word boundaries.
    budget = SNIPPET_MAX - 2  # room for up to two ellipses
    ws = max(s, m.start() - budget // 3)
    we = min(e, ws + budget)
    ws = max(s, we - budget)
    if ws > s:
        sp = text.find(" ", ws)
        ws = sp + 1 if 0 <= sp < m.start() else ws
    if we < e:
        sp = text.rfind(" ", ws, we)
        we = sp if sp > m.end() else we
    out = text[ws:we].strip()
    return ("…" if ws > s else "") + out + ("…" if we < e else "")


def pick_snippet(rows: pd.DataFrame, aspect: str):
    cands = []
    for r in rows.itertuples(index=False):
        snip = extract_snippet(r.Clean_Review_Text, aspect)
        if not snip:
            continue
        rating = int(r.Rating)
        cands.append((
            bool(_SNIPPET_AVOID.search(snip)),   # prefer friendly wording
            rating < 4,                          # prefer Rating >= 4
            not (80 <= len(snip) <= 260),        # prefer complete, readable windows
            -min(int(r.Helpful_Votes), 3),       # some community endorsement helps, capped
            -float(r.Base_Reality_Score),        # then most on-topic w.r.t. the promise
            -rating,
            snip, rating, _str(r.Title),
        ))
    if not cands:
        return None
    best = min(cands, key=lambda c: c[:6])
    return {"text": best[6], "rating": best[7], "title": best[8]}


# ---------------------------------------------------------------------------
# Contrasting review (explains WHY a destination's Reality Match Score is what it is)
# ---------------------------------------------------------------------------
def _has_aspect(value, aspect: str) -> bool:
    """Case- and whitespace-insensitive token match on a Mentioned_Aspects value
    such as "Crowding, Accessibility". Missing values (None/NaN) never match."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return False
    target = aspect.strip().lower()
    return any(tok.strip().lower() == target for tok in str(value).split(","))


def _safe_count(x) -> int:
    """Aspect mention count robust to None/NaN/strings."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0
    return 0 if math.isnan(v) else int(v)


def select_contrasting_review(dest_reviews: pd.DataFrame, mention_counts: dict):
    """Pick the review that best explains the gap between marketing and reality.

    1. Dominant aspect = the aspect with the highest mention count (ties resolved in
       ASPECTS order; None when every count is 0).
    2. Keep only reviews whose Mentioned_Aspects contains the dominant aspect.
    3. Choose the review with the LOWEST Base_Reality_Score, unless that review is a
       statistical outlier within the filtered set (score < Q1 - 1.5 x IQR, needs at
       least 4 reviews), in which case choose the review closest to the MEDIAN score.
       Why: on this dataset the lowest-scoring review is an outlier for 48 of 57
       destinations, and those outliers are usually off-topic (e.g. a review of an
       Indian restaurant at Arugam Bay), so they do not illustrate the issue. The
       median review about the dominant aspect is representative of what visitors
       actually say about it. When the lowest review is NOT an outlier it is kept,
       because it shows the gap most clearly.
    Edge cases: no review mentions the dominant aspect (or no dominant aspect) ->
    lowest Base_Reality_Score across all of the destination's reviews; no reviews at
    all (or no usable scores) -> (None, dominant).

    Returns (row or None, dominant aspect or None).
    """
    counts = {a: _safe_count(mention_counts.get(a)) for a in ASPECTS}
    dominant = max(ASPECTS, key=lambda a: counts[a]) if any(counts.values()) else None

    if dest_reviews is None or dest_reviews.empty:
        return None, dominant

    scores_all = pd.to_numeric(dest_reviews["Base_Reality_Score"], errors="coerce")
    if dominant is not None:
        mask = dest_reviews["Mentioned_Aspects"].apply(lambda v: _has_aspect(v, dominant))
        scores = scores_all[mask].dropna()
    else:
        scores = scores_all.iloc[0:0]

    if scores.empty:
        # Fallback: nothing mentions the dominant aspect -> lowest across all reviews.
        scores_all = scores_all.dropna()
        if scores_all.empty:
            return None, dominant
        return dest_reviews.loc[scores_all.idxmin()], dominant

    lowest_idx = scores.idxmin()
    chosen_idx = lowest_idx
    if len(scores) >= 4:
        q1, q3 = scores.quantile(0.25), scores.quantile(0.75)
        if scores[lowest_idx] < q1 - 1.5 * (q3 - q1):
            median = scores.median()
            chosen_idx = (scores - median).abs().idxmin()
    return dest_reviews.loc[chosen_idx], dominant


# ---------------------------------------------------------------------------
# Tips (positive, triggered by `relative`, not by raw counts)
# ---------------------------------------------------------------------------
ICON_EMOJI = {"sunrise": "⭐", "leaf": "🌿", "bag": "🛍️", "boot": "🥾", "backpack": "🎒",
              "sparkles": "✨", "camera": "📸", "map": "🗺️"}

ASPECT_TIPS = {
    ("Crowding", "above"): ("sunrise", "A popular favourite",
        "This is a well-loved spot that many travellers enjoy! For a calmer experience closer to the "
        "photos, plan your visit for early morning or late afternoon."),
    ("Crowding", "below"): ("leaf", "Room to breathe",
        "Crowds come up less often in reviews here than at most destinations, so you can usually "
        "explore at a relaxed, unhurried pace."),
    ("Facilities", "above"): ("backpack", "Come prepared",
        "Travellers often talk about the on-site amenities here. Bringing your own essentials, like "
        "water, snacks and a small towel, keeps your visit easy and relaxed."),
    ("Commercialization", "above"): ("bag", "Lively local atmosphere",
        "You'll find local vendors, shops and ticketed experiences here. Carry some small notes in "
        "local currency to enjoy the bustle and support local businesses."),
    ("Accessibility", "above"): ("boot", "Get ready for an adventure",
        "Getting here and exploring is part of the fun, with some walking, climbing or a scenic ride "
        "along the way. Comfortable shoes and a bottle of water will help you make the most of it."),
}
BAND_TIPS = {
    "spot_on": ("camera", "Close to the description",
        "Reviews closely echo the way this destination is described, so the picture you form before "
        "your trip is a good guide. Keep your camera ready!"),
    "unique_vibe": ("sparkles", "Its own unique character",
        "Travellers describe a personality all of its own, blending the serene image with lively local "
        "life. Come curious and enjoy both sides."),
    "authentic": ("map", "Enjoy it on its own terms",
        "Visitors describe this place quite differently from its marketing. Come with an open mind and "
        "you'll discover moments no brochure can capture."),
}
GENERIC_TIP = ("map", "Plan with a local",
    "Ask your host or guide for their favourite time to visit. A friendly local tip often turns a good "
    "day into a great one.")


def build_tips(aspects: list[dict], band: str) -> list[dict]:
    tips = []
    for a in aspects:
        t = ASPECT_TIPS.get((a["key"], a["relative"]))
        if t:
            tips.append({"aspect": a["key"], "icon": t[0], "title": t[1], "body": t[2]})
    for icon, title, body in (BAND_TIPS[band], GENERIC_TIP):
        if len(tips) >= 2:
            break
        if all(t["title"] != title for t in tips):
            tips.append({"aspect": None, "icon": icon, "title": title, "body": body})
    return tips[:4]


def tips_to_markdown(tips: list[dict]) -> list[str]:
    return [f"{ICON_EMOJI[t['icon']]} **{t['title']}:** {t['body']}" for t in tips]


# ---------------------------------------------------------------------------
# Load + precompute
# ---------------------------------------------------------------------------
def load_data(csv_path: Path = SCORED_CSV):
    df = pd.read_csv(csv_path)
    df["Base_Reality_Score"] = pd.to_numeric(df["Base_Reality_Score"], errors="coerce")
    df = df.dropna(subset=["Base_Reality_Score", "Location_Name"]).copy()
    df["Clean_Review_Text"] = df["Clean_Review_Text"].fillna("").astype(str)
    df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce")
    df["Helpful_Votes"] = pd.to_numeric(df["Helpful_Votes"], errors="coerce").fillna(0).astype(int)
    df["Pct"] = df["Base_Reality_Score"] * 100.0
    for a in ASPECTS:
        df[f"_{a}"] = aspect_flags(df["Mentioned_Aspects"], a)
    return df


def precompute(df: pd.DataFrame):
    n_reviews = len(df)
    groups = {name: g for name, g in df.groupby("Location_Name", sort=True)}
    # "Average destination" = mean of the per-destination shares, computed the same
    # way as the average Reality Match Score (mean over destinations, not pooled reviews).
    aspect_avg = {
        a: _num(sum(100.0 * g[f"_{a}"].sum() / len(g) for g in groups.values()) / len(groups), 1)
        for a in ASPECTS
    }
    raw_scores = {name: float(g["Pct"].mean()) for name, g in groups.items()}
    scores = {name: round(s, 1) for name, s in raw_scores.items()}
    names = sorted(groups)
    n_dest = len(names)
    values = list(scores.values())
    dataset_avg = _num(sum(raw_scores.values()) / n_dest, 1)

    overview_items, details = [], {}
    for name in names:
        g = groups[name]
        first = g.iloc[0]
        total = len(g)
        score = scores[name]
        lower = sum(v < score for v in values)
        rank = 1 + sum(v > score for v in values)
        percentile = _num(100.0 * lower / (n_dest - 1), 1) if n_dest > 1 else 100.0
        band = _band(score)
        ratings = g["Rating"].dropna()
        avg_rating = _num(ratings.mean(), 2) if len(ratings) else None
        positive_pct = _pct(int((ratings >= 4).sum()), total)

        aspects, aspects_pct, mentions = [], {}, {}
        for a in ASPECTS:
            sub = g[g[f"_{a}"]]
            cnt = len(sub)
            share = _pct(cnt, total) or 0.0
            avg = aspect_avg[a] or 0.0
            if avg > 0 and share >= 1.25 * avg:
                rel = "above"
            elif share <= 0.75 * avg:
                rel = "below"
            else:
                rel = "typical"
            sub_r = sub["Rating"].dropna()
            aspects.append({
                "key": a,
                "mentions": cnt,
                "share_pct": share,
                "dataset_avg_pct": avg,
                "relative": rel,
                "positive_pct": _pct(int((sub_r >= 4).sum()), cnt) if cnt else None,
                "snippet": pick_snippet(sub, a) if cnt else None,
            })
            aspects_pct[a] = share
            mentions[a] = cnt

        ratios = {a: aspects_pct[a] / aspect_avg[a] for a in ASPECTS if aspect_avg[a]}
        top_aspect = max(ASPECTS, key=lambda a: ratios.get(a, -1.0)) if ratios else None

        contrast, contrast_aspect = select_contrasting_review(g, mentions)
        clipped = g["Pct"].clip(lower=0, upper=100)
        bins = [0] * 10
        for v in clipped:
            bins[min(int(v // 10), 9)] += 1
        distribution = [{"bin": f"{i * 10}-{i * 10 + 10}", "count": c} for i, c in enumerate(bins)]

        tips = build_tips(aspects, band)
        meta = {
            "type": _str(first.get("Location_Type")), "province": _str(first.get("Province")),
            "district": _str(first.get("District")), "city": _str(first.get("Located_City")),
        }

        overview_items.append({
            "name": name, **meta,
            "total_reviews": total, "score": score, "percentile": percentile, "rank": rank,
            "band": band, "avg_rating": avg_rating, "positive_pct": positive_pct,
            "aspects_pct": aspects_pct, "top_aspect": top_aspect,
        })
        details[name] = {
            # v1
            "Location_Name": name,
            "Total_Reviews": total,
            "Average_Reality_Score": score,
            "Crowding_Mentions": mentions["Crowding"],
            "Facilities_Mentions": mentions["Facilities"],
            "Commercialization_Mentions": mentions["Commercialization"],
            "Accessibility_Mentions": mentions["Accessibility"],
            "Marketing_Promise": _str(first.get("Promise_Text")),
            "Contrasting_Reality_Review": _str(contrast.get("Clean_Review_Text")) if contrast is not None else None,
            "Alignment_Status": ALIGNMENT_STATUS[band],
            "Recommendations": tips_to_markdown(tips),
            # v2
            "Location_Type": meta["type"], "Province": meta["province"],
            "District": meta["district"], "City": meta["city"],
            "Score_Percentile": percentile, "Score_Rank": rank, "Score_Band": band,
            "Dataset_Avg_Score": dataset_avg,
            "Average_Rating": avg_rating, "Positive_Pct": positive_pct,
            "Contrasting_Review_Title": _str(contrast.get("Title")) if contrast is not None else None,
            "Contrasting_Review_Rating": (int(contrast["Rating"])
                                          if contrast is not None and not pd.isna(contrast["Rating"]) else None),
            "Contrasting_Review_Similarity": _num(contrast["Pct"], 1) if contrast is not None else None,
            "Contrasting_Review_Aspect": contrast_aspect,
            "Score_Distribution": distribution,
            "Aspects": aspects,
            "Tips": tips,
        }

    overview = {
        "total_destinations": n_dest,
        "total_reviews": n_reviews,
        "avg_score": dataset_avg,
        "min_score": _num(min(values), 1),
        "max_score": _num(max(values), 1),
        "median_score": _num(pd.Series(list(raw_scores.values())).median(), 1),
        "aspect_avg_pct": aspect_avg,
        "types": sorted({i["type"] for i in overview_items if i["type"]}),
        "provinces": sorted({i["province"] for i in overview_items if i["province"]}),
        "destinations": overview_items,
    }
    return names, overview, details


print("Loading data...")
_DF = load_data()
NAMES, OVERVIEW, DETAILS = precompute(_DF)
N_REVIEWS = len(_DF)
del _DF
_EXACT = {_norm(n): n for n in NAMES}
_LOOSE = {_norm_loose(n): n for n in NAMES}
print(f"Ready: {len(NAMES)} destinations, {N_REVIEWS} reviews.")


def match_destination(query: str) -> str | None:
    """Exact (case/apostrophe-insensitive) match first, else literal substring,
    most-reviewed wins (ties: alphabetical)."""
    q = _norm(query)
    if not q:
        return None
    if q in _EXACT:
        return _EXACT[q]
    ql = _norm_loose(query)
    if ql in _LOOSE:
        return _LOOSE[ql]
    hits = [n for key, n in _LOOSE.items() if ql in key]
    if not hits:
        return None
    return max(hits, key=lambda n: (DETAILS[n]["Total_Reviews"], [-ord(c) for c in n]))


def _get_or_404(name: str) -> dict:
    found = match_destination(name)
    if found is None:
        raise HTTPException(status_code=404, detail="Destination not found. Please try a different name.")
    return DETAILS[found]


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
def create_app(dist_dir: Path | None = DEFAULT_DIST_DIR) -> FastAPI:
    app = FastAPI(title="TravelMind - Reality Match API")
    app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=False,
                       allow_methods=["GET", "OPTIONS"], allow_headers=["*"])

    @app.get("/api/health")
    def health():
        return {"status": "ok", "destinations": len(NAMES), "reviews": N_REVIEWS}

    @app.get("/api/destinations")
    def get_all_destinations():
        return {"destinations": NAMES}

    @app.get("/api/overview")
    def get_overview():
        return OVERVIEW

    @app.get("/api/destination/{destination_name}")
    def get_destination_details(destination_name: str):
        return _get_or_404(destination_name)

    @app.get("/api/compare")
    def compare(a: str = Query(...), b: str = Query(...)):
        return {"a": _get_or_404(a), "b": _get_or_404(b)}

    dist = Path(dist_dir).resolve() if dist_dir else None
    index = dist / "index.html" if dist else None

    if index is not None and index.is_file():
        @app.get("/", include_in_schema=False)
        def spa_root():
            return FileResponse(index)

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            candidate = (dist / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(dist):
                return FileResponse(candidate)
            return FileResponse(index)
    else:
        @app.get("/")
        def home():
            return {"message": "TravelMind Backend API is running successfully!"}

    return app


app = create_app()
