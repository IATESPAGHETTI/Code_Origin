"""SQLite persistence for eval runs and per-answer results."""
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, dataset_name TEXT, dataset_hash TEXT, config_json TEXT,
  status TEXT, done INTEGER DEFAULT 0, total INTEGER DEFAULT 0, error TEXT, created_at REAL, finished_at REAL
);
CREATE TABLE IF NOT EXISTS results (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, item_id TEXT, model TEXT, mode TEXT, category TEXT,
  response_json TEXT, metrics_json TEXT, jury_json TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS human_grades (
  run_id INTEGER, item_id TEXT, model TEXT, mode TEXT, score INTEGER, PRIMARY KEY (run_id, item_id, model, mode)
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

    @staticmethod
    def _run(row):
        if not row:
            return None
        d = dict(row)
        d["config"] = json.loads(d.pop("config_json") or "{}")
        return d

    def create_run(self, name, dataset_name, dataset_hash, config, total):
        with self._conn() as c:
            cur = c.execute("INSERT INTO runs (name,dataset_name,dataset_hash,config_json,status,total,created_at) VALUES (?,?,?,?,?,?,?)",
                            (name, dataset_name, dataset_hash, json.dumps(config), "running", total, time.time()))
            return cur.lastrowid

    def add_result(self, run_id, item_id, model, mode, category, response, metrics, jury, error):
        with self._conn() as c:
            cur = c.execute("INSERT INTO results (run_id,item_id,model,mode,category,response_json,metrics_json,jury_json,error) VALUES (?,?,?,?,?,?,?,?,?)",
                      (run_id, item_id, model, mode, category, json.dumps(response) if response else None,
                       json.dumps(metrics) if metrics else None, json.dumps(jury) if jury else None, error))
            row_id = cur.lastrowid
            c.execute("UPDATE runs SET done=done+1 WHERE id=?", (run_id,))
            return row_id

    def set_jury(self, row_id, jury):
        with self._conn() as c:
            c.execute("UPDATE results SET jury_json=? WHERE id=?", (json.dumps(jury) if jury else None, row_id))

    def finish_run(self, run_id, status, error=None):
        with self._conn() as c:
            c.execute("UPDATE runs SET status=?, error=?, finished_at=? WHERE id=?", (status, error, time.time(), run_id))

    def get_run(self, run_id):
        with self._conn() as c:
            return self._run(c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone())

    def list_runs(self):
        with self._conn() as c:
            return [self._run(r) for r in c.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 50")]

    def results(self, run_id, with_response=False):
        with self._conn() as c:
            rows = c.execute("SELECT * FROM results WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
        out = []
        for r in rows:
            d = {"item_id": r["item_id"], "model": r["model"], "mode": r["mode"], "category": r["category"],
                 "metrics": json.loads(r["metrics_json"]) if r["metrics_json"] else None,
                 "jury": json.loads(r["jury_json"]) if r["jury_json"] else None, "error": r["error"]}
            if with_response:
                d["response"] = json.loads(r["response_json"]) if r["response_json"] else None
            out.append(d)
        return out

    def fail_stale(self):
        with self._conn() as c:
            c.execute("UPDATE runs SET status='failed', error='interrupted by restart', finished_at=? WHERE status='running'",
                      (time.time(),))

    def set_human_grade(self, run_id, item_id, model, mode, score):
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO human_grades VALUES (?,?,?,?,?)", (run_id, item_id, model, mode, score))

    def human_grades(self, run_id):
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM human_grades WHERE run_id=?", (run_id,))]
