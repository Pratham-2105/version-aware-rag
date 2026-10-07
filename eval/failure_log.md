# Failure Log

Every wrong answer, why it was wrong, and which stage fixed it (or didn't).
Source of truth for numbers: `eval/results/`.

Config for every run unless noted: qwen2.5:7b, nomic-embed-text, top_k = 5.

**Correction (found 7 Oct 2026, see "Noise check"):** until the end of Stage 4, `answer_question()` (the function the eval calls) never passed temperature or seed to Ollama, so every run up to and including Stage 4 Run 3 used Ollama's default temperature, not 0. Notes below that say "temperature 0" or "seed fixed" for those runs describe what was intended, not what ran. The text is kept as written at the time, with corrections marked.

---

## Baseline dense — 1 Oct 2026

Results file: `baseline_dense_20261001_170534.json`

**Failed (20/45):** 3, 5, 7, 8, 11, 13, 15, 16, 18, 20, 21, 25, 27, 29, 30, 32, 33, 41, 42, 44

| ID | Question | What happened | Failure type | Fixed in |
|---|---|---|---|---|
| 8 | Current Codeforces rating? | Answered **1510** (correct: 1550). All four handoffs retrieved at near-identical distances (0.30–0.33); the model cited both copies of the August handoff. The October chunk with 1550 was in context but nothing marked it as newest. | Stale version chosen | Stage 4B (deterministically) |
| 5 | Where is DataLens deployed? | `datalens_handover.md` retrieved first, but the model answered from an older handoff saying "not yet deployed". Correct: Railway. | Stale version chosen | Stage 4A |
| 3 | What optimizer does PixelNet use? | Right file retrieved, but the chunk with the optimizer was not in the top 5; slots taken by duplicates and handoffs mentioning PixelNet. | Right file, wrong chunk | Stage 4A |

Note: observations for IDs 3 and 5 come from debug runs on the same pipeline.

**Patterns**
- Duplicates eat top-k slots: the Aug handoff and its `(1)` copy, and the Oct career plan and its `_backup`, appear as pairs, so only 3–4 unique chunks reach the model.
- No notion of time: historical questions find a right source 83.3% of the time but are answered correctly only 33.3%.
- Cross-document is weakest (16.7% answer, 50% source).
- Refusals are solid (6/6), including both skip-folder questions.

---

## Stage 3 — dedup + grouping (7 Oct 2026)

Results file: `stage3_dedup_grouping_20261007_145452.json`

**Fixed:** 8, 16. **Regressions:** none. **Still failing:** 18 questions.

- **Q8** now answers 1550, but the fix is incidental: removing the `(1)` duplicate freed a top-5 slot and the model happened to prefer the October chunk. No date ranking existed yet.
- **Q16** fixed by the same mechanism.
- **Q5** still answered from an older handoff.
- **Q3** right file, wrong chunk; not a version problem.
- Source hit unchanged at 76.9%: dedup removes noise but cannot surface new sources.

**Observations**
- `version_date` was in metadata but not shown to the model.
- 9 of 22 files are dated by modified time (weak); dates must only be compared within a document family.
- Grouping false positive: `chronicle_july2026` and `chronicle_sep2026` form one family although they are diary entries, not versions. Harmless only while "latest wins" is restricted to current-state questions.
- Near-duplicate detection is unit-tested only; both sample-vault duplicates turned out to be exact after normalization.

---

## Stage 4A — hybrid BM25 + dense, RRF (7 Oct 2026)

Results file: `stage4a_hybrid_20261007_153907.json`

**Fixed (9):** 3, 5, 11, 25, 29, 33, 41, 42, 44. **Regressed (2):** 8, 12. **Still failing:** 11 questions.

- **Q8 regressed.** "cf" and "rating" appear in all four handoffs, so BM25 pulled older versions back into the top 5. This confirmed the Stage 3 fix was luck and showed that better recall makes the version problem worse.
- **Q5 fixed by recall, not by versioning:** the right chunk reached the top 5 and the model chose it.
- **Historical stayed at 50% with 100% source hit:** right files, wrong answers. Dates were not visible to the model.
- **Cross-document** went from 16.7% to 66.7%: named-entity recall was the bottleneck.

**Bug found while building:** BM25 gives negative IDF to terms that appear in more than half the corpus. A `score <= 0` cutoff therefore returned zero BM25 results for common-word queries, silently degrading hybrid search to dense-only. Fixed by using token overlap with the query, not score sign, as the candidate condition. Caught by `test_bm25_where_filter`.

---

## Stage 4B — version-aware retrieval (7 Oct 2026)

Three changes, tested together: an intent classifier (current_state / historical / lookup), an `is_latest` filter for current-state questions applied to both retrievers, and chronological ordering plus visible dates in the context (with one added prompt rule: use the newest value for the current state, describe change in date order for history).

### Run 1 — without version expansion

Results file: `stage4b_version_aware_20261007_155101.json` — 37/45 (82.2%)

**Fixed:** 8, 12, 13. **Regressions:** none. **Failed:** 7, 15, 18, 20, 21, 27, 30, 32.

- **Q8 fixed by design:** stale handoffs cannot enter the candidate pool for current-state questions.

**Scoring errors found by manual review of this run**
- **Q43 false pass.** The answer said Arjun *is* planning to learn Next.js (wrong). It passed because the key fact `"june"` appeared in "from June 2026".
- **Q18 false fail.** The answer was correct but wrote "machine learning" instead of the key fact `"ml"`.
- Overall score unchanged by these two, but verified current-state accuracy for this run was 7/9 (77.8%, not 88.9%) and historical 4/6 (66.7%, not 50%).
- Key facts were **not** edited: changing the metric mid-project would invalidate earlier rows. An LLM judge is planned as a second scorer.

**Classifier accuracy on the 15 time-sensitive questions: 12/15 (80%)**
- Q14 "How many LeetCode problems has Arjun solved?" → lookup (answered correctly anyway).
- Q43 "Is Arjun planning to learn Next.js?" → lookup. This misrouting caused the wrong answer: the June plan was not filtered out.
- Q18 "When was StudyBuddy abandoned and why?" → lookup (answer correct).
- The regex was deliberately **not** tuned to these phrasings; that would overfit the classifier to the test set.

**Remaining historical failures had one shared cause:** Q20 retrieved the October handoff (paused) but not September (active); Q21 retrieved resume v1 but not v2. A "how did X change" question needs both ends of the change, and relevance ranking returned only one version.

### Run 2 — with version expansion

Results file: `stage4b_version_expansion_20261007_155816.json` — 35/45 (77.8%)

Version expansion: for historical questions, every multi-version family in the results gets its missing versions added (best BM25-matching chunk from each), capped at 10 chunks.

- **Expansion worked as designed.** Q20 now retrieved all four handoffs in date order; Q21 retrieved resume v2.
- **Both answers were still wrong.** Q20 claimed QubitML was paused as of 22 September; Q21 attributed v1's skill list to v2. The evidence was present and ordered — the 7B model mislabelled which source said what. **Model-capacity failure, not retrieval.**
- **Q43 and Q44 flipped to failing**, but both are routed as lookup, so their retrieval was identical to Run 1. The only thing that could change was the model output. Concluded at the time that the model is not deterministic across runs. *Correction: this run was at Ollama's default temperature, so the flips were expected sampling, not GPU nondeterminism. True temperature-0 noise was measured later and is smaller.*

### Run 3 — with version expansion, "seed fixed"

Results file: `stage4b_version_expansion_20261007_160237.json` — 36/45 (80.0%)

Intended change: Ollama options `{"temperature": 0, "seed": 42}`. *Correction: the options were added to the CLI chat loop, not to `answer_question()`, so this run also used the default temperature. It is superseded by the noise check below.*

**Failed (9):** 7, 15, 20, 21, 27, 30, 32, 33, 37

- Q33 and Q37 failed here for the first time, on the lookup path whose retrieval had not changed. See the noise check for what happened next.

---

## Noise check — Stage 4 config, 3 runs (7 Oct 2026)

Results files: `noise_check_a_20261007_173045.json`, `noise_check_b_20261007_173420.json`, `noise_check_c_20261007_173824.json`

While building Stage 6 I found that `answer_question()` never passed temperature or seed to Ollama. Only the chat loop did, and the eval doesn't use it. After fixing it, the same Stage 4 setup was run three times.

| Run | Answer | Current state | Refusals | Failed IDs |
|---|---|---|---|---|
| a | 36/45 (80.0%) | 7/9 | 6/6 | 7, 12, 15, 18, 21, 27, 30, 32, 33 |
| b | 37/45 (82.2%) | 8/9 | 6/6 | 7, 15, 18, 21, 27, 30, 32, 33 |
| c | 37/45 (82.2%) | 8/9 | 6/6 | 7, 15, 18, 21, 27, 30, 32, 33 |
| **Mean** | **81.5%** | **85.2%** | **100%** | |

- **Eight questions fail every time:** 7, 15, 18, 21, 27, 30, 32, 33. These are the real failures (18 is the known "machine learning" vs "ml" scoring miss).
- **Q12 failed once in three.** That is the remaining noise: even at temperature 0 with a seed, the GPU can flip a near-tied token. A one-question difference (2.2 points overall, 11 points on the 9-question current-state category) is noise.
- **Q20 and Q37 passed all three times,** so their failures in Run 3 were temperature noise. So was the old 5/6 refusal score.
- **Q33 fails all three times,** so it is a real failure, not variance as Run 3 assumed.

Lesson: check that the config you think you're testing is the one the code actually runs. The seed fix was in the file, just not on the path the eval used.

### Still failing after Stage 4 (3 clean runs)

| ID | Question | Cause | Next fix |
|---|---|---|---|
| 7 | PixelNet parameter count | Right file, wrong chunk | Larger top_k or section-level retrieval |
| 15 | Current tech stack | Answered NoteFlow's stack instead of Arjun's | Model / prompt |
| 18 | When StudyBuddy was abandoned and why | Answer correct; scoring miss ("machine learning" vs "ml") | LLM judge |
| 21 | Resume v1 → v2 | Evidence present; model mixed up versions | Stronger model |
| 27 | Projects with Python + ML | Project handovers not retrieved; resume chunks won | Recall on generic queries (the agent fixes it) |
| 30 | DP problems solved | `dp_problems.md` retrieved, model answered from contest log | Model / prompt |
| 32 | Who is Rohan? | Chronicles not retrieved; handoffs mentioning Rohan outranked them | Recall |
| 33 | Sem 5 subjects | Fails every clean run; not yet analysed (the agent answers it, so the file is findable) | Check retrieved chunk |

---

## Stage 5 — project registry (7 Oct 2026)

Not part of the 45-question eval. Checked by hand against the vault files.

Setup: qwen2.5:7b reads each of the 9 files in `projects/` and `handovers/` once and fills in a fixed form per project (name, status, reason, key result). Code merges these into one record per project, newest version wins.

**Hand check of the 5 projects**

| Field | Correct |
|---|---|
| Status | 5/5 |
| Key result | 5/5 |
| Status-change dates | 4/5 |
| Reason for status | 2/5 real |

- **QubitML's pause date shows 2026-09-30,** the modified time of a file, instead of 2026-10-01 from the October handoff. The overview's history uses weak dates. *Stage 6 hides weak dates in the agent's view of the registry; the generated overview still shows them.*
- **Reasons:** only QubitML and StudyBuddy have a reason stated in the notes. For the three done or active projects the model fills in something anyway.

**Bugs found while building**
- **The build hung.** qwen kept extending the tech list forever inside valid JSON. Fixed with a token cap and a timeout (the fuse), and a maximum list length in the schema (the real fix: the grammar now stops the list).
- **"N/A" as a value.** The model wrote "N/A" for missing metrics, which would have overwritten 91.3% as the newest metric. Code now treats placeholder values as empty.
- **Subtitled names** ("NoteFlow — AI-Powered Note Intelligence") split one project into several. Code now strips subtitles before merging.
- **A feature stored as a metric.** Code now requires a metric to contain a number.
- **The status copied as the reason** ("DONE"). The field was renamed `status_reason`, and the form now asks for the description and evidence before the status, since fields are generated in order.

Lesson: constrained decoding enforces the shape of the output, not its meaning. Fields picked from a fixed list are reliable; free text needs checking in code.

---

## Stage 6 — agent with tools (7 Oct 2026)

Results files: `stage6_agent_qwen_20261007_183109.json` (v1), `stage6_agent_v2_qwen_20261007_184124.json` (v2), `stage6_agent_final_qwen_a/b/c_*.json` (final)

The agent uses the same retrieval and registry as the pipeline, but a model decides which tool to call. Three tools: search_notes (with a time mode: current, history or any), get_project_status and list_projects. Code checks that every answer cites a file the tools actually returned. All runs on qwen2.5:7b, temperature 0, seed 42 (this time on the path that actually runs).

The 5-question checkpoint passed on the first try: right tool and right mode every time, all answers cited. The full 45 questions told a different story.

**Version 1 — 57.8%.** The model routed all 15 time-sensitive questions correctly (the regex classifier gets 12), but end-to-end it was far worse than the pipeline. Sorting the 19 failures by cause:
- **Six used the registry for questions that had nothing to do with status:** get_project_status("web development"), the registry for PixelNet's accuracy history. Q27 passed an empty status that the tool rejected.
- **Four refused without searching at all.**
- **Five retrieved the right file and then read it wrong.**
- **Two said "not stated" and then guessed anyway.**
- **Q20 answered "paused on 2026-09-30",** the registry's weak-date bug from Stage 5 leaking through.

**Version 2 — 68.9%.** The fixes targeted failure types, not specific questions:
- registry tools described as status-only
- list_projects given an explicit "all" option
- weak dates hidden from registry history (the same rule search already used)
- a metric history line
- one code-sent follow-up ("search first") when the model refuses without searching

This fixed 4, 12, 17, 27 and 29, with no regressions. But 5 answers were now blocked as uncited, and reading them showed that 3 (Q19, Q33, Q42) were correct: the model found the answer and forgot the brackets.

**Final — 75.6% in all three runs.** Code now asks once for citations before blocking. Nothing was blocked, and the citation retry recovered 19 and 42. Retries fired on 6 questions in every run (15, 19, 21: cite; 29, 40, 42: search then cite). The agent was frozen and committed before the three runs; all three gave the same score and the same failed IDs: 7, 13, 15, 18, 20, 21, 30, 32, 37, 39, 43.

| Category | Pipeline (mean of 3) | Agent (mean of 3) |
|---|---|---|
| Simple lookup | 76.9 | 84.6 |
| Current state | 85.2 | 66.7 |
| Change over time | 66.7 | 50.0 |
| Project status | 100 | 100 |
| Across documents | 66.7 | 83.3 |
| Should refuse | 100 | 66.7 |
| **Overall** | **81.5** | **75.6** |

- **Where the agent wins:** lookups and cross-document questions. It writes its own queries and can search more than once, which is how it fixes Q27 and Q33, two stable pipeline failures.
- **Where it loses:** the model's reading and judgement. It finds the right file and picks the wrong fact (7, 13, 15, 30), gives only the end date of a change (20), or guesses after saying the notes don't say (37, 39).
- **Q43 is a real routing limit.** "Is Arjun planning to learn Next.js?" is a present-tense question whose answer lives in the June plan, which the "current" mode filters out.

Lesson: a prompt can ask for a rule, but only code can enforce it. Both the "always search" and "always cite" rules were in the prompt from the start; the model followed them only after code checked and asked again.

---

## Open items

- Run the same 45 questions on a stronger hosted model, to see how much of the remaining gap (pipeline and agent) is the 7B model.
- The October handover's header says "October 10, 2026" but the filename rule stores 2026-10-01. A header date in the same month as the filename should win. Not changed yet, because it would move every earlier row.
- The generated project overview still shows weak (modified-time) dates in its status history.
- Key-fact scoring errors (Q18 false fail, Q43 false pass): an LLM judge, spot-checked by hand, as a second scorer.
- Q33 in the pipeline: find out why it fails every clean run when the agent answers it.