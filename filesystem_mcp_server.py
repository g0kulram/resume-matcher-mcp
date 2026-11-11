"""MCP filesystem server for resume matching.

Run with: python filesystem_mcp_server.py (stdio transport; launched by the client).
The official MCP SDK implements JSON-RPC 2.0, initialization, discovery and errors.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


def _setting_path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).expanduser().resolve()


DATA_ROOT = _setting_path("MCP_DATA_ROOT", "data")
RESUME_DIR = _setting_path("MCP_RESUME_DIR", str(DATA_ROOT / "resumes"))
JOB_DIR = _setting_path("MCP_JOB_DIR", str(DATA_ROOT / "jobs"))
MAX_FILE_BYTES = int(os.getenv("MCP_MAX_FILE_BYTES", "2000000"))
for _directory in (RESUME_DIR, JOB_DIR):
    _directory.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("Resume Filesystem MCP", instructions="Read-only resume and job-description access. Use the tools to list, read, search, batch process, and watch files.")


def _safe_path(area: str, filename: str) -> Path:
    base = RESUME_DIR if area == "resumes" else JOB_DIR if area == "jobs" else None
    if base is None:
        raise ValueError("area must be 'resumes' or 'jobs'")
    target = (base / filename).resolve()
    if not target.is_relative_to(base):
        raise ValueError("path escapes configured data directory")
    if not target.is_file():
        raise FileNotFoundError(f"file not found: {filename}")
    if target.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"file exceeds configured limit ({MAX_FILE_BYTES} bytes)")
    return target


def _list_files(area: str) -> list[dict[str, Any]]:
    base = RESUME_DIR if area == "resumes" else JOB_DIR if area == "jobs" else None
    if base is None:
        raise ValueError("area must be 'resumes' or 'jobs'")
    return [{"name": p.name, "size": p.stat().st_size, "modified": p.stat().st_mtime}
            for p in sorted(base.iterdir()) if p.is_file() and not p.is_symlink()]


@mcp.tool()
def list_files(area: str = "resumes") -> list[dict[str, Any]]:
    """List available resume or job files. area: 'resumes' or 'jobs'."""
    return _list_files(area)


@mcp.tool()
def read_file(area: str, filename: str) -> dict[str, str]:
    """Read a UTF-8 resume or job-description file by its safe filename."""
    try:
        path = _safe_path(area, filename)
        return {"name": path.name, "text": path.read_text(encoding="utf-8")}
    except (ValueError, FileNotFoundError, UnicodeDecodeError) as exc:
        raise ValueError(str(exc)) from exc


@mcp.tool()
def search_files(query: str, area: str = "resumes") -> list[dict[str, Any]]:
    """Search filenames and UTF-8 text for a case-insensitive phrase."""
    if not query.strip():
        raise ValueError("query cannot be empty")
    matches = []
    for item in _list_files(area):
        path = _safe_path(area, item["name"])
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if query.casefold() in (path.name + "\n" + content).casefold():
            matches.append({"name": path.name, "size": item["size"]})
    return matches


@mcp.tool()
def batch_process(area: str = "resumes", filenames: list[str] | None = None) -> dict[str, Any]:
    """Read many files in one request; returns per-file content/errors."""
    names = filenames if filenames is not None else [x["name"] for x in _list_files(area)]
    if len(names) > 100:
        raise ValueError("batch limit is 100 files")
    results = []
    for name in names:
        try:
            path = _safe_path(area, name)
            results.append({"name": name, "text": path.read_text(encoding="utf-8"), "error": None})
        except (ValueError, FileNotFoundError, UnicodeDecodeError) as exc:
            results.append({"name": name, "text": None, "error": str(exc)})
    return {"area": area, "processed": len(results), "files": results}


@mcp.tool()
def watch_directory(area: str = "resumes", timeout_seconds: int = 30, poll_interval: float = 1.0) -> dict[str, Any]:
    """Wait for new files up to timeout_seconds and return added filenames (max 300s)."""
    if area not in ("resumes", "jobs"):
        raise ValueError("area must be 'resumes' or 'jobs'")
    timeout_seconds = max(0, min(int(timeout_seconds), 300))
    poll_interval = max(0.2, min(float(poll_interval), 10.0))
    before = {item["name"] for item in _list_files(area)}
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
        current = _list_files(area)
        added = [item["name"] for item in current if item["name"] not in before]
        if added:
            return {"area": area, "new_files": added, "timed_out": False}
    return {"area": area, "new_files": [], "timed_out": True}


@mcp.resource("resumes://list")
def resumes_resource() -> str:
    """Discover available resumes as a JSON resource."""
    return json.dumps(_list_files("resumes"), indent=2)


@mcp.resource("jobs://list")
def jobs_resource() -> str:
    """Discover available job descriptions as a JSON resource."""
    return json.dumps(_list_files("jobs"), indent=2)


@mcp.resource("resume://{filename}")
def resume_resource(filename: str) -> str:
    """Read a resume resource by filename."""
    return _safe_path("resumes", filename).read_text(encoding="utf-8")


@mcp.resource("job://{filename}")
def job_resource(filename: str) -> str:
    """Read a job description resource by filename."""
    return _safe_path("jobs", filename).read_text(encoding="utf-8")


if __name__ == "__main__":
    mcp.run(transport=os.getenv("MCP_TRANSPORT", "stdio"))
