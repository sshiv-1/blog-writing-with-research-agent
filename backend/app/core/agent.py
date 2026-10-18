"""
agent.py — Single-file LangGraph blog-generation workflow.

Consolidates the full pipeline (router → research → planner/orchestrator →
parallel workers → reducer) into one module.  Groq-specific fixes from
Phase 1 are folded in: retry/backoff on 429, worker semaphore(3), json_mode
for evidence extraction, null-to-[] validators (in schemas.py), compact
Tavily snippets (350 chars), and a sliding-window Tavily rate limiter.

Public API
----------
generate_blog(job_id, topic, ...) -> None
    Runs the full pipeline and updates the job store in place.
    Designed to be called from a background thread (FastAPI BackgroundTasks
    or CLI).
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import warnings
from collections import deque
from datetime import date, timedelta
from functools import wraps
from typing import Callable, List, Optional, TypeVar

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from ..models.schemas import (
    EvidenceItem,
    EvidencePack,
    LLMSelection,
    Plan,
    RouterDecision,
    State,
    Task,
)
from .jobs import update_job
from .llm import (
    PROVIDER_REGISTRY,
    blog_llm,
    get_llm,
    scrub_exception_chain,
)

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)


class _LazyBlogLLM:
    """Lazy proxy so module import does not trigger immediate LLM instantiation or env checks."""
    _instance = None

    def __getattr__(self, name):
        if self._instance is None:
            self._instance = blog_llm()
        return getattr(self._instance, name)


# Legacy module-level fallback (lazy)
llm = _LazyBlogLLM()


# ═══════════════════════════════════════════════════════════════════════════
# Helpers: rate limiter & retry decorator
# ═══════════════════════════════════════════════════════════════════════════


class SlidingWindowRateLimiter:
    """
    Thread-safe sliding window rate limiter.

    Guarantees no more than `max_requests` occur within any rolling `period_seconds`.
    Also enforces an optional `min_interval` spacing between consecutive calls.
    """

    def __init__(
        self,
        max_requests: int = 100,
        period_seconds: float = 60.0,
        min_interval: float = 0.6,
    ):
        self.max_requests = max_requests
        self.period_seconds = period_seconds
        self.min_interval = min_interval
        self._timestamps: deque[float] = deque()
        self._last_call: float = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a request slot is available under the rate limit."""
        with self._lock:
            now = time.monotonic()

            # Enforce minimum spacing between calls if configured
            if self.min_interval > 0 and self._last_call > 0:
                elapsed_since_last = now - self._last_call
                if elapsed_since_last < self.min_interval:
                    sleep_needed = self.min_interval - elapsed_since_last
                    time.sleep(sleep_needed)
                    now = time.monotonic()

            # Purge timestamps outside the rolling period window
            cutoff = now - self.period_seconds
            while self._timestamps and self._timestamps[0] <= cutoff:
                self._timestamps.popleft()

            # If capacity reached in the rolling window, wait until oldest expires
            if len(self._timestamps) >= self.max_requests:
                sleep_needed = self._timestamps[0] + self.period_seconds - now
                if sleep_needed > 0:
                    logger.info(
                        "Rate limit reached (%d/%d reqs). Pausing %.2fs...",
                        len(self._timestamps),
                        self.max_requests,
                        sleep_needed,
                    )
                    time.sleep(sleep_needed)
                    now = time.monotonic()
                    # Clean up again after sleeping
                    cutoff = now - self.period_seconds
                    while self._timestamps and self._timestamps[0] <= cutoff:
                        self._timestamps.popleft()

            now = time.monotonic()
            self._timestamps.append(now)
            self._last_call = now


# Shared singleton for Tavily search: 100 requests per 60 seconds (user's tier limit)
tavily_rate_limiter = SlidingWindowRateLimiter(
    max_requests=100,
    period_seconds=60.0,
    min_interval=0.6,  # 60s / 100 reqs = 0.6s spacing
)


T = TypeVar("T")


