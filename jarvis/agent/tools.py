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

from jarvis.registry.queries import get_project_status as registry_status
from jarvis.registry.queries import list_projects as registry_list
from jarvis.registry.store import load_registry
from jarvis.retrieval.search import date_note, retrieve
from jarvis.retrieval.vector_store import open_vectorstore

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


STRONG_DATE_SOURCES = {"filename", "header"}


def strong_history(history):
    """Drop mentions dated only by file mtime: a copy date can't place a change in time.
    Same rule as search output ('undated'). Falls back to everything if nothing is strong."""
    strong = [h for h in history if h.get("date_source") in STRONG_DATE_SOURCES]
    return strong or history


def status_changes(history):
    """-> 'active (2026-06-01 to 2026-09-01) -> paused (2026-10-01)'.
    Each status shows when it was first AND last seen, so 'when did X change'
    can be answered as 'between the last active date and the first paused date'."""
    spans = []  # [status, first_date, last_date]
    for h in strong_history(history):
        if h["status"] == "unclear":
            continue
        if spans and spans[-1][0] == h["status"]:
            spans[-1][2] = h["version_date"]
        else:
            spans.append([h["status"], h["version_date"], h["version_date"]])
    return " -> ".join(
        f"{s} ({first})" if first == last else f"{s} ({first} to {last})"
        for s, first, last in spans
    )


def metric_changes(history):
    """-> '89.7% (2026-08-01) -> 91.3% (2026-10-01)', or '' if the metric never changed."""
    values = []
    for h in strong_history(history):
        m = h.get("key_metric", "")
        if m and (not values or values[-1][0] != m):
            values.append((m, h["version_date"]))
    if len(values) < 2:
        return ""
    return " -> ".join(f"{m} ({d})" for m, d in values)


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
        metrics = metric_changes(r["history"])
        if metrics:
            lines.append(f"key metric history: {metrics}")
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
    """Look up the STATUS of ONE project by its name.

    Returns its current status (active / paused / done / abandoned / planned),
    the reason, the dates of each status, and its SOURCE files.
    Use ONLY for: "is X still going?", "why was X paused/abandoned?",
    "when did X's status change?". name must be a project name.
    NOT for tech stack details, numbers, people, plans or career: use search_notes.
    """
    try:
        record = registry_status(name, registry=_registry())
        if record is None:
            known = ", ".join(r["name"] for r in _registry().values())
            return (
                f"'{name}' is not a project. Projects: {known}. "
                "This tool only covers project status. Call search_notes for this question."
            )
        return format_record(record)
    except FileNotFoundError:
        return "The project registry has not been built yet. Use search_notes instead."
    except Exception as e:
        return f"get_project_status failed: {type(e).__name__}: {e}"


@tool
def list_projects(
    status: Literal["all", "active", "paused", "done", "abandoned", "planned"] = "all",
) -> str:
    """List the user's projects by STATUS.

    status: "all" for every project, or one status to filter by.
    Use ONLY for: "which projects are paused?", "what's done?", "list all projects
    and their statuses". NOT for "which projects use X" or other details: use search_notes.
    """
    try:
        rows = registry_list(None if status == "all" else status, registry=_registry())
        if not rows:
            return f"No projects with status '{status}' in the registry."
        return "\n\n".join(format_record(r) for r in rows)
    except FileNotFoundError:
        return "The project registry has not been built yet. Use search_notes instead."
    except Exception as e:
        return f"list_projects failed: {type(e).__name__}: {e}"


TOOLS = [search_notes, get_project_status, list_projects]