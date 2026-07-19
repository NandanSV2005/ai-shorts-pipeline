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

def count_narration_words(script_text: str) -> int:
    """Extracts spoken narration and returns total word count."""
    narration_lines = []
    for line in script_text.splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        # Skip scene directives and markers in brackets
        if line_str.startswith("[") and line_str.endswith("]"):
            continue
        narration_lines.append(line_str)
    full_narration = " ".join(narration_lines)
    return len(full_narration.split())

def run_script_writer(date_str: str, force: bool = False) -> str:
    output_dir = get_output_dir(date_str)
    topic_file = output_dir / "topic.json"
    research_file = output_dir / "research.md"
    script_file = output_dir / "script.txt"

    if not topic_file.exists() or not research_file.exists():
        raise FileNotFoundError(
            f"Topic/Research files not found for {date_str}. Please run steps 01 and 02 first."
        )

    if script_file.exists() and not force:
        print(f"[03 Script Writer] Script already exists for {date_str}. Skipping.")
        with open(script_file, "r", encoding="utf-8") as f:
            return f.read()

    # Load inputs
    with open(topic_file, "r", encoding="utf-8") as f:
        topic_data = json.load(f)
    with open(research_file, "r", encoding="utf-8") as f:
        research_content = f.read()

    title = topic_data.get("title")
    visual_style = topic_data.get("visual_style", "vintage")

    system_instruction = (
        "You are an elite YouTube Documentarian and Scriptwriter. Your style is engaging, pacing is key, "
        "and you hook the viewer in the first 5 seconds. You intersperse narration with bracketed visual cues "
        "on separate lines (e.g. [SCENE: Vintage black and white footage of the invention moving]). "
        "Keep the narration flowing, conversational, and split into clear paragraphs. Avoid using bullet points "
        "in the narrator's dialogue."
    )

    prompt = (
        f"Topic Title: {title}\n"
        f"Visual Style: {visual_style}\n\n"
        f"Research Report:\n{research_content}\n\n"
        "Draft a complete YouTube script under 4 minutes. Follow these guidelines exactly:\n"
        "1. Write the script with explicit sections: [HOOK], [BODY], and [CTA/OUTRO].\n"
        "2. Place visual scene descriptions inside brackets on their own line (e.g. `[SCENE: description of visuals]`).\n"
        "3. Every paragraph of narration MUST be preceded by a matching [SCENE: ...] directive specifying what to show on screen.\n"
        "4. The narrator text must be conversational and read naturally. Do not write narrator speech as list items.\n"
        "5. TARGET DURATION AND WORD COUNT: The spoken narration MUST be under 550 words total (~3.5 minutes total narration).\n"
        "6. COMPLETE STORY PATH: The script must be a complete, self-contained story with a clear hook, a building middle section, "
        "and a satisfying resolution/ending. Do not cut off mid-narrative. If the topic is broad, narrow the scope of the story "
        "rather than compressing it into a rushed summary.\n"
        "7. SHORTS SPLIT POINT: Place a single `[SPLIT POINT]` directive on its own line exactly where the story should split into "
        "Part 1 and Part 2. This must be a natural cliffhanger cut (usually at the end of the build section, right before the resolution)."
    )

    print(f"[03 Script Writer] Writing script for: '{title}'...")
    script_content = generate_text(prompt, system_instruction=system_instruction)

    # Word count validation & automated LLM revision loop
    word_cap = 550
    words = count_narration_words(script_content)
    attempts = 0
    max_attempts = 2
    
    while words > word_cap and attempts < max_attempts:
        attempts += 1
        print(f"[03 Script Writer] Script is too long ({words} words, cap is {word_cap}). Asking LLM to revise (Attempt {attempts}/{max_attempts})...")
        
        revision_prompt = (
            f"The following script is too long ({words} words). The limit is {word_cap} words of spoken narration "
            f"to keep the video under 4 minutes. Please edit the script to make the narration more concise, "
            f"while preserving all bracketed visual scene directives, the hook, the CTA/outro, and crucially, "
            f"the [SPLIT POINT] marker. It must remain a complete story with a beginning, middle, and satisfying end.\n\n"
            f"Script to revise:\n{script_content}"
        )
        script_content = generate_text(revision_prompt, system_instruction=system_instruction)
        words = count_narration_words(script_content)
        
    if words > word_cap:
        raise ValueError(
            f"Generated script exceeds the narration cap of {word_cap} words even after revision attempts. "
            f"Actual word count: {words}. Please try again or adjust your topic."
        )

    # Output split point verification context in logs
    if "[SPLIT POINT]" in script_content:
        lines = script_content.splitlines()
        for idx, line in enumerate(lines):
            if line.strip() == "[SPLIT POINT]":
                print("\n[03 Script Writer] [SPLIT POINT] detected successfully!")
                print(f"   Context Before: {lines[idx-1] if idx > 0 else 'Start of script'}")
                print(f"   Context After:  {lines[idx+1] if idx < len(lines)-1 else 'End of script'}\n")
                break
    else:
        print("\n[03 Script Writer] [WARNING] No [SPLIT POINT] marker found in script! The video will be split exactly in half by duration.\n")

    with open(script_file, "w", encoding="utf-8") as f:
        f.write(script_content.strip())

    print(f"[03 Script Writer] Successfully saved script to: {script_file} ({words} narration words)")
    return script_content

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Write script for the daily video.")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date directory name (YYYY-MM-DD). Defaults to today's date.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of the script, overwriting any existing one.",
    )
    args = parser.parse_args()

    try:
        content = run_script_writer(args.date, args.force)
        print(content[:500] + "\n... [truncated] ...")
    except Exception as e:
        print(f"[ERROR] Step 03 Script Writer failed: {e}", file=sys.stderr)
        sys.exit(1)
