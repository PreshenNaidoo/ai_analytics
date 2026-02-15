"""SQL safety helpers."""


import re

from agents_runtime.structured_outputs import AnalyzeResult, SQLQuery


def strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--.*?$", " ", sql, flags=re.M)
    return sql


def check_select_only_sql(sql: str) -> str | None:
    s = strip_sql_comments(sql).strip()
    if not s:
        return "Empty SQL is not allowed"

    if ";" in s[:-1]:
        return "Only single-statement SQL is allowed"

    head = s.lower().lstrip("(")
    if not (head.startswith("select") or head.startswith("with")):
        return "SQL must start with SELECT or WITH"

    banned = re.compile(
        r"\b(insert|update|delete|merge|drop|alter|truncate|create|exec|execute|xp_cmdshell|sp_configure)\b",
        flags=re.I,
    )
    if banned.search(s):
        return "Unsafe SQL keyword detected"

    if re.search(r"\bselect\b[\s\S]*\binto\b", s, flags=re.I):
        return "SELECT INTO is not allowed"

    return None


def enforce_sql_safety_sqls(sqls: list[SQLQuery]) -> None:
    for q in sqls:
        reason = check_select_only_sql(q.sql)
        if reason:
            raise ValueError(f"Unsafe SQL in '{q.name}': {reason}")


def enforce_analyze_result_safety(ares: AnalyzeResult) -> None:
    enforce_sql_safety_sqls(ares.sql_appendix)
    if ares.detail_query:
        reason = check_select_only_sql(ares.detail_query.sql)
        if reason:
            raise ValueError(f"Unsafe detail SQL in '{ares.detail_query.name}': {reason}")
