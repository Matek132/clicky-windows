import sqlite3
from contextlib import contextmanager
import time
from .config import data_dir


class ConversationStore:
    def __init__(self, path=None):
        self.path = path or data_dir() / "history.sqlite3"

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                db.execute("CREATE TABLE IF NOT EXISTS turns (at REAL, question TEXT, answer TEXT)")
                yield db
        finally:
            db.close()

    def save(self, question, answer, days):
        with self.connect() as db:
            db.execute("DELETE FROM turns WHERE at < ?", (time.time() - days * 86400,))
            db.execute("INSERT INTO turns VALUES (?, ?, ?)", (time.time(), question, answer))
            db.execute("DELETE FROM turns WHERE rowid NOT IN (SELECT rowid FROM turns ORDER BY at DESC LIMIT 200)")

    def read(self, days=7):
        with self.connect() as db:
            db.execute("DELETE FROM turns WHERE at < ?", (time.time() - days * 86400,))
            return db.execute("SELECT at, question, answer FROM turns ORDER BY at DESC LIMIT 200").fetchall()

    def clear(self):
        if self.path.exists():
            with self.connect() as db:
                db.execute("DELETE FROM turns")
                db.commit()
                db.execute("VACUUM")
