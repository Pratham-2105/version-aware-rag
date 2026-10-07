# Failure Log

Every wrong answer, why it was wrong, and which stage fixed it (or didn't).
Source of truth for numbers: `eval/results/`.

Config for every run unless noted: qwen2.5:7b (temperature 0), nomic-embed-text, top_k = 5.

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

### Run 1 — without version expansion, unseeded

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
- The regex was deliberately **not** tuned to these phrasings; that would overfit the classifier to the test set. A model-based router (Stage 6.5) is the planned fix.

**Remaining historical failures had one shared cause:** Q20 retrieved the October handoff (paused) but not September (active); Q21 retrieved resume v1 but not v2. A "how did X change" question needs both ends of the change, and relevance ranking returned only one version.

### Run 2 — with version expansion, unseeded

Results file: `stage4b_version_expansion_20261007_155816.json` — 35/45 (77.8%)

Version expansion: for historical questions, every multi-version family in the results gets its missing versions added (best BM25-matching chunk from each), capped at 10 chunks.

- **Expansion worked as designed.** Q20 now retrieved all four handoffs in date order; Q21 retrieved resume v2.
- **Both answers were still wrong.** Q20 claimed QubitML was paused as of 22 September; Q21 attributed v1's skill list to v2. The evidence was present and ordered — the 7B model mislabelled which source said what. **Model-capacity failure, not retrieval.**
- **Q43 and Q44 flipped to failing**, but both are routed as lookup, so their retrieval was identical to Run 1. The only thing that could change was the model output. **qwen2.5:7b at temperature 0 is not deterministic across runs** (likely GPU floating-point nondeterminism in Ollama). This means stage-to-stage differences of one or two questions are within noise.

### Run 3 — with version expansion, seed fixed (final Stage 4 row)

Results file: `stage4b_version_expansion_20261007_160237.json` — 36/45 (80.0%)

Change: Ollama options now `{"temperature": 0, "seed": 42}`.

**Failed (9):** 7, 15, 20, 21, 27, 30, 32, 33, 37

| Category | Answer | Source |
|---|---|---|
| Simple lookup | 76.9% | 100% |
| Current state | 88.9% | 88.9% |
| Historical | 66.7% | 100% |
| Status | 100% | 100% |
| Cross-document | 66.7% | 66.7% |
| Should refuse | 83.3% | n/a |

- **Q33 (Sem 5 subjects) and Q37 (refusal)** failed for the first time. Both are on the lookup path, whose retrieval did not change. Treated as model variance until the noise check is done.
- Q43 and Q18 passed in this run; Q43's answer has not been manually checked, so whether it is a true pass is unknown.

### Still failing after Stage 4 — by cause

| ID | Question | Cause | Next fix |
|---|---|---|---|
| 7 | PixelNet parameter count | Right file, wrong chunk | Larger top_k or section-level retrieval |
| 15 | Current tech stack | Answered NoteFlow's stack instead of Arjun's | Model / prompt; check retrieved chunk |
| 20 | When QubitML went active → paused | Evidence present and ordered; model misread it | Stronger model |
| 21 | Resume v1 → v2 | Evidence present; model mixed up versions | Stronger model |
| 27 | Projects with Python + ML | Project handovers not retrieved; resume chunks won | Recall on generic queries |
| 30 | DP problems solved | `dp_problems.md` retrieved, model answered from contest log | Model / prompt |
| 32 | Who is Rohan? | Chronicles not retrieved; handoffs mentioning Rohan outranked them | Recall |
| 33 | Sem 5 subjects | Passed in earlier runs; variance | Noise check |
| 37 | Accepted internship (should refuse) | Passed in earlier runs; variance | Noise check |

---

## Open items

1. **Noise measurement.** Run the identical seeded config twice and compare failed IDs. If they differ, report each stage as the mean of three runs.
2. **LLM-judge scoring** alongside key facts, spot-checked by hand.
3. **Stronger-model run** on the final Stage 4 config to separate retrieval failures from model failures (Q20, Q21, Q30).
4. **Classifier misses** (Q14, Q18, Q43) go to the Stage 6.5 model-based router.
5. **Chronicle grouping false positive** needs a per-folder `versioned: false` setting.