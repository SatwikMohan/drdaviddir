"""Small, local store for explicit durable user facts, separate from biography."""
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import config

PREFERENCE = re.compile(r"\b(?:I prefer|please (?:always )?use|I (?:like|want) (?:detailed|concise|short|simple)|remember (?:that )?I prefer)\b", re.I)
PROJECT = re.compile(r"\b(?:I am|I'm|we are|we're) (?:currently )?(?:working on|researching|studying|developing)\b", re.I)
INTEREST = re.compile(r"\b(?:I am interested in|I'm interested in|I often discuss)\b", re.I)
REMEMBER = re.compile(r"\bremember (?:this|that)\b", re.I)
FICTION = re.compile(r"\b(?:imagine|suppose|hypothetically|in a story|pretend)\b", re.I)


def _connect():
    path = Path(config.MEMORY_DB_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=5)
    db.execute("CREATE TABLE IF NOT EXISTS memories (key TEXT PRIMARY KEY, content TEXT NOT NULL, category TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, source_turn TEXT, confidence REAL NOT NULL, explicit INTEGER NOT NULL, confirmed INTEGER NOT NULL)")
    return db


def extract(message):
    text = " ".join(message.strip().split())
    if len(text) < 12 or len(text) > 500 or FICTION.search(text):
        return None
    for category, pattern in (("USER_PREFERENCES", PREFERENCE), ("ONGOING_CONTEXT", PROJECT), ("USER_INTERESTS", INTEREST), ("CONVERSATION_LEARNINGS", REMEMBER)):
        if pattern.search(text):
            return category, text
    return None


def save(message, source_turn=None, user_id=None):
    item = extract(message)
    if not item:
        return False
    category, content = item
    # A new explicit preference supersedes the previous one; other facts deduplicate by content.
    key = (user_id or "default") + ":" + ("communication_preference" if category == "USER_PREFERENCES" else category + ":" + content.casefold())
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        db.execute("INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?, 1.0, 1, 1) ON CONFLICT(key) DO UPDATE SET content=excluded.content, updated_at=excluded.updated_at, source_turn=excluded.source_turn", (key, content, category, now, now, source_turn))
    return True


def relevant(question, limit=None, user_id=None):
    limit = limit or config.MEMORY_RETRIEVAL_LIMIT
    words = set(re.findall(r"[a-z]{4,}", question.casefold()))
    with _connect() as db:
        rows = db.execute("SELECT content, category FROM memories WHERE key LIKE ? ORDER BY updated_at DESC LIMIT 100", ((user_id or "default") + ":%",)).fetchall()
    ranked = sorted(rows, key=lambda row: (row[1] == "USER_PREFERENCES", len(words & set(re.findall(r"[a-z]{4,}", row[0].casefold())))), reverse=True)
    selected = [row for row in ranked if row[1] == "USER_PREFERENCES" or words & set(re.findall(r"[a-z]{4,}", row[0].casefold()))]
    return "\n".join(f"{category}: {content}" for content, category in selected[:limit])
