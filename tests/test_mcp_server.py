"""Stage 7: the MCP server, tested in memory (no subprocess, no Ollama, no host).
Retrieval is faked; the real config.yaml is used, so personal/ is private."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from mcp import Client

from src.interfaces import mcp_server as server

CANARY = "CANARY-5512"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def text_of(result):
    return "\n".join(getattr(block, "text", "") for block in result.content)


class FakeRetrieve:
    """Returns one shareable and one PRIVATE chunk, to prove the second check drops it."""

    def __init__(self, empty=False):
        self.calls, self.empty = [], empty

    def __call__(self, collection, query, top_k=5, intent=None, folders=None):
        self.calls.append({"intent": intent, "folders": folders, "top_k": top_k})
        if self.empty:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]]}
        metas = [
            {"source": "handovers\\arjun_master_handoff_oct2026.md", "folder": "handovers",
             "header_path": "Ratings", "version_date": "2026-10-01", "date_source": "filename",
             "group_size": 4, "is_latest": True},
            {"source": "personal\\chronicle_sep2026.md", "folder": "personal",
             "header_path": "September", "version_date": "2026-09-01", "date_source": "filename",
             "group_size": 1, "is_latest": True},
        ]
        return {"ids": [["a", "b"]], "documents": [["CF rating is 1550", f"diary {CANARY}"]],
                "metadatas": [metas]}


@pytest.fixture
def fake(monkeypatch):
    fake = FakeRetrieve()
    monkeypatch.setattr(server, "retrieve", fake)
    monkeypatch.setattr(server, "get_collection", lambda: None)
    return fake


@pytest.mark.anyio
async def test_exposes_three_tools():
    async with Client(server.mcp) as client:
        listed = await client.list_tools()
    assert {tool.name for tool in listed.tools} == {"search_notes", "get_project_status", "list_projects"}


@pytest.mark.anyio
async def test_search_is_scoped_to_shareable_folders(fake):
    async with Client(server.mcp) as client:
        await client.call_tool("search_notes", {"query": "cf rating", "mode": "current"})
    call = fake.calls[0]
    assert call["intent"] == "current_state"
    assert "personal" not in call["folders"]
    assert "handovers" in call["folders"]


@pytest.mark.anyio
async def test_private_chunk_never_leaves_even_if_retrieved(fake):
    async with Client(server.mcp) as client:
        result = await client.call_tool("search_notes", {"query": "anything"})
    text = text_of(result)
    assert CANARY not in text
    assert "SOURCE: handovers/arjun_master_handoff_oct2026.md" in text
    assert "personal/" not in text


@pytest.mark.anyio
async def test_history_mode_and_empty_results(monkeypatch):
    fake = FakeRetrieve(empty=True)
    monkeypatch.setattr(server, "retrieve", fake)
    monkeypatch.setattr(server, "get_collection", lambda: None)
    async with Client(server.mcp) as client:
        result = await client.call_tool("search_notes", {"query": "rating", "mode": "history"})
    assert fake.calls[0]["intent"] == "historical"
    assert "No matching notes found." in text_of(result)