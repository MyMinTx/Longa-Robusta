"""ฐานข้อมูล SQLite ไฟล์เดียว (ไม่ต้องติดตั้งอะไรเพิ่ม)"""
import json
import sqlite3
import threading
from pathlib import Path

from .config import settings
from .timeutil import iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS lots (
  lot_id TEXT PRIMARY KEY,
  owner TEXT NOT NULL,
  sacks INTEGER NOT NULL,
  status TEXT NOT NULL,
  moisture_start REAL NOT NULL,
  ready_streak INTEGER NOT NULL DEFAULT 0,
  was_ready INTEGER NOT NULL DEFAULT 0,
  inspection TEXT,          -- JSON
  alert TEXT,               -- JSON
  locked TEXT,              -- JSON ราคาที่ล็อกไว้ตอนกดยืนยันขาย
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS readings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lot_id TEXT NOT NULL, ts TEXT NOT NULL, value REAL NOT NULL, source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lot_id TEXT NOT NULL, ts TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL,
  sacks INTEGER, price REAL, buyer TEXT, result TEXT, ref TEXT
);
CREATE TABLE IF NOT EXISTS push_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lot_id TEXT NOT NULL, kind TEXT NOT NULL, ts TEXT NOT NULL, sent INTEGER NOT NULL, detail TEXT
);
CREATE INDEX IF NOT EXISTS ix_readings_lot ON readings(lot_id, id);
CREATE INDEX IF NOT EXISTS ix_events_lot ON events(lot_id, id);
"""

_lock = threading.RLock()
_conn = None


def conn():
    global _conn
    if _conn is None:
        if settings.db_path != ":memory:":
            Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(settings.db_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
    return _conn


def reset_connection():
    """ใช้ในเทสต์"""
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = None


def q(sql, args=(), one=False):
    with _lock:
        cur = conn().execute(sql, args)
        rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def x(sql, args=()):
    with _lock:
        c = conn()
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid


# ---------- lots ----------
def create_lot(lot_id, owner, sacks, moisture_start):
    t = iso()
    x("INSERT INTO lots (lot_id, owner, sacks, status, moisture_start, created_at, updated_at) "
      "VALUES (?,?,?,?,?,?,?)", (lot_id, owner, sacks, "DRYING", moisture_start, t, t))


def get_lot_row(lot_id):
    return q("SELECT * FROM lots WHERE lot_id=?", (lot_id,), one=True)


def latest_lot_row(owner):
    return q("SELECT * FROM lots WHERE owner=? ORDER BY created_at DESC, rowid DESC LIMIT 1", (owner,), one=True)


def lots_by_status(*statuses):
    marks = ",".join("?" * len(statuses))
    return q(f"SELECT * FROM lots WHERE status IN ({marks})", statuses)


def update_lot(lot_id, **fields):
    for k in ("inspection", "alert", "locked"):
        if k in fields and fields[k] is not None and not isinstance(fields[k], str):
            fields[k] = json.dumps(fields[k], ensure_ascii=False)
    fields["updated_at"] = iso()
    sets = ", ".join(f"{k}=?" for k in fields)
    x(f"UPDATE lots SET {sets} WHERE lot_id=?", (*fields.values(), lot_id))


def next_lot_id():
    n = q("SELECT COUNT(*) AS n FROM lots", one=True)["n"]
    return f"LOT-T49-{n + 1}"


# ---------- readings / events / push ----------
def add_reading(lot_id, value, source):
    x("INSERT INTO readings (lot_id, ts, value, source) VALUES (?,?,?,?)", (lot_id, iso(), value, source))


def readings(lot_id, limit=200):
    rows = q("SELECT ts, value, source FROM readings WHERE lot_id=? ORDER BY id DESC LIMIT ?", (lot_id, limit))
    return [dict(r) for r in reversed(rows)]


def add_event(lot_id, kind, text, sacks=None, price=None, buyer=None, result=None, ref=None):
    x("INSERT INTO events (lot_id, ts, kind, text, sacks, price, buyer, result, ref) VALUES (?,?,?,?,?,?,?,?,?)",
      (lot_id, iso(), kind, text, sacks, price, buyer, result, ref))


def update_event_result(lot_id, ref, result):
    x("UPDATE events SET result=? WHERE lot_id=? AND ref=? AND kind='offer'", (result, lot_id, ref))


def events(lot_id, since_id=0):
    rows = q("SELECT * FROM events WHERE lot_id=? AND id>? ORDER BY id DESC", (lot_id, since_id))
    return [dict(r) for r in rows]


def push_sent(lot_id, kind, since_ts):
    return q("SELECT 1 FROM push_log WHERE lot_id=? AND kind=? AND ts>=?", (lot_id, kind, since_ts), one=True) is not None


def log_push(lot_id, kind, sent, detail=""):
    x("INSERT INTO push_log (lot_id, kind, ts, sent, detail) VALUES (?,?,?,?,?)", (lot_id, kind, iso(), int(sent), detail))


def pushes(limit=50):
    return [dict(r) for r in q("SELECT * FROM push_log ORDER BY id DESC LIMIT ?", (limit,))]


def delete_lot(lot_id):
    for t in ("readings", "events", "push_log", "lots"):
        x(f"DELETE FROM {t} WHERE lot_id=?", (lot_id,))
