"""
core/khuyen_nghi.py – gộp từ 5 module (15/10/2026).

MỤC LỤC
  • analytics/risk_assessment.py – Risk Assessment – đánh giá rủi ro từ SỐ LIỆU THẬT (BCTC, lịch sử giá, kết quả định giá).
      hàm/lớp chính: overall_level, assess_risk
  • analytics/opportunity_score.py – Composite Investment Opportunity Score (0–100).
      hàm/lớp chính: OpportunityScorer
  • analytics/multilayer_reco.py – Khung khuyến nghị cổ phiếu ĐA LỚP – MỘT nhãn duy nhất cho mỗi mã (15/10/2026).
      hàm/lớp chính: percentile_rank, beneish_m, timing_layer, valuation_range, multilayer_recommendation
  • analytics/recommendation.py – Phần phụ của khuyến nghị: màu nhãn, gói kết quả tương thích ("recommendation") và giải trình định giá.
      hàm/lớp chính: not_enough_basis, compat_recommendation, explain_valuation
  • analytics/personalization.py – Báo cáo cá nhân hóa – điều chỉnh khuyến nghị & kế hoạch hành động theo HỒ SƠ NHÀ ĐẦU TƯ.
      hàm/lớp chính: normalize_profile, build_personal_report

Tên trùng giữa các phần đã được đổi (tên cũ → tên mới trong file này):
  multilayer_reco._num → _num_multilayer_reco
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/risk_assessment.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Risk Assessment – đánh giá rủi ro từ SỐ LIỆU THẬT (BCTC, lịch sử giá, kết quả định giá).

Mỗi rủi ro: {severity, category, text, source}. Mức độ: Nghiêm trọng / Cao / Trung bình / Thấp / Cần theo dõi.
Nhóm rủi ro (theo yêu cầu): suy giảm kinh doanh, đòn bẩy, chất lượng dòng tiền, pha loãng, định giá,
dữ liệu cũ/không đầy đủ, thị trường (biến động/thanh khoản), đặc thù ngành (chỉ "cần theo dõi" – không chấm điểm).

Rủi ro NGHIÊM TRỌNG (chặn khuyến nghị MUA, đưa về "CHƯA ĐỦ CƠ SỞ"):
  • Vốn chủ sở hữu ≤ 0                       • Lỗ 2 năm liên tiếp
  • Nợ vay/VCSH > 3 lần và EBIT không đủ trả lãi
  • CFO âm trong khi LNST dương 2 năm liên tiếp (trừ bất động sản – đặc thù vốn lưu động dự án)
  • BCTC năm gần nhất cũ hơn ngưỡng (mặc định 18 tháng)
  • Ngân hàng: VCSH/Tổng tài sản < 4%
Mức tổng thể: có rủi ro nghiêm trọng → "Nghiêm trọng"; ≥ 2 rủi ro cao → "Cao"; 1 cao hoặc ≥ 2 trung bình → "Trung bình";
còn lại → "Thấp". Các ngưỡng là giả định thiết kế, chỉnh ở core/cau_hinh.py (khóa "risk").
"""


import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from core.cau_hinh import load_config

SEVERITIES = ("Nghiêm trọng", "Cao", "Trung bình", "Thấp", "Cần theo dõi")
SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}
LEVEL_HEX = {"Nghiêm trọng": "#991b1b", "Cao": "#dc2626", "Trung bình": "#d97706", "Thấp": "#16a34a"}

SECTOR_WATCH = [
    (("ngân hàng", "ngan hang", "bank"), "Chất lượng tài sản (nợ xấu, chi phí dự phòng), biên lãi ròng (NIM) và hạn mức tăng trưởng tín dụng."),
    (("chứng khoán", "chung khoan", "securities"), "Thanh khoản thị trường ảnh hưởng phí môi giới; danh mục tự doanh và cho vay ký quỹ nhạy với biến động giá cổ phiếu."),
    (("bất động sản", "bat dong san", "real estate"), "Tiến độ pháp lý dự án, lãi suất và khả năng tiêu thụ/hàng tồn kho bất động sản."),
    (("thép", "thep", "vật liệu", "vlxd", "steel"), "Giá thép và nguyên liệu đầu vào (quặng, than cốc), nhu cầu xây dựng và các biện pháp phòng vệ thương mại."),
    (("công nghệ", "cong nghe", "technology", "viễn thông"), "Tỷ giá và nhu cầu CNTT tại thị trường nước ngoài, chi phí nhân sự kỹ thuật."),
    (("bán lẻ", "ban le", "tiêu dùng", "retail", "consumer"), "Sức mua tiêu dùng, biên lợi nhuận và chi phí mặt bằng."),
    (("dầu khí", "dau khi", "năng lượng", "oil", "energy"), "Giá dầu/khí thế giới và chính sách giá điện."),
    (("cảng", "logistics", "vận tải"), "Sản lượng hàng hóa thông qua, giá cước và cạnh tranh khu vực."),
    (("hóa chất", "phân bón", "chemical"), "Giá nguyên liệu và giá bán sản phẩm hóa chất/phân bón."),
    (("thủy sản", "dệt may", "textile", "seafood"), "Đơn hàng xuất khẩu, tỷ giá và rào cản thương mại tại thị trường chính."),
]


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _series(w: Optional[pd.DataFrame], c: str) -> pd.Series:
    return w[c].astype(float) if w is not None and not w.empty and c in w.columns else pd.Series(dtype=float)


def overall_level(items: List[Dict[str, Any]]) -> str:
    sev = [i["severity"] for i in items]
    if "Nghiêm trọng" in sev:
        return "Nghiêm trọng"
    n_high, n_mid = sev.count("Cao"), sev.count("Trung bình")
    if n_high >= 2:
        return "Cao"
    if n_high == 1 or n_mid >= 2:
        return "Trung bình"
    return "Thấp"


