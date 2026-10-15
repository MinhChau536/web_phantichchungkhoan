"""
core/tai_lieu_bctc.py – gộp từ 4 module (15/10/2026).

MỤC LỤC
  • data/pdf_ocr.py – OCR cho PDF scan (không có lớp chữ) – tùy chọn, chạy hoàn toàn trên máy (không gửi file đi đâu).
      hàm/lớp chính: ocr_available, boxes_to_lines, ocr_pdf_pages
  • data/pdf_financial_extractor.py – Trích số liệu BCTC từ file PDF theo MÃ SỐ chuẩn của mẫu biểu VAS
      hàm/lớp chính: read_pdf_text, parse_money, detect_unit, split_statements, extract_statement, is_bank_statement, extract_bank_by_label, normalize_ocr_line, normalize_ocr_text, extract_financials, to_wide
  • services/zenodo_source.py – Kho Báo cáo thường niên trên Zenodo (~14.000 file PDF, 2000–2025), record 20949551.
      hàm/lớp chính: HTTPRangeFile, load_index, list_reports, make_url, parse_url, fetch_pdf
  • services/document_service.py – Kho tài liệu doanh nghiệp: Báo cáo thường niên (BCTN) & BCTC dạng PDF theo năm.
      hàm/lớp chính: classify_document, normalize_doc_url, url_candidates, period_key_for, extract_links_from_html, extract_links_from_json, VietstockDocs, CafefDocs, VietstockStaticDocs, CompanyWebsiteDocs, DocumentService

Tên trùng giữa các phần đã được đổi (tên cũ → tên mới trong file này):
  document_service._HEADERS → _HEADERS_document_service
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: data/pdf_ocr.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
OCR cho PDF scan (không có lớp chữ) – tùy chọn, chạy hoàn toàn trên máy (không gửi file đi đâu).

Thư viện (cài thêm khi cần):  pip install rapidocr_onnxruntime pypdfium2
  • pypdfium2           : dựng ảnh từng trang PDF
  • rapidocr_onnxruntime: nhận dạng chữ (mô hình PP-OCR kèm sẵn trong gói, không cần tải thêm,
                          không cần cài Tesseract). Mô hình không có dấu tiếng Việt nhưng đọc tốt
                          chữ số, mã số và chữ Latin – đủ cho việc trích số liệu BCTC (so khớp bỏ dấu).

Kết quả trả về là văn bản từng trang, mỗi dòng ghép từ các ô chữ cùng hàng (trái → phải),
để đưa thẳng vào bộ trích theo mã số VAS như PDF có lớp chữ.
"""


import logging
from statistics import median
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)
_ENGINE = None

INSTALL_HINT = "pip install rapidocr_onnxruntime pypdfium2"


def ocr_available() -> bool:
    try:
        import pypdfium2  # noqa: F401
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except Exception:
        return False


def _engine():
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR()
    return _ENGINE


def boxes_to_lines(result) -> List[str]:
    """[[box(4 điểm), text, score], ...] → các dòng văn bản (gom theo tâm dọc, sắp trái → phải)."""
    items = []
    for box, text, *_ in result or []:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append(((min(ys) + max(ys)) / 2, min(xs), max(ys) - min(ys), str(text).strip()))
    if not items:
        return []
    tol = 0.55 * median(h for _, _, h, _ in items)
    items.sort(key=lambda t: t[0])
    rows: List[List[tuple]] = []
    for it in items:
        if rows and abs(it[0] - rows[-1][-1][0]) <= tol:
            rows[-1].append(it)
        else:
            rows.append([it])
    return ["  ".join(t for _, _, _, t in sorted(r, key=lambda t: t[1]) if t) for r in rows]


def ocr_pdf_pages(data: bytes, max_pages: int = 25, dpi: int = 200,
                  progress: Optional[Callable[[int, int], None]] = None,
                  stop_when: Optional[Callable[[List[str]], bool]] = None) -> List[str]:
    """Văn bản OCR từng trang. stop_when(các trang đã đọc) = True thì dừng sớm (đã đủ 3 báo cáo)."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(data)
    n = min(len(pdf), max_pages)
    eng = _engine()
    pages: List[str] = []
    for i in range(n):
        img = pdf[i].render(scale=dpi / 72).to_pil().convert("RGB")
        import numpy as np
        result, _ = eng(np.array(img))
        pages.append("\n".join(boxes_to_lines(result)))
        if progress:
            progress(i + 1, n)
        if stop_when and stop_when(pages):
            break
    pdf.close()
    return pages


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: data/pdf_financial_extractor.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Trích số liệu BCTC từ file PDF theo MÃ SỐ chuẩn của mẫu biểu VAS
(Thông tư 200/2014/TT-BTC và 202/2014/TT-BTC cho BCTC hợp nhất).

Cách làm:
  1. Đọc lớp chữ của PDF; PDF scan / lỗi phông → OCR (core/tai_lieu_bctc.py, nếu đã cài thư viện).
     BCTC ngân hàng (không có cột mã số) → nhận diện theo nhãn chỉ tiêu (BANK_LABELS).
  2. Chia văn bản theo 3 báo cáo nhờ tiêu đề: Bảng cân đối kế toán / Báo cáo tình hình tài chính,
     Báo cáo kết quả hoạt động kinh doanh, Báo cáo lưu chuyển tiền tệ. Dừng ở phần Thuyết minh.
  3. Trong từng báo cáo, tìm dòng chứa mã số chuẩn VÀ nhãn khớp từ khóa của mã đó
     (vd mã 10 trong KQKD phải có chữ "doanh thu") rồi lấy số tiền đầu tiên sau mã = kỳ này.
  4. Đọc "Đơn vị tính" để quy về VND. Kiểm tra Tổng tài sản = Nợ phải trả + VCSH.
"""


import io
import math
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from core.du_lieu import strip_accents

