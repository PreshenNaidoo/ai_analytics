# agents_runtime

Pure Python runtime package for AI analytics agents.

This package is intentionally separated from web/API services so the same agent logic can be reused by:
- FastAPI service (later)
- workers/jobs (later)
- notebooks during migration

Current source of truth for behavior is still:
`experiments/experiment_multi_agent_with_chat.ipynb`

The migration strategy is incremental: copy working logic into modules here without changing notebook behavior.
