import os
import pandas as pd

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.models import (
    ChatRequest,
    ChatResponse,
    AuthLoginRequest,
    AuthRegisterRequest,
    HealthResponse,
    ItineraryRequest,
    ItineraryResponse,
    Recommendation,
    RecommendationResponse,
    ScenarioRankingRequest,
    TravelerProfile,
)

from api.services.recommendation_service import (
    RecommendationService,
)
from api.services.explainability_chat_service import (
    ExplainabilityChatService,
)
from api.services.auth_service import AuthService


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="Smart Tourism Recommendation API",
    description=(
        "AI-Based Smart Tourism Recommendation, "
        "Crowd Prediction and Analytics System"
    ),
    version="1.0.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # The frontend does not use cookie-based authentication. Wildcard origins
    # and credentialed requests are rejected by browsers, so keep credentials off.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# RECOMMENDATION SERVICE
# =========================================================

recommendation_service = RecommendationService()
auth_service = AuthService()
explainability_chat_service = ExplainabilityChatService(
    recommendation_service
)


# =========================================================
# PROJECT / RESULTS PATH
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

RESULTS_DIR = os.path.join(
    BASE_DIR,
    "results"
)
bearer_auth = HTTPBearer(auto_error=False)


def optional_account(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_auth)):
    if credentials is None:
        return None
    try:
        return auth_service.verify_token(credentials.credentials)
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


def require_account(account=Depends(optional_account)):
    if account is None:
        raise HTTPException(status_code=401, detail="Sign in to access your account.")
    return account


def ensure_profile_access(user_id: str, account):
    if recommendation_service.get_profile(user_id) is None:
        return
    owner_id = auth_service.get_profile_owner(user_id)
    if owner_id is not None and (account is None or owner_id != account["id"]):
        raise HTTPException(status_code=404, detail="Traveler profile not found.")


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "message": "Smart Tourism Recommendation API",
        "status": "running",
        "version": "1.0.0",
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get(
    "/health",
    response_model=HealthResponse,
)
def health():

    return {
        "status": "healthy",
        "users": len(
            recommendation_service.get_all_users()
        ),
        "recommendations": len(
            recommendation_service.df
        ),
    }


# =========================================================
# USERS
# =========================================================

@app.get("/users")
def get_users(account=Depends(optional_account)):

    return {
        "users": (
            recommendation_service
            .get_all_users(account["id"] if account else None)
        )
    }


@app.post("/profiles")
def create_traveler_profile(profile: TravelerProfile, account=Depends(optional_account)):
    try:
        user_id = recommendation_service.save_profile(
            profile.model_dump(), owner_account_id=account["id"] if account else None
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"user_id": user_id, "profile": profile.model_dump()}


@app.get("/profiles/{user_id}")
def get_traveler_profile(user_id: str, account=Depends(optional_account)):
    ensure_profile_access(user_id, account)
    profile = recommendation_service.get_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Traveler profile not found.")
    return {"user_id": user_id, "profile": profile}


@app.put("/profiles/{user_id}")
def update_traveler_profile(user_id: str, profile: TravelerProfile, account=Depends(optional_account)):
    ensure_profile_access(user_id, account)
    if recommendation_service.get_profile(user_id) is None:
        raise HTTPException(status_code=404, detail="Traveler profile not found.")
    try:
        recommendation_service.save_profile(
            profile.model_dump(), user_id=user_id,
            owner_account_id=account["id"] if account else None,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"user_id": user_id, "profile": profile.model_dump()}


@app.post("/auth/register")
def register_account(request: AuthRegisterRequest):
    try:
        return auth_service.register(request.email, request.password, request.claim_profile_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/auth/login")
def login_account(request: AuthLoginRequest):
    try:
        return auth_service.login(request.email, request.password)
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@app.get("/account/profiles")
def get_account_profiles(account=Depends(require_account)):
    return {"profiles": auth_service.get_account_profiles(account["id"])}


@app.post("/auth/logout")
def logout_account(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_auth)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Sign in to access your account.")
    try:
        auth_service.revoke_token(credentials.credentials)
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=401, detail="Your session is invalid.") from error
    return {"status": "signed out"}


@app.get("/assistant/status")
def get_assistant_status():
    """Expose only whether the assistant is configured, never the secret."""
    return explainability_chat_service.configuration_status()


