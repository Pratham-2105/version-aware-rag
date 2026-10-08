"""Chat with Jarvis through the Stage 6.5 router.

    python -u scripts/chat.py                  # thread "default"
    python -u scripts/chat.py --thread college
    python -u scripts/chat.py --demo           # scripted 10-message checkpoint

In chat: /new starts a fresh thread, /quit exits.
"""
import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.router.config import load_config
from jarvis.router.graph import ask, build_default_app

DEMO = [
    "hey jarvis, how's it going?",                                     # casual, no retrieval
    "What's my current Codeforces rating?",                             # study, current_state
    "And how has it changed over the year?",                            # follow-up -> rewrite, historical
    "Is QubitML still active?",                                         # projects, current_state
    "Why did I pause it?",                                              # follow-up -> 'it' = QubitML
    "Should I restart QubitML or focus on job applications?",           # projects+career, decision
    "What does my career plan say about AI backend roles?",             # career
    "Honestly I've been feeling really low and disconnected lately.",   # personal -> PRIVATE, local
    "Which projects are done?",                                         # projects; turn 8 must be hidden
    "thanks, that helps",                                               # casual
]


def show(state):
    route = state["route"]
    parts = [
        "+".join(route["domains"]),
        route["intent"],
        route["request"],
        f"model={state.get('model_used')}",
        "PRIVATE" if state.get("private") else "shareable",
    ]
    if route.get("fallback"):
        parts.append(f"FALLBACK ({route['fallback']})")
    print("[route] " + " | ".join(parts))
    if state.get("folders"):
        print("[scope] " + ", ".join(state["folders"]))
    if route["search_query"].strip() != state["question"].strip():
        print(f"[query] {route['search_query']}")
    print(
        f"[memory] {state.get('visible_turns', 0)} earlier exchanges visible, "
        f"{state.get('hidden_private', 0)} private hidden"
    )
    print(f"\nJarvis: {state['answer']}\n")


def main():
    parser = argparse.ArgumentParser(description="Chat with Jarvis (Stage 6.5 router)")
    parser.add_argument("--thread", default="default")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    app = build_default_app(load_config())

    if args.demo:
        thread = f"demo-{uuid.uuid4().hex[:6]}"
        for message in DEMO:
            print(f"You: {message}")
            show(ask(app, message, thread))
        return

    thread = args.thread
    print(f"Jarvis (thread '{thread}'). /new = fresh thread, /quit = exit.")
    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not message:
            continue
        if message == "/quit":
            break
        if message == "/new":
            thread = f"chat-{uuid.uuid4().hex[:6]}"
            print(f"(new thread {thread})")
            continue
        show(ask(app, message, thread))


if __name__ == "__main__":
    main()