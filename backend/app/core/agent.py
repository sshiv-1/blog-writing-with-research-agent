"""
agent.py — LangGraph graph compiled once at module load.

The graph is a singleton (_compiled_graph). Per-request state (topic, tone, job_id, etc.)
is passed via the State dict at invocation time — only the state changes per call.

Public API
----------
generate_blog(job_id, topic, ...) -> None
    Runs the full pipeline and updates the job store in place.
    Designed to be called from a background thread (FastAPI BackgroundTasks or CLI).
"""
from __future__ import annotations

import warnings
from datetime import date
from typing import Optional

from langgraph.graph import END, START, StateGraph

from ..models.schemas import State
from .jobs import update_job
from .planner import fanout, orchestator_node, route_next, router_node
from .research import research_node
from .writer import reducer_node, worker_node

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Status-aware node wrappers
# Each wrapper updates the job store before delegating to the real node.
# Because job_id lives in State (and in worker payloads), this is safe
# across concurrent requests without any shared mutable state.
# ---------------------------------------------------------------------------


def _router(state: State) -> dict:
    update_job(state["job_id"], status="running", stage="routing", progress=10)
    return router_node(state)


def _research(state: State) -> dict:
    update_job(state["job_id"], stage="researching", progress=25)
    return research_node(state)


def _orchestrator(state: State) -> dict:
    update_job(state["job_id"], stage="planning", progress=50)
    return orchestator_node(state)


def _worker(payload: dict) -> dict:
    # Multiple workers may run in parallel; this update is idempotent.
    update_job(payload["job_id"], stage="writing", progress=65)
    return worker_node(payload)


def _reducer(state: State) -> dict:
    update_job(state["job_id"], stage="finalizing", progress=90)
    return reducer_node(state)


# ---------------------------------------------------------------------------
# Build and compile the graph ONCE at module load
# ---------------------------------------------------------------------------


def _build_graph():
    g = StateGraph(State)
    g.add_node("router", _router)
    g.add_node("research", _research)
    g.add_node("orchestrator", _orchestrator)
    g.add_node("worker", _worker)
    g.add_node("reducer", _reducer)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        route_next,
        {"research": "research", "orchestrator": "orchestrator"},
    )
    g.add_edge("research", "orchestrator")
    g.add_conditional_edges("orchestrator", fanout, ["worker"])
    g.add_edge("worker", "reducer")
    g.add_edge("reducer", END)

    return g.compile()


# Module-level singleton — reused for every generate_blog() call
_compiled_graph = _build_graph()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_blog(
    job_id: str,
    topic: str,
    tone: str = "professional",
    length: str = "medium",
    style: str = "blog",
    audience: str = "developers",
    use_web: bool = True,
    as_of: Optional[str] = None,
) -> None:
    """
    Run the full blog-generation pipeline.

    Invokes the compiled LangGraph graph with the given parameters,
    updates the job store at each stage, and stores the final result
    (or error) when complete.
    """
    if as_of is None:
        as_of = date.today().isoformat()

    try:
        out = _compiled_graph.invoke(
            {
                "topic": topic,
                "tone": tone,
                "style": style,
                "audience": audience,
                "length": length,
                "use_web": use_web,
                "job_id": job_id,
                "as_of": as_of,
                # Agent-derived — initialised to empty/defaults
                "mode": "",
                "needs_research": False,
                "queries": [],
                "recency_days": 7,
                "evidence": [],
                "plan": None,
                "sections": [],
                "final": "",
            }
        )

        plan = out["plan"]
        result = {
            "title": plan.blog_title,
            "outline": [t.model_dump() for t in plan.tasks],
            "draft": out["final"],
            "sources": [e.model_dump() for e in out.get("evidence", [])],
        }

        update_job(job_id, status="done", stage="done", progress=100, result=result)

    except Exception as exc:
        update_job(job_id, status="error", stage="error", error=str(exc))
        raise
