# version-aware-rag

**A retrieval system that knows which copy of a document is current.**

Notes, plans and project files rarely stay in one clean version. They get duplicated, backed up, rewritten, and quietly corrected by newer files while the old ones stay around. A standard RAG pipeline doesn't know any of this. It retrieves whatever text sounds closest to the question, and when that text comes from an outdated version, the model gives a confident, wrong answer.

This project measures that problem on a fixed set of questions and then fixes it one stage at a time: deduplication, grouping files into versions, hybrid search, and version-aware retrieval. Every number below comes from `eval/run_eval.py`, and the full history of what went wrong is in [`eval/failure_log.md`](eval/failure_log.md).

---

## The problem

The repo ships with a fictional sample vault: 24 files about a student, Arjun, written between June and October 2026. Like real notes, the same facts show up in several files and change over time.

| Fact | Values across files | Correct today |
|---|---|---|
| Codeforces rating | 1420 → 1510 → 1480 → 1550 | 1550 |
| PixelNet accuracy | 89.7% → 91.3% | 91.3% |
| QubitML status | active → paused | paused |
| Career goal | frontend internship → AI backend internship | AI backend |

The vault also contains two exact duplicates: a copied handover with `(1)` in its name and a `_backup` of a career plan.

Ask the baseline system *"What is Arjun's current Codeforces rating?"* and it retrieves all four handovers with almost identical similarity scores, then answers **1510** from the August copy. The correct answer, 1550, was in the retrieved text the whole time. The system had no way of knowing that October comes after August.

---

## Results

45 hand-written questions, each with a verified answer and the files that support it.

| Stage | Source found | Answer correct | Current-state questions | Correct refusals |
|---|---|---|---|---|
| Baseline (dense search) | 76.9% | 55.6% | 55.6% | 100% |
| + Deduplication and version grouping | 76.9% | 60.0% | 66.7% | 100% |
| + Hybrid search (BM25 + dense) | 89.7% | 75.6% | 55.6% | 100% |
| **+ Version-aware retrieval** | **92.3%** | **80.0%** | **88.9%** | 83.3% |
| + Structured project registry | — | — | — | — |

All runs use the same local setup: `qwen2.5:7b` through Ollama at temperature 0, `nomic-embed-text` embeddings, top 5 chunks, and a Chroma vector store. The model never changes between stages, so improvements come from retrieval, not from a better model.

### By category (answer correct / source found)

| Category | n | Baseline | + Dedup | + Hybrid | + Version-aware |
|---|---|---|---|---|---|
| Simple lookup | 13 | 53.8 / 84.6 | 53.8 / 84.6 | 84.6 / 100 | 76.9 / 100 |
| Current state | 9 | 55.6 / 77.8 | 66.7 / 77.8 | 55.6 / 77.8 | 88.9 / 88.9 |
| Change over time | 6 | 33.3 / 83.3 | 50.0 / 83.3 | 50.0 / 100 | 66.7 / 100 |
| Project status | 5 | 80.0 / 80.0 | 80.0 / 80.0 | 100 / 100 | 100 / 100 |
| Across documents | 6 | 16.7 / 50.0 | 16.7 / 50.0 | 66.7 / 66.7 | 66.7 / 66.7 |
| Should refuse | 6 | 100 | 100 | 100 | 83.3 |

### What each stage taught us

**Baseline.** The right file is usually found, but the answer is still often wrong. Questions about how something changed find a correct source 83% of the time and get answered correctly only 33% of the time, because every version comes back with nothing to say which one is newer.

**Deduplication and grouping.** Two duplicate files were removed and the remaining 22 were grouped into 16 document families, each file labelled with its date and whether it is the latest version. This fixed two questions, including the rating question, but only by luck: removing a duplicate made room for the October chunk. Nothing was choosing the newest version yet.

**Hybrid search.** Adding keyword search (BM25) next to embedding search raised the share of questions with a correct source from 77% to 90%. Exact names and numbers like "PixelNet" or "1550" are where keyword search shines. But questions about the current state got *worse*. A query like "current Codeforces rating" matches all four handovers on keywords, so outdated versions came back into the results. **Finding more relevant text made the version problem worse, not better.**

**Version-aware retrieval.** Each question is now classified as asking about the present, about change over time, or as a plain lookup:

- **Present:** only the latest version of each document is searched. Outdated copies never reach the model.
- **Change over time:** every version is kept, missing versions of the same document are pulled in, and everything is shown to the model in date order.
- **Lookup:** nothing is filtered.

