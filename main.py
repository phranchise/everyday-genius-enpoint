"""Everyday Genius Coach — Week 1 base: a reliable /ask reasoning endpoint.

POST /ask returns a flat, validated JSON payload with token + cost accounting.
Week 2 extends THIS SAME service with /ingest + retrieval (RAG); the response
already carries `citations` and `sources_needed`, so /ask gets extended, not
rebuilt.
"""
import json
import os

from fastapi import FastAPI
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field, ValidationError

CHAT_MODEL = "gpt-4o-mini"

# USD per 1M tokens. VERIFY against current OpenAI pricing before trusting cost_usd.
PRICES = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

SYSTEM_PROMPT = (
    "You are Everyday Genius Coach, a memory and cognition coach grounded in the "
    "techniques from Nelson Dellis's book 'Everyday Genius'. Give one concise, "
    "actionable technique the user can apply right now. Report your own confidence "
    "(0-1). Set sources_needed=true if answering well would require source material "
    "you don't actually have."
)

# Structured-output contract enforced by the model, then re-validated below (guardrail).
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

_client = None


def get_client() -> OpenAI:
    # Lazy so importing this module (e.g. for tests) doesn't require OPENAI_API_KEY.
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


class Question(BaseModel):
    question: str


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


@app.get("/health")
def health():
    # Cheap wake-up target for an uptime pinger (beats Render free-tier cold starts).
    return {"status": "ok"}


@app.post("/ask")
def ask(q: Question):
    usage = None
    data = None
    for _ in range(2):  # guardrail: try once, retry once, then fall back to a safe refusal
        try:
            resp = get_client().chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": q.question},
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

    return {
        **data,
        "citations": [],  # populated in Week 2 (RAG)
        "tokens_used": usage.total_tokens if usage else 0,
        "cost_usd": cost_usd(CHAT_MODEL, usage.prompt_tokens, usage.completion_tokens) if usage else 0.0,
    }
