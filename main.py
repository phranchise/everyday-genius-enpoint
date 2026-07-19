"""Everyday Genius Coach — a memory coach for college students.

One service, two ways to use it:
  - POST /ask    : the technique coach. Tell it what you want to remember and it
                   recommends the single best memory technique, in a simple, fun
                   way. Uses general knowledge, no notes needed. (Session 1.)
  - POST /ingest : add your class notes (chunk with overlap, embed, store).
  - POST /study  : study from YOUR notes. Ask about a topic and it retrieves the
                   topic from your notes, suggests a technique to lock it in, cites
                   the passages, and refuses when the topic isn't in your notes. (Session 2.)
  - POST /search : retrieval only, for checking what /study would ground on.
  - GET  /health : liveness (uptime-pinger target for cold starts).

Both /ask and /study share the reliability layer: fixed-schema structured output,
a re-validation guardrail, and per-call token + cost tracking.
"""
import json
import os

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from openai import OpenAI, OpenAIError
from pinecone import Pinecone, ServerlessSpec
from pydantic import BaseModel, Field, ValidationError

CHAT_MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536

INDEX_NAME = "everyday-genius"
TOP_K = 4
# Cosine floor for a chunk to count as relevant. ponytail: calibration knob —
# raise if answers drift off-source, lower if valid topics get refused.
SCORE_THRESHOLD = 0.35
CHUNK_SIZE = 800      # characters
CHUNK_OVERLAP = 150   # characters

# USD per 1M tokens. VERIFY against current OpenAI pricing before trusting cost_usd.
PRICES = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
}

# /ask: recommend a memory technique from general knowledge, student-friendly.
TECHNIQUE_SYSTEM_PROMPT = (
    "You are Everyday Genius Coach, a friendly memory coach for college students. "
    "The student tells you something they want to remember. Recommend the single "
    "best, most effective memory technique for it (for example: the memory palace / "
    "method of loci, chunking, acronyms or acrostics, the major system for numbers, "
    "spaced repetition, vivid mental imagery, or turning it into a short story). "
    "Name the technique, then show how to apply it to their exact input with a "
    "concrete example. Keep it short, simple, and fun, and encourage them. Report "
    "confidence 0-1. Set sources_needed to false."
)

# /study: same coaching, but grounded ONLY in the student's own ingested notes.
STUDY_SYSTEM_PROMPT = (
    "You are Everyday Genius Coach, helping a college student study from THEIR OWN "
    "class notes. Use ONLY the numbered context passages below, which come from the "
    "student's notes. First, in one or two sentences, capture the key idea of the "
    "topic from those passages. Then recommend the best memory technique to lock it "
    "in and show how to apply it to this specific content, in a simple and fun way. "
    "Cite only the passages you actually used. If the passages don't cover the topic, "
    "set sources_needed to true, set a low confidence, and tell the student the topic "
    "isn't in their uploaded notes yet. Do not use outside knowledge. Report confidence 0-1."
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

app = FastAPI(
    title="Everyday Genius Coach",
    version="3.0.0",
    description=(
        "A memory coach for college students.\n\n"
        "**Remember anything** with `POST /ask`: tell it what you want to remember and "
        "it recommends the best memory technique, simply and fun.\n\n"
        "**Study from your notes** with `POST /ingest` (add class notes) then "
        "`POST /study` (ask about a topic): it grounds the answer in your notes, cites "
        "the passages, and refuses when the topic isn't there. `POST /search` shows "
        "retrieval on its own.\n\n"
        "Try any endpoint below with **Try it out**. Full guide: "
        "[DOCS.md on GitHub](https://github.com/phranchise/everyday-genius-enpoint/blob/main/DOCS.md)."
    ),
)

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
    document_id: str
    text: str


class CoachAnswer(BaseModel):
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources_needed: bool


SAFE_REFUSAL = {
    "answer": "I couldn't produce a reliable answer. Try rephrasing.",
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


def guarded_chat(system_prompt: str, user_content: str):
    """Structured chat call with the guardrail: try, retry once, then safe refusal.

    Returns (validated_dict, usage_or_None). Shared by /ask and /study.
    """
    usage = None
    data = None
    for _ in range(2):
        try:
            resp = get_openai().chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
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
    return data, usage


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


@app.get("/", include_in_schema=False)
def root():
    # Landing on the base URL drops you into the interactive docs.
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(q: Question):
    """Technique coach: best way to remember what the student typed. No notes needed."""
    data, usage = guarded_chat(TECHNIQUE_SYSTEM_PROMPT, q.question)
    return {
        **data,
        "citations": [],
        "tokens_used": usage.total_tokens if usage else 0,
        "cost_usd": cost_usd(CHAT_MODEL, usage.prompt_tokens, usage.completion_tokens) if usage else 0.0,
    }


@app.post("/ingest")
def ingest(body: IngestBody):
    chunks = chunk_text(body.text)
    if not chunks:
        return {"document_id": body.document_id, "chunks_ingested": 0, "tokens_used": 0, "cost_usd": 0.0}
    vectors, tokens = embed(chunks)
    items = [
        {
            "id": f"{body.document_id}#{i}",
            "values": v,
            "metadata": {"document_id": body.document_id, "chunk_index": i, "text": chunks[i]},
        }
        for i, v in enumerate(vectors)
    ]
    get_index().upsert(vectors=items)
    return {
        "document_id": body.document_id,
        "chunks_ingested": len(items),
        "tokens_used": tokens,
        "cost_usd": cost_usd(EMBED_MODEL, tokens, 0),
    }


@app.post("/search")
def search(q: Question):
    """Retrieval only — inspect what /study would ground on."""
    matches, tokens = retrieve(q.question)
    return {
        "results": [
            {"id": m.id, "score": round(m.score, 4), "text": m.metadata.get("text", "")[:200]}
            for m in matches
        ],
        "tokens_used": tokens,
    }


@app.post("/study")
def study(q: Question):
    """Grounded coach: retrieve the topic from the student's notes, then coach it."""
    matches, embed_tokens = retrieve(q.question)
    embed_cost = cost_usd(EMBED_MODEL, embed_tokens, 0)
    grounded = [m for m in matches if m.score >= SCORE_THRESHOLD]

    # Refuse (before paying for generation) when the topic isn't in the notes.
    if not grounded:
        return {
            "answer": "That topic isn't in your uploaded notes yet. Add notes on it, then ask again.",
            "confidence": 0.0,
            "sources_needed": True,
            "citations": [],
            "tokens_used": embed_tokens,
            "cost_usd": round(embed_cost, 6),
        }

    context = "\n\n".join(f"[{m.id}] {m.metadata['text']}" for m in grounded)
    data, usage = guarded_chat(STUDY_SYSTEM_PROMPT, f"Context passages:\n{context}\n\nTopic: {q.question}")

    chat_tokens = usage.total_tokens if usage else 0
    chat_cost = cost_usd(CHAT_MODEL, usage.prompt_tokens, usage.completion_tokens) if usage else 0.0
    return {
        **data,
        "citations": [m.id for m in grounded],
        "tokens_used": embed_tokens + chat_tokens,
        "cost_usd": round(embed_cost + chat_cost, 6),
    }
