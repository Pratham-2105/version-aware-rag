"""Stage 6.5 — the conversation graph (LangGraph).

    START -> route --(casual)-----------------> answer -> END
                   \--(else)--> retrieve -----> answer

route     local LLM, JSON schema: search_query, domains, intent, request
retrieve  Stage 4 retrieval with the router's intent + the domains' folders as filter
answer    picks the model (privacy rules), builds base + layers + memory window,
          calls the model, appends this exchange to the thread's history

State is saved per thread_id by the checkpointer: that is the thread's memory.
All dependencies are injected, so tests run with spy models and no Ollama.
"""
import operator
import uuid
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from src.interfaces.cli import SYSTEM_PROMPT
from src.retrieval.search import format_context
from src.router import memory
from src.router.privacy_filter import (
    assert_hosted_safe,
    filter_history,
    route_is_private,
    sources_are_private,
)
from src.router.prompts import (
    CASUAL_PROMPT,
    LOCAL_DOWN,
    MODEL_DOWN,
    PERSONAL_SAFEGUARD,
    REFLECT_PROMPT,
    REQUEST_LAYERS,
)


class ChatState(TypedDict, total=False):
    question: str
    history: Annotated[list, operator.add]  # reducer: each run APPENDS one exchange
    route: dict
    private: bool
    folders: list
    context: str
    sources: list
    answer: str
    model_used: str
    error: str
    visible_turns: int
    hidden_private: int


def build_messages(cfg, question, route, context, history, private):
    request = route["request"]
    if request == "casual":
        system = CASUAL_PROMPT
    else:
        base = REFLECT_PROMPT if request == "reflect" else SYSTEM_PROMPT
        layers = [base, REQUEST_LAYERS.get(request, ""), cfg.style_for(route["domains"])]
        if private:
            layers.append(PERSONAL_SAFEGUARD)
        system = "\n\n".join(layer.strip() for layer in layers if layer and layer.strip())

    messages = [SystemMessage(content=system)]
    for turn in history:
        cls = HumanMessage if turn["role"] == "user" else AIMessage
        messages.append(cls(content=turn["content"]))

    if request == "casual":
        messages.append(HumanMessage(content=question))
    else:
        sources = context or "(no sources found)"
        messages.append(HumanMessage(content=f"Sources:\n\n{sources}\n\nQuestion: {question}"))
    return messages


def build_router_graph(cfg, route_fn, retrieve_fn, local_model, hosted_model=None, checkpointer=None):
    """route_fn(question, recent_history) -> route dict
    retrieve_fn(query, intent, folders) -> Chroma-shaped results"""

    def route_node(state):
        question = state["question"]
        recent = memory.recent(state.get("history", []), cfg.router_history_turns)
        route = route_fn(question, recent)
        # Reset every per-message field so nothing leaks from the previous run's state.
        return {
            "route": route,
            "private": route_is_private(route, cfg),
            "folders": [],
            "context": "",
            "sources": [],
            "answer": "",
            "model_used": "",
            "error": "",
        }

    def after_route(state):
        return "answer" if state["route"]["request"] == "casual" else "retrieve"

    def retrieve_node(state):
        route = state["route"]
        folders = cfg.folders_for(route["domains"]) if cfg.scope_retrieval else None
        if folders is not None and not folders:
            return {}  # domain with no folders: nothing to search

        # The rewrite only exists to resolve follow-ups. On a first message the raw
        # question is safer for BM25 (a 7B paraphrase can drop keywords).
        query = route["search_query"] if state.get("history") else state["question"]
        results = retrieve_fn(query, route["intent"], folders)
        metas = results["metadatas"][0]
        return {
            "folders": folders or [],
            "context": format_context(results) if metas else "",
            "sources": metas,
            # Defence in depth: a private chunk in the results makes the turn private.
            "private": state["private"] or sources_are_private(metas, cfg),
        }

    def answer_node(state):
        route, private, question = state["route"], state["private"], state["question"]
        full = state.get("history", [])
        visible = memory.recent(filter_history(full, allow_private=private), cfg.memory_turns)
        use_hosted = hosted_model is not None and not private

        messages = build_messages(cfg, question, route, state.get("context", ""), visible, private)
        if use_hosted:
            assert_hosted_safe(state.get("sources", []), visible, cfg)

        info = {
            "visible_turns": len(visible) // 2,
            "hidden_private": 0 if private else sum(t["private"] for t in full) // 2,
        }
        model = hosted_model if use_hosted else local_model
        try:
            reply = model.invoke(messages).content
        except Exception as error:
            failure = LOCAL_DOWN if private else MODEL_DOWN.format(error=type(error).__name__)
            return {"answer": failure, "model_used": "none", "error": repr(error), **info}

        exchange = [
            memory.make_turn("user", question, private, route["domains"]),
            memory.make_turn("assistant", reply, private, route["domains"]),
        ]
        return {
            "answer": reply,
            "model_used": "hosted" if use_hosted else "local",
            "history": exchange,
            **info,
        }

    graph = StateGraph(ChatState)
    graph.add_node("route", route_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("answer", answer_node)
    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", after_route, {"retrieve": "retrieve", "answer": "answer"})
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    return graph.compile(checkpointer=checkpointer or InMemorySaver())


def ask(app, question, thread_id):
    return app.invoke({"question": question}, config={"configurable": {"thread_id": thread_id}})


def build_default_app(cfg=None):
    """Real dependencies: Ollama router + local answer model, optional hosted, Chroma index."""
    from src.retrieval.search import retrieve
    from src.retrieval.vector_store import open_vectorstore
    from src.router.config import load_config
    from src.router.llm_router import make_router
    from src.router.models import hosted_chat_model, local_chat_model

    cfg = cfg or load_config()
    collection = open_vectorstore(cfg.index_path, cfg.collection)

    def retrieve_fn(query, intent, folders):
        return retrieve(collection, query, intent=intent, folders=folders)

    route_fn = make_router(cfg, local_chat_model(cfg, num_predict=256, timeout=60))
    return build_router_graph(
        cfg, route_fn, retrieve_fn, local_chat_model(cfg), hosted_chat_model(cfg)
    )


_default_app = None


def router_answer(question):
    """Eval entry point: a fresh thread per question (no memory bleed between
    golden questions). Returns (answer, source metadatas, route)."""
    global _default_app
    if _default_app is None:
        _default_app = build_default_app()
    state = ask(_default_app, question, thread_id=f"eval-{uuid.uuid4().hex}")
    return state["answer"], state.get("sources", []), state["route"]