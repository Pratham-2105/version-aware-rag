"""`jarvis check`: launch the MCP server the way a host does (child process over stdio),
list its tools, run a search and a project listing, and verify that no result comes
from a private folder."""
import asyncio
import sys

from mcp import Client, StdioServerParameters

from jarvis.router.config import config_path, get_config


def text_of(result):
    return "\n".join(getattr(block, "text", "") for block in result.content)


async def call(client, name, args):
    print(f"\n=== {name}({args}) ===")
    try:
        result = await client.call_tool(name, args)
    except Exception as error:
        print(f"ERROR: {type(error).__name__}: {error}")
        return ""
    text = text_of(result)
    print(text)
    return text


async def _check(cfg_file, private_folders, query, mode):
    # The same launch command a host config holds: this Python + `jarvis mcp --config ...`.
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "jarvis", "mcp", "--config", str(cfg_file)]
    )
    async with Client(params) as client:
        listed = await client.list_tools()
        print("Tools:", sorted(tool.name for tool in listed.tools))
        outputs = [
            await call(client, "search_notes", {"query": query, "mode": mode}),
            await call(client, "list_projects", {"status": "all"}),
        ]
    leaked = [f for f in private_folders if any(f"SOURCE: {f}/" in text for text in outputs)]
    if leaked:
        print(f"\nPRIVACY: LEAK - results came from private folders {leaked}")
    else:
        print("\nPRIVACY: OK - no result from a private folder")


def run(query, mode="current"):
    cfg = get_config()
    private = [f for f in cfg.folders if cfg.is_private_folder(f) and f != "."]
    asyncio.run(_check(config_path(), private, query, mode))