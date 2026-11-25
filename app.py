import asyncio

import time

import pandas as pd
import plotly.express as px
import streamlit as st

from agents.graph import run_question
from agents.mcp_client import sales_session


# ============================================================
# DESIGN TOKENS
# Each agent owns one hue. The same hue is used for that agent
# everywhere: diagram, cards, status, charts.
# ============================================================

INK = "#10151C"        # page
PANEL = "#151B24"      # surfaces
RAISED = "#1A222D"     # hover / selected
LINE = "#232C38"       # hairlines
TEXT = "#E6EBF2"
MUTED = "#8C99AB"
FAINT = "#5F6B7C"

PLANNER = "#7AA2F7"    # soft blue
ANALYST = "#7FD1B9"    # sage
WRITER = "#B8A4F0"     # lilac
CRITIC = "#E6C07B"     # amber
A2A_COLOR = "#E8A0B4"  # rose


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Nexus | Multi-agent analytics",
    page_icon=":material/hub:",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# THEME
# ============================================================

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap');

:root {
    --ink: #10151C;
    --panel: #151B24;
    --raised: #1A222D;
    --line: #232C38;
    --text: #E6EBF2;
    --body: #C3CCD9;
    --muted: #8C99AB;
    --faint: #5F6B7C;
    --planner: #7AA2F7;
    --analyst: #7FD1B9;
    --writer: #B8A4F0;
    --critic: #E6C07B;
    --a2a: #E8A0B4;
}

/* Base */
.stApp {
    background: var(--ink);
    color: var(--body);
    font-family: 'Instrument Sans', system-ui, sans-serif;
}
.stApp p, .stApp li, .stApp label, .stApp button, .stApp input,
.stApp textarea, div[data-testid="stMarkdownContainer"] {
    font-family: 'Instrument Sans', system-ui, sans-serif;
}
.stApp p, .stApp li { color: var(--body); }

#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

.block-container {
    max-width: 1080px;
    padding: 3rem 2rem 4rem;
}

/* Headings: one serif, used sparingly */
h1, h2, h3 {
    font-family: 'Newsreader', Georgia, serif !important;
    color: var(--text) !important;
    font-weight: 400 !important;
    letter-spacing: -0.015em;
}
h1 { font-size: 2.7rem !important; line-height: 1.12 !important; padding-bottom: .5rem !important; }
h2, h3 { font-size: 1.45rem !important; margin-top: 1.5rem !important; }

/* Intro text */
.lede {
    font-size: 1.08rem;
    line-height: 1.65;
    color: var(--muted);
    max-width: 58ch;
    margin: .25rem 0 2rem;
}
.label {
    font-size: .8rem;
    font-weight: 500;
    color: var(--faint);
    margin-bottom: .5rem;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--panel);
    border-right: 1px solid var(--line);
}
section[data-testid="stSidebar"] .block-container { padding-top: 2rem; }

.brand { display: flex; align-items: center; gap: .75rem; margin-bottom: 2rem; }
.brand-name { font-family: 'Newsreader', serif; font-size: 1.5rem; color: var(--text); line-height: 1; }
.brand-sub { font-size: .75rem; color: var(--faint); margin-top: .25rem; }

section[data-testid="stSidebar"] div[role="radiogroup"] { gap: .15rem; }
section[data-testid="stSidebar"] div[role="radiogroup"] label {
    width: 100%;
    padding: .5rem .8rem;
    border-radius: 8px;
    cursor: pointer;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child { display: none; }
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover { background: var(--raised); }
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background: var(--raised);
    box-shadow: inset 2px 0 0 var(--analyst);
}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p { color: var(--text); }

.kv {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: .55rem 0;
    border-bottom: 1px solid var(--line);
    font-size: .85rem;
}
.kv .k { color: var(--muted); display: flex; align-items: center; gap: .5rem; }
.kv .v { color: var(--text); }
.dot { width: 7px; height: 7px; border-radius: 50%; background: var(--c, var(--analyst)); display: inline-block; }

/* Key facts row: no boxes, just hairlines */
.stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    border-top: 1px solid var(--line);
    border-bottom: 1px solid var(--line);
    margin: 0 0 2.5rem;
}
.stat { padding: 1.1rem 1.25rem 1.1rem 0; }
.stat + .stat { padding-left: 1.25rem; border-left: 1px solid var(--line); }
.stat .k { font-size: .8rem; color: var(--faint); }
.stat .v { font-family: 'Newsreader', serif; font-size: 1.65rem; color: var(--text); margin: .15rem 0; }
.stat .d { font-size: .85rem; color: var(--muted); line-height: 1.4; }

