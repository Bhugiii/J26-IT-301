"""
Run the full TravelMind Component 03 data pipeline in order:

  1. process_data.py    sri_lanka_reviews.csv + promise_data.csv -> cleaned_master_data.csv
  2. tag_aspects.py     cleaned_master_data.csv -> tagged_master_data.csv
  3. run_ai_model.py    tagged_master_data.csv  -> ../ai_scored_data.csv   (needs sentence-transformers)
  4. aggregate_scores.py ../ai_scored_data.csv   -> ../destination_summary.csv

If sri_lanka_reviews.csv is missing, run `python download_data.py` first.

Usage:
  python run_pipeline.py              # all steps
  python run_pipeline.py --skip-ml    # steps 1, 2, 4 only (4 then uses the existing scored file)
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import aggregate_scores  # noqa: E402
import process_data  # noqa: E402
import tag_aspects  # noqa: E402


def main(argv):
    skip_ml = "--skip-ml" in argv
    if not process_data.REVIEWS_CSV.exists():
        sys.exit(f"Missing {process_data.REVIEWS_CSV.name}. Run `python download_data.py` first.")

    print("\n=== [1/4] process_data ===")
    process_data.main()
    print("\n=== [2/4] tag_aspects ===")
    tag_aspects.main()
    if skip_ml:
        print("\n=== [3/4] run_ai_model: SKIPPED (--skip-ml) ===")
    else:
        print("\n=== [3/4] run_ai_model ===")
        import run_ai_model
        run_ai_model.main()
    print("\n=== [4/4] aggregate_scores ===")
    aggregate_scores.main()
    print("\nPipeline complete.")


if __name__ == "__main__":
    main(sys.argv[1:])
