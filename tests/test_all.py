import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest

from mcp_server.guard import validate_sql
from mcp_server.seed_db import build


@pytest.mark.parametrize("bad", ["DROP TABLE orders", "SELECT 1; DELETE FROM orders", "UPDATE orders SET quantity=0",
                                 "PRAGMA table_info(orders)", "", "INSERT INTO orders VALUES (1,1,1,1,'x')"])
def test_guard_blocks(bad):
    with pytest.raises(ValueError):
        validate_sql(bad)


def test_guard_allows_select_and_cte():
    assert validate_sql("SELECT * FROM orders;") == "SELECT * FROM orders"
    assert validate_sql("WITH x AS (SELECT 1) SELECT * FROM x")


def test_seed_deterministic(tmp_path):
    import sqlite3
    p = build(tmp_path / "a.db")
    assert sqlite3.connect(p).execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 5000


def test_graph_end_to_end_with_stubs(tmp_path, monkeypatch):
    """Runs the real LangGraph flow with a stub LLM and a stub MCP session (no Ollama needed)."""
    from agents import graph, llm

    replies = iter([
        '["total orders"]',                       # planner
        "SELECT COUNT(*) FROM orderz",            # analyst attempt 1 (bad)
        "```sql\nSELECT COUNT(*) FROM orders\n```",  # analyst attempt 2 (fixed)
        "There were 5000 orders.",                # writer
        '{"approved": false, "feedback": "add caveat"}',  # critic rejects
        "There were 5000 orders. Caveat: synthetic data.",  # writer revision
        '{"approved": true, "feedback": ""}',     # critic approves
    ])
    monkeypatch.setattr(llm, "chat", lambda *a, **k: next(replies))

    class FakeSession:
        async def call_tool(self, name, args=None):
            if name == "list_tables":
                text = json.dumps(["orders"])
            elif name == "describe_table":
                text = json.dumps({"table": "orders", "columns": [["id", "INTEGER"]], "sample_rows": []})
            elif "orderz" in args["sql"]:
                return SimpleNamespace(isError=True, content=[SimpleNamespace(type="text", text="no such table")])
            else:
                text = json.dumps({"columns": ["n"], "rows": [[5000]]})
            return SimpleNamespace(isError=False, content=[SimpleNamespace(type="text", text=text)])

    state = asyncio.run(graph.run_question(FakeSession(), "How many orders?"))
    assert state["approved"] is True
    assert state["revisions"] == 1
    assert state["critic_attempts"] == 2
    assert "Caveat" in state["report"]
    assert state["results"][0]["rows"] == [[5000]]


def test_real_and_synthetic_tables(tmp_path):
    import sqlite3
    con = sqlite3.connect(build(tmp_path / "b.db"))
    q = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    assert q("SELECT COUNT(*) FROM employees") == 1470                       # real IBM HR data
    assert q("SELECT ROUND(100.0*SUM(Attrition='Yes')/COUNT(*),1) FROM employees") == 16.1
    assert q("SELECT COUNT(*) FROM llm_models") > 100                        # real price list
    assert q("SELECT COUNT(*) FROM support_tickets") == 3000
    assert q("SELECT COUNT(*) FROM token_usage WHERE cost_usd < 0") == 0
    # cost really is derived from real prices
    assert q("""SELECT COUNT(*) FROM token_usage u JOIN llm_models m ON m.model=u.model
                WHERE ABS(u.cost_usd - (u.input_tokens*m.input_usd_per_1m_tokens + u.output_tokens*m.output_usd_per_1m_tokens)/1e6) > 0.01""") == 0
