"""Generate SYNTHETIC responses for the tourist behaviour survey.

These rows are simulated, not collected from real people. They exist so the pipeline can be built
and tested before real survey responses arrive. Every row is tagged data_source = SYNTHETIC and
carries the archetype it was generated from, so results on this data can never be mistaken for findings.

Usage:  python -m segmentation.synthetic [rows] [seed]
"""
import csv
import random
import sys
from pathlib import Path

from .survey_schema import (ACTIVITIES, AGES, CONSENT, COUNTRIES, D, DECIDES, DIASPORA, DIASPORA_COUNTRIES,
                            FREQUENCY, IMPORTANCE, LEAD, MONTHS, RESIDENT, SEASONS, SOURCES, SPEND,
                            SPLIT_COLS, SPLIT_ROWS, STAY, STYLE, TRANSPORT, VISITOR, WITH, AGO, PURPOSE, ARRANGED)

NOISE = 0.08  # share of single-choice answers drawn at random, to blur the archetypes
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "segmentation"
EAST = {"Ampara", "Batticaloa", "Trincomalee"}
SOUTH_WEST = {"Galle", "Matara", "Hambantota", "Kalutara"}

INTL_MONTHS = [14, 13, 12, 7, 4, 4, 9, 10, 5, 5, 7, 13]
DOMESTIC_MONTHS = [6, 5, 6, 16, 6, 5, 6, 14, 5, 6, 5, 16]

