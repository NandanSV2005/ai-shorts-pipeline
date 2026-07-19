#!/usr/bin/env python3
import sys
import re
import sqlite3
import shutil
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent))

from backend.config import (
    BASE_DIR,
    OUTPUTS_DIR,
    ASSETS_AUDIO_DIR,
    ASSETS_IMAGES_DIR,
    ASSETS_THUMBNAILS_DIR,
    LOGS_DIR,
    DB_PATH,
    ASSETS_GAMEPLAY_DIR
)

def get_latest_date():
    dates = set()
    # Check outputs dir
    if OUTPUTS_DIR.exists():
        for item in OUTPUTS_DIR.iterdir():
            if item.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", item.name):
                dates.add(item.name)
    # Check db
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT date_str FROM topics")
            for row in cursor.fetchall():
                if re.match(r"^\d{4}-\d{2}-\d{2}$", row[0]):
                    dates.add(row[0])
            cursor.execute("SELECT date_str FROM runs")
            for row in cursor.fetchall():
                if re.match(r"^\d{4}-\d{2}-\d{2}$", row[0]):
                    dates.add(row[0])
            conn.close()
        except Exception:
            pass
    return max(dates) if dates else None

def main():
    parser = argparse.ArgumentParser(description="Clean up generated content and database records.")
    parser.add_argument(
        "--keep-latest",
        action="store_true",
        help="Keep the output folder and database records of the most recent test run/date, clearing everything older."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass confirmation prompt."
    )
    args = parser.parse_args()

    latest_date = None
    if args.keep_latest:
        latest_date = get_latest_date()
        if latest_date:
            print(f"Identified most recent run date to keep: {latest_date}")
        else:
            print("No run dates found to keep. Proceeding with full cleanup.")

    # 1. Output directories to delete
    outputs_to_delete = []
    if OUTPUTS_DIR.exists():
        for item in OUTPUTS_DIR.iterdir():
            if item.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", item.name):
                if args.keep_latest and item.name == latest_date:
                    continue
                outputs_to_delete.append(item)

    # 2. Asset files to delete
    asset_dirs = [ASSETS_AUDIO_DIR, ASSETS_IMAGES_DIR, ASSETS_THUMBNAILS_DIR, LOGS_DIR]
    files_to_delete = []
    for folder in asset_dirs:
        if folder.exists():
            for child in folder.iterdir():
                files_to_delete.append(child)

    # 3. Database records to delete
    db_topics_to_delete = []
    db_runs_to_delete = []
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            if args.keep_latest and latest_date:
                cursor.execute("SELECT date_str, title FROM topics WHERE date_str != ?", (latest_date,))
                db_topics_to_delete = cursor.fetchall()
                cursor.execute("SELECT date_str, topic_title FROM runs WHERE date_str != ?", (latest_date,))
                db_runs_to_delete = cursor.fetchall()
            else:
                cursor.execute("SELECT date_str, title FROM topics")
                db_topics_to_delete = cursor.fetchall()
                cursor.execute("SELECT date_str, topic_title FROM runs")
                db_runs_to_delete = cursor.fetchall()
            conn.close()
        except Exception as e:
            print(f"Warning: Could not query database: {e}")

    total_files = len(outputs_to_delete) + len(files_to_delete)
    total_db = len(db_topics_to_delete) + len(db_runs_to_delete)

    if total_files == 0 and total_db == 0:
        print("Nothing to clean up.")
        return

    print("=== Pipeline Cleanup Utility ===")
    print("The following generated content will be DELETED:")
    if outputs_to_delete:
        print(f"\nOutput folders under {OUTPUTS_DIR.relative_to(BASE_DIR)}/:")
        for folder in outputs_to_delete:
            print(f"  - {folder.name}/")
    if files_to_delete:
        print(f"\nFiles/Folders inside assets/ and logs/:")
        for file_path in files_to_delete:
            print(f"  - {file_path.relative_to(BASE_DIR)}")
    if db_topics_to_delete:
        print(f"\nDatabase records in 'topics' table:")
        for row in db_topics_to_delete:
            print(f"  - Date: {row[0]}, Title: '{row[1]}'")
    if db_runs_to_delete:
        print(f"\nDatabase records in 'runs' table:")
        for row in db_runs_to_delete:
            print(f"  - Date: {row[0]}, Run status/topic: '{row[1]}'")

    print("\nProtected folders (NOT touched):")
    print(f"  - assets/gameplay/ ({ASSETS_GAMEPLAY_DIR.relative_to(BASE_DIR)})")
    print("  - backend/bin/ (FFmpeg binaries)")

    print(f"\nSummary: This will delete {total_files} filesystem item(s) and {total_db} database record(s).")

    if not args.force:
        confirm = input("Confirm deletion? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Cleanup cancelled.")
            return

    print("\nPerforming deletion...")

    # Delete output folders
    for folder in outputs_to_delete:
        try:
            shutil.rmtree(folder)
            print(f"Deleted output folder: {folder.relative_to(BASE_DIR)}")
        except Exception as e:
            print(f"Error deleting folder {folder}: {e}")

    # Delete files inside asset dirs & logs
    for file_path in files_to_delete:
        try:
            if file_path.is_file():
                file_path.unlink()
                print(f"Deleted file: {file_path.relative_to(BASE_DIR)}")
            elif file_path.is_dir():
                shutil.rmtree(file_path)
                print(f"Deleted directory: {file_path.relative_to(BASE_DIR)}")
        except Exception as e:
            print(f"Error deleting file/folder {file_path}: {e}")

    # Delete DB records
    if DB_PATH.exists() and (db_topics_to_delete or db_runs_to_delete):
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            if args.keep_latest and latest_date:
                cursor.execute("DELETE FROM topics WHERE date_str != ?", (latest_date,))
                cursor.execute("DELETE FROM runs WHERE date_str != ?", (latest_date,))
            else:
                cursor.execute("DELETE FROM topics")
                cursor.execute("DELETE FROM runs")
            conn.commit()
            conn.close()
            print(f"Cleared {len(db_topics_to_delete)} topic records and {len(db_runs_to_delete)} run records from database.")
        except Exception as e:
            print(f"Error updating database: {e}")

    print("\nCleanup completed successfully.")

if __name__ == "__main__":
    main()
