"""Privacy rules as small pure functions, so each one can be tested on its own.

Rule 1  A route is private if ANY routed domain is private (mixed messages stay local).
Rule 2  Private routes run on the local model only; if it is down, fail visibly (graph.py).
Rule 3  A non-private answer never sees private turns from history, on any model.
Rule 4  Tripwire: before a hosted call, re-check that no private chunk or turn is inside.
"""
from src.ingest.metadata import top_folder


class PrivacyViolation(RuntimeError):
    pass


def route_is_private(route, cfg):
    return any(cfg.is_private_domain(d) for d in route["domains"])


def chunk_folder(meta):
    """Prefer the indexed field; derive from source for chunks indexed before 6.5."""
    return meta.get("folder") or top_folder(meta.get("source", ""))


def sources_are_private(metadatas, cfg):
    return any(cfg.is_private_folder(chunk_folder(m)) for m in metadatas)


def filter_history(history, allow_private):
    """Both halves of a private exchange carry the flag, so both are dropped together."""
    if allow_private:
        return list(history)
    return [turn for turn in history if not turn["private"]]


def assert_hosted_safe(metadatas, history, cfg):
    if sources_are_private(metadatas, cfg):
        raise PrivacyViolation("a private-folder chunk was about to be sent to a hosted model")
    if any(turn["private"] for turn in history):
        raise PrivacyViolation("a private turn was about to be sent to a hosted model")