/* Agent roles */
.roles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; margin: .5rem 0 2.5rem; }
.role { border-top: 2px solid var(--c); padding-top: .9rem; }
.role h4 { margin: 0 0 .35rem; font-size: 1rem; font-weight: 600; color: var(--text); }
.role p { margin: 0; font-size: .88rem; line-height: 1.5; color: var(--muted); }

/* Definition rows */
.defs { margin: .5rem 0 2rem; }
.def {
    display: grid;
    grid-template-columns: 170px 1fr;
    gap: 1.5rem;
    padding: 1rem 0;
    border-bottom: 1px solid var(--line);
}
.def:first-child { border-top: 1px solid var(--line); }
.def .t { color: var(--text); font-weight: 500; display: flex; align-items: center; gap: .6rem; }
.def .d { color: var(--muted); font-size: .92rem; line-height: 1.55; }

/* Diagram surface */
.diagram {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 1.25rem 1rem .75rem;
    margin: 0 0 2.5rem;
}
.diagram svg { width: 100%; height: auto; display: block; }

/* Run status */
.status {
    display: flex;
    align-items: center;
    gap: .6rem;
    padding: .6rem 0;
    font-size: .9rem;
    color: var(--muted);
}

/* Controls */
.stButton > button {
    justify-content: flex-start;
    text-align: left;
    height: auto;
    min-height: 3rem;
    padding: .7rem .95rem;
    border-radius: 10px;
    border: 1px solid var(--line);
    background: transparent;
    color: var(--body);
    font-size: .9rem;
    line-height: 1.4;
    transition: border-color .15s ease, background .15s ease;
}
.stButton > button:hover {
    border-color: var(--analyst);
    background: var(--raised);
    color: var(--text);
}
.stButton > button:focus-visible { outline: 2px solid var(--analyst); outline-offset: 2px; }

