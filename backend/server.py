import os
import sys
import re
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Add project root directory to Python path to allow running backend directly as a script
sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import subprocess
from backend.config import (
    BASE_DIR,
    OUTPUTS_DIR,
    DB_PATH,
    LOGS_DIR
)

# Global execution process state
active_process = {
    "process": None,
    "date_str": None,
    "log_file": None
}

app = FastAPI(title="YouTube Automation Pipeline Dashboard")

# Enable CORS for local convenience
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StatusUpdate(BaseModel):
    status: str

@app.get("/api/runs")
def list_runs():
    runs_map = {}
    
    # 1. Scan outputs directory
    if OUTPUTS_DIR.exists():
        for item in OUTPUTS_DIR.iterdir():
            if item.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", item.name):
                date_str = item.name
                metadata_file = item / "metadata.json"
                metadata = {}
                if metadata_file.exists():
                    try:
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                    except Exception:
                        pass
                
                has_video = (item / "video.mp4").exists()
                has_thumbnail = (item / "thumbnail.png").exists()
                has_script = (item / "script.txt").exists()
                
                seo_title = metadata.get("seo", {}).get("title")
                if not seo_title:
                    topic_file = item / "topic.json"
                    if topic_file.exists():
                        try:
                            with open(topic_file, "r", encoding="utf-8") as f:
                                seo_title = json.load(f).get("title")
                        except Exception:
                            pass
                
                warnings_count = 0
                for check in metadata.get("fact_check", []):
                    if check.get("status") in ("FLAGGED", "UNVERIFIED"):
                        warnings_count += 1
                        
                runs_map[date_str] = {
                    "date": date_str,
                    "title": seo_title or f"Run: {date_str}",
                    "approval_status": metadata.get("approval_status", "unreviewed"),
                    "has_video": has_video,
                    "has_thumbnail": has_thumbnail,
                    "has_script": has_script,
                    "warnings_count": warnings_count,
                    "series": metadata.get("series"),
                    "episode": metadata.get("episode")
                }
                
    # 2. Check DB runs table
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT date_str, topic_title, metadata_json, series, episode FROM runs")
            for row in cursor.fetchall():
                date_str = row[0]
                topic_title = row[1]
                metadata_json = row[2]
                series_col = row[3]
                episode_col = row[4]
                
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                    continue
                try:
                    db_meta = json.loads(metadata_json)
                except Exception:
                    db_meta = {}
                
                approval_status = db_meta.get("approval_status", "unreviewed")
                
                series_val = series_col if series_col is not None else db_meta.get("series")
                episode_val = episode_col if episode_col is not None else db_meta.get("episode")
                
                warnings_count = 0
                for check in db_meta.get("fact_check", []):
                    if check.get("status") in ("FLAGGED", "UNVERIFIED"):
                        warnings_count += 1
                        
                if date_str not in runs_map:
                    runs_map[date_str] = {
                        "date": date_str,
                        "title": topic_title or f"Run: {date_str}",
                        "approval_status": approval_status,
                        "has_video": False,
                        "has_thumbnail": False,
                        "has_script": False,
                        "warnings_count": warnings_count,
                        "series": series_val,
                        "episode": episode_val
                    }
                else:
                    if "approval_status" not in runs_map[date_str] or runs_map[date_str]["approval_status"] == "unreviewed":
                        if approval_status != "unreviewed":
                            runs_map[date_str]["approval_status"] = approval_status
                    if not runs_map[date_str].get("series"):
                        runs_map[date_str]["series"] = series_val
                    if runs_map[date_str].get("episode") is None:
                        runs_map[date_str]["episode"] = episode_val
            conn.close()
        except Exception as e:
            print(f"Error querying DB: {e}")
            
    sorted_runs = sorted(runs_map.values(), key=lambda x: x["date"], reverse=True)
    return sorted_runs

@app.get("/api/runs/{date_str}")
def get_run_detail(date_str: str):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise HTTPException(status_code=400, detail="Invalid date format YYYY-MM-DD")
        
    output_dir = OUTPUTS_DIR / date_str
    metadata = {}
    script_content = ""
    topic_data = {}
    
    # Try reading from outputs folder
    if output_dir.exists():
        metadata_file = output_dir / "metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception:
                pass
                
        script_file = output_dir / "script.txt"
        if script_file.exists():
            try:
                with open(script_file, "r", encoding="utf-8") as f:
                    script_content = f.read()
            except Exception:
                pass
                
        topic_file = output_dir / "topic.json"
        if topic_file.exists():
            try:
                with open(topic_file, "r", encoding="utf-8") as f:
                    topic_data = json.load(f)
            except Exception:
                pass

    # Try filling in missing pieces from database
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT topic_title, metadata_json FROM runs WHERE date_str = ?", (date_str,))
            row = cursor.fetchone()
            if row:
                topic_title, metadata_json = row
                try:
                    db_meta = json.loads(metadata_json)
                except Exception:
                    db_meta = {}
                
                # Merge metadata
                for k, v in db_meta.items():
                    if k not in metadata or not metadata[k]:
                        metadata[k] = v
                        
                if "title" not in topic_data or not topic_data["title"]:
                    topic_data["title"] = topic_title
            conn.close()
        except Exception as e:
            print(f"Error reading details from SQLite: {e}")

    # Fallbacks and basic stats
    has_video = (output_dir / "video.mp4").exists() if output_dir.exists() else False
    has_thumbnail = (output_dir / "thumbnail.png").exists() if output_dir.exists() else False
    
    title = metadata.get("seo", {}).get("title") or topic_data.get("title") or f"Run: {date_str}"
    approval_status = metadata.get("approval_status", "unreviewed")
    
    return {
        "date": date_str,
        "title": title,
        "concept": topic_data.get("concept", ""),
        "approval_status": approval_status,
        "video_url": f"/outputs/{date_str}/video.mp4" if has_video else None,
        "thumbnail_url": f"/outputs/{date_str}/thumbnail.png" if has_thumbnail else None,
        "script": script_content,
        "seo": metadata.get("seo", {}),
        "fact_check": metadata.get("fact_check", []),
        "series": metadata.get("series"),
        "episode": metadata.get("episode")
    }

