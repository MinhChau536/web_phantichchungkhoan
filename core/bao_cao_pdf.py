"""
core/bao_cao_pdf.py – gộp từ 3 module (15/10/2026).

MỤC LỤC
  • reports/cover.py – Trang bìa báo cáo PDF – nền "tảng băng" (assets/report/cover_bg.jpg, đã xóa chữ in sẵn).
      hàm/lớp chính: short_company_name, render_cover
  • reports/excel_export.py – Xuất BCTC chuẩn hóa nhiều năm + chỉ số tài chính + nguồn dữ liệu ra file Excel (.xlsx).
      hàm/lớp chính: statement_table, export_financials
  • reports/pdf_generator.py – PDF Report Generator – Định dạng Báo cáo Phân tích Công ty Chứng khoán Chuyên nghiệp.
      hàm/lớp chính: EquityReportPDF, PDFReportGenerator

Tên trùng giữa các phần đã được đổi (tên cũ → tên mới trong file này):
  pdf_generator.FONT_DIR → FONT_DIR_pdf_generator
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: reports/cover.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Trang bìa báo cáo PDF – nền "tảng băng" (assets/report/cover_bg.jpg, đã xóa chữ in sẵn).

Mọi chữ trên bìa được vẽ lại mỗi lần xuất bằng Pillow:
  • dòng thương hiệu STOCK ANALYTICS + khẩu hiệu
  • "BÁO CÁO PHÂN TÍCH CỔ PHIẾU"
  • MÃ CỔ PHIẾU cỡ lớn (đổi theo mã đang chọn) có hiệu ứng phát sáng
  • tên doanh nghiệp (rút gọn "Công ty Cổ phần" → "CTCP")
  • khung ngày & giờ xuất báo cáo + phiên dữ liệu ở cuối trang
"""


import io
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BG_PATH = ROOT / "assets" / "report" / "cover_bg.jpg"
FONT_DIR = ROOT / "assets" / "fonts"
SCALE = 2                       # vẽ gấp đôi độ phân giải ảnh nền cho chữ sắc nét
_WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


def _font(weight: str, size: float) -> ImageFont.FreeTypeFont:
    for p in (FONT_DIR / f"BeVietnamPro-{weight}.ttf", FONT_DIR / "BeVietnamPro-Bold.ttf"):
        if p.exists():
            return ImageFont.truetype(str(p), int(size * SCALE))
    try:
        import matplotlib
        return ImageFont.truetype(str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans-Bold.ttf"),
                                  int(size * SCALE))
    except Exception:  # pragma: no cover
        return ImageFont.load_default()


def short_company_name(name: str, symbol: str) -> str:
    """'Công ty Cổ phần FPT' → 'CTCP FPT'; 'Ngân hàng TMCP ...' giữ nguyên; viết hoa."""
    n = (name or "").strip() or symbol
    n = re.sub(r"^\s*(công ty|cty)\s+cổ\s+phần\s+", "CTCP ", n, flags=re.I)
    n = re.sub(r"^\s*tổng\s+công\s+ty\s+cổ\s+phần\s+", "TCT CP ", n, flags=re.I)
    n = re.sub(r"\s+", " ", n)
    return n.upper()


def _tracked_width(draw: ImageDraw.ImageDraw, text: str, font, tracking: float) -> float:
    if not text:
        return 0.0
    return sum(draw.textlength(ch, font=font) for ch in text) + tracking * (len(text) - 1)


def _draw_tracked(draw, xy: Tuple[float, float], text: str, font, fill, tracking: float):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill, anchor="ls")
        x += draw.textlength(ch, font=font) + tracking


def _centered_tracked(img: Image.Image, cy: float, text: str, font, fill, tracking: float,
                      max_w: Optional[float] = None, rule: Optional[Tuple[float, tuple]] = None) -> Tuple[float, float]:
    """Vẽ chữ giãn cách căn giữa theo đường chân chữ cy; tự thu nhỏ giãn cách nếu quá rộng.
    rule=(độ dài, màu) → kẻ hai vạch ngang hai bên như mẫu."""
    d = ImageDraw.Draw(img)
    w = _tracked_width(d, text, font, tracking)
    if max_w and w > max_w:
        tracking = max(0.0, tracking - (w - max_w) / max(len(text) - 1, 1))
        w = _tracked_width(d, text, font, tracking)
    x0 = (img.width - w) / 2
    _draw_tracked(d, (x0, cy), text, font, fill, tracking)
    if rule:
        length, color = rule
        asc = font.getbbox("H")[1]
        ly = cy + asc / 2 - 1 * SCALE
        gap = 22 * SCALE
        d.line([(x0 - gap - length, ly), (x0 - gap, ly)], fill=color, width=max(1, int(1.2 * SCALE)))
        d.line([(x0 + w + gap, ly), (x0 + w + gap + length, ly)], fill=color, width=max(1, int(1.2 * SCALE)))
    return x0, w


def _glow_text(base: Image.Image, cx: float, cy: float, text: str, font, max_w: float,
               glow=(80, 170, 255), radius: float = 18) -> None:
    """Chữ lớn tô gradient trắng → xanh băng, có quầng sáng."""
    d0 = ImageDraw.Draw(base)
    while d0.textlength(text, font=font) > max_w and font.size > 40:
        font = font.font_variant(size=int(font.size * 0.94))
    l, t, r, b = d0.textbbox((0, 0), text, font=font, anchor="ls")
    w, h = r - l, b - t
    pad = int(radius * 3 * SCALE)
    mask = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    ImageDraw.Draw(mask).text((pad - l, pad - t), text, font=font, fill=255, anchor="ls")
    ox, oy = int(cx - w / 2 - pad), int(cy + t - pad)

    # quầng sáng (2 lớp)
    for rad, alpha in ((radius * SCALE * 1.8, 150), (radius * SCALE * 0.6, 200)):
        halo = mask.filter(ImageFilter.GaussianBlur(rad)).point(lambda v, a=alpha: min(255, int(v * a / 255 * 1.6)))
        layer = Image.new("RGBA", mask.size, glow + (0,))
        layer.putalpha(halo)
        base.alpha_composite(layer, (ox, oy))

    # thân chữ: gradient dọc
    grad = Image.new("RGBA", mask.size)
    gd = ImageDraw.Draw(grad)
    top, bot = pad, pad + h
    for y in range(mask.size[1]):
        k = min(1.0, max(0.0, (y - top) / max(bot - top, 1)))
        c1, c2, c3 = (255, 255, 255), (214, 238, 255), (150, 205, 255)
        c = tuple(int(c1[i] + (c2[i] - c1[i]) * k * 2) if k < 0.5 else int(c2[i] + (c3[i] - c2[i]) * (k - 0.5) * 2)
                  for i in range(3))
        gd.line([(0, y), (mask.size[0], y)], fill=c + (255,))
    grad.putalpha(mask)
    base.alpha_composite(grad, (ox, oy))


def _rounded_panel(img: Image.Image, box, radius, fill, outline=None, width=1):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    img.alpha_composite(layer)


def _logo_card(img: Image.Image, logo_png: bytes, x: float, y: float, size: float) -> None:
    """Logo doanh nghiệp trong ô trắng bo góc (dán vào khung ngày xuất ở cuối bìa)."""
    card = Image.new("RGBA", (int(size), int(size)), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle((0, 0, size - 1, size - 1), radius=size * 0.2, fill=(255, 255, 255, 255))
    logo = Image.open(io.BytesIO(logo_png)).convert("RGBA")
    inner = int(size * 0.84)
    logo.thumbnail((inner, inner), Image.LANCZOS)
    card.alpha_composite(logo, (int((size - logo.width) / 2), int((size - logo.height) / 2)))
    img.alpha_composite(card, (int(x), int(y)))


def render_cover(symbol: str, company_name: str = "", exported_at: Optional[datetime] = None,
                 session_date: str = "", exchange: str = "", industry: str = "",
                 logo_png: Optional[bytes] = None) -> bytes:
    """Trả về ảnh JPEG của trang bìa (tỉ lệ ≈ A4)."""
    exported_at = exported_at or datetime.now()
    if BG_PATH.exists():
        bg = Image.open(BG_PATH).convert("RGB")
    else:  # dự phòng: nền gradient xanh đậm
        bg = Image.new("RGB", (1055, 1491), (8, 28, 60))
    W, H = bg.width * SCALE, bg.height * SCALE
    img = bg.resize((W, H), Image.LANCZOS).convert("RGBA")
    S = SCALE
    sym = (symbol or "").upper().strip() or "—"

    # 1) Thương hiệu + khẩu hiệu
    _centered_tracked(img, 46 * S, "STOCK ANALYTICS", _font("SemiBold", 15), (235, 243, 255, 235),
                      tracking=7.5 * S, rule=(72 * S, (190, 215, 245, 170)))
    _centered_tracked(img, 74 * S, "KIẾN THỨC SÂU HƠN  ·  QUYẾT ĐỊNH TỐT HƠN", _font("Medium", 10.5),
                      (175, 205, 240, 210), tracking=4.2 * S)

    # 2) Tiêu đề
    title_font = _font("ExtraBold", 54)
    d = ImageDraw.Draw(img)
    while d.textlength("BÁO CÁO PHÂN TÍCH CỔ PHIẾU", font=title_font) > 800 * S:
        title_font = title_font.font_variant(size=int(title_font.size * 0.96))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((W / 2, 162 * S), "BÁO CÁO PHÂN TÍCH CỔ PHIẾU", font=title_font,
                                fill=(10, 30, 70, 160), anchor="ms")
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6 * S)))
    ImageDraw.Draw(img).text((W / 2, 160 * S), "BÁO CÁO PHÂN TÍCH CỔ PHIẾU", font=title_font,
                             fill=(255, 255, 255, 255), anchor="ms")

    # 3) Mã cổ phiếu cỡ lớn
    _glow_text(img, W / 2, 348 * S, sym, _font("Black", 210), max_w=520 * S)

    # 4) Tên doanh nghiệp
    cname = short_company_name(company_name, sym)
    name_font = _font("SemiBold", 24 if len(cname) <= 22 else 19 if len(cname) <= 34 else 15)
    _centered_tracked(img, 389 * S, cname, name_font, (235, 245, 255, 245),
                      tracking=(9 if len(cname) <= 22 else 4) * S, max_w=760 * S,
                      rule=(150 * S if len(cname) <= 14 else 70 * S, (185, 215, 250, 190)))

    # 5) Ngày & giờ xuất báo cáo (khung kính mờ ở cuối trang)
    wd = _WEEKDAYS[exported_at.weekday()]
    line1 = f"NGÀY XUẤT BÁO CÁO   {exported_at.strftime('%d/%m/%Y')}   ·   {exported_at.strftime('%H:%M')}"
    parts = [f"{wd}, {exported_at.strftime('%d/%m/%Y %H:%M:%S')}"]
    if session_date:
        parts.append(f"Dữ liệu phiên {session_date}")
    if exchange:
        parts.append(f"Sàn {exchange}")
    line2 = "   ·   ".join(parts)
    f1, f2 = _font("Bold", 13), _font("Regular", 10.5)
    d = ImageDraw.Draw(img)
    w1 = _tracked_width(d, line1, f1, 2.2 * S)
    w2 = d.textlength(line2, font=f2)
    pw = max(w1, w2) + 70 * S
    lw = 66 * S if logo_png else 0                     # chỗ cho logo bên trái khung (nếu có)
    x0, y0 = (W - pw - lw) / 2, 1404 * S
    _rounded_panel(img, (x0, y0, x0 + pw + lw, y0 + 64 * S), 18 * S, fill=(8, 22, 48, 165),
                   outline=(110, 180, 255, 150), width=max(1, int(1.2 * S)))
    if logo_png:
        try:
            _logo_card(img, logo_png, x0 + 14 * S, y0 + 7 * S, 50 * S)
        except Exception:
            lw = 0
            x0 = (W - pw) / 2
    cx = x0 + lw + pw / 2
    d = ImageDraw.Draw(img)
    _draw_tracked(d, (cx - w1 / 2, y0 + 27 * S), line1, f1, (255, 255, 255, 255), 2.2 * S)
    d.text((cx, y0 + 49 * S), line2, font=f2, fill=(170, 205, 245, 235), anchor="ms")
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90, optimize=True)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: reports/excel_export.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Xuất BCTC chuẩn hóa nhiều năm + chỉ số tài chính + nguồn dữ liệu ra file Excel (.xlsx).

Các sheet:
  KQKD, CDKT, LCTT  – chỉ tiêu × kỳ (tỷ đồng), đúng thứ tự trình bày
  Chi_so            – các chỉ số tính từ BCTC theo nhóm
  Nguon_du_lieu     – nguồn của từng ô (vnstock_vci / vnstock_kbs / vietstock / pdf)
  Bang_goc_<nguồn>  – bảng thô gốc của từng nguồn (nếu có), để đối chiếu
