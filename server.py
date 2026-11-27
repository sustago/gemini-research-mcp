"""MCP server that delegates web research to Gemini (Google Search grounding, URL context)."""

import asyncio
import os
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

# The .env next to this file is found regardless of the client's working directory
load_dotenv(Path(__file__).parent / ".env")

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing: set it in the environment or run configure.py.")

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
gemini = genai.Client(api_key=API_KEY)
mcp = MCPServer("gemini-research", version="1.0.0")

INSTRUCTIONS = (
    "You write research briefs for another AI assistant. State facts with dates, numbers and names "
    "where they matter, mark uncertainty or conflicting sources, and leave out opinions and filler. "
    "Keep to the requested length, shorter if the subject is simple."
)

Detail = Literal["low", "normal", "high"]
LENGTH = {"low": 300, "normal": 800, "high": 2000}


async def ask_gemini(prompt: str, tool: genai_types.Tool) -> tuple[str, genai_types.Candidate]:
    try:
        response = await gemini.aio.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(system_instruction=INSTRUCTIONS, tools=[tool]),
        )
    except genai_errors.APIError as e:
        raise ToolError(f"Gemini API error {e.code}: {e.message}") from e
    if not response.candidates:
        raise ToolError("Gemini returned no candidates.")
    candidate = response.candidates[0]
    if not response.text:
        raise ToolError(f"Gemini returned no text (finish reason: {candidate.finish_reason}).")
    return response.text, candidate


async def resolve(http: httpx.AsyncClient, url: str) -> str:
    """Follow one redirect hop of a grounding link; fall back to the link itself."""
    try:
        response = await http.head(url)
    except httpx.HTTPError:
        return url
    return response.headers.get("location", url) if response.is_redirect else url


async def source_list(candidate: genai_types.Candidate) -> str:
    """Markdown list of the grounding sources, with redirect links replaced by their targets."""
    chunks = candidate.grounding_metadata.grounding_chunks if candidate.grounding_metadata else None
    webs = [chunk.web for chunk in chunks or [] if chunk.web and chunk.web.uri]
    if not webs:
        return ""
    async with httpx.AsyncClient(timeout=5) as http:
        urls = await asyncio.gather(*(resolve(http, web.uri) for web in webs))
    titles: dict[str, str] = {}
    for web, url in zip(webs, urls):
        titles.setdefault(url, web.title or url)
    return "\n\n**Sources:**\n" + "\n".join(f"- [{title}]({url})" for url, title in titles.items())


@mcp.tool(structured_output=False)
async def research(query: str, detail: Detail = "low") -> str:
    """Answer a question or brief a topic from a live Google search, with source links.

    Use for current events, recent releases, prices and anything that may postdate your training data.
    detail sets the length: low ≈ 300 words, normal ≈ 800, high ≈ 2000.
    """
    text, candidate = await ask_gemini(
        f"Search the web and write a brief of about {LENGTH[detail]} words on:\n\n{query}",
        genai_types.Tool(google_search=genai_types.GoogleSearch()),
    )
    return text + await source_list(candidate)


@mcp.tool(structured_output=False)
async def research_url(url: str, detail: Detail = "low") -> str:
    """Read a single web page and summarize it. Fails if the page cannot be retrieved.

    detail sets the length: low ≈ 300 words, normal ≈ 800, high ≈ 2000.
    """
    text, candidate = await ask_gemini(
        f"Read this page and summarize it in about {LENGTH[detail]} words:\n\n{url}",
        genai_types.Tool(url_context=genai_types.UrlContext()),
    )
    # Gemini answers even when the fetch failed, so check the retrieval status explicitly
    metadata = candidate.url_context_metadata.url_metadata if candidate.url_context_metadata else None
    statuses = [entry.url_retrieval_status for entry in metadata or []]
    if genai_types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_SUCCESS not in statuses:
        raise ToolError(f"Could not retrieve {url} (status: {statuses or 'unknown'}).")
    return text


if __name__ == "__main__":
    mcp.run()
