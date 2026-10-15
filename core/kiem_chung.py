"""
core/kiem_chung.py – gộp từ 2 module (15/10/2026).

MỤC LỤC
  • analytics/group_strategy.py – CHIẾN LƯỢC NHÓM (File 1 – "Chiến lược đầu tư cổ phiếu"): Long-only · RS + xu hướng + ATR · tối đa 10 vị thế.
      hàm/lớp chính: atr, indicators, build_panel, explain_row, position_size, latest_signals, backtest
  • services/strategy_service.py – Dịch vụ chiến lược nhóm (File 1) & bot giao dịch (File 2): lấy dữ liệu thật (giá ngày nhiều mã, VN-Index, BCTC quý,
      hàm/lớp chính: load_prices, group_signals
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/group_strategy.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
CHIẾN LƯỢC NHÓM (File 1 – "Chiến lược đầu tư cổ phiếu"): Long-only · RS + xu hướng + ATR · tối đa 10 vị thế.

Quy trình (đúng theo tài liệu):
  1. Dữ liệu: ≥ 260 phiên, thiếu → "THIẾU DỮ LIỆU" (không MUA/BÁN).
  2. Thanh khoản: Median GTGD20 ≥ 10 tỷ, SMA20 Volume ≥ 100.000 cp, Close ≥ 5.000 đ   (GTGD = Close × Volume).
  3. RS = (PR63 + PR126 + PR252)/3, với R_n = C(t−5)/C(t−5−n) − 1, PR = percentile rank trong nhóm ĐẠT thanh khoản
     cùng ngày.
  4. Xu hướng: EMA20 > EMA50 và Close > SMA200.
  5. Anti-Chasing = (Close − EMA20)/ATR14 ≤ 3.
  6. MUA: thanh khoản ∧ RS ≥ 60 ∧ EMA20 > EMA50 ∧ Close > SMA200 ∧ AntiChasing ≤ 3.
     BÁN: Close < SMA200 ∨ RS < 50.   GIỮ: còn lại.
  7. Nhiều mã MUA: ưu tiên RS giảm dần, rồi Median GTGD20 giảm dần; tối đa 10 vị thế.
  8. Khối lượng: Shares ≈ (1% × vốn ban đầu)/(3 × ATR14), làm tròn lô 100; ≤ 10% vốn ban đầu/mã; ≤ 5% GTGD bình quân 20 phiên.
  9. Tín hiệu cuối phiên T, khớp giá mở cửa T+1. Phí 0,1%, thuế bán 0,1%, trượt giá 0,1%.
Chandelier Stop được tính để theo dõi, KHÔNG dùng làm điều kiện BÁN (đúng bản chiến lược cuối).
Bổ sung (tùy chọn, mặc định bật): tuân thủ T+2 – cổ phiếu mua ở phiên D chỉ bán được từ chiều D+2, nên lệnh bán theo
giá mở cửa sớm nhất ở phiên D+3.
"""


import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

DEFAULT_PARAMS: Dict[str, Any] = {
    "min_sessions": 260,
    "min_med_gtgd20": 10e9, "min_vol20": 100_000, "min_close": 5_000,
    "rs_lag": 5, "rs_windows": (63, 126, 252),
    "rs_buy": 60.0, "rs_sell": 50.0, "anti_chasing_max": 3.0,
    "max_positions": 10, "risk_per_trade": 0.01, "atr_mult": 3.0,
    "max_position_pct": 0.10, "max_adv_pct": 0.05,
    "fee": 0.001, "sell_tax": 0.001, "slippage": 0.001,
    "initial_capital": 100_000_000.0, "t_plus": True,
    "chandelier_mult": 3.0, "chandelier_window": 22,
}

SIGNAL_HEX = {"MUA": "#16a34a", "BÁN": "#dc2626", "GIỮ": "#d97706", "THIẾU DỮ LIỆU": "#64748b"}


# ─────────────────────────────────────────────────────────────────────────────
# Chỉ báo
# ─────────────────────────────────────────────────────────────────────────────

