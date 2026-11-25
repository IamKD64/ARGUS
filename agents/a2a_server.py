"""Minimal Agent2Agent (A2A) server: publishes an Agent Card and answers JSON-RPC `message/send`.
This implements the core of the A2A spec by hand so you can see how it works. For production,
use the official SDK (pip install a2a-sdk) - see README.
Run: uvicorn agents.a2a_server:app --port 9000
"""
import uuid

from fastapi import FastAPI, Request

from .graph import run_question
from .mcp_client import sales_session

PORT_URL = "http://localhost:9000/"
AGENT_CARD = {
    "protocolVersion": "0.3.0",
    "name": "Sales Analyst Agent",
    "description": "Answers business questions about sales data using a multi-agent pipeline "
                   "(planner, SQL analyst via MCP, writer, critic).",
    "url": PORT_URL,
    "version": "1.0.0",
    "capabilities": {"streaming": False, "pushNotifications": False},
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["text/markdown"],
    "skills": [{"id": "sales_analysis", "name": "Sales analysis",
                "description": "Revenue, product, region and customer-segment analysis.",
                "tags": ["sql", "analytics", "sales"],
                "examples": ["Which region had the highest revenue in 2024?"]}],
}

app = FastAPI(title="A2A Sales Analyst")


@app.get("/.well-known/agent-card.json")
@app.get("/.well-known/agent.json")
def agent_card():
    return AGENT_CARD


def _text_of(message: dict) -> str:
    return " ".join(p.get("text", "") for p in message.get("parts", []) if p.get("kind", "text") == "text").strip()


@app.post("/")
async def rpc(request: Request):
    body = await request.json()
    rid = body.get("id")
    if body.get("method") != "message/send":
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}}
    question = _text_of(body.get("params", {}).get("message", {}))
    if not question:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": "Empty message"}}
    async with sales_session() as session:
        state = await run_question(session, question)
    return {"jsonrpc": "2.0", "id": rid, "result": {
        "kind": "message", "role": "agent", "messageId": str(uuid.uuid4()),
        "parts": [{"kind": "text", "text": state["report"]}]}}
