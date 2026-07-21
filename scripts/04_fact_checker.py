import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
import json

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import get_output_dir, MOCK_PIPELINE
from backend.llm import generate_text, clean_json_response

def run_fact_checker(date_str: str, force: bool = False) -> list:
    output_dir = get_output_dir(date_str)
    script_file = output_dir / "script.txt"
    research_file = output_dir / "research.md"
    metadata_file = output_dir / "metadata.json"

    if not script_file.exists() or not research_file.exists():
        raise FileNotFoundError(
            f"Script/Research files not found for {date_str}. Please run steps 01-03 first."
        )

    # Load existing metadata if present
    metadata = {}
    if metadata_file.exists():
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except json.JSONDecodeError:
            pass

    # If already fact-checked and not forcing, skip
    if "fact_check" in metadata and not force:
        print(f"[04 Fact Checker] Fact check results already exist in metadata.json for {date_str}. Skipping.")
        return metadata["fact_check"]

    with open(script_file, "r", encoding="utf-8") as f:
        script_content = f.read()
    with open(research_file, "r", encoding="utf-8") as f:
        research_content = f.read()

    system_instruction = (
        "You are an analytical, objective Story Consistency Checker. Your job is to extract key narrative details "
        "and plot points from a script, compare them against the story outline, and check for any internal "
        "contradictions, timeline discrepancies, or character detail changes (e.g. ages, names, relations, or "
        "established events changing partway through). "
        "You classify details as VERIFIED (consistent with the outline and itself), FLAGGED (internal contradiction, "
        "timeline error, or character change detected), or UNVERIFIED (plot hole or detail not established in the outline)."
    )

    prompt = (
        "Compare the following Script against the Story Outline and check for narrative consistency and timeline accuracy. "
        "Extract 3-5 major narrative claims or details from the script and verify them.\n\n"
        f"Story Outline:\n{research_content}\n\n"
        f"Script:\n{script_content}\n\n"
        "Provide your analysis as a raw JSON array of objects (do not include conversational text or markdown blocks outside the JSON):\n"
        "[\n"
        "  {\n"
        '    "claim": "The narrative detail, character profile, or timeline statement checked.",\n'
        '    "status": "VERIFIED or FLAGGED or UNVERIFIED",\n'
        '    "explanation": "Provide a detailed reason explaining the consistency or identifying the exact contradiction/plot hole."\n'
        "  }\n"
        "]"
    )

    if MOCK_PIPELINE:
        print("[04 Fact Checker] [MOCK] Generating placeholder fact check results...")
        # Get title from topic.json if loaded
        topic_title = "The Flying Platform Hoverboard"
        try:
            with open(output_dir / "topic.json", "r", encoding="utf-8") as f:
                topic_title = json.load(f).get("title", topic_title)
        except Exception:
            pass
            
        fact_check_results = [
            {
                "claim": "The narrator is a bricklayer who was physically exhausted after a 12-hour shift.",
                "status": "VERIFIED",
                "explanation": "Consistent with character profile and timeline in the story outline."
            },
            {
                "claim": "The narrator's partner supported them from the beginning.",
                "status": "FLAGGED",
                "explanation": "Contradiction: the script states the partner was horrified, told them to apologize, and stopped returning texts."
            }
        ]
    else:
        print(f"[04 Fact Checker] Extracting and checking claims against research...")
        raw_response = generate_text(prompt, system_instruction=system_instruction)
        clean_response = clean_json_response(raw_response)

        try:
            fact_check_results = json.loads(clean_response)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse Fact Checker JSON response. Raw output was:\n{raw_response}")
            raise e

    # Update metadata and save
    metadata["fact_check"] = fact_check_results
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"[04 Fact Checker] Fact checking complete. Results saved to metadata.json.")

    # Surface flags to console
    flagged_count = 0
    for idx, claim in enumerate(fact_check_results):
        status = claim.get("status", "UNVERIFIED")
        if status in ("FLAGGED", "UNVERIFIED"):
            flagged_count += 1
            print(f"  [WARNING] Claim {idx+1}: {claim.get('claim')}")
            print(f"      Status: {status}")
            print(f"      Details: {claim.get('explanation')}")

    if flagged_count == 0:
        print("  [OK] All checked claims verified successfully.")
    else:
        print(f"  [!] Fact-check finished with {flagged_count} warnings. Review metadata.json before uploading.")

    return fact_check_results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fact check the video script.")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date directory name (YYYY-MM-DD). Defaults to today's date.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of the fact check, overwriting any existing one.",
    )
    args = parser.parse_args()

    try:
        results = run_fact_checker(args.date, args.force)
    except Exception as e:
        print(f"[ERROR] Step 04 Fact Checker failed: {e}", file=sys.stderr)
        sys.exit(1)
