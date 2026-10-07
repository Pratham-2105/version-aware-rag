"""Version-aware retrieval policy.

current_state -> filter to the latest version of every document family
historical    -> keep every version; present chunks oldest -> newest
lookup        -> keep every version; keep relevance order
"""


def version_filter(intent):
    """Metadata filter applied to BOTH dense and BM25 retrieval."""
    if intent == "current_state":
        return {"is_latest": True}
    return None


def order_for_context(results, intent):
    """For history questions, order retrieved chunks by version_date so the
    model sees the progression. Other intents keep relevance order.
    Takes and returns Chroma-shaped results."""
    if intent != "historical":
        return results

    rows = list(zip(results["ids"][0], results["documents"][0], results["metadatas"][0]))
    rows.sort(key=lambda r: r[2].get("version_date", ""))

    return {
        "ids": [[r[0] for r in rows]],
        "documents": [[r[1] for r in rows]],
        "metadatas": [[r[2] for r in rows]],
    }