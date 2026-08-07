"""Session orchestration graph (AGT-006, `GET /sessions/{id}/graph`).

Reconstructed entirely from persisted state on every request — Runs'
`parent_run_id` chains (delegation edges, AGT-006) and ToolRuns' `session_id`
(tool nodes) — rather than a separately maintained graph structure, so it can
never drift from what the session's Runs/ToolRuns actually recorded happening.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from harness.core.app import Application

NodeType = Literal["user", "contact", "tool"]
EdgeType = Literal["message", "delegation"]


class GraphNode(BaseModel):
    id: str
    type: NodeType
    label: str
    status: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    type: EdgeType
    run_id: str


class SessionGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


async def build_session_graph(app: Application, session_id: str) -> SessionGraph:
    runs = await app.runs.list_for_session(session_id)
    tool_runs = await app.tool_runs.list(session_id=session_id)
    runs_by_id = {run.id: run for run in runs}

    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    if runs:
        nodes["user"] = GraphNode(id="user", type="user", label="user")

    contact_handles: dict[str, str] = {}
    for run in runs:
        if run.contact_id not in contact_handles:
            contact = await app.contacts.get(run.contact_id)
            contact_handles[run.contact_id] = contact.handle
        handle = contact_handles[run.contact_id]
        node_id = f"contact:{run.contact_id}"
        # A contact can have several runs in one session; the node reflects the
        # most recently created run's status rather than one per invocation —
        # `runs` is already ordered by created_at, so later assignments win.
        nodes[node_id] = GraphNode(
            id=node_id, type="contact", label=f"@{handle}", status=run.status
        )

        if run.parent_run_id is None:
            edges.append(GraphEdge(source="user", target=node_id, type="message", run_id=run.id))
        else:
            parent_run = runs_by_id.get(run.parent_run_id)
            if parent_run is not None:
                parent_node_id = f"contact:{parent_run.contact_id}"
                edges.append(
                    GraphEdge(
                        source=parent_node_id, target=node_id, type="delegation", run_id=run.id
                    )
                )

    for tool_run in tool_runs:
        node_id = f"tool:{tool_run.id}"
        nodes[node_id] = GraphNode(
            id=node_id, type="tool", label=tool_run.tool_name, status=tool_run.status
        )

    return SessionGraph(nodes=list(nodes.values()), edges=edges)
