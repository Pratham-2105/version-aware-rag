"""Stage 6 checkpoint — run 5 fixed questions through the agent and save the full trace.

    python -u scripts/agent_checkpoint.py

Run once with qwen (free), then once with a hosted model by switching .env.
Saves eval/results/agent_checkpoint_<model>_<timestamp>.json.
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.agent import ask, build_agent, model_label

RESULTS_DIR = Path("eval/results")

# (question, tool we expect it to use, what a correct answer contains)
CHECKPOINT = [
    ("Which projects are paused and why?", "list_projects", "QubitML + its reason"),
    ("What is Arjun's current Codeforces rating?", "search_notes mode=current", "1550"),
    ("How did Arjun's Codeforces rating change over time?", "search_notes mode=history", "1420 -> 1510 -> 1480 -> 1550, dated"),
    ("Should Arjun restart QubitML now?", "get_project_status (+ search_notes)", "why it was paused + current priorities, cited; no generic advice"),
    ("What is Arjun's hostel room number?", "search_notes", "the refusal sentence"),
]

if __name__ == "__main__":
    agent = build_agent()
    model = model_label()
    print(f"Agent checkpoint | model: {model}\n")

    runs = []
    for question, expected_tool, expected in CHECKPOINT:
        start = time.time()
        r = ask(agent, question)
        r["seconds"] = round(time.time() - start, 1)
        r["expected_tool"] = expected_tool
        r["expected"] = expected
        runs.append(r)

        print(f"Q: {question}")
        for call in r["tool_calls"]:
            print(f"  [tool] {call['name']}({call['args']})")
        print(f"  expected tool: {expected_tool} | expected: {expected}")
        print(f"  status: {r['status']} | {r['seconds']} s")
        if r["invented_citations"]:
            print(f"  invented citations: {r['invented_citations']}")
        print(f"A: {r['answer']}\n")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = model.replace("/", "_").replace(":", "_")
    out = RESULTS_DIR / f"agent_checkpoint_{safe_model}_{stamp}.json"
    out.write_text(json.dumps({"model": model, "runs": runs}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {out}")
