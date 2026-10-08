"""Chroma vector store: build (with optional rebuild) and query."""
import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

EMBED_MODEL = "nomic-embed-text"
OLLAMA_URL = "http://127.0.0.1:11434"


def get_embedding_function():
    return OllamaEmbeddingFunction(url=OLLAMA_URL, model_name=EMBED_MODEL)


def build_vectorstore(chunks, store_path, collection_name, rebuild=False):
    client = chromadb.PersistentClient(path=str(store_path))

    if rebuild:
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass  # collection didn't exist; error type differs across chromadb versions

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=get_embedding_function(),
    )

    if collection.count() == 0:
        collection.add(
            documents=[c["content"] for c in chunks],
            metadatas=[{k: v for k, v in c.items() if k != "content"} for c in chunks],
            ids=[f"{c['source']}::chunk_{i}" for i, c in enumerate(chunks)],
        )
    return collection


def open_vectorstore(store_path, collection_name):
    client = chromadb.PersistentClient(path=str(store_path))
    return client.get_collection(name=collection_name, embedding_function=get_embedding_function())


def query_vectorstore(collection, query, top_k=5, where=None):
    return collection.query(query_texts=[query], n_results=top_k, where=where)