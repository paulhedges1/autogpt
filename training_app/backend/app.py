"""
FastAPI backend for the Modern Digital Workplace Training Academy app.

Serves the parsed course content and a small optional progress-sync API.
The frontend works entirely offline from localStorage; syncing to this
backend (via a short learner code) just lets a learner resume on another
device.
"""
import json
import secrets
import sqlite3
import string
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR.parent / "frontend"
CONTENT_PATH = DATA_DIR / "content.json"
DB_PATH = DATA_DIR / "progress.db"

CODE_ALPHABET = string.ascii_uppercase.replace("O", "").replace("I", "") + "23456789"


def generate_code(length=6):
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


@contextmanager
def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS learners (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS progress (
                code TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (code, key),
                FOREIGN KEY (code) REFERENCES learners(code)
            )"""
        )


app = FastAPI(title="Digital Workplace Training Academy")


@app.on_event("startup")
def on_startup():
    init_db()


class CreateLearner(BaseModel):
    name: str


class ProgressPatch(BaseModel):
    updates: dict[str, object]


@app.get("/api/content")
def get_content():
    if not CONTENT_PATH.exists():
        raise HTTPException(status_code=500, detail="Course content has not been generated yet.")
    with open(CONTENT_PATH) as f:
        return json.load(f)


@app.post("/api/learners")
def create_learner(payload: CreateLearner):
    name = payload.name.strip()[:80]
    if not name:
        raise HTTPException(status_code=400, detail="Name is required.")
    with get_db() as conn:
        for _ in range(5):
            code = generate_code()
            existing = conn.execute("SELECT 1 FROM learners WHERE code = ?", (code,)).fetchone()
            if not existing:
                conn.execute("INSERT INTO learners (code, name) VALUES (?, ?)", (code, name))
                return {"code": code, "name": name}
        raise HTTPException(status_code=500, detail="Could not allocate a learner code, please retry.")


@app.get("/api/learners/{code}")
def get_learner(code: str):
    code = code.strip().upper()
    with get_db() as conn:
        row = conn.execute("SELECT code, name FROM learners WHERE code = ?", (code,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Learner code not found.")
        return {"code": row["code"], "name": row["name"]}


@app.get("/api/progress/{code}")
def get_progress(code: str):
    code = code.strip().upper()
    with get_db() as conn:
        learner = conn.execute("SELECT code FROM learners WHERE code = ?", (code,)).fetchone()
        if not learner:
            raise HTTPException(status_code=404, detail="Learner code not found.")
        rows = conn.execute("SELECT key, value FROM progress WHERE code = ?", (code,)).fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}


@app.put("/api/progress/{code}")
def patch_progress(code: str, payload: ProgressPatch):
    code = code.strip().upper()
    with get_db() as conn:
        learner = conn.execute("SELECT code FROM learners WHERE code = ?", (code,)).fetchone()
        if not learner:
            raise HTTPException(status_code=404, detail="Learner code not found.")
        for key, value in payload.updates.items():
            conn.execute(
                """INSERT INTO progress (code, key, value, updated_at)
                   VALUES (?, ?, ?, datetime('now'))
                   ON CONFLICT(code, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
                (code, key, json.dumps(value)),
            )
    return {"status": "ok", "count": len(payload.updates)}


if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")
