import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import get_output_dir, MOCK_PIPELINE
from backend.llm import generate_text, clean_json_response

def generate_seo_metadata(date_str: str, force: bool = False) -> dict:
    output_dir = get_output_dir(date_str)
    topic_file = output_dir / "topic.json"
    script_file = output_dir / "script.txt"
    metadata_file = output_dir / "metadata.json"

    if not topic_file.exists() or not script_file.exists() or not metadata_file.exists():
        raise FileNotFoundError(f"Missing input files for step 10 on date {date_str}. Run previous steps first.")

    # Load existing metadata
    with open(metadata_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    if "seo" in metadata and not force:
        print(f"[10 SEO] SEO metadata already exists in metadata.json for {date_str}. Skipping.")
        return metadata["seo"]

    # Load topic and script contents
    with open(topic_file, "r", encoding="utf-8") as f:
        topic_data = json.load(f)
    with open(script_file, "r", encoding="utf-8") as f:
        script_content = f.read()

    title_concept = topic_data.get("title", "")
    concept = topic_data.get("concept", "")

    system_instruction = (
        "You are an expert YouTube SEO Optimization specialist. Your goal is to maximize click-through rate (CTR) "
        "and search rankings for historical documentary videos. You write compelling, click-worthy titles "
        "and thorough, keyword-rich descriptions using standard YouTube best practices."
    )

    prompt = (
        f"Original Topic Title: {title_concept}\n"
        f"Concept: {concept}\n"
        f"Script Text:\n{script_content}\n\n"
        "Generate high-performing YouTube Shorts SEO metadata for both Part 1 and Part 2 of this split video.\n"
        "Provide your response as a raw JSON object with exactly the following keys (do not include any markdown fences or conversational text outside the JSON):\n"
        "{\n"
        '  "title": "A single overall video title summarizing the whole story (under 60 characters).",\n'
        '  "part1": {\n'
        '    "title": "A punchy click-worthy title for Part 1 (under 60 characters, teasing Part 2, e.g. ending with Part 1 or Part 1/2).",\n'
        '    "description": "A description for Part 1 (150-250 words) with a hook and relevant hashtags.",\n'
        '    "tags": ["10 search terms"]\n'
        '  },\n'
        '  "part2": {\n'
        '    "title": "A title for Part 2 (under 60 characters, indicating continuation, e.g., ending with Part 2 or Part 2/2).",\n'
        '    "description": "A description for Part 2 (150-250 words) referencing that it is the conclusion of Part 1.",\n'
        '    "tags": ["10 search terms"]\n'
        '  }\n'
        "}"
    )

    if MOCK_PIPELINE:
        print("[10 SEO] [MOCK] Generating placeholder SEO metadata...")
        seo_data = {
            "title": f"{title_concept} (Shorts Edit)",
            "part1": {
                "title": f"{title_concept} - Part 1",
                "description": f"Discover the secret history of {title_concept}! This was a wild failed invention of the 20th century. #history #shorts",
                "tags": ["history", "failed tech", "shorts", "part1"]
            },
            "part2": {
                "title": f"{title_concept} - Part 2",
                "description": f"Here is the conclusion and ultimate fate of {title_concept}! Why did it fail? #history #shorts #conclusion",
                "tags": ["history", "failed tech", "shorts", "part2"]
            }
        }
    else:
        print(f"[10 SEO] Querying LLM for optimized SEO metadata...")
        raw_response = generate_text(prompt, system_instruction=system_instruction)
        clean_response = clean_json_response(raw_response)

        try:
            seo_data = json.loads(clean_response)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse SEO JSON response. Raw output was:\n{raw_response}")
            raise e

    # Update metadata
    metadata["seo"] = seo_data
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"[10 SEO] Successfully generated and appended SEO metadata to metadata.json.")
    return seo_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate YouTube SEO metadata.")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date directory name (YYYY-MM-DD). Defaults to today's date.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of the SEO metadata, overwriting any existing one.",
    )
    args = parser.parse_args()

    try:
        seo = generate_seo_metadata(args.date, args.force)
        print(json.dumps(seo, indent=2))
    except Exception as e:
        print(f"[ERROR] Step 10 SEO Generator failed: {e}", file=sys.stderr)
        sys.exit(1)
