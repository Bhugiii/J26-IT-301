from pathlib import Path
import json
import math
import os
import sqlite3
import uuid

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

FINAL_RECOMMENDATIONS_PATH = (
    PROJECT_ROOT
    / "results"
    / "final_demand_aware_recommendations.csv"
)
DESTINATIONS_PATH = PROJECT_ROOT / "data" / "features" / "destinations_with_crowd_predictions.csv"
STORAGE_DIR = Path(os.getenv("TRAVELMIND_STORAGE_DIR", str(PROJECT_ROOT / "data")))
PROFILE_DB_PATH = STORAGE_DIR / "traveler_profiles.sqlite3"

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
        self._initialize_profile_store()

        # Generate rank 1-10 for each user
        # using the existing validated row order.
        self.df["rank"] = (
            self.df.groupby("user_id").cumcount() + 1
        )

        self._validate_data()
        self.custom_profiles: dict[str, dict] = {}
        self._load_saved_profiles()

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
                "SELECT user_id, name, profile_json, recommendations_json "
                "FROM traveler_profiles ORDER BY rowid"
            ).fetchall()
        for user_id, name, profile_json, recommendations_json in rows:
            profile = json.loads(profile_json)
            self.custom_profiles[user_id] = profile
            recommendations = json.loads(recommendations_json)
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
            demand = (crowd_fit + sustainability) / 2
            destination_coordinates = (float(destination["latitude"]), float(destination["longitude"]))
            distance_km = _great_circle_km(origin, destination_coordinates) if origin else None
            distance_fit = max(0.0, 1 - distance_km / 800) if distance_km is not None else 0.5
            duration_hours = float(destination.get("duration_hours", 0) or 0)
            pace_fit = max(0.0, 1 - abs(duration_hours - pace_target_hours) / 8)
            factors = {
                "preference_score": preference,
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
            score = sum(weights[key] * factors[key] for key in weights)
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
        return ranked[:10]

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
        destinations = self.destinations.set_index("destination_id")
        days = [{"stops": [], "hours": 0.0, "areas": []} for _ in range(day_count)]
        candidates = recommendations.sort_values("rank").to_dict("records")
        for recommendation in candidates:
            destination_id = str(recommendation["destination_id"])
            if destination_id not in destinations.index:
                continue
            destination = destinations.loc[destination_id]
            duration = destination.get("duration_hours", 2.0)
            duration = 2.0 if pd.isna(duration) else max(0.5, float(duration))
            available_days = [day for day in days if day["hours"] + duration <= pace_hours]
            target = min(available_days or days, key=lambda day: (day["hours"], len(day["stops"])))
            if target["stops"] and target["hours"] + duration > pace_hours:
                continue
            distance = recommendation.get("distance_km")
            target["stops"].append({
                "destination_id": destination_id,
                "name": str(recommendation["name"]),
                "district": str(recommendation["district"]),
                "rank": int(recommendation["rank"]),
                "estimated_cost_lkr": recommendation.get("estimated_cost_lkr"),
                "visit_duration_hours": duration,
                "straight_line_distance_km": None if pd.isna(distance) else float(distance),
                "recommendation_reason": str(recommendation.get("explanation") or "Selected from your personalized ranking."),
            })
            target["hours"] += duration
            district = str(recommendation["district"])
            if district not in target["areas"]:
                target["areas"].append(district)
        itinerary_days = [
            {
                "day": index + 1,
                "area": " · ".join(day["areas"]) or "No destination matched this day",
                "estimated_visit_hours": round(day["hours"], 1),
                "stops": day["stops"],
            }
            for index, day in enumerate(days)
        ]
        return {
            "user_id": user_id,
            "traveler_name": profile.get("name") or user_id,
            "days": itinerary_days,
            "planning_note": (
                "Drafted from your ranked destinations and pace preference. Visit durations and destination cost figures are estimates. "
                "No verified activities, opening hours, road routes, travel times, meals, or total trip budget are available. "
                "Any displayed distance is straight-line distance, not driving distance."
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