# ---- Archetypes the rows are generated from ----
# Weights follow the order of the option lists above. "districts" lists
# favoured districts (everything else gets a small base weight).
ARCHETYPES = {
    "budget_backpacker": dict(
        share=0.18, who={VISITOR: 1}, ages=[40, 45, 10, 4, 1], days=(19, 7, 7, 60),
        companions=[45, 25, 0, 1, 28, 1, 0], purpose=[90, 1, 1, 2, 1, 5, 0],
        arranged=[92, 6, 0, 2], spend=[30, 45, 20, 4, 1, 0], split=[0.6, 1.0, 1.0, 1.1, 0.3],
        stay=[0, 6, 62, 20, 6, 5, 1, 0], n_districts=(6.5, 1.8),
        districts={"Badulla": 9, "Kandy": 8, "Matara": 9, "Galle": 7, "Nuwara Eliya": 7,
                   "Matale": 7, "Ampara": 6, "Colombo": 6, "Hambantota": 4, "Trincomalee": 4},
        transport=[.15, .05, .02, .85, .75, .8, .3, .3, .01],
        activities=[.8, .6, .45, .3, .8, .5, .45, .75, .5, .15, .45, .25, .15, .3, .7],
        style=[6, 14, 34, 12, 2, 32], importance=[4.5, 1.6, 3.6, 3.7, 4.4, 4.2, 3.4, 3.2],
        lead=[20, 35, 35, 10], sources=[.35, .7, .7, .6, .8, .03, .3, .3, .25],
        frequency=[78, 15, 5, 2, 0], seasons=[35, 12, 22, 6, 25], decides=[35, 10, 30, 3, 22]),
    "high_spend_cultural": dict(
        share=0.16, who={VISITOR: 1}, ages=[2, 14, 30, 38, 16], days=(11, 3, 6, 21),
        companions=[6, 52, 12, 20, 6, 4, 0], purpose=[88, 2, 3, 4, 3, 0, 0],
        arranged=[20, 48, 30, 2], spend=[0, 1, 9, 30, 40, 20], split=[1.7, 1.1, 1.2, 1.3, 0.9],
        stay=[58, 30, 1, 2, 7, 2, 0, 0], n_districts=(5.2, 1.4),
        districts={"Matale": 10, "Kandy": 10, "Anuradhapura": 6, "Polonnaruwa": 7,
                   "Nuwara Eliya": 7, "Galle": 7, "Hambantota": 6, "Colombo": 7, "Gampaha": 4},
        transport=[.9, .03, .2, .35, .02, .3, .01, .25, .08],
        activities=[.5, .12, .75, .25, .25, .92, .85, .65, .55, .3, .1, .5, .3, .3, .85],
        style=[58, 14, 2, 4, 2, 20], importance=[1.8, 4.5, 3.4, 3.4, 4.2, 3.8, 4.4, 4.5],
        lead=[1, 9, 40, 50], sources=[.3, .25, .35, .7, .6, .6, .45, .2, .01],
        frequency=[72, 20, 6, 2, 0], seasons=[55, 8, 15, 4, 18], decides=[45, 25, 5, 8, 17]),
    "domestic_family_leisure": dict(
        share=0.26, who={RESIDENT: 1}, ages=[4, 30, 40, 22, 4], days=(2.6, 1.2, 1, 7),
        companions=[1, 12, 60, 20, 6, 1, 0], purpose=[80, 10, 8, 1, 1, 0, 0],
        arranged=[78, 4, 2, 16], spend=[22, 42, 28, 7, 1, 0], split=[1.3, 1.3, 1.0, 0.6, 0.6],
        stay=[5, 36, 18, 6, 14, 2, 12, 7], n_districts=(1.7, 0.8),
        districts={"Nuwara Eliya": 10, "Kandy": 9, "Galle": 9, "Matara": 6, "Badulla": 6,
                   "Hambantota": 5, "Trincomalee": 5, "Kalutara": 4, "Anuradhapura": 4,
                   "Batticaloa": 3, "Puttalam": 3, "Matale": 4},
        transport=[.25, .7, .05, .1, .1, .2, .03, .08, 0],
        activities=[.6, .08, .3, .08, .2, .35, .55, .35, .45, .03, .03, .45, .15, .08, .8],
        style=[10, 12, 3, 38, 1, 36], importance=[3.9, 3.3, 3.2, 3.0, 3.0, 3.0, 4.6, 4.2],
        lead=[30, 48, 20, 2], sources=[.75, .6, .4, .4, .45, .03, .02, .08, .12],
        frequency=[1, 12, 30, 42, 15], seasons=[25, 30, 18, 5, 22], decides=[10, 68, 5, 7, 10]),
    "beach_relaxation": dict(
        share=0.15, who={VISITOR: 1}, ages=[8, 38, 30, 18, 6], days=(9, 3, 5, 21),
        companions=[8, 62, 12, 6, 12, 0, 0], purpose=[84, 1, 0, 14, 1, 0, 0],
        arranged=[55, 28, 15, 2], spend=[0, 6, 28, 38, 22, 6], split=[1.8, 1.4, 0.6, 0.7, 0.8],
        stay=[38, 32, 4, 2, 20, 4, 0, 0], n_districts=(2.3, 0.9),
        districts={"Galle": 12, "Matara": 10, "Hambantota": 5, "Kalutara": 5, "Gampaha": 4,
                   "Colombo": 4, "Trincomalee": 5, "Batticaloa": 4, "Ampara": 3},
        transport=[.6, .05, .03, .15, .05, .65, .2, .45, .02],
        activities=[.97, .5, .25, .4, .1, .25, .2, .12, .55, .6, .35, .45, .08, .08, .5],
        style=[2, 4, 3, 62, 17, 12], importance=[2.8, 4.2, 4.0, 3.3, 3.1, 1.8, 4.2, 3.9],
        lead=[5, 25, 45, 25], sources=[.4, .65, .4, .65, .85, .3, .1, .2, .03],
        frequency=[60, 25, 12, 3, 0], seasons=[50, 10, 22, 4, 14], decides=[55, 22, 10, 1, 12]),
    "domestic_young_adventure": dict(
        share=0.17, who={RESIDENT: 1}, ages=[55, 38, 6, 1, 0], days=(2.1, 0.9, 1, 5),
        companions=[6, 14, 1, 2, 72, 1, 4], purpose=[86, 3, 2, 0, 1, 7, 1],
        arranged=[85, 1, 1, 13], spend=[55, 35, 9, 1, 0, 0], split=[0.6, 1.2, 1.3, 0.8, 0.2],
        stay=[0, 8, 40, 10, 12, 14, 8, 8], n_districts=(1.9, 0.8),
        districts={"Badulla": 11, "Nuwara Eliya": 10, "Ratnapura": 6, "Kegalle": 5,
                   "Matale": 6, "Kandy": 5, "Matara": 5, "Ampara": 4, "Monaragala": 3,
                   "Trincomalee": 4, "Puttalam": 3},
        transport=[.1, .25, .05, .55, .6, .35, .35, .1, 0],
        activities=[.4, .25, .2, .08, .88, .2, .2, .5, .35, .02, .2, .08, .1, .1, .85],
        style=[2, 22, 52, 8, 0, 16], importance=[4.6, 1.9, 3.9, 3.8, 3.7, 3.4, 3.6, 3.3],
        lead=[55, 38, 6, 1], sources=[.7, .85, .65, .4, .35, .01, .01, .15, .25],
        frequency=[2, 8, 18, 40, 32], seasons=[28, 16, 20, 6, 30], decides=[14, 38, 10, 4, 34]),
    "pilgrimage_and_family_visits": dict(
        share=0.08, who={RESIDENT: 0.72, DIASPORA: 0.28}, ages=[4, 14, 26, 36, 20],
        days=(4, 3, 1, 21), companions=[4, 12, 30, 42, 4, 8, 0],
        purpose=[8, 34, 56, 1, 1, 0, 0], arranged=[45, 5, 12, 38],
        spend=[40, 36, 18, 5, 1, 0], split=[0.7, 1.1, 1.3, 0.4, 0.8],
        stay=[2, 18, 16, 6, 4, 0, 44, 10], n_districts=(2.2, 1.0),
        districts={"Anuradhapura": 12, "Kandy": 11, "Polonnaruwa": 5, "Jaffna": 6,
                   "Ratnapura": 5, "Hambantota": 5, "Matale": 4, "Monaragala": 3,
                   "Kurunegala": 4, "Colombo": 5, "Mannar": 2},
        transport=[.45, .45, .3, .15, .25, .2, .02, .08, .01],
        activities=[.12, .01, .1, .02, .15, .5, .97, .1, .3, .04, .01, .35, .45, .2, .45],
        style=[70, 4, 1, 3, 3, 19], importance=[3.8, 2.8, 2.6, 3.2, 3.6, 2.8, 4.5, 4.3],
        lead=[25, 45, 22, 8], sources=[.85, .25, .15, .15, .15, .12, .03, .03, .15],
        frequency=[3, 15, 32, 35, 15], seasons=[18, 28, 22, 6, 26], decides=[5, 34, 2, 46, 13]),
}