"""


import io
from typing import Any, Dict, Optional

import pandas as pd

from core.phan_tich_co_ban import RATIO_META
from core.phan_tich_co_ban import key_to_label
from core.du_lieu import ITEMS_BY_KEY, PER_UNIT_KEYS, STATEMENT_ITEMS

_SHEETS = {"is": "KQKD", "bs": "CDKT", "cf": "LCTT"}


def statement_table(data: pd.DataFrame, statement: str, unit: float = 1e9) -> pd.DataFrame:
    """Bảng trình bày: dòng = chỉ tiêu (nhãn tiếng Việt), cột = kỳ; tiền tệ chia theo `unit`."""
    keys = [k for k in STATEMENT_ITEMS.get(statement, []) if k in data.columns]
    if not keys:
        return pd.DataFrame()
    rows = []
    for k in keys:
        series = data[k]
        if series.isna().all():
            continue
        scale = 1.0 if k in PER_UNIT_KEYS else unit
        row = {"Chỉ tiêu": ITEMS_BY_KEY[k].label_vi}
        for pk, v in series.items():
            row[key_to_label(pk)] = (v / scale) if pd.notna(v) else None
        rows.append(row)
    return pd.DataFrame(rows)


def export_financials(symbol: str, financials: Dict[str, Any], summary: Optional[Dict[str, Any]] = None,
                      unit: float = 1e9) -> bytes:
    data: pd.DataFrame = financials.get("data", pd.DataFrame())
    sources: pd.DataFrame = financials.get("sources", pd.DataFrame())
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        info = pd.DataFrame({
            "Thông tin": ["Mã", "Kỳ", "Đơn vị tiền tệ", "Thời điểm lấy dữ liệu", "Ghi chú"],
            "Giá trị": [symbol, "Năm" if financials.get("period") == "year" else "Quý",
                        "Tỷ đồng (trừ EPS, BVPS: đồng/cp; số CP: cổ phiếu)", financials.get("fetched_at", ""),
                        "Số liệu chuẩn hóa từ nhiều nguồn; xem sheet Nguon_du_lieu để biết nguồn từng ô."],
        })
        info.to_excel(xw, sheet_name="Thong_tin", index=False)
        for st, name in _SHEETS.items():
            t = statement_table(data, st, unit)
            if not t.empty:
                t.to_excel(xw, sheet_name=name, index=False)
        if summary and summary.get("ratios") is not None and not summary["ratios"].empty:
            r = summary["ratios"]
            rows = []
            for key, (label, group, fmt, _) in RATIO_META.items():
                if key not in r.columns:
                    continue
                scale = unit if fmt == "vnd" and key == "fcf" else 1.0
                row = {"Nhóm": group, "Chỉ số": label, "Đơn vị": {"%": "%", "x": "lần", "days": "ngày",
                                                                     "vnd": "tỷ đồng" if key == "fcf" else "đồng"}.get(fmt, "")}
                for pk, v in r[key].items():
                    row[key_to_label(pk)] = (v / scale) if pd.notna(v) else None
                rows.append(row)
            pd.DataFrame(rows).to_excel(xw, sheet_name="Chi_so", index=False)
        if sources is not None and not sources.empty:
            s = sources.copy()
            s.index = [key_to_label(k) for k in s.index]
            s.columns = [ITEMS_BY_KEY[c].label_vi if c in ITEMS_BY_KEY else c for c in s.columns]
            s.T.to_excel(xw, sheet_name="Nguon_du_lieu")
        for st, by_src in (financials.get("raw") or {}).items():
            for src, raw in by_src.items():
                name = f"Goc_{_SHEETS.get({'income_statement': 'is', 'balance_sheet': 'bs', 'cash_flow': 'cf'}.get(st, ''), st)}_{src}"[:31]
                try:
                    from giao_dien.chung import unique_columns
                    unique_columns(raw).to_excel(xw, sheet_name=name, index=False)
                except Exception:
                    pass
        for ws in xw.book.worksheets:
            ws.freeze_panes = "B2"
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in col[:50])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)
                for c in col[1:]:
                    if isinstance(c.value, float):
                        c.number_format = "#,##0.00"
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: reports/pdf_generator.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
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

from core.phan_tich_co_ban import key_to_label
from core.cau_hinh import settings

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
LINK = (29, 78, 216)       # liên kết bấm được (tin tức, nguồn)
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
FONT_DIR_pdf_generator = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def _brand_fonts() -> Dict[str, str]:
    """Be Vietnam Pro (assets/fonts, giấy phép OFL) – thiết kế riêng cho tiếng Việt."""
    files = {"": "Regular", "B": "Bold", "X": "ExtraBold", "M": "SemiBold"}
    out = {k: str(FONT_DIR_pdf_generator / f"BeVietnamPro-{v}.ttf") for k, v in files.items()}
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


def _hex_rgb(h: str) -> Tuple[int, int, int]:
    h = str(h or "#64748b").lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _score_grade(total) -> Optional[str]:
    """Xếp loại điểm cơ hội theo SCORE_CATEGORIES (Cơ hội nổi bật … Cơ hội rất thấp)."""
    if total is None:
        return None
    from core.cau_hinh import SCORE_CATEGORIES
    t = round(float(total))
    for (lo, hi), (lab, _c, _i) in SCORE_CATEGORIES.items():
        if lo <= t <= hi:
            return lab
    return None


def _score_reco_note(a: dict) -> Optional[str]:
    """Góp ý GK (Vấn đề 1): giải thích quan hệ giữa ĐIỂM CƠ HỘI (sàng lọc nhanh 5 trụ cột) và KHUYẾN NGHỊ 12 THÁNG
    (định giá + sức khỏe tài chính + rủi ro) để người đọc không thấy hai kết luận "mâu thuẫn"."""
    total, recd = a.get("total"), a.get("recd") or {}
    rating = recd.get("rating") or a.get("rec")
    if total is None or not rating:
        return None
    grade = (_score_grade(total) or "").lower()
    ml = a.get("ml")
    if ml:
        return (f"Điểm 5 trụ cột {total:.0f}/100 ({grade}) là điểm SÀNG LỌC THAM KHẢO (gồm cả kỹ thuật và động lượng ngắn hạn), "
                f"không phải khuyến nghị. Khuyến nghị duy nhất của báo cáo là {ml['label']} theo khung đa lớp: điểm cơ bản "
                f"F = {_n(ml.get('F'), 0)} (Chất lượng {_n(ml.get('Q'), 0)}, Định giá {_n(ml.get('V'), 0)}, Tăng trưởng "
                f"{_n(ml.get('G'), 0)}, trừ rủi ro {_n(ml.get('penalty'), 0)}) và điểm so với thị trường R = {_n(ml.get('R'), 0)}.")
    head = f"Điểm cơ hội tổng thể {total:.0f}/100 ({grade})"
    basis = ("Điểm cơ hội là điểm sàng lọc nhanh (gồm cả kỹ thuật và động lượng ngắn hạn); khuyến nghị 12 tháng dựa trên "
             "định giá, sức khỏe tài chính và rủi ro – hai thước đo trả lời hai câu hỏi khác nhau.")
    if rating == "CHƯA ĐỦ CƠ SỞ":
        why = "độ tin cậy định giá chưa đạt ngưỡng" if (a.get("fv") or {}).get("methods") else "chưa có kết quả định giá đáng tin cậy"
        tail = (" Điểm cơ hội thấp → nghiêng THẬN TRỌNG: nhà đầu tư nên theo dõi thêm, chưa giải ngân."
                if total < 50 else " Nhà đầu tư nên chờ thêm dữ liệu (BCTC kỳ tới) trước khi ra quyết định.")
        return (f"Mặc dù {head[0].lower() + head[1:]}, khuyến nghị 12 tháng là CHƯA ĐỦ CƠ SỞ vì {why}. " + basis + tail)
    buyish = str(rating).startswith("MUA")
    sellish = str(rating).startswith("BÁN")
    if (buyish and total < 50) or (sellish and total >= 65):
        return (f"{head} khác chiều với khuyến nghị 12 tháng {rating}. " + basis
                + " Khuyến nghị 12 tháng là kết luận chính; điểm cơ hội thấp/cao chủ yếu ảnh hưởng THỜI ĐIỂM giải ngân.")
    return f"{head}, cùng chiều với khuyến nghị 12 tháng {rating}. " + basis


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
    rows: List[Tuple[str, str]] = [("Sàn niêm yết", _exchange_name(exchange) or "N/A"), ("Ngành", industry or "N/A")]
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
             (f"P/E (EPS {val.get('eps_basis') or 'TTM'})", _n(val.get("pe"), 2, "x")), ("P/B", _n(val.get("pb"), 2, "x")),
             (f"EPS {val.get('eps_basis') or 'TTM'} (đ/cp)", _n(val.get("eps_ttm"))), ("BVPS (đ/cp)", _n(val.get("bvps"))),
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
             ("EPS điều chỉnh (đ/cp)" if "eps_reported" in r.columns else "EPS (đ/cp)",
              [_n(v) for v in r.get("eps", pd.Series(index=w.index, dtype=float))])]
    return {"periods": periods, "rows": rows, "bank": bank}


def _tech_rows(px, idx, signals, stop_p, r1m, r3m, r1y, rs6, wait: bool = False) -> List[Tuple[str, str, str]]:
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
    rows.append(("Cắt lỗ gợi ý (giá − 2×ATR)", "Chưa áp dụng" if wait else _n(stop_p),
                 "đang CHỜ ĐIỂM MUA – chỉ đặt cắt lỗ khi đã mua" if wait else ""))
    rows.append(("Lợi suất 1T / 3T / 12T", f"{_n(r1m, 1, '%', True)} / {_n(r3m, 1, '%', True)} / {_n(r1y, 1, '%', True)}", ""))
    rows.append(("So với VN-Index 6 tháng", _n(rs6, 1, " điểm %", True), "" if rs6 is None else ("Mạnh hơn thị trường" if rs6 > 0 else "Yếu hơn thị trường")))
    trend = (signals.get("trend") or {}).get("name")
    if trend:
        rows.insert(1, ("Xu hướng tổng hợp", trend, "; ".join((signals.get("trend") or {}).get("criteria", [])[:3])))
    return rows


from core.khuyen_nghi import SECTOR_WATCH as _SECTOR_WATCH


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
        c1y = px["close"].astype(float).tail(250)
        mdd = float(((c1y / c1y.cummax()) - 1).min() * 100)
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


def _generate_price_chart(px: pd.DataFrame, ticker: str, target_price: Optional[float], stop_loss: Optional[float],
                          window_days: int = 365) -> io.BytesIO:
    """Biểu đồ giá 12 tháng + MA50 + MA200 + Giá mục tiêu + Cắt lỗ + RSI(14).
    Chỉ báo (MA200…) tính trên TOÀN BỘ lịch sử đã tải rồi mới cắt khung hiển thị → MA200 có từ đầu khung."""
    if px is None or px.empty:
        fig, ax = plt.subplots(figsize=(9.2, 2.2))
        ax.text(0.5, 0.5, "Không có dữ liệu giá lịch sử – không vẽ biểu đồ kỹ thuật",
                ha="center", va="center", color="#6e6e6e", fontsize=9)
        ax.axis("off")
        return _fig_to_png(fig)
    has_vol = "volume" in px.columns and pd.to_numeric(px["volume"], errors="coerce").fillna(0).gt(0).any()
    if has_vol:
        fig, (ax1, axv, ax2) = plt.subplots(
            3, 1, figsize=(9.2, 5.3), sharex=True,
            gridspec_kw={"height_ratios": [3.2, 1.0, 1.0], "hspace": 0.10}
        )
    else:
        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(9.2, 4.4), sharex=True,
            gridspec_kw={"height_ratios": [3.2, 1.0], "hspace": 0.08}
        )
        axv = None

    time_series = px["timestamp"] if "timestamp" in px.columns else px["time"] if "time" in px.columns else px.index
    times_all = pd.to_datetime(pd.Series(np.asarray(time_series)))
    keep = (times_all >= times_all.max() - pd.Timedelta(days=window_days)).to_numpy()
    px_full = px.reset_index(drop=True)
    keep = pd.Series(keep)
    px = px_full.loc[keep]
    times = times_all[keep]
    closes = px["close"].values

    if {"high", "low"} <= set(px.columns):              # biên độ cao–thấp trong phiên (để thấy đỉnh/đáy 52 tuần thật)
        ax1.fill_between(times, px["low"].values, px["high"].values, color="#0e2a52", alpha=0.10, lw=0, label="Cao–thấp phiên")
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

    ax1.set_title(f"{ticker} – Diễn biến giá {window_days // 30} tháng & Hệ thống chỉ báo kỹ thuật", fontsize=10, fontweight="bold",
                  color="#0e2a52", loc="left", pad=16)
    # trục giá: đủ chỗ cho đỉnh/đáy thật, giá mục tiêu, cắt lỗ; chú thích đặt dưới khung giá để không che đỉnh
    hi = float(np.nanmax(px["high"].values if "high" in px.columns else closes))
    lo = float(np.nanmin(px["low"].values if "low" in px.columns else closes))
    for col in (ma50_col, ma200_col):                    # đường MA không bị cắt mất ở mép khung
        if col and px[col].notna().any():
            hi, lo = max(hi, float(np.nanmax(px[col].values))), min(lo, float(np.nanmin(px[col].values)))
    for lv in (target_price, stop_loss):
        if lv and lv > 0:
            hi, lo = max(hi, lv), min(lo, lv)
    pad = (hi - lo) * 0.06 or hi * 0.03
    ax1.set_ylim(lo - pad, hi + pad)
    ax1.legend(fontsize=6.6, loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=7, frameon=False, borderaxespad=0.2,
               handlelength=1.6, columnspacing=1.0)
    ax1.grid(color="#e2e8f0", linestyle="--", linewidth=0.6, alpha=0.8)
    ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x:,.0f}"))

    # Khối lượng: cột xanh = phiên tăng, đỏ = phiên giảm; đường KL bình quân 20 phiên (tính trên toàn bộ lịch sử đã tải)
    if axv is not None:
        vol_all = pd.to_numeric(px_full["volume"], errors="coerce") if "volume" in px_full.columns else None
        vol = pd.to_numeric(px["volume"], errors="coerce").fillna(0).values
        up = np.r_[True, np.diff(closes) >= 0]
        if len(closes) and vol_all is not None:
            prev = pd.to_numeric(px_full["close"], errors="coerce").shift(1).loc[keep].values
            up = np.where(np.isnan(prev), up, closes >= prev)
        span = (times.max() - times.min()).days if len(times) > 1 else 1
        bw = max(0.6, 0.7 * span / max(len(times), 1))
        axv.bar(times, vol, width=bw, color=np.where(up, "#16a34a", "#dc2626"), alpha=0.55, lw=0)
        if vol_all is not None:
            axv.plot(times, vol_all.rolling(20, min_periods=5).mean().loc[keep].values, color="#0e2a52", lw=0.9,
                     label="KL TB 20 phiên")
            axv.legend(fontsize=6.2, loc="upper left", frameon=False, borderaxespad=0.1)
        axv.set_ylabel("KL (triệu cp)", fontsize=7.0, color="#4a5568")
        axv.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1e6:,.0f}" if x >= 1e6 else
                                                                      f"{x / 1e6:,.1f}"))
        axv.set_ylim(0, float(np.nanpercentile(vol, 99)) * 1.15 if np.nanmax(vol) > 0 else 1)
        axv.grid(axis="y", color="#e2e8f0", linestyle="--", linewidth=0.5, alpha=0.8)

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

    for ax in (ax1, ax2) + ((axv,) if axv is not None else ()):
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


def _style_ax(ax, grid_axis: str = "y") -> None:
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.tick_params(colors="#4a5568", labelsize=7)
    ax.grid(axis=grid_axis, color="#e2e8f0", linestyle="--", linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)


def _generate_peer_chart(ticker: str, peers: Dict[str, Any], me: Dict[str, Optional[float]]) -> Optional[io.BytesIO]:
    """So sánh ngành: mỗi chỉ tiêu 1 ô – thanh từng doanh nghiệp cùng nhóm (xám), mã đang phân tích (xanh đậm), đường
    trung vị ngành (vàng). Thiếu số liệu từng mã (bộ nhớ tạm cũ) → chỉ vẽ mã đang phân tích so với trung vị."""
    metrics = [("roe", "ROE (%)"), ("net_margin", "Biên LN ròng (%)"), ("pe", "P/E (lần)"), ("pb", "P/B (lần)")]
    by_peer = peers.get("by_peer") or {}
    panels = []
    for key, label in metrics:
        vals = {t: v.get(key) for t, v in by_peer.items() if v.get(key) is not None}
        if me.get(key) is not None:
            vals[ticker] = me[key]
        med = peers.get(key)
        if me.get(key) is None or (len(vals) < 2 and med is None):
            continue
        if len(vals) < 2:
            vals = {ticker: me[key], "Trung vị": med}
        panels.append((key, label, vals, med))
    if not panels:
        return None
    n = max(len(panels), 3)                     # luôn chia ≥ 3 ô để 1–2 chỉ tiêu không bị kéo giãn hết chiều ngang
    fig, axes = plt.subplots(1, n, figsize=(9.2, 0.9 + 0.21 * max(len(p[2]) for p in panels)),
                             gridspec_kw={"wspace": 0.42})
    axes = np.atleast_1d(axes)
    for ax in axes[len(panels):]:
        ax.axis("off")
    for ax, (key, label, vals, med) in zip(axes, panels):
        items = sorted(vals.items(), key=lambda kv: kv[1])
        names = [k for k, _ in items]
        xs = [v for _, v in items]
        cols = ["#0e2a52" if k == ticker else "#e08a00" if k == "Trung vị" else "#cbd5e1" for k in names]
        ax.barh(names, xs, color=cols, height=0.62)
        if med is not None and "Trung vị" not in vals:
            ax.axvline(med, color="#e08a00", lw=1.2, ls="--")
            ax.text(med, len(names) - 0.4, f" TV {med:,.1f}", color="#b07008", fontsize=6.2, va="bottom")
        for y_, (k, v) in enumerate(items):
            if k == ticker:
                ax.text(v, y_, f" {v:,.1f}", va="center", fontsize=6.6, color="#0e2a52", fontweight="bold")
        ax.set_title(label, fontsize=8, fontweight="bold", color="#0e2a52", loc="left")
        ax.tick_params(axis="y", labelsize=6.6)
        for lbl in ax.get_yticklabels():
            if lbl.get_text() == ticker:
                lbl.set_fontweight("bold")
                lbl.set_color("#0e2a52")
        lo = min(0.0, min(xs))
        ax.set_xlim(lo, max(xs + ([med] if med is not None else [])) * 1.25 if max(xs) > 0 else 1)
        _style_ax(ax, "x")
    return _fig_to_png(fig)


def _generate_ratio_trend_chart(ratios: Optional[pd.DataFrame], wide: Optional[pd.DataFrame],
                                is_bank: bool = False) -> Optional[io.BytesIO]:
    """Trái: biên lợi nhuận & ROE theo năm (%). Phải: dòng tiền theo năm – CFO, capex, cổ tức đã trả (cột) và FCF (đường)."""
    _kl = key_to_label
    if ratios is None or ratios.empty:
        return None
    r = ratios[[int(k) % 10 == 0 for k in ratios.index]].sort_index().iloc[-6:]
    lines = [("gross_margin", "Biên gộp", "#0e2a52"), ("ebitda_margin", "Biên EBITDA", "#2a9d8f"),
             ("net_margin", "Biên ròng", "#e08a00"), ("roe", "ROE", "#be1e2d"), ("roa", "ROA", "#7c3aed")]
    lines = [t for t in lines if t[0] in r.columns and r[t[0]].notna().sum() >= 2]
    if is_bank:
        lines = [t for t in lines if t[0] in ("roe", "roa", "net_margin")]
    if not lines:
        return None
    cf = None
    if not is_bank and wide is not None and not wide.empty and {"cfo", "capex"} <= set(wide.columns):
        w = wide[[int(k) % 10 == 0 for k in wide.index]].sort_index().iloc[-6:]
        if w["cfo"].notna().sum() >= 2:
            cf = w
    fig, axes = plt.subplots(1, 2 if cf is not None else 1, figsize=(9.2, 2.7), gridspec_kw={"wspace": 0.22})
    axes = np.atleast_1d(axes)
    ax = axes[0]
    years = [_kl(k) for k in r.index]
    for key, lbl, col in lines:
        y = r[key].astype(float).values
        ax.plot(years, y, marker="o", ms=3, lw=1.4, color=col, label=lbl)
        last = pd.Series(y).dropna()
        if len(last):
            ax.annotate(f"{last.iloc[-1]:.1f}", (len(years) - 1, last.iloc[-1]), xytext=(4, 0), textcoords="offset points",
                        fontsize=6.3, color=col, va="center")
    ax.set_title("Khả năng sinh lời (%)", fontsize=8.5, fontweight="bold", color="#0e2a52", loc="left")
    ax.legend(fontsize=6.4, frameon=False, ncol=len(lines), loc="lower left", bbox_to_anchor=(0, -0.32))
    _style_ax(ax)
    if cf is not None:
        ax = axes[1]
        yrs = [_kl(k) for k in cf.index]
        x = np.arange(len(yrs))
        cfo = cf["cfo"].astype(float).values / 1e9
        capex = -np.abs(cf["capex"].astype(float).values) / 1e9
        div = (-np.abs(cf["dividends_paid"].astype(float).values) / 1e9) if "dividends_paid" in cf.columns else None
        wbar = 0.27 if div is not None else 0.38
        ax.bar(x - wbar, cfo, width=wbar, color="#0e2a52", label="CFO")
        ax.bar(x, capex, width=wbar, color="#94a3b8", label="Capex")
        if div is not None:
            ax.bar(x + wbar, div, width=wbar, color="#e08a00", label="Cổ tức đã trả")
        fcf = cfo + capex
        ax.plot(x, fcf, color="#16a34a", marker="D", ms=3, lw=1.3, label="FCF = CFO − capex")
        ax.axhline(0, color="#94a3b8", lw=0.7)
        ax.set_xticks(x)
        ax.set_xticklabels(yrs, fontsize=7)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"{v:,.0f}"))
        ax.set_title("Dòng tiền (tỷ đồng)", fontsize=8.5, fontweight="bold", color="#0e2a52", loc="left")
        ax.legend(fontsize=6.4, frameon=False, ncol=4, loc="lower left", bbox_to_anchor=(0, -0.32))
        _style_ax(ax)
    return _fig_to_png(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Lớp Báo Cáo FPDF A4 Chuẩn Tổ Chức
# ─────────────────────────────────────────────────────────────────────────────

PAGE_BG = Path(__file__).resolve().parent.parent / "assets" / "report" / "page_bg.jpg"
FONT_SCALE = 1.10          # phóng chữ nội dung (≤ 11pt) cho dễ đọc; tiêu đề lớn giữ nguyên
LINE_SCALE = 1.06          # giãn dòng tương ứng cho đoạn văn nhiều dòng
PAGE_TOP = 32.0            # nội dung bắt đầu dưới dải tiêu đề của ảnh nền (dải xanh cao ~28 mm)
PAGE_BOTTOM = 18.0         # chừa chỗ cho chân trang (đường kẻ ~283 mm, dải xanh từ ~292 mm)



def _ink(rgb) -> tuple:
    """Màu chữ tương phản (tối/trắng) trên nền rgb – cùng quy tắc với app (giao_dien/chung.py)."""
    from giao_dien.chung import text_on
    try:
        hx = "#%02x%02x%02x" % tuple(int(x) for x in rgb[:3])
    except Exception:
        return (255, 255, 255)
    return (15, 23, 42) if text_on(hx) != "#ffffff" else (255, 255, 255)


def _exchange_name(v) -> str:
    """Mã nhóm chỉ số của nguồn (VNINDEX, HNXIndex, UpcomIndex…) → tên sàn (HOSE, HNX, UPCoM)."""
    t = str(v or "").strip()
    u = t.upper().replace(" ", "")
    if u in ("VNINDEX", "HSX", "HOSE", "VN30"):
        return "HOSE"
    if u.startswith("HNX"):
        return "HNX"
    if u.startswith("UPCOM"):
        return "UPCoM"
    return t

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
            self.cell(90, 6, "STOCK ANALYTICS")
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
            self.cell(90, 5, "STOCK ANALYTICS", align="L")
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

    def h2(self, txt: str, min_space: float = 55, new_page: bool = False):
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

    def h3(self, txt: str, min_space: float = 32):
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
              colors: Optional[List[List[Optional[tuple]]]] = None, bold_first: bool = False,
              links: Optional[List[List[Optional[str]]]] = None):
        """Bảng chung: đầu bảng navy chữ vàng, dòng xen kẽ, tự lặp đầu bảng khi sang trang.
        colors[i][j] = màu chữ riêng cho ô (i, j); links[i][j] = URL → ô bấm được (chữ xanh, gạch chân, mở trang web)."""
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
                li = links[i] if links and i < len(links) else None
                url = li[j] if li and j < len(li) and li[j] else None
                url = url if url and str(url).lower().startswith(("http://", "https://")) else None
                self.set_text_color(*(LINK if url else col))
                self.set_font(f, ("B" if (bold_first and j == 0) else "") + ("U" if url else ""), size)
                txt = "" if v is None else str(v)
                max_chars = int(w / (size * FONT_SCALE * 0.19)) if w else 99
                if len(txt) > max_chars:
                    txt = txt[: max_chars - 1] + "…"
                self.cell(w, h, " " + txt + " ", align=a, fill=True, link=url or "")
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
        "personal": "Báo cáo cá nhân hóa (theo hồ sơ nhà đầu tư)",
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
        sections = [x for x in sections if x != "trading"]          # mục tín hiệu giao dịch (chiến lược nhóm / bot) đã bỏ khỏi app
        personal = analysis.get("personal")
        if personal and "personal" not in sections:
            sections = list(sections) + ["personal"]      # có hồ sơ nhà đầu tư → luôn kèm mục cá nhân hóa
        if not personal:
            sections = [x for x in sections if x != "personal"]
        sections = [x for x in self.DEFAULT_SECTIONS if x in sections] or ["summary"]
        data, a = self._prepare_data(analysis)
        a["personal"] = personal
        a["trading"] = None
        # Khung khuyến nghị đa lớp (15/10/2026): MỘT nhãn duy nhất
        a["ml"] = (a.get("inv") or {}).get("multilayer") or None

        pdf = EquityReportPDF(data)
        pdf.alias_nb_pages()
        if cover:
            self._render_cover(pdf, data)
        has_toc = toc and len(sections) > 1
        if has_toc:
            pdf.add_page()
            pdf.insert_toc_placeholder(self._render_toc, pages=1)   # fpdf2 tự sang trang mới sau chỗ dành cho mục lục
        renderers = {
            "summary": self._render_summary, "personal": self._render_personal, "profile": self._render_profile, "business": self._render_business,
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
            from core.bao_cao_pdf import render_cover
            logo_png = None
            try:                                      # logo doanh nghiệp (nếu tải được) – lỗi thì bìa vẫn như cũ
                from giao_dien.chung import logo_path
                lp = logo_path(data["ticker"])
                logo_png = lp.read_bytes() if lp else None
            except Exception:
                logo_png = None
            img = render_cover(data["ticker"], data.get("name", ""), data.get("exported_at"),
                               data.get("last_session", ""), data.get("exchange", ""), logo_png=logo_png)
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
        ml = a.get("ml")
        box_label = ml["label"] if ml else a["rec"]
        box_col = _hex_rgb(ml["hex"]) if ml else a["rec_color"]
        # Độ tin cậy định giá thấp → giá mục tiêu không dùng để khuyến nghị, nhưng vẫn in số THAM KHẢO (chữ xám + dấu *)
        # thay vì N/A, khớp với mục Định giá (14/10/2026).
        _fv = a.get("fv") or {}
        ref_tgt = a["target"] is None and _fv.get("methods") and _fv.get("target_12m")
        # Góp ý GK (Vấn đề 2): độ tin cậy thấp → KHÔNG đưa giá mục tiêu lên ô nổi bật; số tham khảo chỉ ghi ở chú thích.
        tgt_txt = _n(a["target"]) if a["target"] else ("Chưa đưa ra" if ref_tgt else "N/A")
        up_txt = _n(a["upside"], 1, "%", sign=True) if a["upside"] is not None else ("—" if ref_tgt else "N/A")
        tgt_col = GREY if ref_tgt else GOLD_DK
        pdf.set_fill_color(*box_col)
        pdf.rect(14, y0, 58, 27, "F", round_corners=True, corner_radius=2.6)
        pdf.set_xy(14, y0 + 2.6)
        pdf.set_text_color(*_ink(box_col))
        pdf.set_font(pdf.font_name, "", 7.5)
        pdf.cell(58, 3.8, "KHUYẾN NGHỊ", align="C", new_x="LEFT", new_y="NEXT")
        pdf.set_font(pdf.big_font, "B", 15 if len(box_label) <= 10 else 11 if len(box_label) <= 18 else 9)
        pdf.cell(58, 9 if a.get("inv") else 10, box_label, align="C", new_x="LEFT", new_y="NEXT")
        pdf.set_font(pdf.font_name, "", 7.6)
        er = recd.get("expected_return")
        if ml:
            vr = ml.get("valuation_range") or {}
            pdf.set_font(pdf.font_name, "", 6.9)
            pdf.cell(58, 3.8, f"Cơ bản F {_n(ml.get('F'), 0)} · So với thị trường R {_n(ml.get('R'), 0)}", align="C",
                     new_x="LEFT", new_y="NEXT")
            pdf.cell(58, 3.8, f"Độ tin cậy khuyến nghị: {ml['reliability']['level'].lower()}", align="C")
            rng = (f"{vr['low'] / 1000:,.1f}–{vr['high'] / 1000:,.1f}k" if vr.get("available") else "—")
            boxes = [("Giá hiện tại", _n(a["price"])), ("Giá mục tiêu", tgt_txt, tgt_col), ("Khoảng định giá", rng, NAVY),
                     ("Mức rủi ro", str(((a.get("inv") or {}).get("risk") or {}).get("level", "—")))]
        elif a.get("inv"):
            hs = (a["inv"].get("health") or {}).get("score")
            pdf.set_font(pdf.font_name, "", 6.9)
            pdf.cell(58, 3.8, f"Tổng LN kỳ vọng {er:+.1f}%" if er is not None else "Chưa đủ cơ sở định giá",
                     align="C", new_x="LEFT", new_y="NEXT")
            if hs is not None:
                pdf.cell(58, 3.8, f"Sức khỏe tài chính {hs:.0f}/100", align="C")
            boxes = [("Giá hiện tại", _n(a["price"])), ("Giá mục tiêu", tgt_txt, tgt_col),
                     ("Upside", up_txt, tgt_col),
                     ("Mức rủi ro", str((a["inv"].get("risk") or {}).get("level", "—")))]
        else:
            pdf.cell(58, 4.2, (f"Lợi suất kỳ vọng {er:+.1f}%" if er is not None else "Chưa đủ dữ liệu định giá")
                     + (f" · điểm {a['total']:.0f}/100" if a["total"] is not None else ""), align="C")
            boxes = [("Giá hiện tại", _n(a["price"])), ("Giá trị hợp lý", _n(a["target"])),
                     ("Chênh lệch", _n(a["upside"], 1, "%", sign=True) if a["upside"] is not None else "N/A"),
                     ("Tỷ suất cổ tức", _n((a["fv"] or {}).get("dividend_yield"), 1, "%"))]
        bx_x = 75.0
        for box in boxes:
            lbl, val = box[0], box[1]
            pdf.card(bx_x, y0, 29, 27)
            pdf.set_xy(bx_x, y0 + 4.5)
            pdf.set_text_color(*GREY)
            pdf.set_font(pdf.font_name, "", 7.2)
            pdf.cell(29, 3.8, lbl, align="C")
            pdf.set_xy(bx_x, y0 + 10.5)
            pdf.set_text_color(*(box[2] if len(box) > 2 else GOLD_DK))
            pdf.set_font(pdf.big_font, "B", 12.5 if len(val) <= 8 else 10.5)
            pdf.cell(29, 9, val, align="C")
            bx_x += 31.0
        pdf.set_text_color(*TEXT)
        pdf.set_y(y0 + 31)
        if ref_tgt:
            pdf.set_font(pdf.font_name, "", 6.8)
            pdf.set_text_color(*GREY)
            pdf.multi_cell(182, 3.6, f"Do độ tin cậy định giá {str(_fv.get('confidence') or 'thấp').lower()} "
                                     f"({_fv.get('status') or 'chưa đủ cơ sở định giá'}), báo cáo không đưa ra giá mục tiêu. "
                                     f"Giá trị tham khảo từ mô hình: {_n(_fv.get('target_12m'))} đ/cp – không dùng để ra quyết định "
                                     "đầu tư; chi tiết ở mục Định giá.", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TEXT)
            pdf.ln(0.6)
        if ml:
            pdf.set_font(pdf.font_name, "B", 8.0)
            pdf.set_text_color(*_hex_rgb(ml["hex"]))
            pdf.multi_cell(182, 4.3, f"Khuyến nghị: {ml['label']}. {ml['action']}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(pdf.font_name, "", 7.2)
            pdf.set_text_color(*MUTED)
            pdf.multi_cell(182, 3.8, ml["why"] + " Khung khuyến nghị đa lớp: điểm cơ bản F (Chất lượng, Định giá, Tăng trưởng, "
                                     "trừ điểm rủi ro) × điểm so với thị trường R (thứ hạng trong VN30 + cùng ngành) – chi tiết ở mục Kết luận.", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TEXT)
            pdf.ln(1)
        ps = a.get("personal")
        if ps:
            pdf.set_font(pdf.font_name, "B", 7.8)
            pdf.set_text_color(*ps["color"])
            pdf.multi_cell(182, 4.2, ("Mức phù hợp với hồ sơ " if ml else "Khuyến nghị cá nhân hóa cho hồ sơ ") + f"{ps['profile_text']['risk'].lower()} · "
                                     f"{ps['profile_text']['horizon'].lower()}: " + ("" if ml else f"{(ps.get('final') or {}).get('action') or ps['label']} ") + "(mức phù hợp "
                                     f"{ps['fit_score'] if ps.get('fit_score') is not None else '—'}/100) – chi tiết ở mục "
                                     "\"Báo cáo cá nhân hóa\".", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TEXT)
            pdf.ln(1)

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

        if ml:
            self._ml_bars(pdf, ml)
        # Thẻ điểm 5 trụ cột
        pdf.h3("Thẻ điểm 5 trụ cột (0–100)" + (" – sàng lọc tham khảo" if ml else ""))
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
        if a.get("total") is not None:
            pdf.set_font(pdf.font_name, "B", 8.2)
            pdf.set_text_color(*NAVY)
            pdf.cell(0, 5.6, f"Điểm cơ hội tổng (sàng lọc tham khảo): {a['total']:.0f}/100 – {_score_grade(a['total']) or ''}",
                     new_x="LMARGIN", new_y="NEXT")
            note = _score_reco_note(a)
            if note:
                pdf.set_font(pdf.font_name, "", 7.0)
                pdf.set_text_color(*MUTED)
                pdf.multi_cell(182, 3.7, note, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TEXT)

    # ─────────────────────────────────────────────────────────────────────────
    # Báo cáo cá nhân hóa (theo hồ sơ nhà đầu tư) – core/khuyen_nghi.py
    # ─────────────────────────────────────────────────────────────────────────

    def _render_personal(self, pdf: EquityReportPDF, data: dict, a: dict):
        ps = a.get("personal")
        if not ps:
            return
        pdf.h2("Báo cáo cá nhân hóa (theo hồ sơ nhà đầu tư)", min_space=80)
        pr, pt = ps["profile"], ps["profile_text"]
        pairs = [("Nhà đầu tư", pr.get("name") or "—"), ("Khẩu vị rủi ro", pt["risk"]),
                 ("Kỳ hạn đầu tư", pt["horizon"]), ("Mục tiêu", pt["goal"]),
                 ("Trạng thái", "Đang nắm giữ" if pr.get("holder") else "Chưa nắm giữ"),
                 ("Tổng vốn đầu tư", f"{_n(pr['capital'])} đ" if pr.get("capital") else "Không khai báo")]
        if pr.get("holder"):
            pairs += [("Giá vốn", f"{_n(pr.get('cost'))} đ" if pr.get("cost") else "—"),
                      ("Số cổ phiếu đang có", _n(pr.get("qty")) if pr.get("qty") else "—")]
        pdf.h3("Hồ sơ của bạn")
        pdf.kv_grid(pairs, cols=2, size=7.6, h=5.2)

        # Hộp khuyến nghị cá nhân hóa + lý do
        if pdf.get_y() + 30 > pdf.h - pdf.b_margin:
            pdf.add_page()
        y = pdf.get_y() + 1
        pdf.set_fill_color(*ps["color"])
        pdf.rect(14, y, 50, 26, "F", round_corners=True, corner_radius=2.4)
        pdf.set_xy(14, y + 2.4)
        pdf.set_text_color(*_ink(ps["color"]))
        pdf.set_font(pdf.font_name, "", 7.0)
        lab = ps["label"]
        pdf.cell(50, 3.6, "KHUYẾN NGHỊ", align="C", new_x="LEFT", new_y="NEXT")
        pdf.set_font(pdf.big_font, "B", 15 if len(lab) <= 10 else 11 if len(lab) <= 18 else 9)
        pdf.cell(50, 9, lab, align="C", new_x="LEFT", new_y="NEXT")
        pdf.set_font(pdf.font_name, "", 6.9)
        if ps.get("fit_score") is not None:
            pdf.cell(50, 3.8, f"Mức phù hợp với bạn {ps['fit_score']}/100", align="C", new_x="LEFT", new_y="NEXT")
        pdf.set_xy(68, y)
        pdf.set_text_color(*TEXT)
        pdf.set_font(pdf.font_name, "", 7.8)
        pdf.set_x(68)
        pdf.multi_cell(128, 4.2, ps["summary"], new_x="LEFT", new_y="NEXT")
        pdf.ln(0.6)
        for r in ps.get("reasons", []):
            pdf.set_x(68)
            pdf.multi_cell(128, 4.1, "•  " + r, new_x="LEFT", new_y="NEXT")
            pdf.ln(0.3)
        pdf.set_y(max(pdf.get_y(), y + 28) + 2)

        # Mức độ phù hợp
        stx = {"ok": ("Đạt", GREEN), "warn": ("Cần lưu ý", AMBER), "bad": ("Không đạt", RED)}
        pdf.h3("Mức độ phù hợp của cổ phiếu với hồ sơ")
        rows = [[f["criterion"], f["profile"], f["stock"], stx[f["status"]][0]] for f in ps["fit"]]
        pdf.table(["Tiêu chí", "Yêu cầu của hồ sơ", "Cổ phiếu", "Đánh giá"], rows, [52, 50, 50, 30],
                  aligns=["L", "L", "L", "C"], size=7.2, h=5.0,
                  colors=[[None, MUTED, None, stx[f["status"]][1]] for f in ps["fit"]], bold_first=True)
        notes = [f"{f['criterion']}: {f['note']}" for f in ps["fit"] if f.get("note") and f["status"] != "ok"]
        if notes:
            pdf.bullets(notes, size=7.2, h=3.9)

        # Kế hoạch hành động
        pl, st = ps["plan"], ps["settings"]
        pdf.h3("Kế hoạch hành động gợi ý", min_space=40)
        is_buy = ps["label"] in ("MUA", "TÍCH LŨY TỪNG PHẦN")
        plan_pairs = [
            ("Vùng giá tham khảo để mua", f"{_n(pl.get('entry_low'))} – {_n(pl.get('entry_high'))}"
             if is_buy and pl.get("entry_low") else ("Chưa giải ngân mới" if not is_buy else _n(pl.get("entry_high")))),
            ("Tỷ trọng tối đa / cổ phiếu", f"{pl['weight'] * 100:.1f}% danh mục" if is_buy and pl.get("weight")
             else f"0% (trần hồ sơ {st['max_weight'] * 100:.0f}%)"),
            ("Số tiền gợi ý", f"{_n(pl['amount'])} đ" if pl.get("amount") else "—"),
            ("Số cổ phiếu gợi ý (lô 100)", _n(pl["shares"]) if pl.get("shares") else "—"),
            ("Giá cắt lỗ", _n(pl.get("stop")) if pl.get("stop") else "—"),
            ("Giá chốt lời", _n(pl.get("take_profit")) if pl.get("take_profit") else "—"),
        ]
        pdf.kv_grid(plan_pairs, cols=2, size=7.6, h=5.2)
        expl = []
        if pl.get("stop_basis"):
            expl.append(f"Cắt lỗ = {pl['stop_basis']} (lỗ tối đa của hồ sơ {st['max_loss'] * 100:.0f}%"
                        + (f", ATR 14 phiên {_n(ps['atr'])} đ" if ps.get("atr") else "") + ").")
        if pl.get("tp_basis"):
            expl.append(f"Chốt lời = {pl['tp_basis']}.")
        if is_buy:
            expl.append(f"Tỷ trọng = trần {st['max_weight'] * 100:.0f}% theo khẩu vị × hệ số mức rủi ro "
                        "(Thấp 1,0 · Trung bình 0,75 · Cao 0,5). Nên giải ngân 2–3 lần trong vùng giá tham khảo.")
        if pl.get("note_lot"):
            expl.append(pl["note_lot"])
        if ps["label"] == "TÍCH LŨY TỪNG PHẦN":
            expl.insert(0, "TÍCH LŨY TỪNG PHẦN: chia số tiền gợi ý thành 3 phần – phần đầu ngay, các phần sau khi điểm Thời điểm "
                           "trở lại ≥ 50 hoặc BCTC quý kế tiếp xác nhận luận điểm.")
        if expl:
            pdf.bullets(expl, size=7.2, h=3.9)

        hd = ps.get("holding")
        if hd:
            pdf.h3("Vị thế đang nắm giữ", min_space=30)
            hpairs = [("Giá vốn", _n(hd["cost"])), ("Thị giá", _n(ps.get("price"))),
                      ("Lãi/lỗ tạm tính", _n(hd["pnl_pct"], 1, "%", sign=True)),
                      ("Lãi/lỗ (đồng)", _n(hd["pnl_value"], sign=True) if hd.get("pnl_value") is not None else "—"),
                      ("Giá trị thị trường", _n(hd["market_value"]) if hd.get("market_value") else "—"),
                      ("Còn tới giá chốt lời", _n(hd["to_target"], 1, "%", sign=True) if hd.get("to_target") is not None else "—")]
            if hd.get("weight_now") is not None:
                hpairs.append(("Tỷ trọng hiện tại", f"{hd['weight_now']:.1f}% vốn"))
            pdf.kv_grid(hpairs, cols=2, size=7.6, h=5.2)
            pdf.para("Hành động: " + hd["action"], size=7.8,
                     color=RED if "bán" in hd["action"].lower() or "cắt lỗ" in hd["action"].lower() else TEXT)

        pdf.para(f"Hồ sơ {pt['risk'].lower()}: mức rủi ro tối đa {st['max_risk'].lower()}; biến động chấp nhận ≤ "
                 f"{st['max_vol']:.0f}%/năm; tỷ trọng tối đa {st['max_weight'] * 100:.0f}%/cổ phiếu. Nhãn khuyến nghị dùng chung "
                 "cho mọi hồ sơ (khung đa lớp); hồ sơ chỉ thay đổi mức phù hợp và tỷ trọng. Giả định thiết kế, chỉ mang tính "
                 "tham khảo – không phải tư vấn đầu tư cá nhân.", size=6.9, color=MUTED)

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
            if k == "exchange":
                v = _exchange_name(v)
            if k == "listing_date":
                d = pd.to_datetime(v, errors="coerce")
                v = d.strftime("%d/%m/%Y") if pd.notna(d) else v
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
            # Tỷ lệ TÍNH LẠI = số CP nắm giữ / số CP lưu hành hiện hành (tỷ lệ của nguồn thường theo ngày cập nhật khác,
            # trên số CP cũ → lệch với số CP nắm giữ cùng dòng).
            sh_now = ((a.get("fin_summary") or {}).get("valuation") or {}).get("shares")
            rows = []
            for _, r in sh.head(8).iterrows():
                qty = pd.to_numeric(r.get(qty_c), errors="coerce") if qty_c else np.nan
                pct = (qty / sh_now * 100) if sh_now and pd.notna(qty) and qty > 0 else None
                if pct is None:
                    pct = r.get(pct_c) if pct_c else None
                    pct = pct * 100 if isinstance(pct, (int, float)) and pct <= 1 else pct
                rows.append([str(r.get(name_c, "")), _n(qty) if pd.notna(qty) else "—", _n(pct, 2, "%") if pct is not None else "—"])
            pdf.table(["Cổ đông", "Số cổ phần", "Tỷ lệ"], rows, [128, 32, 22], size=7.2)
            if sh_now:
                pdf.para(f"Tỷ lệ = số cổ phần ÷ {sh_now / 1e6:,.1f} triệu CP lưu hành hiện hành; số cổ phần theo ngày cập nhật "
                         "của nguồn (có thể chưa gồm đợt thưởng/phát hành gần nhất).", size=6.6, color=MUTED)
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

    def _render_quality(self, pdf: EquityReportPDF, a: dict):
        """Chất lượng lợi nhuận – cùng hàm với app (analytics.financial_ratios.earnings_quality)."""
        q = ((a.get("inv") or {}).get("health") or {}).get("earnings_quality")
        if not q:
            try:
                from core.phan_tich_co_ban import earnings_quality
                q = earnings_quality(a.get("fin_wide"))
            except Exception:
                q = None
        if not q or not q.get("available"):
            return
        bn = lambda x: _n(x / 1e9 if x is not None else None)  # noqa: E731
        pdf.h3(f"Chất lượng lợi nhuận {q.get('prev_year')} → {q.get('year')}: {q.get('verdict')}", min_space=40)
        share = q.get("non_core_share_of_op_growth")
        fs = lambda sc, mx: f"{sc}/{mx}" if sc is not None and mx else "—"  # noqa: E731
        rows = [
            ["LN cốt lõi (LN gộp − CP bán hàng − CP quản lý), tỷ", bn(q.get("core_profit_prev")), bn(q.get("core_profit")),
             _n(q.get("core_growth"), 1, "%", sign=True)],
            ["Lợi nhuận sau thuế (LNST), tỷ", bn(q.get("net_income_prev")), bn(q.get("net_income")),
             _n(q.get("net_income_growth"), 1, "%", sign=True)],
            ["LN thuần HĐKD, tỷ · phần tăng đến từ tài chính/khác", bn(q.get("op_profit_prev")), bn(q.get("op_profit")),
             (_n(share, 0, "%") + " mức tăng") if share is not None else "—"],
            ["Dòng tiền tự do FCF = CFO − capex, tỷ", bn(q.get("fcf_prev")), bn(q.get("fcf")),
             _n(q.get("fcf_growth"), 0, "%", sign=True) if q.get("fcf_growth") is not None else "—"],
            ["CFO / LNST", _n(q.get("cfo_to_ni_prev"), 2, "x"), _n(q.get("cfo_to_ni"), 2, "x"),
             _n(q.get("cfo_growth"), 0, "%", sign=True) + " CFO" if q.get("cfo_growth") is not None else "—"],
            ["Piotroski F-score", fs(q.get("fscore_prev"), q.get("fscore_prev_max")), fs(q.get("fscore"), q.get("fscore_max")),
             "≥ 7 mạnh · ≤ 3 yếu"],
        ]
        pdf.table(["Chỉ tiêu", q.get("prev_year", ""), q.get("year", ""), "Thay đổi / ghi chú"], rows, [86, 30, 30, 36],
                  aligns=["L", "R", "R", "R"], size=7.2, h=4.6)
        flags = [("(!) " if f["level"] == "cao" else "") + f["text"] for f in q.get("flags", [])]
        if flags:
            pdf.bullets(flags, size=7.6, h=4.0)

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
            if not cur % 10:
                self._render_latest_quarter(pdf, a)
            self._render_quality(pdf, a)
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

    def _render_latest_quarter(self, pdf: EquityReportPDF, a: dict):
        """Góp ý GK (II.3): báo cáo kỳ NĂM vẫn hiện quý gần nhất so với cùng kỳ + lũy kế từ đầu năm, để người đọc kiểm
        chứng các nhận định dùng số quý (vd cảnh báo của Forecast Engine) ngay trong mục Cập nhật KQKD."""
        q = a.get("fin_q")
        if not isinstance(q, pd.DataFrame) or q.empty:
            return
        q = q.sort_index()
        qk = [int(k) for k in q.index if int(k) % 10]
        if not qk:
            return
        cur = qk[-1]
        same = cur - 10
        if same not in q.index:
            return
        y, qn = divmod(cur, 10)
        ytd_cur = [y * 10 + i for i in range(1, qn + 1)]
        ytd_prev = [(y - 1) * 10 + i for i in range(1, qn + 1)]
        # Q4: lũy kế = cả năm (đã có ở bảng năm) → không lặp
        has_ytd = 1 < qn < 4 and all(k in q.index for k in ytd_cur + ytd_prev)
        bank = a.get("is_bank")
        items = ([("total_operating_income", "Tổng thu nhập hoạt động"), ("provision_expense", "Chi phí dự phòng"),
                  ("profit_before_tax", "Lợi nhuận trước thuế"), ("net_income_parent", "LNST cổ đông công ty mẹ")] if bank else
                 [("revenue", "Doanh thu thuần"), ("gross_profit", "Lợi nhuận gộp"), ("profit_before_tax", "Lợi nhuận trước thuế"),
                  ("net_income_parent", "LNST cổ đông công ty mẹ")])

        def chg(v1, v0):
            if pd.isna(v1) or pd.isna(v0) or v0 == 0:
                return None
            if v0 > 0 and v1 > 0:
                return (v1 / v0 - 1) * 100
            if v0 < 0 and v1 < 0:
                return (abs(v1) / abs(v0) - 1) * 100
            return None
        rows, colors = [], []
        for k, lbl in items:
            if k not in q.columns:
                continue
            v1, v0 = q.loc[cur, k], q.loc[same, k]
            if pd.isna(v1) and pd.isna(v0):
                continue
            row = [lbl, _n(v0 / 1e9 if pd.notna(v0) else None), _n(v1 / 1e9 if pd.notna(v1) else None), _n(chg(v1, v0), 1, "%", sign=True)]
            c1 = chg(v1, v0)
            col = [None, None, None, None if c1 is None else (GREEN if c1 >= 0 else RED)]
            if has_ytd:
                s1, s0 = q.loc[ytd_cur, k].sum(min_count=qn), q.loc[ytd_prev, k].sum(min_count=qn)
                c2 = chg(s1, s0)
                row += [_n(s0 / 1e9 if pd.notna(s0) else None), _n(s1 / 1e9 if pd.notna(s1) else None), _n(c2, 1, "%", sign=True)]
                col += [None, None, None if c2 is None else (GREEN if c2 >= 0 else RED)]
            if k == "provision_expense":          # chi phí: tăng là xấu
                col = [None if c in (None,) else (RED if c == GREEN else GREEN) for c in col]
            rows.append(row)
            colors.append(col)
        if not rows:
            return
        lc, lp = key_to_label(cur), key_to_label(same)
        hdr = ["Chỉ tiêu (tỷ đồng)", lp, lc, "% yoy"]
        widths = [62, 30, 30, 22] if not has_ytd else [50, 22, 22, 19, 24, 24, 21]
        if has_ytd:
            hdr += [f"{qn * 3} tháng {y - 1}", f"{qn * 3} tháng {y}", "% lũy kế"]
        pdf.h3(f"Cập nhật quý gần nhất ({lc})" + (" và lũy kế từ đầu năm" if has_ytd else ""), min_space=48)
        pdf.table(hdr, rows, widths, colors=colors, size=7.3)
        pdf.para("Số liệu quý từ BCTC quý đã công bố đến ngày định giá; dùng để kiểm chứng các nhận định có nhắc tới số quý "
                 "(ví dụ cảnh báo của mô hình dự phóng ở mục Định giá).", size=6.8, color=MUTED)

    def _render_forecast_table(self, pdf: EquityReportPDF, a: dict):
        """Góp ý GK (II.3): in bảng dự phóng kịch bản cơ sở của Forecast Engine (2 năm tới) cạnh năm thực tế gần nhất."""
        f = (a.get("inv") or {}).get("forecast") or {}
        yrs = ((f.get("scenarios") or {}).get("base") or {}).get("years") or []
        if not f.get("available") or not yrs:
            return
        yrs = yrs[:2]
        wide = a.get("fin_wide")
        base_key = (f.get("base") or {}).get("key")
        actual = wide.loc[base_key] if isinstance(wide, pd.DataFrame) and base_key in getattr(wide, "index", []) else None
        r = (a.get("fin_summary") or {}).get("ratios")
        act_r = r.loc[base_key] if isinstance(r, pd.DataFrame) and base_key in r.index else None
        bank = a.get("is_bank")
        rev_k = "total_operating_income" if bank and actual is not None and "revenue" not in actual.index else "revenue"

        def g(row, k):
            v = row.get(k) if row is not None else None
            return None if v is None or (isinstance(v, float) and np.isnan(v)) else v
        cols = [(f.get("base") or {}).get("label", "Thực tế").replace("Năm ", "") + " (TH)"] + \
               [str(y.get("label", "")).replace("FY", "") + "F" for y in yrs]
        rv = [g(actual, rev_k)] + [y.get("revenue") for y in yrs]
        ni = [g(actual, "net_income_parent")] + [y.get("net_income_parent") for y in yrs]

        def gr(vals):
            out = ["—"]
            for a0, a1 in zip(vals[:-1], vals[1:]):
                out.append(_n((a1 / a0 - 1) * 100, 1, "%", sign=True) if a0 and a1 and a0 > 0 else "—")
            return out
        rows = [["Doanh thu (tỷ)"] + [_n(v / 1e9 if v else None) for v in rv], ["  +/- yoy"] + gr(rv)]
        if not bank:
            eb = [None] + [y.get("ebitda") for y in yrs]
            rows.append(["EBITDA (tỷ)"] + [_n(v / 1e9) if v else "—" for v in eb])
        rows += [["LNST cổ đông mẹ (tỷ)"] + [_n(v / 1e9 if v else None) for v in ni], ["  +/- yoy"] + gr(ni),
                 ["EPS (đ/cp)"] + [_n(g(act_r, "eps"))] + [_n(y.get("eps")) for y in yrs],
                 ["ROE"] + [_n(g(act_r, "roe"), 1, "%")] + [_n((y.get("roe") or 0) * 100, 1, "%") if y.get("roe") is not None else "—" for y in yrs],
                 ["Cổ tức tiền mặt/CP (đ)"] + [_n(g(act_r, "dps"))] + [_n(y.get("dps")) for y in yrs]]
        colors = [[None] * 4 if "yoy" not in r_[0] else [None] + [(GREEN if str(v).startswith("+") else RED if str(v).startswith("-") else None) for v in r_[1:]]
                  for r_ in rows]
        pdf.h3("Dự phóng tài chính – kịch bản cơ sở (Forecast Engine)", min_space=40)
        pdf.table(["Chỉ tiêu"] + cols, rows, [62, 40, 40, 40], colors=colors, size=7.4)
        pdf.para("TH = số thực hiện (EPS điều chỉnh theo số CP hiện hành); F = dự phóng kịch bản cơ sở từ BCTC đến ngày định giá – "
                 "giả định tăng trưởng, biên lợi nhuận và tỷ lệ chi trả cổ tức ghi ở mục Kịch bản. Đây là ước tính mô hình, "
                 "không phải kế hoạch của doanh nghiệp.", size=6.8, color=MUTED)

    # ─────────────────────────────────────────────────────────────────────────
    # 06 Phân tích kỹ thuật – biểu đồ và bảng chỉ báo đi liền nhau
    # ─────────────────────────────────────────────────────────────────────────

    def _render_technical(self, pdf: EquityReportPDF, data: dict, a: dict):
        pdf.h2("Phân tích kỹ thuật", min_space=150, new_page=pdf.get_y() > 120)
        ticker = data["ticker"]
        if a.get("px") is None:
            pdf.para("Không có dữ liệu giá lịch sử.", color=MUTED)
            return
        bottom = pdf.chart(_generate_price_chart(a["px"], ticker, a["target"], a["stop"], a.get("chart_days") or 365),
                           x=14, w=182)
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
        ev_df = (a.get("profile") or {}).get("events")
        try:
            from core.tin_tuc import news_insight
            ins = news_insight(items, ev_df)
        except Exception as exc:  # pragma: no cover
            logger.debug("news insight failed: %s", exc)
            ins = None
        if ins and (ins["n"] or ins["events"]):
            self._render_news_insight(pdf, ins)
        if not items:
            pdf.para("Chưa thu thập được tin tức cho mã này tại thời điểm tạo báo cáo.", color=MUTED)
        else:
            if ins and ins["clusters"]:               # mỗi chủ đề 1 dòng (tin trùng nội dung gộp lại, ghi số bài)
                items = [{**c["items"][0], "title": str(c["title"]) + (f"  (+{c['n'] - 1} bài cùng chủ đề)" if c["n"] > 1 else "")}
                         for c in ins["clusters"]]
            pdf.h3("Danh sách tin (đã gộp tin trùng chủ đề)", min_space=30)
            rows, colors, links = [], [], []
            for it in items:
                s_tag = it.get("sentiment", "Trung tính")
                url = it.get("url") or it.get("link") or ""
                rows.append([it.get("date", "--"), s_tag, str(it.get("title", "")), it.get("source", "")])
                colors.append([MUTED, GREEN if "Tích cực" in s_tag else RED if "Tiêu cực" in s_tag else MUTED, None, MUTED])
                links.append([None, None, url, url])
            pdf.table(["Ngày", "Sắc thái", "Tiêu đề", "Nguồn"], rows, [19, 19, 116, 28], aligns=["L", "L", "L", "L"],
                      size=7.2, h=4.8, colors=colors, links=links)
            pdf.para("Bấm vào tiêu đề hoặc nguồn (chữ xanh, gạch chân) để mở bài báo gốc. Sắc thái tin được phân loại tự "
                     "động theo từ điển từ khóa – chỉ mang tính tham khảo.", size=6.8, color=MUTED)
        ev = (a.get("profile") or {}).get("events")
        if isinstance(ev, pd.DataFrame) and not ev.empty:
            pdf.h3("Sự kiện doanh nghiệp", min_space=45)
            cols = list(ev.columns)
            # Ưu tiên tiêu đề CHI TIẾT (vd "Nguyễn Văn Khoa – Đăng kí Mua 428,368 FPT") thay vì tên loại sự kiện
            low = {str(c).lower(): c for c in cols}
            title_c = next((low[k] for k in ("event_title_vi", "event_title", "title", "event_title_en") if k in low), None) \
                or next((c for c in cols if any(k in str(c).lower() for k in ("title", "event_name", "name", "tiêu đề"))), cols[0])
            kind_c = low.get("event_name_vi")
            date_c = next((low[k] for k in ("display_date1", "public_date", "exright_date") if k in low), None) \
                or next((c for c in cols if any(k in str(c).lower() for k in ("date", "ngày"))), None)
            rows, seen = [], set()
            for _, r in ev.iterrows():
                d = str(r.get(date_c, ""))[:10] if date_c else ""
                t = str(r.get(title_c, "") or "").strip()
                k = str(r.get(kind_c, "") or "").strip() if kind_c else ""
                if k and t and k.split(":")[0].lower() not in t.lower():
                    t = f"{k.split(':')[0]}: {t}"
                if (d, t) in seen or not t:
                    continue
                seen.add((d, t))
                rows.append([pd.to_datetime(d, errors="coerce").strftime("%d/%m/%Y") if d else "", t])
                if len(rows) >= 10:
                    break
            pdf.table(["Ngày", "Sự kiện"], rows, [24, 158], aligns=["L", "L"], size=7.2)

    def _render_news_insight(self, pdf: EquityReportPDF, ins: dict):
        """Khối 'Nhận định tin tức' (core/tin_tuc.py): tâm lý, chủ đề nổi bật & ý nghĩa, sự kiện đáng chú ý."""
        pdf.h3("Nhận định tin tức", min_space=45)
        c = ins["counts"]
        n = max(1, ins["n"])
        if ins["n"]:
            # thanh tâm lý: xanh = tích cực, xám = trung tính, đỏ = tiêu cực
            x, y, w, h = 14, pdf.get_y() + 0.5, 182, 4.2
            for k, col in (("pos", GREEN), ("neu", (203, 213, 225)), ("neg", RED)):
                ww = w * c[k] / n
                if ww > 0:
                    pdf.set_fill_color(*col)
                    pdf.rect(x, y, ww, h, "F")
                    x += ww
            pdf.set_y(y + h + 1.5)
        pdf.bullets([self._plain(t) for t in ins["headline"]], size=7.6, h=4.0)
        if ins["themes"]:
            pdf.set_font(pdf.font_name, "B", 7.8)
            pdf.set_text_color(*NAVY)
            pdf.cell(0, 4.6, "Chủ đề nổi bật & ý nghĩa với cổ phiếu", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TEXT)
            pdf.bullets([f"{t['label']} ({t['articles']} bài): {t['implication']}" for t in ins["themes"][:5]], size=7.4, h=3.9)
        if ins["events"]:
            pdf.set_font(pdf.font_name, "B", 7.8)
            pdf.set_text_color(*NAVY)
            pdf.cell(0, 4.6, "Sự kiện doanh nghiệp đáng chú ý", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TEXT)
            pdf.bullets(ins["events"], size=7.4, h=3.9)
        if ins["flags"]:
            pdf.para("Cần xem lại giả định định giá: có tin thuộc nhóm " + ", ".join(ins["flags"]) + ".", size=7.4, color=RED)
        pdf.para("Nhận định tạo tự động theo quy tắc từ khóa (gộp tin trùng chủ đề, phân loại chủ đề, tổng hợp giao dịch nội "
                 "bộ) – chỉ để tham khảo, không thay thế việc đọc bài gốc.", size=6.6, color=MUTED, h=3.4)
        pdf.ln(1)

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
        if not ok:
            pdf.multi_cell(0, 3.6, "* Giá trị tham khảo – không dùng để ra khuyến nghị (độ tin cậy định giá thấp).",
                           new_x="LMARGIN", new_y="NEXT")
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
        from core.dinh_gia import SCEN_LABEL
        pdf.h2("Định giá & giá mục tiêu", new_page=pdf.get_y() > 150)
        fv = a.get("fv") or {}
        if (fv or {}).get("scope_change"):
            pdf.para("Lưu ý: " + fv["scope_change"]["text"] + " EV/EBITDA và DCF tạm không dùng; độ tin cậy giảm một bậc.",
                     size=7.6, color=RED)
        pdf.para("Giá mục tiêu (kỳ hạn 12 tháng kể từ ngày định giá) là ước tính theo các giả định bên dưới, không phải mức giá chắc chắn đạt được. Chỉ phương "
                 "pháp đủ dữ liệu và cho kết quả hợp lệ mới được tính; trọng số được chuẩn hóa lại trên các phương pháp hợp lệ.",
                 size=7.6, color=MUTED)
        if not fv.get("methods"):
            pdf.bullets([f"Trạng thái: {fv.get('status', 'CHƯA ĐỦ CƠ SỞ ĐỊNH GIÁ')}."] + list(fv.get("notes") or [])
                        + [f"Không dùng {m}: {r}." for m, r in fv.get("invalid", [])], size=7.6)
            return
        up, er = fv.get("upside"), fv.get("expected_return")
        ok = bool(fv.get("available"))
        if ok:
            self._tiles(pdf, [("Thị giá", _n(fv.get("price")), NAVY), ("Giá mục tiêu", _n(fv.get("target_12m")), GOLD_DK),
                              ("Upside", _n(up, 1, "%", sign=True), GREEN if (up or 0) >= 0 else RED),
                              ("Tổng LN kỳ vọng", _n(er, 1, "%", sign=True), GREEN if (er or 0) >= 0 else RED)], h=18)
        else:
            # Góp ý GK (Vấn đề 2): độ tin cậy thấp → không hiển thị giá mục tiêu nổi bật; số mô hình chỉ là "giá trị tham khảo".
            self._tiles(pdf, [("Thị giá", _n(fv.get("price")), NAVY), ("Giá mục tiêu", "Chưa đưa ra", GREY),
                              ("Giá trị tham khảo", _n(fv.get("target_12m")), GREY),
                              ("Độ tin cậy định giá", str(fv.get("confidence") or "Thấp"), RED)], h=18)
            pdf.para(f"Trạng thái: {fv.get('status')} (độ tin cậy {fv.get('confidence', '—').lower()}). Do độ tin cậy định giá thấp, "
                     f"báo cáo KHÔNG đưa ra giá mục tiêu. Con số {_n(fv.get('target_12m'))} đ/cp chỉ là kết quả tham khảo từ "
                     f"{len(fv.get('methods') or [])} phương pháp ({', '.join(m['name'] for m in fv.get('methods') or [])}) và không nên "
                     "được dùng để ra quyết định đầu tư.", size=7.6, color=RED)
        hybrid = fv.get("model_engine") == "hybrid" or fv.get("profile") is not None
        if hybrid:
            prof = fv.get("profile") or {}
            pdf.para(f"Giá trị hợp lý HÔM NAY (ngày định giá {fv.get('valuation_date') or '—'}): {_n(fv.get('fair_value_today'))} đ/cp · "
                     f"Giá mục tiêu TƯƠNG LAI (ngày {fv.get('target_date') or '—'}): {_n(fv.get('target_12m'))} đ/cp. "
                     f"Hồ sơ phương pháp: {prof.get('label', '—')} ({prof.get('reason', '')}); {prof.get('rationale', '')} "
                     "Dự phóng lấy từ Forecast Engine (EPS/EBITDA 12 tháng tới, BVPS tại ngày mục tiêu, FCFF 5 năm).",
                     size=7.2, color=MUTED)
        pdf.h3("Kết quả theo từng phương pháp (kịch bản cơ sở)")
        rows = [[m["name"], f"{m['multiple']:.2f}x" if m.get("multiple") else "—",
                 f"{m['base_label']} {m['base']:,.0f}" if m.get("base") is not None else "—", f"{m['fair']:,.0f}",
                 f"{m['upside']:+.1f}%", f"{m['weight'] * 100:.0f}%"] for m in fv["methods"]]
        rows.append(["Giá mục tiêu" if ok else "Giá trị tham khảo*", "", "", f"{fv['target_12m']:,.0f}", f"{up:+.1f}%", "100%"])
        colors = [[None, None, None, None, (GREEN if m["upside"] >= 0 else RED) if ok else GREY, None] for m in fv["methods"]]
        colors.append([NAVY, None, None, GOLD_DK, GREEN if up >= 0 else RED, None] if ok else [GREY] * 6)
        pdf.table(["Phương pháp", "Hệ số", "Cơ sở (đ/cp)", "Giá trị (đ/cp)", "Upside", "Trọng số"], rows,
                  [36, 18, 58, 28, 22, 20], colors=colors)
        pdf.set_font(pdf.font_name, "", 6.9)
        pdf.set_text_color(*MUTED)
        if not ok:
            pdf.multi_cell(0, 3.6, "* Giá trị tham khảo – không dùng để ra khuyến nghị (độ tin cậy định giá thấp).",
                           new_x="LMARGIN", new_y="NEXT")
        for m in fv["methods"]:
            pdf.multi_cell(0, 3.6, f"• {m['name']}: {m['source']}.", new_x="LMARGIN", new_y="NEXT")
        for m, r in fv.get("invalid", []):
            pdf.multi_cell(0, 3.6, f"• Không dùng {m}: {r}.", new_x="LMARGIN", new_y="NEXT")
        for m, r in fv.get("not_applicable", []):
            pdf.multi_cell(0, 3.6, f"• {m}: {r}.", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*TEXT)

        self._render_forecast_table(pdf, a)
        sc = fv.get("scenarios") or {}
        if any((sc.get(k) or {}).get("target") for k in sc):
            pdf.h3("Kịch bản Bear / Base / Bull (thay đổi bộ giả định)", min_space=30)
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
            fsc = ((a.get("inv") or {}).get("forecast") or {}).get("scenarios") or {}
            if hybrid and cfg:
                # Giả định giống nhau ở cả 3 kịch bản → 1 đoạn chung; mỗi kịch bản chỉ ghi phần KHÁC (tránh lặp 3 đoạn gần y hệt)
                ks = [k for k in ("bear", "base", "bull") if k in cfg]
                assum = {k: [x.strip() for x in ((fsc.get(k) or {}).get("assumptions") or []) if str(x).strip()] for k in ks}
                common = [x for x in assum[ks[0]] if all(x in assum[k] for k in ks)] if ks else []
                if common:
                    pdf.para("Giả định chung của 3 kịch bản: " + " ".join(common), size=6.6, color=MUTED)
                lines = []
                for k in ks:
                    diff = " ".join(x for x in assum[k] if x not in common)
                    lines.append(f"{SCEN_LABEL[k]}: bội số phân vị {cfg[k]['multiple_pct']}, Ke {cfg[k]['ke_shift'] * 100:+.0f} "
                                 f"điểm %" + (f". Khác biệt: {diff}" if diff else "."))
                pdf.bullets(lines, size=6.6, h=3.5)
            elif cfg:
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
        ds = fv.get("dcf_sensitivity")
        if ds:
            pdf.h3("Độ nhạy giá trị DCF theo WACC × tăng trưởng dài hạn g (đ/cp)", min_space=40)
            rows, colors = [], []
            for w_, row in zip(ds["wacc"], ds["grid"]):
                rows.append([f"WACC {w_ * 100:.1f}%"] + [f"{x:,.0f}" if x else "—" for x in row])
                colors.append([None] + [(GREEN if x >= fv["price"] else RED) if x else MUTED for x in row])
            pdf.table([""] + [f"g {g_ * 100:.1f}%" for g_ in ds["g"]], rows, [32] + [30] * 5, colors=colors, size=7.2)
        asum = fv.get("assumptions") or {}
        pct = lambda v: _n(v * 100, 1, "%") if v is not None else "—"  # noqa: E731
        growth_line = (f"Tăng trưởng năm 1 (kịch bản cơ sở, Forecast Engine) {pct(asum.get('g_base'))}: {asum.get('basis_growth', '')}; "
                       f"kỳ gốc dự báo {asum.get('forecast_base') or '—'}." if hybrid else
                       f"Tăng trưởng cơ sở {pct(asum.get('g_base'))} = 60% CAGR 3 năm {asum.get('basis_growth', '')} ({pct(asum.get('g_hist'))}) "
                       f"+ 40% tăng trưởng bền vững ROE × (1 − tỷ lệ chi trả) ({pct(asum.get('g_sustainable'))}); biên LN ròng cơ sở {pct(asum.get('net_margin_base'))}.")
        notes = [
            f"Ke = {pct(asum.get('risk_free'))} + β {_n(asum.get('beta_used'), 2)} × {pct(asum.get('equity_premium'))} = {pct(asum.get('ke'))} "
            f"(β đo được {_n(asum.get('beta'), 2)}).",
            growth_line,
            f"Cổ tức tiền mặt dự kiến {_n(fv.get('expected_dividend'))} đ/cp ({_n(fv.get('dividend_yield'), 1, '%')}), "
            + ("đã cộng một lần vào tổng lợi nhuận kỳ vọng; giá mục tiêu là giá sau khi trả cổ tức."
               if fv.get("dividends_included") else "không cộng (chưa trả đều tiền mặt)."),
            (f"Giá trị hợp lý hôm nay = (giá mục tiêu + cổ tức) ÷ (1 + Ke) ≈ {_n(fv.get('fair_value_today'))} đ/cp."
             if hybrid else f"Giá trị nội tại quy về hôm nay = giá mục tiêu ÷ (1 + Ke) ≈ {_n(fv.get('intrinsic_today'))} đ/cp."),
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

    def _ml_bars(self, pdf: EquityReportPDF, ml: dict):
        """Thanh điểm 4 lớp Q/V/G/T + F của khung khuyến nghị đa lớp (trang tóm tắt)."""
        pdf.h3("Điểm khuyến nghị đa lớp (0–100)", min_space=40)
        wf = (ml.get("thresholds") or {}).get("weights_f") or {}
        rows = [("Chất lượng (Q)", ml.get("Q"), f"{wf.get('Q', 0.4) * 100:.0f}% F"),
                ("Định giá (V)", ml.get("V"), f"{wf.get('V', 0.35) * 100:.0f}% F"),
                ("Tăng trưởng (G)", ml.get("G"), f"{wf.get('G', 0.25) * 100:.0f}% F"),
                ("Điểm cơ bản F", ml.get("F"), f"trừ RR {_n(ml.get('penalty'), 0)}"),
                ("So với thị trường (R)", ml.get("R"), "trục 2")]
        for lbl, v, sub in rows:
            bold = lbl.startswith("Điểm cơ bản")
            pdf.set_font(pdf.font_name, "B" if bold else "", 8)
            pdf.cell(32, 5.4, lbl)
            pdf.set_font(pdf.font_name, "", 6.4)
            pdf.set_text_color(*MUTED)
            pdf.cell(14, 5.4, sub)
            pdf.set_text_color(*TEXT)
            yb = pdf.get_y() + 1.3
            pdf.set_fill_color(*TRACK)
            pdf.rect(62, yb, 112, 2.8, "F", round_corners=True, corner_radius=1.4)
            if v is not None:
                pdf.set_fill_color(*(GREEN if v >= 70 else AMBER if v >= 55 else RED))
                pdf.rect(62, yb, max(2.8, min(112.0, 112 * v / 100)), 2.8, "F", round_corners=True, corner_radius=1.4)
            pdf.set_x(176)
            pdf.set_font(pdf.font_name, "B", 8)
            pdf.cell(20, 5.4, f"{v:.0f}/100" if v is not None else "Thiếu DL", align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    def _render_ml_block(self, pdf: EquityReportPDF, ml: dict):
        """Kết luận theo khung khuyến nghị đa lớp: MỘT nhãn + đủ nội dung bắt buộc (mục 7 của khung)."""
        from core.khuyen_nghi import MATRIX_ROWS
        if pdf.get_y() + 34 > pdf.h - pdf.b_margin:
            pdf.add_page()
        col = _hex_rgb(ml["hex"])
        y = pdf.get_y()
        pdf.set_fill_color(*col)
        pdf.rect(14, y, 182, 13, "F", round_corners=True, corner_radius=2.4)
        pdf.set_xy(18, y + 1.6)
        pdf.set_text_color(*_ink(col))
        pdf.set_font(pdf.font_name, "", 7.2)
        pdf.cell(60, 3.6, "KHUYẾN NGHỊ (KHUNG ĐA LỚP)")
        pdf.set_xy(18, y + 5.0)
        pdf.set_font(pdf.big_font, "B", 13)
        pdf.cell(90, 7, ml["label"])
        pdf.set_xy(100, y + 2.2)
        pdf.set_font(pdf.font_name, "", 7.4)
        rel = ml.get("reliability") or {}
        pdf.multi_cell(92, 3.8, f"Điểm cơ bản F {_n(ml.get('F'), 0)} · So với thị trường R {_n(ml.get('R'), 0)}\n"
                                f"Độ tin cậy: {rel.get('level', '—')} (dữ liệu {rel.get('coverage', '—')}%, {rel.get('peers', 0)} DN cùng ngành)",
                       align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*TEXT)
        pdf.set_y(y + 15)
        pdf.para(ml["why"] + " " + ml["action"], size=8.0)
        # ma trận
        pdf.h3("Ma trận khuyến nghị (F × R)", min_space=30)
        rows_, colors = [], []
        rkey = {"strong": 0, "mid": 1, "weak": 2}.get(ml.get("row"))
        ckey = {"good": 1, "mid": 2, "bad": 3}.get(ml.get("col"))
        th = ml["thresholds"]
        for i, r in enumerate(MATRIX_ROWS):
            rows_.append(list(r))
            colors.append([NAVY] + [(col if (i == rkey and j == ckey) else MUTED) for j in (1, 2, 3)])
        pdf.table(["Điểm cơ bản \\ So với thị trường", f"R ≥ {th['r_strong']:.0f} (mạnh hơn)",
                   f"{th['r_weak']:.0f} ≤ R < {th['r_strong']:.0f} (ngang)", f"R < {th['r_weak']:.0f} (yếu hơn)"], rows_,
                  [50, 44, 44, 44], aligns=["L", "C", "C", "C"], size=7.0, h=5.0, colors=colors, bold_first=True)
        rel = ml.get("relative") or {}
        info = []
        if rel.get("rank") and not rel.get("fallback"):
            info.append(f"Xếp hạng sức mạnh {rel['rank'][0]}/{rel['rank'][1]} trong rổ {rel.get('universe')}")
        mk = rel.get("market") or {}
        if mk:
            info.append(f"VN-Index {mk['close']:,.0f} {'dưới' if mk['below'] else 'trên'} MA200 ({mk['ma200']:,.0f})")
        hd = rel.get("hurdle") or {}
        if hd.get("gap") is not None:
            info.append(f"tổng LN kỳ vọng {hd['er']:+.1f}% {'≥' if hd['pass'] else '<'} chi phí vốn Ke {hd['ke']:.1f}%")
        if info:
            pdf.para("; ".join(info) + ". MUA cần: F ≥ 70, R ≥ 60, VN-Index trên MA200 và LN kỳ vọng ≥ Ke.", size=7.0, color=MUTED)
        if ml.get("blocked_by_exclusion"):
            pdf.para("Ô ma trận cho MUA/TÍCH LŨY nhưng mã vướng bộ lọc loại trừ → hạ về THEO DÕI.", size=7.0, color=RED)
        # thành phần 4 lớp
        pdf.h3("Điểm từng lớp và thành phần", min_space=40)
        names = {"Q": "Chất lượng (Q)", "V": "Định giá (V)", "G": "Tăng trưởng (G)", "R": "So với thị trường (R)"}
        trows = []
        for k in ("Q", "V", "G", "R"):
            comps = "; ".join(f"{r['name']} {('%.0f' % r['score']) if r['score'] is not None else 'thiếu DL'}"
                              for r in (ml.get("layers") or {}).get(k, []) if r.get("weight") or r["score"] is not None)
            trows.append([names[k], _n(ml.get(k), 0), comps])
        trows.append(["Điểm trừ rủi ro", f"−{_n(ml.get('penalty'), 0)}",
                      "; ".join(p_["text"] for p_ in ml.get("penalties") or []) or "Không có (Altman Z'', Beneish M-score)"])
        pdf.bullets([f"{r[0]}: {r[1]}/100 – {r[2]}" if not r[0].startswith("Điểm trừ") else f"{r[0]}: {r[1]} – {r[2]}"
                     for r in trows], size=7.3, h=3.9)
        pdf.para("F = 0,40·Q + 0,35·V + 0,25·G − điểm trừ rủi ro (tối đa 15). Lớp thiếu dữ liệu được loại khỏi mẫu số. "
                 "Thứ hạng % trong ngành chỉ dùng khi có ≥ 5 doanh nghiệp cùng nhóm có số liệu.", size=6.8, color=MUTED)
        # bộ lọc loại trừ
        pdf.h3("Bộ lọc loại trừ", min_space=36)
        st_txt = {"pass": "Đạt", "hit": "Vướng", "unknown": "Chưa kiểm tra được"}
        st_col = {"pass": GREEN, "hit": RED, "unknown": MUTED}
        ex = ml.get("exclusions") or []
        pdf.table(["Điều kiện", "Kết quả", "Chi tiết"], [[e["text"], st_txt[e["status"]], e.get("detail") or ""] for e in ex],
                  [72, 28, 82], aligns=["L", "C", "L"], size=6.9, h=4.6,
                  colors=[[None, st_col[e["status"]], MUTED] for e in ex])
        vr = ml.get("valuation_range") or {}
        if vr.get("available"):
            pdf.para(f"Khoảng định giá ({vr['source']}): {_n(vr['low'])} – {_n(vr['high'])} đ/cp; biên an toàn từ đầu thấp "
                     f"{_n(vr.get('margin_of_safety'), 1, '%', sign=True)}; độ phân tán giữa các phương pháp "
                     f"{_n((vr.get('dispersion') or 0) * 100, 0, '%')}" + (" (> 40% → độ tin cậy định giá thấp)."
                                                                          if (vr.get('dispersion') or 0) > 0.4 else "."), size=7.6)
        pdf.h3("Lý do ủng hộ và rủi ro chính", min_space=30)
        pdf.bullets([f"(+) {x}" for x in ml.get("pros") or ["Chưa có thành phần nổi trội (≥ 60 điểm)."]]
                    + [f"(−) {x}" for x in ml.get("cons") or ["Không có thành phần dưới 45 điểm."]], size=7.6, h=4.0)
        pdf.h3("Điều kiện làm luận điểm sai (cần xem lại khuyến nghị)", min_space=24)
        pdf.bullets(ml.get("invalidation") or [], size=7.6, h=4.0)
        if ml.get("notes"):
            pdf.bullets(["Lưu ý: " + n for n in ml["notes"]], size=7.2, h=3.9)

    def _render_conclusion(self, pdf: EquityReportPDF, data: dict, a: dict):
        pdf.h2("Kết luận & khuyến nghị", min_space=90)
        recd = a["recd"]
        ml = a.get("ml")
        if ml:
            self._render_ml_block(pdf, ml)
            fv = a.get("fv") or {}
            if fv.get("methods"):
                pdf.h3("Định giá", min_space=24)
                pdf.para((f"Giá mục tiêu {_n(fv.get('target_12m'))} đ/cp, tổng LN kỳ vọng {_n(fv.get('expected_return'), 1, '%', sign=True)} "
                          f"(độ tin cậy {str(fv.get('confidence') or '—').lower()})." if fv.get("available") else
                          "Chưa đưa ra giá mục tiêu do độ tin cậy định giá thấp; khoảng định giá ở trên chỉ để tham khảo.")
                         + " Định giá là MỘT đầu vào của lớp Định giá (V), không tự quyết định nhãn khuyến nghị.", size=7.8)
        else:
            y = pdf.get_y()
            pdf.set_fill_color(*a["rec_color"])
            pdf.rect(14, y, 50, 22, "F", round_corners=True, corner_radius=2.4)
            pdf.set_xy(14, y + 2.5)
            pdf.set_text_color(*_ink(a["rec_color"]))
            pdf.set_font(pdf.font_name, "", 7.4)
            pdf.cell(50, 3.6, "KHUYẾN NGHỊ", align="C", new_x="LEFT", new_y="NEXT")
            pdf.set_font(pdf.big_font, "B", 15 if len(a["rec"]) <= 10 else 10)
            pdf.cell(50, 9, a["rec"], align="C", new_x="LEFT", new_y="NEXT")
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
        note = _score_reco_note(a)
        if note:
            pdf.para(note, size=7.6, color=NAVY)
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
            if inv.get("explanation"):
                pdf.h3("Giá mục tiêu được tính thế nào?", min_space=40)
                pdf.bullets(inv["explanation"], size=7.4, h=3.9)
        if ml:
            pdf.para(ml.get("disclaimer", ""), size=7.0, color=MUTED)

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
            elif med and abs(me / med - 1) <= 0.10:          # lệch ≤ 10% so với trung vị → tương đương (14/10/2026)
                col, tag = GREY, "Tương đương ngành"
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
                           + (". Đã loại: " + ", ".join(peers["excluded"]) if peers.get("excluded") else "")
                           + ". Trung vị chỉ công bố khi có ≥ 3 doanh nghiệp có số liệu hợp lệ; lệch ≤ 10% so với trung vị "
                             "ghi là tương đương.",
                           new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TEXT)
        try:
            img = _generate_peer_chart(ticker, peers, {"roe": a.get("last_roe"), "net_margin": a.get("last_margin"),
                                                       "pe": rel.get("pe"), "pb": rel.get("pb")})
        except Exception as exc:  # biểu đồ lỗi không làm hỏng báo cáo
            logger.debug("peer chart failed: %s", exc)
            img = None
        if img is not None:
            pdf.ln(1.5)
            pdf.set_y(pdf.chart(img, x=14, w=182) + 1)
            pdf.para(f"Thanh xanh đậm = {ticker}; thanh xám = doanh nghiệp cùng nhóm; đường vàng = trung vị ngành. "
                     "P/E, P/B: thấp hơn = rẻ hơn; ROE, biên LN: cao hơn = tốt hơn.", size=6.8, color=MUTED)

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
        from core.du_lieu import ITEMS_BY_KEY, PER_UNIT_KEYS, STATEMENT_ITEMS
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
                           ". Nguồn đứng trước trong chuỗi ưu tiên được dùng; ô thiếu được bù từ nguồn sau. Dòng EPS trong "
                           "BCTC là EPS cơ bản doanh nghiệp công bố (số kế toán, chưa điều chỉnh); EPS dùng để phân tích, "
                           "tính P/E ở các mục khác là EPS điều chỉnh theo số CP hiện hành.",
                           new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TEXT)

    def _render_ratios(self, pdf: EquityReportPDF, data: dict, a: dict):
        from core.phan_tich_co_ban import RATIO_META
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
        self._ratio_items(pdf, summ, a)
        try:
            img = _generate_ratio_trend_chart(ratios, a.get("fin_wide"), bool(summ.get("is_bank")))
        except Exception as exc:  # pragma: no cover
            logger.debug("ratio chart failed: %s", exc)
            img = None
        if img is not None:
            pdf.h3("Xu hướng sinh lời & dòng tiền qua các năm", min_space=62)
            pdf.set_y(pdf.chart(img, x=14, w=182) + 2)

    def _ratio_items(self, pdf: EquityReportPDF, summ: dict, a: dict):
        font = "VN" if pdf.has_vn else "Helvetica"
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
            (f"P/E (EPS {val.get('eps_basis') or 'TTM'})", _n(val.get("pe"), 1, "x")), ("P/B", _n(val.get("pb"), 2, "x")),
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
        if val.get("share_note"):
            pdf.multi_cell(0, 3.6, val["share_note"], new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 3.6, "Kỳ năm dùng số liệu cả năm; kỳ quý dùng 4 quý gần nhất (TTM). Tỷ số dòng/số dư dùng bình quân "
                       "đầu–cuối kỳ. F-score theo Piotroski (2000); Z''-score theo Altman (2005) cho thị trường mới nổi, "
                       "không áp dụng cho ngân hàng. EPS, BVPS, cổ tức/CP là số ĐIỀU CHỈNH: quy về số CP hiện hành và hồi tố cổ phiếu "
                       "thưởng/chia tách cho các năm trước – cùng mẫu số với thị giá và P/E, P/B ở trang tóm tắt (khác EPS cơ bản "
                       "công bố trong BCTC – dùng CP bình quân gia quyền và trừ quỹ khen thưởng phúc lợi). Tăng trưởng EPS là số ĐIỀU CHỈNH: cổ phiếu thưởng / "
                       "cổ tức bằng cổ phiếu không bị tính là pha loãng, chỉ phát hành thu tiền mới.", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*TEXT)

    def _render_appendix(self, pdf: EquityReportPDF, data: dict, a: dict):
        font = "VN" if pdf.has_vn else "Helvetica"
        pdf.h2("Phụ lục", new_page=pdf.get_y() > 190, min_space=90)   # còn ≥ ~1/3 trang thì viết tiếp, tránh trang gần trắng
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
                pts_txt = (f"{pts:+g} điểm" if not c.get("max") and pts else "0 điểm" if not c.get("max") and pts is not None
                           else f"{pts}/{c.get('max', 0)}" if pts is not None else f"–/{c.get('max', 0)}")
                pdf.cell(20, 4.4, pts_txt, align="C")
                note = str(c.get("note", ""))
                pdf.cell(42, 4.4, note if len(note) <= 30 else note[:28] + "…", align="C",
                         new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)

        # Thuyết minh phương pháp luận – nội dung dùng chung với trang 🎓 Thuyết Minh Đề Án (core/thuyet_minh.py),
        # tham số đọc từ cấu hình mô hình → phụ lục luôn khớp với app.
        self._render_methodology(pdf, a)
        self._render_symbol_explain(pdf, data, a)

        pdf.h3("D. Nguồn dữ liệu")
        src_rows = [["Giá & khối lượng", "DNSE (gần nhất), vnstock/Vietstock (lịch sử, đã nối chuỗi)", data.get("last_session", "")]]
        fs = a.get("fin_sources")
        if fs is not None and not fs.empty:
            used = sorted({str(x) for x in pd.unique(fs.values.ravel()) if isinstance(x, str)})
            src_rows.append(["Báo cáo tài chính", ", ".join(used), ""])
        src_rows.append(["Chỉ số tài chính", "Tự tính từ BCTC (TTM, bình quân đầu–cuối kỳ)", ""])
        if (data.get("peers") or {}).get("peers"):
            src_rows.append(["So sánh ngành", ", ".join(data["peers"]["peers"][:12]), ""])
        src_links = [[None, None, None] for _ in src_rows]
        for it in data.get("news_items", [])[:6]:
            url = it.get("url") or it.get("link") or ""
            src_rows.append(["Tin tức", (it.get("source") or "") + (" – " + str(it.get("title") or url) if url else ""),
                             it.get("date", "")])
            src_links.append([None, url, None])
        pdf.table(["Loại dữ liệu", "Nguồn", "Ngày"], src_rows, [36, 122, 24], aligns=["L", "L", "L"], size=7, links=src_links)
        pdf.h3("E. Tuyên bố miễn trừ trách nhiệm")
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

    @staticmethod
    def _plain(t: str) -> str:
        return str(t).replace("**", "")

    def _pdf_table_auto(self, pdf: EquityReportPDF, headers, rows, size: float = 6.9):
        """Bảng phụ lục: độ rộng cột theo độ dài nội dung (tổng 182 mm, mỗi cột ≥ 22 mm)."""
        n = len(headers)
        if any(len(str(c)) > 95 for r in rows for c in r):
            # ô quá dài (bảng 1 dòng/ô sẽ cắt chữ) → mỗi hàng thành 1 gạch đầu dòng "cột 1 – cột 2 · cột 3"
            pdf.bullets([f"{self._plain(r[0])} – " + " · ".join(
                f"{self._plain(headers[i])}: {self._plain(r[i])}" if n > 2 else self._plain(r[i]) for i in range(1, n))
                for r in rows], size=6.9, h=3.6)
            return
        lens = [max([len(str(headers[i]))] + [min(len(str(r[i])), 140) for r in rows]) for i in range(n)]
        tot = sum(lens) or 1
        w = [max(22.0, 182 * L / tot) for L in lens]
        k = 182 / sum(w)
        w = [x * k for x in w]
        pdf.table(list(headers), [[self._plain(c) for c in r] for r in rows], w, aligns=["L"] * n, size=size, h=4.2)

    def _render_methodology(self, pdf: EquityReportPDF, a: dict):
        from core import thuyet_minh as tc
        pdf.h3("B. Phương pháp luận – lý thuyết, mô hình & công thức", min_space=40)
        pdf.para("Tóm tắt lý thuyết & công thức cốt lõi (phân tích cơ bản, kỹ thuật, dự phóng, định giá); bản đầy đủ gồm hồ sơ "
                 "phương pháp theo ngành, độ tin cậy, 5 trụ cột, khuyến nghị và kiểm chứng ở trang \"Thuyết Minh Đề Án\" của "
                 "ứng dụng. Tham số đọc trực tiếp từ cấu hình mô hình tại thời điểm xuất báo cáo.", size=7.0, color=MUTED)
        # 15/10/2026: phụ lục rút gọn – dừng trước "Hồ sơ phương pháp theo ngành" (bảng hồ sơ ngành, kịch bản, độ tin cậy,
        # 5 trụ cột, khuyến nghị, rủi ro, kiểm chứng xem đầy đủ ở trang Thuyết minh của app)
        keep = ["fundamental", "technical", "forecast", "valuation"]
        secs = {s["key"]: s for s in tc.sections()}
        for i, key in enumerate(keep, 1):
            sec = secs[key]
            pdf.set_font(pdf.font_name, "B", 8.6)
            pdf.set_text_color(*NAVY)
            if pdf.get_y() > pdf.h - pdf.b_margin - 30:
                pdf.add_page()
            pdf.ln(1.5)
            pdf.cell(0, 5.2, f"B.{i}  {sec['title']}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TEXT)
            pdf.bullets([self._plain(x) for x in sec["pitch"]], size=7.2, h=3.8)
            for b in sec["blocks"]:
                kind = b[0]
                if kind == "h" and key == "valuation" and b[1].startswith("Hồ sơ phương pháp"):
                    break
                if kind == "h":
                    pdf.set_font(pdf.font_name, "B", 7.6)
                    pdf.set_text_color(*GOLD_DK)
                    if pdf.get_y() > pdf.h - pdf.b_margin - 18:
                        pdf.add_page()
                    pdf.cell(0, 4.4, self._plain(b[1]), new_x="LMARGIN", new_y="NEXT")
                    pdf.set_text_color(*TEXT)
                elif kind == "p":
                    pdf.para(self._plain(b[1]), size=7.0, h=3.7)
                elif kind == "ul":
                    pdf.bullets([self._plain(x) for x in b[1]], size=7.0, h=3.7)
                elif kind == "f":
                    pdf.set_font(pdf.font_name, "B", 7.2)
                    pdf.set_fill_color(*LIGHT)
                    pdf.multi_cell(182, 4.0, "  " + self._plain(b[2]), fill=True, new_x="LMARGIN", new_y="NEXT")
                    if b[3]:
                        pdf.set_font(pdf.font_name, "", 6.6)
                        pdf.set_text_color(*MUTED)
                        pdf.multi_cell(182, 3.4, "  " + self._plain(b[3]), new_x="LMARGIN", new_y="NEXT")
                        pdf.set_text_color(*TEXT)
                    pdf.ln(0.6)
                elif kind == "t":
                    self._pdf_table_auto(pdf, b[1], b[2])
                    pdf.ln(0.8)
                elif kind == "note":
                    pdf.para(self._plain(b[1]), size=6.6, color=MUTED, h=3.4)

    def _render_symbol_explain(self, pdf: EquityReportPDF, data: dict, a: dict):
        from core import thuyet_minh as tc
        raw = a.get("raw_analysis")
        if not raw:
            return
        ex = tc.explain_symbol(raw)
        pdf.h3(f"C. Giải trình định giá & khuyến nghị cho {data.get('ticker', '')}", min_space=50)
        for title, key in (("C.1  Giá mục tiêu được tính thế nào", "valuation"),
                           ("C.2  Vì sao ra khuyến nghị này", "recommendation"),
                           ("C.3  Điểm cơ hội 5 trụ cột", "pillars")):
            steps = ex.get(key) or []
            if not steps:
                continue
            if pdf.get_y() > pdf.h - pdf.b_margin - 25:
                pdf.add_page()
            pdf.set_font(pdf.font_name, "B", 8.2)
            pdf.set_text_color(*NAVY)
            pdf.cell(0, 5, title, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*TEXT)
            pdf.set_font(pdf.font_name, "", 7.2)
            for j, st_ in enumerate(steps, 1):
                txt = self._plain(st_).replace("✅", "[Đạt]").replace("❌", "[Không]")
                pdf.multi_cell(182, 3.8, f"{j}. {txt}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

    # ─────────────────────────────────────────────────────────────────────────
    # Tiền xử lý dữ liệu – CHỈ dùng số liệu thật từ kết quả StockService.
    # Thiếu dữ liệu -> None -> hiển thị "N/A"; tuyệt đối không tự sinh số giả định.
    # ─────────────────────────────────────────────────────────────────────────

    _LABELS = {
        "fundamental": {
            "roe": ("ROE", "%"), "revenue_growth": ("Tăng trưởng doanh thu", "%"),
            "margin": ("Biên LN ròng", "%"), "debt": ("Nợ/VCSH", "x"),
            "cashflow": ("Dòng tiền HĐKD (CFO)", "cfo"),
            "earnings_quality": ("Chất lượng lợi nhuận (điều chỉnh)", "eq"),
        },
        "valuation": {"pe": ("P/E", "x"), "pb": ("P/B", "x"),
                      "expected_return": ("Tổng LN kỳ vọng 12T (định giá lai)", "%")},
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
            "volatility": ("Biến động năm hóa", "vol"), "drawdown": ("Sụt giảm tối đa 1 năm (MDD)", "mdd"),
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
            if key == "earnings_quality":
                flags = comp.get("flags") or []
                rows.append({"name": name, "value": comp.get("verdict") or "—", "ok": not pts, "pts": pts, "max": 0,
                             "note": (flags[0] if flags else "Không có cảnh báo") + (f" (+{len(flags) - 1} cảnh báo khác)"
                                                                                   if len(flags) > 1 else "")})
                continue
            if pts is None:
                value, note, ok = ("—", comp["note"], None) if comp.get("note") else ("N/A", "Thiếu dữ liệu", None)
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
                ok = (pts / mx >= 0.6) if mx else None      # "đạt" khi ≥ 60% điểm tối đa (5/10 không còn tính là đạt)
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
        wait_buy = False

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
            # Không tự suy khuyến nghị bằng hệ thống cũ (ngưỡng ±15% / điểm tổng hợp) khi thiếu kết quả mô hình 12T
            from core.khuyen_nghi import not_enough_basis
            recd = not_enough_basis("Không có kết quả mô hình định giá & khuyến nghị 12 tháng → chưa đủ cơ sở khuyến nghị.")
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
                    from core.pipeline import StockService
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
        _ml = (inv or {}).get("multilayer") or None
        if inv and fv.get("model") == "12m":
            meth = "; ".join(f"{m['name']} → {m['fair']:,.0f} ({m['weight'] * 100:.0f}%)" for m in fv.get("methods", []))
            if fv.get("available"):
                comments.append(
                    f"Định giá: giá mục tiêu {fv['target_12m']:,.0f} VND/cp ({meth}), upside {fv['upside']:+.1f}% so với "
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
            (f"Khuyến nghị: {_ml['label']} – điểm cơ bản F {_n(_ml.get('F'), 0)}, điểm so với thị trường R {_n(_ml.get('R'), 0)} "
             "(khung khuyến nghị đa lớp)." if _ml else
             f"Khuyến nghị: {rec} (không chạy được khung khuyến nghị đa lớp)."),
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
        try:
            from core.tin_tuc import classify_sentiment, is_relevant
        except Exception:                                    # noqa: BLE001
            is_relevant, classify_sentiment = (lambda t: True), None
        rel_news = [it for it in (analysis.get("news") or []) if is_relevant(str(it.get("title", "")))]
        for it in rel_news[:10]:
            if classify_sentiment and it.get("title"):          # chấm lại theo từ điển mới (tin đã lưu từ trước)
                it = {**it, "sentiment": classify_sentiment(str(it.get("title")) + " " + str(it.get("summary") or ""))}
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
            "raw_analysis": analysis,
            "fin_q": analysis.get("financials_quarter"),
            "fv": fv, "recd": recd, "trend": trend_name, "rsi_last": rsi_last, "inv": inv,
            "last_roa": last_roa,
            "stock_info": _stock_info(p_val, px_df, fin_summary, analysis, exchange, industry),
            "key_fin": _key_fin_table(fin_wide, fin_summary.get("ratios")),
            "tech_rows": _tech_rows(px_df, idx_df, tech.get("signals") or {}, stop_p, ret_1m, ret_3m, ret_1y, rs6,
                                    wait=wait_buy),
            "profile": analysis.get("company_profile") or {},
            "company": company,
            "is_bank": bool(fin_summary.get("is_bank")),
            "price": p_val,
            "target": target_p,
            "upside": upside,
            "stop": stop_p,
            "chart_days": analysis.get("chart_days") or 365,
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
