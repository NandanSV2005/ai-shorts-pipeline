import os
import sys
import argparse
import subprocess
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent))

from backend.config import (
    get_output_dir,
    NOTIFICATION_PROVIDER,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    SMTP_SERVER,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    NOTIFY_EMAIL,
    BASE_DIR
)
from backend.database import update_run_status

def run_step(script_name: str, date_str: str, force: bool = False, topic: str | None = None) -> None:
    """Executes a numbered step script as a subprocess to preserve isolation."""
    script_path = BASE_DIR / "scripts" / script_name
    print(f"\n======================================================================")
    print(f"RUNNING STEP: {script_name}")
    print(f"======================================================================")
    
    cmd = [sys.executable, str(script_path), "--date", date_str]
    if force:
        cmd.append("--force")
    if script_name == "01_topic_generator.py" and topic:
        cmd.extend(["--topic", topic])
        
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"Pipeline failed at step {script_name} (Exit code: {result.returncode})")

def send_notification(date_str: str, status: str, error_msg: str | None = None) -> None:
    """Dispatches pipeline notifications via email, telegram, or logs to console."""
    output_dir = get_output_dir(date_str)
    metadata_file = output_dir / "metadata.json"
    
    title = "Unknown Topic"
    warnings = []
    
    # Load metadata if it exists to build a detailed report
    if metadata_file.exists():
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
                title = meta.get("seo", {}).get("title", "Topic generated")
                fact_checks = meta.get("fact_check", [])
                for check in fact_checks:
                    if check.get("status") in ("FLAGGED", "UNVERIFIED"):
                        warnings.append(f"- [{check.get('status')}] {check.get('claim')}: {check.get('explanation')}")
        except Exception:
            pass

    # Build report body
    body_lines = [
        f"YouTube Content Pipeline Run: {date_str}",
        f"Status: {status.upper()}",
    ]
    if status == "completed":
        body_lines.extend([
            f"Video Title: {title}",
            f"Output Folder: {output_dir.resolve()}",
            f"Fact-Check Warnings: {len(warnings)}"
        ])
        if warnings:
            body_lines.append("\nFact-Check Warnings List:")
            body_lines.extend(warnings)
    else:
        body_lines.append(f"Error Details: {error_msg}")

    msg_content = "\n".join(body_lines)
    
    # Dispatch based on provider
    if NOTIFICATION_PROVIDER == "telegram" and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        print("[Orchestrator] Sending Telegram notification...")
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg_content}
        try:
            import requests  # type: ignore
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"[Orchestrator] [WARNING] Telegram send failed: {e}")
            
    elif NOTIFICATION_PROVIDER == "email" and SMTP_SERVER and NOTIFY_EMAIL:
        print("[Orchestrator] Sending Email notification...")
        mime_msg = MIMEText(msg_content)
        mime_msg["Subject"] = f"YouTube Pipeline Status - {status.upper()} - {date_str}"
        mime_msg["From"] = SMTP_USER
        mime_msg["To"] = NOTIFY_EMAIL
        
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(mime_msg)
        except Exception as e:
            print(f"[Orchestrator] [WARNING] Email send failed: {e}")
            
    else:
        print(f"\n[Orchestrator] Pipeline execution report for {date_str}:")
        print("----------------------------------------------------------------------")
        print(msg_content)
        print("----------------------------------------------------------------------")

