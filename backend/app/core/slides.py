# Slide design principles (page job, layout rhythm, plan/do/check/act repair) adapted from ppt-master by Hugo He (MIT).
from __future__ import annotations

import io
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from .agent import retry_on_rate_limit
from .jobs import get_job, get_slide_job, update_slide_job
from .llm import (
    PROVIDER_REGISTRY,
    get_llm,
    scrub_exception_chain,
    scrub_secrets,
    slides_llm,
)
from ..models.schemas import (
    BlogResult,
    LLMSelection,
    Slide,
    SlideBlock,
    SlideCode,
    SlideDeck,
    SlideDesignBrief,
    SlideStat,
    SlideTable,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Planner prompt
# ---------------------------------------------------------------------------

SLIDES_SYSTEM = """You are a lecturer and presentation designer turning a blog article into a lecture-grade slide deck. Reply with JSON only, matching the schema.

PLAN first. Fill design_brief: the audience, the story arc in one sentence as "narrative", 3-5 key takeaways, and, if the source has one, a single running example that is reused across slides so numbers stay comparable. Color logic for emphasis: red = inputs or problems, blue = parameters or methods, green = outputs or results, purple = operations or process.

DO next. For every slide write page_job: one sentence saying what this slide must do for the reader (for example 'show why X costs more than Y'). Everything on the slide must serve that job. If a bullet does not serve it, delete it. Pick the layout from the job: compare things -> table; define or contrast two ideas -> two_blocks; quantify or derive -> equation, with worked numbers in the bullets; show implementation -> code; one dominant number -> big_stat; recap -> summary_grid.
Content rules: depth over decoration. Carry over equations, numbers, named systems and worked examples from the source. Never invent facts or numbers that are not in the source. 3-5 bullets per slide, each under 14 words. Titles state the claim ('Separable convs cut FLOPs 1.5x'), not the topic ('Results'). insight = one 'so what' sentence. callout = the single central claim, used on at most two slides in the deck.
Rhythm: never more than two consecutive slides with the same layout. Alternate dense slides (equation, table, code) with light ones (big_stat, two_blocks). Title, agenda and summary_grid are the fixed anchors: title first, agenda second, summary_grid last.
Write in the same language as the blog.
Rules: Use ASCII hyphens and plain spaces only. No Unicode dashes or non-breaking spaces. Write math symbols as words or LaTeX in the equation field. Code must come from the source article only; if the source has no code, do not use the code layout.

Output must be valid JSON only. Use ONLY these field names and this structure:
{
 "title": "...", "subtitle": "...", "author": "SAGE", "short_title": "<=30 chars",
 "design_brief": {"audience": "...", "narrative": "...", "takeaways": ["..."], "running_example": "... or null"},
 "slides": [
  {"layout": "title", "page_job": "...", "title": "...", "kicker": null},
  {"layout": "agenda", "page_job": "...", "title": "Agenda", "bullets": ["..."]},
  {"layout": "bullets", "page_job": "...", "title": "...", "bullets": ["..."], "insight": "...", "callout": null, "takeaway": null},
  {"layout": "two_blocks", "page_job": "...", "title": "...", "blocks": [{"heading": "...", "body": "..."}, {"heading": "...", "body": "..."}]},
  {"layout": "table", "page_job": "...", "title": "...", "table": {"headers": ["..."], "rows": [["..."]]}},
  {"layout": "equation", "page_job": "...", "title": "...", "equation": "plain LaTeX, no $", "bullets": ["..."]},
  {"layout": "code", "page_job": "...", "title": "...", "code": {"language": "python", "snippet": "..."}},
  {"layout": "big_stat", "page_job": "...", "title": "...", "stat": {"value": "1.7x", "label": "faster"}, "bullets": ["..."]},
  {"layout": "summary_grid", "page_job": "...", "title": "...", "blocks": [{"heading": "...", "body": "..."}]}
 ]
}

CHECK before answering: slide count is within 1 of the requested count; every slide has a page_job; no duplicate titles; each layout has its payload (table -> table, equation -> equation, code -> code, big_stat -> stat, two_blocks -> exactly 2 blocks, summary_grid -> 4 to 6 blocks); equations are plain LaTeX math with balanced braces and no $ or \\begin. Return valid JSON only."""


# ---------------------------------------------------------------------------
# Compact Blog Text Extractor & Parsing Helpers
# ---------------------------------------------------------------------------

def _clean_json_text(text: str) -> str:
    """Strip markdown code fences and whitespace from LLM response."""
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _format_validation_summary(err: Exception) -> str:
    """Format short summary of validation issues (max ~10 lines, field paths only)."""
    lines = []
    if hasattr(err, "errors"):
        for e in err.errors()[:10]:
            loc = ".".join(str(p) for p in e.get("loc", []))
            msg = e.get("msg", "invalid")
            msg = re.sub(r'\[https?://[^\]]+\]', '', msg).strip()
            lines.append(f"- {loc}: {msg}" if loc else f"- {msg}")
    else:
        lines.append(f"- JSON syntax error: {str(err)[:100]}")
    return "\n".join(lines[:10])


def format_short_error(err: Exception) -> str:
    """Format short error: first 300 characters, no pydantic URLs, no stack of 18 errors."""
    if hasattr(err, "errors"):
        errs = err.errors()
        err_lines = []
        for e in errs[:3]:
            loc = ".".join(str(p) for p in e.get("loc", []))
            msg = e.get("msg", "invalid")
            msg = re.sub(r'\[https?://[^\]]+\]', '', msg).strip()
            err_lines.append(f"{loc}: {msg}" if loc else msg)
        summary = "; ".join(err_lines)
        if len(errs) > 3:
            summary += f" (+{len(errs)-3} more issues)"
        msg = f"Slide schema validation failed: {summary}"
    else:
        msg = f"Slide generation failed: {str(err)}"
    msg = re.sub(r'https?://\S+', '', msg).strip()
    return msg[:300].strip()


def _extract_compact_blog_context(
    blog: BlogResult,
    planner_input_token_cap: Optional[int] = 6000,
) -> str:
    """
    Extract blog context for slide planning.
    - If planner_input_token_cap is set (e.g. 6000 for Groq):
      Extract headings + first ~600 chars of each section, capped at token_cap * 3 chars (~18k).
    - If planner_input_token_cap is None (frontier providers):
      Whole article with a hard ceiling of ~60k tokens (~240,000 chars).
      If draft exceeds 240,000 chars, truncate section bodies evenly.
    """
    lines = [f"# Title: {blog.title}\n"]
    if blog.outline:
        lines.append("## Outline:")
        for sec in blog.outline:
            title = sec.get("title", "")
            bullets = sec.get("bullets", [])
            lines.append(f"- {title}")
            for b in bullets[:3]:
                lines.append(f"  * {b}")
        lines.append("\n## Content Excerpts:\n")

    draft = blog.draft or ""
    sections = re.split(r"(?m)^(?=#{1,3}\s+)", draft)
    sections = [s.strip() for s in sections if s.strip()]

    # Case 1: Cap is specified (e.g. Groq 6000 tokens -> ~18,000 chars)
    if planner_input_token_cap is not None:
        max_chars = planner_input_token_cap * 3
        accumulated_chars = 0
        for sec in sections:
            first_600 = sec[:600]
            if len(sec) > 600:
                first_600 += "..."
            lines.append(first_600 + "\n")
            accumulated_chars += len(first_600)
            if accumulated_chars >= max_chars:
                lines.append("\n[Remaining content truncated for brevity]")
                break
        return "\n".join(lines)

    # Case 2: Frontier models (whole article up to 60k tokens ceiling ~ 240,000 chars)
    HARD_CEILING_CHARS = 240000
    total_draft_len = sum(len(s) for s in sections)
    if total_draft_len <= HARD_CEILING_CHARS:
        for sec in sections:
            lines.append(sec + "\n")
    else:
        # Truncate section bodies evenly across all sections
        num_sections = max(1, len(sections))
        per_sec_cap = HARD_CEILING_CHARS // num_sections
        for sec in sections:
            if len(sec) > per_sec_cap:
                lines.append(sec[:per_sec_cap] + "...\n")
            else:
                lines.append(sec + "\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Planner Execution
# ---------------------------------------------------------------------------

@retry_on_rate_limit(max_retries=3, initial_backoff=2.0)
def plan_slides_deck(
    blog: BlogResult,
    slide_count: int = 10,
    audience: Optional[str] = None,
    llm: Optional[Any] = None,
    planner_input_token_cap: Optional[int] = 6000,
    keys_to_scrub: Optional[list[str]] = None,
) -> SlideDeck:
    """
    Generate a SlideDeck from a blog using the active LLM with json_mode.
    Parses raw text, strips fences, validates through tolerant SlideDeck schema.
    If parsing/validation fails, performs ONE repair call with problem summary.
    """
    if llm is None:
        llm = slides_llm()

    # Bind json_mode if supported, otherwise rely on system prompt JSON instruction
    try:
        json_llm = llm.bind(response_format={"type": "json_object"})
    except Exception:
        json_llm = llm

    compact_context = _extract_compact_blog_context(
        blog, planner_input_token_cap=planner_input_token_cap
    )

    aud_prompt = f"Target audience: {audience}" if audience else "Target audience: developers and engineers"
    user_prompt = (
        f"{aud_prompt}\n"
        f"Requested slide count: {slide_count} slides (must be within 1 of this target).\n"
        f"Source blog:\n\n{compact_context}\n\n"
        "Generate the complete lecture-grade SlideDeck JSON now."
    )

    response = json_llm.invoke([
        {"role": "system", "content": SLIDES_SYSTEM},
        {"role": "user", "content": user_prompt},
    ])
    raw_content = str(response.content if hasattr(response, "content") else response)
    cleaned = _clean_json_text(raw_content)

    # First attempt at parsing & validation
    last_err: Optional[Exception] = None
    try:
        data = json.loads(cleaned)
        return SlideDeck.model_validate(data)
    except Exception as e:
        last_err = e
        logger.warning(
            "First SlideDeck JSON parse/validation failed: %s",
            scrub_secrets(str(e), keys=keys_to_scrub),
        )

    # ONE repair call
    prob_summary = _format_validation_summary(last_err)
    repair_prompt = (
        f"The previous JSON failed validation with the following problems:\n"
        f"{prob_summary}\n\n"
        f"Previous JSON:\n{cleaned[:3000]}\n\n"
        f"Fix the JSON according to the schema. Return corrected JSON only."
    )

    try:
        repair_resp = json_llm.invoke([
            {"role": "system", "content": SLIDES_SYSTEM},
            {"role": "user", "content": repair_prompt},
        ])
        repair_raw = str(repair_resp.content if hasattr(repair_resp, "content") else repair_resp)
        repair_cleaned = _clean_json_text(repair_raw)
        repair_data = json.loads(repair_cleaned)
        return SlideDeck.model_validate(repair_data)
    except Exception as e:
        logger.error(
            "SlideDeck repair attempt failed: %s",
            scrub_secrets(str(e), keys=keys_to_scrub),
        )
        short_err = format_short_error(e)
        scrubbed = scrub_secrets(short_err, keys=keys_to_scrub)
        raise ValueError(scrubbed) from None


# ---------------------------------------------------------------------------
# CHECK & ACT Layer (Lint & Deterministic / Local Repair)
# ---------------------------------------------------------------------------

def lint_slide_deck(deck: SlideDeck, requested_count: int = 10) -> List[str]:
    """
    Deterministic lint enforcing:
    - Slide count within 1 of requested
    - Every slide has non-empty page_job
    - No duplicate titles
    - Layout payloads (table, equation, code, stat, two_blocks, summary_grid)
    - Bullets: 3-5 items, length capped at ~14 words
    - Rhythm: no 3 consecutive identical layouts
    - Fixed anchors: title first, agenda second, summary_grid last
    """
    issues: List[str] = []
    slides = deck.slides or []

    # 1. Slide count
    if abs(len(slides) - requested_count) > 1:
        issues.append(
            f"Slide count mismatch: got {len(slides)}, requested {requested_count} (allowed diff <= 1)"
        )

    # 2. Anchors
    if len(slides) > 0 and slides[0].layout != "title":
        issues.append(f"Anchor violation: first slide must have layout 'title', got '{slides[0].layout}'")
    if len(slides) > 1 and slides[1].layout != "agenda":
        issues.append(f"Anchor violation: second slide must have layout 'agenda', got '{slides[1].layout}'")
    if len(slides) > 2 and slides[-1].layout != "summary_grid":
        issues.append(f"Anchor violation: last slide must have layout 'summary_grid', got '{slides[-1].layout}'")

    # 3. Titles & Page Jobs
    seen_titles = set()
    for idx, s in enumerate(slides):
        s_num = idx + 1
        if not s.page_job or not s.page_job.strip():
            issues.append(f"Slide {s_num} ('{s.title}'): missing page_job")

        norm_title = s.title.strip().lower()
        if norm_title in seen_titles:
            issues.append(f"Duplicate slide title: '{s.title}' on slide {s_num}")
        seen_titles.add(norm_title)

        # 4. Payload check per layout
        layout = s.layout
        if layout == "table":
            if not s.table or not s.table.headers or not s.table.rows:
                issues.append(f"Slide {s_num}: layout is 'table' but table payload is missing or empty")
        elif layout == "equation":
            if not s.equation or not s.equation.strip():
                issues.append(f"Slide {s_num}: layout is 'equation' but equation is missing")
            else:
                eq = s.equation.strip()
                if "$" in eq or "\\begin{" in eq:
                    issues.append(f"Slide {s_num}: equation must not contain $ delimiters or \\begin block")
                if eq.count("{") != eq.count("}"):
                    issues.append(f"Slide {s_num}: equation has unbalanced braces")
        elif layout == "code":
            if not s.code or not s.code.snippet or not s.code.snippet.strip():
                issues.append(f"Slide {s_num}: layout is 'code' but code snippet is missing")
        elif layout == "big_stat":
            if not s.stat or not s.stat.value or not s.stat.value.strip():
                issues.append(f"Slide {s_num}: layout is 'big_stat' but stat value is missing")
        elif layout == "two_blocks":
            if len(s.blocks) != 2:
                issues.append(f"Slide {s_num}: layout is 'two_blocks' but has {len(s.blocks)} blocks (expected 2)")
        elif layout == "summary_grid":
            if len(s.blocks) < 4 or len(s.blocks) > 6:
                issues.append(f"Slide {s_num}: layout is 'summary_grid' but has {len(s.blocks)} blocks (expected 4-6)")

        # 5. Bullets check (for bullet-bearing layouts)
        if layout in ("bullets", "agenda", "big_stat", "equation", "table"):
            if s.bullets and len(s.bullets) > 6:
                issues.append(f"Slide {s_num}: has {len(s.bullets)} bullets (expected 3-5)")
            for b_idx, b in enumerate(s.bullets):
                words = b.split()
                if len(words) > 16:
                    issues.append(f"Slide {s_num} bullet {b_idx + 1} exceeds 14 words ({len(words)} words)")

    # 6. Rhythm: no 3 consecutive identical layouts
    for i in range(len(slides) - 2):
        l1, l2, l3 = slides[i].layout, slides[i + 1].layout, slides[i + 2].layout
        if l1 == l2 == l3:
            issues.append(f"Rhythm violation: 3 consecutive slides ({i+1}, {i+2}, {i+3}) have layout '{l1}'")

    return issues


def repair_slide_deck_deterministic(deck: SlideDeck, requested_count: int = 10) -> Tuple[SlideDeck, List[str]]:
    """
    Apply programmatic repairs for bullet length, bullet count, short_title, and layout rhythm.
    Returns (repaired_deck, applied_repair_messages).
    """
    repairs: List[str] = []
    slides = deck.slides or []

    # 1. Truncate bullet words to max 14 words
    for idx, s in enumerate(slides):
        new_bullets = []
        for b in s.bullets:
            words = b.strip().split()
            if len(words) > 14:
                truncated = " ".join(words[:14])
                new_bullets.append(truncated)
                repairs.append(f"Slide {idx + 1}: truncated bullet from {len(words)} to 14 words")
            else:
                new_bullets.append(b.strip())
        s.bullets = new_bullets

    # 2. Fix rhythm: no 3 consecutive identical layouts (except title/summary_grid)
    for i in range(len(slides) - 2):
        if slides[i].layout == slides[i + 1].layout == slides[i + 2].layout:
            if slides[i + 1].layout == "bullets":
                if slides[i + 1].blocks:
                    slides[i + 1].layout = "two_blocks"
                elif slides[i + 1].stat:
                    slides[i + 1].layout = "big_stat"
                repairs.append(f"Adjusted slide {i + 2} layout to break 3-in-a-row rhythm")

    # 3. Clean equations: strip $ delimiters and \begin{equation}
    for idx, s in enumerate(slides):
        if s.equation:
            cleaned = s.equation.strip()
            cleaned = re.sub(r"^\$+|\$+$", "", cleaned).strip()
            cleaned = re.sub(r"\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}", r"\1", cleaned, flags=re.DOTALL).strip()
            if cleaned != s.equation:
                s.equation = cleaned
                repairs.append(f"Slide {idx + 1}: cleaned equation delimiters")

    return deck, repairs


@retry_on_rate_limit(max_retries=2, initial_backoff=2.0)
def repair_single_slide_with_llm(
    slide: Slide,
    problem: str,
    llm: Optional[Any] = None,
    keys_to_scrub: Optional[list[str]] = None,
) -> Slide:
    """Ask active LLM to repair a single slide with a local issue."""
    if llm is None:
        llm = slides_llm()
    prompt = (
        f"The following slide has an issue:\n"
        f"Problem: {problem}\n"
        f"Current slide JSON:\n{slide.model_dump_json(indent=2)}\n\n"
        "Please fix the slide to strictly adhere to the schema and requirements. Return valid JSON only."
    )
    messages = [
        {"role": "system", "content": SLIDES_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    try:
        structured_llm = llm.with_structured_output(Slide, method="json_mode")
        return structured_llm.invoke(messages)
    except Exception:
        resp = llm.invoke(messages)
        raw = str(resp.content if hasattr(resp, "content") else resp)
        cleaned = _clean_json_text(raw)
        data = json.loads(cleaned)
        return Slide.model_validate(data)


# ---------------------------------------------------------------------------
# Text Sanitizer, LaTeX Escaping & Beamer Renderer
# ---------------------------------------------------------------------------

def sanitize_text(text: Optional[str], is_code: bool = False) -> str:
    """
    Sanitize text before rendering (both Beamer and PPTX):
    - U+2010, U+2011, U+2012 -> '-'
    - U+202F, U+00A0, U+2009 -> ' '
    - U+200B -> removed
    - Curly quotes to straight quotes in code snippets
    - If is_code: replace remaining non-ASCII characters with '?'
    """
    if text is None:
        return ""
    s = str(text)

    # Hyphens & dashes: U+2010 (hyphen), U+2011 (non-breaking hyphen), U+2012 (figure dash)
    s = s.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-")
    # Spaces: U+202F (narrow no-break space), U+00A0 (no-break space), U+2009 (thin space)
    s = s.replace("\u202f", " ").replace("\u00a0", " ").replace("\u2009", " ")
    # Zero-width space: U+200B
    s = s.replace("\u200b", "")

    if is_code:
        # Curly quotes to straight quotes
        s = s.replace("\u201c", '"').replace("\u201d", '"')
        s = s.replace("\u2018", "'").replace("\u2019", "'")
        # Replace any remaining non-ASCII characters with '?'
        s = "".join(ch if ord(ch) < 128 else "?" for ch in s)

    return s


def sanitize_slide_deck(deck: SlideDeck) -> SlideDeck:
    """Apply sanitize_text to every string field across the SlideDeck."""
    deck.title = sanitize_text(deck.title)
    if deck.subtitle:
        deck.subtitle = sanitize_text(deck.subtitle)
    deck.author = sanitize_text(deck.author or "SAGE")
    deck.short_title = sanitize_text(deck.short_title)

    if deck.design_brief:
        deck.design_brief.audience = sanitize_text(deck.design_brief.audience)
        deck.design_brief.narrative = sanitize_text(deck.design_brief.narrative)
        deck.design_brief.takeaways = [sanitize_text(t) for t in (deck.design_brief.takeaways or [])]
        if deck.design_brief.running_example:
            deck.design_brief.running_example = sanitize_text(deck.design_brief.running_example)

    for slide in deck.slides:
        slide.title = sanitize_text(slide.title)
        slide.page_job = sanitize_text(slide.page_job)
        if slide.kicker:
            slide.kicker = sanitize_text(slide.kicker)
        if slide.takeaway:
            slide.takeaway = sanitize_text(slide.takeaway)
        if slide.insight:
            slide.insight = sanitize_text(slide.insight)
        if slide.callout:
            slide.callout = sanitize_text(slide.callout)
        if slide.speaker_notes:
            slide.speaker_notes = sanitize_text(slide.speaker_notes)
        if slide.equation:
            slide.equation = sanitize_text(slide.equation)

        slide.bullets = [sanitize_text(b) for b in (slide.bullets or [])]

        if slide.blocks:
            for blk in slide.blocks:
                blk.heading = sanitize_text(blk.heading)
                blk.body = sanitize_text(blk.body)

        if slide.table:
            slide.table.headers = [sanitize_text(h) for h in (slide.table.headers or [])]
            slide.table.rows = [
                [sanitize_text(cell) for cell in row]
                for row in (slide.table.rows or [])
            ]

        if slide.code:
            slide.code.snippet = sanitize_text(slide.code.snippet, is_code=True)

        if slide.stat:
            slide.stat.value = sanitize_text(slide.stat.value)
            slide.stat.label = sanitize_text(slide.stat.label)

    return deck


def escape_latex(text: Optional[str]) -> str:
    """Escape LaTeX special characters and map mathematical/dash glyphs to math mode."""
    if not text:
        return ""
    s = sanitize_text(text, is_code=False)

    # 1. Escape special LaTeX control characters (order matters for backslash)
    s = s.replace("\\", "\\textbackslash{}")
    s = s.replace("&", "\\&")
    s = s.replace("%", "\\%")
    s = s.replace("$", "\\$")
    s = s.replace("#", "\\#")
    s = s.replace("_", "\\_")
    s = s.replace("{", "\\{")
    s = s.replace("}", "\\}")
    s = s.replace("~", "\\textasciitilde{}")
    s = s.replace("^", "\\textasciicircum{}")

    # 2. Map mathematical and typographic characters to math mode / TeX commands
    s = s.replace("≈", r"\ensuremath{\approx}")
    s = s.replace("×", r"\ensuremath{\times}")
    s = s.replace("→", r"\ensuremath{\rightarrow}")
    s = s.replace("←", r"\ensuremath{\leftarrow}")
    s = s.replace("≤", r"\ensuremath{\leq}")
    s = s.replace("≥", r"\ensuremath{\geq}")
    s = s.replace("±", r"\ensuremath{\pm}")
    s = s.replace("µ", r"\ensuremath{\mu}")
    s = s.replace("μ", r"\ensuremath{\mu}")
    s = s.replace("–", "--")   # en-dash U+2013
    s = s.replace("—", "---")  # em-dash U+2014
    s = s.replace("≠", r"\ensuremath{\neq}")
    s = s.replace("÷", r"\ensuremath{\div}")
    s = s.replace("°", r"\ensuremath{^\circ}")
    s = s.replace("…", r"\ldots{}")
    return s


def render_beamer(deck: SlideDeck) -> str:
    """
    Render SlideDeck into a complete Beamer LaTeX document.
    Visual language:
    - 16:9 aspect ratio
    - Navy (#272A40) headline bar with white sans-serif title text
    - Three-part navy footer: author | short_title | n / N
    - Navy header blocks with light gray body (#F2F2F2)
    - Teal callout box (#DCEEEE fill, #2A8080 text)
    - Accent colors: inputRed, kernelBlue, outputGreen, opPurple
    - Kicker and Takeaway support
    - Big stat layout
    """
    deck = sanitize_slide_deck(deck)
    author = escape_latex(deck.author or "SAGE")
    title = escape_latex(deck.title)
    subtitle = escape_latex(deck.subtitle or "")
    short_title = escape_latex(deck.short_title or deck.title[:30])

    tex: List[str] = []

    # Preamble
    tex.append(r"""\documentclass[aspectratio=169,10pt,xcolor={table}]{beamer}
\usepackage{amsmath,amssymb}
\usepackage{booktabs}
\usepackage{colortbl}
\usepackage{listings}

\usepackage{tikz}
\usepackage[most]{tcolorbox}
\usepackage{helvet}
\renewcommand{\familydefault}{\sfdefault}

% Metropolis / Navy color scheme
\definecolor{navy}{HTML}{272A40}
\definecolor{navyLight}{HTML}{3A3E59}
\definecolor{bgGray}{HTML}{F2F2F2}
\definecolor{tealBoxFill}{HTML}{DCEEEE}
\definecolor{tealBoxText}{HTML}{2A8080}
\definecolor{inputRed}{HTML}{D9534F}
\definecolor{kernelBlue}{HTML}{2980B9}
\definecolor{outputGreen}{HTML}{27AE60}
\definecolor{opPurple}{HTML}{8E44AD}

% Beamer theme settings
\setbeamertemplate{navigation symbols}{}
\setbeamertemplate{itemize items}[circle]
\setbeamercolor{normal text}{fg=navy,bg=white}
\setbeamercolor{structure}{fg=navy}

\makeatletter
% Headline / Frametitle: Dark navy bar with white text and optional kicker
\setbeamertemplate{frametitle}{
  \nointerlineskip
  \begin{beamercolorbox}[wd=\paperwidth,ht=38pt,dp=10pt,leftskip=14pt,rightskip=14pt]{navyBar}
    \color{white}
    \ifx\insertframesubtitle\@empty%
      {\fontsize{13}{15}\selectfont\textbf{\insertframetitle}}
    \else%
      {\fontsize{7.5}{9}\selectfont\color{tealBoxFill}\MakeUppercase{\insertframesubtitle}}\\[2pt]
      {\fontsize{12}{14}\selectfont\textbf{\insertframetitle}}
    \fi%

  \end{beamercolorbox}
}
\makeatother
\setbeamercolor{navyBar}{fg=white,bg=navy}


% Footline: three-part navy bar: author | short_title | n / N
\setbeamertemplate{footline}{
  \leavevmode%
  \hbox{%
  \begin{beamercolorbox}[wd=.333333\paperwidth,ht=14pt,dp=5pt,leftskip=12pt]{footBar}%
    \fontsize{7}{8}\selectfont \textbf{""" + author + r"""}
  \end{beamercolorbox}%
  \begin{beamercolorbox}[wd=.333333\paperwidth,ht=14pt,dp=5pt,center]{footBar}%
    \fontsize{7}{8}\selectfont """ + short_title + r"""
  \end{beamercolorbox}%
  \begin{beamercolorbox}[wd=.333333\paperwidth,ht=14pt,dp=5pt,rightskip=12pt]{footBar}%
    \hfill \fontsize{7}{8}\selectfont \insertframenumber{} / \inserttotalframenumber
  \end{beamercolorbox}}%
  \vskip0pt%
}
\setbeamercolor{footBar}{fg=white,bg=navy}

% Blocks: navy header strip with white text, light gray body (#F2F2F2)
\tcbset{
  navyblock/.style={
    enhanced,
    colback=bgGray,
    colframe=navy,
    coltitle=white,
    fonttitle=\bfseries\small,
    boxrule=0.6pt,
    titlerule=0pt,
    arc=3pt,
    left=6pt,right=6pt,top=4pt,bottom=4pt,
    toptitle=3pt,bottomtitle=3pt
  },
  tealcallout/.style={
    enhanced,
    colback=tealBoxFill,
    colframe=tealBoxText,
    coltext=tealBoxText,
    fontupper=\bfseries\normalsize,
    boxrule=0.8pt,
    arc=4pt,
    halign=center,
    left=10pt,right=10pt,top=6pt,bottom=6pt
  }
}

% Listings styling for code slides
\lstset{
  basicstyle=\ttfamily\scriptsize,
  backgroundcolor=\color{bgGray},
  keywordstyle=\color{kernelBlue}\bfseries,
  stringstyle=\color{outputGreen},
  commentstyle=\color{gray}\itshape,
  frame=single,
  rulecolor=\color{navyLight},
  breaklines=true,
  tabsize=2,
  showstringspaces=false
}

\title{""" + title + r"""}
\subtitle{""" + subtitle + r"""}
\author{""" + author + r"""}

\begin{document}
""")

    # Render each slide
    for s_idx, slide in enumerate(deck.slides):
        is_fragile = (slide.layout == "code")
        fragile_str = "[fragile]" if is_fragile else ""
        kicker_tex = escape_latex(slide.kicker) if slide.kicker else ""
        s_title_tex = escape_latex(slide.title)

        if slide.layout == "title":
            tex.append(r"""\begin{frame}[plain]
  \begin{tikzpicture}[remember picture,overlay]
    \fill[navy] (current page.south west) rectangle (current page.north east);
  \end{tikzpicture}
  \vspace{35pt}
  \begin{center}
    {\fontsize{20}{24}\selectfont\textbf{\color{white}""" + title + r"""}}\\[12pt]
""")
            if subtitle:
                tex.append(r"""    {\fontsize{13}{16}\selectfont\color{tealBoxFill}""" + subtitle + r"""}\\[16pt]""" + "\n")
            tex.append(r"""    \vspace{18pt}
    {\fontsize{9}{11}\selectfont\color{white}""" + author + r"""}
  \end{center}
\end{frame}
""")
            continue

        # Normal frame
        tex.append(f"\\begin{{frame}}{fragile_str}")
        if kicker_tex:
            tex.append(f"  \\framesubtitle{{{kicker_tex}}}")
        tex.append(f"  \\frametitle{{{s_title_tex}}}")
        tex.append("  \\vspace{4pt}")

        # Callout (if present on slide)
        if slide.callout:
            c_text = escape_latex(slide.callout)
            tex.append(r"""  \begin{tcolorbox}[tealcallout]
    """ + c_text + r"""
  \end{tcolorbox}
  \vspace{3pt}
""")

        # Slide Layouts
        layout = slide.layout

        if layout in ("agenda", "bullets"):
            if slide.bullets:
                tex.append("  \\begin{itemize}\\setlength{\\itemsep}{6pt}")
                for b in slide.bullets:
                    tex.append(f"    \\item {escape_latex(b)}")
                tex.append("  \\end{itemize}")

        elif layout == "big_stat":
            val = escape_latex(slide.stat.value if slide.stat else "N/A")
            lbl = escape_latex(slide.stat.label if slide.stat else "")
            tex.append(r"""  \begin{columns}[c]
    \begin{column}{0.44\textwidth}
      \begin{center}
        {\fontsize{34}{38}\selectfont\textbf{\color{outputGreen}""" + val + r"""}}\\[8pt]
        {\fontsize{11}{14}\selectfont\textbf{\color{navy}""" + lbl + r"""}}
      \end{center}
    \end{column}
    \begin{column}{0.54\textwidth}
      \begin{itemize}\setlength{\itemsep}{5pt}
""")
            for b in slide.bullets:
                tex.append(f"        \\item {escape_latex(b)}")
            tex.append(r"""      \end{itemize}
    \end{column}
  \end{columns}
""")

        elif layout == "two_blocks":
            tex.append(r"""  \begin{columns}[t]
""")
            blocks = slide.blocks[:2]
            for b in blocks:
                h = escape_latex(b.heading)
                body = escape_latex(b.body)
                tex.append(r"""    \begin{column}{0.48\textwidth}
      \begin{tcolorbox}[navyblock,title=""" + h + r"""]
        """ + body + r"""
      \end{tcolorbox}
    \end{column}
""")
            tex.append(r"""  \end{columns}
""")

        elif layout == "summary_grid":
            blocks = slide.blocks[:6]
            tex.append(r"""  \begin{columns}[t]
    \begin{column}{0.48\textwidth}
""")
            half = (len(blocks) + 1) // 2
            for b in blocks[:half]:
                tex.append(r"""      \begin{tcolorbox}[navyblock,title=""" + escape_latex(b.heading) + r"""]
        """ + escape_latex(b.body) + r"""
      \end{tcolorbox}
      \vspace{2pt}
""")
            tex.append(r"""    \end{column}
    \begin{column}{0.48\textwidth}
""")
            for b in blocks[half:]:
                tex.append(r"""      \begin{tcolorbox}[navyblock,title=""" + escape_latex(b.heading) + r"""]
        """ + escape_latex(b.body) + r"""
      \end{tcolorbox}
      \vspace{2pt}
""")
            tex.append(r"""    \end{column}
  \end{columns}
""")

        elif layout == "table":
            if slide.table and slide.table.headers:
                headers = slide.table.headers
                rows = slide.table.rows
                col_spec = " ".join(["l" for _ in headers])
                tex.append(r"""  \begin{center}
  \begin{tabular}{""" + col_spec + r"""}
    \rowcolor{navy}\color{white}\textbf{""" + "} & \\color{white}\\textbf{".join(
                    [escape_latex(h) for h in headers]
                ) + r"""} \\ \toprule
""")
                for r_idx, row in enumerate(rows[:6]):
                    r_color = "\\rowcolor{bgGray} " if r_idx % 2 == 1 else ""
                    row_cells = [escape_latex(cell) for cell in row]
                    tex.append("    " + r_color + " & ".join(row_cells) + r""" \\""")
                tex.append(r"""    \bottomrule
  \end{tabular}
  \end{center}
""")

            if slide.bullets:
                tex.append("  \\begin{itemize}\\setlength{\\itemsep}{3pt}")
                for b in slide.bullets[:2]:
                    tex.append(f"    \\item {escape_latex(b)}")
                tex.append("  \\end{itemize}")

        elif layout == "equation":
            eq = slide.equation or "E = mc^2"
            tex.append(r"""  \begin{equation*}
    """ + eq + r"""
  \end{equation*}
  \vspace{4pt}
""")
            if slide.bullets:
                tex.append("  \\begin{itemize}\\setlength{\\itemsep}{4pt}")
                for b in slide.bullets:
                    tex.append(f"    \\item {escape_latex(b)}")
                tex.append("  \\end{itemize}")

        elif layout == "code":
            snippet = slide.code.snippet if slide.code else "# code sample"
            lang = slide.code.language if slide.code and slide.code.language else "python"
            tex.append(r"""  \begin{lstlisting}[language=""" + lang + r"""]
""" + snippet + r"""
\end{lstlisting}
""")
            if slide.bullets:
                tex.append("  \\begin{itemize}\\setlength{\\itemsep}{3pt}")
                for b in slide.bullets[:2]:
                    tex.append(f"    \\item {escape_latex(b)}")
                tex.append("  \\end{itemize}")

        # Insight block (if present)
        if slide.insight:
            ins = escape_latex(slide.insight)
            tex.append(r"""  \vspace{2pt}
  \begin{tcolorbox}[navyblock,title=Key Insight]
    """ + ins + r"""
  \end{tcolorbox}
""")

        # Takeaway at bottom above footer
        if slide.takeaway:
            t_text = escape_latex(slide.takeaway)
            tex.append(r"""  \vspace{\fill}
  {\fontsize{8.5}{10}\selectfont\textbf{\color{navy}Takeaway: }""" + t_text + r"""}
""")

        tex.append("\\end{frame}\n")

    tex.append("\\end{document}\n")
    return "\n".join(tex)


# ---------------------------------------------------------------------------
# Beamer Compiler & Subprocess Execution
# ---------------------------------------------------------------------------

def find_latex_engine() -> Optional[str]:
    """Find an available LaTeX engine in system PATH or known paths."""
    # Ensure system PATH updates from registry/user env or known tools are reflected
    for extra_path in ("C:\\Tools\\Tectonic", "C:\\Program Files\\MiKTeX\\miktex\\bin\\x64"):
        if os.path.exists(extra_path) and extra_path not in os.environ.get("PATH", ""):
            os.environ["PATH"] = extra_path + os.pathsep + os.environ.get("PATH", "")

    for eng in ("tectonic", "xelatex", "latexmk", "pdflatex"):
        if shutil.which(eng):
            return eng
    return None



def compile_beamer(tex_content: str, timeout: int = 90) -> Tuple[Optional[bytes], str]:
    """
    Compile Beamer LaTeX in a temp directory using an available engine.
    Returns (pdf_bytes, log_or_error_excerpt).
    """
    engine = find_latex_engine()
    if not engine:
        return None, "No LaTeX engine found in PATH. Install tectonic, xelatex, or latexmk."

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "slides.tex")
        pdf_path = os.path.join(tmpdir, "slides.pdf")
        log_path = os.path.join(tmpdir, "slides.log")

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_content)

        eng_bin = shutil.which(engine) or engine
        if engine == "tectonic":
            cmd = [eng_bin, "-p", "slides.tex"]
        elif engine == "latexmk":
            cmd = [eng_bin, "-xelatex", "-interaction=nonstopmode", "slides.tex"]
        elif engine == "xelatex":
            cmd = [eng_bin, "-interaction=nonstopmode", "slides.tex"]
        else:
            cmd = [eng_bin, "-interaction=nonstopmode", "slides.tex"]


        try:
            res = subprocess.run(
                cmd,
                cwd=tmpdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                text=True,
            )
            stdout = res.stdout or ""
            stderr = res.stderr or ""
            combined_log = stdout + "\n" + stderr

            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                return pdf_bytes, combined_log[-3000:]

            # Failed to produce PDF
            log_content = ""
            if os.path.exists(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as lf:
                        log_content = lf.read()
                except Exception:
                    pass
            excerpt = (log_content or combined_log)[-3000:]
            return None, f"LaTeX compilation failed (code {res.returncode}):\n{excerpt}"

        except subprocess.TimeoutExpired:
            return None, f"LaTeX compilation timed out after {timeout} seconds"
        except Exception as e:
            return None, f"LaTeX execution error: {str(e)}"


def compile_with_repair(deck: SlideDeck, max_retries: int = 2) -> Tuple[Optional[bytes], str, List[str]]:
    """
    Compile Beamer PDF with slide-targeted repair loop.
    Returns (pdf_bytes, tex_content, warnings).
    """
    warnings: List[str] = []
    current_deck = deck

    for attempt in range(max_retries + 1):
        tex = render_beamer(current_deck)
        engine = find_latex_engine()
        if not engine:
            warnings.append("No LaTeX engine found in PATH. PDF generation skipped.")
            return None, tex, warnings

        pdf_bytes, log_excerpt = compile_beamer(tex)
        if pdf_bytes is not None:
            # Check for overfull warnings in log
            overfull_matches = re.findall(r"Overfull \\vbox.*|Overfull \\hbox.*", log_excerpt)
            if overfull_matches:
                warnings.extend(overfull_matches[:3])
            return pdf_bytes, tex, warnings

        # Failed: attempt repair
        if attempt < max_retries:
            logger.warning("Beamer compile attempt %d failed. Inspecting log for failing slide...", attempt + 1)
            # Find failing slide or equation
            repaired = False
            for s_idx, s in enumerate(current_deck.slides):
                if s.equation and ("Undefined control sequence" in log_excerpt or "Missing $" in log_excerpt):
                    # Local equation fix or downgrade
                    s.equation = escape_latex(s.equation)
                    warnings.append(f"Slide {s_idx + 1} equation failed compile; downgraded to escaped plain text.")
                    repaired = True
                    break

            if not repaired:
                warnings.append(f"Compile attempt {attempt + 1} failed: {log_excerpt[:200]}...")
        else:
            # Last resort
            for s_idx, s in enumerate(current_deck.slides):
                if s.equation and not s.equation.startswith("\\text"):
                    s.equation = escape_latex(s.equation)
                    warnings.append(f"Slide {s_idx + 1} equation downgraded to plain text as last resort.")
            tex = render_beamer(current_deck)
            pdf_bytes, _ = compile_beamer(tex)
            if pdf_bytes is not None:
                return pdf_bytes, tex, warnings

    return None, render_beamer(current_deck), warnings


# ---------------------------------------------------------------------------
# PPTX Renderer (python-pptx)
# ---------------------------------------------------------------------------

def render_pptx(deck: SlideDeck) -> bytes:
    """
    Render SlideDeck into an editable PPTX presentation (16:9 widescreen)
    using python-pptx. Mimics the Beamer dark navy (#272A40) theme:
    - 16:9 widescreen
    - Navy title bar with white text
    - Three-part navy footer bar
    - Teal callout box
    - Big stat layout
    - Native editable tables and shapes
    """
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.enum.text import PP_ALIGN
        from pptx.dml.color import RGBColor
        from pptx.enum.shapes import MSO_SHAPE
    except ImportError:
        raise RuntimeError("python-pptx is not installed. Run 'pip install python-pptx'.")

    prs = Presentation()
    # 16:9 widescreen dimensions
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]  # Blank layout

    # Colors
    NAVY = RGBColor(0x27, 0x2A, 0x40)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    GRAY_BG = RGBColor(0xF2, 0xF2, 0xF2)
    TEAL_BG = RGBColor(0xDC, 0xEE, 0xEE)
    TEAL_TXT = RGBColor(0x2A, 0x80, 0x80)
    GREEN = RGBColor(0x27, 0xAE, 0x60)
    deck = sanitize_slide_deck(deck)
    author = deck.author or "SAGE"
    short_title = deck.short_title or deck.title[:30]
    total_slides = len(deck.slides)

    for idx, slide in enumerate(deck.slides):
        slide_num = idx + 1
        p_slide = prs.slides.add_slide(blank_layout)

        # Title slide
        if slide.layout == "title":
            bg = p_slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
            bg.fill.solid()
            bg.fill.fore_color.rgb = NAVY
            bg.line.fill.background()

            tx = p_slide.shapes.add_textbox(Inches(1.5), Inches(2.2), Inches(10.333), Inches(3.0))
            tf = tx.text_frame
            tf.word_wrap = True

            p1 = tf.paragraphs[0]
            p1.text = deck.title
            p1.font.size = Pt(40)
            p1.font.bold = True
            p1.font.color.rgb = WHITE
            p1.alignment = PP_ALIGN.CENTER

            if deck.subtitle:
                p2 = tf.add_paragraph()
                p2.text = deck.subtitle
                p2.font.size = Pt(22)
                p2.font.color.rgb = TEAL_BG
                p2.alignment = PP_ALIGN.CENTER
                p2.space_before = Pt(14)

            p3 = tf.add_paragraph()
            p3.text = author
            p3.font.size = Pt(14)
            p3.font.color.rgb = WHITE
            p3.alignment = PP_ALIGN.CENTER
            p3.space_before = Pt(24)

            if slide.speaker_notes:
                notes_slide = p_slide.notes_slide
                text_frame = notes_slide.notes_text_frame
                text_frame.text = slide.speaker_notes
            continue


        # Normal Slide: Navy Title Bar
        header = p_slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(1.1))
        header.fill.solid()
        header.fill.fore_color.rgb = NAVY
        header.line.fill.background()

        htx = p_slide.shapes.add_textbox(Inches(0.8), Inches(0.1), Inches(11.7), Inches(0.9))
        htf = htx.text_frame
        htf.word_wrap = True

        if slide.kicker:
            kp = htf.paragraphs[0]
            kp.text = slide.kicker.upper()
            kp.font.size = Pt(9)
            kp.font.bold = True
            kp.font.color.rgb = TEAL_BG

            tp = htf.add_paragraph()
            tp.text = slide.title
            tp.font.size = Pt(20)
            tp.font.bold = True
            tp.font.color.rgb = WHITE
        else:
            tp = htf.paragraphs[0]
            tp.text = slide.title
            tp.font.size = Pt(22)
            tp.font.bold = True
            tp.font.color.rgb = WHITE

        # Footer Bar
        footer = p_slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(7.05), Inches(13.333), Inches(0.45))
        footer.fill.solid()
        footer.fill.fore_color.rgb = NAVY
        footer.line.fill.background()

        ftx = p_slide.shapes.add_textbox(Inches(0.8), Inches(7.05), Inches(11.7), Inches(0.4))
        ftf = ftx.text_frame
        fp = ftf.paragraphs[0]
        fp.text = f"{author}   |   {short_title}   |   {slide_num} / {total_slides}"
        fp.font.size = Pt(10)
        fp.font.color.rgb = WHITE
        fp.alignment = PP_ALIGN.CENTER

        # Content area start
        content_top = Inches(1.3)

        # Callout (if present)
        if slide.callout:
            callout = p_slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.5), content_top, Inches(10.333), Inches(0.7)
            )
            callout.fill.solid()
            callout.fill.fore_color.rgb = TEAL_BG
            callout.line.color.rgb = TEAL_TXT
            callout.line.width = Pt(1)
            ctf = callout.text_frame
            ctf.word_wrap = True
            cp = ctf.paragraphs[0]
            cp.text = slide.callout
            cp.font.size = Pt(13)
            cp.font.bold = True
            cp.font.color.rgb = TEAL_TXT
            cp.alignment = PP_ALIGN.CENTER
            content_top = Inches(2.1)

        layout = slide.layout

        if layout in ("agenda", "bullets"):
            tx = p_slide.shapes.add_textbox(Inches(1.0), content_top, Inches(11.333), Inches(4.5))
            tf = tx.text_frame
            tf.word_wrap = True
            for b_idx, b in enumerate(slide.bullets):
                p = tf.paragraphs[0] if b_idx == 0 else tf.add_paragraph()
                p.text = f"•  {b}"
                p.font.size = Pt(18)
                p.font.color.rgb = NAVY
                p.space_after = Pt(14)

        elif layout == "big_stat":
            val = slide.stat.value if slide.stat else "N/A"
            lbl = slide.stat.label if slide.stat else ""

            # Left column: Stat & label
            stx = p_slide.shapes.add_textbox(Inches(1.0), content_top + Inches(0.5), Inches(4.8), Inches(3.0))
            stf = stx.text_frame
            stf.word_wrap = True
            sp1 = stf.paragraphs[0]
            sp1.text = val
            sp1.font.size = Pt(54)
            sp1.font.bold = True
            sp1.font.color.rgb = GREEN
            sp1.alignment = PP_ALIGN.CENTER

            sp2 = stf.add_paragraph()
            sp2.text = lbl
            sp2.font.size = Pt(18)
            sp2.font.bold = True
            sp2.font.color.rgb = NAVY
            sp2.alignment = PP_ALIGN.CENTER
            sp2.space_before = Pt(10)

            # Right column: Bullets
            btx = p_slide.shapes.add_textbox(Inches(6.2), content_top + Inches(0.4), Inches(6.0), Inches(4.0))
            btf = btx.text_frame
            btf.word_wrap = True
            for b_idx, b in enumerate(slide.bullets):
                p = btf.paragraphs[0] if b_idx == 0 else btf.add_paragraph()
                p.text = f"•  {b}"
                p.font.size = Pt(16)
                p.font.color.rgb = NAVY
                p.space_after = Pt(12)

        elif layout == "two_blocks":
            left_pos = [Inches(1.0), Inches(6.8)]
            for b_idx, b in enumerate(slide.blocks[:2]):
                box = p_slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE, left_pos[b_idx], content_top + Inches(0.2), Inches(5.5), Inches(4.2)
                )
                box.fill.solid()
                box.fill.fore_color.rgb = GRAY_BG
                box.line.color.rgb = NAVY
                box.line.width = Pt(1)
                btf = box.text_frame
                btf.word_wrap = True

                hp = btf.paragraphs[0]
                hp.text = b.heading
                hp.font.size = Pt(17)
                hp.font.bold = True
                hp.font.color.rgb = NAVY
                hp.space_after = Pt(10)

                bp = btf.add_paragraph()
                bp.text = b.body
                bp.font.size = Pt(14)
                bp.font.color.rgb = NAVY

        elif layout == "summary_grid":
            blocks = slide.blocks[:6]
            cols = 2
            rows_cnt = (len(blocks) + 1) // 2
            box_w = Inches(5.5)
            box_h = Inches(1.2)
            for b_idx, b in enumerate(blocks):
                c = b_idx % cols
                r = b_idx // cols
                x = Inches(1.0) if c == 0 else Inches(6.8)
                y = content_top + Inches(0.2) + (r * Inches(1.4))
                box = p_slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, box_w, box_h)
                box.fill.solid()
                box.fill.fore_color.rgb = GRAY_BG
                box.line.color.rgb = NAVY
                box.line.width = Pt(0.8)
                btf = box.text_frame
                btf.word_wrap = True

                hp = btf.paragraphs[0]
                hp.text = b.heading
                hp.font.size = Pt(13)
                hp.font.bold = True
                hp.font.color.rgb = NAVY

                bp = btf.add_paragraph()
                bp.text = b.body
                bp.font.size = Pt(11)
                bp.font.color.rgb = NAVY

        elif layout == "table":
            if slide.table and slide.table.headers:
                headers = slide.table.headers
                rows = slide.table.rows[:5]
                n_rows = len(rows) + 1
                n_cols = len(headers)
                t_shape = p_slide.shapes.add_table(
                    n_rows, n_cols, Inches(1.0), content_top + Inches(0.2), Inches(11.333), Inches(3.0)
                )
                tbl = t_shape.table
                for c_idx, h in enumerate(headers):
                    cell = tbl.cell(0, c_idx)
                    cell.text = h
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = NAVY
                    for p in cell.text_frame.paragraphs:
                        p.font.size = Pt(13)
                        p.font.bold = True
                        p.font.color.rgb = WHITE
                for r_idx, row in enumerate(rows):
                    for c_idx, val in enumerate(row[:n_cols]):
                        cell = tbl.cell(r_idx + 1, c_idx)
                        cell.text = val
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = WHITE if r_idx % 2 == 0 else GRAY_BG
                        for p in cell.text_frame.paragraphs:
                            p.font.size = Pt(12)
                            p.font.color.rgb = NAVY

        elif layout == "equation":
            # Display math equation as text box
            eq_text = slide.equation or "E = mc^2"
            eq_box = p_slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, Inches(2.0), content_top + Inches(0.2), Inches(9.333), Inches(1.4)
            )
            eq_box.fill.solid()
            eq_box.fill.fore_color.rgb = GRAY_BG
            eq_box.line.color.rgb = NAVY
            eq_box.line.width = Pt(1)
            etf = eq_box.text_frame
            ep = etf.paragraphs[0]
            ep.text = eq_text
            ep.font.size = Pt(20)
            ep.font.bold = True
            ep.font.color.rgb = NAVY
            ep.alignment = PP_ALIGN.CENTER

            if slide.bullets:
                tx = p_slide.shapes.add_textbox(Inches(1.5), content_top + Inches(1.8), Inches(10.333), Inches(2.5))
                tf = tx.text_frame
                tf.word_wrap = True
                for b_idx, b in enumerate(slide.bullets):
                    p = tf.paragraphs[0] if b_idx == 0 else tf.add_paragraph()
                    p.text = f"•  {b}"
                    p.font.size = Pt(15)
                    p.font.color.rgb = NAVY
                    p.space_after = Pt(8)

        elif layout == "code":
            snippet = slide.code.snippet if slide.code else "# code sample"
            cbox = p_slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, Inches(1.5), content_top + Inches(0.2), Inches(10.333), Inches(3.2)
            )
            cbox.fill.solid()
            cbox.fill.fore_color.rgb = GRAY_BG
            cbox.line.color.rgb = NAVY
            cbox.line.width = Pt(1)
            ctf = cbox.text_frame
            ctf.word_wrap = True
            cp = ctf.paragraphs[0]
            cp.text = snippet
            cp.font.name = "Consolas"
            cp.font.size = Pt(12)
            cp.font.color.rgb = NAVY

        # Key Insight at bottom
        if slide.insight:
            ibox = p_slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0), Inches(5.8), Inches(11.333), Inches(0.65)
            )
            ibox.fill.solid()
            ibox.fill.fore_color.rgb = GRAY_BG
            ibox.line.color.rgb = NAVY
            ibox.line.width = Pt(1)
            itf = ibox.text_frame
            itf.word_wrap = True
            ip = itf.paragraphs[0]
            ip.text = f"Key Insight:  {slide.insight}"
            ip.font.size = Pt(12)
            ip.font.bold = True
            ip.font.color.rgb = NAVY

        # Takeaway at bottom above footer
        if slide.takeaway:
            ttx = p_slide.shapes.add_textbox(Inches(1.0), Inches(6.5), Inches(11.333), Inches(0.45))
            ttf = ttx.text_frame
            ttf.word_wrap = True
            tp = ttf.paragraphs[0]
            tp.text = f"Takeaway:  {slide.takeaway}"
            tp.font.size = Pt(12)
            tp.font.bold = True
            tp.font.color.rgb = NAVY

        # Speaker notes
        if slide.speaker_notes:
            notes_slide = p_slide.notes_slide
            text_frame = notes_slide.notes_text_frame
            text_frame.text = slide.speaker_notes

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Full Pipeline Orchestration
# ---------------------------------------------------------------------------

