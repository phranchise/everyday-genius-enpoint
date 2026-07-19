# Everyday Genius Coach

A document-grounded API that coaches memory and cognition techniques. Feed it your
own notes with `POST /ingest`, then ask questions with `POST /ask`, and it answers
only from what you gave it, cites the passages it used, and refuses when your notes
do not cover the question. Built on a Week 1 reliable-reasoning base, then extended
with retrieval (RAG) for Week 2.

> Educational project for the AI Engineering Bootcamp. Not affiliated with or
> endorsed by Nelson Dellis or the book's publisher, and no copyrighted book
> text is included in this repository.

**Full guide:** see [DOCS.md](DOCS.md). Interactive API docs are served live at
`/docs` (Swagger) and `/redoc` once the service is running.

## Endpoints

- `GET /health`: liveness, and the uptime-pinger target for cold starts.
- `POST /ingest`: `{"doc_id": "...", "text": "..."}`, chunks with overlap, embeds, stores.
- `POST /ask`: `{"question": "..."}`, retrieves and grounds. Flat JSON:

```json
{
  "answer": "...",
  "confidence": 0.9,
  "sources_needed": false,
  "citations": ["memory-notes#0"],
  "tokens_used": 730,
  "cost_usd": 0.000119
}
```

- `POST /search`: retrieval only, for checking what `/ask` would ground on.

When nothing relevant is retrieved, `/ask` refuses: `sources_needed` is true,
`citations` is empty, and no generation call is made.

## Run locally

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...          # PowerShell: $env:OPENAI_API_KEY="sk-..."
export PINECONE_API_KEY=pcsk_...      # PowerShell: $env:PINECONE_API_KEY="pcsk_..."
uvicorn main:app --reload             # http://localhost:8000
streamlit run streamlit_app.py        # UI with Ingest and Ask tabs
```

## Deploy (Render)

Push to GitHub, create a Render Web Service from the repo (`render.yaml` is
included), and set both `OPENAI_API_KEY` and `PINECONE_API_KEY`. Cold starts:
point a free uptime monitor (cron-job.org or UptimeRobot) at `/health` every
~10 min so the first real request is not a slow wake-up.

## Guardrail

`/ask` re-validates the model's structured output with `parse_answer`. On
malformed output it retries once, then returns a safe refusal. To show the
guardrail catching a bad response, run the smoke test, which feeds malformed
strings straight to it:

```bash
python test_smoke.py
```

## Cost note

`PRICES` in `main.py` is USD per 1M tokens. Verify against current OpenAI pricing
before trusting `cost_usd`.
