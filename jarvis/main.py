"""The `jarvis` command.

    jarvis init <notes folder>          write config.yaml here (every folder private to start)
    jarvis ingest                       build the search index
    jarvis registry [--merge-only]      build the project registry and overview page
    jarvis ask "question" [--agent]     one answer, with sources
    jarvis chat [--thread NAME] [--demo]
    jarvis mcp                          run the MCP server (stdio) for an MCP host
    jarvis check ["query"] [--mode M]   launch the MCP server like a host would and test it

Every command reads config.yaml from the current folder, or from --config / JARVIS_CONFIG.
"""
import argparse
import os
import sys
from pathlib import Path

from jarvis.router.config import CONFIG_ENV, get_config


def cmd_init(args):
    from jarvis.workspace import init_workspace

    target = Path(args.config) if args.config else Path("config.yaml")
    path, folders = init_workspace(args.notes, target, force=args.force)
    print(f"Wrote {path} with {len(folders)} folders, all PRIVATE: {folders}")
    print("Next: edit it (mark shareable folders, split domains, set registry folders), then `jarvis ingest`.")


def cmd_ingest(args):
    from jarvis.ingest.index import build_index

    build_index()


def cmd_registry(args):
    from jarvis.registry.build import run
    from jarvis.registry.overview import write_overview

    if not get_config().registry_folders:
        raise SystemExit("No registry folders configured (registry: folders: in config.yaml).")
    run(merge_only=args.merge_only)
    path, _ = write_overview()
    print(f"\nOverview written to {path}")


def cmd_ask(args):
    if args.agent:
        from jarvis.agent.agent import ask, build_agent

        trace = ask(build_agent(), args.question)
        print(trace["answer"])
        print(f"\n[agent status: {trace['status']}]")
        sources = sorted(set(trace["retrieved_sources"]))
    else:
        from jarvis.interfaces.cli import answer_question
        from jarvis.retrieval.vector_store import open_vectorstore

        cfg = get_config()
        answer, metas = answer_question(open_vectorstore(cfg.index_path, cfg.collection), args.question)
        print(answer)
        sources = sorted({m["source"].replace("\\", "/") for m in metas})
    print("\nSources:")
    for s in sources:
        print(f"  - {s}")


def cmd_chat(args):
    from jarvis.interfaces.chat import run

    run(thread=args.thread, demo=args.demo)


def cmd_mcp(args):
    from jarvis.interfaces.mcp_server import main as serve

    serve()


def cmd_check(args):
    from jarvis.interfaces.mcp_check import run

    run(args.query, args.mode)


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help="path to config.yaml (default: ./config.yaml or $JARVIS_CONFIG)")

    parser = argparse.ArgumentParser(prog="jarvis", description="Version-aware notes assistant.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", parents=[common], help="write config.yaml for a notes folder")
    p.add_argument("notes")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("ingest", parents=[common], help="build the search index")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("registry", parents=[common], help="build the project registry + overview")
    p.add_argument("--merge-only", action="store_true", help="re-merge saved mentions, no model calls")
    p.set_defaults(func=cmd_registry)

    p = sub.add_parser("ask", parents=[common], help="ask one question")
    p.add_argument("question")
    p.add_argument("--agent", action="store_true", help="use the tool-using agent instead of the pipeline")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("chat", parents=[common], help="chat through the router")
    p.add_argument("--thread", default="default")
    p.add_argument("--demo", action="store_true", help="scripted 10-message demo (sample vault)")
    p.set_defaults(func=cmd_chat)

    p = sub.add_parser("mcp", parents=[common], help="run the MCP server over stdio")
    p.set_defaults(func=cmd_mcp)

    p = sub.add_parser("check", parents=[common], help="test the MCP server like a host would")
    p.add_argument("query", nargs="?", default="current status of my projects")
    p.add_argument("--mode", choices=["current", "history", "any"], default="current")
    p.set_defaults(func=cmd_check)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.config and args.command != "init":
        os.environ[CONFIG_ENV] = str(Path(args.config).expanduser().resolve())
    try:
        args.func(args)
    except FileNotFoundError as error:
        print(f"jarvis: {error}", file=sys.stderr)  # stderr: stdout belongs to MCP in `jarvis mcp`
        sys.exit(1)


if __name__ == "__main__":
    main()