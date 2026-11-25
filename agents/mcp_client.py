import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def sales_session():
    """Spawn the MCP server as a subprocess and yield an initialized client session."""
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "mcp_server.server"], env=dict(os.environ), cwd=str(ROOT)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def call(session, tool: str, args: dict | None = None) -> str:
    res = await session.call_tool(tool, args or {})
    text = "".join(c.text for c in res.content if getattr(c, "type", "") == "text")
    if res.isError:
        raise RuntimeError(text or "tool error")
    return text