div[data-testid="stChatInput"] {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
}
div[data-testid="stChatInput"] textarea { background: transparent !important; color: var(--text) !important; }
div[data-testid="stChatMessage"] { background: transparent; border: none; padding-left: 0; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 1.5rem; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { color: var(--muted); background: transparent; padding-left: 0; padding-right: 0; }
.stTabs [aria-selected="true"] { color: var(--text) !important; }
.stTabs [data-baseweb="tab-highlight"] { background: var(--analyst) !important; }

/* Data, expanders, alerts */
div[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
div[data-testid="stExpander"] { border: 1px solid var(--line); border-radius: 10px; background: transparent; }
div[data-testid="stAlert"] { border-radius: 10px; }
hr { border-color: var(--line) !important; }

.foot { color: var(--faint); font-size: .8rem; }

/* Small screens */
@media (max-width: 800px) {
    .stats, .roles { grid-template-columns: 1fr 1fr; }
    .stat + .stat { border-left: none; padding-left: 0; }
    .def { grid-template-columns: 1fr; gap: .25rem; }
    h1 { font-size: 2.1rem !important; }
}

@media (prefers-reduced-motion: reduce) {
    * { transition: none !important; }
}
</style>
"""

st.markdown(THEME_CSS, unsafe_allow_html=True)


# ============================================================
# BACKEND CONNECTION
# ============================================================

async def execute_question(question):
    async with sales_session() as session:
        return await run_question(session, question)


def run_backend(question):
    return asyncio.run(execute_question(question))


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_state" not in st.session_state:
    st.session_state.last_state = None

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None


# ============================================================
# UI HELPERS
# ============================================================

def html(markup):
    """Render HTML safely inside Markdown.

    Markdown treats indented lines and blank lines as code or block
    breaks, so strip indentation and blank lines before rendering.
    """
    cleaned = "\n".join(
        line.strip() for line in markup.splitlines() if line.strip()
    )
    st.markdown(cleaned, unsafe_allow_html=True)


def intro(text):
    html(f'<p class="lede">{text}</p>')


def stat_row(items):
    cells = "".join(
        f'<div class="stat"><div class="k">{k}</div>'
        f'<div class="v">{v}</div><div class="d">{d}</div></div>'
        for k, v, d in items
    )
    html(f'<div class="stats">{cells}</div>')


def role_row(items):
    cells = "".join(
        f'<div class="role" style="--c:{c}"><h4>{name}</h4><p>{desc}</p></div>'
        for name, desc, c in items
    )
    html(f'<div class="roles">{cells}</div>')


def definition_rows(items):
    rows = "".join(
        f'<div class="def"><div class="t">'
        f'<span class="dot" style="--c:{c}"></span>{term}</div>'
        f'<div class="d">{desc}</div></div>'
        for term, desc, c in items
    )
    html(f'<div class="defs">{rows}</div>')


def run_status(state):
    approved = state.get("approved", False)
    revisions = state.get("revisions", 0)
    color = ANALYST if approved else CRITIC
    verdict = "Approved by the critic" if approved else "Not approved by the critic"
    plural = "revision" if revisions == 1 else "revisions"
    html(
        f'<div class="status"><span class="dot" style="--c:{color}"></span>'
        f'{verdict} after {revisions} {plural}</div>'
    )


def arrow_marker(marker_id, color):
    return (
        f'<marker id="{marker_id}" viewBox="0 0 10 10" refX="8" refY="5" '
        f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        f'<path d="M1 1L9 5L1 9" fill="none" stroke="{color}" '
        f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</marker>'
    )


def pipeline_svg(focus="all", approved=None, revisions=0):
    """The project's real architecture, drawn once and reused.

    focus: "all", "mcp" or "a2a" decides which layer is emphasised.
    approved / revisions: pass a finished run to show its outcome.
    """
    flow_op, mcp_op, a2a_op = {
        "all": (1, 1, 1),
        "mcp": (0.5, 1, 0.2),
        "a2a": (0.5, 0.2, 1),
    }[focus]

    agents = [
        ("Planner", "Plans the tasks", PLANNER, 120),
        ("Analyst", "Writes and runs SQL", ANALYST, 290),
        ("Writer", "Drafts the report", WRITER, 460),
        ("Critic", "Reviews the report", CRITIC, 630),
    ]
    cy = 140

    nodes = ""
    for name, role, color, cx in agents:
        nodes += (
            f'<circle cx="{cx}" cy="{cy}" r="24" fill="{PANEL}" '
            f'stroke="{color}" stroke-width="1.5"/>'
            f'<circle cx="{cx}" cy="{cy}" r="6" fill="{color}"/>'
            f'<text x="{cx}" y="188" text-anchor="middle" font-size="14" '
            f'font-weight="600" fill="{TEXT}">{name}</text>'
            f'<text x="{cx}" y="206" text-anchor="middle" font-size="12" '
            f'fill="{MUTED}">{role}</text>'
        )

    links = ""
    for i in range(len(agents) - 1):
        x1 = agents[i][3] + 32
        x2 = agents[i + 1][3] - 32
        links += (
            f'<line x1="{x1}" y1="{cy}" x2="{x2}" y2="{cy}" '
            f'stroke="{FAINT}" stroke-width="1.2" marker-end="url(#arrow-flow)"/>'
        )

    loop_label = "revise" if not revisions else f"revised {revisions}x"
    loop = (
        f'<path d="M630 116 C630 78, 460 78, 460 116" fill="none" '
        f'stroke="{CRITIC}" stroke-width="1.2" stroke-dasharray="4 4" '
        f'marker-end="url(#arrow-loop)"/>'
        f'<text x="545" y="72" text-anchor="middle" font-size="12" '
        f'fill="{CRITIC}">{loop_label}</text>'
    )

    verdict = ""
    if approved is not None:
        verdict_color = ANALYST if approved else CRITIC
        verdict_text = "Approved" if approved else "Not approved"
        verdict = (
            f'<text x="630" y="224" text-anchor="middle" font-size="12" '
            f'font-weight="600" fill="{verdict_color}">{verdict_text}</text>'
        )

    return f"""
    <div class="diagram">
    <svg viewBox="0 0 920 262" xmlns="http://www.w3.org/2000/svg"
         role="img" aria-label="Planner, Analyst, Writer and Critic workflow with MCP tools and an A2A connection"
         style="font-family:'Instrument Sans',system-ui,sans-serif">
    <defs>
    {arrow_marker("arrow-flow", FAINT)}
    {arrow_marker("arrow-loop", CRITIC)}
    {arrow_marker("arrow-mcp", ANALYST)}
    {arrow_marker("arrow-a2a", A2A_COLOR)}
    </defs>
    <g opacity="{flow_op}">
    <rect x="24" y="56" width="700" height="186" rx="16" fill="none"
          stroke="{LINE}" stroke-width="1.2" stroke-dasharray="3 5"/>
    <text x="44" y="82" font-size="12" fill="{FAINT}">LangGraph workflow</text>
    {links}
    {loop}
    {nodes}
    {verdict}
    </g>
    <g opacity="{mcp_op}">
    <rect x="205" y="4" width="170" height="34" rx="17" fill="{PANEL}"
          stroke="{ANALYST}" stroke-width="1.2"/>
    <text x="290" y="25" text-anchor="middle" font-size="12.5" fill="{TEXT}">MCP server, SQLite</text>
    <line x1="290" y1="40" x2="290" y2="112" stroke="{ANALYST}" stroke-width="1.2"
          marker-start="url(#arrow-mcp)" marker-end="url(#arrow-mcp)"/>
    <text x="300" y="100" font-size="12" fill="{MUTED}">SQL tools</text>
    </g>
    <g opacity="{a2a_op}">
    <line x1="726" y1="{cy}" x2="826" y2="{cy}" stroke="{A2A_COLOR}" stroke-width="1.2"
          stroke-dasharray="5 4" marker-start="url(#arrow-a2a)" marker-end="url(#arrow-a2a)"/>
    <text x="776" y="126" text-anchor="middle" font-size="12" fill="{MUTED}">JSON-RPC</text>
    <circle cx="860" cy="{cy}" r="24" fill="{PANEL}" stroke="{A2A_COLOR}" stroke-width="1.5"/>
    <circle cx="860" cy="{cy}" r="6" fill="{A2A_COLOR}"/>
    <text x="860" y="188" text-anchor="middle" font-size="14" font-weight="600" fill="{TEXT}">A2A</text>
    <text x="860" y="206" text-anchor="middle" font-size="12" fill="{MUTED}">External agents</text>
    </g>
    </svg>
    </div>
    """


def show_query_results(state):
    results = state.get("results", [])

    if not results:
        st.info("No query results yet.")
        return

    for index, result in enumerate(results):

        st.markdown(f"**Query {index + 1}**")

        if result.get("question"):
            st.caption(result["question"])

        if result.get("status") == "failed" or "error" in result:
            st.error(result.get("error", "The query failed."))
            continue

        columns = result.get("columns", [])
        rows = result.get("rows", [])

        if columns:
            df = pd.DataFrame(rows, columns=columns)

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )

            # Offer a chart only when the returned data supports it.
            categorical = [
                col for col in df.columns
                if not pd.api.types.is_numeric_dtype(df[col])
            ]
            numeric = df.select_dtypes(include="number").columns.tolist()

            if categorical and numeric and len(df) > 1:
                with st.expander("Chart this result"):
                    chart = px.bar(
                        df,
                        x=categorical[0],
                        y=numeric[0],
                        template="plotly_dark",
                        color_discrete_sequence=[ANALYST],
                    )
                    chart.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font_color=MUTED,
                        margin=dict(l=0, r=0, t=10, b=0),
                        xaxis=dict(gridcolor=LINE, title=None),
                        yaxis=dict(gridcolor=LINE),
                    )
                    chart.update_traces(marker_line_width=0)
                    st.plotly_chart(chart, use_container_width=True)
        else:
            st.info("This query returned no columns.")

        st.divider()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    html(f"""
    <div class="brand">
    <svg width="30" height="30" viewBox="0 0 30 30" fill="none" aria-hidden="true">
    <line x1="15" y1="15" x2="6" y2="7" stroke="{FAINT}" stroke-width="1.2"/>
    <line x1="15" y1="15" x2="24" y2="7" stroke="{FAINT}" stroke-width="1.2"/>
    <line x1="15" y1="15" x2="15" y2="26" stroke="{FAINT}" stroke-width="1.2"/>
    <circle cx="6" cy="7" r="3" fill="{PLANNER}"/>
    <circle cx="24" cy="7" r="3" fill="{WRITER}"/>
    <circle cx="15" cy="26" r="3" fill="{CRITIC}"/>
    <circle cx="15" cy="15" r="4" fill="{ANALYST}"/>
    </svg>
    <div>
    <div class="brand-name">Nexus</div>
    <div class="brand-sub">Multi-agent analytics</div>
    </div>
    </div>
    """)

    page = st.radio(
        "Navigation",
        [
            "Overview",
            "AI Workspace",
            "MCP Tools",
            "A2A Network",
            "Execution Inspector",
        ],
        label_visibility="collapsed",
    )

    st.write("")
    st.write("")
    html('<div class="label">Running locally</div>')

    html(f"""
    <div class="kv"><span class="k"><span class="dot" style="--c:{PLANNER}"></span>Workflow</span><span class="v">LangGraph</span></div>
    <div class="kv"><span class="k"><span class="dot" style="--c:{WRITER}"></span>Model</span><span class="v">llama3.2:3b</span></div>
    <div class="kv"><span class="k"><span class="dot" style="--c:{CRITIC}"></span>Runtime</span><span class="v">Ollama</span></div>
    <div class="kv"><span class="k"><span class="dot" style="--c:{ANALYST}"></span>Data</span><span class="v">SQLite</span></div>
    """)

    st.write("")
    st.caption("Portfolio demonstration")


# ============================================================
# PAGE: OVERVIEW
# ============================================================

if page == "Overview":

    st.title("Business questions, answered by a team of agents")
    intro(
        "Ask in plain language. A planner breaks the question down, an "
        "analyst queries the database through MCP, a writer drafts the "
        "findings and a critic checks them before you see anything."
    )

    html(pipeline_svg("all"))

    stat_row([
        ("Orchestration", "LangGraph", "Stateful workflow with a revision loop"),
        ("Tools", "MCP", "Database access for the analyst"),
        ("Delegation", "A2A", "Lets other services reach the agents"),
        ("Inference", "Ollama", "Llama 3.2 3B on your machine"),
    ])

    st.markdown("### Four agents, one workflow")
    role_row([
        ("Planner", "Splits a question into tasks the analyst can run.", PLANNER),
        ("Analyst", "Writes SQL for each task and runs it through MCP.", ANALYST),
        ("Writer", "Turns the query results into a readable report.", WRITER),
        ("Critic", "Reviews the report and sends it back if it falls short.", CRITIC),
    ])

    st.markdown("### What it runs on")
    definition_rows([
        ("LangGraph", "Routes work between the agents and loops back to the writer when the critic asks for changes.", PLANNER),
        ("MCP", "A server exposes SQL tools over SQLite, so the analyst never touches the database directly.", ANALYST),
        ("A2A", "A separate JSON-RPC service lets other agents send questions to this system.", A2A_COLOR),
        ("Ollama", "Local inference with Llama 3.2 3B. Questions and data stay on your machine.", CRITIC),
    ])

    st.info(
        "This is a portfolio demonstration. The A2A service runs "
        "separately from this app."
    )


# ============================================================
# PAGE: AI WORKSPACE
# ============================================================

elif page == "AI Workspace":

    st.title("AI Workspace")
    intro(
        "Ask about HR, LLM usage, sales or support data. You get a written "
        "report that the critic has already checked."
    )

    html('<div class="label">Try one of these</div>')

    examples = [
        "Which department has the highest attrition and is overtime related?",
        "Which AI models cost us the most in tokens?",
        "Which customer segment generates the highest revenue?",
        "Which support ticket categories take longest to resolve?",
    ]

    example_cols = st.columns(2)

    for index, example in enumerate(examples):
        with example_cols[index % 2]:
            if st.button(
                example,
                key=f"example_{index}",
                use_container_width=True,
            ):
                st.session_state.pending_question = example

    st.write("")

    # Conversation history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input("Ask a question about your business data")

    if question:
        st.session_state.pending_question = question

    if st.session_state.pending_question:

        current_question = st.session_state.pending_question
        st.session_state.pending_question = None

        st.session_state.messages.append({
            "role": "user",
            "content": current_question,
        })

        with st.chat_message("user"):
            st.markdown(current_question)

        with st.chat_message("assistant"):

            try:
                start_time = time.perf_counter()

                with st.spinner(
                "Agents are analyzing your question..."
                ):
                    state = run_backend(current_question)

                elapsed = time.perf_counter() - start_time

                st.caption(f"Completed in {elapsed:.1f} seconds")

                st.session_state.last_state = state

                st.markdown(state.get(
                    "report",
                    "No report was generated.",
                ))

                run_status(state)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": state.get("report", ""),
                })

            except Exception as error:
                error_message = f"The analysis failed: {error}"
                st.error(error_message)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_message,
                })

    if st.session_state.last_state:
        st.caption(
            "See the SQL, data and agent steps for this answer in "
            "Execution Inspector."
        )


# ============================================================
# PAGE: MCP TOOLS
# ============================================================

elif page == "MCP Tools":

    st.title("MCP tools")
    intro(
        "The Model Context Protocol is how the analyst reaches the "
        "database. The agent asks for a tool, the MCP server runs it "
        "against SQLite and returns the rows."
    )

    html(pipeline_svg("mcp"))

    st.markdown("### Data domains")
    definition_rows([
        ("HR analytics", "Employee attrition and workforce data.", PLANNER),
        ("LLM usage", "Model pricing and token consumption.", WRITER),
        ("Sales", "Customers, products and orders.", ANALYST),
        ("Customer support", "Support tickets and resolution times.", CRITIC),
    ])

    st.info(
        "The MCP server lives in the `mcp_server/` package. This page "
        "describes its role in the architecture."
    )


# ============================================================
# PAGE: A2A NETWORK
# ============================================================

elif page == "A2A Network":

    st.title("A2A network")
    intro(
        "Agent-to-Agent lets other services hand questions to this "
        "system over JSON-RPC. It runs as its own server, separate from "
        "this app."
    )

    html(pipeline_svg("a2a"))

    st.markdown("### Start the service")
    st.code(
        "uvicorn agents.a2a_server:app --port 9000",
        language="powershell",
    )

    st.markdown("### Send a request")
    st.code(
        'python -m agents.a2a_client "Top customer segment by revenue?"',
        language="powershell",
    )

    st.warning(
        "This page does not check whether the A2A server is running."
    )


# ============================================================
# PAGE: EXECUTION INSPECTOR
# ============================================================

elif page == "Execution Inspector":

    st.title("Execution Inspector")
    intro(
        "Look inside the latest run: the plan, the SQL each query used, "
        "the data it returned and the critic's verdict."
    )

    state = st.session_state.last_state

    if not state:
        st.info(
            "Nothing to inspect yet. Ask a question in AI Workspace "
            "and the run will appear here."
        )

    else:

        approved = state.get("approved", False)
        revisions = state.get("revisions", 0)
        results = state.get("results", [])

        html(pipeline_svg("all", approved=approved, revisions=revisions))

        stat_row([
            ("Queries", str(len(results)), "Tasks the analyst ran"),
            ("Verdict", "Approved" if approved else "Not approved", "Critic's decision"),
            ("Revisions", str(revisions), "Rewrites by the writer"),
            ("Tasks planned", str(len(state.get("plan", []) or [])), "Steps from the planner"),
        ])

        tab_report, tab_sql, tab_data, tab_agents = st.tabs([
            "Report",
            "SQL",
            "Data",
            "Agents",
        ])

        with tab_report:
            st.markdown(state.get("report", "No report available."))

        with tab_sql:
            if results:
                for index, result in enumerate(results):
                    with st.expander(
                        f"Query {index + 1}: "
                        f"{result.get('question', 'Analysis task')}",
                        expanded=True,
                    ):
                        st.code(
                            result.get("sql") or "-- No SQL generated",
                            language="sql",
                        )
            else:
                st.info("No SQL queries were returned.")

        with tab_data:
            show_query_results(state)

        

        with tab_agents:
            st.markdown("### Planner output")
            st.json(state.get("plan", []))

            st.markdown("### Critic evaluation")

            if state.get("approved"):
                st.success("Report approved by critic.")
            else:
                st.warning("Report not approved by critic.")

            st.markdown("### Critic feedback")
            feedback = state.get("feedback", "")
            st.info(feedback or "No feedback available.")

            st.markdown("### Revision statistics")

            col1, col2 = st.columns(2)

            with col1:
                st.metric(
                    "Writer revisions",
                    state.get("revisions", 0)
                )

            with col2:
                st.metric(
                    "Critic evaluations",
                    state.get("critic_attempts", 0)
                )

            st.markdown("### Agent execution timings")

            timings = state.get("timings", {})

            for agent in ["schema", "planner", "analyst", "writer", "critic"]:
                if agent in timings:
                    st.write(f"**{agent.title()}**")
                    st.progress(
                        min(
                            timings[agent] / max(state.get("total_seconds", 1), 1),
                            1.0
                        )
                    )
                    st.caption(f"{timings[agent]:.2f} seconds")

            st.metric(
                "Total execution time",
                f"{state.get('total_seconds', 0):.2f} seconds"
            )



# ============================================================
# FOOTER
# ============================================================

st.divider()
html(
    '<div class="foot">Nexus runs locally with LangGraph, MCP, A2A '
    'and Ollama.</div>'
)