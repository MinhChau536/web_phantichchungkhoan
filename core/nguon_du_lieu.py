"""
core/nguon_du_lieu.py – gộp từ 6 module (15/10/2026).

MỤC LỤC
  • data/providers/base_provider.py – Abstract base class for all data providers.
      hàm/lớp chính: BaseProvider
  • data/providers/arminer_client.py – Nguồn BCTC năm đóng gói sẵn (offline) từ dự án vn-annual-report-miner (MIT) – xem data/bundled/README.md.
      hàm/lớp chính: ArminerClient
  • data/providers/dnse_client.py – DNSE market-data client – nguồn giá GẦN NHẤT của hệ thống.
      hàm/lớp chính: to_param, note_status, backing_off, is_index, DNSEClient
  • data/providers/vietstock_client.py – Vietstock Finance provider – NGUỒN DỰ PHÒNG (thử nghiệm).
      hàm/lớp chính: VietstockClient
  • data/providers/vnstock_client.py – Vnstock provider – bao bọc thư viện vnstock (ưu tiên API v4, tương thích ngược v3).
      hàm/lớp chính: source_cooldowns, parse_cash_dividend_events, classify_share_event, parse_share_events, parse_paid_share_events, events_cover, parse_dividends, VnstockClient
  • services/dnse_realtime.py – Giá REALTIME qua DNSE OpenAPI (WebSocket) – chỉ ĐỌC giá, không đặt lệnh.
      hàm/lớp chính: canonical, is_index_dnse_realtime, sign, auth_message, decode, RealtimeFeed, configured, get_feed, snapshot, active, status

Tên trùng giữa các phần đã được đổi (tên cũ → tên mới trong file này):
  vietstock_client._HEADERS → _HEADERS_vietstock_client
  vnstock_client._INDEX_ALIAS → _INDEX_ALIAS_vnstock_client
  vnstock_client._STATEMENTS → _STATEMENTS_vnstock_client
  dnse_realtime._INDEX_ALIAS → _INDEX_ALIAS_dnse_realtime
  dnse_realtime.is_index → is_index_dnse_realtime
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: data/providers/base_provider.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Abstract base class for all data providers.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import pandas as pd
from datetime import datetime


class BaseProvider(ABC):
    """Abstract base data provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is currently available."""
        pass

    @abstractmethod
    def get_price_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1D",
    ) -> pd.DataFrame:
        """Get OHLCV price history."""
        pass

    @abstractmethod
    def get_current_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get latest price data."""
        pass

    def validate_symbol(self, symbol: str) -> str:
        """Normalize and validate stock symbol."""
        return symbol.upper().strip()

    def health_check(self) -> Dict[str, Any]:
        """Return provider health status."""
        return {
            "provider": self.name,
            "available": self.is_available,
            "timestamp": datetime.now().isoformat(),
        }


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: data/providers/arminer_client.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Nguồn BCTC năm đóng gói sẵn (offline) từ dự án vn-annual-report-miner (MIT) – xem data/bundled/README.md.

Trả về bảng cùng dạng ma trận như VCI (item, item_en, item_id, các cột năm – năm mới nhất đứng trước)
để đi chung đường chuẩn hóa canonicalize() với các nguồn khác. Chỉ có kỳ NĂM; giá trị theo VND.
"""


import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)
BASE = Path(__file__).resolve().parent.parent / "data" / "bundled" / "arminer_bctc"
_STATEMENTS = {"income_statement": "income_statement", "balance_sheet": "balance_sheet", "cash_flow": "cash_flow"}


@lru_cache(maxsize=8)
def _load(statement: str) -> pd.DataFrame:
    frames = []
    for ex in ("HSX", "HNX"):
        p = BASE / statement / f"{ex}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p, columns=["ticker", "year", "item_code", "item_name", "value"]))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


class ArminerClient:
    name = "arminer"

    def available(self) -> bool:
        return BASE.exists() and any(BASE.rglob("*.parquet"))

    def get_financial_statement(self, symbol: str, statement: str, period: str = "year") -> pd.DataFrame:
        if period not in ("year", "annual", "Y") or statement not in _STATEMENTS:
            return pd.DataFrame()
        df = _load(_STATEMENTS[statement])
        if df.empty:
            return pd.DataFrame()
        sub = df[df["ticker"] == symbol.upper()]
        if sub.empty:
            return pd.DataFrame()
        mat = sub.pivot_table(index=["item_name", "item_code"], columns="year", values="value", aggfunc="first")
        mat = mat[sorted(mat.columns, reverse=True)]
        mat.columns = [str(int(c)) for c in mat.columns]
        mat = mat.reset_index().rename(columns={"item_name": "item", "item_code": "item_id"})
        mat.insert(1, "item_en", None)
        return mat

    def health_check(self):
        return {"provider": "arminer (offline)", "available": self.available()}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: data/providers/dnse_client.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
DNSE market-data client – nguồn giá GẦN NHẤT của hệ thống.

Dùng API biểu đồ công khai của DNSE (Entrade), không cần đăng nhập:
  GET {CHART}/ohlcs/stock?symbol=FPT&resolution=1D&from=<unix>&to=<unix>
  GET {CHART}/ohlcs/index?symbol=VNINDEX&resolution=1D&from=<unix>&to=<unix>
Phản hồi dạng UDF: {"t": [...], "o": [...], "h": [...], "l": [...], "c": [...], "v": [...]}

Giá cổ phiếu DNSE trả về theo đơn vị NGHÌN ĐỒNG (vd 105.5 = 105.500đ); lớp
DataRepository sẽ quy đổi toàn bộ về VND.
"""


import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.cau_hinh import settings


logger = logging.getLogger(__name__)

CHART_BASE = "https://services.entrade.com.vn/chart-api/v2"
INDEX_SYMBOLS = {"VNINDEX", "VN30", "HNXINDEX", "HNX30", "UPCOMINDEX", "HNX", "UPCOM", "VN100", "VNXALL"}
_INDEX_ALIAS = {"HNX": "HNXINDEX", "UPCOM": "UPCOMINDEX", "VN-INDEX": "VNINDEX", "VNI": "VNINDEX"}
_RESOLUTION = {"1D": "1D", "1W": "1W", "1M": "1M", "1H": "1H", "30m": "30", "15m": "15", "5m": "5", "1m": "1"}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://banggia.dnse.com.vn",
    "Referer": "https://banggia.dnse.com.vn/",
}


# ── Chống dữ liệu "đóng băng" & tránh bị DNSE giới hạn tần suất ──
# API biểu đồ DNSE đứng sau bộ nhớ đệm (CDN): cùng một URL sẽ nhận lại bản đã lưu. Trước đây tham số `to` = 0h ngày mai
# → URL giống hệt suốt cả ngày → nhận lại số liệu của lần gọi đầu (vd VN-INDEX đứng ở 11:20, giá FPT lệch 100đ).
# Nay khi khoảng thời gian chạm tới hiện tại, `to` = giây hiện tại → mỗi lần gọi là URL mới, luôn lấy số mới nhất.
_BACKOFF_UNTIL = 0.0           # DNSE trả 429 (gọi quá dày) → tạm dừng các lệnh gọi GIÁ TRONG PHIÊN tới thời điểm này
_NO_CACHE = {"Cache-Control": "no-cache", "Pragma": "no-cache"}


def to_param(end: datetime) -> int:
    """Mốc `to` (unix) cho API DNSE: cuối ngày `end`, nhưng không vượt quá hiện tại (để URL luôn mới khi lấy dữ liệu hôm nay)."""
    fixed = int(time.mktime((end + timedelta(days=1)).timetuple()))
    now = int(time.time())
    return now if fixed > now else fixed