def retry_on_rate_limit(
    max_retries: int = 5,
    initial_backoff: float = 2.0,
    backoff_factor: float = 2.0,
):
    """Decorator that retries a function on Groq 429 (rate-limit) errors with exponential backoff."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            backoff = initial_backoff
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    # Check for 429 status code in the exception
                    exc_str = str(exc).lower()
                    status_code = getattr(exc, "status_code", None)
                    is_rate_limit = (
                        status_code == 429
                        or "429" in exc_str
                        or "rate_limit" in exc_str
                        or "rate limit" in exc_str
                        or "too many requests" in exc_str
                    )
                    if is_rate_limit and attempt < max_retries:
                        logger.warning(
                            "Rate limited (429) on attempt %d/%d. "
                            "Retrying in %.1fs...",
                            attempt + 1,
                            max_retries + 1,
                            backoff,
                        )
                        time.sleep(backoff)
                        backoff *= backoff_factor
                    else:
                        raise

        return wrapper

    return decorator


# ═══════════════════════════════════════════════════════════════════════════
# Prompt constants
# ═══════════════════════════════════════════════════════════════════════════


ROUTER_PROMPT = """You are a routing module for a technical blog planner.

Decide whether web research is needed BEFORE planning.

Modes:
- closed_book (needs_research=false):
  Evergreen topics where correctness does not depend on recent facts (concepts, fundamentals).
- hybrid (needs_research=true):
  Mostly evergreen but needs up-to-date examples/tools/models to be useful.
- open_book (needs_research=true):
  Mostly volatile: weekly roundups, "this week", "latest", rankings, pricing, policy/regulation.

If needs_research=true:
- Output 3-10 high-signal queries.
- Queries should be scoped and specific (avoid generic queries like just "AI" or "LLM").
- For open_book weekly roundup, include queries that reflect the last 7 days constraint.
"""

RESEARCH_SYSTEM = """You are a research synthesizer for technical writing.

Given raw web search results, produce a valid JSON object matching the EvidencePack schema with an "evidence" array of EvidenceItem objects.

Rules:
- Return a valid JSON object with key "evidence".
- Only include items with a non-empty url.
- Prefer relevant + authoritative sources (company blogs, docs, reputable outlets).
- Extract/normalize published_at as ISO (YYYY-MM-DD) if you can infer it from title/snippet.
  If you can't infer a date reliably, set published_at=null (do NOT guess).
- Keep snippets short.
- Deduplicate by URL.
"""

ORCH_SYSTEM = """You are a senior technical writer and developer advocate.
Your job is to produce a highly actionable outline for a technical blog post.

IMPORTANT: The user has explicitly specified tone, audience, and style — honour them exactly.
Do NOT override or reinterpret these values.

Length hint maps to approximate per-section word targets:
  - short  -> 120-200 words per section
  - medium -> 200-400 words per section
  - long   -> 350-550 words per section

Hard requirements:
- Create 5-9 sections (tasks) suitable for the topic and audience.
- Each task must include:
  1) goal (1 sentence)
  2) 3-6 bullets that are concrete, specific, and non-overlapping
  3) target word count within the length range above

Flexibility:
- Do NOT use a fixed taxonomy unless it naturally fits.
- You may tag tasks (tags field), but tags are flexible.

Quality bar:
- Assume the reader matches the specified audience; use correct terminology.
- Bullets must be actionable: build/compare/measure/verify/debug.
- Ensure the overall plan includes at least 2 of these somewhere:
  * minimal code sketch / MWE (set requires_code=True for that section)
  * edge cases / failure modes
  * performance/cost considerations
  * security/privacy considerations (if relevant)
  * debugging/observability tips

Grounding rules:
- Mode closed_book: keep it evergreen; do not depend on evidence.
- Mode hybrid:
  - Use evidence for up-to-date examples (models/tools/releases) in bullets.
  - Mark sections using fresh info as requires_research=True and requires_citations=True.
- Mode open_book (weekly news roundup):
  - Set blog_kind = "news_roundup".
  - Every section is about summarizing events + implications.
  - DO NOT include tutorial/how-to sections (no scraping/RSS/how to fetch news)
    unless user explicitly asked for that.
  - If evidence is empty or insufficient, create a plan that transparently says
    "insufficient fresh sources" and includes only what can be supported.

Output must strictly match the Plan schema.
"""

WORKER_SYSTEM = """You are a senior technical writer and developer advocate.
Write ONE section of a technical blog post in Markdown.

