"""Stage 7 — Jarvis as an MCP server (stdio).   Run: jarvis mcp [--config path]

An MCP host (Claude Desktop, Claude Code, Cursor) starts this as a child process and
talks to it over stdin/stdout. Jarvis exposes RETRIEVAL, not answers: inside those
hosts the reader is a much stronger model than qwen2.5:7b, and the eval showed that
reading, not finding, is where the 7B model fails.

Privacy: the host's model is usually hosted, so everything a tool returns leaves this
machine. Search is limited to folders marked shareable in config.yaml, and every chunk
is checked again before it is returned. Private folders are never reachable here.

Never print() in this file: on stdio, stdout IS the protocol.
"""
from functools import lru_cache
from typing import Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from jarvis.retrieval.search import date_note, retrieve
from jarvis.retrieval.vector_store import open_vectorstore
from jarvis.router.config import get_config
from jarvis.router.privacy_filter import chunk_folder

TOP_K = 8  # the host model reads well, so it gets a few more chunks than qwen did
MODE_TO_INTENT = {"current": "current_state", "history": "historical", "any": "lookup"}

mcp = MCPServer("Jarvis")


@lru_cache(maxsize=1)
def get_collection():
    cfg = get_config()
    return open_vectorstore(cfg.index_path, cfg.collection)


def shareable_folders(cfg):
    """Listed folders not marked private. Unlisted folders are private by default."""
    return sorted(name for name in cfg.folders if not cfg.is_private_folder(name))


def check_registry_shareable(cfg):
    if not cfg.registry_folders:
        raise ToolError("No project registry is configured (registry: folders: in config.yaml).")
    private = [f for f in cfg.registry_folders if cfg.is_private_folder(f)]
    if private:
        raise ToolError(
            f"The project registry is built from {private}, which config.yaml marks private, "
            "so it is not available over MCP."
        )


def format_results(results, cfg):
    """One block per chunk: SOURCE line (file > section, date, version), then the text.
    Private chunks are dropped here too, whatever retrieval returned."""
    blocks = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        if cfg.is_private_folder(chunk_folder(meta)):
            continue
        source = meta["source"].replace("\\", "/")
        header = meta.get("header_path", "")
        blocks.append(f"SOURCE: {source} > {header} ({date_note(meta)})\n{doc}")
    return blocks


def call_agent_tool(name, args):
    """Reuse the Stage 6 tools so registry formatting can't drift between agent and MCP."""
    from jarvis.agent import tools as agent_tools  # heavy (LangChain): import on first use

    try:
        return getattr(agent_tools, name).invoke(args)
    except Exception as error:
        raise ToolError(f"{name} failed ({type(error).__name__}: {error})") from error


@mcp.tool()
def search_notes(query: str, mode: Literal["current", "history", "any"] = "any") -> str:
    """Search the user's personal notes, plans and project files (version-aware).

    Choose mode by what the question asks:
    - "current": what is true NOW (current, latest, still, status). Only the latest
      version of each document is searched, so outdated copies cannot appear.
    - "history": how something changed over time, or when something happened. Every
      version is returned, oldest first.
    - "any": anything else.

    Each result starts with "SOURCE: <file> > <section> (<date>, latest/older version)".
    Cite the file for every fact you use. "undated" means the date is unknown, so do not
    use it to decide which version is newer. If nothing relevant comes back, say the
    notes don't contain it instead of guessing. Private folders are never searched.
    """
    cfg = get_config()
    folders = shareable_folders(cfg)
    if not folders:
        raise ToolError(
            "No folders are marked shareable in config.yaml, so nothing can be searched over MCP. "
            "Set `privacy: shareable` on the folders you are happy to share."
        )
    try:
        results = retrieve(
            get_collection(), query, top_k=TOP_K, intent=MODE_TO_INTENT[mode], folders=folders
        )
    except Exception as error:
        raise ToolError(
            f"Search failed ({type(error).__name__}: {error}). "
            "Is Ollama running, and has `jarvis ingest` been run?"
        ) from error

    blocks = format_results(results, cfg)
    if not blocks:
        return "No matching notes found."
    return "\n\n".join(f"[{n}] {block}" for n, block in enumerate(blocks, start=1))


@mcp.tool()
def get_project_status(name: str) -> str:
    """Status record for ONE project from the user's project registry: status
    (active / paused / done / abandoned / planned), the stated reason, key result,
    status history and source files. Use only for project STATUS questions; use
    search_notes for anything else about a project."""
    check_registry_shareable(get_config())
    return call_agent_tool("get_project_status", {"name": name})


@mcp.tool()
def list_projects(
    status: Literal["all", "active", "paused", "done", "abandoned", "planned"] = "all",
) -> str:
    """List the user's projects from the registry, optionally only those with one status.
    Use for questions like "which projects are paused?" or "what have I finished?"."""
    check_registry_shareable(get_config())
    return call_agent_tool("list_projects", {"status": status})


@mcp.resource("jarvis://overview")
def project_overview() -> str:
    """One-page overview of every project, generated from the registry."""
    cfg = get_config()
    check_registry_shareable(cfg)
    if not cfg.overview_path.exists():
        return "No overview yet. Run `jarvis registry`."
    return cfg.overview_path.read_text(encoding="utf-8")


def main():
    mcp.run()  # stdio by default: blocks, reads requests on stdin, writes replies on stdout


if __name__ == "__main__":
    main()