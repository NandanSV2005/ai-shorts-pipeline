import sqlite3
import json
from datetime import datetime
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
            created_at TEXT
        )
    """)
    
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
                datetime.utcnow().isoformat()
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
    now = datetime.utcnow().isoformat()
    
    cursor.execute("""
        INSERT INTO runs (date_str, topic_title, status, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(date_str) DO UPDATE SET
            topic_title=excluded.topic_title,
            status=excluded.status,
            metadata_json=excluded.metadata_json,
            created_at=excluded.created_at
    """, (date_str, topic_title, status, metadata_json, now))
    
    conn.commit()
    conn.close()

# Auto-initialize the DB on import
init_db()
