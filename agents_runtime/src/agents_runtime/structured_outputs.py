"""Domain models extracted from the working notebook."""

from typing import Literal

from pydantic import BaseModel, Field


class PlannerDecision(BaseModel):
    require_schema_refresh: bool = True
    rationale: str = ""


class CandidateTable(BaseModel):
    name: str
    confidence: float = Field(ge=0, le=1)
    why: str


class ColumnInfo(BaseModel):
    col: str
    type: str | None = None


class TableColumnsEntry(BaseModel):
    table: str
    columns: list[ColumnInfo] = Field(default_factory=list)


class EavHintLite(BaseModel):
    table: str
    attribute_cols: list[str] = Field(default_factory=list)
    value_cols: list[str] = Field(default_factory=list)


class DBCatalogLite(BaseModel):
    candidate_fact_tables: list[CandidateTable] = Field(default_factory=list)
    table_columns: list[TableColumnsEntry] = Field(default_factory=list)
    eav_hints: list[EavHintLite] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


JsonCell = str | int | float | bool | None


class AnswerTable(BaseModel):
    name: str
    columns: list[str]
    rows: list[list[JsonCell]]


class SQLQuery(BaseModel):
    name: str
    sql: str


class AnalyzeResult(BaseModel):
    mode: Literal["SMALL_DIRECT", "LARGE_SPLIT"]
    count_sql: str
    total_rows: int = Field(ge=0)
    insight_tables: list[AnswerTable] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    sql_appendix: list[SQLQuery] = Field(default_factory=list)
    detail_query: SQLQuery | None = None


class ChartMapping(BaseModel):
    applicable: bool
    chart_type: Literal["line", "column", "bar", "pie"] = "line"
    x_field: str | None = None
    y_field: str | None = None
    category_field: str | None = None
    value_field: str | None = None
    reason: str = ""


class NarratorOutput(BaseModel):
    user_output: str
    developer_output: str


class NotebookRunResult(BaseModel):
    final_output: str
    user_output: str | None = None
    developer_output: str | None = None
    verifier_verdict: Literal["PASS", "FAIL"]
    verification_reasons: list[str] = Field(default_factory=list)
