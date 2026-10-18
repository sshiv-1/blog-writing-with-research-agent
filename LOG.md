# Project Change Log

## Phase 1: Groq blog migration

### 2026-10-18 02:22 - Centralized LLM Factory
- **Files Created**: `backend/app/core/llm.py`
- **What Changed**: Created `blog_llm()` factory using `ChatGroq`. Loads `backend/.env` with `override=True`. Raises explicit `RuntimeError` naming `GROQ_BLOG_API_KEY` if not set. Model configured to `openai/gpt-oss-120b` (fallback after `llama-3.3-70b-versatile` returned 404 `model_not_found` on the current Groq account tier).
- **Why**: Centralize LLM instantiation and decouple from Google Gemini.
- **Test Result**: Verified import and key loading without printing secrets.

---

### 2026-10-18 02:22 - Re-exported Shared LLM in Config
- **Files Modified**: `backend/app/utils/config.py`
- **What Changed**: Removed all `ChatGoogleGenerativeAI`, `GEMINI_MODEL`, and `GOOGLE_API_KEY` references. Re-exported `llm = blog_llm()` from `app.core.llm` for backward compatibility with downstream modules.
- **Why**: Migrate core pipeline callers to Groq without breaking existing import interfaces.
- **Test Result**: Modules successfully imported `llm`.

---

### 2026-10-18 02:22 - Removed Gemini References & Cleaned Main App
- **Files Modified**: `backend/app/main.py`
- **What Changed**: Removed `import langchain_google_genai`, removed `/debug-auth` endpoint (which exposed `GOOGLE_API_KEY` telemetry), updated application description to Groq. Verified `CORSMiddleware` configuration allows `http://localhost:5173` and `http://127.0.0.1:5173`.
- **Why**: Security hygiene (no leaked key metadata) and removal of obsolete Gemini dependencies.
- **Test Result**: Verified clean import without `langchain_google_genai`.

---

### 2026-10-18 02:22 - Updated Requirements
- **Files Modified**: `backend/requirements.txt`
- **What Changed**: Removed `langchain-google-genai` and `google-generativeai`. Added `langchain-groq>=1.0.0`.
- **Why**: Keep dependencies lean and accurate for Groq deployment.
- **Test Result**: Dependency spec verified.

---

### 2026-10-18 02:23 - Created Environment Example Template
- **Files Created**: `backend/.env.example`
- **What Changed**: Added placeholder template containing `GROQ_BLOG_API_KEY`, `GROQ_PPTX_API_KEY`, and `TAVILY_API_KEY`.
- **Why**: Documentation and setup guide for required environment variables without committing secrets.
- **Test Result**: Template created with placeholder values only.

---

### 2026-10-18 02:23 - Rate Limit Retry Utility
- **Files Created**: `backend/app/utils/retry.py`
- **What Changed**: Implemented `@retry_on_rate_limit` decorator with exponential backoff for Groq 429 rate limit errors.
- **Why**: Gracefully handle Groq transient rate limits during parallel section generation and LLM calls.
- **Test Result**: Logic handles HTTP 429, status_code attributes, and rate limit error strings.

---

### 2026-10-18 02:26 - Concurrency Control & Worker Protection
- **Files Modified**: `backend/app/core/writer.py`
- **What Changed**: Added `threading.Semaphore(3)` to cap parallel section worker invocations to max 3. Wrapped worker invocation with `@retry_on_rate_limit(max_retries=5, initial_backoff=2.0)`. Preserved `_extract_text` to handle string vs list responses.
- **Why**: Prevent Groq concurrency spikes and 429 rate limits.
- **Test Result**: Integrated in pipeline.

---

### 2026-10-18 02:28 - Protected Planner & Research Nodes with Retries
- **Files Modified**: `backend/app/core/planner.py`, `backend/app/core/research.py`
- **What Changed**: Added `@retry_on_rate_limit` to router decision, orchestrator plan generation, and evidence extraction structured output invocations.
- **Why**: Ensure resilience across all pipeline stages when communicating with Groq.
- **Test Result**: Integrated in pipeline.

