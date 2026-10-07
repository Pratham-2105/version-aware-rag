"""Rebuild the vector store from the vault: python -u scripts/ingest.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingest.pipeline import run_ingestion
from src.retrieval.vector_store import build_vectorstore

VAULT = Path("data/sample-vault")
STORE = Path("data/chroma-store")
COLLECTION = "sample_collection"

if __name__ == "__main__":
    chunks = run_ingestion(VAULT)
    collection = build_vectorstore(chunks, STORE, COLLECTION, rebuild=True)
    print(f"Indexed {collection.count()} chunks into '{COLLECTION}'")