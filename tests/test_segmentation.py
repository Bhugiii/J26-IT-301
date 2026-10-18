"""Tests for the traveller segmentation component. Run with: python -m unittest discover tests"""
import json
import math
import unittest
from pathlib import Path

import pandas as pd

from api.services.segmentation_service import SegmentationService
from segmentation.features import build_features, dispersion_km, districts_in
from segmentation.profile_mapping import SHARED_FEATURES, assign, profile_to_features

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "data" / "segmentation" / "SYNTHETIC_tourist_behaviour_619.csv"
RESULTS = ROOT / "results" / "segmentation"


class FeatureTests(unittest.TestCase):
    def test_district_cells_split_on_commas_outside_brackets(self):
        cell = "Galle (Galle, Unawatuna, Hikkaduwa, Bentota), Kandy, Matale (Sigiriya, Dambulla)"
        self.assertEqual(districts_in(cell), ["Galle", "Kandy", "Matale"])

    def test_dispersion_is_zero_for_one_district_and_grows_with_spread(self):
        self.assertEqual(dispersion_km(["Kandy"]), 0.0)
        self.assertLess(dispersion_km(["Kandy", "Matale"]), dispersion_km(["Jaffna", "Matara"]))

    def test_synthetic_file_gives_31_complete_features(self):
        features = build_features(pd.read_csv(SYNTHETIC))
        self.assertEqual(features.shape, (619, 31))
        self.assertFalse(features.isna().any().any())


class ProfileMappingTests(unittest.TestCase):
    def test_profile_maps_to_every_shared_feature(self):
        features = profile_to_features({"budget": "15000", "tripDuration": "5", "interests": "Beach, Food",
                                        "preferredCrowd": "Low", "travelPace": "Active", "sustainabilityImportance": 1})
        self.assertEqual(set(features), set(SHARED_FEATURES))
        self.assertEqual(features["spend_band"], 2.0)
        self.assertAlmostEqual(features["log_trip_days"], math.log1p(5))
        self.assertEqual(features["values_protecting_the_environment"], 5.0)

    def test_missing_or_invalid_values_fall_back_to_defaults(self):
        features = profile_to_features({"budget": "abc", "tripDuration": "", "preferredCrowd": "Unknown"})
        self.assertEqual(features["spend_band"], 2.0)  # default LKR 10,000 a day
        self.assertEqual(features["values_avoiding_crowded_places"], 3.0)


@unittest.skipUnless((RESULTS / "assignment.json").exists(), "run python -m segmentation.pipeline first")
class ResultTests(unittest.TestCase):
    def setUp(self):
        self.service = SegmentationService(RESULTS)

    def test_results_are_complete_and_consistent(self):
        self.assertTrue(self.service.available)
        segments = self.service.overview()["segments"]
        self.assertEqual(sum(s["size"] for s in segments), self.service.overview()["meta"]["rows"])
        self.assertEqual(len(self.service.points()["points"]), self.service.overview()["meta"]["rows"])

    def test_assignment_returns_a_known_segment_with_strengths_summing_to_one(self):
        result = self.service.assign_profile({"budget": "6000", "tripDuration": "21", "interests": "Hiking, Nature",
                                              "travelPace": "Active", "travelStyle": "Budget Explorer"})
        ids = {s["id"] for s in self.service.overview()["segments"]}
        self.assertIn(result["segment_id"], ids)
        self.assertAlmostEqual(sum(d["match_strength"] for d in result["distances"]), 1.0, places=6)

    def test_no_personal_details_are_stored_in_results(self):
        text = " ".join(path.read_text(encoding="utf-8") for path in RESULTS.glob("*.json"))
        for column in ("Timestamp", "Which country do you live in?", "Which age group are you in?"):
            self.assertNotIn(column, text)

    def test_assign_uses_saved_model_without_scikit_learn(self):
        model = json.loads((RESULTS / "assignment.json").read_text(encoding="utf-8"))
        self.assertEqual(model["features"], SHARED_FEATURES)
        self.assertIn(assign({}, model)["segment_id"], model["centres"])


if __name__ == "__main__":
    unittest.main()
