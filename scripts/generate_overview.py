import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.registry.store import load_registry

OUTPUT_PATH = Path("docs/sample_vault_overview.md")
STATUS_ORDER = ["active", "planned", "paused", "done", "abandoned", "unclear"]


def cell(text):
    """Make text safe inside a markdown table cell."""
    return (text or "—").replace("|", "\\|").replace("\n", " ")


def build_overview(registry):
    rows = sorted(registry.values(), key=lambda r: (STATUS_ORDER.index(r["status"]), r["name"].lower()))
    lines = [
        "# Project overview",
        "",
        "_Generated from the structured registry by `scripts/generate_overview.py`. "
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


if __name__ == "__main__":
    text = build_overview(load_registry())
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(text, encoding="utf-8")
    print(text)