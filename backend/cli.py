#!/usr/bin/env python3
"""
Thin CLI wrapper — calls the same generate_blog() function used by the FastAPI backend.

Usage (run from the backend/ directory):
    python cli.py --topic "Agentic AI in education"
    python cli.py --topic "..." --tone casual --length long --audience "product managers"
    python cli.py --topic "..." --no-web      # skip web research
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as `python cli.py` from the backend/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.agent import generate_blog
from app.core.jobs import create_job, get_job


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a technical blog post using the AI agent."
    )
    parser.add_argument("--topic", required=True, help="Blog topic or working title")
    parser.add_argument(
        "--tone", default="professional",
        help="Writing tone, e.g. casual, professional, conversational (default: professional)"
    )
    parser.add_argument(
        "--length", default="medium", choices=["short", "medium", "long"],
        help="Approximate blog length (default: medium)"
    )
    parser.add_argument(
        "--style", default="blog",
        choices=["blog", "tutorial", "explainer", "news_roundup", "comparison"],
        help="Blog format/style (default: blog)"
    )
    parser.add_argument(
        "--audience", default="developers",
        help="Target audience description (default: developers)"
    )
    parser.add_argument(
        "--no-web", action="store_true",
        help="Disable web research (closed-book mode)"
    )
    parser.add_argument(
        "--as-of", default=None, metavar="YYYY-MM-DD",
        help="Override the as-of date for recency calculations"
    )
    args = parser.parse_args()

    record = create_job()
    job_id = record.job_id

    print(f"[cli] Job started: {job_id}")
    print(f"[cli] Topic     : {args.topic}")
    print(f"[cli] Tone      : {args.tone}")
    print(f"[cli] Length    : {args.length}")
    print(f"[cli] Style     : {args.style}")
    print(f"[cli] Audience  : {args.audience}")
    print(f"[cli] Web       : {not args.no_web}")
    print()

    generate_blog(
        job_id=job_id,
        topic=args.topic,
        tone=args.tone,
        length=args.length,
        style=args.style,
        audience=args.audience,
        use_web=not args.no_web,
        as_of=args.as_of,
    )

    record = get_job(job_id)
    if record.status == "error":
        print(f"[cli] ERROR: {record.error}", file=sys.stderr)
        sys.exit(1)

    result = record.result
    print(result["draft"])
    print(f"\n{'=' * 70}")
    print(f"Title    : {result['title']}")
    print(f"Sections : {len(result['outline'])}")
    print(f"Sources  : {len(result['sources'])}")
    print(f"~Words   : {len(result['draft'].split())}")


if __name__ == "__main__":
    main()
