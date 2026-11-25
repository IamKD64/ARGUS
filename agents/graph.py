
"""NEXUS multi-agent business intelligence workflow.

Workflow:
    Schema -> Planner -> Analyst -> Writer -> Critic
                                      ^          |
                                      |__________|
                                  One feedback revision

Technology:
    LangGraph | MCP | Ollama | SQLite

Designed as a locally runnable portfolio demonstration.
"""

import json
import time
from typing import TypedDict

from langgraph.graph import END, StateGraph

from . import llm
from .mcp_client import call


# ============================================================
# CONFIGURATION
# ============================================================

MAX_SQL_RETRIES = 2
MAX_REVISIONS = 1
MAX_PLAN_QUESTIONS = 1


# ============================================================
# WORKFLOW STATE
# ============================================================

class State(TypedDict, total=False):
    question: str
    schema: str
    plan: list[str]
    results: list[dict]
    report: str
    feedback: str
    revisions: int
    critic_attempts: int
    approved: bool
    timings: dict
    total_seconds: float


# ============================================================
# DOMAIN KNOWLEDGE
# ============================================================

DOMAIN_HINTS = """
DOMAIN KNOWLEDGE:

SALES:
- Revenue = orders.quantity * products.price.

HR:
- employees.Attrition = 'Yes' means the employee left.
- employees.Attrition = 'No' means the employee stayed.
- employees.OverTime = 'Yes' or 'No'.
- Attrition rate:
  100.0 * SUM(CASE WHEN Attrition = 'Yes' THEN 1 ELSE 0 END)
  / COUNT(*)
- Department comparisons must use all employees in each department.
- Overtime analysis must calculate rates separately.
- Use the total employee count in each group as denominator.
- Always use 100.0 for percentage calculations.
- Never confuse DailyRate with attrition rate.
- Employee count is not an attrition percentage.
- Correlation does not establish causation.

LLM COST:
- token_usage.cost_usd already contains the final calculated cost.
- Total cost by model MUST use SUM(cost_usd).
- Average cost per record MUST use AVG(cost_usd).
- Record count MUST use COUNT(*).
- Never multiply cost_usd by a pricing ratio.
- Do not join llm_models when aggregating existing cost_usd.
- Use llm_models reference prices only when calculating cost
  from raw input_tokens and output_tokens.
- Never confuse total cost with average cost.

SUPPORT:
- support_tickets.resolution_hours is NULL for open tickets.
- csat is a score from 1 to 5 or NULL.

GENERAL:
- Dates use ISO format: YYYY-MM-DD.
- Use only tables and columns present in the schema.
- Never invent data or metrics.
"""


# ============================================================
# HELPERS
# ============================================================

def elapsed(started: float) -> float:
    return round(time.perf_counter() - started, 2)


def parse_json(output: str):
    return llm.extract_json(output)


def successful_results(results: list[dict]) -> list[dict]:
    return [
        result for result in results
        if result.get("status") == "success"
    ]


def is_token_cost_question(question: str) -> bool:
    """Identify questions asking for total AI/LLM model token costs."""

    text = question.lower()

    mentions_model = (
        "model" in text
        or "models" in text
        or "llm" in text
        or "ai model" in text
    )

    mentions_cost = any(
        word in text
        for word in ("cost", "costs", "spend", "spent", "expensive")
    )

    mentions_tokens = "token" in text or "tokens" in text

    asks_for_pricing = (
        "per 1m" in text
        or "per million" in text
        or "price per" in text
        or "pricing" in text
    )

    return (
        mentions_model
        and mentions_cost
        and mentions_tokens
        and not asks_for_pricing
    )


def token_cost_sql() -> str:
    """Trusted aggregation over costs already calculated in the database."""

    return """
        SELECT
            model,
            COUNT(*) AS records,
            ROUND(SUM(cost_usd), 2) AS total_cost,
            ROUND(AVG(cost_usd), 4) AS avg_cost
        FROM token_usage
        GROUP BY model
        ORDER BY total_cost DESC
        LIMIT 5
    """


def rows_as_dicts(result: dict) -> list[dict]:
    """Normalize MCP SQL rows into dictionaries."""

    columns = result.get("columns", [])
    rows = result.get("rows", [])

    normalized = []

    for row in rows:
        if isinstance(row, dict):
            normalized.append(row)
        elif isinstance(row, (list, tuple)):
            normalized.append(dict(zip(columns, row)))

    return normalized


