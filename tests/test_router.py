import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.retrieval.bm25 import BM25Index
from src.retrieval.version_ranker import (
    expand_versions,
    order_for_context,
    version_filter,
)
from src.router.classifier import classify_intent


def test_current_state():
    assert (
        classify_intent("What is Arjun's current Codeforces rating?") == "current_state"
    )
    assert classify_intent("Is QubitML still being worked on?") == "current_state"


def test_historical():
    assert classify_intent("How has his CF rating changed since June?") == "historical"
    assert (
        classify_intent("What did his career plan look like originally?")
        == "historical"
    )


def test_historical_beats_current():
    assert (
        classify_intent("How has his rating changed and what is it now?")
        == "historical"
    )


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
        "metadatas": [
            [
                {"version_date": "2026-10-01"},
                {"version_date": "2026-06-01"},
                {"version_date": "2026-08-01"},
            ]
        ],
    }
    ordered = order_for_context(results, "historical")
    assert ordered["ids"][0] == ["jun", "aug", "oct"]
    assert order_for_context(results, "lookup") is results


def _family_index():
    return BM25Index(
        ids=["jun", "oct", "other"],
        documents=[
            "qubitml status active",
            "qubitml status paused",
            "pixelnet accuracy",
        ],
        metadatas=[
            {
                "source": "h_jun.md",
                "doc_group_id": "h",
                "group_size": 2,
                "version_date": "2026-06-01",
            },
            {
                "source": "h_oct.md",
                "doc_group_id": "h",
                "group_size": 2,
                "version_date": "2026-10-01",
            },
            {
                "source": "p.md",
                "doc_group_id": "p",
                "group_size": 1,
                "version_date": "2026-08-01",
            },
        ],
    )


def test_expand_adds_missing_sibling():
    index = _family_index()
    results = {
        "ids": [["oct"]],
        "documents": [["qubitml status paused"]],
        "metadatas": [[index.metadatas[1]]],
    }
    expanded = expand_versions(results, index, "when did qubitml become paused")
    assert expanded["ids"][0] == ["oct", "jun"]


def test_expand_ignores_singletons():
    index = _family_index()
    results = {
        "ids": [["other"]],
        "documents": [["pixelnet accuracy"]],
        "metadatas": [[index.metadatas[2]]],
    }
    assert expand_versions(results, index, "pixelnet accuracy")["ids"][0] == ["other"]
