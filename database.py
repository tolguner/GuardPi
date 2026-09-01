"""SQLite olay loglama, sensor gecmisi, ayarlar ve yetkili RFID kart yonetimi."""
import sqlite3
import threading
from datetime import datetime, timedelta

import config

_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock, _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                detail TEXT
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS authorized_cards (
                uid TEXT PRIMARY KEY,
                name TEXT,
                added_at TEXT NOT NULL
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                temperature REAL,
                humidity REAL,
                gas_alert INTEGER
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(timestamp)")


# ---------- olaylar ----------

def log_event(event_type, detail=""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO events (timestamp, type, detail) VALUES (?, ?, ?)",
            (ts, event_type, detail),
        )
    return ts


def get_events(limit=50):
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT timestamp, type, detail FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------- sensor gecmisi ----------

def log_reading(temperature, humidity, gas_alert):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO readings (timestamp, temperature, humidity, gas_alert) "
            "VALUES (?, ?, ?, ?)",
            (ts, temperature, humidity, 1 if gas_alert else 0),
        )


def get_readings(minutes=180, max_points=300):
    """Son `minutes` dakikadaki okumalar; cok fazlaysa esit araliklarla seyreltir."""
    since = (datetime.now() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT timestamp, temperature, humidity, gas_alert FROM readings "
            "WHERE timestamp >= ? ORDER BY id ASC",
            (since,),
        ).fetchall()
    data = [dict(r) for r in rows]
    if len(data) > max_points:
        step = len(data) / max_points
        data = [data[int(i * step)] for i in range(max_points)]
    return data


def purge_old_readings(days=7):
    """Eski okumalari temizle (DB sismesin)."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM readings WHERE timestamp < ?", (cutoff,))


# ---------- ayarlar ----------

def get_setting(key, default=None):
    with _lock, _connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value)),
        )


def all_settings():
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


# ---------- RFID kartlar ----------

def is_authorized(uid):
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT name FROM authorized_cards WHERE uid = ?", (str(uid),)
        ).fetchone()
    return row["name"] if row else None


def add_card(uid, name):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO authorized_cards (uid, name, added_at) VALUES (?, ?, ?)",
            (str(uid), name, ts),
        )


def list_cards():
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT uid, name, added_at FROM authorized_cards").fetchall()
    return [dict(r) for r in rows]
