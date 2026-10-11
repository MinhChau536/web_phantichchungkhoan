"""
Valuation Engine – GIÁ MỤC TIÊU 12 THÁNG (độc lập, minh bạch, có điểm thời gian).

Phương pháp (chỉ dùng phương pháp đủ dữ liệu và cho kết quả hợp lệ; trọng số chuẩn hóa lại):
  P/E       : Giá mục tiêu = EPS dự phóng (12T tới) × P/E mục tiêu
              EPS dự phóng = Doanh thu năm gần nhất × (1 + g) × biên LN ròng giả định / số CP lưu hành
              (ngân hàng/CTCK/bảo hiểm: LNST × (1 + g)). P/E mục tiêu = trung vị {P/E lịch sử, P/E ngành},
              kịch bản dùng phân vị 25/50/75 của P/E lịch sử. Không dùng khi EPS dự phóng ≤ 0.
  P/B       : Giá mục tiêu = BVPS dự phóng × P/B mục tiêu; BVPS dự phóng = BVPS × (1 + ROE × (1 − tỷ lệ chi trả))
              P/B mục tiêu = trung vị {P/B lịch sử, P/B ngành, P/B hợp lý (ROE − g)/(Ke − g)}.
  DCF-FCFF  : FCFF = CFO + lãi vay × (1 − t) − Capex (bình quân 3 năm); tăng trưởng giảm dần về g dài hạn trong 5 năm;
              WACC = E/(D+E)·Ke + D/(D+E)·Kd·(1 − t); giá trị VCSH = EV − nợ vay + tiền & ĐTNH − lợi ích CĐ thiểu số.
              Giá trị nội tại hôm nay → giá mục tiêu 12T = nội tại × (1 + Ke) − cổ tức dự kiến. Chỉ cho DN phi tài chính.
  EV/EBITDA : EV mục tiêu = EBITDA dự phóng × EV/EBITDA lịch sử (trung vị/phân vị); VCSH = EV − nợ vay ròng − CĐ thiểu số.
Kịch bản Bear/Base/Bull: thay đổi BỘ GIẢ ĐỊNH (tăng trưởng, biên lợi nhuận, bội số theo phân vị, Ke, ROE) – không
cộng/trừ tùy ý vào giá. Không xác định được giá đáng tin cậy → "CHƯA ĐỦ CƠ SỞ ĐỊNH GIÁ".
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from config.investment_model import load_config

FINANCIAL_TYPES = ("bank", "securities", "insurance")
NOT_ENOUGH = "CHƯA ĐỦ CƠ SỞ ĐỊNH GIÁ"
SCEN = ("bear", "base", "bull")
SCEN_LABEL = {"bear": "Thận trọng (Bear)", "base": "Cơ sở (Base)", "bull": "Tích cực (Bull)"}


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _col(w: pd.DataFrame, c: str) -> pd.Series:
    return w[c].astype(float) if w is not None and c in w.columns else pd.Series(index=getattr(w, "index", None), dtype=float)


def _last(s: pd.Series) -> Optional[float]:
    s = s.dropna()
    return float(s.iloc[-1]) if not s.empty else None


def _cagr(s: pd.Series, years: int = 3) -> Optional[float]:
    s = s.dropna()
    if len(s) < 2:
        return None
    n = min(years, len(s) - 1)
    a, b = float(s.iloc[-1 - n]), float(s.iloc[-1])
    if a <= 0 or b <= 0:
        return None
    return (b / a) ** (1 / n) - 1


# ─────────────────────────────────────────────────────────────────────────────
# Điểm thời gian – không dùng dữ liệu công bố sau ngày định giá
# ─────────────────────────────────────────────────────────────────────────────

def annual_available(period_key: int, as_of: pd.Timestamp, release_month: int = 4) -> bool:
    """BCTC năm kiểm toán của năm y được coi là đã công bố từ ngày 1/{release_month}/(y+1)."""
    y = int(period_key) // 10
    return as_of >= pd.Timestamp(year=y + 1, month=release_month, day=1)


def point_in_time(wide: Optional[pd.DataFrame], ratios: Optional[pd.DataFrame], price_df: Optional[pd.DataFrame],
                  as_of: pd.Timestamp, release_month: int = 4):
    keep = lambda df: df[[annual_available(k, as_of, release_month) for k in df.index]] if df is not None and not df.empty else df  # noqa: E731
    px = None
    if price_df is not None and not price_df.empty:
        ts = pd.to_datetime(price_df["timestamp"] if "timestamp" in price_df.columns else price_df.index)
        px = price_df[(ts <= as_of).to_numpy()]
    return keep(wide), keep(ratios), px


# ─────────────────────────────────────────────────────────────────────────────
# Bội số lịch sử (giá cuối năm đã điều chỉnh, số CP hiện tại)
# ─────────────────────────────────────────────────────────────────────────────

def year_end_prices(price_df: Optional[pd.DataFrame]) -> Dict[int, float]:
    if price_df is None or price_df.empty or "close" not in price_df.columns:
        return {}
    ts = pd.to_datetime(price_df["timestamp"] if "timestamp" in price_df.columns else price_df.index)
    s = pd.Series(price_df["close"].astype(float).values, index=ts).dropna().sort_index()
    if s.empty:
        return {}
    last_year = s.index.max().year
    return {int(y): float(g.iloc[-1]) for y, g in s.groupby(s.index.year) if y < last_year or g.index.max().month == 12}


def historical_multiples(wide: Optional[pd.DataFrame], shares: Optional[float], price_df: Optional[pd.DataFrame],
                         years: int = 5) -> Dict[str, Dict[int, float]]:
    out: Dict[str, Dict[int, float]] = {"pe": {}, "pb": {}, "ev_ebitda": {}}
    if wide is None or wide.empty or not shares or shares <= 0:
        return out
    prices = year_end_prices(price_df)
    for k in wide.index:
        y = int(k) // 10
        p = prices.get(y)
        if p is None:
            continue
        r = wide.loc[k]
        ni = _num(r.get("net_income_parent")) or _num(r.get("net_income"))
        eq = _num(r.get("equity"))
        mi = _num(r.get("minority_interest")) or 0.0
        mcap = p * shares
        if ni and ni > 0 and 2 <= mcap / ni <= 60:
            out["pe"][y] = mcap / ni
        if eq and eq - mi > 0 and 0.2 <= mcap / (eq - mi) <= 15:
            out["pb"][y] = mcap / (eq - mi)
        op, dep = _num(r.get("operating_profit")), _num(r.get("depreciation"))
        if op is None and _num(r.get("profit_before_tax")) is not None:     # EBIT ≈ LNTT + lãi vay
            op = _num(r.get("profit_before_tax")) + abs(_num(r.get("interest_expense")) or 0)
        if op is not None:
            ebitda = op + abs(dep or 0)
            debt = abs(_num(r.get("short_term_debt")) or 0) + abs(_num(r.get("long_term_debt")) or 0)
            cash = (_num(r.get("cash")) or 0) + (_num(r.get("short_term_investments")) or 0)
            ev = mcap + debt - cash + mi
            if ebitda > 0 and 1 <= ev / ebitda <= 40:
                out["ev_ebitda"][y] = ev / ebitda
    return {k: dict(sorted(v.items())[-years:]) for k, v in out.items()}


def _pct(vals: List[float], q: float) -> Optional[float]:
    return float(np.percentile(vals, q)) if len(vals) >= 3 else None


# ─────────────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────────────

class ValuationEngine12M:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.cfg = config or load_config()
        self.v = self.cfg["valuation"]

    def ke(self, beta: Optional[float], shift: float = 0.0) -> float:
        lo, hi = self.v["beta_bounds"]
        b = min(max(beta, lo), hi) if beta is not None and not math.isnan(beta) else 1.0
        k = self.v["risk_free"] + b * self.v["equity_premium"] + shift
        return float(min(max(k, self.v["ke_bounds"][0]), self.v["ke_bounds"][1] + 0.01))

    def value(self, *, price: Optional[float], price_date: Optional[pd.Timestamp], wide: Optional[pd.DataFrame],
              ratios: Optional[pd.DataFrame], shares: Optional[float], company: Dict[str, str],
              beta: Optional[float] = None, peers: Optional[Dict[str, Any]] = None,
              price_df: Optional[pd.DataFrame] = None, risk_level: Optional[str] = None,
              as_of: Optional[pd.Timestamp] = None) -> Dict[str, Any]:
        peers = peers or {}
        ftype = company.get("type", "nonfinancial")
        fin = ftype in FINANCIAL_TYPES
        res: Dict[str, Any] = {"available": False, "status": NOT_ENOUGH, "type": ftype, "financial": fin, "methods": [], "invalid": [],
                               "notes": [], "horizon_months": self.v["horizon_months"], "price": _num(price),
                               "price_date": str(pd.Timestamp(price_date).date()) if price_date is not None else None}
        if as_of is not None:
            wide, ratios, price_df = point_in_time(wide, ratios, price_df, pd.Timestamp(as_of))
            res["as_of"] = str(pd.Timestamp(as_of).date())
        price = _num(price)
        if not price or price <= 0:
            res["notes"].append("Thiếu thị giá hợp lệ → không tính giá mục tiêu và upside.")
            return res
        if wide is None or wide.empty or not shares or shares <= 0:
            res["notes"].append("Thiếu BCTC năm hoặc số cổ phiếu lưu hành.")
            return res

        last_key = int(wide.index[-1])
        res["data_period"] = f"{last_key // 10}"
        res["data_date"] = f"31/12/{last_key // 10}"
        ref_date = pd.Timestamp(as_of) if as_of is not None else (pd.Timestamp(price_date) if price_date is not None else pd.Timestamp.now())
        months_old = (ref_date.year - last_key // 10) * 12 + ref_date.month - 12
        stale = months_old > self.v["stale_months"]
        if stale:
            res["notes"].append(f"BCTC năm gần nhất ({last_key // 10}) đã cũ ~{months_old} tháng → giảm độ tin cậy.")

        r_last = ratios.iloc[-1] if ratios is not None and not ratios.empty else pd.Series(dtype=float)
        ni_s = _col(wide, "net_income_parent")
        if ni_s.dropna().empty:
            ni_s = _col(wide, "net_income")
        rev_key = "total_operating_income" if fin and "total_operating_income" in wide.columns else "revenue"
        rev_s = _col(wide, rev_key)
        ni0, rev0 = _last(ni_s), _last(rev_s)
        eq_s = _col(wide, "equity") - _col(wide, "minority_interest").fillna(0)
        eq0 = _last(eq_s)
        payout_hist = ratios["dividend_payout"].dropna().tail(3) if ratios is not None and "dividend_payout" in ratios else pd.Series(dtype=float)
        payout = float(np.clip(payout_hist.mean() / 100, 0, 1)) if not payout_hist.empty else 0.3
        roe0 = _num(r_last.get("roe"))
        hist = historical_multiples(wide, shares, price_df)
        res["history"] = hist

        # ── giả định tăng trưởng gốc ──
        g_hist = (_cagr(ni_s) if fin else _cagr(rev_s)) or (_cagr(rev_s) if fin else _cagr(ni_s))
        g_sust = (roe0 / 100) * (1 - payout) if roe0 is not None else None
        parts = [(0.6, g_hist), (0.4, g_sust)]
        parts = [(w, x) for w, x in parts if x is not None]
        lo_g, hi_g = self.v["growth_bounds"]
        g_base = float(np.clip(sum(w * x for w, x in parts) / sum(w for w, _ in parts), lo_g, hi_g)) if parts else 0.0
        margins = (ni_s / rev_s).replace([np.inf, -np.inf], np.nan).dropna().tail(3)
        m_base = float(margins.mean()) if not margins.empty else None
        # Cổ tức tiền mặt/CP = cổ tức đã trả (LCTT) / số CP hiện tại (cùng cơ sở với giá đã điều chỉnh)
        dps_s = (_col(wide, "dividends_paid").abs() / shares).dropna().tail(3)
        dps = float(dps_s.iloc[-1]) if len(dps_s) and (dps_s > 0).sum() >= 2 else 0.0
        if dps < price * 0.003:          # < 0,3% thị giá: thường chỉ là cổ tức trả cho CĐ thiểu số ở công ty con
            dps = 0.0
        div_ok = dps > 0
        if not div_ok:
            res["notes"].append("Không đủ cơ sở dự phóng cổ tức tiền mặt (chưa trả đều ≥ 2/3 năm gần nhất) → tổng lợi nhuận kỳ vọng = upside giá.")
        res["assumptions"] = {
            "g_hist": g_hist, "g_sustainable": g_sust, "g_base": g_base, "net_margin_base": m_base, "payout": payout,
            "roe": roe0, "beta": beta, "ke": self.ke(beta), "dps_expected": dps, "shares": shares,
            "basis_growth": "LNST" if fin else "doanh thu",
            "risk_free": self.v["risk_free"], "equity_premium": self.v["equity_premium"],
            "beta_used": min(max(beta, self.v["beta_bounds"][0]), self.v["beta_bounds"][1]) if beta is not None and not math.isnan(beta) else 1.0,
        }

        sc_cfg = self.v["scenarios"]
        scen_rows: Dict[str, Dict[str, Any]] = {}
        for s in SCEN:
            p = sc_cfg[s]
            g = float(np.clip(g_base + p["growth_shift"], lo_g, hi_g))
            ke_s = self.ke(beta, p["ke_shift"])
            if fin:
                ni_f = ni0 * (1 + g) * p["margin_factor"] if ni0 is not None else None
                margin_s = None
            else:
                margin_s = m_base * p["margin_factor"] if m_base is not None else None
                ni_f = rev0 * (1 + g) * margin_s if rev0 is not None and margin_s is not None else None
            eps_f = ni_f / shares if ni_f is not None else None
            roe_s = (roe0 + p["roe_shift"]) if roe0 is not None else None
            scen_rows[s] = {"growth": g, "margin": margin_s, "ke": ke_s, "eps_fwd": eps_f, "roe": roe_s, "methods": {}}

            # P/E
            pe_hist = list(hist["pe"].values())
            refs_pe = [x for x in [_pct(pe_hist, 50), _num(peers.get("pe")) if (peers.get("n_pe") or peers.get("n") or 0) >= 3 else None] if x]
            if eps_f is not None and eps_f > 0 and refs_pe:
                pe_t = float(np.median(refs_pe))
                if len(pe_hist) >= 3 and p["multiple_pct"] != 50:
                    pe_t *= float(np.clip(_pct(pe_hist, p["multiple_pct"]) / _pct(pe_hist, 50), 0.7, 1.4))
                if risk_level in ("Cao", "Nghiêm trọng"):
                    pe_t *= 0.9
                if g < 0:
                    pe_t *= 0.9
                scen_rows[s]["methods"]["pe"] = {"target": eps_f * pe_t, "multiple": pe_t, "base": eps_f,
                                                 "base_label": "EPS dự phóng"}
            # P/B
            if eq0 is not None and eq0 > 0 and roe_s is not None:
                bvps = eq0 / shares
                bvps_f = bvps * (1 + (roe_s / 100) * (1 - payout))
                g_t = self.v["terminal_growth"][s]
                jpb = (roe_s / 100 - g_t) / (ke_s - g_t) if ke_s - g_t >= 0.02 and roe_s / 100 > g_t else None
                pb_hist = list(hist["pb"].values())
                h_pb = _pct(pb_hist, p["multiple_pct"]) if len(pb_hist) >= 3 else None
                refs_pb = [x for x in [h_pb, _num(peers.get("pb")) if (peers.get("n_pb") or peers.get("n") or 0) >= 3 else None, jpb] if x and x > 0]
                if refs_pb:
                    pb_t = float(np.median(refs_pb))
                    scen_rows[s]["methods"]["pb"] = {"target": bvps_f * pb_t, "multiple": pb_t, "base": bvps_f,
                                                     "base_label": "BVPS dự phóng", "justified_pb": jpb}
            if not fin:
                dcf = self._dcf(wide, shares, price, g, ke_s, self.v["terminal_growth"][s], dps)
                if dcf.get("valid"):
                    scen_rows[s]["methods"]["dcf"] = dcf
                elif s == "base":
                    res["invalid"].append(("DCF", dcf.get("reason")))
                ev = self._ev_ebitda(wide, shares, hist, g, p)
                if ev.get("valid"):
                    scen_rows[s]["methods"]["ev_ebitda"] = ev
                elif s == "base":
                    res["invalid"].append(("EV/EBITDA", ev.get("reason")))
        base_methods = scen_rows["base"]["methods"]
        if "pe" not in base_methods:
            res["invalid"].append(("P/E", "EPS dự phóng ≤ 0 hoặc không có P/E tham chiếu (lịch sử ≥ 3 năm / ngành ≥ 3 DN)"))
        if "pb" not in base_methods:
            res["invalid"].append(("P/B", "Thiếu VCSH dương/ROE hoặc không có P/B tham chiếu"))

        # ── loại kết quả bất thường ──
        lo_b, hi_b = self.v["sanity_band"]
        for k, m in list(base_methods.items()):
            ratio = m["target"] / price
            if not (lo_b <= ratio <= hi_b) or m["target"] <= 0:
                res["invalid"].append((k.upper(), f"Kết quả {m['target']:,.0f} bất thường so với thị giá ({ratio:.2f} lần) – loại"))
                for s in SCEN:
                    scen_rows[s]["methods"].pop(k, None)
        weights_cfg = self.v["method_weights"]["financial" if fin else "nonfinancial"]
        valid = [k for k in weights_cfg if k in scen_rows["base"]["methods"]]
        if not valid:
            res["notes"].append("Không có phương pháp định giá hợp lệ.")
            res["scenarios"] = scen_rows
            return res
        tw = sum(weights_cfg[k] for k in valid)
        weights = {k: weights_cfg[k] / tw for k in valid}

        names = {"pe": "P/E dự phóng", "pb": "P/B dự phóng", "dcf": "DCF (FCFF)", "ev_ebitda": "EV/EBITDA"}
        for s in SCEN:
            ms = {k: v for k, v in scen_rows[s]["methods"].items() if k in weights}
            sw = sum(weights[k] for k in ms)
            scen_rows[s]["target"] = sum(ms[k]["target"] * weights[k] for k in ms) / sw if sw else None
            scen_rows[s]["upside"] = (scen_rows[s]["target"] / price - 1) * 100 if scen_rows[s]["target"] else None
        target = scen_rows["base"]["target"]
        methods_out = []
        for k in valid:
            m = scen_rows["base"]["methods"][k]
            methods_out.append({"key": k, "name": names[k], "multiple": m.get("multiple"), "base": m.get("base"),
                                "base_label": m.get("base_label", ""), "fair": m["target"], "weight": weights[k],
                                "upside": (m["target"] / price - 1) * 100, "source": self._source(k, m, hist, peers),
                                "detail": {kk: vv for kk, vv in m.items() if kk not in ("target",)}})
        spread = max(m["fair"] for m in methods_out) / min(m["fair"] for m in methods_out)
        tv_flag = any(m["key"] == "dcf" and m["detail"].get("tv_share", 0) > self.v["dcf_max_tv_share"] for m in methods_out)
        n = len(methods_out)
        conf = "Cao" if n >= 3 and spread <= 1.6 else "Trung bình" if n >= 2 and spread <= 2.2 else "Thấp"
        if stale or tv_flag:
            conf = {"Cao": "Trung bình", "Trung bình": "Thấp"}.get(conf, conf)
        if tv_flag:
            res["notes"].append("DCF: giá trị cuối kỳ chiếm > {:.0f}% EV → nhạy với giả định dài hạn.".format(self.v["dcf_max_tv_share"] * 100))
        if spread > 2.2:
            res["notes"].append(f"Các phương pháp chênh nhau lớn (cao/thấp = {spread:.1f} lần).")
        upside = (target / price - 1) * 100
        exp_ret = ((target + dps - price) / price) * 100
        intrinsic = target / (1 + self.ke(beta))
        res.update(
            available=conf != "Thấp", status="OK" if conf != "Thấp" else NOT_ENOUGH, confidence=conf,
            target_12m=target, fair_value=target, intrinsic_today=intrinsic, upside=upside,
            expected_dividend=dps, dividends_included=div_ok, expected_return=exp_ret,
            dividend_yield=dps / price * 100, methods=methods_out, weights=weights, scenarios=scen_rows,
            group_weights={"pe": sum(w for k, w in weights.items() if k in ("pe",)),
                           "pb": sum(w for k, w in weights.items() if k in ("pb",))},
            financial=fin, sensitivity=self._sensitivity(target),
        )
        if conf == "Thấp":
            res["notes"].append("Độ tin cậy định giá thấp (ít phương pháp hợp lệ, phân tán lớn hoặc dữ liệu cũ) → "
                                f"trạng thái: {NOT_ENOUGH}. Các con số chỉ để tham khảo.")
        return res

    # ── DCF-FCFF ──
    def _dcf(self, wide, shares, price, g1, ke, g_t, dps) -> Dict[str, Any]:
        t = self.v["tax_rate"]
        need = {"cfo", "capex"}
        if not need <= set(wide.columns):
            return {"valid": False, "reason": "Thiếu CFO/Capex"}
        df = wide[["cfo", "capex"]].dropna().tail(3)
        if len(df) < 3:
            return {"valid": False, "reason": "Cần ≥ 3 năm CFO và Capex"}
        interest = _col(wide, "interest_expense").abs().reindex(df.index).fillna(0)
        fcff_hist = df["cfo"] + interest * (1 - t) - df["capex"].abs()
        fcff0 = float(fcff_hist.mean())
        if fcff0 <= 0:
            return {"valid": False, "reason": f"FCFF bình quân 3 năm âm ({fcff0 / 1e9:,.0f} tỷ)"}
        debt = abs(_last(_col(wide, "short_term_debt")) or 0) + abs(_last(_col(wide, "long_term_debt")) or 0)
        cash = (_last(_col(wide, "cash")) or 0) + (_last(_col(wide, "short_term_investments")) or 0)
        mi = _last(_col(wide, "minority_interest")) or 0
        debt_s = (_col(wide, "short_term_debt").abs().fillna(0) + _col(wide, "long_term_debt").abs().fillna(0)).tail(2)
        int_last = _last(_col(wide, "interest_expense").abs())
        kd = float(np.clip(int_last / debt_s.mean(), *self.v["kd_bounds"])) if int_last and debt_s.mean() > 0 else self.v["kd_bounds"][0]
        e = price * shares
        wacc = e / (e + debt) * ke + debt / (e + debt) * kd * (1 - t)
        if wacc - g_t < self.v["dcf_min_spread"]:
            return {"valid": False, "reason": f"WACC {wacc * 100:.1f}% − g {g_t * 100:.1f}% quá nhỏ"}
        years = self.v["dcf_years"]
        fcff, pv = fcff0, 0.0
        flows = []
        for i in range(1, years + 1):
            gi = g1 + (g_t - g1) * (i - 1) / max(years - 1, 1)
            fcff *= (1 + gi)
            pv += fcff / (1 + wacc) ** i
            flows.append(fcff)
        tv = fcff * (1 + g_t) / (wacc - g_t)
        pv_tv = tv / (1 + wacc) ** years
        ev = pv + pv_tv
        equity = ev - debt + cash - mi
        if equity <= 0:
            return {"valid": False, "reason": "Giá trị vốn chủ ước tính ≤ 0"}
        intrinsic = equity / shares
        target = intrinsic * (1 + ke) - dps
        return {"valid": True, "target": target, "intrinsic": intrinsic, "multiple": None, "base": fcff0 / shares,
                "base_label": "FCFF bình quân 3 năm/CP", "fcff_avg": fcff0, "wacc": wacc, "kd": kd, "g_terminal": g_t, "ev": ev,
                "tv_share": pv_tv / ev, "net_debt": debt - cash, "flows": flows}

    # ── EV/EBITDA ──
    def _ev_ebitda(self, wide, shares, hist, g, p) -> Dict[str, Any]:
        op, dep = _last(_col(wide, "operating_profit")), _last(_col(wide, "depreciation"))
        if op is None and _last(_col(wide, "profit_before_tax")) is not None:     # EBIT ≈ LNTT + lãi vay
            op = _last(_col(wide, "profit_before_tax")) + abs(_last(_col(wide, "interest_expense")) or 0)
        if op is None:
            return {"valid": False, "reason": "Thiếu lợi nhuận HĐKD và lợi nhuận trước thuế"}
        ebitda = op + abs(dep or 0)
        if ebitda <= 0:
            return {"valid": False, "reason": "EBITDA ≤ 0"}
        vals = list(hist["ev_ebitda"].values())
        if len(vals) < 3:
            return {"valid": False, "reason": "Cần ≥ 3 năm EV/EBITDA lịch sử"}
        mult = _pct(vals, p["multiple_pct"])
        ebitda_f = ebitda * (1 + g) * p["margin_factor"]
        debt = abs(_last(_col(wide, "short_term_debt")) or 0) + abs(_last(_col(wide, "long_term_debt")) or 0)
        cash = (_last(_col(wide, "cash")) or 0) + (_last(_col(wide, "short_term_investments")) or 0)
        mi = _last(_col(wide, "minority_interest")) or 0
        equity = ebitda_f * mult - (debt - cash) - mi
        if equity <= 0:
            return {"valid": False, "reason": "Giá trị vốn chủ ≤ 0"}
        return {"valid": True, "target": equity / shares, "multiple": mult, "base": ebitda_f / shares,
                "base_label": "EBITDA dự phóng/CP", "ebitda_fwd": ebitda_f, "net_debt": debt - cash}

    @staticmethod
    def _source(k, m, hist, peers) -> str:
        def hist_txt(key, fmt):
            v = hist.get(key) or {}
            return (f"{key.upper().replace('_', '/')} lịch sử " + ", ".join(f"{y}: {x:{fmt}}x" for y, x in v.items())
                    + f" (trung vị {np.median(list(v.values())):{fmt}}x)") if len(v) >= 3 else None
        if k == "pe":
            refs = [hist_txt("pe", ".1f"), f"P/E ngành {peers['pe']:.1f}x ({peers.get('group')})" if peers.get("pe") else None]
            return "P/E mục tiêu = trung vị của: " + "; ".join(r for r in refs if r) + f" → {m['multiple']:.1f}x"
        if k == "pb":
            j = m.get("justified_pb")
            refs = [hist_txt("pb", ".2f"), f"P/B ngành {peers['pb']:.2f}x" if peers.get("pb") else None,
                    f"P/B hợp lý (ROE − g)/(Ke − g) = {j:.2f}x" if j else None]
            return "P/B mục tiêu = trung vị của: " + "; ".join(r for r in refs if r) + f" → {m['multiple']:.2f}x"
        if k == "dcf":
            return (f"WACC {m['wacc'] * 100:.1f}% (Kd {m['kd'] * 100:.1f}%), g dài hạn {m['g_terminal'] * 100:.1f}%, "
                    f"giá trị cuối kỳ {m['tv_share'] * 100:.0f}% EV; giá mục tiêu = nội tại {m['intrinsic']:,.0f} × (1 + Ke) − cổ tức")
        if k == "ev_ebitda":
            return hist_txt("ev_ebitda", ".1f") or ""
        return ""

    @staticmethod
    def _sensitivity(target: float) -> List[Dict[str, Any]]:
        rows = []
        for mult_chg in (-0.3, -0.15, 0.0, 0.15, 0.3):
            rows.append({"mult_chg": mult_chg, **{b: target * (1 + mult_chg) * (1 + b) for b in (-0.1, 0.0, 0.1)}})
        return rows
