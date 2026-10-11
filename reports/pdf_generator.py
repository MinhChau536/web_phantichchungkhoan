"""
PDF Report Generator – Định dạng Báo cáo Phân tích Công ty Chứng khoán Chuyên nghiệp.

Tích hợp toàn diện lý thuyết định lượng của hệ thống:
  - Thẻ điểm cơ hội đầu tư đa chiều (Opportunity Score 0–100)
  - Phân tích kỹ thuật (Giá, MA50, MA200, RSI, MACD, ATR, Hỗ trợ / Kháng cự)
  - Phân tích cơ bản (Doanh thu, LNST, ROE, ROA, Biên lợi nhuận, Đòn bẩy Nợ/VCSH)
  - Mô hình định giá (P/E, P/B, Giá trị hợp lý, Dư địa tăng giá, Chiết khấu dòng tiền DCF)
  - Quản trị rủi ro (Biến động Volatility, Max Drawdown, Cắt lỗ gợi ý 2×ATR)
  - Động lượng & Sức mạnh tương đối (Mansfield Relative Strength vs VN-Index)
  - Luận điểm đầu tư & Khuyến nghị tự động
"""
from __future__ import annotations

import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fpdf import FPDF

from analytics.period_utils import key_to_label
from config.settings import settings

logger = logging.getLogger(__name__)

# ── Bảng màu nền sáng kiểu infographic (băng navy + điểm nhấn vàng) ──
BG = (247, 249, 252)       # nền trang
BG_DEEP = (14, 42, 82)     # navy: băng đầu trang, hero, tiêu đề mục, đầu bảng
CARD = (255, 255, 255)     # thẻ
CARD_ALT = (241, 245, 249) # dòng bảng xen kẽ
LINE = (219, 226, 236)     # viền mảnh
GOLD = (242, 193, 102)     # vàng – dùng trên nền navy
GOLD_DK = (176, 112, 8)    # vàng đậm – dùng trên nền sáng
ON_DARK = (255, 255, 255)
ON_DARK_MUTED = (203, 213, 225)
TEXT = (15, 23, 42)        # chữ chính
MUTED = (100, 116, 139)    # chữ phụ
NAVY = BG_DEEP
GREY = MUTED
LIGHT = CARD_ALT
WHITE = CARD
GREEN = (22, 128, 61)
RED = (200, 30, 45)
AMBER = (217, 119, 6)
BORDER = LINE
SUB_FILL = (226, 232, 240) # dòng nhóm trong bảng
TRACK = (226, 232, 240)    # nền thanh tiến trình
FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def _brand_fonts() -> Dict[str, str]:
    """Be Vietnam Pro (assets/fonts, giấy phép OFL) – thiết kế riêng cho tiếng Việt."""
    files = {"": "Regular", "B": "Bold", "X": "ExtraBold", "M": "SemiBold"}
    out = {k: str(FONT_DIR / f"BeVietnamPro-{v}.ttf") for k, v in files.items()}
    return out if all(Path(p).exists() for p in out.values()) else {}


def _font_paths() -> Tuple[Optional[str], Optional[str]]:
    """
    Ưu tiên DejaVuSans (đi kèm matplotlib) để hỗ trợ đầy đủ 100% tiếng Việt
    và các ký tự đặc biệt (✓, ✗, ▲, ▼, •).
    Dự phòng Arial từ Windows Fonts.
    """
    mpl = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    dv_reg = mpl / "DejaVuSans.ttf"
    dv_bold = mpl / "DejaVuSans-Bold.ttf"
    if dv_reg.exists() and dv_bold.exists():
        return str(dv_reg), str(dv_bold)

    win = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    if (win / "arial.ttf").exists() and (win / "arialbd.ttf").exists():
        return str(win / "arial.ttf"), str(win / "arialbd.ttf")

    return None, None


def _n(x, d=0, suf="", sign: bool = False) -> str:
    """Format số an toàn."""
    if x is None or pd.isna(x):
        return "N/A"
    try:
        val = float(x)
        return (f"{val:+,.{d}f}" if sign else f"{val:,.{d}f}") + suf
    except (ValueError, TypeError):
        return str(x)


def _last(series_like) -> Optional[float]:
    try:
        s = pd.Series(series_like).dropna()
        return float(s.iloc[-1]) if not s.empty else None
    except Exception:
        return None


def _stock_info(price, px, summ, analysis, exchange, industry) -> List[Tuple[str, str]]:
    """Hộp thông tin cổ phiếu (giống trang 1 báo cáo CTCK)."""
    val = (summ or {}).get("valuation") or {}
    rows: List[Tuple[str, str]] = [("Sàn niêm yết", exchange or "N/A"), ("Ngành", industry or "N/A")]
    sess = ""
    if px is not None and not px.empty:
        ts = pd.to_datetime(px["timestamp"] if "timestamp" in px.columns else px.index)
        sess = ts.max().strftime("%d/%m/%Y")
        last_y = px[ts >= ts.max() - pd.Timedelta(days=365)]
        rows.append((f"Thị giá ({sess})", _n(price)))
        rows.append(("Biến động 52 tuần", f"{last_y['low'].min():,.0f} – {last_y['high'].max():,.0f}"
                     if {"low", "high"} <= set(last_y.columns) else "N/A"))
        if "volume" in last_y.columns:
            rows.append(("KLGD bình quân 52T (cp)", _n(last_y["volume"].mean())))
            rows.append(("GTGD bình quân 20 phiên (tỷ)", _n((px["close"] * px["volume"]).tail(20).mean() / 1e9, 1)))
    else:
        rows.append(("Thị giá", _n(price)))
    mc = val.get("market_cap")
    rows += [("Vốn hóa (tỷ đồng)", _n(mc / 1e9 if mc else None)), ("Số CP lưu hành (triệu)", _n((val.get("shares") or 0) / 1e6 if val.get("shares") else None, 1)),
             ("P/E (EPS TTM)", _n(val.get("pe"), 2, "x")), ("P/B", _n(val.get("pb"), 2, "x")),
             ("EPS TTM (đ/cp)", _n(val.get("eps_ttm"))), ("BVPS (đ/cp)", _n(val.get("bvps"))),
             ("Tỷ suất cổ tức", _n(val.get("dividend_yield"), 1, "%"))]
    return rows


def _key_fin_table(wide: Optional[pd.DataFrame], ratios: Optional[pd.DataFrame], n: int = 5):
    """Bảng chỉ tiêu tài chính chính n kỳ gần nhất: DTT, ±yoy, LNST, ±yoy, biên gộp, biên ròng, ROE, EPS."""
    if wide is None or wide.empty:
        return None
    w = wide.iloc[-n:]
    r = ratios.reindex(w.index) if ratios is not None and not ratios.empty else pd.DataFrame(index=w.index)
    bank = "net_interest_income" in w.columns and w["net_interest_income"].notna().any() and \
        ("revenue" not in w.columns or w["revenue"].isna().all())
    rev_key = "total_operating_income" if bank else "revenue"
    rev = w.get(rev_key, pd.Series(index=w.index, dtype=float))
    ni = w.get("net_income_parent", pd.Series(index=w.index, dtype=float))
    if ni.isna().all():
        ni = w.get("net_income", pd.Series(index=w.index, dtype=float))
    full_rev = wide.get(rev_key, pd.Series(dtype=float))
    full_ni = wide.get("net_income_parent", wide.get("net_income", pd.Series(dtype=float)))
    def yoy(full, idx):
        out = []
        for k in idx:
            prev = k - 10 if k % 10 == 0 else k - 10
            a, b = full.get(k), full.get(prev)
            out.append((a / b - 1) * 100 if a is not None and b and not pd.isna(a) and not pd.isna(b) and b > 0 else None)
        return out
    periods = [key_to_label(k) for k in w.index]
    rows = [
        ("Tổng thu nhập HĐ (tỷ)" if bank else "Doanh thu thuần (tỷ)", [_n(v / 1e9 if pd.notna(v) else None) for v in rev]),
        ("  +/- yoy", [_n(v, 1, "%", sign=True) for v in yoy(full_rev, w.index)]),
        ("LNST cổ đông công ty mẹ (tỷ)", [_n(v / 1e9 if pd.notna(v) else None) for v in ni]),
        ("  +/- yoy", [_n(v, 1, "%", sign=True) for v in yoy(full_ni, w.index)]),
    ]
    if not bank:
        rows.append(("Biên LN gộp", [_n(v, 1, "%") for v in r.get("gross_margin", pd.Series(index=w.index, dtype=float))]))
    rows += [("Biên LN ròng", [_n(v, 1, "%") for v in r.get("net_margin", pd.Series(index=w.index, dtype=float))]),
             ("ROE", [_n(v, 1, "%") for v in r.get("roe", pd.Series(index=w.index, dtype=float))]),
             ("EPS (đ/cp)", [_n(v) for v in r.get("eps", pd.Series(index=w.index, dtype=float))])]
    return {"periods": periods, "rows": rows, "bank": bank}


def _tech_rows(px, idx, signals, stop_p, r1m, r3m, r1y, rs6) -> List[Tuple[str, str, str]]:
    """(Chỉ báo, Giá trị, Diễn giải) – tính thẳng từ chuỗi giá đã có chỉ báo."""
    if px is None or px.empty:
        return []
    last = px.iloc[-1]
    c = float(last["close"])
    def v(col):
        return _last(px[col]) if col in px.columns else None
    rows: List[Tuple[str, str, str]] = [("Giá đóng cửa", _n(c), "")]
    for n_ in (20, 50, 200):
        m = v(f"SMA_{n_}")
        rows.append((f"MA{n_}", _n(m), "" if m is None else ("Giá trên MA ▲" if c > m else "Giá dưới MA ▼")))
    rsi = v("RSI")
    rows.append(("RSI (14)", _n(rsi, 1), "" if rsi is None else ("Quá mua" if rsi >= 70 else "Quá bán" if rsi <= 30
                                                                 else "Trung tính – nghiêng tích cực" if rsi >= 50 else "Trung tính – nghiêng tiêu cực")))
    macd, sig, hist = v("MACD"), v("MACD_signal"), v("MACD_hist")
    rows.append(("MACD / Signal", f"{_n(macd, 0)} / {_n(sig, 0)}", "" if hist is None else ("Histogram dương ▲" if hist > 0 else "Histogram âm ▼")))
    adx, pdi, mdi = v("ADX"), v("PLUS_DI"), v("MINUS_DI")
    rows.append(("ADX (14) · +DI / −DI", f"{_n(adx, 1)} · {_n(pdi, 1)} / {_n(mdi, 1)}",
                 "" if adx is None else (("Xu hướng mạnh" if adx >= 25 else "Xu hướng yếu") +
                                         ("" if pdi is None or mdi is None else (", phe mua chiếm ưu thế" if pdi > mdi else ", phe bán chiếm ưu thế")))))
    bu, bl = v("BB_upper"), v("BB_lower")
    if bu is not None and bl is not None and bu > bl:
        pb = (c - bl) / (bu - bl)
        rows.append(("Bollinger (dưới – trên)", f"{bl:,.0f} – {bu:,.0f}", f"%B = {pb:.2f}" + (" (sát dải trên)" if pb > 0.8 else " (sát dải dưới)" if pb < 0.2 else "")))
    atr = v("ATR")
    rows.append(("ATR (14)", _n(atr), f"{atr / c * 100:.1f}% giá – biên dao động ngày" if atr else ""))
    mfi, cmf = v("MFI"), v("CMF")
    if mfi is not None or cmf is not None:
        rows.append(("Dòng tiền MFI · CMF", f"{_n(mfi, 0)} · {_n(cmf, 2)}", "" if cmf is None else ("Dòng tiền vào" if cmf > 0 else "Dòng tiền ra")))
    if "volume" in px.columns:
        av = px["volume"].tail(20).mean()
        rows.append(("KL bình quân 20 phiên", _n(av), f"Phiên gần nhất = {float(last['volume']) / av:.2f}× bình quân" if av else ""))
    sr = signals.get("support_resistance") or {}
    sup = min(sr.get("support") or [], key=lambda x: abs(x - c), default=None) if sr.get("support") else None
    res = min(sr.get("resistance") or [], key=lambda x: abs(x - c), default=None) if sr.get("resistance") else None
    if sup is None:
        sup = float(px["low"].tail(60).min()) if "low" in px.columns else None
    if res is None:
        res = float(px["high"].tail(60).max()) if "high" in px.columns else None
    rows.append(("Hỗ trợ gần nhất", _n(sup), f"{(sup / c - 1) * 100:+.1f}% so với giá" if sup else ""))
    rows.append(("Kháng cự gần nhất", _n(res), f"{(res / c - 1) * 100:+.1f}% so với giá" if res else ""))
    rows.append(("Cắt lỗ gợi ý (giá − 2×ATR)", _n(stop_p), ""))
    rows.append(("Lợi suất 1T / 3T / 12T", f"{_n(r1m, 1, '%', True)} / {_n(r3m, 1, '%', True)} / {_n(r1y, 1, '%', True)}", ""))
    rows.append(("So với VN-Index 6 tháng", _n(rs6, 1, " điểm %", True), "" if rs6 is None else ("Mạnh hơn thị trường" if rs6 > 0 else "Yếu hơn thị trường")))
    trend = (signals.get("trend") or {}).get("name")
    if trend:
        rows.insert(1, ("Xu hướng tổng hợp", trend, "; ".join((signals.get("trend") or {}).get("criteria", [])[:3])))
    return rows


from analytics.risk_assessment import SECTOR_WATCH as _SECTOR_WATCH  # noqa: E402 – dùng chung với Risk Assessment


def _build_risks(a: Dict[str, Any], data: Dict[str, Any], px, wide, summ) -> List[Tuple[str, str, str]]:
    """[(Mức độ, Rủi ro, Căn cứ)] rút ra từ số liệu thật; mục ngành ghi rõ là 'cần theo dõi'."""
    out: List[Tuple[str, str, str]] = []
    ratios = (summ or {}).get("ratios")
    last = ratios.iloc[-1] if ratios is not None and not ratios.empty else pd.Series(dtype=float)
    bank = bool((summ or {}).get("is_bank"))
    rg, ng = last.get("revenue_growth"), last.get("net_income_growth")
    for lbl, g in (("Doanh thu", rg), ("Lợi nhuận sau thuế", ng)):
        if g is not None and pd.notna(g) and g < 0:
            out.append(("Cao" if g <= -15 else "Trung bình", f"{lbl} giảm {abs(g):.1f}% so với cùng kỳ – cần theo dõi khả năng phục hồi.",
                        "BCTC kỳ gần nhất"))
    de = last.get("debt_to_equity")
    if not bank and de is not None and pd.notna(de) and de > 1:
        out.append(("Cao" if de > 2 else "Trung bình", f"Đòn bẩy tài chính cao: nợ vay/VCSH {de:.2f} lần – nhạy với lãi suất.", "BCTC"))
    cr = last.get("current_ratio")
    if not bank and cr is not None and pd.notna(cr) and cr < 1:
        out.append(("Trung bình", f"Thanh toán hiện hành {cr:.2f} lần (< 1) – áp lực thanh khoản ngắn hạn.", "BCTC"))
    if wide is not None and not wide.empty and "cfo" in wide.columns:
        cfo = wide["cfo"].dropna()
        ni = wide.get("net_income", pd.Series(dtype=float)).reindex(cfo.index)
        if not cfo.empty and cfo.iloc[-1] < 0:
            out.append(("Trung bình", "Dòng tiền kinh doanh kỳ gần nhất âm – lợi nhuận chưa chuyển thành tiền.", "Lưu chuyển tiền tệ"))
        elif len(cfo) >= 2 and (cfo.tail(2) < 0.5 * ni.tail(2)).all():
            out.append(("Trung bình", "Dòng tiền kinh doanh thấp hơn 50% lợi nhuận 2 kỳ liên tiếp – chất lượng lợi nhuận cần kiểm tra.", "Lưu chuyển tiền tệ"))
    alt = (summ or {}).get("altman") or {}
    if alt.get("score") is not None and not bank:
        z = alt.get("zone", "")
        if "nguy" in str(z).lower() or "distress" in str(z).lower():
            out.append(("Cao", f"Altman Z''-score {alt['score']:.2f} – vùng {z}.", "Mô hình Altman (2005)"))
        elif "xám" in str(z).lower() or "grey" in str(z).lower():
            out.append(("Trung bình", f"Altman Z''-score {alt['score']:.2f} – vùng {z}.", "Mô hình Altman (2005)"))
    pio = (summ or {}).get("piotroski") or {}
    if pio.get("score") is not None and pio["score"] <= 3:
        out.append(("Trung bình", f"Piotroski F-score {pio['score']}/{pio.get('max', 9)} – sức khỏe tài chính yếu.", "Mô hình Piotroski (2000)"))
    if px is not None and len(px) > 60:
        r = px["close"].pct_change().dropna().tail(250)
        vol = float(r.std() * np.sqrt(252) * 100)
        mdd = float(((px["close"] / px["close"].cummax()) - 1).tail(250).min() * 100)
        if vol > 40:
            out.append(("Trung bình", f"Biến động giá cao: {vol:.0f}%/năm.", "Lịch sử giá 1 năm"))
        if mdd < -35:
            out.append(("Trung bình", f"Mức sụt giảm tối đa trong năm {mdd:.0f}%.", "Lịch sử giá 1 năm"))
        if "volume" in px.columns:
            gtgd = float((px["close"] * px["volume"]).tail(20).mean() / 1e9)
            if gtgd < 3:
                out.append(("Trung bình", f"Thanh khoản thấp: GTGD bình quân 20 phiên ~{gtgd:.1f} tỷ đồng.", "Lịch sử giao dịch"))
    trend = a.get("trend") or ""
    if "giảm" in trend.lower():
        out.append(("Trung bình", f"Xu hướng giá {trend.lower()} – rủi ro tiếp tục điều chỉnh ngắn hạn.", "Phân tích kỹ thuật"))
    fv = a.get("fv") or {}
    if fv.get("available"):
        if fv["expected_return"] < 0:
            out.append(("Trung bình", f"Thị giá cao hơn giá trị hợp lý ước tính ({fv['upside']:+.1f}%).", "Định giá"))
        if fv.get("confidence") == "Thấp":
            out.append(("Trung bình", "Kết quả định giá có độ tin cậy thấp – các phương pháp cho kết quả chênh lệch lớn.", "Định giá"))
    else:
        out.append(("Trung bình", "Chưa đủ dữ liệu để định giá – khuyến nghị dựa trên điểm tổng hợp.", "Định giá"))
    ind = f"{data.get('industry', '')} {((data.get('peers') or {}).get('group') or '')}".lower()
    for keys, text in _SECTOR_WATCH:
        if any(k in ind for k in keys):
            out.append(("Cần theo dõi", text, "Đặc thù ngành (không phải sự kiện đã xảy ra)"))
            break
    out.append(("Cần theo dõi", "Rủi ro thị trường chung: lãi suất, tỷ giá, dòng vốn ngoại và tâm lý nhà đầu tư.", "Vĩ mô"))
    order = {"Cao": 0, "Trung bình": 1, "Thấp": 2, "Cần theo dõi": 3}
    return sorted(out, key=lambda t: order.get(t[0], 9))