# mã số -> (chỉ tiêu chuẩn, từ khóa bắt buộc trong nhãn (bỏ dấu)).
# Mọi từ khóa trong danh sách đều phải có; "a|b" nghĩa là có a HOẶC b.
VAS_CODES: Dict[str, Dict[str, Tuple[str, List[str]]]] = {
    "is": {
        "10": ("revenue", ["doanh thu thuan"]),
        "11": ("cogs", ["gia von"]),
        "20": ("gross_profit", ["loi nhuan gop"]),
        "21": ("financial_income", ["doanh thu hoat dong tai chinh"]),
        "22": ("financial_expense", ["chi phi tai chinh"]),
        "23": ("interest_expense", ["lai vay"]),
        "25": ("selling_expense", ["ban hang"]),
        "26": ("admin_expense", ["quan ly"]),
        "30": ("operating_profit", ["loi nhuan thuan", "hoat dong kinh doanh"]),
        "50": ("profit_before_tax", ["truoc thue"]),
        "51": ("income_tax", ["thue"]),
        "60": ("net_income", ["sau thue"]),
        "61": ("net_income_parent", ["cong ty me"]),
        "62": ("minority_profit", ["khong kiem soat|thieu so"]),
        "70": ("eps", ["lai co ban"]),
    },
    "bs": {
        "100": ("current_assets", ["ngan han"]),
        "110": ("cash", ["tien"]),
        "120": ("short_term_investments", ["dau tu tai chinh ngan han"]),
        "130": ("receivables", ["phai thu"]),
        "140": ("inventory", ["hang ton kho"]),
        "220": ("fixed_assets", ["tai san co dinh"]),
        "270": ("total_assets", ["tong", "tai san"]),
        "300": ("total_liabilities", ["no phai tra"]),
        "310": ("current_liabilities", ["no ngan han"]),
        "311": ("payables", ["nguoi ban"]),
        "320": ("short_term_debt", ["vay"]),
        "330": ("long_term_liabilities", ["no dai han"]),
        "338": ("long_term_debt", ["vay"]),
        "400": ("equity", ["von chu so huu"]),
        "411": ("charter_capital", ["von gop|von dau tu|von co phan"]),
        "421": ("retained_earnings", ["chua phan phoi"]),
        "429": ("minority_interest", ["khong kiem soat|thieu so"]),
        "440": ("total_liabilities_and_equity", ["tong", "nguon von"]),
    },
    "cf": {
        "02": ("depreciation", ["khau hao"]),
        "20": ("cfo", ["luu chuyen tien thuan", "kinh doanh"]),
        "21": ("capex", ["mua sam"]),
        "30": ("cfi", ["luu chuyen tien thuan", "dau tu"]),
        "36": ("dividends_paid", ["co tuc"]),
        "40": ("cff", ["luu chuyen tien thuan", "tai chinh"]),
    },
}

_HEADINGS = [
    ("bs", ["BANG CAN DOI KE TOAN", "BAO CAO TINH HINH TAI CHINH"]),
    ("is", ["KET QUA HOAT DONG KINH DOANH"]),
    ("cf", ["LUU CHUYEN TIEN TE"]),
    ("notes", ["THUYET MINH BAO CAO TAI CHINH", "BAN THUYET MINH"]),
]
_MONEY_RE = re.compile(
    r"\(?-?\d{1,3}(?:[.,]\d{3})+\)?"          # 1.234.567 hoặc (1.234)
    r"|\(\d{1,3}\)"                             # (720) – số âm nhỏ trong ngoặc
    r"|(?<![\w.,])0(?![\w.,])"                   # 0
    r"|(?<![\w.,])\(?-?\d{4,}\)?(?![\w.,])"     # 1234567 không phân tách
)


