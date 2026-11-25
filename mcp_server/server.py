"""MCP server exposing a read-only sales database. Run standalone: python -m mcp_server.server"""
import json
import os
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .guard import validate_sql

DB = Path(os.getenv("SALES_DB", Path(__file__).parent / "sales.db"))
MAX_ROWS = 100
mcp = FastMCP("sales-db")


def _connect() -> sqlite3.Connection:
    # read-only at the connection level = defence in depth on top of validate_sql
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


@mcp.tool()
def list_tables() -> str:
    """List all tables in the sales database."""
    with _connect() as con:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    return json.dumps([r[0] for r in rows])


@mcp.tool()
def describe_table(table: str) -> str:
    """Return column names/types and 3 sample rows for a table."""
    with _connect() as con:
        valid = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if table not in valid:
            raise ValueError(f"Unknown table {table!r}. Valid: {sorted(valid)}")
        cols = [(r[1], r[2]) for r in con.execute(f'PRAGMA table_info("{table}")')]
        sample = con.execute(f'SELECT * FROM "{table}" LIMIT 3').fetchall()
    return json.dumps({"table": table, "columns": cols, "sample_rows": sample})


@mcp.tool()
def run_sql(sql: str) -> str:
    """Run ONE read-only SELECT query (max 100 rows). Returns JSON {columns, rows}."""
    q = validate_sql(sql)
    with _connect() as con:
        cur = con.execute(q)
        rows = cur.fetchmany(MAX_ROWS)
        cols = [d[0] for d in cur.description]
    return json.dumps({"columns": cols, "rows": rows})


if __name__ == "__main__":
    mcp.run()  # stdio transport
