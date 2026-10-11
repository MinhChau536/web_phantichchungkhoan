"""
Financial Health Score (0–100) – chấm điểm sức khỏe tài chính từ BCTC năm, giải thích được từng điểm.

Đầu vào lấy từ bộ tính chỉ số sẵn có (analytics.financial_ratios.compute_ratios) – không tính lại.

Doanh nghiệp phi tài chính (trọng số mặc định, cấu hình ở config/investment_model.py):
  Sinh lời 25% (ROE, ROA, biên LN ròng) · Tăng trưởng 20% (doanh thu, LNST, EPS) · Thanh toán 15% (hiện hành, nhanh)
  · Cơ cấu vốn 15% (Nợ vay/VCSH, EBIT/lãi vay) · Chất lượng dòng tiền 25% (CFO/LNST, biên FCF, xu hướng CFO nhiều kỳ)
Ngân hàng: Sinh lời · Tăng trưởng · An toàn vốn (VCSH/TTS) · Chất lượng tài sản (CP dự phòng/TN hoạt động) · Huy động (LDR)
Chứng khoán / Bảo hiểm: Sinh lời · Tăng trưởng · An toàn vốn (Nợ phải trả/VCSH, VCSH/TTS) · Thanh khoản

Chuẩn hóa: mỗi chỉ tiêu nội suy tuyến tính giữa ngưỡng "kém" (0 điểm) và "tốt" (100 điểm), ngưỡng theo ngành.
Thiếu dữ liệu: chỉ tiêu thiếu bị loại khỏi nhóm; nhóm thiếu hẳn bị loại và trọng số chuẩn hóa lại.
Điểm tổng KHÔNG được công bố (score = None, chỉ còn điểm tham khảo) khi thiếu nhóm bắt buộc hoặc độ phủ < ngưỡng.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.investment_model import load_config

GROUP_LABELS = {
    "profitability": "Khả năng sinh lời", "growth": "Tăng trưởng", "liquidity": "Khả năng thanh toán",
    "leverage": "Cơ cấu vốn", "cashflow": "Chất lượng dòng tiền", "capital": "An toàn vốn",
    "asset_quality": "Chất lượng tài sản", "funding": "Huy động & cho vay",
}
METRIC_LABELS = {
    "roe": ("ROE", "%"), "roa": ("ROA", "%"), "net_margin": ("Biên LN ròng", "%"),
    "revenue_growth": ("Tăng trưởng doanh thu", "%"), "net_income_growth": ("Tăng trưởng LNST", "%"),
    "eps_growth": ("Tăng trưởng EPS", "%"), "current_ratio": ("Thanh toán hiện hành", "x"),
    "quick_ratio": ("Thanh toán nhanh", "x"), "debt_to_equity": ("Nợ vay / VCSH", "x"),
    "interest_coverage": ("EBIT / Chi phí lãi vay", "x"), "cfo_to_net_income": ("CFO / LNST", "x"),
    "fcf_margin": ("Biên dòng tiền tự do (FCF/DT)", "%"), "cfo_trend": ("Xu hướng CFO nhiều kỳ", ""),
    "equity_to_assets": ("VCSH / Tổng tài sản", "%"), "provision_to_income": ("CP dự phòng / TN hoạt động", "%"),
    "loan_to_deposit": ("Cho vay / Tiền gửi (LDR)", "%"), "liabilities_to_equity": ("Nợ phải trả / VCSH", "x"),
}


def lin_score(value: Optional[float], poor: float, good: float) -> Optional[float]:
    """0 điểm tại 'kém', 100 tại 'tốt' (tự hiểu chiều 'thấp là tốt' khi poor > good)."""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    if good == poor:
        return 100.0 if value >= good else 0.0
    return float(np.clip((value - poor) / (good - poor) * 100, 0, 100))


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _fmt(v, unit):
    if v is None:
        return "—"
    return f"{v:,.1f}%" if unit == "%" else f"{v:,.2f}x" if unit == "x" else f"{v:,.2f}"


class FinancialHealthEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.cfg = config or load_config()

    def _anchor(self, key: str, sector: str) -> Tuple[float, float]:
        over = self.cfg["sector_overrides"].get(sector, {})
        return tuple(over.get(key, self.cfg["anchors"][key]))

    # ── chỉ tiêu đặc biệt ──
    @staticmethod
    def _prev(wide: pd.DataFrame, col: str) -> Optional[float]:
        if wide is None or col not in wide.columns or len(wide) < 2:
            return None
        return _num(wide[col].iloc[-2])

    def _metric(self, key, value, sector, anchor_key=None, explain="") -> Dict[str, Any]:
        poor, good = self._anchor(anchor_key or key, sector)
        label, unit = METRIC_LABELS[key]
        sc = lin_score(value, poor, good)
        direction = "thấp là tốt" if poor > good else "cao là tốt"
        return {"key": key, "label": label, "value": value, "unit": unit, "score": sc,
                "display": _fmt(value, unit),
                "explain": explain or f"{label} = {_fmt(value, unit)}; 0 điểm tại {poor:g}, 100 điểm tại {good:g} ({direction})."}

    def _cfo_trend(self, wide: pd.DataFrame) -> Dict[str, Any]:
        label, _ = METRIC_LABELS["cfo_trend"]
        n = self.cfg["health"]["years_for_trend"]
        if wide is None or "cfo" not in wide.columns:
            return {"key": "cfo_trend", "label": label, "value": None, "unit": "", "score": None, "display": "—",
                    "explain": "Không có số liệu lưu chuyển tiền HĐKD."}
        cfo = wide["cfo"].dropna().tail(n)
        if len(cfo) < 3:
            return {"key": "cfo_trend", "label": label, "value": None, "unit": "", "score": None, "display": "—",
                    "explain": f"Cần ≥ 3 năm CFO (hiện có {len(cfo)})."}
        pos_share = float((cfo > 0).mean())
        rising = bool(cfo.iloc[-1] >= cfo.iloc[:-1].mean())
        sc = pos_share * 80 + (20 if rising else 0)
        return {"key": "cfo_trend", "label": label, "value": pos_share, "unit": "", "score": sc,
                "display": f"{int((cfo > 0).sum())}/{len(cfo)} năm dương" + (" · tăng" if rising else " · giảm"),
                "explain": f"{(cfo > 0).sum()}/{len(cfo)} năm CFO dương (×80) + 20 điểm nếu CFO năm gần nhất ≥ bình quân các năm trước."}

    # ── mô hình ──
    def score(self, ratios: Optional[pd.DataFrame], wide: Optional[pd.DataFrame], company: Dict[str, str]) -> Dict[str, Any]:
        ftype, sector = company.get("type", "nonfinancial"), company.get("sector", "default")
        out: Dict[str, Any] = {"type": ftype, "sector": sector, "groups": [], "notes": [], "missing": []}
        if ratios is None or ratios.empty:
            out.update(available=False, score=None, partial_score=None, coverage=0.0,
                       notes=["Không có chỉ số tài chính từ BCTC năm – không chấm điểm."])
            return out
        last = ratios.iloc[-1]
        out["period"] = int(ratios.index[-1])
        g = lambda k: _num(last.get(k))  # noqa: E731
        groups: Dict[str, List[Dict[str, Any]]] = {}

        if ftype == "nonfinancial":
            groups["profitability"] = [self._metric("roe", g("roe"), sector), self._metric("roa", g("roa"), sector),
                                       self._metric("net_margin", g("net_margin"), sector)]
            ni_prev = self._prev(wide, "net_income_parent") or self._prev(wide, "net_income")
            growth = [self._metric("revenue_growth", g("revenue_growth"), sector)]
            if ni_prev is not None and ni_prev <= 0:
                out["notes"].append("LNST năm trước ≤ 0 → tăng trưởng LNST/EPS không có ý nghĩa, loại khỏi nhóm Tăng trưởng.")
            else:
                growth += [self._metric("net_income_growth", g("net_income_growth"), sector),
                           self._metric("eps_growth", g("eps_growth"), sector)]
            groups["growth"] = growth
            groups["liquidity"] = [self._metric("current_ratio", g("current_ratio"), sector),
                                   self._metric("quick_ratio", g("quick_ratio"), sector)]
            eq = _num(wide["equity"].iloc[-1]) if wide is not None and "equity" in wide.columns else None
            de = self._metric("debt_to_equity", g("debt_to_equity"), sector)
            if eq is not None and eq <= 0:
                de.update(score=0.0, explain="VCSH âm → 0 điểm cơ cấu vốn.")
            ic_val = g("interest_coverage")
            interest = _num(wide["interest_expense"].iloc[-1]) if wide is not None and "interest_expense" in wide.columns else None
            ic = self._metric("interest_coverage", ic_val, sector)
            if ic_val is None and interest is not None and abs(interest) < 1:
                ic.update(score=100.0, display="không có lãi vay", explain="Không phát sinh chi phí lãi vay → 100 điểm.")
            elif ic_val is not None and ic_val < 0:
                ic.update(score=0.0, explain="EBIT âm → không đủ trả lãi, 0 điểm.")
            groups["leverage"] = [de, ic]
            ni = _num(wide["net_income"].iloc[-1]) if wide is not None and "net_income" in wide.columns else None
            cfo = _num(wide["cfo"].iloc[-1]) if wide is not None and "cfo" in wide.columns else None
            cfo_ni = self._metric("cfo_to_net_income", g("cfo_to_net_income"), sector)
            if ni is not None and ni <= 0:
                if cfo is not None and cfo > 0:
                    cfo_ni.update(score=60.0, display="LNST ≤ 0, CFO > 0",
                                  explain="LNST không dương nên tỷ lệ CFO/LNST không có ý nghĩa; CFO dương → 60 điểm.")
                else:
                    cfo_ni.update(score=0.0 if cfo is not None else None, display="LNST ≤ 0, CFO ≤ 0" if cfo is not None else "—",
                                  explain="LNST và CFO cùng không dương → 0 điểm.")
            groups["cashflow"] = [cfo_ni, self._metric("fcf_margin", g("fcf_margin"), sector), self._cfo_trend(wide)]
        elif ftype == "bank":
            groups["profitability"] = [self._metric("roe", g("roe"), sector, "bank_roe"),
                                       self._metric("roa", g("roa"), sector, "bank_roa")]
            groups["growth"] = [self._metric("revenue_growth", g("revenue_growth"), sector,
                                             explain=f"Tăng trưởng tổng thu nhập hoạt động = {_fmt(g('revenue_growth'), '%')}."),
                                self._metric("net_income_growth", g("net_income_growth"), sector),
                                self._metric("eps_growth", g("eps_growth"), sector)]
            for m in groups["growth"][:1]:
                m["score"] = lin_score(m["value"], *self._anchor("revenue_growth", sector))
            groups["capital"] = [self._metric("equity_to_assets", g("equity_to_assets"), sector)]
            groups["asset_quality"] = [self._metric("provision_to_income", g("provision_to_income"), sector)]
            ldr = g("loan_to_deposit")
            sc = None if ldr is None else float(100 if 75 <= ldr <= 100 else max(0, 100 - abs(ldr - (75 if ldr < 75 else 100)) * 4))
            groups["funding"] = [{"key": "loan_to_deposit", "label": METRIC_LABELS["loan_to_deposit"][0], "value": ldr,
                                  "unit": "%", "score": sc, "display": _fmt(ldr, "%"),
                                  "explain": "LDR đơn giản = cho vay KH / tiền gửi KH (khác LDR theo công thức NHNN). 100 điểm trong 75–100%; "
                                             "mỗi điểm % lệch khỏi vùng này trừ 4 điểm."}]
        else:   # chứng khoán / bảo hiểm
            groups["profitability"] = [self._metric("roe", g("roe"), sector), self._metric("roa", g("roa"), sector),
                                       self._metric("net_margin", g("net_margin"), sector)]
            groups["growth"] = [self._metric("revenue_growth", g("revenue_growth"), sector),
                                self._metric("net_income_growth", g("net_income_growth"), sector)]
            eta = None
            if wide is not None and {"equity", "total_assets"} <= set(wide.columns):
                e, t = _num(wide["equity"].iloc[-1]), _num(wide["total_assets"].iloc[-1])
                eta = e / t * 100 if e is not None and t else None
            groups["capital"] = [self._metric("liabilities_to_equity", g("liabilities_to_equity"), sector),
                                 self._metric("equity_to_assets", eta, sector)]
            groups["liquidity"] = [self._metric("current_ratio", g("current_ratio"), sector)]

        weights = self.cfg["health"]["weights"][ftype]
        total_w, acc, avail_w = sum(weights.values()), 0.0, 0.0
        for key, metrics in groups.items():
            scored = [m for m in metrics if m["score"] is not None]
            gs = float(np.mean([m["score"] for m in scored])) if scored else None
            for m in metrics:
                if m["score"] is None:
                    out["missing"].append(f"{GROUP_LABELS[key]}: {m['label']}")
            out["groups"].append({"key": key, "label": GROUP_LABELS[key], "weight": weights.get(key, 0),
                                  "score": gs, "metrics": metrics})
            if gs is not None:
                acc += gs * weights.get(key, 0)
                avail_w += weights.get(key, 0)
        coverage = avail_w / total_w if total_w else 0.0
        partial = acc / avail_w if avail_w else None
        crit_missing = [GROUP_LABELS[c] for c in self.cfg["health"]["critical_groups"][ftype]
                        if not any(gr["key"] == c and gr["score"] is not None for gr in out["groups"])]
        reliable = partial is not None and not crit_missing and coverage >= self.cfg["health"]["min_coverage"]
        if crit_missing:
            out["notes"].append("Thiếu nhóm bắt buộc: " + ", ".join(crit_missing) + " → không công bố điểm tổng.")
        if coverage < self.cfg["health"]["min_coverage"]:
            out["notes"].append(f"Độ phủ số liệu {coverage * 100:.0f}% < {self.cfg['health']['min_coverage'] * 100:.0f}% → không công bố điểm tổng.")
        out.update(available=reliable, score=round(partial, 1) if reliable else None,
                   partial_score=round(partial, 1) if partial is not None else None, coverage=coverage,
                   rating_text=self.rating_text(partial if reliable else None))
        return out

    @staticmethod
    def rating_text(score: Optional[float]) -> str:
        if score is None:
            return "Chưa đủ dữ liệu"
        return "Rất tốt" if score >= 80 else "Tốt" if score >= 65 else "Trung bình" if score >= 50 else "Yếu" if score >= 35 else "Rất yếu"
