"""
core/thi_truong_danh_muc.py – gộp từ 4 module (15/10/2026).

MỤC LỤC
  • services/market_service.py – MarketService – provides market-level overview and index data.
      hàm/lớp chính: MarketService, sector_map, universe_options, index_history, rsi, period_returns, index_card, universe_snapshot, breadth_stats, sector_performance, market_health, live_refresh_seconds …
  • services/screener_service.py – Bộ lọc cổ phiếu (screener) & so sánh nhiều mã.
      hàm/lớp chính: add_group_signals, build_profile, ScreenerService, compare
  • services/watchlist_service.py – Danh mục theo dõi (watchlist) & cảnh báo giá.
      hàm/lớp chính: check_condition, WatchlistService
  • services/portfolio_service.py – PortfolioService – manages user portfolio and performance tracking.
      hàm/lớp chính: PortfolioService
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: services/market_service.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
MarketService – provides market-level overview and index data.
"""


import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from core.pipeline import get_repo

logger = logging.getLogger(__name__)


INDEX_SYMBOLS = {
    "VNINDEX": "VN-Index",
    "VN30": "VN30",
    "HNX": "HNX-Index",
    "UPCOM": "UPCoM-Index",
}


class MarketService:
    """Market overview data and health scoring."""

    def get_index_snapshots(self) -> Dict[str, Any]:
        """Return current snapshot for main indices."""
        result = {}
        for code, name in INDEX_SYMBOLS.items():
            try:
                # Look back up to 14 days to handle holidays / weekends safely
                end = datetime.now().strftime("%Y-%m-%d")
                start = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")

                candidates = [code]
                if code == "HNX":
                    candidates = ["HNX", "HNXINDEX", "HNXIndex"]
                elif code == "UPCOM":
                    candidates = ["UPCOM", "UPCOMINDEX", "UpcomIndex"]

                df = pd.DataFrame()
                for sym in candidates:
                    try:
                        df = get_repo().get_price_history(sym, start_date=start, end_date=end)
                        if not df.empty:
                            break
                    except Exception:
                        continue

                if not df.empty:
                    last = df.iloc[-1]
                    prev = df.iloc[-2] if len(df) > 1 else last
                    close = float(last.get("close", 0))
                    prev_close = float(prev.get("close", close))
                    change = close - prev_close
                    change_pct = change / prev_close * 100 if prev_close else 0
                    result[code] = {
                        "name": name,
                        "close": close,
                        "change": round(change, 2),
                        "change_pct": round(change_pct, 2),
                        "volume": float(last.get("volume", 0)),
                        "date": str(last.get("timestamp", ""))[:10],
                        "available": True,
                    }
                else:
                    result[code] = {"name": name, "available": False}
            except Exception as exc:
                logger.warning("Index snapshot failed for %s: %s", code, exc)
                result[code] = {"name": name, "available": False, "error": str(exc)}
        return result

    def get_index_history(self, index_code: str = "VNINDEX", days: int = 365) -> pd.DataFrame:
        return get_repo().get_index_history(index_code, days=days)

    def get_market_breadth(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Compute market breadth from a board/listing DataFrame.

        Expected columns: symbol, change or change_pct
        """
        if df.empty:
            return {"available": False}

        change_col = None
        for c in ["change", "change_pct", "priceChange", "percentChange"]:
            if c in df.columns:
                change_col = c
                break

        if change_col is None:
            return {"available": False, "reason": "Không có cột thay đổi giá"}

        changes = pd.to_numeric(df[change_col], errors="coerce").dropna()
        advancing = int((changes > 0).sum())
        declining = int((changes < 0).sum())
        unchanged = int((changes == 0).sum())
        total = advancing + declining + unchanged
        ad_ratio = advancing / declining if declining > 0 else float("inf")

        return {
            "available": True,
            "advancing": advancing,
            "declining": declining,
            "unchanged": unchanged,
            "total": total,
            "ad_ratio": round(ad_ratio, 2),
        }

    def get_top_movers(self, df: pd.DataFrame, n: int = 10) -> Dict[str, pd.DataFrame]:
        """Return top gainers, losers, and highest volume."""
        result = {"gainers": pd.DataFrame(), "losers": pd.DataFrame(), "volume": pd.DataFrame()}
        if df.empty:
            return result

        change_col = next((c for c in ["change_pct", "percentChange", "change"] if c in df.columns), None)
        vol_col = next((c for c in ["volume", "totalVolume", "tradingVolume"] if c in df.columns), None)
        sym_col = next((c for c in ["symbol", "ticker", "code"] if c in df.columns), None)

        if change_col and sym_col:
            df2 = df.copy()
            df2[change_col] = pd.to_numeric(df2[change_col], errors="coerce")
            result["gainers"] = df2.nlargest(n, change_col)
            result["losers"] = df2.nsmallest(n, change_col)

        if vol_col and sym_col:
            df2 = df.copy()
            df2[vol_col] = pd.to_numeric(df2[vol_col], errors="coerce")
            result["volume"] = df2.nlargest(n, vol_col)

        return result

    def get_provider_status(self) -> Dict[str, Any]:
        return get_repo().get_provider_status()


# ═════════════════════════════════════════════════════════════════════════════
#  Bộ tính toán cho trang Tổng quan thị trường (chỉ dùng dữ liệu giá thật)
# ═════════════════════════════════════════════════════════════════════════════
import math
from concurrent.futures import ThreadPoolExecutor

import numpy as np

_INDEX_CANDIDATES = {
    "VNINDEX": ["VNINDEX"],
    "VN30": ["VN30"],
    "HNX": ["HNX", "HNXINDEX", "HNXIndex"],
    "UPCOM": ["UPCOM", "UPCOMINDEX", "UpcomIndex"],
}

# Ngành cho các mã VN30 không nằm trong rổ ngành của ticker_directory
_SECTOR_OVERRIDE = {"BVH": "🛡️ Bảo hiểm", "VJC": "✈️ Hàng không", "BCM": "🏢 Bất động sản"}


def sector_map() -> Dict[str, str]:
    """Mã → ngành, lấy từ các rổ ngành trong ticker_directory (bỏ rổ chỉ số)."""
    from core.du_lieu import BASKETS
    out: Dict[str, str] = {}
    for name, syms in BASKETS.items():
        if not syms or "⭐" in name or name.startswith("Tất cả"):
            continue
        for s in syms:
            out.setdefault(s, name)
    out.update(_SECTOR_OVERRIDE)
    return out


def universe_options() -> Dict[str, List[str]]:
    """Các rổ cổ phiếu dùng để đo độ rộng / heatmap."""
    from core.du_lieu import BASKETS
    opts: Dict[str, List[str]] = {}
    for name, syms in BASKETS.items():
        if syms:
            opts[name] = list(dict.fromkeys(syms))
    sector_all: List[str] = []
    for name, syms in BASKETS.items():
        if syms and "⭐" not in name:
            sector_all += syms
    opts = {"⭐ VN30 (Blue-chips HSX)": opts.pop("⭐ VN30 (Blue-chips HSX)"),
            "🌐 Rổ mở rộng (VN30 + các ngành)": list(dict.fromkeys(BASKETS["⭐ VN30 (Blue-chips HSX)"] + sector_all)),
            **opts}
    return opts


def index_history(code: str, days: int = 400) -> pd.DataFrame:
    """Lịch sử chỉ số, thử các mã thay thế (HNX/UPCOM có nhiều cách viết)."""
    for sym in _INDEX_CANDIDATES.get(code, [code]):
        try:
            df = get_repo().get_price_history(sym, days=days)
            if df is not None and not df.empty and "close" in df.columns:
                return df.sort_values("timestamp").reset_index(drop=True)
        except Exception as exc:  # pragma: no cover - nguồn lỗi
            logger.debug("index history %s failed: %s", sym, exc)
    return pd.DataFrame()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    out[(loss == 0) & (gain > 0)] = 100.0     # chỉ tăng, không phiên giảm
    out[(loss == 0) & (gain == 0)] = 50.0     # đi ngang tuyệt đối
    return out


def period_returns(df: pd.DataFrame) -> Dict[str, Optional[float]]:
    """Hiệu suất 1T, 1Th, 3Th, 6Th, YTD, 1N (%) tính theo giá đóng cửa."""
    out: Dict[str, Optional[float]] = {k: None for k in ("1T", "1Th", "3Th", "6Th", "YTD", "1N")}
    if df is None or df.empty or "close" not in df.columns:
        return out
    s = df.set_index(pd.to_datetime(df["timestamp"]))["close"].astype(float).dropna()
    if len(s) < 2:
        return out
    last_dt, last = s.index[-1], float(s.iloc[-1])

    def ret_since(dt):
        base = s[s.index <= dt]
        if base.empty:
            return None
        b = float(base.iloc[-1])
        return (last / b - 1) * 100 if b else None

    out["1T"] = ret_since(last_dt - pd.Timedelta(days=7))
    out["1Th"] = ret_since(last_dt - pd.Timedelta(days=30))
    out["3Th"] = ret_since(last_dt - pd.Timedelta(days=91))
    out["6Th"] = ret_since(last_dt - pd.Timedelta(days=182))
    out["YTD"] = ret_since(pd.Timestamp(year=last_dt.year, month=1, day=1) - pd.Timedelta(days=1))
    out["1N"] = ret_since(last_dt - pd.Timedelta(days=365)) if s.index[0] <= last_dt - pd.Timedelta(days=360) else None
    return out


def index_card(code: str, df: pd.DataFrame) -> Dict[str, Any]:
    """Số liệu cho thẻ chỉ số: điểm, thay đổi, KL, biên độ, sparkline 60 phiên."""
    name = INDEX_SYMBOLS.get(code, code)
    if df is None or df.empty or len(df) < 2:
        return {"code": code, "name": name, "available": False}
    last, prev = df.iloc[-1], df.iloc[-2]
    close, pclose = float(last["close"]), float(prev["close"])
    chg = close - pclose
    return {
        "code": code, "name": name, "available": True,
        "close": close, "change": chg, "change_pct": chg / pclose * 100 if pclose else 0.0,
        "high": float(last.get("high", close)), "low": float(last.get("low", close)),
        "volume": float(last.get("volume", 0) or 0),
        "date": pd.to_datetime(last["timestamp"]).strftime("%d/%m/%Y")
                + (f" · {last['session_time']}" if isinstance(last.get("session_time"), str) else ""),
        "live": isinstance(last.get("session_time"), str),
        "day": pd.to_datetime(last["timestamp"]).normalize(),
        "spark": df["close"].astype(float).tail(60).round(2).tolist(),
        "returns": period_returns(df),
    }


def _symbol_row(sym: str, sectors: Dict[str, str]) -> Optional[Dict[str, Any]]:
    try:
        df = get_repo().get_price_history(sym, days=120)
    except Exception:
        return None
    if df is None or df.empty or len(df) < 2 or "close" not in df.columns:
        return None
    df = df.sort_values("timestamp")
    c = df["close"].astype(float)
    v = df["volume"].astype(float) if "volume" in df.columns else pd.Series(0.0, index=df.index)
    close, prev = float(c.iloc[-1]), float(c.iloc[-2])
    if not prev:
        return None
    avg20 = float(v.iloc[-21:-1].mean()) if len(v) > 2 else float("nan")
    ma20 = float(c.tail(20).mean())
    hi20, lo20 = float(c.iloc[-21:-1].max()) if len(c) > 2 else close, float(c.iloc[-21:-1].min()) if len(c) > 2 else close

    def ret(n):
        return (close / float(c.iloc[-n - 1]) - 1) * 100 if len(c) > n and c.iloc[-n - 1] else None

    return {
        "symbol": sym, "sector": sectors.get(sym, "Khác"),
        "date": pd.to_datetime(df["timestamp"].iloc[-1]),
        "close": close, "prev_close": prev, "change": close - prev, "change_pct": (close / prev - 1) * 100,
        "volume": float(v.iloc[-1]), "value_bn": close * float(v.iloc[-1]) / 1e9,
        "vol_ratio": float(v.iloc[-1]) / avg20 if avg20 and not math.isnan(avg20) else None,
        "ret_5d": ret(5), "ret_20d": ret(20),
        "above_ma20": close > ma20, "new_high20": close > hi20, "new_low20": close < lo20,
        "spark": c.tail(30).round(2).tolist(),
    }


def universe_snapshot(symbols: List[str], workers: int = 8) -> pd.DataFrame:
    """Ảnh chụp phiên gần nhất cho một rổ mã (tải song song, có cache ở tầng repository)."""
    sectors = sector_map()
    syms = list(dict.fromkeys(s.upper() for s in symbols))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = [r for r in ex.map(lambda s: _symbol_row(s, sectors), syms) if r]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Chỉ giữ các mã có phiên cùng ngày với phiên mới nhất (tránh mã ngừng giao dịch làm sai độ rộng)
    latest = df["date"].max()
    df["stale"] = df["date"] < latest - pd.Timedelta(days=3)
    return df


def breadth_stats(snap: pd.DataFrame) -> Dict[str, Any]:
    if snap is None or snap.empty:
        return {"available": False}
    live = snap[~snap["stale"]] if "stale" in snap.columns else snap
    chg = live["change_pct"]
    adv, dec = int((chg > 0.0001).sum()), int((chg < -0.0001).sum())
    unch = int(len(live) - adv - dec)
    return {
        "available": True, "total": int(len(live)),
        "advancing": adv, "declining": dec, "unchanged": unch,
        "ad_ratio": adv / dec if dec else None,
        "pct_above_ma20": float(live["above_ma20"].mean() * 100) if len(live) else None,
        "new_highs": int(live["new_high20"].sum()), "new_lows": int(live["new_low20"].sum()),
        "value_bn": float(live["value_bn"].sum()),
        "avg_change": float(chg.mean()) if len(live) else None,
        "session": live["date"].max().strftime("%d/%m/%Y") if len(live) else "",
    }


def sector_performance(snap: pd.DataFrame) -> pd.DataFrame:
    """Hiệu suất bình quân theo ngành (trung bình gia quyền theo giá trị giao dịch cho 1 phiên)."""
    if snap is None or snap.empty:
        return pd.DataFrame()
    live = snap[~snap["stale"]] if "stale" in snap.columns else snap
    rows = []
    for sec, g in live.groupby("sector"):
        w = g["value_bn"].clip(lower=0)
        d1 = float(np.average(g["change_pct"], weights=w)) if w.sum() > 0 else float(g["change_pct"].mean())
        rows.append({"sector": sec, "n": len(g), "1D": d1,
                     "5D": float(g["ret_5d"].dropna().mean()) if g["ret_5d"].notna().any() else None,
                     "20D": float(g["ret_20d"].dropna().mean()) if g["ret_20d"].notna().any() else None,
                     "value_bn": float(g["value_bn"].sum()),
                     "adv": int((g["change_pct"] > 0).sum()), "dec": int((g["change_pct"] < 0).sum())})
    return pd.DataFrame(rows)


def market_health(index_df: pd.DataFrame, breadth: Dict[str, Any]) -> Dict[str, Any]:
    """
    Điểm sức khỏe thị trường 0–100 theo quy tắc (không phải dự báo):
      Xu hướng 35% (giá so với MA20/50/200) · Động lượng 20% (RSI14) ·
      Độ rộng 30% (% mã tăng, % mã trên MA20) · Hiệu suất 20 phiên 15%.
    """
    comps: Dict[str, Dict[str, Any]] = {}
    if index_df is not None and not index_df.empty and len(index_df) >= 30:
        c = index_df["close"].astype(float).reset_index(drop=True)
        last = float(c.iloc[-1])
        mas = {n: float(c.tail(n).mean()) for n in (20, 50, 200) if len(c) >= n}
        trend = np.mean([100.0 if last > m else 0.0 for m in mas.values()]) if mas else None
        comps["trend"] = {"label": "Xu hướng", "score": trend, "weight": 35,
                          "detail": " · ".join(f"{'▲' if last > m else '▼'} MA{n}" for n, m in mas.items())}
        r = float(rsi(c).iloc[-1])
        if not math.isnan(r):
            comps["momentum"] = {"label": "Động lượng", "score": float(np.clip((r - 30) / 40 * 100, 0, 100)),
                                 "weight": 20, "detail": f"RSI14 = {r:.1f}"}
        if len(c) > 20:
            r20 = (last / float(c.iloc[-21]) - 1) * 100
            comps["perf"] = {"label": "Hiệu suất 20 phiên", "score": float(np.clip(50 + r20 * 6, 0, 100)),
                             "weight": 15, "detail": f"{r20:+.2f}%"}
    if breadth.get("available") and breadth.get("total"):
        adv, dec = breadth["advancing"], breadth["declining"]
        pa = adv / (adv + dec) * 100 if adv + dec else 50.0
        pm = breadth.get("pct_above_ma20") or 0.0
        comps["breadth"] = {"label": "Độ rộng", "score": (pa + pm) / 2, "weight": 30,
                            "detail": f"{pa:.0f}% mã tăng · {pm:.0f}% trên MA20"}
    valid = [v for v in comps.values() if v.get("score") is not None and not math.isnan(v["score"])]
    if not valid:
        return {"available": False, "components": comps}
    score = sum(v["score"] * v["weight"] for v in valid) / sum(v["weight"] for v in valid)
    if score >= 65:
        label = "Tích cực"
    elif score >= 50:
        label = "Trung tính – nghiêng tích cực"
    elif score >= 35:
        label = "Thận trọng"
    else:
        label = "Tiêu cực"
    return {"available": True, "score": float(score), "label": label, "components": comps}


# ─────────────────────────── Giá TRONG PHIÊN (chỉ số & cổ phiếu, cập nhật ~3 phút) ───────────────────────────
import threading
import time as _time

from core.cau_hinh import settings as _settings
LIVE_POLL_SEC = float(_settings.LIVE_REFRESH_SECONDS)   # giây – mỗi mã gọi DNSE tối đa 1 lần/chu kỳ (mặc định 180 giây,
                                                        # đổi bằng LIVE_REFRESH_SECONDS trong .env) để tránh DNSE chặn
LIVE_MAX_RPS = 4.0                  # tổng số lệnh gọi giá trong phiên tối đa mỗi giây (tránh DNSE chặn vì gọi quá dày)
_rate_lock = threading.Lock()
_next_slot = [0.0]


def _throttle() -> None:
    """Giãn đều các lệnh gọi giá trong phiên: tối đa LIVE_MAX_RPS lệnh/giây cho cả ứng dụng."""
    with _rate_lock:
        now = _time.time()
        slot = max(now, _next_slot[0])
        _next_slot[0] = slot + 1.0 / LIVE_MAX_RPS
    if slot > now:
        _time.sleep(min(slot - now, 1.0))
LIVE_KEEP_SEC = 180                 # nguồn lỗi chốc lát (vd bị giới hạn tần suất) → giữ giá tốt gần nhất ≤ 3 phút
_LIVE_FAIL_TTL = 15.0               # mọi nguồn lỗi và không có giá gần đây → 15 giây sau mới thử lại
_live_cache: Dict[str, tuple] = {}  # mã → (thời điểm gọi, nến hôm nay | None)
_last_good: Dict[str, tuple] = {}   # mã → (thời điểm, nến hôm nay) – giá thật lấy được gần nhất
_live_lock = threading.Lock()
_http = None


def _session():
    global _http
    if _http is None:
        import requests
        from requests.adapters import HTTPAdapter
        from core.nguon_du_lieu import _HEADERS
        s = requests.Session()
        s.headers.update(_HEADERS)
        s.mount("https://", HTTPAdapter(pool_connections=4, pool_maxsize=32, max_retries=0))   # giữ kết nối, không thử lại
        _http = s
    return _http


def _poll_ttl(now: Optional[datetime] = None) -> float:
    """Nghỉ trưa (11:30–13:00) và sau 14:46 giá gần như đứng yên → gọi thưa hơn."""
    now = now or datetime.now()
    hm = (now.hour, now.minute)
    return max(30.0, LIVE_POLL_SEC)          # chu kỳ làm mới (mặc định 180 giây) áp dụng cả lúc nghỉ trưa / cuối phiên


class _FastDNSE:
    """Gọi thẳng API nến DNSE: thời gian chờ ngắn, KHÔNG thử lại, dùng chung kết nối – để không làm chậm trang khi nguồn chậm."""
    TIMEOUT = 4

    def get_price_history(self, symbol: str, start_date: str, end_date: str, interval: str = "1m") -> pd.DataFrame:
        from core import nguon_du_lieu as dc
        if dc.backing_off():                     # DNSE vừa báo gọi quá dày → nhường cho các lệnh lấy lịch sử giá
            return pd.DataFrame()
        sym = dc._INDEX_ALIAS.get(symbol.upper().strip(), symbol.upper().strip())
        start = pd.Timestamp(start_date).to_pydatetime()
        params = {"symbol": sym, "resolution": dc._RESOLUTION.get(interval, "1"),
                  "from": int(_time.mktime(start.timetuple())),
                  "to": dc.to_param(pd.Timestamp(end_date).to_pydatetime())}      # = giây hiện tại → URL luôn mới
        _throttle()
        resp = _session().get(f"{dc.CHART_BASE}/ohlcs/{'index' if dc.is_index(sym) else 'stock'}", params=params,
                              headers=dc._NO_CACHE, timeout=self.TIMEOUT)
        if resp.status_code != 200:
            dc.note_status(resp.status_code, sym)
            return pd.DataFrame()
        return dc.DNSEClient.parse_udf(resp.json(), sym, interval)


def _bar_from_minutes(m: pd.DataFrame, symbol: str, src: str) -> Optional[Dict[str, Any]]:
    from core.du_lieu import to_vnd
    today = pd.Timestamp(datetime.now().date())
    if m is None or m.empty:
        return None
    m = m[pd.to_datetime(m["timestamp"]).dt.normalize() == today].sort_values("timestamp")
    if m.empty:
        return None
    m = to_vnd(m, symbol)
    return {"timestamp": today, "open": float(m["open"].iloc[0]), "high": float(m["high"].max()),
            "low": float(m["low"].min()), "close": float(m["close"].iloc[-1]),
            "volume": float(pd.to_numeric(m["volume"], errors="coerce").fillna(0).sum()),
            "session_time": pd.to_datetime(m["timestamp"].iloc[-1]).strftime("%H:%M"), "source": src}


def _fetch_live(sym: str, allow_slow: bool) -> Optional[Dict[str, Any]]:
    """Nến 1 phút DNSE (dự phòng 5 phút); chỉ khi chưa có giá gần đây mới thử nến 1 phút vnstock (chậm hơn)."""
    d = datetime.now().strftime("%Y-%m-%d")
    tries = [("dnse_1m", _FastDNSE(), "1m"), ("dnse_5m", _FastDNSE(), "5m")]
    if allow_slow:
        tries.append(("vnstock_1m", get_repo()._vnstock, "1m"))
    for src, prov, interval in tries:
        try:
            bar = _bar_from_minutes(prov.get_price_history(sym, d, d, interval), sym, src)
        except Exception as exc:  # pragma: no cover - nguồn lỗi
            logger.debug("live %s %s failed: %s", sym, src, exc)
            continue
        if bar:
            return bar
    return None


def live_refresh_seconds() -> int:
    """Nhịp làm mới ô giá trên trang: vài giây khi đang nhận giá realtime DNSE, ngược lại LIVE_REFRESH_SECONDS (3 phút)."""
    try:
        from core import nguon_du_lieu as rt
        if rt.active():
            return int(_settings.REALTIME_REFRESH_SECONDS)
    except Exception as exc:  # pragma: no cover
        logger.debug("realtime status failed: %s", exc)
    return int(_settings.LIVE_REFRESH_SECONDS)


def live_mode() -> str:
    """'realtime' khi giá đang đến từ WebSocket DNSE, ngược lại 'poll' (API biểu đồ ~3 phút/lần)."""
    try:
        from core import nguon_du_lieu as rt
        f = rt.get_feed()
        return "realtime" if f is not None and f.state == "live" else "poll"
    except Exception:  # pragma: no cover
        return "poll"


def _rt_snapshot(code: str) -> Optional[Dict[str, Any]]:
    try:
        from core import nguon_du_lieu as rt
        return rt.snapshot(code)
    except Exception as exc:  # pragma: no cover
        logger.debug("realtime snapshot %s failed: %s", code, exc)
        return None


def live_bar(code: str) -> Optional[Dict[str, Any]]:
    """
    Phiên HÔM NAY của một mã/chỉ số. Ưu tiên giá REALTIME qua WebSocket DNSE OpenAPI (khi đã nhập API key + secret):
    cổ phiếu có đủ mở/cao/thấp/khớp/KL ngay trong tin khớp lệnh; chỉ số chỉ có giá trị hiện tại/cao/thấp nên vẫn lấy giá
    mở cửa từ nến phút rồi ghi đè phần còn lại. Không có realtime → cách cũ (_live_bar_polled, ~3 phút/lần).
    """
    from core.du_lieu import _in_session
    if not _in_session():
        return None
    code = code.upper().strip()
    rt = _rt_snapshot(code)
    rt_bar = None
    if rt:
        rt_bar = {k: v for k, v in rt.items() if k != "reference"}
        if all(rt_bar.get(k) is not None for k in ("open", "high", "low", "close")):
            if rt_bar.get("volume") is None:
                rt_bar["volume"] = 0.0
            return rt_bar
    bar = _live_bar_polled(code)
    if rt_bar and bar:
        bar = dict(bar)
        c = float(rt_bar["close"])
        bar.update(close=c, high=max(float(bar["high"]), float(rt_bar.get("high") or c), c),
                   low=min(float(bar["low"]), float(rt_bar.get("low") or c), c),
                   session_time=rt_bar["session_time"], source="dnse_realtime")
        if rt_bar.get("volume"):
            bar["volume"] = float(rt_bar["volume"])
    return bar


def _live_bar_polled(code: str) -> Optional[Dict[str, Any]]:
    """
    Phiên HÔM NAY của một mã cổ phiếu hoặc chỉ số (mở/cao/thấp/khớp gần nhất/KL, giờ nến phút mới nhất) – chỉ trong
    giờ giao dịch. Lấy thẳng từ nến phút DNSE, nhớ tạm LIVE_REFRESH_SECONDS (mặc định 180 giây) → trễ tối đa ~3 phút so
    với dữ liệu nến phút của DNSE. Nguồn lỗi chốc lát → giữ giá thật gần nhất (≤ 3 phút); không có → None (không bịa số).
    """
    from core.du_lieu import _in_session
    if not _in_session():
        return None
    code = code.upper().strip()
    now = _time.time()
    with _live_lock:
        hit = _live_cache.get(code)
        if hit and now - hit[0] < (_poll_ttl() if hit[1] else _LIVE_FAIL_TTL):
            return hit[1]
        good = _last_good.get(code)
    fresh_good = good is not None and now - good[0] < LIVE_KEEP_SEC
    bar = None
    for sym in _INDEX_CANDIDATES.get(code, [code]):
        bar = _fetch_live(sym, allow_slow=not fresh_good)
        if bar:
            break
    with _live_lock:
        if bar:
            _last_good[code] = (now, bar)
        elif fresh_good:
            bar = good[1]                       # giữ giá thật vừa lấy được, thử lại ở nhịp sau
        _live_cache[code] = (now, bar)
    return bar


def index_live(code: str) -> Optional[Dict[str, Any]]:
    return live_bar(code)


def live_bars(codes: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    codes = list(dict.fromkeys(c.upper().strip() for c in codes if c))
    if not codes:
        return {}
    with ThreadPoolExecutor(max_workers=min(8, len(codes))) as ex:
        return dict(zip(codes, ex.map(live_bar, codes)))


def index_live_all(codes: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    return live_bars(codes)


def merge_live(df: pd.DataFrame, bar: Optional[Dict[str, Any]]) -> pd.DataFrame:
    """Thay/ghép phiên hôm nay trong chuỗi ngày bằng số trong phiên mới nhất (giữ nguyên các phiên cũ)."""
    if df is None or df.empty or not bar:
        return df
    ts = pd.to_datetime(df["timestamp"])
    base = df[ts.dt.normalize() < bar["timestamp"]]
    if base.empty:
        return df
    row = {c: None for c in df.columns}
    row.update({k: v for k, v in bar.items()})
    if row.get("symbol") is None and "symbol" in df.columns:
        row["symbol"] = df["symbol"].iloc[-1]
    cols = list(df.columns) + [c for c in row if c not in df.columns]
    out = pd.concat([base, pd.DataFrame([row])[cols]], ignore_index=True)
    out.attrs = dict(getattr(df, "attrs", {}))
    return out


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: services/screener_service.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Bộ lọc cổ phiếu (screener) & so sánh nhiều mã.

Mỗi mã được tính một "hồ sơ chỉ số" từ dữ liệu thật:
  giá & hiệu suất (từ chuỗi giá ghép DNSE + lịch sử), chỉ số tính từ BCTC năm gần nhất,
  định giá tại giá hiện tại, Piotroski F-score, Altman Z''-score.
Hồ sơ được lưu cache theo ngày để lọc lại nhanh. Do giới hạn tần suất gọi API của nguồn
dữ liệu, nên dùng bộ lọc trên từng nhóm ngành / rổ (≈ 10–30 mã) thay vì toàn thị trường;
script cập nhật hằng ngày có thể tính trước cho các rổ thường dùng.
"""


import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any, Callable, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from core.du_lieu import cache
from core.cau_hinh import settings

logger = logging.getLogger(__name__)

PROFILE_COLUMNS = {
    "symbol": "Mã", "price": "Giá", "change_1m": "% 1 tháng", "change_3m": "% 3 tháng", "change_1y": "% 12 tháng",
    "market_cap": "Vốn hóa", "pe": "P/E", "pb": "P/B", "ev_ebitda": "EV/EBITDA", "dividend_yield": "Tỷ suất cổ tức %",
    "roe": "ROE %", "roa": "ROA %", "net_margin": "Biên LN ròng %", "gross_margin": "Biên LN gộp %",
    "revenue_growth": "Tăng trưởng DT %", "net_income_growth": "Tăng trưởng LNST %",
    "debt_to_equity": "Nợ vay/VCSH", "current_ratio": "Thanh toán hiện hành",
    "fscore": "F-score", "zscore": "Z''-score", "fin_period": "Kỳ BCTC",
    "rs_group": "RS xếp hạng", "group_signal": "Tín hiệu CL nhóm", "error": "Ghi chú",
}


def add_group_signals(df: pd.DataFrame, symbols: Iterable[str], capital: Optional[float] = None) -> pd.DataFrame:
    """Thêm cột RS xếp hạng (percentile 63/126/252 phiên trong nhóm đạt thanh khoản) & tín hiệu MUA/BÁN/GIỮ của
    chiến lược nhóm (core/kiem_chung.py) – xếp hạng chéo trong chính danh sách đang lọc."""
    from core.kiem_chung import group_signals
    try:
        g = group_signals(symbols, capital=capital)
    except Exception as exc:
        logger.warning("group signals failed: %s", exc)
        return df
    if g is None or g.empty:
        return df
    g = g[["symbol", "rs", "signal"]].rename(columns={"rs": "rs_group", "signal": "group_signal"})
    out = df.drop(columns=[c for c in ("rs_group", "group_signal") if c in df.columns]).merge(g, on="symbol", how="left")
    return out

# Bộ lọc mẫu (chiến lược phổ biến) – (cột, toán tử, ngưỡng)
PRESETS: Dict[str, List[tuple]] = {
    "Giá trị (Value)": [("pe", "<=", 12), ("pb", "<=", 1.5), ("roe", ">=", 12)],
    "Tăng trưởng (Growth)": [("revenue_growth", ">=", 15), ("net_income_growth", ">=", 15), ("roe", ">=", 15)],
    "Chất lượng (Quality)": [("roe", ">=", 18), ("debt_to_equity", "<=", 1), ("fscore", ">=", 6)],
    "Cổ tức cao": [("dividend_yield", ">=", 5), ("debt_to_equity", "<=", 1.5)],
    "Động lượng (Momentum)": [("change_3m", ">=", 10), ("change_1y", ">=", 20)],
}


def build_profile(symbol: str, svc_factory: Callable[[str], Any]) -> Dict[str, Any]:
    """Hồ sơ chỉ số của một mã (svc_factory(symbol) -> StockService)."""
    out: Dict[str, Any] = {"symbol": symbol}
    try:
        svc = svc_factory(symbol)
        px = svc.get_price_df()
        if px is not None and not px.empty:
            c = px["close"].astype(float)
            out["price"] = float(c.iloc[-1])
            for key, n in (("change_1m", 21), ("change_3m", 63), ("change_1y", 250)):
                out[key] = (float(c.iloc[-1]) / float(c.iloc[-n - 1]) - 1) * 100 if len(c) > n else None
        summ = svc.financial_summary("year")
        ratios = summ.get("ratios", pd.DataFrame())
        if ratios is not None and not ratios.empty:
            last = ratios.iloc[-1]
            for k in ("roe", "roa", "net_margin", "gross_margin", "revenue_growth", "net_income_growth",
                      "debt_to_equity", "current_ratio"):
                v = last.get(k)
                out[k] = float(v) if v is not None and pd.notna(v) else None
            from core.phan_tich_co_ban import key_to_label
            out["fin_period"] = key_to_label(ratios.index[-1])
        val = summ.get("valuation") or {}
        for k in ("pe", "pb", "ev_ebitda", "dividend_yield", "market_cap"):
            out[k] = val.get(k)
        out["fscore"] = (summ.get("piotroski") or {}).get("score")
        out["zscore"] = (summ.get("altman") or {}).get("score")
    except Exception as exc:
        out["error"] = str(exc)[:120]
        logger.debug("profile %s failed: %s", symbol, exc)
    return out


class ScreenerService:

    def __init__(self, svc_factory: Optional[Callable[[str], Any]] = None, use_cache: bool = True):
        if svc_factory is None:
            from core.pipeline import StockService
            svc_factory = lambda s: StockService(s, days=400, fin_period="year", fin_years=6)  # noqa: E731
        self.svc_factory = svc_factory
        self.use_cache = use_cache

    def profile(self, symbol: str, force: bool = False) -> Dict[str, Any]:
        svc = self.svc_factory(symbol)
        as_of = getattr(svc, "as_of", None)
        period = getattr(svc, "fin_period", "year")
        years = getattr(svc, "fin_years", "")
        key = f"screen:{symbol}:{as_of.date() if as_of is not None else date.today()}:{period}:{years}:{settings.FINANCIAL_SOURCES}"
        if self.use_cache and not force:
            hit = cache.get(key)
            if hit:
                return hit
        p = build_profile(symbol, lambda _symbol: svc)
        if self.use_cache and "error" not in p:
            cache.set(key, p, ttl=86400)
        return p

    def run(self, symbols: Iterable[str], max_workers: int = 3, force: bool = False,
            progress: Optional[Callable[[int, int], None]] = None) -> pd.DataFrame:
        syms = list(dict.fromkeys(s.upper().strip() for s in symbols if s))
        rows: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for i, res in enumerate(ex.map(lambda s: self.profile(s, force), syms), start=1):
                rows.append(res)
                if progress:
                    progress(i, len(syms))
        return pd.DataFrame(rows)

    @staticmethod
    def apply_filters(df: pd.DataFrame, filters: List[tuple]) -> pd.DataFrame:
        """filters: [(cột, toán tử, ngưỡng)], toán tử: >=, <=, >, <. Mã thiếu số liệu bị loại."""
        if df.empty:
            return df
        mask = pd.Series(True, index=df.index)
        ops = {">=": np.greater_equal, "<=": np.less_equal, ">": np.greater, "<": np.less}
        for col, op, thr in filters:
            if col not in df.columns:
                mask &= False
                continue
            vals = pd.to_numeric(df[col], errors="coerce")
            mask &= vals.notna() & ops[op](vals, thr)
        return df[mask]

    @staticmethod
    def rank(df: pd.DataFrame, weights: Optional[Dict[str, float]] = None) -> pd.DataFrame:
        """
        Xếp hạng tổng hợp theo phân vị: mỗi tiêu chí đổi thành thứ hạng phần trăm trong nhóm
        (chỉ số "thấp là tốt" như P/E, Nợ/VCSH được đảo chiều), rồi lấy bình quân có trọng số.
        """
        if df.empty:
            return df
        weights = weights or {"roe": 1, "revenue_growth": 1, "net_income_growth": 1, "pe": 1, "pb": 0.5,
                              "debt_to_equity": 0.5, "change_3m": 0.5}
        lower_better = {"pe", "pb", "ev_ebitda", "debt_to_equity"}
        score_sum = pd.Series(0.0, index=df.index)
        available_weight = pd.Series(0.0, index=df.index)
        configured_weight = sum(float(w) for w in weights.values() if w > 0)
        for col, w in weights.items():
            if col not in df.columns:
                continue
            vals = pd.to_numeric(df[col], errors="coerce")
            valid = vals.notna()                  # có số liệu (kể cả P/E âm) = có dữ liệu, tính vào độ phủ
            if col in ("pe", "pb", "ev_ebitda"):
                pos = vals.where(vals > 0)
                pct = pos.rank(pct=True, ascending=False)
                pct = pct.where(~(valid & pos.isna()), 0.0)   # P/E âm (thua lỗ): có dữ liệu nhưng điểm 0, không coi là "rẻ"
            else:
                pct = vals.rank(pct=True, ascending=col not in lower_better)
            score_sum = score_sum.add(pct.fillna(0) * w, fill_value=0)
            available_weight = available_weight.add(valid.astype(float) * w, fill_value=0)
        out = df.copy()
        out["coverage_score"] = (available_weight / configured_weight * 100).round(1) if configured_weight else 0.0
        out["rank_score"] = (score_sum / available_weight.replace(0, np.nan) * 100).round(1)
        out.loc[out["coverage_score"] < 60, "rank_score"] = np.nan
        return out.sort_values("rank_score", ascending=False)


def compare(symbols: List[str], svc_factory: Optional[Callable[[str], Any]] = None) -> Dict[str, Any]:
    """So sánh nhiều mã: bảng chỉ số + chuỗi giá chuẩn hóa (gốc = 100)."""
    scr = ScreenerService(svc_factory)
    table = scr.run(symbols)
    prices = {}
    for s in symbols:
        try:
            px = scr.svc_factory(s).get_price_df()
            if px is not None and not px.empty:
                prices[s] = px.set_index("timestamp")["close"].astype(float)
        except Exception:
            continue
    raw = pd.DataFrame(prices).sort_index().dropna(how="all")
    norm = raw.copy()
    if not norm.empty:
        norm = norm.ffill().dropna()
        norm = norm / norm.iloc[0] * 100 if not norm.empty else norm
    return {"table": table, "normalized_prices": norm, "prices": raw}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: services/watchlist_service.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Danh mục theo dõi (watchlist) & cảnh báo giá.

Điều kiện cảnh báo:
  price_above / price_below   : giá hiện tại ≥ / ≤ ngưỡng (VND)
  change_above / change_below : % thay đổi trong phiên ≥ / ≤ ngưỡng
  rsi_above / rsi_below       : RSI(14) ≥ / ≤ ngưỡng
Cảnh báo được kiểm tra mỗi lần mở trang Danh mục theo dõi và bởi script cập nhật hằng ngày;
khi kích hoạt, cảnh báo chuyển sang trạng thái đã kích hoạt kèm thời điểm và giá.
"""


from typing import Any, Dict, List, Optional

import pandas as pd

from core.phan_tich_ky_thuat import rsi_wilder
from core.du_lieu import Database

CONDITIONS = {
    "price_above": "Giá ≥ ngưỡng (VND)",
    "price_below": "Giá ≤ ngưỡng (VND)",
    "change_above": "Tăng trong phiên ≥ (%)",
    "change_below": "Giảm trong phiên ≤ (%)",
    "rsi_above": "RSI(14) ≥",
    "rsi_below": "RSI(14) ≤",
}


def check_condition(condition: str, threshold: float, price: Optional[float],
                    change_pct: Optional[float], rsi: Optional[float]) -> Optional[bool]:
    """True/False nếu đủ dữ liệu để kiểm tra, None nếu thiếu dữ liệu."""
    val = {"price": price, "change": change_pct, "rsi": rsi}[condition.split("_")[0]]
    if val is None or pd.isna(val):
        return None
    return val >= threshold if condition.endswith("above") else val <= threshold


class WatchlistService:

    def __init__(self, repo=None, db: Optional[Database] = None):
        if repo is None:
            from core.pipeline import get_repo
            repo = get_repo()
        self.repo = repo
        self.db = db or Database()

    # ── Watchlist ──
    def add(self, symbol: str, note: str = ""):
        self.db.add_watch(symbol, note)

    def remove(self, symbol: str):
        self.db.remove_watch(symbol)

    def symbols(self) -> List[str]:
        df = self.db.get_watchlist()
        return df["symbol"].tolist() if not df.empty else []

    def snapshot(self) -> pd.DataFrame:
        """Giá, % thay đổi phiên, % 1 tháng, RSI cho từng mã đang theo dõi."""
        rows = []
        for sym in self.symbols():
            rows.append(self._quote(sym))
        return pd.DataFrame(rows)

    def _quote(self, sym: str) -> Dict[str, Any]:
        cur = self.repo.get_current_price(sym) or {}
        px = self.repo.get_price_history(sym, days=60)
        rsi = None
        chg_1m = None
        if px is not None and not px.empty:
            r = rsi_wilder(px["close"], 14).dropna()
            rsi = float(r.iloc[-1]) if not r.empty else None
            if len(px) > 21:
                chg_1m = (float(px["close"].iloc[-1]) / float(px["close"].iloc[-22]) - 1) * 100
        price = cur.get("price") or (float(px["close"].iloc[-1]) if px is not None and not px.empty else None)
        chg = cur.get("change_pct")
        if chg is None and px is not None and len(px) > 1:
            chg = (float(px["close"].iloc[-1]) / float(px["close"].iloc[-2]) - 1) * 100
        prev_close = None                               # giá đóng cửa phiên trước hôm nay (để tính % phiên khi có giá trong phiên)
        if px is not None and not px.empty:
            before = px[pd.to_datetime(px["timestamp"]).dt.normalize() < pd.Timestamp(pd.Timestamp.now().date())]
            prev_close = float(before["close"].iloc[-1]) if not before.empty else None
        return {"symbol": sym, "price": price, "change_pct": chg, "change_1m_pct": chg_1m, "rsi": rsi, "prev_close": prev_close,
                "source": cur.get("source") or (px["source"].iloc[-1] if px is not None and not px.empty else None)}

    # ── Alerts ──
    def add_alert(self, symbol: str, condition: str, threshold: float):
        if condition not in CONDITIONS:
            raise ValueError(condition)
        self.db.add_alert(symbol, condition, threshold)

    def alerts(self, active_only: bool = False) -> pd.DataFrame:
        df = self.db.get_alerts(active_only)
        if not df.empty:
            df["condition_label"] = df["condition"].map(CONDITIONS)
        return df

    def delete_alert(self, alert_id: int):
        self.db.delete_alert(alert_id)

    def evaluate(self) -> List[Dict[str, Any]]:
        """Kiểm tra mọi cảnh báo đang bật; trả về danh sách cảnh báo vừa kích hoạt."""
        active = self.db.get_alerts(active_only=True)
        if active.empty:
            return []
        triggered = []
        quotes: Dict[str, Dict[str, Any]] = {}
        for _, a in active.iterrows():
            q = quotes.setdefault(a["symbol"], self._quote(a["symbol"]))
            hit = check_condition(a["condition"], float(a["threshold"]), q["price"], q["change_pct"], q["rsi"])
            if hit:
                self.db.mark_alert_triggered(int(a["id"]), float(q["price"] or 0))
                triggered.append({"id": int(a["id"]), "symbol": a["symbol"], "condition": CONDITIONS[a["condition"]],
                                  "threshold": float(a["threshold"]), "price": q["price"],
                                  "change_pct": q["change_pct"], "rsi": q["rsi"]})
        return triggered


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: services/portfolio_service.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
PortfolioService – manages user portfolio and performance tracking.
"""


import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from core.pipeline import get_repo

logger = logging.getLogger(__name__)



class PortfolioService:
    """Portfolio management and P&L calculation."""

    def get_portfolio(self, name: str = "default") -> pd.DataFrame:
        return get_repo().get_portfolio(name)

    def add_position(
        self, symbol: str, quantity: float, buy_price: float,
        buy_date: str = "", fee_pct: float = 0.0015,
        notes: str = "", portfolio_name: str = "default"
    ):
        get_repo().add_position(portfolio_name, symbol, quantity, buy_price, buy_date, fee_pct, notes)

    def delete_position(self, position_id: int):
        get_repo().delete_position(position_id)

    def get_portfolio_with_pnl(self, portfolio_name: str = "default") -> pd.DataFrame:
        """Return portfolio positions with current prices and P&L."""
        portfolio = self.get_portfolio(portfolio_name)
        if portfolio.empty:
            return portfolio

        rows = []
        for _, row in portfolio.iterrows():
            symbol = str(row["symbol"])
            qty = float(row["quantity"])
            buy_price = float(row["buy_price"])
            fee_pct = float(row.get("fee_pct", 0.0015))

            # Get current price
            current_data = get_repo().get_current_price(symbol)
            current_price = current_data.get("price", 0) if current_data else 0

            cost_basis = buy_price * qty * (1 + fee_pct)
            current_value = current_price * qty
            unrealized_pnl = current_value - cost_basis
            unrealized_pct = unrealized_pnl / cost_basis * 100 if cost_basis else 0

            rows.append({
                "id": row.get("id"),
                "symbol": symbol,
                "quantity": qty,
                "buy_price": buy_price,
                "buy_date": str(row.get("buy_date", ""))[:10],
                "current_price": current_price,
                "cost_basis": round(cost_basis, 0),
                "current_value": round(current_value, 0),
                "unrealized_pnl": round(unrealized_pnl, 0),
                "unrealized_pct": round(unrealized_pct, 2),
                "notes": row.get("notes", ""),
            })

        return pd.DataFrame(rows)

    def get_portfolio_summary(self, portfolio_name: str = "default") -> Dict[str, Any]:
        """Return summary stats for the portfolio."""
        df = self.get_portfolio_with_pnl(portfolio_name)
        if df.empty:
            return {"empty": True}

        total_cost = df["cost_basis"].sum()
        total_value = df["current_value"].sum()
        total_pnl = df["unrealized_pnl"].sum()
        total_pct = total_pnl / total_cost * 100 if total_cost else 0

        # Weight by current value
        df["weight"] = df["current_value"] / total_value * 100 if total_value else 0

        return {
            "total_cost": round(total_cost, 0),
            "total_value": round(total_value, 0),
            "total_pnl": round(total_pnl, 0),
            "total_pct": round(total_pct, 2),
            "n_positions": len(df),
            "positions": df,
        }
