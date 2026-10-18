# SAGE — AI Research & Presentation Studio

> **Status: Version 1 (v1)** — A full-stack AI-powered research, writing, and presentation platform built with **LangGraph**, **FastAPI**, and **React**. The project exposes a REST API, provides a modern web interface, generates high-quality articles using a multi-agent workflow, and compiles lecture-grade slide decks (Beamer PDF + editable PPTX).

---

# Overview

SAGE is a **multi-agent research, writing, and presentation system** that automatically researches a topic, creates a structured writing plan, generates each section in parallel, assembles a polished Markdown article, and compiles lecture-grade presentation slides.

Unlike traditional single-prompt generators, this project uses **LangGraph** to orchestrate specialized AI agents, each responsible for a distinct stage of the writing process.

The application consists of three layers:

* **Agent Core** — LangGraph workflow and AI agents
* **FastAPI Backend** — REST API and job management
* **React Frontend** — Interactive UI with real-time progress tracking

---

# Features

* Multi-agent architecture powered by LangGraph
* Automatic topic routing
* Intelligent web research using Tavily
* Parallel section generation
* Structured planning before writing
* FastAPI backend with asynchronous job handling
* React + TypeScript frontend
* Live generation progress
* Markdown preview and editing
* Source attribution
* Copy and Markdown export
* REST API for integration with other applications

---

# Architecture

```
                 React + Vite Frontend
                         │
                         │ REST API
                         ▼
                 FastAPI Backend
                         │
                         ▼
               LangGraph Agent Core
        ┌────────────┬─────────────┐
        │            │             │
       Groq LLM    Tavily API   Job Manager
```

---

# Agent Workflow

The generation pipeline is implemented as a LangGraph workflow.

## 1. Router

Determines whether the topic needs fresh web research.

Possible modes:

* **closed_book**
* **hybrid**
* **open_book**

---

## 2. Research

If research is required:

* Generates search queries
* Performs Tavily searches
* Deduplicates evidence
* Filters by recency
* Produces structured evidence for downstream agents

---

## 3. Planner

Creates a complete writing plan including:

* Blog title
* Target audience
* Tone
* Writing style
* Multiple section tasks
* Goals
* Bullet points
* Target word counts

---

## 4. Worker

Each section is generated independently.

LangGraph fans out one worker per section, allowing parallel execution.

Each worker receives:

* Section goal
* Supporting evidence
* Tone
* Audience
* Style

and produces Markdown content.

---

## 5. Reducer

Collects all completed sections and assembles the final article in the correct order.

---

# Tech Stack

## AI

* LangGraph
* LangChain
* Groq (Llama 3.3 70B & gpt-oss-120b)
* Tavily Search

## Backend

* FastAPI
* Uvicorn
* Pydantic

## Frontend

* React
* TypeScript
* Vite
* Tailwind CSS
* shadcn/ui

---

# Project Structure

```
GenAI-AgenticAI/

├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   │   ├── agent.py
│   │   │   ├── planner.py
│   │   │   ├── research.py
│   │   │   ├── writer.py
│   │   │   └── jobs.py
│   │   ├── models/
│   │   ├── utils/
│   │   └── main.py
│   ├── cli.py
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   └── App.tsx
│   └── package.json
│
└── README.md
```

---

# Backend API

## Generate Blog

```
POST /generate
```

Starts a new blog generation job.

Example request:

```json
{
  "topic": "History of Neural Networks",
  "tone": "professional",
  "style": "blog",
  "audience": "developers",
  "length": "medium",
  "use_web": true
}
```

---

## Check Progress

```
GET /jobs/{job_id}
```

Returns:

* status
* current stage
* progress percentage

Stages:

* queued
* routing
* researching
* planning
* writing
* finalizing
* done

---

## Retrieve Result

```
GET /jobs/{job_id}/result
```

Returns:

* title
* outline
* generated Markdown
* cited sources

---

# Frontend

The React application provides:

* Topic input form
* Tone selection
* Audience selection
* Style selection
* Length selection
* Research toggle
* Live progress indicator
* Markdown editor
* Markdown preview
* Source viewer
* Markdown export

---

# Setup

## 1. Clone the repository

```bash
git clone https://github.com/sshiv-1/blog-writing-with-research-agent.git
cd blog-writing-with-research-agent
```

---

## 2. Create a virtual environment

Windows

```bash
python -m venv venv
venv\Scripts\activate
```

macOS/Linux

```bash
python -m venv venv
source venv/bin/activate
```

---

## 3. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

---

## 4. Install frontend dependencies

```bash
cd ../frontend
npm install
```

---

## 5. Configure environment variables

Create a `.env` file inside the `backend` directory.

```env
GROQ_API_KEY=your_key_here
GROQ_PPTX_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
```

---

# Running the Application

## Backend

```bash
cd backend
uvicorn app.main:app --reload
```

FastAPI:

```
http://localhost:8000
```

Swagger Docs:

```
http://localhost:8000/docs
```

---

## Frontend

```bash
cd frontend
npm run dev
```

