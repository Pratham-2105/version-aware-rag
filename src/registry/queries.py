"""Stage 5 — deterministic lookups over the frozen registry. No LLM, same answer every time."""
from src.registry.store import load_registry, normalize_name


def get_project_status(name, registry=None):
    """One project's record by any spelling of its name, or None if unknown."""
    if registry is None:
        registry = load_registry()
    return registry.get(normalize_name(name))


def list_projects(status=None, registry=None):
    """All projects, or only those with the given status."""
    if registry is None:
        registry = load_registry()
    rows = list(registry.values())
    if status:
        rows = [r for r in rows if r["status"] == status.lower()]
    return rows