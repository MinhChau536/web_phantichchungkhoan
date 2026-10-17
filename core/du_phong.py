"""
core/du_phong.py – gộp từ 1 module (15/10/2026).

MỤC LỤC
  • analytics/financial_forecast.py – Forecast Engine – dự báo tài chính 12 tháng (NTM) và 3–5 năm, 3 kịch bản Bear/Base/Bull.
      hàm/lớp chính: robust_growth, quarters_available, annual_available_only, build_ttm, FinancialForecaster, backtest_forecast
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/financial_forecast.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Forecast Engine – dự báo tài chính 12 tháng (NTM) và 3–5 năm, 3 kịch bản Bear/Base/Bull.

Đầu vào: BCTC NĂM và (tùy chọn) QUÝ đã chuẩn hóa (bảng rộng canonical, khóa kỳ năm*10+quý, VND) – số quý phải là
số TỪNG QUÝ (core/du_lieu.py); số cổ phiếu; loại doanh nghiệp (classify_company); ngày dự báo as_of.

Nguyên tắc
  • KHÔNG nhìn trước (look-ahead): chỉ dùng BCTC năm công bố trước as_of (annual_available) và BCTC quý sau
    QUARTER_RELEASE_LAG_DAYS; mọi tham số ước lượng chỉ từ dữ liệu đó.
  • KHÔNG bịa số: thiếu số liệu gốc (doanh thu/LNST/VCSH…) ⇒ chỉ tiêu đó = None kèm lý do; thiếu tham số phụ
    (thuế suất, tỷ lệ chia cổ tức, capex…) ⇒ dùng giả định MẶC ĐỊNH có ghi rõ trong 'warnings' và 'drivers'.
  • Kỳ gốc: TTM (4 quý gần nhất) nếu mới hơn năm tài chính gần nhất và số quý hợp lệ; nếu không: năm tài chính.
  • Mô hình theo ngành:
      - Phi tài chính: doanh thu → biên EBITDA → khấu hao → EBIT → lãi vay → LNTT → thuế → LNST → EPS;
        FCFF = EBIT(1−t) + khấu hao − capex − ΔVốn lưu động; VCSH = VCSH trước + LNST mẹ × (1 − tỷ lệ chia cổ tức).
      - Ngân hàng: tổng thu nhập hoạt động (TOI) tăng theo dư nợ/TOI → lợi nhuận trước dự phòng (PPOP) theo biên
        lịch sử → chi phí dự phòng = chi phí tín dụng × dư nợ bình quân → LNTT. EBITDA/FCFF: không áp dụng.
      - Chứng khoán / bảo hiểm: lợi nhuận biến động theo thị trường → mô hình ROE: LNST mẹ = ROE chuẩn hóa
        (trung vị lịch sử) × VCSH đầu kỳ. EBITDA/FCFF: không áp dụng.
  • Tăng trưởng năm 1 = w × trung vị tăng trưởng YoY lịch sử + (1 − w) × tăng trưởng TTM so cùng kỳ, chặn biên;
    giảm dần tuyến tính về tăng trưởng dài hạn (terminal growth của kịch bản) ở năm cuối.
  • NTM (12 tháng tới tính từ as_of) = nội suy tuyến tính trên đường dự báo năm theo số tháng từ cuối kỳ gốc.

Đầu ra chuẩn hóa ('valuation_inputs') phục vụ P/E Forward (eps_fwd), P/B–ROE (roe_fwd, bvps_fwd), EV/EBITDA
(ebitda_fwd) và DCF (fcff_path, terminal_growth). Module này KHÔNG thay đổi Valuation Engine.
"""


import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.phan_tich_co_ban import core_ebit_ebitda, ebit_ebitda
from core.cau_hinh import load_config
from core.cau_hinh import settings

SCEN = ("bear", "base", "bull")
SCEN_LABEL = {"bear": "Thận trọng (Bear)", "base": "Cơ sở (Base)", "bull": "Tích cực (Bull)"}
FIN_ROE_TYPES = ("securities", "insurance")


# ─────────────────────────────────────────────────────────────────────────────
# Tiện ích
# ─────────────────────────────────────────────────────────────────────────────

def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _col(w: Optional[pd.DataFrame], c: str) -> pd.Series:
    if w is None or c not in w.columns:
        return pd.Series(dtype=float, index=getattr(w, "index", None))
    return pd.to_numeric(w[c], errors="coerce").astype(float)


def _period_end(key: int) -> pd.Timestamp:
    y, q = divmod(int(key), 10)
    return pd.Timestamp(year=y, month=12, day=31) if q == 0 else \
        pd.Timestamp(year=y, month=3 * q, day=1) + pd.offsets.MonthEnd(0)


def _median_ratio(num: pd.Series, den: pd.Series, n: int, absolute_num: bool = False) -> Tuple[Optional[float], int]:
    """Trung vị num/den trên n kỳ gần nhất có đủ hai số (den ≠ 0)."""
    a = num.abs() if absolute_num else num
    df = pd.concat([a, den], axis=1).dropna()
    df = df[df.iloc[:, 1] != 0].tail(n)
    if df.empty:
        return None, 0
    return float((df.iloc[:, 0] / df.iloc[:, 1]).median()), len(df)


def robust_growth(s: pd.Series, n: int) -> Tuple[Optional[float], int]:
    """Trung vị tăng trưởng YoY (chỉ các cặp năm liền nhau cùng dương) trên tối đa n năm gần nhất."""
    s = s.dropna()
    s = s[[int(k) % 10 == 0 for k in s.index]] if len(s) else s
    vals = []
    keys = list(s.index)
    for a, b in zip(keys[:-1], keys[1:]):
        if int(b) - int(a) == 10 and s[a] > 0 and s[b] > 0:
            vals.append(s[b] / s[a] - 1)
    vals = vals[-n:]
    return (float(np.median(vals)), len(vals)) if vals else (None, 0)


def _yoy_list(s: pd.Series, n: int) -> List[float]:
    """Tăng trưởng YoY của n năm gần nhất (chỉ cặp năm liền nhau, năm trước dương)."""
    s = s.dropna()
    s = s[[int(k) % 10 == 0 for k in s.index]] if len(s) else s
    keys = list(s.index)
    out = [s[b] / s[a] - 1 for a, b in zip(keys[:-1], keys[1:]) if int(b) - int(a) == 10 and s[a] > 0]
    return out[-n:]


def quarters_available(qwide: Optional[pd.DataFrame], as_of: Optional[pd.Timestamp],
                       lag_days: Optional[int] = None) -> Optional[pd.DataFrame]:
    """Chỉ giữ quý đã công bố trước as_of (cuối quý + độ trễ công bố)."""
    if qwide is None or qwide.empty:
        return qwide
    keys = np.asarray(qwide.index, dtype=int)
    q = qwide[keys % 10 > 0]
    if as_of is None:
        return q
    lag = settings.QUARTER_RELEASE_LAG_DAYS if lag_days is None else lag_days
    keep = [as_of >= _period_end(k) + pd.Timedelta(days=lag) for k in q.index]
    return q[keep]


def annual_available_only(wide: Optional[pd.DataFrame], as_of: Optional[pd.Timestamp]) -> Optional[pd.DataFrame]:
    if wide is None or wide.empty:
        return wide
    keys = np.asarray(wide.index, dtype=int)
    a = wide[keys % 10 == 0]
    if as_of is None:
        return a
    from core.dinh_gia import annual_available
    actual = getattr(wide, "attrs", {}).get("available_at", {})
    return a[[annual_available(k, as_of, None, actual.get(k, actual.get(str(k)))) for k in a.index]]


FLOW_ITEMS = ("revenue", "total_operating_income", "net_interest_income", "provision_expense", "profit_before_tax",
              "income_tax", "net_income", "net_income_parent", "interest_expense", "depreciation", "capex",
              "dividends_paid", "cfo", "operating_profit", "financial_expense",
              "gross_profit", "selling_expense", "admin_expense", "financial_income", "associates_income")