Hard constraints:
- Follow the provided Goal and cover ALL Bullets in order (do not skip or merge bullets).
- Stay close to Target words (+-15%).
- Output ONLY the section content in Markdown (no blog title H1, no extra commentary).
- Start with a '## <Section Title>' heading.
- Match the specified Tone exactly throughout the section.

Scope guard (prevents mid-blog topic drift):
- If blog_kind == "news_roundup": do NOT turn this into a tutorial/how-to guide.
  Do NOT teach web scraping, RSS, automation, or "how to fetch news" unless bullets
  explicitly ask for it. Focus on summarizing events and implications.

Grounding policy:
- If mode == open_book (weekly news):
  - Do NOT introduce any specific event/company/model/funding/policy claim unless it is
    supported by provided Evidence URLs.
  - For each event claim, attach a source as a Markdown link: ([Source](URL)).
  - Only use URLs provided in Evidence. If not supported, write: "Not found in provided sources."
- If requires_citations == true (hybrid sections):
  - For outside-world claims, cite Evidence URLs the same way.
- Evergreen reasoning (concepts, intuition) is OK without citations unless
  requires_citations is true.

Code:
- If requires_code == true, include at least one minimal, correct code snippet relevant
  to the bullets.

Style:
- Short paragraphs, bullets where helpful, code fences for code.
- Avoid fluff/marketing. Be precise and implementation-oriented.
"""


# ═══════════════════════════════════════════════════════════════════════════
# Small helpers
# ═══════════════════════════════════════════════════════════════════════════


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


def _tavily_search(query: str, max_results: int = 3) -> List[dict]:
    """Run a Tavily search under the 100 req/min rate limit and return normalised results."""
    # Enforce Tavily 100 requests/minute tier limit
    tavily_rate_limiter.acquire()

    tool = TavilySearchResults(max_results=max_results)
    results = tool.invoke({"query": query})
    normalized: List[dict] = []
    for r in results or []:
        raw_text = r.get("snippet") or r.get("content") or ""
        # Compact snippet to 350 chars to prevent prompt bloat against Groq TPM limits
        snippet = raw_text[:350].strip()
        normalized.append(
            {
                "title": (r.get("title") or "").strip(),
                "url": (r.get("url") or "").strip(),
                "snippet": snippet,
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


# Limit parallel workers to avoid Groq 429 rate limits (default fallback)
_WORKER_SEMAPHORE = threading.Semaphore(3)


def _clean_json_text(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def invoke_structured(
    llm_instance: Any,
    schema: type[T],
    messages: list[Any],
    method: Optional[str] = None,
    keys_to_scrub: Optional[list[str]] = None,
) -> T:
    """
    Invoke LLM with structured output, falling back to JSON schema prompt + raw invoke + validation.
    """
    try:
        if method:
            runnable = llm_instance.with_structured_output(schema, method=method)
        else:
            runnable = llm_instance.with_structured_output(schema)
        return runnable.invoke(messages)
    except Exception as first_exc:
        logger.warning(
            "with_structured_output failed (%s), falling back to prompt JSON schema validation",
            scrub_exception_chain(first_exc, keys_to_scrub),
        )

    # Fallback to prompt-based JSON output and validation
    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    fallback_sys = (
        f"\nIMPORTANT: Your output MUST be a valid JSON object matching this schema:\n"
        f"{schema_json}\n"
        f"Return ONLY valid JSON matching the schema above. Do NOT include markdown code blocks or extra text."
    )
    fallback_messages = list(messages)
    if fallback_messages and isinstance(fallback_messages[0], SystemMessage):
        fallback_messages[0] = SystemMessage(
            content=fallback_messages[0].content + "\n" + fallback_sys
        )
    else:
        fallback_messages.insert(0, SystemMessage(content=fallback_sys))

    resp = llm_instance.invoke(fallback_messages)
    raw = _extract_text(resp.content if hasattr(resp, "content") else resp)
    cleaned = _clean_json_text(raw)
    data = json.loads(cleaned)
    return schema.model_validate(data)


# ═══════════════════════════════════════════════════════════════════════════
# LangGraph edge functions
# ═══════════════════════════════════════════════════════════════════════════


def route_next(state: State) -> str:
    """Conditional edge: go to research or skip straight to planning."""
    return "research" if state["needs_research"] else "orchestrator"


def execute_router(state: State, active_llm: Any, keys_to_scrub: Optional[list[str]] = None) -> dict:
    """Decide whether web research is needed and emit search queries."""
    topic = state["topic"]
    use_web = state.get("use_web", True)

    if not use_web:
        return {
            "needs_research": False,
            "mode": "closed_book",
            "queries": [],
            "recency_days": 3650,
        }

    messages = [
        SystemMessage(content=ROUTER_PROMPT),
        HumanMessage(content=f"Topic: {topic}\nAs-of date: {state['as_of']}"),
    ]

    @retry_on_rate_limit(max_retries=3, initial_backoff=2.0)
    def _invoke():
        return invoke_structured(active_llm, RouterDecision, messages, keys_to_scrub=keys_to_scrub)

    decision = _invoke()
    recency_days = {"open_book": 7, "hybrid": 45}.get(decision.mode, 3650)

    return {
        "needs_research": decision.needs_research,
        "mode": decision.mode,
        "queries": decision.queries or [],
        "recency_days": recency_days,
    }


def execute_research(state: State, active_llm: Any, keys_to_scrub: Optional[list[str]] = None) -> dict:
    """Fetch web evidence and synthesise it into a deduplicated EvidenceItem list."""
    # Cap queries to top 4 to stay well within Groq TPM limits and prevent redundant web searches
    queries = (state.get("queries", []) or [])[:4]
    max_results = 3

    raw_results: List[dict] = []
    for q in queries:
        raw_results.extend(_tavily_search(q, max_results=max_results))

    if not raw_results:
        return {"evidence": []}

    # Deduplicate raw results by URL before synthesis and cap at 10 items
    seen_urls = set()
    unique_raw_results: List[dict] = []
    for r in raw_results:
        u = r.get("url")
        if u and u not in seen_urls:
            seen_urls.add(u)
            unique_raw_results.append(r)
    unique_raw_results = unique_raw_results[:10]

    # Format concisely for the prompt to keep prompt tokens under ~1500
    raw_results_text = "\n\n".join(
        f"[{i+1}] Title: {r.get('title', '')}\n"
        f"URL: {r.get('url', '')}\n"
        f"Date: {r.get('published_at') or 'Unknown'}\n"
        f"Snippet: {r.get('snippet', '')}"
        for i, r in enumerate(unique_raw_results)
    )

    messages = [
        SystemMessage(content=RESEARCH_SYSTEM),
        HumanMessage(
            content=(
                f"As-of date: {state['as_of']}\n"
                f"Recency days: {state['recency_days']}\n\n"
                f"Raw search results:\n{raw_results_text}"
            )
        ),
    ]

    @retry_on_rate_limit(max_retries=3, initial_backoff=2.0)
    def _invoke():
        return invoke_structured(
            active_llm,
            EvidencePack,
            messages,
            method="json_mode",
            keys_to_scrub=keys_to_scrub,
        )

    pack = _invoke()

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


def execute_orchestrator(state: State, active_llm: Any, keys_to_scrub: Optional[list[str]] = None) -> dict:
    """Generate a structured outline (Plan) for the blog post."""
    evidence = state.get("evidence", [])
    mode = state.get("mode", "closed_book")

    # User-controlled parameters injected into the prompt
    tone = state.get("tone", "professional")
    style = state.get("style", "blog")
    audience = state.get("audience", "developers")
    length = state.get("length", "medium")
    forced_kind = "news_roundup" if mode == "open_book" else None

    messages = [
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

    @retry_on_rate_limit(max_retries=3, initial_backoff=2.0)
    def _invoke():
        return invoke_structured(active_llm, Plan, messages, keys_to_scrub=keys_to_scrub)

    plan = _invoke()

    # Hard-set blog_kind for news roundup mode
    if forced_kind:
        plan.blog_kind = "news_roundup"

    # Override planner's inferred tone/audience with user's explicit choices
    plan.tone = tone
    plan.audience = audience

    return {"plan": plan}


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


def execute_worker(payload: dict, active_llm: Any, worker_semaphore: threading.Semaphore) -> dict:
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

    messages = [
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

    @retry_on_rate_limit(max_retries=5, initial_backoff=2.0)
    def _invoke():
        with worker_semaphore:
            return active_llm.invoke(messages)

    response = _invoke()

    section_md = _extract_text(response.content)
    # Return as (task_id, markdown) tuple so reducer can sort by id
    return {"sections": [(task.id, section_md)]}


def execute_reducer(state: State) -> dict:
    """Merge all parallel sections into the final ordered Markdown blog post."""
    plan = state["plan"]
    if plan is None:
        raise ValueError("reducer_node called before a plan was produced.")

    ordered = [md for _, md in sorted(state["sections"], key=lambda x: x[0])]
    body = "\n\n".join(ordered).strip()
    final_md = f"# {plan.blog_title}\n\n{body}\n"

    return {"final": final_md}


# ═══════════════════════════════════════════════════════════════════════════
# Dynamic Graph Builder (closures capture LLM and semaphore; zero secrets in state)
# ═══════════════════════════════════════════════════════════════════════════

def _build_workflow(
    active_llm: Any,
    worker_semaphore: threading.Semaphore,
    keys_to_scrub: Optional[list[str]] = None,
):
    def _router(state: State) -> dict:
        update_job(state["job_id"], status="running", stage="routing", progress=10)
        return execute_router(state, active_llm, keys_to_scrub)

    def _research(state: State) -> dict:
        update_job(state["job_id"], stage="researching", progress=25)
        return execute_research(state, active_llm, keys_to_scrub)

    def _orchestrator(state: State) -> dict:
        update_job(state["job_id"], stage="planning", progress=50)
        return execute_orchestrator(state, active_llm, keys_to_scrub)

    def _worker(payload: dict) -> dict:
        update_job(payload["job_id"], stage="writing", progress=65)
        return execute_worker(payload, active_llm, worker_semaphore)

    def _reducer(state: State) -> dict:
        update_job(state["job_id"], stage="finalizing", progress=90)
        return execute_reducer(state)

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


# Legacy wrappers and default module-level graph
def router_node(state: State) -> dict:
    return execute_router(state, llm)


def research_node(state: State) -> dict:
    return execute_research(state, llm)


def orchestator_node(state: State) -> dict:
    return execute_orchestrator(state, llm)


def worker_node(payload: dict) -> dict:
    return execute_worker(payload, llm, _WORKER_SEMAPHORE)


def reducer_node(state: State) -> dict:
    return execute_reducer(state)


def _build_graph():
    return _build_workflow(llm, _WORKER_SEMAPHORE)


_compiled_graph = _build_graph()


# ═══════════════════════════════════════════════════════════════════════════
# Public entry point
# ═══════════════════════════════════════════════════════════════════════════

def generate_blog(
    job_id: str,
    topic: str,
    tone: str = "professional",
    length: str = "medium",
    style: str = "blog",
    audience: str = "developers",
    use_web: bool = True,
    as_of: Optional[str] = None,
    llm_selection: Optional[LLMSelection] = None,
) -> None:
    """
    Run the full blog-generation pipeline.

    Invokes the dynamically compiled LangGraph graph with the given parameters and LLM selection,
    updates the job store at each stage, and stores the final result (or scrubbed error) when complete.
    """
    if as_of is None:
        as_of = date.today().isoformat()

    raw_key = (
        llm_selection.api_key.get_secret_value()
        if (llm_selection and llm_selection.api_key)
        else None
    )
    keys_to_scrub = [raw_key] if raw_key else []

    try:
        provider = (llm_selection.provider or "groq").strip().lower() if llm_selection else "groq"
        provider_cfg = PROVIDER_REGISTRY.get(provider, PROVIDER_REGISTRY["groq"])
        concurrency = provider_cfg["profile"].get("worker_concurrency", 3)
        worker_semaphore = threading.Semaphore(concurrency)

        active_llm = get_llm("blog", llm_selection)
        graph = _build_workflow(active_llm, worker_semaphore, keys_to_scrub=keys_to_scrub)

        out = graph.invoke(
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
        scrubbed = scrub_exception_chain(exc, keys=keys_to_scrub)
        logger.error("Blog generation failed for job %s: %s", job_id, scrubbed)
        update_job(job_id, status="error", stage="error", error=scrubbed)
        raise RuntimeError(scrubbed) from None
