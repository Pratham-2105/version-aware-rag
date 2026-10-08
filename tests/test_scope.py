import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import yaml

from jarvis.ingest.grouping import apply_unversioned
from jarvis.ingest.metadata import top_folder
from jarvis.retrieval.bm25 import BM25Index
from jarvis.retrieval.filters import combine_where, folder_filter, matches
from jarvis.router.config import config_from_dict, load_config
from jarvis.workspace import discover_folders, render_config

RAW = {
    "paths": {"notes": "n", "index": "i", "collection": "c"},
    "folders": {
        "projects": {"privacy": "shareable"},
        "handovers": {"privacy": "shareable"},
        "personal": {"privacy": "private", "versioned": False},
    },
    "domains": {
        "projects": {"description": "projects", "folders": ["projects", "handovers"]},
        "personal": {"description": "feelings", "folders": ["personal"]},
    },
}


def make(raw=None):
    return config_from_dict(raw or RAW)


def test_folders_for_unions_and_sorts():
    assert make().folders_for(["projects", "personal"]) == [
        "handovers",
        "personal",
        "projects",
    ]


def test_unlisted_folder_is_private():
    cfg = make()
    assert cfg.is_private_folder("brand_new_folder")
    assert not cfg.is_private_folder("projects")


def test_domain_privacy_comes_from_folders():
    cfg = make()
    assert cfg.is_private_domain("personal")
    assert not cfg.is_private_domain("projects")
    assert cfg.is_private_domain("no_such_domain")


def test_unversioned_folders():
    assert make().unversioned_folders == {"personal"}


def test_typo_in_domain_folder_is_rejected():
    raw = copy.deepcopy(RAW)
    raw["domains"]["projects"]["folders"] = ["projectz"]
    with pytest.raises(ValueError):
        config_from_dict(raw)


def test_bad_privacy_value_is_rejected():
    raw = copy.deepcopy(RAW)
    raw["folders"]["projects"]["privacy"] = "public"
    with pytest.raises(ValueError):
        config_from_dict(raw)


def test_real_config_is_valid():
    cfg = load_config(Path("config.yaml"))
    assert cfg.private_domains
    assert all(cfg.domains[d].description for d in cfg.domains)


def test_combine_where():
    assert combine_where(None, None) is None
    assert combine_where({"is_latest": True}, None) == {"is_latest": True}
    assert combine_where({"is_latest": True}, {"folder": {"$in": ["dsa"]}}) == {
        "$and": [{"is_latest": True}, {"folder": {"$in": ["dsa"]}}]
    }


def test_matches_chroma_operators():
    meta = {"folder": "dsa", "is_latest": True}
    assert matches(meta, {"is_latest": True})
    assert matches(meta, {"folder": {"$in": ["dsa", "college"]}})
    assert not matches(meta, {"folder": {"$nin": ["dsa"]}})
    assert matches(meta, {"$and": [{"is_latest": True}, {"folder": {"$eq": "dsa"}}]})
    assert not matches(meta, {"$and": [{"is_latest": False}, {"folder": "dsa"}]})


def test_folder_filter():
    assert folder_filter(None) is None
    assert folder_filter(["b", "a"]) == {"folder": {"$in": ["a", "b"]}}
    with pytest.raises(ValueError):
        folder_filter([])


def test_bm25_accepts_chroma_style_filters():
    index = BM25Index(
        ids=["old", "new", "diary"],
        documents=["cf rating 1510", "cf rating 1550", "cf rating made me sad"],
        metadatas=[
            {"folder": "dsa", "is_latest": False},
            {"folder": "dsa", "is_latest": True},
            {"folder": "personal", "is_latest": True},
        ],
    )
    where = combine_where({"is_latest": True}, folder_filter(["dsa", "handovers"]))
    assert [i for i, _ in index.search("cf rating", where=where)] == ["new"]


def test_top_folder():
    assert top_folder("handovers\\arjun_master_handoff_oct2026.md") == "handovers"
    assert top_folder("a/b/c.md") == "a"
    assert top_folder("readme.md") == "."


def test_unversioned_entries_all_stay_latest():
    groups = {
        "personal\\chronicle_july2026.md": {
            "doc_group_id": "personal/chronicle",
            "group_size": 2,
            "version_rank": 2,
            "is_latest": False,
        },
        "personal\\chronicle_sep2026.md": {
            "doc_group_id": "personal/chronicle",
            "group_size": 2,
            "version_rank": 1,
            "is_latest": True,
        },
        "handovers\\h_oct.md": {
            "doc_group_id": "handovers/h",
            "group_size": 2,
            "version_rank": 1,
            "is_latest": True,
        },
    }
    out = apply_unversioned(groups, {"personal"})
    july, sep = (
        out["personal\\chronicle_july2026.md"],
        out["personal\\chronicle_sep2026.md"],
    )
    assert july["is_latest"] and sep["is_latest"]
    assert july["doc_group_id"] != sep["doc_group_id"]
    assert out["handovers\\h_oct.md"] == groups["handovers\\h_oct.md"]


def test_relative_paths_resolve_against_config_folder(tmp_path):
    raw = copy.deepcopy(RAW)
    raw["paths"]["index"] = str(tmp_path / "elsewhere")  # absolute stays absolute
    cfg = config_from_dict(raw, base_dir=tmp_path)
    assert cfg.notes_path == tmp_path / "n"
    assert cfg.index_path == tmp_path / "elsewhere"


def test_registry_folder_typo_is_rejected():
    raw = copy.deepcopy(RAW)
    raw["registry"] = {"folders": ["project"]}
    with pytest.raises(ValueError):
        config_from_dict(raw)


def test_init_writes_a_valid_all_private_config(tmp_path):
    notes = tmp_path / "notes"
    for name in ("work", "diary", "skip_this", ".git"):
        (notes / name).mkdir(parents=True)
    (notes / "readme.md").write_text("x", encoding="utf-8")

    folders = discover_folders(notes)
    assert folders == [".", "diary", "work"]

    cfg = config_from_dict(
        yaml.safe_load(render_config(notes, folders)), base_dir=tmp_path
    )
    assert cfg.notes_path == notes.resolve()
    assert all(cfg.is_private_folder(f) for f in folders)
    assert cfg.index_path == tmp_path / ".jarvis" / "index"
