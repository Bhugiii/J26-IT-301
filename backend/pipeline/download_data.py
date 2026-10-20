from pathlib import Path

import pandas as pd
from datasets import load_dataset

OUTPUT_CSV = Path(__file__).resolve().parent / "sri_lanka_reviews.csv"

print("Downloading dataset... Please wait, this might take a minute.")
dataset = load_dataset("UOM-CSE-E23/Sri-Lankan-Tourism-Review-Incongruence")
df = pd.DataFrame(dataset["train"])
print(f"Success! Downloaded {len(df)} reviews.")
df.to_csv(OUTPUT_CSV, index=False)
print(f"Data saved to '{OUTPUT_CSV}'.")
