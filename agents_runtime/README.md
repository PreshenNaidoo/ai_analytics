# agents_runtime

`agents_runtime` is the Python backend runtime for the AI analytics agents.

It contains:
- agent orchestration logic
- structured outputs (Pydantic models)
- SQL safety and execution helpers
- Chroma memory helpers
- knowledge base file selection logic
- MCP server wiring

This package is kept separate from API and UI services so the same runtime can be reused by:
- a FastAPI service
- background workers
- local notebooks/tests

## Current status

Behavior was extracted from:
- `experiments/experiment_multi_agent_with_chat.ipynb`

The notebook is still useful as a reference, but this folder is now the organized runtime codebase.

## Folder layout

Main source folder:
- `agents_runtime/src/agents_runtime`

Key modules:
- `config.py`: runtime configuration (`RuntimeSettings`)
- `structured_outputs.py`: output schemas used by agents
- `prompts.py` + `prompts/*.md`: prompt loading and prompt files
- `mcp/servers.py`: MCP server construction (MSSQL, chart, PDF, Word, Excel)
- `runtime/context.py`: runtime context assembly
- `runtime/pipeline.py`: main analytics pipeline (`run_request`)
- `runtime/chat.py`: chat runner + streaming helpers
- `memory/store.py`: Chroma collections, retrieval, and upserts
- `sql/safety.py`: SQL guardrails (read-only checks)
- `sql/execution.py`: programmatic query execution and CSV helpers
- `charts/mapping.py`: chart mapping and chart artifact generation
- `knowledge_base/selector.py`: knowledge base pathing and candidate-file selection

Tests and smoke notebook:
- `agents_runtime/tests/smoke_agents_runtime.ipynb`

## Quick smoke test

1. Open:
- `agents_runtime/tests/smoke_agents_runtime.ipynb`

2. Run cells in order:
- import/setup
- prompt definitions
- runtime context setup
- final streamed chat test cell

3. Expected result:
- markdown output streams in one block
- final response includes User Output and Developer Output

## Environment

Runtime expects database and OpenAI credentials in `.env` at repo root.

Common variables:
- `MSSQL_CONNECTION_STRING`
- `OPENAI_API_KEY`
- optional runtime overrides like `MODEL_GENERAL`, `MAX_TURNS_*`, `CHROMA_DIR`

## Notes

- This package intentionally focuses on backend runtime logic only.
- API service and frontend are planned as separate layers.
