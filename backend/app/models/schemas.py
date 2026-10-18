from __future__ import annotations

import operator
import re
from datetime import datetime
from typing import Annotated, Any, List, Literal, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


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
    tags: Optional[List[str]] = Field(default_factory=list)
    requires_research: bool = False
    requires_citations: bool = False
    requires_code: bool = False

    @field_validator("tags", mode="before")
    def _normalize_tags(cls, v):
        return v if v is not None else []


class Plan(BaseModel):
    blog_title: str
    audience: str
    tone: str
    blog_kind: Literal[
        "explainer", "tutorial", "news_roundup", "comparison", "system_design"
    ] = "explainer"
    constraints: Optional[List[str]] = Field(default_factory=list)
    tasks: List[Task]

    @field_validator("constraints", mode="before")
    def _normalize_constraints(cls, v):
        return v if v is not None else []


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
    queries: Optional[List[str]] = Field(default_factory=list)
    max_results_per_query: int = Field(
        5, description="How many results to fetch per query (3-8)."
    )

    @field_validator("queries", mode="before")
    def _normalize_queries(cls, v):
        return v if v is not None else []


class EvidencePack(BaseModel):
    evidence: Optional[List[EvidenceItem]] = Field(default_factory=list)

    @field_validator("evidence", mode="before")
    def _normalize_evidence(cls, v):
        return v if v is not None else []


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


class LLMSelection(BaseModel):
    provider: str = "groq"
    model: Optional[str] = None
    api_key: Optional[SecretStr] = Field(default=None, repr=False)

    model_config = ConfigDict(extra="ignore")

    def __repr__(self) -> str:
        return f"LLMSelection(provider={self.provider!r}, model={self.model!r}, api_key=***)"

    def __str__(self) -> str:
        return self.__repr__()


class LLMTestResponse(BaseModel):
    ok: bool
    provider: str
    model: str
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# SlideDeck domain models (Tolerant Input Parsing)
# ---------------------------------------------------------------------------


class TolerantBaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class SlideBlock(TolerantBaseModel):
    heading: str = ""
    body: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_block(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"heading": "", "body": data}
        if not isinstance(data, dict):
            return {"heading": "", "body": ""}
        d = dict(data)
        # accept title/name/header as heading
        if not d.get("heading"):
            for alt in ("title", "name", "header"):
                if d.get(alt):
                    d["heading"] = str(d[alt])
                    break
        # if body is missing and bullets (list) is present, join them with "; " into body
        body = d.get("body")
        if body is None or body == "":
            bullets = d.get("bullets")
            if isinstance(bullets, list):
                d["body"] = "; ".join(str(b) for b in bullets if b is not None)
            elif isinstance(bullets, str):
                d["body"] = bullets
            else:
                d["body"] = ""
        elif isinstance(body, list):
            d["body"] = "; ".join(str(b) for b in body if b is not None)
        else:
            d["body"] = str(body)

        d["heading"] = str(d.get("heading") or "")
        return d


