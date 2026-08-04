from __future__ import annotations

from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from ..models.schemas import EvidenceItem, Plan, State, Task
from ..utils.config import llm
from ..utils.prompts import WORKER_SYSTEM


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_text(content) -> str:
    """Normalise LLM response content to a plain string."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(block.get("text", ""))
        return "".join(parts).strip()
    return str(content).strip()


# ---------------------------------------------------------------------------
# Worker node (one instance per task via fan-out)
# ---------------------------------------------------------------------------


def worker_node(payload: dict) -> dict:
    """Write a single blog section from its task payload and return it."""
    task = Task(**payload["task"])
    plan = Plan(**payload["plan"])
    evidence = [EvidenceItem(**e) for e in payload.get("evidence", [])]
    topic = payload["topic"]
    tone = payload.get("tone", "professional")
    mode = payload.get("mode", "closed_book")
    as_of = payload.get("as_of")
    recency_days = payload.get("recency_days")

    bullets_text = "\n- " + "\n- ".join(task.bullets)

    evidence_text = ""
    if evidence:
        evidence_text = "\n".join(
            f"- {e.title} | {e.url} | {e.published_at or 'date:unknown'}".strip()
            for e in evidence[:20]
        )

    response = llm.invoke(
        [
            SystemMessage(content=WORKER_SYSTEM),
            HumanMessage(
                content=(
                    f"Blog title: {plan.blog_title}\n"
                    f"Audience: {plan.audience}\n"
                    f"Tone: {tone}\n"
                    f"Blog kind: {plan.blog_kind}\n"
                    f"Constraints: {plan.constraints}\n"
                    f"Topic: {topic}\n"
                    f"Mode: {mode}\n"
                    f"As-of: {as_of} (recency_days={recency_days})\n\n"
                    f"Section title: {task.title}\n"
                    f"Goal: {task.goal}\n"
                    f"Target words: {task.target_words}\n"
                    f"Tags: {task.tags}\n"
                    f"requires_research: {task.requires_research}\n"
                    f"requires_citations: {task.requires_citations}\n"
                    f"requires_code: {task.requires_code}\n"
                    f"Bullets:{bullets_text}\n\n"
                    f"Evidence (ONLY use these URLs when citing):\n{evidence_text}\n"
                )
            ),
        ]
    )

    section_md = _extract_text(response.content)
    # Return as (task_id, markdown) tuple so reducer can sort by id
    return {"sections": [(task.id, section_md)]}


# ---------------------------------------------------------------------------
# Reducer node
# ---------------------------------------------------------------------------


def reducer_node(state: State) -> dict:
    """Merge all parallel sections into the final ordered Markdown blog post."""
    plan = state["plan"]
    if plan is None:
        raise ValueError("reducer_node called before a plan was produced.")

    ordered = [md for _, md in sorted(state["sections"], key=lambda x: x[0])]
    body = "\n\n".join(ordered).strip()
    final_md = f"# {plan.blog_title}\n\n{body}\n"

    return {"final": final_md}
