# GenAI Agentic AI — Blog Generation Agent

> **Status: Version 0 (v0)** — This is an early, CLI-only version of the project. Output is currently printed to the terminal. A proper UI, file export, and additional features are planned for future versions.

## Overview

This project is a **multi-agent blog generation pipeline** built with [LangGraph](https://github.com/langchain-ai/langgraph). Given a topic, it automatically:

1. **Routes** the topic to decide whether it needs fresh web research or can be answered from general knowledge.
2. **Researches** the topic on the web (if needed) using Tavily search.
3. **Plans** a structured blog outline with multiple sections, each with goals, bullet points, and word targets.
4. **Writes** each section in parallel using an LLM.
5. **Combines** all sections into a final blog post and prints it to the terminal.

The pipeline is powered by Google's Gemini models via `langchain-google-genai`, and orchestrated as a stateful graph using LangGraph.

## How It Works

The pipeline is built as a directed graph with the following nodes:

| Node | Responsibility |
|---|---|
| **Router** | Decides whether the topic needs research (`closed_book`, `hybrid`, or `open_book` mode) and generates search queries if needed. |
| **Research** | Runs web searches via Tavily, extracts and deduplicates evidence, and filters by recency if the topic is time-sensitive. |
| **Orchestrator** | Produces a structured `Plan` — a blog title, audience, tone, and 5–9 sections (tasks), each with a goal, bullets, and target word count. |
| **Worker** | Runs in parallel (fanned out via `Send`) — one worker per section — to write the actual Markdown content for that section, grounded in evidence where required. |
| **Reducer** | Assembles all sections in order into the final blog post and prints it to the terminal. |

### Modes

- **`closed_book`** — Evergreen topics (concepts, fundamentals) that don't need current information.
- **`hybrid`** — Mostly evergreen but benefits from up-to-date examples, tools, or models.
- **`open_book`** — Volatile topics like weekly news roundups, rankings, or pricing that require fresh evidence.

## Requirements

- Python 3.11+
- A [Google Gemini API key](https://ai.google.dev/)
- A [Tavily API key](https://tavily.com/) (for web research)

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/<your-username>/<repo-name>.git
   cd <repo-name>
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate   # macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**

   Create a `.env` file in the project root:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   TAVILY_API_KEY=your_tavily_api_key_here
   ```

   > ⚠️ Never commit your `.env` file. It's already excluded via `.gitignore`.

## Usage

Run the agent with a topic hardcoded at the bottom of `agent.py`:

```bash
python agent.py
```

Currently the topic is set directly in code:
```python
run("Write a blog on history of neural networks")
```

The final blog post, along with routing/research/planning metadata, will be printed to the terminal.

### Example output metadata
```
TOPIC: Write a blog on synchronous generators
MODE: closed_book
BLOG_KIND: tutorial
NEEDS_RESEARCH: False
TASKS: 5
```

## Project Structure

```
.
├── agent.py           # Main LangGraph pipeline (router, research, orchestrator, worker, reducer)
├── .env               # API keys (not committed)
├── .gitignore
├── requirements.txt
└── README.md
```

## Known Limitations (v0)

- **CLI-only** — no web UI or API endpoint yet.
- **Hardcoded topic** — no CLI argument or input prompt for the topic yet.
- **No file export** — output is printed, not saved (by design, for now).
- **No persistence** — no database or history of past runs.
- **No tests** — pipeline has not been unit tested yet.
- Uses `langchain_community`'s `TavilySearchResults`, which is deprecated upstream and will need migration to a standalone Tavily integration package in a future version.

## Roadmap

- [ ] Add a simple web UI (likely Streamlit or a lightweight frontend)
- [ ] Accept topic as CLI argument / user input
- [ ] Optional file export (Markdown/PDF)
- [ ] Migrate off deprecated `langchain_community` Tavily tool
- [ ] Add basic tests for individual nodes
- [ ] Add configurable model selection


**This is version 0 — an early prototype focused on validating the core agent pipeline. Expect breaking changes as the project evolves.**
