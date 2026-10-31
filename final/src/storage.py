"""SQLite: три таблицы (countries, currencies, languages) + UPSERT."""
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def init_db(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS countries (
            business_key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            capital TEXT,
            population INTEGER,
            area_km2 REAL,
            iso2 TEXT,
            iso3 TEXT,
            region TEXT,
            currencies TEXT,
            languages TEXT,
            api_match INTEGER,
            source TEXT NOT NULL,
            collected_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            parser_version TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS currencies (
            business_key TEXT PRIMARY KEY,
            country_name TEXT NOT NULL,
            iso3 TEXT,
            currency_code TEXT NOT NULL,
            currency_name TEXT,
            currency_symbol TEXT,
            source TEXT NOT NULL,
            collected_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            parser_version TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS languages (
            business_key TEXT PRIMARY KEY,
            country_name TEXT NOT NULL,
            iso3 TEXT,
            language_name TEXT NOT NULL,
            language_native TEXT,
            source TEXT NOT NULL,
            collected_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            parser_version TEXT NOT NULL
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_country_name ON countries(name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_country_region ON countries(region)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_currency_iso3 ON currencies(iso3)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_language_iso3 ON languages(iso3)")

    conn.commit()
    return conn


def upsert_countries(conn, rows, version="1.0.0"):
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    ins = upd = 0
    for r in rows:
        bkey = hashlib.md5(r["name"].lower().encode()).hexdigest()
        cur.execute("""
            INSERT INTO countries (business_key, name, capital, population, area_km2,
                                   iso2, iso3, region, currencies, languages,
                                   api_match, source, collected_at, updated_at, parser_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(business_key) DO UPDATE SET
                capital=excluded.capital, population=excluded.population,
                area_km2=excluded.area_km2, iso2=excluded.iso2, iso3=excluded.iso3,
                region=excluded.region, currencies=excluded.currencies,
                languages=excluded.languages, api_match=excluded.api_match,
                updated_at=excluded.updated_at, parser_version=excluded.parser_version
        """, (bkey, r["name"], r.get("capital"), r.get("population"), r.get("area_km2"),
              r.get("iso2"), r.get("iso3"), r.get("region"), r.get("currencies"),
              r.get("languages"), int(r.get("api_match") or 0), r["source"],
              now, now, version))
        if cur.rowcount == 1: ins += 1
        else: upd += 1
    conn.commit()
    return ins, upd


def upsert_currencies(conn, rows, version="1.0.0"):
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    ins = upd = 0
    for r in rows:
        bkey = hashlib.md5(f"{r['country_name'].lower()}|{r['currency_code']}".encode()).hexdigest()
        cur.execute("""
            INSERT INTO currencies (business_key, country_name, iso3, currency_code,
                                    currency_name, currency_symbol, source,
                                    collected_at, updated_at, parser_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(business_key) DO UPDATE SET
                currency_name=excluded.currency_name,
                currency_symbol=excluded.currency_symbol,
                updated_at=excluded.updated_at,
                parser_version=excluded.parser_version
        """, (bkey, r["country_name"], r.get("iso3"), r["currency_code"],
              r.get("currency_name"), r.get("currency_symbol"), r["source"],
              now, now, version))
        if cur.rowcount == 1: ins += 1
        else: upd += 1
    conn.commit()
    return ins, upd


def upsert_languages(conn, rows, version="1.0.0"):
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    ins = upd = 0
    for r in rows:
        bkey = hashlib.md5(f"{r['country_name'].lower()}|{r['language_name']}".encode()).hexdigest()
        cur.execute("""
            INSERT INTO languages (business_key, country_name, iso3, language_name,
                                   language_native, source,
                                   collected_at, updated_at, parser_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(business_key) DO UPDATE SET
                language_native=excluded.language_native,
                updated_at=excluded.updated_at,
                parser_version=excluded.parser_version
        """, (bkey, r["country_name"], r.get("iso3"), r["language_name"],
              r.get("language_native"), r["source"], now, now, version))
        if cur.rowcount == 1: ins += 1
        else: upd += 1
    conn.commit()
    return ins, upd