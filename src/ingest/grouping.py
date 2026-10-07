"""Group files into document families and rank versions within each family.

Family key = folder + filename stem with dates, version tags (v1, v2) and copy
markers stripped:
    handovers/arjun_master_handoff_aug2026.md -> handovers/arjun_master_handoff
    career/resume_v2_oct2026.md               -> career/resume
"""
import re
from collections import defaultdict
from pathlib import Path

from src.ingest.dedup import COPY_MARKERS
from src.ingest.metadata import FILENAME_DATE

VERSION_TOKEN = re.compile(r"(?<![a-z])v\d+(?![a-z0-9])")


def family_key(relative_path):
    path = Path(relative_path.replace("\\", "/"))
    stem = path.stem.lower()

    stem = COPY_MARKERS.sub("", stem)
    stem = FILENAME_DATE.sub("", stem)
    stem = VERSION_TOKEN.sub("", stem)
    stem = re.sub(r"[_\-\s]+", "_", stem).strip("_")

    folder = path.parent.as_posix()
    return stem if folder == "." else f"{folder}/{stem}"


def group_documents(paths, dates):
    """paths: list of relative paths, dates: {path: iso_date}
    Returns {path: {doc_group_id, group_size, version_rank, is_latest}}.
    version_rank 1 = newest in its family."""
    families = defaultdict(list)
    for path in paths:
        families[family_key(path)].append(path)

    info = {}
    for group_id, members in families.items():
        members.sort(key=lambda p: dates[p], reverse=True)
        newest_date = dates[members[0]]
        for rank, path in enumerate(members, start=1):
            info[path] = {
                "doc_group_id": group_id,
                "group_size": len(members),
                "version_rank": rank,
                "is_latest": dates[path] == newest_date,
            }
    return info