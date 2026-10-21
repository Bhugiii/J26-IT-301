# TravelMind research and completion guide

This document describes what is implemented, what the saved results show, and what evidence is still needed before presenting TravelMind as a validated tourism recommender. It is intended as a starting point for the dissertation and project demonstration. Replace assumptions with cited sources and supervisor-approved methods before submission.

## Working title

**An Explainable Multi-Criteria Tourism Recommendation and Itinerary Planning Prototype for Sri Lanka**

An optional research extension is traveler-adjustable trade-offs between preference fit, estimated crowd suitability, and sustainability.

## Problem and aim

Travelers choose among destinations with different interests, budgets, weather preferences, travel distances, sustainability attributes, and crowd conditions. A ranking that optimizes a single signal can hide trade-offs. TravelMind explores a transparent, interactive approach that ranks Sri Lankan destinations against a traveler profile, surfaces scoring factors, and lets the traveler adjust some ranking priorities and itinerary choices.

**Aim:** design and evaluate a web prototype for personalized destination ranking and itinerary adaptation using a multi-criteria scoring approach, while clearly communicating uncertainty and data provenance.

## Research questions to validate

1. How do general, content-based, context-aware, hybrid, and demand-aware ranking approaches compare on Precision@K, Recall@K, and NDCG@K using a clearly defined held-out relevance set?
2. How does adding crowd suitability and sustainability signals change ranking quality and the resulting recommendation trade-offs?
3. Do explanations and traveler-controlled ranking weights help users understand and adapt a proposed itinerary?
4. Does showing a Pareto shortlist help travelers understand trade-offs better than showing only a single weighted ranking?

Questions 2 and 3 require better data or a human participant study; current results do not answer them conclusively.

## System implementation

- **Frontend:** React, TypeScript, Vite, and Recharts. It provides account/profile flows, recommendation cards and map view, filters and comparison, saved places, crowd and weather scenario views, itinerary editing, export/share, assistant, and research analytics.
- **API:** Python and FastAPI. It provides profile and account endpoints, recommendation retrieval, scenario reranking, itinerary creation, evaluation data, and an evidence-constrained assistant endpoint.
- **Storage:** CSV research artifacts and SQLite traveler profiles/accounts. Category feedback and recommendation scenario sliders are stored in browser local storage.
- **Authentication:** salted PBKDF2 password hashes and signed bearer sessions. This is suitable for a prototype deployment; public production use needs operational security review, HTTPS, backup, monitoring, and account recovery processes.
- **Recommender:** for newly created profiles, the live API blends offline SBERT destination embeddings (through a nearest-profile prototype transfer) with weighted interest/style match, estimated budget fit, crowd preference fit, stored weather attributes, sustainability, seasonality, sentiment, straight-line distance, and travel pace. The semantic signal currently contributes 20% of the final score when embedding artifacts are available; the remaining multi-criteria score is scaled to 80%. Scenario ranking reweights preference, crowd, and sustainability signals and returns an explanation based on the strongest fit factors. Demo-user benchmark rows remain the saved offline recommendations.
- **Pareto shortlist:** recommendation results mark options that are non-dominated across preference fit, crowd fit, and sustainability fit among the returned top-10 list. This gives travelers a view of trade-offs that a single weighted score can conceal. It is an explainable multi-objective decision aid; effectiveness and research novelty remain to be established empirically and through literature review.
- **Research models:** notebooks cover content/context/hybrid ranking, SBERT semantic experiments, a Random Forest crowd-score experiment, demand-aware reranking, evaluation, explanations, and project validation. The current live profile scorer is a hand-weighted multi-criteria score; do not describe every live recommendation as an SBERT inference.
- **Itinerary:** distributes ranked stops over the requested trip length, observes relaxed/balanced/active hour and stop-count limits, groups the same district on a day where possible, labels a theme from stop categories, and totals the estimated destination costs against the daily budget. Alternative destinations can be searched and added by the user and update the estimate. It does not verify routes, opening hours, transport time, activities, or complete trip costs.

## Data and provenance

The current project data includes 100 destination rows, 50 traveler profiles, and 500 evaluation cases. The records explicitly identify profiles as synthetic and destination attributes as estimated/research-seed values. Evaluation cases are derived from those synthetic profiles and seed destination records; they are not observed user interactions or independently collected traveler judgments.

Destination names and locations may refer to real places, but attributes such as costs, crowd score, sustainability, seasonality, sentiment, weather and relevance should be treated as estimates unless each field has a verifiable source, collection date, and methodology. Cite the provenance of every attribute in submitted research and replace estimates where possible.

The application has **no time-stamped visitor-count series, live crowd feed, forecast horizon, holiday/Poya calendar, school-break schedule, or live weather provider**. Crowd and weather screens are static scenario/sensitivity analyses over stored fields. Do not present them as today's forecast or a forecast for the user's travel date.

## Current saved results

### Ranking comparison at K=5

| Model | Precision@5 | Recall@5 | NDCG@5 |
|---|---:|---:|---:|
| General baseline (B1) | 0.0111 | 0.0278 | 0.5593 |
| Content-based (B2) | 0.0722 | 0.1898 | 0.6274 |
| Context-aware (B3) | 0.0833 | 0.2222 | 0.6127 |
| Hybrid (B4) | 0.0889 | 0.2546 | 0.5530 |
| Demand-aware (saved comparison) | 0.0111 | 0.0278 | 0.6204 |

The saved tables show a metric trade-off. B4 has the highest Precision@5 and Recall@5 among these rows; demand-aware has higher NDCG@5 than B4, while having much lower Precision@5 and Recall@5. Therefore do not claim that demand-aware ranking outperforms the baselines overall. Check the evaluation notebook's candidate matching and metric aggregation before interpreting this result; investigate why the saved demand-aware metric row has such low precision/recall alongside higher NDCG.

