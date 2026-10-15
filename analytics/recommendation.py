"""
Hệ thống khuyến nghị (dùng chung cho ứng dụng và báo cáo PDF).

Bước 1 – theo định giá (giống hệ thống khuyến nghị của các CTCK, vd VCBS):
    Lợi suất kỳ vọng = (Giá trị hợp lý / Giá hiện tại − 1) + Tỷ suất cổ tức tiền mặt
      MUA        : lợi suất kỳ vọng ≥ +15%
      TRUNG LẬP  : −15% < lợi suất kỳ vọng < +15%
      BÁN        : lợi suất kỳ vọng ≤ −15%
Bước 2 – kiểm tra chéo bằng điểm tổng hợp 5 trụ cột (cơ bản, định giá, kỹ thuật, động lượng, rủi ro):
      MUA nhưng điểm < 40  → hạ xuống TRUNG LẬP (nguy cơ "bẫy giá trị": rẻ nhưng chất lượng/xu hướng yếu)
      BÁN nhưng điểm ≥ 65  → nâng lên TRUNG LẬP (định giá cao nhưng nền tảng và xu hướng tốt)
      Độ tin cậy định giá "Thấp" → không đưa MUA/BÁN mạnh: chỉ TRUNG LẬP kèm ghi chú
Không có giá trị hợp lý → chỉ dựa trên điểm tổng hợp và ghi rõ "chưa đủ dữ liệu định giá".
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

BUY_THRESHOLD = 15.0
SELL_THRESHOLD = -15.0

COLORS = {"MUA": (22, 128, 61), "TRUNG LẬP": (217, 119, 6), "BÁN": (200, 30, 45), "CHƯA ĐỦ DỮ LIỆU": (120, 120, 120)}
HEX = {"MUA": "#16a34a", "TRUNG LẬP": "#d97706", "BÁN": "#dc2626", "CHƯA ĐỦ DỮ LIỆU": "#64748b"}

SYSTEM_TEXT = [
    ("MUA", f"Lợi suất kỳ vọng từ {BUY_THRESHOLD:.0f}% trở lên"),
    ("TRUNG LẬP", f"Lợi suất kỳ vọng trong khoảng {SELL_THRESHOLD:.0f}% đến {BUY_THRESHOLD:.0f}%"),
    ("BÁN", f"Lợi suất kỳ vọng thấp hơn {SELL_THRESHOLD:.0f}%"),
]


def recommend(fv: Optional[Dict[str, Any]], score: Optional[float] = None,
              trend: Optional[str] = None) -> Dict[str, Any]:
    reasons: List[str] = []
    fv = fv or {}
    if fv.get("available"):
        er = float(fv["expected_return"])
        base = "MUA" if er >= BUY_THRESHOLD else "BÁN" if er <= SELL_THRESHOLD else "TRUNG LẬP"
        rating = base
        reasons.append(f"Lợi suất kỳ vọng {er:+.1f}% = chênh lệch giá trị hợp lý {fv['upside']:+.1f}% "
                       f"+ tỷ suất cổ tức {fv.get('dividend_yield', 0):.1f}% → theo định giá: {base}.")
        if fv.get("confidence") == "Thấp" and base != "TRUNG LẬP":
            rating = "TRUNG LẬP"
            reasons.append("Độ tin cậy định giá thấp (ít phương pháp hoặc các phương pháp chênh nhau lớn) "
                           "→ không đưa khuyến nghị mạnh, giữ TRUNG LẬP.")
        if score is not None:
            if rating == "MUA" and score < 40:
                rating = "TRUNG LẬP"
                reasons.append(f"Điểm tổng hợp chỉ {score:.0f}/100 (chất lượng/xu hướng yếu) → hạ xuống TRUNG LẬP "
                               "để tránh bẫy giá trị.")
            elif rating == "BÁN" and score >= 65:
                rating = "TRUNG LẬP"
                reasons.append(f"Điểm tổng hợp {score:.0f}/100 (nền tảng và xu hướng tốt) → nâng lên TRUNG LẬP.")
            else:
                reasons.append(f"Điểm tổng hợp {score:.0f}/100 không mâu thuẫn với kết luận định giá.")
        if trend:
            reasons.append(f"Xu hướng kỹ thuật hiện tại: {trend.lower()} – dùng để chọn thời điểm, không thay đổi khuyến nghị.")
        return {"rating": rating, "base_rating": base, "expected_return": er, "fair_value": fv["fair_value"],
                "upside": fv["upside"], "color": COLORS[rating], "hex": HEX[rating], "reasons": reasons,
                "basis": "valuation"}

    if score is None:
        return {"rating": "CHƯA ĐỦ DỮ LIỆU", "base_rating": None, "expected_return": None, "fair_value": None,
                "upside": None, "color": COLORS["CHƯA ĐỦ DỮ LIỆU"], "hex": HEX["CHƯA ĐỦ DỮ LIỆU"],
                "reasons": ["Không đủ dữ liệu định giá lẫn điểm tổng hợp."], "basis": None}
    rating = "MUA" if score >= 75 else "BÁN" if score < 35 else "TRUNG LẬP"
    reasons.append(f"Chưa đủ dữ liệu định giá → khuyến nghị dựa trên điểm tổng hợp {score:.0f}/100 "
                   "(MUA ≥ 75, BÁN < 35).")
    return {"rating": rating, "base_rating": None, "expected_return": None, "fair_value": None, "upside": None,
            "color": COLORS[rating], "hex": HEX[rating], "reasons": reasons, "basis": "score"}


# ═════════════════════════════════════════════════════════════════════════════
# HỆ THỐNG KHUYẾN NGHỊ 12 THÁNG (Recommendation Engine) – 3 yếu tố:
#   1. Financial Health Score (analytics/financial_health.py)
#   2. Expected Total Return = (Giá mục tiêu 12T − Thị giá + Cổ tức tiền mặt dự kiến) / Thị giá
#      (analytics/valuation_engine.py – cổ tức chỉ tính 1 lần, giá mục tiêu đã là giá "sau cổ tức")
#   3. Risk Assessment (analytics/risk_assessment.py)
# Thứ tự luật (dừng ở luật đầu tiên khớp):
#   R1 CHƯA ĐỦ CƠ SỞ : thiếu thị giá | không có định giá tin cậy | độ tin cậy < ngưỡng | thiếu BCTC (không có điểm
#                       sức khỏe) | có rủi ro NGHIÊM TRỌNG
#   R2 BÁN / TRÁNH MUA: Expected Return < sell_max_return (mặc định −10%) với định giá tin cậy
#   R3 MUA           : Health ≥ buy_min_health (75) VÀ Expected Return ≥ buy_min_return (20%) VÀ không rủi ro nghiêm trọng
#   R4 NẮM GIỮ (đang nắm giữ) / THEO DÕI (chưa nắm giữ): các trường hợp còn lại
# Không bao giờ MUA chỉ vì Health cao (luôn cần ER) và không bao giờ BÁN chỉ vì Health thấp (luôn cần ER).
# ═════════════════════════════════════════════════════════════════════════════

COLORS.update({"NẮM GIỮ": (217, 119, 6), "THEO DÕI": (37, 99, 235), "TRÁNH MUA": (200, 30, 45),
               "BÁN / TRÁNH MUA": (200, 30, 45), "NẮM GIỮ / THEO DÕI": (217, 119, 6), "CHƯA ĐỦ CƠ SỞ": (100, 116, 139)})
HEX.update({"NẮM GIỮ": "#d97706", "THEO DÕI": "#2563eb", "TRÁNH MUA": "#dc2626", "BÁN / TRÁNH MUA": "#dc2626",
            "NẮM GIỮ / THEO DÕI": "#d97706", "CHƯA ĐỦ CƠ SỞ": "#64748b"})
_CONF_RANK = {"Thấp": 0, "Trung bình": 1, "Cao": 2}


def investment_system_text(cfg: Optional[Dict[str, Any]] = None):
    from config.investment_model import load_config
    c = (cfg or load_config())["recommendation"]
    return [
        ("MUA", f"Sức khỏe ≥ {c['buy_min_health']:.0f}/100, tổng LN kỳ vọng ≥ {c['buy_min_return']:.0f}%, không rủi ro "
                f"nghiêm trọng, định giá tin cậy ≥ {c['min_confidence']}"),
        ("NẮM GIỮ / THEO DÕI", "Các trường hợp còn lại: NẮM GIỮ nếu đang có cổ phiếu, THEO DÕI nếu chưa có"),
        ("BÁN / TRÁNH MUA", f"Tổng lợi nhuận kỳ vọng < {c['sell_max_return']:.0f}% với định giá tin cậy: BÁN nếu đang nắm giữ, "
                            "TRÁNH MUA nếu chưa có"),
        ("CHƯA ĐỦ CƠ SỞ", "Thiếu thị giá, thiếu định giá tin cậy, BCTC không đủ, độ tin cậy thấp hoặc có rủi ro nghiêm trọng"),
    ]


def recommend_investment(health: Optional[Dict[str, Any]], valuation: Optional[Dict[str, Any]],
                         risk: Optional[Dict[str, Any]], config: Optional[Dict[str, Any]] = None,
                         holder: Optional[bool] = None) -> Dict[str, Any]:
    """holder: True = đang nắm giữ, False = chưa nắm giữ, None = hiển thị cả hai hành động."""
    from config.investment_model import load_config
    cfg = config or load_config()
    c = cfg["recommendation"]
    health, valuation, risk = health or {}, valuation or {}, risk or {}
    hs = health.get("score")
    er = valuation.get("expected_return")
    up = valuation.get("upside")
    conf = valuation.get("confidence")
    price = valuation.get("price")
    level = risk.get("level")
    severe_items = [i for i in risk.get("items", []) if i.get("severity") == "Nghiêm trọng"]
    trace: List[Dict[str, Any]] = []
    reasons: List[str] = []

    def chk(rule, ok, detail):
        trace.append({"rule": rule, "passed": bool(ok), "detail": detail})
        return ok

    # ── R1: đủ cơ sở? ──
    blockers = []
    if not chk("Có thị giá hợp lệ", price is not None and price > 0, f"Thị giá: {price:,.0f}" if price else "Thiếu thị giá"):
        blockers.append("thiếu thị giá hợp lệ")
    val_ok = bool(valuation.get("available")) and valuation.get("target_12m") is not None
    if not chk("Có giá mục tiêu 12T hợp lệ", val_ok, valuation.get("status", "Chưa định giá")):
        blockers.append("chưa có giá mục tiêu 12 tháng đáng tin cậy")
    conf_ok = conf is not None and _CONF_RANK.get(conf, -1) >= _CONF_RANK.get(c["min_confidence"], 1)
    if not chk(f"Độ tin cậy định giá ≥ {c['min_confidence']}", conf_ok, f"Độ tin cậy: {conf or '—'}") and val_ok:
        blockers.append(f"độ tin cậy định giá '{conf}' thấp hơn ngưỡng '{c['min_confidence']}'")
    if not chk("Đủ BCTC để chấm Financial Health", hs is not None,
               f"Health: {hs:.1f}/100" if hs is not None else f"Độ phủ số liệu {health.get('coverage', 0) * 100:.0f}%"):
        blockers.append("BCTC không đủ để chấm điểm sức khỏe tài chính")
    if not chk("Không có rủi ro nghiêm trọng", not severe_items, f"Mức rủi ro: {level or '—'}"):
        blockers.append("có rủi ro nghiêm trọng: " + "; ".join(i["text"] for i in severe_items[:2]))

    hs_txt = f"{hs:.1f}/100" if hs is not None else "chưa đủ dữ liệu"
    er_txt = f"{er:+.1f}%" if er is not None else "—"
    if blockers:
        rating = "CHƯA ĐỦ CƠ SỞ"
        reasons.append("Chưa đủ cơ sở khuyến nghị vì " + "; ".join(blockers) + ".")
        if val_ok and er is not None:
            reasons.append(f"Số liệu tham khảo: sức khỏe tài chính {hs_txt}, tổng lợi nhuận kỳ vọng {er_txt} – "
                           "không dùng để ra quyết định khi chưa khắc phục các điểm trên.")
        holder_label = non_holder_label = rating
        rule = "R1"
    elif chk(f"Tổng lợi nhuận kỳ vọng < {c['sell_max_return']:.0f}%", er < c["sell_max_return"], f"ER {er_txt}"):
        rating, rule = "BÁN", "R2"
        holder_label, non_holder_label = "BÁN", "TRÁNH MUA"
        reasons.append(f"Tổng lợi nhuận kỳ vọng 12 tháng {er_txt} thấp hơn ngưỡng {c['sell_max_return']:.0f}% "
                       f"(giá mục tiêu {valuation['target_12m']:,.0f} so với thị giá {price:,.0f}).")
        if hs is not None and hs >= c["buy_min_health"]:
            reasons.append(f"Doanh nghiệp tốt (sức khỏe {hs_txt}) nhưng thị giá đã vượt xa giá trị – chất lượng tốt không bù được định giá đắt.")
    elif chk(f"Health ≥ {c['buy_min_health']} và ER ≥ {c['buy_min_return']:.0f}%",
             hs >= c["buy_min_health"] and er >= c["buy_min_return"], f"Health {hs_txt}, ER {er_txt}"):
        rating, rule = "MUA", "R3"
        holder_label, non_holder_label = "MUA", "MUA"
        reasons.append(f"Sức khỏe tài chính {hs_txt} (≥ {c['buy_min_health']}), tổng lợi nhuận kỳ vọng {er_txt} "
                       f"(≥ {c['buy_min_return']:.0f}%), định giá độ tin cậy {conf.lower()}, mức rủi ro {str(level).lower()}.")
    else:
        rating, rule = "NẮM GIỮ", "R4"
        holder_label, non_holder_label = "NẮM GIỮ", "THEO DÕI"
        if er >= c["buy_min_return"] and hs < c["buy_min_health"]:
            reasons.append(f"Upside lớn (ER {er_txt}) nhưng sức khỏe tài chính chỉ {hs_txt} < {c['buy_min_health']} – "
                           "giá rẻ có thể phản ánh chất lượng yếu (bẫy giá trị) → chưa MUA.")
        elif hs >= c["buy_min_health"]:
            reasons.append(f"Doanh nghiệp khỏe ({hs_txt}) nhưng tổng lợi nhuận kỳ vọng {er_txt} chưa đạt {c['buy_min_return']:.0f}% → "
                           "chưa đủ biên an toàn để MUA.")
        else:
            reasons.append(f"Sức khỏe tài chính {hs_txt}, tổng lợi nhuận kỳ vọng {er_txt} – nằm giữa ngưỡng MUA và BÁN.")
        if hs < c["hold_min_health"]:
            reasons.append(f"Cảnh báo: sức khỏe tài chính dưới {c['hold_min_health']} – theo dõi sát kết quả kinh doanh.")
    if rule != "R1" and level in ("Cao",):
        reasons.append("Mức rủi ro tổng thể CAO – cân nhắc tỷ trọng thấp.")

    if holder is True:
        label = holder_label
    elif holder is False:
        label = non_holder_label
    else:
        label = holder_label if holder_label == non_holder_label else f"{holder_label} / {non_holder_label}"
    return {"rating": rating, "label": label, "label_holder": holder_label, "label_non_holder": non_holder_label,
            "rule": rule, "trace": trace, "reasons": reasons, "color": COLORS[label], "hex": HEX[label],
            "health_score": hs, "expected_return": er, "upside": up, "target_12m": valuation.get("target_12m"),
            "fair_value": valuation.get("target_12m"), "risk_level": level, "confidence": conf,
            "base_rating": rating, "basis": "health+valuation+risk", "thresholds": dict(c)}


def explain_recommendation(symbol: str, rec: Dict[str, Any], health: Dict[str, Any], valuation: Dict[str, Any],
                           risk: Dict[str, Any]) -> List[str]:
    """Trả lời: 'Tại sao cổ phiếu này được khuyến nghị …, và giá mục tiêu 12 tháng được tính như thế nào?'"""
    out = [f"Khuyến nghị {rec['label']} cho {symbol} (luật {rec['rule']}): " + " ".join(rec["reasons"])]
    if health.get("score") is not None:
        g = ", ".join(f"{x['label']} {x['score']:.0f}" for x in health.get("groups", []) if x.get("score") is not None)
        out.append(f"Sức khỏe tài chính {health['score']:.1f}/100 ({health.get('rating_text', '')}) – điểm nhóm: {g}.")
    if valuation.get("methods"):
        parts = []
        for m in valuation["methods"]:
            mult = f" × {m['multiple']:.2f}x" if m.get("multiple") else ""
            base = f"{m['base_label']} {m['base']:,.0f}{mult} = " if m.get("base") is not None and m.get("multiple") else ""
            parts.append(f"{m['name']}: {base}{m['fair']:,.0f} (trọng số {m['weight'] * 100:.0f}%)")
        t = valuation.get("target_12m")
        out.append("Giá mục tiêu 12 tháng = bình quân có trọng số các phương pháp hợp lệ: " + "; ".join(parts)
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
