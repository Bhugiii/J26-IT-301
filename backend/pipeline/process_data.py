"""
Step 1 of the pipeline: clean review text and pair every review with its
destination's marketing "promise".

Input : sri_lanka_reviews.csv (download_data.py), promise_data.csv
Output: cleaned_master_data.csv
"""
from pathlib import Path
import re
import unicodedata

import pandas as pd

HERE = Path(__file__).resolve().parent
REVIEWS_CSV = HERE / "sri_lanka_reviews.csv"
PROMISE_CSV = HERE / "promise_data.csv"
OUTPUT_CSV = HERE / "cleaned_master_data.csv"

# Apostrophe look-alikes: curly quotes, primes, backtick, and the cp1252 byte
# 0x92 that survives in the dataset as the C1 control char U+0092
# (e.g. 'Lipton\x92s Seat').
_APOSTROPHES = "’‘ʼ′´`\x92\x91"
_APOS_TABLE = str.maketrans({c: "'" for c in _APOSTROPHES})


def tidy_name(name):
    """Display-safe destination name: straight apostrophes, single spaces."""
    name = unicodedata.normalize("NFKC", str(name)).translate(_APOS_TABLE)
    return " ".join(name.split())


def join_key(name):
    """Normalised key used ONLY for joining reviews to promises.
    'Lipton\\x92s Seat', 'Liptons Seat' and "Lipton's Seat" all -> 'liptons seat'."""
    return tidy_name(name).replace("'", "").casefold()


def clean_text(text):
    text = unicodedata.normalize("NFKC", str(text)).translate(_APOS_TABLE)
    text = re.sub(r"<.*?>", " ", text)            # HTML tags
    text = re.sub(r"http\S+", " ", text)          # URLs
    # Remove emojis/symbols. Keep letters (incl. accented), digits, basic
    # punctuation, apostrophes and hyphens ("tuk-tuk", "well-maintained").
    text = re.sub(r"[^\w\s\.\,\!\?\'\-]", " ", text)
    text = text.replace("_", " ")
    text = " ".join(text.split())                 # collapse whitespace
    return text.strip()


def main():
    print("1. Loading reality (reviews) and promise (marketing) data...")
    reality_df = pd.read_csv(REVIEWS_CSV)
    promise_df = pd.read_csv(PROMISE_CSV)

    print("2. Cleaning the review text...")
    reality_df = reality_df.dropna(subset=["Text", "Location_Name"]).copy()
    reality_df["Clean_Review_Text"] = reality_df["Text"].apply(clean_text)
    reality_df = reality_df[reality_df["Clean_Review_Text"].str.len() > 0]
    reality_df["Location_Name"] = reality_df["Location_Name"].apply(tidy_name)

    print("3. Merging promise text with review text (normalised names)...")
    promise_df = promise_df.dropna(subset=["Destination_Name", "Promise_Text"]).copy()
    promise_df["Destination_Name"] = promise_df["Destination_Name"].apply(tidy_name)
    promise_df["_key"] = promise_df["Destination_Name"].apply(join_key)
    promise_df = promise_df.drop_duplicates(subset="_key", keep="first")
    reality_df["_key"] = reality_df["Location_Name"].apply(join_key)

    merged_df = pd.merge(reality_df, promise_df, on="_key", how="inner").drop(columns="_key")

    unmatched = sorted(set(promise_df["Destination_Name"]) - set(merged_df["Destination_Name"]))
    if unmatched:
        print(f"   NOTE: {len(unmatched)} promise(s) had no reviews: {unmatched}")

    merged_df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSuccess! Created '{OUTPUT_CSV.name}' with {len(merged_df)} clean, paired reviews "
          f"for {merged_df['Location_Name'].nunique()} destinations.")


if __name__ == "__main__":
    main()
