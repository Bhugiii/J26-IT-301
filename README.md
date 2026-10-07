# TravelMind – AI-Powered Tourism Recommendation Engine

## Component Overview

The **Recommendation Engine** is a core component of the **TravelMind AI-Based Smart Tourism Recommendation, Crowd Prediction and Analytics System**.

The purpose of this component is to generate **personalized, explainable and demand-aware tourism recommendations** based on user preferences, destination characteristics, predicted crowd levels, weather suitability, sustainability, sentiment and budget compatibility.

> **Component focus:** *“I don't just say go here — I say why.”*

The engine combines traditional recommendation techniques with semantic similarity and tourism-demand intelligence to produce ranked destination recommendations for individual users.

---

## Objectives

The Recommendation Engine aims to:

* Generate personalized tourism destination recommendations.
* Understand user preferences and destination descriptions semantically.
* Incorporate predicted crowd levels into recommendation ranking.
* Consider budget and travel preferences.
* Consider weather suitability.
* Consider sustainability preferences.
* Incorporate destination sentiment information.
* Provide an explanation for every recommendation.
* Evaluate recommendation quality using ranking metrics.
* Provide recommendations through a REST API for frontend integration.

---

## System Architecture

```text
                    ┌─────────────────────┐
                    │    User Profile     │
                    │                     │
                    │ Preferences         │
                    │ Budget              │
                    │ Travel Style        │
                    │ Interests           │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Feature Engineering │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
      │ Semantic     │ │ Destination  │ │ Crowd/Demand │
      │ Similarity   │ │ Features     │ │ Prediction   │
      └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                 ┌────────────────────────┐
                 │ Hybrid Recommendation  │
                 │ & Demand-Aware Ranking │
                 └────────────┬───────────┘
                              │
                              ▼
                 ┌────────────────────────┐
                 │ Explainable Ranking    │
                 │ & Recommendation       │
                 └────────────┬───────────┘
                              │
                              ▼
                 ┌────────────────────────┐
                 │ Top-K Destinations      │
                 │ + Explanations          │
                 └────────────┬───────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ FastAPI REST API │
                    └────────┬─────────┘
                             │
                             ▼
                       TravelMind UI
```

---

## Main Features

### 1. Personalized Recommendation

The engine uses user-profile information to determine how suitable each destination is for a particular user.

Example user preferences include:

* Destination type
* Activities
* Travel style
* Budget
* Weather preference
* Sustainability preference
* Preferred crowd level
* Interests

The system calculates a preference score for candidate destinations and ranks them accordingly.

---

### 2. Semantic Recommendation

TravelMind uses **Sentence-BERT (SBERT)** embeddings to represent users and destinations in a semantic vector space.

Destination descriptions and user preference text are transformed into embeddings.

The system then calculates semantic similarity between the user profile and destinations.

```text
User Preferences
       │
       ▼
   SBERT Model
       │
       ▼
User Embedding
       │
       │ Cosine Similarity
       ▼
Destination Embeddings
       │
       ▼
Semantic Similarity Score
```

This allows the system to identify destinations with similar meaning rather than relying only on exact keyword matches.

---

### 3. Demand and Crowd Prediction

The recommendation system incorporates predicted tourism crowd levels.

A machine-learning model predicts the expected crowd condition for a destination.

The prediction is categorized into levels such as:

* Low
* Medium
* High

The predicted crowd level is then incorporated into the recommendation ranking.

This allows TravelMind to recommend destinations that better match a user's preferred tourism-demand conditions.

---

### 4. Demand-Aware Recommendation

The final recommendation score combines multiple factors.

The current recommendation pipeline considers:

* Preference score
* Budget fit
* Predicted crowd fit
* Weather fit
* Sustainability fit
* Sentiment fit
* Demand suitability

A demand-aware score is then generated to rank destinations.

Conceptually:

```text
Demand-Aware Score
        =
Personal Preference
        +
Budget Compatibility
        +
Crowd Suitability
        +
Weather Suitability
        +
Sustainability
        +
Sentiment
        +
Demand Suitability
```

The actual weighting is controlled by the implemented recommendation model.

---

## Explainable Recommendations

A major feature of the component is **explainability**.

Instead of returning only:

```text
1. Ella
2. Mirissa
3. Nuwara Eliya
```

the system provides reasons behind the recommendation.

Example:

```text
Ella is recommended because it matches your
nature and hiking preferences, fits your budget,
has suitable weather conditions, and has a
lower predicted crowd level.
```

Each recommendation contains an explanation generated from the underlying recommendation features.

This improves transparency and allows users to understand **why a destination was recommended**.

---

## Recommendation Pipeline

The component follows the following workflow:

### Step 1 – Load Data

The system loads:

* Destination information
* User profiles
* Evaluation cases
* Destination features
* Model outputs

### Step 2 – Preprocess Data

Raw tourism and user data are cleaned and transformed into machine-learning-ready features.

### Step 3 – Feature Engineering

Relevant features are generated for:

* Users
* Destinations
* Preferences
* Crowd prediction
* Recommendation scoring

### Step 4 – Semantic Representation

SBERT generates embeddings for destination and user preference text.

### Step 5 – Candidate Scoring

Each destination receives multiple component scores.

### Step 6 – Demand Integration

Predicted crowd/demand information is incorporated into the recommendation score.

### Step 7 – Ranking

Destinations are ranked according to the final recommendation score.

### Step 8 – Explanation Generation

The system identifies the main factors contributing to the recommendation.

### Step 9 – Top-K Recommendations

The highest-ranked destinations are returned to the user.

---

## Project Structure

