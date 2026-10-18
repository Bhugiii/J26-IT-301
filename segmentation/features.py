"""Turn survey responses into the behavioural feature table used for clustering."""
import re

import numpy as np
import pandas as pd

from .survey_schema import (ACTIVITIES, FREQUENCY, IMPORTANCE, LEAD, Q_ACTIVITIES, Q_DAYS, Q_DISTRICTS, Q_FREQUENCY,
                            Q_GROUP, Q_IMPORTANCE, Q_LEAD, Q_SPEND, Q_SPLIT, Q_STOPS, Q_TRANSPORT, SPEND, SPLIT_COLS,
                            SPLIT_ROWS, TRANSPORT)

# Approximate coordinates of each district's main town, for mobility dispersion.
DISTRICT_COORDS = {
    "Ampara": (7.30, 81.67), "Anuradhapura": (8.31, 80.40), "Badulla": (6.99, 81.06),
    "Batticaloa": (7.73, 81.69), "Colombo": (6.93, 79.86), "Galle": (6.05, 80.22),
    "Gampaha": (7.09, 80.00), "Hambantota": (6.12, 81.12), "Jaffna": (9.66, 80.02),
    "Kalutara": (6.58, 79.96), "Kandy": (7.29, 80.63), "Kegalle": (7.25, 80.35),
    "Kilinochchi": (9.38, 80.40), "Kurunegala": (7.49, 80.36), "Mannar": (8.98, 79.90),
    "Matale": (7.47, 80.62), "Matara": (5.95, 80.54), "Monaragala": (6.87, 81.35),
    "Mullaitivu": (9.27, 80.81), "Nuwara Eliya": (6.97, 80.77), "Polonnaruwa": (7.94, 81.00),
    "Puttalam": (8.03, 79.83), "Ratnapura": (6.68, 80.40), "Trincomalee": (8.57, 81.23),
    "Vavuniya": (8.75, 80.50),
}
# Related tick-box options are grouped so 24 yes/no columns do not swamp the other features.
ACTIVITY_GROUPS = {
    "act_beach_water": ACTIVITIES[0:2] + [ACTIVITIES[3]],
    "act_nature_adventure": [ACTIVITIES[2], ACTIVITIES[4], ACTIVITIES[7]],
    "act_culture_heritage": ACTIVITIES[5:7] + ACTIVITIES[12:14],
    "act_wellness": [ACTIVITIES[9]],
    "act_food_shopping_nightlife": [ACTIVITIES[8], ACTIVITIES[10], ACTIVITIES[11]],
}
TRANSPORT_GROUPS = {
    "transport_private": [TRANSPORT[0], TRANSPORT[1], TRANSPORT[7]],
    "transport_public": [TRANSPORT[3], TRANSPORT[4]],
    "transport_light": [TRANSPORT[5], TRANSPORT[6]],
    "transport_organised": [TRANSPORT[2], TRANSPORT[8]],
}



def districts_in(cell):
    """Split a tick-box cell on commas that are not inside brackets."""
    names = [part.split(" (")[0] for part in re.split(r", (?![^()]*\))", str(cell))]
    return [n for n in names if n in DISTRICT_COORDS]


def dispersion_km(names):
    """Mean distance of the visited districts from their centre; 0 for a single district."""
    if len(names) < 2:
        return 0.0
    points = np.array([DISTRICT_COORDS[n] for n in names])
    offsets = (points - points.mean(axis=0)) * [110.6, 110.6 * np.cos(np.radians(7.8))]
    return float(np.hypot(offsets[:, 0], offsets[:, 1]).mean())


def share_ticked(cells, options):
    return cells.apply(lambda cell: np.mean([option in cell for option in options]))


def build_features(df):
    visited = df[Q_DISTRICTS].apply(districts_in)
    activities = df[Q_ACTIVITIES].fillna("")
    transport = df[Q_TRANSPORT].fillna("")

    features = pd.DataFrame({
        "log_trip_days": np.log1p(df[Q_DAYS].astype(float)),
        "spend_band": df[Q_SPEND].map(SPEND.index),
        "districts_visited": visited.apply(len),
        "mobility_dispersion_km": visited.apply(dispersion_km),
        "log_overnight_stops": np.log1p(df[Q_STOPS].astype(float)),
        "log_group_size": np.log(df[Q_GROUP].astype(float)),
        "activity_count": activities.apply(lambda cell: sum(a in cell for a in ACTIVITIES)),
        "planning_lead": df[Q_LEAD].map(LEAD.index),
        "trip_frequency": df[Q_FREQUENCY].map(FREQUENCY.index),
    }, index=df.index)
    for name, options in ACTIVITY_GROUPS.items():
        features[name] = share_ticked(activities, options)
    for name, options in TRANSPORT_GROUPS.items():
        features[name] = share_ticked(transport, options)
    for row in SPLIT_ROWS:
        features["spend_on_" + row.split(",")[0].split(" ")[0].lower()] = df[Q_SPLIT.format(row)].map(SPLIT_COLS.index)
    for row in IMPORTANCE:
        features["values_" + "_".join(row.lower().split()[:3])] = df[Q_IMPORTANCE.format(row)].astype(float)
    return features

