from src.registry.store import clean_mention, merge_mentions, normalize_name


def mention(name="PixelNet", status="active", date="2026-08-01", date_source="filename",
            source="handovers/h.md", **fields):
    m = {"name": name, "description": "", "status_evidence": "", "status": status,
         "status_reason": "", "next_step": "", "key_metric": "", "tech": [],
         "source": source, "version_date": date, "date_source": date_source,
         "doc_group_id": "g", "is_latest": False}
    m.update(fields)
    return m


def test_normalize_strips_subtitle_and_spacing():
    assert normalize_name("PixelNet — From-Scratch Image Classifier") == "pixelnet"
    assert normalize_name("Pixel Net project") == "pixelnet"


def test_placeholders_become_empty_and_tech_dedups():
    m = clean_mention(mention(key_metric="N/A", tech=["N/A", "NumPy", "numpy"]))
    assert m["key_metric"] == ""
    assert [t.lower() for t in m["tech"]] == ["numpy"]


def test_metric_without_number_is_dropped():
    assert clean_mention(mention(key_metric="Real-time chat feature"))["key_metric"] == ""


def test_status_word_is_not_a_reason():
    assert clean_mention(mention(status_reason="PAUSED"))["status_reason"] == ""


def test_newest_date_wins():
    reg = merge_mentions([mention(status="active", date="2026-09-01"),
                          mention(status="paused", date="2026-10-01")])
    assert reg["pixelnet"]["status"] == "paused"


def test_strong_date_beats_later_mtime():
    reg = merge_mentions([
        mention(status="paused", date="2026-10-01"),
        mention(status="active", date="2026-10-05", date_source="mtime", source="projects/pixelnet.md"),
    ])
    assert reg["pixelnet"]["status"] == "paused"


def test_unclear_never_overrides_real_status():
    reg = merge_mentions([mention(status="done", date="2026-09-01"),
                          mention(status="unclear", date="2026-10-01")])
    assert reg["pixelnet"]["status"] == "done"


def test_reason_never_borrowed_from_different_status():
    reg = merge_mentions([
        mention(status="active", date="2026-09-01", status_reason="for internships"),
        mention(status="paused", date="2026-10-01"),
    ])
    assert reg["pixelnet"]["status_reason"] == ""


def test_reason_taken_from_lower_ranked_same_status_mention():
    reg = merge_mentions([
        mention(status="paused", date="2026-09-30", date_source="mtime",
                source="projects/pixelnet.md", status_reason="too theoretical"),
        mention(status="paused", date="2026-10-01"),
    ])
    assert reg["pixelnet"]["status_reason"] == "too theoretical"


def test_input_mentions_not_mutated():
    raw = mention(key_metric="N/A")
    merge_mentions([raw])
    assert raw["key_metric"] == "N/A"