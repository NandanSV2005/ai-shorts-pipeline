import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
import json

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import get_output_dir
from backend.llm import generate_text

def run_research(date_str: str, force: bool = False) -> str:
    output_dir = get_output_dir(date_str)
    topic_file = output_dir / "topic.json"
    research_file = output_dir / "research.md"

    if not topic_file.exists():
        raise FileNotFoundError(
            f"Topic file not found for {date_str}. Please run 01_topic_generator.py first."
        )

    if research_file.exists() and not force:
        print(f"[02 Research Agent] Research already exists for {date_str}. Skipping.")
        with open(research_file, "r", encoding="utf-8") as f:
            return f.read()

    with open(topic_file, "r", encoding="utf-8") as f:
        topic_data = json.load(f)

    title = topic_data.get("title")
    concept = topic_data.get("concept")
    keywords = ", ".join(topic_data.get("keywords", []))

    system_instruction = (
        "You are an expert historical researcher and investigator. Your job is to gather and compile "
        "comprehensive, accurate, and detailed factual research reports on obscure 20th-century failed inventions. "
        "Focus on: Background (Who, When, Where, Why), Design & Specifications, Performance Claims, and specific "
        "engineering/usage details on why it failed or rolled back."
    )

    prompt = (
        f"Topic Title: {title}\n"
        f"Topic Concept: {concept}\n"
        f"Keywords: {keywords}\n\n"
        "Generate a detailed research report on this topic. Structure your response in Markdown as follows:\n\n"
        "# Research Report: [Topic Name]\n\n"
        "## Background\n"
        "- Clear, bulleted historical background including inventors, dates, and motivations.\n\n"
        "## Technical Specifications & Design\n"
        "- Mechanics, materials, power sources, dimensions, controls, and layout details.\n\n"
        "## Claims & Performance\n"
        "- Speeds, capabilities, or benefits claimed by the inventor versus documented test results.\n\n"
        "## Why it Failed\n"
        "- Mechanical, safety, environmental, steering, or cost issues that caused the invention to fail."
    )

    print(f"[02 Research Agent] Gathering research for: '{title}'...")
    research_content = generate_text(prompt, system_instruction=system_instruction)

    with open(research_file, "w", encoding="utf-8") as f:
        f.write(research_content.strip())

    print(f"[02 Research Agent] Successfully saved research report to: {research_file}")
    return research_content

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Research the daily video topic.")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date directory name (YYYY-MM-DD). Defaults to today's date.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of the research report, overwriting any existing one.",
    )
    args = parser.parse_args()

    try:
        content = run_research(args.date, args.force)
        print(content[:500] + "\n... [truncated] ...")
    except Exception as e:
        print(f"[ERROR] Step 02 Research Agent failed: {e}", file=sys.stderr)
        sys.exit(1)