# ─────────────────────────────────────────────────────────────────────────────
# Vẽ biểu đồ phân tích (Matplotlib engine)
# ─────────────────────────────────────────────────────────────────────────────

def _fig_to_png(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _generate_price_chart(px: pd.DataFrame, ticker: str, target_price: Optional[float], stop_loss: Optional[float]) -> io.BytesIO:
    """Biểu đồ giá 12 tháng + MA50 + MA200 + Giá mục tiêu + Cắt lỗ + RSI(14)."""
    if px is None or px.empty:
        fig, ax = plt.subplots(figsize=(9.2, 2.2))
        ax.text(0.5, 0.5, "Không có dữ liệu giá lịch sử – không vẽ biểu đồ kỹ thuật",
                ha="center", va="center", color="#6e6e6e", fontsize=9)
        ax.axis("off")
        return _fig_to_png(fig)
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9.2, 4.4), sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1.0], "hspace": 0.08}
    )

    time_series = px["timestamp"] if "timestamp" in px.columns else px["time"] if "time" in px.columns else px.index
    times = pd.to_datetime(time_series)
    closes = px["close"].values

    ax1.plot(times, closes, color="#0e2a52", lw=1.4, label="Giá đóng cửa")

    # MA50
    ma50_col = "SMA_50" if "SMA_50" in px.columns else "ma50" if "ma50" in px.columns else None
    if ma50_col and px[ma50_col].notna().any():
        ax1.plot(times, px[ma50_col].values, color="#e08a00", lw=1.1, label="MA50")

    # MA200
    ma200_col = "SMA_200" if "SMA_200" in px.columns else "ma200" if "ma200" in px.columns else None
    if ma200_col and px[ma200_col].notna().any():
        ax1.plot(times, px[ma200_col].values, color="#2a9d8f", lw=1.1, label="MA200")

    # Target & Stop loss
    if target_price and target_price > 0:
        ax1.axhline(target_price, color="#108040", ls="--", lw=1.1, label=f"Giá mục tiêu ({target_price:,.0f})")
    if stop_loss and stop_loss > 0:
        ax1.axhline(stop_loss, color="#be1e2d", ls=":", lw=1.1, label=f"Cắt lỗ 2xATR ({stop_loss:,.0f})")

    ax1.set_title(f"{ticker} – Diễn biến giá 12 tháng & Hệ thống chỉ báo kỹ thuật", fontsize=10, fontweight="bold", color="#0e2a52", loc="left")
    ax1.legend(fontsize=7, loc="upper left", ncol=5, frameon=True, framealpha=0.85, facecolor="#ffffff", edgecolor="#e2e8f0")
    ax1.grid(color="#e2e8f0", linestyle="--", linewidth=0.6, alpha=0.8)
    ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x:,.0f}"))

    # RSI
    rsi_col = "RSI" if "RSI" in px.columns else "rsi" if "rsi" in px.columns else None
    if rsi_col and px[rsi_col].notna().any():
        ax2.plot(times, px[rsi_col].values, color="#4a5568", lw=1.0)
    else:
        ax2.text(0.5, 0.5, "Chưa đủ dữ liệu tính RSI", transform=ax2.transAxes,
                 ha="center", va="center", color="#6e6e6e", fontsize=7)

    ax2.axhspan(30, 70, color="#0e2a52", alpha=0.08)
    ax2.axhline(70, color="#be1e2d", ls="--", lw=0.6, alpha=0.6)
    ax2.axhline(30, color="#108040", ls="--", lw=0.6, alpha=0.6)
    ax2.set_ylabel("RSI (14)", fontsize=7.5, color="#4a5568")
    ax2.set_ylim(0, 100)
    ax2.grid(color="#e2e8f0", linestyle="--", linewidth=0.5, alpha=0.8)

    for ax in (ax1, ax2):
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.spines["left"].set_color("#cbd5e1")
        ax.spines["bottom"].set_color("#cbd5e1")
        ax.tick_params(colors="#4a5568", labelsize=7)

    return _fig_to_png(fig)