Current-state accuracy went from 55.6% to 88.9%, and the rating question is now answered correctly by design rather than by luck.

### Honest limits

- **The set is small.** One question moves the overall score by 2.2 points and a category score by up to 20. Read small differences with caution.
- **Run-to-run variation.** Two runs of the same pipeline differed by two answers on questions the code change could not affect, even at temperature 0. The final row uses a fixed seed. A proper noise measurement is the next step, and small stage-to-stage differences (one or two questions) are within this noise. The large ones are not.
- **Key-fact scoring is imperfect.** An answer counts as correct if it contains every expected key fact. A manual review of one run found one wrong answer scored as correct and one correct answer scored as wrong. An LLM judge, spot-checked by hand, is planned as a second scorer.
- **The remaining failures are mostly the model, not retrieval.** For both of the remaining "change over time" failures, every relevant version is now retrieved and shown in date order, and the 7B model still mixes up which source said what. Running the same evaluation with a stronger model is planned.
- **The refusal drop (6/6 → 5/6)** appeared in the seeded run on a question whose retrieval did not change. It is logged as a model-variance case, not a retrieval change.

---

## How it works

Indexing runs once, offline, and labels every chunk with version information. At question time, retrieval reads those labels.

```
INDEXING  (python scripts/ingest.py)

  sample vault
     │
     ├─ load files            skip the private skip/ folder
     ├─ date each file        from the filename, else the document header,
     │                        else the file's modified time (marked as weak)
     ├─ remove duplicates     exact copies by content hash; near-copies only
     │                        if they also share the same date
     ├─ group versions        files with the same name apart from date or
     │                        v1/v2 form one family, newest marked as latest
     ├─ split into chunks     by markdown headings
     └─ store in Chroma       with source, date, family and is_latest

QUESTION TIME  (cli.py, run_eval.py)

  question
     ├─ classify              present / change over time / lookup
     ├─ search                dense + BM25, merged by rank (RRF);
     │                        "present" questions search latest versions only
     ├─ expand                "change" questions pull in missing versions
     ├─ order                 "change" questions sorted oldest to newest
     └─ answer                each source shown with its date and whether it
                              is the latest version; the model must cite
                              sources or say it doesn't know
```

A few decisions worth explaining:

- **Dates come before deduplication.** Two versions of a handover can be 90% identical with one changed number. Treating them as duplicates would throw away the newer fact, so near-duplicates must also share a date.
- **Version information is decided per file and stored per chunk.** A chunk inherits its file's date and family, so retrieval can filter without re-reading anything.
- **Search results are merged by rank, not score.** Keyword scores and embedding distances are on different scales. Reciprocal Rank Fusion avoids normalising them.
- **Weak dates are hidden from the model.** Files dated only by modified time show as "undated", because a copy date would make an old file look like the newest one.
- **The question classifier is rule-based for now.** It is fast, free, testable, and routes 12 of the 15 time-sensitive questions correctly. A model-based router is planned.

---

## Quickstart

You need Python 3.11+ and [Ollama](https://ollama.com).

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
python scripts/ingest.py         # build the index and print an ingestion report
python src/interfaces/cli.py     # ask questions, type 'exit' to quit
python eval/run_eval.py          # run the 45-question evaluation
python -m pytest tests           # unit tests
```

The code talks to Ollama at `http://127.0.0.1:11434` directly, so an `OLLAMA_HOST=0.0.0.0` setting (used for Docker) doesn't break it.

---

## Project layout

```
data/sample-vault/   fictional test corpus, safe to share
eval/                questions, evaluation runner, results, failure log
scripts/             ingest.py rebuilds the index
src/ingest/          loading, dating, deduplication, grouping, chunking
src/retrieval/       vector store, BM25, hybrid search, version-aware ranking
src/router/          question classifier
src/interfaces/      command-line interface
tests/               unit tests for every ingestion and retrieval step
```

---

## Privacy

The sample vault is fictional, so the project can be tried and evaluated in public. Real personal notes are only ever used locally, stay out of the repository, and are embedded with a local model.

---

## Status

- [x] Sample vault and 45-question evaluation set
- [x] Loading and heading-aware chunking
- [x] Baseline retrieval, command-line interface, evaluation harness
- [x] Deduplication, version dating, document grouping
- [x] Hybrid search and version-aware retrieval
- [ ] Noise measurement across repeated runs, LLM-judge scoring
- [ ] Structured project registry for status questions
- [ ] Agent with tools, MCP server