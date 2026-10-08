import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.ingest.dedup import content_hash, deduplicate, find_exact_duplicates
from jarvis.ingest.loaders import load_vault
from jarvis.ingest.metadata import resolve_version_date

BASE_WORDS = " ".join(f"word{i}" for i in range(100))


def test_hash_ignores_whitespace_and_line_endings():
    assert content_hash("Hello  World\r\nok") == content_hash("hello world\nok")


def test_exact_duplicate_keeps_unmarked_copy():
    files = {"a.md": "same text", "a (1).md": "same  text"}
    assert find_exact_duplicates(files) == {"a (1).md": "a.md"}


def test_near_duplicate_same_date_dropped():
    files = {"plan.md": BASE_WORDS, "plan_backup.md": BASE_WORDS.replace("word50", "changed")}
    dates = {"plan.md": "2026-10-01", "plan_backup.md": "2026-10-01"}
    kept, report = deduplicate(files, dates)
    assert set(kept) == {"plan.md"}
    assert report["near"] == {"plan_backup.md": "plan.md"}


def test_near_identical_different_dates_both_kept():
    # newer version with one changed fact must NEVER be dropped
    files = {"h_sep.md": BASE_WORDS, "h_oct.md": BASE_WORDS.replace("word50", "1550")}
    dates = {"h_sep.md": "2026-09-01", "h_oct.md": "2026-10-01"}
    kept, _ = deduplicate(files, dates)
    assert set(kept) == {"h_sep.md", "h_oct.md"}


def test_real_sample_vault():
    vault = Path("data/sample-vault")
    files = load_vault(vault)
    dates = {p: resolve_version_date(p, t, vault)[0] for p, t in files.items()}
    kept, report = deduplicate(files, dates)

    dropped = {p.replace("\\", "/") for p in list(report["exact"]) + list(report["near"])}
    print("\nsimilarity scores:", report["similarity_scores"])

    assert dropped == {
        "handovers/arjun_master_handoff_aug2026 (1).md",
        "career/career_plan_oct2026_backup.md",
    }
    assert len(kept) == len(files) - 2