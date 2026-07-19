# Everyday Genius Coach: Documentation

A document-grounded API that coaches memory and cognition techniques. You feed it
your own notes, then ask questions, and it answers only from what you gave it,
cites the passages it used, and refuses when your notes do not cover the question.

The project grew in two stages. Week 1 was a reliable reasoning endpoint. Week 2,
this version, keeps that same service and adds retrieval so answers are grounded
in your data.

## The shape of it

One service, two everyday processes:

- **Ingest** when your data changes: `POST /ingest` chunks your text, embeds it,
  and stores it in a vector database.
- **Ask** when you have a question: `POST /ask` embeds the question, pulls the
  most relevant chunks, and answers from them with citations.

There is also a `POST /search` for looking at retrieval on its own, and a
`GET /health` liveness check.

## Endpoints

### POST /ingest

Send plain text with a document id. The service splits it into overlapping chunks
so no idea gets cut in half, embeds each chunk, and stores it.

Request:

```json
{ "doc_id": "memory-notes", "text": "The memory palace method works by..." }
```

Response:

```json
{ "doc_id": "memory-notes", "chunks_ingested": 3, "tokens_used": 412, "cost_usd": 0.000008 }
```

### POST /ask

Send a question. The service retrieves the top matching chunks, and if they clear
a relevance threshold it grounds an answer in them. If nothing relevant comes
back, it refuses instead of guessing.

Request:

```json
{ "question": "How does the memory palace method work?" }
```

Grounded response:

```json
{
  "answer": "Walk a familiar route in your mind and place each item at a spot along it...",
  "confidence": 0.9,
  "sources_needed": false,
  "citations": ["memory-notes#0", "memory-notes#1"],
  "tokens_used": 730,
  "cost_usd": 0.000119
}
```

Refusal response, when your notes do not cover the question:

```json
{
  "answer": "I don't have information on that in the ingested documents.",
  "confidence": 0.0,
  "sources_needed": true,
  "citations": [],
  "tokens_used": 8,
  "cost_usd": 0.0
}
```

Every field:

- **answer**: the grounded coaching response, or a refusal.
- **confidence**: the model's self-reported confidence, from 0 to 1.
- **sources_needed**: true when the ingested notes cannot support a real answer.
- **citations**: the chunk ids the answer was grounded in, empty on a refusal.
- **tokens_used**: total tokens across the embedding and the generation.
- **cost_usd**: the dollar cost of the call.

### POST /search

Retrieval only, no generation. Useful for checking what `/ask` would ground on
before you trust the answer. Returns the matched chunk ids with their similarity
scores and a text preview.

### GET /health

Returns `{"status": "ok"}`. Point an uptime pinger at it so the service does not
fall asleep on the free tier.

## How grounding and refusal work

Retrieved chunks come back with a similarity score. Only chunks above a score
floor count as relevant. If none clear it, the service refuses right away without
paying for a generation call. When chunks do clear it, they become the only
context the model is allowed to use, and the model is told to refuse if that
context still is not enough. The score floor is a tuning knob in `main.py`: raise
it if answers drift off-source, lower it if fair questions get refused.

## The reliability layer, unchanged from Week 1

- **Structured output.** Every answer matches a fixed JSON schema, so clients
  always get the same shape.
- **A guardrail.** The service re-validates each response. On malformed output it
  retries once, then falls back to a safe refusal.
- **Cost tracking.** Each call reports its own tokens and dollar cost, now summed
  across the embedding and the generation.

## Try it

Replace `<your-url>` with your deployed address.

```bash
# ingest some notes
curl -X POST <your-url>/ingest \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "memory-notes", "text": "The memory palace method places items along a familiar route..."}'

# ask a grounded question
curl -X POST <your-url>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How does the memory palace method work?"}'

# ask something your notes do not cover, and watch it refuse
curl -X POST <your-url>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the capital of France?"}'
```

Interactive docs come for free at `<your-url>/docs` (Swagger) and `<your-url>/redoc`.

## Run it locally

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...          # PowerShell: $env:OPENAI_API_KEY="sk-..."
export PINECONE_API_KEY=pcsk_...      # PowerShell: $env:PINECONE_API_KEY="pcsk_..."
uvicorn main:app --reload             # http://localhost:8000
streamlit run streamlit_app.py        # UI with Ingest and Ask tabs
```

Run the smoke test to check the deterministic parts, chunking and cost math and
the guardrail, without needing any keys:

```bash
python test_smoke.py
```

## A note on what you ingest

The ingest pipeline is content-neutral: it stores whatever text you send. Keep the
corpus to material you have the right to use, such as your own notes and
paraphrases or public-domain sources. Do not ingest copyrighted book text into a
public deployment, and do not commit any corpus text to this repository.

## Note

This is an educational project for the AI Engineering Bootcamp. It is not
affiliated with or endorsed by Nelson Dellis or the book's publisher, and no
copyrighted book text is included in this repository.
