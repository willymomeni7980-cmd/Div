import sqlite3
import random


class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self._init_db()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER,
                    referred_id INTEGER UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config TEXT UNIQUE NOT NULL,
                    is_used INTEGER DEFAULT 0,
                    given_to INTEGER DEFAULT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS config_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)

    def add_user(self, user_id: int, username: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )

    def add_referral(self, referrer_id: int, referred_id: int) -> bool:
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
                    (referrer_id, referred_id)
                )
                return conn.execute("SELECT changes()").fetchone()[0] > 0
        except Exception:
            return False

    def get_referral_count(self, user_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,)
            ).fetchone()
            return row[0] if row else 0

    def add_config(self, config: str) -> bool:
        try:
            with self._conn() as conn:
                conn.execute("INSERT OR IGNORE INTO configs (config) VALUES (?)", (config,))
                return conn.execute("SELECT changes()").fetchone()[0] > 0
        except Exception:
            return False

    def get_and_mark_config(self, user_id: int) -> str | None:
        """Get a free config, mark it as used, return it. Atomic."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, config FROM configs WHERE is_used = 0 ORDER BY RANDOM() LIMIT 1"
            ).fetchone()
            if not row:
                return None
            config_id, config = row
            conn.execute(
                "UPDATE configs SET is_used = 1, given_to = ? WHERE id = ?",
                (user_id, config_id)
            )
            conn.execute("INSERT INTO config_usage (user_id) VALUES (?)", (user_id,))
            return config

    def get_all_configs(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT config, is_used FROM configs ORDER BY added_at DESC"
            ).fetchall()
            return [{"config": r[0], "used": bool(r[1])} for r in rows]

    def clear_configs(self):
        with self._conn() as conn:
            conn.execute("DELETE FROM configs")

    def get_configs_used(self, user_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM config_usage WHERE user_id = ?", (user_id,)
            ).fetchone()
            return row[0] if row else 0

    def get_stats(self) -> dict:
        with self._conn() as conn:
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total = conn.execute("SELECT COUNT(*) FROM configs").fetchone()[0]
            used = conn.execute("SELECT COUNT(*) FROM configs WHERE is_used = 1").fetchone()[0]
            free = total - used
            return {"users": users, "configs": free, "configs_total": total, "used": used}

    def get_setting(self, key: str, default: str = "") -> str:
        try:
            with self._conn() as conn:
                row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
                return row[0] if row else default
        except Exception:
            return default

    def set_setting(self, key: str, value: str):
        with self._conn() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

    def is_referral_active(self) -> bool:
        return self.get_setting("referral_active", "1") == "1"

    def toggle_referral(self) -> bool:
        current = self.is_referral_active()
        self.set_setting("referral_active", "0" if current else "1")
        return not current
