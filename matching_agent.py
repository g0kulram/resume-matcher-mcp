"""LangGraph resume matcher using only an MCP client for filesystem access."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MatchState(TypedDict, total=False):
    job_file: str
    job: str
    resumes: list[dict[str, Any]]
    matches: list[dict[str, Any]]
    resources: list[str]
    error: str


def _json_result(result: Any) -> Any:
    if getattr(result, "isError", False):
        raise RuntimeError("MCP tool returned an error")
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    for block in getattr(result, "content", []):
        if getattr(block, "text", None):
            try:
                return json.loads(block.text)
            except json.JSONDecodeError:
                return block.text
    return None


def _terms(text: str) -> set[str]:
    stop = {"the", "and", "for", "with", "from", "this", "that", "you", "our", "are", "will", "have", "has", "your", "into", "years", "year", "experience", "role", "team", "strong", "ability", "using"}
    return {w for w in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.\-]{1,}", text.casefold()) if w not in stop}


def build_graph(session: ClientSession):
    async def discover(state: MatchState) -> dict[str, Any]:
        resources = await session.list_resources()
        uris = [str(item.uri) for item in resources.resources]
        # Include templated resources from discovery as well.
        templates = await session.list_resource_templates()
        uris.extend(str(item.uriTemplate) for item in templates.resourceTemplates)
        return {"resources": uris}

    async def load_job(state: MatchState) -> dict[str, Any]:
        job_name = state.get("job_file", "data-engineer.txt")
        job = _json_result(await session.call_tool("read_file", {"area": "jobs", "filename": job_name}))
        return {"job": job["text"]}

    async def load_resumes(state: MatchState) -> dict[str, Any]:
        batch = _json_result(await session.call_tool("batch_process", {"area": "resumes"}))
        return {"resumes": [item for item in batch["files"] if item.get("text") and not item.get("error")]}

    async def rank(state: MatchState) -> dict[str, Any]:
        job_terms = _terms(state["job"])
        scored = []
        for resume in state.get("resumes", []):
            resume_terms = _terms(resume["text"])
            overlap = sorted(job_terms & resume_terms)
            score = round(100 * len(overlap) / max(1, len(job_terms)), 1)
            scored.append({"resume": resume["name"], "score": score, "matched_terms": overlap})
        scored.sort(key=lambda x: (-x["score"], x["resume"].casefold()))
        return {"matches": scored}

    graph = StateGraph(MatchState)
    graph.add_node("discover_mcp_resources", discover)
    graph.add_node("load_job_via_mcp", load_job)
    graph.add_node("batch_read_resumes_via_mcp", load_resumes)
    graph.add_node("rank_candidates", rank)
    graph.add_edge(START, "discover_mcp_resources")
    graph.add_edge("discover_mcp_resources", "load_job_via_mcp")
    graph.add_edge("load_job_via_mcp", "batch_read_resumes_via_mcp")
    graph.add_edge("batch_read_resumes_via_mcp", "rank_candidates")
    graph.add_edge("rank_candidates", END)
    return graph.compile()


async def run(job_file: str = "data-engineer.txt") -> dict[str, Any]:
    root = Path(__file__).resolve().parent
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(root / "filesystem_mcp_server.py")],
        env={**os.environ, "MCP_DATA_ROOT": str(root / "data")},
    )
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await build_graph(session).ainvoke({"job_file": job_file})


def main() -> None:
    job_file = sys.argv[1] if len(sys.argv) > 1 else "data-engineer.txt"
    try:
        result = asyncio.run(run(job_file))
    except Exception as exc:
        print(f"Agent failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print("MCP resources discovered:")
    print("\n".join(f"  - {item}" for item in result["resources"]))
    print("\nCandidate ranking (keyword overlap baseline):")
    for item in result["matches"]:
        print(f"  {item['score']:5.1f}%  {item['resume']}  | matched: {', '.join(item['matched_terms'])}")


if __name__ == "__main__":
    main()