def weighted(options, weights):
    """One option by weight; occasionally uniform at random to add noise."""
    if random.random() < NOISE:
        return random.choice(options)
    return random.choices(options, weights=weights)[0]


def ticked(options, probabilities):
    chosen = [o for o, p in zip(options, probabilities) if random.random() < p]
    return chosen or [random.choices(options, weights=probabilities)[0]]


def bounded(mean, sd, low, high):
    return max(low, min(high, round(random.gauss(mean, sd))))


def pick_districts(spec, month):
    weights = {name: 0.35 for name in D}
    weights.update(spec["districts"])
    east_season = month in MONTHS[4:9]  # May to September
    for name in weights:
        if name in EAST:
            weights[name] *= 2.5 if east_season else 0.4
        elif name in SOUTH_WEST:
            weights[name] *= 0.6 if east_season else 1.5
    count = bounded(*spec["n_districts"], 1, 12)
    chosen = []
    while len(chosen) < count:
        pool = [n for n in weights if n not in chosen]
        chosen.append(random.choices(pool, weights=[weights[n] for n in pool])[0])
    return [D[name] for name in sorted(chosen)]


def group_size(companions):
    if companions == "Alone":
        return 1
    if companions == "Partner or spouse":
        return 2
    if companions == "Organised tour group":
        return random.randint(8, 30)
    if companions.startswith("Family"):
        return random.randint(3, 7)
    return random.randint(2, 8)


