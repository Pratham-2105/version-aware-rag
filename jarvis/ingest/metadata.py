"""Resolve a version date for each file in the vault.

Priority (most trustworthy first):
  1. date in the filename      e.g. arjun_master_handoff_aug2026.md
  2. date in the document head e.g. "Date: 21 August 2026"
  3. filesystem modified time  (weak: copying a file resets it)

Dates are ISO strings "YYYY-MM-DD" so they compare correctly as plain strings
and can be stored directly in Chroma metadata (which rejects datetime/None).
"""

import re
from datetime import datetime
from pathlib import Path

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

# Only real month spellings, so "decision" is never read as December.
MONTH = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)

# (?<![a-z]) = no letter right before the month, so "arjun" never matches "jun".
FILENAME_DATE = re.compile(r"(?<![a-z])" + MONTH + r"[_\- ]?(\d{4})")
HEADER_DATE = re.compile(r"(?<![a-z0-9])(?:(\d{1,2})\s+)?" + MONTH + r"\.?,?\s+(\d{4})")
HEADER_DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

HEADER_SCAN_CHARS = 500  # only look at the top of the document


def _iso(year, month, day=1):
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def date_from_filename(relative_path):
    stem = Path(relative_path).stem.lower()
    match = FILENAME_DATE.search(stem)
    if not match:
        return None
    month_name, year = match.groups()
    return _iso(year, MONTHS[month_name[:3]])


def date_from_header(text):
    head = text[:HEADER_SCAN_CHARS].lower()

    match = HEADER_DATE_ISO.search(head)
    if match:
        return _iso(*match.groups())

    match = HEADER_DATE.search(head)
    if match:
        day, month_name, year = match.groups()
        day = int(day) if day and 1 <= int(day) <= 31 else 1
        return _iso(year, MONTHS[month_name[:3]], day)

    return None


def date_from_mtime(full_path):
    timestamp = Path(full_path).stat().st_mtime
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")


def resolve_version_date(relative_path, text, vault_path):
    """Return (iso_date, date_source) where date_source is
    'filename', 'header', or 'mtime'."""
    date = date_from_filename(relative_path)
    if date:
        return date, "filename"

    date = date_from_header(text)
    if date:
        return date, "header"

    return date_from_mtime(Path(vault_path) / relative_path), "mtime"


ROOT_FOLDER = "."


def top_folder(relative_path):
    """'handovers\\x.md' -> 'handovers'; 'a/b/c.md' -> 'a'; 'x.md' -> '.' (vault root)."""
    parts = str(relative_path).replace("\\", "/").split("/")
    return parts[0] if len(parts) > 1 else ROOT_FOLDER
