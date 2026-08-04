from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage

from ..models.schemas import EvidenceItem, EvidencePack, State
from ..utils.config import llm
from ..utils.prompts import RESEARCH_SYSTEM


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tavily_search(query: str, max_results: int = 5) -> List[dict]:
    """Run a Tavily search and return a normalised list of result dicts."""
    tool = TavilySearchResults(max_results=max_results)
    results = tool.invoke({"query": query})
    normalized: List[dict] = []
    for r in results or []:
        normalized.append(
            {
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "snippet": r.get("content") or r.get("snippet") or "",
                "published_at": r.get("published_date") or r.get("published_at"),
                "source": r.get("source"),
            }
        )
    return normalized


def _iso_to_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------


def research_node(state: State) -> dict:
    """Fetch web evidence and synthesise it into a deduplicated EvidenceItem list."""
    queries = (state.get("queries", []) or [])[:10]
    max_results = 6

    raw_results: List[dict] = []
    for q in queries:
        raw_results.extend(_tavily_search(q, max_results=max_results))

    if not raw_results:
        return {"evidence": []}

    extractor = llm.with_structured_output(EvidencePack)
    pack = extractor.invoke(
        [
            SystemMessage(content=RESEARCH_SYSTEM),
            HumanMessage(
                content=(
                    f"As-of date: {state['as_of']}\n"
                    f"Recency days: {state['recency_days']}\n\n"
                    f"Raw results:\n{raw_results}"
                )
            ),
        ]
    )

    # Deduplicate by URL
    dedup: dict = {e.url: e for e in pack.evidence if e.url}
    evidence = list(dedup.values())

    # Filter to recency window for open_book mode
    if state.get("mode") == "open_book":
        as_of = date.fromisoformat(state["as_of"])
        cutoff = as_of - timedelta(days=int(state["recency_days"]))
        evidence = [
            e for e in evidence
            if (d := _iso_to_date(e.published_at)) and d >= cutoff
        ]

    return {"evidence": evidence}
