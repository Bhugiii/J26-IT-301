from pathlib import Path
import json
import math
import os
import re
import sqlite3
import uuid
from collections import Counter

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

FINAL_RECOMMENDATIONS_PATH = (
    PROJECT_ROOT
    / "results"
    / "final_demand_aware_recommendations.csv"
)
DESTINATIONS_PATH = PROJECT_ROOT / "data" / "features" / "destinations_with_crowd_predictions.csv"
FEATURES_DIR = PROJECT_ROOT / "data" / "features"
STORAGE_DIR = Path(os.getenv("TRAVELMIND_STORAGE_DIR", str(PROJECT_ROOT / "data")))
PROFILE_DB_PATH = STORAGE_DIR / "traveler_profiles.sqlite3"
SEMANTIC_WEIGHT = 0.20

MODEL_WEIGHTS = {
    "preference_score": 0.25,
    "budget_fit": 0.15,
    "predicted_crowd_fit": 0.20,
    "weather_fit": 0.10,
    "sustainability_fit": 0.10,
    "seasonality_fit": 0.05,
    "sentiment_fit": 0.10,
    "demand_suitability": 0.05,
}
STARTING_LOCATIONS = {
    "colombo": (6.9271, 79.8612), "kandy": (7.2906, 80.6337),
    "gampaha": (7.0840, 80.0098), "galle": (6.0535, 80.2210),
    "negombo": (7.2083, 79.8358), "jaffna": (9.6615, 80.0255),
    "trincomalee": (8.5874, 81.2152), "batticaloa": (7.7102, 81.6924),
    "anuradhapura": (8.3114, 80.4037), "matara": (5.9549, 80.5550),
    "kurunegala": (7.4863, 80.3623), "ratnapura": (6.6828, 80.3992),
    "badulla": (6.9934, 81.0550), "nuwara eliya": (6.9497, 80.7891),
}


def _great_circle_km(origin: tuple[float, float], target: tuple[float, float]) -> float:
    from math import asin, cos, radians, sin, sqrt

    lat1, lon1 = map(radians, origin)
    lat2, lon2 = map(radians, target)
    delta_lat, delta_lon = lat2 - lat1, lon2 - lon1
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 6371 * 2 * asin(sqrt(value))


