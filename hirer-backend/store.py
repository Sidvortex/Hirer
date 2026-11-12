"""Job records in SQLite, so finished results survive a server restart."""

import json
import sqlite3
import threading
import time


class JobStore:
    def __init__(self, path):
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, created REAL, data TEXT)")
            self._db.commit()
        # a job that was mid-run when the server stopped can't be picked up again
        for job_id, data in self._all():
            if data.get("status") == "running":
                self.update(job_id, status="error", step="Interrupted",
                            error="The server restarted while this job was running. Please run it again.")

    def _all(self):
        with self._lock:
            rows = self._db.execute("SELECT id, data FROM jobs").fetchall()
        return [(i, json.loads(d)) for i, d in rows]

    def create(self, job_id, **fields):
        data = {"status": "running", "step": "Queued...", "pct": 0, "steps": [],
                "error": None, "result": None, **fields}
        with self._lock:
            self._db.execute("INSERT INTO jobs VALUES (?, ?, ?)", (job_id, time.time(), json.dumps(data)))
            self._db.commit()

    def get(self, job_id):
        with self._lock:
            row = self._db.execute("SELECT data FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def update(self, job_id, **fields):
        with self._lock:
            row = self._db.execute("SELECT data FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return
            data = json.loads(row[0])
            step = fields.pop("add_step", None)
            data.update(fields)
            if step:
                data["steps"].append(step)
            self._db.execute("UPDATE jobs SET data = ? WHERE id = ?", (json.dumps(data), job_id))
            self._db.commit()

    def step(self, job_id, step, pct, status="running"):
        self.update(job_id, step=step, pct=pct, status=status, add_step=step)

    def purge(self, max_age_seconds):
        """delete records older than max_age_seconds; returns their ids"""
        cutoff = time.time() - max_age_seconds
        with self._lock:
            ids = [r[0] for r in self._db.execute("SELECT id FROM jobs WHERE created < ?", (cutoff,))]
            self._db.execute("DELETE FROM jobs WHERE created < ?", (cutoff,))
            self._db.commit()
        return ids
