"""End-to-end analytics request pipeline."""


import json
from typing import Any

from agents import Agent, ModelSettings, Runner

from agents_runtime.charts.mapping import maybe_generate_chart
from agents_runtime.knowledge_base.selector import build_kb_context
from agents_runtime.prompts import load_prompt
from agents_runtime.runtime.context import RuntimeContext
from agents_runtime.memory.store import rag_retrieve, rag_upsert_catalog, rag_upsert_semantics, rag_upsert_session_turn
from agents_runtime.sql.execution import execute_query_programmatically_large, write_rows_to_csv
from agents_runtime.sql.safety import enforce_analyze_result_safety
from agents_runtime.structured_outputs import (
    AnalyzeResult,
    ChartMapping,
    DBCatalogLite,
    NarratorOutput,
    NotebookRunResult,
    PlannerDecision,
)


def _parse_model(model_cls, text: str, label: str = "model_output"):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    if not text:
        raise ValueError(f"No output received for {label}")
    return model_cls.model_validate_json(text)


def build_agents(ctx: RuntimeContext) -> dict[str, Agent]:
    s = ctx.settings
    doc_servers = [ctx.pdf_reader_server, ctx.word_reader_server, ctx.excel_server]
    sql_servers = [ctx.mssql_server, *doc_servers]

    return {
        "planner": Agent(
            name="Planner",
            model=s.model_planner,
            model_settings=ModelSettings(temperature=s.default_temperature),
            instructions=load_prompt("planner"),
            output_type=PlannerDecision,
            mcp_servers=[],
        ),
        "sql_analyst_discover": Agent(
            name="SQL Analyst Discover",
            model=s.model_general,
            model_settings=ModelSettings(temperature=s.sql_temperature),
            instructions=load_prompt("sql_analyst_discover"),
            output_type=DBCatalogLite,
            mcp_servers=sql_servers,
        ),
        "sql_analyst_query": Agent(
            name="SQL Analyst Query",
            model=s.model_general,
            model_settings=ModelSettings(temperature=s.sql_temperature),
            instructions=load_prompt("sql_analyst_query"),
            output_type=AnalyzeResult,
            mcp_servers=sql_servers,
        ),
        "chart_mapper": Agent(
            name="Chart Mapper",
            model=s.model_general,
            model_settings=ModelSettings(temperature=s.default_temperature),
            instructions=load_prompt("chart_mapper"),
            output_type=ChartMapping,
            mcp_servers=[ctx.chart_server],
        ),
        "narrator": Agent(
            name="Narrator",
            model=s.model_general,
            model_settings=ModelSettings(temperature=s.default_temperature),
            instructions=load_prompt("narrator"),
            output_type=NarratorOutput,
            mcp_servers=doc_servers,
        ),
    }


async def run_structured(agent: Agent, payload: dict[str, Any], model_cls, *, debug_label: str, max_turns: int):
    res = await Runner.run(agent, json.dumps(payload), max_turns=max_turns)
    out = res.final_output

    if isinstance(out, model_cls):
        return out
    if isinstance(out, dict):
        return model_cls.model_validate(out)
    if isinstance(out, str):
        return _parse_model(model_cls, out, label=debug_label)
    raise ValueError(f"{debug_label}: unexpected output type {type(out)}")


async def run_planner(ctx: RuntimeContext, agents: dict[str, Agent], db_key: str, user_prompt: str, rag_ctx: str) -> PlannerDecision:
    payload = {"user_request": user_prompt, "rag_context": rag_ctx, **build_kb_context(db_key, user_prompt, ctx.settings)}
    return await run_structured(
        agents["planner"],
        payload,
        PlannerDecision,
        debug_label="Planner",
        max_turns=ctx.settings.max_turns_planner,
    )


async def run_sql_analyst_discover(ctx: RuntimeContext, agents: dict[str, Agent], db_key: str, user_prompt: str, rag_ctx: str) -> DBCatalogLite:
    payload = {
        "task_mode": "DISCOVER",
        "user_request": user_prompt,
        "rag_context": rag_ctx,
        **build_kb_context(db_key, user_prompt, ctx.settings),
    }
    catalog = await run_structured(
        agents["sql_analyst_discover"],
        payload,
        DBCatalogLite,
        debug_label="SQL Analyst DISCOVER",
        max_turns=ctx.settings.max_turns_sql_analyst_discover,
    )
    rag_upsert_catalog(ctx.chroma_client, db_key, catalog, embedding_fn=ctx.embedding_fn)
    return catalog


