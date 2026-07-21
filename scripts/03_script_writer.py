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

    metadata_file = output_dir / "metadata.json"
    parts_count = 1
    if metadata_file.exists():
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                parts_count = json.load(f).get("parts", 1)
        except Exception:
            pass

    title = topic_data.get("title")
    visual_style = topic_data.get("visual_style", "vintage")

    system_instruction = (
        "You are an elite creative writer and storyteller. Your style is engaging, conversational, and "
        "perfectly emulates first-person Reddit-post confessions (like AITA, relationship drama, or workplace revenge). "
        "You hook the viewer in the first 3 seconds, intersperse narration with bracketed gameplay visual cues "
        "on separate lines (e.g. [SCENE: Gameplay showing fast parkour movements]), and maintain dramatic tension."
    )

    split_instruction = ""
    if parts_count == 2:
        split_instruction = (
            "7. Cliffhanger & Split Point: Place a single `[SPLIT POINT]` directive on its own line exactly where the story should split into Part 1 and Part 2. This must be a genuine, dramatic cliffhanger right before the twist or final resolution."
        )
    else:
        split_instruction = (
            "7. Do NOT include any [SPLIT POINT] directive. The script should be a single continuous narrative without any splitting markers."
        )

    prompt = (
        f"Story Premise: {title}\n"
        f"Visual Style: {visual_style}\n\n"
        f"Story Outline/Plan:\n{research_content}\n\n"
        "Draft a complete first-person YouTube script under 4 minutes. Follow these guidelines exactly:\n"
        "1. Style: Write in the first-person, confessional Reddit-post narration style (e.g. 'My fiancé and I were supposed to get married in three weeks, until I found out...', 'So this happened last month and I\'m still not over it...'). The tone must sound like someone reading their own real Reddit post aloud.\n"
        "2. Hook: Start with a natural opening hook in the first 3-5 seconds (e.g. starting mid-action or with the most shocking line before giving context).\n"
        "3. Structure: Write the script with explicit section markers: [HOOK], [BODY], and [CTA/OUTRO].\n"
        "4. Visuals: Place visual scene descriptions inside brackets on their own line (e.g. `[SCENE: Description of gameplay visuals matching the intensity of the scene]`). Every paragraph of narration MUST be preceded by a matching [SCENE: ...] directive.\n"
        "5. Word Count: The spoken narration MUST be under 550 words total to keep the video under 4 minutes.\n"
        "6. Complete Story: The script must be a complete, self-contained story with a clear hook, escalating conflict, and satisfying resolution.\n"
        f"{split_instruction}"
    )

    print(f"[03 Script Writer] Writing script for: '{title}' (parts={parts_count})...")
    script_content = generate_text(prompt, system_instruction=system_instruction)

    # Word count validation & automated LLM revision loop
    word_cap = 550
    words = count_narration_words(script_content)
    attempts = 0
    max_attempts = 2
    
    while words > word_cap and attempts < max_attempts:
        attempts += 1
        print(f"[03 Script Writer] Script is too long ({words} words, cap is {word_cap}). Asking LLM to revise (Attempt {attempts}/{max_attempts})...")
        
        split_point_instruction = ""
        if parts_count == 2:
            split_point_instruction = "and crucially, the [SPLIT POINT] marker. "
        else:
            split_point_instruction = "Do NOT include any [SPLIT POINT] marker. "

        revision_prompt = (
            f"The following script is too long ({words} words). The limit is {word_cap} words of spoken narration "
            f"to keep the video under 4 minutes. Please edit the script to make the narration more concise, "
            f"while preserving all bracketed visual scene directives, the hook, the CTA/outro, {split_point_instruction}"
            f"It must remain a complete story with a beginning, middle, and satisfying end.\n\n"
            f"Script to revise:\n{script_content}"
        )
        script_content = generate_text(revision_prompt, system_instruction=system_instruction)
        words = count_narration_words(script_content)
        
    if words > word_cap:
        raise ValueError(
            f"Generated script exceeds the narration cap of {word_cap} words even after revision attempts. "
            f"Actual word count: {words}. Please try again or adjust your topic."
        )

    # Programmatically strip [SPLIT POINT] if we are generating a single part
    if parts_count == 1:
        script_content = script_content.replace("[SPLIT POINT]\n", "").replace("[SPLIT POINT]", "")

    # Output split point verification context in logs
    if parts_count == 2:
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
