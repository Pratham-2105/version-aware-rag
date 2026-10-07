import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chromadb
from chromadb.utils.embedding_functions.ollama_embedding_function import (
    OllamaEmbeddingFunction,
)

from src.interfaces.cli import answer_question

# "pipeline" = V1 fixed pipeline (cli.answer_question), the Stages 0-4 rows.
# "agent"    = Stage 6 agent (model picks tools and the time mode itself).
ANSWER_MODE = "pipeline"
STAGE_NAME = "stage6_agent_final_qwen_c"
LLM_MODEL = "qwen2.5:7b"   # pipeline mode only; agent mode reads the model from .env
EMBED_MODEL = "nomic-embed-text"
RESULTS_DIR = Path("eval/results")

REGISTRY_TOOLS = {"get_project_status", "list_projects"}


def route_ok(category, tool_calls):
    """Did the agent take a version-correct route on a time-sensitive question?

    current_state -> search_notes(mode="current") or a registry tool (registry = latest status)
    historical    -> search_notes(mode="history") or get_project_status (it carries status history)
    Other categories are not scored (returns None).
    """
    if category == "current_state_temporal":
        return any(
            (c["name"] == "search_notes" and c["args"].get("mode") == "current")
            or c["name"] in REGISTRY_TOOLS
            for c in tool_calls
        )
    if category == "historical_change":
        return any(
            (c["name"] == "search_notes" and c["args"].get("mode") == "history")
            or c["name"] == "get_project_status"
            for c in tool_calls
        )
    return None


# Load golden questions
with open("eval/golden_questions.json", "r", encoding="utf-8") as file:
    data = json.load(file)

if ANSWER_MODE == "agent":
    from src.agent.agent import ask, build_agent, model_label

    agent = build_agent()
    LLM_MODEL = model_label()
else:
    # Open the existing collection (no re-ingestion)
    client = chromadb.PersistentClient(path="data/chroma-store")
    embedding_function = OllamaEmbeddingFunction(
        url="http://localhost:11434",
        model_name=EMBED_MODEL,
    )
    collection = client.get_collection(
        name="sample_collection",
        embedding_function=embedding_function,
    )

results = []          # one record per question
category_stats = {}   # category -> counts

for item in data:
    qid = item["id"]
    category = item["category"]
    expected_sources = item["expected_sources"]
    key_facts = item["key_facts"]

    print(f"[{qid}/{len(data)}] {item['question']}")

    agent_trace = None
    if ANSWER_MODE == "agent":
        agent_trace = ask(agent, item["question"])
        actual_answer = agent_trace["answer"]
        actual_paths = agent_trace["retrieved_sources"]
    else:
        actual_answer, actual_sources = answer_question(collection, item["question"])
        actual_paths = [s["source"].replace("\\", "/") for s in actual_sources]

    # Source hit: any expected file among the retrieved sources.
    # Refusal questions have no valid source, so they are not scored on this.
    scored_for_source = category != "should_refuse"
    source_hit = any(p in expected_sources for p in actual_paths) if scored_for_source else None

    # Answer correctness: every key fact appears in the answer
    answer_lower = actual_answer.lower()
    answer_correct = all(fact in answer_lower for fact in key_facts)

    record = {
        "id": qid,
        "category": category,
        "question": item["question"],
        "expected_answer": item["expected_answer"],
        "key_facts": key_facts,
        "actual_answer": actual_answer,
        "expected_sources": expected_sources,
        "retrieved_sources": actual_paths,
        "source_hit": source_hit,
        "answer_correct": answer_correct,
    }
    if agent_trace is not None:
        record.update({
            "status": agent_trace["status"],
            "retried": agent_trace["retried"],
            "draft": agent_trace["draft"],
            "tool_calls": agent_trace["tool_calls"],
            "route_ok": route_ok(category, agent_trace["tool_calls"]),
            "invented_citations": agent_trace["invented_citations"],
        })
    results.append(record)

    stats = category_stats.setdefault(
        category, {"total": 0, "answer_correct": 0, "source_scored": 0, "source_hit": 0}
    )
    stats["total"] += 1
    stats["answer_correct"] += int(answer_correct)
    if scored_for_source:
        stats["source_scored"] += 1
        stats["source_hit"] += int(source_hit)