@app.post("/itinerary/{user_id}", response_model=ItineraryResponse)
def create_personalized_itinerary(
    user_id: str,
    request: ItineraryRequest,
    account=Depends(optional_account),
):
    ensure_profile_access(user_id, account)
    result = recommendation_service.build_itinerary(
        user_id,
        request.profile.model_dump(),
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found.")
    return result


# =========================================================
# HELPER FUNCTION
# =========================================================

def convert_value(value):

    if pd.isna(value):
        return None

    return value


def row_to_recommendation(row):

    return Recommendation(

        rank=int(row["rank"]),

        destination_id=str(
            row["destination_id"]
        ),

        name=str(
            row["name"]
        ),

        category=str(
            row["category"]
        ),

        district=str(
            row["district"]
        ),

        distance_km=convert_value(row.get("distance_km")),

        duration_hours=convert_value(row.get("duration_hours")),

        estimated_cost_lkr=convert_value(
            row["estimated_cost_lkr"]
        ),

        sustainability_score=convert_value(
            row["sustainability_score"]
        ),

        seasonality_score=convert_value(
            row["seasonality_score"]
        ),

        weather_temp_c=convert_value(
            row["weather_temp_c"]
        ),

        weather_rain_risk=convert_value(
            row["weather_rain_risk"]
        ),

        weather_suitability=convert_value(
            row["weather_suitability"]
        ),

        predicted_crowd_score=convert_value(
            row["predicted_crowd_score"]
        ),

        predicted_crowd_level=convert_value(
            row["predicted_crowd_level"]
        ),

        preference_score=convert_value(
            row["preference_score"]
        ),

        budget_fit=convert_value(
            row["budget_fit"]
        ),

        predicted_crowd_fit=convert_value(
            row["predicted_crowd_fit"]
        ),

        weather_fit=convert_value(
            row["weather_fit"]
        ),

        sustainability_fit=convert_value(
            row["sustainability_fit"]
        ),

        distance_fit=convert_value(row.get("distance_fit")),

        pace_fit=convert_value(row.get("pace_fit")),

        sentiment_fit=convert_value(
            row["sentiment_fit"]
        ),

        demand_suitability=convert_value(
            row["demand_suitability"]
        ),

        demand_aware_score=convert_value(
            row["demand_aware_score"]
        ),

        scenario_score=convert_value(row.get("scenario_score")),

        explanation=convert_value(
            row["explanation"]
        ),
    )


# =========================================================
# MODEL EVALUATION
# =========================================================

@app.get("/evaluation")
def get_evaluation():

    model_metrics_path = os.path.join(
        RESULTS_DIR,
        "model_comparison_metrics.csv"
    )

    comparison_path = os.path.join(
        RESULTS_DIR,
        "b4_vs_demand_aware_comparison.csv"
    )

    ndcg_path = os.path.join(
        RESULTS_DIR,
        "ndcg_evaluation.csv"
    )

    demand_metrics_path = os.path.join(
        RESULTS_DIR,
        "demand_aware_metrics.csv"
    )

    # -----------------------------------------------------
    # Check files
    # -----------------------------------------------------

    required_files = [
        model_metrics_path,
        comparison_path,
        ndcg_path,
        demand_metrics_path,
    ]

    missing_files = [
        path
        for path in required_files
        if not os.path.exists(path)
    ]

    if missing_files:

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Evaluation files are missing.",
                "missing_files": missing_files,
            },
        )

    # -----------------------------------------------------
    # Load CSV files
    # -----------------------------------------------------

    model_metrics = pd.read_csv(
        model_metrics_path
    )

    comparison = pd.read_csv(
        comparison_path
    )

    ndcg = pd.read_csv(
        ndcg_path
    )

    demand_metrics = pd.read_csv(
        demand_metrics_path
    )

    # -----------------------------------------------------
    # B1 - B4 models
    # -----------------------------------------------------

    models = []

    for _, row in model_metrics.iterrows():

        model_name = str(
            row["Model"]
        )

        if model_name.startswith("B1"):
            model_id = "B1"
            display_name = "General Baseline"

        elif model_name.startswith("B2"):
            model_id = "B2"
            display_name = "Content-Based"

        elif model_name.startswith("B3"):
            model_id = "B3"
            display_name = "Context-Aware"

        elif model_name.startswith("B4"):
            model_id = "B4"
            display_name = "Hybrid"

        else:
            model_id = model_name
            display_name = model_name

        models.append(
            {
                "id": model_id,
                "name": display_name,
                "precision_at_5": float(
                    row["Precision@5"]
                ),
                "recall_at_5": float(
                    row["Recall@5"]
                ),
                "ndcg_at_5": float(
                    row["NDCG@5"]
                ),
            }
        )

    # -----------------------------------------------------
    # Proposed Demand-Aware model
    # -----------------------------------------------------

    demand_aware_row = comparison[
        comparison["Model"]
        == "Final Demand-Aware Hybrid"
    ]

    if demand_aware_row.empty:

        raise HTTPException(
            status_code=500,
            detail=(
                "Final Demand-Aware Hybrid "
                "evaluation row not found."
            ),
        )

    demand_row = demand_aware_row.iloc[0]

    models.append(
        {
            "id": "PROPOSED",
            "name": "Demand-Aware AI",
            "precision_at_5": float(
                demand_row["Precision@5"]
            ),
            "recall_at_5": float(
                demand_row["Recall@5"]
            ),
            "ndcg_at_5": float(
                demand_row["NDCG@5"]
            ),
        }
    )

    # -----------------------------------------------------
    # NDCG by K
    # -----------------------------------------------------

    ndcg_by_k = []

    for _, row in ndcg.iterrows():

        ndcg_by_k.append(
            {
                "k": int(row["k"]),
                "b5_ndcg": float(
                    row["B5_NDCG"]
                ),
                "demand_aware_ndcg": float(
                    row["Demand_Aware_NDCG"]
                ),
                "ndcg_change": float(
                    row["NDCG_change"]
                ),
            }
        )

    # -----------------------------------------------------
    # Demand-aware system statistics
    # -----------------------------------------------------

    def get_metric(metric_name):

        rows = demand_metrics[
            demand_metrics["metric"]
            == metric_name
        ]

        if rows.empty:
            return None

        return float(
            rows.iloc[0]["value"]
        )

    demand_aware_statistics = {
        "total_recommendations": get_metric(
            "total_recommendations"
        ),
        "unique_users": get_metric(
            "unique_users"
        ),
        "unique_destinations": get_metric(
            "unique_destinations"
        ),
        "mean_sbert_hybrid_score": get_metric(
            "mean_sbert_hybrid_score"
        ),
        "mean_predicted_crowd_score": get_metric(
            "mean_predicted_crowd_score"
        ),
        "mean_crowd_suitability": get_metric(
            "mean_crowd_suitability"
        ),
        "mean_demand_aware_score": get_metric(
            "mean_demand_aware_score"
        ),
        "changed_rankings": get_metric(
            "changed_rankings"
        ),
        "unchanged_rankings": get_metric(
            "unchanged_rankings"
        ),
    }

    # -----------------------------------------------------
    # Final response
    # -----------------------------------------------------

    return {
        "models": models,
        "ndcg_by_k": ndcg_by_k,
        "demand_aware_statistics": (
            demand_aware_statistics
        ),
    }


