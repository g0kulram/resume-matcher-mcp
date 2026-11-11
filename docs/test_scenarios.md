# Manual test scenarios

Run the commands from the project root after installing `requirements.txt`.

1. **Protocol startup and discovery** — open `filesystem_mcp_server.py` in MCP Inspector (`mcp dev filesystem_mcp_server.py`) or configure it as a stdio server in an MCP host. Confirm initialization succeeds, tools list contains `list_files`, `read_file`, `search_files`, `batch_process`, `watch_directory`, and resources list contains `resumes://list` and `jobs://list`.
2. **Read resource** — read `resumes://list`, then `resume://alex-chen.txt`. Confirm the JSON listing and UTF-8 text are returned.
3. **Tool search** — call `search_files` with `query="Spark"`, `area="resumes"`; Alex and Jordan should be returned.
4. **Batch processing** — call `batch_process` with `area="resumes"`. Confirm all sample resumes are returned in one request. Call it with `filenames=["missing.txt"]` to see a per-file error while the batch response remains valid.
5. **Path protection** — call `read_file` with `filename="../.env"`. Confirm a JSON-RPC tool error is returned and no outside file is read.
6. **Directory watch** — call `watch_directory` with `timeout_seconds=20`, then add a new `.txt` file to `data/resumes` while the call is waiting. Confirm its name appears in `new_files`. A no-change call should return `timed_out: true`.
7. **End-to-end LangGraph agent** — run `python matching_agent.py`. Confirm the graph discovers MCP resources, obtains the job description and resume batch through MCP tools, and prints a descending ranking. Alex should rank above Sam for the sample role.
8. **Configuration** — set `MCP_DATA_ROOT` to a different data directory when launching the MCP server; confirm resources/tools read only the configured resume and job folders.

Note: the SDK maps handler exceptions to MCP/JSON-RPC errors; batch processing intentionally captures per-file errors so remaining files still process.
