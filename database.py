import sqlite3
import random
import os


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
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS config_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def add_user(self, user_id: int, username: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )

    def add_referral(self, referrer_id: int, referred_id: int) -> bool:
        """Returns True if referral was new."""
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

    def get_random_config(self) -> str | None:
        with self._conn() as conn:
            rows = conn.execute("SELECT config FROM configs").fetchall()
            if not rows:
                return None
            return random.choice(rows)[0]

    def get_all_configs(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute("SELECT config FROM configs ORDER BY added_at DESC").fetchall()
            return [r[0] for r in rows]

    def clear_configs(self):
        with self._conn() as conn:
            conn.execute("DELETE FROM configs")

    def get_configs_used(self, user_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM config_usage WHERE user_id = ?", (user_id,)
            ).fetchone()
            return row[0] if row else 0

    def use_config(self, user_id: int):
        with self._conn() as conn:
            conn.execute("INSERT INTO config_usage (user_id) VALUES (?)", (user_id,))

    def get_stats(self) -> dict:
        with self._conn() as conn:
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            configs = conn.execute("SELECT COUNT(*) FROM configs").fetchone()[0]
            used = conn.execute("SELECT COUNT(*) FROM config_usage").fetchone()[0]
            return {"users": users, "configs": configs, "used": used}

    def get_setting(self, key: str, default: str = "") -> str:
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
                return row[0] if row else default
        except Exception:
            return default

    def set_setting(self, key: str, value: str):
        with self._conn() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

    def is_referral_active(self) -> bool:
        return self.get_setting("referral_active", "1") == "1"

    def toggle_referral(self) -> bool:
        """Toggle referral system. Returns new state (True=active)."""
        current = self.is_referral_active()
        self.set_setting("referral_active", "0" if current else "1")
        return not current
