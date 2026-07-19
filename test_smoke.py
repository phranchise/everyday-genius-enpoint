"""Runnable checks for the deterministic logic: guardrail parsing, cost math,
and overlap chunking. Runs offline (no OpenAI/Pinecone keys) because the clients
are lazy-initialised.
    python test_smoke.py
"""
from main import parse_answer, cost_usd, chunk_text


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
    assert cost_usd("text-embedding-3-small", 1_000_000, 0) == 0.02


def test_chunk_overlap():
    chunks = chunk_text("a" * 1000, size=800, overlap=150)
    assert len(chunks) == 2
    assert len(chunks[0]) == 800
    assert chunks[0][-150:] == chunks[1][:150]  # the overlap is actually preserved


def test_chunk_empty():
    assert chunk_text("   ") == []


if __name__ == "__main__":
    test_parse_valid()
    test_parse_malformed_is_caught()
    test_cost_math()
    test_chunk_overlap()
    test_chunk_empty()
    print("all smoke tests passed")