def note_status(code: int, symbol: str = "") -> None:
    global _BACKOFF_UNTIL
    if code == 429:
        _BACKOFF_UNTIL = time.time() + 15
        logger.warning("DNSE báo gọi quá dày (HTTP 429) %s – tạm giãn cập nhật giá trong phiên 15 giây", symbol)
    elif code >= 400:
        logger.warning("DNSE trả HTTP %s cho %s", code, symbol)


def backing_off() -> bool:
    return time.time() < _BACKOFF_UNTIL


def is_index(symbol: str) -> bool:
    return symbol.upper().strip() in INDEX_SYMBOLS


class DNSEClient(BaseProvider):
    """Giá OHLCV & giá gần nhất từ DNSE."""

    def __init__(self, session: Optional[requests.Session] = None):
        self._session = session or self._build_session()
        self._available: Optional[bool] = None
        self._last_error: str = ""

    @staticmethod
    def _build_session() -> requests.Session:
        s = requests.Session()
        retry = Retry(total=settings.MAX_RETRIES, backoff_factor=settings.RETRY_BACKOFF,
                      status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"],
                      raise_on_status=False)
        s.mount("https://", HTTPAdapter(max_retries=retry))
        s.headers.update(_HEADERS)
        return s

    @property
    def name(self) -> str:
        return "DNSE"

    @property
    def is_available(self) -> bool:
        if self._available is None:
            end = datetime.now()
            df = self._fetch("VNINDEX", end - timedelta(days=10), end, "1D")
            self._available = not df.empty
        return bool(self._available)

    # ─────────────────── Core fetch ───────────────────────────────────────────

    def _fetch(self, symbol: str, start: datetime, end: datetime, interval: str) -> pd.DataFrame:
        sym = _INDEX_ALIAS.get(symbol.upper().strip(), symbol.upper().strip())
        kind = "index" if is_index(sym) else "stock"
        params = {
            "symbol": sym,
            "resolution": _RESOLUTION.get(interval, "1D"),
            "from": int(time.mktime(start.timetuple())),
            "to": to_param(end),
        }
        try:
            resp = self._session.get(f"{CHART_BASE}/ohlcs/{kind}", params=params, headers=_NO_CACHE,
                                     timeout=settings.REQUEST_TIMEOUT)
            if resp.status_code != 200:
                self._last_error = f"HTTP {resp.status_code}"
                note_status(resp.status_code, sym)
                return pd.DataFrame()
            return self.parse_udf(resp.json(), sym, interval)
        except Exception as exc:
            self._last_error = str(exc)
            logger.debug("DNSE fetch failed for %s: %s", sym, exc)
            return pd.DataFrame()

    @staticmethod
    def parse_udf(data: Dict[str, Any], symbol: str, interval: str = "1D") -> pd.DataFrame:
        """Chuyển phản hồi UDF {t,o,h,l,c,v} thành DataFrame chuẩn."""
        if not isinstance(data, dict) or not data.get("t"):
            return pd.DataFrame()
        n = len(data["t"])
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(data["t"], unit="s", utc=True)
                           .tz_convert("Asia/Ho_Chi_Minh").tz_localize(None),
            "open": data.get("o", [None] * n),
            "high": data.get("h", [None] * n),
            "low": data.get("l", [None] * n),
            "close": data.get("c", [None] * n),
            "volume": data.get("v", [None] * n),
        })
        if interval in ("1D", "1W", "1M"):
            df["timestamp"] = df["timestamp"].dt.normalize()
        df["symbol"] = symbol.upper()
        df["source"] = "dnse"
        return df.dropna(subset=["close"]).reset_index(drop=True)

    # ─────────────────── Public API ──────────────────────────────────────────

    def get_price_history(self, symbol: str, start_date: str, end_date: str,
                          interval: str = "1D") -> pd.DataFrame:
        start = pd.to_datetime(start_date).to_pydatetime()
        end = pd.to_datetime(end_date).to_pydatetime()
        return self._fetch(symbol, start, end, interval)

    def get_current_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Giá khớp gần nhất: nến 1 phút mới nhất trong ngày, nếu không có thì nến ngày gần nhất."""
        end = datetime.now()
        intraday = self._fetch(symbol, end - timedelta(days=3), end, "1m")
        daily = self._fetch(symbol, end - timedelta(days=15), end, "1D")
        if daily.empty and intraday.empty:
            return None
        last = intraday.iloc[-1] if not intraday.empty else daily.iloc[-1]
        prev_close = None
        if not daily.empty:
            last_day = pd.Timestamp(last["timestamp"]).normalize()
            prior = daily[daily["timestamp"] < last_day]
            if not prior.empty:
                prev_close = float(prior["close"].iloc[-1])
        price = float(last["close"])
        change = price - prev_close if prev_close else None
        return {
            "symbol": symbol.upper(),
            "price": price,
            "reference_price": prev_close,
            "change": change,
            "change_pct": (change / prev_close * 100) if (change is not None and prev_close) else None,
            "volume": float(daily["volume"].iloc[-1]) if not daily.empty else None,
            "timestamp": str(last["timestamp"]),
            "source": "dnse",
            "unit": "index_point" if is_index(symbol) else "thousand_vnd",
        }

    def health_check(self) -> Dict[str, Any]:
        res = super().health_check()
        res["base_url"] = CHART_BASE
        res["last_error"] = self._last_error
        return res


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: data/providers/vietstock_client.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Vietstock Finance provider – NGUỒN DỰ PHÒNG (thử nghiệm).

Vietstock không có API công khai chính thức; client này đọc các endpoint mà
website finance.vietstock.vn dùng nội bộ, nên có thể ngừng hoạt động khi Vietstock
thay đổi trang. Mọi hàm đều trả DataFrame rỗng thay vì ném lỗi để chuỗi dự phòng
của DataRepository tự chuyển sang nguồn kế tiếp.

  Giá lịch sử : api.vietstock.vn/tvnew/history (định dạng UDF giống TradingView)
  BCTC        : finance.vietstock.vn/data/financeinfo (cần token chống CSRF lấy từ trang HTML)
"""


import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from core.cau_hinh import settings


logger = logging.getLogger(__name__)

FINANCE_BASE = "https://finance.vietstock.vn"
CHART_URL = "https://api.vietstock.vn/tvnew/history"
_HEADERS_vietstock_client = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9",
    "Referer": "https://stockchart.vietstock.vn/",
}
# Mã loại báo cáo trên Vietstock
_REPORT_TYPE = {"income_statement": "KQKD", "balance_sheet": "CDKT", "cash_flow": "LC", "ratio": "CSTC"}