def _prep(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if "timestamp" in d.columns:
        d["timestamp"] = pd.to_datetime(d["timestamp"]).dt.normalize()
        d = d.set_index("timestamp")
    d.index = pd.to_datetime(d.index).normalize()
    d = d[~d.index.duplicated(keep="last")].sort_index()
    for c in ("open", "high", "low", "close", "volume"):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    if "open" not in d.columns:
        d["open"] = d["close"]
    if "high" not in d.columns:
        d["high"] = d["close"]
    if "low" not in d.columns:
        d["low"] = d["close"]
    if "volume" not in d.columns:
        d["volume"] = np.nan
    return d[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """ATR14 = MA14(True Range), True Range = max(H−L, |H−C₋₁|, |L−C₋₁|)."""
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def indicators(df: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """Chỉ báo của một mã (index = ngày)."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    d = _prep(df)
    c, v = d["close"], d["volume"]
    out = pd.DataFrame(index=d.index)
    out["open"], out["high"], out["low"], out["close"], out["volume"] = d["open"], d["high"], d["low"], c, v
    gtgd = c * v
    out["gtgd"] = gtgd
    out["med_gtgd20"] = gtgd.rolling(20, min_periods=20).median()
    out["avg_gtgd20"] = gtgd.rolling(20, min_periods=20).mean()
    out["vol20"] = v.rolling(20, min_periods=20).mean()
    out["n_obs"] = np.arange(1, len(d) + 1)
    out["enough"] = out["n_obs"] >= p["min_sessions"]
    out["liquid"] = (out["med_gtgd20"] >= p["min_med_gtgd20"]) & (out["vol20"] >= p["min_vol20"]) & (c >= p["min_close"])
    lag = p["rs_lag"]
    for w in p["rs_windows"]:
        out[f"r{w}"] = c.shift(lag) / c.shift(lag + w) - 1
    out["ema20"] = c.ewm(span=20, adjust=False).mean()
    out["ema50"] = c.ewm(span=50, adjust=False).mean()
    out["sma200"] = c.rolling(200, min_periods=200).mean()
    out["atr14"] = atr(d, 14)
    out["anti_chasing"] = (c - out["ema20"]) / out["atr14"]
    hh = d["high"].rolling(p["chandelier_window"], min_periods=p["chandelier_window"]).max()
    out["chandelier"] = hh - p["chandelier_mult"] * out["atr14"]
    return out


def build_panel(prices: Dict[str, pd.DataFrame], params: Optional[Dict[str, Any]] = None) -> Dict[str, pd.DataFrame]:
    """Tính chỉ báo + RS xếp hạng chéo + tín hiệu cho mọi mã. → {mã: DataFrame chỉ báo theo ngày}."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    ind = {s: indicators(df, p) for s, df in prices.items() if df is not None and not df.empty}
    ind = {s: d for s, d in ind.items() if not d.empty}
    if not ind:
        return {}
    dates = sorted(set().union(*[d.index for d in ind.values()]))
    pr_sum = {s: pd.Series(0.0, index=dates) for s in ind}
    pr_cnt = {s: pd.Series(0, index=dates) for s in ind}
    for w in p["rs_windows"]:
        col = f"r{w}"
        mat = pd.DataFrame({s: d[col].where(d["liquid"] & d["enough"]) for s, d in ind.items()}).reindex(dates)
        rank = mat.rank(axis=1, pct=True) * 100
        for s in ind:
            pr_sum[s] = pr_sum[s] + rank[s].fillna(0)
            pr_cnt[s] = pr_cnt[s] + rank[s].notna().astype(int)
    elig = pd.DataFrame({s: (d["liquid"] & d["enough"]) for s, d in ind.items()}).reindex(dates).fillna(False)
    n_elig = elig.sum(axis=1)
    for s, d in ind.items():
        rs = (pr_sum[s] / pr_cnt[s].replace(0, np.nan)).where(pr_cnt[s] == len(p["rs_windows"]))
        d["rs"] = rs.reindex(d.index)
        d["universe_n"] = n_elig.reindex(d.index)
        d["signal"] = _signals(d, p)
    return ind


def _signals(d: pd.DataFrame, p: Dict[str, Any]) -> pd.Series:
    buy = (d["liquid"] & (d["rs"] >= p["rs_buy"]) & (d["ema20"] > d["ema50"]) & (d["close"] > d["sma200"])
           & (d["anti_chasing"] <= p["anti_chasing_max"]))
    sell = (d["close"] < d["sma200"]) | (d["rs"] < p["rs_sell"])
    sig = pd.Series("GIỮ", index=d.index, dtype=object)
    sig[sell.fillna(False)] = "BÁN"
    sig[buy.fillna(False)] = "MUA"
    sig[~d["enough"]] = "THIẾU DỮ LIỆU"
    return sig


def explain_row(r: pd.Series, p: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Checklist từng điều kiện cho một phiên (dùng cho giao diện & PDF)."""
    p = {**DEFAULT_PARAMS, **(p or {})}

    def ok(x):
        return None if x is None or (isinstance(x, float) and math.isnan(x)) else bool(x)

    def f(x, d=0, suf=""):
        return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:,.{d}f}{suf}"

    rows = [
        {"step": "Dữ liệu ≥ 260 phiên", "value": f"{int(r['n_obs'])} phiên", "pass": bool(r["enough"])},
        {"step": "Median GTGD20 ≥ 10 tỷ", "value": f(r["med_gtgd20"] / 1e9 if pd.notna(r["med_gtgd20"]) else None, 1, " tỷ"),
         "pass": ok(r["med_gtgd20"] >= p["min_med_gtgd20"]) if pd.notna(r["med_gtgd20"]) else None},
        {"step": "SMA20 Volume ≥ 100.000 cp", "value": f(r["vol20"]),
         "pass": ok(r["vol20"] >= p["min_vol20"]) if pd.notna(r["vol20"]) else None},
        {"step": "Giá đóng cửa ≥ 5.000 đ", "value": f(r["close"]), "pass": ok(r["close"] >= p["min_close"])},
        {"step": f"RS ≥ {p['rs_buy']:.0f} (BÁN nếu < {p['rs_sell']:.0f})",
         "value": f(r["rs"], 1) + (f" (nhóm {int(r['universe_n'])} mã)" if pd.notna(r.get("universe_n")) else ""),
         "pass": ok(r["rs"] >= p["rs_buy"]) if pd.notna(r["rs"]) else None},
        {"step": "EMA20 > EMA50", "value": f"{f(r['ema20'])} / {f(r['ema50'])}",
         "pass": ok(r["ema20"] > r["ema50"])},
        {"step": "Close > SMA200", "value": f"{f(r['close'])} / {f(r['sma200'])}",
         "pass": ok(r["close"] > r["sma200"]) if pd.notna(r["sma200"]) else None},
        {"step": f"Anti-Chasing (Close−EMA20)/ATR14 ≤ {p['anti_chasing_max']:.0f}", "value": f(r["anti_chasing"], 2),
         "pass": ok(r["anti_chasing"] <= p["anti_chasing_max"]) if pd.notna(r["anti_chasing"]) else None},
    ]
    return rows


def position_size(price: float, atr14: Optional[float], avg_gtgd20: Optional[float], capital: float,
                  cash: Optional[float] = None, params: Optional[Dict[str, Any]] = None) -> int:
    """Shares ≈ (risk% × vốn ban đầu)/(atr_mult × ATR14), lô 100; ≤ 10% vốn; ≤ 5% GTGD20 bình quân; ≤ tiền mặt."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    if not price or not atr14 or atr14 <= 0 or (isinstance(atr14, float) and math.isnan(atr14)):
        return 0
    lim = [(p["risk_per_trade"] * capital) / (p["atr_mult"] * atr14), p["max_position_pct"] * capital / price]
    if avg_gtgd20 and not math.isnan(avg_gtgd20):
        lim.append(p["max_adv_pct"] * avg_gtgd20 / price)
    if cash is not None:
        lim.append(cash / (price * (1 + p["fee"])))
    return int(max(0.0, min(lim)) // 100) * 100


def latest_signals(prices: Dict[str, pd.DataFrame], params: Optional[Dict[str, Any]] = None,
                   as_of: Optional[pd.Timestamp] = None, capital: Optional[float] = None) -> pd.DataFrame:
    """Tín hiệu ở phiên gần nhất (≤ as_of) cho từng mã, xếp theo luật ưu tiên của tài liệu."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    if as_of is not None:
        lim = pd.Timestamp(as_of).normalize()
        prices = {s: _prep(df).loc[:lim].reset_index().rename(columns={"index": "timestamp"})
                  for s, df in prices.items() if df is not None and not df.empty}
    panel = build_panel(prices, p)
    rows = []
    for s, d in panel.items():
        r = d.iloc[-1]
        cap = capital or p["initial_capital"]
        rows.append({"symbol": s, "date": d.index[-1], "close": r["close"], "signal": r["signal"], "rs": r["rs"],
                     "r63": r["r63"] * 100 if pd.notna(r["r63"]) else None,
                     "r126": r["r126"] * 100 if pd.notna(r["r126"]) else None,
                     "r252": r["r252"] * 100 if pd.notna(r["r252"]) else None,
                     "liquid": bool(r["liquid"]), "med_gtgd20_bn": r["med_gtgd20"] / 1e9 if pd.notna(r["med_gtgd20"]) else None,
                     "ema20": r["ema20"], "ema50": r["ema50"], "sma200": r["sma200"], "atr14": r["atr14"],
                     "anti_chasing": r["anti_chasing"], "chandelier": r["chandelier"],
                     "shares": position_size(r["close"], r["atr14"], r["avg_gtgd20"], cap, params=p)
                     if r["signal"] == "MUA" else 0,
                     "universe_n": int(r["universe_n"]) if pd.notna(r["universe_n"]) else 0,
                     "checks": explain_row(r, p)})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    order = {"MUA": 0, "GIỮ": 1, "BÁN": 2, "THIẾU DỮ LIỆU": 3}
    out["_o"] = out["signal"].map(order)
    out = out.sort_values(["_o", "rs", "med_gtgd20_bn"], ascending=[True, False, False], na_position="last")
    out["priority"] = np.where(out["signal"] == "MUA", out.groupby("_o").cumcount() + 1, np.nan)
    out["in_top"] = out["priority"] <= p["max_positions"]
    return out.drop(columns="_o").reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Backtest danh mục
# ─────────────────────────────────────────────────────────────────────────────

def backtest(prices: Dict[str, pd.DataFrame], start: str, end: Optional[str] = None,
             params: Optional[Dict[str, Any]] = None, index_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    p = {**DEFAULT_PARAMS, **(params or {})}
    panel = build_panel(prices, p)
    if not panel:
        return {"available": False, "reason": "Không có dữ liệu giá của mã nào."}
    start_ts = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end).normalize() if end else max(d.index.max() for d in panel.values())
    dates = sorted(set().union(*[d.index for d in panel.values()]))
    dates = [d for d in dates if start_ts <= d <= end_ts]
    if len(dates) < 30:
        return {"available": False, "reason": "Giai đoạn backtest quá ngắn hoặc không có dữ liệu trong giai đoạn đã chọn."}
    cols = {k: pd.DataFrame({s: d[k] for s, d in panel.items()}).reindex(dates)
            for k in ("open", "close", "signal", "rs", "med_gtgd20", "avg_gtgd20", "atr14")}
    C0 = float(p["initial_capital"])
    cash, positions, trades, equity = C0, {}, [], []
    pending: List[tuple] = []          # lệnh chờ khớp ở phiên kế tiếp: (loại, mã, ...)
    skipped_t2 = 0
    for i, day in enumerate(dates):
        # 1) Khớp lệnh từ tín hiệu phiên trước tại giá mở cửa hôm nay
        for kind, sym, info in pending:
            o = cols["open"].at[day, sym]
            if pd.isna(o) or o <= 0:
                o = cols["close"].at[day, sym]
            if pd.isna(o) or o <= 0:
                continue
            if kind == "sell" and sym in positions:
                pos = positions[sym]
                if p["t_plus"] and i - pos["entry_idx"] < 3:
                    skipped_t2 += 1
                    continue                                      # chưa đủ T+2 → giữ lại, xét lại ở tín hiệu sau
                px = o * (1 - p["slippage"])
                gross = px * pos["shares"]
                net = gross * (1 - p["fee"] - p["sell_tax"])
                cash += net
                pnl = net - pos["cost"]
                trades.append({"symbol": sym, "entry_date": pos["entry_date"], "entry_price": pos["entry_price"],
                               "exit_date": day, "exit_price": px, "shares": pos["shares"], "pnl": pnl,
                               "ret": pnl / pos["cost"] * 100, "days": (day - pos["entry_date"]).days,
                               "exit_reason": info})
                del positions[sym]
        for kind, sym, info in pending:
            if kind != "buy" or sym in positions or len(positions) >= p["max_positions"]:
                continue
            o = cols["open"].at[day, sym]
            if pd.isna(o) or o <= 0:
                continue
            px = o * (1 + p["slippage"])
            sh = position_size(px, info["atr"], info["adv"], C0, cash, p)
            if sh <= 0:
                continue
            cost = px * sh * (1 + p["fee"])
            cash -= cost
            positions[sym] = {"shares": sh, "entry_price": px, "entry_date": day, "entry_idx": i, "cost": cost}
        pending = []
        # 2) Định giá danh mục cuối phiên
        mv = 0.0
        for sym, pos in positions.items():
            c = cols["close"].at[day, sym]
            if pd.isna(c):
                prev = cols["close"][sym].loc[:day].dropna()
                c = prev.iloc[-1] if not prev.empty else pos["entry_price"]
            pos["last"] = float(c)
            mv += pos["shares"] * float(c)
        equity.append((day, cash + mv, len(positions)))
        if i == len(dates) - 1:
            break
        # 3) Tín hiệu cuối phiên → lệnh cho phiên sau
        sig = cols["signal"].loc[day]
        for sym in list(positions):
            if sig.get(sym) == "BÁN":
                c, s200 = cols["close"].at[day, sym], panel[sym]["sma200"].get(day)
                reason = "Close < SMA200" if pd.notna(s200) and c < s200 else "RS < 50"
                pending.append(("sell", sym, reason))
        slots = p["max_positions"] - len(positions) + sum(1 for k, *_ in pending if k == "sell")
        if slots > 0:
            cands = [s for s in sig.index if sig[s] == "MUA" and s not in positions]
            cands.sort(key=lambda s: (-(cols["rs"].at[day, s] or 0), -(cols["med_gtgd20"].at[day, s] or 0)))
            for s in cands[:slots]:
                pending.append(("buy", s, {"atr": cols["atr14"].at[day, s], "adv": cols["avg_gtgd20"].at[day, s]}))

    eq = pd.DataFrame(equity, columns=["date", "equity", "n_pos"]).set_index("date")
    final = float(eq["equity"].iloc[-1])
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    total = (final / C0 - 1) * 100
    cagr = ((final / C0) ** (1 / years) - 1) * 100 if final > 0 else None
    dd = eq["equity"] / eq["equity"].cummax() - 1
    tr = pd.DataFrame(trades)
    wins = tr[tr["pnl"] > 0] if not tr.empty else tr
    losses = tr[tr["pnl"] <= 0] if not tr.empty else tr
    pf = (wins["pnl"].sum() / abs(losses["pnl"].sum())) if not tr.empty and losses["pnl"].sum() != 0 else None
    stats = {"initial": C0, "final": final, "total_return": total, "cagr": cagr, "mdd": float(dd.min() * 100),
             "n_trades": int(len(tr)), "win_rate": (len(wins) / len(tr) * 100) if len(tr) else None,
             "profit_factor": pf, "avg_hold_days": float(tr["days"].mean()) if len(tr) else None,
             "open_positions": len(positions), "exposure": float((eq["n_pos"] > 0).mean() * 100),
             "start": str(eq.index[0].date()), "end": str(eq.index[-1].date()), "years": years,
             "skipped_t2": skipped_t2}
    idx_eq = None
    if index_df is not None and not index_df.empty:
        ic = _prep(index_df)["close"].reindex(eq.index).ffill()
        if ic.notna().any():
            ic = ic.bfill()
            idx_eq = ic / ic.iloc[0] * C0
            stats["index_return"] = (float(idx_eq.iloc[-1]) / C0 - 1) * 100
            stats["index_cagr"] = ((float(idx_eq.iloc[-1]) / C0) ** (1 / years) - 1) * 100
            stats["index_mdd"] = float((idx_eq / idx_eq.cummax() - 1).min() * 100)
    open_pos = [{"symbol": s, "entry_date": v["entry_date"], "entry_price": v["entry_price"], "shares": v["shares"],
                 "last": v.get("last"), "unrealized": (v.get("last", v["entry_price"]) * v["shares"] - v["cost"])}
                for s, v in positions.items()]
    return {"available": True, "stats": stats, "equity": eq, "index_equity": idx_eq, "trades": tr,
            "open_positions": open_pos, "params": p, "universe": sorted(panel),
            "coverage": {s: (str(d.index.min().date()), int(len(d))) for s, d in panel.items()}}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: services/strategy_service.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Dịch vụ chiến lược nhóm (File 1) & bot giao dịch (File 2): lấy dữ liệu thật (giá ngày nhiều mã, VN-Index, BCTC quý,
nến 15 phút DNSE) rồi gọi analytics.group_strategy (bot 4 tầng đã bỏ 14/10/2026).
Hỗ trợ as_of (định giá tại ngày): mọi chuỗi giá cắt về ngày đó, BCTC quý chỉ dùng kỳ đã công bố (45 ngày sau quý).
"""


import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Iterable, Optional

import pandas as pd

from core.du_lieu import BASKETS

logger = logging.getLogger(__name__)

VN30 = BASKETS.get("⭐ VN30 (Blue-chips HSX)", [])


def _repo(repo=None):
    if repo is not None:
        return repo
    from core.pipeline import get_repo
    return get_repo()


def load_prices(symbols: Iterable[str], days: int = 460, end: Optional[str] = None, repo=None,
                max_workers: int = 3, progress: Optional[Callable[[int, int], None]] = None,
                start: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """Giá ngày nhiều mã (song song, có cache của repository). Mã lỗi/không có dữ liệu bị bỏ qua."""
    r = _repo(repo)
    syms = list(dict.fromkeys(s.upper().strip() for s in symbols if s and s.strip()))
    end_s = str(pd.Timestamp(end).date()) if end else ""

    def one(s):
        try:
            if start:
                return s, r.get_price_history(s, start_date=start, end_date=end_s)
            return s, r.get_price_history(s, end_date=end_s, days=days)
        except Exception as exc:
            logger.debug("load %s failed: %s", s, exc)
            return s, pd.DataFrame()

    out: Dict[str, pd.DataFrame] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for i, (s, df) in enumerate(ex.map(one, syms), start=1):
            if df is not None and not df.empty:
                out[s] = df
            if progress:
                progress(i, len(syms))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# File 1 – chiến lược nhóm
# ─────────────────────────────────────────────────────────────────────────────

def group_signals(symbols: Iterable[str], as_of: Optional[str] = None, repo=None, capital: Optional[float] = None,
                  params: Optional[Dict[str, Any]] = None, progress=None) -> pd.DataFrame:
    from core.kiem_chung import latest_signals
    prices = load_prices(symbols, days=460, end=as_of, repo=repo, progress=progress)
    return latest_signals(prices, params=params, as_of=pd.Timestamp(as_of) if as_of else None, capital=capital)
