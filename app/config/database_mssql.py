import os
from functools import lru_cache
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()


def _build_mssql_url() -> str:
    """
    Build MSSQL connection URL from env vars.

    Priority:
    1) BMT_MSSQL_URL (full SQLAlchemy URL)
    2) Individual env vars (host/user/password/database/etc),
       built as `mssql+pyodbc:///?odbc_connect=...`
    """
    direct_url = os.getenv("BMT_MSSQL_URL")
    if direct_url:
        return direct_url

    host = os.getenv("BMT_MSSQL_HOST")
    user = os.getenv("BMT_MSSQL_USER")
    password = os.getenv("BMT_MSSQL_PASSWORD")
    database = os.getenv("BMT_MSSQL_DATABASE")

    missing = [
        name
        for name, value in {
            "BMT_MSSQL_HOST": host,
            "BMT_MSSQL_USER": user,
            "BMT_MSSQL_PASSWORD": password,
            "BMT_MSSQL_DATABASE": database,
        }.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "MSSQL connection is not configured. "
            "Set BMT_MSSQL_URL or required fields: "
            + ", ".join(missing)
        )

    driver = os.getenv("BMT_MSSQL_DRIVER", "FreeTDS")
    port = os.getenv("BMT_MSSQL_PORT", "1433")
    tds_version = os.getenv("BMT_MSSQL_TDS_VERSION", "7.0")
    charset = os.getenv("BMT_MSSQL_CHARSET", "UTF-8")
    encrypt = os.getenv("BMT_MSSQL_ENCRYPT", "no")
    trust_cert = os.getenv("BMT_MSSQL_TRUST_SERVER_CERTIFICATE", "yes")

    server = f"{host},{port}" if port else host

    odbc_connect = quote_plus(
        (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={user};"
            f"PWD={password};"
            f"TDS_Version={tds_version};"
            f"ClientCharset={charset};"
            f"Encrypt={encrypt};"
            f"TrustServerCertificate={trust_cert};"
        )
    )

    return f"mssql+pyodbc:///?odbc_connect={odbc_connect}"


@lru_cache(maxsize=1)
def get_mssql_engine() -> Engine:
    # Lazy, cached initialization: app can boot without MSSQL configured.
    return create_engine(
        _build_mssql_url(),
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def _get_mssql_session_factory():
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=get_mssql_engine(),
    )


def get_mssql_db():
    db: Session = _get_mssql_session_factory()()
    try:
        yield db
    finally:
        db.close()
