# Everyday Genius Coach

A memory coach for college students. Two ways to use it:

1. **Remember anything** with `POST /ask`: tell it what you want to remember and it
   recommends the best memory technique to lock it in, simply and with a fun example.
2. **Study from your notes** with `POST /ingest` then `POST /study`: add your class
   notes, ask about a topic, and it grounds a technique in your own notes, cites the
   passages, and refuses when the topic is not there.

Built on a Session 1 reliable-reasoning base, then extended with retrieval (RAG) for
Session 2.

> Educational project for the AI Engineering Bootcamp. Not affiliated with or
> endorsed by Nelson Dellis or the book's publisher, and no copyrighted book
> text is included in this repository.

**Full guide:** see [DOCS.md](DOCS.md). Interactive API docs are served live at
`/docs` (Swagger) and `/redoc`, and the base URL redirects there.

## Endpoints

- `GET /health`: liveness, and the uptime-pinger target for cold starts.
- `POST /ask`: `{"question": "..."}`, recommends a technique. Ungrounded, no notes needed.
- `POST /ingest`: `{"document_id": "...", "text": "..."}`, chunks with overlap, embeds, stores.
- `POST /study`: `{"question": "..."}`, retrieves from your notes and grounds the answer:

```json
{
  "answer": "...",
  "confidence": 0.9,
  "sources_needed": false,
  "citations": ["bio-chapter-3#0"],
  "tokens_used": 730,
  "cost_usd": 0.000119
}
```

- `POST /search`: retrieval only, for checking what `/study` would ground on.

When the topic is not in your notes, `/study` refuses: `sources_needed` is true and
`citations` is empty.

## Run locally

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...          # PowerShell: $env:OPENAI_API_KEY="sk-..."
export PINECONE_API_KEY=pcsk_...      # PowerShell: $env:PINECONE_API_KEY="pcsk_..."
uvicorn main:app --reload             # http://localhost:8000
streamlit run streamlit_app.py        # student UI
```

## Deploy (Render)

Push to GitHub, create a Render Web Service from the repo (`render.yaml` is
included), and set both `OPENAI_API_KEY` and `PINECONE_API_KEY`. Cold starts: point a
free uptime monitor (cron-job.org or UptimeRobot) at `/health` every ~10 min so the
first real request is not a slow wake-up.

## Guardrail

`/ask` and `/study` re-validate the model's structured output with `parse_answer`. On
malformed output they retry once, then return a safe refusal. To show the guardrail
catching a bad response, run the smoke test, which feeds malformed strings straight to
it:

```bash
python test_smoke.py
```

## Cost note

`PRICES` in `main.py` is USD per 1M tokens. Verify against current OpenAI pricing
before trusting `cost_usd`.
