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

## Stage 3 — dedup + grouping + version dates

(to fill after the Stage 3 eval run)