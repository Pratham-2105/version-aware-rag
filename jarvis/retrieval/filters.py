"""Metadata filters in Chroma's syntax, usable by BOTH retrievers.

Chroma evaluates these natively; BM25Index evaluates them with matches().
One filter dict -> identical scoping on the dense and sparse sides (same idea
as the Stage 4B is_latest filter, now with more than one condition).
"""


def folder_filter(folders):
    """None = no scoping. An EMPTY scope is a caller bug, not 'search everything'."""
    if folders is None:
        return None
    if not folders:
        raise ValueError("empty folder scope; skip retrieval instead of filtering on nothing")
    return {"folder": {"$in": sorted(folders)}}


def combine_where(*filters):
    """Chroma needs $and for more than one condition."""
    parts = [f for f in filters if f]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return {"$and": parts}


def matches(meta, where):
    """Python evaluation of the Chroma operators we use: plain equality,
    $eq, $ne, $in, $nin, $and, $or."""
    for key, cond in where.items():
        if key == "$and":
            if not all(matches(meta, w) for w in cond):
                return False
        elif key == "$or":
            if not any(matches(meta, w) for w in cond):
                return False
        elif isinstance(cond, dict):
            value = meta.get(key)
            for op, target in cond.items():
                if op == "$eq":
                    ok = value == target
                elif op == "$ne":
                    ok = value != target
                elif op == "$in":
                    ok = value in target
                elif op == "$nin":
                    ok = value not in target
                else:
                    raise ValueError(f"unsupported filter operator {op}")
                if not ok:
                    return False
        elif meta.get(key) != cond:
            return False
    return True