def read_pdf_text(data: bytes, max_pages: int = 80) -> List[str]:
    """Văn bản từng trang (cần thư viện pypdf)."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for i, page in enumerate(reader.pages):
        if i >= max_pages:
            break
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return pages


def parse_money(token: str) -> Optional[float]:
    neg = token.startswith("(") and token.endswith(")") or token.startswith("-")
    digits = re.sub(r"[^\d]", "", token)
    if not digits:
        return None
    v = float(digits)
    return -v if neg else v


def detect_unit(text: str) -> float:
    t = strip_accents(text.lower())
    m = re.search(r"don vi(?: tinh)?\s*[:：]?\s*([a-z ]{2,20})", t)
    unit = m.group(1) if m else ""
    if "trieu" in unit:
        return 1e6
    if "nghin" in unit or "ngan" in unit:
        return 1e3
    if "ty" in unit.split()[:1]:
        return 1e9
    return 1.0


def split_statements(pages: List[str]) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {"bs": [], "is": [], "cf": []}
    current: Optional[str] = None
    for page in pages:
        for line in page.splitlines():
            plain = strip_accents(line).upper()
            compact = re.sub(r"[^A-Z]", "", plain)
            for key, heads in _HEADINGS:
                if any(h in plain or h.replace(" ", "") in compact for h in heads) and len(plain) < 120:
                    current = key
                    break
            if current in sections:
                sections[current].append(line)
    return sections


def extract_statement(lines: List[str], statement: str) -> Dict[str, float]:
    codes = VAS_CODES[statement]
    found: Dict[str, float] = {}
    for line in lines:
        money = list(_MONEY_RE.finditer(line))
        if not money:
            continue
        head = line[:money[0].start()]
        label_plain = strip_accents(head.lower())
        for tok in re.finditer(r"(?<![\w.,])(\d{2,3})(?![\w.,])", head):
            code = tok.group(1)
            if code not in codes:
                continue
            key, kws = codes[code]
            if key in found:
                continue
            label_part = label_plain[:tok.start()] + " " + label_plain[tok.end():]
            compact = re.sub(r"[^a-z]", "", label_part)          # OCR hay dính/mất khoảng trắng
            if all(any(alt in label_part or alt.replace(" ", "") in compact for alt in kw.split("|")) for kw in kws):
                v = parse_money(money[0].group(0))
                if v is not None:
                    found[key] = v
                break
    return found


# BCTC ngân hàng (mẫu TCTD) không có cột "Mã số" → nhận diện theo nhãn chỉ tiêu (bỏ dấu, bỏ khoảng trắng).
# (chỉ tiêu, các nhãn chấp nhận, các cụm loại trừ)
BANK_LABELS: List[Tuple[str, List[str], List[str]]] = [
    ("total_assets", ["tongtaisan"], ["tongtaisanco", "nophaitra"]),
    ("customer_loans", ["chovaykhachhang"], ["duphong", "lai", "thu"]),
    ("customer_deposits", ["tienguicuakhachhang"], ["lai"]),
    ("total_liabilities", ["tongnophaitra"], ["vonchusohuu"]),
    ("equity", ["tongvonchusohuu", "vonchusohuu"], ["nophaitra", "loiich", "khac"]),
    ("charter_capital", ["vondieule"], []),
    ("net_interest_income", ["thunhaplaithuan"], []),
    ("total_operating_income", ["tongthunhaphoatdong"], []),
    ("provision_expense", ["chiphiduphongruirotindung"], []),
    ("profit_before_tax", ["tongloinhuantruocthue", "loinhuantruocthue"], ["chiphi"]),
    ("income_tax", ["chiphithuethunhapdoanhnghiep"], ["hoanlai"]),
    ("net_income", ["loinhuansauthue"], ["chuaphanphoi", "congtyme", "khongkiemsoat", "thieuso"]),
    ("net_income_parent", ["loinhuansauthuecuacodongcuangannhangme", "codongcuacongtyme", "codongcuanganhangme"], []),
    ("eps", ["laicobantrencophieu"], ["suygiam"]),
]


_ROMAN_PREFIX = re.compile(r"^\s*(?:[IVXLl1]{1,5}|[A-Ha-h]|\d{1,2})\s*[.)]\s*")


def _fuzzy_starts(head: str, label: str, threshold: float = 0.84) -> bool:
    """head bắt đầu bằng label, chấp nhận vài lỗi nhận dạng OCR (vd 'truec' ~ 'truoc', 'huru' ~ 'huu')."""
    if head.startswith(label):
        return True
    if len(head) < len(label) - 2:
        return False
    from difflib import SequenceMatcher
    return max(SequenceMatcher(None, head[:len(label) + d], label).ratio() for d in (-1, 0, 1, 2)) >= threshold


def is_bank_statement(text: str) -> bool:
    t = re.sub(r"[^a-z]", "", strip_accents(text.lower()))
    return sum(k in t for k in ("chovaykhachhang", "tienguicuakhachhang", "thunhaplaithuan",
                                "ngannhangnhanuoc", "nganhangnhanuoc")) >= 2


def extract_bank_by_label(lines: List[str]) -> Dict[str, float]:
    found: Dict[str, float] = {}
    for line in lines:
        money = list(_MONEY_RE.finditer(line))
        if not money:
            continue
        raw = _ROMAN_PREFIX.sub("", line[:money[0].start()])       # bỏ "I.", "Vlll.", "A.", "1." đầu dòng
        head = re.sub(r"[^a-z]", "", strip_accents(raw.lower()))
        for key, labels, excl in BANK_LABELS:
            if key in found:
                continue
            if any(_fuzzy_starts(head, lb) for lb in labels) and not any(e in head for e in excl):
                v = parse_money(money[0].group(0))
                if v is not None:
                    found[key] = v
                break
    return found


_AMOUNT_TOKEN = r"(?:\(?-?\d{1,3}(?:[.,]\d{3})+\)?|\(\d{1,3}\))"
_AMOUNT_RUN = re.compile(f"(?:{_AMOUNT_TOKEN})+")
_NOTE_REF = re.compile(r"^[IVXLlvi]{1,4}\.(\d{1,2})")


def _all_codes() -> set:
    codes = {c for st in VAS_CODES.values() for c in st}
    return codes | {"01", "02"}


def normalize_ocr_line(line: str, codes: Optional[set] = None) -> str:
    """
    Tách phần số bị OCR dán liền: 'tien110V.17.1206.010' → 'tien 110 V.1 7.120 6.010'.
    Thử từng vị trí bắt đầu dãy số: [mã số VAS]? [số thuyết minh]? rồi các số tiền đúng định dạng nhóm 3 chữ số.
    """
    codes = codes or _all_codes()
    starts = [m.start() for m in re.finditer(r"(?<!\d)\d", line)]
    for p in starts:
        sraw = line[p:].replace(" ", "")
        cands = []
        for code in [sraw[:3], sraw[:2], ""]:
            if code and code not in codes:
                continue
            rest = sraw[len(code):]
            notes = [("", rest)]
            m = _NOTE_REF.match(rest)
            if m:
                pre = rest[:m.start(1)]
                digits = m.group(1)
                notes = [(pre + digits[:k], rest[len(pre) + k:]) for k in (1, 2) if k <= len(digits)] + notes
            for note, amounts in notes:
                if amounts and _AMOUNT_RUN.fullmatch(amounts):
                    toks = re.findall(_AMOUNT_TOKEN, amounts)
                    cands.append((code, note, toks))
        if cands:
            def score(c):
                vals = [abs(parse_money(t) or 0) for t in c[2][:2]]
                gap = abs(math.log(vals[0] / vals[1])) if len(vals) == 2 and min(vals) > 0 else 0.0
                return (gap, 0 if c[0] else 1)          # 2 kỳ gần nhau nhất; ưu tiên có mã số
            code, note, toks = min(cands, key=score)
            head = line[:p].rstrip()
            return " ".join(x for x in [head, code, note, *toks] if x)
    return line


def normalize_ocr_text(pages: List[str]) -> List[str]:
    codes = _all_codes()
    return ["\n".join(normalize_ocr_line(ln, codes) for ln in pg.splitlines()) for pg in pages]


def _past_statements(pages: List[str]) -> bool:
    """Đã đọc qua báo cáo lưu chuyển tiền tệ và sang phần thuyết minh → đủ để dừng OCR."""
    plain = strip_accents("\n".join(pages)).upper()
    i = plain.rfind("LUU CHUYEN TIEN TE")
    return i >= 0 and "THUYET MINH" in plain[i:]


def _parse(pages: List[str]) -> Tuple[Dict[str, float], float, bool]:
    full = "\n".join(pages)
    unit = detect_unit(full)
    sections = split_statements(pages)
    values: Dict[str, float] = {}
    for st in ("is", "bs", "cf"):
        for k, v in extract_statement(sections[st], st).items():
            values[k] = v
    bank = is_bank_statement(full)
    if bank:
        lines = sections["bs"] + sections["is"] + sections["cf"] or full.splitlines()
        for k, v in extract_bank_by_label(lines).items():
            values.setdefault(k, v)
    values = {k: v * (unit if k != "eps" else 1.0) for k, v in values.items()}
    return values, unit, bank


def extract_financials(data: bytes, use_ocr: bool = True,
                       progress: Optional[Any] = None) -> Dict[str, Any]:
    """
    Trả về {"values": {chỉ tiêu: giá trị VND}, "unit": hệ số, "checks": {...}, "pages": n,
            "text_found": bool, "method": "text" | "ocr", "bank": bool}
    PDF scan (không có lớp chữ) hoặc chữ bị lỗi phông → tự chạy OCR nếu đã cài thư viện OCR.
    """
    from core.tai_lieu_bctc import INSTALL_HINT, ocr_available, ocr_pdf_pages
    pages = read_pdf_text(data)
    method = "text"
    has_text = len("\n".join(pages).strip()) >= 200
    values, unit, bank = _parse(pages) if has_text else ({}, None, False)

    if len(values) < 3 and use_ocr:
        if ocr_available():
            try:
                ocr_pages = normalize_ocr_text(ocr_pdf_pages(data, progress=progress, stop_when=_past_statements))
                o_values, o_unit, o_bank = _parse(ocr_pages)
                if len(o_values) > len(values):
                    values, unit, bank, pages, method = o_values, o_unit, o_bank, ocr_pages, "ocr"
                    has_text = True
            except Exception as exc:          # OCR lỗi thì giữ kết quả lớp chữ
                return {"values": values, "unit": unit, "checks": {}, "pages": len(pages), "text_found": has_text,
                        "method": method, "bank": bank, "note": f"OCR gặp lỗi: {exc}"}
        elif not has_text:
            return {"values": {}, "unit": None, "checks": {}, "pages": len(pages), "text_found": False,
                    "method": method, "bank": False,
                    "note": "PDF không có lớp chữ (bản scan). Cài thư viện OCR để đọc file scan: "
                            f"`{INSTALL_HINT}` rồi khởi động lại app."}

    checks = {}
    ta, tle = values.get("total_assets"), values.get("total_liabilities_and_equity")
    if ta and values.get("total_liabilities") is not None and values.get("equity") is not None:
        diff = abs(ta - values["total_liabilities"] - values["equity"]) / abs(ta)
        checks["balance_identity"] = diff < 0.01
    if ta and tle:
        checks["assets_equal_sources"] = abs(ta - tle) / abs(ta) < 0.001
    values.pop("total_liabilities_and_equity", None)
    values.pop("minority_profit", None)
    out = {"values": values, "unit": unit, "checks": checks, "pages": len(pages), "text_found": has_text,
           "method": method, "bank": bank}
    if not values:
        out["note"] = ("Không nhận ra chỉ tiêu nào – có thể file không phải BCTC chính (vd chỉ có thuyết minh) "
                       "hoặc bố cục khác mẫu chuẩn.")
    return out


def to_wide(records: List[Tuple[int, Dict[str, float]]]) -> pd.DataFrame:
    """[(khóa kỳ, values)] -> bảng rộng canonical."""
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame({k: v for k, v in records}).T
    df.index = df.index.astype(int)
    df.index.name = "period_key"
    return df.sort_index()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: services/zenodo_source.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Kho Báo cáo thường niên trên Zenodo (~14.000 file PDF, 2000–2025), record 20949551.

Cách lấy 1 file mà KHÔNG tải cả kho ZIP nhiều GB: mở file ZIP từ xa bằng HTTP Range
(chỉ đọc phần mục lục ở cuối ZIP và đúng khối dữ liệu của file cần lấy).
Ý tưởng và chỉ mục (data/bundled/zenodo_bctn_index.parquet) lấy từ dự án vn-annual-report-miner
(Trương Minh Quân, giấy phép MIT – data/bundled/LICENSE_vn-annual-report-miner.txt); mã được viết gọn lại.
"""


