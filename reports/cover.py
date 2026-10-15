"""
Trang bìa báo cáo PDF – nền "tảng băng" (assets/report/cover_bg.jpg, đã xóa chữ in sẵn).

Mọi chữ trên bìa được vẽ lại mỗi lần xuất bằng Pillow:
  • dòng thương hiệu STOCK ANALYTICS PRO + khẩu hiệu
  • "BÁO CÁO PHÂN TÍCH CỔ PHIẾU"
  • MÃ CỔ PHIẾU cỡ lớn (đổi theo mã đang chọn) có hiệu ứng phát sáng
  • tên doanh nghiệp (rút gọn "Công ty Cổ phần" → "CTCP")
  • khung ngày & giờ xuất báo cáo + phiên dữ liệu ở cuối trang
"""
from __future__ import annotations

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


def render_cover(symbol: str, company_name: str = "", exported_at: Optional[datetime] = None,
                 session_date: str = "", exchange: str = "", industry: str = "") -> bytes:
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
    _centered_tracked(img, 46 * S, "STOCK ANALYTICS PRO", _font("SemiBold", 15), (235, 243, 255, 235),
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
    x0, y0 = (W - pw) / 2, 1404 * S
    _rounded_panel(img, (x0, y0, x0 + pw, y0 + 64 * S), 18 * S, fill=(8, 22, 48, 165),
                   outline=(110, 180, 255, 150), width=max(1, int(1.2 * S)))
    _centered_tracked(img, y0 + 27 * S, line1, f1, (255, 255, 255, 255), tracking=2.2 * S)
    ImageDraw.Draw(img).text((W / 2, y0 + 49 * S), line2, font=f2, fill=(170, 205, 245, 235), anchor="ms")
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90, optimize=True)
    return buf.getvalue()
