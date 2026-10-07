"""Stage 6 — the agent: model + tools + system prompt, run as a LangGraph loop.

create_agent builds a two-node graph:  model -> (tool calls?) -> tools -> model -> ... -> answer.
The loop ends when the model replies without asking for a tool.

Model reads, code decides (same rule as Stage 5): the model writes a draft answer,
then check_citations() verifies it in plain Python. A draft that cites nothing it
actually retrieved is replaced by the refusal.
"""
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from src.agent.prompts import AGENT_SYSTEM_PROMPT, REFUSAL
from src.agent.tools import TOOLS

# Each model call and each tool execution is one graph step.
# 12 steps = at most ~5 tool rounds. The fuse against a model that loops on tool calls.
MAX_STEPS = 12

# Turn off to see raw drafts (e.g. to measure how often enforcement fires).
ENFORCE_CITATIONS = True

# No spaces or brackets in the class, so "[a/b.md]" and "(b.md)" both yield "b.md".
PATH_RE = re.compile(r"[A-Za-z0-9_\-./]+\.md")


def get_model():
    """Model choice lives in .env, not in code: swapping models must not touch the agent."""
    load_dotenv()
    provider = os.getenv("JARVIS_LLM_PROVIDER", "ollama")

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=os.getenv("JARVIS_MODEL", "qwen2.5:7b"),
            base_url="http://127.0.0.1:11434",
            temperature=0,
            seed=42,
            num_predict=1024,
            client_kwargs={"timeout": 120},
        )

    if provider == "openai_compat":  # any OpenAI-compatible API (AirRouter, OpenRouter, DeepSeek...)
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=os.environ["JARVIS_MODEL"],
            base_url=os.environ["JARVIS_API_BASE"],
            api_key=os.environ["JARVIS_API_KEY"],
            temperature=0,
            max_tokens=1024,
            timeout=60,
        )

    raise ValueError(f"Unknown JARVIS_LLM_PROVIDER: {provider!r} (use 'ollama' or 'openai_compat')")


def model_label():
    load_dotenv()
    return os.getenv("JARVIS_MODEL", "qwen2.5:7b")


def build_agent(model=None):
    return create_agent(model or get_model(), tools=TOOLS, system_prompt=AGENT_SYSTEM_PROMPT)


# ---------- citation enforcement (pure function, unit-tested) ----------

def _file_names(text):
    return {Path(p).name.lower() for p in PATH_RE.findall(text.replace("\\", "/"))}


def check_citations(answer, tool_text):
    """Which .md files does the answer cite, and were they really retrieved?

    Compares file names (not full paths) so 'oct2026.md' and 'handovers/oct2026.md'
    count as the same citation.
    """
    retrieved = _file_names(tool_text)
    cited = _file_names(answer)
    return {"valid": sorted(cited & retrieved), "invented": sorted(cited - retrieved)}


def is_refusal(text):
    return REFUSAL.lower().rstrip(".") in text.lower()


def judge(draft, tool_calls, tool_text):
    """Decide what the user sees. Returns (status, final_answer)."""
    if is_refusal(draft):
        return "refused", draft
    if not tool_calls:
        status = "no_tool"            # answered from its own knowledge
    else:
        cites = check_citations(draft, tool_text)
        if not cites["valid"]:
            status = "uncited"
        elif cites["invented"]:
            status = "ok_invented_citation"   # kept, but flagged in the trace
        else:
            status = "ok"
    if ENFORCE_CITATIONS and status in ("no_tool", "uncited"):
        return status, REFUSAL
    return status, draft


# ---------- one question in, answer + trace out ----------

def ask(agent, question):
    """Run one question through the agent (no conversation memory yet — Stage 6.5)."""
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config={"recursion_limit": MAX_STEPS},
        )
    except GraphRecursionError:
        return {
            "question": question, "answer": REFUSAL, "draft": "", "status": "step_limit",
            "tool_calls": [], "valid_citations": [], "invented_citations": [],
        }

    messages = result["messages"]
    tool_calls = [
        {"name": c["name"], "args": c["args"]}
        for m in messages if isinstance(m, AIMessage)
        for c in m.tool_calls
    ]
    tool_text = "\n".join(m.text for m in messages if isinstance(m, ToolMessage))
    draft = messages[-1].text

    status, answer = judge(draft, tool_calls, tool_text)
    cites = check_citations(draft, tool_text)
    return {
        "question": question,
        "answer": answer,
        "draft": draft,
        "status": status,
        "tool_calls": tool_calls,
        "valid_citations": cites["valid"],
        "invented_citations": cites["invented"],
    }
