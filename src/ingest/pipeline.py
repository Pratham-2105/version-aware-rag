"""Ingestion pipeline: load -> date -> dedup -> group -> chunk.

Each chunk carries file-level metadata so retrieval can filter and rank
by version without re-reading the files.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.ingest.chunker import chunk_document
from src.ingest.dedup import deduplicate
from src.ingest.grouping import apply_unversioned, group_documents
from src.ingest.loaders import load_vault
from src.ingest.metadata import resolve_version_date, top_folder


def print_report(report):
    print("=" * 60)
    print("INGESTION REPORT")
    print("=" * 60)
    print(f"Files loaded:            {report['files_loaded']}")
    print(f"Exact duplicates:        {len(report['exact'])}")
    for dup, keep in report["exact"].items():
        print(f"    {dup}  ->  {keep}")
    print(f"Near duplicates:         {len(report['near'])}")
    for dup, keep in report["near"].items():
        print(f"    {dup}  ->  {keep}")
    print(f"Files kept:              {report['files_kept']}")
    print(f"Date sources:            {dict(report['date_sources'])}")
    print(f"Document groups:         {report['groups_total']}")
    print("Multi-version families:")
    for group_id, members in report["families"].items():
        print(f"    {group_id}")
        for path, date, latest in members:
            flag = "  <- latest" if latest else ""
            print(f"        {date}  {path}{flag}")
    print(f"Chunks created:          {report['chunks']}")
    print("=" * 60)


def run_ingestion(vault_path, verbose=True, unversioned_folders=()):
    vault_path = Path(vault_path)

    files = load_vault(vault_path)

    date_info = {p: resolve_version_date(p, t, vault_path) for p, t in files.items()}
    dates = {p: d for p, (d, _) in date_info.items()}

    kept, dup_report = deduplicate(files, dates)
    groups = group_documents(list(kept), dates)
    groups = apply_unversioned(groups, unversioned_folders)

    chunks = []
    for path, text in kept.items():
        file_meta = {
            "version_date": dates[path],
            "date_source": date_info[path][1],
            **groups[path],
        }
        for chunk in chunk_document(text, path):
            chunk.update(file_meta)
            chunk["folder"] = top_folder(chunk["source"])
            chunks.append(chunk)

    if verbose:
        families = {}
        for path, g in groups.items():
            if g["group_size"] > 1:
                families.setdefault(g["doc_group_id"], []).append(
                    (path, dates[path], g["is_latest"])
                )
        for members in families.values():
            members.sort(key=lambda m: m[1])

        print_report({
            "files_loaded": len(files),
            "exact": dup_report["exact"],
            "near": dup_report["near"],
            "files_kept": len(kept),
            "date_sources": Counter(date_info[p][1] for p in kept),
            "groups_total": len({g["doc_group_id"] for g in groups.values()}),
            "families": families,
            "chunks": len(chunks),
        })

    return chunks


if __name__ == "__main__":
    run_ingestion("data/sample-vault")