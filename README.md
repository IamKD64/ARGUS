# ARGUS — Multi-Agent Intelligence Engine

**A locally runnable multi-agent AI system for business intelligence and analytical workflows.**

ARGUS brings together autonomous AI agents, database tools, and agent-to-agent communication to turn natural-language business questions into SQL-backed analytical reports.

Built with **LangGraph, Model Context Protocol (MCP), A2A-inspired communication, Ollama, and SQLite.**

---

## Overview

ARGUS demonstrates how multiple specialized AI agents can collaborate to answer business intelligence questions.

Instead of relying on a single LLM call, the system uses a coordinated workflow for planning, SQL analysis, report generation, and result evaluation.

### Key Capabilities

- **Multi-agent orchestration:** LangGraph coordinates planning, analysis, reporting, and evaluation.
- **Tool integration:** An MCP server exposes database operations to the agent workflow.
- **Agent communication:** A lightweight custom A2A-inspired JSON-RPC prototype demonstrates communication between independent agent services.
- **Local LLM inference:** Ollama runs the language model locally.
- **Business intelligence:** Natural-language questions are translated into SQL-backed insights.
- **Evaluation workflow:** A critic agent reviews generated reports and can request revisions.
- **Benchmarking:** A benchmark script evaluates the system against predefined questions.
- **Interactive dashboard:** Streamlit provides the user interface and execution inspector.

---

## Application Screenshots

Explore the ARGUS interface and its different components, including the dashboard, AI workspace, execution inspector, MCP tools, and A2A network.

### 1. Overview

The main dashboard introduces the ARGUS platform and its architecture.

![ARGUS Overview](docs/Overview.png)

![ARGUS Overview — Additional View](docs/Overview4A.png)

### 2. AI Workspace

Interact with the multi-agent system, submit analytical queries, and receive AI-generated business intelligence reports.

![ARGUS AI Workspace](docs/AIWorkSpace.png)

![ARGUS AI Workspace — View 2](docs/AIWorkSpace1.png)

![ARGUS AI Workspace — View 3](docs/AIWorkSpace2.png)

![ARGUS AI Workspace — View 4](docs/AIWorkSpace3.png)

### 3. Execution Inspector

Inspect agent execution, generated SQL queries, query results, and execution details.

![ARGUS Execution Inspector](docs/Execution-Inspector.png)

![ARGUS Execution Inspector — View 2](docs/Execution-Inspector1.png)

![ARGUS Execution Inspector — View 3](docs/Execution-Inspector2.png)

![ARGUS Execution Inspector — View 4](docs/Execution-Inspector3.png)

![ARGUS Execution Inspector — View 5](docs/Execution-Inspector4.png)

![ARGUS Execution Inspector — View 6](docs/Execution-Inspector5.png)

### 4. MCP Tools

Explore the Model Context Protocol integration and the tools exposed to ARGUS agents.

![ARGUS MCP Tools](docs/MCPTools.png)

![ARGUS MCP Tools — Additional View](docs/MCPTools1.png)

### 5. A2A Network

Explore agent-to-agent communication and the ARGUS multi-agent network.

![ARGUS A2A Network](docs/A2Anetwork.png)

![ARGUS A2A Network — Additional View](docs/A2Anetwork1.png)

---

## Architecture

ARGUS uses a coordinated multi-agent workflow orchestrated by LangGraph.

```mermaid
flowchart TD
    U[User] --> UI[Streamlit Interface]
    UI --> G[LangGraph Orchestrator]

    G --> P[Planner Agent]
    P --> A[Analyst Agent]
    A --> MCP[MCP Client]
    MCP --> DB[(SQLite Database)]

    A --> W[Writer Agent]
    W --> C[Critic Agent]

    C -->|Approved| R[Final Report]
    C -->|Revision| W

    G <--> L[Ollama Local LLM]
    G <--> A2A[A2A-inspired Agent Service]

    R --> UI
```

### Workflow

1. The user submits a natural-language business question through Streamlit.
2. The Planner Agent interprets the request and determines the analytical approach.
3. The Analyst Agent performs the required database analysis using MCP tools.
4. The Writer Agent converts the analytical results into a structured report.
5. The Critic Agent evaluates the generated report and can request revisions.
6. The final report is returned to the Streamlit interface.

