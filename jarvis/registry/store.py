"""
Stage 5 — merge per-document mentions into one record per project.

Version-aware: a project's current status comes from its most recent mention,
where filename/header dates always beat mtime dates (mtime = when the file was
copied, not when the fact was true). On a date tie, the project's own file wins.

LLM output is validated here: the schema constrains shape, code enforces meaning.
"""

import json
import re
from pathlib import Path

from jarvis.router.config import get_config

STRONG_DATE_SOURCES = {"filename", "header"}
TEXT_FIELDS = (
    "description",
    "status_evidence",
    "status_reason",
    "next_step",
    "key_metric",
)
STATUS_WORDS = {"active", "paused", "done", "abandoned", "planned", "unclear"}
EMPTY_VALUES = {
    "",
    "n/a",
    "na",
    "none",
    "null",
    "not stated",
    "not mentioned",
    "unknown",
    "-",
}
MAX_TECH = 8


def clean_value(value):
    """Strip stray braces/quotes; treat 'N/A'-style placeholders as empty."""
    value = value.strip().strip("{}\"'").strip()
    return "" if value.lower() in EMPTY_VALUES else value


def clean_mention(m):
    """Code-side validation of one LLM mention. Returns a cleaned copy (input untouched)."""
    m = {**m, **{f: clean_value(m[f]) for f in TEXT_FIELDS}}
    if m["status_reason"].lower().rstrip(".") in STATUS_WORDS:
        m["status_reason"] = ""  # 'DONE' is the status, not a reason
    if not re.search(r"\d", m["key_metric"]):
        m["key_metric"] = ""  # no number -> it's a feature, not a metric
    tech = [clean_value(t) for t in m["tech"]]
    m["tech"] = list({t.lower(): t for t in tech if t}.values())[:MAX_TECH]
    return m


def display_name(name):
    """'NoteFlow — AI-Powered Note Intelligence' -> 'NoteFlow'."""
    return re.split(r"\s[—–-]\s|:|\(", name)[0].strip()


def normalize_name(name):
    """'PixelNet', 'Pixel Net', 'DataLens — CSV Tool', 'pixelnet project' -> 'pixelnet'."""
    name = re.sub(r"\bproject\b", " ", display_name(name).lower())
    return re.sub(r"[^a-z0-9]", "", name)


def _recency_key(mention, project_key):
    """Sort key, best last: (strong date?, date, is this the project's own file?)."""
    strong = mention["date_source"] in STRONG_DATE_SOURCES
    own_file = project_key in re.sub(r"[^a-z0-9]", "", mention["source"].lower())
    return (strong, mention["version_date"], own_file)


def _best_with(group, field, status=None):
    """Best-ranked mention that has a non-empty `field` (optionally with a given status)."""
    for m in reversed(group):
        if m[field] and (status is None or m["status"] == status):
            return m
    return None


def merge_mentions(mentions):
    by_key = {}
    for raw in mentions:
        m = clean_mention(raw)
        key = normalize_name(m["name"])
        if key:
            by_key.setdefault(key, []).append(m)

    registry = {}
    for key, group in by_key.items():
        group.sort(
            key=lambda m: _recency_key(m, key)
        )  # weakest/oldest first, best last

        stated = [m for m in group if m["status"] != "unclear"]
        current = (
            stated[-1] if stated else group[-1]
        )  # 'unclear' never overwrites a real status

        # reason/next_step must come from a mention with the SAME status as current
        reason_m = _best_with(group, "status_reason", current["status"])
        step_m = _best_with(group, "next_step", current["status"])
        metric_m = _best_with(group, "key_metric")
        desc_m = _best_with(group, "description")

        tech = list({t.lower(): t for m in group for t in m["tech"]}.values())

        registry[key] = {
            "name": display_name(current["name"]),
            "description": desc_m["description"] if desc_m else "",
            "status": current["status"],
            "status_evidence": current["status_evidence"],
            "status_reason": reason_m["status_reason"] if reason_m else "",
            "status_reason_source": reason_m["source"] if reason_m else "",
            "next_step": step_m["next_step"] if step_m else "",
            "as_of": current["version_date"],
            "source": current["source"],
            "key_metric": metric_m["key_metric"] if metric_m else "",
            "key_metric_source": metric_m["source"] if metric_m else "",
            "tech": tech,
            "history": [
                {
                    "version_date": m["version_date"],
                    "date_source": m["date_source"],
                    "status": m["status"],
                    "key_metric": m["key_metric"],
                    "source": m["source"],
                }
                for m in sorted(group, key=lambda m: m["version_date"])
            ],
        }
    return dict(sorted(registry.items()))


def registry_file():
    return get_config().registry_path / "registry.json"


def save_registry(registry, path=None):
    path = Path(path) if path else registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_registry(path=None):
    path = Path(path) if path else registry_file()
    return json.loads(path.read_text(encoding="utf-8"))
