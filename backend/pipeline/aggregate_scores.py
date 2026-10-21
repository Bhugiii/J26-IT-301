"""
Step 4 of the pipeline: one summary row per destination.

Input : ../ai_scored_data.csv
Output: ../destination_summary.csv  (Location_Name, Total_Reviews,
        Average_Reality_Score, Crowding/Facilities/Commercialization/Accessibility_Mentions)
"""
from pathlib import Path

import pandas as pd

from tag_aspects import ASPECTS, aspect_flags

HERE = Path(__file__).resolve().parent
INPUT_CSV = HERE.parent / "ai_scored_data.csv"
OUTPUT_CSV = HERE.parent / "destination_summary.csv"


def main():
    print("Loading AI scored data...")
    df = pd.read_csv(INPUT_CSV)

    df["Base_Reality_Score"] = pd.to_numeric(df["Base_Reality_Score"], errors="coerce")
    df = df.dropna(subset=["Base_Reality_Score"]).copy()
    df["Match_Score_Percent"] = df["Base_Reality_Score"] * 100

    # Token-based flags (robust to NaN and to substrings of other labels)
    for aspect in ASPECTS:
        df[f"{aspect}_Mentions"] = aspect_flags(df["Mentioned_Aspects"], aspect).astype(int)

    print("Aggregating data for the dashboard...")
    agg = {
        "Total_Reviews": ("Match_Score_Percent", "count"),
        "Average_Reality_Score": ("Match_Score_Percent", "mean"),
    }
    agg.update({f"{a}_Mentions": (f"{a}_Mentions", "sum") for a in ASPECTS})
    summary_df = df.groupby("Location_Name").agg(**agg).reset_index()
    summary_df["Average_Reality_Score"] = summary_df["Average_Reality_Score"].round(1)

    summary_df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSuccess! Aggregated data for {len(summary_df)} destinations -> '{OUTPUT_CSV}'.")
    print(summary_df[["Location_Name", "Average_Reality_Score", "Total_Reviews", "Crowding_Mentions"]].head(10))


if __name__ == "__main__":
    main()
