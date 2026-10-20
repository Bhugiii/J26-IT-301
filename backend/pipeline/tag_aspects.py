"""
Step 2 of the pipeline: tag each review with the destination aspects it talks about.

Input : cleaned_master_data.csv   (from process_data.py)
Output: tagged_master_data.csv    (adds the `Mentioned_Aspects` column)

`Mentioned_Aspects` is a ", "-joined list in fixed order
(Crowding, Facilities, Commercialization, Accessibility) or "General" when no
aspect vocabulary is found.

==============================================================================
KEYWORD DESIGN NOTES  (why the lists look the way they do)
==============================================================================
The first version used plain substring tests (`keyword in text`). On 13,943
reviews that produced heavy false positives, e.g.
    "line"  -> online, lined, airline, guideline     "bus"   -> business
    "rush"  -> brush                                 "train" -> training
    "road"  -> abroad                                "far"   -> farm, fare, "so far"
    "shop"  -> workshop                              "people"-> "friendly people"
1,323 of the 2,841 Crowding tags came only from the bare words "people"/"line".

Principles used in this rewrite:
 1. WORD BOUNDARIES. Every pattern is wrapped in \\b...\\b, so "bus" can no
    longer match "business", "shop" no longer matches "workshop", etc.
 2. PHRASES FOR AMBIGUOUS WORDS. A word that is only an aspect signal in
    certain contexts is only accepted inside a phrase:
      - people/tourists/visitors -> only with a quantity cue: "too many people",
        "lots of tourists", "full of people", "people everywhere"...
        ("friendly people" / "local people" are about hospitality, not crowds).
      - line   -> "long line(s)", "wait/stand in line", "line up".
      - rush   -> "rush hour", "rush of people/tourists" (not "rush of water").
      - far    -> "far from", "far away", "too/quite/not far"
                  (excludes "so far", "by far", "as far as").
      - train  -> travel uses only: "by train", "take/took the train",
                  "train ride/journey/station", "railway station". At Nine Arch
                  Bridge most "train" mentions describe the sight itself, not
                  how to get there.
      - walk   -> effort/distance uses only: "walking distance", "long walk",
                  "walk up/down", "steep walk", "walking shoes". A generic
                  "walk along the beach" is an activity, not an access issue.
      - packed -> only "was/so/very packed", "packed with/out", "jam packed"
                  (not "packed lunch" or tea "dried and packed").
      - wait   -> "long wait", "had to wait", "waiting time", "wait in line".
 3. DESTINATION-APPROPRIATE VOCABULARY for Sri Lankan attractions:
      tuk tuk / three wheeler, jeep (safari parks), entrance/entry fee,
      foreigner price, touts, gem/spice "shops", donations at temples,
      steps/stairs/climb (Sigiriya, Mihintale, Adam's Peak style sites).
 4. CLEANED-TEXT ARTEFACTS. The original cleaning step removed hyphens, so the
    text contains "tuktuk", "ripoff", "jampacked", "wellmaintained",
    "overpriced", "carpark". Patterns accept both the joined and spaced forms
    (`[\\s-]?`).
 5. TOPIC, NOT SENTIMENT. An aspect is "mentioned" whether the review is
    positive or negative about it ("not crowded at all" still discusses
    Crowding; "clean toilets" still discusses Facilities). Sentiment is
    handled separately (Rating) in the API.
 6. Deliberately NOT used: "quiet", "peaceful", "beautiful", "nice", generic
    "walk", "car", "money", "pay", "buy" - they are too common and too vague to act as
    evidence for a specific aspect, and would dilute the signal.
==============================================================================
"""
from pathlib import Path
import re

import pandas as pd

HERE = Path(__file__).resolve().parent
INPUT_CSV = HERE / "cleaned_master_data.csv"
OUTPUT_CSV = HERE / "tagged_master_data.csv"

ASPECTS = ["Crowding", "Facilities", "Commercialization", "Accessibility"]

