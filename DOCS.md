# Everyday Genius Coach: Documentation

A memory coach for college students. It does two things:

1. **Remember anything.** Tell it what you want to remember and it recommends the
   single best memory technique to lock it in, explained simply and with a fun
   example. No setup needed.
2. **Study from your notes.** Add your class notes, then ask about a topic. It
   pulls that topic from your own notes, suggests a technique made for that exact
   material, cites the passages it used, and tells you honestly when a topic is not
   in your notes yet.

The project grew in two stages. Stage one was a reliable technique coach. Stage two
kept that same service and added retrieval so the coach can work from your notes.

## Endpoints

### POST /ask — remember anything

Recommends a memory technique from general knowledge. No notes involved.

Request:

```json
{ "question": "The first 8 elements of the periodic table" }
```

Response:

```json
{
  "answer": "Use an acrostic. Turn H He Li Be B C N O into a silly sentence...",
  "confidence": 0.9,
  "sources_needed": false,
  "citations": [],
  "tokens_used": 180,
  "cost_usd": 0.00006
}
```

### POST /ingest — add class notes

Send plain text with a `document_id`. The service splits it into overlapping
chunks so no idea gets cut in half, embeds each chunk, and stores it.

Request:

```json
{ "document_id": "bio-chapter-3", "text": "The Krebs cycle is a series of..." }
```

Response:

```json
{ "document_id": "bio-chapter-3", "chunks_ingested": 3, "tokens_used": 412, "cost_usd": 0.000008 }
```

### POST /study — remember a topic from your notes

Retrieves the topic from your ingested notes and coaches it. If the notes cover the
topic it grounds the answer and cites the chunks. If they do not, it refuses instead
of guessing.

Request:

```json
{ "question": "How do I remember the steps of the Krebs cycle?" }
```

Grounded response:

```json
{
  "answer": "Key idea from your notes: the cycle has 8 steps... Use a memory palace...",
  "confidence": 0.9,
  "sources_needed": false,
  "citations": ["bio-chapter-3#0", "bio-chapter-3#1"],
  "tokens_used": 730,
  "cost_usd": 0.000119
}
```

Refusal, when the topic is not in your notes:

```json
{
  "answer": "That topic isn't in your uploaded notes yet. Add notes on it, then ask again.",
  "confidence": 0.0,
  "sources_needed": true,
  "citations": [],
  "tokens_used": 8,
  "cost_usd": 0.0
}
```

### POST /search — retrieval only

No generation. Returns the matched chunk ids, their similarity scores, and a text
preview, so you can check what `/study` would ground on before you trust it.

### GET /health

Returns `{"status": "ok"}`. Point an uptime pinger at it so the service does not
fall asleep on the free tier.

## Every response field

- **answer**: the coaching response, or a refusal.
- **confidence**: the model's self-reported confidence, from 0 to 1.
- **sources_needed**: for `/study`, true when your notes cannot support the topic.
- **citations**: the chunk ids the answer was grounded in. Always empty for `/ask`.
- **tokens_used**: total tokens across embedding and generation.
- **cost_usd**: the dollar cost of the call.

## How grounding and refusal work

Retrieved chunks come back with a similarity score. Only chunks above a score floor
count as relevant. If none clear it, `/study` refuses right away without paying for a
generation call. When chunks do clear it, they become the only context the model may
use, and the model is told to refuse if that context still is not enough. The score
floor is a tuning knob in `main.py`: raise it if answers drift off-source, lower it if
fair topics get refused.

## The reliability layer

Both `/ask` and `/study` share it:

- **Structured output.** Every answer matches a fixed JSON schema, so clients always
  get the same shape.
- **A guardrail.** The service re-validates each response. On malformed output it
  retries once, then falls back to a safe refusal.
- **Cost tracking.** Each call reports its own tokens and dollar cost.

## Try it

Replace `<your-url>` with your deployed address.

```bash
# remember anything
curl -X POST <your-url>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "the cranial nerves in order"}'

# add class notes
curl -X POST <your-url>/ingest \
  -H "Content-Type: application/json" \
  -d '{"document_id": "bio-chapter-3", "text": "The Krebs cycle has eight steps..."}'

# study a topic from your notes (grounded, cited)
curl -X POST <your-url>/study \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I remember the Krebs cycle steps?"}'

# study a topic your notes do not cover (watch it refuse)
curl -X POST <your-url>/study \
  -H "Content-Type: application/json" \
  -d '{"question": "the plot of Hamlet"}'
```

Interactive docs come for free at `<your-url>/docs` (Swagger) and `<your-url>/redoc`.

## Run it locally

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...          # PowerShell: $env:OPENAI_API_KEY="sk-..."
export PINECONE_API_KEY=pcsk_...      # PowerShell: $env:PINECONE_API_KEY="pcsk_..."
uvicorn main:app --reload             # http://localhost:8000
streamlit run streamlit_app.py        # student UI: Remember anything + Study from my notes
```

Run the smoke test to check the deterministic parts, chunking and cost math and the
guardrail, without needing any keys:

```bash
python test_smoke.py
```

## A note on what you ingest

The ingest pipeline is content-neutral: it stores whatever text you send. Keep it to
material you have the right to use, such as your own class notes. Do not ingest
copyrighted book text into a public deployment, and do not commit any corpus text to
this repository.

## Note

This is an educational project for the AI Engineering Bootcamp. It is not affiliated
with or endorsed by Nelson Dellis or the book's publisher, and no copyrighted book
text is included in this repository.
