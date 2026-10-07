# version-aware-rag

**A retrieval system that knows which copy of a document is current.**

Notes, plans and project files rarely stay in one clean version. They get duplicated, backed up, rewritten, and quietly corrected by newer files while the old ones stay around. A standard RAG pipeline doesn't know any of this. It retrieves whatever text sounds closest to the question, and when that text comes from an outdated version, the model gives a confident, wrong answer.

This project measures that problem on a fixed set of questions and then fixes it one stage at a time: deduplication, grouping files into versions, hybrid search, version-aware retrieval, a structured project registry, and finally a tool-using agent. Every number below comes from `eval/run_eval.py` or a hand check, and the full history of what went wrong is in [`eval/failure_log.md`](eval/failure_log.md).

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
| **+ Version-aware retrieval** (mean of 3 runs) | **92.3%** | **81.5%** | **85.2%** | **100%** |
| Agent: the model picks the tools (mean of 3 runs) | 92.3% | 75.6% | 66.7% | 66.7% |

The agent row is not a further step on top of the stages above. It is a different design: the same retrieval and registry, but a model decides which tool to call and how to search, instead of fixed code. It is compared against the best pipeline row.

The project registry (below) doesn't change these numbers, since project status questions were already 5/5. It is checked separately.

All runs use the same local setup: `qwen2.5:7b` through Ollama, `nomic-embed-text` embeddings, top 5 chunks, and a Chroma vector store. The model never changes between stages, so improvements come from retrieval, not from a better model. The last two rows are the mean of three runs at temperature 0 with a fixed seed. The earlier rows are single runs: until Stage 4 was finished, a bug meant the evaluation ran at Ollama's default temperature instead of 0 (found and fixed on 7 Oct).

### By category (answer correct / source found)

| Category | n | Baseline | + Dedup | + Hybrid | + Version-aware | Agent |
|---|---|---|---|---|---|---|
| Simple lookup | 13 | 53.8 / 84.6 | 53.8 / 84.6 | 84.6 / 100 | 76.9 / 100 | 84.6 / 100 |
| Current state | 9 | 55.6 / 77.8 | 66.7 / 77.8 | 55.6 / 77.8 | 85.2 / 88.9 | 66.7 / 77.8 |
| Change over time | 6 | 33.3 / 83.3 | 50.0 / 83.3 | 50.0 / 100 | 66.7 / 100 | 50.0 / 100 |
| Project status | 5 | 80.0 / 80.0 | 80.0 / 80.0 | 100 / 100 | 100 / 100 | 100 / 80.0 |
| Across documents | 6 | 16.7 / 50.0 | 16.7 / 50.0 | 66.7 / 66.7 | 66.7 / 66.7 | 83.3 / 100 |
| Should refuse | 6 | 100 | 100 | 100 | 100 | 66.7 |

### What each stage taught us

**Baseline.** The right file is usually found, but the answer is still often wrong. Questions about how something changed find a correct source 83% of the time and get answered correctly only 33% of the time, because every version comes back with nothing to say which one is newer.

**Deduplication and grouping.** Two duplicate files were removed and the remaining 22 were grouped into 16 document families, each file labelled with its date and whether it is the latest version. This fixed two questions, including the rating question, but only by luck: removing a duplicate made room for the October chunk. Nothing was choosing the newest version yet.

**Hybrid search.** Adding keyword search (BM25) next to embedding search raised the share of questions with a correct source from 77% to 90%. Exact names and numbers like "PixelNet" or "1550" are where keyword search shines. But questions about the current state got *worse*. A query like "current Codeforces rating" matches all four handovers on keywords, so outdated versions came back into the results. **Finding more relevant text made the version problem worse, not better.**

**Version-aware retrieval.** Each question is now classified as asking about the present, about change over time, or as a plain lookup:

- **Present:** only the latest version of each document is searched. Outdated copies never reach the model.
- **Change over time:** every version is kept, missing versions of the same document are pulled in, and everything is shown to the model in date order.
- **Lookup:** nothing is filtered.

Current-state accuracy went from 55.6% to 85.2% (mean of three runs), and the rating question is now answered correctly by design rather than by luck.

**Project registry.** Questions like "which projects are paused?" shouldn't depend on which chunks happen to be retrieved, or on a model that can answer differently between runs. So during indexing, the model reads each project file and handover once and fills in a fixed form for every project: name, status, reason and key result. Code then merges these into one record per project, keeping the newest version, the same rule retrieval uses. Status questions can now read from this small table and get the same answer every time. It also produces a one-page [project overview](docs/sample_vault_overview.md).

Checked by hand: all 5 statuses and key results are correct. The model was reliable when picking from a fixed list (status) and unreliable when writing free text: it wrote "N/A", repeated itself, or copied the status as the reason. So code checks every field before it is saved.

**Agent.** Instead of fixed code deciding each step, a model (built with LangChain's `create_agent`) chooses between three tools: search the notes (and whether to look at the present, the history, or everything), look up one project's status, or list projects by status. Every answer must cite the files the tools actually returned, and code checks this.

The model picked the right time mode on all 15 time-sensitive questions, better than the rule-based classifier (12 of 15). It also did better on lookups (84.6% vs 76.9%) and on questions that need several documents (83.3% vs 66.7%), because it writes its own search queries and can search more than once. But overall it scored 75.6% against the pipeline's 81.5%. With a 7B model, the losses come from the model's own decisions, not from where it looks:

- The first version scored 57.8%. It used the project registry for questions that had nothing to do with status, and it answered "I don't know" without searching at all.
- Narrowing the registry tools to status questions only, and having code send one follow-up ("search first") when the model refuses without searching, raised it to 68.9%.
- The model often found the right answer and then forgot to cite it, so the citation check threw correct answers away. Having code ask once for citations before blocking raised it to 75.6%.

The rule that came out of this: **a prompt can ask the model to follow a rule, but only code can make sure it did.** Each fix was written for a type of failure, not for specific questions, and the agent was frozen before the final three runs.

### Honest limits

- **The set is small.** One question moves the overall score by 2.2 points and a category score by up to 20. Read small differences with caution.
- **Run-to-run variation.** Three identical runs of the pipeline (temperature 0, fixed seed) still differed by one question. On a GPU, tiny floating-point differences can flip a near-tie between two tokens even with greedy decoding. So a one-question difference between stages (2.2 points overall, 11 points on the 9-question current-state category) is noise. The big jumps are not. The three agent runs happened to come out identical.
- **Key-fact scoring is imperfect.** An answer counts as correct if it contains every expected key fact. A manual review of one run found one wrong answer scored as correct and one correct answer scored as wrong. An LLM judge, spot-checked by hand, is planned as a second scorer.
- **The remaining failures are mostly the model, not retrieval.** For both of the remaining "change over time" failures in the pipeline, every relevant version is now retrieved and shown in date order, and the 7B model still mixes up which source said what. Running the same evaluation with a stronger model is planned.
- **The agent's "source found" is measured more loosely.** It counts any file returned by any tool call, while the pipeline counts a fixed top 5. Compare the two on answer correctness.
- **The agent still guesses on two refusal questions.** It correctly says the notes don't state the answer, then adds a guess anyway. The prompt forbids this; a 7B model doesn't always listen.
- **The registry's reasons are partial.** Only 2 of 5 projects have a real stated reason; the other three are finished or active projects with no reason in the notes, and the model fills in something anyway.

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

PROJECT REGISTRY  (python scripts/build_registry.py)

  project files + handovers
     ├─ read each file once   the model fills a fixed form per project
     ├─ check every field     code rejects "N/A", metrics without numbers, etc.
     └─ merge                 one record per project, newest version wins

QUESTION TIME, PIPELINE  (cli.py, run_eval.py)

  question
     ├─ classify              present / change over time / lookup
     ├─ search                dense + BM25, merged by rank (RRF);
     │                        "present" questions search latest versions only
     ├─ expand                "change" questions pull in missing versions
     ├─ order                 "change" questions sorted oldest to newest
     └─ answer                each source shown with its date and whether it
                              is the latest version; the model must cite
                              sources or say it doesn't know

QUESTION TIME, AGENT  (cli.py --agent)

  question
     ├─ model picks a tool    search_notes (present / history / any),
     │                        get_project_status, or list_projects
     ├─ tools run             the same retrieval and registry as above
     ├─ model answers         from the tool results, citing file paths
     └─ code checks           refused without searching → told to search once;
                              no valid citation → asked to cite once;
                              still uncited → replaced with "I don't know"
```

A few decisions worth explaining:

- **Dates come before deduplication.** Two versions of a handover can be 90% identical with one changed number. Treating them as duplicates would throw away the newer fact, so near-duplicates must also share a date.
- **Version information is decided per file and stored per chunk.** A chunk inherits its file's date and family, so retrieval can filter without re-reading anything.
- **Search results are merged by rank, not score.** Keyword scores and embedding distances are on different scales. Reciprocal Rank Fusion avoids normalising them.
- **Weak dates are hidden from the model.** Files dated only by modified time show as "undated", because a copy date would make an old file look like the newest one. The agent's project history follows the same rule.
- **The question classifier is rule-based for now.** It is fast, free, testable, and routes 12 of the 15 time-sensitive questions correctly. The agent routes all 15 correctly, but costs accuracy elsewhere.
- **The model reads, code decides.** In the registry, the model only extracts what each file says. Dates, sources and which version wins are handled by code, so they can't be invented. In the agent, code checks every citation against the files the tools actually returned.
- **Three tools, not five.** A timeline tool and an "have I planned this already" tool were folded into search and the prompt. Overlapping tools make a small model pick the wrong one.

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

Copy `.env.example` to `.env`. By default the agent uses `qwen2.5:7b` through Ollama; set `JARVIS_LLM_PROVIDER=openai_compat` and the `JARVIS_*` values to use any OpenAI-compatible API instead.

From the project root:

```bash
python scripts/ingest.py              # build the index and print an ingestion report
python scripts/build_registry.py      # build the project registry (one model call per file)
python scripts/generate_overview.py   # write docs/sample_vault_overview.md
python src/interfaces/cli.py          # ask questions (pipeline), type 'exit' to quit
python src/interfaces/cli.py --agent  # ask questions (agent), shows each tool call
python scripts/agent_checkpoint.py    # 5 fixed questions through the agent, with a trace
python eval/run_eval.py               # run the 45-question evaluation
python -m pytest tests                # unit tests
```

To evaluate the agent instead of the pipeline, set `ANSWER_MODE = "agent"` at the top of `eval/run_eval.py`.

The code talks to Ollama at `http://127.0.0.1:11434` directly, so an `OLLAMA_HOST=0.0.0.0` setting (used for Docker) doesn't break it.

---

## Project layout

```
data/sample-vault/   fictional test corpus, safe to share
docs/                generated project overview
eval/                questions, evaluation runner, results, failure log
scripts/             rebuild the index, the registry and the overview; agent checkpoint
src/ingest/          loading, dating, deduplication, grouping, chunking
src/retrieval/       vector store, BM25, hybrid search, version-aware ranking
src/registry/        project registry: extraction, merging, lookups
src/agent/           agent tools, prompt, and the agent loop with citation checks
src/router/          question classifier
src/interfaces/      command-line interface (pipeline and agent)
tests/               unit tests for ingestion, retrieval, the registry and the agent
```

---

## Privacy

The sample vault is fictional, so the project can be tried and evaluated in public. Real personal notes are only ever used locally, stay out of the repository, and are embedded with a local model.