_CROWD_NOUNS = r"(?:people|tourists?|visitors?|crowds?|locals|foreigners|travell?ers|families|pilgrims|devotees|groups?)"
_QUANTITY = (
    r"(?:too|so|very|really)\s+many|lots?\s+of|a\s+lot\s+of|full\s+of|packed\s+with|filled\s+with|"
    r"crammed\s+with|hundreds\s+of|thousands\s+of|loads\s+of|tons\s+of|plenty\s+of|"
    r"hordes\s+of|masses\s+of|swarms?\s+of|heaps\s+of|flocks?\s+of|throngs?\s+of|"
    r"influx\s+of|number\s+of|amount\s+of"
)

ASPECT_PATTERNS_RAW = {
    "Crowding": [
        r"crowd(?:s|ed|ing)?", r"over[\s-]?crowded", r"un[\s-]?crowded",
        r"queu(?:e|es|ed|ing)",
        r"busy", r"busier", r"busiest",
        r"jam[\s-]?packed", r"packed\s+(?:with|full|out|to\s+the)",
        r"(?:so|very|really|completely|totally|fully|absolutely|quite|was|is|were|are|be|gets?|got|getting|becomes?)\s+packed"
        r"(?!\s+(?:lunch|breakfast|food|meals?|snacks?|dinner|and\s+shipped))",
        r"rush\s+hour", r"rush\s+of\s+(?:people|tourists|visitors)",
        r"(?:long|huge|big|endless|massive)\s+(?:lines?|queues?|waits?|waiting)",
        r"(?:stand|stood|standing|wait|waited|waiting|queue|queued|queuing)\s+in\s+(?:a\s+|the\s+)?(?:long\s+)?(?:line|queue)",
        r"lined?\s+up", r"line\s+ups?",
        r"had\s+to\s+wait", r"waiting\s+times?",
        rf"(?:{_QUANTITY})\s+(?:other\s+)?{_CROWD_NOUNS}",
        rf"{_CROWD_NOUNS}\s+everywhere",
        r"bus\s?loads?", r"coach\s?loads?", r"tour\s+bus(?:es)?", r"tour\s+groups?",
        r"school\s+(?:trips?|groups?|children|kids|tours?)",
        r"swarm(?:ed|ing)", r"hordes", r"throngs?", r"heaving",
        r"elbow\s+room", r"no\s+space", r"standing\s+room",
        r"peak\s+(?:season|time|hours?)",
    ],
    "Facilities": [
        r"toilets?", r"restrooms?", r"rest\s+rooms?", r"washrooms?", r"wash\s+rooms?",
        r"bathrooms?", r"loos?", r"lavator(?:y|ies)", r"wc",
        r"changing\s+rooms?", r"showers?", r"lockers?",
        r"parking", r"car\s?parks?", r"car\s+park(?:ing)?",
        r"clean(?:er|est|ed|liness|ly)?", r"unclean", r"dirt(?:y|ier)", r"filthy",
        r"litter(?:ed)?", r"rubbish", r"garbage", r"trash", r"plastic\s+(?:bottles?|waste|bags?)",
        r"(?:well|poorly|badly|nicely)[\s-]?maintained", r"maintenance", r"upkeep",
        r"facilit(?:y|ies)", r"amenit(?:y|ies)",
        r"drinking\s+water", r"benches", r"seating", r"rest\s+areas?",
        r"canteen", r"cafeteria", r"refreshments?", r"snack\s+bars?",
        r"information\s+(?:centre|center|desk|boards?)", r"sign\s?boards?", r"signage",
        r"lifeguards?", r"first\s+aid",
    ],
    "Commercialization": [
        r"vendors?", r"hawkers?", r"sellers?", r"sales\s?(?:man|men|people|pitch)",
        r"touts?", r"touting", r"scam(?:s|med|mers?)?", r"rip[\s-]?off", r"ripped\s+off",
        r"over[\s-]?priced", r"over[\s-]?charg(?:e|ed|ing)", r"expensive", r"pricey", r"pricy",
        r"tourist\s+(?:trap|prices?)", r"touristy", r"commerciali[sz](?:ed|ation)", r"commercial",
        r"tickets?", r"entr(?:y|ance)\s+(?:fees?|tickets?|charges?)", r"admission",
        r"fees?", r"foreigners?\s+(?:pay|prices?|rates?|tickets?|fees?)",
        r"prices?", r"priced", r"pricing", r"charged", r"charges",
        r"rupees", r"lkr", r"rs\.?\s?\d+", r"usd", r"\$\s?\d+", r"dollars?",
        r"souvenirs?", r"shops?", r"shopping", r"stalls?", r"boutiques?",
        r"gift\s+shops?", r"gem\s+(?:shops?|factory|factories|stores?)",
        r"selling",
        r"donations?", r"commissions?", r"pushy", r"hassl(?:e|ed|ing)",
        r"tips?\s+(?:for|to)\s+the\s+guide",
    ],
    "Accessibility": [
        r"transport(?:ation)?", r"roads?", r"potholes?", r"bumpy", r"narrow\s+(?:road|lane|path)s?",
        r"tuk[\s-]?tuks?", r"tuktuks?", r"three[\s-]?wheelers?", r"taxis?", r"cabs?",
        r"uber", r"pickme", r"jeeps?", r"buses", r"bus",
        r"by\s+(?:train|rail|car|bus|road|taxi|tuk[\s-]?tuk|tuktuk|scooter|bike|motorbike)",
        r"(?:take|took|taking|catch|caught)\s+(?:a|the)\s+train",
        r"train\s+(?:ride|journey|trip|station|from|to)", r"railway\s+station", r"bus\s+stand|bus\s+station",
        r"drive\s+from", r"(?:hour|hours|hr|hrs|minute|minutes|min|mins)\s+(?:drive|ride|journey|walk|trek|hike|climb)",
        r"walking\s+distance", r"(?:long|short|steep|hard|tough|easy|uphill|downhill|gentle)\s+(?:walk|hike|trek|climb)",
        r"walk(?:ed|ing)?\s+(?:up|down)", r"walking\s+shoes", r"comfortable\s+(?:shoes|footwear)",
        r"climb(?:s|ed|ing)?", r"steps", r"stairs?", r"stair[\s-]?cases?", r"steep",
        r"hik(?:e|ed|es|ing)", r"trek(?:s|ked|king)?", r"uphill", r"slippery",
        r"far\s+(?:from|away|out)", r"(?:too|quite|very|bit|not|how|that)\s+far",
        r"(?:long|a\s+long)\s+way", r"remote", r"off\s+the\s+beaten\s+(?:track|path)",
        r"(?:easy|easily|difficult|hard|tricky)\s+to\s+(?:reach|get\s+to|find|access|get\s+there)",
        r"accessib(?:le|ility)", r"inaccessible", r"access", r"wheel\s?chairs?",
        r"elderly", r"disabled", r"mobility", r"directions", r"sign\s?posted",
        r"get(?:ting)?\s+there", r"to\s+reach", r"reachable", r"\d+\s?km", r"kilomet(?:er|re)s",
    ],
}

