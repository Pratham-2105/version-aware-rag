"""Model factory for the router graph. Two explicit slots instead of one env switch:
local  -> always available, used for the router and every private answer
hosted -> optional, only ever used for NON-private answers
"""
import os

from langchain_ollama import ChatOllama


def local_chat_model(cfg, num_predict=1024, timeout=120):
    m = cfg.local_model
    return ChatOllama(
        model=m.get("model", "qwen2.5:7b"),
        base_url=m.get("host", "http://127.0.0.1:11434"),
        temperature=m.get("temperature", 0),
        seed=m.get("seed", 42),
        num_predict=num_predict,
        client_kwargs={"timeout": timeout},
    )


def hosted_chat_model(cfg):
    """None unless config enables it. Missing keys = loud error, never a quiet downgrade."""
    if not cfg.hosted_model.get("enabled"):
        return None
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    model = os.getenv("JARVIS_MODEL")
    key = os.getenv("JARVIS_API_KEY")
    base = os.getenv("JARVIS_API_BASE")
    if not (model and key):
        raise RuntimeError(
            "models.hosted.enabled is true but JARVIS_MODEL / JARVIS_API_KEY are missing in .env"
        )
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model, base_url=base, api_key=key, temperature=0)