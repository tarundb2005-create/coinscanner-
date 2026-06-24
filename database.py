"""
database.py - CoinScanner Database Layer
========================================
Railway production database layer using PostgreSQL, with SQLite fallback for local development.
"""

import os
import time
import sqlite3

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

DATABASE_URL = os.getenv("DATABASE_URL")
USE_SQLITE = not HAS_POSTGRES or not DATABASE_URL or not DATABASE_URL.startswith(("postgresql://", "postgres://"))

# ── PostgreSQL Wrappers ────────────────────────────────────
class _CursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=()):
        self._cursor.execute(sql, params)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        return self._cursor.close()

    def __iter__(self):
        return iter(self._cursor)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _ConnectionWrapper:
    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return _CursorWrapper(self._connection.cursor(cursor_factory=RealDictCursor))

    def execute(self, sql, params=()):
        return self.cursor().execute(sql, params)

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        return self._connection.rollback()

    def close(self):
        return self._connection.close()

    def __getattr__(self, name):
        return getattr(self._connection, name)

# ── SQLite Wrappers ────────────────────────────────────────
class SQLiteCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=()):
        # Convert %s placeholders to ? placeholders
        sql = sql.replace("%s", "?")
        self._cursor.execute(sql, params)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [dict(row) for row in rows]

    def close(self):
        self._cursor.close()

    def __iter__(self):
        return iter(self._cursor)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class SQLiteConnectionWrapper:
    def __init__(self, connection):
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    def cursor(self):
        return SQLiteCursorWrapper(self._connection.cursor())

    def execute(self, sql, params=()):
        return self.cursor().execute(sql, params)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    def __getattr__(self, name):
        return getattr(self._connection, name)


def get_db_connection():
    """Return a PostgreSQL connection, or SQLite connection for local development."""
    if USE_SQLITE:
        db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "coinscanner.db")
        conn = sqlite3.connect(db_path)
        return SQLiteConnectionWrapper(conn)
    else:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL environment variable is not set.")
        return _ConnectionWrapper(psycopg2.connect(DATABASE_URL))


def init_db():
    """Create tables and run lightweight migrations if needed."""
    conn = get_db_connection()
    cursor = conn.cursor()

    users_ddl = """
    CREATE TABLE IF NOT EXISTS users (
        id                 SERIAL PRIMARY KEY,
        name               TEXT    NOT NULL,
        email              TEXT    UNIQUE NOT NULL,
        phone              TEXT    UNIQUE,
        password_hash      TEXT    NOT NULL,
        email_verified     BOOLEAN DEFAULT FALSE,
        phone_verified     BOOLEAN DEFAULT FALSE,
        status             VARCHAR(20) DEFAULT 'pending',
        failed_attempts    INTEGER DEFAULT 0,
        locked_until       INTEGER DEFAULT 0,
        session_version    INTEGER DEFAULT 0,
        created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    coin_watchlist_ddl = """
    CREATE TABLE IF NOT EXISTS coin_watchlist (
        id          SERIAL PRIMARY KEY,
        user_id     INTEGER NOT NULL,
        coin_id     TEXT    NOT NULL,
        coin_name   TEXT    NOT NULL,
        coin_symbol TEXT    NOT NULL,
        coin_image  TEXT    DEFAULT '',
        added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, coin_id),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """
    exchange_watchlist_ddl = """
    CREATE TABLE IF NOT EXISTS exchange_watchlist (
        id            SERIAL PRIMARY KEY,
        user_id       INTEGER NOT NULL,
        exchange_id   TEXT    NOT NULL,
        exchange_name TEXT    NOT NULL,
        exchange_logo TEXT    DEFAULT '',
        added_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, exchange_id),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """
    login_log_ddl = """
    CREATE TABLE IF NOT EXISTS login_log (
        id         SERIAL PRIMARY KEY,
        ip         TEXT,
        identifier TEXT,
        success    INTEGER DEFAULT 0,
        reason     TEXT,
        timestamp  INTEGER
    )
    """

    if USE_SQLITE:
        users_ddl = users_ddl.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        coin_watchlist_ddl = coin_watchlist_ddl.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        exchange_watchlist_ddl = exchange_watchlist_ddl.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        login_log_ddl = login_log_ddl.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")

    cursor.execute(users_ddl)

    new_columns = [
        ("failed_attempts", "INTEGER DEFAULT 0"),
        ("locked_until", "INTEGER DEFAULT 0"),
        ("session_version", "INTEGER DEFAULT 0"),
        ("email_verified", "BOOLEAN DEFAULT FALSE"),
        ("phone_verified", "BOOLEAN DEFAULT FALSE"),
        ("status", "VARCHAR(20) DEFAULT 'pending'"),
    ]
    for col_name, col_def in new_columns:
        try:
            if USE_SQLITE:
                # Check if column exists in SQLite
                cursor.execute("PRAGMA table_info(users)")
                columns = [row["name"] for row in cursor.fetchall()]
                if col_name not in columns:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                    conn.commit()
            else:
                cursor.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_def}")
                conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

    # Populate a user status for older databases.
    # Active if both email and phone were already verified, otherwise pending.
    try:
        cursor.execute(
            "UPDATE users SET status = 'active' "
            "WHERE email_verified IS TRUE AND phone_verified IS TRUE"
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    try:
        cursor.execute(
            "UPDATE users SET status = 'active' WHERE is_verified IS TRUE"
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    cursor.execute(coin_watchlist_ddl)
    cursor.execute(exchange_watchlist_ddl)
    cursor.execute(login_log_ddl)

    conn.commit()
    conn.close()


def purge_old_logs(days=90):
    """Delete login_log entries older than `days` days."""
    cutoff = int(time.time()) - (days * 86400)
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM login_log WHERE timestamp < %s", (cutoff,))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()
