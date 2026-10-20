# TravelMind · Component 03 — NLP-Based Destination Trust Engine

Compares tourism marketing text ("the promise") with real visitor reviews ("the experience") for 57 Sri Lankan
destinations, using multilingual Sentence-BERT similarity and a destination-specific aspect taxonomy
(Crowding, Facilities, Commercialization, Accessibility). Grounded in Expectation-Confirmation Theory.

```
TravelMind_Component03/
├── backend/            FastAPI API (main.py) + data CSVs + tests
│   └── pipeline/       Data/ML pipeline scripts (re-run only to regenerate data)
├── frontend/           React + TypeScript + Vite + Tailwind UI
│   └── dist/           Pre-built UI (served by the backend — no Node needed to demo)
└── API_CONTRACT.md     The JSON contract between backend and frontend
```

## Requirements
Python 3.10+ (tested on 3.13). Node.js 18+ only if you want to change the UI.

## Option A — Demo mode (one terminal, Python only)  ← use this for the viva

The UI is already built into `frontend/dist`, and the backend serves it.

Windows (PowerShell / VS Code terminal):
```powershell
cd TravelMind_Component03\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
uvicorn main:app --reload
```
macOS/Linux: same, but `source .venv/bin/activate`.

Open **http://127.0.0.1:8000** — the full app. API docs: http://127.0.0.1:8000/docs

## Option B — Development mode (two terminals, needs Node.js 18+)

Terminal 1 (backend):
```powershell
cd TravelMind_Component03\backend
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload
```
Terminal 2 (frontend with hot reload):
```powershell
cd TravelMind_Component03\frontend
npm install
npm run dev
```
Open **http://localhost:5173** (Vite proxies `/api` to port 8000).
After UI changes run `npm run build` so demo mode (Option A) picks them up.

## Run the tests
```powershell
cd backend
python -m pytest -q        # 145 tests; use python -m so the venv's packages are used
```

## Notes
- `/api/destination/{name}` accepts partial names; when several match, the most-reviewed one wins (e.g. "Sigiriya" gives *Sigiriya Museum*). The UI always sends full names.
- `frontend/dist` is committed on purpose so Demo mode works without Node. If you change the UI, rebuild it.

## Pages
Sections and cards fade up as you scroll (disabled automatically when the system asks for reduced motion).

| Page | What it shows |
|---|---|
| Overview | Headline numbers, top reality matches, what visitors talk about, band distribution |
| Destinations | All 57 ranked; filter by type/province, search, sort |
| Destination insight | Gauge (Reality Match), simple topic bars vs. a typical destination, Promise vs Review, Pro-tips, aspect cards with real review snippets, similarity distribution, explainability report |
| Compare | Two destinations side by side (gauges, topic bars, metric table) |

## Re-running the data pipeline (optional)
Only needed to regenerate the data, e.g. to add the 3 destinations whose names previously failed to join
(Lipton's Seat, Lover's Leap Falls, St Clair's Falls):
```powershell
cd backend\pipeline
pip install sentence-transformers torch datasets
python run_pipeline.py            # process → tag → SBERT scoring → aggregate (several minutes)
```
`python run_pipeline.py --skip-ml` re-runs everything except the SBERT step.

## What changed from the original hand-over (and why)
| Area | Problem found | Fix |
|---|---|---|
| `main.py` search | `str.contains()` treated names as regex, so "Gangaramaya (Vihara) Buddhist Temple" and "Twin Baths (Kuttam Pokuna)" returned 404 | Exact (case/apostrophe-insensitive) match first, then literal substring match |
| `main.py` robustness | CSV paths depended on the working folder; work recomputed per request | Paths relative to `main.py`; everything precomputed at startup; JSON-safe values |
| Aspect tagging | Substring matching: "line" matched "online", "bus" matched "business", "far" matched "safari", "rush" matched "crushed"; bare "people" ("friendly people") counted as crowding | Word-boundary regexes plus phrase rules. See `pipeline/RETAG_REPORT.md` for before/after counts |
| Text cleaning | Removed hyphens, so the "tuk-tuk" keyword could never match | Hyphens kept; "tuktuk"/"tuk tuk" handled |
| Promise join | 3 of 60 promises never joined because of apostrophe differences (’ vs ' vs cp1252) | Normalised name join in `process_data.py` |
| Tips logic | Triggered by raw mention counts, which favours destinations with more reviews | Triggered by share of reviews vs. the average destination (≥ 1.25×) |
| Radar chart | Raw counts not comparable across destinations | % of reviews, overlaid with the dataset average |
| `run_ai_model.py` | Re-encoded the same promise ~14,000 times | Each promise encoded once |
| API | Only 2 endpoints | Added `/api/overview`, `/api/compare`, `/api/health` and richer destination detail. v1 fields unchanged |

The SBERT similarity scores (`Base_Reality_Score`) are **unchanged**. Only the aspect tags (and numbers derived from
them) changed. If teammates quoted the old aspect counts anywhere, update them from `destination_summary.csv`.

## Limitations (good to state in the viva)
- The score measures **semantic similarity**, not factual accuracy: it shows how closely reviews echo the promise.
- Scores fall in a narrow band (≈ 39–64%), so read them relative to other destinations.
- Aspect figures count **mentions**, not complaints. Satisfaction among those reviewers is shown separately.
- The model is multilingual, but the dataset is English-only.
- "Closest-matching review" is, by construction, the review most similar to the promise. It is a selected example, not a random sample.

## Optional destination photos
The app draws an illustrated scene per destination type. To use real photos, put JPGs in
`frontend/public/images/` named by slug (e.g. `galle-fort.jpg`), then `npm run build`.
See `frontend/public/images/README.txt`. Only use photos you have the right to use.

## Design system
Brand tokens live in `frontend/src/index.css` (`:root`, `--tm-*`) and are mirrored in `tailwind.config.js`:
Primary `#123B5D`, Secondary `#0D9488` (hover `#0F766E`), Success `#16A34A`, Accent `#F5B942`,
Background `#F5F8FA`, Card `#FFFFFF`, Text `#172B3A`, Muted `#64748B`, Border `#D9E2EA`, radius 12px.
`.primary-button` / `.btn-primary` and `.dashboard-card` / `.card` follow the brand CSS.
Logo assets: `frontend/public/brand/` (transparent PNGs cut from the TravelMind logo). Banner photos: `frontend/public/photos/`.
Inter for the interface, Manrope for headings; fonts are bundled so the app works offline.
Per the "helpful local friend" philosophy, no red or warning colours are used.