class RecommendationService:

    @staticmethod
    def mark_pareto_frontier(recommendations: list[dict]) -> list[dict]:
        """Mark non-dominated options across preference, crowd, and sustainability fit."""
        objectives = (
            "preference_score",
            "predicted_crowd_fit",
            "sustainability_fit",
        )
        values = [
            tuple(float(item.get(key) or 0) for key in objectives)
            for item in recommendations
        ]
        for index, item in enumerate(recommendations):
            current = values[index]
            dominated = any(
                other_index != index
                and all(other >= score for other, score in zip(values[other_index], current))
                and any(other > score for other, score in zip(values[other_index], current))
                for other_index in range(len(recommendations))
            )
            item["pareto_optimal"] = not dominated
        return recommendations

    def __init__(self):
        if not FINAL_RECOMMENDATIONS_PATH.exists():
            raise FileNotFoundError(
                f"Final recommendations file not found: "
                f"{FINAL_RECOMMENDATIONS_PATH}"
            )

        self.df = pd.read_csv(
            FINAL_RECOMMENDATIONS_PATH
        )
        self.destinations = pd.read_csv(DESTINATIONS_PATH)
        self._load_semantic_artifacts()
        self._initialize_profile_store()

        # Generate rank 1-10 for each user
        # using the existing validated row order.
        self.df["rank"] = (
            self.df.groupby("user_id").cumcount() + 1
        )

        self._validate_data()
        self.custom_profiles: dict[str, dict] = {}
        self._load_saved_profiles()

    def _load_semantic_artifacts(self):
        """Load offline SBERT vectors without requiring a transformer runtime in the API."""
        try:
            destination_text = pd.read_csv(FEATURES_DIR / "destination_text.csv")
            user_text = pd.read_csv(FEATURES_DIR / "user_text.csv")
            destination_vectors = np.load(FEATURES_DIR / "destination_sbert_embeddings.npy")
            user_vectors = np.load(FEATURES_DIR / "user_sbert_embeddings.npy")
            if not destination_text["destination_id"].astype(str).equals(
                self.destinations["destination_id"].astype(str)
            ):
                raise ValueError("Destination embeddings are not aligned with the catalog.")
            if len(destination_vectors) != len(destination_text) or len(user_vectors) != len(user_text):
                raise ValueError("SBERT embedding rows do not match their text catalogs.")

            self.destination_vectors = self._normalize_vectors(destination_vectors)
            self.user_vectors = self._normalize_vectors(user_vectors)
            self.user_text_records = [
                Counter(re.findall(r"[a-z0-9]+", str(value).lower()))
                for value in user_text["user_preference_text"]
            ]
            self.semantic_model_name = "all-MiniLM-L6-v2 (offline SBERT embeddings)"
            self.semantic_enabled = True
        except (OSError, KeyError, ValueError) as error:
            # Keep the application usable if optional research artifacts are absent.
            self.destination_vectors = None
            self.user_vectors = None
            self.user_text_records = []
            self.semantic_model_name = "lexical and contextual fallback"
            self.semantic_enabled = False
            print(f"Semantic ranking is unavailable: {error}")

    @staticmethod
    def _normalize_vectors(vectors: np.ndarray) -> np.ndarray:
        values = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(values, axis=1, keepdims=True)
        return values / np.maximum(norms, 1e-12)

    @staticmethod
    def _profile_semantic_text(profile: dict) -> str:
        budget = float(profile.get("budget", 0) or 0)
        budget_band = "budget" if budget <= 7000 else "moderate" if budget <= 15000 else "premium"
        style_terms = {
            "nature & adventure": "nature hiking wildlife adventure waterfalls",
            "relaxation & leisure": "beach relaxation wellness nature",
            "culture & heritage": "heritage history culture religious",
            "wildlife & safari": "wildlife safari nature",
            "beach & coastal": "beach coastal relaxation",
            "budget explorer": "budget nature culture heritage beach",
        }
        style = str(profile.get("travelStyle", "")).strip().lower()
        weather_aliases = {"sunny": "sunny warm dry", "cool": "cool", "rainy": "rainy wet", "cloudy": "cloudy"}
        crowd = str(profile.get("preferredCrowd", "")).strip().lower()
        weather = str(profile.get("preferredWeather", "")).strip().lower()
        return " ".join((
            str(profile.get("interests", "")).replace(";", " ").replace(",", " "),
            style_terms.get(style, style),
            budget_band,
            crowd,
            weather_aliases.get(weather, weather),
            str(profile.get("startingLocation", "")),
            str(profile.get("travelPace", "")),
        ))

    @staticmethod
    def _token_cosine(left: Counter, right: Counter) -> float:
        shared = left.keys() & right.keys()
        numerator = sum(left[token] * right[token] for token in shared)
        denominator = math.sqrt(sum(value * value for value in left.values())) * math.sqrt(
            sum(value * value for value in right.values())
        )
        return numerator / denominator if denominator else 0.0

    def _semantic_scores(self, profile: dict) -> dict[str, float]:
        if not self.semantic_enabled:
            return {}
        query_tokens = Counter(re.findall(r"[a-z0-9]+", self._profile_semantic_text(profile).lower()))
        similarities = np.asarray(
            [self._token_cosine(query_tokens, record) for record in self.user_text_records],
            dtype=np.float32,
        )
        top_indices = np.argsort(similarities)[-5:]
        selected_similarities = similarities[top_indices]
        weights = np.exp((selected_similarities - selected_similarities.max()) / 0.12)
        weights /= max(float(weights.sum()), 1e-12)
        query_vector = np.sum(self.user_vectors[top_indices] * weights[:, None], axis=0)
        norm = max(float(np.linalg.norm(query_vector)), 1e-12)
        cosine_scores = self.destination_vectors @ (query_vector / norm)
        low, high = float(cosine_scores.min()), float(cosine_scores.max())
        if high - low < 1e-8:
            normalized = np.full_like(cosine_scores, 0.5)
        else:
            normalized = (cosine_scores - low) / (high - low)
        return {
            str(destination_id): float(score)
            for destination_id, score in zip(self.destinations["destination_id"], normalized)
        }

    def _initialize_profile_store(self):
        PROFILE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(PROFILE_DB_PATH) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS traveler_profiles ("
                "user_id TEXT PRIMARY KEY, name TEXT NOT NULL, "
                "profile_json TEXT NOT NULL, recommendations_json TEXT NOT NULL)"
            )

    def _load_saved_profiles(self):
        with sqlite3.connect(PROFILE_DB_PATH) as connection:
            rows = connection.execute(
                "SELECT user_id, name, profile_json "
                "FROM traveler_profiles ORDER BY rowid"
            ).fetchall()
        for user_id, name, profile_json in rows:
            profile = json.loads(profile_json)
            self.custom_profiles[user_id] = profile
            # Refresh saved custom profiles with the current ranking model on service startup.
            recommendations = self._rank_for_profile(user_id, profile)
            with sqlite3.connect(PROFILE_DB_PATH) as connection:
                connection.execute(
                    "UPDATE traveler_profiles SET recommendations_json=? WHERE user_id=?",
                    (json.dumps(recommendations), user_id),
                )
            frame = pd.DataFrame(recommendations)
            if not frame.empty:
                self.df = pd.concat([self.df, frame], ignore_index=True)

    def _rank_for_profile(
        self,
        user_id: str,
        profile: dict,
        scenario_weights: dict | None = None,
        preference_feedback: dict[str, int] | None = None,
    ) -> list[dict]:
        budget = float(profile["budget"])
        interests = {
            value.strip().lower().replace(" ", "_")
            for value in profile["interests"].replace(";", ",").split(",")
            if value.strip()
        }
        style_tags = {
            "nature & adventure": {"nature", "hiking", "wildlife", "adventure", "waterfalls"},
            "relaxation & leisure": {"beach", "relaxation", "wellness", "nature"},
            "culture & heritage": {"heritage", "history", "culture", "religious"},
            "wildlife & safari": {"wildlife", "safari", "nature"},
            "beach & coastal": {"beach", "coastal", "relaxation"},
            "budget explorer": {"nature", "culture", "heritage", "beach"},
        }.get(profile.get("travelStyle", "").strip().lower(), set())
        crowd_target = {"low": 25, "medium": 50, "high": 75}.get(
            profile["preferredCrowd"].strip().lower(), 25
        )
        origin = STARTING_LOCATIONS.get(profile.get("startingLocation", "").strip().lower())
        pace_target_hours = {"relaxed": 2.5, "balanced": 4.0, "active": 6.0}.get(
            profile.get("travelPace", "Balanced").strip().lower(), 4.0
        )
        ranked = []
        semantic_scores = self._semantic_scores(profile)
        for _, destination in self.destinations.iterrows():
            tags = {
                value.strip().lower().replace(" ", "_")
                for value in f"{destination.get('interest_tags', '')};{destination.get('category', '')}".replace(",", ";").split(";")
                if value.strip()
            }
            interest_match = len(interests & tags) / max(1, len(interests))
            style_match = len(style_tags & tags) / max(1, len(style_tags)) if style_tags else interest_match
            preference = 0.75 * interest_match + 0.25 * style_match
            cost = max(0.0, float(destination.get("estimated_cost_lkr", 0) or 0))
            budget_fit = min(1.0, budget / cost) if cost else 1.0
            crowd = float(destination.get("predicted_crowd_score", destination.get("crowd_score", 50)) or 0)
            crowd_fit = max(0.0, 1 - abs(crowd - crowd_target) / 100)
            rain = float(destination.get("weather_rain_risk", 0.5) or 0)
            temperature = float(destination.get("weather_temp_c", 25) or 25)
            weather_preference = profile["preferredWeather"].strip().lower()
            if weather_preference == "rainy":
                weather_fit = rain
            elif weather_preference == "cloudy":
                weather_fit = max(0.0, 1 - abs(rain - 0.5) * 2)
            elif weather_preference == "cool":
                weather_fit = max(0.0, 1 - abs(temperature - 20) / 20)
            else:
                weather_fit = 1 - rain
            sustainability = float(destination.get("sustainability_score", 0) or 0) / 100
            seasonality = float(destination.get("seasonality_score", 0) or 0) / 100
            sentiment_values = [
                float(destination.get(column, 0) or 0)
                for column in ("sentiment_nature", "sentiment_service", "sentiment_value")
            ]
            sentiment = sum(sentiment_values) / len(sentiment_values)
            semantic_fit = semantic_scores.get(str(destination["destination_id"]), preference)
            demand = (crowd_fit + sustainability) / 2
            destination_coordinates = (float(destination["latitude"]), float(destination["longitude"]))
            distance_km = _great_circle_km(origin, destination_coordinates) if origin else None
            distance_fit = max(0.0, 1 - distance_km / 800) if distance_km is not None else 0.5
            duration_hours = float(destination.get("duration_hours", 0) or 0)
            pace_fit = max(0.0, 1 - abs(duration_hours - pace_target_hours) / 8)
            factors = {
                "preference_score": preference,
                "semantic_fit": semantic_fit,
                "budget_fit": budget_fit,
                "predicted_crowd_fit": crowd_fit,
                "weather_fit": max(0.0, min(1.0, weather_fit)),
                "sustainability_fit": sustainability,
                "seasonality_fit": seasonality,
                "sentiment_fit": sentiment,
                "demand_suitability": demand,
                "distance_fit": distance_fit,
                "pace_fit": pace_fit,
            }
            sustainability_importance = max(
                0.0, min(1.0, float(profile.get("sustainabilityImportance", 0.5)))
            )
            sustainability_weight = 0.05 + 0.15 * sustainability_importance
            other_weight = 1 - sustainability_weight - 0.15
            weights = {
                key: value * other_weight / (1 - MODEL_WEIGHTS["sustainability_fit"])
                for key, value in MODEL_WEIGHTS.items()
                if key != "sustainability_fit"
            }
            weights["sustainability_fit"] = sustainability_weight
            weights["distance_fit"] = 0.10
            weights["pace_fit"] = 0.05
            base_score = sum(weights[key] * factors[key] for key in weights)
            semantic_weight = SEMANTIC_WEIGHT if self.semantic_enabled else 0.0
            score = base_score * (1 - semantic_weight) + semantic_weight * semantic_fit
            scenario_score = None
            if scenario_weights is not None:
                weight_total = sum(max(0, int(value)) for value in scenario_weights.values())
                weighted_signals = (
                    preference * max(0, int(scenario_weights.get("preference", 0)))
                    + crowd_fit * max(0, int(scenario_weights.get("crowd", 0)))
                    + sustainability * max(0, int(scenario_weights.get("sustainability", 0)))
                )
                scenario_score = weighted_signals / max(1, weight_total)
                feedback_value = int((preference_feedback or {}).get(str(destination.get("category", "")).strip().lower(), 0))
                scenario_score = max(0.0, min(1.0, scenario_score + max(-3, min(3, feedback_value)) * 0.05))
            explanations = sorted(factors.items(), key=lambda item: item[1], reverse=True)[:2]
            ranked.append({
                "user_id": user_id,
                "destination_id": str(destination["destination_id"]),
                "name": str(destination["name"]),
                "category": str(destination["category"]),
                "district": str(destination["district"]),
                "distance_km": distance_km,
                "duration_hours": duration_hours,
                "estimated_cost_lkr": cost,
                "sustainability_score": float(destination.get("sustainability_score", 0) or 0),
                "seasonality_score": float(destination.get("seasonality_score", 0) or 0),
                "weather_temp_c": temperature,
                "weather_rain_risk": rain,
                "weather_suitability": float(destination.get("weather_suitability", 0) or 0),
                "predicted_crowd_score": crowd,
                "predicted_crowd_level": str(destination.get("predicted_crowd_level", "Unknown")),
                "preference_score": preference,
                "semantic_fit": semantic_fit,
                "budget_fit": budget_fit,
                "predicted_crowd_fit": crowd_fit,
                "weather_fit": factors["weather_fit"],
                "sustainability_fit": sustainability,
                "sentiment_fit": sentiment,
                "demand_suitability": demand,
                "distance_fit": distance_fit,
                "pace_fit": pace_fit,
                "demand_aware_score": score,
                "scenario_score": scenario_score,
                "explanation": "Best fit signals: " + ", ".join(
                    f"{key.replace('_', ' ')} ({value:.0%})" for key, value in explanations
                ),
            })
        ranking_key = "scenario_score" if scenario_weights is not None else "demand_aware_score"
        ranked.sort(key=lambda item: item[ranking_key] if item[ranking_key] is not None else 0, reverse=True)
        distance_limit = profile.get("maxDistanceKm", "Any distance").strip().lower()
        if origin and distance_limit not in {"", "any distance"}:
            try:
                max_distance = float(distance_limit)
                ranked = [item for item in ranked if item["distance_km"] <= max_distance]
            except ValueError:
                pass
        for rank, item in enumerate(ranked[:10], start=1):
            item["rank"] = rank
        return self.mark_pareto_frontier(ranked[:10])

    def save_profile(
        self,
        profile: dict,
        user_id: str | None = None,
        owner_account_id: int | None = None,
    ) -> str:
        name = profile.get("name", "").strip()
        if not name:
            raise ValueError("Enter a traveler name.")
        try:
            budget = float(profile.get("budget", 0))
        except (TypeError, ValueError) as error:
            raise ValueError("Enter a valid daily budget.") from error
        if not math.isfinite(budget) or budget <= 0:
            raise ValueError("Daily budget must be greater than zero.")
        if not profile.get("startingLocation", "").strip():
            raise ValueError("Enter your starting location.")
        if not profile.get("interests", "").strip():
            raise ValueError("Add at least one interest.")
        saved_profile = {**profile, "budget": str(budget)}
        if user_id and user_id in self.custom_profiles:
            target_id = user_id
        else:
            target_id = f"TRV-{uuid.uuid4().hex[:10].upper()}"
        recommendations = self._rank_for_profile(target_id, saved_profile)
        with sqlite3.connect(PROFILE_DB_PATH) as connection:
            connection.execute(
                "INSERT INTO traveler_profiles (user_id, name, profile_json, recommendations_json, owner_account_id) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET "
                "name=excluded.name, profile_json=excluded.profile_json, "
                "recommendations_json=excluded.recommendations_json, "
                "owner_account_id=COALESCE(excluded.owner_account_id, traveler_profiles.owner_account_id)",
                (target_id, name, json.dumps(saved_profile), json.dumps(recommendations), owner_account_id),
            )
        self.custom_profiles[target_id] = saved_profile
        existing = self.df[self.df["user_id"].astype(str) != target_id]
        self.df = pd.concat([existing, pd.DataFrame(recommendations)], ignore_index=True)
        return target_id

    def get_profile(self, user_id: str) -> dict | None:
        return self.custom_profiles.get(user_id)

    def build_itinerary(self, user_id: str, profile: dict) -> dict:
        recommendations = self.get_recommendations(user_id)
        if recommendations is None:
            return None
        try:
            day_count = max(1, min(7, int(profile.get("tripDuration", 3))))
        except (TypeError, ValueError):
            day_count = 3
        pace_hours = {"relaxed": 4.0, "balanced": 6.0, "active": 8.0}.get(
            profile.get("travelPace", "Balanced").strip().lower(), 6.0
        )
        pace_stops = {"relaxed": 2, "balanced": 3, "active": 4}.get(
            profile.get("travelPace", "Balanced").strip().lower(), 3
        )
        try:
            daily_budget = max(0.0, float(profile.get("budget", 0) or 0))
        except (TypeError, ValueError):
            daily_budget = 0.0
        destinations = self.destinations.set_index("destination_id")
        days = [
            {"stops": [], "hours": 0.0, "cost": 0.0, "areas": [], "categories": Counter()}
            for _ in range(day_count)
        ]
        candidates = recommendations.sort_values("rank").to_dict("records")
        for recommendation in candidates:
            destination_id = str(recommendation["destination_id"])
            if destination_id not in destinations.index:
                continue
            destination = destinations.loc[destination_id]
            duration = destination.get("duration_hours", 2.0)
            duration = 2.0 if pd.isna(duration) else max(0.5, float(duration))
            available_days = [
                day for day in days
                if day["hours"] + duration <= pace_hours and len(day["stops"]) < pace_stops
            ]
            if not available_days:
                continue
            district = str(recommendation["district"])
            same_area_days = [day for day in available_days if district in day["areas"]]
            target = min(
                same_area_days or available_days,
                key=lambda day: (day["hours"], len(day["stops"]), day["cost"]),
            )
            distance = recommendation.get("distance_km")
            estimated_cost = recommendation.get("estimated_cost_lkr")
            estimated_cost = 0.0 if estimated_cost is None or pd.isna(estimated_cost) else float(estimated_cost)
            target["stops"].append({
                "destination_id": destination_id,
                "name": str(recommendation["name"]),
                "district": str(recommendation["district"]),
                "rank": int(recommendation["rank"]),
                "estimated_cost_lkr": estimated_cost,
                "visit_duration_hours": duration,
                "straight_line_distance_km": None if pd.isna(distance) else float(distance),
                "recommendation_reason": str(recommendation.get("explanation") or "Selected from your personalized ranking."),
            })
            target["hours"] += duration
            target["cost"] += estimated_cost
            target["categories"][str(recommendation.get("category", "") or "Other")] += 1
            if district not in target["areas"]:
                target["areas"].append(district)
        itinerary_days = [
            {
                "day": index + 1,
                "area": " / ".join(day["areas"]) or "No destination matched this day",
                "theme": day["categories"].most_common(1)[0][0] if day["categories"] else "Open day",
                "estimated_visit_hours": round(day["hours"], 1),
                "estimated_cost_lkr": round(day["cost"], 2),
                "over_daily_budget": bool(daily_budget and day["cost"] > daily_budget),
                "stops": day["stops"],
            }
            for index, day in enumerate(days)
        ]
        return {
            "user_id": user_id,
            "traveler_name": profile.get("name") or user_id,
            "days": itinerary_days,
            "daily_budget_lkr": daily_budget,
            "estimated_total_cost_lkr": round(sum(day["estimated_cost_lkr"] for day in itinerary_days), 2),
            "planning_note": (
                f"Drafted from your personalized ranking, {profile.get('travelPace', 'Balanced').lower()} pace, and trip length. "
                "Stops are grouped by district where possible and limited by estimated visit hours and daily stop count. "
                "Daily and total costs sum destination estimates only; they are not a complete trip budget and exclude transport, meals, and fees. "
                "Opening hours, activities, road routes, and travel times are not verified. Distances are straight-line estimates."
            ),
        }

    def _validate_data(self):
        expected_users = 50
        expected_recommendations = 500

        actual_users = self.df["user_id"].nunique()
        actual_recommendations = len(self.df)

        if actual_users != expected_users:
            raise ValueError(
                f"Expected {expected_users} users, "
                f"found {actual_users}"
            )

        if actual_recommendations != expected_recommendations:
            raise ValueError(
                f"Expected {expected_recommendations} "
                f"recommendations, "
                f"found {actual_recommendations}"
            )

        recommendations_per_user = (
            self.df.groupby("user_id").size()
        )

        if not (recommendations_per_user == 10).all():
            raise ValueError(
                "Every user must have exactly "
                "10 recommendations."
            )

    def get_all_users(self, account_id: int | None = None):
        demo_users = self.df[self.df["user_id"].astype(str).str.startswith("U")]["user_id"].astype(str).unique().tolist()
        with sqlite3.connect(PROFILE_DB_PATH) as connection:
            if account_id is None:
                rows = connection.execute(
                    "SELECT user_id FROM traveler_profiles WHERE owner_account_id IS NULL"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT user_id FROM traveler_profiles WHERE owner_account_id=?",
                    (account_id,),
                ).fetchall()
        return sorted(set(demo_users + [row[0] for row in rows]))

    def get_recommendations(self, user_id: str):

        user_data = self.df[
            self.df["user_id"].astype(str) == str(user_id)
        ].copy()

        if user_data.empty:
            return None

        return user_data

    def get_recommendation(
        self,
        user_id: str,
        rank: int
    ):

        user_data = self.get_recommendations(
            user_id
        )

        if user_data is None:
            return None

        recommendation = user_data[
            user_data["rank"] == rank
        ]

        if recommendation.empty:
            return None

        return recommendation.iloc[0]
