# gemini-research-mcp

A local [MCP](https://modelcontextprotocol.io) server (stdio) that hands web research to Gemini. Your assistant gets live search results and page summaries with source links, while the raw pages and search results stay out of its context.

| Tool | Arguments | What it does |
|------|-----------|--------------|
| `research` | `query`, `detail` | Runs a Google search via Gemini's search grounding and returns a summary plus a list of source URLs |
| `research_url` | `url`, `detail` | Fetches one page via Gemini's URL context tool and summarizes it. Returns an error if the page could not be retrieved, instead of a guessed summary |

`detail` sets the length of the summary: `low` (≈ 300 words, default), `normal` (≈ 800), `high` (≈ 2000).

## Requirements

- Python ≥ 3.11 and [Poetry](https://python-poetry.org/docs/#installation) 2.x
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey). **Search grounding needs a project with billing enabled**: on the free tier `research` fails with `429`. Costs are per request, see [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing).

## Installation

```bash
git clone <repo-url> gemini-research-mcp
cd gemini-research-mcp
poetry install --only main        # creates .venv/ in the project (see poetry.toml)
poetry run python configure.py    # prompts for the API key, writes .env with mode 600
```

Instead of running `configure.py` you can create `.env` yourself or pass the variables through your MCP client's config:

| Variable | Default | |
|----------|---------|---|
| `GEMINI_API_KEY` | – | required |
| `GEMINI_MODEL` | `gemini-3.5-flash` | any Gemini model that supports search grounding and URL context |

Environment variables set by the client take precedence over `.env`.

## Registering the server

The server is started by the client over stdio. Point the client at the interpreter inside `.venv` so no shell activation is needed:

- macOS/Linux: `<repo>/.venv/bin/python <repo>/server.py`
- Windows: `<repo>\.venv\Scripts\python.exe <repo>\server.py`

**Claude Code** (all projects):

```bash
claude mcp add --scope user gemini-research -- <repo>/.venv/bin/python <repo>/server.py
```

**Claude Desktop**: add to `mcpServers` in `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`), then restart the app:

```json
{
  "mcpServers": {
    "gemini-research": {
      "command": "<repo>/.venv/bin/python",
      "args": ["<repo>/server.py"]
    }
  }
}
```

Other MCP clients work the same way: a stdio server with the command above.

## Troubleshooting

| Error | Cause |
|-------|-------|
| `GEMINI_API_KEY is missing` on startup | No `.env` next to `server.py` and no variable from the client |
| `404 … no longer available to new users` | Google retired the model for new keys. Set `GEMINI_MODEL` to a current one |
| `429 … exceeded your current quota` | Billing is not enabled, or the rate limit was hit |
| `503 … high demand` | Model temporarily overloaded. Retry later or switch `GEMINI_MODEL` |
| `Could not retrieve <url>` | Gemini could not fetch the page (paywall, bot protection, unreachable host) |

The server logs to stderr. In Claude Code, `/mcp` shows the connection status.

## Development

```bash
poetry install
poetry run pytest    # starts the server over stdio and checks the tool schemas, no API key needed
```

## License

[MIT](LICENSE)
