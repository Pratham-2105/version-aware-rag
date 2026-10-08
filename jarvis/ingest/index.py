"""`jarvis ingest`: rebuild the search index from the notes folder in config.yaml."""
from jarvis.ingest.pipeline import run_ingestion
from jarvis.retrieval.vector_store import build_vectorstore
from jarvis.router.config import get_config


def build_index(cfg=None):
    cfg = cfg or get_config()
    print(f"Notes: {cfg.notes_path}  ->  index: {cfg.index_path} [{cfg.collection}]")
    if cfg.unversioned_folders:
        print(f"Unversioned folders (entries, not versions): {sorted(cfg.unversioned_folders)}")

    chunks = run_ingestion(cfg.notes_path, unversioned_folders=cfg.unversioned_folders)

    unlisted = sorted({c["folder"] for c in chunks} - set(cfg.folders))
    if unlisted:
        print(f"WARNING: folders not in config.yaml, treated as PRIVATE: {unlisted}")

    build_vectorstore(chunks, cfg.index_path, cfg.collection, rebuild=True)
    print(f"Indexed {len(chunks)} chunks.")
    return len(chunks)