class VietstockClient(BaseProvider):

    def __init__(self, session: Optional[requests.Session] = None):
        self._session = session or requests.Session()
        self._session.headers.update(_HEADERS_vietstock_client)
        self._token: Optional[str] = None
        self._last_error = ""

    @property
    def name(self) -> str:
        return "Vietstock"

    @property
    def is_available(self) -> bool:
        return True  # chỉ biết khi gọi thật

    # ─────────────────── Price ───────────────────────────────────────────────

    def get_price_history(self, symbol: str, start_date: str, end_date: str,
                          interval: str = "1D") -> pd.DataFrame:
        res = {"1D": "D", "1W": "W", "1M": "M"}.get(interval, "D")
        params = {
            "symbol": symbol.upper(), "resolution": res,
            "from": int(time.mktime(pd.to_datetime(start_date).timetuple())),
            "to": int(time.mktime(pd.to_datetime(end_date).timetuple())) + 86400,
        }
        try:
            r = self._session.get(CHART_URL, params=params, timeout=settings.REQUEST_TIMEOUT)
            if r.status_code != 200:
                self._last_error = f"HTTP {r.status_code}"
                return pd.DataFrame()
            data = r.json()
            if not isinstance(data, dict) or data.get("s") not in (None, "ok") or not data.get("t"):
                return pd.DataFrame()
            df = pd.DataFrame({
                "timestamp": pd.to_datetime(data["t"], unit="s").normalize(),
                "open": data.get("o"), "high": data.get("h"), "low": data.get("l"),
                "close": data.get("c"), "volume": data.get("v"),
            })
            df["symbol"] = symbol.upper()
            df["source"] = "vietstock"
            return df.dropna(subset=["close"])
        except Exception as exc:
            self._last_error = str(exc)
            return pd.DataFrame()

    def get_current_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        end = datetime.now()
        df = self.get_price_history(symbol, (end - pd.Timedelta(days=10)).strftime("%Y-%m-%d"),
                                    end.strftime("%Y-%m-%d"))
        if df.empty:
            return None
        return {"symbol": symbol.upper(), "price": float(df["close"].iloc[-1]),
                "timestamp": str(df["timestamp"].iloc[-1]), "source": "vietstock"}

    # ─────────────────── Financial statements ────────────────────────────────

    def _ensure_token(self, symbol: str) -> Optional[str]:
        if self._token:
            return self._token
        try:
            r = self._session.get(f"{FINANCE_BASE}/{symbol.upper()}/tai-chinh.htm",
                                  timeout=settings.REQUEST_TIMEOUT)
            m = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', r.text)
            self._token = m.group(1) if m else None
        except Exception as exc:
            self._last_error = str(exc)
        return self._token

    def get_financial_statement(self, symbol: str, statement: str, period: str = "year",
                                n_periods: int = 8) -> pd.DataFrame:
        report = _REPORT_TYPE.get(statement)
        token = self._ensure_token(symbol) if report else None
        if not token:
            return pd.DataFrame()
        form = {
            "Code": symbol.upper(), "ReportType": report,
            "ReportTermType": "1" if period == "year" else "2",
            "Unit": "1", "Page": "1", "PageSize": str(n_periods),
            "__RequestVerificationToken": token,
        }
        try:
            r = self._session.post(f"{FINANCE_BASE}/data/financeinfo", data=form,
                                   timeout=settings.REQUEST_TIMEOUT)
            if r.status_code != 200:
                self._last_error = f"HTTP {r.status_code}"
                return pd.DataFrame()
            df = self.parse_financeinfo(r.json(), period)
            df.attrs["source"] = "vietstock"
            return df
        except Exception as exc:
            self._last_error = str(exc)
            return pd.DataFrame()

    @staticmethod
    def parse_financeinfo(payload: Any, period: str = "year") -> pd.DataFrame:
        """
        Đọc phản hồi financeinfo một cách "chịu lỗi":
          payload[0] : danh sách kỳ   [{"YearPeriod": 2024, "TermCode": "N"/"Q1"…}, …]
          payload[1] : {"<tên báo cáo>": [{"Name": ..., "NameEn": ..., "Value1": ..., "Value2": ...}, …]}
        Trả về dạng ma trận item × kỳ giống vnstock để dùng chung bộ chuẩn hóa.
        """
        if not isinstance(payload, list) or len(payload) < 2:
            return pd.DataFrame()
        periods_raw, body = payload[0], payload[1]
        labels: List[str] = []
        for p in periods_raw or []:
            y = p.get("YearPeriod") or p.get("Year")
            term = str(p.get("TermCode") or p.get("Term") or "")
            q = re.search(r"([1-4])", term)
            labels.append(f"{y}-Q{q.group(1)}" if (period != "year" and q) else str(y))
        rows = []
        groups = body.values() if isinstance(body, dict) else [body]
        for group in groups:
            for item in group or []:
                if not isinstance(item, dict) or not item.get("Name"):
                    continue
                row = {"item": str(item.get("Name")).strip(), "item_en": item.get("NameEn"),
                       "item_id": item.get("ReportNormID") or item.get("ID")}
                for i, lab in enumerate(labels, start=1):
                    row[lab] = item.get(f"Value{i}")
                rows.append(row)
        return pd.DataFrame(rows)

    def health_check(self) -> Dict[str, Any]:
        res = super().health_check()
        res["last_error"] = self._last_error
        res["note"] = "Nguồn dự phòng thử nghiệm (cào web)"
        return res


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: data/providers/vnstock_client.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Vnstock provider – bao bọc thư viện vnstock (ưu tiên API v4, tương thích ngược v3).

API v4 (vnstock >= 4.0, kiểm tra theo mã nguồn 4.0.9):
  Quote(source, symbol).history(start, end, interval)          source: vci | kbs | msn
  Finance(source, symbol, period).income_statement(period=...)  source: vci | kbs
  Company(source, symbol).info() / overview() / news() / events() / shareholders() / officers()
  Listing(source).all_symbols() / symbols_by_industries()
  Trading(source).price_board(symbols_list=[...])

