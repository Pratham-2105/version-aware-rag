import json
import sys
import time

from jarvis.ingest.pipeline import run_ingestion
from jarvis.registry.extractor import build_extraction_chain, extract_from_document
from jarvis.registry.store import merge_mentions, registry_file, save_registry
from jarvis.router.config import get_config

META_KEYS = ("version_date", "date_source", "doc_group_id", "is_latest")


def mentions_file():
    return get_config().registry_path / "mentions.json"


def documents_to_extract(vault_path):
    """One entry per KEPT document (dedup already applied), with its version metadata."""
    chunks = run_ingestion(vault_path, verbose=False)
    registry_folders = set(get_config().registry_folders)
    docs = {}
    for c in chunks:
        source = c["source"]
        folder = source.replace("\\", "/").split("/")[0]
        if folder in registry_folders and source not in docs:
            docs[source] = {k: c[k] for k in META_KEYS}
    return docs


def extract_all(vault_path):
    chain = build_extraction_chain()
    docs = documents_to_extract(vault_path)
    mentions = []
    for i, (source, meta) in enumerate(sorted(docs.items()), 1):
        text = (vault_path / source.replace("\\", "/")).read_text(encoding="utf-8")
        start = time.time()
        try:
            found = extract_from_document(chain, source, text, meta)
        except Exception as e:  # one bad doc must not kill the build
            print(f"[{i}/{len(docs)}] FAILED {source}: {e}")
            continue
        names = ", ".join(f"{m['name']}={m['status']}" for m in found) or "(none)"
        print(
            f"[{i}/{len(docs)}] {source} ({len(text)} chars, {time.time() - start:.1f}s) -> {names}"
        )
        mentions.extend(found)
    return mentions


def run(merge_only=False):
    path = mentions_file()
    if merge_only:
        mentions = json.loads(path.read_text(encoding="utf-8"))
    else:
        mentions = extract_all(get_config().notes_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(mentions, indent=2, ensure_ascii=False), encoding="utf-8")

    registry = merge_mentions(mentions)
    save_registry(registry)

    print(f"\n{len(mentions)} mentions -> {len(registry)} projects  (saved {registry_file()})\n")
    for r in registry.values():
        trail = " -> ".join(h["status"] for h in r["history"])
        print(f"{r['name']:<16} {r['status']:<10} as of {r['as_of']}  metric: {r['key_metric'] or '-'}")
        print(f"{'':<16} history: {trail}   [{r['source']}]")
    return registry


if __name__ == "__main__":
    run("--merge-only" in sys.argv)