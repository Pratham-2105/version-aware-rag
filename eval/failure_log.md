# Failure Log

Every wrong answer, why it was wrong, and which stage fixed it (or didn't).
Source of truth for numbers: `eval/results/`.

---

## Baseline dense — 1 Oct 2026

Config: qwen2.5:7b (temp 0), nomic-embed-text, top_k = 5, no dedup, no version awareness.
Results file: `eval/results/baseline_dense_20261001_170534.json`

Failed answer IDs (20/45): 3, 5, 7, 8, 11, 13, 15, 16, 18, 20, 21, 25, 27, 29, 30, 32, 33, 41, 42, 44

### Analysed failures

| ID | Question | What happened | Failure type | Expected fix |
|---|---|---|---|---|
| 8 | What is Arjun's current Codeforces rating? | Answered **1510** (correct: 1550). All four handoffs were retrieved with near-identical distances (0.30–0.33); the model cited both copies of the August handoff. The October chunk with 1550 was in the context but nothing marked it as newest. | Stale version chosen | Stage 3 (collapse Aug duplicate) + Stage 4 (prefer newest version for current-state questions) |
| 5 | Where is DataLens deployed? | `datalens_handover.md` was retrieved first, but the model answered from an older master handoff saying DataLens had "not yet been deployed". Correct: Railway. | Stale version chosen | Stage 4 (version-aware ranking) |
| 3 | What optimizer does PixelNet use? | `pixelnet_handover.md` was retrieved, but the model refused: the chunk containing the optimizer detail was not in the top 5. Other slots were taken by career-plan duplicates and handoffs mentioning PixelNet. | Right file, wrong chunk | Stage 3 (dedup frees slots) + Stage 4 (hybrid/BM25 for exact terms) |

Note: the observations for IDs 3 and 5 come from debug runs on the same pipeline; confirm against the results file.

### Patterns across the baseline

- **Duplicates eat top-k slots.** `arjun_master_handoff_aug2026.md` and its `(1)` copy, and `career_plan_oct2026.md` and its `_backup`, appear as pairs with identical distances, so effectively only 3–4 unique chunks reach the model.
- **No notion of time.** Historical questions hit the right source 83.3% of the time but are answered correctly only 33.3% of the time. Every version comes back with no ordering.
- **Cross-document is weakest** (16.7% answer, 50% source). Facts spread across several files don't all fit in top 5.
- **Refusals are solid** (6/6), including both skip-folder questions.

### Not yet analysed

7, 11, 13, 15, 16, 18, 20, 21, 25, 27, 29, 30, 32, 33, 41, 42, 44

---

## Stage 3 — dedup + grouping (stage3_dedup_grouping_20261007_145452.json)

**Fixed:** Q8, Q16. **Regressions:** none. **Still failing:** 18.

- **Q8 (current CF rating)** — now answers 1550. Cause of fix: removing the Aug "(1)" duplicate freed a top-5 slot, letting the Oct handoff chunk in; the LLM preferred it (filename shows oct2026). **Fragile:** no date-based ranking exists yet, so the correct answer depends on the LLM's choice. Stage 4 must make this deterministic (filter `is_latest` for current-state questions).
- **Q16** — fixed by the same mechanism (fewer duplicate chunks in context).
- **Q5 (DataLens deployment)** — still answers from an older handoff. Needs version-aware ranking (Stage 4).
- **Q3** — right file, wrong chunk; not a version problem. Candidate for hybrid retrieval / larger top_k (Stage 4).
- **Cross-document (16.7%, source 50%)** — unchanged; dedup cannot help recall. Needs hybrid retrieval.

**Observations for Stage 4**
- Source hit rate unchanged at 76.9%: all remaining misses are recall failures.
- `version_date` is in chunk metadata but NOT shown to the LLM — `format_context` prints only file and header. Show the date in the context so the model can reason about recency even without filtering.
- 9/22 files are dated by mtime (weak). Version ranking must only compare dates within a doc_group_id.
- Grouping false positive: chronicle_july2026 + chronicle_sep2026 grouped as one family (diary entries, not versions). Harmless only if "latest wins" is restricted to current-state questions.

**Unit-test note:** near-duplicate detection is unit-tested only; both sample-vault duplicates were exact after normalization.