BCTC từ VCI trả về dạng ma trận: cột item / item_en / item_id + mỗi cột là 1 kỳ
("2025", "2025-Q4", có thể trùng dạng "2025-Q4_1"), kỳ mới nhất đứng trước.
KBS trả cùng dạng, item_id đã chuẩn hóa (revenue, net_profit, total_assets…),
giá trị đã quy về VND, nhưng mặc định chỉ 4 kỳ gần nhất.
"""


import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd



logger = logging.getLogger(__name__)

_INDEX_ALIAS_vnstock_client = {"HNX": "HNXINDEX", "HNX-INDEX": "HNXINDEX", "UPCOM": "UPCOMINDEX",
                "UPCOM-INDEX": "UPCOMINDEX", "UPINDEX": "UPCOMINDEX", "VN-INDEX": "VNINDEX", "VNI": "VNINDEX"}
_STATEMENTS_vnstock_client = ("income_statement", "balance_sheet", "cash_flow", "ratio")


NETWORK_COOLDOWN = 600      # giây tạm bỏ qua một nguồn sau lỗi mạng
CALL_TIMEOUT = int(os.getenv("VNSTOCK_CALL_TIMEOUT", "10"))   # giây tối đa chờ MỘT lệnh gọi vnstock
_POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix="vnstock")
_POOL_SLOTS = threading.BoundedSemaphore(value=32)  # 16 chạy + tối đa 16 chờ; tránh queue tăng vô hạn
SLOW_CALL_SEC = 8
_COOLDOWN: Dict[str, float] = {}
_NET_MARKERS = ("timed out", "timeout", "connectionpool", "connection aborted", "connection reset", "max retries",
                "proxyerror", "name resolution", "failed to establish", "remote end closed", "ssl")


def _is_network_error(exc: Exception) -> bool:
    txt = f"{type(exc).__name__} {exc}".lower()
    return any(m in txt for m in _NET_MARKERS)


def _trip(src: str, why: str) -> None:
    already = _COOLDOWN.get(src, 0) > time.time()
    _COOLDOWN[src] = time.time() + NETWORK_COOLDOWN
    if already:
        return
    logger.warning("vnstock %s lỗi mạng – tạm bỏ qua nguồn này %d phút (%s)", src.upper(), NETWORK_COOLDOWN // 60, why[:160])


def source_cooldowns() -> Dict[str, float]:
    """Các nguồn vnstock đang tạm bỏ qua → thời điểm hết hạn (epoch)."""
    now = time.time()
    return {k: v for k, v in _COOLDOWN.items() if v > now}


def _norm_source(source: str) -> str:
    s = (source or "vci").lower().replace("vnstock_", "")
    return s if s in ("vci", "kbs", "msn") else "vci"



def _ev_col(df: pd.DataFrame, *names: str):
    cols = {str(c).lower(): c for c in df.columns}
    return next((cols[n] for n in names if n in cols), None)


def parse_cash_dividend_events(df: Any) -> pd.DataFrame:
    """Bảng sự kiện vnstock (VCI: event_code, category, exright_date, value_per_share…) → cổ tức TIỀN MẶT đã công bố
    (date = ngày GDKHQ, dps VND/cp). Dùng khi vnstock không có hàm dividends()."""
    empty = pd.DataFrame(columns=["date", "dps", "year"])
    if not isinstance(df, pd.DataFrame) or df.empty:
        return empty
    vps, dt = _ev_col(df, "value_per_share", "cash_value"), _ev_col(df, "exright_date", "ex_date", "record_date")
    if vps is None or dt is None:
        return empty
    d = df.copy()
    v = pd.to_numeric(d[vps], errors="coerce")
    is_cash = v > 0                     # value_per_share chỉ có ở sự kiện trả cổ tức tiền mặt
    out = pd.DataFrame({"date": pd.to_datetime(d.loc[is_cash, dt], errors="coerce"), "dps": v[is_cash]})
    out["year"] = np.nan
    out = out.dropna(subset=["date", "dps"])
    out = out[(out["dps"] > 0) & (out["dps"] < 50_000)].sort_values("date").reset_index(drop=True)
    return out


_CASH_KW = ("tiền mặt", "bằng tiền", "cash")
_BONUS_KW = ("thưởng", "bonus", "bằng cổ phiếu", "bằng cp", "stock dividend", "share dividend")
_PAID_KW = ("cbcnv", "esop", "người lao động", "riêng lẻ", "private", "quyền mua", "rights", "chào bán", "chuyển đổi",
            "convert", "hoán đổi", "swap")


def classify_share_event(code: Any, title: Any) -> Optional[str]:
    """'bonus' = tăng CP KHÔNG thu tiền (thưởng / cổ tức bằng CP – giá được điều chỉnh tương ứng);
    'paid' = phát hành có thu tiền / hoán đổi (ESOP, riêng lẻ, quyền mua…); None = sự kiện khác (cổ tức TIỀN MẶT – cột
    exercise_ratio của nó là % mệnh giá, KHÔNG phải tỷ lệ CP; niêm yết bổ sung; giao dịch nội bộ…)."""
    c, t = str(code or "").upper(), str(title or "").lower()
    if any(k in t for k in _CASH_KW) and not any(k in t for k in ("bằng cổ phiếu", "bằng cp")):
        return None
    if any(k in t for k in _PAID_KW):
        return "paid"
    if any(k in t for k in _BONUS_KW):
        return "bonus"
    return None


def _share_events(df: Any, kind: str) -> List[Dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    ratio, dt = _ev_col(df, "exercise_ratio", "ratio"), _ev_col(df, "exright_date", "ex_date")
    if ratio is None or dt is None:
        return []
    code = _ev_col(df, "event_code")
    title = _ev_col(df, "event_title_vi", "event_name_vi", "event_title_en")
    title_en = _ev_col(df, "event_title_en")
    lst = _ev_col(df, "listing_date")
    out = []
    for _, r in df.iterrows():
        x = pd.to_numeric(r.get(ratio), errors="coerce")
        d = pd.to_datetime(r.get(dt), errors="coerce")
        if pd.isna(x) or pd.isna(d) or not (0 < float(x) <= 3):
            continue
        t = f"{r.get(title) or ''} {r.get(title_en) or '' if title_en is not None else ''}"
        if classify_share_event(r.get(code) if code is not None else None, t) != kind:
            continue
        listed = pd.to_datetime(r.get(lst), errors="coerce") if lst is not None else pd.NaT
        out.append({"date": d.normalize(), "ratio": float(x), "listed": None if pd.isna(listed) else listed.normalize(),
                    "title": str(r.get(title) or "")})
    return sorted(out, key=lambda e: e["date"])


def parse_share_events(df: Any) -> List[Dict[str, Any]]:
    """Sự kiện làm TĂNG số CP KHÔNG thu tiền: cổ phiếu thưởng / cổ tức bằng cổ phiếu (tỷ lệ exercise_ratio, ngày GDKHQ).
    listed = ngày niêm yết bổ sung (None nếu chưa niêm yết).
    Sửa 15/10/2026: trước đây nhận nhầm cổ tức TIỀN MẶT (exercise_ratio = % mệnh giá, vd 0,1 = 1.000đ) và phát hành
    ESOP ("Phát hành cho CBCNV") là chia CP."""
    return _share_events(df, "bonus")


def parse_paid_share_events(df: Any) -> List[Dict[str, Any]]:
    """Phát hành CÓ thu tiền / hoán đổi (ESOP, riêng lẻ, quyền mua…) – số CP tăng nhưng giá KHÔNG điều chỉnh theo."""
    return _share_events(df, "paid")


def events_cover(df: Any, date) -> bool:
    """Bảng sự kiện có phủ tới ngày `date` không (nguồn chỉ trả ~50 sự kiện gần nhất → mã nhiều sự kiện bị cắt lịch sử)."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False
    cols = [c for c in df.columns if "date" in str(c).lower()]
    if not cols:
        return False
    oldest = pd.concat([pd.to_datetime(df[c], errors="coerce") for c in cols]).min()
    return pd.notna(oldest) and oldest.tz_localize(None) <= pd.Timestamp(date) if getattr(oldest, "tzinfo", None) else \
        (pd.notna(oldest) and oldest <= pd.Timestamp(date))


def parse_dividends(df: Any) -> pd.DataFrame:
    """Bảng cổ tức của vnstock (tên cột khác nhau giữa các nguồn) → date, dps (VND/cp tiền mặt), year."""
    empty = pd.DataFrame(columns=["date", "dps", "year"])
    if not isinstance(df, pd.DataFrame) or df.empty:
        return empty
    cols = {str(c).lower(): c for c in df.columns}
    date_c = next((cols[c] for c in cols if any(k in c for k in ("exercise_date", "ex_date", "exright", "record_date",
                                                                 "date", "ngay"))), None)
    pct_c = next((cols[c] for c in cols if "cash" in c and ("percent" in c or "rate" in c or "ratio" in c)), None) or \
        next((cols[c] for c in cols if any(k in c for k in ("percentage", "dividend_rate", "ty_le", "rate"))), None)
    val_c = next((cols[c] for c in cols if any(k in c for k in ("cash_dividend_value", "value_per_share", "dps",
                                                                "dividend_value", "amount"))), None)
    meth_c = next((cols[c] for c in cols if any(k in c for k in ("issue_method", "method", "type", "hinh_thuc"))), None)
    year_c = next((cols[c] for c in cols if "year" in c or c == "nam"), None)
    if date_c is None or (pct_c is None and val_c is None):
        return empty
    d = df.copy()
    if meth_c is not None:
        m = d[meth_c].astype(str).str.lower()
        d = d[m.str.contains("cash|tiền|tien", regex=True) | m.isin(["", "nan", "none"])]
    if val_c is not None:
        dps = pd.to_numeric(d[val_c], errors="coerce")
    else:
        pct = pd.to_numeric(d[pct_c], errors="coerce")
        dps = pct.where(pct > 1, pct * 100) * 100            # 0.2 → 20% → 2.000đ ; 20 → 20% → 2.000đ (mệnh giá 10.000đ)
    out = pd.DataFrame({"date": pd.to_datetime(d[date_c], errors="coerce", dayfirst=True), "dps": dps,
                        "year": pd.to_numeric(d[year_c], errors="coerce") if year_c is not None else np.nan})
    out = out.dropna(subset=["date", "dps"])
    out = out[(out["dps"] > 0) & (out["dps"] < 50_000)].sort_values("date").reset_index(drop=True)
    return out

