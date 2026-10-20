"""
Step 3 of the pipeline: Sentence-BERT cosine similarity between each review and
its destination's marketing promise ("Base_Reality_Score", -1..1).

Input : tagged_master_data.csv (tag_aspects.py)
Output: ../ai_scored_data.csv   (read by the API)

Requires: pip install sentence-transformers torch
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
INPUT_CSV = HERE / "tagged_master_data.csv"
OUTPUT_CSV = HERE.parent / "ai_scored_data.csv"
MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"


def main():
    from sentence_transformers import SentenceTransformer, util

    print("1. Loading tagged data...")
    df = pd.read_csv(INPUT_CSV)

    print(f"2. Loading Multilingual Sentence-BERT ({MODEL_NAME})...")
    model = SentenceTransformer(MODEL_NAME)

    print("3. Generating embeddings...")
    reviews = df["Clean_Review_Text"].astype(str).tolist()
    promises = df["Promise_Text"].astype(str)
    # There are only ~60 distinct promises: encode each once, not once per review.
    unique_promises = promises.unique().tolist()
    promise_index = {p: i for i, p in enumerate(unique_promises)}
    promise_emb = model.encode(unique_promises, batch_size=32, convert_to_tensor=True,
                               show_progress_bar=True)
    review_emb = model.encode(reviews, batch_size=32, convert_to_tensor=True,
                              show_progress_bar=True)

    print("4. Calculating similarity scores...")
    idx = [promise_index[p] for p in promises]
    paired_promise_emb = promise_emb[idx]
    df["Base_Reality_Score"] = util.pairwise_cos_sim(paired_promise_emb, review_emb).cpu().numpy()

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Success! Saved {len(df)} scored reviews to '{OUTPUT_CSV}'.")


if __name__ == "__main__":
    main()
