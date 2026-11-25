"""Single-agent vs multi-agent benchmark on questions with known answers (gold SQL).
Metric: does the final text contain the gold value?  Also reports latency.
Run: python -m bench.run_bench"""
import asyncio
import json
import re
import sqlite3
import time

from agents import llm
from agents.graph import DOMAIN_HINTS, get_schema, run_question
from agents.mcp_client import call, sales_session
from mcp_server.server import DB

CASES = [
    ("Which region had the highest total revenue in 2024?",
     "SELECT c.region FROM orders o JOIN customers c ON c.id=o.customer_id JOIN products p ON p.id=o.product_id GROUP BY c.region ORDER BY SUM(o.quantity*p.price) DESC LIMIT 1"),
    ("How many orders were placed in 2024?", "SELECT COUNT(*) FROM orders"),
    ("Which product category sold the most units?",
     "SELECT p.category FROM orders o JOIN products p ON p.id=o.product_id GROUP BY p.category ORDER BY SUM(o.quantity) DESC LIMIT 1"),
    ("How many distinct customers are in the Enterprise segment?", "SELECT COUNT(*) FROM customers WHERE segment='Enterprise'"),
    ("What percentage of employees have left the company (attrition rate)? Give one decimal place.",
     "SELECT ROUND(100.0*SUM(Attrition='Yes')/COUNT(*),1) FROM employees"),
    ("Which department has the most employees who left?",
     "SELECT Department FROM employees WHERE Attrition='Yes' GROUP BY Department ORDER BY COUNT(*) DESC LIMIT 1"),
    ("Which job role has the most employees who work overtime?",
     "SELECT JobRole FROM employees WHERE OverTime='Yes' GROUP BY JobRole ORDER BY COUNT(*) DESC LIMIT 1"),
    ("Which LLM model generated the highest total token cost?",
     "SELECT model FROM token_usage GROUP BY model ORDER BY SUM(cost_usd) DESC LIMIT 1"),
    ("Which support ticket category has the longest average resolution time?",
     "SELECT category FROM support_tickets WHERE resolution_hours IS NOT NULL GROUP BY category ORDER BY AVG(resolution_hours) DESC LIMIT 1"),
    ("How many support tickets are still open?", "SELECT COUNT(*) FROM support_tickets WHERE status='Open'"),
    ("Which customer segment has the highest total revenue?",
     "SELECT c.segment FROM orders o JOIN customers c ON c.id=o.customer_id JOIN products p ON p.id=o.product_id GROUP BY c.segment ORDER BY SUM(o.quantity*p.price) DESC LIMIT 1"),
]


def gold(sql: str) -> str:
    return str(sqlite3.connect(f"file:{DB}?mode=ro", uri=True).execute(sql).fetchone()[0])


def contains(text: str, value: str) -> bool:
    return value.lower() in re.sub(r"(?<=\d),(?=\d)", "", text).lower()


async def single_agent(session, question: str) -> str:
    schema = await get_schema(session)
    sql = llm.clean_sql(llm.chat(
        f"SQLite schema:\n{schema}\n{DOMAIN_HINTS}\nWrite ONE SQL query for: {question}\nReply with only SQL."))
    try:
        data = await call(session, "run_sql", {"sql": sql})
    except Exception as e:
        return f"error: {e}"
    return llm.chat(f"Question: {question}\nSQL result: {data}\nAnswer in one sentence.")


async def main() -> None:
    rows = {"single": [0, 0.0], "multi": [0, 0.0]}
    async with sales_session() as s:
        for q, sql in CASES:
            g = gold(sql)
            t = time.perf_counter(); a = await single_agent(s, q)
            rows["single"][0] += contains(a, g); rows["single"][1] += time.perf_counter() - t
            t = time.perf_counter(); b = (await run_question(s, q))["report"]
            rows["multi"][0] += contains(b, g); rows["multi"][1] += time.perf_counter() - t
            print(f"- {q}  gold={g}")
    n = len(CASES)
    out = {k: {"accuracy": v[0] / n, "avg_latency_s": round(v[1] / n, 1)} for k, v in rows.items()}
    print(json.dumps(out, indent=2))
    open("bench/results.json", "w").write(json.dumps(out, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
