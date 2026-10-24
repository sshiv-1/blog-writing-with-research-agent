# SAGE — Autonomous Research, Writing & Presentation Studio
### Complete Application Architecture, Feature Guide & Technology Stack

> **Tagline**: *Research it. Write it. Present it.*  
> **Classification**: Production-grade Multi-Agent Full-Stack Application  
> **Status**: Version 1 (v1) Production-Ready

---

## 1. Executive Summary

**SAGE** is an autonomous full-stack AI research and presentation studio. Unlike standard conversational AI wrappers or single-prompt text generators, SAGE decomposes high-complexity intellectual work into specialized, autonomous agent nodes orchestrated by **LangGraph**.

Given a simple topic and configuration (tone, target audience, format style, length, and web research toggle), SAGE:
1. Formulates search strategies and conducts live web research using **Tavily**.
2. Synthesizes and deduplicates findings into structured evidence packs.
3. Plans an extensive multi-section article with individualized section goals and word count targets.
4. Fans out parallel worker agents to draft each section concurrently under strict rate limiting.
5. Assembles a cohesive, citation-backed Markdown publication with source attribution.
6. Automatically transforms the resulting research into a lecture-grade presentation deck, compiling both a pixel-perfect **Beamer LaTeX PDF** and an editable **16:9 widescreen PPTX presentation**.
7. Provides a complete **Bring-Your-Own-Key (BYOK)** model layer across 5 major AI providers (Groq, OpenAI, Anthropic, Google Gemini, OpenRouter), backed by optional **Supabase Authentication**, client-side Fernet encryption, and persistent job history.

---

## 2. Key Features & Capabilities

### 🔍 Autonomous Multi-Agent Research & Writing Pipeline
- **Intelligent Topic Routing**: Evaluates whether a prompt requires live current events, technical domain lookups, or timeless conceptual foundations (`open_book`, `hybrid`, `closed_book`).
- **Live Search & Evidence Synthesis**: Uses Tavily API to extract high-signal domain evidence, deduplicates URLs, filters by recency, and condenses findings into a structured `EvidencePack`.
- **Hierarchical Outline Planning**: Decomposes the article into structured sections with clear narrative trajectories, assigned word budgets, and research requirements.
- **Concurrent Section Drafting**: Dispatches worker nodes in parallel with concurrency semaphore controls (3 concurrent workers on Groq; 5 on frontier providers) and automated exponential backoff on rate limits.
- **Deterministic Reducer**: Reassembles independently generated sections, normalizes Markdown heading levels, and appends formatted citation sources.

### 📊 Lecture-Grade Slide Deck Generation
- **Page-Job Driven Layouts**: Every slide is assigned a strict functional goal (e.g. *“demonstrate why X costs more than Y”*). Layouts adapt dynamically to the job:
  - `title`: Header slide with subtitle and author wordmark.
  - `agenda`: Structured presentation roadmap.
  - `bullets`: Dense 3–5 bullet claims (under 14 words per bullet) with key takeaway or callout.
  - `two_blocks`: Contrastive side-by-side comparative cards.
  - `table`: Structured tabular data comparisons.
  - `equation`: Centered mathematical derivations in LaTeX with worked numbers.
  - `code`: Formatted code blocks with syntax styling.
  - `big_stat`: Dominant numerical metric callouts with contextual subtitles.
  - `summary_grid`: 4–6 takeaway matrix recapping the presentation.
- **Dual Presentation Compilers**:
  - **Beamer LaTeX Engine**: Rendered into Beamer code utilizing a bespoke Navy/Teal palette, sans-serif typography (`helvet`), custom `tcolorbox` blocks, and compiled via **Tectonic** into vector PDFs.
  - **Editable PPTX**: Rendered natively via `python-pptx` with identical geometry, custom brand colors, shapes, and native PowerPoint tables.
- **Plan-Do-Check-Act Repair Loop**: Deterministic linting catches duplicate titles, layout mismatches, and rhythm violations, while single-slide LLM repair fixes local schema discrepancies before rendering.

### 🔑 Bring-Your-Own-Key (BYOK) Model Layer
- **Multi-Provider Freedom**: Direct native support for:
  - **Groq**: Ultra-fast inference with `openai/gpt-oss-120b` (default) and `llama-3.3-70b-versatile`.
  - **OpenAI**: Next-generation reasoning models (`gpt-6.1-sol`, `gpt-6-astra`, `gpt-6-luna`).
  - **Anthropic**: Frontier reasoning and analysis (`claude-sonnet-5-5`, `claude-haiku-5-5`, `claude-opus-5-5`).
  - **Google Gemini**: Large-context analysis (`gemini-1.5-pro-latest`, `gemini-1.5-flash-latest`).
  - **OpenRouter**: Unified gateway to open-weights and proprietary models.
