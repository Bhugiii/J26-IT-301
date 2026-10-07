# API and local explainability chat

The explainability assistant uses Ollama locally by default. This avoids paid API calls and does not require an OpenAI key. It still needs Ollama installed, the model downloaded, and enough local memory/storage to run it.

## Start local AI chat on Windows

1. Install Ollama from [ollama.com/download](https://ollama.com/download).
2. Open PowerShell and download the Qwen 3 4B model:

   ```powershell
   ollama pull qwen3:4b
   ```

   The model download is about 2.5 GB. Ollama's local chat API supports schema-constrained JSON, which the assistant uses to validate its cited evidence.
3. Keep Ollama running, then open another PowerShell at the project root and start FastAPI:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000
   ```

4. Start the frontend in another terminal:

   ```powershell
   cd frontend
   npm run dev
   ```

`AI_PROVIDER` defaults to `ollama`; `OLLAMA_MODEL` defaults to `qwen3:4b`; `OLLAMA_BASE_URL` defaults to `http://127.0.0.1:11434`; and local model requests have a 180-second timeout by default (`OLLAMA_TIMEOUT_SECONDS`). The model stays loaded for 10 minutes after a chat request. Optional overrides belong in `api/.env`. Do not add a paid API key to frontend configuration.

To explicitly use OpenAI instead, set `AI_PROVIDER=openai` and configure `OPENAI_API_KEY` in the API server environment. OpenAI API use can incur charges.

The browser calls `POST /assistant/chat/{user_id}`. The API sends the current question, up to six recent chat turns, the selected traveler profile, and that user's recommendation records to the selected provider. It validates the structured answer and its evidence IDs against the records supplied in that request before returning cited sources.

Traveler profiles can be created or updated through `POST /profiles` and `PUT /profiles/{user_id}`. Profile preferences and their personalized top-10 recommendations are stored in `data/traveler_profiles.sqlite3`; `GET /profiles/{user_id}` reloads the profile and `GET /recommendations/{user_id}` returns its current ranking. These are guest profiles for the research prototype and do not use account authentication.

The itinerary planner calls `POST /itinerary/{user_id}` with the current traveler profile and distributes ranked destinations over the requested trip days and pace. It uses estimated visit lengths; the response explicitly identifies missing route, opening-hour, activity, and total-cost data.

Accounts are available through `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, and `GET /account/profiles`. Passwords are stored as salted PBKDF2 hashes, and account access uses signed, eight-hour bearer tokens stored in the current browser session. Guest profiles can be linked during registration. This research prototype does not provide email verification or password recovery; use HTTPS when hosting it beyond a trusted local development environment.

The current evidence does not include verified opening hours, activities, route distances, or itinerary schedules. The assistant is instructed to say when those facts are unavailable. Source IDs establish traceability, but semantic entailment still requires a human or rule-based fidelity audit as described in the proposal.