def build_ttm(q: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """TTM từ 4 quý LIÊN TIẾP gần nhất: chỉ tiêu dòng = tổng 4 quý (đủ cả 4 mới tính), số dư = quý cuối."""
    if q is None or len(q) < 4:
        return None
    keys = sorted(int(k) for k in q.index)
    last = keys[-1]
    y, qq = divmod(last, 10)
    need = []
    for _ in range(4):
        need.append(y * 10 + qq)
        qq -= 1
        if qq == 0:
            y, qq = y - 1, 4
    if not all(k in q.index for k in need):
        return None
    row: Dict[str, Optional[float]] = {}
    for c in q.columns:
        vals = pd.to_numeric(q.loc[need, c], errors="coerce")
        if c in FLOW_ITEMS:
            row[c] = float(vals.sum()) if vals.notna().all() else None
        else:
            row[c] = _num(q.loc[last, c])
    return {"key": last, "end": _period_end(last), "row": row, "quarters": sorted(need)}


# ─────────────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────────────

class FinancialForecaster:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.cfg = config or load_config()
        self.f = self.cfg["forecast"]
        self.tg = self.cfg["valuation"]["terminal_growth"]       # chỉ đọc – dùng cùng g dài hạn với DCF

    # ── chính ──
    def forecast(self, *, annual: Optional[pd.DataFrame], quarterly: Optional[pd.DataFrame] = None,
                 shares: Optional[float] = None, company: Optional[Dict[str, str]] = None,
                 as_of: Optional[Any] = None, quarter_basis_ok: bool = True) -> Dict[str, Any]:
        company = company or {"type": "nonfinancial", "sector": "default"}
        ftype = company.get("type", "nonfinancial")
        model = "bank" if ftype == "bank" else "roe" if ftype in FIN_ROE_TYPES else "nonfinancial"
        as_of_ts = pd.Timestamp(as_of).normalize() if as_of is not None else pd.Timestamp.now().normalize()
        res: Dict[str, Any] = {"available": False, "model": model, "type": ftype, "as_of": str(as_of_ts.date()),
                               "warnings": [], "data_gaps": [], "drivers": {}, "scenarios": {}, "valuation_inputs": {}}
        W = res["warnings"]

        a = annual_available_only(annual, as_of_ts)
        from core.dinh_gia import sanitize_annual
        a, dq = sanitize_annual(a)
        W.extend(dq)
        if a is None or a.empty:
            res["reason"] = "Không có BCTC năm đã công bố trước ngày dự báo."
            return res
        a = a.sort_index().tail(self.f["hist_years"] + 1)
        q = quarters_available(quarterly, as_of_ts)
        if not shares or shares <= 0:
            res["reason"] = "Thiếu số cổ phiếu lưu hành → không tính được EPS/BVPS."
            return res

        # ── kỳ gốc ──
        fy_key = int(a.index[-1])
        fy_end = _period_end(fy_key)
        base_row = {c: _num(a.loc[fy_key, c]) for c in a.columns}
        base = {"kind": "FY", "key": fy_key, "end": fy_end, "label": f"Năm {fy_key // 10}"}
        ttm, ttm_prev = None, None
        if q is not None and not q.empty:
            if not quarter_basis_ok:
                W.append("Số quý chưa xác định là số từng quý (độc lập) → không dùng TTM, dùng năm tài chính gần nhất.")
            else:
                ttm = build_ttm(q)
                if ttm is not None:
                    q_prev = q[[int(k) <= ttm["key"] - 10 for k in q.index]]
                    ttm_prev = build_ttm(q_prev) if q_prev is not None and len(q_prev) >= 4 else None
                    if ttm_prev is not None and ttm_prev["key"] != ttm["key"] - 10:
                        ttm_prev = None
        # Đổi phạm vi hợp nhất (vd công ty con → liên kết): doanh thu TTM / so cùng kỳ không còn cùng cơ sở
        from core.phan_tich_co_ban import detect_scope_change
        sc = detect_scope_change(q) if q is not None and not q.empty and quarter_basis_ok else {"active": False}
        if sc.get("active"):
            res["scope_change"] = sc
            W.append(sc["text"] + " → tăng trưởng doanh thu so cùng kỳ thay bằng tăng trưởng LNST cổ đông mẹ; "
                     "các phương pháp dựa trên doanh thu/EBITDA/FCFF tạm không dùng cho tới khi đủ 4 quý theo cơ sở mới.")
        if ttm is not None and ttm["end"] > fy_end:
            merged = dict(base_row)
            merged.update({k: v for k, v in ttm["row"].items() if v is not None})
            # chỉ tiêu dòng thiếu trong TTM: KHÔNG lấy số năm cũ ghép vào → để trống
            for c in FLOW_ITEMS:
                if c in ttm["row"] and ttm["row"][c] is None:
                    merged[c] = None
            base_row = merged
            lab = f"TTM Q{ttm['key'] % 10}/{ttm['key'] // 10}"
            base = {"kind": "TTM", "key": ttm["key"], "end": ttm["end"], "label": lab, "quarters": ttm["quarters"]}
        # Bước 9: kỳ gốc là năm tài chính nhưng đã có bảng cân đối QUÝ mới hơn (công bố trước ngày dự báo) → VCSH và
        # lợi ích CĐ thiểu số lấy từ quý đó (số dư không phụ thuộc cơ sở số liệu quý), để khớp với số CP hiện hành
        # (vd phát hành thêm có thu tiền sau kỳ năm). Chỉ tiêu dòng giữ nguyên của năm tài chính.
        if base["kind"] == "FY" and q is not None and not q.empty:
            newer = [int(k) for k in q.index if int(k) // 10 > fy_key // 10 and _num(q.loc[k].get("equity")) is not None]
            if newer:
                kq = max(newer)
                for c in ("equity", "minority_interest"):
                    val = _num(q.loc[kq].get(c))
                    if val is not None:
                        base_row[c] = val
                base["balance_from"] = f"Q{kq % 10}/{kq // 10}"
                W.append(f"VCSH kỳ gốc lấy từ bảng cân đối Q{kq % 10}/{kq // 10} (mới nhất đã công bố); lợi nhuận/dòng tiền "
                         f"vẫn theo {base['label']}.")
        res["base"] = {**base, "end": str(base["end"].date())}
        # 16/10/2026: SỐ THỰC HIỆN của kỳ gốc (năm tài chính hoặc TTM 4 quý) để bảng dự phóng in cột "TH" – trước đây bảng
        # tra số TH trong BCTC NĂM theo khóa kỳ gốc; kỳ gốc là TTM (khóa quý) thì không tìm thấy → cả cột N/A.
        nip_b0 = _num(base_row.get("net_income_parent"))
        nip_b0 = nip_b0 if nip_b0 is not None else _num(base_row.get("net_income"))
        eq_b0 = _num(base_row.get("equity"))
        mi_b0 = _num(base_row.get("minority_interest")) or 0.0
        eq_prev = ta_prev = None                               # VCSH, tổng TS 1 năm trước kỳ gốc (cùng quý / năm trước)
        prev_k = int(base["key"]) - 10
        for src in ((q,) if base["kind"] == "TTM" else ()) + (a,):
            if src is not None and not src.empty and prev_k in src.index:
                eq_prev = _num(src.loc[prev_k].get("equity"))
                ta_prev = _num(src.loc[prev_k].get("total_assets"))
                if eq_prev is not None:
                    eq_prev -= _num(src.loc[prev_k].get("minority_interest")) or 0.0
                    break
        eq_par = eq_b0 - mi_b0 if eq_b0 is not None else None
        avg_eq = (eq_par + eq_prev) / 2 if eq_par and eq_prev else eq_par
        divp = _num(base_row.get("dividends_paid"))
        res["base"]["actual"] = {
            "revenue": _num(base_row.get("revenue")),
            "total_operating_income": _num(base_row.get("total_operating_income")),
            "net_income_parent": nip_b0,
            "eps": nip_b0 / shares if nip_b0 is not None else None,
            "roe": nip_b0 / avg_eq if nip_b0 is not None and avg_eq and avg_eq > 0 else None,
            "dps": abs(divp) / shares if divp else None,
            "bvps": eq_par / shares if eq_par else None,
            "equity_parent": eq_par,
            "customer_loans": _num(base_row.get("customer_loans")),
            "net_interest_income": _num(base_row.get("net_interest_income")),
            "provision": abs(_num(base_row.get("provision_expense")) or 0) or None,
            "total_assets": _num(base_row.get("total_assets")),
        }
        _toi0, _pbt0 = res["base"]["actual"]["total_operating_income"], _num(base_row.get("profit_before_tax"))
        _nii0, _ta0 = res["base"]["actual"]["net_interest_income"], res["base"]["actual"]["total_assets"]
        if _nii0 is not None and _ta0:
            res["base"]["actual"]["nim"] = _nii0 / ((_ta0 + ta_prev) / 2 if ta_prev else _ta0)
        if _toi0 and _pbt0 is not None and res["base"]["actual"]["provision"] is not None:
            res["base"]["actual"]["cir"] = 1 - (_pbt0 + res["base"]["actual"]["provision"]) / _toi0
        months_old = (as_of_ts.year - base["end"].year) * 12 + as_of_ts.month - base["end"].month
        if months_old > self.cfg["valuation"]["stale_months"]:
            W.append(f"Kỳ gốc {base['label']} đã cũ ~{months_old} tháng so với ngày dự báo → độ tin cậy thấp.")

        # ── tham số chung ──
        eq_tmp = _col(a, "equity") - _col(a, "minority_interest").fillna(0)
        res["cyclical"] = self._is_cyclical(a, model, eq_tmp)
        n_r = self.f["ratio_years"]
        drv = res["drivers"]
        tax, n_tax = _median_ratio(_col(a, "income_tax").abs(), _col(a, "profit_before_tax"), n_r)
        if tax is None or not (0 <= tax <= 0.5):
            tax = self.f["default_tax"]
            self._gap(res, "thuế suất thực tế", f"không ước lượng được → giả định {tax:.0%}", "thấp")
        drv["tax_rate"] = {"value": tax, "basis": f"trung vị {n_tax} năm" if n_tax else "mặc định cấu hình"}
        pbt_b, tax_b = _num(base_row.get("profit_before_tax")), _num(base_row.get("income_tax"))
        if n_tax and pbt_b and pbt_b > 0 and tax_b is not None and 0 <= abs(tax_b) / pbt_b <= 0.5:
            tax = self._anchor(res, drv["tax_rate"], tax, abs(tax_b) / pbt_b)
        ni_s = _col(a, "net_income")
        nip_s = _col(a, "net_income_parent")
        ps, n_ps = _median_ratio(nip_s, ni_s, n_r)
        if ps is None or not (0.3 <= ps <= 1.2):
            ps, basis_ps = 1.0, "không có số LNST cổ đông mẹ → coi LNST mẹ = LNST"
            if nip_s.dropna().empty:
                self._gap(res, "LNST cổ đông mẹ", "coi bằng LNST hợp nhất", "trung bình")
        else:
            basis_ps = f"trung vị {n_ps} năm"
        drv["parent_share"] = {"value": ps, "basis": basis_ps}
        ni_b, nip_b = _num(base_row.get("net_income")), _num(base_row.get("net_income_parent"))
        if n_ps and ni_b and nip_b is not None and ni_b > 0 and 0.3 <= nip_b / ni_b <= 1.2:
            ps = self._anchor(res, drv["parent_share"], ps, nip_b / ni_b)
        pay, n_pay = _median_ratio(_col(a, "dividends_paid"), nip_s.where(nip_s.notna(), ni_s), n_r, absolute_num=True)
        if pay is None:
            pay = 0.0
            self._gap(res, "cổ tức tiền mặt", "không có số liệu → giả định không chia cổ tức tiền mặt (BVPS có thể "
                                              "bị đánh giá cao)", "trung bình")
        pay = float(np.clip(pay, 0, 1))
        drv["payout"] = {"value": pay, "basis": f"trung vị {n_pay} năm" if n_pay else "giả định 0"}
        eq_s = _col(a, "equity") - _col(a, "minority_interest").fillna(0)
        eq0 = _num(base_row.get("equity"))
        if eq0 is not None:
            mi0 = _num(base_row.get("minority_interest"))
            if mi0 is None:
                self._gap(res, "lợi ích CĐ thiểu số (kỳ gốc)", "không có số liệu → VCSH mẹ = VCSH hợp nhất", "thấp")
            eq0 = eq0 - (mi0 or 0.0)
        if eq0 is None or eq0 <= 0:
            W.append("Thiếu VCSH dương ở kỳ gốc → không dự báo được ROE/BVPS.")

        if model == "nonfinancial":
            ok = self._drivers_nonfin(res, a, base_row, ttm, ttm_prev)
        elif model == "bank":
            ok = self._drivers_bank(res, a, base_row, ttm, ttm_prev)
            if not ok:                      # thiếu LNTT/dự phòng/TOI → mô hình ROE (vẫn dựa trên LNST & VCSH thật)
                reason = res.pop("reason", "")
                res["warnings"].append(f"Ngân hàng: {reason} → dùng mô hình ROE chuẩn hóa thay cho mô hình thu nhập–dự phòng.")
                model = res["model"] = "roe"
                ok = self._drivers_roe(res, a, base_row, eq_s)
        else:
            ok = self._drivers_roe(res, a, base_row, eq_s)
        if not ok:
            return res
        self._stability_checks(res, a, company, model, eq_s)
        self._assumption_checks(res, a, base_row, model)

        # ── kịch bản ──
        N = int(self.f["years"])
        months_to_end = _years_between(base["end"], as_of_ts + pd.DateOffset(months=12))
        res["ntm_offset_years"] = round(months_to_end, 3)
        res["scenario_group"] = self._group(res)
        for s in SCEN:
            p = self._scenario_params(res, s)
            years = self._project(model, res, base_row, eq0, shares, tax, ps, pay, p, self.tg[s], N)
            ntm = _interp(years, base_row, model, months_to_end, eq0, shares)
            res["scenarios"][s] = {"label": SCEN_LABEL[s], "assumptions": self._explain(model, res, p, s),
                                   "years": years, "ntm": ntm}
            if model == "bank":
                self._bank_nii(res, a, base_row, years)
            fy0 = base["end"]
            for t, y in enumerate(years, start=1):          # nhãn kỳ: năm t kết thúc tại cuối kỳ gốc + t năm
                y["period_end"] = str((fy0 + pd.DateOffset(years=t)).date())
                y["label"] = (f"FY{fy0.year + t}" if base["kind"] == "FY" else
                              f"12T đến {(fy0 + pd.DateOffset(years=t)):%m/%Y}")
            y1 = years[0] if years else {}
            res["valuation_inputs"][s] = {
                # *_fwd = NTM (12 tháng kể từ ngày dự báo) – dùng cho P/E Forward, P/B–ROE, EV/EBITDA
                "eps_fwd": ntm.get("eps"), "net_income_fwd": ntm.get("net_income_parent"),
                "revenue_fwd": ntm.get("revenue"), "ebitda_fwd": ntm.get("ebitda"),
                "ebitda_core_fwd": ntm.get("ebitda_core"),        # EV/EBITDA (bước 9): EBITDA cốt lõi NTM
                "roe_fwd": ntm.get("roe"), "bvps_fwd": ntm.get("bvps"),
                "ntm_window_end": str((as_of_ts + pd.DateOffset(months=12)).date()),
                # *_fy1 = năm dự báo đầu tiên kể từ kỳ gốc (KHÔNG phải NTM) – để đối chiếu với số liệu công ty/CTCK
                "fy1_label": y1.get("label"), "fy1_period_end": y1.get("period_end"),
                "eps_fy1": y1.get("eps"), "net_income_fy1": y1.get("net_income_parent"),
                "ebitda_fy1": y1.get("ebitda"), "roe_fy1": y1.get("roe"),
                # DCF: dòng tiền theo năm kể từ cuối kỳ gốc, kèm ngày kết thúc từng kỳ để chiết khấu đúng thời điểm
                "fcff_path": [y.get("fcff") for y in years] if model == "nonfinancial" else None,
                "revenue_path": [y.get("revenue") for y in years], "eps_path": [y.get("eps") for y in years],
                "dps_path": [y.get("dps") for y in years], "roe_path": [y.get("roe") for y in years],
                "bvps_path": [y.get("bvps") for y in years],
                "fcff_period_ends": [y.get("period_end") for y in years] if model == "nonfinancial" else None,
                "terminal_growth": self.tg[s], "base_period": base["label"], "horizon_years": N,
                "applicable": {"pe_forward": True, "pb_roe": True,
                               "ev_ebitda": model == "nonfinancial", "dcf_fcff": model == "nonfinancial"},
            }
        if model == "nonfinancial" and res["drivers"].get("core_ebitda_margin") and \
                all((y.get("fcff") or 0) <= 0 for y in res["scenarios"]["base"]["years"]):
            res["warnings"].append("FCFF dự báo âm ở mọi năm của kịch bản cơ sở (đầu tư/vốn lưu động lớn) → DCF theo FCFF "
                                   "không có ý nghĩa với giả định hiện tại.")
        if model != "nonfinancial":
            res["not_applicable"] = {"ebitda": "Không áp dụng cho ngân hàng/CTCK/bảo hiểm (định giá theo P/B–ROE, P/E)",
                                     "fcff": "Không áp dụng cho ngân hàng/CTCK/bảo hiểm"}
        res["available"] = True
        return res

    # ── tham số theo mô hình ──
    def _growth(self, res, series_a: pd.Series, ttm_val, ttm_prev_val, label) -> Optional[float]:
        g_h, n_h = robust_growth(series_a, self.f["hist_years"])
        g_t = (ttm_val / ttm_prev_val - 1) if ttm_val and ttm_prev_val and ttm_val > 0 and ttm_prev_val > 0 else None
        w = self.f["w_hist"]
        parts = [(w, g_h), (1 - w, g_t)]
        parts = [(x, g) for x, g in parts if g is not None]
        lo, hi = self.f["growth_bounds"]
        if not parts:
            self._gap(res, f"tăng trưởng {label}", "không đủ ≥ 2 năm lịch sử liên tiếp dương → giả định 0%", "cao")
            g, basis = 0.0, "giả định 0% (thiếu lịch sử)"
        else:
            raw = sum(x * gg for x, gg in parts) / sum(x for x, _ in parts)
            g = float(np.clip(raw, lo, hi))
            basis = (f"trung vị YoY {n_h} năm = {g_h:.1%}" if g_h is not None else "") + \
                    (f"; TTM so cùng kỳ = {g_t:.1%}" if g_t is not None else "") + \
                    (f"; chặn trong [{lo:.0%}, {hi:.0%}]" if g != raw else "")
            shrink = self._param(res, "growth_shrink")
            # 15/10/2026: doanh nghiệp tăng trưởng ĐỀU (≥ 4/5 năm gần nhất tăng, trung vị ≥ 8%) → co ít hơn về g dài hạn.
            # Mức co 0,25 hiệu chỉnh trên toàn thị trường (tăng trưởng hồi quy mạnh về trung bình) làm doanh nghiệp tăng
            # trưởng bền vững (vd FPT ~20%/năm) bị dự báo chỉ ~7%/năm → định giá thấp có hệ thống.
            sc = self.f.get("growth_shrink_consistent")
            if sc is not None and shrink < float(sc) and g > 0 and g_h is not None:
                yoy = _yoy_list(series_a, self.f.get("consistent_years", 5))
                if len(yoy) >= self.f.get("consistent_years", 5) - 1 and \
                        sum(1 for x in yoy if x > 0) >= self.f.get("consistent_min_up", 4) and \
                        g_h >= self.f.get("consistent_min_growth", 0.08):
                    shrink = float(sc)
                    basis += (f"; tăng trưởng đều {sum(1 for x in yoy if x > 0)}/{len(yoy)} năm (trung vị {g_h:.0%}) "
                              f"→ co ít hơn")
            if shrink < 1:
                g_lr = self.tg["base"]
                # Co BẤT ĐỐI XỨNG: tăng trưởng âm (doanh nghiệp đang đi xuống) giữ lại phần lớn mức giảm – co đối xứng
                # về g dài hạn dương kéo một mức giảm −10% lên ≈ 0% → EPS NTM lạc quan đúng lúc kinh doanh xấu đi.
                neg = self.f.get("growth_shrink_negative")
                if g < 0 and neg is not None and float(neg) > shrink:
                    shrink = min(float(neg), 1.0)
                    basis += "; tăng trưởng âm → co ít hơn (bất đối xứng)"
                if shrink < 1:
                    g = shrink * g + (1 - shrink) * g_lr
                    basis += f"; co về tăng trưởng dài hạn {g_lr:.1%} với trọng số {1 - shrink:.0%}"
            if n_h < 3 and g_t is None:
                res["warnings"].append(f"Tăng trưởng {label} chỉ dựa trên {n_h} năm lịch sử → độ tin cậy thấp.")
        res["drivers"]["growth"] = {"value": g, "basis": basis.strip("; "), "series": label}
        return g

    def _drivers_nonfin(self, res, a, base_row, ttm, ttm_prev) -> bool:
        rev0 = _num(base_row.get("revenue"))
        if rev0 is None or rev0 <= 0:
            res["reason"] = "Thiếu doanh thu kỳ gốc → không dự báo được."
            return False
        n_r = self.f["ratio_years"]
        rev_a = _col(a, "revenue")
        if (res.get("scope_change") or {}).get("active") and ttm and ttm_prev:
            # khác cơ sở hợp nhất → dùng tăng trưởng LNST mẹ TTM làm tín hiệu tăng trưởng gần nhất (không bị đổi phạm vi)
            self._growth(res, rev_a, _num(ttm["row"].get("net_income_parent")),
                         _num(ttm_prev["row"].get("net_income_parent")), "doanh thu (tín hiệu TTM: LNST mẹ – đổi phạm vi hợp nhất)")
        else:
            self._growth(res, rev_a, rev0 if ttm else None,
                         _num((ttm_prev or {}).get("row", {}).get("revenue")) if ttm else None, "doanh thu")
        ebitda_a = ebit_ebitda(a)[1]
        m_all = (ebitda_a / rev_a.where(rev_a != 0)).dropna()
        hist_m = m_all.tail(n_r).tolist()
        m0 = _num(ebit_ebitda(pd.DataFrame([base_row]))[1].iloc[0])
        m0 = m0 / rev0 if m0 is not None else None
        use_ttm = res["base"]["kind"] == "TTM" and m0 is not None
        vals = hist_m + ([m0] if use_ttm else [])
        if not vals:
            res["reason"] = "Thiếu LNTT/lãi vay/khấu hao để tính biên EBITDA → không dự báo được lợi nhuận."
            return False
        lo, hi = self.f["margin_bounds"]
        m_med = float(np.median(vals))
        lam = self._param(res, "margin_anchor") if m0 is not None else 0.0
        margin = float(np.clip(lam * m0 + (1 - lam) * m_med if m0 is not None else m_med, lo, hi))
        long_n = int(self.f.get("margin_long_years", n_r))
        m_long = float(np.clip(m_all.tail(long_n).median(), lo, hi)) if len(m_all) else margin
        res["drivers"]["ebitda_margin"] = {
            "value": margin, "long_run": m_long,
            "basis": (f"{lam:.0%} biên kỳ gốc + {1 - lam:.0%} " if lam else "") + f"trung vị {len(hist_m)} năm"
                     + (" và TTM" if use_ttm else "") + f"; hồi quy dần về trung vị {min(long_n, len(m_all))} năm "
                     f"({m_long:.1%}) ở năm cuối"}
        da, n_da = _median_ratio(_col(a, "depreciation"), rev_a, n_r, absolute_num=True)
        if da is None:
            res["reason"] = "Thiếu khấu hao → không tách được EBIT/EBITDA."
            return False
        res["drivers"]["da_pct_revenue"] = {"value": da, "basis": f"trung vị {n_da} năm"}
        da_b = _num(base_row.get("depreciation"))
        if da_b is not None:
            self._anchor(res, res["drivers"]["da_pct_revenue"], da, abs(da_b) / rev0)
        intr = _num(base_row.get("interest_expense"))
        if intr is None:
            intr = 0.0
            self._gap(res, "chi phí lãi vay (kỳ gốc)", "không có số liệu → coi bằng 0 (LNTT dự báo có thể bị "
                                                    "đánh giá cao)", "trung bình")
        res["drivers"]["interest_expense"] = {"value": abs(intr), "basis": f"giữ bằng kỳ gốc ({res['base']['label']}) – giả định nợ vay không đổi"}
        cap, n_cap = _median_ratio(_col(a, "capex"), rev_a, n_r, absolute_num=True)
        if cap is None:
            cap = da
            self._gap(res, "capex", "không có số liệu → giả định capex = khấu hao (duy trì)", "cao")
        res["drivers"]["capex_pct_revenue"] = {"value": cap, "basis": f"trung vị {n_cap} năm" if n_cap else "giả định = khấu hao"}
        nwc = _col(a, "receivables") + _col(a, "inventory") - _col(a, "payables")
        nwc_pct, n_nwc = _median_ratio(nwc, rev_a, n_r)
        if nwc_pct is None:
            nwc_pct = 0.0
            self._gap(res, "vốn lưu động (phải thu, tồn kho, phải trả)", "không đủ số liệu → coi ΔVLĐ = 0 (FCFF có thể "
                                                                          "bị đánh giá cao)", "trung bình")
        res["drivers"]["nwc_pct_revenue"] = {"value": nwc_pct, "basis": f"trung vị {n_nwc} năm" if n_nwc else "giả định 0"}
        self._core_margin(res, a, base_row, rev0, rev_a, use_ttm, lam if m0 is not None else 0.0)
        return True

    def _core_margin(self, res, a, base_row, rev0, rev_a, use_ttm, lam) -> None:
        """Biên EBITDA CỐT LÕI (bước 9): loại DT tài chính, CP tài chính khác lãi vay, lãi/lỗ công ty liên kết và thu
        nhập khác (xem financial_ratios.core_ebit_ebitda). Chỉ dùng cho FCFF (DCF) và EBITDA của EV/EBITDA; dự báo
        LNST/EPS vẫn dùng biên EBITDA toàn phần ở trên (giữ nguyên kết quả đã hiệu chỉnh ở bước 6)."""
        n_r = self.f["ratio_years"]
        lo, hi = self.f["margin_bounds"]
        c_all = (core_ebit_ebitda(a)[1] / rev_a.where(rev_a != 0)).dropna()
        c0 = _num(core_ebit_ebitda(pd.DataFrame([base_row]))[1].iloc[0])
        c0 = c0 / rev0 if c0 is not None else None
        hist_c = c_all.tail(n_r).tolist()
        vals = hist_c + ([c0] if use_ttm and c0 is not None else [])
        if not vals:
            res["drivers"]["core_ebitda_margin"] = None
            self._gap(res, "EBIT cốt lõi (LN gộp, CP bán hàng, CP quản lý hoặc DT/CP tài chính, lãi công ty liên kết)",
                      "không tách được thu nhập tài chính khỏi EBIT → không dự báo FCFF/EBITDA cốt lõi (không dùng EBIT "
                      "toàn phần để tránh tính trùng)", "cao")
            return
        c_med = float(np.median(vals))
        lam_c = lam if c0 is not None else 0.0
        c1 = float(np.clip(lam_c * c0 + (1 - lam_c) * c_med if c0 is not None else c_med, lo, hi))
        long_n = int(self.f.get("margin_long_years", n_r))
        c_long = float(np.clip(c_all.tail(long_n).median(), lo, hi)) if len(c_all) else c1
        res["drivers"]["core_ebitda_margin"] = {
            "value": c1, "long_run": c_long,
            "basis": (f"{lam_c:.0%} biên cốt lõi kỳ gốc + {1 - lam_c:.0%} " if lam_c else "") + f"trung vị {len(hist_c)} năm"
                     + f"; hồi quy về trung vị {min(long_n, len(c_all))} năm ({c_long:.1%}) ở năm cuối. "
                     "Biên cốt lõi = (LN gộp − CP bán hàng − CP quản lý + khấu hao) / doanh thu."}

    def _drivers_bank(self, res, a, base_row, ttm, ttm_prev) -> bool:
        toi0 = _num(base_row.get("total_operating_income"))
        pbt0 = _num(base_row.get("profit_before_tax"))
        if toi0 is None or toi0 <= 0 or pbt0 is None:
            res["reason"] = "Thiếu tổng thu nhập hoạt động hoặc LNTT kỳ gốc của ngân hàng."
            return False
        n_r = self.f["ratio_years"]
        toi_a = _col(a, "total_operating_income")
        loans_a = _col(a, "customer_loans")
        g_loans, n_l = robust_growth(loans_a, self.f["hist_years"])
        self._growth(res, toi_a, toi0 if ttm else None,
                     _num((ttm_prev or {}).get("row", {}).get("total_operating_income")) if ttm else None,
                     "tổng thu nhập hoạt động")
        if g_loans is not None:                                   # TOI đi cùng tăng trưởng tín dụng
            g = res["drivers"]["growth"]
            lo, hi = self.f["growth_bounds"]
            g["value"] = float(np.clip(0.5 * g["value"] + 0.5 * g_loans, lo, hi))
            g["basis"] += f"; bình quân với tăng trưởng dư nợ trung vị {n_l} năm = {g_loans:.1%}"
        prov_a = _col(a, "provision_expense").abs()
        ppop_a = _col(a, "profit_before_tax") + prov_a
        m, n_m = _median_ratio(ppop_a, toi_a, n_r)
        if m is None:
            res["reason"] = "Thiếu chi phí dự phòng → không tách được lợi nhuận trước dự phòng."
            return False
        res["drivers"]["ppop_margin"] = {"value": m, "basis": f"trung vị {n_m} năm (LNTT + dự phòng)/TOI"}
        pbt_b, prov_b = _num(base_row.get("profit_before_tax")), _num(base_row.get("provision_expense"))
        if pbt_b is not None and prov_b is not None:
            lam = self._param(res, "margin_anchor")
            if lam:
                d0 = res["drivers"]["ppop_margin"]
                d0["value"] = lam * (pbt_b + abs(prov_b)) / toi0 + (1 - lam) * m
                d0["basis"] = f"{lam:.0%} biên kỳ gốc + {1 - lam:.0%} " + d0["basis"]
        avg_loans = (loans_a + loans_a.shift(1)) / 2
        cc, n_cc = _median_ratio(prov_a, avg_loans, n_r)
        loans0 = _num(base_row.get("customer_loans"))
        if cc is not None and loans0:
            res["drivers"]["credit_cost"] = {"value": cc, "basis": f"trung vị {n_cc} năm dự phòng/dư nợ bình quân"}
            res["drivers"]["loans_base"] = loans0
        else:
            pr, n_pr = _median_ratio(prov_a, toi_a, n_r)
            res["drivers"]["provision_pct_toi"] = {"value": pr or 0.0, "basis": f"trung vị {n_pr} năm dự phòng/TOI"}
            self._gap(res, "dư nợ cho vay", "không có số liệu → dự phòng tính theo tỷ lệ trên TOI", "trung bình")
        return True

    def _bank_nii(self, res, a, base_row, years) -> None:
        """16/10/2026 (lựa chọn B): TÁCH thu nhập lãi thuần (NII) và NIM cho bảng dự phóng ngân hàng.
        Mô hình ngân hàng dự phóng GỘP tổng thu nhập hoạt động (TOI) → NII_t = TOI_t × tỷ trọng NII/TOI trung vị 3 năm gần
        nhất; tổng tài sản tăng cùng tốc độ dư nợ cho vay; NIM_t (xấp xỉ) = NII_t ÷ tổng tài sản bình quân. Đây là GIẢ ĐỊNH
        trình bày (không đổi LNST/định giá) – ghi rõ ở drivers['nii_share']."""
        toi_a, nii_a = _col(a, "total_operating_income"), _col(a, "net_interest_income")
        share, n = _median_ratio(nii_a, toi_a, 3)
        if share is None or not (0 < share < 1.2):
            share = None
        else:
            res["drivers"]["nii_share"] = {"value": share, "basis": f"trung vị {n} năm TN lãi thuần / tổng TN hoạt động"}
        ta0, loans0 = _num(base_row.get("total_assets")), _num(base_row.get("customer_loans"))
        prev_ta, prev_loans = ta0, loans0
        for y in years:
            toi = _num(y.get("total_operating_income"))
            y["net_interest_income"] = toi * share if toi is not None and share is not None else None
            loans = _num(y.get("customer_loans"))
            y["credit_growth"] = loans / prev_loans - 1 if loans and prev_loans else None
            ta = prev_ta * loans / prev_loans if prev_ta and loans and prev_loans else None
            y["total_assets"] = ta
            y["nim"] = (y["net_interest_income"] / ((prev_ta + ta) / 2)
                        if y["net_interest_income"] is not None and ta and prev_ta else None)
            ppop = _num(y.get("ppop"))
            y["cir"] = 1 - ppop / toi if ppop is not None and toi else None
            prev_ta, prev_loans = ta, loans

    def _drivers_roe(self, res, a, base_row, eq_s) -> bool:
        nip = _col(a, "net_income_parent")
        nip = nip.where(nip.notna(), _col(a, "net_income"))
        avg_eq = (eq_s + eq_s.shift(1)) / 2
        roe, n = _median_ratio(nip, avg_eq, self.f["hist_years"])
        if roe is None:
            res["reason"] = "Thiếu LNST/VCSH lịch sử để chuẩn hóa ROE."
            return False
        lo, hi = self.f["roe_bounds"]
        res["drivers"]["roe_norm"] = {"value": float(np.clip(roe, lo, hi)),
                                      "basis": f"trung vị ROE {n} năm (lợi nhuận CTCK/bảo hiểm biến động theo thị trường)"}
        roe_ser = (nip / avg_eq).dropna()
        lam = self._param(res, "roe_anchor")
        roe_last = float(roe_ser.iloc[-1]) if len(roe_ser) else None
        roe1 = lam * roe_last + (1 - lam) * roe if roe_last is not None and lam else roe
        res["drivers"]["roe_y1"] = {"value": float(np.clip(roe1, lo, hi)),
                                    "basis": (f"{lam:.0%} ROE kỳ gốc + {1 - lam:.0%} " if lam and roe_last is not None else "")
                                             + "ROE chuẩn hóa"}
        nm, n_nm = _median_ratio(nip, _col(a, "revenue"), self.f["ratio_years"])
        if nm:
            res["drivers"]["net_margin"] = {"value": nm, "basis": f"trung vị {n_nm} năm (chỉ để suy ra doanh thu tham khảo)"}
        if n < 3:
            res["warnings"].append(f"ROE chuẩn hóa chỉ dựa trên {n} năm → độ tin cậy thấp.")
        return True

    # ── dự phóng từng năm ──
    def _project(self, model, res, base_row, eq0, shares, tax, ps, pay, p, g_term, N) -> List[Dict[str, Any]]:
        d = res["drivers"]
        lo, hi = self.f["growth_bounds"]
        out: List[Dict[str, Any]] = []
        eq_prev = eq0 if eq0 and eq0 > 0 else None
        if model == "roe":
            roe = float(np.clip(d["roe_y1"]["value"] + p["roe_shift"], *self.f["roe_bounds"]))
            for t in range(1, N + 1):
                if eq_prev is None:
                    out.append({"year": t})
                    continue
                nip = roe * eq_prev
                eq = eq_prev + nip * (1 - pay)
                nm = (d.get("net_margin") or {}).get("value")
                out.append({"year": t, "net_income_parent": nip, "net_income": nip / ps if ps else nip,
                            "revenue": nip / nm if nm else None, "eps": nip / shares, "equity_parent": eq,
                            "bvps": eq / shares, "roe": nip / ((eq_prev + eq) / 2), "dps": nip * pay / shares,
                            "ebitda": None, "fcff": None})
                eq_prev = eq
            return out

        g1 = float(np.clip(d["growth"]["value"] + p["growth_shift"], lo, hi))
        if model == "nonfinancial":
            prev_rev = _num(base_row.get("revenue"))
            margin1 = d["ebitda_margin"]["value"]
            margin_lr = d["ebitda_margin"].get("long_run", margin1)
            core = d.get("core_ebitda_margin")
        else:
            prev_rev = _num(base_row.get("total_operating_income"))
            margin = d["ppop_margin"]["value"] + p["margin_shift"]
            loans_prev = d.get("loans_base")
        for t in range(1, N + 1):
            g = g1 + (g_term - g1) * (t - 1) / max(N - 1, 1)
            rev = prev_rev * (1 + g)
            row: Dict[str, Any] = {"year": t, "growth": g}
            if model == "nonfinancial":
                margin = float(np.clip(margin1 + (margin_lr - margin1) * (t - 1) / max(N - 1, 1) + p["margin_shift"],
                                       *self.f["margin_bounds"]))
                ebitda = rev * margin
                da = rev * d["da_pct_revenue"]["value"]
                ebit = ebitda - da
                pbt = ebit - d["interest_expense"]["value"]
                capex = rev * d["capex_pct_revenue"]["value"] * p["capex_factor"]
                dnwc = d["nwc_pct_revenue"]["value"] * (rev - prev_rev)
                # FCFF chỉ từ EBIT CỐT LÕI (bước 9) – thu nhập tài chính/công ty liên kết không vào dòng tiền vì tài
                # sản tương ứng được cộng riêng ở cầu nối EV → vốn chủ.
                if core:
                    cm = float(np.clip(core["value"] + (core["long_run"] - core["value"]) * (t - 1) / max(N - 1, 1)
                                       + p["margin_shift"], *self.f["margin_bounds"]))
                    ebitda_c = rev * cm
                    ebit_c = ebitda_c - da
                    fcff = ebit_c * (1 - tax) + da - capex - dnwc
                else:
                    cm = ebitda_c = ebit_c = fcff = None
                row.update(revenue=rev, ebitda=ebitda, ebitda_margin=margin, depreciation=da, ebit=ebit,
                           ebitda_core=ebitda_c, ebit_core=ebit_c, core_margin=cm,
                           capex=capex, delta_nwc=dnwc, fcff=fcff)
            else:
                ppop = rev * margin
                if "credit_cost" in d:
                    loans = loans_prev * (1 + g)
                    prov = d["credit_cost"]["value"] * p["credit_cost_factor"] * (loans_prev + loans) / 2
                    row["customer_loans"] = loans
                    loans_prev = loans
                else:
                    prov = rev * d["provision_pct_toi"]["value"] * p["credit_cost_factor"]
                pbt = ppop - prov
                row.update(total_operating_income=rev, ppop=ppop, provision=prov, ebitda=None, fcff=None)
            ni = pbt - max(pbt, 0) * tax
            nip = ni * ps
            row.update(profit_before_tax=pbt, net_income=ni, net_income_parent=nip, eps=nip / shares)
            if eq_prev is not None:
                eq = eq_prev + nip - max(nip, 0) * pay
                row.update(equity_parent=eq, bvps=eq / shares, roe=nip / ((eq_prev + eq) / 2),
                           dps=max(nip, 0) * pay / shares)
                eq_prev = eq
            else:
                row.update(equity_parent=None, bvps=None, roe=None, dps=None)
            out.append(row)
            prev_rev = rev
        return out

    def _explain(self, model, res, p, s) -> List[str]:
        d = res["drivers"]
        tg = self.tg[s]
        lines = []
        if model == "roe":
            lines.append(f"ROE năm 1 {d['roe_y1']['value']:.1%} {p['roe_shift']:+.1%} (kịch bản) – {d['roe_y1']['basis']}; "
                         f"ROE chuẩn hóa {d['roe_norm']['value']:.1%} ({d['roe_norm']['basis']}).")
        else:
            lines.append(f"Tăng trưởng năm 1: {d['growth']['value']:.1%} {p['growth_shift']:+.1%} (kịch bản), giảm dần về "
                         f"{tg:.1%} ở năm cuối – cơ sở: {d['growth']['basis']}.")
            if model == "nonfinancial":
                lines.append(f"Biên EBITDA {d['ebitda_margin']['value']:.1%} {p['margin_shift']:+.1%}; khấu hao "
                             f"{d['da_pct_revenue']['value']:.1%} DT; capex {d['capex_pct_revenue']['value']:.1%} DT × {p['capex_factor']:.2f}; "
                             f"VLĐ {d['nwc_pct_revenue']['value']:.1%} DT; lãi vay giữ bằng kỳ gốc.")
                core = d.get("core_ebitda_margin")
                if core:
                    lines.append(f"FCFF dùng biên EBITDA cốt lõi {core['value']:.1%} → {core['long_run']:.1%} (không gồm "
                                 "thu nhập tài chính/công ty liên kết – các tài sản này cộng riêng khi tính vốn chủ).")
            else:
                cc = d.get("credit_cost")
                lines.append(f"Biên lợi nhuận trước dự phòng {d['ppop_margin']['value']:.1%} {p['margin_shift']:+.1%}; "
                             + (f"chi phí tín dụng {cc['value']:.2%} × {p['credit_cost_factor']:.2f}" if cc else
                                f"dự phòng {d['provision_pct_toi']['value']:.1%} TOI × {p['credit_cost_factor']:.2f}") + ".")
        if p.get("calibrated"):
            lines.append(f"Độ lệch {SCEN_LABEL[s]} lấy theo phân vị {'20' if s == 'bear' else '80'} của sai số dự báo lịch sử "
                         f"nhóm '{res.get('scenario_group')}' (hiệu chỉnh trên tập mã/năm tách biệt, xem forecast.scenario_bands).")
        lines.append(f"Thuế suất {d['tax_rate']['value']:.0%} ({d['tax_rate']['basis']}); tỷ lệ chia cổ tức tiền mặt "
                     f"{d['payout']['value']:.0%} ({d['payout']['basis']}); số CP giữ nguyên (chưa tính phát hành/pha loãng).")
        return lines

    def _param(self, res, key):
        """Tham số hiệu chỉnh. Thứ tự ưu tiên: riêng theo mô hình (forecast.model_overrides[bank|roe|nonfinancial])
        → riêng cho doanh nghiệp chu kỳ (forecast.cyclical) → giá trị chung."""
        mo = (self.f.get("model_overrides") or {}).get(res.get("model")) or {}
        if mo.get(key) is not None:
            return float(mo[key])
        cyc = self.f.get("cyclical") or {}
        if res.get("cyclical") and cyc.get(key) is not None:
            return float(cyc[key])
        return float(self.f.get(key, {"growth_shrink": 1.0}.get(key, 0.0)))

    def _group(self, res) -> str:
        """Nhóm dùng cho khoảng kịch bản – xác định từ dữ liệu đã công bố (không nhìn trước)."""
        if res["model"] == "bank":
            return "bank"
        if res["model"] == "roe":
            return "securities"
        nwc = (res["drivers"].get("nwc_pct_revenue") or {}).get("value") or 0
        if nwc > 0.5:
            return "nwc_heavy"
        return "cyclical" if res.get("cyclical") else "stable"

    def _scenario_params(self, res, s) -> Dict[str, Any]:
        """Tham số kịch bản. Nếu có khoảng hiệu chỉnh theo nhóm (forecast.scenario_bands – phân vị P20/P80 của sai số
        tham số trên tập hiệu chỉnh), Bear/Bull dùng các độ lệch đó; nếu không, dùng độ lệch cố định."""
        p = dict(self.f["scenarios"][s])
        band = (self.f.get("scenario_bands") or {}).get(self._group(res))
        if band and s != "base":
            k = "lo" if s == "bear" else "hi"
            for src, dst in (("growth", "growth_shift"), ("margin", "margin_shift"), ("roe", "roe_shift")):
                if band.get(src):
                    p[dst] = float(band[src][k] - band[src].get("mid", 0.0))
            p["calibrated"] = True
        return p

    def _anchor(self, res, drv: Dict[str, Any], med: float, base_val: float, key: str = "ratio_anchor") -> float:
        """Tỷ lệ năm 1 = λ × tỷ lệ kỳ gốc + (1 − λ) × trung vị lịch sử (λ = forecast.ratio_anchor)."""
        lam = self._param(res, key)
        if not lam:
            return med
        v = lam * base_val + (1 - lam) * med
        drv["value"] = v
        drv["basis"] = f"{lam:.0%} kỳ gốc + {1 - lam:.0%} " + drv["basis"]
        return v

    def _is_cyclical(self, a, model, eq_s) -> bool:
        """Chu kỳ = hệ số biến thiên của biên EBITDA (phi tài chính) / ROE (tài chính) trên dữ liệu ĐÃ CÔNG BỐ."""
        n = self.f["hist_years"]
        if model == "nonfinancial":
            rev = _col(a, "revenue")
            m = (ebit_ebitda(a)[1] / rev.where(rev != 0)).dropna().tail(n)
        else:
            nip = _col(a, "net_income_parent").where(_col(a, "net_income_parent").notna(), _col(a, "net_income"))
            m = (nip / ((eq_s + eq_s.shift(1)) / 2)).dropna().tail(n)
        if len(m) < 3 or m.median() == 0:
            return False
        return float(m.std() / abs(m.median())) > float((self.f.get("cyclical") or {}).get("cv_threshold", 0.35))

    def _assumption_checks(self, res, a, base_row, model) -> None:
        """Kiểm tra các giả định lãi vay, CAPEX, vốn lưu động, số cổ phiếu trên dữ liệu đã công bố (bước 6)."""
        from core.phan_tich_co_ban import shares_series
        W, d = res["warnings"], res["drivers"]
        # Số cổ phiếu: dự báo giữ nguyên số CP hiện tại (EPS/BVPS theo số CP hiện tại, cùng cơ sở với thị giá)
        sh = shares_series(a).dropna()
        gr = (sh / sh.shift(1) - 1).dropna().tail(3)
        d["share_count"] = {"value": float(sh.iloc[-1]) if len(sh) else None,
                            "hist_growth_median": float(gr.median()) if len(gr) else None,
                            "basis": "giữ nguyên số CP hiện tại (chưa tính phát hành mới / cổ phiếu thưởng)"}
        if len(gr) and (gr.median() > 0.05 or gr.max() > 0.20):
            W.append(f"Số cổ phiếu tăng mạnh trong lịch sử (trung vị {gr.median():.0%}/năm, cao nhất {gr.max():.0%}) – "
                     "dự báo giữ số CP hiện tại; nếu tiếp tục phát hành, EPS báo cáo tương lai sẽ thấp hơn.")
        so, cc = _num(base_row.get("shares_outstanding")), _num(base_row.get("charter_capital"))
        if so and cc and abs(so / (cc / 10_000) - 1) > 0.05:
            W.append(f"Số CP lưu hành ({so:,.0f}) lệch > 5% so với vốn điều lệ / mệnh giá ({cc / 10_000:,.0f}) – "
                     "kiểm tra cổ phiếu quỹ / dữ liệu nguồn.")
        if model != "nonfinancial":
            return
        # Lãi vay: giữ bằng kỳ gốc. Kiểm tra lãi suất ngầm định = lãi vay / nợ vay bình quân
        debt = (_col(a, "short_term_debt").abs().fillna(0) + _col(a, "long_term_debt").abs().fillna(0))
        intr = _col(a, "interest_expense").abs()
        if len(debt) >= 2 and debt.iloc[-2:].mean() > 0 and pd.notna(intr.iloc[-1]):
            rate = float(intr.iloc[-1] / debt.iloc[-2:].mean())
            d["implied_interest_rate"] = {"value": rate, "basis": "lãi vay năm gần nhất / nợ vay bình quân 2 năm"}
            if not 0.02 <= rate <= 0.20:
                W.append(f"Lãi suất ngầm định {rate:.1%} bất thường (lãi vay/nợ vay) – dữ liệu nợ vay hoặc lãi vay có thể "
                         "chưa đầy đủ; lãi vay dự báo giữ bằng kỳ gốc.")
        # CAPEX: biến động mạnh ⇒ FCFF/DCF bất định
        cap = (_col(a, "capex").abs() / _col(a, "revenue").where(_col(a, "revenue") != 0)).dropna().tail(5)
        if len(cap) >= 3 and cap.median() > 0 and cap.std() / cap.median() > 0.5:
            W.append(f"CAPEX/doanh thu biến động mạnh ({cap.min():.0%}–{cap.max():.0%} trong {len(cap)} năm) – FCFF dự báo dùng "
                     "trung vị nên sai số lớn ở từng năm.")
        # Vốn lưu động: trung vị âm hoặc dao động mạnh
        nwc = ((_col(a, "receivables") + _col(a, "inventory") - _col(a, "payables"))
               / _col(a, "revenue").where(_col(a, "revenue") != 0)).dropna().tail(5)
        if len(nwc) >= 3 and (nwc.median() < 0 or (nwc.max() - nwc.min()) > 0.5):
            W.append(f"Vốn lưu động/doanh thu dao động ({nwc.min():.0%}–{nwc.max():.0%}) – ΔVLĐ trong FCFF kém tin cậy.")

    def _stability_checks(self, res, a, company, model, eq_s) -> None:
        """Cảnh báo khi tham số lịch sử biến động mạnh (doanh nghiệp chu kỳ) hoặc mô hình kém phù hợp ngành."""
        n = self.f["hist_years"]
        if model == "nonfinancial":
            m = (ebit_ebitda(a)[1] / _col(a, "revenue").where(_col(a, "revenue") != 0)).dropna().tail(n)
            label = "biên EBITDA"
        elif model == "bank":
            toi = _col(a, "total_operating_income")
            m = ((_col(a, "profit_before_tax") + _col(a, "provision_expense").abs()) / toi.where(toi != 0)).dropna().tail(n)
            label = "biên lợi nhuận trước dự phòng"
        else:
            nip = _col(a, "net_income_parent").where(_col(a, "net_income_parent").notna(), _col(a, "net_income"))
            m = (nip / ((eq_s + eq_s.shift(1)) / 2)).dropna().tail(n)
            label = "ROE"
        if len(m) >= 3 and abs(m.median()) > 0:
            cv = float(m.std() / abs(m.median()))
            res["drivers"]["stability"] = {"value": cv, "basis": f"hệ số biến thiên {label} {len(m)} năm"}
            if cv > 0.35:
                res["warnings"].append(f"{label.capitalize()} biến động mạnh (hệ số biến thiên {cv:.2f} trong {len(m)} năm – "
                                       "doanh nghiệp có tính chu kỳ) → dự báo lợi nhuận có sai số lớn, nên xem cả 3 kịch bản.")
        if model == "nonfinancial":
            nwc = (res["drivers"].get("nwc_pct_revenue") or {}).get("value") or 0
            if company.get("sector") == "real_estate" or nwc > 0.5:
                res["warnings"].append(f"Vốn lưu động lớn ({nwc:.0%} doanh thu, đặc thù bất động sản/dự án) → FCFF rất nhạy "
                                       "với tiến độ dự án; DCF theo FCFF kém phù hợp, nên tham khảo RNAV.")

    @staticmethod
    def _gap(res, item, treatment, impact):
        res["data_gaps"].append({"item": item, "treatment": treatment, "impact": impact})
        res["warnings"].append(f"Thiếu dữ liệu {item}: {treatment}.")


def _years_between(a: pd.Timestamp, b: pd.Timestamp) -> float:
    """Số năm giữa hai ngày theo THÁNG lịch (cuối tháng → cuối tháng tròn tháng), phần lẻ theo ngày/30,44."""
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    months = (b.year - a.year) * 12 + (b.month - a.month)
    a_end, b_end = a.is_month_end, b.is_month_end
    frac = 0.0 if (a_end and b_end) else (b.day - a.day) / 30.44
    return (months + frac) / 12


def _path_value(pts: List[Dict[str, Any]], key: str, off: float) -> Optional[float]:
    """Giá trị tại 'off' năm sau cuối kỳ gốc, nội suy tuyến tính giữa hai điểm năm liền kề. Thiếu một đầu mút ⇒ None
    (không đoán), trừ khi 'off' trùng đúng một điểm năm."""
    off = min(max(off, 0.0), float(len(pts) - 1))
    i = min(int(math.floor(off)), len(pts) - 2)
    frac = off - i
    a, b = pts[i].get(key), pts[i + 1].get(key)
    if frac == 0:
        return a
    if frac == 1:
        return b
    return a + (b - a) * frac if a is not None and b is not None else None


def _interp(years: List[Dict[str, Any]], base_row: Dict[str, Any], model: str, offset: float,
            eq0: Optional[float], shares: float) -> Dict[str, Any]:
    """NTM = 12 tháng kết thúc tại (ngày dự báo + 12 tháng), KHÔNG phải năm tài chính kế tiếp.

    Mỗi điểm năm t là chỉ tiêu dòng 12 tháng kết thúc tại (cuối kỳ gốc + t năm); điểm 0 = kỳ gốc. Chỉ tiêu dòng NTM
    = nội suy tuyến tính tại offset = (ngày dự báo + 12 tháng − cuối kỳ gốc) / 1 năm. Số dư (VCSH) lấy tại thời điểm
    đầu và cuối cửa sổ NTM; ROE NTM = LNST mẹ NTM / VCSH bình quân hai thời điểm đó.
    Đã kiểm chứng trên chuỗi EBITDA TTM thật của Vietcap (xem tests/data/vci_ttm_ebitda_samples.json)."""
    if not years:
        return {}
    rev_key = "revenue" if model != "bank" else "total_operating_income"
    pts = [{"revenue": _num(base_row.get(rev_key)), "ebitda": _num(ebit_ebitda(pd.DataFrame([base_row]))[1].iloc[0])
            if model == "nonfinancial" else None,
            "ebitda_core": _num(core_ebit_ebitda(pd.DataFrame([base_row]))[1].iloc[0]) if model == "nonfinancial" else None,
            "net_income_parent": _num(base_row.get("net_income_parent")) if _num(base_row.get("net_income_parent")) is not None
            else _num(base_row.get("net_income")),
            "equity_parent": eq0}]
    pts += [{"revenue": y.get(rev_key), "ebitda": y.get("ebitda"), "ebitda_core": y.get("ebitda_core"),
             "net_income_parent": y.get("net_income_parent"), "equity_parent": y.get("equity_parent")} for y in years]
    out: Dict[str, Any] = {"offset_years": round(offset, 3), "window": "NTM (12 tháng kể từ ngày dự báo)"}
    if offset > len(years):
        out["note"] = "Ngày dự báo vượt quá tầm dự báo so với kỳ gốc"
        return out
    for k in ("revenue", "ebitda", "ebitda_core", "net_income_parent"):
        out[k] = _path_value(pts, k, offset)
    eq_end, eq_start = _path_value(pts, "equity_parent", offset), _path_value(pts, "equity_parent", max(offset - 1, 0.0))
    out["equity_parent"] = eq_end
    if out.get("net_income_parent") is not None:
        out["eps"] = out["net_income_parent"] / shares
    if eq_end is not None:
        out["bvps"] = eq_end / shares
        if eq_start is not None and out.get("net_income_parent") is not None and eq_start + eq_end > 0:
            out["roe"] = out["net_income_parent"] / ((eq_start + eq_end) / 2)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Kiểm tra sai số: dự báo 1 năm tới từ dữ liệu ĐẾN năm Y−1, so với thực tế năm Y (không look-ahead)
# ─────────────────────────────────────────────────────────────────────────────

def backtest_forecast(annual: pd.DataFrame, shares: float, company: Optional[Dict[str, str]] = None,
                      min_history: int = 4, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Mỗi năm Y: chỉ dùng các năm < Y (cắt bảng, không dùng as_of để tránh phụ thuộc lịch công bố), dự báo năm 1
    (kỳ gốc = năm Y−1) và so với số thực tế năm Y. Trả APE từng năm, MAPE, trung vị APE, sai lệch có dấu (bias)
    và tỷ lệ số thực tế nằm trong khoảng Bear–Bull."""
    fc = FinancialForecaster(config)
    a = annual[[int(k) % 10 == 0 for k in annual.index]].sort_index()
    model_type = (company or {}).get("type", "nonfinancial")
    key_rev = "total_operating_income" if model_type == "bank" else "revenue"
    rows = []
    for i in range(min_history, len(a)):
        train, actual = a.iloc[:i], a.iloc[i]
        y = int(a.index[i]) // 10
        r = fc.forecast(annual=train, shares=shares, company=company,
                        as_of=pd.Timestamp(year=y, month=1, day=1) + pd.DateOffset(months=4))
        if not r.get("available"):
            continue
        rec = {"year": y}
        for var, act_key in ((key_rev, key_rev), ("net_income_parent", "net_income_parent")):
            act = _num(actual.get(act_key))
            if var == "net_income_parent" and act is None:
                act = _num(actual.get("net_income"))
            yrs = {s: r["scenarios"][s]["years"][0].get(var) for s in SCEN}
            if act is None or yrs["base"] is None or act == 0:
                continue
            rec[f"{var}_actual"], rec[f"{var}_base"] = act, yrs["base"]
            rec[f"{var}_ape"] = abs(yrs["base"] / act - 1)
            rec[f"{var}_err"] = yrs["base"] / act - 1
            lo, hi = min(yrs.values()), max(yrs.values())
            rec[f"{var}_in_range"] = lo <= act <= hi
        rows.append(rec)
    df = pd.DataFrame(rows)
    summary = {}
    for var in (key_rev, "net_income_parent"):
        if f"{var}_ape" in df and df[f"{var}_ape"].notna().any():
            d = df[f"{var}_ape"].dropna()
            summary[var] = {"n": int(len(d)), "mape": float(d.mean()), "median_ape": float(d.median()),
                            "bias": float(df[f"{var}_err"].dropna().mean()),
                            "coverage": float(df[f"{var}_in_range"].dropna().mean())}
    return {"rows": df, "summary": summary}
