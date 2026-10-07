"""Version-aware retrieval policy.

current_state -> filter to the latest version of every document family
historical    -> keep every version; pull in missing sibling versions;
                 present chunks oldest -> newest
lookup        -> keep every version; keep relevance order
"""

MAX_HISTORICAL_CHUNKS = 10


def version_filter(intent):
    """Metadata filter applied to BOTH dense and BM25 retrieval."""
    if intent == "current_state":
        return {"is_latest": True}
    return None


def expand_versions(results, bm25, query, max_total=MAX_HISTORICAL_CHUNKS):
    """For every multi-version family present in results, add the best
    BM25-matching chunk from each version of that family that is missing.
    A 'how did X change' question needs both endpoints of the change."""
    ids = list(results["ids"][0])
    docs = list(results["documents"][0])
    metas = list(results["metadatas"][0])

    present_sources = {m["source"] for m in metas}
    families = {m["doc_group_id"] for m in metas if m.get("group_size", 1) > 1}

    sibling_dates = {}
    for m in bm25.metadatas:
        if m.get("doc_group_id") in families and m["source"] not in present_sources:
            sibling_dates[m["source"]] = m.get("version_date", "")

    by_id = dict(zip(bm25.ids, zip(bm25.documents, bm25.metadatas)))

    for source in sorted(sibling_dates, key=sibling_dates.get):
        if len(ids) >= max_total:
            break
        hits = bm25.search(query, top_k=1, where={"source": source})
        if not hits:
            continue
        chunk_id = hits[0][0]
        doc, meta = by_id[chunk_id]
        ids.append(chunk_id)
        docs.append(doc)
        metas.append(meta)

    return {"ids": [ids], "documents": [docs], "metadatas": [metas]}


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