ASPECT_PATTERNS = {
    aspect: re.compile(r"\b(?:" + "|".join(f"(?:{p})" for p in pats) + r")(?!\w)", re.IGNORECASE)
    for aspect, pats in ASPECT_PATTERNS_RAW.items()
}


def find_aspect_match(text, aspect):
    """Return the first re.Match for `aspect` in `text`, or None."""
    return ASPECT_PATTERNS[aspect].search(str(text))


def tag_review(text):
    """Return the ", "-joined aspect list for one review, or "General"."""
    text = "" if text is None else str(text)
    tags = [a for a in ASPECTS if ASPECT_PATTERNS[a].search(text)]
    return ", ".join(tags) if tags else "General"


def aspect_flags(series, aspect):
    """Robust boolean Series: does a Mentioned_Aspects value contain `aspect` as a token?"""
    return series.fillna("").astype(str).apply(
        lambda s: aspect in [t.strip() for t in s.split(",")]
    )


def main():
    print("Loading cleaned data...")
    df = pd.read_csv(INPUT_CSV)
    print("Tagging reviews with destination-specific aspects...")
    df["Mentioned_Aspects"] = df["Clean_Review_Text"].apply(tag_review)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Success! Aspects tagged and saved to '{OUTPUT_CSV.name}'.")
    print("\n--- Aspect Frequency ---")
    for aspect in ASPECTS:
        print(f"{aspect}: {int(aspect_flags(df['Mentioned_Aspects'], aspect).sum())} reviews")


if __name__ == "__main__":
    main()
