"""
core/du_lieu.py – gộp từ 7 module (15/10/2026).

MỤC LỤC
  • data/cache.py – Disk-based cache with TTL using diskcache.
      hàm/lớp chính: CacheManager
  • data/database.py – DuckDB-based data repository.
      hàm/lớp chính: Database
  • data/financial_mapping.py – Chuẩn hóa BCTC từ mọi nguồn về MỘT bộ chỉ tiêu chuẩn (canonical items).
      hàm/lớp chính: strip_accents, norm_label, Item, to_matrix, canonicalize, infer_scale, apply_scale, wide_to_long, long_to_wide
  • data/data_normalizer.py – Data normalizer – converts raw provider data into the canonical internal schema.
      hàm/lớp chính: DataNormalizer
  • data/quarter_basis.py – Chuẩn hóa số liệu BCTC QUÝ về "số của riêng từng quý" trước khi cộng dồn (TTM / số năm).
      hàm/lớp chính: flow_columns, detect_basis, decumulate, normalize_quarters
  • data/ticker_directory.py – Comprehensive Stock Directory and Industry Baskets for Vietnam Equities.
      hàm/lớp chính: load_all_stocks, get_symbol_map, get_basket_names, get_tickers_for_basket, get_ticker_label, extract_symbol_from_label, get_formatted_options, find_option_for_symbol
  • data/data_repository.py – DataRepository – lớp truy cập dữ liệu duy nhất của hệ thống (Single Source of Truth).
      hàm/lớp chính: to_vnd, stitch_prices, fix_unadjusted_gaps, source_conflict, merge_financial_sources, DataRepository
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: data/cache.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Disk-based cache with TTL using diskcache.
"""


import logging
from typing import Any, Optional

import diskcache

from core.cau_hinh import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Simple disk cache with per-key TTL."""

    _instance: Optional["CacheManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = diskcache.Cache(str(settings.CACHE_DIR))
        return cls._instance

    @staticmethod
    def _key(key: str) -> str:
        return f"{settings.CACHE_SCHEMA_VERSION}:{key}"

    def get(self, key: str) -> Optional[Any]:
        try:
            return self._cache.get(self._key(key))
        except Exception as exc:
            logger.debug("Cache get error: %s", exc)
            return None

    def set(self, key: str, value: Any, ttl: int = 300):
        try:
            self._cache.set(self._key(key), value, expire=ttl)
        except Exception as exc:
            logger.debug("Cache set error: %s", exc)

    def delete(self, key: str):
        try:
            self._cache.delete(self._key(key))
        except Exception:
            pass

    def clear_prefix(self, prefix: str):
        try:
            versioned_prefix = self._key(prefix)
            for key in list(self._cache):
                if isinstance(key, str) and key.startswith(versioned_prefix):
                    self._cache.delete(key)
        except Exception as exc:
            logger.debug("Cache clear prefix error: %s", exc)

    def clear_all(self):
        try:
            self._cache.clear()
        except Exception:
            pass

    def stats(self) -> dict:
        try:
            return {
                "size": len(self._cache),
                "directory": str(settings.CACHE_DIR),
            }
        except Exception:
            return {}


cache = CacheManager()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: data/database.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
DuckDB-based data repository.

Tables:
  price_daily    – OHLCV day-level data
  price_intraday – intraday OHLCV
  financial_is   – income statement rows
  financial_bs   – balance sheet rows
  financial_cf   – cash flow rows
  financial_ratio– ratios
  company_info   – company metadata
  portfolio      – user portfolio positions
  analysis_log   – history of analyses performed
  reports_log    – history of generated PDF reports
"""


import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from core.cau_hinh import settings

logger = logging.getLogger(__name__)
ALLOWED_PRICE_TABLES = {"price_daily", "price_intraday"}

