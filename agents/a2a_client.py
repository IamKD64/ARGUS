"""A second, independent agent that discovers the Sales Analyst via its Agent Card and delegates to it.
Run (server must be up):  python -m agents.a2a_client "Top 3 products by revenue?" """
import sys
import uuid

import httpx


def ask_remote_agent(base_url: str, question: str) -> str:
    card = httpx.get(f"{base_url}/.well-known/agent-card.json", timeout=30).json()
    print(f"Discovered agent: {card['name']} - skills: {[s['id'] for s in card['skills']]}")
    payload = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "message/send",
               "params": {"message": {"kind": "message", "role": "user", "messageId": str(uuid.uuid4()),
                                      "parts": [{"kind": "text", "text": question}]}}}
    resp = httpx.post(card["url"], json=payload, timeout=900).json()
    if "error" in resp:
        raise RuntimeError(resp["error"])
    return "".join(p["text"] for p in resp["result"]["parts"])


if __name__ == "__main__":
    print(ask_remote_agent("http://localhost:9000", " ".join(sys.argv[1:]) or "Which region has the highest revenue?"))
