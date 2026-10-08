"""Stage 6.5 privacy suite. Spy models record every message they receive; a
canary string planted in private content must never reach the hosted model.
No Ollama needed: router, retriever and models are all fakes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from langchain_core.messages import AIMessage

from src.router.config import config_from_dict
from src.router.graph import ask, build_router_graph
from src.router.llm_router import fallback_route, normalize_route
from src.router.memory import make_turn
from src.router.privacy_filter import (
    PrivacyViolation,
    assert_hosted_safe,
    filter_history,
    route_is_private,
)
from src.router.prompts import LOCAL_DOWN

CANARY = "CANARY-7731"

CFG = config_from_dict({
    "paths": {"notes": "n", "index": "i", "collection": "c"},
    "folders": {
        "projects": {"privacy": "shareable"},
        "handovers": {"privacy": "shareable"},
        "personal": {"privacy": "private", "versioned": False},
    },
    "domains": {
        "projects": {"description": "projects", "folders": ["projects", "handovers"]},
        "personal": {"description": "feelings", "folders": ["personal"], "style": "Talk like a friend."},
    },
})


class SpyModel:
    def __init__(self, name, fail=False):
        self.name, self.fail, self.calls = name, fail, []

    def invoke(self, messages):
        self.calls.append(messages)
        if self.fail:
            raise ConnectionError("model down")
        return AIMessage(content=f"{self.name} answer")


def text(call):
    return "\n".join(str(m.content) for m in call)


def fake_route(question, recent=()):
    if "[casual]" in question:
        domains, request = ["projects"], "casual"
    elif "[mixed]" in question:
        domains, request = ["projects", "personal"], "decision"
    elif "[personal]" in question:
        domains, request = ["personal"], "reflect"
    else:
        domains, request = ["projects"], "question"
    leaked = " ".join(t["content"] for t in recent)  # deliberately leaky rewrite
    return {
        "search_query": f"{question} {leaked}".strip(),
        "domains": domains,
        "intent": "lookup",
        "request": request,
        "fallback": None,
    }


class FakeRetriever:
    def __init__(self, leak_private=False):
        self.calls, self.leak_private = [], leak_private

    def __call__(self, query, intent, folders):
        self.calls.append((query, intent, folders))
        chunks = []
        if folders is None or "projects" in folders:
            chunks.append(("PixelNet reached 91.3%",
                           {"source": "projects\\pixelnet.md", "folder": "projects", "header_path": "Results"}))
        if self.leak_private or (folders and "personal" in folders):
            chunks.append((f"diary entry {CANARY}",
                           {"source": "personal\\chronicle_sep2026.md", "folder": "personal", "header_path": "Sep"}))
        return {
            "ids": [[f"id{i}" for i in range(len(chunks))]],
            "documents": [[c[0] for c in chunks]],
            "metadatas": [[c[1] for c in chunks]],
        }


def test_private_turn_never_reaches_hosted():
    local, hosted, retriever = SpyModel("local"), SpyModel("hosted"), FakeRetriever()
    app = build_router_graph(CFG, fake_route, retriever, local, hosted)
    first = ask(app, f"[personal] I feel low {CANARY}", "t")
    second = ask(app, "What is the status of PixelNet?", "t")
    assert first["private"] and first["model_used"] == "local"
    assert second["model_used"] == "hosted"
    assert len(local.calls) == 1 and len(hosted.calls) == 1
    assert CANARY not in text(hosted.calls[0])
    assert CANARY in retriever.calls[1][0]  # the leaky rewrite DID carry it, but only to local retrieval


def test_mixed_domain_message_stays_local():
    local, hosted = SpyModel("local"), SpyModel("hosted")
    app = build_router_graph(CFG, fake_route, FakeRetriever(), local, hosted)
    result = ask(app, "[mixed] should I pause PixelNet, I'm exhausted", "t")
    assert result["private"] and result["model_used"] == "local"
    assert hosted.calls == []


def test_local_down_fails_visibly_no_fallback():
    local, hosted = SpyModel("local", fail=True), SpyModel("hosted")
    app = build_router_graph(CFG, fake_route, FakeRetriever(), local, hosted)
    result = ask(app, "[personal] rough day", "t")
    assert result["answer"] == LOCAL_DOWN
    assert result["model_used"] == "none"
    assert hosted.calls == []


def test_private_chunk_in_results_forces_local():
    local, hosted = SpyModel("local"), SpyModel("hosted")
    app = build_router_graph(CFG, fake_route, FakeRetriever(leak_private=True), local, hosted)
    result = ask(app, "What is the status of PixelNet?", "t")
    assert result["private"] and result["model_used"] == "local"
    assert hosted.calls == []


def test_scope_excludes_private_folders():
    retriever = FakeRetriever()
    app = build_router_graph(CFG, fake_route, retriever, SpyModel("local"))
    ask(app, "What is the status of PixelNet?", "t")
    assert retriever.calls[0][2] == ["handovers", "projects"]


def test_non_private_answer_never_sees_private_turns_even_locally():
    local = SpyModel("local")
    app = build_router_graph(CFG, fake_route, FakeRetriever(), local)
    ask(app, f"[personal] I feel low {CANARY}", "t")
    second = ask(app, "What is the status of PixelNet?", "t")
    assert CANARY not in text(local.calls[1])
    assert second["hidden_private"] == 1


def test_memory_is_per_thread():
    local = SpyModel("local")
    app = build_router_graph(CFG, fake_route, FakeRetriever(), local)
    ask(app, "What is the status of PixelNet?", "a")
    ask(app, "And QubitML?", "a")
    ask(app, "And QubitML?", "b")
    assert "status of PixelNet" in text(local.calls[1])
    assert "status of PixelNet" not in text(local.calls[2])


def test_casual_skips_retrieval():
    retriever = FakeRetriever()
    app = build_router_graph(CFG, fake_route, retriever, SpyModel("local"))
    ask(app, "[casual] hey", "t")
    assert retriever.calls == []


def test_router_fallback_fails_closed():
    route = fallback_route("anything", CFG, "router error")
    assert set(route["domains"]) == set(CFG.domain_names)
    assert route_is_private(route, CFG)


def test_normalize_drops_unknown_domains():
    route = normalize_route(
        {"domains": ["projects", "bogus", "projects"], "intent": "weird", "request": "question",
         "search_query": ""},
        "q?", CFG,
    )
    assert route["domains"] == ["projects"]
    assert route["intent"] in ("current_state", "historical", "lookup")
    assert route["search_query"] == "q?"
    assert normalize_route({"domains": ["bogus"]}, "q?", CFG)["fallback"]


def test_hosted_tripwire():
    with pytest.raises(PrivacyViolation):
        assert_hosted_safe([{"source": "personal\\d.md"}], [], CFG)
    with pytest.raises(PrivacyViolation):
        assert_hosted_safe([], [make_turn("user", "x", True, ["personal"])], CFG)
    assert_hosted_safe([{"source": "projects\\p.md", "folder": "projects"}], [], CFG)


def test_filter_history_drops_both_sides_of_private_exchange():
    history = [
        make_turn("user", "a", False, ["projects"]), make_turn("assistant", "b", False, ["projects"]),
        make_turn("user", "c", True, ["personal"]), make_turn("assistant", "d", True, ["personal"]),
    ]
    assert [t["content"] for t in filter_history(history, allow_private=False)] == ["a", "b"]
    assert len(filter_history(history, allow_private=True)) == 4