from __future__ import annotations

import operator
from typing import Annotated, List, Literal, Optional, TypedDict

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class Task(BaseModel):
    id: int
    title: str
    goal: str = Field(
        ..., description="One sentence describing what the reader should do/understand"
    )
    bullets: List[str] = Field(
        ...,
        min_length=3,
        max_length=6,
        description="3-6 concrete, non-overlapping subpoints to cover in this section.",
    )
    target_words: int = Field(..., description="Target words (120-550).")
    tags: List[str] = Field(default_factory=list)
    requires_research: bool = False
    requires_citations: bool = False
    requires_code: bool = False


class Plan(BaseModel):
    blog_title: str
    audience: str
    tone: str
    blog_kind: Literal[
        "explainer", "tutorial", "news_roundup", "comparison", "system_design"
    ] = "explainer"
    constraints: List[str] = Field(default_factory=list)
    tasks: List[Task]


class EvidenceItem(BaseModel):
    title: str
    url: str
    published_at: Optional[str] = None
    snippet: Optional[str] = None
    source: Optional[str] = None


class RouterDecision(BaseModel):
    needs_research: bool
    mode: Literal["closed_book", "hybrid", "open_book"]
    reason: str
    queries: List[str] = Field(default_factory=list)
    max_results_per_query: int = Field(
        5, description="How many results to fetch per query (3-8)."
    )


class EvidencePack(BaseModel):
    evidence: List[EvidenceItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LangGraph State
# ---------------------------------------------------------------------------


class State(TypedDict):
    # User-provided inputs
    topic: str
    tone: str
    style: str
    audience: str
    length: str
    use_web: bool
    job_id: str
    as_of: str

    # Agent-derived fields
    mode: str
    needs_research: bool
    queries: List[str]
    recency_days: int
    evidence: List[EvidenceItem]
    plan: Optional[Plan]
    # LangGraph reducer: sections from parallel workers are merged via operator.add
    sections: Annotated[List[tuple[int, str]], operator.add]
    final: str


# ---------------------------------------------------------------------------
# REST API schemas
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    topic: str
    tone: str = "professional"
    length: Literal["short", "medium", "long"] = "medium"
    style: Literal["blog", "tutorial", "explainer", "news_roundup", "comparison"] = "blog"
    audience: str = "developers"
    use_web: bool = True


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    stage: str
    progress: int
    error: Optional[str] = None


class BlogResult(BaseModel):
    title: str
    outline: List[dict]
    draft: str
    sources: List[dict]
