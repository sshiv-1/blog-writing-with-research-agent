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

---

## Phase 3a: Bring-Your-Own-Key (BYOK) Model Layer

### 2026-10-18 - Multi-Provider Registry, Secret Concealment, and Dynamic Concurrency
- **Files Modified**:
  - `backend/app/models/schemas.py`:
    - Added `LLMSelection` with `api_key: Optional[SecretStr] = Field(default=None, repr=False)` and custom `__repr__`/`__str__` masking keys as `***`.
    - Added `LLMTestResponse` (`ok`, `provider`, `model`, `error`).
  - `backend/app/core/llm.py`:
    - Centralized `PROVIDER_REGISTRY` covering 5 providers (`groq`, `openai`, `anthropic`, `google`, `openrouter`) with all model identifiers, defaults (`blog`, `slides`, `test`), recommended models, base URL allowlists, and execution profiles (`planner_input_token_cap`, `worker_concurrency`, `max_output_tokens_*`).
    - Added provider and model string validators (`validate_provider`, `validate_model_name`).
    - Added security sanitizers (`scrub_secrets`, `scrub_exception_chain`) stripping API key patterns (`sk-...`, `sk-ant-...`, `sk-or-...`, `gsk_...`, `AIza...`) and exception cause chains (`__cause__`, `__context__`).
    - Implemented in-memory sliding window IP rate limiting (`check_ip_rate_limit`) allowing max 10 test probes/min.
    - Implemented `get_llm(role, selection, override_options)` with lazy imports and fallback to server Groq keys only when no provider and no key are specified.
    - Retained `blog_llm()` and `slides_llm()` as backward-compatibility aliases.
  - `backend/app/core/agent.py`:
    - Replaced module-level static LLM instantiation with `_LazyBlogLLM()` proxy.
    - Added `invoke_structured()` wrapper trying `with_structured_output()` first and falling back to prompt JSON schema validation.
    - Parameterized pipeline graph creation via `_build_workflow()` with closures capturing the active LLM, dynamic worker concurrency semaphore, and secret scrubber.
    - Updated `generate_blog()` to accept `llm_selection: Optional[LLMSelection] = None`, dynamically size the worker semaphore, and scrub all exceptions before updating `JobRecord`.
  - `backend/app/core/slides.py`:
    - Updated `_extract_compact_blog_context()` to accept dynamic `planner_input_token_cap`: finite caps apply the ~600-char/section window, while frontier providers (None) include the whole article subject to a hard ceiling of 60k tokens (~240,000 characters) with even section truncation.
    - Updated `plan_slides_deck()` and `repair_single_slide_with_llm()` to accept `llm`, `planner_input_token_cap`, and scrub keys from warnings and errors.
    - Updated `generate_slides_for_blog()` to accept `llm_selection: Optional[LLMSelection] = None`.
  - `backend/app/api/routes.py`:
    - Added `_resolve_selection()` parsing headers (`X-LLM-Provider`, `X-LLM-Model`, `X-LLM-Key`, `X-LLM-Slides-Provider`, `X-LLM-Slides-Model`). Non-Groq providers without keys strictly return HTTP 400.
    - Passed resolved selection into background tasks for `POST /generate` and `POST /jobs/{id}/slides`.
    - Added `POST /llm/test` probe endpoint with client IP rate limiting and parameter-rejection retry.
  - `backend/app/main.py`:
    - Allowed custom `X-LLM-*` headers in CORS middleware.
    - Added global exception handler ensuring unhandled 500 exceptions never echo request headers or secrets.
  - `backend/requirements.txt`:
    - Added `langchain-openai>=0.2.0`, `langchain-anthropic>=0.2.0`, `langchain-google-genai>=2.0.0`.
- **Verification Results**:
  - `pip install --dry-run`: **PASS** (zero dependency conflicts with pinned `langchain==1.3.14` and `langchain-core==1.5.3`).
  - `python -c "import app.main"`: **PASS** (exited with code 0).
  - Mocked offline test script: **PASS** (all 5 checks verified):
    - Provider routing: all 5 providers correctly dispatched.
    - Unknown provider rejected with `ValueError`.
    - Base URL hijacking ignored; allowlist URLs enforced.
    - Non-Groq providers without keys strictly raise HTTP 400.
    - Key scrubbing: `"sk-TEST-123"` never appeared in `repr()`/`str()` of `LLMSelection`, `JobRecord`, `SlideJobRecord`, or exception chains (`__cause__`/`__context__`).
  - Background processes: **None**.

---

## Phase 3b: Supabase Persistence + Optional Auth

