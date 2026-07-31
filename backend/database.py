"""聊天历史 SQLite 持久化"""
import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "chat.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            references_json TEXT DEFAULT '[]',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 兼容旧表：缺少 references_json 列时补齐
    cols = [r[1] for r in conn.execute("PRAGMA table_info(chat_history)").fetchall()]
    if "references_json" not in cols:
        conn.execute("ALTER TABLE chat_history ADD COLUMN references_json TEXT DEFAULT '[]'")
    conn.commit()
    conn.close()


def save_message(session_id: str, role: str, content: str, references=None):
    refs_json = json.dumps(references or [], ensure_ascii=False)
    conn = _get_conn()
    conn.execute(
        "INSERT INTO chat_history (session_id, role, content, references_json) VALUES (?, ?, ?, ?)",
        (session_id, role, content, refs_json),
    )
    conn.commit()
    conn.close()


def get_messages(session_id: str):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT role, content, references_json FROM chat_history WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    conn.close()

    messages = []
    for r in rows:
        msg = {"role": r["role"], "content": r["content"]}
        try:
            msg["references"] = json.loads(r["references_json"] or "[]")
        except (json.JSONDecodeError, TypeError):
            msg["references"] = []
        messages.append(msg)
    return messages


def delete_session(session_id: str):
    conn = _get_conn()
    conn.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


# 启动时初始化
init_db()