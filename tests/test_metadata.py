import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingest.metadata import date_from_filename, date_from_header, resolve_version_date


def test_filename_month_year():
    assert date_from_filename("handovers/arjun_master_handoff_aug2026.md") == "2026-08-01"


def test_filename_not_fooled_by_name_containing_month():
    # "arjun" contains "jun" - must still read the real date, June
    assert date_from_filename("handovers/arjun_master_handoff_jun2026.md") == "2026-06-01"


def test_filename_full_month_name():
    assert date_from_filename("personal/chronicle_july2026.md") == "2026-07-01"


def test_filename_backup_suffix_still_dated():
    assert date_from_filename("career/career_plan_oct2026_backup.md") == "2026-10-01"


def test_filename_without_date():
    assert date_from_filename("dsa/contest_log.md") is None
    assert date_from_filename("notes/decision_2026.md") is None  # not December


def test_header_day_month_year():
    assert date_from_header("# Notes\nDate: 21 August 2026\n...") == "2026-08-21"


def test_header_iso():
    assert date_from_header("# Log\nUpdated 2026-09-14\n") == "2026-09-14"


def test_priority_filename_over_header(tmp_path):
    date, source = resolve_version_date("plan_oct2026.md", "Date: 3 June 2026", tmp_path)
    assert (date, source) == ("2026-10-01", "filename")


def test_mtime_fallback(tmp_path):
    (tmp_path / "notes.md").write_text("no date anywhere", encoding="utf-8")
    date, source = resolve_version_date("notes.md", "no date anywhere", tmp_path)
    assert source == "mtime"
    assert len(date) == 10