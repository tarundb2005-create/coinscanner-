"""
database.py - CoinScanner Database Layer
========================================
Railway production database layer using PostgreSQL with connection pooling,
with SQLite fallback for local development.
"""

import os
import time
import sqlite3

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2.pool import SimpleConnectionPool
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False
    SimpleConnectionPool = None

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


# ── PostgreSQL Connection Pool ────────────────────────────────
_db_pool = None


def _init_db_pool():
    """
    Initialize the PostgreSQL connection pool.
    Called once at application startup.
    
    Pool configuration:
      - minconn: 1 (minimum 1 idle connection)
      - maxconn: 20 (maximum 20 connections)
    """
    global _db_pool
    if USE_SQLITE or not HAS_POSTGRES or not DATABASE_URL:
        return
    
    try:
        _db_pool = SimpleConnectionPool(
            minconn=1,
            maxconn=20,
            dsn=DATABASE_URL
        )
    except Exception as e:
        print(f"Failed to initialize connection pool: {e}")
        _db_pool = None


def get_db_connection():
    """
    Get a database connection from the pool (PostgreSQL) or direct connection (SQLite).
    
    For PostgreSQL: Returns a connection from the pool.
    For SQLite: Returns a new SQLite connection.
    
    IMPORTANT: PostgreSQL connections must be released via release_db_connection()
    when done to return them to the pool.
    """
    if USE_SQLITE:
        db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "coinscanner.db")
        conn = sqlite3.connect(db_path)
        return SQLiteConnectionWrapper(conn)
    else:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL environment variable is not set.")
        
        # Use connection pool if available
        if _db_pool:
            try:
                pg_conn = _db_pool.getconn()
                return _ConnectionWrapper(pg_conn)
            except Exception as e:
                print(f"Failed to get connection from pool: {e}")
                # Fallback to direct connection
                return _ConnectionWrapper(psycopg2.connect(DATABASE_URL))
        else:
            return _ConnectionWrapper(psycopg2.connect(DATABASE_URL))


def release_db_connection(conn):
    """
    Release a PostgreSQL connection back to the pool.
    
    IMPORTANT: Only call this for PostgreSQL connections obtained via get_db_connection().
    SQLite connections will be closed normally.
    
    Args:
        conn: The connection wrapper to release
    """
    if USE_SQLITE or not _db_pool:
        # SQLite — just close normally
        if hasattr(conn, 'close'):
            conn.close()
        return
    
    # PostgreSQL — return to pool
    try:
        # Extract the underlying psycopg2 connection from the wrapper
        if isinstance(conn, _ConnectionWrapper):
            pg_conn = conn._connection
            _db_pool.putconn(pg_conn)
        else:
            conn.close()
    except Exception as e:
        print(f"Error returning connection to pool: {e}")
        try:
            conn.close()
        except Exception:
            pass


def close_db_pool():
    """
    Close all connections in the pool and clean up.
    Called at application shutdown.
    """
    global _db_pool
    if _db_pool:
        try:
            _db_pool.closeall()
            _db_pool = None
        except Exception as e:
            print(f"Error closing connection pool: {e}")




def run_safe_migrations():
    """
    Run safe schema migrations.
    
    - Checks if columns/indexes exist before altering
    - Prevents duplicate execution
    - Maintains backward compatibility
    - Does NOT run schema changes directly inside request flow
    
    Should be called once at application startup via init_db().
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # ══════════════════════════════════════════════════════════
        # Migration 1: Add missing columns to users table
        # ══════════════════════════════════════════════════════════
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
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
        
        # ══════════════════════════════════════════════════════════
        # Migration 2: Populate user status for older databases
        # ══════════════════════════════════════════════════════════
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
        
        # Handle legacy is_verified column if it exists
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
        
        # ══════════════════════════════════════════════════════════
        # Migration 3: Create database indexes for performance
        # ══════════════════════════════════════════════════════════
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);",
            "CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);",
            "CREATE INDEX IF NOT EXISTS idx_login_identifier ON login_log(identifier);",
            "CREATE INDEX IF NOT EXISTS idx_coin_watchlist_user_id ON coin_watchlist(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_exchange_watchlist_user_id ON exchange_watchlist(user_id);",
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
                conn.commit()
            except Exception as e:
                # Index might already exist or syntax differs for SQLite
                try:
                    conn.rollback()
                except Exception:
                    pass
    
    except Exception as e:
        print(f"Error running migrations: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        release_db_connection(conn)


def init_db():
    """
    Create all required database tables.
    Then run all safe migrations.
    
    Called once at application startup.
    """
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

    try:
        cursor.execute(users_ddl)
        cursor.execute(coin_watchlist_ddl)
        cursor.execute(exchange_watchlist_ddl)
        cursor.execute(login_log_ddl)
        conn.commit()
    except Exception as e:
        print(f"Error creating tables: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        release_db_connection(conn)
    
    # Run all migrations after tables are created
    run_safe_migrations()


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
        release_db_connection(conn)