def _generate_fin_chart(fin_df: pd.DataFrame) -> io.BytesIO:
    """Biểu đồ Doanh thu & LNST theo kỳ báo cáo (số liệu thật từ BCTC)."""
    fig, ax = plt.subplots(figsize=(4.4, 2.6))
    if fin_df is not None and not fin_df.empty and fin_df["revenue"].notna().any():
        fin_df = fin_df.fillna({"revenue": 0, "npat": 0})
        years = fin_df["period"].astype(str).tolist()
        rev = (fin_df["revenue"] / 1e9 if fin_df["revenue"].max() > 1e7 else fin_df["revenue"]).tolist()
        npat = (fin_df["npat"] / 1e9 if fin_df["npat"].max() > 1e7 else fin_df["npat"]).tolist()
        x = np.arange(len(years))
        width = 0.36
        ax.bar(x - width/2, rev, width=width, color="#0e2a52", label="Doanh thu")
        ax.bar(x + width/2, npat, width=width, color="#e08a00", label="LNST")
        ax.set_xticks(x)
        ax.set_xticklabels(years, fontsize=7.5)
    else:
        ax.text(0.5, 0.5, "Không đủ dữ liệu BCTC", ha="center", va="center", color="#6e6e6e")
        ax.set_xticks([])
        ax.set_yticks([])

    ax.set_title("Doanh thu & LNST (tỷ đồng)", fontsize=8.5, fontweight="bold", color="#0e2a52", loc="left")
    if ax.get_legend_handles_labels()[0]:
        ax.legend(fontsize=7, frameon=False, loc="upper left")
    ax.grid(axis="y", color="#e2e8f0", linestyle="--", linewidth=0.6, alpha=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.tick_params(colors="#4a5568", labelsize=7)
    return _fig_to_png(fig)


def _generate_rel_chart(px: pd.DataFrame, idx: Optional[pd.DataFrame]) -> io.BytesIO:
    """Sức mạnh tương đối 6 tháng so với VN-Index (gốc = 100)."""
    fig, ax = plt.subplots(figsize=(4.4, 2.6))
    tail_px = px.tail(126).copy() if px is not None else pd.DataFrame()
    if not tail_px.empty and len(tail_px) >= 5:
        p_base = tail_px["close"].iloc[0]
        p_norm = (tail_px["close"] / p_base) * 100
        time_p = pd.to_datetime(tail_px["timestamp"] if "timestamp" in tail_px.columns else tail_px["time"] if "time" in tail_px.columns else tail_px.index)
        ax.plot(time_p, p_norm, color="#0e2a52", lw=1.4, label="Cổ phiếu")

        if idx is not None and not idx.empty and "close" in idx.columns:
            tail_idx = idx.tail(126).copy()
            i_base = tail_idx["close"].iloc[0]
            i_norm = (tail_idx["close"] / i_base) * 100
            time_i = pd.to_datetime(tail_idx["timestamp"] if "timestamp" in tail_idx.columns else tail_idx["time"] if "time" in tail_idx.columns else tail_idx.index)
            ax.plot(time_i, i_norm, color="#94a3b8", lw=1.2, ls="--", label="VN-Index")

        ax.axhline(100, color="#cbd5e1", lw=0.7, ls=":")
        ax.set_title("Sức mạnh tương đối 6 tháng (gốc = 100)", fontsize=8.5, fontweight="bold", color="#0e2a52", loc="left")
        ax.legend(fontsize=7, frameon=False, loc="upper left")
        ax.grid(color="#e2e8f0", linestyle="--", linewidth=0.6, alpha=0.8)
        ax.tick_params(axis="x", labelsize=6.5, rotation=25)
    else:
        ax.text(0.5, 0.5, "Không đủ dữ liệu lịch sử", ha="center", va="center", color="#6e6e6e")
        ax.set_xticks([])
        ax.set_yticks([])

    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.tick_params(colors="#4a5568", labelsize=7)
    return _fig_to_png(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Lớp Báo Cáo FPDF A4 Chuẩn Tổ Chức
# ─────────────────────────────────────────────────────────────────────────────

PAGE_BG = Path(__file__).resolve().parent.parent / "assets" / "report" / "page_bg.jpg"
FONT_SCALE = 1.10          # phóng chữ nội dung (≤ 11pt) cho dễ đọc; tiêu đề lớn giữ nguyên
LINE_SCALE = 1.06          # giãn dòng tương ứng cho đoạn văn nhiều dòng
PAGE_TOP = 32.0            # nội dung bắt đầu dưới dải tiêu đề của ảnh nền (dải xanh cao ~28 mm)
PAGE_BOTTOM = 18.0         # chừa chỗ cho chân trang (đường kẻ ~283 mm, dải xanh từ ~292 mm)


class EquityReportPDF(FPDF):
    """Trang A4 nền tối kiểu infographic: tiêu đề mục đánh số + viên thuốc, điểm nhấn vàng."""

    def __init__(self, meta: Dict[str, Any]):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.meta = meta
        self.cover_page = 0          # số trang của bìa (0 = không có bìa)
        self.sec_no = 0
        self.has_vn = False
        self.bold_x = "B"           # kiểu chữ cho số lớn
        dv_reg, dv_bold = _font_paths()
        brand = _brand_fonts()
        if brand:
            self.add_font("VN", "", brand[""])
            self.add_font("VN", "B", brand["B"])
            self.add_font("VNX", "", brand["X"])
            self.add_font("VNX", "B", brand["X"])
            self.has_vn = True
        elif dv_reg and dv_bold:
            self.add_font("VN", "", dv_reg)
            self.add_font("VN", "B", dv_bold)
            self.has_vn = True
        if dv_reg and dv_bold:
            # ký hiệu ✓ ✗ ▲ ▼ → … không có trong Be Vietnam Pro: lấy từ DejaVu
            self.add_font("DV", "", dv_reg)
            self.add_font("DV", "B", dv_bold)
            if brand:
                self.set_fallback_fonts(["DV"], exact_match=False)
        self.big_font = "VNX" if brand else ("VN" if self.has_vn else "Helvetica")
        self.has_bg = PAGE_BG.exists()
        self.top = PAGE_TOP if self.has_bg else 14.0
        self.set_auto_page_break(True, margin=PAGE_BOTTOM if self.has_bg else 16)
        self.set_margins(14, self.top, 14)

    # ── phóng chữ nội dung & giãn dòng (áp dụng cho mọi phần của báo cáo) ──
    def set_font(self, family=None, style="", size=0):
        if size and size <= 11:
            size = round(size * FONT_SCALE, 2)
        super().set_font(family, style, size)

    def multi_cell(self, w, h=None, *args, **kwargs):
        if h and self.font_size_pt <= 11 * FONT_SCALE:
            h = h * LINE_SCALE
        return super().multi_cell(w, h, *args, **kwargs)

    # ── nền & đầu/chân trang ──
    def header(self):
        if self.cover_page and self.page == self.cover_page:
            return
        f = "VN" if self.has_vn else "Helvetica"
        tk = self.meta.get("ticker", "")
        if self.has_bg:
            # ảnh nền: dải xanh trên (logo có sẵn) + nền sáng + dải xanh dưới
            self.image(str(PAGE_BG), x=0, y=0, w=210, h=297)
            self.set_xy(26, 7.2)
            self.set_font(self.big_font, "B", 11.5)
            self.set_text_color(255, 255, 255)
            self.cell(90, 6, "STOCK ANALYTICS PRO")
            self.set_xy(26, 13.4)
            self.set_font(f, "", 7.2)
            self.set_text_color(214, 228, 244)
            self.cell(90, 4, "Báo cáo phân tích cổ phiếu tự động")
            self.set_xy(110, 7.2)
            self.set_font(self.big_font, "B", 11.5)
            self.set_text_color(*GOLD)
            self.cell(86, 6, tk, align="R")
            self.set_xy(110, 13.4)
            self.set_font(f, "", 7.2)
            self.set_text_color(214, 228, 244)
            self.cell(86, 4, f"BÁO CÁO PHÂN TÍCH CỔ PHIẾU · {tk}", align="R")
        else:
            self.set_fill_color(*BG)
            self.rect(0, 0, 210, 297, "F")
            self.set_fill_color(*BG_DEEP)
            self.rect(0, 0, 210, 9, "F")
            self.set_fill_color(*GOLD)
            self.rect(0, 9, 210, 0.6, "F")
            self.set_xy(14, 2.2)
            self.set_font(f, "B", 7.2)
            self.set_text_color(*ON_DARK)
            self.cell(90, 5, "STOCK ANALYTICS PRO", align="L")
            self.set_text_color(*GOLD)
            self.set_x(110)
            self.cell(86, 5, f"BÁO CÁO PHÂN TÍCH CỔ PHIẾU  ·  {tk}", align="R")
        self.set_xy(14, self.top)
        self.set_text_color(*TEXT)

    def footer(self):
        if self.cover_page and self.page == self.cover_page:
            return
        if self.has_bg:
            self.set_y(284.2)               # nằm giữa đường kẻ (~283 mm) và dải xanh dưới (~292 mm) của ảnh nền
        else:
            self.set_y(-11)
            self.set_draw_color(*LINE)
            self.set_line_width(0.2)
            self.line(14, self.get_y() - 1, 196, self.get_y() - 1)
        self.set_x(10 if self.has_bg else 14)
        self.set_font("VN" if self.has_vn else "Helvetica", "", 6.6)
        self.set_text_color(*MUTED)
        sess = self.meta.get("last_session", datetime.now().strftime("%d/%m/%Y"))
        gen_time = self.meta.get("fetched_at", datetime.now().strftime("%H:%M %d/%m/%Y"))
        src = self.meta.get("data_source", "Vnstock / DNSE / BCTC Niêm Yết")
        self.cell(140, 4, f"Dữ liệu: {src}  |  Phiên: {sess}  |  Xuất lúc: {gen_time}", align="L")
        self.set_text_color(*GOLD_DK)
        self.cell(50 if self.has_bg else 0, 4, f"Trang {self.page_no()}/{{nb}}", align="R")

    # ── thành phần giao diện ──
    def card(self, x: float, y: float, w: float, h: float, fill=CARD, border=LINE, r: float = 2.4):
        self.set_fill_color(*fill)
        self.set_draw_color(*border)
        self.set_line_width(0.25)
        self.rect(x, y, w, h, "DF", round_corners=True, corner_radius=r)

    def chart(self, img, x: float, w: float, y: Optional[float] = None, pad: float = 1.8) -> float:
        """Đặt biểu đồ (giữ nguyên nền trắng) vào khung trắng bo góc; trả về đáy khung."""
        y = self.get_y() if y is None else y
        from PIL import Image as _Im
        img.seek(0)
        iw, ih = _Im.open(img).size
        img.seek(0)
        h = (w - 2 * pad) * ih / iw
        if y + h + 2 * pad > self.h - self.b_margin:
            self.add_page()
            y = self.get_y()
        self.set_fill_color(255, 255, 255)
        self.set_draw_color(*LINE)
        self.rect(x, y, w, h + 2 * pad, "DF", round_corners=True, corner_radius=2.4)
        self.image(img, x=x + pad, y=y + pad, w=w - 2 * pad)
        return y + h + 2 * pad

    @staticmethod
    def _split_title(txt: str) -> Tuple[str, str, str]:
        """→ (phần trắng, phần vàng, chú thích trong ngoặc)."""
        note = ""
        if "(" in txt and txt.rstrip().endswith(")"):
            i = txt.index("(")
            txt, note = txt[:i].strip(), txt[i + 1:-1].strip()
        up = txt.upper()
        if " & " in up:
            i = up.index(" & ")
            return up[:i + 3], up[i + 3:], note
        if ":" in up:
            i = up.index(":")
            return up[:i + 1] + " ", up[i + 1:].strip(), note
        words = up.split()
        k = 1 if len(words) <= 3 else 2
        return " ".join(words[:-k]) + " ", " ".join(words[-k:]), note

    def h2(self, txt: str, min_space: float = 30, new_page: bool = False):
        """Tiêu đề MỤC LỚN (đánh số 01, 02… và ghi vào mục lục): vòng tròn số + viên thuốc navy, phần cuối tô vàng."""
        f = "VN" if self.has_vn else "Helvetica"
        if new_page or self.get_y() > self.h - self.b_margin - min_space:
            self.add_page()
        self.sec_no += 1
        self.ln(3)
        y = self.get_y()
        try:
            self.start_section(f"{self.sec_no:02d}  {txt.split('(')[0].strip()}", level=0)
        except Exception:
            pass
        white, gold, note = self._split_title(txt)
        # vòng tròn số
        r = 4.6
        self.set_fill_color(*BG_DEEP)
        self.set_draw_color(*GOLD)
        self.set_line_width(0.5)
        self.circle(14 + r, y + r, r, "DF")   # fpdf2 2.8: (x, y) là TÂM đường tròn
        self.set_font(self.big_font, "B" if self.big_font != "Helvetica" else "B", 10)
        self.set_text_color(*ON_DARK)
        self.set_xy(14, y + 0.1)
        self.set_font(self.big_font, "B", 8.6)
        self.cell(2 * r, 2 * r, f"{self.sec_no:02d}", align="C")
        # viên thuốc
        self.set_font(f, "B", 9.6)
        tw = self.get_string_width(white) + self.get_string_width(gold) + 10
        pw = min(182 - 2 * r - 3, max(60, tw))
        px = 14 + 2 * r + 2.5
        self.set_fill_color(*BG_DEEP)
        self.set_draw_color(*BG_DEEP)
        self.set_line_width(0.25)
        self.rect(px, y + 0.4, pw, 2 * r - 0.8, "DF", round_corners=True, corner_radius=(2 * r - 0.8) / 2)
        self.set_xy(px + 5, y + 0.4)
        self.set_text_color(*ON_DARK)
        self.cell(self.get_string_width(white), 2 * r - 0.8, white)
        self.set_text_color(*GOLD)
        self.cell(self.get_string_width(gold) + 1, 2 * r - 0.8, gold)
        self.set_y(y + 2 * r + 1.6)
        if note:
            self.set_x(px + 1)
            self.set_font(f, "", 7.2)
            self.set_text_color(*MUTED)
            self.cell(0, 3.8, note, new_x="LMARGIN", new_y="NEXT")
        self.ln(1.4)
        self.set_text_color(*TEXT)

    # ── tiêu đề phụ, bảng, gạch đầu dòng ──
    @property
    def font_name(self) -> str:
        return "VN" if self.has_vn else "Helvetica"

    def h3(self, txt: str, min_space: float = 22):
        """Tiêu đề phụ trong một mục: vạch vàng bên trái + chữ navy đậm."""
        if self.get_y() > self.h - self.b_margin - min_space:
            self.add_page()
        self.ln(1.5)
        y = self.get_y()
        self.set_fill_color(*GOLD)
        self.rect(14, y + 0.6, 1.2, 4.4, "F")
        self.set_xy(17, y)
        self.set_font(self.font_name, "B", 9.2)
        self.set_text_color(*NAVY)
        self.cell(0, 5.6, txt, new_x="LMARGIN", new_y="NEXT")
        self.ln(0.8)
        self.set_text_color(*TEXT)

    def para(self, txt: str, size: float = 8.2, color=None, h: float = 4.3):
        self.set_font(self.font_name, "", size)
        self.set_text_color(*(color or TEXT))
        self.multi_cell(0, h, txt, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*TEXT)

    def bullets(self, items: List[str], size: float = 8.2, h: float = 4.4, prefix: str = "•  "):
        self.set_font(self.font_name, "", size)
        for it in items:
            if self.get_y() > self.h - self.b_margin - 8:
                self.add_page()
            self.set_x(15)
            self.multi_cell(181, h, prefix + it, new_x="LMARGIN", new_y="NEXT")
            self.ln(0.5)

    def table(self, headers: List[str], rows: List[List[Any]], widths: List[float],
              aligns: Optional[List[str]] = None, size: float = 7.6, h: float = 5.4,
              colors: Optional[List[List[Optional[tuple]]]] = None, bold_first: bool = False):
        """Bảng chung: đầu bảng navy chữ vàng, dòng xen kẽ, tự lặp đầu bảng khi sang trang.
        colors[i][j] = màu chữ riêng cho ô (i, j)."""
        aligns = aligns or (["L"] + ["R"] * (len(headers) - 1))
        f = self.font_name

        def head():
            self.set_font(f, "B", size)
            self.set_fill_color(*BG_DEEP)
            self.set_text_color(*GOLD)
            for t, w, a in zip(headers, widths, aligns):
                self.cell(w, h + 0.4, " " + str(t) + " ", align=a if a != "L" else "L", fill=True)
            self.ln()
            self.set_text_color(*TEXT)

        need = (len(rows) + 1) * h + 4
        usable = self.h - self.b_margin - self.t_margin - 10
        if self.get_y() + 2 * h + 4 > self.h - self.b_margin or \
                (need <= min(usable, 75) and self.get_y() + need > self.h - self.b_margin):
            self.add_page()                      # bảng ngắn: không cắt đôi giữa 2 trang
        head()
        for i, row in enumerate(rows):
            if self.get_y() + h > self.h - self.b_margin:
                self.add_page()
                head()
            self.set_fill_color(*(CARD_ALT if i % 2 == 0 else CARD))
            for j, (v, w, a) in enumerate(zip(row, widths, aligns)):
                ci = colors[i] if colors and i < len(colors) else None
                col = ci[j] if ci and j < len(ci) and ci[j] else TEXT
                self.set_text_color(*col)
                self.set_font(f, "B" if (bold_first and j == 0) else "", size)
                txt = "" if v is None else str(v)
                max_chars = int(w / (size * FONT_SCALE * 0.19)) if w else 99
                if len(txt) > max_chars:
                    txt = txt[: max_chars - 1] + "…"
                self.cell(w, h, " " + txt + " ", align=a, fill=True)
            self.ln()
        self.set_text_color(*TEXT)
        self.ln(1.2)

    def kv_grid(self, pairs: List[Tuple[str, str]], cols: int = 2, h: float = 5.5, size: float = 7.8,
                x: float = 14, width: float = 182):
        """Lưới nhãn – giá trị (vd thông tin cổ phiếu)."""
        f = self.font_name
        cw = width / cols
        for i in range(0, len(pairs), cols):
            if self.get_y() + h > self.h - self.b_margin:
                self.add_page()
            self.set_x(x)
            for lbl, val in pairs[i:i + cols]:
                self.set_fill_color(*(CARD_ALT if (i // cols) % 2 == 0 else CARD))
                self.set_font(f, "", size)
                self.set_text_color(*MUTED)
                self.cell(cw * 0.52, h, " " + lbl, fill=True)
                self.set_font(f, "B", size)
                self.set_text_color(*TEXT)
                self.cell(cw * 0.48, h, str(val) + " ", align="R", fill=True)
            self.ln()
        self.set_text_color(*TEXT)
        self.ln(1)

    def sub(self, txt: str):
        """Tiêu đề phụ màu vàng."""
        self.set_font("VN" if self.has_vn else "Helvetica", "B", 8.8)
        self.set_text_color(*NAVY)
        self.cell(0, 5, txt, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*TEXT)

    def hero(self, ticker: str, subtitle: str, closes: Optional[List[float]] = None):
        """Khối mở đầu kiểu infographic: MÃ (vàng) – tiêu đề, phụ đề, nền có đường giá mờ."""
        y0 = self.get_y() - 4
        h = 33
        self.set_fill_color(*BG_DEEP)
        self.rect(0, y0, 210, h, "F")
        if closes is not None and len(closes) > 5:
            vals = [float(v) for v in closes if v == v]
            lo, hi = min(vals), max(vals)
            rng = (hi - lo) or 1
            x0, x1, yt, yb = 132, 204, y0 + 13, y0 + h - 2
            pts = [(x0 + (x1 - x0) * i / (len(vals) - 1), yb - (v - lo) / rng * (yb - yt)) for i, v in enumerate(vals)]
            with self.local_context(fill_opacity=0.10, stroke_opacity=0.45):
                self.set_fill_color(*GOLD)
                self.polygon(pts + [(x1, yb), (x0, yb)], style="F")
                self.set_draw_color(*GOLD)
                self.set_line_width(0.45)
                self.polyline(pts)
        self.set_fill_color(*GOLD)
        self.rect(0, y0 + h, 210, 0.5, "F")
        f = "VN" if self.has_vn else "Helvetica"
        self.set_xy(14, y0 + 4.5)
        self.set_font(self.big_font, "B", 25)
        self.set_text_color(*GOLD)
        self.cell(self.get_string_width(ticker) + 2, 12, ticker)
        self.set_text_color(*ON_DARK)
        self.cell(0, 12, "–  Báo Cáo Phân Tích Cổ Phiếu")
        self.set_xy(14, y0 + 17.5)
        self.set_font(f, "", 8.6)
        self.set_text_color(*ON_DARK_MUTED)
        self.multi_cell(118, 4.2, subtitle, new_x="LMARGIN", new_y="NEXT")
        self.set_y(y0 + h + 4)
        self.set_text_color(*TEXT)


# ─────────────────────────────────────────────────────────────────────────────
# Bộ Điều Phối & Xử Lý Dữ Liệu Báo Cáo
# ─────────────────────────────────────────────────────────────────────────────

class PDFReportGenerator:
    """Tạo báo cáo phân tích đầu tư PDF định dạng tổ chức tài chính chuyên nghiệp."""

    def __init__(self):
        settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    SECTIONS = {
        "summary": "Tổng quan & khuyến nghị",
        "profile": "Hồ sơ doanh nghiệp",
        "business": "Cập nhật kết quả kinh doanh",
        "financials": "Báo cáo tài chính nhiều năm",
        "ratios": "Chỉ số tài chính (tính từ BCTC)",
        "peers": "So sánh với ngành",
        "technical": "Phân tích kỹ thuật",
        "news": "Tin tức & sự kiện",
        "valuation": "Định giá cổ phiếu",
        "risks": "Rủi ro & thách thức",
        "conclusion": "Kết luận & khuyến nghị",
        "appendix": "Phụ lục: giải trình chấm điểm, phương pháp, nguồn dữ liệu",
    }
    DEFAULT_SECTIONS = list(SECTIONS)
    SHORT_SECTIONS = ["summary", "business", "technical", "valuation", "risks", "conclusion"]
    _ALIASES = {"scoring": "appendix"}

    def generate(
        self,
        analysis: Dict[str, Any],
        report_type: str = "full",
        output_path: Optional[str] = None,
        sections: Optional[List[str]] = None,
        cover: bool = True,
        toc: bool = True,
    ) -> bytes:
        """
        Tạo báo cáo PDF theo các mục người dùng chọn và trả về bytes.
        report_type "short" = tóm tắt, KQKD, kỹ thuật, định giá, rủi ro, kết luận; "full" = tất cả các mục.
        """
        if sections is None:
            sections = self.SHORT_SECTIONS if report_type == "short" else list(self.DEFAULT_SECTIONS)
        sections = [self._ALIASES.get(x, x) for x in sections]
        sections = [x for x in self.DEFAULT_SECTIONS if x in sections] or ["summary"]
        data, a = self._prepare_data(analysis)

        pdf = EquityReportPDF(data)
        pdf.alias_nb_pages()
        if cover:
            self._render_cover(pdf, data)
        has_toc = toc and len(sections) > 1
        if has_toc:
            pdf.add_page()
            pdf.insert_toc_placeholder(self._render_toc, pages=1)   # fpdf2 tự sang trang mới sau chỗ dành cho mục lục
        renderers = {
            "summary": self._render_summary, "profile": self._render_profile, "business": self._render_business,
            "financials": self._render_financials, "ratios": self._render_ratios, "peers": self._render_peers,
            "technical": self._render_technical, "news": self._render_news, "valuation": self._render_valuation,
            "risks": self._render_risks, "conclusion": self._render_conclusion, "appendix": self._render_appendix,
        }
        for i, sec in enumerate(sections):
            if i == 0 and (not has_toc or pdf.page <= pdf.cover_page):
                pdf.add_page()           # mục đầu tiên mở trang mới (khi chưa có trang mục lục đi trước)
            renderers[sec](pdf, data, a)

        pdf_bytes = bytes(pdf.output())
        symbol = data["ticker"]
        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(settings.REPORTS_DIR / f"{symbol}_{report_type}_{ts}.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        logger.info("PDF generated successfully: %s (%d bytes)", output_path, len(pdf_bytes))
        return pdf_bytes

    # ─────────────────────────────────────────────────────────────────────────
    # Bìa & mục lục
    # ─────────────────────────────────────────────────────────────────────────

    def _render_cover(self, pdf: EquityReportPDF, data: dict):
        """Trang bìa ảnh tảng băng: mã, tên doanh nghiệp, ngày & giờ xuất thay đổi theo từng lần xuất."""
        try:
            from reports.cover import render_cover   # thiếu file cover.py thì bỏ bìa, vẫn xuất báo cáo
            img = render_cover(data["ticker"], data.get("name", ""), data.get("exported_at"),
                               data.get("last_session", ""), data.get("exchange", ""))
        except Exception as exc:          # bìa lỗi thì vẫn xuất phần nội dung
            logger.warning("Không dựng được trang bìa: %s", exc)
            return
        pdf.cover_page = pdf.page + 1      # đặt TRƯỚC add_page để header() bỏ qua trang bìa
        pdf.add_page()
        pdf.set_auto_page_break(False)
        pdf.image(io.BytesIO(img), x=0, y=0, w=210, h=297)
        pdf.set_auto_page_break(True, margin=PAGE_BOTTOM if pdf.has_bg else 16)

    @staticmethod
    def _render_toc(pdf: EquityReportPDF, outline):
        f = pdf.font_name
        pdf.set_y(pdf.top + 6)
        pdf.set_font(pdf.big_font, "B", 22)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 12, "MỤC LỤC", new_x="LMARGIN", new_y="NEXT")
        pdf.set_fill_color(*GOLD)
        pdf.rect(14, pdf.get_y(), 24, 1.1, "F")
        pdf.ln(5)
        pdf.set_font(f, "", 8.4)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 5, f"{pdf.meta.get('ticker', '')} · {pdf.meta.get('name', '')} · xuất lúc {pdf.meta.get('fetched_at', '')}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        for sec in outline:
            if sec.level != 0:
                continue
            num, _, title = sec.name.partition("  ")
            y = pdf.get_y()
            pdf.set_fill_color(*BG_DEEP)
            pdf.rect(14, y + 0.6, 11, 7, "F", round_corners=True, corner_radius=1.5)
            pdf.set_xy(14, y + 0.6)
            pdf.set_font(pdf.big_font, "B", 9.5)
            pdf.set_text_color(*GOLD)
            pdf.cell(11, 7, num, align="C")
            pdf.set_xy(29, y)
            pdf.set_font(f, "B", 10.5)
            pdf.set_text_color(*TEXT)
            pdf.cell(140, 8.2, title, link=pdf.add_link(page=sec.page_number))
            pdf.set_draw_color(*LINE)
            pdf.set_line_width(0.2)
            pdf.set_dash_pattern(dash=0.8, gap=1.2)
            pdf.line(29 + pdf.get_string_width(title) + 3, y + 5.6, 184, y + 5.6)
            pdf.set_dash_pattern()
            pdf.set_xy(184, y)
            pdf.set_font(pdf.big_font, "B", 10)
            pdf.set_text_color(*GOLD_DK)
            pdf.cell(12, 8.2, str(sec.page_number), align="R", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2.4)
        pdf.set_text_color(*TEXT)

    # ─────────────────────────────────────────────────────────────────────────
    # 01 Tổng quan & khuyến nghị
    # ─────────────────────────────────────────────────────────────────────────

    def _render_summary(self, pdf: EquityReportPDF, data: dict, a: dict):
        ticker, name, industry = data["ticker"], data["name"], data["industry"]
        sub_title = " • ".join(x for x in [name, industry, data.get("exchange", "")] if x)
        sub_title += ("\nPhân tích định lượng tự động: cơ bản, định giá, kỹ thuật, động lượng và rủi ro"
                      f" – dữ liệu phiên {data.get('last_session', '')}"
                      + (f" (định giá tại ngày {pd.Timestamp(data['as_of']):%d/%m/%Y})." if data.get("as_of") else "."))
        closes = a["px"]["close"].tail(160).tolist() if a.get("px") is not None else None
        pdf.hero(ticker, sub_title, closes)
        pdf.sec_no += 1
        try:
            pdf.start_section(f"{pdf.sec_no:02d}  Tổng quan & khuyến nghị", level=0)
        except Exception:
            pass

        # Hộp khuyến nghị + 4 thẻ
        y0 = pdf.get_y()
        recd = a["recd"]
        pdf.set_fill_color(*a["rec_color"])
        pdf.rect(14, y0, 58, 27, "F", round_corners=True, corner_radius=2.6)
        pdf.set_xy(14, y0 + 2.6)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(pdf.font_name, "", 7.5)
        pdf.cell(58, 3.8, "KHUYẾN NGHỊ", align="C", new_x="LEFT", new_y="NEXT")
        pdf.set_font(pdf.big_font, "B", 15 if len(a["rec"]) <= 10 else 10)
        pdf.cell(58, 9 if a.get("inv") else 10, a["rec"], align="C", new_x="LEFT", new_y="NEXT")
        pdf.set_font(pdf.font_name, "", 7.6)
        er = recd.get("expected_return")
        if a.get("inv"):
            hs = (a["inv"].get("health") or {}).get("score")
            pdf.set_font(pdf.font_name, "", 6.9)
            pdf.cell(58, 3.8, f"Tổng LN kỳ vọng {er:+.1f}%" if er is not None else "Chưa đủ cơ sở định giá",
                     align="C", new_x="LEFT", new_y="NEXT")
            if hs is not None:
                pdf.cell(58, 3.8, f"Sức khỏe tài chính {hs:.0f}/100", align="C")
            boxes = [("Giá hiện tại", _n(a["price"])), ("Giá mục tiêu 12T", _n(a["target"])),
                     ("Upside", _n(a["upside"], 1, "%", sign=True) if a["upside"] is not None else "N/A"),
                     ("Mức rủi ro", str((a["inv"].get("risk") or {}).get("level", "—")))]
        else:
            pdf.cell(58, 4.2, (f"Lợi suất kỳ vọng {er:+.1f}%" if er is not None else "Chưa đủ dữ liệu định giá")
                     + (f" · điểm {a['total']:.0f}/100" if a["total"] is not None else ""), align="C")
            boxes = [("Giá hiện tại", _n(a["price"])), ("Giá trị hợp lý", _n(a["target"])),
                     ("Chênh lệch", _n(a["upside"], 1, "%", sign=True) if a["upside"] is not None else "N/A"),
                     ("Tỷ suất cổ tức", _n((a["fv"] or {}).get("dividend_yield"), 1, "%"))]
        bx_x = 75.0
        for lbl, val in boxes:
            pdf.card(bx_x, y0, 29, 27)
            pdf.set_xy(bx_x, y0 + 4.5)
            pdf.set_text_color(*GREY)
            pdf.set_font(pdf.font_name, "", 7.2)
            pdf.cell(29, 3.8, lbl, align="C")
            pdf.set_xy(bx_x, y0 + 10.5)
            pdf.set_text_color(*GOLD_DK)
            pdf.set_font(pdf.big_font, "B", 12.5 if len(val) <= 8 else 10.5)
            pdf.cell(29, 9, val, align="C")
            bx_x += 31.0
        pdf.set_text_color(*TEXT)
        pdf.set_y(y0 + 31)

        # Thông tin cổ phiếu (trái) + luận điểm (phải)
        y1 = pdf.get_y()
        pdf.h3("Thông tin cổ phiếu")
        pdf.kv_grid(a["stock_info"], cols=1, width=80, size=7.4, h=4.9)
        y_left_end = pdf.get_y()
        pdf.set_xy(98, y1)
        pdf.set_fill_color(*GOLD)
        pdf.rect(98, y1 + 2.1, 1.2, 4.4, "F")
        pdf.set_xy(101, y1 + 1.5)
        pdf.set_font(pdf.font_name, "B", 9.2)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 5.6, "Luận điểm đầu tư")
        pdf.set_xy(98, y1 + 9)
        pdf.set_font(pdf.font_name, "", 7.7)
        pdf.set_text_color(*TEXT)
        for c in a["comments"]:
            pdf.set_x(98)
            pdf.multi_cell(98, 4.1, "•  " + c, new_x="LEFT", new_y="NEXT")
            pdf.ln(0.6)
        pdf.set_y(max(pdf.get_y(), y_left_end) + 2)

        # Chỉ tiêu tài chính chính
        kf = a.get("key_fin")
        if kf:
            pdf.h3("Chỉ tiêu tài chính chính (đơn vị: tỷ đồng)")
            n = len(kf["periods"])
            pdf.table(["Chỉ tiêu"] + kf["periods"], [[lbl] + vals for lbl, vals in kf["rows"]],
                      [62] + [120 / n] * n, size=7.4, h=4.7,
                      colors=[[None] + [(GREEN if str(v).startswith("+") else RED if str(v).startswith("-") else None) for v in vals]
                              if "yoy" in lbl else None for lbl, vals in kf["rows"]])

        # Thẻ điểm 5 trụ cột
        pdf.h3("Thẻ điểm 5 trụ cột (0–100)")
        names_ = {"technical": "Kỹ thuật", "momentum": "Động lượng", "fundamental": "Cơ bản",
                  "valuation": "Định giá", "risk": "Quản trị rủi ro"}
        wsum = sum(a["weights"].values()) or 100
        for k in ["fundamental", "valuation", "technical", "momentum", "risk"]:
            s_val = a["scores"].get(k)
            pdf.set_font(pdf.font_name, "", 8)
            pdf.cell(46, 5.4, f"{names_[k]} ({a['weights'].get(k, 20) / wsum * 100:.0f}%)")
            yb = pdf.get_y() + 1.3
            pdf.set_fill_color(*TRACK)
            pdf.rect(62, yb, 112, 2.8, "F", round_corners=True, corner_radius=1.4)
            if s_val is not None:
                pdf.set_fill_color(*(GREEN if s_val >= 65 else AMBER if s_val >= 45 else RED))
                pdf.rect(62, yb, max(2.8, min(112.0, 112 * s_val / 100)), 2.8, "F", round_corners=True, corner_radius=1.4)
            pdf.set_x(176)
            pdf.set_font(pdf.font_name, "B", 8)
            pdf.cell(20, 5.4, f"{s_val:.0f}/100" if s_val is not None else "Thiếu DL", align="R", new_x="LMARGIN", new_y="NEXT")

    @staticmethod
    def _tiles(pdf: EquityReportPDF, items, h: float = 17, gap: float = 3.0):
        """Hàng thẻ số lớn (nhãn nhỏ phía trên, số đậm phía dưới) chia đều bề rộng trang."""
        n = len(items)
        w = (182 - gap * (n - 1)) / n
        if pdf.get_y() + h > pdf.h - pdf.b_margin:
            pdf.add_page()
        y = pdf.get_y()
        f = pdf.font_name
        for i, (lbl, val, col) in enumerate(items):
            x = 14 + i * (w + gap)
            pdf.card(x, y, w, h)
            pdf.set_fill_color(*GOLD)
            pdf.rect(x + 4, y + h - 2.2, 10, 0.8, "F")
            pdf.set_xy(x + 4, y + 2.6)
            pdf.set_font(f, "", 7.3)
            pdf.set_text_color(*MUTED)
            pdf.cell(w - 8, 3.6, lbl)
            pdf.set_xy(x + 4, y + h / 2 - 2.2)
            pdf.set_font(pdf.big_font, "B", 13)
            pdf.set_text_color(*col)
            pdf.cell(w - 8, 7, val)
        pdf.set_text_color(*TEXT)
        pdf.set_y(y + h + 2.5)

    # ─────────────────────────────────────────────────────────────────────────
    # 02 Hồ sơ doanh nghiệp
    # ─────────────────────────────────────────────────────────────────────────

    def _render_profile(self, pdf: EquityReportPDF, data: dict, a: dict):
        pdf.h2("Hồ sơ doanh nghiệp")
        c = a.get("company") or {}
        labels = [("company_name", "Tên doanh nghiệp"), ("short_name", "Tên viết tắt"), ("exchange", "Sàn niêm yết"),
                  ("industry", "Ngành"), ("icb_name3", "Ngành ICB cấp 3"), ("icb_name4", "Ngành ICB cấp 4"),
                  ("charter_capital", "Vốn điều lệ"), ("established_year", "Năm thành lập"),
                  ("listing_date", "Ngày niêm yết"), ("no_employees", "Số nhân sự"), ("website", "Website"),
                  ("address", "Trụ sở")]
        pairs = []
        for k, lbl in labels:
            v = c.get(k)
            if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "nan", "None"):
                continue
            if k == "charter_capital" and isinstance(v, (int, float)):
                v = f"{v / 1e9:,.0f} tỷ đồng" if v > 1e6 else f"{v:,.0f}"
            pairs.append((lbl, str(v)[:60]))
        if pairs:
            pdf.h3("Thông tin niêm yết")
            pdf.kv_grid(pairs, cols=2, size=7.5)
        about = c.get("company_profile") or c.get("overview") or c.get("business_model")
        if about and isinstance(about, str):
            pdf.h3("Hoạt động kinh doanh")
            pdf.para(about[:1500] + ("…" if len(about) > 1500 else ""), size=7.8)
        prof = a.get("profile") or {}
        sh = prof.get("shareholders")
        if isinstance(sh, pd.DataFrame) and not sh.empty:
            pdf.h3("Cổ đông lớn")
            name_c = next((x for x in sh.columns if any(k in str(x).lower() for k in ("name", "share_holder", "tên"))), sh.columns[0])
            pct_c = next((x for x in sh.columns if any(k in str(x).lower() for k in ("percent", "ratio", "own", "tỷ lệ"))), None)
            qty_c = next((x for x in sh.columns if any(k in str(x).lower() for k in ("quantity", "shares", "số lượng"))), None)
            rows = []
            for _, r in sh.head(8).iterrows():
                pct = r.get(pct_c) if pct_c else None
                pct = pct * 100 if isinstance(pct, (int, float)) and pct <= 1 else pct
                rows.append([str(r.get(name_c, ""))[:60], _n(r.get(qty_c)) if qty_c else "—", _n(pct, 2, "%") if pct is not None else "—"])
            pdf.table(["Cổ đông", "Số cổ phần", "Tỷ lệ"], rows, [112, 40, 30])
        off = prof.get("officers")
        if isinstance(off, pd.DataFrame) and not off.empty:
            pdf.h3("Ban lãnh đạo")
            name_c = next((x for x in off.columns if "name" in str(x).lower() or "tên" in str(x).lower()), off.columns[0])
            pos_c = next((x for x in off.columns if any(k in str(x).lower() for k in ("position", "chức"))), None)
            pdf.table(["Họ và tên", "Chức vụ"], [[str(r.get(name_c, ""))[:50], str(r.get(pos_c, "") if pos_c else "")[:70]]
                                                 for _, r in off.head(8).iterrows()], [70, 112])
        if not pairs and not (isinstance(sh, pd.DataFrame) and not sh.empty):
            pdf.para("Nguồn dữ liệu chưa trả về hồ sơ doanh nghiệp tại thời điểm tạo báo cáo.", color=MUTED)

    # ─────────────────────────────────────────────────────────────────────────
    # 03 Cập nhật kết quả kinh doanh
    # ─────────────────────────────────────────────────────────────────────────

    def _render_business(self, pdf: EquityReportPDF, data: dict, a: dict):
        pdf.h2("Cập nhật kết quả kinh doanh")
        wide = a.get("fin_wide")
        if wide is None or wide.empty or len(wide) < 2:
            pdf.para("Không đủ số liệu BCTC để so sánh cùng kỳ.", color=MUTED)
        else:
            cur, prev = wide.index[-1], wide.index[-2]
            pcur, pprev = key_to_label(cur), key_to_label(prev)
            if cur % 10:                                     # kỳ quý → so với cùng quý năm trước nếu có
                same = cur - 10
                if same in wide.index:
                    prev, pprev = same, key_to_label(same)
            bank = a.get("is_bank")
            items = ([("net_interest_income", "Thu nhập lãi thuần"), ("total_operating_income", "Tổng thu nhập hoạt động"),
                      ("provision_expense", "Chi phí dự phòng rủi ro tín dụng"), ("profit_before_tax", "Lợi nhuận trước thuế"),
                      ("net_income", "Lợi nhuận sau thuế"), ("net_income_parent", "LNST cổ đông công ty mẹ")] if bank else
                     [("revenue", "Doanh thu thuần"), ("gross_profit", "Lợi nhuận gộp"), ("financial_income", "Doanh thu HĐ tài chính"),
                      ("financial_expense", "Chi phí tài chính"), ("selling_expense", "Chi phí bán hàng"),
                      ("admin_expense", "Chi phí quản lý DN"), ("profit_before_tax", "Lợi nhuận trước thuế"),
                      ("net_income", "Lợi nhuận sau thuế"), ("net_income_parent", "LNST cổ đông công ty mẹ")])
            rows, colors, notes = [], [], []
            for k, lbl in items:
                if k not in wide.columns:
                    continue
                v1, v0 = wide.loc[cur, k], wide.loc[prev, k]
                if pd.isna(v1) and pd.isna(v0):
                    continue
                chg = (v1 / v0 - 1) * 100 if pd.notna(v1) and pd.notna(v0) and v0 not in (0,) and v0 > 0 and v1 > 0 else None
                if pd.notna(v1) and pd.notna(v0) and v0 < 0 and v1 < 0:
                    chg = (abs(v1) / abs(v0) - 1) * 100
                rows.append([lbl, _n(v0 / 1e9 if pd.notna(v0) else None), _n(v1 / 1e9 if pd.notna(v1) else None),
                             _n(chg, 1, "%", sign=True)])
                good = not (v1 < 0 if pd.notna(v1) else False)
                colors.append([None, None, None, None if chg is None else ((GREEN if chg >= 0 else RED) if good else (RED if chg >= 0 else GREEN))])
            pdf.h3(f"Kết quả kinh doanh {pcur} so với {pprev} (tỷ đồng)")
            pdf.table(["Chỉ tiêu", pprev, pcur, "% thay đổi"], rows, [82, 34, 34, 32], colors=colors)
            r = (a.get("fin_summary") or {}).get("ratios")
            if r is not None and not r.empty and cur in r.index and prev in r.index:
                for key, lbl in (("gross_margin", "Biên lợi nhuận gộp"), ("net_margin", "Biên lợi nhuận ròng"), ("roe", "ROE")):
                    if key in r.columns and pd.notna(r.loc[cur, key]) and pd.notna(r.loc[prev, key]):
                        d = r.loc[cur, key] - r.loc[prev, key]
                        notes.append(f"{lbl} {r.loc[cur, key]:.1f}% ({'tăng' if d >= 0 else 'giảm'} {abs(d):.1f} điểm % so với {pprev}).")
            rg = a.get("rev_g")
            if rg is not None:
                notes.insert(0, f"Tăng trưởng doanh thu kỳ gần nhất {rg:+.1f}% ({a.get('rev_g_basis') or 'so với kỳ trước'}).")
            if notes:
                pdf.bullets(notes, size=7.9)
        # Biểu đồ doanh thu – LNST & sức mạnh tương đối (giữ nguyên biểu đồ cũ)
        pdf.h3("Doanh thu & lợi nhuận qua các kỳ", min_space=70)
        y_chart = pdf.get_y()
        b1 = pdf.chart(_generate_fin_chart(a["fin"]), x=14, y=y_chart, w=89.5)
        kf = a.get("key_fin")
        pdf.set_xy(107, y_chart)
        if kf:
            pdf.set_font(pdf.font_name, "", 7.6)
            for lbl, vals in kf["rows"][:4]:
                pdf.set_x(107)
                pdf.set_text_color(*MUTED)
                pdf.cell(40, 5, lbl.strip())
                pdf.set_text_color(*TEXT)
                pdf.cell(49, 5, "  ".join(str(v) for v in vals[-3:]), align="R", new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(107)
            pdf.set_font(pdf.font_name, "", 6.8)
            pdf.set_text_color(*MUTED)
            pdf.multi_cell(89, 3.6, "3 kỳ gần nhất: " + ", ".join(kf["periods"][-3:]) + ". Biểu đồ trái: doanh thu và LNST (tỷ đồng) theo kỳ BCTC.",
                           new_x="LMARGIN", new_y="NEXT")
        pdf.set_y(max(b1, pdf.get_y()) + 2)
        pdf.set_text_color(*TEXT)

    # ─────────────────────────────────────────────────────────────────────────
    # 06 Phân tích kỹ thuật – biểu đồ và bảng chỉ báo đi liền nhau
    # ─────────────────────────────────────────────────────────────────────────

    def _render_technical(self, pdf: EquityReportPDF, data: dict, a: dict):
        pdf.h2("Phân tích kỹ thuật", min_space=150, new_page=pdf.get_y() > 120)
        ticker = data["ticker"]
        if a.get("px") is None:
            pdf.para("Không có dữ liệu giá lịch sử.", color=MUTED)
            return
        bottom = pdf.chart(_generate_price_chart(a["px"], ticker, a["target"], a["stop"]), x=14, w=182)
        pdf.set_y(bottom + 2)
        rows = a.get("tech_rows") or []
        if rows:
            pdf.h3("Chỉ báo kỹ thuật (phiên gần nhất)", min_space=40)
            colors = []
            for _, _, note in rows:
                c = None
                if any(k in note for k in ("▲", "dương", "mua chiếm", "vào", "Mạnh hơn", "tích cực")):
                    c = GREEN
                elif any(k in note for k in ("▼", "âm", "bán chiếm", "ra", "Yếu hơn", "tiêu cực", "Quá mua")):
                    c = RED
                colors.append([None, None, c])
            pdf.table(["Chỉ báo", "Giá trị", "Diễn giải"], [list(r) for r in rows], [58, 46, 78],
                      aligns=["L", "R", "L"], size=7.3, h=4.6, colors=colors)
        # Sức mạnh tương đối + nhận định
        pdf.h3("Sức mạnh tương đối so với VN-Index & nhận định", min_space=65)
        y = pdf.get_y()
        b = pdf.chart(_generate_rel_chart(a["px"], a["idx"]), x=14, y=y, w=89.5)
        pdf.set_xy(107, y)
        notes = []
        if a.get("trend"):
            notes.append(f"Xu hướng tổng hợp: {a['trend'].lower()}.")
        if a.get("rsi_last") is not None:
            r = a["rsi_last"]
            notes.append(f"RSI {r:.0f}: " + ("vùng quá mua – dễ điều chỉnh." if r >= 70 else "vùng quá bán – có thể hồi kỹ thuật." if r <= 30
                                             else "trung tính."))
        if a.get("rs6") is not None:
            notes.append(f"6 tháng qua {'mạnh' if a['rs6'] > 0 else 'yếu'} hơn VN-Index {abs(a['rs6']):.1f} điểm %.")
        if a.get("stop"):
            notes.append(f"Mức cắt lỗ tham khảo {a['stop']:,.0f} VND (giá − 2×ATR).")
        notes.append("Phân tích kỹ thuật dùng để chọn thời điểm giao dịch, không thay đổi khuyến nghị theo định giá.")
        pdf.set_font(pdf.font_name, "", 7.8)
        for t in notes:
            pdf.set_x(107)
            pdf.multi_cell(89, 4.2, "•  " + t, new_x="LEFT", new_y="NEXT")
            pdf.ln(0.6)
        pdf.set_y(max(b, pdf.get_y()) + 2)

    # ─────────────────────────────────────────────────────────────────────────
    # 07 Tin tức & sự kiện
    # ─────────────────────────────────────────────────────────────────────────

    def _render_news(self, pdf: EquityReportPDF, data: dict, a: dict):
        pdf.h2("Tin tức & sự kiện")
        items = data.get("news_items", [])
        if not items:
            pdf.para("Chưa thu thập được tin tức cho mã này tại thời điểm tạo báo cáo.", color=MUTED)
        else:
            rows, colors = [], []
            for it in items:
                s_tag = it.get("sentiment", "Trung tính")
                rows.append([it.get("date", "--"), s_tag, str(it.get("title", "")), it.get("source", "")])
                colors.append([MUTED, GREEN if "Tích cực" in s_tag else RED if "Tiêu cực" in s_tag else MUTED, None, MUTED])
            pdf.table(["Ngày", "Sắc thái", "Tiêu đề", "Nguồn"], rows, [16, 20, 118, 28], aligns=["L", "L", "L", "L"],
                      size=7.2, h=4.8, colors=colors)
            pdf.para("Sắc thái tin được phân loại tự động theo từ điển từ khóa – chỉ mang tính tham khảo.", size=6.8, color=MUTED)
        ev = (a.get("profile") or {}).get("events")
        if isinstance(ev, pd.DataFrame) and not ev.empty:
            pdf.h3("Sự kiện doanh nghiệp")
            cols = list(ev.columns)
            title_c = next((c for c in cols if any(k in str(c).lower() for k in ("title", "event_name", "name", "tiêu đề"))), cols[0])
            date_c = next((c for c in cols if any(k in str(c).lower() for k in ("date", "ngày"))), None)
            pdf.table(["Ngày", "Sự kiện"], [[str(r.get(date_c, ""))[:10] if date_c else "", str(r.get(title_c, ""))]
                                            for _, r in ev.head(8).iterrows()], [24, 158], aligns=["L", "L"], size=7.2)

    # ─────────────────────────────────────────────────────────────────────────
    # 08 Định giá
    # ─────────────────────────────────────────────────────────────────────────

    def _render_valuation(self, pdf: EquityReportPDF, data: dict, a: dict):
        if (a.get("fv") or {}).get("model") == "12m":
            return self._render_valuation_12m(pdf, data, a)
        pdf.h2("Định giá cổ phiếu", new_page=pdf.get_y() > 150)
        fv = a.get("fv") or {}
        pdf.para("Giá trị hợp lý là ước tính theo các giả định bên dưới, không phải mức giá chắc chắn đạt được. "
                 "Mỗi phương pháp ghi rõ hệ số dùng và nguồn của hệ số; chỉ phương pháp đủ dữ liệu mới được tính.", size=7.6, color=MUTED)
        if not fv.get("available"):
            pdf.bullets(fv.get("notes") or ["Không đủ dữ liệu để định giá."])
            return
        self._tiles(pdf, [("Thị giá", _n(fv["price"]), NAVY), ("Giá trị hợp lý", _n(fv["fair_value"]), GOLD_DK),
                          ("Chênh lệch", _n(fv["upside"], 1, "%", sign=True), GREEN if fv["upside"] >= 0 else RED),
                          ("Lợi suất kỳ vọng", _n(fv["expected_return"], 1, "%", sign=True),
                           GREEN if fv["expected_return"] >= 0 else RED)], h=18)
        pdf.h3("Kết quả theo từng phương pháp")
        rows = [[m["name"], f"{m['multiple']:.2f}x", f"{m['base_label']} {m['base']:,.0f}", f"{m['fair']:,.0f}",
                 f"{m['upside']:+.1f}%", f"{m['weight'] * 100:.0f}%"] for m in fv["methods"]]
        rows.append(["Giá trị hợp lý tổng hợp", "", "", f"{fv['fair_value']:,.0f}", f"{fv['upside']:+.1f}%", "100%"])
        colors = [[None, None, None, None, GREEN if m["upside"] >= 0 else RED, None] for m in fv["methods"]]
        colors.append([NAVY, None, None, GOLD_DK, GREEN if fv["upside"] >= 0 else RED, None])
        pdf.table(["Phương pháp", "Hệ số", "Cơ sở (đ/cp)", "Giá trị (đ/cp)", "Chênh lệch", "Trọng số"], rows,
                  [46, 22, 40, 30, 24, 20], colors=colors)
        pdf.set_font(pdf.font_name, "", 6.9)
        pdf.set_text_color(*MUTED)
        for m in fv["methods"]:
            pdf.multi_cell(0, 3.6, f"• {m['name']}: {m['source']}.", new_x="LMARGIN", new_y="NEXT")
        gw = fv.get("group_weights", {})
        pdf.multi_cell(0, 3.6, f"• Trọng số nhóm: P/E {gw.get('pe', 0) * 100:.0f}% – P/B {gw.get('pb', 0) * 100:.0f}% "
                               f"({'doanh nghiệp tài chính' if fv.get('financial') else 'doanh nghiệp phi tài chính'}); "
                               "trong mỗi nhóm các phương pháp chia đều.", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*TEXT)
        hist = fv.get("history") or {}
        years = sorted(set(hist.get("pe", {})) | set(hist.get("pb", {})))
        if years:
            pdf.h3("Bội số lịch sử cuối năm của doanh nghiệp")
            pdf.table(["Chỉ tiêu"] + [str(y) for y in years] + ["Trung vị"],
                      [["P/E"] + [_n(hist.get("pe", {}).get(y), 1, "x") for y in years] + [_n(hist.get("pe_median"), 1, "x")],
                       ["P/B"] + [_n(hist.get("pb", {}).get(y), 2, "x") for y in years] + [_n(hist.get("pb_median"), 2, "x")]],
                      [30] + [128 / (len(years) + 1)] * (len(years) + 1), size=7.4)
            pdf.para("Giá cuối năm là giá đã điều chỉnh; lợi nhuận và vốn chủ từng năm chia cho số cổ phiếu hiện tại để cùng cơ sở.",
                     size=6.8, color=MUTED)
        pdf.h3("Độ nhạy của giá trị hợp lý (đ/cp)", min_space=48)
        sens = fv.get("sensitivity") or []
        rows, colors = [], []
        for r in sens:
            label = f"Hệ số {r['mult_chg'] * 100:+.0f}%"
            vals = [r[-0.1], r[0.0], r[0.1]]
            rows.append([label] + [f"{v:,.0f}" for v in vals])
            colors.append([None] + [GREEN if v >= fv["price"] else RED for v in vals])
        pdf.table(["Thay đổi hệ số định giá", "EPS/BVPS −10%", "Cơ sở", "EPS/BVPS +10%"], rows, [62, 40, 40, 40], colors=colors)
        asum = fv.get("assumptions") or {}
        notes = [f"Chi phí vốn chủ Ke = {asum.get('risk_free', 0) * 100:.0f}% + β × {asum.get('equity_premium', 0) * 100:.0f}% = "
                 f"{asum.get('ke', 0) * 100:.1f}% (β dùng {_n(asum.get('beta_used'), 2)}, β đo được {_n(asum.get('beta'), 2)}, chặn trong 0,6–1,6; "
                 f"Ke chặn trong 10–18%); tăng trưởng dài hạn tối đa {asum.get('g_cap', 0) * 100:.0f}%.",
                 f"Độ tin cậy định giá: {fv.get('confidence', '—')}."] + list(fv.get("notes") or [])
        pdf.bullets(notes, size=7.4, h=4)


    def _render_valuation_12m(self, pdf: EquityReportPDF, data: dict, a: dict):
        """Mục Định giá theo Valuation Engine 12 tháng: phương pháp, kịch bản, giả định, nguồn & ngày dữ liệu."""
        from analytics.valuation_engine import SCEN_LABEL
        pdf.h2("Định giá & giá mục tiêu 12 tháng", new_page=pdf.get_y() > 150)
        fv = a.get("fv") or {}
        pdf.para("Giá mục tiêu 12 tháng là ước tính theo các giả định bên dưới, không phải mức giá chắc chắn đạt được. Chỉ phương "
                 "pháp đủ dữ liệu và cho kết quả hợp lệ mới được tính; trọng số được chuẩn hóa lại trên các phương pháp hợp lệ.",
                 size=7.6, color=MUTED)
        if not fv.get("methods"):
            pdf.bullets([f"Trạng thái: {fv.get('status', 'CHƯA ĐỦ CƠ SỞ ĐỊNH GIÁ')}."] + list(fv.get("notes") or [])
                        + [f"Không dùng {m}: {r}." for m, r in fv.get("invalid", [])], size=7.6)
            return
        up, er = fv.get("upside"), fv.get("expected_return")
        self._tiles(pdf, [("Thị giá", _n(fv.get("price")), NAVY), ("Giá mục tiêu 12T", _n(fv.get("target_12m")), GOLD_DK),
                          ("Upside", _n(up, 1, "%", sign=True), GREEN if (up or 0) >= 0 else RED),
                          ("Tổng LN kỳ vọng", _n(er, 1, "%", sign=True), GREEN if (er or 0) >= 0 else RED)], h=18)
        if not fv.get("available"):
            pdf.para(f"Trạng thái: {fv.get('status')} (độ tin cậy {fv.get('confidence', '—').lower()}) – các con số dưới đây "
                     "chỉ để tham khảo, KHÔNG dùng để ra khuyến nghị.", size=7.6, color=RED)
        pdf.h3("Kết quả theo từng phương pháp (kịch bản cơ sở)")
        rows = [[m["name"], f"{m['multiple']:.2f}x" if m.get("multiple") else "—",
                 f"{m['base_label']} {m['base']:,.0f}" if m.get("base") is not None else "—", f"{m['fair']:,.0f}",
                 f"{m['upside']:+.1f}%", f"{m['weight'] * 100:.0f}%"] for m in fv["methods"]]
        rows.append(["Giá mục tiêu 12 tháng", "", "", f"{fv['target_12m']:,.0f}", f"{up:+.1f}%", "100%"])
        colors = [[None, None, None, None, GREEN if m["upside"] >= 0 else RED, None] for m in fv["methods"]]
        colors.append([NAVY, None, None, GOLD_DK, GREEN if up >= 0 else RED, None])
        pdf.table(["Phương pháp", "Hệ số", "Cơ sở (đ/cp)", "Giá trị (đ/cp)", "Upside", "Trọng số"], rows,
                  [36, 18, 58, 28, 22, 20], colors=colors)
        pdf.set_font(pdf.font_name, "", 6.9)
        pdf.set_text_color(*MUTED)
        for m in fv["methods"]:
            pdf.multi_cell(0, 3.6, f"• {m['name']}: {m['source']}.", new_x="LMARGIN", new_y="NEXT")
        for m, r in fv.get("invalid", []):
            pdf.multi_cell(0, 3.6, f"• Không dùng {m}: {r}.", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*TEXT)

        sc = fv.get("scenarios") or {}
        if any((sc.get(k) or {}).get("target") for k in sc):
            pdf.h3("Kịch bản Bear / Base / Bull (thay đổi bộ giả định)", min_space=40)
            srows, scol = [], []
            for k in ("bear", "base", "bull"):
                r = sc.get(k) or {}
                if not r.get("target"):
                    continue
                srows.append([SCEN_LABEL[k], _n((r.get("growth") or 0) * 100, 1, "%", sign=True),
                              _n(r["margin"] * 100, 1, "%") if r.get("margin") is not None else "—",
                              _n(r.get("ke", 0) * 100, 1, "%"), _n(r.get("eps_fwd")), _n(r.get("target")),
                              _n(r.get("upside"), 1, "%", sign=True)])
                scol.append([{"bear": RED, "base": AMBER, "bull": GREEN}[k], None, None, None, None, GOLD_DK,
                             GREEN if (r.get("upside") or 0) >= 0 else RED])
            pdf.table(["Kịch bản", "Tăng trưởng", "Biên LN", "Ke", "EPS dự phóng", "Giá mục tiêu", "Upside"], srows,
                      [40, 24, 22, 20, 26, 26, 24], colors=scol, bold_first=True)
            cfg = (a.get("inv") or {}).get("config", {}).get("valuation", {}).get("scenarios", {})
            if cfg:
                pdf.para("Giả định kịch bản: " + "; ".join(
                    f"{SCEN_LABEL[k]}: tăng trưởng {v['growth_shift'] * 100:+.0f} điểm %, biên LN ×{v['margin_factor']:.2f}, "
                    f"bội số phân vị {v['multiple_pct']}, Ke {v['ke_shift'] * 100:+.0f} điểm %, ROE {v['roe_shift']:+.0f} điểm %"
                    for k, v in cfg.items()) + ".", size=6.8, color=MUTED)

        hist = fv.get("history") or {}
        years = sorted(set(hist.get("pe", {})) | set(hist.get("pb", {})) | set(hist.get("ev_ebitda", {})))
        if years:
            pdf.h3("Bội số lịch sử cuối năm của doanh nghiệp", min_space=30)
            mk = lambda key, d: [_n((hist.get(key) or {}).get(y), d, "x") for y in years]  # noqa: E731
            hrows = [["P/E"] + mk("pe", 1), ["P/B"] + mk("pb", 2)]
            if not fv.get("financial"):          # EV/EBITDA không dùng cho ngân hàng/CTCK/bảo hiểm
                hrows.append(["EV/EBITDA"] + mk("ev_ebitda", 1))
            pdf.table(["Chỉ tiêu"] + [str(y) for y in years], hrows,
                      [30] + [152 / len(years)] * len(years), size=7.4)
        pdf.h3("Độ nhạy của giá mục tiêu (đ/cp)", min_space=48)
        rows, colors = [], []
        for r in fv.get("sensitivity") or []:
            vals = [r[-0.1], r[0.0], r[0.1]]
            rows.append([f"Bội số {r['mult_chg'] * 100:+.0f}%"] + [f"{v:,.0f}" for v in vals])
            colors.append([None] + [GREEN if v >= fv["price"] else RED for v in vals])
        pdf.table(["Thay đổi bội số định giá", "Lợi nhuận/BV −10%", "Cơ sở", "Lợi nhuận/BV +10%"], rows, [62, 40, 40, 40], colors=colors)
        asum = fv.get("assumptions") or {}
        pct = lambda v: _n(v * 100, 1, "%") if v is not None else "—"  # noqa: E731
        notes = [
            f"Ke = {pct(asum.get('risk_free'))} + β {_n(asum.get('beta_used'), 2)} × {pct(asum.get('equity_premium'))} = {pct(asum.get('ke'))} "
            f"(β đo được {_n(asum.get('beta'), 2)}).",
            f"Tăng trưởng cơ sở {pct(asum.get('g_base'))} = 60% CAGR 3 năm {asum.get('basis_growth', '')} ({pct(asum.get('g_hist'))}) "
            f"+ 40% tăng trưởng bền vững ROE × (1 − tỷ lệ chi trả) ({pct(asum.get('g_sustainable'))}); biên LN ròng cơ sở {pct(asum.get('net_margin_base'))}.",
            f"Cổ tức tiền mặt dự kiến {_n(fv.get('expected_dividend'))} đ/cp ({_n(fv.get('dividend_yield'), 1, '%')}), "
            + ("đã cộng một lần vào tổng lợi nhuận kỳ vọng; giá mục tiêu là giá sau khi trả cổ tức."
               if fv.get("dividends_included") else "không cộng (chưa trả đều tiền mặt)."),
            f"Giá mục tiêu 12T = giá trị nội tại hôm nay × (1 + Ke) − cổ tức; nội tại hôm nay ≈ {_n(fv.get('intrinsic_today'))} đ/cp.",
            f"Thị giá ngày {fv.get('price_date') or '—'}; BCTC năm gần nhất đến {fv.get('data_date') or '—'}; kỳ hạn {fv.get('horizon_months', 12)} tháng; "
            f"độ tin cậy định giá: {fv.get('confidence', '—')}.",
        ] + list(fv.get("notes") or [])
        pdf.bullets(notes, size=7.3, h=3.9)

    # ─────────────────────────────────────────────────────────────────────────
    # 09 Rủi ro & 10 Kết luận
    # ─────────────────────────────────────────────────────────────────────────

    def _render_risks(self, pdf: EquityReportPDF, data: dict, a: dict):
        pdf.h2("Rủi ro & thách thức")
        risks = a.get("risks") or []
        if not risks:
            pdf.para("Không phát hiện rủi ro trọng yếu từ số liệu hiện có.", color=MUTED)
            return
        col = {"Nghiêm trọng": RED, "Cao": RED, "Trung bình": AMBER, "Thấp": GREEN, "Cần theo dõi": MUTED}
        lvl = ((a.get("inv") or {}).get("risk") or {}).get("level")
        if lvl:
            pdf.para(f"Mức rủi ro tổng thể: {lvl}. " + (a["inv"]["risk"].get("rule") or ""), size=7.4)
        pdf.table(["Mức độ", "Rủi ro", "Căn cứ"], [list(r) for r in risks], [24, 118, 40], aligns=["L", "L", "L"],
                  size=7.3, h=5.0, colors=[[col.get(r[0], None), None, MUTED] for r in risks])
        pdf.para("Các mục 'Cần theo dõi' là khung rà soát theo đặc thù ngành/vĩ mô, không phải sự kiện đã xảy ra.",
                 size=6.8, color=MUTED)

    def _render_conclusion(self, pdf: EquityReportPDF, data: dict, a: dict):
        pdf.h2("Kết luận & khuyến nghị", min_space=90)
        recd = a["recd"]
        y = pdf.get_y()
        pdf.set_fill_color(*a["rec_color"])
        pdf.rect(14, y, 50, 22, "F", round_corners=True, corner_radius=2.4)
        pdf.set_xy(14, y + 2.5)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(pdf.font_name, "", 7.4)
        pdf.cell(50, 3.6, "KHUYẾN NGHỊ", align="C", new_x="LEFT", new_y="NEXT")
        pdf.set_font(pdf.big_font, "B", 15 if len(a["rec"]) <= 10 else 10)
        pdf.cell(50, 9, a["rec"], align="C", new_x="LEFT", new_y="NEXT")
        pdf.set_font(pdf.font_name, "", 7.2)
        pdf.cell(50, 4, (f"Giá mục tiêu 12T {_n(a['target'])}" if a.get("inv") else f"Giá trị hợp lý {_n(a['target'])}")
                 if a["target"] else "Chưa đủ dữ liệu định giá", align="C")
        pdf.set_xy(68, y)
        pdf.set_text_color(*TEXT)
        pdf.set_font(pdf.font_name, "", 7.9)
        for r in recd.get("reasons", []):
            pdf.set_x(68)
            pdf.multi_cell(128, 4.2, "•  " + r, new_x="LEFT", new_y="NEXT")
            pdf.ln(0.4)
        pdf.set_y(max(pdf.get_y(), y + 24) + 2)
        inv = a.get("inv")
        if inv:
            self._render_health_block(pdf, inv)
        pdf.h3("Tóm tắt luận điểm")
        pdf.bullets(a["comments"], size=7.9)
        watch = [r[1] for r in (a.get("risks") or []) if r[0] in ("Nghiêm trọng", "Cao", "Trung bình")][:4]
        watch.append("Kết quả kinh doanh và BCTC kỳ tới; diễn biến giá quanh vùng hỗ trợ/kháng cự trong bảng chỉ báo kỹ thuật.")
        pdf.h3("Điều cần theo dõi")
        pdf.bullets(watch, size=7.9)
        if inv:
            th = inv.get("thesis") or {}
            if th.get("positives") or th.get("negatives"):
                pdf.h3("Điểm mạnh / điểm yếu từ số liệu")
                pdf.bullets([f"(+) {x}" for x in th.get("positives", [])] + [f"(−) {x}" for x in th.get("negatives", [])], size=7.6)
            pdf.h3("Vì sao khuyến nghị như vậy & giá mục tiêu được tính thế nào?", min_space=40)
            pdf.bullets(inv.get("explanation") or [], size=7.4, h=3.9)
            from analytics.recommendation import investment_system_text
            pdf.h3("Hệ thống khuyến nghị", min_space=36)
            pdf.table(["Khuyến nghị", "Tiêu chí"], [[k, v] for k, v in investment_system_text(inv.get("config"))], [40, 142],
                      aligns=["L", "L"], colors=[[GREEN, None], [AMBER, None], [RED, None], [MUTED, None]], bold_first=True)
            pdf.para("Tổng lợi nhuận kỳ vọng = (giá mục tiêu 12 tháng − thị giá + cổ tức tiền mặt dự kiến) / thị giá. Không bao giờ "
                     "MUA chỉ vì sức khỏe tài chính cao và không BÁN chỉ vì sức khỏe thấp – luôn cần kết quả định giá đáng tin cậy. "
                     "Các ngưỡng là giả định thiết kế, cấu hình được.", size=7.2, color=MUTED)
            return
        pdf.h3("Hệ thống khuyến nghị")
        from analytics.recommendation import SYSTEM_TEXT
        pdf.table(["Khuyến nghị", "Tiêu chí"], [[k, v] for k, v in SYSTEM_TEXT], [40, 142], aligns=["L", "L"],
                  colors=[[GREEN, None], [AMBER, None], [RED, None]], bold_first=True)
        pdf.para("Lợi suất kỳ vọng = chênh lệch giữa giá trị hợp lý và thị giá + tỷ suất cổ tức tiền mặt. Khuyến nghị được kiểm "
                 "tra chéo bằng điểm tổng hợp 5 trụ cột: MUA nhưng điểm < 40 hạ về TRUNG LẬP; BÁN nhưng điểm ≥ 65 nâng về TRUNG LẬP; "
                 "định giá độ tin cậy thấp chỉ cho TRUNG LẬP.", size=7.2, color=MUTED)

    def _render_health_block(self, pdf: EquityReportPDF, inv: dict):
        h = inv.get("health") or {}
        if not h.get("groups"):
            return
        hs = h.get("score")
        pdf.h3("Sức khỏe tài chính (Financial Health Score) – " + (f"{hs:.1f}/100 · {h.get('rating_text', '')}" if hs is not None
               else f"chưa công bố (độ phủ số liệu {h.get('coverage', 0) * 100:.0f}%)"), min_space=40)
        rows, colors = [], []
        for g in h["groups"]:
            gs = g.get("score")
            gcol = GREEN if (gs or 0) >= 75 else AMBER if (gs or 0) >= 50 else RED
            for i, m in enumerate(g["metrics"]):
                ms = m.get("score")
                rows.append([f"{g['label']} ({g['weight']}%)" if i == 0 else "", _n(gs, 0) if i == 0 and gs is not None else "",
                             m["label"], m["display"], _n(ms, 0) if ms is not None else "không chấm"])
                colors.append([None, gcol if i == 0 else None, None, None,
                               None if ms is None else GREEN if ms >= 75 else AMBER if ms >= 50 else RED])
        pdf.table(["Nhóm (trọng số)", "Điểm nhóm", "Chỉ tiêu", "Giá trị", "Điểm"], rows, [46, 20, 66, 30, 20],
                  aligns=["L", "C", "L", "R", "C"], size=7.0, h=4.4, colors=colors)
        for n in h.get("notes", []):
            pdf.para("Lưu ý: " + n, size=6.8, color=MUTED)

    def _render_peers(self, pdf: EquityReportPDF, data: dict, a: dict):
        ticker = data["ticker"]
        font = "VN" if pdf.has_vn else "Helvetica"
        peers = data.get("peers") or {}
        group_name = peers.get("group")
        if group_name:
            pdf.h2(f"So sánh với ngành: {group_name} ({peers.get('n', 0)} doanh nghiệp có số liệu)")
        else:
            pdf.h2("So sánh với ngành: chưa xác định được nhóm ngành")

        rel = a.get("rel_val", {})
        peer_rows = [
            ("ROE (%)", a.get("last_roe"), peers.get("roe"), "higher"),
            ("Biên LN ròng (%)", a.get("last_margin"), peers.get("net_margin"), "higher"),
            ("Nợ/VCSH (lần)", a.get("last_de"), peers.get("de"), "lower"),
            ("P/E (lần)", rel.get("pe"), peers.get("pe"), "cheaper"),
            ("P/B (lần)", rel.get("pb"), peers.get("pb"), "cheaper"),
        ]
        pdf.set_font(font, "B", 7.6)
        pdf.set_fill_color(*SUB_FILL)
        for h, ww in [("Chỉ tiêu tài chính", 68), (ticker, 38), ("Trung vị ngành", 38), ("Đánh giá", 38)]:
            pdf.cell(ww, 5.0, h, fill=True, align="C")
        pdf.ln()

        pdf.set_font(font, "", 7.6)
        for idx, (lbl, me, med, mode) in enumerate(peer_rows):
            ok = me is not None and med is not None and not pd.isna(me) and not pd.isna(med)
            if not ok:
                col, tag = GREY, "Không đủ dữ liệu"
            elif mode == "higher":
                col, tag = (GREEN, "Tốt hơn ngành") if me > med else (RED, "Kém hơn ngành")
            elif mode == "lower":
                col, tag = (GREEN, "Tốt hơn ngành") if me < med else (RED, "Kém hơn ngành")
            else:
                col, tag = (GREEN, "Rẻ hơn ngành") if me < med else (RED, "Đắt hơn ngành")

            pdf.set_fill_color(*(LIGHT if idx % 2 == 0 else WHITE))
            pdf.cell(68, 4.8, "  " + lbl, fill=True)
            pdf.cell(38, 4.8, _n(me, 1), fill=True, align="C")
            pdf.cell(38, 4.8, _n(med, 1), fill=True, align="C")
            pdf.set_text_color(*col)
            pdf.cell(38, 4.8, tag, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TEXT)

        if peers.get("peers"):
            pdf.set_font(font, "", 6.8)
            pdf.set_text_color(*GREY)
            pdf.multi_cell(0, 3.6, "Nhóm so sánh: " + ", ".join(peers["peers"])
                           + ". Trung vị chỉ công bố khi có ≥ 3 doanh nghiệp có số liệu hợp lệ.",
                           new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TEXT)

    def _period_table(self, pdf: EquityReportPDF, title_col: str, rows: List[Tuple[str, List[str]]],
                      periods: List[str], label_w: float = 62.0):
        font = "VN" if pdf.has_vn else "Helvetica"
        col_w = (182 - label_w) / max(len(periods), 1)

        def head():
            pdf.set_font(font, "B", 7.4)
            pdf.set_fill_color(*BG_DEEP)
            pdf.set_text_color(*GOLD)
            pdf.cell(label_w, 5, " " + title_col, fill=True)
            for p in periods:
                pdf.cell(col_w, 5, p, align="C", fill=True)
            pdf.ln()
            pdf.set_text_color(*TEXT)
            pdf.set_font(font, "", 7.2)

        if pdf.get_y() + 20 > pdf.h - pdf.b_margin:
            pdf.add_page()
        head()
        pdf.set_text_color(*TEXT)
        pdf.set_font(font, "", 7.2)
        for i, (label, vals) in enumerate(rows):
            if pdf.get_y() + 4.6 > pdf.h - pdf.b_margin:
                pdf.add_page()
                head()
            if label.startswith("§"):
                pdf.set_font(font, "B", 7.4)
                pdf.set_fill_color(*SUB_FILL)
                pdf.set_text_color(*NAVY)
                pdf.cell(182, 4.6, " " + label[1:], fill=True, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(*TEXT)
                pdf.set_font(font, "", 7.2)
                continue
            pdf.set_fill_color(*(LIGHT if i % 2 == 0 else WHITE))
            pdf.cell(label_w, 4.4, " " + (label if len(label) <= 40 else label[:38] + "…"), fill=True)
            for v in vals:
                pdf.cell(col_w, 4.4, v, align="R", fill=True)
            pdf.ln()

    def _render_financials(self, pdf: EquityReportPDF, data: dict, a: dict):
        from data.financial_mapping import ITEMS_BY_KEY, PER_UNIT_KEYS, STATEMENT_ITEMS
        font = "VN" if pdf.has_vn else "Helvetica"
        fin = a.get("fin_wide")
        pdf.h2("Báo cáo tài chính nhiều năm (chuẩn hóa – đơn vị: tỷ đồng)", new_page=pdf.get_y() > 120)
        if fin is None or fin.empty:
            pdf.set_font(font, "", 8)
            pdf.cell(0, 5, "Không lấy được BCTC từ các nguồn dữ liệu.", new_x="LMARGIN", new_y="NEXT")
            return
        fin = fin.iloc[-6:]
        periods = [key_to_label(k) for k in fin.index]
        names = {"is": "KẾT QUẢ KINH DOANH", "bs": "CÂN ĐỐI KẾ TOÁN", "cf": "LƯU CHUYỂN TIỀN TỆ"}
        for st in ("is", "bs", "cf"):
            keys = [k for k in STATEMENT_ITEMS[st] if k in fin.columns and fin[k].notna().any()]
            if not keys:
                continue
            rows: List[Tuple[str, List[str]]] = [("§" + names[st], [])]
            for k in keys:
                per = k in PER_UNIT_KEYS
                rows.append((ITEMS_BY_KEY[k].label_vi,
                             [_n(v if per else (v / 1e9 if pd.notna(v) else v), 0) for v in fin[k].tolist()]))
            self._period_table(pdf, "Chỉ tiêu", rows, periods)
            pdf.ln(1.5)
        src = a.get("fin_sources")
        if src is not None and not src.empty:
            used = sorted({str(x) for x in pd.unique(src.values.ravel()) if isinstance(x, str)})
            pdf.set_font(font, "", 6.8)
            pdf.set_text_color(*GREY)
            pdf.multi_cell(0, 3.6, "Nguồn số liệu: " + ", ".join(used) +
                           ". Nguồn đứng trước trong chuỗi ưu tiên được dùng; ô thiếu được bù từ nguồn sau.",
                           new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TEXT)

    def _render_ratios(self, pdf: EquityReportPDF, data: dict, a: dict):
        from analytics.financial_ratios import RATIO_META
        font = "VN" if pdf.has_vn else "Helvetica"
        summ = a.get("fin_summary") or {}
        ratios = summ.get("ratios")
        pdf.h2("Chỉ số tài chính – tính trực tiếp từ BCTC")
        if ratios is None or ratios.empty:
            pdf.set_font(font, "", 8)
            pdf.cell(0, 5, "Không đủ BCTC để tính chỉ số.", new_x="LMARGIN", new_y="NEXT")
            return
        r = ratios.iloc[-6:]
        periods = [key_to_label(k) for k in r.index]
        rows: List[Tuple[str, List[str]]] = []
        group = None
        for key, (label, grp, fmt, _) in RATIO_META.items():
            if key not in r.columns or r[key].isna().all() or fmt == "vnd" and key == "fcf":
                continue
            if grp != group:
                rows.append(("§" + grp.upper(), []))
                group = grp
            suf = {"%": "%", "x": "x", "days": ""}.get(fmt, "")
            d = 0 if fmt in ("days", "vnd") else (1 if fmt == "%" else 2)
            rows.append((label, [_n(v, d, suf) for v in r[key].tolist()]))
        self._period_table(pdf, "Chỉ số", rows, periods)

        # F-score, Z-score, định giá tại giá hiện tại
        pdf.ln(2)
        val = summ.get("valuation") or {}
        pio = summ.get("piotroski") or {}
        alt = summ.get("altman") or {}
        pdf.set_font(font, "B", 8.4)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 5, "Định giá tại giá hiện tại & điểm sức khỏe tài chính", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*TEXT)
        pdf.set_font(font, "", 7.8)
        fin_firm = bool(summ.get("is_bank")) or ((a.get("inv") or {}).get("company") or {}).get("type") in ("bank", "securities", "insurance")
        na_fin = "Không áp dụng (DN tài chính)"
        items = [
            ("P/E (EPS TTM)", _n(val.get("pe"), 1, "x")), ("P/B", _n(val.get("pb"), 2, "x")),
            ("P/S", _n(val.get("ps"), 2, "x")),
            ("EV/EBITDA", na_fin if fin_firm else _n(val.get("ev_ebitda"), 1, "x")),
            ("Tỷ suất cổ tức", _n(val.get("dividend_yield"), 1, "%")),
            ("Vốn hóa (tỷ)", _n((val.get("market_cap") or 0) / 1e9 if val.get("market_cap") else None, 0)),
            ("Piotroski F-score", f"{pio.get('score')}/{pio.get('max')}" if pio.get("score") is not None else "N/A"),
            ("Altman Z''-score", na_fin if fin_firm else
             f"{_n(alt.get('score'), 2)} – {alt.get('zone', '')}" if alt.get("score") is not None else "N/A"),
        ]
        for i, (lbl, v) in enumerate(items):
            pdf.set_fill_color(*LIGHT)
            pdf.cell(45, 5.2, " " + lbl, fill=True)
            pdf.cell(46, 5.2, v + " ", fill=True, align="R")
            if i % 2 == 1:          # 2 cặp (nhãn, giá trị) mỗi dòng
                pdf.ln(6)
        pdf.ln(2)
        pdf.set_font(font, "", 6.8)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 3.6, "Kỳ năm dùng số liệu cả năm; kỳ quý dùng 4 quý gần nhất (TTM). Tỷ số dòng/số dư dùng bình quân "
                       "đầu–cuối kỳ. F-score theo Piotroski (2000); Z''-score theo Altman (2005) cho thị trường mới nổi, "
                       "không áp dụng cho ngân hàng.", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*TEXT)

    def _render_appendix(self, pdf: EquityReportPDF, data: dict, a: dict):
        font = "VN" if pdf.has_vn else "Helvetica"
        pdf.h2("Phụ lục", new_page=True)
        pdf.h3("A. Giải trình chấm điểm chi tiết từng trụ cột")
        pdf.set_font(font, "", 7.0)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 3.6, "Bảng dưới đây là đúng các thành phần mà hệ thống đã dùng để tính điểm. "
                       "Thành phần thiếu dữ liệu được loại khỏi cả tử số và mẫu số, không bị gán 0.",
                       new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*TEXT)
        pdf.ln(1)

        for title, group_checks in a.get("checks", []):
            if not group_checks:
                continue
            if pdf.get_y() + 10 + 4.4 * min(len(group_checks), 6) > pdf.h - pdf.b_margin:
                pdf.add_page()          # không để tên nhóm nằm lẻ cuối trang
            pdf.set_font(font, "B", 8.6)
            pdf.set_text_color(*NAVY)
            pdf.cell(0, 4.8, title, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TEXT)

            pdf.set_font(font, "B", 7.4)
            pdf.set_fill_color(*SUB_FILL)
            headers = [("Tiêu chí định lượng", 62), ("Giá trị thực tế", 44), ("Đạt", 14), ("Điểm", 20), ("Ghi chú", 42)]
            for h, ww in headers:
                pdf.cell(ww, 4.6, h, fill=True, align="C")
            pdf.ln()

            pdf.set_font(font, "", 7.4)
            for c in group_checks:
                ok = "✓" if c.get("ok") is True else "✗" if c.get("ok") is False else "–"
                pdf.cell(62, 4.4, "  " + c.get("name", ""))
                pdf.cell(44, 4.4, str(c.get("value", "")), align="C")
                c_color = GREEN if c.get("ok") is True else RED if c.get("ok") is False else GREY
                pdf.set_text_color(*c_color)
                pdf.cell(14, 4.4, ok, align="C")
                pdf.set_text_color(*TEXT)
                pts = c.get("pts")
                pdf.cell(20, 4.4, f"{pts}/{c.get('max', 0)}" if pts is not None else f"–/{c.get('max', 0)}", align="C")
                note = str(c.get("note", ""))
                pdf.cell(42, 4.4, note if len(note) <= 30 else note[:28] + "…", align="C",
                         new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)

        # Thuyết minh phương pháp luận
        pdf.h3("B. Phương pháp luận định lượng")
        pdf.set_font(font, "", 7.5)
        rel = a.get("rel_val", {})
        methods = [
            "Điểm cơ hội đầu tư tổng hợp = 25% Kỹ thuật + 20% Động lượng + 25% Cơ bản + 20% Định giá + 10% Quản trị rủi ro. "
            "Nhóm nào thiếu dữ liệu được loại ra và các trọng số còn lại được chuẩn hóa lại; độ phủ dữ liệu được ghi cạnh điểm tổng.",
            ("Khuyến nghị 12 tháng dựa trên 3 yếu tố: Financial Health Score, tổng lợi nhuận kỳ vọng (upside + cổ tức) và đánh giá rủi ro "
             "(chi tiết ở mục Kết luận). Điểm cơ hội tổng hợp chỉ để tham khảo, không quyết định khuyến nghị."
             if a.get("inv") else
             "Khuyến nghị: MUA khi lợi suất kỳ vọng (chênh lệch so với giá trị hợp lý + tỷ suất cổ tức) ≥ 15%, TRUNG LẬP từ −15% đến 15%, "
             "BÁN khi ≤ −15%; kiểm tra chéo bằng điểm tổng hợp. Không định giá được thì dựa trên điểm (MUA ≥ 75, BÁN < 35)."),
            ("Giá mục tiêu 12 tháng = bình quân có trọng số các phương pháp hợp lệ (P/E dự phóng, P/B dự phóng, DCF-FCFF, EV/EBITDA) "
             "theo kịch bản cơ sở; kèm kịch bản Bear/Bull (chi tiết ở mục Định giá)." if a.get("inv") else
             "Giá trị hợp lý = bình quân có trọng số của P/E lịch sử, P/E ngành, P/B lịch sử và P/B theo ROE (chi tiết ở mục Định giá)."),
            "Cắt lỗ gợi ý = Giá hiện tại − 2 × ATR(14). Không có dữ liệu ATR thì không đưa mức cắt lỗ.",
            "Tăng trưởng doanh thu/LNST so với cùng kỳ năm trước (YoY) khi xác định được kỳ báo cáo; nếu không, ghi rõ cơ sở so sánh.",
        ]
        for m in methods:
            pdf.multi_cell(0, 3.8, "•  " + m, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(0.2)

        pdf.h3("C. Nguồn dữ liệu")
        src_rows = [["Giá & khối lượng", "DNSE (gần nhất), vnstock/Vietstock (lịch sử, đã nối chuỗi)", data.get("last_session", "")]]
        fs = a.get("fin_sources")
        if fs is not None and not fs.empty:
            used = sorted({str(x) for x in pd.unique(fs.values.ravel()) if isinstance(x, str)})
            src_rows.append(["Báo cáo tài chính", ", ".join(used), ""])
        src_rows.append(["Chỉ số tài chính", "Tự tính từ BCTC (TTM, bình quân đầu–cuối kỳ)", ""])
        if (data.get("peers") or {}).get("peers"):
            src_rows.append(["So sánh ngành", ", ".join(data["peers"]["peers"][:12]), ""])
        for it in data.get("news_items", [])[:6]:
            src_rows.append(["Tin tức", (it.get("source") or "") + (" – " + it["url"] if it.get("url") else ""), it.get("date", "")])
        pdf.table(["Loại dữ liệu", "Nguồn", "Ngày"], src_rows, [36, 122, 24], aligns=["L", "L", "L"], size=7)
        pdf.h3("D. Tuyên bố miễn trừ trách nhiệm")
        pdf.set_font(font, "", 7.2)
        pdf.set_text_color(*GREY)
        disclaimer = (
            "Dữ liệu thị trường và báo cáo tài chính được tổng hợp tự động từ Vnstock và DNSE. "
            "Báo cáo được lập hoàn toàn tự động bằng thuật toán định lượng phục vụ mục đích nghiên cứu học thuật. "
            "Các mục ghi N/A là do nguồn dữ liệu không cung cấp tại thời điểm tạo báo cáo. "
            "Báo cáo không cấu thành lời mời chào hay khuyến nghị mua/bán bất kỳ chứng khoán nào. "
            "Nhà đầu tư tự chịu trách nhiệm đối với quyết định của mình."
        )
        pdf.multi_cell(0, 3.8, disclaimer, new_x="LMARGIN", new_y="NEXT")

    # ─────────────────────────────────────────────────────────────────────────
    # Tiền xử lý dữ liệu – CHỈ dùng số liệu thật từ kết quả StockService.
    # Thiếu dữ liệu -> None -> hiển thị "N/A"; tuyệt đối không tự sinh số giả định.
    # ─────────────────────────────────────────────────────────────────────────

    _LABELS = {
        "fundamental": {
            "roe": ("ROE", "%"), "revenue_growth": ("Tăng trưởng doanh thu", "%"),
            "margin": ("Biên LN ròng", "%"), "debt": ("Nợ/VCSH", "x"),
            "cashflow": ("Dòng tiền HĐKD (CFO)", "cfo"),
        },
        "valuation": {"pe": ("P/E", "x"), "pb": ("P/B", "x")},
        "technical": {
            "ma_alignment": ("Giá so với SMA20/50/200", None), "rsi": ("RSI(14)", ""),
            "macd": ("MACD histogram", ""), "volume": ("Khối lượng tương đối", "x"),
            "bollinger": ("Vị trí dải Bollinger", None), "adx": ("ADX(14) + hướng DI", ""),
            "money_flow": ("Dòng tiền CMF / MFI / OBV", "mf"),
        },
        "momentum": {
            "short_momentum": ("Động lượng 5–10 phiên", "%"), "medium_momentum": ("Động lượng 20 phiên", "%"),
            "long_momentum": ("Động lượng 60–120 phiên", "%"),
            "relative_strength": ("Mạnh/yếu hơn VN-Index 60p", " đ%"), "rsi_zone": ("Vùng RSI", ""),
        },
        "risk": {
            "volatility": ("Biến động năm hóa", "vol"), "drawdown": ("Sụt giảm tối đa (MDD)", "mdd"),
            "beta": ("Beta so với VN-Index", ""), "debt_equity": ("Nợ/VCSH", "x"),
        },
    }

    def _component_rows(self, group: str, components: Dict[str, Any]) -> List[dict]:
        rows = []
        labels = self._LABELS.get(group, {})
        for key, comp in (components or {}).items():
            if not isinstance(comp, dict):
                continue
            name, fmt = labels.get(key, (key.replace("_", " ").title(), ""))
            pts, mx = comp.get("score"), comp.get("max", 0)
            v = comp.get("value")
            if pts is None:
                value, note, ok = "N/A", "Thiếu dữ liệu", None
            else:
                if fmt == "cfo":
                    cfo = comp.get("cfo")
                    value = _n(cfo / 1e9 if cfo is not None and abs(cfo) > 1e7 else cfo, 0, " tỷ")
                elif fmt == "mf":
                    parts = []
                    if comp.get("cmf") is not None:
                        parts.append(f"CMF {comp['cmf']:+.2f}")
                    if comp.get("mfi") is not None:
                        parts.append(f"MFI {comp['mfi']:.0f}")
                    if comp.get("obv_above_ma20") is not None:
                        parts.append("OBV>MA20" if comp["obv_above_ma20"] else "OBV<MA20")
                    value = " · ".join(parts) or "—"
                elif fmt == "vol":
                    value = _n(comp.get("annualized_vol"), 1, "%")
                elif fmt == "mdd":
                    value = _n(comp.get("max_drawdown_pct"), 1, "%")
                elif fmt is None:
                    value = "—"
                elif fmt == "x":
                    value = _n(v, 2, "x")
                else:
                    value = _n(v, 1, fmt)
                if key == "adx" and comp.get("direction"):
                    value += " ↑" if "Tăng" in comp["direction"] else " ↓"
                note = comp.get("basis") or comp.get("method") or comp.get("note") or ""
                note = (note.replace("YoY (cùng kỳ năm trước)", "YoY cùng kỳ")
                            .replace("So với trung vị ngành", "vs trung vị ngành")
                            .replace("Ngưỡng tuyệt đối thị trường", "Ngưỡng tuyệt đối"))
                ok = (pts / mx >= 0.5) if mx else None
            rows.append({"name": name, "value": value, "ok": ok, "pts": pts, "max": mx, "note": note})
        return rows

    @staticmethod
    def _fin_table(rp: Dict[str, Any], n: int = 6) -> pd.DataFrame:
        """Bảng KQKD theo kỳ từ chuỗi thật (revenue_series / net_profit_series)."""
        rev = rp.get("revenue_series") or []
        periods = rp.get("periods") or [f"Kỳ {i + 1}" for i in range(len(rev))]
        if not rev:
            return pd.DataFrame()
        np_map = dict(zip(rp.get("net_profit_periods") or [], rp.get("net_profit_series") or []))
        rows = []
        for per, r in list(zip(periods, rev))[-n:]:
            npat = np_map.get(per)
            margin = (npat / r * 100) if (npat is not None and r) else None
            rows.append({"period": per, "revenue": r, "npat": npat, "net_margin": margin})
        return pd.DataFrame(rows)

    @staticmethod
    def _level(score: Optional[float]) -> str:
        if score is None:
            return "chưa đủ dữ liệu"
        return "tích cực" if score >= 65 else "trung bình" if score >= 45 else "yếu"

    def _prepare_data(self, analysis: Dict[str, Any]) -> Tuple[dict, dict]:
        symbol = analysis.get("symbol", "UNKNOWN")
        company = analysis.get("company_info", {}) or {}
        name = company.get("company_name", company.get("short_name", company.get("name", symbol)))
        exchange = str(company.get("exchange", "") or "").strip()
        exchange = {"VNINDEX": "HOSE", "HSX": "HOSE", "HNXINDEX": "HNX", "UPCOMINDEX": "UPCOM",
                    "UPCOM": "UPCoM"}.get(exchange.upper(), exchange)       # nguồn đôi khi trả tên chỉ số
        industry = company.get("industry", company.get("sector", ""))

        # ── Giá hiện tại & lịch sử giá (không có thì để None, không tự sinh) ──
        curr_p = analysis.get("current_price") or {}
        p_val = curr_p.get("price")
        tech = analysis.get("technical", {}) or {}
        px_df = tech.get("data") if tech.get("available") and isinstance(tech.get("data"), pd.DataFrame) else None
        if px_df is not None and px_df.empty:
            px_df = None
        if px_df is not None:
            px_df = px_df.copy()
            if p_val is None:
                p_val = float(px_df["close"].iloc[-1])

        # Chuẩn hóa đơn vị giá (quote < 1000 là nghìn đồng trên sàn VN)
        if p_val is not None and 0 < p_val < 1000.0:
            p_val = p_val * 1000.0
        if px_df is not None and px_df["close"].iloc[-1] < 1000.0 and (p_val or 0) >= 1000.0:
            for col in ["open", "high", "low", "close", "SMA_10", "SMA_20", "SMA_50", "SMA_100", "SMA_200",
                        "EMA_12", "EMA_26", "BB_upper", "BB_mid", "BB_lower", "ATR"]:
                if col in px_df.columns:
                    px_df[col] = px_df[col] * 1000.0

        # ── Định giá & giá trị hợp lý ──
        val_sec = analysis.get("valuation", {}) or {}
        val_score_data = val_sec.get("score", {}) if isinstance(val_sec, dict) else {}
        rel_val = val_score_data.get("relative_valuation", {}) if isinstance(val_score_data, dict) else {}
        fv = analysis.get("fair_value") or {"available": False}
        target_p = fv.get("fair_value") if fv.get("available") else None     # giá trị hợp lý tổng hợp nhiều phương pháp
        upside = fv.get("upside") if fv.get("available") else None

        # ── Cắt lỗ = Giá − 2 × ATR (chỉ khi có ATR thật) ──
        stop_p = None
        if px_df is not None and "ATR" in px_df.columns and px_df["ATR"].notna().any() and p_val:
            stop_p = max(0.0, p_val - 2.0 * float(px_df["ATR"].dropna().iloc[-1]))

        # ── Điểm ──
        opp = analysis.get("opportunity_score", {}) or {}
        composite = opp.get("composite") if isinstance(opp.get("composite"), dict) else opp
        total_score = composite.get("score")
        coverage = composite.get("coverage_pct")
        sub_scores = opp.get("sub_scores", {}) if isinstance(opp.get("sub_scores"), dict) else {}

        def _sec_score(sec_name):
            sec = analysis.get(sec_name, {}) or {}
            sc = sec.get("score", {})
            return sc.get("score") if isinstance(sc, dict) else None

        weights = {"technical": 25, "momentum": 20, "fundamental": 25, "valuation": 20, "risk": 10}
        scores_dict = {
            "technical": sub_scores.get("technical", _sec_score("technical")),
            "momentum": sub_scores.get("momentum", _sec_score("momentum")),
            "fundamental": sub_scores.get("fundamental", _sec_score("fundamental")),
            "valuation": sub_scores.get("valuation", _sec_score("valuation")),
            "risk": sub_scores.get("risk"),
        }

        # ── Khuyến nghị: hệ thống chung (định giá → kiểm tra chéo bằng điểm tổng hợp) ──
        trend_name = ((tech.get("signals") or {}).get("trend") or {}).get("name")
        recd = analysis.get("recommendation") or {}
        if not recd.get("rating"):
            from analytics.recommendation import recommend
            recd = recommend(fv, total_score, trend_name)
        rec, rec_color = recd["rating"], tuple(recd["color"])

        # ── Hiệu suất giá (None khi không đủ phiên) ──
        ret_1m = ret_3m = ret_1y = None
        closes_s = px_df["close"].dropna() if px_df is not None else pd.Series(dtype=float)
        if len(closes_s) > 21:
            ret_1m = (closes_s.iloc[-1] / closes_s.iloc[-22] - 1) * 100
        if len(closes_s) > 63:
            ret_3m = (closes_s.iloc[-1] / closes_s.iloc[-64] - 1) * 100
        if len(closes_s) > 200:
            ret_1y = (closes_s.iloc[-1] / closes_s.iloc[0] - 1) * 100

        idx_df, rs6 = analysis.get("index_history"), None
        if px_df is not None:
            if idx_df is None:
                try:
                    from services.stock_service import StockService
                    idx_df = StockService(symbol, days=365).get_index_df()
                except Exception:
                    idx_df = None
            if idx_df is not None and not idx_df.empty and "close" in idx_df.columns:
                i_close = idx_df["close"].dropna()
                if len(i_close) > 120 and len(closes_s) > 120:
                    rs6 = ((closes_s.iloc[-1] / closes_s.iloc[-121] - 1)
                           - (i_close.iloc[-1] / i_close.iloc[-121] - 1)) * 100

        # ── Số liệu cơ bản thật ──
        fund_sec = analysis.get("fundamental", {}) or {}
        metrics = fund_sec.get("metrics", {}) if isinstance(fund_sec, dict) else {}
        rp = metrics.get("revenue_profit", {}) or {}
        rm = metrics.get("return_metrics", {}) or {}
        debt = metrics.get("debt", {}) or {}
        last_roe, last_roa = rm.get("roe"), rm.get("roa")
        last_margin = rp.get("net_margin")
        last_de = debt.get("debt_to_equity")
        rev_g, rev_g_basis = rp.get("revenue_yoy"), rp.get("revenue_growth_basis")
        fin_df = self._fin_table(rp)

        # ── Luận điểm đầu tư (văn bản sinh theo số liệu thật, tự điều chỉnh giọng theo điểm) ──
        rsi_last = None
        if px_df is not None and "RSI" in px_df.columns and px_df["RSI"].notna().any():
            rsi_last = float(px_df["RSI"].dropna().iloc[-1])
        trend = ((tech.get("signals") or {}).get("trend") or {}).get("name")

        def sc(k):
            v = scores_dict.get(k)
            return f"{v:.0f}/100" if v is not None else "N/A"

        # ── Luận điểm đầu tư (viết từ ĐÚNG các con số dùng để định giá & chấm điểm) ──
        comments = []
        inv = analysis.get("investment") if isinstance(analysis.get("investment"), dict) else None
        if inv and fv.get("model") == "12m":
            meth = "; ".join(f"{m['name']} → {m['fair']:,.0f} ({m['weight'] * 100:.0f}%)" for m in fv.get("methods", []))
            if fv.get("available"):
                comments.append(
                    f"Định giá: giá mục tiêu 12 tháng {fv['target_12m']:,.0f} VND/cp ({meth}), upside {fv['upside']:+.1f}% so với "
                    f"thị giá {fv['price']:,.0f}; cộng cổ tức {fv.get('dividend_yield', 0):.1f}% → tổng lợi nhuận kỳ vọng "
                    f"{fv['expected_return']:+.1f}%. Độ tin cậy: {fv.get('confidence', '—').lower()}.")
            else:
                comments.append(f"Định giá: {fv.get('status', 'CHƯA ĐỦ CƠ SỞ ĐỊNH GIÁ')}" + (f" (tham khảo: {meth})" if meth else "") + ".")
            hs = (inv.get("health") or {}).get("score")
            comments.append("Sức khỏe tài chính: " + (f"{hs:.1f}/100 ({inv['health'].get('rating_text', '')})" if hs is not None
                            else "chưa đủ dữ liệu để công bố điểm") + f"; mức rủi ro tổng thể: {inv['risk'].get('level', '—')}.")
        elif fv.get("available"):
            meth = "; ".join(f"{m['name']} {m['multiple']:.1f}x → {m['fair']:,.0f}" for m in fv["methods"])
            comments.append(
                f"Định giá: giá trị hợp lý tổng hợp {fv['fair_value']:,.0f} VND/cp ({meth}), chênh lệch "
                f"{fv['upside']:+.1f}% so với thị giá {p_val:,.0f}; cộng tỷ suất cổ tức {fv.get('dividend_yield', 0):.1f}% "
                f"→ lợi suất kỳ vọng {fv['expected_return']:+.1f}%. Độ tin cậy: {fv.get('confidence', '—').lower()}.")
        else:
            comments.append("Định giá: " + " ".join(fv.get("notes") or ["chưa đủ dữ liệu để định giá."]))
        comments += [
            f"Chất lượng doanh nghiệp {self._level(scores_dict['fundamental'])} ({sc('fundamental')}): "
            f"ROE {_n(last_roe, 1, '%')}, ROA {_n(last_roa, 1, '%')}, biên LN ròng {_n(last_margin, 1, '%')}, "
            f"tăng trưởng doanh thu {_n(rev_g, 1, '%')}" + (f" ({rev_g_basis})." if rev_g_basis else "."),
            f"Kỹ thuật {self._level(scores_dict['technical'])} ({sc('technical')}): RSI {_n(rsi_last, 1)}"
            + (f", xu hướng {trend.lower()}" if trend else "")
            + (f"; cắt lỗ gợi ý {stop_p:,.0f} VND (2×ATR)." if stop_p else "."),
            f"Động lượng {self._level(scores_dict['momentum'])} ({sc('momentum')}): hiệu suất 3 tháng {_n(ret_3m, 1, '%')}, "
            f"12 tháng {_n(ret_1y, 1, '%')}" + (f", chênh lệch với VN-Index 6 tháng {rs6:+.1f} điểm %." if rs6 is not None else ".")
            + f" Điểm rủi ro {sc('risk')}.",
            f"Khuyến nghị: {rec}" + (f" (luật {recd['rule']})" if recd.get("rule") else "")
            + (f" ({'tổng LN' if recd.get('rule') else 'lợi suất'} kỳ vọng {recd['expected_return']:+.1f}%)"
               if recd.get("expected_return") is not None else "")
            + (f"; điểm tổng hợp {total_score:.0f}/100" if total_score is not None else "") + ".",
        ]

        # ── Giải trình điểm: lấy ĐÚNG các thành phần đã dùng để chấm ──
        def comps(sec_name):
            sec = analysis.get(sec_name, {}) or {}
            sc_ = sec.get("score", {})
            return sc_.get("components", {}) if isinstance(sc_, dict) else {}

        risk_comps = ((opp.get("risk_detail") or {}).get("components")) or {}
        checks = [
            (f"1. Phân tích cơ bản – {sc('fundamental')}", self._component_rows("fundamental", comps("fundamental"))),
            (f"2. Định giá – {sc('valuation')}", self._component_rows("valuation", comps("valuation"))),
            (f"3. Kỹ thuật – {sc('technical')}", self._component_rows("technical", comps("technical"))),
            (f"4. Động lượng – {sc('momentum')}", self._component_rows("momentum", comps("momentum"))),
            (f"5. Quản trị rủi ro – {sc('risk')}", self._component_rows("risk", risk_comps)),
        ]

        # ── Tin tức thật (nếu StockService/trang PDF đã thu thập) ──
        sent_map = {"positive": "Tích cực", "negative": "Tiêu cực", "neutral": "Trung tính"}
        news_items = []
        for it in (analysis.get("news") or [])[:10]:
            d = it.get("timestamp_dt") or it.get("date") or it.get("published")
            if hasattr(d, "strftime"):
                d = d.strftime("%d/%m")
            news_items.append({
                "source": it.get("source") or it.get("publisher") or "",
                "url": it.get("url") or it.get("link") or "",
                "date": str(d)[:10] if d else "--",
                "sentiment": sent_map.get(it.get("sentiment"), it.get("sentiment") or "Trung tính"),
                "title": it.get("title", ""),
            })

        exported_at = datetime.now()
        last_session = exported_at.strftime("%d/%m/%Y")
        if px_df is not None:
            ts_col = "timestamp" if "timestamp" in px_df.columns else "time" if "time" in px_df.columns else None
            try:
                last_session = pd.to_datetime(px_df[ts_col].iloc[-1] if ts_col else px_df.index[-1]).strftime("%d/%m/%Y")
            except Exception:
                pass
        data_meta = {
            "ticker": symbol,
            "name": name,
            "exchange": exchange,
            "industry": industry,
            "last_session": last_session,
            "fetched_at": exported_at.strftime("%H:%M %d/%m/%Y"),
            "exported_at": exported_at,
            "data_source": "Vnstock / DNSE / BCTC Niêm Yết",
            "as_of": analysis.get("as_of"),
            "peers": analysis.get("peers") or {},
            "news_items": news_items,
        }

        fin_wide = (analysis.get("financials") or {}).get("data")
        fin_summary = analysis.get("financial_summary") or {}
        analysis_dict = {
            "fv": fv, "recd": recd, "trend": trend_name, "rsi_last": rsi_last, "inv": inv,
            "last_roa": last_roa,
            "stock_info": _stock_info(p_val, px_df, fin_summary, analysis, exchange, industry),
            "key_fin": _key_fin_table(fin_wide, fin_summary.get("ratios")),
            "tech_rows": _tech_rows(px_df, idx_df, tech.get("signals") or {}, stop_p, ret_1m, ret_3m, ret_1y, rs6),
            "profile": analysis.get("company_profile") or {},
            "company": company,
            "is_bank": bool(fin_summary.get("is_bank")),
            "price": p_val,
            "target": target_p,
            "upside": upside,
            "stop": stop_p,
            "total": total_score,
            "coverage": coverage,
            "rec": rec,
            "rec_color": rec_color,
            "scores": scores_dict,
            "weights": weights,
            "comments": comments,
            "ret_1m": ret_1m,
            "ret_3m": ret_3m,
            "ret_1y": ret_1y,
            "rs6": rs6,
            "px": px_df,
            "idx": idx_df,
            "fin": fin_df,
            "rel_val": rel_val,
            "last_roe": last_roe,
            "last_margin": last_margin,
            "last_de": last_de,
            "rev_g": rev_g,
            "rev_g_basis": rev_g_basis,
            "checks": checks,
            "fin_wide": (analysis.get("financials") or {}).get("data"),
            "fin_sources": (analysis.get("financials") or {}).get("sources"),
            "fin_summary": analysis.get("financial_summary"),
        }
        if inv and (inv.get("risk") or {}).get("items") is not None:
            analysis_dict["risks"] = [(i["severity"], i["text"], i["source"]) for i in inv["risk"]["items"]]
        else:
            analysis_dict["risks"] = _build_risks(analysis_dict, data_meta, px_df, fin_wide, fin_summary)
        return data_meta, analysis_dict
