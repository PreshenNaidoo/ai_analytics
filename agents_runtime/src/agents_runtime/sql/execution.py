"""Programmatic SQL execution and CSV helpers."""


import ast
import asyncio
import csv
import json
import os
import re
import tempfile
from typing import Any

try:
    import pyodbc
except Exception:  # pragma: no cover
    pyodbc = None

from agents_runtime.sql.safety import check_select_only_sql


def normalize_model_output(text: str) -> str:
    """Normalize model text output by stripping markdown fences."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.I)
        text = re.sub(r"\s*```$", "", text.strip())
    return text.strip()


def extract_first_json_block(text: str) -> str:
    """Extract the first valid JSON object/array from free text."""
    s = (text or "")
    starts = [i for i in [s.find("{"), s.find("[")] if i >= 0]
    if not starts:
        raise ValueError("No JSON found")
    start = min(starts)
    stack: list[str] = []
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch in "[{":
            stack.append(ch)
        elif ch in "]}":
            if not stack:
                continue
            op = stack[-1]
            if (op == "{" and ch == "}") or (op == "[" and ch == "]"):
                stack.pop()
                if not stack:
                    return s[start : i + 1]
    raise ValueError("Unbalanced JSON block")


def extract_jsonish_from_tool_result(result: Any) -> Any:
    """Read JSON-like payloads from MCP tool result objects."""
    if not result or not getattr(result, "content", None):
        raise ValueError("Tool returned no content")

    for part in result.content:
        for attr in ("json", "data"):
            if not hasattr(part, attr):
                continue
            val = getattr(part, attr)
            if callable(val):
                try:
                    val = val()
                except TypeError:
                    continue
            if val is not None and not callable(val):
                return val

        txt = getattr(part, "text", None)
        if txt and not callable(txt):
            norm = normalize_model_output(str(txt))
            if not norm:
                continue
            try:
                return json.loads(norm)
            except Exception:
                continue

    first = result.content[0] if result.content else None
    first_text = getattr(first, "text", "") if first is not None else ""
    if first_text and not callable(first_text):
        return str(first_text)
    raise ValueError("Tool content had no parseable JSON/data payload")


def rows_from_result_obj(obj: Any):
    """Convert common tool result shapes into columns and rows."""
    if isinstance(obj, str):
        norm = normalize_model_output(obj)
        try:
            return rows_from_result_obj(json.loads(norm))
        except Exception:
            pass
        try:
            return rows_from_result_obj(json.loads(extract_first_json_block(norm)))
        except Exception:
            pass
        try:
            lit = ast.literal_eval(norm)
            return rows_from_result_obj(lit)
        except Exception:
            preview = norm[:240].replace("\n", " ")
            raise ValueError(f"Unsupported execute_query text payload: {preview}")

    if isinstance(obj, list):
        if not obj:
            return [], []
        if isinstance(obj[0], dict):
            columns = list(obj[0].keys())
            rows = [[r.get(c) for c in columns] for r in obj]
            return columns, rows
        if isinstance(obj[0], list):
            return [], obj

    if isinstance(obj, dict):
        if isinstance(obj.get("text"), str):
            return rows_from_result_obj(obj["text"])
        if isinstance(obj.get("result"), dict):
            return rows_from_result_obj(obj["result"])
        if isinstance(obj.get("output"), dict):
            return rows_from_result_obj(obj["output"])
        if isinstance(obj.get("data"), (dict, list)):
            return rows_from_result_obj(obj["data"])
        if isinstance(obj.get("rows"), list) and isinstance(obj.get("columns"), list):
            cols_raw = obj["columns"]
            if cols_raw and isinstance(cols_raw[0], dict):
                columns = [str(c.get("name") or c.get("column") or c.get("field") or "") for c in cols_raw]
            else:
                columns = [str(c) for c in cols_raw]
            rows_raw = obj["rows"]
            if rows_raw and isinstance(rows_raw[0], dict):
                if not columns or all(c == "" for c in columns):
                    columns = list(rows_raw[0].keys())
                rows = [[r.get(c) for c in columns] for r in rows_raw]
            else:
                rows = rows_raw
            return columns, rows
        if isinstance(obj.get("records"), list):
            return rows_from_result_obj(obj["records"])
        if isinstance(obj.get("items"), list):
            return rows_from_result_obj(obj["items"])
        if isinstance(obj.get("recordset"), list):
            return rows_from_result_obj(obj["recordset"])
        if isinstance(obj.get("resultset"), list):
            return rows_from_result_obj(obj["resultset"])
        if isinstance(obj.get("results"), list) and obj["results"]:
            return rows_from_result_obj(obj["results"][0])

    raise ValueError(f"Unsupported execute_query result format for export: {type(obj)}")


async def execute_query_programmatically(mssql_server, sql: str) -> tuple[list[str], list[list[Any]]]:
    """Run a safe read-only SQL query through the MSSQL MCP server."""
    reason = check_select_only_sql(sql)
    if reason:
        raise ValueError(f"Unsafe programmatic SQL: {reason}")

    try:
        result = await mssql_server.call_tool("execute_query", {"sql": sql})
    except Exception:
        result = await mssql_server.call_tool("execute_query", {"query": sql})

    obj = extract_jsonish_from_tool_result(result)
    return rows_from_result_obj(obj)


def build_pyodbc_connection_string() -> str:
    """Build a pyodbc connection string from environment variables."""
    raw = (os.getenv("MSSQL_CONNECTION_STRING") or "").strip()
    if raw and ("driver=" in raw.lower() or "dsn=" in raw.lower()):
        return raw

    host = (os.getenv("MSSQL_HOST") or "").strip()
    port = (os.getenv("MSSQL_PORT") or "1433").strip()
    database = (os.getenv("MSSQL_DATABASE") or "").strip()
    user = (os.getenv("MSSQL_USER") or "").strip()
    password = os.getenv("MSSQL_PASSWORD") or ""
    encrypt_raw = (os.getenv("MSSQL_ENCRYPT") or "true").strip().lower()
    encrypt = "yes" if encrypt_raw in {"1", "true", "yes", "y", "on"} else "no"

    missing = [
        k
        for k, v in {
            "MSSQL_HOST": host,
            "MSSQL_DATABASE": database,
            "MSSQL_USER": user,
            "MSSQL_PASSWORD": password,
        }.items()
        if not v
    ]
    if missing:
        raise RuntimeError(f"Missing DB env vars for pyodbc: {', '.join(missing)}")

    trust = "no" if encrypt == "yes" else "yes"
    return (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{host},{port};"
        f"Database={database};"
        f"Uid={user};"
        f"Pwd={password};"
        f"Encrypt={encrypt};"
        f"TrustServerCertificate={trust};"
    )


def execute_query_pyodbc_sync(sql: str) -> tuple[list[str], list[list[Any]]]:
    """Run SQL synchronously with pyodbc and return columns and rows."""
    if pyodbc is None:
        raise RuntimeError("pyodbc is not installed in this environment")
    conn_str = build_pyodbc_connection_string()
    conn = pyodbc.connect(conn_str)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        columns = [d[0] for d in (cur.description or [])]
        rows = [list(r) for r in cur.fetchall()]
        return columns, rows
    finally:
        conn.close()


async def execute_query_programmatically_large(sql: str) -> tuple[list[str], list[list[Any]]]:
    """Run large read-only SQL via a thread using pyodbc."""
    reason = check_select_only_sql(sql)
    if reason:
        raise ValueError(f"Unsafe programmatic SQL: {reason}")
    return await asyncio.to_thread(execute_query_pyodbc_sync, sql)


def write_rows_to_csv(columns: list[str], rows: list[list[Any]], prefix: str = "ai_analytics_detail") -> str:
    """Write query results to a temporary CSV file and return its path."""
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=".csv")
    os.close(fd)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(columns)
        w.writerows(rows)
    return path


def read_top_rows_from_csv(path: str, n: int = 10) -> tuple[list[str], list[list[str]]]:
    """Read the header and first n rows from a CSV file."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        all_rows = list(r)
    if not all_rows:
        return [], []
    return all_rows[0], all_rows[1 : 1 + n]
