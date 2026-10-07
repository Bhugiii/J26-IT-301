# Docker deployment

Docker Compose runs the React/Vite frontend and FastAPI backend as separate containers. Nginx serves the frontend and proxies `/api` requests to the API. The API database and signing secret live in the persistent `tourism_state` volume. The API port is only available inside the Compose network; the browser uses the frontend port.

## Start the application

1. Install Docker Desktop (Windows/macOS) or Docker Engine with the Compose plugin (Linux).
2. From the repository root, copy `docker.env.example` to `.env` and replace `TRAVELMIND_AUTH_SECRET` with a random value of at least 32 bytes. For example, generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
3. Run `docker compose up --build -d`.
4. Open `http://localhost:8080` (or the port set by `APP_PORT`). Check `http://localhost:8080/health` for API health through the frontend proxy.

View logs with `docker compose logs -f api frontend`. Stop the stack with `docker compose down`. The named state volume is retained when the stack is stopped; `docker compose down -v` deletes that volume and its account/profile data.

## Explainability assistant

The main recommendation, itinerary, profile, and research features do not require a language model. With the example settings, chat expects Ollama at `http://ollama:11434`. Start the optional service with `docker compose --profile local-ai up --build -d`, then download the configured model once with `docker compose --profile local-ai exec ollama ollama pull qwen3:4b`. Model weights use the separate `ollama_models` volume. Ollama can require several gigabytes of disk and memory. To use an OpenAI provider instead, set `AI_PROVIDER=openai` and `OPENAI_API_KEY` in `.env`, then recreate the API container; API keys stay server-side.

## Operating notes

- Keep `.env` private. Change the signing secret before public use and keep it stable across restarts so existing account sessions remain verifiable.
- The API is intentionally not published on a host port. Put the frontend behind an HTTPS reverse proxy for public access; set a firewall rule for the chosen `APP_PORT`.
- SQLite persists in a Docker named volume and is suitable for this single API container. Back up account/profile data before upgrades. Multiple API replicas require a shared production database and coordinated session-secret management.
- This package does not include a time-stamped tourism demand series, holiday/Poya calendar, or live weather provider. Do not describe the static crowd/weather attributes as date-specific forecasts.
- The included destination records identify several attributes as synthetic research-seed estimates. Validate their source provenance and replace or clearly label estimates before presenting the service as operational travel advice.
- Recommendation scenario weights are evaluated by the API against the full destination catalog. Explicit category feedback and slider settings are saved in the current browser's local storage; they are not yet synchronized across devices or accounts.

## Build checks

Run the frontend TypeScript check with `npm --prefix frontend exec tsc -- --noEmit`, and check Python syntax with `python -m compileall -q api`. A Docker build also runs `npm ci` and the frontend production build inside its build stage.
