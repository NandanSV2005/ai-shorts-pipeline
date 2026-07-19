import sqlite3
import json
from datetime import datetime, timezone
from backend.config import DB_PATH

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Table to track topics for avoiding duplicates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_str TEXT UNIQUE,
            niche TEXT,
            title TEXT,
            concept TEXT,
            keywords TEXT,
            created_at TEXT
        )
    """)
    
    # Table to track full pipeline runs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            date_str TEXT PRIMARY KEY,
            topic_title TEXT,
            status TEXT,
            metadata_json TEXT,
            created_at TEXT,
            series TEXT,
            episode INTEGER
        )
    """)
    
    # Check if the series and episode columns exist, and add them if not (for existing databases)
    cursor.execute("PRAGMA table_info(runs)")
    columns = [row[1] for row in cursor.fetchall()]
    if "series" not in columns:
        try:
            cursor.execute("ALTER TABLE runs ADD COLUMN series TEXT")
        except sqlite3.OperationalError as e:
            print(f"[DB init] Note: {e}")
    if "episode" not in columns:
        try:
            cursor.execute("ALTER TABLE runs ADD COLUMN episode INTEGER")
        except sqlite3.OperationalError as e:
            print(f"[DB init] Note: {e}")
            
    conn.commit()
    conn.close()

def add_topic(date_str: str, niche: str, title: str, concept: str, keywords: list) -> bool:
    """Inserts a new topic. Returns True if inserted, False if date already exists."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO topics (date_str, niche, title, concept, keywords, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                date_str,
                niche,
                title,
                concept,
                json.dumps(keywords),
                datetime.now(timezone.utc).isoformat()
            )
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_past_topics(niche: str) -> list:
    """Retrieves all past topic titles and concepts to prevent duplicates."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT title, concept FROM topics WHERE niche = ?", (niche,))
    rows = cursor.fetchall()
    conn.close()
    return [{"title": row["title"], "concept": row["concept"]} for row in rows]

def update_run_status(date_str: str, topic_title: str, status: str, metadata: dict | None = None) -> None:
    """Updates or inserts a pipeline run log entry."""
    conn = get_db_connection()
    cursor = conn.cursor()
    metadata_json = json.dumps(metadata) if metadata else "{}"
    now = datetime.now(timezone.utc).isoformat()
    
    series = metadata.get("series") if metadata else None
    episode = metadata.get("episode") if metadata else None
    
    cursor.execute("""
        INSERT INTO runs (date_str, topic_title, status, metadata_json, created_at, series, episode)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date_str) DO UPDATE SET
            topic_title=excluded.topic_title,
            status=excluded.status,
            metadata_json=excluded.metadata_json,
            created_at=excluded.created_at,
            series=excluded.series,
            episode=excluded.episode
    """, (date_str, topic_title, status, metadata_json, now, series, episode))
    
    conn.commit()
    conn.close()

# Auto-initialize the DB on import
init_db()
