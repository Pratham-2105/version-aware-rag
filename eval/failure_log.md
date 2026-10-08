# Failure Log

Every wrong answer, why it was wrong, and which stage fixed it (or didn't).
Source of truth for numbers: `eval/results/`. Config unless noted: qwen2.5:7b, nomic-embed-text, top_k = 5.

**Correction (found 7 Oct 2026):** until the end of Stage 4, `answer_question()` (the function the eval calls) never passed temperature or seed to Ollama, so every run up to Stage 4 Run 3 used Ollama's default temperature, not 0. See "Noise check".

---

## Baseline dense — 1 Oct 2026

`baseline_dense_20261001_170534.json` — failed 20/45: 3, 5, 7, 8, 11, 13, 15, 16, 18, 20, 21, 25, 27, 29, 30, 32, 33, 41, 42, 44

| ID | Question | What happened | Fixed in |
|---|---|---|---|
| 8 | Current Codeforces rating? | Answered 1510 (correct: 1550). All four handoffs came back at near-identical distances; the October chunk was in context but nothing marked it as newest. | Stage 4B |
| 5 | Where is DataLens deployed? | Answered from an older handoff ("not yet deployed"). Correct: Railway. | Stage 4A |
| 3 | PixelNet's optimizer? | Right file, but the optimizer chunk wasn't in the top 5. | Stage 4A |

- Duplicates eat top-k slots: the `(1)` and `_backup` copies appear as pairs, so only 3–4 unique chunks reach the model.
- No notion of time: historical questions find a right source 83.3% of the time but are answered correctly only 33.3%.
- Refusals are solid (6/6).

---

## Stage 3 — dedup + grouping (7 Oct 2026)

`stage3_dedup_grouping_20261007_145452.json` — fixed 8, 16; no regressions.

- **Q8 was fixed by luck:** removing the `(1)` duplicate freed a slot and the model happened to prefer the October chunk. Nothing ranked by date yet.
- Source hit unchanged (76.9%): dedup removes noise but can't surface new sources.
- 9 of 22 files are dated by modified time (weak), so dates are only compared within a document family.
- Grouping false positive: the two chronicles (diary entries) formed one family. *Fixed in Stage 6.5: `personal/` is marked not versioned.*

---

## Stage 4A — hybrid BM25 + dense (7 Oct 2026)

`stage4a_hybrid_20261007_153907.json` — fixed 3, 5, 11, 25, 29, 33, 41, 42, 44; regressed 8, 12.

- **Q8 regressed:** "cf" and "rating" appear in every handoff, so BM25 pulled old versions back in. Better recall made the version problem worse.
- Cross-document went 16.7% → 66.7%: named-entity recall was the bottleneck.
- **Bug:** BM25 gives negative scores to words in more than half the corpus, and a `score <= 0` cutoff silently dropped all keyword results for common-word queries. Fixed by using word overlap, not score sign.

---

## Stage 4B — version-aware retrieval (7 Oct 2026)

An intent classifier (current / historical / lookup), an `is_latest` filter for current-state questions on both retrievers, and dates plus chronological order in the context.

**Run 1** (`stage4b_version_aware_20261007_155101.json`) — 82.2%. Fixed 8 (by design this time), 12, 13; no regressions.

- **Scoring errors:** Q43 passed wrongly (the key fact "june" appeared in a wrong answer); Q18 failed wrongly ("machine learning" vs "ml"). Key facts were not edited, since that would invalidate earlier rows.
- **Classifier: 12/15** time-sensitive questions. Misses: Q14, Q18, Q43 (Q43's misroute caused a wrong answer). The regex was deliberately not tuned to the test phrasings.
- Q20 and Q21 retrieved only one end of the change they asked about.

**Run 2** (`stage4b_version_expansion_20261007_155816.json`) — 77.8%. Version expansion pulls in missing versions for history questions. Q20 then got all four handoffs and Q21 got resume v2, but both answers were still wrong: the evidence was there, in order, and the 7B model mixed up which source said what. **Model failure, not retrieval.**

**Run 3** (`stage4b_version_expansion_20261007_160237.json`) — 80.0%. The "fixed seed" was added to the chat loop, not to the eval path, so this run is superseded by the noise check.

---

## Noise check — Stage 4, 3 runs (7 Oct 2026)

`noise_check_a/b/c_20261007_*.json`, after fixing temperature and seed on the eval path.

| Run | Answer | Current state | Failed IDs |
|---|---|---|---|
| a | 80.0% | 7/9 | 7, 12, 15, 18, 21, 27, 30, 32, 33 |
| b | 82.2% | 8/9 | 7, 15, 18, 21, 27, 30, 32, 33 |
| c | 82.2% | 8/9 | 7, 15, 18, 21, 27, 30, 32, 33 |
| **Mean** | **81.5%** | **85.2%** | refusals 100% |

- Eight questions fail every time; Q12 failed once. Even at temperature 0 with a seed, a one-question difference is noise.
- The old refusal drop (5/6) was temperature noise.

Lesson: check that the config you think you're testing is the one that actually runs.

**Still failing after Stage 4**

| ID | Question | Cause |
|---|---|---|
| 7 | PixelNet parameter count | Right file, wrong chunk |
| 15 | Current tech stack | Answered NoteFlow's stack instead of Arjun's |
| 18 | When/why StudyBuddy was abandoned | Correct answer, scoring miss |
| 21 | Resume v1 → v2 | Evidence present, model mixed up versions |
| 27 | Projects with Python + ML | Resume chunks outranked project files |
| 30 | DP problems solved | Answered from the contest log |
| 32 | Who is Rohan? | Handoffs mentioning Rohan outranked the chronicles |
| 33 | Sem 5 subjects | Not yet analysed (the agent answers it) |

---

## Stage 5 — project registry (7 Oct 2026)

Checked by hand, not in the 45-question eval. The model reads each project file and handover once and fills a fixed form; code merges one record per project, newest wins.

Status 5/5, key result 5/5, status-change dates 4/5 (QubitML's pause shows a file's modified time), real reasons 2/5 (the model invents reasons when none are stated).

Bugs found while building:
- The build hung: qwen extended the tech list forever. Fixed with a token cap, a timeout, and a maximum list length in the schema.
- "N/A" would have overwritten 91.3% as the newest metric. Placeholders now count as empty.
- Subtitled names split one project into several; a feature was stored as a metric; the status was copied as the reason. Each fixed in code or field order.

Lesson: constrained decoding enforces the shape of the output, not its meaning.

---

## Stage 6 — agent with tools (7 Oct 2026)

`stage6_agent_qwen_*` (v1), `stage6_agent_v2_qwen_*` (v2), `stage6_agent_final_qwen_a/b/c_*` (final)

A model picks between three tools (search with a time mode, project status, list projects); code checks every citation.

- **v1 — 57.8%.** Routed all 15 time-sensitive questions correctly, but used the registry for non-status questions, refused without searching, and read the right files wrong.
- **v2 — 68.9%.** Registry tools limited to status questions, weak dates hidden, and code says "search first" once when the model refuses without searching.
- **Final — 75.6% in all three runs.** Code asks once for citations before blocking an uncited answer. Failed: 7, 13, 15, 18, 20, 21, 30, 32, 37, 39, 43.

| Category | Pipeline | Agent |
|---|---|---|
| Simple lookup | 76.9 | 84.6 |
| Current state | 85.2 | 66.7 |
| Change over time | 66.7 | 50.0 |
| Project status | 100 | 100 |
| Across documents | 66.7 | 83.3 |
| Should refuse | 100 | 66.7 |
| **Overall** | **81.5** | **75.6** |

The agent wins where writing its own queries helps (it fixes Q27 and Q33), and loses on reading and judgement: wrong fact from the right file (7, 13, 15, 30), only one end of a change (20), guessing after saying the notes don't say (37, 39). Q43 is a real limit: a present-tense question whose answer is in the June plan, which the "current" mode filters out.

Lesson: a prompt can ask for a rule, but only code can enforce it.

---

## Stage 6.5 — router (8 Oct 2026)

`stage65_regression_*`, `stage65_router_scoped_*`, `stage65_router_unscoped_*` (single runs)

A local model reads each message first: rewritten question, 1–2 life areas, time mode, message type. Folders, areas and privacy come from `config.yaml`.

| Category | Pipeline | Router, search limited | Router |
|---|---|---|---|
| Simple lookup | 76.9 | 61.5 | 84.6 |
| Current state | 88.9 | 66.7 | 88.9 |
| Change over time | 66.7 | 50.0 | 66.7 |
| Project status | 100 | 100 | 100 |
| Across documents | 66.7 | 50.0 | 50.0 |
| Should refuse | 100 | 100 | 100 |
| **Overall** | **82.2** | **68.9** | **82.2** |

- **Regression run:** the same failed IDs as the noise check, so re-indexing didn't touch V1.
- **Search limited to the chosen areas cost 13 points,** all recall (source found 92.3% → 82.1%). Q12 and Q43 were routed to personal only, so only `personal/` was searched. 7 of 45 factual questions went to personal, because the prompt says "include personal when unsure". That bias is cheap for choosing a model, expensive as a search filter. Q2, Q4, Q20, Q34 not yet analysed.
- **Search not limited matched the pipeline** (fixed 33, broke 44: noise).
- **Time routing 11/15,** one fewer than the regex.

Decision: ship with the search not limited. The area picks tone and which model may see the message, not what gets searched.

Lesson: a filter is only as safe as whatever decides it. The latest-version filter reads dates computed by code; the area filter read a 7B model's guess.

---

## Stage 7 — MCP server (8 Oct 2026)

Not in the 45-question eval: the server returns search results, not answers. Checked with in-memory tests and with `jarvis check`, which starts the server as a real subprocess over stdio.

The first run passed: three tools listed, history search returned every handover in date order, registry tools returned QubitML paused with its reason, and nothing came back from `personal/`. Three findings:

- **Versions are tracked per file, not per section.** For "current Codeforces rating", an August entry of `dsa/contest_log.md` ranked above the October handover. The log is one undated file, so it counts as its own latest version, while its history lives inside it as dated headings.
- **Privacy is per folder, and files mix content.** Nothing came back from `personal/`, but the handovers' "Mental State" sections did, because `handovers/` is shareable.
- **The sample vault contradicts itself.** The contest log reaches 1510 on 7 September; the 18 August handover already says 1510. No golden question depends on it.

---

## Open items

- One eval run on a stronger hosted model, to measure how much of the remaining gap is the 7B model.
- A header date in the same month as the filename date should win (the October handover says "October 10" but is stored as 10-01).
- The generated overview still shows weak dates in its status history.
- An LLM judge as a second scorer, for key-fact scoring errors (Q18, Q43).
- Analyse pipeline Q33 and limited-search failures 2, 4, 20, 34.
- Run the router eval on `eval/router_messages.json`; private recall must be 100%.
- Designed, not built: non-private messages search every shareable folder; regex-first time routing.
- Section-level versioning for log-style files, and section-level privacy (private section names in `config.yaml`).
- Try the MCP server inside Claude Desktop itself (so far tested with the MCP SDK's client).