Open:

```
http://localhost:5173
```

---

## CLI

The original CLI interface is still available.

```bash
cd backend

python cli.py \
    --topic "History of Neural Networks" \
    --tone professional \
    --length medium
```

---

# Deployment

SAGE is designed for seamless zero-downtime deployment with a containerized backend on **Render** and a static SPA on **Vercel**.

---

## 1. Backend Deployment (Render)

Deploy the backend as a **Web Service** using the included production Dockerfile.

### Setup Steps
1. Create a new **Web Service** in Render and connect your repository.
2. Configure settings:
   - **Root Directory**: `backend`
   - **Environment**: `Docker`
   - **Health Check Path**: `/health` (responds immediately with `{"status": "ok"}` without external dependencies)
3. Set the following environment variables in the Render dashboard:

| Variable | Required | Description |
| :--- | :---: | :--- |
| `GROQ_BLOG_API_KEY` | Yes | Default server Groq API key for article generation |
| `GROQ_PPTX_API_KEY` | Yes | Default server Groq API key for slide generation |
| `TAVILY_API_KEY` | Yes | Tavily search API key for real-time web research |
| `SUPABASE_URL` | Optional | Supabase project URL (`https://<project-ref>.supabase.co`). If unset, runs in guest in-memory mode. |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional | Supabase service role secret (backend only). |
| `SUPABASE_JWT_SECRET` | Optional | Supabase JWT secret for HS256 validation. If omitted, verifies via JWKS RS256/ES256. |
| `APP_ENCRYPTION_KEY` | Optional | 32-byte Fernet base64 key for BYOK encryption. Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `CORS_ORIGINS` | Yes | Comma-separated allowed frontend origins (e.g. `https://sage-app.vercel.app`). Localhost is always included. |
| `TRUST_PROXY` | Yes | Set to `true` to enable client IP extraction from `X-Forwarded-For` behind Render's reverse proxy. |
| `GUEST_JOBS_PER_HOUR` | Optional | Sliding hourly rate limit for guest jobs (default: `20`). Soft in-memory abuse control. |
| `DAILY_USER_JOB_CAP` | Optional | Daily job limit per registered user (default: `50`). |
| `MAX_CONCURRENT_USER_JOBS` | Optional | Maximum concurrent jobs per registered user (default: `3`). |

> [!NOTE]
> **Interrupted Job Recovery**: If Render restarts the backend container, any in-flight or queued jobs from previous runs are automatically detected and marked as failed (`Interrupted by a server restart`) during application startup and on read.

---

## 2. Frontend Deployment (Vercel)

Deploy the frontend as a static SPA on Vercel.

### Setup Steps
1. Import your repository into **Vercel**.
2. Configure settings:
   - **Framework Preset**: `Vite`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
3. Client-side routing is configured via [`frontend/vercel.json`](file:///c:/Coding/Project/blog-writing-with-research-agent/frontend/vercel.json) to rewrite deep links to `index.html`.
4. Configure environment variables in the Vercel dashboard:

| Variable | Required | Description |
| :--- | :---: | :--- |
| `VITE_API_URL` | Yes | URL of your deployed Render backend (e.g. `https://sage-api.onrender.com`) |
| `VITE_SUPABASE_URL` | Optional | Supabase project URL for authentication and history |
| `VITE_SUPABASE_ANON_KEY` | Optional | Supabase public anonymous key (never use service role key in frontend) |

---

## 3. Supabase Dashboard Configuration

If using Supabase for user authentication, saved BYOK keys, and history:
1. In your Supabase Dashboard, navigate to **Authentication -> URL Configuration**.
2. Set **Site URL** to your Vercel deployment URL (e.g. `https://sage-app.vercel.app`).
3. Add `https://sage-app.vercel.app/**` to **Redirect URLs**.
4. Run the schema migrations from [`supabase/schema.sql`](file:///c:/Coding/Project/blog-writing-with-research-agent/supabase/schema.sql) in the Supabase SQL Editor.

---

# Current Capabilities

* Multi-agent orchestration
* Automatic research routing
* Live web search
* Parallel section generation
* Structured planning
* REST API
* Interactive web interface
* Progress tracking
* Markdown editing
* Source citations
* Markdown export

---

# Future Improvements

* Persistent job storage using Redis
* WebSocket-based live streaming
* PDF and DOCX export
* Authentication
* Blog history
* Saved projects
* Regenerate individual sections
* Multiple LLM providers
* Docker deployment
* CI/CD pipeline
* Automated testing

---

# Why LangGraph?

This project demonstrates how LangGraph can be used to build production-style AI systems using:

* Routing agents
* Planning agents
* Parallel workers
* State management
* Graph-based orchestration

instead of relying on a single LLM prompt.

---

# License

This project is intended for educational and portfolio purposes.

---

Built with ❤️ using **LangGraph**, **FastAPI**, **React**, **Groq**, and **Tavily Search**.
Slide design principles (page job, layout rhythm, plan/do/check/act repair) adapted from ppt-master by Hugo He (MIT).
