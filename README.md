# version-aware-rag

**A RAG engine that knows which copy of a document is current.**

Personal notes, plans, and project files pile up as overlapping versions: duplicated handovers, backups, and later files that quietly correct earlier ones. Plain similarity search retrieves whichever chunk *sounds* closest to the question, which is often the stale one, and the model answers confidently wrong.

This project measures that failure on a fixed evaluation set, then fixes it stage by stage with deduplication, document grouping, version-aware ranking, and hybrid retrieval. Every number in this README comes from `eval/run_eval.py`.

---

## The problem, concretely

The bundled sample vault describes a fictional student, Arjun, across 24 files written between June and October 2026. The same facts appear in several places and change over time:

| Fact | Values across files | Current |
|---|---|---|
| Codeforces rating | 1420 → 1510 → 1480 → 1550 | 1550 (Oct) |
| PixelNet accuracy | 89.7% (Aug, stale) → 91.3% | 91.3% |
| QubitML status | active → paused | paused (Oct) |
| Career goal | frontend internship → AI backend internship | AI backend (Oct) |

The vault also contains an exact duplicate (`arjun_master_handoff_aug2026 (1).md`) and a near-duplicate backup (`career_plan_oct2026_backup.md`).

Asked *"What is Arjun's current Codeforces rating?"*, the baseline retrieves all four handoffs with nearly identical similarity scores (0.30–0.33) and answers **1510**, citing the two copies of the August handoff. The right answer, 1550, was in the retrieved context. Nothing in the system knows that October is newer than August.

---

## Results

Evaluated on 45 hand-written questions with verified answers and source files.

| Stage | Source hit rate | Answer correctness | Temporal (current-state) | Refusal accuracy |
|---|---|---|---|---|
| **Baseline dense** | **76.9%** (30/39) | **55.6%** (25/45) | **55.6%** (5/9) | **100%** (6/6) |
| + Dedup & version grouping | — | — | — | — |
| + Hybrid (BM25 + dense) | — | — | — | — |
| + Version-aware ranking & intent routing | — | — | — | — |
| + Structured registry for status questions | — | — | — | — |

Configuration for all runs: LLM `qwen2.5:7b` (local, Ollama, temperature 0), embeddings `nomic-embed-text`, top-k = 5, Chroma vector store. The model and settings stay fixed across stages so differences come from retrieval changes, not model changes.

### Baseline by category

| Category | n | Answer correctness | Source hit rate |
|---|---|---|---|
| Simple lookup | 13 | 53.8% | 84.6% |
| Current-state (temporal trap) | 9 | 55.6% | 77.8% |
| Historical / change over time | 6 | 33.3% | 83.3% |
| Status aggregation | 5 | 80.0% | 80.0% |
| Cross-document | 6 | 16.7% | 50.0% |
| Should refuse | 6 | 100.0% | n/a |

What the baseline shows:

- **Retrieval often finds the right file but the answer is still wrong.** Historical questions hit the right source 83% of the time but are answered correctly only 33% of the time: the chunks for every version come back, with nothing to order them by date.
- **Cross-document questions are the weakest** (16.7%). Facts spread over several files get crowded out of the top 5 by duplicate chunks.
- **Grounding works.** The model refused all 6 questions whose answers are not in the vault, including two whose answers exist only in a folder that is deliberately excluded from ingestion.

Wrong answers and their causes are tracked in [`eval/failure_log.md`](eval/failure_log.md).
Full per-question results: `eval/results/`.

---

## How evaluation works

`eval/golden_questions.json` holds 45 questions across six categories. Each has an expected answer, the files that support it, and a list of `key_facts`.

- **Source hit rate:** at least one expected file appears in the top-k retrieved chunks. The 6 should-refuse questions are excluded (they have no valid source), so this is out of 39.
- **Answer correctness:** every key fact (lowercased) appears in the model's answer. For example, the current-rating question requires `"1550"`; the PixelNet optimizer question requires both `"sgd"` and `"momentum"`.
- **Refusal accuracy:** for questions with no answer in the vault, the model must say it doesn't have the information.

**Known limits of key-fact matching.** It can pass an answer that mentions the right value but picks a different one as current, and it can fail a correct answer phrased differently. A few questions whose true answer is "no" use an indirect fact. An LLM-as-judge, spot-checked by hand, is planned as a second scoring method; both will be reported.

---

## Architecture (current)

```
data/sample-vault/*.md
        │  load_vault()        walks the vault, skips the skip/ folder
        ▼
   chunk_document()            splits on markdown headers, keeps the header path
        │
        ▼
   Chroma (persistent)         embeddings via nomic-embed-text on Ollama
        │  query_vectorstore()  top-k by cosine distance
        ▼
   answer_question()           numbered, cited context → qwen2.5:7b
                               "answer only from sources, cite them, refuse otherwise"
```

Planned next: content-hash deduplication, grouping files into document families with resolved version dates, hybrid BM25 + dense retrieval, and ranking that prefers the newest version for current-state questions while keeping all versions for history questions.

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

Build the vector store, chat, and run the evaluation (from the project root):

```bash
python src/retrieval/vector_store.py   # ingest + embed the sample vault
python src/interfaces/cli.py           # interactive Q&A, type 'exit' to quit
python eval/run_eval.py                # full eval, results saved to eval/results/
```

Note: the code connects to Ollama at `http://127.0.0.1:11434` explicitly, so an `OLLAMA_HOST=0.0.0.0` setting used for Docker doesn't break the Python client.

---

## Project layout

```
data/sample-vault/   fictional, shareable test corpus
eval/                golden questions, eval runner, results, failure log
src/ingest/          loaders, chunker, pipeline
src/retrieval/       vector store (BM25, hybrid, version ranking to come)
src/interfaces/      CLI (MCP server and API to come)
tests/
```

---

## Privacy

The sample vault is fictional and exists so the project can be tried and evaluated publicly. Real personal notes are only ever used locally, are gitignored, and are embedded with a local model.

---

## Status

- [x] Stage 0: sample vault + 45-question golden set
- [x] Stage 1: loading and structure-aware chunking
- [x] Stage 2: baseline dense RAG, CLI, eval harness
- [ ] Stage 3: deduplication, document grouping, version dates
- [ ] Stage 4: hybrid retrieval, version-aware ranking, intent routing
- [ ] Later: project-status registry, agent with tools, MCP server