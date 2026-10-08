"""Stage 6 — tests for the deterministic parts of the agent (no LLM, no Chroma)."""
from jarvis.agent import agent as agent_module
from jarvis.agent.agent import REFUSAL, check_citations, judge
from jarvis.agent.tools import TOOLS, format_hits, format_record, metric_changes, status_changes

RECORD = {
    "name": "QubitML",
    "description": "Quantum ML experiments",
    "status": "paused",
    "status_evidence": "",
    "status_reason": "focus on internships",
    "status_reason_source": "handovers\\arjun_master_handoff_oct2026.md",
    "next_step": "",
    "as_of": "2026-10-01",
    "source": "handovers\\arjun_master_handoff_oct2026.md",
    "key_metric": "",
    "key_metric_source": "",
    "tech": ["Python", "Qiskit"],
    "history": [
        {"version_date": "2026-06-01", "date_source": "filename", "status": "active", "key_metric": ""},
        {"version_date": "2026-08-01", "date_source": "filename", "status": "active", "key_metric": "70%"},
        {"version_date": "2026-09-01", "date_source": "filename", "status": "unclear", "key_metric": ""},
        {"version_date": "2026-09-30", "date_source": "mtime", "status": "paused", "key_metric": "99%"},
        {"version_date": "2026-10-01", "date_source": "filename", "status": "paused", "key_metric": "72%"},
    ],
}


# ---- tool schemas: this is what the model actually sees ----

def test_tool_names():
    assert [t.name for t in TOOLS] == ["search_notes", "get_project_status", "list_projects"]


def test_search_notes_mode_is_an_enum():
    schema = TOOLS[0].args
    assert set(schema["mode"]["enum"]) == {"current", "history", "any"}


# ---- formatting ----

def test_list_projects_has_explicit_all():
    schema = TOOLS[2].args
    assert "all" in schema["status"]["enum"]


def test_status_changes_spans_and_hides_weak_dates():
    # mtime-dated mention (2026-09-30) is dropped; 'unclear' is skipped
    assert status_changes(RECORD["history"]) == "active (2026-06-01 to 2026-08-01) -> paused (2026-10-01)"


def test_metric_changes_ignores_weak_dates():
    assert metric_changes(RECORD["history"]) == "70% (2026-08-01) -> 72% (2026-10-01)"


def test_metric_changes_empty_when_unchanged():
    one = [{"version_date": "2026-10-01", "date_source": "filename", "status": "done", "key_metric": "91.3%"}]
    assert metric_changes(one) == ""


def test_format_record_uses_forward_slashes_and_skips_empty_fields():
    text = format_record(RECORD)
    assert "SOURCE: handovers/arjun_master_handoff_oct2026.md" in text
    assert "\\" not in text
    assert "key metric:" not in text and "next step" not in text
    assert "reason: focus on internships" in text


def test_format_hits_labels_every_chunk():
    results = {
        "documents": [["CF rating 1550", "CF rating 1510"]],
        "metadatas": [[
            {"source": "handovers\\oct.md", "header_path": "Ratings", "version_date": "2026-10-01",
             "date_source": "filename", "group_size": 4, "is_latest": True},
            {"source": "handovers\\aug.md", "header_path": "Ratings", "version_date": "2026-08-01",
             "date_source": "filename", "group_size": 4, "is_latest": False},
        ]],
    }
    text = format_hits(results)
    assert text.count("SOURCE: ") == 2
    assert "(2026-10-01, latest version)" in text
    assert "(2026-08-01, older version)" in text


# ---- citation enforcement ----

TOOL_TEXT = "SOURCE: handovers/arjun_master_handoff_oct2026.md > Ratings (2026-10-01)\nCF 1550"


def test_valid_citation_full_path_or_bare_name():
    assert check_citations("1550 [handovers/arjun_master_handoff_oct2026.md]", TOOL_TEXT)["valid"]
    assert check_citations("1550 (arjun_master_handoff_oct2026.md)", TOOL_TEXT)["valid"]


def test_invented_citation_detected():
    c = check_citations("1550 [handovers/arjun_master_handoff_dec2026.md]", TOOL_TEXT)
    assert c == {"valid": [], "invented": ["arjun_master_handoff_dec2026.md"]}


def test_judge_blocks_uncited_answer():
    calls = [{"name": "search_notes", "args": {}}]
    assert judge("It is 1550.", calls, TOOL_TEXT) == ("uncited", REFUSAL)


def test_judge_blocks_answer_without_any_tool_call():
    assert judge("It is 1550 [x.md].", [], "") == ("no_tool", REFUSAL)


def test_judge_keeps_refusal_and_cited_answer():
    calls = [{"name": "search_notes", "args": {}}]
    assert judge(REFUSAL, calls, TOOL_TEXT)[0] == "refused"
    draft = "1550 [handovers/arjun_master_handoff_oct2026.md]"
    assert judge(draft, calls, TOOL_TEXT) == ("ok", draft)


def test_refusal_without_search_is_flagged():
    assert judge(REFUSAL, [], "") == ("refused_no_search", REFUSAL)


def test_enforcement_switch(monkeypatch):
    monkeypatch.setattr(agent_module, "ENFORCE_CITATIONS", False)
    calls = [{"name": "search_notes", "args": {}}]
    assert judge("It is 1550.", calls, TOOL_TEXT) == ("uncited", "It is 1550.")