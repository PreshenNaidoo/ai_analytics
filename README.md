# ai_analytics

`ai_analytics` is a prompt-to-analytics workspace. The goal is to let an agent answer business questions against trusted data sources while keeping the runtime reusable, testable, and careful around SQL execution.

In practice, a user can ask a question in plain English, the runtime can inspect the database schema, build the SQL it needs behind the scenes, run the query safely, and turn the result into an analytics answer. When a chart would make the answer clearer, it can also map the result into a graph or plot.

The current codebase is centered on the Python runtime in `agents_runtime`. That runtime handles agent orchestration, structured outputs, SQL safety, query execution, chart mapping, Chroma-backed memory, knowledge base file selection, and MCP server setup. API and UI layers live separately under `services` and `apps` so they can build on the same runtime instead of duplicating agent logic.

## Repository Layout

- `agents_runtime/`: Python backend runtime for the analytics agents.
- `agents_runtime/src/agents_runtime/`: runtime package source.
- `agents_runtime/tests/`: smoke notebook, unit tests, and integration test placeholder.
- `apps/web/`: web app.
- `services/`: service layer projects.
- `experiments/`: notebooks and earlier prototypes.
- `knowledge_base/`: source files used by the runtime when selecting supporting context.
- `SETUP_WINDOWS.md`: Windows and WSL setup notes.

## Runtime Package

The runtime code was extracted from `experiments/experiment_multi_agent_with_chat.ipynb`. The notebook is still useful as a reference, but the maintained implementation is now in `agents_runtime/src/agents_runtime`.

Key modules:

- `config.py`: runtime settings.
- `structured_outputs.py`: Pydantic models returned by agents.
- `prompts.py` and `prompts/*.md`: prompt loading and prompt files.
- `mcp/servers.py`: MCP server construction for MSSQL, charts, PDF, Word, and Excel.
- `runtime/context.py`: runtime context assembly.
- `runtime/pipeline.py`: main analytics pipeline.
- `runtime/chat.py`: chat runner and streaming helpers.
- `memory/store.py`: Chroma collections, retrieval, and upserts.
- `sql/safety.py`: read-only SQL guardrails.
- `sql/execution.py`: programmatic query execution and CSV helpers.
- `charts/mapping.py`: chart mapping and chart artifact generation.
- `knowledge_base/selector.py`: knowledge base pathing and candidate file selection.

## Environment

The runtime expects credentials and connection settings in a `.env` file at the repository root.

Common variables:

- `MSSQL_CONNECTION_STRING`
- `OPENAI_API_KEY`
- `MODEL_GENERAL`
- `MAX_TURNS_*`
- `CHROMA_DIR`

Only `MSSQL_CONNECTION_STRING` and `OPENAI_API_KEY` are expected for the normal path. The others are optional runtime overrides.

## Setup

Python 3.12 or newer is required.

From the repository root:

```bash
uv sync
```

For Windows and WSL notes, see `SETUP_WINDOWS.md`.

## Smoke Test

The quickest end-to-end check is the smoke notebook:

```text
agents_runtime/tests/smoke_agents_runtime.ipynb
```

Run the cells in order:

1. Import and setup.
2. Prompt definitions.
3. Runtime context setup.
4. Final streamed chat test.

The expected result is a streamed markdown response with both user-facing output and developer output.

There are early unit tests under `agents_runtime/tests/unit`, but the smoke notebook is the current practical check for the full agent flow.

## Notes

- The runtime package is deliberately backend-only.
- API services, background workers, notebooks, and the web app should call into the runtime rather than reimplementing orchestration.
- SQL helpers are designed around read-only execution. Keep data-changing behavior out of the analytics path unless the runtime is deliberately extended for it.
