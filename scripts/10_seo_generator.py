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

def generate_seo_metadata(date_str: str, force: bool = False, parts: int | None = None) -> dict:
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

    series = metadata.get("series")
    episode = metadata.get("episode")
    
    series_info = ""
    if series:
        ep_info = f" Episode {episode}" if episode is not None else ""
        series_info = (
            f"Note: This video is part of a series named '{series}'{ep_info}.\n"
            f"Ensure descriptions reference that it is part of the '{series}' series.\n"
        )

    parts_count = metadata.get("parts", 1)

    system_instruction = (
        "You are an expert YouTube SEO Optimization specialist. Your goal is to maximize click-through rate (CTR) "
        "and search rankings for AI Reddit-style stories and confessions (AITA, relationship drama, etc.). "
        "You write highly dramatic, hook-driven, click-worthy titles (e.g. phrased as direct questions or dramatic statements) "
        "and thorough description texts containing a short disclosure noting the story is fictional."
    )

    if parts_count == 2:
        prompt = (
            f"Story Premise: {title_concept}\n"
            f"Concept/Outline: {concept}\n"
            f"{series_info}"
            f"Script Text:\n{script_content}\n\n"
            "Generate high-performing YouTube Shorts SEO metadata for both Part 1 and Part 2 of this split video.\n"
            "Provide your response as a raw JSON object with exactly the following keys (do not include any markdown fences or conversational text outside the JSON):\n"
            "{\n"
            '  "title": "A single overall video title summarizing the whole story (under 60 characters, e.g. phrased as a question or dramatic first-person statement like: AITA for refusing to give up my seat?).",\n'
            '  "part1": {\n'
            '    "title": "A punchy click-worthy title for Part 1 (under 60 characters, teasing Part 2, e.g. ending with Part 1 or Part 1/2).",\n'
            '    "description": "A description for Part 1 (150-250 words) with a dramatic hook, relevant hashtags, and a brief disclosure line: \'This is a fictional story for entertainment purposes.\'.",\n'
            '    "tags": ["10 search terms"]\n'
            '  },\n'
            '  "part2": {\n'
            '    "title": "A title for Part 2 (under 60 characters, indicating continuation, e.g., ending with Part 2 or Part 2/2).",\n'
            '    "description": "A description for Part 2 (150-250 words) referencing that it is the conclusion of Part 1 and containing the disclosure line: \'This is a fictional story for entertainment purposes.\'.",\n'
            '    "tags": ["10 search terms"]\n'
            '  }\n'
            "}"
        )
    else:
        prompt = (
            f"Story Premise: {title_concept}\n"
            f"Concept/Outline: {concept}\n"
            f"{series_info}"
            f"Script Text:\n{script_content}\n\n"
            "Generate high-performing YouTube Shorts SEO metadata for this video.\n"
            "Provide your response as a raw JSON object with exactly the following keys (do not include any markdown fences or conversational text outside the JSON):\n"
            "{\n"
            '  "title": "A punchy click-worthy YouTube title summarizing the whole story (under 60 characters, e.g. phrased as a question or dramatic first-person statement like: AITA for refusing to give up my seat?).",\n'
            '  "description": "A description (150-250 words) with a dramatic hook, relevant hashtags, and a brief disclosure line: \'This is a fictional story for entertainment purposes.\'.",\n'
            '  "tags": ["10 search terms"]\n'
            "}"
        )

    if MOCK_PIPELINE:
        print("[10 SEO] [MOCK] Generating placeholder SEO metadata...")
        if parts_count == 2:
            seo_data = {
                "title": f"{title_concept} (Shorts Edit)",
                "part1": {
                    "title": f"{title_concept} - Part 1",
                    "description": f"Is this story wrong? Here is Part 1 of {title_concept}! This is a fictional story for entertainment purposes. #redditstories #aita #shorts",
                    "tags": ["redditstories", "aita", "relationshipdrama", "shorts", "part1"]
                },
                "part2": {
                    "title": f"{title_concept} - Part 2",
                    "description": f"Here is the conclusion of {title_concept}! This is a fictional story for entertainment purposes. #redditstories #aita #shorts #conclusion",
                    "tags": ["redditstories", "aita", "relationshipdrama", "shorts", "part2"]
                }
            }
        else:
            seo_data = {
                "title": f"{title_concept} (Shorts Edit)",
                "description": f"Is this story wrong? Here is the full story of {title_concept}! This is a fictional story for entertainment purposes. #redditstories #aita #shorts",
                "tags": ["redditstories", "aita", "relationshipdrama", "shorts"]
            }
    else:
        print(f"[10 SEO] Querying LLM for optimized SEO metadata (parts={parts_count})...")
        raw_response = generate_text(prompt, system_instruction=system_instruction)
        clean_response = clean_json_response(raw_response)

        try:
            seo_data = json.loads(clean_response)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse SEO JSON response. Raw output was:\n{raw_response}")
            raise e

    # Append series / episode metadata to titles, descriptions & tags if present
    series = metadata.get("series")
    episode = metadata.get("episode")
    
    if series:
        ep_str = f" Ep. {episode}" if episode is not None else ""
        title_suffix = f" | {series}{ep_str}"
        
        # Update top-level title
        main_title = seo_data.get("title", title)
        if title_suffix not in main_title:
            seo_data["title"] = f"{main_title}{title_suffix}"
            
        if parts_count == 2:
            for part in ["part1", "part2"]:
                if part in seo_data:
                    part_data = seo_data[part]
                    if isinstance(part_data, dict):
                        # Update part title
                        p_title = part_data.get("title", "")
                        if isinstance(p_title, str) and title_suffix not in p_title:
                            part_data["title"] = f"{p_title}{title_suffix}"
                        
                        # Update description
                        p_desc = part_data.get("description", "")
                        if isinstance(p_desc, str):
                            desc_line = f"This video is part of the '{series}' series."
                            if desc_line.lower() not in p_desc.lower():
                                if "#" in p_desc:
                                    p_parts = p_desc.split("#", 1)
                                    p_desc = f"{p_parts[0].rstrip()}\n\n{desc_line}\n\n#{p_parts[1]}"
                                else:
                                    p_desc = f"{p_desc}\n\n{desc_line}"
                                part_data["description"] = p_desc
                        
                        # Update tags
                        p_tags = part_data.get("tags", [])
                        if isinstance(p_tags, list):
                            series_tag = series.lower()
                            if series_tag not in [str(t).lower() for t in p_tags]:
                                p_tags.append(series_tag)
                            if episode is not None:
                                ep_tag = f"{series_tag} ep {episode}"
                                if ep_tag not in [str(t).lower() for t in p_tags]:
                                    p_tags.append(ep_tag)
                            part_data["tags"] = p_tags
        else:
            # Update description for single-part video
            p_desc = seo_data.get("description", "")
            if isinstance(p_desc, str):
                desc_line = f"This video is part of the '{series}' series."
                if desc_line.lower() not in p_desc.lower():
                    if "#" in p_desc:
                        p_parts = p_desc.split("#", 1)
                        p_desc = f"{p_parts[0].rstrip()}\n\n{desc_line}\n\n#{p_parts[1]}"
                    else:
                        p_desc = f"{p_desc}\n\n{desc_line}"
                    seo_data["description"] = p_desc
            
            # Update tags for single-part video
            p_tags = seo_data.get("tags", [])
            if isinstance(p_tags, list):
                series_tag = series.lower()
                if series_tag not in [str(t).lower() for t in p_tags]:
                    p_tags.append(series_tag)
                if episode is not None:
                    ep_tag = f"{series_tag} ep {episode}"
                    if ep_tag not in [str(t).lower() for t in p_tags]:
                        p_tags.append(ep_tag)
                seo_data["tags"] = p_tags

    # Update metadata
    metadata["seo"] = seo_data
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"[10 SEO] Successfully generated and saved SEO metadata.")
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
    parser.add_argument(
        "--parts",
        type=int,
        default=None,
        help="Number of video parts (1 or 2).",
    )
    args = parser.parse_args()

    try:
        seo = generate_seo_metadata(args.date, args.force, args.parts)
        print(json.dumps(seo, indent=2))
    except Exception as e:
        print(f"[ERROR] Step 10 SEO Generator failed: {e}", file=sys.stderr)
        sys.exit(1)