@app.post("/api/runs/{date_str}/status")
def update_run_status_endpoint(date_str: str, data: StatusUpdate):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise HTTPException(status_code=400, detail="Invalid date format YYYY-MM-DD")
        
    status = data.status
    if status not in ("approved", "rejected", "unreviewed"):
        raise HTTPException(status_code=400, detail="Status must be approved, rejected, or unreviewed")
        
    # 1. Update outputs/date_str/metadata.json
    output_dir = OUTPUTS_DIR / date_str
    metadata_file = output_dir / "metadata.json"
    metadata = {}
    if output_dir.exists():
        if metadata_file.exists():
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception:
                pass
        metadata["approval_status"] = status
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
            
    # 2. Update SQLite database
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT metadata_json, topic_title FROM runs WHERE date_str = ?", (date_str,))
            row = cursor.fetchone()
            if row:
                existing_meta_str, topic_title = row
                try:
                    db_meta = json.loads(existing_meta_str)
                except Exception:
                    db_meta = {}
                db_meta["approval_status"] = status
                cursor.execute(
                    "UPDATE runs SET metadata_json = ? WHERE date_str = ?",
                    (json.dumps(db_meta), date_str)
                )
            else:
                db_meta = {"approval_status": status}
                cursor.execute(
                    "INSERT INTO runs (date_str, topic_title, status, metadata_json, created_at) VALUES (?, ?, ?, ?, ?)",
                    (date_str, "Unknown", "completed", json.dumps(db_meta), datetime.now(timezone.utc).isoformat())
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error writing status to SQLite: {e}")
            
    return {"success": True, "status": status}

class GenerateRequest(BaseModel):
    date_str: str | None = None
    force: bool = False
    topic: str | None = None

@app.post("/api/generate")
def start_generation(req: GenerateRequest):
    global active_process
    
    # 1. Check if a process is already running
    if active_process["process"] is not None:
        poll_result = active_process["process"].poll()
        if poll_result is None:
            raise HTTPException(status_code=400, detail="A video generation run is already in progress.")
        else:
            # Clean up finished process log handle
            if active_process["log_file"]:
                active_process["log_file"].close()
            active_process["process"] = None
            active_process["date_str"] = None
            active_process["log_file"] = None

    # Get target date
    date_str = req.date_str
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise HTTPException(status_code=400, detail="Invalid date format YYYY-MM-DD")

    # Command
    cmd = [sys.executable, "run_pipeline.py", "--date", date_str]
    if req.force:
        cmd.append("--force")
    if req.topic:
        cmd.extend(["--topic", req.topic])

    # Open log file
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file_path = LOGS_DIR / f"generation_{date_str}.log"
    
    try:
        log_f = open(log_file_path, "w", encoding="utf-8")
        proc = subprocess.Popen(
            cmd,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            text=True,
            close_fds=True
        )
        active_process["process"] = proc
        active_process["date_str"] = date_str
        active_process["log_file"] = log_f
        return {"success": True, "date": date_str}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start pipeline: {e}")

@app.get("/api/generate/status")
def get_generation_status():
    global active_process
    
    proc = active_process["process"]
    if proc is None:
        return {"active": False, "date": None, "exit_code": None}
        
    exit_code = proc.poll()
    if exit_code is not None:
        # Closed finished handle
        if active_process["log_file"]:
            active_process["log_file"].close()
        active_process["process"] = None
        active_process["date_str"] = None
        active_process["log_file"] = None
        return {"active": False, "date": None, "exit_code": exit_code}
        
    return {"active": True, "date": active_process["date_str"], "exit_code": None}

@app.get("/api/generate/logs")
def get_generation_logs():
    global active_process
    
    # Identify target date
    date_str = active_process["date_str"]
    if not date_str:
        # Check logs directory for latest log file
        log_files = list(LOGS_DIR.glob("generation_*.log"))
        if log_files:
            latest_log = max(log_files, key=os.path.getmtime)
            try:
                return {"logs": latest_log.read_text(encoding="utf-8")}
            except Exception:
                return {"logs": ""}
        return {"logs": "No logs found."}
        
    log_file_path = LOGS_DIR / f"generation_{date_str}.log"
    if not log_file_path.exists():
        return {"logs": "Log file not created yet."}
        
    try:
        with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return {"logs": content}
    except Exception as e:
        return {"logs": f"Error reading logs: {e}"}

# Serve Frontend SPA
@app.get("/")
def read_root():
    static_index = Path("backend/static/index.html")
    if not static_index.exists():
        raise HTTPException(status_code=404, detail="index.html not found in backend/static")
    return FileResponse(static_index)

# Mount outputs/ folder to stream video and load thumbnails
if OUTPUTS_DIR.exists():
    app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")

# Mount backend/static folder for scripts/stylesheets
static_dir = Path("backend/static")
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

if __name__ == "__main__":
    import uvicorn
    print("Starting Web Dashboard on http://localhost:8000 ...")
    uvicorn.run("backend.server:app", host="127.0.0.1", port=8000, reload=True)

