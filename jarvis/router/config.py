"""Load config.yaml into one typed object.

Everything that differs between users lives in config.yaml: where the notes are, where
the index and registry go, which top-level folders exist, which are private, which hold
versions of one document vs separate entries (diaries), and which life areas the router
chooses between. Code asks this object; it never hard-codes a path or a folder name.

Which config? --config (sets JARVIS_CONFIG), else JARVIS_CONFIG, else ./config.yaml.
Relative paths inside it resolve against the config file's own folder, so the same
config works no matter which folder Jarvis is launched from (MCP hosts launch it from
their own folder).
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_ENV = "JARVIS_CONFIG"
DEFAULT_CONFIG_PATH = Path("config.yaml")
PRIVATE = "private"
SHAREABLE = "shareable"
PRIVACY_LEVELS = (PRIVATE, SHAREABLE)


@dataclass
class FolderConfig:
    name: str
    privacy: str
    versioned: bool


@dataclass
class DomainConfig:
    name: str
    description: str
    folders: list
    style: str = ""


@dataclass
class JarvisConfig:
    notes_path: Path
    index_path: Path
    collection: str
    folders: dict
    domains: dict
    registry_path: Path = Path("data/registry")
    overview_path: Path = Path("docs/overview.md")
    registry_folders: list = field(default_factory=list)
    default_folder_privacy: str = PRIVATE
    scope_retrieval: bool = True
    router_history_turns: int = 2
    memory_turns: int = 4
    local_model: dict = field(default_factory=dict)
    hosted_model: dict = field(default_factory=dict)
    config_dir: Path = None

    @property
    def domain_names(self):
        return list(self.domains)

    @property
    def private_domains(self):
        return [d for d in self.domains if self.is_private_domain(d)]

    @property
    def unversioned_folders(self):
        return {name for name, f in self.folders.items() if not f.versioned}

    def is_private_folder(self, folder):
        """Unlisted folders get the default, which is private: fail closed."""
        f = self.folders.get(folder)
        privacy = f.privacy if f else self.default_folder_privacy
        return privacy == PRIVATE

    def is_private_domain(self, domain):
        """A domain is private if ANY of its folders is. Unknown domain -> private."""
        d = self.domains.get(domain)
        if d is None:
            return True
        return any(self.is_private_folder(f) for f in d.folders)

    def folders_for(self, domains):
        out = set()
        for name in domains:
            d = self.domains.get(name)
            if d:
                out.update(d.folders)
        return sorted(out)

    def style_for(self, domains):
        styles = [
            self.domains[d].style.strip()
            for d in domains
            if d in self.domains and self.domains[d].style.strip()
        ]
        return "\n".join(styles)


def _check_privacy(value, where):
    if value not in PRIVACY_LEVELS:
        raise ValueError(f"{where}: privacy must be one of {PRIVACY_LEVELS}, got {value!r}")


def _resolve(value, base_dir):
    path = Path(str(value)).expanduser()
    if base_dir is not None and not path.is_absolute():
        path = base_dir / path
    return path


def config_from_dict(raw, base_dir=None):
    """Build + validate. base_dir = folder of the config file (None keeps paths as written)."""
    paths = raw.get("paths") or {}
    default_privacy = raw.get("default_folder_privacy", PRIVATE)
    _check_privacy(default_privacy, "default_folder_privacy")

    folders = {}
    for name, spec in (raw.get("folders") or {}).items():
        spec = spec or {}
        privacy = spec.get("privacy", default_privacy)
        _check_privacy(privacy, f"folders.{name}")
        folders[str(name)] = FolderConfig(str(name), privacy, bool(spec.get("versioned", True)))

    domains = {}
    for name, spec in (raw.get("domains") or {}).items():
        spec = spec or {}
        listed = [str(f) for f in (spec.get("folders") or [])]
        unknown = [f for f in listed if f not in folders]
        if unknown:
            raise ValueError(f"domain '{name}' uses folders not listed under 'folders:': {unknown}")
        description = str(spec.get("description") or "").strip()
        if not description:
            raise ValueError(f"domain '{name}' needs a description (the router reads it)")
        domains[name] = DomainConfig(name, description, listed, str(spec.get("style") or ""))

    if not domains:
        raise ValueError("config needs at least one domain")

    registry = raw.get("registry") or {}
    registry_folders = [str(f) for f in (registry.get("folders") or [])]
    unknown = [f for f in registry_folders if f not in folders]
    if unknown:
        raise ValueError(f"registry.folders uses folders not listed under 'folders:': {unknown}")

    router = raw.get("router") or {}
    memory = raw.get("memory") or {}
    models = raw.get("models") or {}

    return JarvisConfig(
        notes_path=_resolve(paths.get("notes", "data/sample-vault"), base_dir),
        index_path=_resolve(paths.get("index", "data/chroma-store"), base_dir),
        collection=paths.get("collection", "sample_collection"),
        folders=folders,
        domains=domains,
        registry_path=_resolve(paths.get("registry", "data/registry"), base_dir),
        overview_path=_resolve(paths.get("overview", "docs/overview.md"), base_dir),
        registry_folders=registry_folders,
        default_folder_privacy=default_privacy,
        scope_retrieval=bool(router.get("scope_retrieval", True)),
        router_history_turns=int(router.get("history_turns", 2)),
        memory_turns=int(memory.get("turns", 4)),
        local_model=dict(models.get("local") or {}),
        hosted_model=dict(models.get("hosted") or {}),
        config_dir=base_dir,
    )


def config_path():
    """--config / JARVIS_CONFIG if set, else config.yaml in the current folder."""
    return Path(os.environ.get(CONFIG_ENV) or DEFAULT_CONFIG_PATH).expanduser().resolve()


def load_config(path=None):
    path = Path(path).expanduser().resolve() if path else config_path()
    if not path.exists():
        raise FileNotFoundError(
            f"No config at {path}. Run `jarvis init <notes folder>` in this folder, or pass --config."
        )
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return config_from_dict(raw, base_dir=path.parent)


_cache = {}


def get_config():
    """The active config, loaded once per config file."""
    path = config_path()
    if path not in _cache:
        _cache[path] = load_config(path)
    return _cache[path]