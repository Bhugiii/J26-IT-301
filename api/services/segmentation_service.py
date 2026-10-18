"""Serve the traveller segments produced by `python -m segmentation.pipeline`."""
import json
from pathlib import Path

from segmentation.profile_mapping import assign

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = PROJECT_ROOT / "results" / "segmentation"
FILES = ("segments", "evaluation", "points", "assignment")


class SegmentationService:
    def __init__(self, results_dir=RESULTS_DIR):
        self.results_dir = Path(results_dir)
        self.data = {}
        self.reload()

    def reload(self):
        self.data = {}
        for name in FILES:
            path = self.results_dir / f"{name}.json"
            if path.exists():
                self.data[name] = json.loads(path.read_text(encoding="utf-8"))

    @property
    def available(self):
        return all(name in self.data for name in FILES)

    def overview(self):
        return self.data["segments"]

    def evaluation(self):
        return self.data["evaluation"]

    def points(self):
        return self.data["points"]

    def assign_profile(self, profile):
        model = self.data["assignment"]
        result = assign(profile, model)
        names = {s["id"]: s["name"] for s in self.data["segments"]["segments"]}
        result["segment_name"] = names[result["segment_id"]]
        for row in result["distances"]:
            row["segment_name"] = names[row["segment_id"]]
        result["data_source"] = model["meta"]["data_source"]
        result["agreement_with_full_model"] = model["agreement_with_full_model"]
        return result