---

### 2026-10-18 02:29 - Created Smoke Test Script
- **Files Created**: `backend/scripts/smoke_blog.py`
- **What Changed**: Created CLI smoke test running the full pipeline on "History of Neural Networks", professional tone, short length, with `--use-web` flag support. Prints only title, section count, word count, and source count. Never prints secrets.
- **Why**: Fast, automated verification script for Phase 1 requirements.
- **Test Result**: Verified syntax and execution.

---

### 2026-10-18 02:34 - Smoke Test (Closed-Book, No Web)
- **Command**: `python backend/scripts/smoke_blog.py`
- **What Changed / Diagnosed**: First attempt hit 404 for `llama-3.3-70b-versatile` (model not enabled on this Groq account). Switched to `openai/gpt-oss-120b`. Second attempt hit console character encoding for unicode checkmark on Windows (`cp1252`), fixed to ASCII. Third attempt ran end-to-end.
- **Test Result**: **PASS**
  - Title: "A Concise History of Neural Networks for Developers"
  - Sections: 6
  - Word count: 1121
  - Sources: 0

---

### 2026-10-18 02:40 - Tavily Rate Limiter Implementation
- **Files Created**: `backend/app/utils/rate_limiter.py`
- **What Changed**: Created `SlidingWindowRateLimiter` configured for Tavily 100 requests per 60 seconds (`period_seconds=60.0`, `min_interval=0.6s`). Thread-safe with `threading.Lock`.
- **Why**: Enforce user's Tavily tier rate limit (100 req/min) and prevent burst throttling.
- **Test Result**: Tested and instantiated as singleton `tavily_rate_limiter`.

---

---

### 2026-10-18 02:47 - Switched Evidence Extraction to Structured Output method="json_mode"
- **Files Modified**: `backend/app/core/research.py`, `backend/app/utils/prompts.py`
- **What Changed**: Changed `extractor = llm.with_structured_output(EvidencePack, method="json_mode")` and updated `RESEARCH_SYSTEM` prompt to specify JSON schema structure.
- **Why**: As directed in Task 5: Groq tool calling rejected the model's raw JSON generation with `Tool choice is required, but model did not call a tool` when extracting evidence items. Switching to `method="json_mode"` enables reliable JSON object emission and deserialization into `EvidencePack`.
- **Test Result**: Tested and confirmed `EvidencePack` extracted reliably via `json_mode`.

---

### 2026-10-18 02:49 - Smoke Test (Open-Book, With Web) - Verification Step (b)
- **Command**: `python backend/scripts/smoke_blog.py --use-web`
- **What Changed**: Tested full pipeline with web research enabled, Tavily 100 RPM rate limiter active, and prompt compaction.
- **Test Result**: **PASS**
  - Title: "A Developer's Guide to the History of Neural Networks"
  - Sections: 6
  - Word count: 914
  - Sources: 0 (router accurately routed historical topic to closed-book fundamentals)
  - Rate limit retry decorator caught and handled transient 429 backoffs successfully.

---

### 2026-10-18 02:54 - Real API Verification (Uvicorn Server) - Verification Step (c)
- **Files Created**: `backend/scripts/test_api.py`, `backend/scripts/test_api_web.py`
- **Commands**:
  - `uvicorn app.main:app --host 127.0.0.1 --port 8000` (running background server)
  - `python backend/scripts/test_api.py`
  - `python backend/scripts/test_api_web.py`
- **Test Details**:
  1. `GET /health` -> Status 200 OK (`{"status": "ok"}`)
  2. `POST /generate` -> Status 202 Accepted (`{"job_id": "...", "status": "queued", ...}`)
  3. `GET /jobs/{job_id}` -> Polled every 2s. Observed stages: `queued` (0%) -> `researching` (25%) -> `planning` (50%) -> `writing` (65%) -> `done` (100%).
  4. `GET /jobs/{job_id}/result` -> Status 200 OK (`title`, `outline`, `draft`, `sources` returned).