---

## Technology Stack

| Component | Technology |
|---|---|
| Agent orchestration | LangGraph |
| LLM inference | Ollama |
| Language model | Llama 3.2 3B |
| Tool integration | Model Context Protocol |
| Agent communication | Custom A2A-inspired JSON-RPC |
| Database | SQLite |
| User interface | Streamlit |
| Data analysis | SQL |
| Testing | Pytest |
| Benchmarking | Python |

---

## Project Structure

```text
ARGUS/
├── agents/
│   ├── graph.py
│   ├── llm.py
│   ├── mcp_client.py
│   ├── a2a_client.py
│   ├── a2a_server.py
│   └── run.py
├── bench/
│   └── run_bench.py
├── data/
│   ├── hr_attrition.csv
│   └── llm_models.csv
├── mcp_server/
│   ├── server.py
│   ├── seed_db.py
│   └── guard.py
├── scripts/
├── tests/
├── docs/
│   └── Application screenshots
├── app.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11
- Git
- Ollama
- Approximately 16 GB RAM recommended for a comfortable local development experience with the selected model.

### 1. Clone the Repository

```bash
git clone https://github.com/IamKD64/ARGUS.git
cd ARGUS
```

### 2. Create a Virtual Environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```powershell
Copy-Item .env.example .env
```

### 5. Download the Local Model

```powershell
ollama pull llama3.2:3b
```

Ensure Ollama is running before starting ARGUS.

### 6. Initialize the Database

```powershell
python -m mcp_server.seed_db
```

### 7. Run the Application

```powershell
streamlit run app.py
```

Open the local Streamlit URL displayed in your terminal.

---

## Example Queries

Try asking ARGUS:

- Which department has the highest employee attrition, and is overtime associated with it?
- Which AI models have the highest total token costs?
- Which customer segments generate the most revenue?
- Which support ticket categories take the longest to resolve?

---

## Running Tests

Execute the test suite:

```powershell
python -m pytest -q tests
```

---

## Running the CLI

Run ARGUS directly from the command line:

```powershell
python -m agents.run "Which department has the highest attrition?"
```

---

## A2A Communication Demo

Start the agent service:

```powershell
uvicorn agents.a2a_server:app --port 9000
```

In another terminal, run the client:

```powershell
python -m agents.a2a_client "Top customer segment by revenue?"
```

The A2A component is a lightweight custom JSON-RPC prototype inspired by agent-to-agent communication patterns. It is not a claim of full official A2A protocol compliance.

---

## Benchmarking

Run the evaluation script:

```powershell
python -m bench.run_bench
```

The benchmark uses a predefined set of questions and expected answers to provide a basic indication of analytical performance.

It is intended as a demonstration and development aid, not a comprehensive scientific evaluation.

---

## Dataset Notes

ARGUS combines reference datasets and synthetic demonstration data.

- **Employee attrition data:** IBM HR Analytics sample dataset.
- **LLM model metadata:** Model pricing and context information.
- **Customer, product, and order records:** Synthetic data.
- **Token usage and support tickets:** Synthetic data generated for demonstration.

**Important:** The token usage and business records are not real company billing or customer records. Reported financial values are based on the local demonstration database.

---

## Design Considerations and Limitations

ARGUS is an educational and portfolio demonstration of an industry-inspired multi-agent architecture.

- SQL validation uses basic safeguards and is not a production-grade security boundary.
- LLM-generated analysis and evaluation can make mistakes.
- The custom A2A-inspired service is a minimal prototype.
- Benchmark results are indicative, not a guarantee of analytical accuracy.
- Local inference performance depends on available CPU, memory, and model configuration.

The project is not intended for production deployment or use with sensitive business data without additional engineering, security, and validation.

---

## Future Improvements

- Stronger SQL validation and query policies.
- More comprehensive evaluation datasets and metrics.
- Official A2A protocol integration.
- Persistent agent memory.
- Distributed model inference.
- Deployment with a hosted inference provider.

---

## Author

**ARGUS — Multi-Agent Intelligence Engine**

Built as an AI engineering portfolio project exploring multi-agent orchestration, tool integration, local LLM inference, and business intelligence.

**GitHub:** [IamKD64/ARGUS](https://github.com/IamKD64/ARGUS)