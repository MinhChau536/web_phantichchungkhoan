"""
Định giá cổ phiếu nhiều phương pháp – minh bạch từng giả định (dùng chung cho ứng dụng và báo cáo PDF).

Phương pháp (chỉ dùng phương pháp đủ dữ liệu, trọng số được chuẩn hóa lại):
  1. P/E lịch sử     : EPS TTM × trung vị P/E cuối năm của chính doanh nghiệp (tối đa 5 năm gần nhất, ≥ 3 năm)
  2. P/E ngành       : EPS TTM × trung vị P/E nhóm ngành (≥ 3 doanh nghiệp)
  3. P/B lịch sử     : BVPS × trung vị P/B cuối năm của chính doanh nghiệp
  4. P/B theo ROE    : BVPS × (ROE − g) / (Ke − g)   (mô hình Gordon cho giá trị sổ sách)
       Ke = lãi suất phi rủi ro + β × phần bù rủi ro (CAPM), g = ROE × (1 − tỷ lệ chi trả), có chặn trên.
Trọng số nhóm: doanh nghiệp thường P/E 60% – P/B 40%; ngân hàng/chứng khoán/bảo hiểm P/E 40% – P/B 60%;
doanh nghiệp lỗ (EPS ≤ 0) chỉ dùng P/B. Trong mỗi nhóm, các phương pháp có mặt chia đều.

Không phải dự báo giá – kết quả nhạy với giả định, luôn đọc cùng bảng độ nhạy.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

RISK_FREE = 0.04          # lợi suất TPCP 10 năm (giả định)
EQUITY_PREMIUM = 0.08     # phần bù rủi ro thị trường VN (giả định)
KE_BOUNDS = (0.10, 0.18)
G_CAP = 0.07              # tăng trưởng dài hạn tối đa
PE_BOUNDS = (2.0, 60.0)   # loại P/E bất thường khi tính trung vị lịch sử
PB_BOUNDS = (0.2, 15.0)
FINANCIAL_HINTS = ("ngân hàng", "ngan hang", "bank", "chứng khoán", "chung khoan", "securities", "bảo hiểm",
                   "bao hiem", "insurance", "tài chính", "financial")


def _pos(v) -> Optional[float]:
    try:
        f = float(v)
        return f if f > 0 and not math.isnan(f) else None
    except (TypeError, ValueError):
        return None


def year_end_prices(price_df: Optional[pd.DataFrame]) -> Dict[int, float]:
    """Giá đóng cửa phiên cuối cùng của mỗi năm (VND)."""
    if price_df is None or price_df.empty or "close" not in price_df.columns:
        return {}
    ts = pd.to_datetime(price_df["timestamp"] if "timestamp" in price_df.columns else price_df.index)
    s = pd.Series(price_df["close"].astype(float).values, index=ts).dropna().sort_index()
    out = {}
    last_year = s.index.max().year
    for y, g in s.groupby(s.index.year):
        if y < last_year or g.index.max().month == 12:                # chỉ năm đã kết thúc
            out[int(y)] = float(g.iloc[-1])
    return out


def historical_multiples(annual_wide: Optional[pd.DataFrame], shares_now: Optional[float],
                         price_df: Optional[pd.DataFrame], years: int = 5) -> Dict[str, Any]:
    """
    P/E, P/B cuối từng năm. Giá lịch sử là giá ĐÃ ĐIỀU CHỈNH (chia tách, cổ tức cổ phiếu) nên lợi nhuận và
    vốn chủ của từng năm được chia cho SỐ CỔ PHIẾU HIỆN TẠI để cùng cơ sở:  P/E_y = giá đc_y / (LNST_y / CP hiện tại).
    """
    out: Dict[str, Any] = {"pe": {}, "pb": {}}
    sh = _pos(shares_now)
    if annual_wide is None or annual_wide.empty or not sh:
        out.update(pe_median=None, pb_median=None)
        return out
    prices = year_end_prices(price_df)
    for key in annual_wide.index:
        y = int(key) // 10
        p = prices.get(y)
        if p is None:
            continue
        row = annual_wide.loc[key]
        ni = _pos(row.get("net_income_parent")) or _pos(row.get("net_income"))
        eq = row.get("equity")
        mi = row.get("minority_interest")
        eq_parent = _pos(eq - (mi if mi is not None and not pd.isna(mi) else 0)) if _pos(eq) else None
        if ni and PE_BOUNDS[0] <= p / (ni / sh) <= PE_BOUNDS[1]:
            out["pe"][y] = p / (ni / sh)
        if eq_parent and PB_BOUNDS[0] <= p / (eq_parent / sh) <= PB_BOUNDS[1]:
            out["pb"][y] = p / (eq_parent / sh)
    for k in ("pe", "pb"):
        recent = dict(sorted(out[k].items())[-years:])
        out[k] = recent
        out[f"{k}_median"] = float(np.median(list(recent.values()))) if len(recent) >= 3 else None
    return out


def cost_of_equity(beta: Optional[float]) -> float:
    b = min(max(beta, 0.6), 1.6) if beta is not None and not math.isnan(beta) else 1.0
    return float(min(max(RISK_FREE + b * EQUITY_PREMIUM, KE_BOUNDS[0]), KE_BOUNDS[1]))


def is_financial(industry: str = "", bank_flag: bool = False) -> bool:
    t = (industry or "").lower()
    return bank_flag or any(h in t for h in FINANCIAL_HINTS)


def fair_value(price: Optional[float], eps_ttm: Optional[float], bvps: Optional[float],
               roe_pct: Optional[float] = None, payout_pct: Optional[float] = None,
               dividend_yield_pct: Optional[float] = None, beta: Optional[float] = None,
               peer_pe: Optional[float] = None, peer_pb: Optional[float] = None, peer_n: int = 0,
               peer_group: Optional[str] = None, hist: Optional[Dict[str, Any]] = None,
               financial: bool = False) -> Dict[str, Any]:
    """Kết quả định giá đầy đủ: từng phương pháp, giá trị hợp lý tổng hợp, chênh lệch, bảng độ nhạy."""
    hist = hist or {}
    price = _pos(price)
    eps = _pos(eps_ttm)
    bv = _pos(bvps)
    methods: List[Dict[str, Any]] = []
    notes: List[str] = []

    def add(name, group, multiple, base, base_label, source):
        methods.append({"name": name, "group": group, "multiple": multiple, "base": base,
                        "base_label": base_label, "fair": multiple * base, "source": source})

    if eps:
        if hist.get("pe_median"):
            yrs = ", ".join(str(y) for y in hist["pe"])
            add("P/E lịch sử", "pe", hist["pe_median"], eps, "EPS TTM", f"Trung vị P/E cuối năm {yrs}")
        if _pos(peer_pe) and peer_n >= 3:
            add("P/E ngành", "pe", float(peer_pe), eps, "EPS TTM", f"Trung vị {peer_group or 'nhóm ngành'} ({peer_n} DN)")
    else:
        notes.append("EPS TTM không dương (doanh nghiệp lỗ hoặc thiếu số liệu) → bỏ các phương pháp P/E.")
    if bv:
        if hist.get("pb_median"):
            yrs = ", ".join(str(y) for y in hist["pb"])
            add("P/B lịch sử", "pb", hist["pb_median"], bv, "BVPS", f"Trung vị P/B cuối năm {yrs}")
        roe = (roe_pct or 0) / 100 if roe_pct is not None else None
        if roe is not None and roe > 0:
            ke = cost_of_equity(beta)
            payout = min(max((payout_pct or 40.0) / 100, 0.0), 1.0)
            g = min(roe * (1 - payout), G_CAP, ke - 0.02)
            jpb = (roe - g) / (ke - g)
            if jpb > 0:
                add("P/B theo ROE", "pb", float(jpb), bv, "BVPS",
                    f"(ROE {roe * 100:.1f}% − g {g * 100:.1f}%) / (Ke {ke * 100:.1f}% − g)")
    else:
        notes.append("Không có BVPS → bỏ các phương pháp P/B.")

    if not methods or not price:
        return {"available": False, "methods": methods, "notes": notes or ["Không đủ dữ liệu để định giá."],
                "price": price}

    gw = {"pe": 0.4, "pb": 0.6} if financial else {"pe": 0.6, "pb": 0.4}
    present = {m["group"] for m in methods}
    total_gw = sum(gw[g] for g in present)
    for g in present:
        ms = [m for m in methods if m["group"] == g]
        for m in ms:
            m["weight"] = gw[g] / total_gw / len(ms)
    fv = float(sum(m["fair"] * m["weight"] for m in methods))
    for m in methods:
        m["upside"] = (m["fair"] / price - 1) * 100
    upside = (fv / price - 1) * 100
    dy = float(dividend_yield_pct) if dividend_yield_pct is not None and not math.isnan(dividend_yield_pct) else 0.0

    # Độ nhạy: hệ số định giá ±15% / ±30% × cơ sở (EPS hoặc BVPS) ±10%
    sens_rows = []
    for mult_chg in (-0.3, -0.15, 0.0, 0.15, 0.3):
        row = {"mult_chg": mult_chg}
        for base_chg in (-0.1, 0.0, 0.1):
            row[base_chg] = fv * (1 + mult_chg) * (1 + base_chg)
        sens_rows.append(row)

    spread = max(m["fair"] for m in methods) / min(m["fair"] for m in methods) if len(methods) > 1 else 1.0
    if spread > 2:
        notes.append(f"Các phương pháp chênh nhau lớn (cao nhất gấp {spread:.1f} lần thấp nhất) – độ tin cậy thấp.")
    confidence = "Cao" if len(methods) >= 3 and spread <= 1.5 else "Trung bình" if len(methods) >= 2 and spread <= 2 else "Thấp"

    return {
        "available": True, "price": price, "fair_value": fv, "upside": upside,
        "dividend_yield": dy, "expected_return": upside + dy,
        "methods": methods, "group_weights": {g: gw[g] / total_gw for g in present},
        "financial": financial, "sensitivity": sens_rows, "confidence": confidence, "notes": notes,
        "assumptions": {"risk_free": RISK_FREE, "equity_premium": EQUITY_PREMIUM,
                        "ke": cost_of_equity(beta), "beta": beta,
                        "beta_used": min(max(beta, 0.6), 1.6) if beta is not None and not math.isnan(beta) else 1.0,
                        "g_cap": G_CAP},
    }