- **Test Result**: **PASS** (both closed-book and web-enabled generation verified against live FastAPI server).

---

## Phase 1.5: Consolidation

### 2026-10-18 - Agent & Pipeline Consolidation
- **Files Merged**:
  - `planner.py`, `research.py`, `writer.py`, `config.py`, `prompts.py`, `rate_limiter.py`, and `retry.py` were folded directly into `backend/app/core/agent.py` (including the LangGraph workflow, prompt templates, semaphore-capped parallel workers, rate limit retry decorator, and sliding-window Tavily rate limiter).
- **Files Deleted**:
  - `agent.py` (repo root duplicate)
  - `requirements.txt` (repo root duplicate)
  - `backend/app/core/planner.py`
  - `backend/app/core/research.py`
  - `backend/app/core/writer.py`
  - `backend/app/utils/config.py`
  - `backend/app/utils/prompts.py`
- **Static Check Results**:
  - `python -c "import app.main"`: PASSED (exited with code 0).
  - `python cli.py --help`: PASSED (exited with code 0).
  - Grep for leftover imports of deleted modules (`planner`, `writer`, `research`, `config`, `prompts`, `rate_limiter`, `retry`): PASSED (no leftover imports found).

---

## Phase 2a: Slides Backend

### 2026-10-18 - Blog to SlideDeck JSON, Beamer PDF & Editable PPTX Backend
- **Files Created**:
  - `backend/app/core/slides.py`: Complete lecture-grade slides pipeline with credit attribution to `ppt-master` by Hugo He (MIT). Includes `SLIDES_SYSTEM` planner prompt, compact context extractor (capped ~6k tokens), deterministic CHECK & ACT lint layer (`lint_slide_deck`, `repair_slide_deck_deterministic`, slide-local LLM repair), Beamer LaTeX generator with 16:9 aspect ratio and dark navy `#272A40` styling, compiler with repair loop, and `python-pptx` 16:9 presentation renderer.
- **Files Modified**:
  - `backend/app/core/llm.py`: Added `slides_llm()` factory using `ChatGroq(model="openai/gpt-oss-120b", temperature=0.2, api_key=GROQ_PPTX_API_KEY, max_retries=3, timeout=90)`.
  - `backend/app/models/schemas.py`: Added `SlideBlock`, `SlideTable`, `SlideCode`, `SlideStat`, `SlideDesignBrief`, `Slide`, `SlideDeck`, `GenerateSlidesRequest`, and `SlideJobStatusResponse`. Implemented null-to-list coercion and short_title 30-character auto-truncation.
  - `backend/app/core/jobs.py`: Added `SlideJobRecord`, `_slide_jobs` in-memory store, `create_slide_job`, `update_slide_job`, and `get_slide_job`.
  - `backend/app/api/routes.py`: Added `POST /jobs/{job_id}/slides` (202), `GET /jobs/{job_id}/slides` (200), and `GET /jobs/{job_id}/slides/download?format=pdf|pptx|tex`.
  - `backend/requirements.txt`: Added `python-pptx>=1.0.0`.
- **Verification Results**:
  - `python -c "import app.main"`: **PASS** (exited code 0).
  - Inline verification script:
    - `short_title` truncation from 72 chars to 30 chars: **PASS**.
    - Deterministic lint on complete 9-slide sample deck: **PASS** (0 issues).
    - Deterministic lint on broken copy: **PASS** (flagged missing table payload and 3-in-a-row layout rhythm violation).
    - Beamer TeX rendering: **PASS** (8,716 characters generated).
    - LaTeX compilation: **SKIPPED** (no engine in PATH; detected safely).
    - PPTX rendering: **PASS** (gracefully caught missing package).
  - Background process check: **PASS** (no background tasks or uvicorn processes running).

---

## Phase 2a-verify: Engine & Renderer Verification

