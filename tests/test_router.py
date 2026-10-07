import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.retrieval.version_ranker import order_for_context, version_filter
from src.router.classifier import classify_intent


def test_current_state():
    assert classify_intent("What is Arjun's current Codeforces rating?") == "current_state"
    assert classify_intent("Is QubitML still being worked on?") == "current_state"


def test_historical():
    assert classify_intent("How has his CF rating changed since June?") == "historical"
    assert classify_intent("What did his career plan look like originally?") == "historical"


def test_historical_beats_current():
    assert classify_intent("How has his rating changed and what is it now?") == "historical"


def test_lookup_default():
    assert classify_intent("What optimizer does PixelNet use?") == "lookup"


def test_filter_only_for_current_state():
    assert version_filter("current_state") == {"is_latest": True}
    assert version_filter("historical") is None
    assert version_filter("lookup") is None


def test_historical_ordering_oldest_first():
    results = {
        "ids": [["oct", "jun", "aug"]],
        "documents": [["c", "a", "b"]],
        "metadatas": [[{"version_date": "2026-10-01"}, {"version_date": "2026-06-01"},
                       {"version_date": "2026-08-01"}]],
    }
    ordered = order_for_context(results, "historical")
    assert ordered["ids"][0] == ["jun", "aug", "oct"]
    assert order_for_context(results, "lookup") is results