# version-aware-rag

**A RAG engine that knows which copy of a document is current.**

Personal notes, plans, and project files pile up as overlapping versions: duplicated handovers, backups, and later files that quietly correct earlier ones. Plain similarity search retrieves whichever chunk *sounds* closest to the question, which is often the stale one, and the model answers confidently wrong.

This project measures that failure on a fixed evaluation set, then fixes it stage by stage with deduplication, document grouping, hybrid retrieval, and version-aware ranking. Every number in this README comes from `eval/run_eval.py`.

---

## The problem, concretely

The bundled sample vault describes a fictional student, Arjun, across 24 files written between June and October 2026. The same facts appear in several places and change over time:

| Fact | Values across files | Current |
|---|---|---|
| Codeforces rating | 1420 → 1510 → 1480 → 1550 | 1550 (Oct) |
| PixelNet accuracy | 89.7% (Aug, stale) → 91.3% | 91.3% |
| QubitML status | active → paused | paused (Oct) |
| Career goal | frontend internship → AI backend internship | AI backend (Oct) |

The vault also contains two duplicate copies: `arjun_master_handoff_aug2026 (1).md` and `career_plan_oct2026_backup.md`.

Asked *"What is Arjun's current Codeforces rating?"*, the baseline retrieves all four handoffs with nearly identical similarity scores (0.30–0.33) and answers **1510**, citing the two copies of the August handoff. The right answer, 1550, was in the retrieved context. Nothing in the system knows that October is newer than August.

---

## Results

Evaluated on 45 hand-written questions with verified answers and source files.

| Stage | Source hit rate | Answer correctness | Temporal (current-state) | Refusal accuracy |
|---|---|---|---|---|
| Baseline dense | 76.9% (30/39) | 55.6% (25/45) | 55.6% (5/9) | 100% (6/6) |
| + Dedup & version grouping | 76.9% (30/39) | 60.0% (27/45) | 66.7% (6/9) | 100% (6/6) |
| + Hybrid (BM25 + dense) | **89.7%** (35/39) | **75.6%** (34/45) | 55.6% (5/9) | 100% (6/6) |
| + Version-aware ranking & intent routing | — | — | — | — |
| + Structured registry for status questions | — | — | — | — |

Configuration for all runs: LLM `qwen2.5:7b` (local, Ollama, temperature 0), embeddings `nomic-embed-text`, top-k = 5, Chroma vector store. The model, prompt and settings stay fixed across stages, so differences come from retrieval changes, not model changes. Each stage changes one thing.

### By category

Answer correctness / source hit rate.

| Category | n | Baseline | + Dedup & grouping | + Hybrid |
|---|---|---|---|---|
| Simple lookup | 13 | 53.8 / 84.6 | 53.8 / 84.6 | 84.6 / 100.0 |
| Current-state (temporal trap) | 9 | 55.6 / 77.8 | 66.7 / 77.8 | 55.6 / 77.8 |
| Historical / change over time | 6 | 33.3 / 83.3 | 50.0 / 83.3 | 50.0 / 100.0 |
| Status aggregation | 5 | 80.0 / 80.0 | 80.0 / 80.0 | 100.0 / 100.0 |
| Cross-document | 6 | 16.7 / 50.0 | 16.7 / 50.0 | 66.7 / 66.7 |
| Should refuse | 6 | 100.0 / n/a | 100.0 / n/a | 100.0 / n/a |

### What each stage showed

**Baseline.** Retrieval often finds the right file but the answer is still wrong. Historical questions hit the right source 83% of the time but are answered correctly only 33% of the time: chunks for every version come back with nothing to order them by date. Cross-document questions are weakest (16.7%) because duplicate chunks crowd facts out of the top 5. Grounding works: all 6 unanswerable questions were refused, including two whose answers exist only in a deliberately excluded folder.

**+ Dedup & grouping.** Removed 2 duplicate files (14 chunks) and grouped the remaining 22 files into 16 document families, each file labelled with a resolved version date and its rank within the family. Fixed 2 questions, no regressions. The current-rating question now answered 1550, but only because removing the duplicate freed a top-5 slot for the October chunk. Nothing ranks by date yet, so the fix was incidental. Source hit rate did not move: dedup removes noise but cannot surface new sources.

**+ Hybrid retrieval.** BM25 keyword search fused with dense search (Reciprocal Rank Fusion). Fixed 9 questions; source hit rate rose to 89.7% and cross-document answers from 16.7% to 66.7%, since project names and numbers are exactly what keyword matching is good at. **But temporal correctness dropped.** "Current Codeforces rating" shares its keywords with all four handoffs, so BM25 pulled older versions back into the top 5 and the answer regressed. Better recall makes the version problem worse. That is the case for version-aware ranking, the next stage.

