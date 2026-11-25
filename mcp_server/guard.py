"""SQL guardrail: only a single read-only SELECT/WITH statement is allowed."""
import re

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|replace|vacuum|reindex)\b", re.I
)


def validate_sql(sql: str) -> str:
    s = sql.strip().rstrip(";").strip()
    if not s:
        raise ValueError("Empty query")
    if ";" in s:
        raise ValueError("Only one statement is allowed")
    if not re.match(r"^(select|with)\b", s, re.I):
        raise ValueError("Only SELECT queries are allowed")
    if FORBIDDEN.search(s):
        raise ValueError("Query contains a forbidden keyword")
    return s
