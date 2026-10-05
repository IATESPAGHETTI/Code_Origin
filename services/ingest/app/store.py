"""SQLite state for repositories, ingest jobs and job events."""
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
  id TEXT PRIMARY KEY, kind TEXT, source TEXT, owner TEXT, name TEXT, ref TEXT,
  status TEXT, last_sha TEXT, last_issue_sync TEXT, options_json TEXT, counts_json TEXT,
  error TEXT, created_at REAL, updated_at REAL
);
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, repo_id TEXT, kind TEXT, status TEXT, stage TEXT,
  progress INTEGER DEFAULT 0, message TEXT, started_at REAL, finished_at REAL
);
CREATE TABLE IF NOT EXISTS job_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, ts REAL, stage TEXT, message TEXT, progress INTEGER, data TEXT
);
"""


class Store:
    def __init__(self, path):
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._lock = threading.RLock()
        self._mem = sqlite3.connect(":memory:", check_same_thread=False) if path == ":memory:" else None
        with self._conn() as c:
            c.executescript(SCHEMA)
            cols = {r[1] for r in c.execute("PRAGMA table_info(job_events)")}
            if "data" not in cols:   # databases created before live events existed
                c.execute("ALTER TABLE job_events ADD COLUMN data TEXT")

    @contextmanager
    def _conn(self):
        with self._lock:
            conn = self._mem or sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            finally:
                if not self._mem:
                    conn.close()

    # ------------------------------------------------------------------ repos
    @staticmethod
    def _repo(row):
        if row is None:
            return None
        d = dict(row)
        d["options"] = json.loads(d.pop("options_json") or "{}")
        d["counts"] = json.loads(d.pop("counts_json") or "{}")
        return d

    def upsert_repo(self, repo_id, **fields):
        now = time.time()
        with self._conn() as c:
            row = c.execute("SELECT id FROM repos WHERE id=?", (repo_id,)).fetchone()
            if row is None:
                c.execute(
                    "INSERT INTO repos (id,kind,source,owner,name,ref,status,options_json,counts_json,created_at,updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (repo_id, fields.get("kind"), fields.get("source"), fields.get("owner"), fields.get("name"),
                     fields.get("ref"), fields.get("status", "registered"),
                     json.dumps(fields.get("options", {})), "{}", now, now))
            else:
                self.update_repo(repo_id, **fields)

    def update_repo(self, repo_id, **fields):
        cols = []
        vals = []
        for k, v in fields.items():
            if k == "options":
                k, v = "options_json", json.dumps(v)
            elif k == "counts":
                k, v = "counts_json", json.dumps(v)
            cols.append(f"{k}=?")
            vals.append(v)
        cols.append("updated_at=?")
        vals.append(time.time())
        with self._conn() as c:
            c.execute(f"UPDATE repos SET {', '.join(cols)} WHERE id=?", (*vals, repo_id))

    def get_repo(self, repo_id):
        with self._conn() as c:
            return self._repo(c.execute("SELECT * FROM repos WHERE id=?", (repo_id,)).fetchone())

    def list_repos(self):
        with self._conn() as c:
            return [self._repo(r) for r in c.execute("SELECT * FROM repos ORDER BY created_at DESC")]

    def delete_repo(self, repo_id):
        with self._conn() as c:
            c.execute("DELETE FROM repos WHERE id=?", (repo_id,))

    # ------------------------------------------------------------------- jobs
    def create_job(self, repo_id, kind):
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO jobs (repo_id,kind,status,stage,progress,started_at) VALUES (?,?,?,?,?,?)",
                (repo_id, kind, "running", "queued", 0, time.time()))
            return cur.lastrowid

    def active_job(self, repo_id):
        with self._conn() as c:
            r = c.execute("SELECT * FROM jobs WHERE repo_id=? AND status='running' ORDER BY id DESC", (repo_id,)).fetchone()
            return dict(r) if r else None

    def progress(self, job_id, stage, message, progress=None, data=None):
        """Record a job event. `progress=None` keeps the last percentage; `data` is a structured
        payload (commit, chunk batch, file, ...) that the UI animates live."""
        with self._conn() as c:
            c.execute("UPDATE jobs SET stage=?, message=?, progress=COALESCE(?, progress) WHERE id=?",
                      (stage, message, progress, job_id))
            c.execute("INSERT INTO job_events (job_id,ts,stage,message,progress,data) VALUES (?,?,?,?,?,?)",
                      (job_id, time.time(), stage, message, progress, json.dumps(data) if data is not None else None))

    def finish_job(self, job_id, status, message):
        with self._conn() as c:
            c.execute("UPDATE jobs SET status=?, message=?, finished_at=?, progress=? WHERE id=?",
                      (status, message, time.time(), 100 if status == "done" else None, job_id))
            c.execute("INSERT INTO job_events (job_id,ts,stage,message,progress) VALUES (?,?,?,?,?)",
                      (job_id, time.time(), status, message, 100 if status == "done" else None))

    def get_job(self, job_id):
        with self._conn() as c:
            r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(r) if r else None

    def job_events(self, job_id, after_id=0):
        with self._conn() as c:
            rows = [dict(r) for r in c.execute(
                "SELECT * FROM job_events WHERE job_id=? AND id>? ORDER BY id", (job_id, after_id))]
        for r in rows:
            r["data"] = json.loads(r["data"]) if r.get("data") else None
        return rows

    def fail_stale_jobs(self):
        """Jobs left 'running' by a crashed process are marked failed on boot."""
        with self._conn() as c:
            c.execute("UPDATE jobs SET status='failed', message='interrupted by restart', finished_at=? WHERE status='running'",
                      (time.time(),))
            c.execute("UPDATE repos SET status='failed', error='interrupted by restart' WHERE status='ingesting'")
