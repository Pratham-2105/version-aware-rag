"""Short-term memory: the thread's exchanges, verbatim, newest last.

Each entry remembers whether it was private, so later non-private answers can
leave it out (privacy_filter.filter_history). No summaries: a window of recent
exchanges handles follow-ups, and a summary would be one more place for private
text to hide. Persistence comes from the LangGraph checkpointer, keyed by thread_id.
"""


def make_turn(role, content, private, domains):
    return {"role": role, "content": content, "private": bool(private), "domains": list(domains)}


def recent(history, exchanges):
    """Last N exchanges (2 entries each)."""
    if exchanges <= 0:
        return []
    return list(history[-2 * exchanges:])