def money(value) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def build_token_cost_report(results: list[dict]) -> str:
    """Create a factual report directly from verified SQL output."""

    successful = successful_results(results)

    if not successful:
        return (
            "## AI Model Token Costs\n\n"
            "The analysis could not be completed because the SQL query failed. "
            "No cost figures are available."
        )

    rows = rows_as_dicts(successful[0])

    if not rows:
        return (
            "## AI Model Token Costs\n\n"
            "The database returned no model cost records."
        )

    top = rows[0]

    lines = [
        "## Business Intelligence Report: AI Model Token Costs",
        "",
        "**Headline answer:** "
        f"{top.get('model', 'Unknown')} has the highest recorded "
        f"token cost at **{money(top.get('total_cost'))}**.",
        "",
        "### Top 5 models by total token cost",
        "",
        "| AI model | Records | Total cost | Average cost per record |",
        "|---|---:|---:|---:|",
    ]

    for row in rows:
        lines.append(
            f"| {row.get('model', 'Unknown')} "
            f"| {row.get('records', 'N/A')} "
            f"| {money(row.get('total_cost'))} "
            f"| {money(row.get('avg_cost'))} |"
        )

    lines.extend([
        "",
        "### Interpretation",
        "",
        "Total cost is calculated by summing the existing "
        "`token_usage.cost_usd` values for each model. "
        "Average cost per record is calculated separately.",
        "",
        "**Caveat:** These figures represent the records currently "
        "stored in the local demonstration database. They should not "
        "be interpreted as real-world provider billing.",
    ])

    return "\n".join(lines)


# ============================================================
# SCHEMA RETRIEVAL
# ============================================================

async def get_schema(session) -> str:

    tables_response = await call(session, "list_tables")
    tables = json.loads(tables_response)

    schema_parts = []

    for table in tables:

        description_response = await call(
            session,
            "describe_table",
            {"table": table},
        )

        description = json.loads(description_response)

        columns = ", ".join(
            f"{name} {column_type}"
            for name, column_type in description["columns"]
        )

        schema_parts.append(f"{table}({columns})")

    return "\n".join(schema_parts)


# ============================================================
# GRAPH BUILDER
# ============================================================

