"""Describe each segment in plain language: its size, typical trip, top activities, and a short name."""
from collections import Counter

from .features import districts_in
from .survey_schema import (ACTIVITIES, IMPORTANCE, Q_ACTIVITIES, Q_DAYS, Q_DESCRIBES, Q_DISTRICTS, Q_GROUP,
                            Q_IMPORTANCE, Q_STYLE, Q_TRANSPORT, RESIDENT, TRANSPORT)

SPEND_LABELS = ["under LKR 5,000", "LKR 5,000–10,000", "LKR 10,000–20,000", "LKR 20,000–40,000",
                "LKR 40,000–75,000", "over LKR 75,000"]

# Traits shown side by side on the website, in display order.
TRAITS = [
    ("trip_days", "Average trip length", "days"),
    ("spend_band", "Daily spending level (0–5)", ""),
    ("districts_visited", "Districts visited", ""),
    ("dispersion_km", "Travel spread", "km"),
    ("activity_count", "Activities per trip", ""),
    ("group_size", "Group size", "people"),
    ("overseas_share", "From overseas", "%"),
    ("values_avoiding_crowded_places", "Avoiding crowds matters (1–5)", ""),
    ("values_keeping_costs_low", "Keeping costs low matters (1–5)", ""),
    ("values_comfort_and_luxury", "Comfort and luxury matter (1–5)", ""),
]


def _top(counter, total, n):
    return [{"label": label, "share": round(count / total, 3)} for label, count in counter.most_common(n)]


def _name(trip_days, spend, districts, overseas):
    length = "Short" if trip_days < 4 else "Mid-length" if trip_days < 12 else "Long"
    cost = "low-cost" if spend < 1.6 else "mid-range" if spend < 2.8 else "higher-spend"
    who = " domestic" if overseas < 0.25 else " overseas" if overseas > 0.6 else ""
    scope = "one-area" if districts < 2.5 else "multi-stop" if districts < 5 else "island-wide"
    return f"{length}, {cost}{who} trips", scope


def describe_segments(df, features, labels):
    """One summary per segment label, largest segment first."""
    segments = []
    for segment_id in sorted(set(labels), key=lambda s: (-(labels == s).sum(), s)):
        mask = labels == segment_id
        rows, part = df[mask], features[mask]
        n = int(mask.sum())
        activities = Counter(a for cell in rows[Q_ACTIVITIES].fillna("") for a in ACTIVITIES if a in cell)
        transport = Counter(t for cell in rows[Q_TRANSPORT].fillna("") for t in TRANSPORT if t in cell)
        districts = Counter(d for cell in rows[Q_DISTRICTS] for d in districts_in(cell))
        importance = {label: float(rows[Q_IMPORTANCE.format(label)].astype(float).mean()) for label in IMPORTANCE}
        traits = {
            "trip_days": float(rows[Q_DAYS].astype(float).mean()),
            "spend_band": float(part["spend_band"].mean()),
            "districts_visited": float(part["districts_visited"].mean()),
            "dispersion_km": float(part["mobility_dispersion_km"].mean()),
            "activity_count": float(part["activity_count"].mean()),
            "group_size": float(rows[Q_GROUP].astype(float).mean()),
            "overseas_share": float((rows[Q_DESCRIBES] != RESIDENT).mean()),
            "values_avoiding_crowded_places": float(part["values_avoiding_crowded_places"].mean()),
            "values_keeping_costs_low": float(part["values_keeping_costs_low"].mean()),
            "values_comfort_and_luxury": float(part["values_comfort_and_luxury"].mean()),
        }
        name, scope = _name(traits["trip_days"], traits["spend_band"], traits["districts_visited"], traits["overseas_share"])
        top_activities = _top(activities, n, 4)
        top_values = sorted(importance, key=importance.get, reverse=True)[:2]
        description = (
            f"Trips of about {traits['trip_days']:.0f} days, spending {SPEND_LABELS[round(traits['spend_band'])]} a day "
            f"and covering {traits['districts_visited']:.1f} districts on average ({scope}). "
            f"Most often: {', '.join(a['label'].lower() for a in top_activities[:2])}. "
            f"What matters most: {top_values[0].lower()}, then {top_values[1].lower()}."
        )
        segments.append({
            "label": int(segment_id), "name": name, "scope": scope, "description": description,
            "size": n, "share": round(n / len(df), 4), "typical_spend": SPEND_LABELS[round(traits["spend_band"])],
            "traits": {k: round(v, 3) for k, v in traits.items()},
            "top_activities": top_activities, "top_transport": _top(transport, n, 3), "top_districts": _top(districts, n, 4),
            "top_styles": _top(Counter(rows[Q_STYLE]), n, 2),
            "importance": {k: round(v, 2) for k, v in importance.items()},
        })
    names = Counter(s["name"] for s in segments)
    for s in segments:  # keep names unique by adding the travel scope
        if names[s["name"]] > 1:
            s["name"] = s["name"].replace(" trips", f" {s['scope']} trips")
    return segments
