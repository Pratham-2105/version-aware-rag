import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.ingest.pipeline import run_ingestion
from jarvis.registry.extractor import build_extraction_chain, extract_from_document
from jarvis.registry.store import REGISTRY_PATH, merge_mentions, save_registry

VAULT_PATH = Path("data/sample-vault/")
REGISTRY_FOLDERS = {"projects", "handovers"}
MENTIONS_PATH = REGISTRY_PATH.parent / "mentions.json"
META_KEYS = ("version_date", "date_source", "doc_group_id", "is_latest")


def documents_to_extract(vault_path):
    """One entry per KEPT document (dedup already applied), with its version metadata."""
    chunks = run_ingestion(vault_path, verbose=False)
    docs = {}
    for c in chunks:
        source = c["source"]
        folder = source.replace("\\", "/").split("/")[0]
        if folder in REGISTRY_FOLDERS and source not in docs:
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
        except Exception as e:                      # one bad doc must not kill the build
            print(f"[{i}/{len(docs)}] FAILED {source}: {e}")
            continue
        names = ", ".join(f"{m['name']}={m['status']}" for m in found) or "(none)"
        print(f"[{i}/{len(docs)}] {source} ({len(text)} chars, {time.time() - start:.1f}s) -> {names}")
        mentions.extend(found)
    return mentions


if __name__ == "__main__":
    if "--merge-only" in sys.argv:
        mentions = json.loads(MENTIONS_PATH.read_text(encoding="utf-8"))
    else:
        mentions = extract_all(VAULT_PATH)
        MENTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        MENTIONS_PATH.write_text(json.dumps(mentions, indent=2, ensure_ascii=False), encoding="utf-8")

    registry = merge_mentions(mentions)
    save_registry(registry)

    print(f"\n{len(mentions)} mentions -> {len(registry)} projects  (saved {REGISTRY_PATH})\n")
    for r in registry.values():
        trail = " -> ".join(h["status"] for h in r["history"])
        print(f"{r['name']:<16} {r['status']:<10} as of {r['as_of']}  metric: {r['key_metric'] or '-'}")
        print(f"{'':<16} history: {trail}   [{r['source']}]")