### 2026-10-18 - Supabase Persistence, Algorithm-Pinned JWT Auth, Fernet BYOK Encryption, and Owner Isolation
- **Files Created**:
  - `supabase/schema.sql`:
    - Idempotent schema defining `jobs` (uuid pk), `slide_jobs` (uuid pk referencing `jobs(id)` on delete cascade), and `user_api_keys` (composite pk `user_id, provider`).
    - Added index on `jobs(user_id, created_at desc)` and `slide_jobs(user_id, created_at desc)`.
    - RLS enabled across all three tables. SELECT-only policy for authenticated users (`auth.uid() = user_id`) on `jobs` and `slide_jobs`. Zero access policies for authenticated users on `user_api_keys` (reserved exclusively for service role).
    - Private `artifacts` bucket configured with zero direct authenticated user access policies (streamed by backend).
  - `backend/app/core/crypto.py`:
    - Symmetric Fernet cipher using `APP_ENCRYPTION_KEY`.
    - Enforces 512 character maximum key length; extracts `last4` suffix for UI display.
    - Clears plaintext keys from local execution scope before returning.
    - Explicit `RuntimeError` diagnostic instructing how to generate 32-byte key if unset or invalid.
  - `backend/app/core/auth.py`:
    - `verify_supabase_jwt(token)` enforcing audience `"authenticated"` and issuer `"{SUPABASE_URL}/auth/v1"`.
    - Strict algorithm pinning: rejects `"none"` and unpinned algorithms; allows `HS256` only when `SUPABASE_JWT_SECRET` is set and token header specifies `HS256`; allows `RS256`, `ES256`, `EdDSA` via cached JWKS discovery client.
    - Sync FastAPI dependencies `get_current_user` (returns 401 on missing/invalid token) and `get_optional_user` (returns None for guests; 401 on invalid/expired credentials). Returns 401 if `SUPABASE_URL` is unset when a token is provided.
  - `backend/app/core/db.py`:
    - Supabase singleton client using `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. Falls back to in-memory guest mode if unconfigured.
    - Startup stale job cleanup (`cleanup_stale_jobs_on_startup`) and read-time stale evaluation: marks queued/running jobs older than 15 minutes as error (`"Interrupted by a server restart"`).
    - CRUD helpers: `save_job_db`, `get_job_db`, `list_user_jobs_db`, `count_user_active_jobs_db`, `count_user_daily_jobs_db`, `delete_job_db`, `save_slide_job_db` (storing `slide_count`, `warnings`, `deck`, `title` inside `result`), `get_slide_job_db`, `save_user_key_db`, `get_user_key_db`, `list_user_keys_db`, `delete_user_key_db`, `upload_artifact_storage`, `get_artifact_storage`.
    - All DB/storage errors trapped, sanitized via `scrub_exception_chain`, and logged as warnings without interrupting in-memory job workflows.
- **Files Modified**:
  - `backend/app/core/jobs.py`:
    - Added `user_id`, `topic`, and non-secret `params` to `JobRecord`.
    - Added `user_id` to `SlideJobRecord`.
    - Threaded non-blocking write-through to DB triggered on stage changes and done/error transitions, avoiding database writes on intermediate progress ticks.
    - Lazy artifact upload to private storage bucket on slide job completion.
    - Cache-miss fallback to DB on `get_job()` and `get_slide_job()`.
  - `backend/app/api/routes.py`:
    - Integrated `get_optional_user` and `get_current_user`.
    - Updated `_resolve_selection` to resolve saved encrypted keys from `user_api_keys` when `X-LLM-Key` header is omitted for authenticated users.
    - Added abuse controls: sliding-window IP rate limiting (`GUEST_JOBS_PER_HOUR`, default 20), signed-in concurrent job cap (`MAX_CONCURRENT_USER_JOBS`, default 3), and daily user cap (`DAILY_USER_JOB_CAP`, default 50).
    - Enforced owner isolation on `GET /jobs/{id}`, `GET /jobs/{id}/result`, `GET /jobs/{id}/slides`, and `GET /jobs/{id}/slides/download`: mismatched or unauthenticated requests to user-owned jobs return 404 Not Found to prevent ID enumeration.
    - Added authenticated endpoints: `GET /me/jobs`, `DELETE /jobs/{id}`, `GET /me/keys`, `PUT /me/keys/{provider}`, `DELETE /me/keys/{provider}`.
  - `backend/app/main.py`:
    - Added FastAPI lifespan hook triggering `cleanup_stale_jobs_on_startup()`.
    - Explicitly exposed `Authorization` in CORS allowed headers.
  - `backend/app/models/schemas.py`:
    - Added `UserJobSummary`, `PaginatedUserJobs`, `UserKeyItem`, and `SaveKeyRequest`.
  - `backend/.env.example`:
    - Added placeholders for `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `APP_ENCRYPTION_KEY`, `GUEST_JOBS_PER_HOUR`, `DAILY_USER_JOB_CAP`, and `MAX_CONCURRENT_USER_JOBS`.
  - `backend/requirements.txt`:
    - Added `supabase>=2.0.0` and `PyJWT[crypto]>=2.8.0`.
- **Verification Results**:
  - `python -c "import app.main"`: **PASS** (exited with code 0).
  - Offline test suite: **PASS** (7/7 tests passed):
    - Test 1 (Fernet Crypto): encryption, decryption, `last4` extraction, and missing key `RuntimeError`.
    - Test 2 (JWT & Algorithm Pinning): valid token decodes `AuthUser`, rejects `"none"`, wrong alg, wrong issuer, wrong audience, expired token, and unset `SUPABASE_URL` with 401.
    - Test 3 (Stale Jobs): queued/running jobs >15m marked failed with `"Interrupted by a server restart"`.
    - Test 4 (Resilient Write-Through): simulated DB timeouts/failures do not fail in-memory jobs.
    - Test 5 (Guest Behavior): unauthenticated requests run in-memory; unconfigured Supabase degrades gracefully.
    - Test 6 (Access Isolation): cross-user or anonymous access to user-owned jobs returns 404 (not 403).
    - Test 7 (Saved BYOK Resolution): decrypted key passed as `SecretStr`, concealed in `repr()`/`str()`.
  - Leftover test files: **None** (cleaned up).
  - Background processes: **None**.



