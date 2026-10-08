import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.retrieval.bm25 import BM25Index, tokenize
from jarvis.retrieval.hybrid import reciprocal_rank_fusion


def test_tokenize_splits_filenames_and_keeps_numbers():
    assert tokenize("handovers\\arjun_master_handoff_oct2026.md rating 1550") == [
        "handovers", "arjun", "master", "handoff", "oct2026", "md", "rating", "1550"
    ]


def test_rrf_rewards_agreement():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["c", "a", "d"]])
    assert fused == ["a", "c", "b", "d"]


def test_bm25_finds_rare_keyword():
    index = BM25Index(
        ids=["x", "y", "z"],
        documents=["pixelnet reached 91.3 percent", "studybuddy was abandoned", "notes on graphs"],
        metadatas=[{"source": "p.md"}, {"source": "s.md"}, {"source": "g.md"}],
    )
    assert index.search("what accuracy did PixelNet reach")[0][0] == "x"


def test_bm25_where_filter():
    index = BM25Index(
        ids=["old", "new"],
        documents=["cf rating 1510", "cf rating 1550"],
        metadatas=[{"is_latest": False}, {"is_latest": True}],
    )
    ids = [i for i, _ in index.search("cf rating", where={"is_latest": True})]
    assert ids == ["new"]