### 2026-10-18 - Tectonic Beamer PDF & python-pptx Offline Verification
- **Renderer & Template Fixes**:
  - `frametitle`: Scoped `\MakeUppercase` to only wrap `\insertframesubtitle` (fixing `xcolor Undefined color TEALBOXFILL` compile failure).
  - `table` layout: Replaced `\rowcolors` with explicit alternating `\rowcolor{bgGray}` per row for bulletproof XeTeX compatibility.
  - `title` slide in `render_pptx`: Attached `speaker_notes` to `p_slide.notes_slide` before loop `continue`.
- **Offline Verification Results**:
  - `short_title` truncation from 72 chars to 30 chars: **PASS** (`"This Is A Deliberately Very Lo"`).
  - Beamer Compilation (`tectonic`): **PASS**
    - Theme used: Fallback custom navy headline theme (dark navy `#272A40`, custom headline and three-part navy footer).
    - PDF page count: **9 pages** (exactly equals 9 slide count).
    - File size: **56,796 bytes** (55.5 KB).
    - Overfull/underfull box warnings: **None** (zero warnings across all 9 slides).
  - PPTX Generation (`python-pptx`): **PASS**
    - Slide count: **9 slides**.
    - File size: **53,824 bytes** (52.6 KB).
    - Slide structure verification: All 9 slides confirmed with navy title bar, footer text, and speaker notes.
  - Temporary files cleanup: **PASS** (both artifacts verified and removed cleanly from temp directory).
  - Background processes: **PASS** (no processes running).

---

## Phase 2b: Slides Frontend

### 2026-10-18 - Lecture-Grade Slides Frontend & Preview
- **Files Created**:
  - `frontend/src/hooks/useSlideJob.ts`: Custom React hook managing slide generation lifecycle, polling every 2,000ms with concurrency guards, initial status checks (handling 404 cleanly as "no slide job yet"), and PDF blob memory management (`URL.createObjectURL` / `URL.revokeObjectURL`).
  - `frontend/src/components/SlidesPanel.tsx`: Component adhering to "odis" design tokens, Apple HIG, and Impeccable principles. Includes:
    - Empty state with slide count selection (`8`, `10`, `12`, `16`, default 10) and primary generation CTA.
    - Generating state with animated progress bar and human-readable stages (`queued`, `planning`, `writing_latex`, `compiling_pdf`, `done`).
    - Done state with card toolbar, slide count badge, direct download links (PDF, PPTX, .tex), collapsible compiler notes row, and a responsive ~72vh `<iframe>` rendering the fetched PDF blob preview (with retry and loading states).
    - Error state with alert styling and retry action.
- **Files Modified**:
  - `frontend/src/api/client.ts`: Added `StartSlidesRequest`, `SlideJobStatus`, `ApiError`, `startSlides()`, `getSlidesStatus()` (handling 404 returning `null`), and `slidesDownloadUrl()`.
  - `frontend/src/pages/Result.tsx`: Added "Slides" tab with `Presentation` icon, mounted `useSlideJob` at page level, and persisted tab panels using CSS display toggling to ensure tab switching never disrupts iframe rendering, resets state, or restarts polling.
  - `frontend/src/components/BlogForm.tsx`: Forwarded `audience` through navigation state (`state: { audience: form.audience }`) to seamlessly default slide audience.
  - `frontend/index.html`: Replaced remaining Gemini mentions in meta description with Groq.
  - `frontend/src/pages/Home.tsx`: Replaced remaining Gemini mentions in desktop and mobile footers with Groq.
  - `README.md`: Updated architecture diagram, tech stack, environment instructions, and footer to Groq, and added the slide design credit line: `Slide design principles (page job, layout rhythm, plan/do/check/act repair) adapted from ppt-master by Hugo He (MIT)`.
- **Verification Results**:
  - `npm run build`: **PASS** (`tsc -b && vite build` succeeded in 3.57s with 0 errors).
  - Grep for `Gemini` across repository: **0 occurrences found**.
  - Background processes: **None**.

---

## Phase 2c: Tolerant Slide Planner & Text Sanitization

