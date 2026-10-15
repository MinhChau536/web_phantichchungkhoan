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
còn lại → "Thấp". Các ngưỡng là giả định thiết kế, chỉnh ở config/investment_model.py (khóa "risk").
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from config.investment_model import load_config

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
    from analytics.financial_ratios import shares_series
    sh = shares_series(wide).dropna().tail(4)
    if len(sh) >= 2 and sh.iloc[0] > 0:
        n = len(sh) - 1
        cg = (sh.iloc[-1] / sh.iloc[0]) ** (1 / n) - 1
        if cg > rc.get("dilution_high", 0.10):
            add("Cao" if cg > 0.20 else "Trung bình", "Pha loãng",
                f"Số cổ phiếu tăng bình quân {cg * 100:.1f}%/năm trong {n} năm – pha loãng EPS "
                "(có thể do phát hành thêm hoặc cổ tức bằng cổ phiếu).", "Vốn điều lệ / số CP")

    # ── Định giá ──
    v = valuation or {}
    if v:
        if not v.get("methods"):
            why = "; ".join(f"{m}: {r}" for m, r in v.get("invalid", [])[:3]) or " ".join(v.get("notes", [])[:1])
            add("Cao", "Định giá", "Không có phương pháp định giá hợp lệ" + (f" – {why.rstrip('.')}." if why else "."), "Valuation Engine")
        elif v.get("confidence") == "Thấp":
            add("Cao", "Định giá", "Độ tin cậy định giá thấp (ít phương pháp hợp lệ hoặc kết quả phân tán lớn).", "Valuation Engine")
        if v.get("upside") is not None and v["upside"] < 0:
            add("Trung bình", "Định giá", f"Thị giá cao hơn giá mục tiêu 12 tháng ({v['upside']:+.1f}%).", "Valuation Engine")

    # ── Thị trường ──
    if price_df is not None and len(price_df) > 60 and "close" in price_df.columns:
        r = price_df["close"].astype(float).pct_change().dropna().tail(250)
        vol = float(r.std() * np.sqrt(252) * 100)
        mdd = float(((price_df["close"] / price_df["close"].cummax()) - 1).tail(250).min() * 100)
        if vol > 40:
            add("Trung bình", "Thị trường", f"Biến động giá cao: {vol:.0f}%/năm.", "Lịch sử giá 1 năm")
        if mdd < -35:
            add("Trung bình", "Thị trường", f"Mức sụt giảm tối đa trong năm {mdd:.0f}%.", "Lịch sử giá 1 năm")
        if "volume" in price_df.columns:
            gtgd = float((price_df["close"] * price_df["volume"]).tail(20).mean() / 1e9)
            if gtgd < 3:
                add("Trung bình", "Thị trường", f"Thanh khoản thấp: GTGD bình quân 20 phiên ~{gtgd:.1f} tỷ đồng.", "Lịch sử giao dịch")
    if trend and "giảm" in trend.lower():
        add("Thấp", "Thị trường", f"Xu hướng giá {trend.lower()} – rủi ro điều chỉnh ngắn hạn (chỉ dùng chọn thời điểm).", "Phân tích kỹ thuật")

    # ── Đặc thù ngành: cần theo dõi ──
    ind = (industry_text or "").lower()
    for keys, text in SECTOR_WATCH:
        if any(k in ind for k in keys):
            add("Cần theo dõi", "Ngành", text, "Đặc thù ngành")
            break
    return _pack(items)


def _pack(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = sorted(items, key=lambda i: SEV_RANK[i["severity"]])
    level = overall_level(items)
    return {"level": level, "hex": LEVEL_HEX[level], "severe": level == "Nghiêm trọng",
            "items": items, "counts": {s: sum(i["severity"] == s for i in items) for s in SEVERITIES},
            "rule": "Nghiêm trọng nếu có ≥ 1 rủi ro nghiêm trọng; Cao nếu ≥ 2 rủi ro cao; "
                    "Trung bình nếu 1 rủi ro cao hoặc ≥ 2 rủi ro trung bình; còn lại Thấp."}
