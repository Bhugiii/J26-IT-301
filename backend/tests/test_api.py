import math
import re
import sys
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import main  # noqa: E402
from tag_aspects import ASPECTS, aspect_flags, tag_review  # noqa: E402

client = TestClient(main.app)
SCORED = pd.read_csv(BACKEND / "ai_scored_data.csv")
SUMMARY = pd.read_csv(BACKEND / "destination_summary.csv")

BANNED = re.compile(
    r"\b(warning|warn|avoid|scam\w*|bad|risk\w*|danger\w*|dirty|terrible|awful|horrible|"
    r"crowded|overcrowded|worst|beware|unsafe|rip[\s-]?off|tout\w*|expensive|overpriced)\b",
    re.IGNORECASE,
)
ICONS = {"sunrise", "leaf", "bag", "boot", "backpack", "sparkles", "camera", "map"}


def destinations():
    return client.get("/api/destinations").json()["destinations"]


def get(name):
    return client.get(f"/api/destination/{quote(name, safe='')}")


def walk(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)
    else:
        yield obj


# --- basics -----------------------------------------------------------------
def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "destinations": 57, "reviews": len(SCORED)}


def test_destinations_sorted_and_complete():
    names = destinations()
    assert names == sorted(names)
    assert set(names) == set(SCORED["Location_Name"])
    assert len(names) == 57


def test_root_json_when_no_frontend_build(tmp_path):
    c = TestClient(main.create_app(dist_dir=tmp_path))
    assert c.get("/").json() == {"message": "TravelMind Backend API is running successfully!"}