def build_graph(session):

    # --------------------------------------------------------
    # 1. SCHEMA NODE
    # --------------------------------------------------------

    async def load_schema(state: State) -> State:

        started = time.perf_counter()

        schema = await get_schema(session)

        return {
            "schema": schema,
            "revisions": 0,
            "critic_attempts": 0,
            "feedback": "",
            "timings": {
                **state.get("timings", {}),
                "schema": elapsed(started),
            },
        }

    # --------------------------------------------------------
    # 2. PLANNER NODE
    # --------------------------------------------------------

    def planner(state: State) -> State:

        started = time.perf_counter()

        # Known financial aggregation does not need an LLM plan.
        if is_token_cost_question(state["question"]):
            plan = [
                "Calculate total and average token cost by AI model."
            ]

        else:

            prompt = f"""
DATABASE SCHEMA:
{state['schema']}

BUSINESS QUESTION:
{state['question']}

Create the smallest useful analysis plan.

RULES:
- Prefer ONE focused analysis task.
- Every task must be answerable with one SQLite SELECT query.
- Avoid redundant analysis.
- Preserve the original question's intent.
- Do not invent business requirements.

Return ONLY a JSON list of strings.

Example:
["Calculate total revenue by customer segment."]
"""

            output = llm.chat(
                prompt,
                system=(
                    "You are a precise business intelligence planner. "
                    "Create concise and answerable analysis tasks. "
                    "Return valid JSON only."
                ),
                temperature=0,
                num_predict=128,
            )

            try:
                parsed = parse_json(output)

                if not isinstance(parsed, list):
                    raise ValueError("Expected a JSON list.")

                plan = [
                    str(item).strip()
                    for item in parsed
                    if str(item).strip()
                ][:MAX_PLAN_QUESTIONS]

            except (ValueError, TypeError, AttributeError):
                plan = [state["question"]]

        return {
            "plan": plan or [state["question"]],
            "timings": {
                **state.get("timings", {}),
                "planner": elapsed(started),
            },
        }

    # --------------------------------------------------------
    # 3. ANALYST NODE
    # --------------------------------------------------------

    async def analyst(state: State) -> State:

        started = time.perf_counter()

        results = []

        deterministic_cost_query = is_token_cost_question(
            state["question"]
        )

        for task in state["plan"]:

            previous_sql = None
            previous_error = None
            successful = False

            for attempt in range(MAX_SQL_RETRIES):

                # Use trusted SQL for token-cost aggregation.
                # No LLM-generated financial formula is accepted here.
                if deterministic_cost_query:
                    sql = token_cost_sql()

                else:

                    retry_context = ""

                    if previous_error:
                        retry_context = f"""
PREVIOUS SQL:
{previous_sql}

EXECUTION ERROR:
{previous_error}

Correct the SQL query.
"""

                    prompt = f"""
DATABASE SCHEMA:
{state['schema']}

ORIGINAL BUSINESS QUESTION:
{state['question']}

ANALYSIS TASK:
{task}

{DOMAIN_HINTS}

SQL REQUIREMENTS:
1. Generate exactly ONE SQLite SELECT query.
2. Use only existing tables and columns.
3. Calculate metrics correctly.
4. Use correct percentage denominators.
5. Use explicit aliases for calculated columns.
6. Use 100.0 for percentage calculations.
7. Ensure GROUP BY matches the requested comparison.
8. Answer the actual business question.
9. Never generate database write operations.

{retry_context}

Return ONLY executable SQLite SQL.
"""

                    sql = llm.clean_sql(
                        llm.chat(
                            prompt,
                            system=(
                                "You are a senior SQL analyst. "
                                "Generate accurate, executable SQLite "
                                "SELECT queries. Return SQL only."
                            ),
                            temperature=0,
                            num_predict=384,
                        )
                    )

                try:

                    response = await call(
                        session,
                        "run_sql",
                        {"sql": sql},
                    )

                    data = json.loads(response)

                    results.append({
                        "question": task,
                        "sql": sql,
                        "columns": data["columns"],
                        "rows": data["rows"],
                        "status": "success",
                    })

                    successful = True
                    break

                except Exception as error:

                    previous_sql = sql
                    previous_error = str(error)

                    # The deterministic query should not be replaced
                    # with an LLM-generated query after a failure.
                    if deterministic_cost_query:
                        break

            if not successful:

                results.append({
                    "question": task,
                    "sql": previous_sql or (
                        token_cost_sql()
                        if deterministic_cost_query
                        else None
                    ),
                    "error": previous_error,
                    "status": "failed",
                })

        return {
            "results": results,
            "timings": {
                **state.get("timings", {}),
                "analyst": elapsed(started),
            },
        }

    # --------------------------------------------------------
    # 4. WRITER NODE
    # --------------------------------------------------------

    def writer(state: State) -> State:

        started = time.perf_counter()

        is_revision = bool(state.get("feedback"))
        revisions = state.get("revisions", 0)

        if is_revision:
            revisions += 1

        # Financial output is generated from actual SQL rows,
        # not free-form LLM interpretation.
        if is_token_cost_question(state["question"]):

            report = build_token_cost_report(state["results"])

        else:

            prompt = f"""
ORIGINAL BUSINESS QUESTION:
{state['question']}

SQL ANALYSIS RESULTS:
{json.dumps(state['results'], default=str)[:5000]}

PREVIOUS REPORT:
{state.get('report', 'No previous report.')}

CRITIC FEEDBACK:
{state.get('feedback', 'This is the initial report.')}

{DOMAIN_HINTS}

Write a concise business intelligence report in Markdown.

STRUCTURE:
- Headline answer.
- Two to four key findings.
- One caveat.

RULES:
1. Answer the original question directly.
2. Use only successful SQL results.
3. Never invent values.
4. Distinguish counts from percentages.
5. Explain comparisons using correct denominators.
6. Mention failed queries and limitations.
7. Do not claim causation from correlation.
8. Avoid unsupported conclusions.
9. If there is insufficient evidence, say so.
10. Address every specific issue raised by the critic.
11. Never repeat an unsupported claim from the previous report.

Keep the report concise and factual.
"""

            report = llm.chat(
                prompt,
                system=(
                    "You are a precise business intelligence writer. "
                    "Use only the supplied SQL evidence. "
                    "Address critic feedback when revising reports."
                ),
                temperature=0,
                num_predict=384,
            )

        timings = dict(state.get("timings", {}))

        writer_time = elapsed(started)

        timings["writer"] = writer_time
        timings["writer_total"] = round(
            timings.get("writer_total", 0) + writer_time,
            2,
        )

        return {
            "report": report,
            "revisions": revisions,
            "feedback": "",
            "timings": timings,
        }

    # --------------------------------------------------------
    # 5. CRITIC NODE
    # --------------------------------------------------------

    def critic(state: State) -> State:

        started = time.perf_counter()

        # Verify the deterministic financial report against
        # the actual SQL output.
        if is_token_cost_question(state["question"]):

            successful = successful_results(state["results"])
            rows = rows_as_dicts(successful[0]) if successful else []

            approved = bool(rows)

            if approved:
                feedback = (
                    "Token-cost report generated directly from successful "
                    "SQL results. Model totals and averages use the "
                    "database aggregation."
                )
            else:
                feedback = (
                    "Token-cost report could not be verified because "
                    "the SQL query returned no successful records."
                )

        else:

            prompt = f"""
ORIGINAL BUSINESS QUESTION:
{state['question']}

ANALYSIS TASKS:
{json.dumps(state.get('plan', []))}

SQL RESULTS:
{json.dumps(state['results'], default=str)[:5000]}

GENERATED REPORT:
{state['report']}

Evaluate the report against the actual SQL evidence.

CHECK:
1. Does it answer the original question?
2. Are numerical claims supported by successful SQL results?
3. Are counts and percentages distinguished?
4. Are percentage denominators correct?
5. Are comparisons supported by the results?
6. Does it avoid unsupported causal claims?
7. Does it disclose failed queries?
8. Does it distinguish averages from totals?

IMPORTANT:
- Do not reject a report merely because of stylistic preferences.
- Do not invent additional requirements.
- Approve a concise report if its claims are supported.
- Reject unsupported numerical claims or material analytical errors.
- If no SQL task succeeded, the report must disclose insufficient evidence.

Return ONLY valid JSON:

{{
    "approved": true,
    "feedback": "The report is supported by the SQL results."
}}
"""

            output = llm.chat(
                prompt,
                system=(
                    "You are an analytical quality reviewer. "
                    "Compare important claims with supplied SQL evidence. "
                    "Be strict about factual errors but fair about style. "
                    "Return valid JSON only."
                ),
                temperature=0,
                num_predict=192,
            )

            try:

                verdict = parse_json(output)

                if not isinstance(verdict, dict):
                    raise ValueError("Expected a JSON object.")

                if not isinstance(verdict.get("approved"), bool):
                    raise ValueError("Approval must be a boolean.")

                approved = verdict["approved"]
                feedback = str(
                    verdict.get("feedback", "")
                ).strip()

                if not feedback:
                    feedback = (
                        "Approved based on supplied SQL evidence."
                        if approved
                        else "The critic rejected the report without details."
                    )

            except (ValueError, TypeError, AttributeError):

                approved = False
                feedback = (
                    "Critic returned invalid JSON. "
                    "The report could not be automatically verified."
                )

        critic_attempts = state.get("critic_attempts", 0) + 1

        timings = dict(state.get("timings", {}))

        critic_time = elapsed(started)

        timings["critic"] = critic_time
        timings["critic_total"] = round(
            timings.get("critic_total", 0) + critic_time,
            2,
        )

        return {
            "approved": approved,
            "feedback": feedback,
            "critic_attempts": critic_attempts,
            "timings": timings,
        }

    # --------------------------------------------------------
    # 6. ROUTING
    # --------------------------------------------------------

    def route(state: State) -> str:

        if state.get("approved"):
            return END

        if state.get("revisions", 0) < MAX_REVISIONS:
            return "writer"

        return END

    # --------------------------------------------------------
    # 7. BUILD LANGGRAPH
    # --------------------------------------------------------

    graph = StateGraph(State)

    graph.add_node("load_schema", load_schema)
    graph.add_node("planner", planner)
    graph.add_node("analyst", analyst)
    graph.add_node("writer", writer)
    graph.add_node("critic", critic)

    graph.set_entry_point("load_schema")

    graph.add_edge("load_schema", "planner")
    graph.add_edge("planner", "analyst")
    graph.add_edge("analyst", "writer")
    graph.add_edge("writer", "critic")

    graph.add_conditional_edges(
        "critic",
        route,
        {
            END: END,
            "writer": "writer",
        },
    )

    return graph.compile()


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================

async def run_question(session, question: str) -> State:

    started = time.perf_counter()

    graph = build_graph(session)

    state = await graph.ainvoke({
        "question": question,
        "timings": {},
        "revisions": 0,
        "critic_attempts": 0,
        "feedback": "",
    })

    state["total_seconds"] = round(
        time.perf_counter() - started,
        2,
    )

    return state
