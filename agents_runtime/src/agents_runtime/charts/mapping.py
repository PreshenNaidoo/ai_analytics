"""Chart mapping and rendering helpers."""


import json
from typing import Any

from agents_runtime.structured_outputs import AnalyzeResult, ChartMapping
from agents_runtime.sql.execution import normalize_model_output, read_top_rows_from_csv


def coerce_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    try:
        return float(s)
    except Exception:
        return None


def numeric_score(rows: list[list[Any]], col_i: int, sample_n: int = 30) -> int:
    score = 0
    for r in rows[:sample_n]:
        if len(r) <= col_i:
            continue
        if coerce_float(r[col_i]) is not None:
            score += 1
    return score


def to_chart_data(rows: list[list[Any]], columns: list[str], mapping: ChartMapping) -> dict[str, Any]:
    idx = {c: i for i, c in enumerate(columns)}

    if mapping.chart_type in ["line", "column", "bar"]:
        if not mapping.x_field or not mapping.y_field:
            raise ValueError("Chart mapping missing x_field/y_field")
        xi = idx[mapping.x_field]
        yi = idx[mapping.y_field]

        if numeric_score(rows, yi) == 0 and numeric_score(rows, xi) > 0:
            xi, yi = yi, xi

        data = []
        for r in rows:
            if len(r) <= max(xi, yi):
                continue
            val = coerce_float(r[yi])
            if val is None:
                continue
            if mapping.chart_type == "line":
                data.append({"time": str(r[xi]), "value": val})
            else:
                data.append({"category": str(r[xi]), "value": val})

        if not data:
            raise ValueError("No numeric values available for chart y-axis")

        if mapping.chart_type == "line":
            return {
                "tool": "generate_line_chart",
                "input": {"data": data, "xField": "time", "yField": "value", "title": "Line chart"},
            }
        if mapping.chart_type == "bar":
            return {"tool": "generate_bar_chart", "input": {"data": data, "title": "Bar chart"}}
        return {"tool": "generate_column_chart", "input": {"data": data, "title": "Column chart"}}

    if mapping.chart_type == "pie":
        if not mapping.category_field or not mapping.value_field:
            raise ValueError("Pie mapping missing category/value fields")
        ci = idx[mapping.category_field]
        vi = idx[mapping.value_field]
        data = []
        for r in rows:
            if len(r) <= max(ci, vi):
                continue
            val = coerce_float(r[vi])
            if val is None:
                continue
            data.append({"category": str(r[ci]), "value": val})
        if not data:
            raise ValueError("No numeric values available for pie chart")
        return {
            "tool": "generate_pie_chart",
            "input": {"data": data, "angleField": "value", "colorField": "category", "title": "Pie chart"},
        }

    raise ValueError(f"Unsupported chart type: {mapping.chart_type}")


def extract_chart_image_url(result: Any) -> str | None:
    if not result or not getattr(result, "content", None):
        return None
    for part in result.content:
        txt = getattr(part, "text", None)
        if txt and isinstance(txt, str):
            s = txt.strip()
            if s.startswith("http"):
                return s
            try:
                obj = json.loads(normalize_model_output(s))
                if isinstance(obj, dict):
                    for k in ["image_url", "url", "chartUrl"]:
                        if isinstance(obj.get(k), str):
                            return obj[k]
            except Exception:
                pass
    return None


async def maybe_generate_chart(
    run_chart_mapper,
    chart_server,
    user_prompt: str,
    ares: AnalyzeResult,
    include_chart: bool,
    detail_export_path: str | None = None,
) -> dict[str, Any] | None:
    if not include_chart or not ares.insight_tables:
        return None

    t = ares.insight_tables[0]
    if len(t.columns) < 2 or not t.rows:
        return None

    mapping = await run_chart_mapper(user_prompt, t.columns, t.rows[:10])
    if not mapping.applicable:
        return None

    if detail_export_path:
        columns, top_rows = read_top_rows_from_csv(detail_export_path, n=2000)
        chart_source_cols = columns
        chart_source_rows = top_rows
    else:
        chart_source_cols = t.columns
        chart_source_rows = t.rows[:2000]

    if not chart_source_cols or not chart_source_rows:
        return None

    try:
        chart_cfg = to_chart_data(chart_source_rows, chart_source_cols, mapping)
    except Exception:
        return None

    result = await chart_server.call_tool(chart_cfg["tool"], chart_cfg["input"])
    image_url = extract_chart_image_url(result)
    if not image_url:
        return None

    return {
        "image_url": image_url,
        "mapping": mapping.model_dump(),
        "source": detail_export_path or "insight_table",
    }
