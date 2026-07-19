"""Everyday Genius Coach — RAG endpoint (Week 2, built on the Week 1 base).

Same service, two processes:
  - POST /ingest : chunk text (with overlap), embed, store in Pinecone.
  - POST /ask    : embed the question, retrieve top-k chunks, answer ONLY from
                   them with citations, and refuse when the corpus can't support it.
  - POST /search : retrieval-only, for validating retrieval before trusting /ask.
  - GET  /health : liveness (uptime-pinger target for cold starts).

/ask keeps the Week 1 reliability layer unchanged: fixed-schema structured
output, a re-validation guardrail, and per-call token + cost tracking. Retrieval
was inserted in front of the model; the response shape did not change.
"""
import json
import os

from fastapi import FastAPI
from openai import OpenAI, OpenAIError
from pinecone import Pinecone, ServerlessSpec
from pydantic import BaseModel, Field, ValidationError

CHAT_MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536

INDEX_NAME = "everyday-genius"
TOP_K = 4
# Cosine floor for a chunk to count as relevant. ponytail: calibration knob —
# raise if answers drift off-source, lower if valid questions get refused.
SCORE_THRESHOLD = 0.35
CHUNK_SIZE = 800      # characters
CHUNK_OVERLAP = 150   # characters

# USD per 1M tokens. VERIFY against current OpenAI pricing before trusting cost_usd.
PRICES = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
}

GROUNDED_SYSTEM_PROMPT = (
    "You are Everyday Genius Coach, a memory and cognition coach. Answer the user's "
    "question using ONLY the numbered context passages provided, which come from the "
    "user's own ingested notes. Give one concise, actionable technique. If the "
    "passages don't contain enough to answer, set sources_needed=true, set a low "
    "confidence, and say you don't have that in your sources. Do not use outside "
    "knowledge. Report confidence 0-1."
)

ANSWER_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "coach_answer",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "confidence": {"type": "number"},
                "sources_needed": {"type": "boolean"},
            },
            "required": ["answer", "confidence", "sources_needed"],
            "additionalProperties": False,
        },
    },
}

app = FastAPI(title="Everyday Genius Coach")

# --- lazy clients (so importing this module for tests needs no keys) ---
_openai = None
_index = None


def get_openai() -> OpenAI:
    global _openai
    if _openai is None:
        _openai = OpenAI()
    return _openai


def get_index():
    global _index
    if _index is None:
        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        if not pc.has_index(INDEX_NAME):
            pc.create_index(
                name=INDEX_NAME,
                dimension=EMBED_DIM,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        _index = pc.Index(INDEX_NAME)
    return _index


class Question(BaseModel):
    question: str


class IngestBody(BaseModel):
    doc_id: str
    text: str


class CoachAnswer(BaseModel):
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources_needed: bool


SAFE_REFUSAL = {
    "answer": "I couldn't produce a reliable, grounded answer. Try rephrasing.",
    "confidence": 0.0,
    "sources_needed": True,
}


def parse_answer(raw: str):
    """Guardrail: return a validated dict, or None if the model output is malformed."""
    try:
        return CoachAnswer(**json.loads(raw)).model_dump()
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p = PRICES[model]
    return round(prompt_tokens / 1e6 * p["input"] + completion_tokens / 1e6 * p["output"], 6)


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """Split text into overlapping chunks so context isn't cut mid-idea."""
    text = text.strip()
    if not text:
        return []
    step = max(1, size - overlap)
    return [text[i:i + size] for i in range(0, len(text), step) if text[i:i + size].strip()]


def embed(texts):
    """Embed a list of texts with the single locked embedding model."""
    resp = get_openai().embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data], resp.usage.total_tokens


def retrieve(question: str, top_k: int = TOP_K):
    qvec, tokens = embed([question])
    res = get_index().query(vector=qvec[0], top_k=top_k, include_metadata=True)
    return res.matches, tokens


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
def ingest(body: IngestBody):
    chunks = chunk_text(body.text)
    if not chunks:
        return {"doc_id": body.doc_id, "chunks_ingested": 0, "tokens_used": 0, "cost_usd": 0.0}
    vectors, tokens = embed(chunks)
    items = [
        {
            "id": f"{body.doc_id}#{i}",
            "values": v,
            "metadata": {"doc_id": body.doc_id, "chunk_index": i, "text": chunks[i]},
        }
        for i, v in enumerate(vectors)
    ]
    get_index().upsert(vectors=items)
    return {
        "doc_id": body.doc_id,
        "chunks_ingested": len(items),
        "tokens_used": tokens,
        "cost_usd": cost_usd(EMBED_MODEL, tokens, 0),
    }


@app.post("/search")
def search(q: Question):
    """Retrieval only — inspect what /ask would ground on."""
    matches, tokens = retrieve(q.question)
    return {
        "results": [
            {"id": m.id, "score": round(m.score, 4), "text": m.metadata.get("text", "")[:200]}
            for m in matches
        ],
        "tokens_used": tokens,
    }


@app.post("/ask")
def ask(q: Question):
    matches, embed_tokens = retrieve(q.question)
    embed_cost = cost_usd(EMBED_MODEL, embed_tokens, 0)
    grounded = [m for m in matches if m.score >= SCORE_THRESHOLD]

    # Refuse before spending on generation when nothing relevant was retrieved.
    if not grounded:
        return {
            "answer": "I don't have information on that in the ingested documents.",
            "confidence": 0.0,
            "sources_needed": True,
            "citations": [],
            "tokens_used": embed_tokens,
            "cost_usd": round(embed_cost, 6),
        }

    context = "\n\n".join(f"[{m.id}] {m.metadata['text']}" for m in grounded)
    usage = None
    data = None
    for _ in range(2):  # guardrail: try, retry once, then safe refusal
        try:
            resp = get_openai().chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": GROUNDED_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Context passages:\n{context}\n\nQuestion: {q.question}"},
                ],
                response_format=ANSWER_SCHEMA,
            )
        except OpenAIError:
            continue
        usage = resp.usage
        data = parse_answer(resp.choices[0].message.content)
        if data is not None:
            break

    if data is None:
        data = dict(SAFE_REFUSAL)

    chat_tokens = usage.total_tokens if usage else 0
    chat_cost = cost_usd(CHAT_MODEL, usage.prompt_tokens, usage.completion_tokens) if usage else 0.0
    return {
        **data,
        "citations": [m.id for m in grounded],
        "tokens_used": embed_tokens + chat_tokens,
        "cost_usd": round(embed_cost + chat_cost, 6),
    }
