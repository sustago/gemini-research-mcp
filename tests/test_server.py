"""Smoke test: start the server over stdio like an MCP client does. Needs no valid API key."""

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = Path(__file__).parent.parent / "server.py"


async def list_tools() -> dict:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER)],
        env={**os.environ, "GEMINI_API_KEY": "dummy"},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        return {tool.name: tool for tool in (await session.list_tools()).tools}


def test_tools_are_listed():
    tools = asyncio.run(list_tools())

    assert set(tools) == {"research", "research_url"}
    assert tools["research"].input_schema["required"] == ["query"]
    assert tools["research_url"].input_schema["required"] == ["url"]
    assert tools["research"].input_schema["properties"]["detail"]["enum"] == ["low", "normal", "high"]