### NDCG at different list lengths

The saved B5 semantic versus demand-aware comparison reports these demand-aware changes: K=1: 0.0000; K=3: -0.0039; K=5: +0.0011; K=10: -0.0040. Changes are small and mixed. No confidence intervals or significance tests are available.

The interactive profile-to-SBERT prototype transfer and the current multi-criteria scorer are newer live-path changes. The saved benchmark CSVs do **not** evaluate this exact implementation. Run a clean held-out evaluation for this model before reporting any quality gain.

### Crowd-score model

Notebook 05 trains a Random Forest regressor using five attributes (estimated cost, sustainability, seasonality, temperature, rain risk) to predict the stored `crowd_score`. It uses a random 80/20 split of only 100 destination rows. Saved test metrics are MAE 4.438, RMSE 5.611, and R² -0.349. The negative R² means the model did worse than a test-set-mean predictor on this split. More fundamentally, the target is an estimated static score rather than measured, date-specific visitor volume. This is not evidence of a useful operational crowd forecast.

## Research interpretation

The defensible current contribution is a **working prototype and an offline comparison of ranking approaches on synthetic/estimated seed data**. The potentially novel research direction is the combination of:

- interpretable multi-criteria destination scoring;
- traveler-adjustable preference/crowd/sustainability trade-offs;
- lower-score alternative exploration; and
- user-directed itinerary adaptation.

The Pareto shortlist adds a testable question: compared with one weighted ranking, does showing non-dominated trade-offs improve choice quality or understanding? Evaluate frontier size and coverage alongside user choices; the current benchmark does not yet report those measures.

Call this a proposed contribution until a literature review establishes the gap and a controlled evaluation provides evidence. UI features alone do not establish novelty or effectiveness.

## Work required for a defensible final study

### 1. Audit the benchmark before reporting it

- Trace how each metric row was generated and ensure the same users, candidate catalog, relevance labels, cutoff K, and missing-label policy are used for every model.
- Verify that Precision@K and Recall@K use a consistent denominator and that each user's relevant ground truth is computed only from a declared held-out set.
- Check that train/test separation prevents information leakage. Report split unit, random seed, user/destination overlap, and the number of judged candidates per user.
- Recompute metrics from raw predictions and labels in one reproducible evaluation script; export results from that script rather than manually maintained CSVs.
- Report per-user results and bootstrap confidence intervals. If paired statistical tests are used, predeclare the test and correct for multiple model comparisons.
- Resolve the discrepancy between the B4 versus demand-aware table and the NDCG comparison; document which evaluation population and model version each file represents.

### 2. Establish valid crowd/weather evidence

- Obtain permitted, sourced, dated crowd observations across multiple destinations and dates (for example, official counts or a documented survey/proxy). Record measurement method and missingness.
- Define the prediction target, prediction horizon, and intended decision. Use a chronological holdout by date; avoid random row splits when records share destination/time structure.
- Compare against simple baselines (historical seasonal mean and recent-value baseline). Report MAE/RMSE/R² plus a relevant classification metric if showing low/medium/high categories. Include uncertainty and coverage.
- Source weather from a timestamped provider or archive, preserve retrieval time and target travel date, and evaluate weather suitability separately from crowd prediction.
- Until then, label these screens “dataset scenario” or “estimated destination score” rather than forecast.

### 3. Run a traveler study for explanations and itinerary adaptation

- Write a protocol and obtain institutional ethics approval/consent before recruiting participants or collecting identifiable data.
- Compare at least a fixed ranked itinerary with the interactive alternative-search workflow. Randomize task/order where practical and use the same destination information in both conditions.
- Predefine outcomes such as task completion, selected-destination preference fit, number and direction of edits, perceived usefulness, trust/calibration, and explanation comprehension. Use validated scales where appropriate and cite them.
- Determine sample size with a power analysis; report recruitment, exclusions, demographics only as necessary, effect sizes, uncertainty intervals, and limitations.
- Do not use synthetic profile ratings as substitutes for participants.

### 4. Product completion before real-world launch

- Verify all destination facts and clearly mark estimated values in the interface.
- Add date-aware, sourced weather/crowd services only after provider terms, failure handling, freshness indicators, and evaluation are in place.
- Add real route distance/time, verified opening hours and an itinerary budget only from reliable data sources; otherwise retain the current limitation text.
- For public deployment, use HTTPS, a stable private signing secret, database backups/migrations, logging/monitoring, rate limiting, privacy notice, and security review. The Docker package is a deployment package, not by itself a production operation plan.
- Maintain a data dictionary, source register, model version, experiment configuration, and reproducible artifact-generation instructions.

## Suggested dissertation structure

1. Introduction and Sri Lanka tourism decision problem
2. Literature review: recommender systems, context-aware/multi-criteria ranking, explainability, crowd-aware tourism and itinerary planning
3. Requirements, data provenance, ethics and system design
4. Methods: features, ranking baselines, proposed score, crowd experiment, metrics and split protocol
5. Implementation: architecture and user workflows
6. Offline results, honest interpretation, and error analysis
7. User study (only after approval and completion)
8. Limitations, deployment considerations, conclusion and future work

## Short project explanation

> TravelMind is a Sri Lanka-focused tourism recommendation prototype. It uses a traveler profile and destination attributes to rank places across interests, budget, estimated crowd suitability, stored weather signals, sustainability and practical fit. The interface exposes recommendation factors, lets users adjust selected trade-offs, compare destinations, and adapt a draft itinerary. The current benchmark uses synthetic profiles and estimated destination attributes, so its results are exploratory; real crowd forecasting and traveler benefit remain to be validated with sourced temporal data and a participant study.
