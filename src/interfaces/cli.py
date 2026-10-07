import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ollama import Client

from src.ingest.pipeline import run_ingestion
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.vector_store import build_vectorstore, query_vectorstore
from src.retrieval.version_ranker import (
    expand_versions,
    order_for_context,
    version_filter,
)
from src.router.classifier import classify_intent

RETRIEVAL_MODE = "hybrid"

_retrievers = {}


def get_retriever(collection):
    """Build the BM25 index once per collection, then reuse it."""
    if collection.name not in _retrievers:
        _retrievers[collection.name] = HybridRetriever(collection)
    return _retrievers[collection.name]


def retrieve(collection, question, top_k=5):
    intent = classify_intent(question)
    retriever = get_retriever(collection)
    results = retriever.search(
        question, top_k=top_k, where=version_filter(intent), mode=RETRIEVAL_MODE
    )
    if intent == "historical":
        results = expand_versions(results, retriever.bm25, question)
    return order_for_context(results, intent)


vault_path = Path("././data/sample-vault/")
store_path = Path("././data/chroma-store/")

chunks = run_ingestion(vault_path)
collection = build_vectorstore(chunks, store_path, "sample_collection")

ollama_client = Client(host="http://127.0.0.1:11434")


def format_context(results):
    parts = []
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    for n, (doc, meta) in enumerate(zip(docs, metas), start=1):
        if meta.get("date_source") == "mtime":
            date_note = "undated"
        else:
            date_note = meta.get("version_date", "undated")
        if meta.get("group_size", 1) > 1:
            date_note += (
                ", latest version" if meta.get("is_latest") else ", older version"
            )
        parts.append(
            f"[Source {n}] {meta['source']} > {meta['header_path']} ({date_note})\n{doc}"
        )
    return "\n\n".join(parts)


SYSTEM_PROMPT = (
    "You are a knowledge assistant that answers questions based ONLY on the provided sources. "
    "Rules:\n"
    "1. Only use information from the SOURCES below to answer.\n"
    "2. Cite the source file for every claim (e.g. 'According to [Source 1]...').\n"
    "3. If the sources don't contain the answer, say 'I don't have that information in my sources.'\n"
    "4. Never make up information that isn't in the sources.\n\n"
    "Each source shows its date and whether it is the latest version of its document. If sources give different values for the same fact, use the most recent one when asked about the current state, and describe the change in date order when asked how something changed."
)


def answer_question(collection, question: str) -> str:

    results = retrieve(collection, question)
    context = format_context(results)

    prompt_with_context = SYSTEM_PROMPT + "SOURCES:\n" + context

    response = ollama_client.chat(
        model="qwen2.5:7b",
        messages=[
            {"role": "system", "content": prompt_with_context},
            {"role": "user", "content": question},
        ],
    )

    output_answer = response["message"]["content"]

    return output_answer, results["metadatas"][0]


if __name__ == "__main__":
    print("Jarvis CLI — type 'exit' to quit\n")

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ("exit", "quit", "break"):
            break

        if not user_input:
            continue

        results = query_vectorstore(collection, query=user_input)
        context = format_context(results)

        prompt_with_context = SYSTEM_PROMPT + "SOURCES:\n" + context

        response = ollama_client.chat(
            model="qwen2.5:7b",
            messages=[
                {"role": "system", "content": prompt_with_context},
                {"role": "user", "content": user_input},
            ],
            options={"temperature": 0},
        )

        print(f"\nJarvis: {response['message']['content']}\n")