import io
import logging
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

RECORD_ID = "20949551"
RECORD_URL = f"https://zenodo.org/records/{RECORD_ID}"
FILES_URL = f"https://zenodo.org/api/records/{RECORD_ID}/files"
ARCHIVES = {
    "2000_2005": "vn_bctn_2000_2005.zip", "2006_2010": "vn_bctn_2006_2010.zip",
    "2011_2015": "vn_bctn_2011_2015.zip", "2016_2020": "vn_bctn_2016_2020.zip",
    "2021_2025": "vn_bctn_2021_2025.zip",
}
INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "bundled" / "zenodo_bctn_index.parquet"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0 Safari/537.36",
            "Accept-Encoding": "identity"}


class HTTPRangeFile(io.RawIOBase):
    """File đọc-được-tìm-kiếm (seekable) trên HTTP Range, đệm theo khối – đủ để zipfile đọc ZIP từ xa."""

    def __init__(self, url: str, session: Optional[requests.Session] = None, block: int = 1 << 20,
                 timeout: float = 30):
        self.url, self.block, self.timeout = url, block, timeout
        self.s = session or requests.Session()
        self.pos, self._cache = 0, {}
        r = self.s.get(url, headers={**_HEADERS, "Range": "bytes=0-0"}, timeout=timeout)
        if r.status_code not in (200, 206):
            raise IOError(f"HTTP {r.status_code} khi mở {url}")
        cr = r.headers.get("Content-Range", "")
        self.size = int(cr.split("/")[-1]) if "/" in cr else int(r.headers.get("Content-Length", 0))
        if r.status_code == 200 and "/" not in cr:
            raise IOError("Máy chủ không hỗ trợ tải theo khoảng (Range)")

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        base = {0: 0, 1: self.pos, 2: self.size}[whence]
        self.pos = max(0, min(base + offset, self.size))
        return self.pos

    def _blk(self, i: int) -> bytes:
        if i not in self._cache:
            start = i * self.block
            end = min(start + self.block, self.size) - 1
            r = self.s.get(self.url, headers={**_HEADERS, "Range": f"bytes={start}-{end}"}, timeout=self.timeout)
            r.raise_for_status()
            if len(self._cache) > 64:
                self._cache.clear()
            self._cache[i] = r.content
        return self._cache[i]

    def readinto(self, b) -> int:
        n = 0
        while n < len(b) and self.pos < self.size:
            data = self._blk(self.pos // self.block)
            off = self.pos % self.block
            chunk = data[off: off + len(b) - n]
            if not chunk:
                break
            b[n: n + len(chunk)] = chunk
            n += len(chunk)
            self.pos += len(chunk)
        return n


@lru_cache(maxsize=1)
def load_index() -> pd.DataFrame:
    if not INDEX_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(INDEX_PATH)
    return df[df.get("status", "ok") == "ok"] if "status" in df.columns else df


def list_reports(symbol: str) -> List[Dict]:
    """Các BCTN của mã trong kho Zenodo: [{year, archive_period, relative_path, size_mb}], năm mới trước."""
    idx = load_index()
    if idx.empty:
        return []
    sub = idx[(idx["ticker_folder"].str.upper() == symbol.upper()) & (idx["archive_period"].isin(ARCHIVES))]
    sub = sub.sort_values("year_full", ascending=False).drop_duplicates("year_full")
    return [{"year": int(r.year_full), "archive_period": r.archive_period, "relative_path": r.relative_path,
             "size_mb": float(r.file_size_mb)} for r in sub.itertuples()]


def make_url(archive_period: str, relative_path: str) -> str:
    return f"zenodo://{archive_period}/{relative_path}"


def parse_url(url: str):
    rest = url[len("zenodo://"):]
    archive, rel = rest.split("/", 1)
    return archive, rel


def fetch_pdf(archive_period: str, relative_path: str, session: Optional[requests.Session] = None,
              base_url: Optional[str] = None) -> bytes:
    """Lấy nội dung 1 file PDF trong kho ZIP trên Zenodo (base_url dùng cho kiểm thử)."""
    zip_name = ARCHIVES.get(archive_period)
    if not zip_name:
        raise ValueError(f"Không có kho cho giai đoạn {archive_period}")
    url = f"{base_url or FILES_URL}/{zip_name}/content"
    with zipfile.ZipFile(HTTPRangeFile(url, session=session)) as zf:
        want = relative_path.replace("\\", "/").lstrip("/").lower()
        name = next((n for n in zf.namelist() if n.replace("\\", "/").lower().endswith(want)), None)
        if name is None:
            base = Path(want).name
            name = next((n for n in zf.namelist() if Path(n).name.lower() == base), None)
        if name is None:
            raise FileNotFoundError(f"{relative_path} không có trong {zip_name}")
        return zf.read(name)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: services/document_service.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Kho tài liệu doanh nghiệp: Báo cáo thường niên (BCTN) & BCTC dạng PDF theo năm.

Nguồn tìm tài liệu (theo settings.DOCUMENT_SOURCES, có thể đổi thứ tự):
  - vietstock : trang "Tải tài liệu" của mã trên finance.vietstock.vn
  - cafef     : trang/endpoint tài liệu của CafeF (chỉ có BCTC)
  - vietstock_static : kho file tĩnh Vietstock – Báo cáo thường niên theo năm
  - website   : trang Quan hệ cổ đông / Nhà đầu tư trên website doanh nghiệp (lấy từ hồ sơ công ty)
  - upload    : người dùng tự tải file lên (luôn hoạt động)
Tất cả đều là đọc trang web công khai → có thể hỏng khi trang đổi cấu trúc; khi đó
người dùng vẫn tải tay hoặc dán link PDF trực tiếp.

Mỗi tài liệu được phân loại tự động (BCTN / BCTC năm / bán niên / quý, hợp nhất / riêng)
và gắn năm, lưu tại data/documents/<MÃ>/ và ghi chỉ mục vào DuckDB.
"""


import hashlib
import ipaddress
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests

from core.cau_hinh import settings
from core.du_lieu import Database
from core.du_lieu import strip_accents


logger = logging.getLogger(__name__)

DOC_TYPES = {
    "annual_report": "Báo cáo thường niên",
    "fs_annual": "BCTC năm (kiểm toán)",
    "fs_semiannual": "BCTC bán niên (soát xét)",
    "fs_quarterly": "BCTC quý",
    "other": "Tài liệu khác",
}
_HEADERS_document_service = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.6",
}
_DOC_EXT = (".pdf", ".zip", ".rar", ".doc", ".docx", ".xls", ".xlsx")
_INVESTOR_HINTS = ("quan-he-co-dong", "quan-he-nha-dau-tu", "nha-dau-tu", "co-dong", "investor",
                   "ir", "bao-cao", "tai-lieu", "cong-bo-thong-tin", "shareholder")


def _safe_download_url(url: str) -> str:
    """Reject URL có thể đọc file/mạng nội bộ; kiểm tra lại sau redirect."""
    try:
        parsed = urlparse(str(url).strip())
        host = (parsed.hostname or "").lower().rstrip(".")
    except ValueError as exc:
        raise ValueError("URL tài liệu không hợp lệ") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not host:
        raise ValueError("Chỉ hỗ trợ URL http/https tuyệt đối")
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("Không cho phép tải tài liệu từ máy nội bộ")
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        address = None
    if address and not address.is_global:
        raise ValueError("Không cho phép tải tài liệu từ địa chỉ mạng riêng")
    return parsed.geturl()


def _read_limited_response(resp: requests.Response) -> bytes:
    """Đọc response theo luồng, dừng trước khi RAM/ổ đĩa bị lấp bởi file quá lớn."""
    limit = settings.MAX_DOCUMENT_BYTES
    content_length = resp.headers.get("Content-Length") if hasattr(resp, "headers") else None
    if content_length:
        try:
            if int(content_length) > limit:
                raise ValueError(f"Tài liệu vượt giới hạn {limit // (1024 * 1024)} MiB")
        except ValueError as exc:
            if "vượt giới hạn" in str(exc):
                raise
    chunks, total = [], 0
    iterator = resp.iter_content(chunk_size=256 * 1024) if hasattr(resp, "iter_content") else [resp.content]
    for chunk in iterator:
        if not chunk:
            continue
        total += len(chunk)
        if total > limit:
            raise ValueError(f"Tài liệu vượt giới hạn {limit // (1024 * 1024)} MiB")
        chunks.append(chunk)
    return b"".join(chunks)


# ─────────────────────────────────────────────────────────────────────────────
# Phân loại tài liệu
# ─────────────────────────────────────────────────────────────────────────────

def classify_document(title: str, url: str = "") -> Dict[str, Any]:
    """Suy loại tài liệu, năm, quý, hợp nhất/riêng từ tiêu đề + đường dẫn."""
    text = strip_accents(f"{title} {url}".lower()).replace("_", " ").replace("-", " ")
    doc_type = "other"
    if re.search(r"bao cao thuong nien|annual report|\bbctn\b", text):
        doc_type = "annual_report"
    elif re.search(r"bao cao tai chinh|financial statement|\bbctc\b|\bfs\b", text):
        if re.search(r"ban nien|soat xet|6 thang|semi|interim|giua nien do", text):
            doc_type = "fs_semiannual"
        elif re.search(r"\bquy\s*[1-4]\b|\bq\s*[1-4]\b|quarter", text):
            doc_type = "fs_quarterly"
        else:
            doc_type = "fs_annual"
    years = [int(y) for y in re.findall(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)", text) if int(y) <= datetime.now().year]
    q = re.search(r"(?:quy|q)\s*([1-4])\b", text)
    return {
        "doc_type": doc_type,
        "year": max(years) if years else None,
        "quarter": int(q.group(1)) if (q and doc_type == "fs_quarterly") else None,
        "consolidated": None if doc_type in ("annual_report", "other") else
        (False if re.search(r"\brieng\b|cong ty me|separate", text) else True),
    }


# File BCTC/BCTN của CafeF nằm trên CDN "cafef1.mediacdn.vn"; endpoint của CafeF đôi khi trả link
# sang "cafefnew.mediacdn.vn" (hoặc đường dẫn tương đối trên cafef.vn) → mở ra "File not found".
_CAFEF_CDN = ["cafef1.mediacdn.vn", "cafefnew.mediacdn.vn"]


def _is_cafef_file(url: str) -> bool:
    u = urlparse(url or "")
    return (u.netloc in _CAFEF_CDN or u.netloc.endswith("cafef.vn")) and "/Images/Uploaded/" in u.path


def normalize_doc_url(url: Optional[str]) -> Optional[str]:
    """Đưa link file CafeF về máy chủ CDN đang phục vụ file (cafef1.mediacdn.vn)."""
    if not isinstance(url, str) or not url.strip():
        return None                      # file tải lên không có link (NaN/None)
    if not _is_cafef_file(url):
        return url
    return urlparse(url)._replace(netloc=_CAFEF_CDN[0], scheme="https").geturl()


def url_candidates(url: Optional[str]) -> List[str]:
    """Các địa chỉ thử lần lượt khi tải file (link chuẩn hóa trước, link gốc sau, rồi các CDN khác)."""
    if not isinstance(url, str) or not url.strip():
        return []
    cands = [normalize_doc_url(url), url]
    if _is_cafef_file(url):
        cands += [urlparse(url)._replace(netloc=h, scheme="https").geturl() for h in _CAFEF_CDN]
    return list(dict.fromkeys(cands))


def period_key_for(doc: Dict[str, Any]) -> Optional[int]:
    y = doc.get("year")
    if not y:
        return None
    if doc.get("doc_type") == "fs_quarterly" and doc.get("quarter"):
        return int(y) * 10 + int(doc["quarter"])
    if doc.get("doc_type") == "fs_semiannual":
        return int(y) * 10 + 2
    return int(y) * 10


def _doc_id(symbol: str, url_or_name: str) -> str:
    return hashlib.sha1(f"{symbol}|{url_or_name}".encode("utf-8")).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────────────────────
# Trích link tài liệu từ HTML / JSON
# ─────────────────────────────────────────────────────────────────────────────

def extract_links_from_html(html: str, base_url: str) -> List[Tuple[str, str]]:
    """[(tiêu đề, url tuyệt đối)] cho mọi link tới file tài liệu."""
    out: List[Tuple[str, str]] = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            title = " ".join(a.get_text(" ").split()) or a.get("title") or ""
            out.append((title, urljoin(base_url, href)))
    except Exception:
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.I | re.S):
            out.append((re.sub(r"<[^>]+>", " ", m.group(2)).strip(), urljoin(base_url, m.group(1))))
    docs = []
    for title, url in out:
        path = urlparse(url).path.lower()
        if path.endswith(_DOC_EXT) or "download" in path or "file" in path and "." in path.rsplit("/", 1)[-1]:
            docs.append((title or Path(path).name, url))
    return docs


def extract_links_from_json(payload: Any, base_url: str) -> List[Tuple[str, str]]:
    """Duyệt JSON bất kỳ, lấy các cặp (tiêu đề, link file)."""
    found: List[Tuple[str, str]] = []

    def walk(node):
        if isinstance(node, dict):
            url = next((v for k, v in node.items() if isinstance(v, str)
                        and (v.lower().split("?")[0].endswith(_DOC_EXT) or k.lower() in ("link", "url", "fileurl", "filepath"))
                        and ("/" in v)), None)
            if url:
                title = next((str(node[k]) for k in ("Title", "title", "Name", "name", "FileName", "Description", "Desc")
                              if node.get(k)), "")
                found.append((title, urljoin(base_url, url)))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(payload)
    return found


# ─────────────────────────────────────────────────────────────────────────────
# Các nguồn tìm tài liệu
# ─────────────────────────────────────────────────────────────────────────────

class _WebSource:
    name = "web"

    def __init__(self, session: requests.Session):
        self.s = session

    def _get(self, url: str, **kw) -> Optional[requests.Response]:
        try:
            r = self.s.get(url, timeout=12, **kw)
            return r if r.status_code == 200 else None
        except Exception as exc:
            logger.debug("%s GET %s failed: %s", self.name, url, exc)
            return None

    def _collect(self, url: str) -> List[Tuple[str, str]]:
        r = self._get(url)
        if r is None:
            return []
        ctype = r.headers.get("content-type", "")
        if "json" in ctype or r.text[:1] in "[{":
            try:
                return extract_links_from_json(r.json(), url)
            except Exception:
                pass
        return extract_links_from_html(r.text, url)

    def list(self, symbol: str, info: Dict[str, Any]) -> List[Tuple[str, str]]:
        raise NotImplementedError


class VietstockDocs(_WebSource):
    name = "vietstock"

    def list(self, symbol, info):
        out = []
        for url in (f"https://finance.vietstock.vn/{symbol}/tai-tai-lieu.htm",
                    f"https://finance.vietstock.vn/{symbol}/tai-lieu.htm"):
            out += self._collect(url)
        return out


class CafefDocs(_WebSource):
    name = "cafef"

    def list(self, symbol, info):
        out = []
        for url in (f"https://cafef.vn/du-lieu/Ajax/PageNew/FileBCTC.ashx?Symbol={symbol}&Type=1&Year=0",
                    f"https://s.cafef.vn/Ajax/CongTy/BaoCaoTaiChinh.aspx?sym={symbol}"):
            out += self._collect(url)
        return out


class VietstockStaticDocs(_WebSource):
    """
    Báo cáo thường niên trên kho file tĩnh của Vietstock, đường dẫn theo quy luật:
      https://static2.vietstock.vn/data/<SÀN>/<NĂM>/BCTN/VN/<MÃ>_Baocaothuongnien_<NĂM>.pdf
    Dò các năm gần nhất (song song), chỉ giữ link thật sự trả về file PDF.
    (Endpoint BCTC của CafeF không có BCTN nên cần nguồn này.)
    """
    name = "vietstock_static"
    YEARS_BACK = 10
    _EXCH = {"HOSE": "HOSE", "HSX": "HOSE", "VNINDEX": "HOSE", "HNX": "HNX", "HNXINDEX": "HNX",
             "UPCOM": "UPCOM", "UPCOMINDEX": "UPCOM"}

    def _is_pdf(self, url: str) -> bool:
        try:
            r = self.s.get(url, timeout=8, stream=True)
            ok = r.status_code == 200 and next(r.iter_content(8), b"")[:4] == b"%PDF"
            r.close()
            return ok
        except Exception:
            return False

    def list(self, symbol, info):
        from concurrent.futures import ThreadPoolExecutor
        exch = self._EXCH.get(str((info or {}).get("exchange", "")).upper())
        exchanges = [exch] if exch else ["HOSE", "HNX", "UPCOM"]
        this_year = datetime.now().year
        cands = [(y, f"https://static2.vietstock.vn/data/{ex}/{y}/BCTN/VN/{symbol}_Baocaothuongnien_{y}.pdf")
                 for y in range(this_year, this_year - self.YEARS_BACK - 1, -1) for ex in exchanges]
        with ThreadPoolExecutor(max_workers=8) as pool:
            hits = list(pool.map(lambda c: (c, self._is_pdf(c[1])), cands))
        out, years = [], set()
        for (y, url), ok in hits:
            if ok and y not in years:
                years.add(y)
                out.append((f"Báo cáo thường niên năm {y}", url))
        return out


class CompanyWebsiteDocs(_WebSource):
    """Dò trang Quan hệ cổ đông trên website doanh nghiệp (tối đa 8 trang, cùng tên miền)."""
    name = "website"

    def list(self, symbol, info):
        site = (info or {}).get("website")
        if not site:
            return []
        if not site.startswith("http"):
            site = "https://" + site.lstrip("/")
        home = self._get(site)
        if home is None:
            return []
        domain = urlparse(home.url).netloc
        docs = extract_links_from_html(home.text, home.url)
        candidates = []
        for title, url in self._all_links(home.text, home.url):
            low = strip_accents(f"{title} {url}".lower())
            if urlparse(url).netloc == domain and any(h in low for h in _INVESTOR_HINTS):
                candidates.append(url)
        for url in list(dict.fromkeys(candidates))[:8]:
            docs += self._collect(url)
        return docs

    @staticmethod
    def _all_links(html: str, base: str) -> List[Tuple[str, str]]:
        return [(re.sub(r"<[^>]+>", " ", t).strip(), urljoin(base, h))
                for h, t in re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', html, flags=re.I | re.S)]


_SOURCES = {"vietstock": VietstockDocs, "vietstock_static": VietstockStaticDocs, "cafef": CafefDocs,
            "website": CompanyWebsiteDocs}


# ─────────────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────────────

class DocumentService:

    def __init__(self, db: Optional[Database] = None, session: Optional[requests.Session] = None,
                 base_dir: Optional[Path] = None):
        self.db = db or Database()
        self.session = session or requests.Session()
        self.session.headers.update(_HEADERS_document_service)
        self.base_dir = Path(base_dir or settings.DOCUMENTS_DIR)

    def _dir(self, symbol: str) -> Path:
        d = self.base_dir / symbol.upper()
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ── Tìm tài liệu ──
    def discover(self, symbol: str, company_info: Optional[Dict[str, Any]] = None,
                 sources: Optional[Iterable[str]] = None) -> pd.DataFrame:
        symbol = symbol.upper()
        report: List[str] = []
        seen = set()
        for name in list(sources or settings.DOCUMENT_SOURCES) + ["vietstock_static", "website"]:
            cls = _SOURCES.get(name)
            if cls is None or name in report:
                continue
            report.append(name)
            try:
                links = cls(self.session).list(symbol, company_info or {})
            except Exception as exc:
                logger.debug("doc source %s failed: %s", name, exc)
                links = []
            for title, url in links:
                if url in seen:
                    continue
                seen.add(url)
                meta = classify_document(title, url)
                if meta["doc_type"] == "other":
                    continue          # chỉ giữ BCTN & BCTC
                self.db.upsert_document({
                    "doc_id": _doc_id(symbol, url), "symbol": symbol, "year": meta["year"],
                    "period": f"Q{meta['quarter']}" if meta["quarter"] else None,
                    "doc_type": meta["doc_type"], "title": title[:300], "url": normalize_doc_url(url), "source": name,
                })
        self.add_zenodo_reports(symbol)
        return self.list_documents(symbol)

    def add_zenodo_reports(self, symbol: str) -> int:
        """Thêm các BCTN có trong kho Zenodo (theo chỉ mục đóng gói sẵn – không cần mạng để liệt kê)."""
        from core import tai_lieu_bctc as zs
        n = 0
        for r in zs.list_reports(symbol):
            url = zs.make_url(r["archive_period"], r["relative_path"])
            self.db.upsert_document({
                "doc_id": _doc_id(symbol.upper(), url), "symbol": symbol.upper(), "year": r["year"], "period": None,
                "doc_type": "annual_report", "title": f"Báo cáo thường niên năm {r['year']} (kho Zenodo, {r['size_mb']:.1f} MB)",
                "url": url, "source": "zenodo"})
            n += 1
        return n

    def add_link(self, symbol: str, url: str, title: str = "") -> Dict[str, Any]:
        """Người dùng dán link PDF trực tiếp."""
        url = _safe_download_url(url)
        meta = classify_document(title or url, url)
        doc = {"doc_id": _doc_id(symbol.upper(), url), "symbol": symbol.upper(), "year": meta["year"],
               "period": f"Q{meta['quarter']}" if meta["quarter"] else None, "doc_type": meta["doc_type"],
               "title": title or Path(urlparse(url).path).name, "url": url, "source": "link"}
        self.db.upsert_document(doc)
        return doc

    def list_documents(self, symbol: str) -> pd.DataFrame:
        df = self.db.get_documents(symbol.upper())
        if not df.empty:
            for col in ("url", "local_path", "title", "source"):   # NaN → None (file tải lên không có link)
                if col in df.columns:
                    df[col] = pd.Series([v if isinstance(v, str) and v.strip() else None for v in df[col]],
                                        index=df.index, dtype=object)
            # sửa cả link cũ đã lưu (CafeF CDN)
            df["url"] = pd.Series([normalize_doc_url(u) for u in df["url"]], index=df.index, dtype=object)
            df["doc_type_label"] = df["doc_type"].map(DOC_TYPES).fillna("Khác")
            df["downloaded"] = df["local_path"].apply(lambda p: bool(p) and Path(str(p)).exists())
        return df

    # ── Tải về / tải lên ──
    def download(self, doc: Dict[str, Any]) -> Optional[Path]:
        url = doc.get("url")
        if not isinstance(url, str) or not url:
            return None
        if url.startswith("zenodo://"):
            from core import tai_lieu_bctc as zs
            try:
                content = zs.fetch_pdf(*zs.parse_url(url), session=self.session)
            except Exception as exc:
                logger.warning("Tải từ Zenodo thất bại %s: %s", url, exc)
                return None
            path = self._dir(doc["symbol"]) / f"{doc.get('year') or 'na'}_{doc.get('doc_type')}_{doc['doc_id']}.pdf"
            path.write_bytes(content)
            self.db.upsert_document({**doc, "local_path": str(path), "size_bytes": len(content)})
            return path
        r = None
        body = b""
        for cand in url_candidates(url):
            try:
                _safe_download_url(cand)
                resp = self.session.get(cand, timeout=60, stream=True)
                _safe_download_url(getattr(resp, "url", cand))
                body = _read_limited_response(resp)
            except Exception as exc:
                logger.warning("Tải tài liệu thất bại %s: %s", cand, exc)
                continue
            # một số CDN trả 200 kèm JSON báo lỗi ("File not found") thay vì 404
            if resp.status_code == 200 and body and not body.lstrip()[:1] == b"{":
                r, url = resp, cand
                break
        if r is None:
            return None
        ext = Path(urlparse(url).path).suffix.lower() or ".pdf"
        if body[:4] == b"%PDF":
            ext = ".pdf"
        elif ext == ".pdf":
            logger.warning("Nội dung tải về không phải PDF: %s", url)
            return None
        fname = f"{doc.get('year') or 'na'}_{doc.get('doc_type')}_{doc['doc_id']}{ext}"
        path = self._dir(doc["symbol"]) / fname
        path.write_bytes(body)
        self.db.upsert_document({**doc, "local_path": str(path), "size_bytes": len(body)})
        return path

    def save_upload(self, symbol: str, filename: str, content: bytes, doc_type: Optional[str] = None,
                    year: Optional[int] = None, quarter: Optional[int] = None) -> Dict[str, Any]:
        if len(content) > settings.MAX_DOCUMENT_BYTES:
            raise ValueError(f"Tệp vượt giới hạn {settings.MAX_DOCUMENT_BYTES // (1024 * 1024)} MiB")
        if not content.startswith(b"%PDF"):
            raise ValueError("Tệp tải lên không phải PDF hợp lệ")
        meta = classify_document(filename)
        doc_type = doc_type or meta["doc_type"]
        year = year or meta["year"]
        quarter = quarter or meta["quarter"]
        doc_id = _doc_id(symbol.upper(), f"upload:{filename}:{len(content)}")
        path = self._dir(symbol) / f"{year or 'na'}_{doc_type}_{doc_id}{Path(filename).suffix or '.pdf'}"
        path.write_bytes(content)
        doc = {"doc_id": doc_id, "symbol": symbol.upper(), "year": year,
               "period": f"Q{quarter}" if quarter else None, "doc_type": doc_type, "title": filename,
               "url": None, "local_path": str(path), "source": "upload", "size_bytes": len(content)}
        self.db.upsert_document(doc)
        return doc

    # ── Trích số liệu ──
    def extract(self, doc: Dict[str, Any], use_ocr: bool = True, progress=None) -> Dict[str, Any]:
        """
        Trích số liệu 1 file. Kết quả được lưu cạnh file (<tên>.extract.json) để lần sau không phải đọc/OCR lại.
        use_ocr=False: không chạy OCR mới (dùng cho nguồn dự phòng tự động) – vẫn dùng kết quả OCR đã lưu.
        """
        path = doc.get("local_path")
        if not path or not Path(path).exists():
            return {"values": {}, "note": "Chưa tải tài liệu về máy"}
        if not str(path).lower().endswith(".pdf"):
            return {"values": {}, "note": "Chỉ trích được từ file PDF"}
        p = Path(path)
        cache_f = p.with_suffix(".extract.json")
        res = None
        if cache_f.exists() and cache_f.stat().st_mtime >= p.stat().st_mtime:
            try:
                res = json.loads(cache_f.read_text(encoding="utf-8"))
            except Exception:
                res = None
        if res is None or (use_ocr and not res.get("values") and res.get("method") != "ocr"):
            res = extract_financials(p.read_bytes(), use_ocr=use_ocr, progress=progress)
            if res.get("values") or res.get("method") == "ocr":
                try:
                    cache_f.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass
        res["period_key"] = period_key_for(doc)
        return res

    def pdf_financials(self, symbol: str, period: str = "year") -> pd.DataFrame:
        """Bảng canonical từ các PDF BCTC đã tải (nguồn dự phòng cuối của DataRepository)."""
        docs = self.list_documents(symbol)
        if docs.empty:
            return pd.DataFrame()
        types = ["fs_annual"] if period == "year" else ["fs_quarterly", "fs_semiannual"]
        docs = docs[docs["doc_type"].isin(types) & docs["downloaded"]]
        # Ưu tiên báo cáo hợp nhất: tiêu đề không chứa "riêng"/"công ty mẹ"
        records = []
        for _, d in docs.iterrows():
            meta = classify_document(str(d.get("title") or ""), str(d.get("url") or ""))
            if meta.get("consolidated") is False:
                continue
            res = self.extract(d.to_dict(), use_ocr=False)     # không tự OCR khi tải BCTC
            if res.get("values") and res.get("period_key"):
                vals = dict(res["values"])
                if d.get("doc_type") == "fs_semiannual":
                    # BCTC bán niên: KQKD/LCTT là số 6 THÁNG, không phải số quý 2 → chỉ giữ chỉ tiêu số dư (30/6)
                    from core.du_lieu import FLOW_KEYS
                    flows = set(FLOW_KEYS["is"]) | set(FLOW_KEYS["cf"])
                    vals = {k: v for k, v in vals.items() if k not in flows}
                    records.append((0, res["period_key"], vals))
                else:
                    records.append((1, res["period_key"], vals))
        merged: Dict[int, Dict[str, float]] = {}
        for _, key, vals in sorted(records, key=lambda r: r[0]):     # BCTC quý ghi đè bán niên cùng kỳ
            merged.setdefault(key, {}).update(vals)
        return to_wide([(k, v) for k, v in merged.items() if v])
