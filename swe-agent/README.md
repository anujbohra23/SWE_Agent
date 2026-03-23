# SWE-Agent — Autonomous Software Engineering Agent

An MVP autonomous agent that reads a GitHub-style issue, retrieves relevant code from a local repository, generates a patch, applies it to a sandboxed copy, runs pytest, and retries with self-correction up to 3 times.

---

## Architecture

```
Issue Input
  → Planner         (reads issue + retrieved chunks, writes a plan)
  → Retriever       (embeds chunks, FAISS similarity search)
  → Patcher         (generates structured search/replace edits)
  → Executor        (applies patch to sandbox, runs pytest)
  → Reflector       (on failure: summarizes errors, retries up to 3×)
  → Reporter        (formats final result)
```

Implemented as a **LangGraph** stateful graph with typed state.

---

## Quickstart

### 1. Clone / download

```bash
git clone <this-repo>
cd swe-agent
```

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — set OPENAI_API_KEY and optionally OPENAI_BASE_URL / MODEL_NAME
```

### 4. Run against the bundled demo repo

```bash
python main.py \
  --repo data/demo_repo \
  --issue "The function add_numbers in calculator.py returns the wrong result when both inputs are negative. Fix it." \
  --test-cmd "pytest tests/ -v"
```

### 5. Run with your own repository

```bash
python main.py \
  --repo /path/to/your/python/repo \
  --issue "Describe the bug here" \
  --test-cmd "pytest tests/ -v" \
  --max-retries 3
```

---

## Output

The agent prints a structured JSON result containing:

| Field | Description |
|---|---|
| `success` | Whether tests passed after patching |
| `retry_count` | How many patch attempts were made |
| `planned_files` | Files the planner targeted |
| `retrieved_files` | Files surfaced by retrieval |
| `final_diff` | Unified diff of applied changes |
| `final_test_output` | Last pytest stdout/stderr |
| `summary` | One-paragraph natural language summary |
| `sandbox_path` | Path to the modified sandbox copy |

A full JSON log is also written to `logs/run_<timestamp>.json`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *required* | API key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Override for local/proxy LLMs |
| `MODEL_NAME` | `gpt-4o` | Model to use |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model |
| `TOP_K_CHUNKS` | `20` | Chunks returned by retrieval |
| `MAX_RETRIES` | `3` | Max patch/test retry cycles |
| `TEST_TIMEOUT` | `120` | Seconds before test run is killed |
| `SANDBOX_BASE_DIR` | `/tmp/swe_agent_sandboxes` | Where sandbox copies are created |

---

## Project Layout

```
swe-agent/
├── app/
│   ├── config.py           # Settings (pydantic-settings)
│   ├── state.py            # LangGraph typed state
│   ├── schemas.py          # Pydantic models for LLM I/O
│   ├── graph.py            # LangGraph graph assembly
│   ├── prompts/
│   │   ├── planner.txt
│   │   ├── patcher.txt
│   │   └── reflector.txt
│   ├── tools/
│   │   ├── repo_ingest.py  # Walk repo, produce file list
│   │   ├── chunking.py     # Split files into chunks
│   │   ├── embeddings.py   # sentence-transformers wrapper
│   │   ├── retrieval.py    # FAISS index + query
│   │   ├── sandbox.py      # Copy repo to temp dir
│   │   ├── patch_apply.py  # Apply search/replace edits
│   │   ├── test_runner.py  # Run pytest, capture output
│   │   ├── diff_utils.py   # Generate unified diff
│   │   ├── failure_parser.py  # Parse pytest failures
│   │   └── llm.py          # OpenAI-compatible client
│   └── nodes/
│       ├── planner.py
│       ├── retriever.py
│       ├── patcher.py
│       ├── executor.py
│       ├── reflector.py
│       └── reporter.py
├── data/
│   └── demo_repo/          # Bundled buggy demo project
├── logs/                   # Run logs written here
├── main.py                 # CLI entry point
├── requirements.txt
├── .env.example
└── README.md
```

---

## Adding Docker Later

The `executor` node calls `app/tools/test_runner.py`.  
Replace `run_tests_local()` with `run_tests_docker()` — the rest of the graph is unchanged.  
A `Dockerfile.sandbox` template is included in `app/tools/test_runner.py` comments.

---

## Known Limitations (MVP)

- Python repositories only
- pytest only
- Local path input only (no GitHub URL cloning)
- Single-file or multi-file search/replace edits (no binary patches)
- No parallel retry branches