```text
Smart-Tourism-Recommendation/
│
├── api/
│   ├── main.py
│   ├── models.py
│   ├── requirements.txt
│   │
│   └── services/
│       ├── auth_service.py
│       ├── recommendation_service.py
│       └── explainability_chat_service.py
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── features/
│
├── models/
│   ├── sbert_model.joblib
│   └── crowd_prediction_random_forest.joblib
│
├── notebooks/
│   ├── 01_data_preprocessing.ipynb
│   ├── 02_feature_engineering.ipynb
│   ├── 03_recommendation_models.ipynb
│   ├── 04_sbert_semantic_recommendation.ipynb
│   ├── 05_demand_crowd_prediction.ipynb
│   ├── 06_demand_aware_recommendation.ipynb
│   ├── 07_final_model_evaluation.ipynb
│   ├── 08_explainable_recommendation.ipynb
│   └── 09_final_project_validation.ipynb
│
├── results/
│
├── frontend/
│
├── compose.yaml
├── DEPLOYMENT.md
└── README.md
```

---

## Notebooks

The recommendation research and implementation are divided into several notebooks.

| Notebook                                 | Purpose                                        |
| ---------------------------------------- | ---------------------------------------------- |
| `01_data_preprocessing.ipynb`            | Cleans and prepares raw datasets               |
| `02_feature_engineering.ipynb`           | Creates recommendation features                |
| `03_recommendation_models.ipynb`         | Develops recommendation approaches             |
| `04_sbert_semantic_recommendation.ipynb` | Implements semantic recommendation using SBERT |
| `05_demand_crowd_prediction.ipynb`       | Predicts destination crowd levels              |
| `06_demand_aware_recommendation.ipynb`   | Integrates demand predictions into ranking     |
| `07_final_model_evaluation.ipynb`        | Evaluates recommendation performance           |
| `08_explainable_recommendation.ipynb`    | Generates recommendation explanations          |
| `09_final_project_validation.ipynb`      | Performs final system validation               |

---

## Machine Learning Models

### SBERT Semantic Model

The semantic recommendation component uses a Sentence-BERT model to generate dense vector representations.

Purpose:

```text
User preference text
        ↓
SBERT embedding
        ↓
Semantic similarity
        ↓
Destination ranking
```

The model is stored under:

```text
models/sbert_model.joblib
```

---

### Crowd Prediction Model

The system also uses a machine-learning model to predict destination crowd conditions.

Model:

```text
Random Forest
```

Stored under:

```text
models/crowd_prediction_random_forest.joblib
```

The prediction is subsequently used by the demand-aware recommendation component.

---

## Evaluation

The recommendation engine is evaluated using ranking-based metrics.

### NDCG

**Normalized Discounted Cumulative Gain (NDCG)** evaluates the quality of the ranked recommendations while giving higher importance to relevant items appearing near the top.

### Precision@K

Precision@K measures how many of the top-K recommendations are relevant to the user.

For example:

```text
Precision@10
```

measures the proportion of relevant recommendations among the top 10 results.

---

## Model Comparison

The recommendation pipeline supports comparison between different recommendation approaches.

Examples include:

* Baseline recommendation
* Content-based recommendation
* Semantic recommendation
* Hybrid recommendation
* Demand-aware recommendation

This allows the research to evaluate whether adding semantic understanding and tourism-demand information improves recommendation quality.

---

## API Integration

The recommendation engine is exposed through the TravelMind FastAPI backend.

Main API implementation:

```text
api/main.py
```

Recommendation service:

```text
api/services/recommendation_service.py
```

The API provides the recommendation engine with a bridge between the machine-learning layer and the TravelMind frontend.

Conceptual request:

```text
Frontend
   ↓
FastAPI
   ↓
Recommendation Service
   ↓
User Profile
   ↓
Recommendation Engine
   ↓
Top-K Recommendations
   ↓
Explanations
   ↓
Frontend
```

---

## Example Recommendation Output

A recommendation can contain information such as:

```json
{
  "destination": "Ella",
  "rank": 1,
  "preference_score": 0.91,
  "budget_fit": 0.88,
  "predicted_crowd_fit": 0.92,
  "weather_fit": 0.86,
  "sustainability_fit": 0.84,
  "sentiment_fit": 0.90,
  "demand_suitability": 0.89,
  "demand_aware_score": 0.90,
  "explanation": "Recommended because it strongly matches your nature and hiking preferences while offering suitable crowd and weather conditions."
}
```

---

## Technologies

### Machine Learning

* Python
* Scikit-learn
* Sentence-BERT
* NumPy
* Pandas
* Joblib

### Backend

* FastAPI
* Python
* REST API
* Pydantic

### Frontend

* React
* TypeScript
* Vite

### Development

* Jupyter Notebook
* Git
* GitHub
* Docker

---

## Research Contribution

The Recommendation Engine contributes to TravelMind by combining:

1. **Personalized user preferences**
2. **Semantic understanding**
3. **Tourism demand prediction**
4. **Crowd-aware ranking**
5. **Multi-factor recommendation**
6. **Explainable AI**

The key research contribution is the integration of **demand-aware tourism intelligence with personalized recommendation**, allowing the system to recommend destinations not only because they match the user's interests, but also because they are suitable considering predicted tourism conditions.

## Expected Outcome

The final component is designed to produce:

```text
Personalized
     +
Semantic
     +
Demand-Aware
     +
Explainable
     ↓
Tourism Recommendations
```

The system therefore moves beyond a basic destination recommender toward an **AI-powered, context-aware and explainable tourism recommendation system**.

---

## Component Owner

**Component:** Recommendation Engine
**Project:** TravelMind – AI-Based Smart Tourism Recommendation, Crowd Prediction and Analytics System
**Student ID:** IT23429932
**Research Area:** AI-Based Tourism Recommendation and Demand-Aware Ranking
