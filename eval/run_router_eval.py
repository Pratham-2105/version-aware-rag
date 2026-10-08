"""Router accuracy on its own (no answering).

Part 1  intent on the time-sensitive golden questions: LLM router vs Stage 4 regex
Part 2  domains + request on eval/router_messages.json (hand-labelled)
        private-domain recall is reported separately: a miss = a potential leak,
        so it must be 100% before the router is trusted
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.router.classifier import classify_intent
from src.router.config import load_config
from src.router.llm_router import make_router
from src.router.models import local_chat_model

GOLDEN = Path("eval/golden_questions.json")
MESSAGES = Path("eval/router_messages.json")
RESULTS_DIR = Path("eval/results")
EXPECTED_INTENT = {"current_state_temporal": "current_state", "historical_change": "historical"}


def pct(n, d):
    return f"{n}/{d} = {100 * n / d:.1f}%" if d else "n/a"


def load_golden():
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    return data["questions"] if isinstance(data, dict) else data


def intent_part(route):
    rows = []
    for q in load_golden():
        expected = EXPECTED_INTENT.get(q["category"])
        if expected is None:
            continue
        r = route(q["question"])
        rows.append({
            "id": q.get("id"),
            "question": q["question"],
            "expected": expected,
            "router": r["intent"],
            "regex": classify_intent(q["question"]),
            "fallback": r["fallback"],
        })
    n = len(rows)
    router_ok = sum(r["router"] == r["expected"] for r in rows)
    regex_ok = sum(r["regex"] == r["expected"] for r in rows)
    print("\n== Intent on time-sensitive golden questions ==")
    print(f"LLM router: {pct(router_ok, n)}   regex: {pct(regex_ok, n)}")
    for r in rows:
        if r["router"] != r["expected"] or r["regex"] != r["expected"]:
            print(f"  Q{r['id']}: expected {r['expected']}, router {r['router']}, regex {r['regex']}")
    return rows, {"n": n, "router_correct": router_ok, "regex_correct": regex_ok}


def message_part(route, private_domains):
    rows = []
    for m in json.loads(MESSAGES.read_text(encoding="utf-8")):
        r = route(m["message"])
        rows.append({
            "message": m["message"],
            "expected_domains": sorted(m["domains"]),
            "routed_domains": sorted(r["domains"]),
            "expected_request": m["request"],
            "routed_request": r["request"],
            "fallback": r["fallback"],
        })

    private = set(private_domains)
    scored = [r for r in rows if r["expected_domains"]]
    exact = sum(r["expected_domains"] == r["routed_domains"] for r in scored)
    overlap = sum(bool(set(r["expected_domains"]) & set(r["routed_domains"])) for r in scored)
    request_ok = sum(r["expected_request"] == r["routed_request"] for r in rows)
    should_private = [r for r in scored if private & set(r["expected_domains"])]
    recall = sum(bool(private & set(r["routed_domains"])) for r in should_private)
    false_private = sum(
        bool(private & set(r["routed_domains"])) for r in scored if not private & set(r["expected_domains"])
    )
    fallbacks = sum(bool(r["fallback"]) for r in rows)

    print("\n== Domains + request on labelled messages ==")
    print(f"domains exact:    {pct(exact, len(scored))}")
    print(f"domains overlap:  {pct(overlap, len(scored))}")
    print(f"request type:     {pct(request_ok, len(rows))}")
    print(f"PRIVATE recall:   {pct(recall, len(should_private))}   (must be 100%)")
    print(f"private false +:  {false_private}   (costs quality, not privacy)")
    print(f"fallbacks:        {fallbacks}")
    for r in rows:
        bad_domain = r["expected_domains"] and r["expected_domains"] != r["routed_domains"]
        if bad_domain or r["expected_request"] != r["routed_request"]:
            print(f"  '{r['message'][:60]}': expected {r['expected_domains']}/{r['expected_request']}, "
                  f"got {r['routed_domains']}/{r['routed_request']}")

    summary = {
        "n": len(rows), "domain_scored": len(scored), "domains_exact": exact,
        "domains_overlap": overlap, "request_correct": request_ok,
        "private_expected": len(should_private), "private_recall": recall,
        "private_false_positives": false_private, "fallbacks": fallbacks,
    }
    return rows, summary


def main():
    cfg = load_config()
    route = make_router(cfg, local_chat_model(cfg, num_predict=256, timeout=60))
    intent_rows, intent_summary = intent_part(route)
    message_rows, message_summary = message_part(route, cfg.private_domains)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"router_{cfg.local_model.get('model', 'local').replace(':', '-')}_{stamp}.json"
    out.write_text(json.dumps({
        "intent": {"summary": intent_summary, "rows": intent_rows},
        "messages": {"summary": message_summary, "rows": message_rows},
    }, indent=2), encoding="utf-8")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()