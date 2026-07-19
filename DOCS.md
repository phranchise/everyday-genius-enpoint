# Everyday Genius Coach: Documentation

An API that coaches memory and cognition techniques inspired by Nelson Dellis's
book *Everyday Genius*. You send a question, and it returns a short, practical
technique along with its confidence, the tokens used, and the dollar cost of the
call.

This is the Week 1 build: a reliable reasoning endpoint. Week 2 adds retrieval so
answers are grounded in source material with citations.

## What it does

Send a question to `POST /ask` and you get back a single, clean JSON object:

```json
{
  "answer": "Repeat the person's name right after you hear it, then link it to something memorable about them.",
  "confidence": 0.9,
  "sources_needed": false,
  "citations": [],
  "tokens_used": 215,
  "cost_usd": 0.000071
}
```

Every field has a job:

- **answer**: the coaching response, kept short and actionable.
- **confidence**: the model's self-reported confidence, from 0 to 1.
- **sources_needed**: true when a good answer would need source material the
  service does not have. In Week 2 this drives honest refusals.
- **citations**: empty for now. Week 2 fills this with the chunks or documents an
  answer is grounded in.
- **tokens_used**: total tokens for the call.
- **cost_usd**: the dollar cost of the call, computed from current token pricing.

## Endpoints

### GET /health

A liveness check. Returns `{"status": "ok"}`. Use it as the target for an uptime
pinger so the service does not fall asleep on the free tier.

### POST /ask

Request body:

```json
{ "question": "How do I remember someone's name when I first meet them?" }
```

Returns the JSON object shown above.

## Try it

Replace `<your-url>` with your deployed address.

```bash
# health
curl <your-url>/health

# ask a question
curl -X POST <your-url>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I remember a shopping list without writing it down?"}'
```

Interactive docs come for free. FastAPI serves a live Swagger UI at
`<your-url>/docs` and a ReDoc page at `<your-url>/redoc`, where you can read the
schema and send test requests straight from the browser.

## How it stays reliable

Three things separate this from a raw model call:

- **Structured output.** The model is required to return JSON that matches a
  fixed schema, so clients always get the same shape back.
- **A guardrail.** The service re-validates every response. If the output is
  malformed, it retries once, then falls back to a safe refusal instead of
  returning garbage.
- **Cost tracking.** Every call reports its own token count and dollar cost, so
  nothing about spend is a mystery.

## Run it locally

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...          # PowerShell: $env:OPENAI_API_KEY="sk-..."
uvicorn main:app --reload             # http://localhost:8000
streamlit run streamlit_app.py        # optional UI
```

Run the smoke test to watch the guardrail catch bad output on its own:

```bash
python test_smoke.py
```

## What's next

Week 2 turns this into a document-grounded system. It adds a `POST /ingest`
endpoint that chunks and embeds text into a vector store, and it upgrades `/ask`
to retrieve relevant passages, cite them, and refuse when the source material
does not cover the question.

## Note

This is an educational project for the AI Engineering Bootcamp. It is not
affiliated with or endorsed by Nelson Dellis or the book's publisher, and no
copyrighted book text is included in this repository.