def assess_risk(wide: Optional[pd.DataFrame], ratios: Optional[pd.DataFrame], company: Dict[str, str], *,
                summary: Optional[Dict[str, Any]] = None, price_df: Optional[pd.DataFrame] = None,
                valuation: Optional[Dict[str, Any]] = None, health: Optional[Dict[str, Any]] = None,
                industry_text: str = "", trend: Optional[str] = None, as_of: Optional[pd.Timestamp] = None,
                config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = config or load_config()
    rc = cfg.get("risk", {})
    stale_m = cfg["valuation"]["stale_months"]
    ftype = (company or {}).get("type", "nonfinancial")
    sector = (company or {}).get("sector", "default")
    fin = ftype in ("bank", "securities", "insurance")
    items: List[Dict[str, Any]] = []

    def add(sev, cat, text, src):
        items.append({"severity": sev, "category": cat, "text": text, "source": src})

    if wide is None or wide.empty:
        add("Nghiêm trọng", "Dữ liệu", "Không có báo cáo tài chính năm – không thể đánh giá doanh nghiệp.", "BCTC")
        return _pack(items)

    last = ratios.iloc[-1] if ratios is not None and not ratios.empty else pd.Series(dtype=float)
    last_key = int(wide.index[-1])
    year = last_key // 10
    period_txt = f"BCTC năm {year}"

    # ── Dữ liệu cũ / thiếu ──
    ref = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.now()
    months_old = (ref.year - year) * 12 + ref.month - 12
    if months_old > stale_m:
        add("Nghiêm trọng", "Dữ liệu", f"BCTC năm gần nhất là {year} (~{months_old} tháng trước, ngưỡng {stale_m} tháng) – "
            "dữ liệu đã cũ, không đủ cơ sở khuyến nghị.", "BCTC")
    if health is not None and health.get("score") is None:
        add("Cao", "Dữ liệu", f"Số liệu BCTC chỉ phủ {health.get('coverage', 0) * 100:.0f}% trọng số chấm điểm sức khỏe tài chính "
            "(thiếu: " + ", ".join(health.get("missing", [])[:4]) + ").", "Financial Health Score")
    if len(wide) < 3:
        add("Trung bình", "Dữ liệu", f"Chỉ có {len(wide)} năm BCTC – xu hướng và định giá lịch sử kém tin cậy.", "BCTC")

    # ── Vốn chủ & thua lỗ ──
    eq = _num(wide["equity"].iloc[-1]) if "equity" in wide.columns else None
    if eq is not None and eq <= 0:
        add("Nghiêm trọng", "Đòn bẩy", f"Vốn chủ sở hữu âm ({eq / 1e9:,.0f} tỷ đồng) – âm vốn chủ.", period_txt)
    ni = _series(wide, "net_income_parent")
    if ni.dropna().empty:
        ni = _series(wide, "net_income")
    ni = ni.dropna()
    if len(ni) >= 2 and (ni.tail(2) < 0).all():
        add("Nghiêm trọng", "Suy giảm", "Lỗ 2 năm liên tiếp (" + ", ".join(f"{int(k) // 10}: {v / 1e9:,.0f} tỷ" for k, v in ni.tail(2).items()) + ").", "BCTC")
    elif len(ni) and ni.iloc[-1] < 0:
        add("Cao", "Suy giảm", f"Lỗ trong năm {year} ({ni.iloc[-1] / 1e9:,.0f} tỷ đồng) – P/E không áp dụng.", period_txt)

    # ── Suy giảm kinh doanh ──
    for lbl, key in (("Doanh thu" if not fin else "Tổng thu nhập hoạt động", "revenue_growth"),
                     ("Lợi nhuận sau thuế", "net_income_growth")):
        g = _num(last.get(key))
        if g is not None and g < 0:
            sev = "Cao" if g <= rc.get("decline_high", -25.0) else "Trung bình"
            add(sev, "Suy giảm", f"{lbl} giảm {abs(g):.1f}% so với năm trước.", period_txt)

    # ── Đòn bẩy ──
    if not fin:
        de, ic = _num(last.get("debt_to_equity")), _num(last.get("interest_coverage"))
        if de is not None and de > rc.get("de_severe", 3.0) and ic is not None and ic < 1:
            add("Nghiêm trọng", "Đòn bẩy", f"Nợ vay/VCSH {de:.2f} lần và EBIT chỉ bằng {ic:.2f} lần chi phí lãi vay – rủi ro mất khả năng trả nợ.", period_txt)
        elif de is not None and de > rc.get("de_high", 2.0):
            add("Cao", "Đòn bẩy", f"Đòn bẩy cao: nợ vay/VCSH {de:.2f} lần – nhạy với lãi suất.", period_txt)
        elif de is not None and de > 1:
            add("Trung bình", "Đòn bẩy", f"Nợ vay/VCSH {de:.2f} lần.", period_txt)
        if ic is not None and ic < rc.get("ic_high", 1.5) and not (de is not None and de > 3 and ic < 1):
            add("Cao", "Đòn bẩy", f"Khả năng trả lãi thấp: EBIT/chi phí lãi vay {ic:.2f} lần.", period_txt)
        cr = _num(last.get("current_ratio"))
        if cr is not None and cr < 1 and sector != "real_estate":
            add("Trung bình", "Thanh khoản", f"Thanh toán hiện hành {cr:.2f} lần (< 1) – áp lực thanh khoản ngắn hạn.", period_txt)
        alt = (summary or {}).get("altman") or {}
        if alt.get("score") is not None and "nguy" in str(alt.get("zone", "")).lower():
            add("Cao", "Đòn bẩy", f"Altman Z''-score {alt['score']:.2f} – {alt['zone']}.", "Mô hình Altman (2005)")
    else:
        eta = _num(last.get("equity_to_assets"))
        if ftype == "bank" and eta is not None:
            if eta < rc.get("bank_eta_severe", 4.0):
                add("Nghiêm trọng", "Đòn bẩy", f"VCSH/Tổng tài sản chỉ {eta:.1f}% – đệm vốn rất mỏng.", period_txt)
            elif eta < 6:
                add("Cao", "Đòn bẩy", f"VCSH/Tổng tài sản {eta:.1f}% (< 6%) – đệm vốn mỏng.", period_txt)
        pti = _num(last.get("provision_to_income"))
        if ftype == "bank" and pti is not None and pti > 40:
            add("Cao", "Chất lượng tài sản", f"Chi phí dự phòng chiếm {pti:.0f}% thu nhập hoạt động – áp lực nợ xấu.", period_txt)
        ldr = _num(last.get("loan_to_deposit"))
        if ftype == "bank" and ldr is not None and ldr > 115:
            add("Trung bình", "Thanh khoản", f"Dư nợ/tiền gửi khách hàng (giản đơn) {ldr:.0f}% – phụ thuộc vốn ngoài tiền gửi.", period_txt)
        lte = _num(last.get("liabilities_to_equity"))
        if ftype in ("securities", "insurance") and lte is not None and lte > 6:
            add("Cao", "Đòn bẩy", f"Nợ phải trả/VCSH {lte:.1f} lần.", period_txt)

    # ── Chất lượng dòng tiền (phi tài chính) ──
    if not fin and "cfo" in wide.columns:
        cfo = _series(wide, "cfo").dropna()
        ni_al = _series(wide, "net_income").reindex(cfo.index)
        both = (cfo < 0) & (ni_al > 0)
        if len(cfo) >= 2 and both.tail(2).all():
            sev = "Cao" if sector == "real_estate" else "Nghiêm trọng"
            add(sev, "Dòng tiền", "Dòng tiền kinh doanh âm trong khi báo lãi 2 năm liên tiếp – lợi nhuận chưa thành tiền"
                + (" (đặc thù vốn lưu động dự án BĐS)." if sector == "real_estate" else "."), "Lưu chuyển tiền tệ")
        elif len(cfo) and cfo.iloc[-1] < 0:
            add("Trung bình", "Dòng tiền", f"Dòng tiền kinh doanh năm {year} âm ({cfo.iloc[-1] / 1e9:,.0f} tỷ đồng).", "Lưu chuyển tiền tệ")
        elif len(cfo) >= 2 and (cfo.tail(2) < 0.5 * ni_al.tail(2)).all():
            add("Trung bình", "Dòng tiền", "CFO thấp hơn 50% LNST 2 năm liên tiếp – chất lượng lợi nhuận cần kiểm tra.", "Lưu chuyển tiền tệ")

    # ── Pha loãng ──
    from core.phan_tich_co_ban import shares_series
    sh = shares_series(wide).dropna().tail(4)
    if len(sh) >= 2 and sh.iloc[0] > 0:
        n = len(sh) - 1
        cg = (sh.iloc[-1] / sh.iloc[0]) ** (1 / n) - 1
        if cg > rc.get("dilution_high", 0.10):
            # Phân biệt PHA LOÃNG THẬT (phát hành thu tiền mới) với cổ phiếu thưởng / cổ tức bằng cổ phiếu
            # (không làm thay đổi giá trị cổ đông, chỉ chia nhỏ số cổ phiếu).
            iss = wide["equity_issued"].reindex(sh.index[1:]).abs() if "equity_issued" in wide.columns else None
            eq0 = wide["equity"].reindex(sh.index[:1]).iloc[0] if "equity" in wide.columns else None
            if iss is not None and iss.notna().any() and eq0 and eq0 > 0:
                raised = float(iss.fillna(0).sum()) / float(eq0) / n          # tiền thu mới / VCSH đầu kỳ, bình quân/năm
                if raised > 0.05:
                    add("Cao" if raised > 0.15 else "Trung bình", "Pha loãng",
                        f"Phát hành cổ phiếu thu tiền mới ≈ {raised * 100:.1f}% VCSH/năm trong {n} năm (số CP tăng "
                        f"{cg * 100:.1f}%/năm) – pha loãng thật đối với cổ đông hiện hữu.", "LCTT: tiền thu phát hành CP")
                else:
                    add("Cần theo dõi", "Cơ cấu cổ phần",
                        f"Số cổ phiếu tăng {cg * 100:.1f}%/năm nhưng tiền thu từ phát hành chỉ ≈ {raised * 100:.1f}% VCSH/năm "
                        "→ chủ yếu là cổ phiếu thưởng/cổ tức bằng cổ phiếu (không làm loãng giá trị); EPS các năm trước "
                        "cần điều chỉnh khi so sánh.", "Vốn điều lệ & LCTT")
            else:
                add("Trung bình", "Pha loãng",
                    f"Số cổ phiếu tăng bình quân {cg * 100:.1f}%/năm trong {n} năm – chưa xác định được là phát hành thu "
                    "tiền (pha loãng) hay cổ phiếu thưởng/cổ tức bằng cổ phiếu (không pha loãng).", "Vốn điều lệ / số CP")

    # ── Định giá ──
    v = valuation or {}
    if v:
        if not v.get("methods"):
            why = "; ".join(f"{m}: {r}" for m, r in v.get("invalid", [])[:3]) or " ".join(v.get("notes", [])[:1])
            add("Cao", "Định giá", "Không có phương pháp định giá hợp lệ" + (f" – {why.rstrip('.')}." if why else "."), "Valuation Engine")
        elif v.get("confidence") == "Thấp":
            add("Cao", "Định giá", "Độ tin cậy định giá thấp (ít phương pháp hợp lệ hoặc kết quả phân tán lớn).", "Valuation Engine")
        if v.get("upside") is not None and v["upside"] < 0:
            add("Trung bình", "Định giá", f"Thị giá cao hơn giá mục tiêu ({v['upside']:+.1f}%).", "Valuation Engine")

    # ── Thị trường ──
    if price_df is not None and len(price_df) > 60 and "close" in price_df.columns:
        r = price_df["close"].astype(float).pct_change().dropna().tail(250)
        vol = float(r.std() * np.sqrt(252) * 100)
        c1y = price_df["close"].astype(float).tail(250)          # chỉ 1 năm gần nhất (đỉnh cũng trong 1 năm)
        mdd = float(((c1y / c1y.cummax()) - 1).min() * 100)
        if vol > 40:
            add("Trung bình", "Thị trường", f"Biến động giá cao: {vol:.0f}%/năm.", "Lịch sử giá 1 năm")
        if mdd < -35:      # 14/10/2026: Trung bình → Cao (giảm > 35% trong năm là rủi ro thị trường đáng kể)
            add("Cao", "Thị trường", f"Mức sụt giảm tối đa trong năm {mdd:.0f}% (> 35%).", "Lịch sử giá 1 năm")
        if "volume" in price_df.columns:
            gtgd = float((price_df["close"] * price_df["volume"]).tail(20).mean() / 1e9)
            if gtgd < 3:
                add("Trung bình", "Thị trường", f"Thanh khoản thấp: GTGD bình quân 20 phiên ~{gtgd:.1f} tỷ đồng.", "Lịch sử giao dịch")
    strong_down = _strong_downtrend(price_df)
    if strong_down:
        # Không đẩy lên "Nghiêm trọng" (xu hướng chỉ dùng chọn thời điểm, không khóa khuyến nghị) – chỉ nâng mức rủi ro.
        add("Trung bình", "Thị trường", strong_down, "Phân tích kỹ thuật")
    elif trend and "giảm" in trend.lower():
        add("Thấp", "Thị trường", f"Xu hướng giá {trend.lower()} – rủi ro điều chỉnh ngắn hạn (chỉ dùng chọn thời điểm).", "Phân tích kỹ thuật")

    # ── Đặc thù ngành: cần theo dõi ──
    ind = (industry_text or "").lower()
    for keys, text in SECTOR_WATCH:
        if any(k in ind for k in keys):
            add("Cần theo dõi", "Ngành", text, "Đặc thù ngành")
            break
    return _pack(items)


def _strong_downtrend(price_df: Optional[pd.DataFrame]) -> Optional[str]:
    """Xu hướng giảm MẠNH và DÀI HẠN: giá dưới SMA200 và ADX ≥ 30 với −DI > +DI (phe bán áp đảo). None nếu không."""
    if price_df is None or len(price_df) < 210 or not {"high", "low", "close"} <= set(price_df.columns):
        return None
    try:
        from core.phan_tich_ky_thuat import TechnicalAnalyzer
        d = TechnicalAnalyzer(price_df.copy()).compute_all()
        last = d.iloc[-1]
        close, sma200 = float(last["close"]), float(last.get("SMA_200", np.nan))
        adx, pdi, mdi = (float(last.get(k, np.nan)) for k in ("ADX", "PLUS_DI", "MINUS_DI"))
    except Exception:
        return None
    if np.isnan(sma200) or np.isnan(adx) or np.isnan(pdi) or np.isnan(mdi):
        return None
    if close < sma200 and adx >= 30 and mdi > pdi:
        return (f"Xu hướng giảm mạnh: giá {close:,.0f} dưới SMA200 ({sma200:,.0f}, {close / sma200 - 1:+.0%}), ADX {adx:.0f} "
                f"với phe bán áp đảo (−DI {mdi:.0f} > +DI {pdi:.0f}) – dùng chọn thời điểm, không thay đổi giá mục tiêu.")
    return None


def _pack(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = sorted(items, key=lambda i: SEV_RANK[i["severity"]])
    level = overall_level(items)
    return {"level": level, "hex": LEVEL_HEX[level], "severe": level == "Nghiêm trọng",
            "items": items, "counts": {s: sum(i["severity"] == s for i in items) for s in SEVERITIES},
            "rule": "Nghiêm trọng nếu có ≥ 1 rủi ro nghiêm trọng; Cao nếu ≥ 2 rủi ro cao; "
                    "Trung bình nếu 1 rủi ro cao hoặc ≥ 2 rủi ro trung bình; còn lại Thấp."}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/opportunity_score.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Composite Investment Opportunity Score (0–100).

Aggregates technical, momentum, fundamental, valuation, and risk sub-scores.
Weights are configurable. Missing data is explicitly tracked – not set to 0.
"""


import logging
from typing import Any, Dict, List, Optional

from core.cau_hinh import DEFAULT_SCORE_WEIGHTS, SCORE_CATEGORIES

logger = logging.getLogger(__name__)


class OpportunityScorer:
    """
    Combine sub-scores into a composite Investment Opportunity Score.

    Score classification (configurable):
      80–100 : Cơ hội nổi bật
      65–79  : Tích cực
      50–64  : Trung tính
      35–49  : Thận trọng
       0–34  : Rủi ro cao

    IMPORTANT: This is a rule-based internal score, NOT a probability of gain.
    """

    def __init__(self, weights: Optional[Dict[str, int]] = None):
        self.weights = weights or DEFAULT_SCORE_WEIGHTS
        # Validate weights sum ≈ 100
        total = sum(self.weights.values())
        if total != 100:
            logger.warning("Score weights sum to %d, not 100. Normalizing.", total)
            self.weights = {k: v / total * 100 for k, v in self.weights.items()}

    def compute(
        self,
        technical_score: Optional[float],
        momentum_score: Optional[float],
        fundamental_score: Optional[float],
        valuation_score: Optional[float],
        risk_score: Optional[float] = None,
        missing_groups: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate sub-scores into a final composite score.

        Parameters
        ----------
        technical_score    : 0–100 from TechnicalAnalyzer
        momentum_score     : 0–100 from MomentumAnalyzer
        fundamental_score  : 0–100 from FundamentalAnalyzer
        valuation_score    : 0–100 from ValuationEngine
        risk_score         : 0–100 (lower risk = higher risk_score contribution)
        missing_groups     : list of group names with missing data
        """
        scores_input = {
            "technical": technical_score,
            "momentum": momentum_score,
            "fundamental": fundamental_score,
            "valuation": valuation_score,
            "risk": risk_score,
        }

        components: Dict[str, Any] = {}
        weighted_total = 0.0
        available_weight = 0.0

        for group, raw_score in scores_input.items():
            weight = self.weights.get(group, 0)
            if raw_score is None:
                components[group] = {
                    "score": None,
                    "weight": weight,
                    "contribution": None,
                    "status": "missing_data",
                    "reason": f"Không có dữ liệu {group}",
                }
            else:
                capped = max(0.0, min(100.0, float(raw_score)))
                contribution = capped * (weight / 100)
                weighted_total += contribution
                available_weight += weight
                components[group] = {
                    "score": round(capped, 1),
                    "weight": weight,
                    "contribution": round(contribution, 2),
                    "status": "ok",
                }

        # Normalize to available weight
        if available_weight == 0:
            final_score = None
            coverage = 0
            note = "Không đủ dữ liệu để chấm điểm"
        else:
            # Scale score to available weight
            normalized = (weighted_total / available_weight) * 100
            final_score = round(normalized)
            coverage = round(available_weight)
            if coverage < 100:
                note = f"Điểm tính trên {coverage}% trọng số – còn thiếu dữ liệu"
            else:
                note = "Đủ dữ liệu để chấm điểm toàn diện"

        classification = self._classify(final_score)

        return {
            "score": final_score,
            "classification": classification,
            "coverage_pct": coverage,
            "note": note,
            "components": components,
            "disclaimer": (
                "Đây là điểm quy tắc nội bộ, không phải xác suất sinh lời. "
                "Điểm cao không đảm bảo lợi nhuận. Luôn xem xét rủi ro và đa dạng hóa danh mục."
            ),
        }

    @staticmethod
    def _classify(score: Optional[float]) -> Dict[str, str]:
        if score is None:
            return {"label": "Chưa xác định", "color": "#90a4ae", "emoji": "❓"}
        for (lo, hi), (label, color, emoji) in SCORE_CATEGORIES.items():
            if lo <= score <= hi:
                return {"label": label, "color": color, "emoji": emoji}
        return {"label": "Chưa xác định", "color": "#90a4ae", "emoji": "❓"}

    # ─────────────────── Risk Score ───────────────────────────────────────────

    @staticmethod
    def compute_risk_score(
        volatility_30d: Optional[float] = None,
        max_drawdown: Optional[float] = None,
        beta: Optional[float] = None,
        debt_to_equity: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Compute risk score (0–100, higher = lower risk).

        Chỉ những thành phần CÓ dữ liệu mới được cộng vào mẫu số. Trước đây mẫu số
        luôn là 100 nên khi chỉ có Volatility + Drawdown, điểm tối đa chỉ đạt 60.

        Components:
          Volatility   (30)
          Drawdown     (30)
          Beta         (20)
          Debt/Equity  (20)
        """
        components: Dict[str, Any] = {}
        total = 0.0
        max_pts = 0

        # ── Volatility (30) ──
        if volatility_30d is not None:
            vol_ann = volatility_30d * (252 ** 0.5)
            if vol_ann < 0.2:
                s = 30
            elif vol_ann < 0.35:
                s = 22
            elif vol_ann < 0.5:
                s = 14
            elif vol_ann < 0.7:
                s = 7
            else:
                s = 2
            components["volatility"] = {"score": s, "max": 30, "annualized_vol": round(vol_ann * 100, 1)}
            total += s
            max_pts += 30

        # ── Drawdown (30) ──
        if max_drawdown is not None:
            mdd = abs(max_drawdown)
            if mdd < 0.10:
                s = 30
            elif mdd < 0.20:
                s = 22
            elif mdd < 0.30:
                s = 14
            elif mdd < 0.50:
                s = 7
            else:
                s = 2
            components["drawdown"] = {"score": s, "max": 30, "max_drawdown_pct": round(mdd * 100, 1)}
            total += s
            max_pts += 30

        # ── Beta (20) ──
        if beta is not None:
            if 0.5 <= beta <= 1.2:
                s = 20
            elif beta < 0.5:
                s = 15
            elif beta <= 1.5:
                s = 12
            else:
                s = 5
            components["beta"] = {"score": s, "max": 20, "value": round(beta, 2)}
            total += s
            max_pts += 20

        # ── Debt (20) ──
        if debt_to_equity is not None:
            if debt_to_equity <= 0.5:
                s = 20
            elif debt_to_equity <= 1.0:
                s = 14
            elif debt_to_equity <= 2.0:
                s = 7
            else:
                s = 2
            components["debt_equity"] = {"score": s, "max": 20, "value": round(debt_to_equity, 2)}
            total += s
            max_pts += 20

        if max_pts == 0:
            return {
                "score": None,
                "components": components,
                "coverage_pts": 0,
                "interpretation": "Không đủ dữ liệu",
            }
        final = round((total / max_pts) * 100)

        return {
            "score": final,
            "components": components,
            "coverage_pts": max_pts,
            "interpretation": "Rủi ro thấp" if final >= 70 else "Rủi ro trung bình" if final >= 50 else "Rủi ro cao",
        }

    @staticmethod
    def compute_market_health_score(
        advance_decline: Optional[float] = None,
        index_above_ma: Optional[bool] = None,
        avg_rsi: Optional[float] = None,
        foreign_net_buy: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Market Health Score 0–100.

        Components:
          Advance/Decline ratio (30)
          Index above SMA50     (25)
          Market avg RSI        (25)
          Foreign net buying    (20)
        """
        components: Dict[str, Any] = {}
        total = 0.0
        max_pts = 0

        # Advance/Decline (30)
        if advance_decline is not None:
            max_pts += 30
            if advance_decline > 2.0:
                s = 30
            elif advance_decline > 1.5:
                s = 22
            elif advance_decline > 1.0:
                s = 15
            elif advance_decline > 0.5:
                s = 8
            else:
                s = 2
            components["advance_decline"] = {"score": s, "max": 30, "ratio": round(advance_decline, 2)}
            total += s

        # Index above MA (25)
        if index_above_ma is not None:
            max_pts += 25
            s = 25 if index_above_ma else 5
            components["index_ma"] = {"score": s, "max": 25, "above_ma50": index_above_ma}
            total += s

        # Market RSI (25)
        if avg_rsi is not None:
            max_pts += 25
            if 50 <= avg_rsi <= 65:
                s = 25
            elif 40 <= avg_rsi < 50:
                s = 15
            elif avg_rsi > 65:
                s = 10
            else:
                s = 5
            components["market_rsi"] = {"score": s, "max": 25, "value": round(avg_rsi, 1)}
            total += s

        # Foreign (20)
        if foreign_net_buy is not None:
            max_pts += 20
            if foreign_net_buy > 0:
                s = 20
            elif foreign_net_buy > -100e9:
                s = 10
            else:
                s = 3
            components["foreign"] = {"score": s, "max": 20, "net_buy": foreign_net_buy}
            total += s

        # Chỉ chia cho tổng điểm của các thành phần có dữ liệu
        final = round((total / max_pts) * 100) if max_pts else None
        return {"score": final, "components": components}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/multilayer_reco.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Khung khuyến nghị cổ phiếu ĐA LỚP – MỘT nhãn duy nhất cho mỗi mã (15/10/2026).

Theo tài liệu "Khung khuyến nghị cổ phiếu đa lớp" v1.0 (người dùng cung cấp):
  Bước 1 – Bộ lọc loại trừ: vướng điều kiện → không được nhận MUA / TÍCH LŨY TỪNG PHẦN; thiếu dữ liệu → KHÔNG ĐỦ DỮ LIỆU.
  Bước 2 – Chấm 3 lớp nền tảng 0–100: Chất lượng (Q), Định giá (V), Tăng trưởng (G).
           F = 0,40·Q + 0,35·V + 0,25·G − điểm trừ rủi ro (tối đa 15).
           Trục So với thị trường (R, 16/10/2026): phân vị trong rổ VN30 + cùng ngành
           (động lượng 6T & 12-1T 60%, vị thế MA200 25%, LN kỳ vọng − Ke 15%); rổ < 10 mã → trục Thời điểm tuyệt đối.
  Bước 3 – Ma trận F × R:
                     R ≥ 60      40 ≤ R < 60          R < 40
       F ≥ 65        MUA         TÍCH LŨY TỪNG PHẦN   THEO DÕI
       55 ≤ F < 65   NẮM GIỮ     THEO DÕI             THEO DÕI
       F < 55        THEO DÕI    GIẢM TỶ TRỌNG/TRÁNH  GIẢM TỶ TRỌNG/TRÁNH
       MUA chỉ khi VN-Index trên MA200, LN kỳ vọng > Ke và định giá đủ tin cậy; nếu không → TÍCH LŨY TỪNG PHẦN.
  + khoảng định giá (thấp–cao), biên an toàn từ đầu thấp, độ phân tán > 40% → độ tin cậy định giá thấp.

Giới hạn (ghi rõ trong kết quả, không bịa số):
  • Thứ hạng phần trăm trong ngành chỉ dùng cho chỉ số có số liệu các mã cùng nhóm (P/E, P/B, ROE, Nợ/VCSH) và khi
    có ≥ min_peers_percentile mã; chỉ số khác dùng thang điểm tuyệt đối của Financial Health / định giá.
  • Ý kiến kiểm toán, cổ phiếu bị cảnh báo/kiểm soát, chậm công bố BCTC, cầm cố cổ phiếu, khối ngoại: nguồn dữ liệu
    hiện tại không có → "chưa kiểm tra được"; trọng số khối ngoại trong T chia lại cho các thành phần còn lại.
  • Chống đổi nhãn liên tục (hysteresis 3 điểm / 5 phiên) cần nhật ký nhãn – chưa làm (để sau).
Các ngưỡng là tham số khởi điểm, chưa hiệu chỉnh trên dữ liệu Việt Nam.
"""


from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

LABELS = {
    "MUA": "#16a34a",
    "TÍCH LŨY TỪNG PHẦN": "#0d9488",
    "NẮM GIỮ": "#d97706",
    "THEO DÕI": "#2563eb",
    "GIẢM TỶ TRỌNG / TRÁNH": "#dc2626",
    "KHÔNG ĐỦ DỮ LIỆU": "#64748b",
}
ACTION_TEXT = {
    "MUA": "Nền tảng mạnh và thời điểm thuận lợi: có thể mua theo kế hoạch tỷ trọng đã định.",
    "TÍCH LŨY TỪNG PHẦN": "Nền tảng mạnh nhưng chưa đủ mọi điều kiện MUA: chia vốn dự định thành 3 phần – phần đầu ngay, "
                          "các phần sau khi điểm so với thị trường R ≥ 60 (và VN-Index trên MA200) hoặc BCTC quý xác nhận luận điểm.",
    "NẮM GIỮ": "Nền tảng trung bình khá, cổ phiếu mạnh hơn thị trường: đang có thì tiếp tục nắm giữ; chưa có thì chưa ưu tiên mua mới.",
    "THEO DÕI": "Chưa đủ điều kiện giải ngân: đưa vào danh sách theo dõi, chờ nền tảng hoặc sức mạnh so với thị trường cải thiện.",
    "GIẢM TỶ TRỌNG / TRÁNH": "Nền tảng yếu và cổ phiếu không mạnh hơn thị trường: đang có thì giảm tỷ trọng; chưa có thì tránh mua.",
    "KHÔNG ĐỦ DỮ LIỆU": "Không đủ dữ liệu để chấm điểm – không tự điền số ước đoán.",
}
LAYER_NAMES = {"Q": "Chất lượng", "V": "Định giá", "G": "Tăng trưởng", "T": "Thời điểm", "R": "So với thị trường"}
DISCLAIMER = ("Thông tin tham khảo từ mô hình định lượng, không phải tư vấn đầu tư cá nhân hóa. Các ngưỡng là tham số khởi "
              "điểm, chưa hiệu chỉnh trên dữ liệu thị trường Việt Nam.")


def _num_multilayer_reco(v) -> Optional[float]:
    try:
        f = float(v)
        return f if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _clip(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return float(min(hi, max(lo, v)))


def _lin(v: Optional[float], x0: float, x1: float) -> Optional[float]:
    """Ánh xạ tuyến tính x0 → 0 điểm, x1 → 100 điểm (chặn 0–100)."""
    if v is None:
        return None
    return _clip((v - x0) / (x1 - x0) * 100)


def percentile_rank(value: Optional[float], peers: List[Optional[float]], higher_better: bool = True,
                    min_n: int = 5) -> Optional[float]:
    """Thứ hạng phần trăm 0–100 của value trong nhóm (cắt ngoại lệ phân vị 5%–95% như tài liệu)."""
    vals = [float(x) for x in peers if _num_multilayer_reco(x) is not None]
    if value is None or len(vals) < min_n:
        return None
    lo, hi = np.percentile(vals, 5), np.percentile(vals, 95)
    vals = [min(hi, max(lo, x)) for x in vals]
    v = min(hi, max(lo, float(value)))
    below = sum(1 for x in vals if x < v) + 0.5 * sum(1 for x in vals if x == v)
    p = below / len(vals) * 100
    return round(p if higher_better else 100 - p, 1)


def _avg(parts: List[Tuple[str, Optional[float], float]]) -> Tuple[Optional[float], List[Dict[str, Any]]]:
    """Bình quân gia quyền các thành phần có số liệu; trả kèm bảng thành phần."""
    rows = [{"name": n, "score": None if s is None else round(s, 1), "weight": w} for n, s, w in parts]
    ok = [(s, w) for _, s, w in parts if s is not None and w > 0]
    if not ok:
        return None, rows
    return round(sum(s * w for s, w in ok) / sum(w for _, w in ok), 1), rows


# ─────────────────────────────────────────────────────────────────────────────
# Beneish M-score (1999) – chỉ là cờ cảnh báo
# ─────────────────────────────────────────────────────────────────────────────

def beneish_m(wide: Optional[pd.DataFrame]) -> Optional[Dict[str, Any]]:
    """M = −4,84 + 0,92·DSRI + 0,528·GMI + 0,404·AQI + 0,892·SGI + 0,115·DEPI − 0,172·SGAI + 4,679·TATA − 0,327·LVGI.
    Cần 2 năm liền kề; thiếu biến → None (không ước đoán)."""
    if wide is None or wide.empty:
        return None
    a = wide[[int(k) % 10 == 0 for k in wide.index]].sort_index()
    if len(a) < 2:
        return None
    t, p = a.iloc[-1], a.iloc[-2]
    g = lambda r, k: _num_multilayer_reco(r.get(k))  # noqa: E731
    try:
        rev1, rev0 = g(t, "revenue"), g(p, "revenue")
        rec1, rec0 = g(t, "receivables"), g(p, "receivables")
        gp1 = g(t, "gross_profit") if g(t, "gross_profit") is not None else (rev1 - abs(g(t, "cogs"))) if g(t, "cogs") else None
        gp0 = g(p, "gross_profit") if g(p, "gross_profit") is not None else (rev0 - abs(g(p, "cogs"))) if g(p, "cogs") else None
        ca1, ca0 = g(t, "current_assets"), g(p, "current_assets")
        fa1, fa0 = g(t, "fixed_assets"), g(p, "fixed_assets")
        ta1, ta0 = g(t, "total_assets"), g(p, "total_assets")
        dep1, dep0 = abs(g(t, "depreciation") or 0) or None, abs(g(p, "depreciation") or 0) or None
        sga1 = abs(g(t, "selling_expense") or 0) + abs(g(t, "admin_expense") or 0)
        sga0 = abs(g(p, "selling_expense") or 0) + abs(g(p, "admin_expense") or 0)
        ni1, cfo1 = g(t, "net_income"), g(t, "cfo")
        cl1, cl0 = g(t, "current_liabilities"), g(p, "current_liabilities")
        ltd1, ltd0 = g(t, "long_term_debt") or 0, g(p, "long_term_debt") or 0
        need = [rev1, rev0, rec1, rec0, gp1, gp0, ca1, ca0, fa1, fa0, ta1, ta0, dep1, dep0, ni1, cfo1, cl1, cl0]
        if any(x is None for x in need) or min(rev0, rev1, ta0, ta1, gp1) <= 0 or sga0 <= 0 or sga1 <= 0:
            return None
        dsri = (rec1 / rev1) / (rec0 / rev0)
        gmi = (gp0 / rev0) / (gp1 / rev1)
        aqi = (1 - (ca1 + fa1) / ta1) / (1 - (ca0 + fa0) / ta0)
        sgi = rev1 / rev0
        depi = (dep0 / (dep0 + fa0)) / (dep1 / (dep1 + fa1))
        sgai = (sga1 / rev1) / (sga0 / rev0)
        tata = (ni1 - cfo1) / ta1
        lvgi = ((cl1 + ltd1) / ta1) / ((cl0 + ltd0) / ta0)
        m = (-4.84 + 0.92 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi + 0.115 * depi - 0.172 * sgai
             + 4.679 * tata - 0.327 * lvgi)
    except (ZeroDivisionError, TypeError):
        return None
    if not np.isfinite(m):
        return None
    return {"score": round(float(m), 2), "flag": m > -1.78,
            "parts": {k: round(float(v), 3) for k, v in (("DSRI", dsri), ("GMI", gmi), ("AQI", aqi), ("SGI", sgi),
                                                          ("DEPI", depi), ("SGAI", sgai), ("TATA", tata), ("LVGI", lvgi))}}


# ─────────────────────────────────────────────────────────────────────────────
# Lớp Thời điểm (T)
# ─────────────────────────────────────────────────────────────────────────────

def timing_layer(price_df: Optional[pd.DataFrame], index_df: Optional[pd.DataFrame], cfg: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"score": None, "components": [], "notes": [], "levels": {}}
    if price_df is None or price_df.empty or "close" not in price_df.columns:
        out["notes"].append("Không có dữ liệu giá.")
        return out
    c = pd.to_numeric(price_df["close"], errors="coerce").dropna().reset_index(drop=True)
    w = dict(cfg.get("weights_t") or {"momentum": 40, "ma": 30, "foreign": 20, "volume": 10})
    mom = ma = vol = None
    mom_txt = ma_txt = vol_txt = ""
    if len(c) >= 252:
        r = c.iloc[-21] / c.iloc[-252] - 1
        ex = r
        if index_df is not None and not index_df.empty and "close" in index_df.columns:
            ic = pd.to_numeric(index_df["close"], errors="coerce").dropna().reset_index(drop=True)
            if len(ic) >= 252:
                ex = r - (ic.iloc[-21] / ic.iloc[-252] - 1)
        mom = _lin(ex * 100, -30, 30)
        mom_txt = f"Lợi suất 12 tháng bỏ tháng gần nhất {r * 100:+.1f}%" + (f", so với VN-Index {ex * 100:+.1f} điểm %" if ex is not r else "")
    if len(c) >= 200:
        p, m50, m200 = float(c.iloc[-1]), float(c.tail(50).mean()), float(c.tail(200).mean())
        conds = [p > m50, p > m200, m50 > m200]
        ma = sum(conds) / 3 * 100
        ma_txt = (f"Giá {'trên' if conds[0] else 'dưới'} MA50, {'trên' if conds[1] else 'dưới'} MA200; "
                  f"MA50 {'trên' if conds[2] else 'dưới'} MA200")
        out["levels"] = {"ma50": m50, "ma200": m200, "price": p}
    if "volume" in price_df.columns and len(c) >= 60:
        v = pd.to_numeric(price_df["volume"], errors="coerce").dropna().reset_index(drop=True)
        if len(v) >= 60 and v.tail(60).mean() > 0:
            ratio = float(v.tail(20).mean() / v.tail(60).mean())
            r20 = float(c.iloc[-1] / c.iloc[-21] - 1) if len(c) > 21 else 0.0
            vol = _clip(50 + np.sign(r20) * max(-25.0, min(25.0, (ratio - 1) * 50)))
            vol_txt = f"KL 20 phiên / 60 phiên = {ratio:.2f} lần, giá 20 phiên {r20 * 100:+.1f}%"
    parts = [("Động lượng 12–1 tháng", mom, w.get("momentum", 40)), ("Xu hướng MA50/MA200", ma, w.get("ma", 30)),
             ("Mua/bán ròng khối ngoại 20 phiên", None, 0), ("Xu hướng khối lượng", vol, w.get("volume", 10))]
    score, rows = _avg(parts)
    for r_, txt in zip(rows, (mom_txt, ma_txt, "Chưa có dữ liệu khối ngoại – trọng số chia lại cho các thành phần khác", vol_txt)):
        r_["detail"] = txt
    out.update(score=score, components=rows)
    if mom is None:
        out["notes"].append("Chưa đủ 252 phiên để tính động lượng 12–1 tháng.")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Khuyến nghị
# ─────────────────────────────────────────────────────────────────────────────

def _closes(df: Optional[pd.DataFrame]) -> Optional[pd.Series]:
    if df is None or df.empty or "close" not in df.columns:
        return None
    c = pd.to_numeric(df["close"], errors="coerce").dropna().reset_index(drop=True)
    return c if len(c) else None


def relative_layer(symbol: str, price_df: Optional[pd.DataFrame], index_df: Optional[pd.DataFrame],
                   universe: Optional[Dict[str, pd.DataFrame]], valuation: Dict[str, Any], cfg: Dict[str, Any],
                   universe_label: str = "rổ so sánh") -> Dict[str, Any]:
    """Điểm SỨC MẠNH SO VỚI THỊ TRƯỜNG R (0–100) – thứ hạng % của mã trong rổ tham chiếu (VN30 + cùng ngành), nên trung vị
    luôn là 50. Thành phần (trọng số trong cfg['weights_r']):
      • Động lượng: 50% thứ hạng lợi suất 6 tháng + 50% thứ hạng lợi suất 12 tháng bỏ tháng gần nhất (Jegadeesh–Titman).
      • Vị trí so với MA200: thứ hạng của (giá / MA200 − 1).
      • Định giá so với ngưỡng tối thiểu: tổng LN kỳ vọng − Ke (−20 điểm % → 0, +20 → 100); chỉ khi định giá đủ tin cậy.
    Thêm trạng thái thị trường: VN-Index so với MA200."""
    w = dict(cfg.get("weights_r") or {"momentum": 60, "ma200": 25, "hurdle": 15})
    out: Dict[str, Any] = {"score": None, "components": [], "notes": [], "levels": {}, "rank": None, "universe_n": 0,
                           "market": {}, "hurdle": {}}
    rows = {}
    MIN_LEN = 220            # ~1 năm giao dịch (rổ lấy 365 ngày từ DNSE để không tốn lượt gọi vnstock)

    def feats(c):
        n = min(len(c), 250)
        return {"ret6": float(c.iloc[-1] / c.iloc[-126] - 1), "ret12_1": float(c.iloc[-21] / c.iloc[-n] - 1),
                "ma200": float(c.iloc[-1] / c.tail(200).mean() - 1)}
    for sym, df in (universe or {}).items():
        c = _closes(df)
        if c is None or len(c) < MIN_LEN:
            continue
        rows[sym] = feats(c)
    me = _closes(price_df)
    if me is not None and len(me) >= MIN_LEN:
        rows[symbol] = feats(me)
        p = float(me.iloc[-1]); m200 = float(me.tail(200).mean())
        out["levels"] = {"price": p, "ma200": m200, "ma50": float(me.tail(50).mean())}
    n_min = int(cfg.get("min_universe", 10))
    out["universe_n"] = len(rows)
    if symbol not in rows or len(rows) < n_min:
        out["notes"].append(f"Chưa đủ dữ liệu giá của {universe_label} (cần ≥ {n_min} mã có ≥ {MIN_LEN} phiên) – chưa xếp hạng được.")
        return out
    others = {k: v for k, v in rows.items()}
    def pr(key):
        return percentile_rank(rows[symbol][key], [v[key] for v in others.values()], True, n_min)
    mom = None
    p6, p12 = pr("ret6"), pr("ret12_1")
    if p6 is not None and p12 is not None:
        mom = 0.5 * p6 + 0.5 * p12
    ma_s = pr("ma200")
    hurdle_s = None
    er, ke = _num_multilayer_reco((valuation or {}).get("expected_return")), \
        _num_multilayer_reco(((valuation or {}).get("assumptions") or {}).get("ke"))
    if er is not None and ke is not None and (valuation or {}).get("confidence") in ("Cao", "Trung bình"):
        gap = er - ke * 100
        hurdle_s = _lin(gap, -20, 20)
        out["hurdle"] = {"er": er, "ke": ke * 100, "gap": gap, "pass": gap >= 0}
    else:
        out["hurdle"] = {"er": er, "ke": ke * 100 if ke is not None else None, "gap": None, "pass": None}
    r6 = rows[symbol]["ret6"] * 100; r12 = rows[symbol]["ret12_1"] * 100; dma = rows[symbol]["ma200"] * 100
    parts = [("Động lượng 6 & 12 tháng so với rổ (thứ hạng %)", mom, w.get("momentum", 60)),
             ("Giá so với MA200 so với rổ (thứ hạng %)", ma_s, w.get("ma200", 25)),
             ("LN kỳ vọng so với chi phí vốn Ke", hurdle_s, w.get("hurdle", 15))]
    score, comps = _avg(parts)
    comps[0]["detail"] = f"Lợi suất 6 tháng {r6:+.1f}%, 12 tháng bỏ tháng gần nhất {r12:+.1f}%"
    comps[1]["detail"] = f"Giá {'trên' if dma >= 0 else 'dưới'} MA200 {abs(dma):.1f}%"
    comps[2]["detail"] = (f"Tổng LN kỳ vọng {er:+.1f}% so với Ke {ke * 100:.1f}%" if hurdle_s is not None
                          else "Định giá chưa đủ tin cậy – không dùng")
    out.update(score=score, components=comps)
    comp = {k: 0.5 * (0.5 * percentile_rank(v["ret6"], [x["ret6"] for x in rows.values()], True, n_min)
                      + 0.5 * percentile_rank(v["ret12_1"], [x["ret12_1"] for x in rows.values()], True, n_min))
            + 0.5 * percentile_rank(v["ma200"], [x["ma200"] for x in rows.values()], True, n_min) for k, v in rows.items()}
    out["rank"] = (1 + sum(1 for k, v in comp.items() if v > comp[symbol] + 1e-9), len(comp))   # hạng 1 = mạnh nhất
    ic = _closes(index_df)
    if ic is not None and len(ic) >= 200:
        m = float(ic.tail(200).mean())
        out["market"] = {"close": float(ic.iloc[-1]), "ma200": m, "below": float(ic.iloc[-1]) < m}
    return out


def _liquidity_bn(price_df: Optional[pd.DataFrame]) -> Optional[float]:
    if price_df is None or price_df.empty or not {"close", "volume"} <= set(price_df.columns):
        return None
    t = price_df.tail(20)
    c = pd.to_numeric(t["close"], errors="coerce")
    unit = 1000.0 if c.median() < 1000 else 1.0
    val = (c * unit * pd.to_numeric(t["volume"], errors="coerce")).mean()
    return float(val) / 1e9 if pd.notna(val) else None


def valuation_range(valuation: Dict[str, Any]) -> Dict[str, Any]:
    vals = [float(m["fair"]) for m in (valuation or {}).get("methods") or [] if _num_multilayer_reco(m.get("fair"))]
    src = "các phương pháp hợp lệ"
    if len(vals) < 2:
        sc = (valuation or {}).get("scenarios") or {}
        vals = [float(sc[k]["target"]) for k in ("bear", "base", "bull") if _num_multilayer_reco((sc.get(k) or {}).get("target"))]
        src = "kịch bản Bear–Bull"
    if not vals:
        return {"available": False}
    lo, hi = min(vals), max(vals)
    price = _num_multilayer_reco((valuation or {}).get("price"))
    return {"available": True, "low": lo, "high": hi, "source": src, "n": len(vals),
            "dispersion": (hi - lo) / lo if lo > 0 else None,
            "margin_of_safety": (lo - price) / price * 100 if price else None,
            "methods": [m.get("name") for m in (valuation or {}).get("methods") or []]}


def _phrase(layer: str, r: Dict[str, Any], good: bool, universe_label: str = "rổ so sánh") -> str:
    """Câu lý do ủng hộ / rủi ro dễ đọc cho một thành phần điểm (thay cho 'Tên – 78/100')."""
    n, sc = r["name"], r["score"]
    tail = f" ({sc:.0f}/100)"
    det = r.get("detail")
    table = [
        ("Khả năng sinh lời", "Khả năng sinh lời tốt (ROE, ROA, biên lợi nhuận)", "Khả năng sinh lời thấp (ROE, ROA, biên lợi nhuận)"),
        ("Khả năng thanh toán", "Khả năng thanh toán ngắn hạn tốt", "Khả năng thanh toán ngắn hạn yếu"),
        ("Cơ cấu vốn", "Cơ cấu vốn an toàn, đòn bẩy thấp", "Đòn bẩy tài chính cao"),
        ("Chất lượng dòng tiền", "Lợi nhuận chuyển thành tiền tốt (CFO, FCF)", "Lợi nhuận chưa chuyển thành tiền (CFO, FCF yếu)"),
        ("An toàn vốn", "Vốn đệm an toàn tốt", "Vốn đệm an toàn mỏng"),
        ("Chất lượng tài sản", "Chất lượng tài sản tốt (nợ xấu thấp)", "Chất lượng tài sản đáng lo (nợ xấu cao)"),
        ("Huy động & cho vay", "Cơ cấu huy động – cho vay lành mạnh", "Cơ cấu huy động – cho vay căng"),
        ("ROE so với ngành", "ROE thuộc nhóm cao trong ngành", "ROE thấp hơn phần lớn doanh nghiệp cùng ngành"),
        ("Bội số", "Định giá rẻ so với lịch sử 5 năm và ngành (P/E, P/B…)", "Định giá đắt so với lịch sử 5 năm và ngành (P/E, P/B…)"),
        ("P/E so với ngành", "P/E thấp hơn phần lớn doanh nghiệp cùng ngành", "P/E cao hơn phần lớn doanh nghiệp cùng ngành"),
        ("Nhóm tăng trưởng", "Doanh thu và lợi nhuận tăng trưởng tốt", "Tăng trưởng doanh thu/lợi nhuận yếu"),
        ("Động lượng 6 & 12", f"Đà tăng giá 6–12 tháng mạnh hơn phần lớn {universe_label}",
         f"Đà giá 6–12 tháng yếu hơn phần lớn {universe_label}"),
        ("Giá so với MA200", f"Vị thế giá so với MA200 tốt hơn phần lớn {universe_label}",
         f"Vị thế giá so với MA200 kém hơn phần lớn {universe_label}"),
        ("LN kỳ vọng so với chi phí vốn", "Lợi nhuận kỳ vọng vượt chi phí vốn chủ sở hữu (Ke)",
         "Lợi nhuận kỳ vọng chưa bù được chi phí vốn chủ sở hữu (Ke)"),
        ("Động lượng 12–1", "Giá tăng mạnh hơn VN-Index trong 12 tháng", "Giá kém hơn VN-Index trong 12 tháng"),
        ("Xu hướng MA50/MA200", "Xu hướng giá tăng (trên MA50/MA200)", "Xu hướng giá giảm (dưới MA50/MA200)"),
        ("Xu hướng khối lượng", "Khối lượng ủng hộ chiều giá", "Khối lượng không ủng hộ chiều giá"),
    ]
    if n.startswith("Biên an toàn"):
        mos = r.get("value")
        txt = (f"Giá thấp hơn đầu dưới khoảng định giá {abs(mos):.0f}%" if good and mos is not None else
               f"Giá cao hơn đầu dưới khoảng định giá {abs(mos):.0f}% – biên an toàn mỏng" if mos is not None else
               ("Biên an toàn tốt" if good else "Biên an toàn mỏng"))
        return txt + tail
    if n.startswith("Biên LN gộp"):
        return n.replace("Biên LN gộp", "Biên LN gộp " + ("cải thiện" if good else "thu hẹp")) + tail
    for key, pos, neg in table:
        if key in n:
            return (pos if good else neg) + (f" – {det}" if det else "") + tail
    return f"{LAYER_NAMES.get(layer, layer)}: {n}" + tail



def multilayer_recommendation(*, health: Dict[str, Any], summary: Dict[str, Any], annual: Optional[pd.DataFrame],
                              quarterly: Optional[pd.DataFrame], price_df: Optional[pd.DataFrame],
                              index_df: Optional[pd.DataFrame], valuation: Dict[str, Any], multiples: Dict[str, Any],
                              peers: Dict[str, Any], company: Dict[str, str], risk: Dict[str, Any],
                              cfg: Dict[str, Any], ratios: Optional[pd.DataFrame] = None,
                              universe: Optional[Dict[str, pd.DataFrame]] = None, symbol: str = "",
                              universe_label: str = "VN30 + cùng ngành") -> Dict[str, Any]:
    c = cfg.get("multilayer") or {}
    ftype = (company or {}).get("type", "nonfinancial")
    sector = (company or {}).get("sector", "")
    bank = ftype == "bank"
    other_fin = ftype in ("securities", "insurance", "financial") and not bank
    min_peers = int(c.get("min_peers_percentile", 5))
    by_peer = (peers or {}).get("by_peer") or {}
    peer_vals = lambda k: [v.get(k) for v in by_peer.values()]  # noqa: E731
    notes: List[str] = []

    # ── Bước 1: bộ lọc loại trừ ──
    excl: List[Dict[str, Any]] = []

    def add_ex(text, status, detail=""):
        excl.append({"text": text, "status": status, "detail": detail})

    a = annual[[int(k) % 10 == 0 for k in annual.index]].sort_index() if annual is not None and not annual.empty else None
    nq = sum(1 for k in (quarterly.index if quarterly is not None and not quarterly.empty else []) if int(k) % 10)
    ny = len(a) if a is not None else 0
    nsess = len(price_df) if price_df is not None else 0
    data_ok = nsess >= int(c.get("min_sessions", 250)) and (nq >= int(c.get("min_quarters", 8)) or ny >= 3)
    add_ex("Đủ dữ liệu (≥ 8 quý/3 năm BCTC, ≥ 250 phiên)", "pass" if data_ok else "hit",
           f"{nq} quý, {ny} năm BCTC; {nsess} phiên" + ("" if nq >= 8 else " – dùng BCTC năm" if ny >= 3 else ""))
    eq = _num_multilayer_reco(a.iloc[-1].get("equity")) if a is not None and len(a) else None
    add_ex("Vốn chủ sở hữu dương", "unknown" if eq is None else ("pass" if eq > 0 else "hit"),
           "" if eq is None else f"VCSH {eq / 1e9:,.0f} tỷ")
    if a is not None and len(a) >= 2 and {"net_income", "cfo"} <= set(a.columns):
        last2 = a.tail(2)
        bad = bool(((last2["net_income"] > 0) & (last2["cfo"] < 0)).all())
        add_ex("Không có 2 năm liền LNST > 0 mà CFO < 0", "hit" if bad else "pass",
               "; ".join(f"{int(k) // 10}: LN {r['net_income'] / 1e9:,.0f}, CFO {r['cfo'] / 1e9:,.0f} tỷ"
                         for k, r in last2.iterrows() if pd.notna(r["net_income"]) and pd.notna(r["cfo"])))
    else:
        add_ex("Không có 2 năm liền LNST > 0 mà CFO < 0", "unknown", "Thiếu số liệu 2 năm")
    liq = _liquidity_bn(price_df)
    mn = float(c.get("min_liquidity_bn", 1.0))
    add_ex(f"Thanh khoản ≥ {mn:g} tỷ đồng/phiên (TB 20 phiên)", "unknown" if liq is None else ("pass" if liq >= mn else "hit"),
           "" if liq is None else f"{liq:,.1f} tỷ/phiên")
    if liq is not None and mn <= liq < float(c.get("liquidity_warn_bn", 5.0)):
        notes.append(f"Thanh khoản thấp ({liq:,.1f} tỷ/phiên) – giới hạn quy mô vị thế.")
    severe = [i for i in (risk or {}).get("items", []) if i.get("severity") == "Nghiêm trọng"]
    add_ex("Không có rủi ro nghiêm trọng (mô hình rủi ro)", "hit" if severe else "pass",
           "; ".join(i["text"] for i in severe[:2]))
    for t in ("Kiểm toán không từ chối / trái ngược", "Không bị cảnh báo / kiểm soát / đình chỉ GD",
              "Không chậm công bố BCTC"):
        add_ex(t, "unknown", "Chưa có nguồn dữ liệu – đối chiếu thủ công")
    excluded = [e for e in excl if e["status"] == "hit" and not e["text"].startswith("Đủ dữ liệu")]

    # ── Bước 2: bốn lớp ──
    groups = {g["key"]: g for g in (health or {}).get("groups", [])}
    # Q – Chất lượng
    qparts: List[Tuple[str, Optional[float], float]] = []
    for k, g in groups.items():
        if k != "growth":
            qparts.append((f"{g['label']} (sức khỏe TC)", _num_multilayer_reco(g.get("score")), float(g.get("weight") or 0)))
    wq = sum(w for _, _, w in qparts) or 1.0
    # 16/10/2026: bỏ Piotroski F-score khỏi Q – 9 tiêu chí của F-score (ROA, CFO, đòn bẩy, thanh toán, biên gộp, vòng quay)
    # trùng gần hết với 4 nhóm sinh lời/thanh toán/cơ cấu vốn/dòng tiền → bị tính 2 lần. F-score vẫn hiển thị và vẫn là
    # điều kiện làm sai luận điểm.
    qparts = [(n, s, w / wq * 70) for n, s, w in qparts]           # 70% từ các nhóm sức khỏe tài chính
    pio = (summary or {}).get("piotroski") or {}
    roe = ((peers or {}).get("self") or {}).get("roe")
    if roe is None and ratios is not None and not ratios.empty and "roe" in ratios.columns:
        roe = _num_multilayer_reco(ratios["roe"].dropna().iloc[-1]) if ratios["roe"].notna().any() else None
    roe_p = percentile_rank(roe, peer_vals("roe"), True, min_peers)
    qparts.append((f"ROE so với ngành (thứ hạng %)", roe_p, 30))
    Q, q_rows = _avg(qparts)
    # V – Định giá
    vr = valuation_range(valuation)
    conf = (valuation or {}).get("confidence")
    disp_hi = vr.get("dispersion") is not None and vr["dispersion"] > float(c.get("dispersion_low_conf", 0.40))
    if disp_hi:
        notes.append(f"Các phương pháp định giá lệch nhau {vr['dispersion'] * 100:.0f}% (> 40%) → độ tin cậy định giá thấp.")
    use_mos = vr.get("available") and conf in ("Cao", "Trung bình") and not disp_hi
    mos_s = _lin(vr.get("margin_of_safety"), -30, 30) if use_mos else None
    vparts = [("Bội số so với lịch sử 5 năm & ngành", _num_multilayer_reco((multiples or {}).get("score")), 50),
              ("Biên an toàn (đầu thấp khoảng định giá)", mos_s, 30)]
    rel = (multiples or {}).get("relative_valuation") or {}
    pe_p = percentile_rank(_num_multilayer_reco(rel.get("pe")), peer_vals("pe"), False, min_peers) if _num_multilayer_reco(rel.get("pe")) and rel.get("pe") > 0 else None
    vparts.append(("P/E so với ngành (thứ hạng %, thấp = tốt)", pe_p, 20))
    V, v_rows = _avg(vparts)
    for r_, k_, val_ in zip(v_rows, ("multiples", "margin_of_safety", "pe_rank"),
                            (None, vr.get("margin_of_safety") if use_mos else None, pe_p)):
        r_["key"], r_["value"] = k_, val_
    if not use_mos:
        notes.append("Định giá chưa đủ tin cậy → lớp Định giá không dùng biên an toàn, chỉ dùng bội số.")
    # G – Tăng trưởng
    gparts = [("Nhóm tăng trưởng (sức khỏe TC)", _num_multilayer_reco((groups.get("growth") or {}).get("score")), 70)]
    if not bank and ratios is not None and not ratios.empty and "gross_margin" in ratios.columns:
        gm = ratios["gross_margin"].dropna()
        if len(gm) >= 2:
            gparts.append((f"Biên LN gộp {gm.iloc[-1] - gm.iloc[-2]:+.1f} điểm %", _lin(gm.iloc[-1] - gm.iloc[-2], -3, 3), 30))
    G, g_rows = _avg(gparts)
    # R – Sức mạnh so với thị trường (thứ hạng trong rổ VN30 + cùng ngành); thiếu rổ → dùng điểm thời điểm tuyệt đối
    tl = relative_layer(symbol, price_df, index_df, universe, valuation, c, universe_label)
    if tl["score"] is None:
        abs_t = timing_layer(price_df, index_df, c)
        tl["score"], tl["components"] = abs_t["score"], abs_t["components"]
        tl["levels"] = tl["levels"] or abs_t["levels"]
        tl["notes"].append("R tạm tính theo thang tuyệt đối (động lượng, MA, khối lượng) – chưa so được với thị trường.")
        tl["fallback"] = True
    R = tl["score"]

    # điểm trừ rủi ro
    pen: List[Dict[str, Any]] = []
    alt = (summary or {}).get("altman") or {}
    if not bank and not other_fin and alt.get("zone"):
        if "Nguy cơ" in alt["zone"]:
            pen.append({"text": f"Altman Z'' {alt.get('score')} – {alt['zone']}", "points": 8})
        elif "cảnh báo" in alt["zone"].lower():
            pen.append({"text": f"Altman Z'' {alt.get('score')} – {alt['zone']}", "points": 3})
    bm = beneish_m(annual) if not bank and not other_fin else None
    if bm and bm["flag"]:
        pen.append({"text": f"Beneish M-score {bm['score']} > −1,78 (cờ cảnh báo, không chứng minh gian lận)", "points": 5})
    penalty = min(float(c.get("max_penalty", 15)), sum(p["points"] for p in pen))

    wf = c.get("weights_f") or {"Q": 0.4, "V": 0.35, "G": 0.25}
    lay = {"Q": Q, "V": V, "G": G}
    have = {k: v for k, v in lay.items() if v is not None}
    F = None
    if Q is not None and V is not None:
        F = round(sum(v * wf[k] for k, v in have.items()) / sum(wf[k] for k in have) - penalty, 1)

    # ── Bước 3: ma trận F × R + điều kiện MUA ──
    fs, fm = float(c.get("f_strong", 65)), float(c.get("f_mid", 55))
    rs, rw = float(c.get("r_strong", 60)), float(c.get("r_weak", 40))
    blocked = False
    gates: List[str] = []
    if not data_ok or F is None or R is None:
        label = "KHÔNG ĐỦ DỮ LIỆU"
        why = ("Không đủ dữ liệu: " + ("thiếu lịch sử giá/BCTC; " if not data_ok else "")
               + ("thiếu lớp Chất lượng hoặc Định giá; " if F is None else "") + ("thiếu điểm so với thị trường" if R is None else "")).rstrip("; ")
        row = col = None
    else:
        row = "strong" if F >= fs else "mid" if F >= fm else "weak"
        col = "good" if R >= rs else "mid" if R >= rw else "bad"
        label = MATRIX[(row, col)]
        f_txt = {"strong": "doanh nghiệp tốt", "mid": "nền tảng trung bình khá", "weak": "nền tảng yếu"}[row]
        r_txt = {"good": "mạnh hơn thị trường", "mid": "ngang thị trường", "bad": "yếu hơn thị trường"}[col]
        rk = tl.get("rank")
        rk_txt = f", xếp hạng sức mạnh giá {rk[0]}/{rk[1]} trong {universe_label}" if rk and not tl.get("fallback") else ""
        why = f"{f_txt[0].upper() + f_txt[1:]} (F {F:.0f}) và cổ phiếu {r_txt} (R {R:.0f}/100{rk_txt}) → {label}."
        if row == "strong" and col == "bad":
            why += f" Chờ R vượt {rw:.0f} hoặc giá lấy lại MA200 rồi xem xét lại."
        if row == "weak" and col == "good":
            why += " Đà giá thiếu nền tảng – rủi ro đầu cơ."
        if label == "MUA":
            mk = tl.get("market") or {}
            hd = tl.get("hurdle") or {}
            rk_ = tl.get("rank")
            top = float(c.get("leader_top_pct", 0.30))
            leader = bool(rk_ and not tl.get("fallback") and rk_[1] and top > 0 and rk_[0] <= math.ceil(top * rk_[1]))
            if c.get("market_gate", True) and mk.get("below"):
                if leader:
                    # 16/10/2026: cổ phiếu DẪN DẮT (top 30% sức mạnh giá trong rổ) được MUA dù thị trường chung dưới MA200
                    why += (f" VN-Index ({mk['close']:,.0f}) đang dưới MA200 ({mk['ma200']:,.0f}) nhưng cổ phiếu thuộc nhóm dẫn "
                            f"dắt (hạng {rk_[0]}/{rk_[1]}, top {top:.0%} rổ) → vẫn đủ điều kiện thị trường.")
                    notes.append("Thị trường chung đang dưới MA200 – MUA nhờ cổ phiếu thuộc nhóm dẫn dắt; nên giải ngân "
                                 "từng phần và theo dõi sát mức cắt lỗ.")
                else:
                    gates.append(f"VN-Index ({mk['close']:,.0f}) đang dưới MA200 ({mk['ma200']:,.0f}) – thị trường chung xu "
                                 f"hướng giảm và cổ phiếu chưa thuộc nhóm dẫn dắt (top {top:.0%} rổ)")
            if hd.get("pass") is None:
                gates.append("định giá chưa đủ tin cậy để xác nhận lợi nhuận kỳ vọng vượt chi phí vốn")
            elif not hd["pass"]:
                gates.append(f"tổng LN kỳ vọng {hd['er']:+.1f}% thấp hơn chi phí vốn Ke {hd['ke']:.1f}%")
            if gates:
                label = "TÍCH LŨY TỪNG PHẦN"
                why += " Chưa đủ điều kiện MUA vì " + "; ".join(gates) + " → TÍCH LŨY TỪNG PHẦN."
        if excluded and label in ("MUA", "TÍCH LŨY TỪNG PHẦN"):
            blocked = True
            why += f" Bị chặn bởi bộ lọc loại trừ ({excluded[0]['text'].lower()}) → THEO DÕI."
            label = "THEO DÕI"

    # ── nội dung bắt buộc ──
    comp_all = [(k, r) for k, rows_ in (("Q", q_rows), ("V", v_rows), ("G", g_rows), ("R", tl["components"]))
                for r in rows_ if r["score"] is not None]
    pros = [_phrase(k, r, True, universe_label) for k, r in sorted(comp_all, key=lambda x: -x[1]["score"])
            if r["score"] >= 60][:3]
    cons = [_phrase(k, r, False, universe_label) for k, r in sorted(comp_all, key=lambda x: x[1]["score"])
            if r["score"] < 45][:3]
    cons += [i["text"] for i in (risk or {}).get("items", []) if i.get("severity") in ("Nghiêm trọng", "Cao")][:max(0, 3 - len(cons))]
    inval = []
    if _num_multilayer_reco(pio.get("score")) is not None and not bank:
        inval.append(f"F-score giảm từ {int(pio['score'])} xuống ≤ {max(0, int(pio['score']) - 2)}.")
    inval.append("Tăng trưởng EPS 4 quý gần nhất (TTM) chuyển âm.")
    if not bank:
        inval.append("Dòng tiền kinh doanh (CFO) năm gần nhất chuyển âm.")
    if tl["levels"].get("ma200"):
        inval.append(f"Giá đóng cửa thủng MA200 (~{tl['levels']['ma200'] * (1000 if tl['levels']['ma200'] < 1000 else 1):,.0f} đ) "
                     "kèm khối ngoại bán ròng kéo dài (khối ngoại: theo dõi thủ công).")
    n_comp = sum(len(x) for x in (q_rows, v_rows, g_rows, tl["components"]))
    n_ok = sum(1 for x in (q_rows, v_rows, g_rows, tl["components"]) for r in x if r["score"] is not None)
    coverage = n_ok / n_comp if n_comp else 0.0
    n_peers = int((peers or {}).get("n") or 0)
    if coverage >= 0.8 and n_peers >= min_peers and not disp_hi and conf in ("Cao", "Trung bình"):
        reliab = "Cao"
    elif coverage < 0.6 or disp_hi or label == "KHÔNG ĐỦ DỮ LIỆU":
        reliab = "Thấp"
    else:
        reliab = "Trung bình"

    return {
        "available": label != "KHÔNG ĐỦ DỮ LIỆU", "label": label, "hex": LABELS[label], "action": ACTION_TEXT[label],
        "why": why, "blocked_by_exclusion": blocked,
        "F": F, "R": R, "T": R, "Q": Q, "V": V, "G": G, "penalty": penalty, "penalties": pen,   # "T" = tên cũ của R
        "layers": {"Q": q_rows, "V": v_rows, "G": g_rows, "R": tl["components"], "T": tl["components"]},
        "relative": {"rank": tl.get("rank"), "universe_n": tl.get("universe_n"), "universe": universe_label,
                     "market": tl.get("market"), "hurdle": tl.get("hurdle"), "fallback": bool(tl.get("fallback"))},
        "gates": gates,
        "row": row, "col": col, "exclusions": excl, "valuation_range": vr, "valuation_confidence": conf,
        "pros": pros, "cons": cons, "invalidation": inval,
        "reliability": {"level": reliab, "coverage": round(coverage * 100), "dispersion": vr.get("dispersion"),
                        "peers": n_peers},
        "liquidity_bn": liq, "beneish": bm, "notes": notes + tl["notes"],
        "thresholds": {"f_strong": fs, "f_mid": fm, "r_strong": rs, "r_weak": rw, "t_good": rs, "weights_f": dict(wf)},
        "disclaimer": DISCLAIMER,
    }


# Ma trận F × R (15/10/2026): cột = R ≥ 60 (mạnh hơn thị trường) · 40–60 (ngang) · < 40 (yếu hơn thị trường)
MATRIX = {("strong", "good"): "MUA", ("strong", "mid"): "TÍCH LŨY TỪNG PHẦN", ("strong", "bad"): "THEO DÕI",
          ("mid", "good"): "NẮM GIỮ", ("mid", "mid"): "THEO DÕI", ("mid", "bad"): "THEO DÕI",
          ("weak", "good"): "THEO DÕI", ("weak", "mid"): "GIẢM TỶ TRỌNG / TRÁNH", ("weak", "bad"): "GIẢM TỶ TRỌNG / TRÁNH"}
MATRIX_ROWS = [("F ≥ 65 (nền tảng mạnh)", "MUA", "TÍCH LŨY TỪNG PHẦN", "THEO DÕI"),
               ("55 ≤ F < 65 (trung bình khá)", "NẮM GIỮ", "THEO DÕI", "THEO DÕI"),
               ("F < 55 (nền tảng yếu)", "THEO DÕI", "GIẢM TỶ TRỌNG / TRÁNH", "GIẢM TỶ TRỌNG / TRÁNH")]


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/recommendation.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Phần phụ của khuyến nghị: màu nhãn, gói kết quả tương thích ("recommendation") và giải trình định giá.

15/10/2026: khuyến nghị DUY NHẤT đến từ khung đa lớp (core/khuyen_nghi.py). Hệ thống cũ (luật R1–R4
+ "hành động đề xuất") đã xóa. Khối "recommendation" trong kết quả phân tích giữ cùng các khóa cũ (rating, label,
reasons, expected_return, hex, color…) nhưng lấy nhãn từ khung đa lớp, để báo cáo/trang cũ đọc được.
"""


from typing import Any, Dict, List, Optional




def _rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


HEX: Dict[str, str] = dict(LABELS)
COLORS: Dict[str, tuple] = {k: _rgb(v) for k, v in HEX.items()}


def not_enough_basis(reason: str) -> Dict[str, Any]:
    """Không chạy được mô hình → KHÔNG ĐỦ DỮ LIỆU (không rơi về mô hình khác)."""
    lab = "KHÔNG ĐỦ DỮ LIỆU"
    return {"rating": lab, "label": lab, "expected_return": None, "fair_value": None, "upside": None,
            "color": COLORS[lab], "hex": HEX[lab], "reasons": [reason], "available": False}


def compat_recommendation(ml: Optional[Dict[str, Any]], valuation: Dict[str, Any], health: Dict[str, Any],
                          risk: Dict[str, Any]) -> Dict[str, Any]:
    """Gói "recommendation" (khóa cũ) từ kết quả khung đa lớp."""
    if not ml:
        return not_enough_basis("Không chạy được khung khuyến nghị đa lớp (xem Nhật ký lỗi) → không đủ dữ liệu.")
    lab = ml["label"]
    return {"rating": lab, "label": lab, "hex": ml["hex"], "color": _rgb(ml["hex"]), "reasons": [ml["why"]],
            "expected_return": (valuation or {}).get("expected_return"), "upside": (valuation or {}).get("upside"),
            "target_12m": (valuation or {}).get("target_12m"), "fair_value": (valuation or {}).get("target_12m"),
            "health_score": (health or {}).get("score"), "risk_level": (risk or {}).get("level"),
            "confidence": (valuation or {}).get("confidence"), "available": bool(ml.get("available")),
            "basis": "multilayer"}


def explain_valuation(symbol: str, health: Dict[str, Any], valuation: Dict[str, Any], risk: Dict[str, Any]) -> List[str]:
    """Giải trình sức khỏe tài chính + giá mục tiêu được tính thế nào (từng phương pháp, trọng số, upside, rủi ro)."""
    out: List[str] = []
    if health.get("score") is not None:
        g = ", ".join(f"{x['label']} {x['score']:.0f}" for x in health.get("groups", []) if x.get("score") is not None)
        out.append(f"Sức khỏe tài chính {health['score']:.1f}/100 ({health.get('rating_text', '')}) – điểm nhóm: {g}.")
    if valuation.get("methods"):
        parts = []
        for m in valuation["methods"]:
            mult = f" × {m['multiple']:.2f}x" if m.get("multiple") else ""
            br = (m.get("detail") or {}).get("bridge_per_share")
            if br is not None:
                mult += f" {'+' if br >= 0 else '−'} {abs(br):,.0f} (tiền ròng − LI CĐTS)/CP"
            base = f"{m['base_label']} {m['base']:,.0f}{mult} = " if m.get("base") is not None and m.get("multiple") else ""
            parts.append(f"{m['name']}: {base}{m['fair']:,.0f} (trọng số {m['weight'] * 100:.0f}%)")
        t = valuation.get("target_12m")
        out.append("Giá mục tiêu = bình quân có trọng số các phương pháp hợp lệ: " + "; ".join(parts)
                   + (f" → {t:,.0f} VND/cp." if t else "."))
        if valuation.get("expected_return") is not None:
            out.append(f"Upside = {t:,.0f}/{valuation['price']:,.0f} − 1 = {valuation['upside']:+.1f}%; cộng cổ tức tiền mặt dự kiến "
                       f"{valuation.get('expected_dividend', 0):,.0f} đ/cp ({valuation.get('dividend_yield', 0):.1f}%) → "
                       f"tổng lợi nhuận kỳ vọng {valuation['expected_return']:+.1f}% (giá ngày {valuation.get('price_date') or '—'}, "
                       f"BCTC đến {valuation.get('data_date') or '—'}, kỳ hạn {valuation.get('horizon_months', 12)} tháng).")
    for m, r in valuation.get("invalid", []):
        out.append(f"Không dùng {m}: {r}.")
    if risk.get("level"):
        out.append(f"Mức rủi ro tổng thể: {risk['level']} ({risk.get('rule', '')})")
    return out


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/personalization.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Báo cáo cá nhân hóa – điều chỉnh khuyến nghị & kế hoạch hành động theo HỒ SƠ NHÀ ĐẦU TƯ.

Đầu vào: kết quả StockService.full_analysis() (đã có khối "investment") + hồ sơ:
    risk     : "conservative" | "balanced" | "aggressive"   (khẩu vị rủi ro)
    horizon  : "short" | "medium" | "long"                  (< 6 tháng | 6–12 tháng | > 12 tháng)
    goal     : "growth" | "income" | "balanced"             (tăng trưởng | cổ tức | cân bằng)
    holder   : True/False (đang nắm giữ?), cost (giá vốn, đ/cp), qty (số cp đang có)
    capital  : tổng vốn đầu tư (đ) – để tính tỷ trọng & số cổ phiếu gợi ý
    name     : tên hiển thị trên báo cáo (tùy chọn)

Cách cá nhân hóa (không tạo dữ liệu mới, chỉ dùng lại kết quả định giá/sức khỏe/rủi ro đã tính):
  1. Nhãn khuyến nghị dùng CHUNG cho mọi hồ sơ (khung đa lớp) – không sinh nhãn riêng.
  2. Lớp phù hợp cá nhân: rủi ro vượt khẩu vị → giảm một nửa tỷ trọng; mục tiêu/kỳ hạn/biến động không khớp → cảnh báo.
  3. Kế hoạch hành động: tỷ trọng tối đa = trần theo khẩu vị × hệ số mức rủi ro; cắt lỗ = max(giá − k×ATR, giá × (1 − lỗ tối đa));
     chốt lời = giá mục tiêu Base (Bull với nhà đầu tư mạo hiểm). Lô chẵn 100 cp.
Mọi ngưỡng là GIẢ ĐỊNH THIẾT KẾ, sửa trong PROFILES.
"""


import copy
import math
from typing import Any, Dict, List, Optional

import pandas as pd

RISK_LABEL = {"conservative": "Thận trọng", "balanced": "Cân bằng", "aggressive": "Mạo hiểm"}
HORIZON_LABEL = {"short": "Ngắn hạn (< 6 tháng)", "medium": "Trung hạn (6–12 tháng)", "long": "Dài hạn (> 12 tháng)"}
GOAL_LABEL = {"growth": "Tăng trưởng vốn", "income": "Thu nhập cổ tức", "balanced": "Cân bằng"}

PROFILES: Dict[str, Dict[str, Any]] = {
    "conservative": {
        "max_weight": 0.05, "atr_k": 1.5, "max_loss": 0.07, "max_vol": 30.0, "max_risk": "Trung bình", "tp": "base",
    },
    "balanced": {
        "max_weight": 0.10, "atr_k": 2.0, "max_loss": 0.10, "max_vol": 40.0, "max_risk": "Cao", "tp": "base",
    },
    "aggressive": {
        "max_weight": 0.15, "atr_k": 2.5, "max_loss": 0.15, "max_vol": 60.0, "max_risk": "Cao", "tp": "bull",
    },
}
RISK_FACTOR = {"Thấp": 1.0, "Trung bình": 0.75, "Cao": 0.5}
_RISK_RANK = {"Thấp": 0, "Trung bình": 1, "Cao": 2, "Nghiêm trọng": 3}
INCOME_MIN_YIELD = 3.0        # % tỷ suất cổ tức tối thiểu cho mục tiêu thu nhập
GROWTH_MIN_SCORE = 60         # điểm nhóm Tăng trưởng tối thiểu cho mục tiêu tăng trưởng

DEFAULT_PROFILE = {"risk": "balanced", "horizon": "medium", "goal": "balanced", "holder": False,
                   "cost": None, "qty": None, "capital": None, "name": ""}


def _f(x) -> Optional[float]:
    try:
        v = float(x)
        return None if math.isnan(v) or math.isinf(v) else v
    except (TypeError, ValueError):
        return None


def _annual_vol(px: Optional[pd.DataFrame]) -> Optional[float]:
    if px is None or px.empty or "close" not in px.columns:
        return None
    r = px["close"].astype(float).pct_change().dropna().tail(252)
    return float(r.std() * math.sqrt(252) * 100) if len(r) >= 40 else None


def _last_atr(px: Optional[pd.DataFrame]) -> Optional[float]:
    if px is None or px.empty:
        return None
    if "ATR" in px.columns and px["ATR"].notna().any():
        return float(px["ATR"].dropna().iloc[-1])
    if {"high", "low", "close"} <= set(px.columns) and len(px) >= 15:
        h, l, c = px["high"].astype(float), px["low"].astype(float), px["close"].astype(float)
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        return float(tr.tail(14).mean())
    return None


def normalize_profile(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    p = {**DEFAULT_PROFILE, **(profile or {})}
    if p["risk"] not in PROFILES:
        p["risk"] = "balanced"
    if p["horizon"] not in HORIZON_LABEL:
        p["horizon"] = "medium"
    if p["goal"] not in GOAL_LABEL:
        p["goal"] = "balanced"
    p["holder"] = bool(p.get("holder"))
    p["cost"] = _f(p.get("cost")) if p["holder"] else None
    p["qty"] = int(_f(p.get("qty")) or 0) if p["holder"] else None
    cap = _f(p.get("capital"))
    p["capital"] = cap if cap and cap > 0 else None
    return p


def build_personal_report(analysis: Dict[str, Any], profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """→ dict dùng cho mục PDF 'Báo cáo cá nhân hóa' và phần xem trước trên app."""
    from core.khuyen_nghi import COLORS, HEX

    p = normalize_profile(profile)
    prof = PROFILES[p["risk"]]
    inv = analysis.get("investment") or {}
    health, val, risk = inv.get("health") or {}, inv.get("valuation") or {}, inv.get("risk") or {}
    rec = inv.get("recommendation") or {}
    ml = inv.get("multilayer") or {}
    label = ml.get("label") or rec.get("label") or "KHÔNG ĐỦ DỮ LIỆU"
    reasons = [ml["why"]] if ml.get("why") else list(rec.get("reasons") or [])

    tech = analysis.get("technical") or {}
    px = tech.get("data") if isinstance(tech.get("data"), pd.DataFrame) else None
    signals = tech.get("signals") or {}
    trend = (signals.get("trend") or {}).get("name")
    sr = signals.get("support_resistance") or {}
    price = _f(val.get("price")) or _f((analysis.get("current_price") or {}).get("price"))
    if px is not None and not px.empty and price and float(px["close"].iloc[-1]) < 1000 <= price:
        px = px.copy()
        for c in ("open", "high", "low", "close", "ATR"):
            if c in px.columns:
                px[c] = px[c] * 1000.0
    level = risk.get("level")
    hs = _f(health.get("score"))
    er = _f(val.get("expected_return"))
    dy = _f(val.get("dividend_yield"))
    vol = _annual_vol(px)
    atr = _last_atr(px)
    growth_g = next((g for g in health.get("groups", []) if g.get("key") == "growth"), None)
    growth_s = _f((growth_g or {}).get("score"))

    # ── Lớp phù hợp cá nhân ──
    over_risk = level is not None and _RISK_RANK.get(level, 0) > _RISK_RANK[prof["max_risk"]]
    if over_risk:
        reasons.append(f"Mức rủi ro tổng thể {str(level).upper()} vượt khẩu vị {RISK_LABEL[p['risk']].lower()} "
                       f"(tối đa: {prof['max_risk'].lower()}) → nếu giải ngân, chỉ dùng một nửa tỷ trọng tối đa của hồ sơ.")

    fit: List[Dict[str, Any]] = []

    def add(crit, mine, stock, status, note=""):
        fit.append({"criterion": crit, "profile": mine, "stock": stock, "status": status, "note": note})

    add("Mức rủi ro tổng thể", f"Tối đa: {prof['max_risk']}", level or "—",
        "bad" if over_risk else "ok" if level else "warn",
        "Vượt khẩu vị" if over_risk else "Trong khẩu vị" if level else "Chưa đánh giá được")
    if vol is not None:
        add("Biến động giá (năm hóa)", f"≤ {prof['max_vol']:.0f}%", f"{vol:.0f}%",
            "ok" if vol <= prof["max_vol"] else "warn" if vol <= prof["max_vol"] * 1.25 else "bad",
            "Phù hợp" if vol <= prof["max_vol"] else "Biến động cao hơn mức bạn chịu được")
    else:
        add("Biến động giá (năm hóa)", f"≤ {prof['max_vol']:.0f}%", "—", "warn", "Thiếu lịch sử giá")
    if p["goal"] == "income":
        add("Mục tiêu cổ tức", f"Tỷ suất ≥ {INCOME_MIN_YIELD:.0f}%", f"{dy:.1f}%" if dy is not None else "—",
            "ok" if (dy or 0) >= INCOME_MIN_YIELD else "bad",
            "Đạt" if (dy or 0) >= INCOME_MIN_YIELD else "Cổ tức tiền mặt thấp/không đều – ít phù hợp mục tiêu thu nhập")
    elif p["goal"] == "growth":
        add("Mục tiêu tăng trưởng", f"Điểm tăng trưởng ≥ {GROWTH_MIN_SCORE}",
            f"{growth_s:.0f}/100" if growth_s is not None else "—",
            "ok" if (growth_s or 0) >= GROWTH_MIN_SCORE else "warn" if growth_s is not None else "warn",
            "Tăng trưởng tốt" if (growth_s or 0) >= GROWTH_MIN_SCORE else "Tăng trưởng chưa nổi bật")
    else:
        add("Mục tiêu cân bằng", "Sức khỏe ≥ 60 & có cổ tức",
            f"{hs:.0f}/100 · cổ tức {dy:.1f}%" if hs is not None and dy is not None else "—",
            "ok" if (hs or 0) >= 60 and (dy or 0) > 0 else "warn", "")
    if p["horizon"] == "short":
        down = bool(trend) and any(k in trend.lower() for k in ("giảm", "down"))
        add("Kỳ hạn đầu tư", HORIZON_LABEL["short"], f"Xu hướng: {trend or '—'}",
            "bad" if down else "warn",
            "Mô hình định giá có kỳ hạn 12 tháng; ngắn hạn phụ thuộc xu hướng kỹ thuật"
            + (" – xu hướng đang giảm" if down else ""))
        if label in ("MUA", "TÍCH LŨY TỪNG PHẦN") and down:
            reasons.append("Kỳ hạn ngắn nhưng xu hướng kỹ thuật đang giảm → chờ tín hiệu đảo chiều trước khi giải ngân.")
    elif p["horizon"] == "long":
        add("Kỳ hạn đầu tư", HORIZON_LABEL["long"], f"Sức khỏe {hs:.0f}/100" if hs is not None else "—",
            "ok" if (hs or 0) >= 70 else "warn",
            "Nắm giữ dài hạn cần doanh nghiệp khỏe bền vững" if (hs or 0) < 70 else "Nền tảng phù hợp nắm giữ dài")
    else:
        add("Kỳ hạn đầu tư", HORIZON_LABEL["medium"], "Giá mục tiêu", "ok", "Khớp kỳ hạn mô hình")
    add("Độ tin cậy định giá", "≥ Trung bình", val.get("confidence") or "—",
        "ok" if val.get("confidence") in ("Cao", "Trung bình") else "bad", "")

    score_map = {"ok": 1.0, "warn": 0.5, "bad": 0.0}
    fit_score = round(sum(score_map[f["status"]] for f in fit) / len(fit) * 100) if fit else None
    fit_text = ("Phù hợp" if fit_score is not None and fit_score >= 75 else
                "Phù hợp một phần" if fit_score is not None and fit_score >= 50 else "Ít phù hợp")

    # ── Kế hoạch hành động ──
    plan: Dict[str, Any] = {"weight": 0.0, "shares": None, "amount": None, "stop": None, "take_profit": None,
                            "entry_low": None, "entry_high": None}
    if price:
        stops = [price * (1 - prof["max_loss"])]
        if atr:
            stops.append(price - prof["atr_k"] * atr)
        plan["stop"] = max(stops)
        plan["stop_basis"] = (f"max(giá − {prof['atr_k']}×ATR, giá × (1 − {prof['max_loss'] * 100:.0f}%))" if atr
                              else f"giá × (1 − {prof['max_loss'] * 100:.0f}%)")
        scen = val.get("scenarios") or {}
        tp = _f((scen.get(prof["tp"]) or {}).get("target")) or _f(val.get("target_12m"))
        plan["take_profit"] = tp
        plan["tp_basis"] = "Giá mục tiêu kịch bản Tích cực (Bull)" if prof["tp"] == "bull" and _f((scen.get("bull") or {}).get("target")) \
            else "Giá mục tiêu (Base)"
        sup = [s for s in (sr.get("support") or []) if _f(s) and _f(s) < price]
        if sup:
            sup1 = float(sup[0]) * (1000.0 if float(sup[0]) < 1000 <= price else 1.0)
            plan["entry_low"] = max(sup1, plan["stop"])
        elif atr:
            plan["entry_low"] = max(price - atr, plan["stop"])
        plan["entry_high"] = price
    # Khung khuyến nghị đa lớp: MỘT nhãn chung cho mọi hồ sơ – cá nhân hóa chỉ đổi MỨC PHÙ HỢP và TỶ TRỌNG.
    buy_now = label in ("MUA", "TÍCH LŨY TỪNG PHẦN")
    if buy_now and level:
        plan["weight"] = prof["max_weight"] * RISK_FACTOR.get(level, 0.5) * (0.5 if over_risk else 1.0)
    if buy_now and p["capital"] and price:
        plan["amount"] = p["capital"] * plan["weight"]
        plan["shares"] = int(plan["amount"] // (price * 100)) * 100
        if plan["shares"] == 0:
            plan["note_lot"] = "Vốn × tỷ trọng chưa đủ mua 1 lô 100 cp."

    # ── Danh mục đang nắm giữ ──
    holding = None
    if p["holder"] and p["cost"] and price:
        pnl = (price / p["cost"] - 1) * 100
        qty = p["qty"] or 0
        holding = {"cost": p["cost"], "qty": qty, "pnl_pct": pnl, "pnl_value": (price - p["cost"]) * qty if qty else None,
                   "market_value": price * qty if qty else None,
                   "to_target": ((plan["take_profit"] / price - 1) * 100) if plan.get("take_profit") else None}
        if p["capital"] and qty:
            holding["weight_now"] = price * qty / p["capital"] * 100
        if label in ("BÁN", "GIẢM TỶ TRỌNG / TRÁNH"):
            holding["action"] = "Cân nhắc bán/giảm tỷ trọng: tổng lợi nhuận kỳ vọng dưới ngưỡng bán của hồ sơ."
        elif plan.get("stop") and pnl <= -prof["max_loss"] * 100:
            holding["action"] = (f"Khoản lỗ {pnl:.1f}% đã vượt mức lỗ tối đa {prof['max_loss'] * 100:.0f}% của hồ sơ → "
                                 "xem lại luận điểm, cân nhắc cắt lỗ.")
        elif holding["to_target"] is not None and holding["to_target"] <= 3:
            holding["action"] = "Giá đã gần/vượt mục tiêu → cân nhắc chốt lời một phần."
        elif p["capital"] and holding.get("weight_now", 0) > prof["max_weight"] * 100 * 1.5:
            holding["action"] = (f"Tỷ trọng hiện tại {holding['weight_now']:.1f}% cao hơn nhiều mức tối đa "
                                 f"{prof['max_weight'] * 100:.0f}% → cân nhắc giảm bớt để phân tán rủi ro.")
        else:
            holding["action"] = "Tiếp tục nắm giữ, đặt cắt lỗ theo kế hoạch bên dưới."

    # ── Tóm tắt ──
    who = p["name"].strip() or "nhà đầu tư"
    summary = (f"Với hồ sơ {RISK_LABEL[p['risk']].lower()}, {HORIZON_LABEL[p['horizon']].lower()}, mục tiêu "
               f"{GOAL_LABEL[p['goal']].lower()}, khuyến nghị (chung cho mọi hồ sơ): {label}. "
               f"Mức độ phù hợp của cổ phiếu với hồ sơ: {fit_text.lower()}"
               + (f" ({fit_score}/100)." if fit_score is not None else "."))
    if buy_now and plan["weight"]:
        summary += f" Tỷ trọng tối đa gợi ý {plan['weight'] * 100:.1f}% danh mục."
    std = label

    return {"profile": p, "profile_text": {"risk": RISK_LABEL[p["risk"]], "horizon": HORIZON_LABEL[p["horizon"]],
                                           "goal": GOAL_LABEL[p["goal"]]},
            "label": label, "rule": None, "reasons": reasons, "standard_label": std,
            "color": COLORS.get(label, (100, 116, 139)), "hex": HEX.get(label, "#64748b"),
            "settings": dict(prof),
            "fit": fit, "fit_score": fit_score, "fit_text": fit_text, "plan": plan, "holding": holding,
            "price": price, "volatility": vol, "atr": atr, "summary": summary}
