import os
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_AUDIT_ENGINE: Engine | None = None

try:
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=env_path, override=False)
    load_dotenv(override=False)
except Exception:
    pass


def _get_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _build_db_url(db_name: str, host=None, port=None, user=None, password=None) -> str:
    host = host or _get_env("DB_HOST", "192.168.31.241")
    port = port or _get_env("DB_PORT", "3306")
    user = user or _get_env("DB_USER", "root")
    if password is None:
        password = os.getenv("DB_PASSWORD") or os.getenv("MYSQL_PWD") or ""
    password = quote_plus(password) if password else ""
    auth = f"{user}:{password}" if password else user
    return f"mysql+pymysql://{auth}@{host}:{port}/{db_name}"


def build_engine(db_name: str, host=None, port=None, user=None, password=None):
    return create_engine(
        _build_db_url(db_name, host=host, port=port, user=user, password=password),
        pool_pre_ping=True,
    )


DB_NAME = _get_env("DB_NAME", "test2")
DB_NAME_TEST2 = _get_env("DB_NAME_TEST2", "test2")

DATABASE1 = build_engine(DB_NAME)
DATABASE2 = build_engine(DB_NAME)
DATABASE3 = build_engine(DB_NAME)
DATABASE_TEST2 = build_engine(DB_NAME_TEST2)


def get_db_name():
    return os.getenv("DB_NAME_TEST2") or os.getenv("DB_NAME") or "test2"


def _parse_host_port(db_url):
    if not db_url:
        return None, None
    try:
        parsed = urlparse(db_url)
    except Exception:
        return None, None
    return parsed.hostname, parsed.port


def _is_loopback_host(host: str | None) -> bool:
    host = (host or "").strip().lower()
    return host in ("", "127.0.0.1", "localhost", "::1")


def get_local_engine():
    # VM lane rule: if DB_HOST is explicitly set to a non-loopback host, always prefer DB_*
    # and ignore LOCAL_DB_* even if present (LOCAL_DB_URL may point to 127.0.0.1).
    db_host = os.getenv("DB_HOST")
    if db_host and not _is_loopback_host(db_host):
        return build_engine(
            get_db_name(),
            host=db_host,
            port=os.getenv("DB_PORT"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
        )

    db_url = os.getenv("LOCAL_DB_URL")
    if db_url:
        return create_engine(db_url, pool_pre_ping=True)
    return build_engine(
        get_db_name(),
        host=os.getenv("LOCAL_DB_HOST"),
        port=os.getenv("LOCAL_DB_PORT"),
        user=os.getenv("LOCAL_DB_USER"),
        password=os.getenv("LOCAL_DB_PASSWORD"),
    )


def get_remote_engine():
    db_url = os.getenv("REMOTE_DB_URL")
    if db_url:
        return create_engine(db_url, pool_pre_ping=True)

    host = os.getenv("REMOTE_DB_HOST")
    if not host:
        return None

    return build_engine(
        os.getenv("REMOTE_DB_NAME") or get_db_name(),
        host=host,
        port=os.getenv("REMOTE_DB_PORT"),
        user=os.getenv("REMOTE_DB_USER"),
        password=os.getenv("REMOTE_DB_PASSWORD"),
    )


def dual_write(write_one_db_fn, *, engine_local, engine_remote, enable_remote=True):
    if engine_local is None:
        raise ValueError("engine_local is required")
    with engine_local.begin() as conn:
        write_one_db_fn(conn)

    exit_code = 0
    if enable_remote and engine_remote is not None:
        remote_dry_run = os.getenv("REMOTE_DB_DRY_RUN", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "y",
            "on",
        )
        if remote_dry_run:
            return exit_code
        try:
            with engine_remote.begin() as conn:
                write_one_db_fn(conn)
        except Exception:
            import traceback

            traceback.print_exc()
            exit_code = 2
    return exit_code


def bond_code2sql_fromat(symbol):
    """
    Convert a string or list into the SQL tuple format used by IN clauses.
    """
    if isinstance(symbol, list) and len(symbol) == 1:
        symbol = symbol[0]
    if isinstance(symbol, list):
        return str(tuple(symbol))
    if isinstance(symbol, (str, np.str_)):
        return str(tuple([symbol])).replace(",", "")
    return str(tuple([symbol])).replace(",", "")


def get_audit_schema() -> str | None:
    """
    Resolve audit schema/db name.

    Contract:
    - If EVENT_AUDIT_DB_URL is set, prefer its database name (path part).
    - Else use AUDIT_SCHEMA.
    """
    url = os.getenv("EVENT_AUDIT_DB_URL")
    if url:
        try:
            parsed = urlparse(url)
            name = parsed.path.lstrip("/") if parsed.path else None
            return name or None
        except Exception:
            return None
    schema = os.getenv("AUDIT_SCHEMA")
    return schema or None


def get_event_audit_log_table() -> str:
    """
    Audit log table name inside audit schema.

    Default remains wb_event_audit_log for backwards compatibility.
    """
    return (os.getenv("EVENT_AUDIT_LOG_TABLE") or "wb_event_audit_log").strip() or "wb_event_audit_log"


def get_audit_db_url() -> str:
    """
    Build audit DB URL.

    Contract:
    - Prefer EVENT_AUDIT_DB_URL when provided.
    - Else requires AUDIT_SCHEMA and DB_* credentials.
    """
    url = os.getenv("EVENT_AUDIT_DB_URL")
    if url:
        return url
    schema = os.getenv("AUDIT_SCHEMA")
    if not schema:
        raise RuntimeError("AUDIT_SCHEMA is required when EVENT_AUDIT_DB_URL is empty")
    user = os.getenv("DB_USER") or "root"
    password = os.getenv("DB_PASSWORD") or os.getenv("MYSQL_PWD") or ""
    host = os.getenv("DB_HOST") or "localhost"
    port = os.getenv("DB_PORT") or "3306"
    password = quote_plus(password) if password else ""
    auth = f"{user}:{password}" if password else user
    return f"mysql+pymysql://{auth}@{host}:{port}/{schema}"


def get_audit_engine() -> Engine:
    """
    Get (cached) SQLAlchemy engine for audit DB (webond_event_audit).
    """
    global _AUDIT_ENGINE
    if _AUDIT_ENGINE is None:
        _AUDIT_ENGINE = create_engine(get_audit_db_url(), pool_pre_ping=True)
    return _AUDIT_ENGINE