- **Role-Based Provider Splitting**: Users can select separate models for Article Writing and Slide Deck Planning (e.g. Claude 3.5 Sonnet for writing; Groq for rapid slide deck assembly).
- **In-App Connectivity Testing**: Dedicated `POST /llm/test` endpoint fires a minimal ~16-token probe to verify API credentials before initiating long-running jobs.
- **Zero-Leakage Guarantee**: API keys are scrubbed from exception chains, never stored in job records, omitted from logs, and scrubbed from responses.

### 🛡️ Authentication, Persistence & Job History
- **Dual Guest & Authenticated Modes**: Guests can generate articles immediately in memory without signing in; authenticated users unlock persistent history, cloud storage, and encrypted key management.
- **Supabase Authentication**: Supports standard Email/Password authentication and one-click Google OAuth.
- **Fernet Symmetric Encryption**: User API keys are encrypted at rest using 32-byte AES-grade Fernet encryption (`APP_ENCRYPTION_KEY`). The backend displays only the safe `last4` characters.
- **Row Level Security (RLS)**: Database tables enforce strict user isolation (`auth.uid() = user_id`). Users can never enumerate, view, or delete other users' jobs or credentials.
- **Interrupted Job Recovery**: If the backend container restarts during deployment, queued or running jobs older than 15 minutes are automatically transitioned to a graceful error state on reboot.

### 🎨 Apple-Inspired Editorial UI
- **Design Language**: Crafted according to Apple Human Interface Guidelines (HIG) with an editorial warm off-white canvas, micro-borders (`1px`), subtle amber accents, and clean SF-style typography.
- **Real-Time Progress Tracking**: Step-by-step pipeline tracker reporting live status: *Queued → Routing → Researching → Planning → Writing → Finalizing → Done*.
- **Live Markdown Editor & Preview**: Side-by-side editing pane, rendered preview, one-click copy, and `.md` file export.
- **Integrated PDF Preview**: Fetches authenticated blob streams directly into an interactive in-browser previewer without triggering unwanted download prompts.

---

## 3. System Architecture & Information Flow

```
                           ┌────────────────────────────┐
                           │   React + Vite Frontend    │
                           │  (Apple HIG / TypeScript)  │
                           └──────────────┬─────────────┘
                                          │  REST API + JWT Bearer
                                          ▼
                           ┌────────────────────────────┐
                           │      FastAPI Backend       │
                           │ (Abuse limits / BYOK auth) │
                           └──────┬───────────────┬─────┘
                                  │               │
            ┌─────────────────────┴──────┐        └────────────────────┐
            │                            │                             │
            ▼                            ▼                             ▼
┌───────────────────────┐   ┌─────────────────────────┐   ┌────────────────────────┐
│ LangGraph Agent Core  │   │   Slide Planning Core   │   │  Supabase Cloud Store  │
│  - Router Node        │   │  - Page-Job Planner     │   │  - PostgreSQL DB (RLS) │
│  - Tavily Researcher  │   │  - Lenient JSON Loader  │   │  - Auth (OAuth/Email)  │
│  - Article Planner    │   │  - 400 Salvage Protocol │   │  - Private Artifacts   │
│  - Parallel Workers   │   │  - Deterministic Linter │   │  - Fernet BYOK Keys    │
│  - Markdown Reducer   │   └────────────┬────────────┘   └────────────────────────┘
└───────────────────────┘                │
                                         ▼
                            ┌────────────────────────┐
                            │ Presentation Compilers │
                            │  - Tectonic XeTeX (PDF)│
                            │  - python-pptx (PPTX)  │
                            └────────────────────────┘
```

---

## 4. Complete Technology Stack

