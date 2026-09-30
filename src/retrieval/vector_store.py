import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import chromadb
from chromadb.utils.embedding_functions.ollama_embedding_function import (
    OllamaEmbeddingFunction,
)

from src.ingest.pipeline import run_ingestion


def build_vectorstore(chunks: list, store_path: str, collection_name: str):
    """Takes chunk dicts, embeds and stores them in a persistent Chroma collection."""

    client = chromadb.PersistentClient(path=store_path)

    embedding_function = OllamaEmbeddingFunction(
        url="http://localhost:11434",
        model_name="nomic-embed-text",
    )

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_function,
    )

    # Unpack chunks into the three parallel lists Chroma expects
    documents = []
    metadatas = []
    ids = []

    for i, chunk in enumerate(chunks):
        documents.append(chunk["content"])
        metadatas.append({
            "source": chunk["source"],
            "header_path": chunk["header_path"],
        })
        ids.append(f"{chunk['source']}::chunk_{i}")

    collection.add(documents=documents, metadatas=metadatas, ids=ids)

    return collection


def query_vectorstore(collection, query: str, top_k: int = 5):
    """Queries the collection and returns top-k results."""

    results = collection.query(query_texts=[query], n_results=top_k)

    return results


if __name__ == "__main__":
    vault_path = Path("././data/sample-vault/")
    store_path = "././data/chroma-store/"

    chunks = run_ingestion(vault_path)
    print(f"Loaded {len(chunks)} chunks")

    collection = build_vectorstore(chunks, store_path, "sample_collection")
    print(f"Stored {collection.count()} documents in Chroma")

    # Test query
    results = query_vectorstore(collection, "What accuracy did PixelNet reach on MNIST?")
    results = query_vectorstore(collection, "What is Arjun's current Codeforces rating?")

    for i in range(len(results["documents"][0])):
        print(f"\n--- Result {i+1} ---")
        print(f"Source: {results['metadatas'][0][i]['source']}")
        print(f"Header: {results['metadatas'][0][i]['header_path']}")
        print(f"Content: {results['documents'][0][i][:200]}")
        print(f"Distance: {results['distances'][0][i]:.4f}")