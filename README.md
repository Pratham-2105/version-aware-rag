# version-aware-rag (Jarvis)

![tests](https://github.com/Pratham-2105/version-aware-rag/actions/workflows/tests.yml/badge.svg)

**A notes assistant that knows which copy of a document is current.**

Point it at a folder of notes, plans and project files. It answers questions with citations, knows that the October version of a fact replaces the August one, tracks project status, and can be used from Claude Desktop, Claude Code or Cursor through MCP. Everything runs locally by default.

<!-- demo GIF: docs/demo.gif (terminal recording of `jarvis check`) -->

---

## The problem

Notes, plans and project files rarely stay in one clean version. They get duplicated, backed up, rewritten, and quietly corrected by newer files while the old ones stay around. A standard RAG pipeline doesn't know any of this. It retrieves whatever text sounds closest to the question, and when that text comes from an outdated version, the model gives a confident, wrong answer.

The repo ships with a fictional sample vault: 24 files about a student, Arjun, written between June and October 2026. Like real notes, the same facts show up in several files and change over time.

| Fact | Values across files | Correct today |
|---|---|---|
| Codeforces rating | 1420 → 1510 → 1480 → 1550 | 1550 |
| PixelNet accuracy | 89.7% → 91.3% | 91.3% |
| QubitML status | active → paused | paused |
| Career goal | frontend internship → AI backend internship | AI backend |

The vault also contains two exact duplicates: a copied handover with `(1)` in its name and a `_backup` of a career plan.

Ask a standard RAG pipeline *"What is Arjun's current Codeforces rating?"* and it retrieves all four handovers with almost identical similarity scores, then answers **1510** from the August copy. The correct answer, 1550, was in the retrieved text the whole time. The system had no way of knowing that October comes after August.

This project measures that problem on a fixed set of questions and fixes it one stage at a time. Every number below comes from `eval/run_eval.py` or a hand check, and the full history of what went wrong is in [`eval/failure_log.md`](eval/failure_log.md).

---

## Quickstart (sample vault, about 5 minutes)

You need Python 3.11+ and [Ollama](https://ollama.com).

```bash
git clone https://github.com/Pratham-2105/version-aware-rag.git
cd version-aware-rag
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -e .

ollama pull nomic-embed-text
ollama pull qwen2.5:7b

jarvis ingest                                             # index the sample vault
jarvis ask "What is Arjun's current Codeforces rating?"   # 1550, with sources
jarvis chat                                               # talk to it; /new, /quit
```

The `config.yaml` in the repo points at the sample vault. `jarvis registry` builds the project registry (one model call per project file, about 2 minutes), which the agent and the MCP server use for project-status questions.

| Command | What it does |
|---|---|
| `jarvis init <folder>` | write a `config.yaml` for your own notes |
| `jarvis ingest` | build the search index |
| `jarvis registry` | build the project registry and a one-page overview |
| `jarvis ask "..."` | one answer with sources (`--agent` for the tool-using agent) |
| `jarvis chat` | chat through the router, with memory per conversation (`--demo` for a scripted run) |
| `jarvis mcp` | run the MCP server for Claude Desktop, Claude Code, Cursor |
| `jarvis check` | start the MCP server the way an app would and test its tools |

Every command reads `config.yaml` from the current folder, or from `--config`.

---

## Use it on your own notes

```bash
mkdir my-jarvis
cd my-jarvis
jarvis init "D:\path\to\your\notes"
```

This writes a `config.yaml` listing every top-level folder of your notes. **Every folder starts as private.** Private folders never leave your machine: they are answered only by the local model and are never returned over MCP. Open the file and:

1. Mark the folders you're happy to share as `privacy: shareable`.
2. Mark folders of separate entries (diaries, logs) as `versioned: false`, so older entries are never hidden as outdated.
3. Optionally split the single `notes` area into areas like projects, career and personal, with a one-line description each. The router reads these descriptions.
4. Optionally list your project folders under `registry: folders:` to get the project registry.

Then run `jarvis ingest`, and `jarvis chat` or `jarvis ask`. The index and registry go into `.jarvis/` next to the config, never into your notes folder.

## Use it from Claude Desktop, Claude Code or Cursor

Add Jarvis to the app's MCP config. For Claude Desktop on Windows that's `%APPDATA%\Claude\claude_desktop_config.json`; use absolute paths:

```json
{
  "mcpServers": {
    "jarvis": {
      "command": "D:\\path\\to\\version-aware-rag\\.venv\\Scripts\\jarvis.exe",
      "args": ["mcp", "--config", "D:\\path\\to\\my-jarvis\\config.yaml"]
    }
  }
}
```

For Claude Code: `claude mcp add jarvis -- <path to jarvis.exe> mcp --config <path to config.yaml>`.

The app can then search your shareable folders by time mode (current, history, any), look up a project's status, list projects, and attach the project overview. `jarvis check` runs the same launch-and-call sequence an app does, so you can test it without one.

---

## Results

45 hand-written questions about the sample vault, each with a verified answer and the files that support it.

| Stage | Source found | Answer correct | Current-state questions | Correct refusals |
|---|---|---|---|---|
| Baseline (dense search) | 76.9% | 55.6% | 55.6% | 100% |
| + Deduplication and version grouping | 76.9% | 60.0% | 66.7% | 100% |
| + Hybrid search (BM25 + dense) | 89.7% | 75.6% | 55.6% | 100% |
| **+ Version-aware retrieval** (mean of 3 runs) | **92.3%** | **81.5%** | **85.2%** | **100%** |
| Agent: the model picks the tools (mean of 3 runs) | 92.3% | 75.6% | 66.7% | 66.7% |
| Router, search limited to the chosen life area (1 run) | 82.1% | 68.9% | 66.7% | 100% |
| Router, search not limited (1 run) | 92.3% | 82.2% | 88.9% | 100% |

The agent row is not a further step on top of the stages above. It is a different design: the same retrieval and registry, but a model decides which tool to call and how to search, instead of fixed code. It is compared against the best pipeline row.

The router rows are also a different design, not a further step. A model reads each message first and decides which part of the user's life it is about and whether it asks about the present, a change over time, or neither. The pipeline then answers with that decision. Both router rows are single runs.

The project registry doesn't change these numbers, since project status questions were already 5/5. It is checked separately. The MCP server doesn't answer questions itself, so it has no row.

All runs use the same local setup: `qwen2.5:7b` through Ollama, `nomic-embed-text` embeddings, top 5 chunks, and a Chroma vector store. The model never changes between stages, so improvements come from retrieval, not from a better model. The version-aware and agent rows are the mean of three runs at temperature 0 with a fixed seed. The earlier rows are single runs: until Stage 4 was finished, a bug meant the evaluation ran at Ollama's default temperature instead of 0 (found and fixed on 7 Oct). The exact package versions behind these numbers are in `requirements.txt`.

### By category (answer correct / source found)

| Category | n | Baseline | + Dedup | + Hybrid | + Version-aware | Agent |
|---|---|---|---|---|---|---|
| Simple lookup | 13 | 53.8 / 84.6 | 53.8 / 84.6 | 84.6 / 100 | 76.9 / 100 | 84.6 / 100 |
| Current state | 9 | 55.6 / 77.8 | 66.7 / 77.8 | 55.6 / 77.8 | 85.2 / 88.9 | 66.7 / 77.8 |
| Change over time | 6 | 33.3 / 83.3 | 50.0 / 83.3 | 50.0 / 100 | 66.7 / 100 | 50.0 / 100 |
| Project status | 5 | 80.0 / 80.0 | 80.0 / 80.0 | 100 / 100 | 100 / 100 | 100 / 80.0 |
| Across documents | 6 | 16.7 / 50.0 | 16.7 / 50.0 | 66.7 / 66.7 | 66.7 / 66.7 | 83.3 / 100 |
| Should refuse | 6 | 100 | 100 | 100 | 100 | 66.7 |

The router's per-category numbers are in the [failure log](eval/failure_log.md).

### What each stage taught us

**Baseline.** The right file is usually found, but the answer is still often wrong. Questions about how something changed find a correct source 83% of the time and get answered correctly only 33% of the time, because every version comes back with nothing to say which one is newer.

**Deduplication and grouping.** Two duplicate files were removed and the remaining 22 were grouped into 16 document families, each file labelled with its date and whether it is the latest version. This fixed two questions, including the rating question, but only by luck: removing a duplicate made room for the October chunk. Nothing was choosing the newest version yet.

**Hybrid search.** Adding keyword search (BM25) next to embedding search raised the share of questions with a correct source from 77% to 90%. Exact names and numbers like "PixelNet" or "1550" are where keyword search shines. But questions about the current state got *worse*. A query like "current Codeforces rating" matches all four handovers on keywords, so outdated versions came back into the results. **Finding more relevant text made the version problem worse, not better.**

**Version-aware retrieval.** Each question is now classified as asking about the present, about change over time, or as a plain lookup:

- **Present:** only the latest version of each document is searched. Outdated copies never reach the model.
- **Change over time:** every version is kept, missing versions of the same document are pulled in, and everything is shown to the model in date order.
- **Lookup:** nothing is filtered.

Current-state accuracy went from 55.6% to 85.2% (mean of three runs), and the rating question is now answered correctly by design rather than by luck.

**Project registry.** Questions like "which projects are paused?" shouldn't depend on which chunks happen to be retrieved, or on a model that can answer differently between runs. So the model reads each project file and handover once and fills in a fixed form for every project: name, status, reason and key result. Code then merges these into one record per project, keeping the newest version, the same rule retrieval uses. Status questions can now read from this small table and get the same answer every time. It also produces a one-page [project overview](docs/sample_vault_overview.md).

Checked by hand: all 5 statuses and key results are correct. The model was reliable when picking from a fixed list (status) and unreliable when writing free text: it wrote "N/A", repeated itself, or copied the status as the reason. So code checks every field before it is saved.

**Agent.** Instead of fixed code deciding each step, a model (built with LangChain's `create_agent`) chooses between three tools: search the notes (and whether to look at the present, the history, or everything), look up one project's status, or list projects by status. Every answer must cite the files the tools actually returned, and code checks this.

The model picked the right time mode on all 15 time-sensitive questions, better than the rule-based classifier (12 of 15). It also did better on lookups (84.6% vs 76.9%) and on questions that need several documents (83.3% vs 66.7%), because it writes its own search queries and can search more than once. But overall it scored 75.6% against the pipeline's 81.5%. With a 7B model, the losses come from the model's own decisions, not from where it looks:

- The first version scored 57.8%. It used the project registry for questions that had nothing to do with status, and it answered "I don't know" without searching at all.
- Narrowing the registry tools to status questions only, and having code send one follow-up ("search first") when the model refuses without searching, raised it to 68.9%.
- The model often found the right answer and then forgot to cite it, so the citation check threw correct answers away. Having code ask once for citations before blocking raised it to 75.6%.

The rule that came out of this: **a prompt can ask the model to follow a rule, but only code can make sure it did.** Each fix was written for a type of failure, not for specific questions, and the agent was frozen before the final three runs.

**Router.** To make Jarvis usable as a chat, every message now goes through a small model call first. It decides which life areas the message is about (projects, career, study, personal), whether it asks about the present, a change or neither, and what kind of message it is (a question, a decision, talking something through, or small talk). It also rewrites follow-ups like "and before that?" into full questions. The life areas, the folders behind them and which folders are private all live in one file, `config.yaml`.

The first version also limited the search to the folders of the chosen life areas. That cost 13 points: 68.9% against 82.2%, with the correct source found 82.1% of the time instead of 92.3%. When the model picks the wrong area, the right file is removed before search ranking ever sees it, and nothing later can bring it back. With the same router and no search limit, accuracy matched the pipeline exactly (82.2%). So the life area now chooses the answer's tone and which model may see the message, not what gets searched.

The lesson: **a filter is only as safe as whatever decides it.** Filtering to the latest version works because it reads dates computed by code. Filtering by life area failed because it read a 7B model's guess.

The model also picked the right time mode on only 11 of the 15 time-sensitive questions, one fewer than the rule-based classifier. The router's value is privacy, tone and follow-ups, not better time routing.

Privacy is enforced in code, and a test suite checks it with a planted marker string:

- A message that touches any private area runs only on the local model. If that model is down, Jarvis says so instead of quietly using a hosted one.
- Answers to non-private messages never see earlier private messages in the conversation, on any model.
- Before any call to a hosted model, code checks again that nothing private is inside, and stops if it is.

**MCP server.** The last stage makes Jarvis usable from other AI apps. It runs as an MCP server: an app like Claude Desktop, Claude Code or Cursor starts it as a background process and calls its tools. It offers the same three tools as the agent (search with a time mode, one project's status, list projects), plus the project overview as a document the user can attach.

It returns search results, not answers. Inside those apps the model reading the results is much stronger than qwen 7B, and the evaluation showed that reading, not finding, is where the 7B model fails.

Anything a tool returns goes to that app's model, which is usually hosted, so only folders marked shareable are searched, and every result is checked again before it is returned. A test plants a private chunk in the search results and checks that it never comes out. The server is tested in memory in the test suite, and over a real connection with `jarvis check`, which launches it exactly the way an app does. It has not yet been tried inside Claude Desktop itself.

### Honest limits

- **The set is small.** One question moves the overall score by 2.2 points and a category score by up to 20. Read small differences with caution.
- **Run-to-run variation.** Three identical runs of the pipeline (temperature 0, fixed seed) still differed by one question. On a GPU, tiny floating-point differences can flip a near-tie between two tokens even with greedy decoding. So a one-question difference between stages (2.2 points overall, 11 points on the 9-question current-state category) is noise. The big jumps are not. The three agent runs happened to come out identical.
- **Key-fact scoring is imperfect.** An answer counts as correct if it contains every expected key fact. A manual review of one run found one wrong answer scored as correct and one correct answer scored as wrong. An LLM judge, spot-checked by hand, is planned as a second scorer.
- **The remaining failures are mostly the model, not retrieval.** For both of the remaining "change over time" failures in the pipeline, every relevant version is now retrieved and shown in date order, and the 7B model still mixes up which source said what. Running the same evaluation with a stronger model is planned.
- **The agent's "source found" is measured more loosely.** It counts any file returned by any tool call, while the pipeline counts a fixed top 5. Compare the two on answer correctness.
- **The agent still guesses on two refusal questions.** It correctly says the notes don't state the answer, then adds a guess anyway. The prompt forbids this; a 7B model doesn't always listen.
- **The registry's reasons are partial.** Only 2 of 5 projects have a real stated reason; the other three are finished or active projects with no reason in the notes, and the model fills in something anyway.
- **Personal notes can appear in non-personal answers.** With the search not limited, a question about projects can retrieve a chunk from a private folder. When that happens the answer is moved to the local model, so nothing private leaves the machine, but it can still show up in an unrelated answer.
- **Versions are tracked per file, not per section.** A log file with one dated entry per contest counts as a single, always-latest document, so an August entry can rank above October's handover in a current-state search. Dating each section from its heading would fix this.
- **Privacy is per folder.** Real notes mix work and personal text in one file: the sample handovers are shareable but contain a "Mental State" section, which the MCP server will return. Marking such folders private, or naming private sections in the config (not built yet), is the fix.

---

## How it works

Indexing runs once, offline, and labels every chunk with version information. At question time, retrieval reads those labels.

```
INDEXING  (jarvis ingest)

  notes folder
     │
     ├─ load files            skip folders named skip*
     ├─ date each file        from the filename, else the document header,
     │                        else the file's modified time (marked as weak)
     ├─ remove duplicates     exact copies by content hash; near-copies only
     │                        if they also share the same date
     ├─ group versions        files with the same name apart from date or
     │                        v1/v2 form one family, newest marked as latest;
     │                        folders marked "not versioned" (diaries) keep
     │                        every file as its own entry
     ├─ split into chunks     by markdown headings
     └─ store in Chroma       with source, folder, date, family and is_latest

PROJECT REGISTRY  (jarvis registry)

  project folders from config.yaml
     ├─ read each file once   the model fills a fixed form per project
     ├─ check every field     code rejects "N/A", metrics without numbers, etc.
     └─ merge                 one record per project, newest version wins

QUESTION TIME, PIPELINE  (jarvis ask)

  question
     ├─ classify              present / change over time / lookup
     ├─ search                dense + BM25, merged by rank (RRF);
     │                        "present" questions search latest versions only
     ├─ expand                "change" questions pull in missing versions
     ├─ order                 "change" questions sorted oldest to newest
     └─ answer                each source shown with its date and whether it
                              is the latest version; the model must cite
                              sources or say it doesn't know

QUESTION TIME, AGENT  (jarvis ask --agent)

  question
     ├─ model picks a tool    search_notes (present / history / any),
     │                        get_project_status, or list_projects
     ├─ tools run             the same retrieval and registry as above
     ├─ model answers         from the tool results, citing file paths
     └─ code checks           refused without searching → told to search once;
                              no valid citation → asked to cite once;
                              still uncited → replaced with "I don't know"

QUESTION TIME, ROUTER  (jarvis chat)

  message
     ├─ route                 local model fills a fixed form: rewritten question,
     │                        life areas, time mode, message type
     ├─ search                same version-aware search as the pipeline,
     │                        using the router's time mode
     ├─ choose model          anything private → local model only, no fallback
     ├─ build the prompt      base rules + tone for the message type and area
     │                        + the last 4 exchanges of this conversation
     │                        (earlier private ones left out for non-private answers)
     └─ remember              the exchange is saved to this conversation's thread

MCP SERVER  (jarvis mcp)

  app (Claude Desktop, Claude Code, Cursor) starts Jarvis, talks over stdin/stdout
     ├─ search_notes          version-aware search over SHAREABLE folders only,
     │                        each result re-checked before it is returned
     ├─ get_project_status    registry lookups, refused if the registry's
     ├─ list_projects         folders are private
     └─ jarvis://overview     the project overview, attachable as a document
```

A few decisions worth explaining:

- **Dates come before deduplication.** Two versions of a handover can be 90% identical with one changed number. Treating them as duplicates would throw away the newer fact, so near-duplicates must also share a date.
- **Version information is decided per file and stored per chunk.** A chunk inherits its file's date and family, so retrieval can filter without re-reading anything.
- **Search results are merged by rank, not score.** Keyword scores and embedding distances are on different scales. Reciprocal Rank Fusion avoids normalising them.
- **Weak dates are hidden from the model.** Files dated only by modified time show as "undated", because a copy date would make an old file look like the newest one. The agent's project history follows the same rule.
- **The question classifier is still rule-based in the pipeline.** It is fast, free, testable, and routes 12 of the 15 time-sensitive questions correctly. The agent routes all 15 but costs accuracy elsewhere; the router's model gets 11.
- **The model reads, code decides.** In the registry, the model only extracts what each file says. Dates, sources and which version wins are handled by code, so they can't be invented. In the agent, code checks every citation against the files the tools actually returned.
- **Three tools, not five.** A timeline tool and an "have I planned this already" tool were folded into search and the prompt. Overlapping tools make a small model pick the wrong one.
- **The router always runs on the local model.** It reads every message before anyone knows whether the message is private, so it can never be a hosted model.
- **The MCP server returns evidence, not answers.** The app's own model is a better reader than a local 7B model, so routing answers through qwen would put the weakest reader back in the loop.
- **Everything is configured from one file, and privacy fails closed.** `jarvis init` marks every folder private, folders missing from the config are treated as private, and relative paths resolve against the config file, so the same config works no matter where Jarvis is started from.

---

## Development

```bash
pip install -e ".[dev]"
python -m pytest                        # unit tests (also run in CI on Python 3.11 and 3.12)
python eval/run_eval.py                 # the 45-question evaluation on the sample vault
python eval/run_router_eval.py          # router accuracy on labelled messages
python scripts/agent_checkpoint.py      # 5 fixed questions through the agent, with a trace
python scripts/compare_runs.py A.json B.json   # which questions flipped between two eval runs
```

Set `ANSWER_MODE` at the top of `eval/run_eval.py` to `"pipeline"`, `"agent"` or `"router"`. `requirements.txt` holds the exact package versions behind the published numbers; `pyproject.toml` holds the version ranges for installing.

The code talks to Ollama at `http://127.0.0.1:11434` directly, so an `OLLAMA_HOST=0.0.0.0` setting (used for Docker) doesn't break it. To use a hosted model for the agent, copy `.env.example` to `.env` and set `JARVIS_LLM_PROVIDER=openai_compat` and the `JARVIS_*` values.

## Project layout

```
config.yaml          sample-vault config: notes folder, privacy, life areas, models
pyproject.toml       package and the `jarvis` command
data/sample-vault/   fictional test corpus, safe to share
docs/                generated project overview
eval/                questions, evaluation runners, results, failure log
scripts/             dev tools: agent checkpoint, run comparison
jarvis/main.py       the `jarvis` command
jarvis/workspace.py  `jarvis init`
jarvis/ingest/       loading, dating, deduplication, grouping, chunking, indexing
jarvis/retrieval/    vector store, BM25, hybrid search, version-aware ranking, filters
jarvis/registry/     project registry: extraction, merging, lookups, overview
jarvis/agent/        agent tools, prompt, and the agent loop with citation checks
jarvis/router/       config, classifier, the router (LangGraph), privacy rules, memory
jarvis/interfaces/   pipeline CLI, chat, MCP server and its check
tests/               unit tests for every layer, including privacy and the MCP server
```

---

## Privacy

The sample vault is fictional, so the project can be tried and evaluated in public. Real notes are only ever used locally, stay out of the repository, and are embedded with a local model. Each folder is marked shareable or private in `config.yaml`; `jarvis init` starts every folder as private, and a folder that isn't listed is treated as private. Private messages are answered only by the local model, and private folders are never returned over MCP.