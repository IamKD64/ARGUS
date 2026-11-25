"""CLI:  python -m agents.run "Which AI models cost us the most in tokens?" """
import asyncio
import sys

from .graph import run_question
from .mcp_client import sales_session


async def main(question: str) -> None:
    async with sales_session() as session:
        state = await run_question(session, question)
    for r in state["results"]:
        print("SQL:", r["sql"])
    print("\n" + state["report"])
    print(f"\n(approved={state['approved']}, revisions={state['revisions']})")


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "Which department has the highest employee attrition, and what drives it?"))