# =========================================================
# ALL RECOMMENDATIONS FOR A USER
# =========================================================

@app.post(
    "/assistant/chat/{user_id}",
    response_model=ChatResponse,
)
async def explain_recommendations(
    user_id: str,
    request: ChatRequest,
    account=Depends(optional_account),
):
    ensure_profile_access(user_id, account)
    if not request.question.strip():
        raise HTTPException(
            status_code=422,
            detail="Question cannot be blank.",
        )

    try:
        result = await explainability_chat_service.answer(
            user_id,
            request,
        )
    except RuntimeError as error:
        status_code = 503 if "OPENAI_API_KEY is missing" in str(error) else 502
        raise HTTPException(
            status_code=status_code,
            detail=str(error),
        ) from error

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"User '{user_id}' not found.",
        )

    return result


# =========================================================
# ALL RECOMMENDATIONS FOR A USER
# =========================================================

@app.get(
    "/recommendations/{user_id}",
    response_model=RecommendationResponse,
)
def get_recommendations(
    user_id: str,
    account=Depends(optional_account),
):

    ensure_profile_access(user_id, account)

    recommendations = (
        recommendation_service
        .get_recommendations(user_id)
    )

    if recommendations is None:

        raise HTTPException(
            status_code=404,
            detail=f"User '{user_id}' not found.",
        )

    results = []

    for _, row in recommendations.iterrows():

        results.append(
            row_to_recommendation(row)
        )

    return {
        "user_id": user_id,
        "recommendations": results,
    }


@app.post(
    "/recommendations/{user_id}/scenario",
    response_model=RecommendationResponse,
)
def rank_recommendation_scenario(
    user_id: str,
    request: ScenarioRankingRequest,
    account=Depends(optional_account),
):
    ensure_profile_access(user_id, account)
    if recommendation_service.get_recommendations(user_id) is None:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found.")
    weights = request.scenario_weights.model_dump()
    if sum(weights.values()) <= 0:
        raise HTTPException(status_code=422, detail="Set at least one scenario weight above zero.")
    try:
        if float(request.profile.budget) <= 0:
            raise ValueError
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail="Enter a valid positive travel budget before ranking this scenario.") from error
    if any(value < -3 or value > 3 for value in request.preference_feedback.values()):
        raise HTTPException(status_code=422, detail="Preference feedback values must be between -3 and 3.")
    recommendations = recommendation_service._rank_for_profile(
        user_id,
        request.profile.model_dump(),
        scenario_weights=weights,
        preference_feedback=request.preference_feedback,
    )
    return {"user_id": user_id, "recommendations": recommendations}


# =========================================================
# SINGLE RECOMMENDATION
# =========================================================

@app.get(
    "/recommendations/{user_id}/{rank}",
    response_model=Recommendation,
)
def get_single_recommendation(
    user_id: str,
    rank: int,
    account=Depends(optional_account),
):

    ensure_profile_access(user_id, account)

    if rank < 1 or rank > 10:

        raise HTTPException(
            status_code=400,
            detail="Rank must be between 1 and 10.",
        )

    recommendation = (
        recommendation_service
        .get_recommendation(
            user_id,
            rank,
        )
    )

    if recommendation is None:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Recommendation rank {rank} "
                f"not found for user '{user_id}'."
            ),
        )

    return row_to_recommendation(
        recommendation
    )