class SlideTable(TolerantBaseModel):
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_table(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return {"headers": [], "rows": []}
        d = dict(data)
        # accept header/columns as headers
        raw_headers = d.get("headers")
        if raw_headers is None:
            for alt in ("header", "columns", "column_names"):
                if alt in d and d[alt] is not None:
                    raw_headers = d[alt]
                    break
        if raw_headers is None:
            raw_headers = []
        elif isinstance(raw_headers, (str, int, float)):
            raw_headers = [str(raw_headers)]
        # coerce non-string cells to str
        headers = [str(h) if h is not None else "" for h in raw_headers]

        raw_rows = d.get("rows")
        if raw_rows is None:
            raw_rows = []
        elif not isinstance(raw_rows, list):
            raw_rows = [raw_rows]

        rows: List[List[str]] = []
        width = len(headers)
        for r in raw_rows:
            if isinstance(r, list):
                row_cells = [str(c) if c is not None else "" for c in r]
            elif isinstance(r, dict):
                if headers:
                    row_cells = [str(r.get(h, "")) for h in headers]
                else:
                    row_cells = [str(v) if v is not None else "" for v in r.values()]
            else:
                row_cells = [str(r) if r is not None else ""]

            # pad or trim rows to the header width
            if width > 0:
                if len(row_cells) < width:
                    row_cells.extend([""] * (width - len(row_cells)))
                elif len(row_cells) > width:
                    row_cells = row_cells[:width]
            rows.append(row_cells)

        return {"headers": headers, "rows": rows}


class SlideCode(TolerantBaseModel):
    language: str = "python"
    snippet: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_code(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"language": "python", "snippet": data}
        if not isinstance(data, dict):
            return {"language": "python", "snippet": ""}
        d = dict(data)
        # accept "code"/"content" as snippet
        if not d.get("snippet"):
            for alt in ("code", "content"):
                if d.get(alt):
                    d["snippet"] = str(d[alt])
                    break
        d.setdefault("language", "python")
        d["snippet"] = str(d.get("snippet") or "")
        return d


class SlideStat(TolerantBaseModel):
    value: str = ""
    label: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_stat(cls, data: Any) -> Any:
        if isinstance(data, str):
            text = data.strip()
            # extract first number-with-unit as value and use remaining text as label
            match = re.search(r'([+\-~]?(?:\$|€|£)?[0-9]+(?:\.[0-9]+)?(?:[xX%kKmMbBtT]|ms|s|ns|fps|GHz|MHz|MB|GB|TB|KB)?%?)', text)
            if match and match.group(1).strip():
                val = match.group(1).strip()
                lbl = (text[:match.start()] + " " + text[match.end():]).strip()
                val = re.sub(r'\s+', ' ', val)[:16]
                lbl = re.sub(r'\s+', ' ', lbl)
                return {"value": val, "label": lbl}
            else:
                val = text[:16]
                lbl = text[16:].strip()
                return {"value": val, "label": lbl}

        if not isinstance(data, dict):
            return {"value": "", "label": ""}

        d = dict(data)
        raw_val = str(d.get("value", "") or "")
        d["value"] = raw_val[:16]
        d["label"] = str(d.get("label", "") or "")
        return d


class SlideDesignBrief(TolerantBaseModel):
    audience: str = "general"
    narrative: str = ""
    takeaways: List[str] = Field(default_factory=list)
    running_example: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_brief(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return {"narrative": str(data) if data is not None else ""}
        d = dict(data)
        # accept story_arc/arc/story as narrative
        if not d.get("narrative"):
            for alt in ("story_arc", "arc", "story"):
                if d.get(alt):
                    d["narrative"] = str(d[alt])
                    break
        d.setdefault("narrative", "")
        d.setdefault("audience", "general")
        raw_t = d.get("takeaways")
        if raw_t is None:
            d["takeaways"] = []
        elif isinstance(raw_t, str):
            d["takeaways"] = [raw_t]
        elif isinstance(raw_t, list):
            d["takeaways"] = [str(x) for x in raw_t if x is not None]
        return d


class Slide(TolerantBaseModel):
    layout: str = "bullets"
    title: str = ""
    page_job: str = ""
    kicker: Optional[str] = None
    takeaway: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)
    blocks: List[SlideBlock] = Field(default_factory=list)
    table: Optional[SlideTable] = None
    equation: Optional[str] = None
    code: Optional[SlideCode] = None
    stat: Optional[SlideStat] = None
    insight: Optional[str] = None
    callout: Optional[str] = None
    speaker_notes: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_slide(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return {"layout": "bullets", "title": str(data or ""), "page_job": ""}
        d = dict(data)
        # unknown layout values fall back to "bullets"
        valid_layouts = {
            "title",
            "agenda",
            "bullets",
            "two_blocks",
            "table",
            "equation",
            "code",
            "summary_grid",
            "big_stat",
        }
        layout = str(d.get("layout", "") or "").lower().strip()
        if layout not in valid_layouts:
            d["layout"] = "bullets"
        else:
            d["layout"] = layout

        # title and page_job
        d["title"] = str(d.get("title") or "")
        d["page_job"] = str(d.get("page_job") or "")

        # equation: strip surrounding $, $$, \[ \], \begin{...}/\end{...} wrappers
        eq = d.get("equation")
        if eq is not None:
            eq_str = str(eq).strip()
            if eq_str.startswith("$$") and eq_str.endswith("$$") and len(eq_str) >= 4:
                eq_str = eq_str[2:-2].strip()
            elif eq_str.startswith("$") and eq_str.endswith("$") and len(eq_str) >= 2:
                eq_str = eq_str[1:-1].strip()
            elif eq_str.startswith(r"\[") and eq_str.endswith(r"\]") and len(eq_str) >= 4:
                eq_str = eq_str[2:-2].strip()
            eq_str = re.sub(r"^\\begin\{[a-zA-Z*]+\}\s*", "", eq_str)
            eq_str = re.sub(r"\s*\\end\{[a-zA-Z*]+\}$", "", eq_str)
            d["equation"] = eq_str.strip()

        # coerce null lists to []
        if d.get("bullets") is None:
            d["bullets"] = []
        elif isinstance(d["bullets"], str):
            d["bullets"] = [d["bullets"]]
        elif isinstance(d["bullets"], list):
            d["bullets"] = [str(b) for b in d["bullets"] if b is not None]

        if d.get("blocks") is None:
            d["blocks"] = []

        return d


class SlideDeck(TolerantBaseModel):
    design_brief: SlideDesignBrief = Field(default_factory=lambda: SlideDesignBrief())
    title: str = ""
    subtitle: Optional[str] = None
    author: str = "SAGE"
    short_title: str = ""
    slides: List[Slide] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_deck(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return {"title": "Presentation", "author": "SAGE", "slides": []}
        d = dict(data)

        slides_raw = d.get("slides")
        if slides_raw is None:
            d["slides"] = []
        elif not isinstance(slides_raw, list):
            d["slides"] = [slides_raw]

        # fill missing title from first slide's title (or "Presentation")
        title = d.get("title")
        if not title or not str(title).strip():
            first_slide_title = ""
            if d["slides"] and isinstance(d["slides"][0], dict):
                first_slide_title = d["slides"][0].get("title", "")
            title = str(first_slide_title).strip() if first_slide_title else "Presentation"
            d["title"] = title
        else:
            d["title"] = str(title).strip()

        # missing short_title from title (truncated to 30)
        short_title = d.get("short_title")
        if not short_title or not str(short_title).strip():
            d["short_title"] = d["title"][:30]
        else:
            d["short_title"] = str(short_title)[:30]

        # author default "SAGE"
        if not d.get("author") or not str(d["author"]).strip():
            d["author"] = "SAGE"
        else:
            d["author"] = str(d["author"]).strip()

        if "design_brief" not in d or d["design_brief"] is None:
            d["design_brief"] = {}

        return d


# ---------------------------------------------------------------------------
# Slide REST API schemas
# ---------------------------------------------------------------------------


class GenerateSlidesRequest(BaseModel):
    slide_count: int = Field(default=10, ge=8, le=16)
    audience: Optional[str] = None


class SlideJobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    stage: str
    progress: int
    slide_count: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Phase 3b: User Job History & Saved Key Schemas
# ---------------------------------------------------------------------------


class UserJobSummary(BaseModel):
    job_id: str
    topic: str
    status: str
    stage: str
    progress: int
    created_at: datetime
    has_slides: bool = False


class PaginatedUserJobs(BaseModel):
    items: List[UserJobSummary]
    total: int
    limit: int
    offset: int


class UserKeyItem(BaseModel):
    provider: str
    last4: str
    created_at: Optional[datetime] = None


class SaveKeyRequest(BaseModel):
    api_key: str = Field(..., max_length=512)

