import os
from pathlib import Path

# Only these file types count as notes. Everything else (images, PDFs, zips...)
# is skipped. Allowlist, not blocklist: we can name what a note IS,
# but we can never list every kind of file that ISN'T one.
NOTE_EXTENSIONS = {".md", ".markdown", ".txt"}

# A folder with exactly this name (inside the vault) is ignored, with everything under it.
SKIP_FOLDER = "skip"


def is_note_file(file_name: str) -> bool:
    return Path(file_name).suffix.lower() in NOTE_EXTENSIONS


def read_text_file(full_path: str) -> str | None:
    """Return the file's text, or None if it isn't valid UTF-8.

    utf-8-sig = UTF-8 that also drops the invisible BOM some Windows editors
    put at the start of a file (otherwise the first '# Header' wouldn't start with '#').
    """
    try:
        with open(full_path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except UnicodeDecodeError:
        return None


def load_vault(directory_path, verbose: bool = True) -> dict:
    """Read every note in the vault -> {relative_path: text}.

    Files that aren't notes, or aren't readable as UTF-8, are skipped
    (one bad file must never crash the whole ingest) and listed at the end
    so the user can see exactly what was left out.
    """
    file_dict = {}
    skipped = []  # list of (relative_path, reason)

    for directory, sub_folders, files in os.walk(directory_path):
        # Compare folder NAMES inside the vault, not the whole absolute path string.
        relative_dir = os.path.relpath(directory, directory_path)
        if SKIP_FOLDER in Path(relative_dir).parts:
            continue

        for file in files:
            full_path = os.path.join(directory, file)
            relative_path = os.path.relpath(full_path, directory_path)

            if not is_note_file(file):
                skipped.append((relative_path, "not a note file type"))
                continue

            content = read_text_file(full_path)
            if content is None:
                skipped.append((relative_path, "not valid UTF-8 text"))
                continue

            file_dict[relative_path] = content

    if verbose and skipped:
        print(f"Skipped {len(skipped)} file(s):")
        for path, reason in skipped:
            print(f"  - {path}  ({reason})")

    return file_dict