def execute_pipeline(date_str: str, force: bool = False, topic: str | None = None, series: str | None = None, episode: int | None = None, parts: int = 1) -> None:
    print(f"Starting YouTube Automation Pipeline Run for: {date_str}")
    
    output_dir = get_output_dir(date_str)
    topic_file = output_dir / "topic.json"
    metadata_file = output_dir / "metadata.json"
    
    # Auto-force if configuration changes
    if not force:
        if topic and topic_file.exists():
            try:
                with open(topic_file, "r", encoding="utf-8") as f:
                    old_title = json.load(f).get("title")
                    if old_title and old_title.lower() != topic.lower():
                        print(f"[Orchestrator] Detected topic change from '{old_title}' to '{topic}'. Auto-forcing regeneration.")
                        force = True
            except Exception:
                pass
        if metadata_file.exists():
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    old_meta = json.load(f)
                    if series and old_meta.get("series") != series:
                        print(f"[Orchestrator] Detected series change from '{old_meta.get('series')}' to '{series}'. Auto-forcing regeneration.")
                        force = True
                    if episode is not None and old_meta.get("episode") != episode:
                        print(f"[Orchestrator] Detected episode change from '{old_meta.get('episode')}' to '{episode}'. Auto-forcing regeneration.")
                        force = True
                    if old_meta.get("parts", 1) != parts:
                        print(f"[Orchestrator] Detected parts configuration change from '{old_meta.get('parts', 1)}' to '{parts}'. Auto-forcing regeneration.")
                        force = True
            except Exception:
                pass

    # Pre-initialize metadata with series, episode & parts info so subsequent steps can load them
    metadata_dict = {}
    if metadata_file.exists():
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata_dict = json.load(f)
        except Exception:
            pass
            
    metadata_dict["series"] = series if series else None
    metadata_dict["episode"] = episode if episode is not None else None
    metadata_dict["parts"] = parts
    
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata_dict, f, indent=2, ensure_ascii=False)
        
    update_run_status(date_str, "Running Pipeline", "pending", metadata_dict)
    
    steps = [
        "01_topic_generator.py",
        "02_research_agent.py",
        "03_script_writer.py",
        "04_fact_checker.py",
        "05_voice_generator.py",
        "06_scene_planner.py",
        "07_video_editor.py",
        "08_subtitle_generator.py",
        "09_thumbnail_generator.py",
        "10_seo_generator.py"
    ]
    
    topic_title = "Unknown"
    
    try:
        # Run all steps sequentially
        for step in steps:
            run_step(step, date_str, force, topic)
            
        # Get final topic title from topic.json
        topic_file = output_dir / "topic.json"
        if topic_file.exists():
            with open(topic_file, "r", encoding="utf-8") as f:
                topic_title = json.load(f).get("title", "Unknown")
        
        # Load final metadata
        if metadata_file.exists():
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata_dict = json.load(f)

        # Update SQLite runs table
        update_run_status(date_str, topic_title, "completed", metadata_dict)
        print(f"\n[Orchestrator] Pipeline completed successfully for date {date_str}!")
        
        # Notify
        send_notification(date_str, "completed")
        
    except Exception as e:
        print(f"\n[ERROR] Pipeline run failed: {e}", file=sys.stderr)
        
        # Try merging failure state into existing metadata.json (preserves series/episode)
        failed_metadata = {"error": str(e)}
        if metadata_file.exists():
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    existing_meta = json.load(f)
                    existing_meta.update(failed_metadata)
                    failed_metadata = existing_meta
            except Exception:
                pass
                
        update_run_status(date_str, topic_title, "failed", failed_metadata)
        send_notification(date_str, "failed", str(e))
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Content Pipeline Orchestrator.")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Target date directory (YYYY-MM-DD). Defaults to today's date.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force execution of all pipeline steps, overwriting any cached step outputs.",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Manual topic override to skip auto-generation.",
    )
    parser.add_argument(
        "--series",
        type=str,
        default=None,
        help="Optional series name for batch production.",
    )
    parser.add_argument(
        "--episode",
        type=int,
        default=None,
        help="Optional episode number within the series.",
    )
    parser.add_argument(
        "--parts",
        type=int,
        choices=[1, 2],
        default=1,
        help="Number of parts to generate/render (1 for single video, 2 for split).",
    )
    args = parser.parse_args()

    execute_pipeline(args.date, args.force, args.topic, args.series, args.episode, args.parts)
