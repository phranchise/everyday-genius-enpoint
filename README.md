# Everyday Genius Coach

A reliable reasoning endpoint that coaches memory & cognition techniques from
Nelson Dellis's *Everyday Genius*. **Week 1 base** — Week 2 extends this same
service with RAG (`/ingest` + retrieval + citations).

> Educational project for the AI Engineering Bootcamp. Not affiliated with or
> endorsed by Nelson Dellis or the book's publisher, and no copyrighted book
> text is included in this repository.

**Full guide:** see [DOCS.md](DOCS.md). Interactive API docs are served live at
`/docs` (Swagger) and `/redoc` once the service is running.

## Endpoints

- `GET /health` — liveness (also the uptime-pinger target for cold starts).
- `POST /ask` — `{"question": "..."}` → flat JSON:

```json
{
  "answer": "...",
  "confidence": 0.9,
  "sources_needed": false,
  "citations": [],
  "tokens_used": 138,
  "cost_usd": 0.000041
}
```

`citations` is empty until Week 2 wires in retrieval.

## Run locally

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...          # Windows PowerShell: $env:OPENAI_API_KEY="sk-..."
uvicorn main:app --reload             # http://localhost:8000
streamlit run streamlit_app.py        # UI (reads API_URL, defaults to localhost)
```

## Deploy (Render)

Push to GitHub, create a Render Web Service from the repo (`render.yaml` is
included), set `OPENAI_API_KEY`. **Cold starts:** point a free uptime monitor
(cron-job.org / UptimeRobot) at `/health` every ~10 min so the first real
request isn't a 10-second wake-up.

## Guardrail

`/ask` re-validates the model's structured output with `parse_answer`; on
malformed output it retries once, then returns a safe refusal. To show the
guardrail catching a bad response, run the smoke test — it feeds malformed
strings straight to the guardrail:

```bash
python test_smoke.py
```

## Cost note

`PRICES` in `main.py` is USD per 1M tokens — **verify against current OpenAI
pricing** before trusting `cost_usd`.
