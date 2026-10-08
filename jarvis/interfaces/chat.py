"""`jarvis chat`: talk to Jarvis through the Stage 6.5 router. /new = fresh thread, /quit = exit."""
import uuid

from jarvis.router.config import get_config
from jarvis.router.graph import ask, build_default_app

# Scripted checkpoint for the bundled sample vault (fictional student Arjun).
DEMO = [
    "hey jarvis, how's it going?",
    "What's my current Codeforces rating?",
    "And how has it changed over the year?",
    "Is QubitML still active?",
    "Why did I pause it?",
    "Should I restart QubitML or focus on job applications?",
    "What does my career plan say about AI backend roles?",
    "Honestly I've been feeling really low and disconnected lately.",
    "Which projects are done?",
    "thanks, that helps",
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


def run(thread="default", demo=False):
    app = build_default_app(get_config())

    if demo:
        thread = f"demo-{uuid.uuid4().hex[:6]}"
        for message in DEMO:
            print(f"You: {message}")
            show(ask(app, message, thread))
        return

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