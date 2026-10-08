"""`jarvis init <notes folder>`: write a starter config.yaml for someone's own notes.

Fails closed: every folder starts PRIVATE, so nothing reaches an MCP host or a hosted
model until the user marks a folder shareable. Folders the loader skips ('skip' in the
name) and hidden folders are left out. Files directly in the notes folder become the
'.' folder.
"""
import json
from pathlib import Path


def discover_folders(notes):
    notes = Path(notes)
    found = set()
    for entry in notes.iterdir():
        if entry.name.startswith("."):
            continue
        if entry.is_dir() and "skip" not in entry.name:
            found.add(entry.name)
        elif entry.is_file():
            found.add(".")
    return sorted(found)


def render_config(notes, folders):
    folder_lines = "\n".join(
        f"  {json.dumps(f)}: {{privacy: private, versioned: true}}" for f in folders
    ) or "  {}"
    return f"""# Jarvis configuration, written by `jarvis init`. Edit freely.
# Relative paths below are relative to this file.

paths:
  notes: {json.dumps(str(Path(notes).resolve()))}
  index: .jarvis/index
  collection: notes
  registry: .jarvis/registry
  overview: .jarvis/overview.md

# Every top-level folder of your notes ("." = files directly in the notes folder).
# privacy:   private (default) = never leaves this machine: local model only, never returned over MCP
#            shareable         = may be returned to an MCP host or sent to a hosted model
# versioned: true  = files with the same name apart from a date or v1/v2 are versions of ONE document
#            false = separate entries (diaries, logs): none is ever hidden as "older"
folders:
{folder_lines}

default_folder_privacy: private

# Life areas the router chooses between; the description is the router's prompt.
# Splitting this into areas (projects / career / personal ...) gives better routing and tone.
domains:
  notes:
    description: Everything in the notes folder.
    folders: {json.dumps(folders)}

# Folders whose files describe projects (status, results). Empty = no project registry.
registry:
  folders: []

router:
  scope_retrieval: false
  history_turns: 2

memory:
  turns: 4

models:
  local:
    model: qwen2.5:7b
    host: http://127.0.0.1:11434
    temperature: 0
    seed: 42
  hosted:
    enabled: false
"""


def init_workspace(notes, target=Path("config.yaml"), force=False):
    notes = Path(notes).expanduser()
    if not notes.is_dir():
        raise SystemExit(f"Not a folder: {notes}")
    target = Path(target)
    if target.exists() and not force:
        raise SystemExit(f"{target} already exists (use --force to overwrite).")
    folders = discover_folders(notes)
    target.write_text(render_config(notes, folders), encoding="utf-8")
    return target, folders