import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingest.grouping import family_key, group_documents
from src.ingest.pipeline import run_ingestion


def test_family_key_strips_date():
    assert (
        family_key("handovers\\arjun_master_handoff_aug2026.md")
        == "handovers/arjun_master_handoff"
    )


def test_family_key_strips_version_and_date():
    assert family_key("career/resume_v1_aug2026.md") == "career/resume"
    assert family_key("career/resume_v2_oct2026.md") == "career/resume"


def test_family_key_folder_separates():
    assert family_key("a/notes.md") != family_key("b/notes.md")


def test_ranking_newest_first():
    paths = ["h_jun2026.md", "h_oct2026.md", "h_aug2026.md"]
    dates = {
        "h_jun2026.md": "2026-06-01",
        "h_oct2026.md": "2026-10-01",
        "h_aug2026.md": "2026-08-01",
    }
    info = group_documents(paths, dates)
    assert info["h_oct2026.md"]["group_size"] == 3
    assert info["h_oct2026.md"]["version_rank"] == 1
    assert info["h_oct2026.md"]["is_latest"] is True
    assert info["h_jun2026.md"]["version_rank"] == 3
    assert info["h_jun2026.md"]["is_latest"] is False


def test_real_vault_families():
    chunks = run_ingestion("data/sample-vault", verbose=False)
    by_file = {c["source"].replace("\\", "/"): c for c in chunks}

    handoff = by_file["handovers/arjun_master_handoff_oct2026.md"]
    assert handoff["group_size"] == 4
    assert handoff["is_latest"] is True
    assert by_file["handovers/arjun_master_handoff_aug2026.md"]["is_latest"] is False

    assert by_file["career/resume_v2_oct2026.md"]["group_size"] == 2
    assert by_file["career/career_plan_oct2026.md"]["group_size"] == 2
    assert by_file["dsa/contest_log.md"]["group_size"] == 1
    assert "handovers/arjun_master_handoff_aug2026 (1).md" not in by_file