class VnstockClient(BaseProvider):
    """Data provider dùng thư viện vnstock."""

    def __init__(self, source: str = "VCI"):
        self._source = _norm_source(source)
        self._available: Optional[bool] = None
        self._error_message: str = ""
        self._version = "unknown"
        self._major = 0
        try:
            import vnstock
            self._version = getattr(vnstock, "__version__", "unknown")
            try:
                self._major = int(str(self._version).split(".")[0])
            except ValueError:
                self._major = 4
            self._available = True
        except ImportError as exc:
            self._available = False
            self._error_message = (f"vnstock chưa được cài: {exc}. Cài bằng: pip install -U vnstock "
                                   "--extra-index-url https://vnstocks.com/api/simple")

    @property
    def name(self) -> str:
        return "vnstock"

    @property
    def is_available(self) -> bool:
        return bool(self._available)

    # ─────────────────── Helpers ─────────────────────────────────────────────

    def _try(self, label: str, *fns: Callable[[], Any]) -> Any:
        """
        Chạy lần lượt các cách gọi (v4 rồi v3) cho tới khi có kết quả.
        CẦU DAO NGẮT: máy chủ nguồn (vd iq.vietcap.com.vn của VCI) quá tải/không phản hồi thì mỗi lệnh gọi chờ 30 giây và
        vnstock còn tự thử lại → trang treo nhiều phút. Khi gặp lỗi mạng/quá thời gian, nguồn đó bị tạm bỏ qua
        NETWORK_COOLDOWN giây (các nguồn khác trong chuỗi dự phòng vẫn chạy), không gọi tiếp cách v3 vì cùng máy chủ.
        """
        if not self.is_available:
            return None
        src = label.split("[", 1)[1].rstrip("]") if "[" in label else self._source
        until = _COOLDOWN.get(src, 0.0)
        if until > time.time():
            self._error_message = f"{label}: nguồn {src.upper()} tạm bỏ qua đến {time.strftime('%H:%M:%S', time.localtime(until))} (lỗi mạng trước đó)"
            return None
        for fn in fns:
            t0 = time.time()
            try:
                if not _POOL_SLOTS.acquire(timeout=0.25):
                    self._error_message = f"{label}: hàng đợi nguồn dữ liệu đang đầy"
                    _trip(src, self._error_message)
                    break
                try:
                    fut = _POOL.submit(fn)
                except Exception:
                    _POOL_SLOTS.release()
                    raise
                fut.add_done_callback(lambda _f: _POOL_SLOTS.release())
                try:
                    res = fut.result(timeout=CALL_TIMEOUT)
                except FutureTimeout:
                    # vnstock tự chờ 30 giây/lần và tự thử lại → không đợi nó; luồng nền tự kết thúc sau
                    _trip(src, f"{label}: không phản hồi sau {CALL_TIMEOUT} giây")
                    self._error_message = f"{label}: không phản hồi sau {CALL_TIMEOUT} giây"
                    fut.cancel()  # hủy nếu task chưa bắt đầu; task đang chạy sẽ tự nhả slot khi kết thúc
                    break
                if res is None or (isinstance(res, pd.DataFrame) and res.empty):
                    if time.time() - t0 > SLOW_CALL_SEC:          # trả rỗng sau khi chờ rất lâu = máy chủ không phản hồi
                        _trip(src, f"{label}: phản hồi quá chậm")
                        break
                    continue
                return res
            except Exception as exc:
                self._error_message = f"{label}: {exc}"
                logger.debug("vnstock %s failed: %s", label, exc)
                if _is_network_error(exc) or time.time() - t0 > SLOW_CALL_SEC:
                    _trip(src, f"{label}: {exc}")
                    break
        return None

    # ─────────────────── Price ───────────────────────────────────────────────

    def get_price_history(self, symbol: str, start_date: str, end_date: str,
                          interval: str = "1D", source: Optional[str] = None) -> pd.DataFrame:
        sym = _INDEX_ALIAS_vnstock_client.get(self.validate_symbol(symbol), self.validate_symbol(symbol))
        src = _norm_source(source or self._source)

        def v4():
            from vnstock.api.quote import Quote
            return Quote(source=src, symbol=sym).history(start=start_date, end=end_date, interval=interval)

        def v3():
            from vnstock import Vnstock
            return Vnstock().stock(symbol=sym, source=src.upper()).quote.history(
                start=start_date, end=end_date, interval=interval)

        df = self._try(f"history[{src}]", v4, v3)
        if df is None:
            return pd.DataFrame()
        df = df.reset_index(drop="time" not in getattr(df.index, "names", []) and df.index.name not in ("time", "date"))
        df = df.rename(columns={"time": "timestamp", "date": "timestamp", "Date": "timestamp"})
        df = df.loc[:, ~df.columns.duplicated()]
        if "timestamp" not in df.columns:
            return pd.DataFrame()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        for c in ["open", "high", "low", "close", "volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["symbol"] = sym
        df["source"] = f"vnstock_{src}"
        return df.dropna(subset=["close"]).reset_index(drop=True)

    def get_index_history(self, index_code: str = "VNINDEX", start_date: str = "",
                          end_date: str = "", interval: str = "1D") -> pd.DataFrame:
        start_date = start_date or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        end_date = end_date or datetime.now().strftime("%Y-%m-%d")
        return self.get_price_history(index_code, start_date, end_date, interval)

    def get_current_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        end = datetime.now()
        df = self.get_price_history(symbol, (end - timedelta(days=10)).strftime("%Y-%m-%d"),
                                    end.strftime("%Y-%m-%d"))
        if df.empty:
            return None
        last = df.iloc[-1]
        prev = float(df["close"].iloc[-2]) if len(df) > 1 else None
        price = float(last["close"])
        return {
            "symbol": symbol.upper(), "price": price, "reference_price": prev,
            "change": price - prev if prev else None,
            "change_pct": (price / prev - 1) * 100 if prev else None,
            "volume": float(last.get("volume") or 0), "timestamp": str(last["timestamp"]),
            "source": df["source"].iloc[-1],
        }

    def get_price_board(self, symbols: List[str], source: Optional[str] = None) -> pd.DataFrame:
        src = _norm_source(source or self._source)
        if src == "msn":
            src = "vci"

        def v4():
            from vnstock.api.trading import Trading
            return Trading(source=src).price_board(symbols_list=list(symbols))

        def v3():
            from vnstock import Vnstock
            return Vnstock().stock(symbol=symbols[0], source=src.upper()).trading.price_board(list(symbols))

        df = self._try(f"price_board[{src}]", v4, v3)
        if df is None:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ["_".join(str(x) for x in c if str(x)) for c in df.columns]
        return df

    # ─────────────────── Financial statements ────────────────────────────────

    def get_financial_statement(self, symbol: str, statement: str, period: str = "year",
                                source: Optional[str] = None) -> pd.DataFrame:
        """
        statement: income_statement | balance_sheet | cash_flow | ratio
        period   : year | quarter
        Trả về bảng thô của nguồn (dạng ma trận item × kỳ); DataRepository chuẩn hóa sau.
        """
        if statement not in _STATEMENTS_vnstock_client:
            raise ValueError(statement)
        sym = self.validate_symbol(symbol)
        src = _norm_source(source or self._source)
        if src == "msn":
            return pd.DataFrame()
        period = "year" if period in ("year", "annual", "Y") else "quarter"

        def v4():
            from vnstock.api.financial import Finance
            fin = Finance(source=src, symbol=sym, period=period)
            fn = getattr(fin, statement)
            if src == "vci":
                return fn(period=period, lang="vi", dropna=True)
            try:
                return fn(period=period, display_mode=None)   # KBS: giữ item, item_en, item_id
            except TypeError:                                 # phiên bản không có display_mode
                return fn(period=period)

        def v3():
            from vnstock import Vnstock
            fin = Vnstock().stock(symbol=sym, source=src.upper()).finance
            fn = getattr(fin, statement)
            try:
                return fn(period=period, lang="vi")
            except TypeError:                     # KBS (vnstock mới) không nhận tham số lang
                return fn(period=period)

        df = self._try(f"{statement}[{src}]", v4, v3)
        if df is None:
            return pd.DataFrame()
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [" ".join(str(x) for x in c if str(x) and not str(x).startswith("Unnamed")).strip()
                          for c in df.columns]
        df.attrs["source"] = f"vnstock_{src}"
        df.attrs["period"] = period
        return df

    # Giữ tên hàm cũ để tương thích code cũ
    def get_income_statement(self, symbol: str, period: str = "quarter", lang: str = "vi") -> pd.DataFrame:
        return self.get_financial_statement(symbol, "income_statement", period)

    def get_balance_sheet(self, symbol: str, period: str = "quarter", lang: str = "vi") -> pd.DataFrame:
        return self.get_financial_statement(symbol, "balance_sheet", period)

    def get_cash_flow(self, symbol: str, period: str = "quarter", lang: str = "vi") -> pd.DataFrame:
        return self.get_financial_statement(symbol, "cash_flow", period)

    def get_financial_ratios(self, symbol: str, period: str = "quarter") -> pd.DataFrame:
        return self.get_financial_statement(symbol, "ratio", period)

    # ─────────────────── Company ─────────────────────────────────────────────

    def _company(self, symbol: str, method: str, source: Optional[str] = None, **kwargs) -> Any:
        sym = self.validate_symbol(symbol)
        src = _norm_source(source or self._source)
        if src == "msn":
            src = "vci"

        def v4():
            from vnstock.api.company import Company
            return getattr(Company(source=src, symbol=sym), method)(**kwargs)

        def v3():
            from vnstock import Vnstock
            comp = Vnstock().stock(symbol=sym, source=src.upper()).company
            return getattr(comp, {"info": "profile"}.get(method, method))(**kwargs)

        return self._try(f"company.{method}[{src}]", v4, v3)

    def get_company_info(self, symbol: str) -> Dict[str, Any]:
        """Hồ sơ doanh nghiệp, chuẩn hóa về các khóa: company_name, short_name, exchange, industry, ..."""
        out: Dict[str, Any] = {}
        for method in ("info", "overview"):
            df = self._company(symbol, method)
            if isinstance(df, pd.DataFrame) and not df.empty:
                row = df.iloc[0].to_dict()
                out.update({k: v for k, v in row.items() if v is not None and not (isinstance(v, float) and pd.isna(v))})
        if not out:
            return {}
        pick = lambda *keys: next((out[k] for k in keys if out.get(k) not in (None, "")), None)  # noqa: E731
        out["company_name"] = pick("company_name", "name", "organ_name", "vi_organ_name", "short_name")
        out["short_name"] = pick("short_name", "organ_short_name")
        out["industry"] = pick("industry", "icb_name3", "icb_name2", "sector", "industry_name")
        out["exchange"] = pick("exchange", "com_group_code", "floor")
        out["description"] = pick("profile", "company_profile", "description", "history")
        out["website"] = pick("website", "web_address", "url")
        out["issue_share"] = pick("issue_share", "issued_share", "outstanding_share", "financial_ratio_issue_share")
        out["symbol"] = symbol.upper()
        return out

    def get_dividends(self, symbol: str) -> pd.DataFrame:
        """Lịch sử chia cổ tức ĐÃ CÔNG BỐ (vnstock Company.dividends, thử VCI → TCBS → KBS).
        Chuẩn hóa về các cột: date (ngày GDKHQ/thực hiện), dps (VND/cp, chỉ cổ tức TIỀN MẶT), year (năm cổ tức nếu có).
        Tỷ lệ % được quy đổi theo mệnh giá 10.000đ. Không có dữ liệu → DataFrame rỗng (không đoán)."""
        for src in ("vci", "tcbs", "kbs"):
            df = self._company(symbol, "dividends", source=src)
            out = parse_dividends(df)
            if not out.empty:
                out.attrs["source"] = f"vnstock_{src}"
                return out
        return pd.DataFrame(columns=["date", "dps", "year"])

    def get_company_overview(self, symbol: str) -> Dict[str, Any]:
        return self.get_company_info(symbol)

    def get_company_news(self, symbol: str) -> List[Dict[str, Any]]:
        """Tin doanh nghiệp từ vnstock (VCI, dự phòng KBS), chuẩn hóa về title/url/published_at/source."""
        items: List[Dict[str, Any]] = []
        for src in ("vci", "kbs"):
            df = self._company(symbol, "news", source=src)
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            for _, r in df.iterrows():
                title = r.get("news_title") or r.get("title") or r.get("news_short_content")
                if not title:
                    continue
                pub = r.get("public_date") or r.get("published_date") or r.get("created_at")
                try:
                    pub = pd.to_datetime(pub, unit="ms") if isinstance(pub, (int, float)) else pd.to_datetime(pub)
                except Exception:
                    pub = None
                items.append({
                    "title": str(title).strip(),
                    "url": r.get("news_source_link") or r.get("url") or "",
                    "published_at": pub,
                    "summary": r.get("news_short_content") or r.get("news_sub_title") or "",
                    "source": r.get("news_source") or f"vnstock_{src}",
                })
            if items:
                break
        return items

    def get_company_events(self, symbol: str) -> pd.DataFrame:
        df = self._company(symbol, "events")
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

    def get_shareholders(self, symbol: str) -> pd.DataFrame:
        df = self._company(symbol, "shareholders")
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

    def get_officers(self, symbol: str) -> pd.DataFrame:
        df = self._company(symbol, "officers")
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

    # ─────────────────── Listing ─────────────────────────────────────────────

    def get_all_symbols(self) -> pd.DataFrame:
        src = self._source if self._source in ("vci", "kbs") else "vci"

        def v4():
            from vnstock.api.listing import Listing
            df = Listing(source=src).symbols_by_exchange()
            if df is not None and "type" in df.columns:
                df = df[df["type"].astype(str).str.upper() == "STOCK"]
            return df

        def v4b():
            from vnstock.api.listing import Listing
            return Listing(source=src).all_symbols()

        df = self._try("listing", v4, v4b)
        if df is None:
            import json
            from pathlib import Path
            local = Path(__file__).resolve().parent.parent / "data" / "listed_stocks.json"
            if local.exists():
                return pd.DataFrame(json.loads(local.read_text(encoding="utf-8")))
            return pd.DataFrame()
        return df.reset_index(drop=True)

    def get_symbols_by_industries(self) -> pd.DataFrame:
        def v4():
            from vnstock.api.listing import Listing
            return Listing(source="vci").symbols_by_industries()
        df = self._try("symbols_by_industries", v4)
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

    def get_symbols_by_exchange(self, exchange: str = "HOSE") -> pd.DataFrame:
        df = self.get_all_symbols()
        if df.empty or "exchange" not in df.columns:
            return pd.DataFrame()
        target = exchange.upper()
        ex = df["exchange"].astype(str).str.upper()
        return df[ex.isin(["HOSE", "HSX"])] if target in ("HOSE", "HSX") else df[ex == target]

    def get_market_overview(self) -> pd.DataFrame:
        syms = self.get_all_symbols()
        if syms.empty or "symbol" not in syms.columns:
            return pd.DataFrame()
        return self.get_price_board(syms["symbol"].astype(str).tolist()[:400])

    def health_check(self) -> Dict[str, Any]:
        res = super().health_check()
        res.update({"version": self._version, "source": self._source})
        if self._error_message:
            res["last_error"] = self._error_message
        return res


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: services/dnse_realtime.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Giá REALTIME qua DNSE OpenAPI (WebSocket) – chỉ ĐỌC giá, không đặt lệnh.

Giao thức theo SDK chính thức của DNSE (github.com/dnse-tech/openapi-sdk, python/dnse/websocket):
  1. Kết nối  {DNSE_WS_URL}/v1/stream?encoding=json   → máy chủ gửi lời chào {"session_id": ...}
  2. Xác thực {"action":"auth","api_key":K,"signature":HMAC_SHA256(secret, "K:timestamp:nonce"),"timestamp":ts,"nonce":n}
     → {"action":"auth_success"} hoặc {"action":"auth_error","message":...}
  3. Đăng ký  {"action":"subscribe","channels":[{"name":"tick.G1.json","symbols":["FPT",...]}]}
              {"action":"subscribe","channels":[{"name":"market_index.VNINDEX.json","symbols":[]}]}
  4. Tin nhắn T="t"  (khớp lệnh): symbol, matchPrice (nghìn đồng), matchQtty, openPrice, highestPrice, lowestPrice,
                                  totalVolumeTraded, time
              T="mi" (chỉ số):   indexName, valueIndexes, highestValueIndexes, lowestValueIndexes, priorValueIndexes,
                                  totalVolumeTraded, transactTime
     Giữ kết nối: gửi {"action":"ping"} mỗi 25 giây; máy chủ gửi "ping" → trả {"action":"pong"}.

Thiết kế:
- Một luồng nền (daemon) giữ 1 kết nối cho cả ứng dụng, lưu giá mới nhất của từng mã trong bộ nhớ.
- Trang nào cần mã nào thì gọi want(code) → luồng nền tự đăng ký thêm; snapshot(code) trả nến phiên hôm nay.
- Mất kết nối → tự kết nối lại (chờ 1, 2, 4… tối đa 60 giây). Sai key/secret → dừng hẳn, không gọi lặp lại.
- Không có key/secret, tắt DNSE_REALTIME, chưa nhận được giá, hoặc lỗi → snapshot() trả None và app quay về cách cũ
  (API biểu đồ công khai ~3 phút/lần). Không bao giờ bịa số; secret không bao giờ được ghi ra log.
"""


import asyncio
import hashlib
import hmac
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

VN_TZ = timezone(timedelta(hours=7))
BOARD = "G1"                                   # bảng lô chẵn – giá khớp chính thức
INDEX_CODES = {"VNINDEX", "VN30", "HNX", "HNX30", "UPCOM", "VN100", "VNXALLSHARE"}
_INDEX_ALIAS_dnse_realtime = {"HNXINDEX": "HNX", "UPCOMINDEX": "UPCOM", "VN-INDEX": "VNINDEX", "VNI": "VNINDEX", "VNXALL": "VNXALLSHARE"}
MAX_SYMBOLS = 150                              # giới hạn số mã đăng ký cùng lúc
HEARTBEAT_SEC = 25.0
TIMEOUT_SEC = 15.0


def canonical(code: str) -> str:
    c = str(code or "").upper().strip()
    return _INDEX_ALIAS_dnse_realtime.get(c, c)


def is_index_dnse_realtime(code: str) -> bool:
    return canonical(code) in INDEX_CODES


def sign(api_key: str, api_secret: str, timestamp: int, nonce: str) -> str:
    return hmac.new(api_secret.encode("utf-8"), f"{api_key}:{timestamp}:{nonce}".encode("utf-8"),
                    hashlib.sha256).hexdigest()


def auth_message(api_key: str, api_secret: str, now: Optional[float] = None) -> Dict[str, Any]:
    now = time.time() if now is None else now
    ts, nonce = int(now), str(int(now * 1_000_000))
    return {"action": "auth", "api_key": api_key, "signature": sign(api_key, api_secret, ts, nonce),
            "timestamp": ts, "nonce": nonce}


def _parse_time(v: Any) -> Optional[datetime]:
    """Giờ của tin nhắn → datetime giờ Việt Nam. Hỗ trợ ISO, {Seconds,Nanos}, unix giây/mili giây."""
    try:
        if v is None or v == "":
            return None
        if isinstance(v, dict):
            sec = float(v.get("Seconds", v.get("seconds", 0))) + float(v.get("Nanos", v.get("nanos", 0))) / 1e9
            return datetime.fromtimestamp(sec, VN_TZ) if sec > 0 else None
        if isinstance(v, (int, float)):
            sec = float(v) / (1000.0 if v > 1e12 else 1.0)
            return datetime.fromtimestamp(sec, VN_TZ)
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return dt.astimezone(VN_TZ) if dt.tzinfo else dt.replace(tzinfo=VN_TZ)
    except Exception:
        return None


def decode(raw: Any) -> Optional[Dict[str, Any]]:
    """Giải mã 1 khung tin: chuỗi/bytes JSON, hoặc bytes msgpack (DNSE có thể gửi kênh giá khớp dạng tick.G1.msgpack
    dù đã đăng ký .json). Không giải mã được → None (bỏ qua khung đó)."""
    if isinstance(raw, (bytes, bytearray)):
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            pass
        try:
            import msgpack
            out = msgpack.unpackb(bytes(raw), raw=False)
        except Exception:
            return None
    else:
        try:
            out = json.loads(raw)
        except (TypeError, ValueError):
            return None
    return out if isinstance(out, dict) else None


def _num(v: Any) -> Optional[float]:
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


class RealtimeFeed:
    """Kết nối WebSocket DNSE OpenAPI chạy nền; an toàn khi gọi từ nhiều luồng Streamlit."""

    def __init__(self, api_key: str, api_secret: str, ws_url: str = "wss://ws-openapi.dnse.com.vn",
                 connect: Optional[Callable[..., Any]] = None, clock: Callable[[], float] = time.time):
        self._key, self._secret = api_key, api_secret
        self.url = f"{ws_url.rstrip('/')}/v1/stream?encoding=json"
        self._connect = connect
        self._clock = clock
        self._lock = threading.Lock()
        self._wanted: set = set()
        self._sent: set = set()
        self._data: Dict[str, Dict[str, Any]] = {}
        self.state = "off"               # off | connecting | live | auth_failed | error | stopped
        self.message = ""
        self.connected_at: Optional[float] = None
        self.last_message_at: Optional[float] = None
        self.n_messages = 0
        self.n_undecoded = 0
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws: Any = None
        self._stop = False

    # ── API cho phần còn lại của app ──
    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            if self.state == "auth_failed":
                return
            self._stop = False
            self.state = "connecting"
            self._thread = threading.Thread(target=self._run, name="dnse-realtime", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop = True
        self.state = "stopped"
        loop, ws = self._loop, self._ws
        if loop and ws and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(ws.close(), loop)
            except Exception:
                pass

    def want(self, *codes: str) -> None:
        new = False
        with self._lock:
            for c in codes:
                c = canonical(c)
                if c and c not in self._wanted and len(self._wanted) < MAX_SYMBOLS:
                    self._wanted.add(c)
                    new = True
        if new and self.state == "live" and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._flush(), self._loop)

    def active(self) -> bool:
        """Đang (hoặc sắp) nhận giá realtime – dùng để chọn nhịp làm mới trang."""
        return self.state in ("connecting", "live")

    def snapshot(self, code: str) -> Optional[Dict[str, Any]]:
        """Nến phiên HÔM NAY từ giá realtime (VND), hoặc None nếu chưa có / không còn kết nối."""
        code = canonical(code)
        self.want(code)
        if self.state != "live":
            return None
        with self._lock:
            d = dict(self._data.get(code) or {})
        if not d or d.get("close") is None:
            return None
        today = datetime.fromtimestamp(self._clock(), VN_TZ).date()
        if d["dt"].date() != today:
            return None
        return {"timestamp": pd.Timestamp(today), "open": d.get("open"), "high": d.get("high"), "low": d.get("low"),
                "close": d["close"], "volume": d.get("volume"), "reference": d.get("reference"),
                "session_time": d["dt"].strftime("%H:%M:%S"), "source": "dnse_realtime"}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            n_wanted, n_data = len(self._wanted), len(self._data)
        return {"state": self.state, "message": self.message, "connected_at": self.connected_at,
                "last_message_at": self.last_message_at, "messages": self.n_messages, "undecoded": self.n_undecoded,
                "symbols_wanted": n_wanted, "symbols_with_price": n_data}

    # ── Xử lý tin nhắn (tách riêng để kiểm thử) ──
    def handle(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cập nhật bộ nhớ giá từ 1 tin nhắn; trả về tin điều khiển cần gửi lại (vd pong) nếu có."""
        if not isinstance(msg, dict):
            return None
        action = msg.get("action") or msg.get("a")
        if action == "ping":
            return {"action": "pong"}
        if action == "error":
            self.message = str(msg.get("message") or msg.get("msg") or "lỗi từ máy chủ")[:200]
            logger.warning("DNSE realtime: máy chủ báo lỗi: %s", self.message)
            return None
        t = msg.get("T")
        now = self._clock()
        if t == "t":
            sym = canonical(msg.get("symbol") or msg.get("Symbol") or "")
            board = msg.get("boardId")
            price = _num(msg.get("matchPrice"))
            if not sym or price is None or price <= 0 or (board and board != BOARD):
                return None
            mult = 1000.0 if price < 1000 else 1.0          # DNSE trả giá cổ phiếu theo NGHÌN đồng
            dt = _parse_time(msg.get("time")) or datetime.fromtimestamp(now, VN_TZ)
            rec = {"close": price * mult, "dt": dt,
                   "open": (_num(msg.get("openPrice")) or 0) * mult or None,
                   "high": (_num(msg.get("highestPrice")) or 0) * mult or None,
                   "low": (_num(msg.get("lowestPrice")) or 0) * mult or None,
                   "volume": _num(msg.get("totalVolumeTraded"))}
        elif t == "mi":
            sym = canonical(msg.get("indexName") or "")
            val = _num(msg.get("valueIndexes"))
            if not sym or val is None or val <= 0:
                return None
            dt = _parse_time(msg.get("transactTime") or msg.get("time")) or datetime.fromtimestamp(now, VN_TZ)
            rec = {"close": val, "dt": dt, "open": None,
                   "high": _num(msg.get("highestValueIndexes")), "low": _num(msg.get("lowestValueIndexes")),
                   "reference": _num(msg.get("priorValueIndexes")), "volume": _num(msg.get("totalVolumeTraded"))}
        else:
            return None
        with self._lock:
            old = self._data.get(sym) or {}
            for k in ("open", "high", "low", "volume", "reference"):          # tin thiếu trường → giữ giá trị cũ
                if rec.get(k) is None and old.get(k) is not None and old.get("dt") and old["dt"].date() == dt.date():
                    rec[k] = old[k]
            if rec.get("high") is not None:
                rec["high"] = max(rec["high"], rec["close"])
            if rec.get("low") is not None:
                rec["low"] = min(rec["low"], rec["close"])
            self._data[sym] = rec
        self.last_message_at = now
        self.n_messages += 1
        return None

    def subscribe_messages(self, codes) -> list:
        stocks = sorted(c for c in codes if not is_index_dnse_realtime(c))
        out = []
        if stocks:
            out.append({"action": "subscribe", "channels": [{"name": f"tick.{BOARD}.json", "symbols": stocks}]})
        for c in sorted(c for c in codes if is_index_dnse_realtime(c)):
            out.append({"action": "subscribe", "channels": [{"name": f"market_index.{c}.json", "symbols": []}]})
        return out

    # ── Luồng nền ──
    def _run(self) -> None:
        try:
            asyncio.run(self._main())
        except Exception as exc:  # pragma: no cover - lỗi ngoài dự kiến
            self.state, self.message = "error", f"{type(exc).__name__}: {exc}"[:200]
            logger.warning("DNSE realtime dừng: %s", self.message)

    async def _flush(self) -> None:
        ws = self._ws
        if ws is None:
            return
        with self._lock:
            new = self._wanted - self._sent
            self._sent |= new
        for m in self.subscribe_messages(new):
            await ws.send(json.dumps(m))

    async def _heartbeat(self, ws) -> None:
        while not self._stop:
            await asyncio.sleep(HEARTBEAT_SEC)
            await ws.send(json.dumps({"action": "ping"}))

    async def _session(self, ws) -> bool:
        """Một phiên kết nối. Trả về False nếu không nên kết nối lại (sai key/secret)."""
        await asyncio.wait_for(ws.recv(), TIMEOUT_SEC)                       # lời chào {"session_id": ...}
        await ws.send(json.dumps(auth_message(self._key, self._secret)))
        resp = decode(await asyncio.wait_for(ws.recv(), TIMEOUT_SEC)) or {}
        action = resp.get("action") or resp.get("a")
        if action != "auth_success":
            self.state = "auth_failed"
            self.message = str(resp.get("message") or resp.get("msg") or action or "xác thực thất bại")[:200]
            logger.warning("DNSE realtime: xác thực thất bại (%s) – kiểm tra DNSE_API_KEY / DNSE_API_SECRET", self.message)
            return False
        self._ws = ws
        with self._lock:
            self._sent = set()
        self.state, self.message, self.connected_at = "live", "", self._clock()
        logger.info("DNSE realtime: đã kết nối và xác thực")
        await self._flush()
        hb = asyncio.create_task(self._heartbeat(ws))
        try:
            async for raw in ws:
                msg = decode(raw)
                if msg is None:
                    self.n_undecoded += 1
                    continue
                reply = self.handle(msg)
                if reply:
                    await ws.send(json.dumps(reply))
        finally:
            hb.cancel()
            self._ws = None
        return True

    async def _main(self) -> None:
        self._loop = asyncio.get_running_loop()
        connect = self._connect
        if connect is None:
            import websockets
            connect = websockets.connect
        delay = 1.0
        while not self._stop:
            self.state = "connecting"
            try:
                async with connect(self.url, open_timeout=TIMEOUT_SEC, ping_interval=None) as ws:
                    delay = 1.0
                    if not await self._session(ws):
                        return
            except asyncio.CancelledError:  # pragma: no cover
                return
            except Exception as exc:
                if self._stop:
                    return
                self.message = f"{type(exc).__name__}: {exc}"[:200]
                logger.info("DNSE realtime mất kết nối (%s) – thử lại sau %.0f giây", self.message, delay)
            if self._stop:
                return
            self.state = "error"
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)


