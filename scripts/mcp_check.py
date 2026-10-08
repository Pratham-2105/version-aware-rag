"""Play the MCP host: launch the Jarvis server as a real stdio subprocess and call its tools.

This is what Claude Desktop does, minus the chat window: spawn the server, send JSON-RPC
on its stdin, read replies on its stdout.

    python -u scripts/mcp_check.py                          # fixed checkpoint calls
    python -u scripts/mcp_check.py "rating history" history  # one search of your own
"""
import asyncio
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "src" / "interfaces" / "mcp_server.py"

CHECKPOINT = [
    ("search_notes", {"query": "current codeforces rating", "mode": "current"}),
    ("search_notes", {"query": "codeforces rating", "mode": "history"}),
    ("list_projects", {"status": "paused"}),
    ("get_project_status", {"name": "QubitML"}),
    ("search_notes", {"query": "diary feelings personal reflections", "mode": "any"}),  # privacy probe
]


def text_of(result):
    return "\n".join(getattr(block, "text", "") for block in result.content)


async def call(client, name, args):
    print(f"\n=== {name}({args}) ===")
    try:
        result = await client.call_tool(name, args)
    except Exception as error:  # the client may raise for a tool error
        print(f"ERROR: {type(error).__name__}: {error}")
        return ""
    text = text_of(result)
    print(text)
    return text


async def main():
    # Same launch command a host config would hold: this venv's Python + the server file.
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with Client(params) as client:
        listed = await client.list_tools()
        print("Tools:", sorted(tool.name for tool in listed.tools))

        if len(sys.argv) > 1:
            mode = sys.argv[2] if len(sys.argv) > 2 else "any"
            await call(client, "search_notes", {"query": sys.argv[1], "mode": mode})
            return

        outputs = [await call(client, name, args) for name, args in CHECKPOINT]
        leaked = any("SOURCE: personal/" in text for text in outputs)
        print("\nPRIVACY:", "LEAK - a personal/ source was returned" if leaked else "OK - no personal/ source in any result")


if __name__ == "__main__":
    asyncio.run(main())