Wrong answers and their causes are tracked in [`eval/failure_log.md`](eval/failure_log.md). Full per-question results: `eval/results/`.

---

## How evaluation works

`eval/golden_questions.json` holds 45 questions across six categories. Each has an expected answer, the files that support it, and a list of `key_facts`.

- **Source hit rate:** at least one expected file appears in the top-k retrieved chunks. The 6 should-refuse questions are excluded (they have no valid source), so this is out of 39.
- **Answer correctness:** every key fact (lowercased) appears in the model's answer. For example, the current-rating question requires `"1550"`; the PixelNet optimizer question requires both `"sgd"` and `"momentum"`.
- **Refusal accuracy:** for questions with no answer in the vault, the model must say it doesn't have the information.

**Known limits of key-fact matching.** It can pass an answer that mentions the right value but picks a different one as current, and it can fail a correct answer phrased differently. A few key facts are weak (very short strings). The set is small, so one question moves overall accuracy by 2.2 points and a category by up to 20. An LLM-as-judge, spot-checked by hand, is planned as a second scoring method; both will be reported.

---

## Architecture (current)

Ingestion runs offline and labels every chunk; retrieval reads those labels at question time.

```
data/sample-vault/*.md
        │  scripts/ingest.py      (rebuild the index)
        ▼
 load_vault()          walk the vault, skip the skip/ folder
        ▼
 resolve_version_date  date per file: filename > document header > file mtime
        ▼
 deduplicate()         SHA-256 of normalized text for exact copies;
                       word-shingle Jaccard for near-copies, only when
                       both files have the same version date
        ▼
 group_documents()     document families by filename stem (dates, v1/v2,
                       copy markers stripped); rank versions newest first
        ▼
 chunk_document()      split on markdown headers, keep the header path
        ▼
 Chroma                every chunk stores: source, header_path, version_date,
                       date_source, doc_group_id, version_rank, is_latest
        │
        │  question time  (src/interfaces/cli.py, eval/run_eval.py)
        ▼
 HybridRetriever       dense top-20 (Chroma) + BM25 top-20, fused with RRF → top 5
        ▼
 answer_question()     numbered, cited context → qwen2.5:7b
                       "answer only from sources, cite them, refuse otherwise"
```

Design choices worth knowing:

- **Dates are resolved before deduplication.** A near-duplicate check on text alone would drop a newer version that differs by one changed fact. Requiring the same version date prevents it.
- **Version decisions are made per file, stored per chunk.** Chunks inherit their file's date and family, so retrieval can filter and rank without re-reading files.
- **Fusion uses ranks, not scores.** BM25 scores and cosine distances live on different scales; Reciprocal Rank Fusion (k = 60) needs no normalization or tuning.
- **The BM25 index is built from Chroma** at startup, so both retrievers share the same chunks and IDs.

Next: version-aware ranking (prefer `is_latest` within a document family for current-state questions, keep every version for history questions), a question-intent classifier to decide which applies, and version dates shown to the model in context.

---

## Quickstart

Requirements: Python 3.11+, [Ollama](https://ollama.com).

```bash
git clone https://github.com/Pratham-2105/version-aware-rag.git
cd version-aware-rag
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

ollama pull nomic-embed-text
ollama pull qwen2.5:7b
```

From the project root:

```bash
python scripts/ingest.py         # ingest, dedup, group, embed the sample vault (prints a report)
python src/interfaces/cli.py     # interactive Q&A, type 'exit' to quit
python eval/run_eval.py          # full eval, results saved to eval/results/
python -m pytest tests           # unit tests
```

Note: the code connects to Ollama at `http://127.0.0.1:11434` explicitly, so an `OLLAMA_HOST=0.0.0.0` setting used for Docker doesn't break the Python client.

---

## Project layout

```
data/sample-vault/   fictional, shareable test corpus
eval/                golden questions, eval runner, results, failure log
scripts/             ingest.py (rebuild the index)
src/ingest/          loaders, version dates, dedup, grouping, chunker, pipeline
src/retrieval/       vector store, BM25, hybrid fusion (version ranking to come)
src/interfaces/      CLI (MCP server and API to come)
tests/               dedup, grouping, version dates, retrieval
```

---

## Privacy

The sample vault is fictional and exists so the project can be tried and evaluated publicly. Real personal notes are only ever used locally, are gitignored, and are embedded with a local model.

---

## Status

- [x] Stage 0: sample vault + 45-question golden set
- [x] Stage 1: loading and structure-aware chunking
- [x] Stage 2: baseline dense RAG, CLI, eval harness
- [x] Stage 3: deduplication, document grouping, version dates
- [ ] Stage 4: hybrid retrieval ✓, version-aware ranking, intent routing
- [ ] Later: project-status registry, agent with tools, MCP server