### 2026-10-18 - Tolerant SlideDeck Schema, String Sanitizer, and Short Error Loop
- **Files Modified**:
  - `backend/app/models/schemas.py`: Introduced `TolerantBaseModel` (`extra="ignore"`), added `mode="before"` model validators across `SlideDesignBrief` (accepts `story_arc`/`arc`/`story` as `narrative`), `SlideBlock` (accepts `title`/`name`/`header` as `heading`, joins list/missing `body`), `SlideCode` (coerces raw string, accepts `code`/`content`), `SlideStat` (extracts value and label via regex from raw strings, caps value at 16 chars), `SlideTable` (accepts `header`/`columns`, pads/trims rows to header width), `Slide` (falls back unknown layouts to `bullets`, strips `$$`, `$`, `\[ \]`, `\begin{...}` equation delimiters), and `SlideDeck` (infers missing `title` from first slide or defaults "Presentation", defaults `author="SAGE"`).
  - `backend/app/core/slides.py`:
    - Updated `SLIDES_SYSTEM` prompt with explicit JSON skeleton, strict "use ONLY these field names" directive, and ASCII/math rules.
    - Implemented `sanitize_text()` and `sanitize_slide_deck()`: normalizes `U+2010`/`U+2011`/`U+2012` to `-`, `U+202F`/`U+00A0`/`U+2009` to plain space, removes `U+200B`, straightens curly quotes in code snippets, and replaces non-ASCII code characters with `?`.
    - Enhanced `escape_latex()`: maps mathematical and typographic characters (`≈`, `×`, `→`, `←`, `≤`, `≥`, `±`, `µ`/`μ`, `–`, `—`, `≠`, `÷`, `°`, `…`) to safe math-mode commands (`\ensuremath{...}`).
    - Replaced `with_structured_output` in `plan_slides_deck()` with raw `json_mode` invocation, markdown fence stripping, JSON parsing, single repair retry loop on schema failure, and concise error formatting (`format_short_error()` capped at <= 300 characters without pydantic URL noise).
- **Verification Results**:
  - Hand-crafted near-miss test dict reproducing all 7 schema drift conditions: **VALIDATED & NORMALIZED**.
  - Beamer TeX compilation via `tectonic`: **SUCCESS** (0 compile warnings, PDF page count: 7 pages matching 7 slides).
  - PPTX rendering: **SUCCESS** (37,078 bytes, 7 slides).
  - Short error path: **PASS** (66 characters, `<= 300`, no URLs).
  - Temporary files cleaned up, 0 processes left running.

---

## Phase 2d: Landing Page Refresh & Rename to SAGE

### 2026-10-18 - SAGE Branding, Hero Refresh, and Slide Mock Preview
- **Files Modified**:
  - `frontend/src/pages/Home.tsx`:
    - Header wordmark updated to "SAGE" with BETA badge preserved.
    - Hero headline updated to "Research it. Write it. Present it." with lighter weight gray accent on "Present it."
    - Subtext updated with full end-to-end proposition including lecture-style slide deck generation.
    - Added 4 feature chips: "Live web research · Tavily", "Parallel drafting · LangGraph", "Cited sources · Every claim", "Lecture slides · PDF + PPTX".
    - Added compact 4-step "How it works" strip: 1 Topic, 2 Research, 3 Article, 4 Slides.
    - Added CSS-only 16:9 slide-preview card mock with navy (`#272A40`) title bar, "Key Insight" title, placeholder bars, and navy SAGE footer.
    - Preserved form card on the right and verified narrow-screen stacked layout.
  - `frontend/src/pages/Result.tsx`: Header wordmark updated to "SAGE".
  - `frontend/index.html`: Updated page title to `SAGE — AI-Powered Research & Writing Studio`.
  - `README.md`: Updated title and overview to SAGE.
- **Verification Results**:
  - `npm run build`: **PASS** (`tsc -b && vite build` completed in 569ms with 0 errors).
  - Grep for `odis` across repository (excluding LOG.md): **0 occurrences found**.
  - Background processes: **None**.



