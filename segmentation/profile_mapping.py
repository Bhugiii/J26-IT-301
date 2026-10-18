"""Map a website traveller profile onto the survey features it shares, and assign the nearest segment.

The Traveler Profile form asks fewer and differently worded questions than the survey, so a website
user can only be placed using the 12 features both share. The mapping below is an approximation and
is documented as such. This module is pure Python so the API can use it without scikit-learn.
"""
import math

# Survey features that a Traveler Profile can also supply.
SHARED_FEATURES = [
    "log_trip_days", "spend_band",
    "act_beach_water", "act_nature_adventure", "act_culture_heritage", "act_wellness", "act_food_shopping_nightlife",
    "values_keeping_costs_low", "values_comfort_and_luxury", "values_avoiding_crowded_places",
    "values_protecting_the_environment", "values_seeing_as_many",
]

# Daily budget (LKR) thresholds of the survey's six spending bands.
SPEND_THRESHOLDS = [5000, 10000, 20000, 40000, 75000]

# Profile interest tags grouped like the survey's activity groups, with each group's size in the survey.
INTEREST_GROUPS = {
    "act_beach_water": ({"beach", "marine", "snorkelling", "snorkeling", "surfing", "water sports", "coastal", "boat trip"}, 3),
    "act_nature_adventure": ({"nature", "hiking", "wildlife", "adventure", "rafting", "birdwatching", "photography"}, 3),
    "act_culture_heritage": ({"heritage", "history", "culture", "religious", "village", "education"}, 4),
    "act_wellness": ({"relaxation", "wellness"}, 1),
    "act_food_shopping_nightlife": ({"food", "shopping", "city", "nightlife"}, 3),
}
STYLE_TO_GROUP = {
    "Beach & Coastal": "act_beach_water", "Nature & Adventure": "act_nature_adventure",
    "Wildlife & Safari": "act_nature_adventure", "Culture & Heritage": "act_culture_heritage",
    "Relaxation & Leisure": "act_wellness",
}
COST_IMPORTANCE = [5.0, 4.5, 3.5, 2.5, 2.0, 1.5]   # by spending band
LUXURY_IMPORTANCE = [1.5, 2.0, 2.8, 3.5, 4.2, 4.6]  # by spending band
CROWD_AVOIDANCE = {"low": 5.0, "medium": 3.0, "high": 1.0}
PACE_COVERAGE = {"relaxed": 2.0, "balanced": 3.0, "active": 4.5}


def _number(value, default):
    try:
        number = float(str(value).replace(",", "").strip())
        return number if number > 0 else default
    except (TypeError, ValueError):
        return default


def profile_to_features(profile):
    """Turn a Traveler Profile (dict with the website's field names) into the shared survey features."""
    days = _number(profile.get("tripDuration"), 3)
    budget = _number(profile.get("budget"), 10000)
    band = sum(budget >= limit for limit in SPEND_THRESHOLDS)
    tags = {tag.strip().lower() for tag in str(profile.get("interests", "")).split(",") if tag.strip()}
    style = str(profile.get("travelStyle", ""))

    features = {"log_trip_days": math.log1p(days), "spend_band": float(band)}
    for name, (group_tags, survey_size) in INTEREST_GROUPS.items():
        count = len(tags & group_tags) + (1 if STYLE_TO_GROUP.get(style) == name else 0)
        features[name] = min(1.0, count / survey_size)
    features["values_keeping_costs_low"] = 5.0 if style == "Budget Explorer" else COST_IMPORTANCE[band]
    features["values_comfort_and_luxury"] = LUXURY_IMPORTANCE[band]
    features["values_avoiding_crowded_places"] = CROWD_AVOIDANCE.get(str(profile.get("preferredCrowd", "")).lower(), 3.0)
    importance = profile.get("sustainabilityImportance", 0.5)
    features["values_protecting_the_environment"] = 1 + 4 * min(1.0, max(0.0, float(importance)))
    features["values_seeing_as_many"] = PACE_COVERAGE.get(str(profile.get("travelPace", "")).lower(), 3.0)
    return features


def assign(profile, model):
    """Nearest segment centre in the standardised shared-feature space.

    `model` is the assignment section written by the pipeline: feature means, standard deviations
    and one centre per segment. Match strength is each segment's share of inverse distance.
    """
    features = profile_to_features(profile)
    point = [(features[f] - model["mean"][f]) / model["std"][f] for f in SHARED_FEATURES]
    distances = []
    for segment_id, centre in model["centres"].items():
        distance = math.sqrt(sum((p - centre[f]) ** 2 for p, f in zip(point, SHARED_FEATURES)))
        distances.append((segment_id, distance))
    distances.sort(key=lambda item: item[1])
    inverse = [1 / max(d, 1e-6) for _, d in distances]
    total = sum(inverse)
    return {
        "segment_id": distances[0][0],
        "match_strength": inverse[0] / total,
        "distances": [{"segment_id": s, "distance": d, "match_strength": w / total} for (s, d), w in zip(distances, inverse)],
        "features_used": features,
    }
