import sqlite3
import json
import os
from typing import Dict, Any, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "mock_interview.db")

def init_db():
    """Initialize the SQLite database and create schemas if they do not exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Resume profiles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resume_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE,
            raw_text TEXT,
            skills TEXT, -- JSON string list
            projects TEXT, -- JSON string list
            classified_role TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Interview sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interview_sessions (
            session_id TEXT PRIMARY KEY,
            candidate_id INTEGER,
            role TEXT,
            difficulty TEXT,
            duration INTEGER,
            status TEXT DEFAULT 'active', -- 'active', 'completed'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(candidate_id) REFERENCES resume_profiles(id)
        )
    """)

    # 3. Chat history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            turn_index INTEGER,
            sender TEXT, -- 'assistant' or 'user'
            message TEXT,
            audio_path TEXT,
            tokens INTEGER DEFAULT 0,
            latency REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES interview_sessions(session_id)
        )
    """)

    # 4. Evaluation reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_reports (
            session_id TEXT PRIMARY KEY,
            technical_score INTEGER,
            communication_score INTEGER,
            relevance_score INTEGER,
            overall_score INTEGER,
            strengths TEXT, -- JSON string list
            improvements TEXT, -- JSON string list
            ideal_answers TEXT, -- JSON structure
            study_topics TEXT, -- JSON string list
            pdf_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES interview_sessions(session_id)
        )
    """)

    conn.commit()
    conn.close()

def get_db_connection():
    """Return a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Helper functions to store/retrieve data
def save_resume_profile(filename: str, raw_text: str, skills: List[str], projects: List[str], classified_role: str) -> int:
    """Save extracted resume profile to database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT OR REPLACE INTO resume_profiles (filename, raw_text, skills, projects, classified_role)
            VALUES (?, ?, ?, ?, ?)
            """,
            (filename, raw_text, json.dumps(skills), json.dumps(projects), classified_role)
        )
        conn.commit()
        # Get the ID of the inserted row
        cursor.execute("SELECT id FROM resume_profiles WHERE filename = ?", (filename,))
        row = cursor.fetchone()
        profile_id = row['id'] if row else -1
        return profile_id
    finally:
        conn.close()

def get_resume_profile(profile_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve resume profile by ID."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM resume_profiles WHERE id = ?", (profile_id,)).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "filename": row["filename"],
            "raw_text": row["raw_text"],
            "skills": json.loads(row["skills"]),
            "projects": json.loads(row["projects"]),
            "classified_role": row["classified_role"],
            "created_at": row["created_at"]
        }
    finally:
        conn.close()

def save_interview_session(session_id: str, candidate_id: int, role: str, difficulty: str, duration: int):
    """Create a new interview session."""
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO interview_sessions (session_id, candidate_id, role, difficulty, duration)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, candidate_id, role, difficulty, duration)
        )
        conn.commit()
    finally:
        conn.close()

def get_interview_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve interview session."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM interview_sessions WHERE session_id = ?", (session_id,)).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()

def save_chat_turn(session_id: str, turn_index: int, sender: str, message: str, audio_path: Optional[str] = None, tokens: int = 0, latency: float = 0.0):
    """Save a single chat turn (AI question or user answer)."""
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO chat_history (session_id, turn_index, sender, message, audio_path, tokens, latency)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, turn_index, sender, message, audio_path, tokens, latency)
        )
        conn.commit()
    finally:
        conn.close()

def get_chat_history(session_id: str) -> List[Dict[str, Any]]:
    """Retrieve all chat turns for a session sorted by turn_index."""
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM chat_history WHERE session_id = ? ORDER BY turn_index ASC", (session_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def save_evaluation_report(
    session_id: str,
    tech_score: int,
    comm_score: int,
    rel_score: int,
    overall_score: int,
    strengths: List[str],
    improvements: List[str],
    ideal_answers: Dict[str, str],
    study_topics: List[str],
    pdf_path: str
):
    """Save the final evaluation report."""
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO evaluation_reports 
            (session_id, technical_score, communication_score, relevance_score, overall_score, strengths, improvements, ideal_answers, study_topics, pdf_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                tech_score,
                comm_score,
                rel_score,
                overall_score,
                json.dumps(strengths),
                json.dumps(improvements),
                json.dumps(ideal_answers),
                json.dumps(study_topics),
                pdf_path
            )
        )
        conn.execute(
            "UPDATE interview_sessions SET status = 'completed' WHERE session_id = ?",
            (session_id,)
        )
        conn.commit()
    finally:
        conn.close()

def get_evaluation_report(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the evaluation report for a session."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM evaluation_reports WHERE session_id = ?", (session_id,)).fetchone()
        if not row:
            return None
        return {
            "session_id": row["session_id"],
            "technical_score": row["technical_score"],
            "communication_score": row["communication_score"],
            "relevance_score": row["relevance_score"],
            "overall_score": row["overall_score"],
            "strengths": json.loads(row["strengths"]),
            "improvements": json.loads(row["improvements"]),
            "ideal_answers": json.loads(row["ideal_answers"]),
            "study_topics": json.loads(row["study_topics"]),
            "pdf_path": row["pdf_path"],
            "created_at": row["created_at"]
        }
    finally:
        conn.close()

# Initialize on import
init_db()
