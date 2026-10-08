"""Rebuild the index from scratch:  python -u scripts/ingest.py
Paths and per-folder settings come from config.yaml."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingest.pipeline import run_ingestion
from src.retrieval.vector_store import build_vectorstore
from src.router.config import load_config


def main():
    cfg = load_config()
    print(f"Notes: {cfg.notes_path}  ->  index: {cfg.index_path} [{cfg.collection}]")
    if cfg.unversioned_folders:
        print(f"Unversioned folders (entries, not versions): {sorted(cfg.unversioned_folders)}")

    chunks = run_ingestion(cfg.notes_path, unversioned_folders=cfg.unversioned_folders)

    unlisted = sorted({c["folder"] for c in chunks} - set(cfg.folders))
    if unlisted:
        print(f"WARNING: folders not in config.yaml, treated as PRIVATE: {unlisted}")

    build_vectorstore(chunks, cfg.index_path, cfg.collection, rebuild=True)
    print(f"Indexed {len(chunks)} chunks.")


if __name__ == "__main__":
    main()