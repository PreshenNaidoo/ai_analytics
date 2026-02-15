"""Runtime settings for agents_runtime."""


from dataclasses import dataclass
import os


@dataclass(frozen=True)
class RuntimeSettings:
    # Models and temperatures
    model_general: str = "gpt-4.1-mini"
    model_planner: str = "gpt-4.1-mini"
    default_temperature: float = 0.5
    sql_temperature: float = 0.1

    # Workflow thresholds
    small_row_threshold: int = 1000
    max_direct_columns: int = 30

    # Turn budgets
    max_turns_planner: int = 12
    max_turns_sql_analyst_discover: int = 12
    max_turns_sql_analyst_query: int = 30
    max_turns_chart_mapper: int = 12
    max_turns_narrator: int = 12
    max_turns_chat_orchestrator: int = 12

    # Runtime paths and KB
    chroma_dir: str = ".chroma_ai_analytics"
    knowledge_base_dir: str = "knowledge_base"
    shared_docs_subdir: str = "_shared"
    max_kb_candidate_files: int = 30
    kb_allowed_extensions: tuple[str, ...] = (".pdf", ".doc", ".docx", ".xlsx", ".xls", ".xlsm")

    # MCP
    mcp_client_timeout_seconds: int = 60

    @staticmethod
    def from_env() -> "RuntimeSettings":
        base = RuntimeSettings()
        return RuntimeSettings(
            model_general=os.getenv("MODEL_GENERAL", base.model_general),
            model_planner=os.getenv("MODEL_PLANNER", base.model_planner),
            default_temperature=float(os.getenv("DEFAULT_AGENT_TEMPERATURE", str(base.default_temperature))),
            sql_temperature=float(os.getenv("SQL_ANALYST_TEMPERATURE", str(base.sql_temperature))),
            small_row_threshold=int(os.getenv("SMALL_ROW_THRESHOLD", str(base.small_row_threshold))),
            max_direct_columns=int(os.getenv("MAX_DIRECT_COLUMNS", str(base.max_direct_columns))),
            max_turns_planner=int(os.getenv("MAX_TURNS_PLANNER", str(base.max_turns_planner))),
            max_turns_sql_analyst_discover=int(
                os.getenv("MAX_TURNS_SQL_ANALYST_DISCOVER", str(base.max_turns_sql_analyst_discover))
            ),
            max_turns_sql_analyst_query=int(os.getenv("MAX_TURNS_SQL_ANALYST_QUERY", str(base.max_turns_sql_analyst_query))),
            max_turns_chart_mapper=int(os.getenv("MAX_TURNS_CHART_MAPPER", str(base.max_turns_chart_mapper))),
            max_turns_narrator=int(os.getenv("MAX_TURNS_NARRATOR", str(base.max_turns_narrator))),
            max_turns_chat_orchestrator=int(os.getenv("MAX_TURNS_CHAT_ORCHESTRATOR", str(base.max_turns_chat_orchestrator))),
            chroma_dir=os.getenv("CHROMA_DIR", base.chroma_dir),
            knowledge_base_dir=os.getenv("KNOWLEDGE_BASE_DIR", base.knowledge_base_dir),
            shared_docs_subdir=os.getenv("SHARED_DOCS_SUBDIR", base.shared_docs_subdir),
            max_kb_candidate_files=int(os.getenv("MAX_KB_CANDIDATE_FILES", str(base.max_kb_candidate_files))),
            mcp_client_timeout_seconds=int(os.getenv("MCP_CLIENT_TIMEOUT_SECONDS", str(base.mcp_client_timeout_seconds))),
        )
