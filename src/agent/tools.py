"""Stage 6 — the agent's tools.

Each tool is a thin wrapper over code that already works and is already tested:
  search_notes                       -> Stage 4 version-aware hybrid retrieval
  get_project_status, list_projects  -> Stage 5 structured registry

The docstring of each tool IS the prompt the model reads when deciding which tool
to call and with what arguments, so it is written for the model, not for us.

Tools never raise. Any failure comes back as text the model can read and recover
from (an exception would end the whole agent run).

Every tool output labels its evidence with "SOURCE: <path>" so the citation
checker in agent.py can tell real citations from invented ones.
"""
from pathlib import Path
from typing import Literal, Optional

from langchain.tools import tool

from src.registry.queries import get_project_status as registry_status
from src.registry.queries import list_projects as registry_list
from src.registry.store import load_registry
from src.retrieval.search import date_note, retrieve
from src.retrieval.vector_store import open_vectorstore

STORE_PATH = Path("data/chroma-store/")
COLLECTION_NAME = "sample_collection"
SEARCH_TOP_K = 5

# The agent picks the time intent; the Stage 4 regex classifier is bypassed here.
MODE_TO_INTENT = {"current": "current_state", "history": "historical", "any": "lookup"}

NO_RESULTS = "No matching notes found. Try different keywords once; if still nothing, the notes don't cover it."

_cache = {}


def _collection():
    if "collection" not in _cache:
        _cache["collection"] = open_vectorstore(STORE_PATH, COLLECTION_NAME)
    return _cache["collection"]


def _registry():
    if "registry" not in _cache:
        _cache["registry"] = load_registry()
    return _cache["registry"]


def clean_path(source):
    return source.replace("\\", "/")


# ---------- formatting (pure functions, unit-tested) ----------

def format_hits(results):
    """Chroma-shaped results -> one text block per chunk, newest-relevant info first."""
    blocks = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        header = f"SOURCE: {clean_path(meta['source'])} > {meta['header_path']} ({date_note(meta)})"
        blocks.append(f"{header}\n{doc.strip()}")
    return "\n\n---\n\n".join(blocks)


def status_changes(history):
    """[{status, version_date}, ...] -> 'active (2026-06-01) -> paused (2026-10-01)'."""
    changes, prev = [], None
    for h in history:
        if h["status"] != "unclear" and h["status"] != prev:
            changes.append(f"{h['status']} ({h['version_date']})")
            prev = h["status"]
    return " -> ".join(changes)


def format_record(r):
    """One registry row -> compact text. Empty fields are left out, not shown as blanks."""
    lines = [
        f"PROJECT: {r['name']}",
        f"status: {r['status']} (as of {r['as_of']}) SOURCE: {clean_path(r['source'])}",
    ]
    if r.get("status_reason"):
        lines.append(f"reason: {r['status_reason']} SOURCE: {clean_path(r['status_reason_source'])}")
    if r.get("next_step"):
        lines.append(f"next step: {r['next_step']}")
    if r.get("key_metric"):
        lines.append(f"key metric: {r['key_metric']} SOURCE: {clean_path(r['key_metric_source'])}")
    if r.get("description"):
        lines.append(f"about: {r['description']}")
    if r.get("tech"):
        lines.append(f"tech: {', '.join(r['tech'])}")
    if r.get("history"):
        lines.append(f"status history: {status_changes(r['history'])}")
    return "\n".join(lines)


# ---------- the tools ----------

@tool
def search_notes(query: str, mode: Literal["current", "history", "any"] = "any") -> str:
    """Search the user's notes (handovers, plans, project docs, resumes, ratings) for facts.

    Use for any factual question that is not purely about a project's status.
    query: a short keyword-rich search phrase, e.g. "Codeforces rating" (not a full sentence).
    mode:
      "current" - the question asks about NOW (current, latest, still, these days).
                  Only the newest version of each document is searched.
      "history" - the question asks how something CHANGED, when, or over time.
                  All versions are returned in date order, oldest first.
      "any"     - everything else.
    Each result starts with SOURCE: <file path> (date). Cite that path.
    """
    try:
        results = retrieve(_collection(), query, top_k=SEARCH_TOP_K, intent=MODE_TO_INTENT[mode])
        if not results["documents"][0]:
            return NO_RESULTS
        return format_hits(results)
    except Exception as e:  # never crash the agent run
        return f"search_notes failed: {type(e).__name__}: {e}"


@tool
def get_project_status(name: str) -> str:
    """Look up ONE project by name in the project registry.

    Returns its current status (active / paused / done / abandoned / planned),
    the reason for that status, next step, key metric, tech and status history,
    each with the SOURCE file it came from. Use for "is X still going?",
    "why was X paused?", "what did X achieve?". Any spelling of the name works.
    """
    try:
        record = registry_status(name, registry=_registry())
        if record is None:
            known = ", ".join(r["name"] for r in _registry().values())
            return f"No project called '{name}' in the registry. Known projects: {known}."
        return format_record(record)
    except FileNotFoundError:
        return "The project registry has not been built yet. Use search_notes instead."
    except Exception as e:
        return f"get_project_status failed: {type(e).__name__}: {e}"


@tool
def list_projects(
    status: Optional[Literal["active", "paused", "done", "abandoned", "planned"]] = None,
) -> str:
    """List the user's projects from the project registry.

    status: only projects with this current status, or leave empty for ALL projects.
    Use for "which projects are paused?", "what's done?", "list all my projects".
    Each project comes with its reason, dates and SOURCE files.
    """
    try:
        rows = registry_list(status, registry=_registry())
        if not rows:
            return f"No projects with status '{status}' in the registry."
        return "\n\n".join(format_record(r) for r in rows)
    except FileNotFoundError:
        return "The project registry has not been built yet. Use search_notes instead."
    except Exception as e:
        return f"list_projects failed: {type(e).__name__}: {e}"


TOOLS = [search_notes, get_project_status, list_projects]