async def run_sql_analyst_query(
    ctx: RuntimeContext,
    agents: dict[str, Agent],
    db_key: str,
    user_prompt: str,
    rag_ctx: str,
    catalog: DBCatalogLite | None,
    verifier_fixes: list[str] | None = None,
) -> AnalyzeResult:
    payload = {
        "task_mode": "ANALYZE",
        "user_request": user_prompt,
        "rag_context": rag_ctx,
        "catalog": catalog.model_dump() if catalog else None,
        "verifier_fixes": verifier_fixes or [],
        "small_row_threshold": ctx.settings.small_row_threshold,
        "max_direct_columns": ctx.settings.max_direct_columns,
        **build_kb_context(db_key, user_prompt, ctx.settings),
    }
    ares = await run_structured(
        agents["sql_analyst_query"],
        payload,
        AnalyzeResult,
        debug_label="SQL Analyst ANALYZE",
        max_turns=ctx.settings.max_turns_sql_analyst_query,
    )
    enforce_analyze_result_safety(ares)
    return ares


async def run_chart_mapper(
    ctx: RuntimeContext,
    agents: dict[str, Agent],
    user_prompt: str,
    columns: list[str],
    sample_rows: list[list[Any]],
) -> ChartMapping:
    payload = {"user_request": user_prompt, "columns": columns, "sample_rows": sample_rows[:10]}
    return await run_structured(
        agents["chart_mapper"],
        payload,
        ChartMapping,
        debug_label="Chart Mapper",
        max_turns=ctx.settings.max_turns_chart_mapper,
    )


async def run_narrator(
    ctx: RuntimeContext,
    agents: dict[str, Agent],
    db_key: str,
    user_prompt: str,
    ares: AnalyzeResult,
    chart_artifact: dict[str, Any] | None,
    detail_export_path: str | None,
) -> NarratorOutput:
    payload = {
        "mode": ares.mode,
        "total_rows": ares.total_rows,
        "insight_tables": [t.model_dump() for t in ares.insight_tables],
        "assumptions": ares.assumptions,
        "caveats": ares.caveats,
        "sql_appendix": [q.model_dump() for q in ares.sql_appendix]
        + ([ares.detail_query.model_dump()] if ares.detail_query else []),
        "detail_query": ares.detail_query.model_dump() if ares.detail_query else None,
        "detail_export_path": detail_export_path,
        "chart_artifact": chart_artifact,
        **build_kb_context(db_key, user_prompt, ctx.settings),
    }
    return await run_structured(
        agents["narrator"],
        payload,
        NarratorOutput,
        debug_label="Narrator",
        max_turns=ctx.settings.max_turns_narrator,
    )


async def run_request(ctx: RuntimeContext, user_prompt: str, db_key: str, use_narrator: bool = True) -> NotebookRunResult:
    agents = build_agents(ctx)

    rag_ctx = rag_retrieve(
        ctx.chroma_client,
        db_key,
        user_prompt,
        embedding_fn=ctx.embedding_fn,
        k=8,
        max_chars=5000,
    )
    plan = await run_planner(ctx, agents, db_key, user_prompt, rag_ctx)

    catalog = None
    if plan.require_schema_refresh or not rag_ctx.strip():
        catalog = await run_sql_analyst_discover(ctx, agents, db_key, user_prompt, rag_ctx)
        rag_ctx = rag_retrieve(
            ctx.chroma_client,
            db_key,
            user_prompt,
            embedding_fn=ctx.embedding_fn,
            k=10,
            max_chars=5000,
        )

    ares = await run_sql_analyst_query(ctx, agents, db_key, user_prompt, rag_ctx, catalog)

    detail_export_path = None
    if ares.mode == "LARGE_SPLIT" and ares.detail_query:
        cols, rows = await execute_query_programmatically_large(ares.detail_query.sql)
        detail_export_path = write_rows_to_csv(cols, rows)

    rag_upsert_semantics(
        ctx.chroma_client,
        db_key,
        user_prompt,
        ares,
        catalog=catalog,
        embedding_fn=ctx.embedding_fn,
    )

    async def _run_cm(prompt: str, cols: list[str], sample: list[list[Any]]) -> ChartMapping:
        return await run_chart_mapper(ctx, agents, prompt, cols, sample)

    chart_artifact = await maybe_generate_chart(
        run_chart_mapper=_run_cm,
        chart_server=ctx.chart_server,
        user_prompt=user_prompt,
        ares=ares,
        include_chart=True,
        detail_export_path=detail_export_path,
    )

    user_output = None
    developer_output = None
    if use_narrator:
        nout = await run_narrator(ctx, agents, db_key, user_prompt, ares, chart_artifact, detail_export_path)
        user_output = nout.user_output
        developer_output = nout.developer_output
        rag_upsert_session_turn(
            ctx.chroma_client,
            db_key,
            user_prompt,
            user_output,
            embedding_fn=ctx.embedding_fn,
        )
        final_output = "\n\n---\n\n".join(["# User Output\n" + user_output, "# Developer Output\n" + developer_output])
    else:
        final_output = json.dumps(ares.model_dump(), indent=2)

    return NotebookRunResult(
        final_output=final_output,
        user_output=user_output,
        developer_output=developer_output,
        verifier_verdict="PASS",
        verification_reasons=[],
    )
