import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to sys.path so we can import from backend
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import NICHE, get_output_dir
from backend.database import get_past_topics, add_topic
from backend.llm import generate_text, clean_json_response

def generate_video_topic(date_str: str, force: bool = False, manual_topic: str | None = None) -> dict:
    output_dir = get_output_dir(date_str)
    topic_file = output_dir / "topic.json"

    # Check if file exists and we are not forcing
    if topic_file.exists() and not force:
        should_skip = True
        if manual_topic:
            try:
                with open(topic_file, "r", encoding="utf-8") as f:
                    cached_title = json.load(f).get("title")
                    if cached_title and cached_title.lower() != manual_topic.lower():
                        should_skip = False
            except Exception:
                should_skip = False
                
        if should_skip:
            print(f"[01 Topic Generator] Topic already exists for {date_str}. Loading from file.")
            with open(topic_file, "r", encoding="utf-8") as f:
                return json.load(f)

    if manual_topic:
        print(f"[01 Topic Generator] Using manually provided topic override: '{manual_topic}'")
        topic_data = {
            "title": manual_topic,
            "concept": f"Manually specified topic about: {manual_topic}.",
            "keywords": [manual_topic.lower()],
            "visual_style": "bold Reddit text style, gameplay video background"
        }
        # Write to dated output folder
        with open(topic_file, "w", encoding="utf-8") as f:
            json.dump(topic_data, f, indent=2, ensure_ascii=False)

        # Save to SQLite database to prevent reuse
        inserted = add_topic(date_str, NICHE, topic_data["title"], topic_data["concept"], topic_data["keywords"])
        if inserted:
            print(f"[01 Topic Generator] Saved manual topic to database for {date_str}.")
        else:
            print(f"[01 Topic Generator] Note: Topic for {date_str} already recorded in DB.")
            
        print(f"[01 Topic Generator] Successfully processed manual topic: '{topic_data['title']}'")
        return topic_data

    # Fetch past topics to avoid duplicates
    past_topics = get_past_topics(NICHE)
    past_topics_summary = "\n".join(
        [f"- Title: {t['title']} | Concept: {t['concept']}" for t in past_topics]
    ) if past_topics else "None"

    system_instruction = (
        f"You are a YouTube Content Director specializing in the niche: '{NICHE}'. "
        "Your goal is to suggest one single, highly engaging, highly dramatic premise for a daily video. "
        "Each topic must focus on a compelling first-person fictional scenario in the Reddit-story style "
        "(AITA, relationship drama, malicious compliance, family drama, workplace stories). Ensure the premise has "
        "strong emotional hooks, high tension, and a major twist or cliffhanger."
    )

    prompt = (
        f"Generate a single new video topic premise. To prevent duplicates, DO NOT suggest any of these past topics:\n"
        f"{past_topics_summary}\n\n"
        "Provide your response as a raw JSON object with EXACTLY the following keys (do not include any conversational text outside the JSON):\n"
        "{\n"
        '  "title": "A short, viral, dramatic title phrased in first-person (e.g. AITA for Refusing to Give Up My Seat to a Pregnant Woman?).",\n'
        '  "concept": "A 2-3 sentence summary of the scenario, highlighting the setup, conflict, and the twist.",\n'
        '  "keywords": ["3 to 5 relevant search keywords/phrases for gameplay or video category search"],\n'
        '  "visual_style": "A brief description of the visual mood, style, and text overlay color scheme (e.g. high-contrast bold white text, red highlight alert tags, gameplay background)."\n'
        "}"
    )

    print(f"[01 Topic Generator] Querying LLM for a new topic in niche: '{NICHE}'...")
    raw_response = generate_text(prompt, system_instruction=system_instruction)
    clean_response = clean_json_response(raw_response)

    try:
        topic_data = json.loads(clean_response)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse LLM JSON response. Raw output was:\n{raw_response}")
        raise e

    # Ensure all required keys exist
    required_keys = ["title", "concept", "keywords", "visual_style"]
    for key in required_keys:
        if key not in topic_data:
            topic_data[key] = "" if key != "keywords" else []

    # Write to dated output folder
    with open(topic_file, "w", encoding="utf-8") as f:
        json.dump(topic_data, f, indent=2, ensure_ascii=False)

    # Save to SQLite database to prevent reuse
    inserted = add_topic(date_str, NICHE, topic_data["title"], topic_data["concept"], topic_data["keywords"])
    if inserted:
        print(f"[01 Topic Generator] Saved new topic to database for {date_str}.")
    else:
        print(f"[01 Topic Generator] Note: Topic for {date_str} already recorded in DB.")

    print(f"[01 Topic Generator] Successfully generated topic: '{topic_data['title']}'")
    return topic_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a daily YouTube video topic.")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date directory name (YYYY-MM-DD). Defaults to today's date.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of the topic, overwriting any existing one.",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Manually specify a topic to override auto-generation.",
    )
    args = parser.parse_args()

    try:
        topic = generate_video_topic(args.date, args.force, args.topic)
        print(json.dumps(topic, indent=2))
    except Exception as e:
        print(f"[ERROR] Step 01 Topic Generator failed: {e}", file=sys.stderr)
        sys.exit(1)
