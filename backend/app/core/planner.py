from __future__ import annotations

from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Send

from ..models.schemas import Plan, RouterDecision, State
from ..utils.config import llm
from ..utils.prompts import ORCH_SYSTEM, ROUTER_PROMPT


# ---------------------------------------------------------------------------
# Router node
# ---------------------------------------------------------------------------


def router_node(state: State) -> dict:
    """Decide whether web research is needed and emit search queries."""
    topic = state["topic"]
    use_web = state.get("use_web", True)

    # Short-circuit: user disabled web research
    if not use_web:
        return {
            "needs_research": False,
            "mode": "closed_book",
            "queries": [],
            "recency_days": 3650,
        }

    decider = llm.with_structured_output(RouterDecision)
    decision = decider.invoke(
        [
            SystemMessage(content=ROUTER_PROMPT),
            HumanMessage(content=f"Topic: {topic}\nAs-of date: {state['as_of']}"),
        ]
    )

    recency_days = {"open_book": 7, "hybrid": 45}.get(decision.mode, 3650)

    return {
        "needs_research": decision.needs_research,
        "mode": decision.mode,
        "queries": decision.queries,
        "recency_days": recency_days,
    }


def route_next(state: State) -> str:
    """Conditional edge: go to research or skip straight to planning."""
    return "research" if state["needs_research"] else "orchestrator"


# ---------------------------------------------------------------------------
# Orchestrator (planner) node
# ---------------------------------------------------------------------------


def orchestator_node(state: State) -> dict:
    """Generate a structured outline (Plan) for the blog post."""
    planner = llm.with_structured_output(Plan)
    evidence = state.get("evidence", [])
    mode = state.get("mode", "closed_book")

    # User-controlled parameters injected into the prompt
    tone = state.get("tone", "professional")
    style = state.get("style", "blog")
    audience = state.get("audience", "developers")
    length = state.get("length", "medium")
    forced_kind = "news_roundup" if mode == "open_book" else None

    plan = planner.invoke(
        [
            SystemMessage(content=ORCH_SYSTEM),
            HumanMessage(
                content=(
                    f"Topic: {state['topic']}\n"
                    f"Tone: {tone}\n"
                    f"Style: {style}\n"
                    f"Target audience: {audience}\n"
                    f"Target length: {length}\n"
                    f"Mode: {mode}\n"
                    f"As-of: {state['as_of']} (recency_days={state['recency_days']})\n"
                    f"{'Force blog_kind=news_roundup' if forced_kind else ''}\n\n"
                    f"Evidence (ONLY use for fresh claims; may be empty):\n"
                    f"{[e.model_dump() for e in evidence][:16]}\n\n"
                    f"Instruction: If mode=open_book, your plan must NOT drift into a tutorial."
                )
            ),
        ]
    )

    # Hard-set blog_kind for news roundup mode
    if forced_kind:
        plan.blog_kind = "news_roundup"

    # Override planner's inferred tone/audience with user's explicit choices
    plan.tone = tone
    plan.audience = audience

    return {"plan": plan}


# ---------------------------------------------------------------------------
# Fan-out helper
# ---------------------------------------------------------------------------


def fanout(state: State) -> List[Send]:
    """Send each task to a parallel worker node via LangGraph's Send API."""
    assert state["plan"] is not None, "fanout called before plan was created"
    return [
        Send(
            "worker",
            {
                "task": task.model_dump(),
                "topic": state["topic"],
                "tone": state["tone"],
                "style": state["style"],
                "audience": state["audience"],
                "length": state["length"],
                "job_id": state["job_id"],
                "mode": state["mode"],
                "as_of": state["as_of"],
                "recency_days": state["recency_days"],
                "plan": state["plan"].model_dump(),
                "evidence": [e.model_dump() for e in state.get("evidence", [])],
            },
        )
        for task in state["plan"].tasks
    ]
