"""Exact and near-duplicate detection at the FILE level.

Exact duplicates: same SHA-256 of normalized text.
Near-duplicates:  word-shingle Jaccard similarity >= threshold
                  AND the same resolved version date
                  (so a newer version with one changed fact is never dropped).
"""
import hashlib
import re
from collections import defaultdict
from pathlib import Path

SHINGLE_SIZE = 5
NEAR_DUP_THRESHOLD = 0.85
REPORT_SCORE_FLOOR = 0.5  # pairs above this are listed in the report for inspection

COPY_MARKERS = re.compile(r"(\(\d+\)|copy|backup|_bak\b|\bold\b)", re.IGNORECASE)


def normalize_text(text):
    text = text.replace("\r\n", "\n").lower()
    return re.sub(r"\s+", " ", text).strip()


def content_hash(text):
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def shingles(text, k=SHINGLE_SIZE):
    words = normalize_text(text).split()
    if len(words) < k:
        return {" ".join(words)}
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def jaccard(a, b):
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def canonical_sort_key(path):
    """Sort so the 'real' file comes first: no copy marker, then shorter path."""
    has_marker = bool(COPY_MARKERS.search(Path(path).stem))
    return (has_marker, len(path), path)


def find_exact_duplicates(files):
    """files: {path: text} -> {duplicate_path: canonical_path}"""
    by_hash = defaultdict(list)
    for path, text in files.items():
        by_hash[content_hash(text)].append(path)

    dup_map = {}
    for paths in by_hash.values():
        if len(paths) < 2:
            continue
        paths.sort(key=canonical_sort_key)
        for duplicate in paths[1:]:
            dup_map[duplicate] = paths[0]
    return dup_map


def find_near_duplicates(files, dates, threshold=NEAR_DUP_THRESHOLD):
    """Returns ({duplicate_path: canonical_path}, [(a, b, score), ...])."""
    paths = sorted(files)
    shingle_sets = {p: shingles(files[p]) for p in paths}

    dup_map = {}
    scores = []
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            a, b = paths[i], paths[j]
            score = jaccard(shingle_sets[a], shingle_sets[b])
            if score >= REPORT_SCORE_FLOOR:
                scores.append((a, b, round(score, 3)))
            if score >= threshold and dates[a] == dates[b]:
                keep, drop = sorted([a, b], key=canonical_sort_key)
                dup_map.setdefault(drop, keep)
    return dup_map, scores


def deduplicate(files, dates):
    """files: {path: text}, dates: {path: iso_date}
    Returns (kept_files, report)."""
    exact = find_exact_duplicates(files)
    remaining = {p: t for p, t in files.items() if p not in exact}

    near, scores = find_near_duplicates(remaining, dates)
    kept = {p: t for p, t in remaining.items() if p not in near}

    report = {"exact": exact, "near": near, "similarity_scores": scores}
    return kept, report