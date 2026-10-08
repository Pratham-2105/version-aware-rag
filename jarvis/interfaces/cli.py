"""Jarvis CLI.

    python -u src/interfaces/cli.py            V1 pipeline (fixed retrieve -> answer; what eval measures)
    python -u src/interfaces/cli.py --agent    Stage 6 agent (model chooses tools)

Importing this file has no side effects (no ingestion, no index build), so
run_eval.py can import answer_question cheaply. Build the index with scripts/ingest.py.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ollama import Client

from jarvis.retrieval.search import format_context, retrieve
from jarvis.retrieval.vector_store import open_vectorstore

STORE_PATH = Path("data/chroma-store/")
COLLECTION_NAME = "sample_collection"
LLM_MODEL = "qwen2.5:7b"
LLM_OPTIONS = {"temperature": 0, "seed": 42}

ollama_client = Client(host="http://127.0.0.1:11434")

SYSTEM_PROMPT = (
    "You are a knowledge assistant that answers questions based ONLY on the provided sources. "
    "Rules:\n"
    "1. Only use information from the SOURCES below to answer.\n"
    "2. Cite the source file for every claim (e.g. 'According to [Source 1]...').\n"
    "3. If the sources don't contain the answer, say 'I don't have that information in my sources.'\n"
    "4. Never make up information that isn't in the sources.\n\n"
    "Each source shows its date and whether it is the latest version of its document. If sources give different values for the same fact, use the most recent one when asked about the current state, and describe the change in date order when asked how something changed."
)


def answer_question(collection, question: str):
    """V1 pipeline: retrieve (Stage 4) -> stuff context -> one LLM call."""
    results = retrieve(collection, question)
    context = format_context(results)

    prompt_with_context = SYSTEM_PROMPT + "SOURCES:\n" + context

    response = ollama_client.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": prompt_with_context},
            {"role": "user", "content": question},
        ],
        options=LLM_OPTIONS,
    )

    return response["message"]["content"], results["metadatas"][0]


def chat_loop(handle):
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit", "break"):
            break
        if user_input:
            handle(user_input)


def run_pipeline_chat():
    collection = open_vectorstore(STORE_PATH, COLLECTION_NAME)

    def handle(question):
        answer, metas = answer_question(collection, question)
        sources = sorted({m["source"].replace("\\", "/") for m in metas})
        print(f"\nJarvis: {answer}\n  sources: {', '.join(sources)}\n")

    chat_loop(handle)


def run_agent_chat():
    from jarvis.agent.agent import ask, build_agent, model_label

    agent = build_agent()
    print(f"(agent mode, model: {model_label()})\n")

    def handle(question):
        r = ask(agent, question)
        for call in r["tool_calls"]:
            args = ", ".join(f"{k}={v!r}" for k, v in call["args"].items())
            print(f"  [tool] {call['name']}({args})")
        print(f"\nJarvis: {r['answer']}\n  status: {r['status']}")
        if r["invented_citations"]:
            print(f"  invented citations: {', '.join(r['invented_citations'])}")
        if r["answer"] != r["draft"]:
            print(f"  (blocked draft: {r['draft'][:200]!r})")
        print()

    chat_loop(handle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jarvis CLI")
    parser.add_argument("--agent", action="store_true", help="use the Stage 6 tool-calling agent")
    args = parser.parse_args()

    print("Jarvis CLI — type 'exit' to quit\n")
    if args.agent:
        run_agent_chat()
    else:
        run_pipeline_chat()
