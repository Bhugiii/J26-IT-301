"""
Re-apply the (fixed) aspect tagger to an already-scored dataset.

Overwrites ONLY the `Mentioned_Aspects` column of backend/ai_scored_data.csv.
Embeddings / Base_Reality_Score are left untouched, so no ML model is needed.

Usage:  python retag_scored_data.py [path/to/ai_scored_data.csv]
"""
from pathlib import Path
import sys

import pandas as pd

from tag_aspects import ASPECTS, aspect_flags, tag_review

HERE = Path(__file__).resolve().parent
DEFAULT_CSV = HERE.parent / "ai_scored_data.csv"


def main(csv_path=DEFAULT_CSV):
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path)
    before = {a: int(aspect_flags(df["Mentioned_Aspects"], a).sum()) for a in ASPECTS}
    df["Mentioned_Aspects"] = df["Clean_Review_Text"].apply(tag_review)
    after = {a: int(aspect_flags(df["Mentioned_Aspects"], a).sum()) for a in ASPECTS}
    df.to_csv(csv_path, index=False)
    print(f"Re-tagged {len(df)} reviews in {csv_path}")
    for a in ASPECTS:
        print(f"  {a:<18} {before[a]:>6} -> {after[a]:>6}")
    print(f"  {'General':<18} -> {int((df['Mentioned_Aspects'] == 'General').sum()):>6}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV)
