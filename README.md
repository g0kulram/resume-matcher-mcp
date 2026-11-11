# Resume Matcher — MCP + LangGraph

A small, runnable Python project demonstrating a standardized MCP filesystem server and a LangGraph agent that consumes it. It uses local sample resumes and job descriptions and a deterministic keyword-overlap ranking baseline, so no API key is required.

## Requirements

- Python 3.11 or newer
- IntelliJ IDEA with the Python plugin (or another Python IDE)

## Run in IntelliJ

1. Unzip the project and open the extracted folder in IntelliJ IDEA.
2. Configure a Python 3.11+ interpreter for the project (a virtual environment is recommended).
3. In IntelliJ's terminal, install dependencies: `python -m pip install -r requirements.txt`.
4. Open `matching_agent.py` and run it. It launches `filesystem_mcp_server.py` as a child MCP process over stdio and prints candidate scores.
5. To inspect the server separately, run `mcp dev filesystem_mcp_server.py` in the terminal. This opens MCP Inspector when Node.js/npx is installed. The agent itself does not require Inspector.

To run from a terminal:

```bash
python -m pip install -r requirements.txt
python matching_agent.py
```

## Project map

- `filesystem_mcp_server.py` — MCP server with resources, tools, safe read-only filesystem access, config, batch processing, and directory watching.
- `matching_agent.py` — LangGraph workflow and official MCP stdio client; no direct filesystem operations.
- `data/` — sample job and resumes. Add UTF-8 `.txt` files here.
- `docs/workflow.mmd` — agent ↔ MCP state/workflow diagram source.
- `docs/test_scenarios.md` — manual protocol, tool, safety, configuration, and end-to-end scenarios.

## MCP interface

**Resources:** `resumes://list`, `jobs://list`, `resume://{filename}`, `job://{filename}`.

**Tools:** `list_files(area)`, `read_file(area, filename)`, `search_files(query, area)`, `batch_process(area, filenames?)`, `watch_directory(area, timeout_seconds, poll_interval)`.

The official Python MCP SDK handles JSON-RPC 2.0 framing, initialization, resource/tool discovery, and protocol-level error responses. The server validates areas, blocks path traversal, bounds file sizes and batch/watch durations, and reports batch-level file errors individually. Transport defaults to stdio, which is appropriate for a local MCP host; choose `MCP_TRANSPORT=streamable-http` when running the SDK's HTTP transport in a supported deployment environment.

## Configuration

Environment variables:

- `MCP_DATA_ROOT` (default `data`)
- `MCP_RESUME_DIR` (defaults to `<MCP_DATA_ROOT>/resumes`)
- `MCP_JOB_DIR` (defaults to `<MCP_DATA_ROOT>/jobs`)
- `MCP_MAX_FILE_BYTES` (default `2000000`)
- `MCP_TRANSPORT` (default `stdio`)

The agent points the server at this project's bundled `data/` directory. For a different dataset, update the server environment in `matching_agent.py` or launch the server from your MCP host with the appropriate settings.

## Demo video outline (5–6 minutes)

1. Show the project structure and explain the goal (30 sec).
2. Start MCP Inspector and show initialize, resource discovery, and resource reads (60 sec).
3. Demonstrate `search_files`, `batch_process`, a rejected traversal path, and `watch_directory` noticing a newly created resume (90 sec).
4. Explain the LangGraph nodes and the workflow diagram (60 sec).
5. Run `matching_agent.py` end to end and describe the scores/matched terms (60 sec).
6. Show configuration and summarize how another MCP server could be added as a second client connection (30 sec).

The bonus multi-server connection is left as an extension point; the required filesystem MCP integration is implemented end to end.