def pct(a, b):
    return round(100 * a / b, 1) if b else None


# Overall numbers
total = len(results)
total_correct = sum(r["answer_correct"] for r in results)
source_scored = [r for r in results if r["source_hit"] is not None]
total_source_hit = sum(r["source_hit"] for r in source_scored)
refusals = [r for r in results if r["category"] == "should_refuse"]
refusal_correct = sum(r["answer_correct"] for r in refusals)

summary = {
    "stage": STAGE_NAME,
    "answer_mode": ANSWER_MODE,
    "llm_model": LLM_MODEL,
    "embed_model": EMBED_MODEL,
    "top_k": 5,
    "run_at": datetime.now().isoformat(timespec="seconds"),
    "source_hit_rate": pct(total_source_hit, len(source_scored)),
    "answer_correctness": pct(total_correct, total),
    "refusal_accuracy": pct(refusal_correct, len(refusals)),
    "temporal_correctness": pct(
        category_stats.get("current_state_temporal", {}).get("answer_correct", 0),
        category_stats.get("current_state_temporal", {}).get("total", 0),
    ),
    "per_category": {
        cat: {
            "answer_correctness": pct(s["answer_correct"], s["total"]),
            "source_hit_rate": pct(s["source_hit"], s["source_scored"]),
            "n": s["total"],
        }
        for cat, s in category_stats.items()
    },
}

if ANSWER_MODE == "agent":
    routed = [r for r in results if r["route_ok"] is not None]
    summary["agent"] = {
        "route_correct": sum(r["route_ok"] for r in routed),
        "route_scored": len(routed),
        "route_misses": [r["id"] for r in routed if not r["route_ok"]],
        "status_counts": dict(Counter(r["status"] for r in results)),
        "tool_counts": dict(Counter(c["name"] for r in results for c in r["tool_calls"])),
        "retried_ids": {r["id"]: r["retried"] for r in results if r["retried"]},
        "blocked_ids": [r["id"] for r in results if r["status"] in ("no_tool", "uncited", "step_limit")],
        "invented_citation_ids": [r["id"] for r in results if r["invented_citations"]],
    }

# Print report
print("\n" + "=" * 60)
print(f"Stage: {STAGE_NAME} | mode: {ANSWER_MODE} | LLM: {LLM_MODEL} | Embeddings: {EMBED_MODEL}")
print("=" * 60)
print(f"Source hit rate:      {total_source_hit}/{len(source_scored)} = {summary['source_hit_rate']}%")
print(f"Answer correctness:   {total_correct}/{total} = {summary['answer_correctness']}%")
print(f"Refusal accuracy:     {refusal_correct}/{len(refusals)} = {summary['refusal_accuracy']}%")
print(f"Temporal correctness: {summary['temporal_correctness']}%")
print("\nPer category:")
for cat, s in summary["per_category"].items():
    src = f"{s['source_hit_rate']}%" if s["source_hit_rate"] is not None else "n/a"
    print(f"  {cat:<24} n={s['n']:<3} answer={s['answer_correctness']}%  source={src}")

failed = [r["id"] for r in results if not r["answer_correct"]]
print(f"\nFailed answer IDs: {failed}")

if ANSWER_MODE == "agent":
    a = summary["agent"]
    print("\nAgent:")
    print(f"  Time-sensitive routing: {a['route_correct']}/{a['route_scored']}  misses: {a['route_misses']}")
    print(f"  Status counts:          {a['status_counts']}")
    print(f"  Tool calls:             {a['tool_counts']}")
    print(f"  Retried:                {a['retried_ids']}")
    print(f"  Blocked by enforcement: {a['blocked_ids']}")
    print(f"  Invented citations:     {a['invented_citation_ids']}")

# Save everything
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
out_path = RESULTS_DIR / f"{STAGE_NAME}_{stamp}.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({"summary": summary, "results": results}, f, indent=2, ensure_ascii=False)

print(f"\nSaved to {out_path}")