def test_spa_serving(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>spa</html>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    c = TestClient(main.create_app(dist_dir=tmp_path))
    assert "spa" in c.get("/").text
    assert "spa" in c.get("/destination/Galle%20Fort").text
    assert "console.log" in c.get("/assets/app.js").text
    assert c.get("/api/does-not-exist").status_code == 404
    assert c.get("/api/health").json()["status"] == "ok"


def test_cors():
    r = client.options("/api/overview", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


# --- destination matching ---------------------------------------------------
@pytest.mark.parametrize("name", sorted(SCORED["Location_Name"].unique()))
def test_every_destination_returns_itself(name):
    r = get(name)
    assert r.status_code == 200
    assert r.json()["Location_Name"] == name


@pytest.mark.parametrize("name", ["Gangaramaya (Vihara) Buddhist Temple", "Twin Baths (Kuttam Pokuna)"])
def test_parentheses_names(name):
    assert get(name).json()["Location_Name"] == name
    assert get(name.lower()).json()["Location_Name"] == name


def test_partial_match_most_reviewed():
    r = get("Sigiriya")
    assert r.status_code == 200
    data = r.json()
    assert "Sigiriya" in data["Location_Name"]
    counts = SCORED[SCORED["Location_Name"].str.contains("Sigiriya", regex=False)]["Location_Name"].value_counts()
    assert data["Location_Name"] == counts.idxmax()


def test_regex_chars_are_literal():
    assert get(".*").status_code == 404
    assert get("(").status_code == 200  # literal "(" exists in two names


def test_not_found():
    r = get("Atlantis Underwater City")
    assert r.status_code == 404
    assert "detail" in r.json()


def test_compare():
    r = client.get("/api/compare", params={"a": "Galle Fort", "b": "Mirissa Beach"})
    assert r.status_code == 200
    j = r.json()
    assert j["a"]["Location_Name"] == "Galle Fort"
    assert j["b"]["Location_Name"] == "Mirissa Beach"
    assert j["a"].keys() == get("Galle Fort").json().keys()
    assert client.get("/api/compare", params={"a": "Galle Fort", "b": "Nowhere"}).status_code == 404
    assert client.get("/api/compare", params={"a": "Galle Fort"}).status_code == 422


# --- overview consistency ---------------------------------------------------
def test_overview_consistent_with_csv():
    o = client.get("/api/overview").json()
    assert o["total_destinations"] == SUMMARY.shape[0] == 57
    assert o["total_reviews"] == len(SCORED)
    by_name = {d["name"]: d for d in o["destinations"]}
    assert set(by_name) == set(SUMMARY["Location_Name"])
    for row in SUMMARY.itertuples():
        d = by_name[row.Location_Name]
        assert d["total_reviews"] == row.Total_Reviews
        assert d["score"] == pytest.approx(row.Average_Reality_Score, abs=0.05)
        for a in ASPECTS:
            exp = 100 * getattr(row, f"{a}_Mentions") / row.Total_Reviews
            assert d["aspects_pct"][a] == pytest.approx(exp, abs=0.05)
    scores = [d["score"] for d in o["destinations"]]
    assert o["min_score"] == min(scores) and o["max_score"] == max(scores)
    assert o["avg_score"] == pytest.approx(sum(scores) / len(scores), abs=0.1)
    for a in ASPECTS:
        # mean of per-destination shares (same averaging as avg_score)
        exp = sum(d["aspects_pct"][a] for d in o["destinations"]) / len(o["destinations"])
        assert o["aspect_avg_pct"][a] == pytest.approx(exp, abs=0.1)
    top = max(o["destinations"], key=lambda d: d["score"])
    assert top["rank"] == 1 and top["percentile"] == 100.0
    for d in o["destinations"]:
        exp_band = "spot_on" if d["score"] > 60 else "unique_vibe" if d["score"] > 45 else "authentic"
        assert d["band"] == exp_band
        assert d["top_aspect"] in ASPECTS


def test_v1_fields_match_summary_csv():
    for row in SUMMARY.itertuples():
        d = get(row.Location_Name).json()
        assert d["Total_Reviews"] == row.Total_Reviews
        assert d["Average_Reality_Score"] == row.Average_Reality_Score
        for a in ASPECTS:
            assert d[f"{a}_Mentions"] == getattr(row, f"{a}_Mentions")


# --- per-destination payload --------------------------------------------------
V1_STATUS = {
    "🌟 The marketing is spot on! What you see is exactly what you get.",
    "✨ A destination with its own unique vibe! Expect a mix of the serene marketing and a lively local atmosphere.",
    "🌍 An authentic, bustling travel experience! Come with an open mind to enjoy the real local energy.",
}


@pytest.mark.parametrize("name", sorted(SCORED["Location_Name"].unique()))
def test_destination_payload(name):
    d = get(name).json()
    assert d["Alignment_Status"] in V1_STATUS
    # JSON-native, no NaN
    for v in walk(d):
        assert v is None or isinstance(v, (str, int, float, bool))
        if isinstance(v, float):
            assert math.isfinite(v)
    # aspects
    assert [a["key"] for a in d["Aspects"]] == ASPECTS
    for a in d["Aspects"]:
        assert 0 <= a["share_pct"] <= 100
        assert 0 <= a["dataset_avg_pct"] <= 100
        assert a["relative"] in {"above", "below", "typical"}
        if a["mentions"] == 0:
            assert a["positive_pct"] is None and a["snippet"] is None
        else:
            assert 0 <= a["positive_pct"] <= 100
            s = a["snippet"]
            assert s is not None and 0 < len(s["text"]) <= 280
            core = s["text"].strip("…")
            assert core in " ".join(SCORED.loc[SCORED["Location_Name"] == name, "Clean_Review_Text"])
    # tips
    tips = d["Tips"]
    assert 2 <= len(tips) <= 4
    for t in tips:
        assert t["icon"] in ICONS
        assert not BANNED.search(t["title"] + " " + t["body"]), t
        assert "**" not in t["body"]
    rel = {a["key"]: a["relative"] for a in d["Aspects"]}
    for a in ASPECTS:
        if rel[a] == "above":
            assert any(t["aspect"] == a for t in tips)
    assert len(d["Recommendations"]) == len(tips)
    assert all(isinstance(r, str) and "**" in r for r in d["Recommendations"])
    for r in d["Recommendations"]:
        assert not BANNED.search(r)
    # distribution
    assert [b["bin"] for b in d["Score_Distribution"]] == [f"{i}-{i + 10}" for i in range(0, 100, 10)]
    assert sum(b["count"] for b in d["Score_Distribution"]) == d["Total_Reviews"]
    assert 1 <= d["Average_Rating"] <= 5
    assert 0 <= d["Positive_Pct"] <= 100
    assert 0 <= d["Score_Percentile"] <= 100


# --- tagger regression ------------------------------------------------------
@pytest.mark.parametrize("text,absent", [
    ("The people are all very friendly", "Crowding"),
    ("I booked online and the street was lined with palms", "Crowding"),
    ("They also have a business in Hikkaduwa", "Accessibility"),
    ("Long and broad strip of sand, friends from abroad loved it", "Accessibility"),
    ("Best beach so far and by far the nicest, near the farm", "Accessibility"),
    ("Surf trainers and training available", "Accessibility"),
    ("Visited the workshop", "Commercialization"),
    ("Use a toothbrush", "Crowding"),
    ("We brought a packed lunch", "Crowding"),
])
def test_tagger_no_false_positive(text, absent):
    assert absent not in tag_review(text)


@pytest.mark.parametrize("text,present", [
    ("It was so crowded on the weekend", "Crowding"),
    ("Too many people at sunset", "Crowding"),
    ("We waited in a long queue", "Crowding"),
    ("Clean toilets near the car park", "Facilities"),
    ("The entrance fee is 30 USD for foreigners", "Commercialization"),
    ("Lots of shops selling souvenirs", "Commercialization"),
    ("Took a tuktuk from Ella, then a steep climb", "Accessibility"),
    ("Take the train from Kandy, it is not far", "Accessibility"),
])
def test_tagger_true_positive(text, present):
    assert present in tag_review(text)


def test_tagger_general_and_format():
    assert tag_review("What a lovely sunset") == "General"
    assert tag_review("Crowded, dirty and expensive, long steep climb") == \
        "Crowding, Facilities, Commercialization, Accessibility"
