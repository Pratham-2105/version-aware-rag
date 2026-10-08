"""Stage 6.5 router: one small LLM call per message, constrained to a JSON schema.

Always runs on the LOCAL model: it reads every message before anyone knows
whether the message is private, so it cannot be a hosted model.

Fails closed: if the call errors or returns nothing usable, the message is routed
to ALL domains (which includes the private ones -> local model) and the Stage 4
regex supplies the time intent.
"""
from jarvis.router.classifier import classify_intent
from jarvis.router.prompts import PRIVATE_RULE, ROUTER_PROMPT

INTENTS = ["current_state", "historical", "lookup"]
REQUESTS = ["question", "decision", "reflect", "casual"]
SNIPPET_CHARS = 300


def route_schema(domain_names):
    """Property order = generation order: rewrite first, then classify the rewrite."""
    return {
        "title": "Route",
        "description": "How Jarvis should handle one chat message.",
        "type": "object",
        "properties": {
            "search_query": {
                "type": "string",
                "description": "The message rewritten to stand on its own.",
            },
            "domains": {
                "type": "array",
                "items": {"type": "string", "enum": list(domain_names)},
                "minItems": 1,
                "maxItems": 2,
                "description": "The 1 or 2 life areas the message is about.",
            },
            "intent": {"type": "string", "enum": INTENTS},
            "request": {"type": "string", "enum": REQUESTS},
        },
        "required": ["search_query", "domains", "intent", "request"],
    }


def format_recent(history):
    lines = []
    for turn in history:
        speaker = "User" if turn["role"] == "user" else "Jarvis"
        text = turn["content"].replace("\n", " ")
        lines.append(f"{speaker}: {text[:SNIPPET_CHARS]}")
    return "\n".join(lines) or "(none)"


def fallback_route(question, cfg, reason):
    return {
        "search_query": question,
        "domains": cfg.domain_names,
        "intent": classify_intent(question),
        "request": "question",
        "fallback": reason,
    }


def normalize_route(raw, question, cfg):
    """The grammar guarantees the shape; code still checks the meaning."""
    domains = []
    for d in raw.get("domains") or []:
        if d in cfg.domains and d not in domains:
            domains.append(d)
    if not domains:
        return fallback_route(question, cfg, "no valid domain")

    intent = raw.get("intent")
    if intent not in INTENTS:
        intent = classify_intent(question)
    request = raw.get("request")
    if request not in REQUESTS:
        request = "question"
    query = str(raw.get("search_query") or "").strip() or question

    return {
        "search_query": query,
        "domains": domains,
        "intent": intent,
        "request": request,
        "fallback": None,
    }


def build_router_prompt(cfg):
    domain_lines = "\n".join(f"- {d.name}: {d.description}" for d in cfg.domains.values())
    private = cfg.private_domains
    rule = PRIVATE_RULE.format(names=", ".join(f'"{n}"' for n in private)) if private else ""
    return ROUTER_PROMPT.format(domains=domain_lines, private_rule=rule)


def make_router(cfg, model):
    """Returns route(question, recent_history) -> route dict."""
    structured = model.with_structured_output(route_schema(cfg.domain_names), method="json_schema")
    system = build_router_prompt(cfg)

    def route(question, recent_history=()):
        user = f"Recent conversation:\n{format_recent(recent_history)}\n\nNew message: {question}"
        try:
            raw = structured.invoke([("system", system), ("human", user)])
        except Exception as error:
            return fallback_route(question, cfg, f"router error: {type(error).__name__}")
        if not isinstance(raw, dict):
            return fallback_route(question, cfg, "router returned no JSON")
        return normalize_route(raw, question, cfg)

    return route