# ── Một kết nối dùng chung cho cả ứng dụng ──
_feed: Optional[RealtimeFeed] = None
_feed_lock = threading.Lock()


def configured() -> bool:
    from core.cau_hinh import settings
    return bool(settings.DNSE_REALTIME and settings.DNSE_API_KEY and settings.DNSE_API_SECRET)


def get_feed(start: bool = True) -> Optional[RealtimeFeed]:
    """Kết nối realtime dùng chung (tự khởi động lần đầu). None nếu chưa cấu hình key/secret."""
    global _feed
    if not configured():
        return None
    from core.cau_hinh import settings
    with _feed_lock:
        if _feed is None:
            _feed = RealtimeFeed(settings.DNSE_API_KEY, settings.DNSE_API_SECRET, settings.DNSE_WS_URL)
    if start:
        _feed.start()
    return _feed


def snapshot(code: str) -> Optional[Dict[str, Any]]:
    f = get_feed()
    return f.snapshot(code) if f else None


def active() -> bool:
    f = get_feed()
    return bool(f and f.active())


def status() -> Dict[str, Any]:
    """Trạng thái cho trang Nguồn dữ liệu (không chứa key/secret)."""
    if not configured():
        from core.cau_hinh import settings
        reason = "đã tắt (DNSE_REALTIME=0)" if not settings.DNSE_REALTIME else "chưa nhập DNSE_API_KEY / DNSE_API_SECRET"
        return {"state": "off", "message": reason}
    return get_feed().status()