def make_row(name, spec):
    who = random.choices(list(spec["who"]), weights=list(spec["who"].values()))[0]
    countries = {VISITOR: COUNTRIES, DIASPORA: DIASPORA_COUNTRIES}.get(who, {"Sri Lanka": 1})
    month = weighted(MONTHS, DOMESTIC_MONTHS if who == RESIDENT else INTL_MONTHS)
    days = bounded(*spec["days"])
    stay = weighted(STAY, spec["stay"])
    if days == 1:
        stay = STAY[-1]
    elif stay == STAY[-1]:
        stay = STAY[2]
    districts = pick_districts(spec, month)
    stops = 0 if days == 1 else max(1, min(days - 1, round(len(districts) * random.uniform(0.8, 1.5))))
    companions = weighted(WITH, spec["companions"])

    row = {
        "data_source": "SYNTHETIC",
        "synthetic_archetype": name,
        "Timestamp": "",
        "Consent": CONSENT,
        "In the last 2 years, have you taken a leisure or holiday trip within Sri Lanka?": "Yes",
        "Which age group are you in?": weighted(AGES, spec["ages"]),
        "Which best describes you?": who,
        "Which country do you live in?": random.choices(list(countries), weights=list(countries.values()))[0],
        "How long ago was this trip?": random.choices(AGO, weights=[25, 22, 28, 25])[0],
        "In which month did the trip start?": month,
        "How many days did the trip last?": days,
        "Who did you travel with?": companions,
        "How many people travelled together, including you?": group_size(companions),
        "What was the main purpose of the trip?": weighted(PURPOSE, spec["purpose"]),
        "How was the trip arranged?": weighted(ARRANGED, spec["arranged"]),
        "About how much did you spend per person, per day?": weighted(SPEND, spec["spend"]),
    }
    for label, level in zip(SPLIT_ROWS, spec["split"]):
        row[f"How much of your spending went on each of these? [{label}]"] = SPLIT_COLS[bounded(level, 0.6, 0, 2)]
    row.update({
        "Where did you mostly stay?": stay,
        "Which districts did you visit on this trip?": ", ".join(districts),
        "In how many different towns or areas did you stay overnight?": stops,
        "How did you travel between places?": ", ".join(ticked(TRANSPORT, spec["transport"])),
        "Which of these did you do on this trip?": ", ".join(ticked(ACTIVITIES, spec["activities"])),
        "Which one best describes the style of this trip?": weighted(STYLE, spec["style"]),
    })
    for label, mean in zip(IMPORTANCE, spec["importance"]):
        row[f"How important was each of these when you planned and took the trip? [{label}]"] = bounded(mean, 0.9, 1, 5)
    row.update({
        "How far ahead did you plan this trip?": weighted(LEAD, spec["lead"]),
        "Where did you get information to plan the trip?": ", ".join(ticked(SOURCES, spec["sources"])),
        "How often do you take leisure trips within Sri Lanka?": weighted(FREQUENCY, spec["frequency"]),
        "When do you most prefer to travel in Sri Lanka?": weighted(SEASONS, spec["seasons"]),
        "What mostly decides when you travel?": weighted(DECIDES, spec["decides"]),
        "Is there anything that would have made this trip better? (optional)": "",
    })
    return row


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 619
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 20261010
    DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)
    out = DEFAULT_OUTPUT / f"SYNTHETIC_tourist_behaviour_{count}.csv"

    random.seed(seed)
    names = list(ARCHETYPES)
    shares = [ARCHETYPES[n]["share"] for n in names]
    rows = [make_row(n, ARCHETYPES[n]) for n in random.choices(names, weights=shares, k=count)]
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} synthetic rows to {out.name}")


if __name__ == "__main__":
    main()