| Layer | Technology | Purpose & Implementation Details |
| :--- | :--- | :--- |
| **Frontend Framework** | **React 18** | Modular UI architecture with hooks and concurrent mode rendering. |
| **Language (Frontend)**| **TypeScript 5.x** | End-to-end typed contracts matching backend Pydantic schemas. |
| **Build Tool** | **Vite 6** | Ultra-fast HMR and optimized production bundling with chunk splitting. |
| **Styling & Design** | **Tailwind CSS** | Utility-first styling with Apple HIG design system tokens and responsive layouts. |
| **UI Components** | **Radix UI / shadcn** | Accessible primitives for dialogs, modals, dropdowns, and tabs. |
| **Icons** | **Lucide React** | Clean, minimal vector iconography. |
| **Backend Framework** | **FastAPI** | High-performance asynchronous REST API with automatic OpenAPI documentation. |
| **ASGI Server** | **Uvicorn** | Production-ready ASGI server supporting proxy headers and dynamic ports. |
| **Agent Orchestration**| **LangGraph** | Stateful cyclical/directed graph engine managing multi-agent pipeline state. |
| **LLM Framework** | **LangChain Core** | Provider abstraction layer across Groq, OpenAI, Anthropic, and Google. |
| **Default Inference** | **Groq Cloud** | Ultra-high throughput LPU inference running `openai/gpt-oss-120b`. |
| **Web Search** | **Tavily Search API**| Real-time developer search engine optimized for AI fact retrieval and synthesis. |
| **Data Validation** | **Pydantic v2** | Strict schema parsing, type coercion, and tolerant JSON schema models. |
| **PDF Compilation** | **Tectonic** | Self-contained, modernized XeTeX LaTeX typesetting engine producing vector PDFs. |
| **PPTX Generation** | **python-pptx** | Direct binary generation of editable 16:9 widescreen PowerPoint decks. |
| **Cloud Database** | **Supabase (PostgreSQL)** | Managed relational database storing jobs, slide records, and encrypted keys. |
| **Data Security** | **PostgreSQL RLS** | Row Level Security policies enforcing owner isolation (`auth.uid() = user_id`). |
| **Key Encryption** | **Cryptography (Fernet)**| Symmetric 128-bit AES encryption for BYOK credentials stored at rest. |
| **Auth Verification** | **PyJWT [crypto]** | Strict RS256/ES256 JWKS and HS256 algorithm pinning for Supabase JWTs. |
| **Containerization** | **Docker** | Debian Bookworm slim runtime with pre-baked TeX package bundles and non-root user. |
| **Backend Host** | **Render** | Cloud Docker service with automated health check monitoring (`/health`). |
| **Frontend Host** | **Vercel** | Edge-deployed static single-page application with rewrite rules (`vercel.json`). |

---

## 5. Security & Reliability Highlights

1. **Hardened CORS & Proxy Forwarding**:
   - `CORS_ORIGINS` dynamically whitelists deployed frontend domains. Wildcard `*` is prohibited when `allow_credentials=True`.
   - `TRUST_PROXY=true` safely extracts the client IP from the last entry of `X-Forwarded-For` behind cloud load balancers.
2. **Abuse Mitigation & Rate Limiting**:
   - In-memory sliding-window limiter restricts unauthenticated guest jobs (default: 20 jobs/hour).
   - Signed-in user limits enforce concurrent active jobs (max: 3) and daily limits (max: 50).
   - Dedicated probe rate limiter restricts `/llm/test` attempts to 10 requests/minute per IP.
3. **Groq `json_validate_failed` Resiliency**:
   - Groq slide planning bypasses `response_format=json_object` to prevent premature HTTP 400 rejections.
   - Built-in `lenient_json_loads` repairs single-backslash LaTeX (`\alpha`, `\frac`), unescaped quotes in code blocks, and unclosed JSON containers from truncated tokens.
   - 400 error salvage recovers `failed_generation` text directly from API responses.
4. **Secret Sanitization**:
   - Centralized secret scrubber strips API keys, Authorization headers, and Bearer tokens before any error message is returned to the user or recorded in logs.

---

## 6. Project Layout

```
├── backend/
│   ├── Dockerfile                  # Production Debian 12 container with Tectonic
│   ├── requirements.txt            # Pinned Python dependencies
│   └── app/
│       ├── main.py                 # FastAPI initialization, CORS, lifespan
│       ├── api/
│           └── routes.py           # REST endpoints, abuse limits, BYOK test probe
│       ├── core/
│           ├── agent.py            # LangGraph pipeline construction and execution
│           ├── auth.py             # JWKS / HMAC JWT verification & user dependency
│           ├── crypto.py           # 32-byte Fernet symmetric encryption for keys
│           ├── db.py               # Supabase CRUD operations & stale job cleanup
│           ├── jobs.py             # Thread-safe in-memory + write-through job store
│           ├── llm.py              # Provider registry & dynamic model factory
│           ├── planner.py          # Routing & multi-section article planning
│           ├── research.py         # Tavily web search & evidence condensation
│           ├── slides.py           # Beamer PDF & PPTX generators, lenient loader
│           └── writer.py           # Parallel section worker nodes
│       └── models/
│           └── schemas.py          # Tolerant Pydantic models for jobs & slides
│
├── frontend/
│   ├── vercel.json                 # Vercel SPA client routing configuration
│   ├── package.json                # React, TypeScript, Tailwind, Lucide dependencies
│   └── src/
│       ├── App.tsx                 # Client routing & application providers
│       ├── api/client.ts           # Authenticated API client (Supabase token injection)
│       ├── components/             # Form cards, header, modals, slides viewer
│       ├── context/                # AuthContext and ModelSettingsContext (BYOK)
│       ├── pages/                  # Home, Result, History pages
│       └── lib/supabase.ts         # Supabase client instantiation
│
└── supabase/
    └── schema.sql                  # Idempotent PostgreSQL schema with RLS policies
```

---

*Authored for SAGE — Production Autonomous Research & Presentation Studio.*
