"""One-page project overview, generated from the registry. Written by `jarvis registry`."""
from jarvis.registry.store import load_registry
from jarvis.router.config import get_config

STATUS_ORDER = ["active", "planned", "paused", "done", "abandoned", "unclear"]


def cell(text):
    """Make text safe inside a markdown table cell."""
    return (text or "—").replace("|", "\\|").replace("\n", " ")


def build_overview(registry):
    rows = sorted(registry.values(), key=lambda r: (STATUS_ORDER.index(r["status"]), r["name"].lower()))
    lines = [
        "# Project overview",
        "",
        "_Generated from the structured registry by `jarvis registry`. "
        "Every row cites the document and date its status came from._",
        "",
        "| Project | Status | As of | Key metric | Why | Next step | Source |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        source = r["source"].replace("\\", "/")
        lines.append(
            f"| {cell(r['name'])} | {r['status']} | {r['as_of']} | {cell(r['key_metric'])} | "
            f"{cell(r['status_reason'])} | {cell(r['next_step'])} | {source} |"
        )

    lines += ["", "## Status changes", ""]
    for r in rows:
        changes, prev = [], None
        for h in r["history"]:
            if h["status"] != "unclear" and h["status"] != prev:
                changes.append(f"{h['status']} ({h['version_date']})")
                prev = h["status"]
        lines.append(f"- **{r['name']}**: " + " → ".join(changes))
    return "\n".join(lines) + "\n"


def write_overview():
    """Write the overview to the path in config.yaml (paths: overview:)."""
    path = get_config().overview_path
    text = build_overview(load_registry())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path, text


if __name__ == "__main__":
    _, text = write_overview()
    print(text)