DDL = """
CREATE TABLE IF NOT EXISTS price_daily (
    symbol      VARCHAR NOT NULL,
    timestamp   TIMESTAMP NOT NULL,
    open        DOUBLE,
    high        DOUBLE,
    low         DOUBLE,
    close       DOUBLE NOT NULL,
    volume      BIGINT,
    value       DOUBLE,
    source      VARCHAR,
    interval    VARCHAR DEFAULT '1D',
    adjusted    BOOLEAN DEFAULT FALSE,
    fetched_at  TIMESTAMP,
    PRIMARY KEY (symbol, timestamp, adjusted)
);

CREATE TABLE IF NOT EXISTS price_intraday (
    symbol      VARCHAR NOT NULL,
    timestamp   TIMESTAMP NOT NULL,
    open        DOUBLE,
    high        DOUBLE,
    low         DOUBLE,
    close       DOUBLE NOT NULL,
    volume      BIGINT,
    value       DOUBLE,
    source      VARCHAR,
    interval    VARCHAR,
    adjusted    BOOLEAN DEFAULT FALSE,
    fetched_at  TIMESTAMP,
    PRIMARY KEY (symbol, timestamp, interval)
);

CREATE TABLE IF NOT EXISTS financial_is (
    id          INTEGER PRIMARY KEY,
    symbol      VARCHAR NOT NULL,
    period      VARCHAR,
    year        INTEGER,
    quarter     INTEGER,
    report_type VARCHAR DEFAULT 'consolidated',
    source      VARCHAR,
    fetched_at  TIMESTAMP,
    data        JSON
);

CREATE SEQUENCE IF NOT EXISTS seq_financial_is;
ALTER TABLE financial_is ALTER COLUMN id SET DEFAULT nextval('seq_financial_is');

CREATE TABLE IF NOT EXISTS financial_bs (
    id          INTEGER PRIMARY KEY,
    symbol      VARCHAR NOT NULL,
    period      VARCHAR,
    year        INTEGER,
    quarter     INTEGER,
    report_type VARCHAR DEFAULT 'consolidated',
    source      VARCHAR,
    fetched_at  TIMESTAMP,
    data        JSON
);

CREATE SEQUENCE IF NOT EXISTS seq_financial_bs;
ALTER TABLE financial_bs ALTER COLUMN id SET DEFAULT nextval('seq_financial_bs');

CREATE TABLE IF NOT EXISTS financial_cf (
    id          INTEGER PRIMARY KEY,
    symbol      VARCHAR NOT NULL,
    period      VARCHAR,
    year        INTEGER,
    quarter     INTEGER,
    report_type VARCHAR DEFAULT 'consolidated',
    source      VARCHAR,
    fetched_at  TIMESTAMP,
    data        JSON
);

CREATE SEQUENCE IF NOT EXISTS seq_financial_cf;
ALTER TABLE financial_cf ALTER COLUMN id SET DEFAULT nextval('seq_financial_cf');

CREATE TABLE IF NOT EXISTS financial_ratio (
    id          INTEGER PRIMARY KEY,
    symbol      VARCHAR NOT NULL,
    period      VARCHAR,
    year        INTEGER,
    quarter     INTEGER,
    source      VARCHAR,
    fetched_at  TIMESTAMP,
    data        JSON
);

CREATE SEQUENCE IF NOT EXISTS seq_financial_ratio;
ALTER TABLE financial_ratio ALTER COLUMN id SET DEFAULT nextval('seq_financial_ratio');

CREATE TABLE IF NOT EXISTS company_info (
    symbol      VARCHAR PRIMARY KEY,
    name        VARCHAR,
    exchange    VARCHAR,
    sector      VARCHAR,
    industry    VARCHAR,
    founded     VARCHAR,
    employees   INTEGER,
    website     VARCHAR,
    description TEXT,
    source      VARCHAR,
    fetched_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS portfolio (
    id          INTEGER PRIMARY KEY,
    portfolio_name VARCHAR DEFAULT 'default',
    symbol      VARCHAR NOT NULL,
    quantity    DOUBLE NOT NULL,
    buy_price   DOUBLE NOT NULL,
    buy_date    DATE,
    fee_pct     DOUBLE DEFAULT 0.0015,
    notes       TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE SEQUENCE IF NOT EXISTS seq_portfolio;
ALTER TABLE portfolio ALTER COLUMN id SET DEFAULT nextval('seq_portfolio');

CREATE TABLE IF NOT EXISTS analysis_log (
    id          INTEGER PRIMARY KEY,
    symbol      VARCHAR NOT NULL,
    analysis_type VARCHAR,
    score       DOUBLE,
    summary     TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE SEQUENCE IF NOT EXISTS seq_analysis_log;
ALTER TABLE analysis_log ALTER COLUMN id SET DEFAULT nextval('seq_analysis_log');

CREATE TABLE IF NOT EXISTS reports_log (
    id          INTEGER PRIMARY KEY,
    symbol      VARCHAR NOT NULL,
    report_type VARCHAR,
    file_path   VARCHAR,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE SEQUENCE IF NOT EXISTS seq_reports_log;
ALTER TABLE reports_log ALTER COLUMN id SET DEFAULT nextval('seq_reports_log');

CREATE TABLE IF NOT EXISTS financial_canonical (
    symbol      VARCHAR NOT NULL,
    period_type VARCHAR NOT NULL,
    period_key  INTEGER NOT NULL,
    item        VARCHAR NOT NULL,
    value       DOUBLE,
    source      VARCHAR,
    fetched_at  TIMESTAMP,
    PRIMARY KEY (symbol, period_type, period_key, item)
);

CREATE TABLE IF NOT EXISTS documents (
    doc_id      VARCHAR PRIMARY KEY,
    symbol      VARCHAR NOT NULL,
    year        INTEGER,
    period      VARCHAR,
    doc_type    VARCHAR,
    title       VARCHAR,
    url         VARCHAR,
    local_path  VARCHAR,
    source      VARCHAR,
    size_bytes  BIGINT,
    fetched_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS news_items (
    news_id     VARCHAR PRIMARY KEY,
    symbol      VARCHAR,
    title       VARCHAR,
    url         VARCHAR,
    source      VARCHAR,
    published_at TIMESTAMP,
    sentiment   VARCHAR,
    summary     TEXT,
    fetched_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watchlist (
    symbol      VARCHAR PRIMARY KEY,
    note        VARCHAR,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_alerts (
    id          INTEGER PRIMARY KEY,
    symbol      VARCHAR NOT NULL,
    condition   VARCHAR NOT NULL,
    threshold   DOUBLE NOT NULL,
    active      BOOLEAN DEFAULT TRUE,
    triggered_at TIMESTAMP,
    triggered_price DOUBLE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE SEQUENCE IF NOT EXISTS seq_price_alerts;
ALTER TABLE price_alerts ALTER COLUMN id SET DEFAULT nextval('seq_price_alerts');

CREATE TABLE IF NOT EXISTS update_log (
    job         VARCHAR,
    status      VARCHAR,
    detail      TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


class Database:
    """
    Singleton DuckDB connection manager.

    Kết nối DuckDB không an toàn khi dùng chung giữa nhiều luồng (Streamlit, bộ lọc chạy song song).
    Mỗi luồng vì vậy dùng một cursor riêng (`base.cursor()`), cùng trỏ tới một cơ sở dữ liệu.
    """

    _instance: Optional["Database"] = None

    @property
    def _conn(self):
        base = self.__dict__.get("_base")
        if base is None:
            return None
        local = self.__dict__.setdefault("_local", threading.local())
        cur = getattr(local, "cursor", None)
        if cur is None or getattr(local, "base_id", None) != id(base):
            cur = base if threading.current_thread() is threading.main_thread() else base.cursor()
            local.cursor, local.base_id = cur, id(base)
        return cur

    @_conn.setter
    def _conn(self, value):
        self.__dict__["_base"] = value
        self.__dict__["_local"] = threading.local()

    def __new__(cls, db_path: Optional[str] = None):
        if db_path is not None:
            instance = super().__new__(cls)
            instance._conn = None
            instance._init_db(db_path)
            return instance

        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._conn = None
            cls._instance._init_db()
        return cls._instance

    def _init_db(self, custom_path: Optional[str] = None):
        db_path = custom_path or settings.DB_PATH
        self.mode = "initializing"
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = duckdb.connect(db_path)
            self.mode = "memory" if db_path == ":memory:" else "read_write"
            # Run DDL statements one at a time to make errors easier to diagnose
            for stmt in [s.strip() for s in DDL.split(";") if s.strip()]:
                try:
                    self._conn.execute(stmt)
                except Exception as e:
                    # Some statements may already exist — log but continue
                    logger.debug("DDL note: %s", e)
            logger.info("Database initialised at %s", db_path)
        except Exception as exc:
            try:
                # If file is locked by running app, fallback to read-only connection
                self._conn = duckdb.connect(db_path, read_only=True)
                self.mode = "read_only"
                logger.info("Database opened in read-only mode at %s", db_path)
            except Exception:
                logger.warning("DuckDB file lock/WAL error (%s), falling back to in-memory", exc)
                self._conn = duckdb.connect(":memory:")
                self.mode = "ephemeral"
                for stmt in [s.strip() for s in DDL.split(";") if s.strip()]:
                    try:
                        self._conn.execute(stmt)
                    except Exception:
                        pass

    def close(self):
        """Close connection cleanly."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        return self._conn

    @property
    def is_writable(self) -> bool:
        return self.mode in {"read_write", "memory", "ephemeral"}

    @property
    def is_persistent(self) -> bool:
        return self.mode == "read_write"

    # ─────────────────── Price ───────────────────────────────────────────────

    def upsert_price(self, df: pd.DataFrame, table: str = "price_daily"):
        """Insert-or-replace price rows matching existing columns."""
        if df.empty:
            return
        if table not in ALLOWED_PRICE_TABLES:
            raise ValueError(f"Bảng giá không được phép: {table}")
        try:
            tbl_info = self._conn.execute(f"PRAGMA table_info('{table}')").df()
            tbl_cols = tbl_info["name"].tolist()
            common_cols = [c for c in tbl_cols if c in df.columns]
            if not common_cols:
                return
            cols_str = ", ".join(common_cols)
            self._conn.register("_tmp_price", df[common_cols])
            try:
                self._conn.execute(f"""
                    INSERT OR REPLACE INTO {table} ({cols_str})
                    SELECT {cols_str} FROM _tmp_price
                """)
            finally:
                self._conn.unregister("_tmp_price")
        except Exception as exc:
            logger.error("upsert_price failed: %s", exc)

    def get_price(self, symbol: str, start: Optional[str] = None, end: Optional[str] = None,
                  table: str = "price_daily") -> pd.DataFrame:
        if table not in ALLOWED_PRICE_TABLES:
            raise ValueError(f"Bảng giá không được phép: {table}")
        try:
            query = f"SELECT * FROM {table} WHERE symbol = ?"
            params = [symbol.upper()]
            if start:
                query += " AND timestamp >= ?"
                params.append(start)
            if end:
                query += " AND timestamp <= ?"
                params.append(end)
            query += " ORDER BY timestamp"
            return self._conn.execute(query, params).df()
        except Exception as exc:
            logger.error("get_price failed: %s", exc)
            return pd.DataFrame()

    # ─────────────────── Company ─────────────────────────────────────────────

    def upsert_company(self, info: dict):
        try:
            self._conn.execute("""
                INSERT OR REPLACE INTO company_info
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                info.get("symbol", ""),
                info.get("name", ""),
                info.get("exchange", ""),
                info.get("sector", ""),
                info.get("industry", ""),
                info.get("founded", ""),
                info.get("employees"),
                info.get("website", ""),
                info.get("description", ""),
                info.get("source", ""),
                datetime.now(),
            ])
        except Exception as exc:
            logger.error("upsert_company failed: %s", exc)

    def get_company(self, symbol: str) -> dict:
        try:
            row = self._conn.execute(
                "SELECT * FROM company_info WHERE symbol = ?", [symbol.upper()]
            ).fetchone()
            if not row:
                return {}
            cols = [d[0] for d in self._conn.description]
            return dict(zip(cols, row))
        except Exception:
            return {}

    # ─────────────────── Portfolio ───────────────────────────────────────────

    def add_position(self, portfolio_name: str, symbol: str, quantity: float,
                     buy_price: float, buy_date: str = "", fee_pct: float = 0.0015,
                     notes: str = ""):
        try:
            self._conn.execute(
                "INSERT INTO portfolio (portfolio_name, symbol, quantity, buy_price, buy_date, fee_pct, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [portfolio_name, symbol.upper(), quantity, buy_price, buy_date, fee_pct, notes],
            )
        except Exception as exc:
            logger.error("add_position failed: %s", exc)

    def get_portfolio(self, portfolio_name: str = "default") -> pd.DataFrame:
        try:
            return self._conn.execute(
                "SELECT * FROM portfolio WHERE portfolio_name = ? ORDER BY created_at",
                [portfolio_name],
            ).df()
        except Exception:
            return pd.DataFrame()

    def delete_position(self, position_id: int):
        try:
            self._conn.execute("DELETE FROM portfolio WHERE id = ?", [position_id])
        except Exception as exc:
            logger.error("delete_position failed: %s", exc)

    # ─────────────────── Analysis Log ────────────────────────────────────────

    def log_analysis(self, symbol: str, analysis_type: str, score: float, summary: str):
        try:
            self._conn.execute(
                "INSERT INTO analysis_log (symbol, analysis_type, score, summary) VALUES (?, ?, ?, ?)",
                [symbol.upper(), analysis_type, score, summary],
            )
        except Exception as exc:
            logger.error("log_analysis failed: %s", exc)

    def get_analysis_history(self, symbol: str = "", limit: int = 50) -> pd.DataFrame:
        try:
            if symbol:
                return self._conn.execute(
                    "SELECT * FROM analysis_log WHERE symbol = ? ORDER BY created_at DESC LIMIT ?",
                    [symbol.upper(), limit],
                ).df()
            return self._conn.execute(
                "SELECT * FROM analysis_log ORDER BY created_at DESC LIMIT ?", [limit]
            ).df()
        except Exception:
            return pd.DataFrame()

    # ─────────────────── Reports Log ─────────────────────────────────────────

    def log_report(self, symbol: str, report_type: str, file_path: str):
        try:
            self._conn.execute(
                "INSERT INTO reports_log (symbol, report_type, file_path) VALUES (?, ?, ?)",
                [symbol.upper(), report_type, file_path],
            )
        except Exception as exc:
            logger.error("log_report failed: %s", exc)

    def get_reports_history(self, limit: int = 50) -> pd.DataFrame:
        try:
            return self._conn.execute(
                "SELECT * FROM reports_log ORDER BY created_at DESC LIMIT ?", [limit]
            ).df()
        except Exception:
            return pd.DataFrame()

    # ─────────────────── Financial (canonical, long format) ──────────────────

    def upsert_financial(self, symbol: str, period_type: str, long_df: pd.DataFrame):
        """long_df columns: period_key, item, value, source."""
        if long_df is None or long_df.empty:
            return
        try:
            df = long_df[["period_key", "item", "value", "source"]].copy()
            df.insert(0, "period_type", period_type)
            df.insert(0, "symbol", symbol.upper())
            df["fetched_at"] = datetime.now()
            self._conn.register("_tmp_fin", df)
            self._conn.execute(
                "INSERT OR REPLACE INTO financial_canonical "
                "SELECT symbol, period_type, CAST(period_key AS INTEGER), item, value, source, fetched_at FROM _tmp_fin"
            )
            self._conn.unregister("_tmp_fin")
        except Exception as exc:
            logger.error("upsert_financial failed: %s", exc)

    def get_financial(self, symbol: str, period_type: str) -> pd.DataFrame:
        try:
            return self._conn.execute(
                "SELECT period_key, item, value, source, fetched_at FROM financial_canonical "
                "WHERE symbol = ? AND period_type = ? ORDER BY period_key",
                [symbol.upper(), period_type],
            ).df()
        except Exception:
            return pd.DataFrame()

    # ─────────────────── Documents ───────────────────────────────────────────

    def upsert_document(self, doc: dict):
        cols = ["doc_id", "symbol", "year", "period", "doc_type", "title", "url",
                "local_path", "source", "size_bytes", "fetched_at"]
        row = {c: doc.get(c) for c in cols}
        row["fetched_at"] = row["fetched_at"] or datetime.now()
        try:
            self._conn.execute(
                f"INSERT OR REPLACE INTO documents ({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})",
                [row[c] for c in cols],
            )
        except Exception as exc:
            logger.error("upsert_document failed: %s", exc)

    def get_documents(self, symbol: str) -> pd.DataFrame:
        try:
            return self._conn.execute(
                "SELECT * FROM documents WHERE symbol = ? ORDER BY year DESC NULLS LAST, doc_type",
                [symbol.upper()],
            ).df()
        except Exception:
            return pd.DataFrame()

    # ─────────────────── News ────────────────────────────────────────────────

    def upsert_news(self, items: list):
        cols = ["news_id", "symbol", "title", "url", "source", "published_at", "sentiment", "summary", "fetched_at"]
        for it in items or []:
            try:
                row = [it.get(c) for c in cols]
                row[-1] = row[-1] or datetime.now()
                self._conn.execute(
                    f"INSERT OR IGNORE INTO news_items ({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})",
                    row,
                )
            except Exception as exc:
                logger.debug("upsert_news skip: %s", exc)

    def get_news(self, symbol: str = "", days: int = 30, limit: int = 200) -> pd.DataFrame:
        try:
            q = ("SELECT * FROM news_items WHERE COALESCE(published_at, fetched_at) >= "
                 "CURRENT_TIMESTAMP - (? * INTERVAL 1 DAY)")
            params: list = [days]
            if symbol:
                q += " AND symbol = ?"
                params.append(symbol.upper())
            q += " ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT ?"
            params.append(limit)
            return self._conn.execute(q, params).df()
        except Exception:
            return pd.DataFrame()

    # ─────────────────── Watchlist & Alerts ──────────────────────────────────

    def add_watch(self, symbol: str, note: str = ""):
        try:
            self._conn.execute("INSERT OR REPLACE INTO watchlist (symbol, note, added_at) VALUES (?, ?, ?)",
                               [symbol.upper(), note, datetime.now()])
        except Exception as exc:
            logger.error("add_watch failed: %s", exc)

    def remove_watch(self, symbol: str):
        try:
            self._conn.execute("DELETE FROM watchlist WHERE symbol = ?", [symbol.upper()])
        except Exception as exc:
            logger.error("remove_watch failed: %s", exc)

    def get_watchlist(self) -> pd.DataFrame:
        try:
            return self._conn.execute("SELECT * FROM watchlist ORDER BY added_at").df()
        except Exception:
            return pd.DataFrame(columns=["symbol", "note", "added_at"])

    def add_alert(self, symbol: str, condition: str, threshold: float):
        try:
            self._conn.execute("INSERT INTO price_alerts (symbol, condition, threshold) VALUES (?, ?, ?)",
                               [symbol.upper(), condition, float(threshold)])
        except Exception as exc:
            logger.error("add_alert failed: %s", exc)

    def get_alerts(self, active_only: bool = False) -> pd.DataFrame:
        try:
            q = "SELECT * FROM price_alerts"
            if active_only:
                q += " WHERE active"
            return self._conn.execute(q + " ORDER BY created_at DESC").df()
        except Exception:
            return pd.DataFrame()

    def mark_alert_triggered(self, alert_id: int, price: float):
        try:
            self._conn.execute(
                "UPDATE price_alerts SET active = FALSE, triggered_at = ?, triggered_price = ? WHERE id = ?",
                [datetime.now(), float(price), int(alert_id)],
            )
        except Exception as exc:
            logger.error("mark_alert_triggered failed: %s", exc)

    def delete_alert(self, alert_id: int):
        try:
            self._conn.execute("DELETE FROM price_alerts WHERE id = ?", [int(alert_id)])
        except Exception as exc:
            logger.error("delete_alert failed: %s", exc)

    # ─────────────────── Update log ──────────────────────────────────────────

    def log_update(self, job: str, status: str, detail: str = ""):
        try:
            self._conn.execute("INSERT INTO update_log (job, status, detail, created_at) VALUES (?, ?, ?, ?)",
                               [job, status, detail[:4000], datetime.now()])
        except Exception as exc:
            logger.debug("log_update failed: %s", exc)

    def get_update_log(self, limit: int = 50) -> pd.DataFrame:
        try:
            return self._conn.execute("SELECT * FROM update_log ORDER BY created_at DESC LIMIT ?", [limit]).df()
        except Exception:
            return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: data/financial_mapping.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Chuẩn hóa BCTC từ mọi nguồn về MỘT bộ chỉ tiêu chuẩn (canonical items).

Đầu vào chấp nhận:
  (a) Dạng ma trận  : cột item / item_en / item_id + mỗi cột là một kỳ (vnstock v4 VCI/KBS, Vietstock)
  (b) Dạng bảng     : mỗi dòng là một kỳ, có cột Năm / Kỳ, mỗi cột là một chỉ tiêu (vnstock v3)
Đầu ra: DataFrame "rộng" – index = khóa kỳ (năm*10 + quý, tăng dần), cột = chỉ tiêu chuẩn,
giá trị quy về VND (trừ EPS/BVPS tính bằng đồng/cp và số cổ phiếu).

Quy tắc khớp cho từng chỉ tiêu, theo thứ tự ưu tiên:
  1. item_id trùng khớp chính xác (KBS đã chuẩn hóa: revenue, net_profit, total_assets…)
  2. Tên tiếng Việt BẮT ĐẦU bằng mẫu (sau khi bỏ số thứ tự "I.", "1.", "A."…)
  3. Tên tiếng Việt CHỨA mẫu
  4. Tương tự với tên tiếng Anh
Mọi bước đều loại các dòng chứa từ loại trừ (vd "tăng trưởng", "%", "biên") để tránh
lấy nhầm dòng "Tăng trưởng doanh thu (%)" thay cho "Doanh thu".
So khớp cả bản có dấu và bản bỏ dấu tiếng Việt.
"""


import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd



def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d").replace("Đ", "D")


_ENUM_RE = re.compile(r"^\s*(?:[-–•+]\s*)?(?:(?:[ivxlcdm]+|[a-z]|\d+(?:\.\d+)*)\s*[\.\)\-–:/]\s*)?", re.I)


# Cặp "lãi/lỗ", "lợi nhuận/(lỗ)", "lãi (lỗ)", "profit/loss", "profit/(loss)"… → bỏ phần "lỗ/loss":
#   "Lợi nhuận/(lỗ) trước thuế" → "lợi nhuận trước thuế", "Operating Profit/Loss" → "operating profit".
# (dấu "/" ở đây KHÔNG phải tỷ số – trước đây bị loại nhầm, làm mất LN thuần HĐKD, LN trước thuế, LNST từ VCI)
_PAIR_RE = re.compile(r"(lãi|lời|lợi nhuận|thu nhập|profit|gain|income|earnings)\s*(?:/\s*\(?|\()\s*(lỗ|loss|losses|chi phí|expense)\s*\)?",
                      re.I)


def _pair_norm(t: str) -> str:
    return _PAIR_RE.sub(lambda m: m.group(1), t)


def norm_label(text) -> str:
    """Chuẩn hóa nhãn: chữ thường, bỏ số thứ tự đầu dòng, gộp cặp lãi/lỗ, gộp khoảng trắng."""
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return ""
    t = unicodedata.normalize("NFC", str(text)).lower().strip()
    t = _ENUM_RE.sub("", t, count=1)
    t = _pair_norm(t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


@dataclass
class Item:
    key: str
    statement: str            # is | bs | cf | ratio
    label_vi: str
    ids: List[str] = field(default_factory=list)
    vi: List[str] = field(default_factory=list)
    en: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    unit: str = "vnd"         # vnd | per_share | shares | ratio


_COMMON_EXCL = ["tăng trưởng", "growth", "%", "yoy", "qoq", "biên", "margin", "vòng quay", "turnover",
                "/", "trên ", " per ", "tỷ lệ", "ratio", "tỷ suất"]

CANONICAL_ITEMS: List[Item] = [
    # ── Kết quả kinh doanh ──
    Item("revenue", "is", "Doanh thu thuần",
         ids=["revenue", "net_revenue", "net_sales", "doanh_thu_thuan", "operating_income_revenue"],
         vi=["doanh thu thuần về bán hàng", "doanh thu thuần", "doanh số thuần", "doanh thu"],
         en=["net revenue", "net sales", "revenue"],
         exclude=_COMMON_EXCL + ["giảm trừ", "deduction", "tài chính", "financial", "khác", "other",
                                 "chưa thực hiện", "unearned", "nhận trước"]),
    Item("cogs", "is", "Giá vốn hàng bán", ids=["cost_of_goods_sold", "cogs"],
         vi=["giá vốn hàng bán", "giá vốn"], en=["cost of goods sold", "cost of sales"],
         exclude=_COMMON_EXCL),
    Item("gross_profit", "is", "Lợi nhuận gộp", ids=["gross_profit"],
         vi=["lợi nhuận gộp"], en=["gross profit"], exclude=_COMMON_EXCL),
    Item("financial_income", "is", "Doanh thu hoạt động tài chính", ids=["financial_income"],
         vi=["doanh thu hoạt động tài chính"], en=["financial income"], exclude=_COMMON_EXCL),
    Item("financial_expense", "is", "Chi phí tài chính", ids=["finance_expenses", "financial_expenses"],
         vi=["chi phí tài chính"], en=["financial expense", "finance expense"], exclude=_COMMON_EXCL + ["lãi vay"]),
    Item("interest_expense", "is", "Chi phí lãi vay", ids=["interest_expense", "interest_expenses"],
         vi=["trong đó: chi phí lãi vay", "chi phí lãi vay"], en=["interest expense"], exclude=_COMMON_EXCL),
    # Bước 9: phần lãi/lỗ công ty liên doanh, liên kết – tách khỏi EBIT cốt lõi (DCF/EV), tài sản tương ứng cộng riêng
    Item("associates_income", "is", "Lãi/lỗ từ công ty liên doanh, liên kết",
         ids=["profit_from_associates", "share_of_profit_of_associates", "profit_loss_from_joint_ventures",
              "gain_loss_from_joint_ventures_and_associates"],
         vi=["lãi từ công ty liên doanh", "lãi trong công ty liên doanh", "phần lãi trong công ty liên doanh",
             "phần lãi hoặc lỗ trong công ty liên doanh", "lợi nhuận từ công ty liên doanh",
             "lợi nhuận trong công ty liên doanh", "lãi lỗ trong công ty liên doanh"],
         en=["share of profit of associates", "share of profits of associates", "profit from associates",
             "share of profit from joint ventures", "joint ventures and associates"],
         exclude=_COMMON_EXCL + ["đầu tư vào", "investment in", "investments in"]),
    Item("selling_expense", "is", "Chi phí bán hàng", ids=["selling_expenses"],
         vi=["chi phí bán hàng"], en=["selling expense"], exclude=_COMMON_EXCL),
    Item("admin_expense", "is", "Chi phí quản lý doanh nghiệp", ids=["admin_expenses", "general_and_administrative_expenses"],
         vi=["chi phí quản lý doanh nghiệp", "chi phí quản lý"], en=["general and administrative", "administrative expense"],
         exclude=_COMMON_EXCL),
    Item("operating_profit", "is", "Lợi nhuận thuần từ HĐKD", ids=["operating_profit"],
         vi=["lợi nhuận thuần từ hoạt động kinh doanh", "lợi nhuận từ hoạt động kinh doanh", "lãi từ hoạt động kinh doanh",
             "lãi thuần từ hoạt động kinh doanh", "lợi nhuận thuần từ hđkd", "lợi nhuận hoạt động"],
         en=["operating profit", "profit from operating activities", "net operating profit", "operating income"], exclude=_COMMON_EXCL + ["trước thuế", "before tax"]),
    Item("profit_before_tax", "is", "Lợi nhuận trước thuế", ids=["profit_before_tax"],
         vi=["tổng lợi nhuận kế toán trước thuế", "lợi nhuận trước thuế", "lãi trước thuế", "ln trước thuế",
             "lãi ròng trước thuế", "lợi nhuận kế toán trước thuế", "tổng lợi nhuận trước thuế"],
         en=["profit before tax", "accounting profit before tax", "earnings before tax", "pre-tax profit"],
         exclude=_COMMON_EXCL),
    Item("income_tax", "is", "Chi phí thuế TNDN", ids=["income_tax", "corporate_income_tax"],
         vi=["chi phí thuế thu nhập doanh nghiệp", "chi phí thuế tndn hiện hành", "thuế thu nhập doanh nghiệp"],
         en=["income tax expense", "corporate income tax"],
         exclude=_COMMON_EXCL + ["hoãn lại", "deferred", "lợi nhuận", "lãi", "trước thuế", "sau thuế", "profit", "before tax",
                                 "after tax", "phải nộp", "payable"]),
    Item("net_income", "is", "Lợi nhuận sau thuế", ids=["net_profit", "net_profit_after_tax", "profit_after_tax"],
         vi=["lợi nhuận sau thuế thu nhập doanh nghiệp", "lợi nhuận sau thuế", "lãi sau thuế", "lãi thuần sau thuế",
             "lợi nhuận kế toán sau thuế", "lợi nhuận thuần"],
         en=["net profit after tax", "profit after tax", "net profit", "net income", "profit for the year"],
         exclude=_COMMON_EXCL + ["công ty mẹ", "parent", "thiểu số", "minority", "không kiểm soát",
                                 "non-controlling", "chưa phân phối", "undistributed", "hoạt động kinh doanh",
                                 "hđkd", "operating", "trước thuế", "before tax"]),
    Item("net_income_parent", "is", "LNST của cổ đông công ty mẹ",
         ids=["net_profit_parent", "profit_attributable_to_parent", "net_profit_attributable_to_parent"],
         vi=["lợi nhuận sau thuế của cổ đông công ty mẹ", "cổ đông của công ty mẹ", "cổ đông công ty mẹ",
             "lợi nhuận sau thuế phân bổ cho chủ sở hữu", "phân bổ cho chủ sở hữu"],
         en=["attributable to parent", "attributable to owners of the parent", "parent company", "attributable to owners"],
         exclude=_COMMON_EXCL),
    Item("eps", "is", "EPS cơ bản (đồng/cp)", ids=["eps", "basic_eps", "earnings_per_share"],
         vi=["lãi cơ bản trên cổ phiếu", "lãi cơ bản trên mỗi cổ phiếu", "eps"],
         en=["basic earnings per share", "earnings per share", "eps"],
         exclude=["pha loãng", "diluted", "tăng trưởng", "growth", "%"], unit="per_share"),
    # Ngân hàng
    Item("net_interest_income", "is", "Thu nhập lãi thuần", ids=["net_interest_income"],
         vi=["thu nhập lãi thuần"], en=["net interest income"], exclude=_COMMON_EXCL),
    Item("total_operating_income", "is", "Tổng thu nhập hoạt động", ids=["total_operating_income"],
         vi=["tổng thu nhập hoạt động"], en=["total operating income"], exclude=_COMMON_EXCL),
    Item("provision_expense", "is", "Chi phí dự phòng rủi ro tín dụng", ids=["provision_for_credit_losses"],
         vi=["chi phí dự phòng rủi ro tín dụng"], en=["provision for credit losses", "credit loss expense"],
         exclude=_COMMON_EXCL),

    # ── Cân đối kế toán ──
    Item("cash", "bs", "Tiền và tương đương tiền", ids=["cash_and_cash_equivalents", "cash"],
         vi=["tiền và các khoản tương đương tiền", "tiền và tương đương tiền"], en=["cash and cash equivalents"],
         exclude=_COMMON_EXCL + ["đầu kỳ", "cuối kỳ", "beginning", "end of", "tăng", "giảm", "increase",
                                 "lưu chuyển", "ảnh hưởng"]),
    Item("short_term_investments", "bs", "Đầu tư tài chính ngắn hạn", ids=["short_term_investments"],
         vi=["đầu tư tài chính ngắn hạn", "các khoản đầu tư tài chính ngắn hạn"],
         en=["short-term investments", "short term financial investments", "short-term financial investments"],
         exclude=_COMMON_EXCL),
    Item("long_term_investments", "bs", "Đầu tư tài chính dài hạn",
         ids=["long_term_investments", "long_term_financial_investments"],
         vi=["đầu tư tài chính dài hạn", "các khoản đầu tư tài chính dài hạn"],
         en=["long-term investments", "long-term financial investments", "long term financial investments"],
         exclude=_COMMON_EXCL + ["dự phòng", "provision", "khác", "other", "giảm giá"]),
    Item("receivables", "bs", "Phải thu ngắn hạn", ids=["short_term_receivables", "accounts_receivable"],
         vi=["các khoản phải thu ngắn hạn", "phải thu ngắn hạn"], en=["short-term receivables", "accounts receivable"],
         exclude=_COMMON_EXCL + ["khác", "other", "dự phòng", "provision", "nội bộ"]),
    Item("inventory", "bs", "Hàng tồn kho", ids=["inventories", "inventory"],
         vi=["hàng tồn kho"], en=["inventories", "inventory"],
         exclude=_COMMON_EXCL + ["dự phòng", "provision", "giảm giá", "tăng", "giảm"]),
    Item("current_assets", "bs", "Tài sản ngắn hạn", ids=["current_assets", "short_term_assets"],
         vi=["tài sản ngắn hạn"], en=["current assets", "short-term assets"],
         exclude=_COMMON_EXCL + ["khác", "other", "dài hạn"]),
    Item("fixed_assets", "bs", "Tài sản cố định", ids=["fixed_assets"],
         vi=["tài sản cố định"], en=["fixed assets"],
         exclude=_COMMON_EXCL + ["khấu hao", "depreciation", "mua sắm", "purchase", "thanh lý", "disposal",
                                 "vô hình", "intangible", "thuê tài chính", "xây dựng"]),
    Item("total_assets", "bs", "Tổng tài sản", ids=["total_assets", "assets"],
         vi=["tổng cộng tài sản", "tổng tài sản"], en=["total assets"],
         exclude=_COMMON_EXCL + ["lợi nhuận", "return", "roa"]),
    Item("current_liabilities", "bs", "Nợ ngắn hạn", ids=["current_liabilities", "short_term_liabilities"],
         vi=["nợ ngắn hạn"], en=["current liabilities", "short-term liabilities"],
         exclude=_COMMON_EXCL + ["vay", "borrow", "khác", "other"]),
    Item("long_term_liabilities", "bs", "Nợ dài hạn", ids=["long_term_liabilities", "non_current_liabilities"],
         vi=["nợ dài hạn"], en=["long-term liabilities", "non-current liabilities"],
         exclude=_COMMON_EXCL + ["vay", "borrow", "khác", "other"]),
    Item("payables", "bs", "Phải trả người bán ngắn hạn", ids=["accounts_payable", "short_term_trade_payables"],
         vi=["phải trả người bán ngắn hạn", "phải trả người bán"], en=["short-term trade payables", "accounts payable", "trade payables"],
         exclude=_COMMON_EXCL + ["dài hạn", "long-term", "trả trước", "advance"]),
    Item("short_term_debt", "bs", "Vay ngắn hạn", ids=["short_term_borrowings", "short_term_debt"],
         vi=["vay và nợ thuê tài chính ngắn hạn", "vay và nợ ngắn hạn", "vay ngắn hạn"],
         en=["short-term borrowings", "short-term debt", "short-term loans"], exclude=_COMMON_EXCL),
    Item("long_term_debt", "bs", "Vay dài hạn", ids=["long_term_borrowings", "long_term_debt"],
         vi=["vay và nợ thuê tài chính dài hạn", "vay và nợ dài hạn", "vay dài hạn"],
         en=["long-term borrowings", "long-term debt", "long-term loans"], exclude=_COMMON_EXCL),
    Item("total_liabilities", "bs", "Nợ phải trả", ids=["total_liabilities", "liabilities"],
         vi=["tổng nợ phải trả", "nợ phải trả"], en=["total liabilities", "liabilities"],
         exclude=_COMMON_EXCL + ["ngắn hạn", "dài hạn", "short", "long", "khác", "other", "vốn chủ",
                                 "equity", "người bán", "supplier", "nguồn vốn"]),
    Item("equity", "bs", "Vốn chủ sở hữu", ids=["equity", "owners_equity", "total_equity"],
         vi=["vốn chủ sở hữu"], en=["owner's equity", "owners' equity", "total equity", "equity"],
         exclude=_COMMON_EXCL + ["nợ phải trả và", "liabilities and", "nguồn vốn", "roe", "lợi nhuận",
                                 "return", "khác", "other", "vốn góp", "contributed", "thay đổi", "change"]),
    Item("minority_interest", "bs", "Lợi ích cổ đông không kiểm soát", ids=["minority_interest", "non_controlling_interest"],
         vi=["lợi ích cổ đông không kiểm soát", "lợi ích của cổ đông thiểu số", "cổ đông thiểu số"],
         en=["non-controlling interest", "minority interest"], exclude=_COMMON_EXCL),
    Item("charter_capital", "bs", "Vốn góp của chủ sở hữu", ids=["charter_capital", "share_capital", "paid_in_capital"],
         vi=["vốn góp của chủ sở hữu", "vốn đầu tư của chủ sở hữu", "vốn điều lệ", "vốn cổ phần"],
         en=["paid-in capital", "share capital", "charter capital", "owner's capital"], exclude=_COMMON_EXCL),
    Item("retained_earnings", "bs", "LNST chưa phân phối", ids=["retained_earnings", "undistributed_earnings_after_tax"],
         vi=["lợi nhuận sau thuế chưa phân phối", "lợi nhuận chưa phân phối"], en=["undistributed", "retained earnings"],
         exclude=_COMMON_EXCL),
    Item("customer_loans", "bs", "Cho vay khách hàng", ids=["loans_to_customers"],
         vi=["cho vay khách hàng"], en=["loans to customers"], exclude=_COMMON_EXCL + ["dự phòng", "provision"]),
    Item("customer_deposits", "bs", "Tiền gửi của khách hàng", ids=["deposits_from_customers", "customer_deposits"],
         vi=["tiền gửi của khách hàng"], en=["deposits from customers", "customer deposits"], exclude=_COMMON_EXCL),

    # ── Lưu chuyển tiền tệ ──
    Item("depreciation", "cf", "Khấu hao TSCĐ", ids=["depreciation", "depreciation_and_amortization"],
         vi=["khấu hao tài sản cố định", "khấu hao tscđ", "khấu hao"], en=["depreciation"],
         exclude=["lũy kế", "accumulated", "%"]),
    Item("cfo", "cf", "LCTT thuần từ HĐKD",
         ids=["operating_cash_flow", "net_cash_flows_from_operating_activities", "cash_flow_from_operating_activities"],
         vi=["lưu chuyển tiền thuần từ hoạt động kinh doanh", "lưu chuyển tiền thuần từ các hoạt động sản xuất kinh doanh",
             "lưu chuyển tiền tệ ròng từ các hoạt động sản xuất kinh doanh", "lưu chuyển tiền thuần từ hđkd"],
         en=["net cash flows from operating", "net cash from operating", "cash flows from operating activities"],
         exclude=["trước", "before", "vốn lưu động", "working capital", "%"]),
    Item("cfi", "cf", "LCTT thuần từ HĐ đầu tư",
         ids=["investing_cash_flow", "net_cash_flows_from_investing_activities"],
         vi=["lưu chuyển tiền thuần từ hoạt động đầu tư", "lưu chuyển tiền tệ ròng từ hoạt động đầu tư"],
         en=["net cash flows from investing", "investing activities"], exclude=["%"]),
    Item("cff", "cf", "LCTT thuần từ HĐ tài chính",
         ids=["financing_cash_flow", "net_cash_flows_from_financing_activities"],
         vi=["lưu chuyển tiền thuần từ hoạt động tài chính", "lưu chuyển tiền tệ ròng từ hoạt động tài chính"],
         en=["net cash flows from financing", "financing activities"], exclude=["%"]),
    Item("capex", "cf", "Tiền chi mua sắm TSCĐ", ids=["purchase_of_fixed_assets", "capex", "capital_expenditure"],
         vi=["tiền chi để mua sắm, xây dựng tài sản cố định", "tiền chi để mua sắm", "mua sắm tài sản cố định",
             "mua sắm, xây dựng tscđ"],
         en=["purchase of fixed assets", "purchases of fixed assets", "acquisition of fixed assets", "capital expenditure"],
         exclude=["thanh lý", "disposal", "thu từ", "proceeds", "%"]),
    Item("equity_issued", "cf", "Tiền thu từ phát hành cổ phiếu, nhận vốn góp",
         ids=["proceeds_from_issuance_of_shares", "proceeds_from_issuing_shares"],
         vi=["tiền thu từ phát hành cổ phiếu, nhận vốn góp của chủ sở hữu", "tiền thu từ phát hành cổ phiếu và vốn góp",
             "tiền thu từ phát hành cổ phiếu", "thu từ phát hành cổ phiếu"],
         en=["proceeds from issuance of shares", "proceeds from issuing shares", "proceeds from share issues"],
         exclude=["trái phiếu", "công cụ nợ", "bond", "debt", "mua lại", "repurchase", "%"]),
    Item("dividends_paid", "cf", "Cổ tức đã trả", ids=["dividends_paid"],
         vi=["cổ tức, lợi nhuận đã trả cho chủ sở hữu", "cổ tức, lợi nhuận đã trả", "cổ tức đã trả"],
         en=["dividends paid"], exclude=["nhận", "received", "%"]),

    # ── Từ bảng chỉ số / thông tin cổ phiếu ──
    Item("shares_outstanding", "ratio", "Số CP lưu hành",
         ids=["outstanding_share", "shares_outstanding", "outstanding_shares", "issue_share"],
         vi=["số cổ phiếu lưu hành", "số cp lưu hành", "khối lượng cổ phiếu đang lưu hành", "số lượng cổ phiếu lưu hành"],
         en=["outstanding shares", "shares outstanding", "outstanding share"],
         exclude=["%", "tăng trưởng", "bình quân", "average"], unit="shares"),
]

# Mã chỉ tiêu của bộ dữ liệu BCTC đóng gói sẵn (vn-annual-report-miner) – so khớp chính xác theo item_id,
# không ảnh hưởng cách nhận diện theo nhãn của các nguồn khác.
_ARMINER_IDS: Dict[str, List[str]] = {
    "revenue": ["is_doanh_so_thuan", "is_doanh_thu_thuan_ve_hoat_dong_kinh_doanh"],
    "gross_profit": ["is_lai_gop"],
    "operating_profit": ["is_lai_lo_tu_hoat_dong_kinh_doanh"],
    "financial_income": ["is_thu_nhap_tai_chinh", "is_doanh_thu_hoat_dong_tai_chinh"],
    "profit_before_tax": ["is_lai_lo_rong_truoc_thue", "is_tong_loi_nhuan_ke_toan_truoc_thue"],
    "net_income": ["is_lai_lo_thuan_sau_thue"],
    "net_income_parent": ["is_loi_nhuan_cua_co_dong_cua_cong_ty_me"],
    "short_term_investments": ["bs_gia_tri_thuan_dau_tu_ngan_han"],
    "long_term_investments": ["bs_dau_tu_dai_han"],
    "associates_income": ["is_lai_lo_tu_cong_ty_lien_doanh", "is_lai_lo_tu_cong_ty_lien_doanh_tu_nam_2015"],
    "selling_expense": ["is_chi_phi_ban_hang"],
    "admin_expense": ["is_chi_phi_quan_ly_doanh_nghiep"],
    "receivables": ["bs_cac_khoan_phai_thu"],
    "cfo": ["cf_luu_chuyen_tien_thuan_tu_cac_hoat_dong_san_xuat_kinh_doanh"],
    "cfi": ["cf_luu_chuyen_tien_te_rong_tu_hoat_dong_dau_tu", "cf_luu_chuyen_tien_thuan_tu_hoat_dong_dau_tu"],
    "cff": ["cf_luu_chuyen_tien_te_tu_hoat_dong_tai_chinh"],
    "capex": ["cf_tien_mua_tai_san_co_dinh_va_cac_tai_san_dai_han_khac"],
    "charter_capital": ["bs_von_gop", "bs_co_phieu_pho_thong"],
    "retained_earnings": ["bs_lai_chua_phan_phoi"],
    "dividends_paid": ["cf_co_tuc_da_tra"],
    "equity_issued": ["cf_tien_thu_tu_phat_hanh_co_phieu_va_von_gop"],
}
for _it in CANONICAL_ITEMS:
    _it.ids = list(_it.ids) + [i for i in _ARMINER_IDS.get(_it.key, []) if i not in _it.ids]

ITEMS_BY_KEY: Dict[str, Item] = {it.key: it for it in CANONICAL_ITEMS}
PER_UNIT_KEYS = {k for k, it in ITEMS_BY_KEY.items() if it.unit != "vnd"}
STATEMENT_ITEMS: Dict[str, List[str]] = {}
for _it in CANONICAL_ITEMS:
    STATEMENT_ITEMS.setdefault(_it.statement, []).append(_it.key)


# ─────────────────────────────────────────────────────────────────────────────
# Chuyển mọi định dạng về dạng ma trận: cột "label" (vi), "label_en", "item_id" + cột kỳ
# ─────────────────────────────────────────────────────────────────────────────

def to_matrix(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[int], List[int]]:
    """Trả về (bảng ma trận, VỊ TRÍ các cột kỳ đã sắp tăng dần theo thời gian, khóa kỳ tương ứng)."""
    if df is None or df.empty:
        return pd.DataFrame(), [], []
    # Nhãn kỳ suy biến: ≥ 4 cột kỳ nhưng tất cả cùng MỘT nhãn (vd 16 cột đều là "2018") →
    # không xác định được cột nào thuộc kỳ nào → bỏ bảng này thay vì gán nhầm số liệu.
    # (Kiểm tra TRƯỚC khi loại cột trùng.)
    if not isinstance(df.columns, pd.MultiIndex):
        parsed = [parse_period_key(c) for c in map(str, df.columns)
                  if str(c) not in ("item", "item_en", "item_id") and not re.search(r"_\d+$", str(c))]
        parsed = [k for k in parsed if k is not None]
        if len(parsed) >= 4 and len(set(parsed)) == 1:
            return pd.DataFrame(), [], []
    df = flatten_columns(df)
    id_cols = [c for c in ("item", "item_en", "item_id") if c in df.columns]

    if not id_cols:
        # Dạng bảng (mỗi dòng 1 kỳ) -> chuyển vị
        tab = order_tabular(df)
        if not all(isinstance(k, (int, np.integer)) for k in tab.index):
            return pd.DataFrame(), [], []
        skip = {c for c in tab.columns if norm_label(c) in
                {"năm", "nam", "year", "kỳ", "ky", "quý", "quy", "quarter", "cp", "ticker", "symbol",
                 "yearreport", "lengthreport", "source", "fetched_at"}}
        value_cols = [c for c in tab.columns if c not in skip]
        mat = tab[value_cols].T
        mat.columns = [key_to_label(k) for k in tab.index]
        mat.insert(0, "item", [str(c) for c in value_cols])
        df = mat.reset_index(drop=True)
        id_cols = ["item"]

    # Cột kỳ: đọc nhãn -> khóa kỳ, xác định theo VỊ TRÍ cột (không theo tên) vì nguồn có thể
    # trả nhiều cột cùng tên – vd bảng chỉ số VCI theo quý nhưng nhãn chỉ ghi năm ("2025" ×4).
    # Với mỗi kỳ chỉ giữ cột ĐẦU TIÊN (nguồn VCI xếp kỳ mới nhất trước).
    keyed: Dict[int, int] = {}
    for pos, c in enumerate(df.columns):
        if c in id_cols or _norm(c) in META_COLS | {"rownumber"}:
            continue
        if re.search(r"_\d+$", str(c)):          # cột trùng do nguồn tự đánh hậu tố
            continue
        k = parse_period_key(c)
        if k is not None and k not in keyed:
            keyed[k] = pos
    keys = sorted(keyed)
    return df, [keyed[k] for k in keys], keys


# ─────────────────────────────────────────────────────────────────────────────
# Khớp chỉ tiêu
# ─────────────────────────────────────────────────────────────────────────────

def _excluded(label: str, excl: List[str]) -> bool:
    plain = strip_accents(label)
    return any(e in label or strip_accents(e) in plain for e in excl)


def _find_row(mat: pd.DataFrame, item: Item) -> Optional[int]:
    ids = mat["item_id"].astype(str).str.lower().tolist() if "item_id" in mat.columns else []
    for want in item.ids:
        if want in ids:
            return ids.index(want)

    for col, patterns in (("item", item.vi), ("item_en", item.en)):
        if col not in mat.columns or not patterns:
            continue
        labels = [norm_label(x) for x in mat[col].tolist()]
        plains = [strip_accents(x) for x in labels]
        for pat in patterns:
            p = _pair_norm(pat.lower())
            pp = strip_accents(p)
            for mode in ("start", "contain"):
                for i, (lab, plain) in enumerate(zip(labels, plains)):
                    if not lab or _excluded(lab, item.exclude):
                        continue
                    hit = (lab.startswith(p) or plain.startswith(pp)) if mode == "start" else (p in lab or pp in plain)
                    if hit:
                        return i
    return None


def _unit_factor_from_labels(mat: pd.DataFrame) -> Optional[float]:
    text = " ".join(str(x) for x in mat.get("item", pd.Series(dtype=str)).tolist()).lower()
    if "tỷ đồng" in text or "(tỷ" in text:
        return 1e9
    if "triệu đồng" in text or "(triệu" in text:
        return 1e6
    return None


def canonicalize(df: pd.DataFrame, statement: Optional[str] = None,
                 unit_factor: Optional[float] = None) -> pd.DataFrame:
    """
    Chuẩn hóa một bảng BCTC thô về dạng rộng: index = khóa kỳ, cột = chỉ tiêu chuẩn.

    statement : "is" | "bs" | "cf" | "ratio" | None (None = thử mọi chỉ tiêu)
    unit_factor: hệ số quy đổi về VND nếu đã biết (vd 1e9 khi nguồn ghi "tỷ đồng").
    """
    mat, period_pos, keys = to_matrix(df)
    if mat.empty or not period_pos:
        return pd.DataFrame()
    wanted = CANONICAL_ITEMS if statement is None else [i for i in CANONICAL_ITEMS if i.statement == statement]
    out = {}
    for item in wanted:
        idx = _find_row(mat, item)
        if idx is None:
            continue
        vals = pd.to_numeric(mat.iloc[idx, period_pos], errors="coerce").to_numpy(dtype=float)
        out[item.key] = vals
    if not out:
        return pd.DataFrame()
    wide = pd.DataFrame(out, index=pd.Index(keys, name="period_key"))

    factor = unit_factor or _unit_factor_from_labels(mat)
    if factor:
        money = [c for c in wide.columns if c not in PER_UNIT_KEYS]
        wide[money] = wide[money] * factor
    return wide.dropna(how="all")


def infer_scale(wide: pd.DataFrame) -> float:
    """
    Đoán hệ số đơn vị khi nguồn không ghi rõ: tổng tài sản (hoặc doanh thu) của DN niêm yết
    luôn ≥ 10 tỷ VND. Trả về hệ số nhỏ nhất trong {1, 1e3, 1e6, 1e9} đưa trung vị về ≥ 1e10.
    """
    for col in ("total_assets", "equity", "revenue", "total_operating_income"):
        if col in wide.columns:
            med = wide[col].abs().median()
            if pd.notna(med) and med > 0:
                for f in (1.0, 1e3, 1e6, 1e9):
                    if med * f >= 1e10:
                        return f
    return 1.0


def apply_scale(wide: pd.DataFrame, factor: float) -> pd.DataFrame:
    if factor == 1.0 or wide.empty:
        return wide
    wide = wide.copy()
    money = [c for c in wide.columns if c not in PER_UNIT_KEYS]
    wide[money] = wide[money] * factor
    return wide


def wide_to_long(wide: pd.DataFrame, source_map: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    if wide.empty:
        return pd.DataFrame(columns=["period_key", "item", "value", "source"])
    # Đặt tên chỉ mục tường minh: pandas 2.x làm mất tên chỉ mục sau combine_first/merge (pandas 3 thì giữ) →
    # reset_index() ra cột "index" và melt(id_vars="period_key") lỗi KeyError → toàn bộ BCTC không lưu/đọc được.
    wide = wide.rename_axis("period_key")
    long = wide.reset_index().melt(id_vars="period_key", var_name="item", value_name="value").dropna(subset=["value"])
    if source_map is not None and not source_map.empty:
        src = source_map.rename_axis("period_key").reset_index().melt(id_vars="period_key", var_name="item",
                                                                      value_name="source")
        long = long.merge(src, on=["period_key", "item"], how="left")
    else:
        long["source"] = None
    return long


def long_to_wide(long: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if long is None or long.empty:
        return pd.DataFrame(), pd.DataFrame()
    wide = long.pivot_table(index="period_key", columns="item", values="value", aggfunc="first").sort_index()
    src = long.pivot_table(index="period_key", columns="item", values="source", aggfunc="first").sort_index()
    wide.index = wide.index.astype(int)
    src.index = src.index.astype(int)
    return wide, src


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: data/data_normalizer.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Data normalizer – converts raw provider data into the canonical internal schema.

Internal price schema:
  symbol, timestamp, open, high, low, close, volume, value,
  source, interval, adjusted, fetched_at

Key invariants:
  - Prices in VND.
  - Timestamps in Asia/Ho_Chi_Minh, tz-naive (local time stored as-is).
  - Volume in shares (integer).
  - No mixing of adjusted and unadjusted series without explicit flag.
  - No future data in historical series.
"""


import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import pytz

logger = logging.getLogger(__name__)
HCM_TZ = pytz.timezone("Asia/Ho_Chi_Minh")
PRICE_SCHEMA = ["symbol", "timestamp", "open", "high", "low", "close",
                "volume", "value", "source", "interval", "adjusted", "fetched_at"]


class DataNormalizer:
    """Normalize and validate raw data from any provider."""

    # ─────────────────── Price Data ─────────────────────────────────────────

    @staticmethod
    def normalize_price(df: pd.DataFrame, symbol: str = "", source: str = "",
                        interval: str = "1D", adjusted: bool = False) -> pd.DataFrame:
        """
        Return a clean price DataFrame conforming to the internal schema.

        Parameters
        ----------
        df       : Raw DataFrame from a provider.
        symbol   : Stock ticker override (if not already in df).
        source   : Provider name override.
        interval : Time resolution string.
        adjusted : Whether prices are dividend-adjusted.
        """
        if df is None or df.empty:
            return pd.DataFrame(columns=PRICE_SCHEMA)

        df = df.copy()

        # ── Map common column aliases ──
        col_aliases = {
            "date": "timestamp", "Date": "timestamp", "time": "timestamp",
            "Time": "timestamp", "Datetime": "timestamp", "datetime": "timestamp",
            "Open": "open", "High": "high", "Low": "low", "Close": "close",
            "Volume": "volume", "Value": "value",
        }
        df.rename(columns={k: v for k, v in col_aliases.items() if k in df.columns}, inplace=True)
        df = df.loc[:, ~df.columns.duplicated()]

        # ── Ensure required columns exist ──
        required_cols = ["open", "high", "low", "close", "volume"]
        missing = [c for c in required_cols if c not in df.columns]
        if "close" in missing:
            logger.error("Required column 'close' missing from price DataFrame.")
            return pd.DataFrame(columns=PRICE_SCHEMA)

        # ── Timestamp ──
        if "timestamp" not in df.columns:
            logger.error("No timestamp column found in price DataFrame.")
            return pd.DataFrame(columns=PRICE_SCHEMA)

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        # Convert to HCM local time (tz-naive storage)
        if df["timestamp"].dt.tz is not None:
            df["timestamp"] = df["timestamp"].dt.tz_convert(HCM_TZ).dt.tz_localize(None)
        # else: assume already local

        # ── Numeric coercion ──
        for col in ["open", "high", "low", "close", "volume", "value"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Fill missing value
        if "value" not in df.columns:
            df["value"] = None
        for col in ["open", "high", "low"]:
            if col not in df.columns:
                df[col] = df["close"]

        # ── Metadata columns ──
        if symbol:
            df["symbol"] = symbol.upper()
        elif "symbol" not in df.columns:
            df["symbol"] = ""
        df["symbol"] = df["symbol"].astype(str).str.upper()

        if source:
            df["source"] = source
        elif "source" not in df.columns:
            df["source"] = "unknown"

        df["interval"] = interval
        df["adjusted"] = adjusted

        if "fetched_at" not in df.columns:
            df["fetched_at"] = datetime.now().isoformat()

        # ── Anti-look-ahead guard ──
        now_local = datetime.now()
        future_mask = df["timestamp"] > pd.Timestamp(now_local)
        if future_mask.any():
            logger.warning("Dropping %d future rows for %s", future_mask.sum(), symbol)
            df = df[~future_mask]

        # ── Data quality checks ──
        before = len(df)
        df = df.dropna(subset=["close", "timestamp"])
        df = df[df["close"] > 0]
        df = df.drop_duplicates(subset=["timestamp", "symbol"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        after = len(df)
        if before != after:
            logger.debug("Dropped %d invalid rows for %s", before - after, symbol)

        # Sanity: OHLC consistency
        if all(c in df.columns for c in ["open", "high", "low", "close"]):
            bad = (df["high"] < df["low"]) | (df["close"] > df["high"] * 1.2) | \
                  (df["close"] < df["low"] * 0.8)
            if bad.any():
                logger.warning("%d OHLC inconsistencies detected for %s", bad.sum(), symbol)

        return df[PRICE_SCHEMA]

    # ─────────────────── Financial Data ─────────────────────────────────────

    @staticmethod
    def normalize_financial(df: pd.DataFrame, symbol: str, report_type: str = "consolidated",
                            source: str = "vnstock") -> pd.DataFrame:
        """Normalize financial statement DataFrame."""
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        df["symbol"] = symbol.upper()
        df["report_type"] = report_type
        df["source"] = source
        df["fetched_at"] = datetime.now().isoformat()
        return df

    @staticmethod
    def format_currency(value: Optional[float], unit: str = "tỷ") -> str:
        """Format a VND value with unit label."""
        if value is None or pd.isna(value):
            return "N/A"
        if unit == "tỷ":
            return f"{value / 1e9:,.1f} tỷ"
        if unit == "triệu":
            return f"{value / 1e6:,.1f} triệu"
        return f"{value:,.0f}"

    @staticmethod
    def pct_change(new: float, old: float) -> Optional[float]:
        """Safe percentage change calculation."""
        if old is None or old == 0:
            return None
        return (new - old) / abs(old) * 100


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: data/quarter_basis.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Chuẩn hóa số liệu BCTC QUÝ về "số của riêng từng quý" trước khi cộng dồn (TTM / số năm).

Vấn đề: theo mẫu VAS, BCTC quý có thể trình bày
  • KQKD: cột "Quý này" (số độc lập từng quý) và/hoặc "Lũy kế từ đầu năm";
  • LCTT (mẫu B03a): thường CHỈ có "Lũy kế từ đầu năm đến cuối quý này";
  • BCTC bán niên: số 6 tháng (= lũy kế đến Q2).
Nguồn trực tuyến không ghi rõ dạng số → nếu cộng thẳng 4 quý của số lũy kế, doanh thu/dòng tiền năm bị
phóng đại (~2,5 lần); nếu lấy quý cuối của số độc lập, số năm chỉ còn ~1/4.

Cách làm (theo từng nguồn × từng báo cáo):
  1. Bằng chứng đối chiếu: năm có cả số NĂM và đủ 4 quý → Σ4 quý ≈ năm ⇒ độc lập; Q4 ≈ năm ⇒ lũy kế.
  2. Bằng chứng hình dạng: với các chỉ tiêu luôn dương và đều theo thời gian (doanh thu, giá vốn, chi phí
     bán hàng/QLDN, lãi vay, khấu hao, capex) – lũy kế ⇒ tăng dần, Q2/Q1 ≈ 2, Q3/Q1 ≈ 3; độc lập ⇒ Q2/Q1 ≈ 1.
  3. Kết luận chỉ khi bằng chứng áp đảo; không đủ ⇒ "unknown".
  4. Lũy kế ⇒ chuyển về độc lập: Q1 = L1, Qn = Ln − L(n−1) (thiếu kỳ liền trước ⇒ bỏ trống, KHÔNG đoán).
  5. "unknown" ⇒ giữ nguyên để hiển thị nhưng KHÔNG được dùng để tạo số năm (data_repository._align_period).
Chỉ tiêu theo cổ phiếu (EPS) không được trừ/cộng (nguồn có thể trả EPS 4 quý gần nhất) ⇒ bỏ trống khi suy diễn.
"""


from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd



DISCRETE, CUMULATIVE, UNKNOWN = "discrete", "cumulative", "unknown"

FLOW_KEYS: Dict[str, List[str]] = {
    st: [k for k, it in ITEMS_BY_KEY.items() if it.statement == st] for st in ("is", "cf")
}
PER_SHARE_FLOW = {k for st in FLOW_KEYS.values() for k in st if ITEMS_BY_KEY[k].unit != "vnd"}
# Chỉ tiêu đều đặn, luôn cùng dấu → dùng để nhận dạng hình dạng lũy kế
SHAPE_KEYS = {"is": ["revenue", "cogs", "selling_expense", "admin_expense", "interest_expense", "total_operating_income"],
              "cf": ["depreciation", "capex"]}
TOL = 0.02          # sai số đối chiếu với số năm (2%)


def flow_columns(wide: pd.DataFrame, statement: str) -> List[str]:
    keys = FLOW_KEYS["is"] + FLOW_KEYS["cf"] if statement == "all" else FLOW_KEYS.get(statement, [])
    return [c for c in keys if c in wide.columns]


def _quarter_rows(wide: pd.DataFrame, year: int) -> Dict[int, pd.Series]:
    return {q: wide.loc[year * 10 + q] for q in range(1, 5) if year * 10 + q in wide.index}


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= TOL * max(abs(a), abs(b), 1.0)


def _with_reference(wide: pd.DataFrame, reference: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Bổ sung dòng NĂM từ bảng tham chiếu (vd BCTC năm đã tải, đã gộp nguồn) để đối chiếu Σ4 quý / Q4 = năm.
    Chỉ thêm năm chưa có, chỉ các cột trùng tên; KHÔNG làm thay đổi số liệu trả về (chỉ dùng để nhận dạng)."""
    if reference is None or reference.empty:
        return wide
    rk = np.asarray(reference.index, dtype=int)
    ann = reference[(rk % 10 == 0)]
    ann = ann[[c for c in ann.columns if c in wide.columns]]
    ann = ann[~ann.index.isin(wide.index)]
    return pd.concat([wide, ann]).sort_index() if not ann.empty else wide


def detect_basis(wide: pd.DataFrame, statement: str, reference: Optional[pd.DataFrame] = None) -> Tuple[str, str]:
    """(dạng số, diễn giải). statement: is | cf | all (khi nguồn trả chung một bảng, vd PDF).
    reference: bảng có số NĂM (tùy chọn) dùng làm bằng chứng đối chiếu khi bảng quý không kèm số năm."""
    wide = _with_reference(wide, reference) if wide is not None and not wide.empty else wide
    cols = flow_columns(wide, statement)
    if wide is None or wide.empty or not cols:
        return UNKNOWN, "không có chỉ tiêu dòng"
    keys = np.asarray(wide.index, dtype=int)
    years = sorted(set(keys[keys % 10 > 0] // 10))
    if not years:
        return UNKNOWN, "không có số quý"

    # 1) Đối chiếu với số năm (bằng chứng mạnh)
    vd = vc = 0
    for y in years:
        if y * 10 not in wide.index:
            continue
        qs = _quarter_rows(wide, y)
        if len(qs) < 4:
            continue
        ann = wide.loc[y * 10]
        for c in cols:
            if c in PER_SHARE_FLOW:
                continue
            vals = [qs[q].get(c) for q in range(1, 5)]
            a = ann.get(c)
            if a is None or pd.isna(a) or any(v is None or pd.isna(v) for v in vals) or abs(a) < 1:
                continue
            s_ok, q4_ok = _close(sum(vals), a), _close(vals[3], a)
            if s_ok and not q4_ok:
                vd += 1
            elif q4_ok and not s_ok:
                vc += 1
    if vd >= 2 and vd >= 3 * vc:
        return DISCRETE, f"đối chiếu số năm: {vd} chỉ tiêu Σ4 quý = năm"
    if vc >= 2 and vc >= 3 * vd:
        return CUMULATIVE, f"đối chiếu số năm: {vc} chỉ tiêu quý 4 = năm"

    # 2) Hình dạng chuỗi trong năm
    sd = sc = 0
    shape_cols = [c for c in (SHAPE_KEYS["is"] + SHAPE_KEYS["cf"] if statement == "all" else SHAPE_KEYS.get(statement, []))
                  if c in wide.columns]
    for y in years:
        qs = _quarter_rows(wide, y)
        if not {1, 2, 3}.issubset(qs):
            continue
        for c in shape_cols:
            v = [qs[q].get(c) for q in sorted(qs)]
            if any(x is None or pd.isna(x) for x in v):
                continue
            a = np.abs(np.asarray(v, dtype=float))
            if a[0] <= 0 or np.sign(v[0]) != np.sign(v[1]) or np.sign(v[0]) != np.sign(v[2]):
                continue
            r2, r3 = a[1] / a[0], a[2] / a[0]
            if 1.6 <= r2 <= 2.6 and 2.3 <= r3 <= 3.9 and np.all(np.diff(a) > 0):
                sc += 1
            elif 0.5 <= r2 <= 1.5 and 0.4 <= r3 <= 1.8:
                sd += 1
    if sc >= 2 and sc >= 3 * sd:
        return CUMULATIVE, f"hình dạng: {sc} chuỗi tăng dần ≈ 1:2:3"
    if sd >= 2 and sd >= 3 * sc:
        return DISCRETE, f"hình dạng: {sd} chuỗi đều theo quý"
    return UNKNOWN, f"chưa đủ bằng chứng (đối chiếu {vd}/{vc}, hình dạng {sd}/{sc})"


def decumulate(wide: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """Số lũy kế từ đầu năm → số từng quý. Thiếu kỳ liền trước ⇒ NaN. Dòng NĂM giữ nguyên."""
    out = wide.copy()
    keys = np.asarray(wide.index, dtype=int)
    for c in cols:
        if c in out.columns:                       # pandas 3: không gán NaN/số thực vào cột kiểu số nguyên
            out[c] = pd.to_numeric(out[c], errors="coerce").astype("float64")
        if c in PER_SHARE_FLOW:
            out.loc[keys % 10 > 0, c] = np.nan
            continue
        for k in keys[keys % 10 > 1]:
            prev = k - 1
            cur = wide.at[k, c]
            if prev in wide.index and pd.notna(wide.at[prev, c]) and pd.notna(cur):
                out.at[k, c] = float(cur) - float(wide.at[prev, c])
            else:
                out.at[k, c] = np.nan
    return out


def normalize_quarters(wide: pd.DataFrame, statement: str, default: Optional[str] = None,
                       reference: Optional[pd.DataFrame] = None) -> Tuple[pd.DataFrame, str, str]:
    """Đưa số quý về dạng độc lập. Trả (bảng, dạng số SAU chuẩn hóa, diễn giải).

    default: dạng số đã biết của nguồn khi không tự nhận dạng được (vd LCTT trong PDF theo mẫu B03a = lũy kế).
    Không xác định được ⇒ giữ nguyên số liệu, chỉ gắn nhãn "unknown" để bước tạo số năm KHÔNG cộng các quý.
    """
    if wide is None or wide.empty:
        return wide, UNKNOWN, "rỗng"
    if statement not in ("is", "cf", "all"):
        return wide, DISCRETE, "chỉ tiêu số dư"
    keys = np.asarray(wide.index, dtype=int)
    if not (keys % 10 > 0).any():
        return wide, DISCRETE, "chỉ có số năm"
    basis, why = detect_basis(wide, statement, reference)
    if basis == UNKNOWN and default in (DISCRETE, CUMULATIVE):
        basis, why = default, f"theo mẫu biểu của nguồn ({why})"
    if basis == CUMULATIVE:
        return decumulate(wide, flow_columns(wide, statement)), DISCRETE, f"lũy kế → đã quy về từng quý; {why}"
    return wide, basis, why


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: data/ticker_directory.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Comprehensive Stock Directory and Industry Baskets for Vietnam Equities.
Provides fast lookups, sector/index basket filters, and formatted labels
for all ~1,750+ listed stocks across HOSE, HNX, and UPCoM.
"""


import json
from pathlib import Path
from typing import Dict, List, Optional

# Pre-defined Index & Sector Baskets (as in modern quant & report miners)
BASKETS: Dict[str, List[str]] = {
    "Tất cả (~1,750+ mã)": [],  # Filled dynamically from all listings
    "⭐ VN30 (Blue-chips HSX)": [
        "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
        "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
        "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE"
    ],
    "⭐ HNX30 (Trụ cột HNX)": [
        "BVS", "CAP", "CEO", "DHT", "DTD", "HUT", "IDC", "IDV", "L14", "LAS",
        "MBS", "NBC", "NET", "NTP", "PBL", "PGS", "PLC", "PSD", "PVC", "PVS",
        "SHS", "SLS", "SZB", "THT", "TNG", "TVD", "VC3", "VCS", "VGS"
    ],
    "🏦 Ngân hàng": [
        "VCB", "BID", "CTG", "TCB", "MBB", "ACB", "VPB", "STB", "HDB", "SHB",
        "TPB", "VIB", "LPB", "MSB", "OCB", "EIB", "SSB", "NAB", "BVB", "BAB",
        "NVB", "PGB", "ABB", "KLB", "VAB", "SGB"
    ],
    "📈 Chứng khoán": [
        "SSI", "VND", "VCI", "HCM", "SHS", "MBS", "FTS", "BSI", "CTS", "VIX",
        "AGR", "ORS", "TVS", "VDS", "TCI", "SBS", "APS", "PSI", "IVS", "EVS",
        "APG", "VIG"
    ],
    "🏢 Bất động sản": [
        "VHM", "VIC", "VRE", "NVL", "KDH", "DIG", "DXG", "PDR", "KBC", "NLG",
        "CEO", "HDC", "DXS", "TCH", "IJC", "CRE", "SCR", "D2D", "SZC", "IDC",
        "NHA", "HQC", "LDG", "QCG", "KHG", "BCM"
    ],
    "🏗️ Thép & VLXD": [
        "HPG", "HSG", "NKG", "VGS", "TLH", "POM", "TVN", "SMC", "BCC", "HT1",
        "DHA", "KSB", "NNC", "VCS"
    ],
    "💻 Công nghệ & Viễn thông": [
        "FPT", "CMG", "FOX", "ELC", "CTR", "VGI", "SAM", "ICT", "ITD", "ONE", "SGT"
    ],
    "🛒 Bán lẻ & Tiêu dùng": [
        "MWG", "FRT", "DGW", "PNJ", "VNM", "MSN", "SAB", "KDC", "HAG", "DBC",
        "BAF", "MCH", "QNS", "VHC", "ANV", "IDI", "FMC"
    ],
    "⚡ Dầu khí & Năng lượng": [
        "GAS", "PLX", "PVD", "PVS", "BSR", "PVT", "POW", "REE", "GEG", "HDG",
        "PC1", "NT2", "PGV", "TV2", "VSH", "SBA"
    ],
    "🧪 Hóa chất & Phân bón": [
        "DGC", "DCM", "DPM", "BFC", "CSV", "LAS", "DDV", "PHR", "DPR", "DRI", "GVR"
    ],
    "🚢 Cảng biển & Logistics": [
        "GMD", "HAH", "VSC", "PVT", "VOS", "TCL", "DVP", "TMS", "SGP", "MVN", "PHP"
    ],
    "🧵 Dệt may & Thủy sản": [
        "TNG", "MSH", "TCM", "STK", "VGT", "GIL", "VHC", "ANV", "IDI", "FMC", "CMX"
    ],
}

_ALL_STOCKS_CACHE: Optional[List[Dict[str, str]]] = None
_SYMBOL_MAP_CACHE: Optional[Dict[str, Dict[str, str]]] = None


def load_all_stocks() -> List[Dict[str, str]]:
    """Loads all listed stocks from local persistent cache or default."""
    global _ALL_STOCKS_CACHE, _SYMBOL_MAP_CACHE
    if _ALL_STOCKS_CACHE is not None:
        return _ALL_STOCKS_CACHE

    json_file = Path(__file__).resolve().parent.parent / "data" / "listed_stocks.json"
    stocks: List[Dict[str, str]] = []
    if json_file.exists():
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                stocks = json.load(f)
        except Exception:
            stocks = []

    if not stocks:
        # Fallback to popular tickers if file cannot be read
        stocks = [
            {"symbol": "FPT", "exchange": "HSX", "organ_short_name": "Tập đoàn FPT", "organ_name": "Công ty Cổ phần FPT"},
            {"symbol": "HPG", "exchange": "HSX", "organ_short_name": "Tập đoàn Hòa Phát", "organ_name": "Công ty Cổ phần Tập đoàn Hòa Phát"},
            {"symbol": "VCB", "exchange": "HSX", "organ_short_name": "Vietcombank", "organ_name": "Ngân hàng TMCP Ngoại thương Việt Nam"},
            {"symbol": "SSI", "exchange": "HSX", "organ_short_name": "Chứng khoán SSI", "organ_name": "Công ty Cổ phần Chứng khoán SSI"},
            {"symbol": "MWG", "exchange": "HSX", "organ_short_name": "Thế Giới Di Động", "organ_name": "Công ty Cổ phần Đầu tư Thế Giới Di Động"},
            {"symbol": "TCB", "exchange": "HSX", "organ_short_name": "Techcombank", "organ_name": "Ngân hàng TMCP Kỹ Thương Việt Nam"},
            {"symbol": "VHM", "exchange": "HSX", "organ_short_name": "Vinhomes", "organ_name": "Công ty Cổ phần Vinhomes"},
            {"symbol": "VNM", "exchange": "HSX", "organ_short_name": "Vinamilk", "organ_name": "Công ty Cổ phần Sữa Việt Nam"},
            {"symbol": "MBB", "exchange": "HSX", "organ_short_name": "MBBank", "organ_name": "Ngân hàng TMCP Quân Đội"},
            {"symbol": "STB", "exchange": "HSX", "organ_short_name": "Sacombank", "organ_name": "Ngân hàng TMCP Sài Gòn Thương Tín"},
        ]

    _ALL_STOCKS_CACHE = stocks
    _SYMBOL_MAP_CACHE = {s["symbol"].upper(): s for s in stocks}
    return _ALL_STOCKS_CACHE


def get_symbol_map() -> Dict[str, Dict[str, str]]:
    """Returns map of symbol -> stock metadata."""
    if _SYMBOL_MAP_CACHE is None:
        load_all_stocks()
    return _SYMBOL_MAP_CACHE or {}


def get_basket_names() -> List[str]:
    """Returns list of basket / sector category names."""
    return list(BASKETS.keys())


def get_tickers_for_basket(basket_name: str) -> List[str]:
    """Returns list of symbols matching the selected basket/category."""
    stocks = load_all_stocks()
    if basket_name == "Tất cả (~1,750+ mã)":
        return [s["symbol"] for s in stocks]
    
    basket_symbols = BASKETS.get(basket_name, [])
    # Return matched symbols in order
    return basket_symbols


def get_ticker_label(symbol: str) -> str:
    """Formats symbol as display string: 'SYMBOL - Tên công ty (Sàn)'."""
    symbol_upper = symbol.strip().upper()
    s_map = get_symbol_map()
    meta = s_map.get(symbol_upper)
    if meta:
        raw_name = meta.get("organ_short_name") or meta.get("organ_name") or ""
        name = str(raw_name).strip() if raw_name is not None else ""
        if name.lower() == "nan":
            name = ""
        raw_exch = meta.get("exchange") or ""
        exch = str(raw_exch).strip() if raw_exch is not None else ""
        if exch.lower() == "nan":
            exch = ""
        # Shorten very long names if needed
        if len(name) > 32:
            name = name[:30] + "..."
        if name and exch:
            return f"{symbol_upper} - {name} ({exch})"
        elif name:
            return f"{symbol_upper} - {name}"
        return f"{symbol_upper} ({exch})" if exch else symbol_upper
    return symbol_upper


def extract_symbol_from_label(label: str) -> str:
    """Extracts raw ticker symbol from formatted label or text input."""
    if not label:
        return "FPT"
    clean = label.strip()
    if " - " in clean:
        return clean.split(" - ")[0].strip().upper()
    if " (" in clean:
        return clean.split(" (")[0].strip().upper()
    return clean.upper()


def get_formatted_options(basket_name: str = "Tất cả (~1,750+ mã)") -> List[str]:
    """Returns formatted display options for a given basket."""
    symbols = get_tickers_for_basket(basket_name)
    return [get_ticker_label(s) for s in symbols]


def find_option_for_symbol(symbol: str, options: List[str]) -> Optional[str]:
    """Finds matching option string in options list for a given symbol."""
    sym = symbol.strip().upper()
    for opt in options:
        if opt == sym or opt.startswith(f"{sym} ") or opt.startswith(f"{sym}-"):
            return opt
    return None


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: data/data_repository.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
DataRepository – lớp truy cập dữ liệu duy nhất của hệ thống (Single Source of Truth).

GIÁ (get_price_history) – ghép nhiều nguồn:
  ┌──────────── phần cũ ────────────┐┌──── DNSE_RECENT_DAYS ngày gần nhất ────┐
  vnstock VCI → KBS → MSN → Vietstock      DNSE (nếu lỗi: dùng nguồn lịch sử)
  - Mọi giá cổ phiếu quy về VND (nguồn báo theo nghìn đồng được nhân 1.000).
  - Ở điểm nối, so sánh các phiên trùng nhau: nếu lệch (do một bên đã điều chỉnh
    cổ tức/chia tách) thì nhân phần cũ với hệ số để chuỗi liền mạch, ghi lại hệ số.
  - Mỗi dòng có cột `source`; attrs["provenance"] tóm tắt nguồn theo đoạn thời gian.

BCTC (get_financials) – chuỗi dự phòng nhiều nguồn:
  vnstock VCI → vnstock KBS → Vietstock → PDF BCTC đã tải (trích theo mã số VAS)
  - Mỗi nguồn được chuẩn hóa về cùng bộ chỉ tiêu (core/du_lieu.py).
  - Nguồn trước được ưu tiên; ô nào nguồn trước THIẾU (kỳ hoặc chỉ tiêu) thì lấy nguồn sau.
  - Lưu nguồn của từng ô (period × item) để hiển thị và kiểm tra.
"""


import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.cau_hinh import settings





from core.nguon_du_lieu import DNSEClient, is_index
from core.nguon_du_lieu import VietstockClient
from core.nguon_du_lieu import VnstockClient

logger = logging.getLogger(__name__)
db = Database()
normalizer = DataNormalizer()

_STATEMENT_CODE = {"income_statement": "is", "balance_sheet": "bs", "cash_flow": "cf", "ratio": "ratio"}


def to_vnd(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Cổ phiếu niêm yết VN luôn có giá ≥ 1.000đ; nguồn nào báo < 1.000 là đơn vị nghìn đồng."""
    if df.empty or is_index(symbol):
        return df
    med = pd.to_numeric(df["close"], errors="coerce").median()
    if pd.notna(med) and 0 < med < 1000:
        df = df.copy()
        for c in ("open", "high", "low", "close"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce") * 1000.0
    return df


def stitch_prices(recent: pd.DataFrame, older: pd.DataFrame, tolerance: float = 0.005) -> Tuple[pd.DataFrame, Optional[float]]:
    """
    Nối chuỗi cũ với chuỗi gần nhất. Nếu các phiên trùng nhau lệch giá > tolerance
    (thường do một nguồn đã điều chỉnh cổ tức / chia tách còn nguồn kia chưa),
    nhân toàn bộ chuỗi cũ với hệ số k = trung vị(giá mới / giá cũ) trên các phiên trùng.
    Trả về (chuỗi đã nối, hệ số k hoặc None nếu không cần điều chỉnh).
    """
    if older.empty:
        return recent.copy(), None
    if recent.empty:
        return older.copy(), None
    o = older.set_index(pd.to_datetime(older["timestamp"]).dt.normalize())
    r = recent.set_index(pd.to_datetime(recent["timestamp"]).dt.normalize())
    common = o.index.intersection(r.index)
    k = None
    if len(common) >= 1:
        ratio = (r.loc[common, "close"].astype(float) / o.loc[common, "close"].astype(float)).replace([np.inf, -np.inf], np.nan).dropna()
        if not ratio.empty:
            med = float(ratio.median())
            if abs(med - 1.0) > tolerance:
                k = med
    older_part = older[pd.to_datetime(older["timestamp"]).dt.normalize() < r.index.min()].copy()
    if k is not None:
        for c in ("open", "high", "low", "close"):
            if c in older_part.columns:
                older_part[c] = older_part[c].astype(float) * k
        older_part["adjusted"] = True
    out = pd.concat([older_part, recent], ignore_index=True)
    out = out.drop_duplicates(subset=["timestamp"], keep="last").sort_values("timestamp").reset_index(drop=True)
    return out, k


def _in_session(now: Optional[datetime] = None) -> bool:
    """Giờ giao dịch HOSE/HNX: thứ 2–6, 9:00–15:00 (cộng 15 phút cho ATC / đóng cửa)."""
    now = now or datetime.now()
    return now.weekday() < 5 and (9, 0) <= (now.hour, now.minute) <= (15, 15)


_BAND = {"HOSE": 0.07, "HSX": 0.07, "HNX": 0.10, "UPCOM": 0.15}


def _exchange_band(symbol: str) -> float:
    try:
        from core.du_lieu import get_symbol_map
        ex = str((get_symbol_map().get(symbol.upper()) or {}).get("exchange") or "").upper()
        return _BAND.get(ex, 0.15)
    except Exception:
        return 0.15


def fix_unadjusted_gaps(df: pd.DataFrame, symbol: str, band: Optional[float] = None) -> pd.DataFrame:
    """
    Phát hiện & điều chỉnh các bước nhảy giá do sự kiện quyền (chia tách, cổ phiếu thưởng, cổ tức bằng cổ phiếu, phát hành
    quyền mua) mà nguồn dữ liệu CHƯA điều chỉnh. Giao dịch thật không thể mở cửa lệch quá biên độ (HOSE ±7%, HNX ±10%,
    UPCoM ±15%) so với giá đóng cửa phiên trước – trừ ngày giao dịch không hưởng quyền, khi giá tham chiếu đã được điều
    chỉnh. Gặp bước nhảy như vậy → nhân toàn bộ giá TRƯỚC ngày đó với hệ số k = giá mở cửa / đóng cửa phiên trước
    (khối lượng chia cho k) để chuỗi giá liền mạch. Chuỗi đã điều chỉnh sẵn thì không có bước nhảy → không thay đổi.
    """
    if df is None or df.empty or is_index(symbol) or not {"open", "close"} <= set(df.columns) or len(df) < 3:
        return df
    band = band if band is not None else _exchange_band(symbol)
    d = df.sort_values("timestamp").reset_index(drop=True).copy()
    # Ép kiểu số thực trước khi nhân/chia hệ số điều chỉnh: nguồn có thể trả khối lượng/giá kiểu SỐ NGUYÊN (int64) –
    # pandas 3 KHÔNG cho gán số thập phân vào cột số nguyên (lỗi "Invalid value … for dtype int64") làm hỏng cả chuỗi
    # giá (beta, kỹ thuật, động lượng, điểm cơ hội).
    for col in ("open", "high", "low", "close", "volume"):
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").astype("float64")
    ts = pd.to_datetime(d["timestamp"])
    o, c = pd.to_numeric(d["open"], errors="coerce"), pd.to_numeric(d["close"], errors="coerce")
    gap_open = o / c.shift() - 1
    gap_close = c / c.shift() - 1
    days = ts.diff().dt.days
    flag = (gap_open.abs() > band + 0.02) & (gap_close.abs() > band + 0.02) & (days <= 15)
    events = []
    for i in d.index[flag.fillna(False)][::-1]:                   # từ gần đến xa để hệ số cộng dồn đúng
        k = float(o.iloc[i] / c.iloc[i - 1])
        if not (0.2 < k < 5):
            continue
        for col in ("open", "high", "low", "close"):
            if col in d.columns:
                d.loc[: i - 1, col] = pd.to_numeric(d.loc[: i - 1, col], errors="coerce") * k
        if "volume" in d.columns:
            d.loc[: i - 1, "volume"] = pd.to_numeric(d.loc[: i - 1, "volume"], errors="coerce") / k
        o, c = pd.to_numeric(d["open"], errors="coerce"), pd.to_numeric(d["close"], errors="coerce")
        events.append({"date": str(ts.iloc[i].date()), "factor": round(k, 4)})
    d.attrs = dict(getattr(df, "attrs", {}))
    if events:
        d.attrs["corporate_action_adjustments"] = events[::-1]
        logger.info("%s: điều chỉnh %d bước nhảy giá do sự kiện quyền chưa được nguồn điều chỉnh: %s", symbol, len(events), events)
    return d


_CHECK_ITEMS = ("revenue", "net_income", "net_income_parent", "total_assets")


def source_conflict(primary: pd.DataFrame, other: pd.DataFrame, tol: float = 0.05, min_overlap: int = 2) -> Optional[str]:
    """Kiểm tra chéo nguồn phụ với nguồn đã gộp trước đó trên các kỳ TRÙNG NHAU (doanh thu, LNST, LNST mẹ, tổng TS).
    Lệch > tol ở quá nửa số ô so sánh được → nguồn phụ nhiều khả năng gắn SAI KỲ hoặc khác đơn vị/cơ sở (vd KBS trả số
    quý FPT bị xáo kỳ: "Q3/2025" thực ra là Q2/2026) → trả lý do để bỏ nguồn đó. None = khớp / không đủ kỳ trùng."""
    if primary is None or primary.empty or other is None or other.empty:
        return None
    idx = primary.index.intersection(other.index)
    cols = [c for c in _CHECK_ITEMS if c in primary.columns and c in other.columns]
    n = bad = 0
    for c in cols:
        a = pd.to_numeric(primary.loc[idx, c], errors="coerce")
        b = pd.to_numeric(other.loc[idx, c], errors="coerce")
        ok = a.notna() & b.notna() & (a.abs() > 0)
        if not ok.any():
            continue
        rel = ((b[ok] - a[ok]).abs() / a[ok].abs())
        n += int(ok.sum())
        bad += int((rel > tol).sum())
    if n >= min_overlap and bad > n / 2:
        return f"lệch > {tol:.0%} so với nguồn ưu tiên ở {bad}/{n} ô trùng kỳ (có thể gắn sai kỳ / khác cơ sở)"
    return None


def merge_financial_sources(frames: List[Tuple[str, pd.DataFrame]],
                            rejected: Optional[List[Dict[str, str]]] = None,
                            cross_check: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Gộp nhiều bảng đã chuẩn hóa theo thứ tự ưu tiên.
    frames: [(tên nguồn, bảng rộng)], nguồn đứng trước được ưu tiên.
    Nguồn sau KHÔNG khớp với phần đã gộp trên các kỳ trùng (source_conflict) → bị loại hẳn (không dùng để bù ô trống),
    ghi vào `rejected`.
    Trả về (bảng giá trị, bảng nguồn của từng ô).
    """
    values = pd.DataFrame()
    sources = pd.DataFrame()
    for name, wide in frames:
        if wide is None or wide.empty:
            continue
        if cross_check and not values.empty:
            why = source_conflict(values, wide)
            if why:
                logger.warning("Bỏ nguồn %s khi gộp BCTC: %s", name, why)
                if rejected is not None:
                    rejected.append({"source": name, "reason": why})
                continue
        src = pd.DataFrame(name, index=wide.index, columns=wide.columns).where(wide.notna())
        if values.empty:
            values, sources = wide.copy(), src
            continue
        values = values.combine_first(wide)
        sources = sources.combine_first(src)
    if not values.empty:
        values = values.sort_index()
        sources = sources.reindex(index=values.index, columns=values.columns)
    return values, sources


def _default_pdf_loader(symbol: str, period: str) -> pd.DataFrame:
    """Số liệu trích từ các PDF BCTC đã tải về kho tài liệu (nguồn dự phòng cuối)."""
    try:
        from core.tai_lieu_bctc import DocumentService
        return DocumentService(db=db).pdf_financials(symbol, period)
    except Exception as exc:
        logger.debug("PDF financial loader failed: %s", exc)
        return pd.DataFrame()


class DataRepository:
    """Truy cập dữ liệu: Cache → Nguồn trực tuyến (theo chuỗi ưu tiên) → DuckDB."""

    def __init__(self, vnstock_client: Optional[VnstockClient] = None,
                 dnse_client: Optional[DNSEClient] = None,
                 vietstock_client: Optional[VietstockClient] = None,
                 pdf_financial_loader: Optional[Callable[[str, str], pd.DataFrame]] = None,
                 use_cache: bool = True, arminer_client=None):
        self._vnstock = vnstock_client or VnstockClient(source=settings.VNSTOCK_SOURCE)
        self._dnse = dnse_client or DNSEClient()
        self._vietstock = vietstock_client or VietstockClient()
        self._pdf_loader = pdf_financial_loader if pdf_financial_loader is not None else _default_pdf_loader
        self._use_cache = use_cache
        if arminer_client is None:
            from core.nguon_du_lieu import ArminerClient
            arminer_client = ArminerClient()
        self._arminer = arminer_client or None        # False = tắt nguồn offline (dùng trong kiểm thử)

    # ─────────────────── Cache helpers ───────────────────────────────────────

    def _cget(self, key: str):
        return cache.get(key) if getattr(self, "_use_cache", False) else None

    def _cset(self, key: str, value, ttl: int):
        if getattr(self, "_use_cache", False):
            cache.set(key, value, ttl=ttl)

    # ─────────────────── Status ──────────────────────────────────────────────

    def get_provider_status(self) -> Dict[str, Any]:
        return {
            "dnse": self._dnse.health_check(),
            "vnstock": self._vnstock.health_check(),
            "vietstock": self._vietstock.health_check(),
            "arminer": self._arminer.health_check() if self._arminer else {"available": False},
            "cache": cache.stats(),
            "strategy": {
                "dnse_recent_days": settings.DNSE_RECENT_DAYS,
                "price_history_sources": settings.PRICE_HISTORY_SOURCES,
                "financial_sources": settings.FINANCIAL_SOURCES,
            },
        }

    # ─────────────────── Price (hybrid) ──────────────────────────────────────

    def _history_from(self, source: str, symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
        if source.startswith("vnstock"):
            return self._vnstock.get_price_history(symbol, start, end, interval, source=source)
        if source == "vietstock":
            return self._vietstock.get_price_history(symbol, start, end, interval)
        if source == "dnse":
            return self._dnse.get_price_history(symbol, start, end, interval)
        return pd.DataFrame()

    def _history_chain(self, symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
        for src in settings.PRICE_HISTORY_SOURCES:
            df = self._history_from(src, symbol, start, end, interval)
            if not df.empty:
                return to_vnd(df, symbol)
        return pd.DataFrame()

    def get_price_history(self, symbol: str, start_date: str = "", end_date: str = "",
                          days: int = 365, interval: str = "1D", force_refresh: bool = False) -> pd.DataFrame:
        symbol = symbol.upper().strip()
        end_dt = pd.to_datetime(end_date) if end_date else pd.Timestamp(datetime.now().date())
        start_dt = pd.to_datetime(start_date) if start_date else end_dt - pd.Timedelta(days=days)
        key = f"price2:{symbol}:{start_dt.date()}:{end_dt.date()}:{interval}"
        if not force_refresh:
            cached = self._cget(key)
            if cached is not None and not cached.empty:
                # chuỗi đã đóng cửa lấy từ bộ nhớ tạm; chỉ nến TRONG PHIÊN được làm mới (nến phút, nhớ LIVE_REFRESH_SECONDS)
                return self._append_live_bar(cached, symbol, end_dt) if interval == "1D" else cached

        cutoff = end_dt - pd.Timedelta(days=settings.DNSE_RECENT_DAYS)
        fmt = "%Y-%m-%d"

        # 1) Đoạn gần nhất từ DNSE
        recent = pd.DataFrame()
        if end_dt >= cutoff:
            recent = to_vnd(self._dnse.get_price_history(symbol, max(start_dt, cutoff).strftime(fmt),
                                                         end_dt.strftime(fmt), interval), symbol)
        # 2) Đoạn cũ (lấy dư 10 ngày để có phiên trùng phục vụ nối chuỗi)
        older = pd.DataFrame()
        older_end = cutoff + pd.Timedelta(days=10) if not recent.empty else end_dt
        if start_dt < cutoff or recent.empty:
            older = self._older_history(symbol, start_dt, older_end, interval, final=not recent.empty)

        merged, k = stitch_prices(recent, older)
        merged = self._fill_from_db(merged, symbol, start_dt, end_dt, interval)
        if merged.empty:
            logger.warning("Không có dữ liệu giá cho %s từ bất kỳ nguồn nào", symbol)
            return pd.DataFrame()

        if "source" not in merged.columns:
            merged["source"] = "unknown"
        merged["source"] = merged["source"].fillna("unknown")
        df = normalizer.normalize_price(merged, symbol=symbol, interval=interval)   # giữ nguyên cột source
        df = df[(df["timestamp"] >= start_dt) & (df["timestamp"] <= end_dt + pd.Timedelta(days=1))].reset_index(drop=True)
        if interval == "1D":
            df = fix_unadjusted_gaps(df, symbol)

        prov = []
        for src, g in df.groupby("source", sort=False):
            prov.append({"source": src, "from": str(g["timestamp"].min().date()),
                         "to": str(g["timestamp"].max().date()), "rows": int(len(g))})
        df.attrs["provenance"] = prov
        df.attrs["stitch_factor"] = k
        df.attrs.setdefault("corporate_action_adjustments", [])

        db.upsert_price(df)
        # Chuỗi ngắn bất thường (nguồn lỗi tạm thời) → chỉ nhớ 60 giây để lần sau thử lấy đủ lịch sử
        span = (df["timestamp"].max() - df["timestamp"].min()).days if not df.empty else 0
        complete = span >= 0.7 * (end_dt - start_dt).days or (end_dt - start_dt).days < 60
        self._cset(key, df, settings.CACHE_TTL_PRICE if complete else 60)
        # Nến tạm tính trong phiên ghép SAU khi lưu: không ghi vào CSDL, không nằm trong bộ nhớ tạm của chuỗi đóng cửa
        return self._append_live_bar(df, symbol, end_dt) if interval == "1D" else df

    def _fill_from_db(self, merged: pd.DataFrame, symbol: str, start_dt: pd.Timestamp, end_dt: pd.Timestamp,
                      interval: str) -> pd.DataFrame:
        """
        Nguồn mạng chỉ trả một đoạn ngắn (vd DNSE lỗi tạm thời, nguồn dự phòng có ít phiên) → biểu đồ kéo sang trái bị trống.
        Bù phần thiếu ở ĐẦU kỳ bằng giá thật đã lưu trong CSDL từ những lần tải trước (không bịa số).
        """
        if interval != "1D" or (end_dt - start_dt).days < 60:
            return merged
        first = pd.to_datetime(merged["timestamp"]).min() if not merged.empty else end_dt + pd.Timedelta(days=1)
        if first <= start_dt + pd.Timedelta(days=20):
            return merged
        try:
            stored = db.get_price(symbol, start_dt.strftime("%Y-%m-%d"),
                                  (first - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
        except Exception:
            return merged
        if stored is None or stored.empty:
            if not merged.empty:
                logger.warning("Giá %s chỉ có từ %s (thiếu lịch sử trước đó – nguồn lỗi tạm thời)", symbol, first.date())
            return merged
        stored = stored.copy()
        stored["timestamp"] = pd.to_datetime(stored["timestamp"])
        if "source" not in stored.columns or stored["source"].isna().all():
            stored["source"] = "db_cache"
        cols = [c for c in merged.columns] if not merged.empty else list(stored.columns)
        for c in cols:
            if c not in stored.columns:
                stored[c] = None
        out = pd.concat([stored[cols], merged[cols]] if not merged.empty else [stored[cols]], ignore_index=True)
        logger.info("Giá %s: bù %d phiên đầu kỳ từ CSDL", symbol, len(stored))
        return out.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)

    def _older_history(self, symbol: str, start_dt: pd.Timestamp, end_dt: pd.Timestamp, interval: str,
                       final: bool) -> pd.DataFrame:
        """
        Đoạn giá CŨ (trước DNSE_RECENT_DAYS) không đổi theo ngày → nhớ tạm 12 giờ thay vì tải lại vnstock mỗi 5 phút.
        Mọi nguồn mạng lỗi → dùng giá đã lưu trong CSDL (giá thật đã tải trước đó) nếu đủ phủ khoảng thời gian.
        """
        fmt = "%Y-%m-%d"
        key = f"older2:{symbol}:{start_dt.date()}:{end_dt.date()}:{interval}"
        cached = self._cget(key)
        if cached is not None and not cached.empty:
            return cached
        df = self._history_chain(symbol, start_dt.strftime(fmt), end_dt.strftime(fmt), interval)
        if df.empty and interval == "1D":
            stored = db.get_price(symbol, start_dt.strftime(fmt), end_dt.strftime(fmt))
            if stored is not None and not stored.empty:
                stored = stored.copy()
                stored["timestamp"] = pd.to_datetime(stored["timestamp"])
                if stored["timestamp"].min() <= start_dt + pd.Timedelta(days=15):
                    logger.info("Giá cũ %s: nguồn mạng lỗi → dùng %d phiên đã lưu trong CSDL", symbol, len(stored))
                    if "source" not in stored.columns or stored["source"].isna().all():
                        stored["source"] = "db_cache"
                    df = stored
        if not df.empty and final:
            self._cset(key, df, 12 * 3600)
        return df

    def _append_live_bar(self, df: pd.DataFrame, symbol: str, end_dt: pd.Timestamp) -> pd.DataFrame:
        """
        Nến NGÀY của DNSE chỉ có sau khi đóng cửa, còn nến 1 phút thì có ngay trong phiên. Nếu chuỗi giá chưa có phiên
        hôm nay (ngày làm việc, từ 9:00) → dựng nến ngày tạm tính từ các nến 1 phút hôm nay: mở = nến đầu, cao/thấp = max/min,
        đóng = giá khớp gần nhất, KL = tổng. Dòng này có cột session_time (giờ cập nhật) để giao diện ghi "trong phiên".
        """
        now = datetime.now()
        today = pd.Timestamp(now.date())
        if df is None or df.empty or end_dt.normalize() < today or now.weekday() >= 5 or now.hour < 9:
            return df
        last_day = pd.to_datetime(df["timestamp"]).max().normalize()
        if last_day >= today:
            return df
        mkey = f"live1m:{symbol}:{today.date()}"
        m = self._cget(mkey)
        if m is None:
            try:
                m = self._dnse.get_price_history(symbol, today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), "1m")
            except Exception as exc:
                logger.debug("intraday bar %s failed: %s", symbol, exc)
                m = pd.DataFrame()
            # Nhớ bằng chu kỳ làm mới giá trong phiên (mặc định 180 giây). Trước đây 20 giây → gần như mỗi lần chuyển trang
            # trong giờ giao dịch đều gọi lại DNSE cho từng mã (mã đang xem, VN-Index, chỉ số, danh sách theo dõi).
            self._cset(mkey, m if m is not None else pd.DataFrame(), settings.LIVE_REFRESH_SECONDS)
        if m is None or m.empty:
            return df
        m = to_vnd(m, symbol)
        m = m[pd.to_datetime(m["timestamp"]).dt.normalize() == today].sort_values("timestamp")
        if m.empty:
            return df
        bar = {"timestamp": today, "open": float(m["open"].iloc[0]), "high": float(m["high"].max()),
               "low": float(m["low"].min()), "close": float(m["close"].iloc[-1]),
               "volume": float(pd.to_numeric(m["volume"], errors="coerce").fillna(0).sum()),
               "symbol": symbol, "source": "dnse_intraday", "interval": "1D",
               "session_time": pd.to_datetime(m["timestamp"].iloc[-1]).strftime("%H:%M")}
        for c in df.columns:
            bar.setdefault(c, None)
        out = pd.concat([df, pd.DataFrame([bar])[list(df.columns) + (["session_time"] if "session_time" not in df.columns else [])]],
                        ignore_index=True)
        out.attrs = dict(getattr(df, "attrs", {}))
        return out

    def get_current_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Giá gần nhất: DNSE trước (cập nhật nhất), dự phòng vnstock rồi Vietstock. Quy về VND."""
        symbol = symbol.upper().strip()
        key = f"current_price2:{symbol}"
        cached = self._cget(key)
        if cached:
            return cached
        if self._cget(f"current_price_fail:{symbol}"):      # vừa thử mọi nguồn thất bại → không gọi lại ngay
            return None
        data = None
        for getter in (self._dnse.get_current_price, self._vnstock.get_current_price, self._vietstock.get_current_price):
            try:
                data = getter(symbol)
            except Exception as exc:
                logger.debug("current price getter failed: %s", exc)
            if data and data.get("price"):
                break
        if not data:
            self._cset(f"current_price_fail:{symbol}", True, 30)
            return None
        if not is_index(symbol) and 0 < float(data["price"]) < 1000:
            for k in ("price", "reference_price", "change"):
                if data.get(k) is not None:
                    data[k] = float(data[k]) * 1000.0
        self._cset(key, data, settings.CACHE_TTL_MARKET)
        return data

    def get_intraday(self, symbol: str, interval: str = "15m", days: int = 14,
                     end: Optional[str] = None) -> pd.DataFrame:
        """Nến trong ngày (mặc định 15 phút) từ DNSE – chỉ dùng cho tín hiệu bot (Tầng 3). Lỗi/không có → DataFrame rỗng."""
        symbol = symbol.upper().strip()
        end_dt = pd.to_datetime(end) + pd.Timedelta(hours=23, minutes=59) if end else pd.Timestamp(datetime.now())
        start_dt = end_dt - pd.Timedelta(days=days)
        key = f"intraday:{symbol}:{interval}:{start_dt:%Y%m%d%H}:{end_dt:%Y%m%d%H%M}"[:-1]   # cache ~10 phút
        cached = self._cget(key)
        if cached is not None and not cached.empty:
            return cached
        try:
            df = self._dnse.get_price_history(symbol, start_dt.strftime("%Y-%m-%d %H:%M"),
                                              end_dt.strftime("%Y-%m-%d %H:%M"), interval)
        except Exception as exc:
            logger.debug("intraday %s failed: %s", symbol, exc)
            df = pd.DataFrame()
        if df is None or df.empty:
            return pd.DataFrame()
        df = to_vnd(df, symbol)
        df = df[pd.to_datetime(df["timestamp"]) <= end_dt].sort_values("timestamp").reset_index(drop=True)
        self._cset(key, df, 600)
        return df

    def get_index_history(self, index_code: str = "VNINDEX", start_date: str = "", days: int = 365) -> pd.DataFrame:
        return self.get_price_history(index_code, start_date=start_date, days=days)

    # ─────────────────── Company ─────────────────────────────────────────────

    def get_company_info(self, symbol: str) -> Dict[str, Any]:
        symbol = symbol.upper().strip()
        key = f"company2:{symbol}"
        cached = self._cget(key)
        if cached and (cached.get("issue_share") or self._cget(f"company2_retry:{symbol}")):
            return cached
        # bản lưu thiếu số CP niêm yết (lần trước vnstock lỗi → lấy từ CSDL/nguồn phụ) → thử lại vnstock (tối đa 1 lần/giờ)
        if cached:
            self._cset(f"company2_retry:{symbol}", {"at": str(pd.Timestamp.now())}, 3600)
        info = self._vnstock.get_company_info(symbol) or cached or db.get_company(symbol) or {}
        if info:
            info["symbol"] = symbol
            try:
                db.upsert_company(info)
            except Exception:
                pass
            self._cset(key, info, settings.CACHE_TTL_FINANCIAL)
        return info

    @staticmethod
    def manual_dividends(symbol: str) -> pd.DataFrame:
        """Cổ tức tiền mặt nhập tay có nguồn (config/announced_dividends.json) – ưu tiên cao nhất."""
        import json
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "announced_dividends.json")
        try:
            with open(path, encoding="utf-8") as f:
                rows = (json.load(f) or {}).get(symbol.upper()) or []
        except (OSError, ValueError):
            return pd.DataFrame(columns=["date", "dps", "year"])
        df = pd.DataFrame([{"date": pd.to_datetime(r.get("ex_date"), errors="coerce"), "dps": r.get("dps"),
                            "year": np.nan, "source": r.get("source", "")} for r in rows if r.get("dps")])
        if df.empty:
            return pd.DataFrame(columns=["date", "dps", "year"])
        df["dps"] = pd.to_numeric(df["dps"], errors="coerce")
        df = df.dropna(subset=["date", "dps"]).sort_values("date").reset_index(drop=True)
        df.attrs["source"] = "nhập tay có nguồn (config/announced_dividends.json)"
        return df

    def get_dividends(self, symbol: str) -> pd.DataFrame:
        """Cổ tức tiền mặt đã công bố (date, dps VND/cp): nhập tay có nguồn → vnstock dividends → bảng sự kiện."""
        manual = self.manual_dividends(symbol)
        if not manual.empty:
            return manual
        key = f"dividends1:{symbol.upper()}"
        cached = self._cget(key)
        if cached is not None:
            return cached
        try:
            df = self._vnstock.get_dividends(symbol) if hasattr(self._vnstock, "get_dividends") else pd.DataFrame()
        except Exception as exc:
            logger.debug("dividends %s failed: %s", symbol, exc)
            df = pd.DataFrame()
        df = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        if df.empty:                       # vnstock không có hàm dividends() → lấy cổ tức tiền mặt từ bảng sự kiện
            try:
                from core.nguon_du_lieu import parse_cash_dividend_events
                df = parse_cash_dividend_events(self.get_company_events(symbol))
                if not df.empty:
                    df.attrs["source"] = "vnstock sự kiện (value_per_share)"
            except Exception as exc:
                logger.debug("dividend events %s failed: %s", symbol, exc)
        self._cset(key, df, 24 * 3600 if not df.empty else 3600)
        return df

    def get_company_events(self, symbol: str) -> pd.DataFrame:
        return self._vnstock.get_company_events(symbol)

    def get_shareholders(self, symbol: str) -> pd.DataFrame:
        return self._vnstock.get_shareholders(symbol)

    def get_officers(self, symbol: str) -> pd.DataFrame:
        return self._vnstock.get_officers(symbol)

    def get_vnstock_news(self, symbol: str) -> List[Dict[str, Any]]:
        return self._vnstock.get_company_news(symbol)

    # ─────────────────── Financial statements (multi-source) ─────────────────

    def _raw_statement(self, source: str, symbol: str, statement: str, period: str) -> Tuple[pd.DataFrame, Optional[float]]:
        """Bảng thô từ một nguồn + hệ số đơn vị đã biết của nguồn đó (None = tự đoán)."""
        if source.startswith("vnstock"):
            df = self._vnstock.get_financial_statement(symbol, statement, period, source=source)
            # KBS đã quy về VND; VCI (iq.vietcap) trả VND. Bảng v3 có ghi "(Tỷ đồng)" → nhận diện theo nhãn.
            return df, None
        if source == "vietstock":
            return self._vietstock.get_financial_statement(symbol, statement, period), 1.0
        if source == "arminer":
            if self._arminer is None or statement == "ratio":
                return pd.DataFrame(), None
            return self._arminer.get_financial_statement(symbol, statement, period), 1.0
        if source == "pdf" and self._pdf_loader is not None:
            return self._pdf_loader(symbol, period), 1.0
        return pd.DataFrame(), None

    def get_financials(self, symbol: str, period: str = "year", years: int = 10,
                       force_refresh: bool = False) -> Dict[str, Any]:
        """
        BCTC chuẩn hóa nhiều năm, gộp nhiều nguồn.

        Returns dict:
          data      : DataFrame rộng (index = khóa kỳ tăng dần, cột = chỉ tiêu chuẩn, VND)
          sources   : DataFrame cùng kích thước – nguồn của từng ô
          raw       : {statement: {source: bảng thô}} để hiển thị đầy đủ dòng gốc
          attempts  : nhật ký thử từng nguồn (thành công / rỗng / lỗi)
        """
        symbol = symbol.upper().strip()
        period = "year" if period in ("year", "annual", "Y") else "quarter"
        key = f"fin7:{symbol}:{period}"   # đổi phiên bản khóa khi sửa bộ chuẩn hóa → không dùng lại số cũ trong cache
        if not force_refresh:
            cached = self._cget(key)
            if cached is not None:
                return self._trim(cached, years, period)

        frames: List[Tuple[str, pd.DataFrame]] = []
        basis_log: Dict[str, Dict[str, Dict[str, str]]] = {}
        # Số NĂM đã có trong bộ nhớ tạm (không gọi mạng thêm) làm bằng chứng đối chiếu khi nhận dạng số quý
        annual_ref = None
        if period == "quarter":
            cached_year = self._cget(f"fin7:{symbol}:year")
            annual_ref = (cached_year or {}).get("data") if isinstance(cached_year, dict) else None
            if annual_ref is None:
                # Chưa có số năm trong bộ nhớ tạm → tải trước để có bằng chứng đối chiếu (tổng 4 quý = số năm). Thiếu bước
                # này LCTT quý (vd FPT) bị "không xác định được số quý độc lập hay lũy kế" → app bỏ TTM.
                try:
                    annual_ref = self.get_financials(symbol, period="year", years=10).get("data")
                except Exception as exc:
                    logger.debug("annual reference %s failed: %s", symbol, exc)
        raw: Dict[str, Dict[str, pd.DataFrame]] = {}
        attempts: List[Dict[str, Any]] = []
        for source in settings.FINANCIAL_SOURCES:
            per_source: List[pd.DataFrame] = []
            if source == "pdf":
                df, factor = self._raw_statement(source, symbol, "all", period)
                if df is not None and not df.empty:
                    df = self._normalize_pdf_quarters(df, basis_log.setdefault(source, {}))
                    per_source.append(df)       # trình trích PDF đã trả về dạng rộng chuẩn
                attempts.append({"source": source, "statement": "all", "rows": 0 if df is None else len(df)})
            else:
                for statement in ("income_statement", "balance_sheet", "cash_flow", "ratio"):
                    try:
                        df, factor = self._raw_statement(source, symbol, statement, period)
                    except Exception as exc:
                        attempts.append({"source": source, "statement": statement, "error": str(exc)})
                        continue
                    attempts.append({"source": source, "statement": statement, "rows": len(df)})
                    if df is None or df.empty:
                        continue
                    raw.setdefault(statement, {})[source] = df
                    code = _STATEMENT_CODE[statement]
                    wide = canonicalize(df, code, unit_factor=factor)
                    # số quý lũy kế từ đầu năm → số từng quý; không xác định được → không dùng để cộng ra số năm
                    wide, basis, why = normalize_quarters(wide, code, reference=annual_ref)
                    if code in ("is", "cf") and (np.asarray(wide.index, dtype=int) % 10 > 0).any():
                        basis_log.setdefault(source, {})[code] = {"basis": basis, "why": why}
                        if basis == UNKNOWN:
                            logger.warning("%s %s %s: không xác định được số quý độc lập hay lũy kế (%s)",
                                           symbol, source, code, why)
                    wide = self._align_period(wide, period, code, basis)
                    if not wide.empty:
                        per_source.append(wide)
            if not per_source:
                continue
            combined = per_source[0]
            for w in per_source[1:]:
                combined = combined.combine_first(w)
            if source.startswith("vnstock"):
                combined = apply_scale(combined, infer_scale(combined))
            frames.append((source, combined))

        rejected: List[Dict[str, str]] = []
        # Kiểm tra chéo cho số QUÝ (lỗi gắn sai kỳ hay gặp ở nguồn phụ); số NĂM có thể lệch hợp lệ (điều chỉnh hồi tố,
        # BCTC riêng vs hợp nhất trong PDF) → không loại cả nguồn.
        values, sources = merge_financial_sources(frames, rejected, cross_check=(period == "quarter"))
        for r in rejected:
            attempts.append({"source": r["source"], "statement": "all", "rejected": r["reason"]})
        # Nhận dạng số quý chỉ tính cho nguồn THỰC SỰ có ô trong bảng gộp (nguồn bị loại / không đóng góp ô nào không được
        # làm app bỏ TTM – vd KBS "unknown" trong khi toàn bộ số quý lấy từ VCI đã xác nhận là số từng quý).
        if sources is not None and not sources.empty:
            used = {str(x) for x in pd.unique(sources.values.ravel()) if isinstance(x, str)}
            basis_log = {k: v for k, v in basis_log.items() if k in used}
        if values.empty:
            # Không lấy được trực tuyến → dùng bản đã lưu trong DuckDB (nếu có)
            values, sources = long_to_wide(db.get_financial(symbol, period))
            if not values.empty:
                attempts.append({"source": "duckdb", "statement": "all", "rows": len(values)})
        else:
            db.upsert_financial(symbol, period, wide_to_long(values, sources))

        result = {"symbol": symbol, "period": period, "data": values, "sources": sources,
                  "raw": raw, "attempts": attempts, "quarter_basis": basis_log, "rejected_sources": rejected,
                  "fetched_at": datetime.now().isoformat()}
        if not values.empty:
            self._cset(key, result, settings.CACHE_TTL_FINANCIAL)
        return self._trim(result, years, period)

    @staticmethod
    def _normalize_pdf_quarters(df: pd.DataFrame, log: Dict[str, Dict[str, str]]) -> pd.DataFrame:
        """PDF trả chung một bảng: chuẩn hóa riêng nhóm KQKD và nhóm LCTT.
        Mặc định theo mẫu VAS khi không tự nhận dạng được: KQKD lấy cột "Quý này" (độc lập),
        LCTT mẫu B03a chỉ có "Lũy kế từ đầu năm" (lũy kế)."""
        if df is None or df.empty or not (np.asarray(df.index, dtype=int) % 10 > 0).any():
            return df
        out = df.copy()
        for code, default in (("is", DISCRETE), ("cf", CUMULATIVE)):
            cols = flow_columns(df, code)
            if not cols:
                continue
            part, basis, why = normalize_quarters(df[cols], code, default=default)
            out[cols] = part[cols]
            log[code] = {"basis": basis, "why": why}
        return out

    @staticmethod
    def _align_period(wide: pd.DataFrame, period: str, statement: str = "is", basis: str = UNKNOWN) -> pd.DataFrame:
        """
        Chỉ giữ đúng loại kỳ được yêu cầu. Khi cần số liệu NĂM mà nguồn chỉ có số quý:
          • Bảng cân đối / bảng chỉ số (chỉ tiêu SỐ DƯ, vd vốn CSH, số CP lưu hành) → số dư cuối năm = số của
            quý 4; năm chưa có quý 4 thì KHÔNG tạo số năm (tránh lấy số dư giữa năm làm số cuối năm).
          • KQKD / LCTT (chỉ tiêu DÒNG, vd doanh thu, LNST, CFO) → TỔNG đủ 4 quý của năm, CHỈ KHI basis =
            "discrete" (đã chuẩn hóa thành số từng quý – xem core/du_lieu.py); thiếu quý nào thì bỏ trống
            chỉ tiêu đó; basis khác → không tạo số năm. EPS không cộng.
        Số năm do nguồn cung cấp trực tiếp luôn được ưu tiên.
        """
        if wide.empty:
            return wide
        q = np.asarray(wide.index, dtype=int) % 10
        if period == "year":
            annual = wide[q == 0]
            quarterly = wide[q > 0]
            if not quarterly.empty:
                keys = np.asarray(quarterly.index, dtype=int)
                years = keys // 10 * 10
                if statement in ("bs", "ratio"):
                    q4 = quarterly[keys % 10 == 4]
                    by_year = q4.copy()
                    by_year.index = np.asarray(q4.index, dtype=int) // 10 * 10
                elif basis != DISCRETE:
                    by_year = pd.DataFrame()     # chưa chắc số quý là số độc lập → không cộng ra số năm
                else:
                    num = quarterly.apply(pd.to_numeric, errors="coerce")
                    num = num.drop(columns=[c for c in num.columns if c in PER_SHARE_FLOW])   # EPS không cộng
                    by_year = num.groupby(years).sum(min_count=4)
                    n_q = pd.Series(keys % 10, index=quarterly.index).groupby(years).nunique()
                    by_year = by_year[by_year.index.isin(n_q[n_q == 4].index)]
                if not by_year.empty:
                    annual = annual.combine_first(by_year) if not annual.empty else by_year
            return annual.sort_index()
        quarterly = wide[q > 0]
        if statement in ("bs", "ratio") and (q == 0).any():
            # Số dư cuối năm = số dư cuối Q4 → bù cho Q4 khi nguồn chỉ có số năm
            annual = wide[q == 0].copy()
            annual.index = np.asarray(annual.index, dtype=int) + 4
            quarterly = quarterly.combine_first(annual) if not quarterly.empty else annual
        return quarterly.sort_index()

    @staticmethod
    def _trim(result: Dict[str, Any], years: int, period: str) -> Dict[str, Any]:
        data = result.get("data", pd.DataFrame())
        if data is None or data.empty or not years:
            return result
        n = years if period == "year" else years * 4
        out = dict(result)
        out["data"] = data.iloc[-n:]
        src = result.get("sources", pd.DataFrame())
        out["sources"] = src.iloc[-n:] if src is not None and not src.empty else src
        return out

    # Tương thích ngược: các trang/analyzer cũ gọi bảng thô từng loại
    def _legacy(self, symbol: str, statement: str, period: str) -> pd.DataFrame:
        p = "year" if period in ("year", "annual") else "quarter"
        key = f"financial2:{symbol.upper()}:{statement}:{p}"
        cached = self._cget(key)
        if cached is not None and not cached.empty:
            return cached
        for source in settings.FINANCIAL_SOURCES:
            if source == "pdf":
                continue
            df, _ = self._raw_statement(source, symbol.upper(), statement, p)
            if df is not None and not df.empty:
                self._cset(key, df, settings.CACHE_TTL_FINANCIAL)
                return df
        return pd.DataFrame()

    def get_income_statement(self, symbol: str, period: str = "quarter") -> pd.DataFrame:
        return self._legacy(symbol, "income_statement", period)

    def get_balance_sheet(self, symbol: str, period: str = "quarter") -> pd.DataFrame:
        return self._legacy(symbol, "balance_sheet", period)

    def get_cash_flow(self, symbol: str, period: str = "quarter") -> pd.DataFrame:
        return self._legacy(symbol, "cash_flow", period)

    def get_financial_ratios(self, symbol: str, period: str = "quarter") -> pd.DataFrame:
        return self._legacy(symbol, "ratio", period)

    # ─────────────────── Listings ────────────────────────────────────────────

    def get_all_symbols(self) -> pd.DataFrame:
        cached = self._cget("all_symbols2")
        if cached is not None and not cached.empty:
            return cached
        df = self._vnstock.get_all_symbols()
        if not df.empty:
            self._cset("all_symbols2", df, 3600 * 12)
        return df

    def get_symbols_by_industries(self) -> pd.DataFrame:
        cached = self._cget("symbols_icb2")
        if cached is not None and not cached.empty:
            return cached
        df = self._vnstock.get_symbols_by_industries()
        if not df.empty:
            self._cset("symbols_icb2", df, 3600 * 24)
        return df

    def get_price_board(self, symbols: List[str]) -> pd.DataFrame:
        return self._vnstock.get_price_board(symbols)

    # ─────────────────── Portfolio ───────────────────────────────────────────

    def get_portfolio(self, name: str = "default") -> pd.DataFrame:
        return db.get_portfolio(name)

    def add_position(self, portfolio_name: str, symbol: str, quantity: float, buy_price: float,
                     buy_date: str = "", fee_pct: float = 0.0015, notes: str = ""):
        db.add_position(portfolio_name, symbol, quantity, buy_price, buy_date, fee_pct, notes)

    def delete_position(self, position_id: int):
        db.delete_position(position_id)


# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Import chéo (các file import lẫn nhau) – đặt CUỐI file để tránh vòng lặp import; chỉ được dùng bên trong hàm.
# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
from core.phan_tich_co_ban import META_COLS, _norm, flatten_columns, key_to_label, order_tabular, parse_period_key
