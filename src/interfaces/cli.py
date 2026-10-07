import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ollama import Client

from src.ingest.pipeline import run_ingestion
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.vector_store import build_vectorstore, query_vectorstore

RETRIEVAL_MODE = "hybrid"

_retrievers = {}


def get_retriever(collection):
    """Build the BM25 index once per collection, then reuse it."""
    if collection.name not in _retrievers:
        _retrievers[collection.name] = HybridRetriever(collection)
    return _retrievers[collection.name]


def retrieve(collection, question, top_k=5):
    return get_retriever(collection).search(question, top_k=top_k, mode=RETRIEVAL_MODE)


vault_path = Path("././data/sample-vault/")
store_path = Path("././data/chroma-store/")

chunks = run_ingestion(vault_path)
collection = build_vectorstore(chunks, store_path, "sample_collection")

ollama_client = Client(host="http://127.0.0.1:11434")


def format_context(results):
    """Format retrieved chunks into a numbered context string with sources."""
    context_parts = []

    for i, (doc, meta) in enumerate(
        zip(results["documents"][0], results["metadatas"][0])
    ):
        context_parts.append(
            f"[Source {i + 1}] {meta['source']} > {meta['header_path']}\n{doc}"
        )

    return "\n\n".join(context_parts)


SYSTEM_PROMPT = (
    "You are a knowledge assistant that answers questions based ONLY on the provided sources. "
    "Rules:\n"
    "1. Only use information from the SOURCES below to answer.\n"
    "2. Cite the source file for every claim (e.g. 'According to [Source 1]...').\n"
    "3. If the sources don't contain the answer, say 'I don't have that information in my sources.'\n"
    "4. Never make up information that isn't in the sources.\n\n"
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
