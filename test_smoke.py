"""Runnable checks for the deterministic logic: guardrail parsing + cost math.

Runs offline (no OpenAI key needed) because the client is lazy-initialised.
    python test_smoke.py
"""
from main import parse_answer, cost_usd


def test_parse_valid():
    good = '{"answer": "Use a memory palace.", "confidence": 0.9, "sources_needed": false}'
    assert parse_answer(good) == {
        "answer": "Use a memory palace.",
        "confidence": 0.9,
        "sources_needed": False,
    }


def test_parse_malformed_is_caught():
    assert parse_answer("not json at all") is None                                    # bad JSON
    assert parse_answer('{"answer": "x"}') is None                                    # missing fields
    assert parse_answer('{"answer": "x", "confidence": 5, "sources_needed": false}') is None  # out of range


def test_cost_math():
    assert cost_usd("gpt-4o-mini", 1_000_000, 0) == 0.15
    assert cost_usd("gpt-4o-mini", 0, 1_000_000) == 0.60


if __name__ == "__main__":
    test_parse_valid()
    test_parse_malformed_is_caught()
    test_cost_math()
    print("all smoke tests passed")
