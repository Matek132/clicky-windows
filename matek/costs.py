from datetime import datetime, timezone
from contextlib import contextmanager
import json
import math
from pathlib import Path
import sqlite3
import sys
import threading
import time
import uuid

from .config import data_dir


def pricing_path():
    target = data_dir() / "pricing.json"
    if not target.exists():
        bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "config" / "pricing.json"
        target.write_bytes(bundled.read_bytes())
    return target


class CostLedger:
    """Reserve before dispatch. Unknown completion costs retain the full reservation."""
    def __init__(self, path=None, pricing=None, clock=time.time):
        self.path = path or data_dir() / "usage.sqlite3"
        self.pricing = pricing or pricing_path()
        self.clock = clock
        self.lock = threading.RLock()
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, at REAL, model TEXT, endpoint TEXT, "
                       "estimate REAL, charged REAL, status TEXT, input_tokens INTEGER, output_tokens INTEGER)")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def rates(self, settings):
        data = json.loads(Path(self.pricing).read_text(encoding="utf-8"))
        from urllib.parse import urlparse
        provider = settings.api_base
        rate = data.get("providers", {}).get(provider, {}).get(settings.model)
        if not rate and (provider == "openai" or urlparse(provider).hostname == "api.openai.com"):
            rate = data["models"].get(settings.model)
        if not rate:
            raise ValueError("No pricing configured for this model. Edit pricing.json before cloud use.")
        if any(not math.isfinite(float(rate[k])) or float(rate[k]) < 0 for k in ("input_per_million", "output_per_million", "image_token_bound")):
            raise ValueError("Invalid pricing configuration")
        return rate

    def estimate(self, package, settings, instructions):
        rate = self.rates(settings)
        # UTF-8 byte count is a conservative bound for text; add message framing overhead.
        tokens = len((package.text() + instructions + str(package.conversation)).encode("utf-8")) + 1024
        tokens += len(package.frames) * rate["image_token_bound"]
        amount = (tokens * rate["input_per_million"] + settings.max_output_tokens * rate["output_per_million"]) / 1e6
        return amount * 1.25, rate

    def totals(self):
        now = datetime.fromtimestamp(self.clock(), timezone.utc).astimezone()
        day = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
        with self.connect() as db:
            return tuple(db.execute("SELECT COALESCE(SUM(charged), 0) FROM calls WHERE at >= ?", (cutoff,)).fetchone()[0]
                         for cutoff in (day, month))

    def check(self, estimate, settings):
        daily, monthly = self.totals()
        if estimate > settings.per_question_usd:
            raise PermissionError("Per-question spending ceiling would be exceeded.")
        if daily + estimate > settings.daily_usd or monthly + estimate > settings.monthly_usd:
            raise PermissionError("Daily or monthly spending ceiling would be exceeded.")

    def reserve(self, estimate, settings):
        with self.lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.check(estimate, settings)
            identity = uuid.uuid4().hex
            db.execute("INSERT INTO calls VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)",
                       (identity, self.clock(), settings.model, settings.api_base, estimate, estimate, "reserved"))
            return identity

    def settle(self, identity, status, usage=None, rate=None):
        with self.connect() as db:
            if usage is not None and rate is not None:
                incoming, outgoing = usage
                actual = (incoming * rate["input_per_million"] + outgoing * rate["output_per_million"]) / 1e6
                db.execute("UPDATE calls SET status=?, charged=?, input_tokens=?, output_tokens=? WHERE id=?",
                           (status, actual, incoming, outgoing, identity))
            else:
                db.execute("UPDATE calls SET status=? WHERE id=?", (status, identity))

    def history(self):
        with self.connect() as db:
            return db.execute("SELECT at, model, estimate, charged, status, input_tokens, output_tokens, endpoint "
                              "FROM calls ORDER BY at DESC LIMIT 200").fetchall()
