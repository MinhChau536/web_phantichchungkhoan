"""
Backtest hệ thống khuyến nghị 12 tháng so với VN-Index (tái sử dụng cho mọi mã).

Quy trình (không dùng dữ liệu tương lai):
  • Mỗi năm, ngày quyết định = 15/4 (sau hạn công bố BCTC năm kiểm toán) – hoặc phiên giao dịch gần nhất trước đó.
  • Chỉ dùng BCTC năm đã công bố trước ngày quyết định (valuation_engine.annual_available) và lịch sử giá đến ngày đó.
  • Không dùng trung vị ngành và beta (không có dữ liệu điểm-thời-gian) → định giá dựa trên bội số lịch sử của chính DN + DCF.
  • Chạy đủ 3 engine (Health → Risk → Valuation → Recommendation) như bản trực tiếp.
  • Lợi nhuận kỳ sau = giá sau 12 tháng / giá ngày quyết định − 1 (giá đã điều chỉnh).
Chiến lược kiểm định: nắm giữ cổ phiếu 12 tháng khi khuyến nghị MUA, đứng ngoài (lợi nhuận 0) trong các trường hợp khác;
mỗi lần mua/bán chịu phí giao dịch `cost` (mặc định 0,3% mỗi chiều, gồm phí + thuế bán). Chuẩn so sánh: mua & giữ VN-Index.

Giới hạn: số kỳ ít (1 kỳ/năm) nên kết quả mang tính minh họa; giá điều chỉnh có thể làm lệch nhẹ tỷ suất cổ tức
quá khứ; không có dữ liệu BCTC công bố thực tế từng ngày nên dùng mốc 15/4 cố định. Chỉ kết luận sau khi kiểm chứng
trên nhiều mã và nhiều năm.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from config.investment_model import load_config


def _series(df: Optional[pd.DataFrame]) -> pd.Series:
    if df is None or df.empty or "close" not in df.columns:
        return pd.Series(dtype=float)
    ts = pd.to_datetime(df["timestamp"] if "timestamp" in df.columns else df.index)
    return pd.Series(df["close"].astype(float).values, index=ts).dropna().sort_index()


def _price_at(s: pd.Series, d: pd.Timestamp) -> Optional[tuple]:
    sub = s[s.index <= d]
    if sub.empty or (d - sub.index[-1]).days > 10:
        return None
    return sub.index[-1], float(sub.iloc[-1])


def _mdd(eq: pd.Series) -> Optional[float]:
    return float((eq / eq.cummax() - 1).min() * 100) if len(eq) > 1 else None


def _cagr(eq: pd.Series) -> Optional[float]:
    if len(eq) < 2:
        return None
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return float(((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1) * 100) if yrs > 0.5 and eq.iloc[0] > 0 else None


def backtest_recommendations(wide: pd.DataFrame, price_df: pd.DataFrame, index_df: Optional[pd.DataFrame],
                             company: Dict[str, str], *, cost: float = 0.003, decision_month: int = 4,
                             decision_day: int = 15, config: Optional[Dict[str, Any]] = None,
                             summary_fn=None) -> Dict[str, Any]:
    """
    wide: BCTC năm chuẩn hóa (index = year*10); price_df/index_df: lịch sử giá (timestamp, close).
    summary_fn(wide) -> dict có 'altman' (tùy chọn) để dùng cho Risk Assessment.
    """
    from analytics import financial_ratios as fr
    from analytics.financial_health import FinancialHealthEngine
    from analytics.recommendation import recommend_investment
    from analytics.risk_assessment import assess_risk
    from analytics.valuation_engine import ValuationEngine12M, point_in_time

    cfg = config or load_config()
    px, ix = _series(price_df), _series(index_df)
    out: Dict[str, Any] = {"periods": [], "available": False, "cost": cost,
                           "method": f"Ngày quyết định {decision_day}/{decision_month} hằng năm; giữ 12 tháng khi MUA; "
                                     f"phí {cost * 100:.2f}%/chiều; chuẩn so sánh VN-Index."}
    if wide is None or wide.empty or px.empty:
        out["reason"] = "Thiếu BCTC năm hoặc lịch sử giá."
        return out
    annual = wide[[int(k) % 10 == 0 for k in wide.index]]
    ratios_all = fr.compute_ratios(annual, "year")
    first = px.index[0].year
    last_dec = px.index[-1] - pd.DateOffset(months=12)
    health_eng, val_eng = FinancialHealthEngine(cfg), ValuationEngine12M(cfg)
    rows: List[Dict[str, Any]] = []
    for y in range(first, last_dec.year + 1):
        d = pd.Timestamp(year=y, month=decision_month, day=decision_day)
        if d > last_dec:
            break
        p0 = _price_at(px, d)
        p1 = _price_at(px, d + pd.DateOffset(months=12))
        if p0 is None or p1 is None:
            continue
        w_pit, r_pit, px_pit = point_in_time(annual, ratios_all, price_df, d)
        if w_pit is None or w_pit.empty or len(w_pit) < 2:
            continue
        sh = fr.shares_series(w_pit).dropna()
        shares = float(sh.iloc[-1]) if not sh.empty else None
        summ = summary_fn(w_pit) if summary_fn else {}
        health = health_eng.score(r_pit, w_pit, company)
        rk = dict(summary=summ, price_df=px_pit, health=health, as_of=d, config=cfg)
        risk0 = assess_risk(w_pit, r_pit, company, **rk)
        val = val_eng.value(price=p0[1], price_date=p0[0], wide=w_pit, ratios=r_pit, shares=shares, company=company,
                            beta=None, peers={}, price_df=px_pit, risk_level=risk0["level"])
        risk = assess_risk(w_pit, r_pit, company, valuation=val, **rk)
        rec = recommend_investment(health, val, risk, cfg, holder=False)
        i0, i1 = _price_at(ix, d), _price_at(ix, d + pd.DateOffset(months=12))
        stock_ret = (p1[1] / p0[1] - 1) * 100
        idx_ret = (i1[1] / i0[1] - 1) * 100 if i0 and i1 else None
        rows.append({"decision_date": p0[0].date(), "data_year": int(w_pit.index[-1]) // 10, "price": p0[1],
                     "rating": rec["rating"], "label": rec["label"], "health": health.get("score"),
                     "target": val.get("target_12m"), "expected_return": val.get("expected_return"),
                     "confidence": val.get("confidence"), "risk": risk.get("level"),
                     "exit_date": p1[0].date(), "exit_price": p1[1], "stock_ret": stock_ret, "index_ret": idx_ret,
                     "excess": stock_ret - idx_ret if idx_ret is not None else None,
                     "strategy_ret": ((1 - cost) ** 2 * (1 + stock_ret / 100) - 1) * 100 if rec["rating"] == "MUA" else 0.0})
    out["periods"] = rows
    if not rows:
        out["reason"] = "Không có kỳ nào đủ dữ liệu (cần ≥ 2 năm BCTC trước ngày quyết định và giá 12 tháng sau)."
        return out

    # Đường vốn theo ngày: giữ CP trong kỳ MUA, tiền mặt khi khác
    start, end = pd.Timestamp(rows[0]["decision_date"]), pd.Timestamp(rows[-1]["exit_date"])
    days = px[(px.index >= start) & (px.index <= end)]
    daily = pd.Series(0.0, index=days.index)
    stock_daily = days.pct_change().fillna(0.0)
    for r in rows:
        if r["rating"] != "MUA":
            continue
        a, b = pd.Timestamp(r["decision_date"]), pd.Timestamp(r["exit_date"])
        m = (daily.index > a) & (daily.index <= b)
        daily[m] = stock_daily[m]
        for dd in (a, b):                       # phí mua tại ngày vào, phí bán tại ngày ra
            if dd in daily.index:
                daily[dd] = (1 + daily[dd]) * (1 - cost) - 1
    eq = (1 + daily).cumprod() * 100
    bh = days / days.iloc[0] * 100
    idx_eq = None
    if not ix.empty:
        isub = ix[(ix.index >= start) & (ix.index <= end)]
        idx_eq = isub / isub.iloc[0] * 100 if not isub.empty else None
    buys = [r for r in rows if r["rating"] == "MUA"]
    sells = [r for r in rows if r["rating"] == "BÁN"]

    def wr(lst, key, cond):
        v = [r[key] for r in lst if r.get(key) is not None]
        return float(np.mean([cond(x) for x in v]) * 100) if v else None

    out.update(available=True, equity=eq, buy_hold=bh, index_equity=idx_eq, stats={
        "n_periods": len(rows), "n_buy": len(buys), "n_sell": len(sells),
        "n_insufficient": sum(r["rating"] == "CHƯA ĐỦ CƠ SỞ" for r in rows),
        "strategy_total": float(eq.iloc[-1] - 100), "buy_hold_total": float(bh.iloc[-1] - 100),
        "index_total": float(idx_eq.iloc[-1] - 100) if idx_eq is not None else None,
        "strategy_cagr": _cagr(eq), "buy_hold_cagr": _cagr(bh), "index_cagr": _cagr(idx_eq) if idx_eq is not None else None,
        "strategy_mdd": _mdd(eq), "buy_hold_mdd": _mdd(bh), "index_mdd": _mdd(idx_eq) if idx_eq is not None else None,
        "buy_win_rate": wr(buys, "stock_ret", lambda x: x > 0),
        "buy_beat_index": wr(buys, "excess", lambda x: x > 0),
        "sell_correct": wr(sells, "excess", lambda x: x < 0),
        "avg_buy_ret": float(np.mean([r["stock_ret"] for r in buys])) if buys else None,
        "avg_buy_excess": float(np.mean([r["excess"] for r in buys if r["excess"] is not None])) if any(r["excess"] is not None for r in buys) else None,
    })
    out["conclusion"] = _conclude(out["stats"])
    return out


def _conclude(st: Dict[str, Any]) -> str:
    n = st["n_periods"]
    if st["n_buy"] < 3 or n < 4:
        return (f"Chỉ có {n} kỳ ({st['n_buy']} lần MUA) – quá ít để kết luận về hiệu quả hệ thống; "
                "cần kiểm chứng trên nhiều mã/nhiều năm.")
    better = st["index_total"] is not None and st["strategy_total"] > st["index_total"]
    return (f"{n} kỳ, {st['n_buy']} lần MUA: tỷ lệ MUA có lãi {st['buy_win_rate']:.0f}%, vượt VN-Index "
            f"{st['buy_beat_index'] or 0:.0f}%. Chiến lược {'vượt' if better else 'kém'} VN-Index trong giai đoạn kiểm định "
            "(sau phí). Đây là kết quả trên 1 mã – chưa đủ để kết luận chung.")
