"""Shared retrieval pipeline (the Stage 4 logic), importable with no side effects.

Moved out of cli.py in Stage 6. The V1 CLI, run_eval (through cli.answer_question)
and the agent's search_notes tool all call retrieve() from here, so the agent and
the evaluated pipeline can never drift apart.
"""

from jarvis.retrieval.filters import combine_where, folder_filter
from jarvis.retrieval.hybrid import HybridRetriever
from jarvis.retrieval.version_ranker import (
    expand_versions,
    order_for_context,
    version_filter,
)
from jarvis.router.classifier import classify_intent

RETRIEVAL_MODE = "hybrid"

_retrievers = {}


def get_retriever(collection):
    """Build the BM25 index once per collection, then reuse it."""
    if collection.name not in _retrievers:
        _retrievers[collection.name] = HybridRetriever(collection)
    return _retrievers[collection.name]


def retrieve(collection, question, top_k=5, intent=None, folders=None):
    """Version-aware hybrid retrieval.

    intent=None   -> the Stage 4 regex classifier decides (V1 behaviour, used by eval).
    intent given  -> the caller decides (agent via search_notes mode, router via its LLM).
    folders=None  -> whole vault (V1 / agent). A list -> only chunks from those folders
                     (Stage 6.5 domain scope), applied to dense AND BM25.
    """
    if intent is None:
        intent = classify_intent(question)
    retriever = get_retriever(collection)
    where = combine_where(version_filter(intent), folder_filter(folders))
    results = retriever.search(question, top_k=top_k, where=where, mode=RETRIEVAL_MODE)
    if intent == "historical":
        results = expand_versions(results, retriever.bm25, question)
    return order_for_context(results, intent)


def date_note(meta):
    """'2026-10-01, latest version' / 'undated' — what the model sees about a chunk's age."""
    if meta.get("date_source") == "mtime":
        note = "undated"
    else:
        note = meta.get("version_date", "undated")
    if meta.get("group_size", 1) > 1:
        note += ", latest version" if meta.get("is_latest") else ", older version"
    return note


def format_context(results):
    parts = []
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    for n, (doc, meta) in enumerate(zip(docs, metas), start=1):
        parts.append(
            f"[Source {n}] {meta['source']} > {meta['header_path']} ({date_note(meta)})\n{doc}"
        )
    return "\n\n".join(parts)