def generate_slides_for_blog(
    job_id: str,
    slide_count: int = 10,
    audience: Optional[str] = None,
    llm_selection: Optional[LLMSelection] = None,
) -> None:
    """
    Main background pipeline:
    1. Validate blog job is done
    2. Plan SlideDeck JSON via active LLM (stage: planning, 10-30%)
    3. Lint & deterministic repair (stage: planning, 40%)
    4. Render PPTX (stage: writing_latex, 60%)
    5. Render Beamer & compile PDF with repair loop (stage: compiling, 85%)
    6. Store artifacts in job record (stage: done, 100%)
    """
    raw_key = (
        llm_selection.api_key.get_secret_value()
        if (llm_selection and llm_selection.api_key)
        else None
    )
    keys_to_scrub = [raw_key] if raw_key else []

    blog_job = get_job(job_id)
    if not blog_job or not blog_job.result:
        update_slide_job(
            job_id,
            status="error",
            stage="planning",
            error=f"Associated blog job '{job_id}' result not found.",
        )
        return

    try:
        blog_result = BlogResult(**blog_job.result)
    except Exception as e:
        update_slide_job(
            job_id,
            status="error",
            stage="planning",
            error=f"Failed to parse blog result: {e}",
        )
        return

    update_slide_job(
        job_id,
        status="running",
        stage="planning",
        progress=10,
        title=blog_result.title,
    )

    warnings: List[str] = []

    # Resolve active LLM & planner input cap
    provider = (llm_selection.provider or "groq").strip().lower() if llm_selection else "groq"
    provider_cfg = PROVIDER_REGISTRY.get(provider, PROVIDER_REGISTRY["groq"])
    token_cap = provider_cfg["profile"].get("planner_input_token_cap")

    try:
        active_llm = get_llm("slides", llm_selection)
    except Exception as exc:
        scrubbed = scrub_exception_chain(exc, keys=keys_to_scrub)
        logger.error("Failed to initialize slides LLM: %s", scrubbed)
        update_slide_job(job_id, status="error", stage="planning", error=scrubbed)
        return

    # 1. Plan deck
    try:
        deck = plan_slides_deck(
            blog_result,
            slide_count=slide_count,
            audience=audience,
            llm=active_llm,
            planner_input_token_cap=token_cap,
            keys_to_scrub=keys_to_scrub,
        )
    except Exception as e:
        scrubbed = scrub_exception_chain(e, keys=keys_to_scrub)
        logger.error("Slide planning failed: %s", scrubbed)
        update_slide_job(
            job_id,
            status="error",
            stage="planning",
            error=scrubbed,
        )
        return

    update_slide_job(job_id, progress=35, slide_count=len(deck.slides))

    # 2. Lint & deterministic repair
    deck, det_repairs = repair_slide_deck_deterministic(deck, requested_count=slide_count)
    warnings.extend(det_repairs)

    issues = lint_slide_deck(deck, requested_count=slide_count)
    if issues:
        warnings.extend(issues)

    # Sanitize all string fields across SlideDeck before rendering
    deck = sanitize_slide_deck(deck)

    update_slide_job(job_id, stage="writing_latex", progress=55, warnings=warnings)

    # 3. PPTX Rendering
    pptx_bytes: Optional[bytes] = None
    try:
        pptx_bytes = render_pptx(deck)
    except Exception as e:
        warnings.append(f"PPTX render warning: {str(e)}")
        logger.warning("PPTX render error: %s", e)

    update_slide_job(job_id, stage="compiling", progress=75, warnings=warnings)

    # 4. Beamer Compile with Repair Loop
    pdf_bytes, tex_content, compile_warnings = compile_with_repair(deck, max_retries=2)
    warnings.extend(compile_warnings)

    # 5. Finalize Job
    update_slide_job(
        job_id,
        status="done",
        stage="done",
        progress=100,
        slide_count=len(deck.slides),
        warnings=warnings,
        pdf_bytes=pdf_bytes,
        pptx_bytes=pptx_bytes,
        tex_content=tex_content,
        title=deck.title,
        deck=deck.model_dump(),
    )
    logger.info("Slide job %s completed successfully with %d slides", job_id, len(deck.slides))
