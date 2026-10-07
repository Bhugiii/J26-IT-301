from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field


class Recommendation(BaseModel):

    rank: int

    destination_id: str
    name: str
    category: str
    district: str
    distance_km: Optional[float] = None
    duration_hours: Optional[float] = None

    estimated_cost_lkr: Optional[float] = None

    sustainability_score: Optional[float] = None
    seasonality_score: Optional[float] = None

    weather_temp_c: Optional[float] = None
    weather_rain_risk: Optional[float] = None
    weather_suitability: Optional[float] = None

    predicted_crowd_score: Optional[float] = None
    predicted_crowd_level: Optional[str] = None

    preference_score: Optional[float] = None
    budget_fit: Optional[float] = None
    predicted_crowd_fit: Optional[float] = None

    weather_fit: Optional[float] = None
    sustainability_fit: Optional[float] = None
    distance_fit: Optional[float] = None
    pace_fit: Optional[float] = None
    sentiment_fit: Optional[float] = None

    demand_suitability: Optional[float] = None
    demand_aware_score: Optional[float] = None
    scenario_score: Optional[float] = None

    explanation: Optional[str] = None


class RecommendationResponse(BaseModel):

    user_id: str

    recommendations: list[Recommendation]


class ItineraryStop(BaseModel):
    destination_id: str
    name: str
    district: str
    rank: int
    estimated_cost_lkr: Optional[float] = None
    visit_duration_hours: float
    straight_line_distance_km: Optional[float] = None
    recommendation_reason: str


class ItineraryDay(BaseModel):
    day: int
    area: str
    estimated_visit_hours: float
    stops: list[ItineraryStop]


class ItineraryResponse(BaseModel):
    user_id: str
    traveler_name: str
    days: list[ItineraryDay]
    planning_note: str


class HealthResponse(BaseModel):

    status: str
    users: int
    recommendations: int


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1200)


class TravelerProfile(BaseModel):
    name: str = Field(default="", max_length=80)
    sustainabilityImportance: float = Field(default=0.5, ge=0, le=1)
    budget: str = Field(default="", max_length=40)
    tripDuration: str = Field(default="", max_length=20)
    travelStyle: str = Field(default="", max_length=120)
    startingLocation: str = Field(default="", max_length=120)
    interests: str = Field(default="", max_length=400)
    maxDistanceKm: Literal["Any distance", "100", "250", "500", "800"] = "Any distance"
    travelPace: Literal["Relaxed", "Balanced", "Active"] = "Balanced"
    preferredCrowd: str = Field(default="", max_length=40)
    preferredWeather: str = Field(default="", max_length=40)


class ItineraryRequest(BaseModel):
    profile: TravelerProfile


class ScenarioWeights(BaseModel):
    preference: int = Field(default=60, ge=0, le=100)
    crowd: int = Field(default=25, ge=0, le=100)
    sustainability: int = Field(default=15, ge=0, le=100)


class ScenarioRankingRequest(BaseModel):
    profile: TravelerProfile
    scenario_weights: ScenarioWeights
    preference_feedback: Dict[str, int] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1200)
    profile: TravelerProfile = Field(default_factory=TravelerProfile)
    history: list[ChatTurn] = Field(default_factory=list, max_length=8)


class ChatSource(BaseModel):
    id: str
    title: str
    details: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    latency_ms: int
    model: str


class AuthRegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    claim_profile_id: Optional[str] = Field(default=None, max_length=40)


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)
