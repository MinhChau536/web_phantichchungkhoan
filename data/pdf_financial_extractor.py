"""
Trích số liệu BCTC từ file PDF theo MÃ SỐ chuẩn của mẫu biểu VAS
(Thông tư 200/2014/TT-BTC và 202/2014/TT-BTC cho BCTC hợp nhất).

Cách làm:
  1. Đọc lớp chữ của PDF; PDF scan / lỗi phông → OCR (data/pdf_ocr.py, nếu đã cài thư viện).
     BCTC ngân hàng (không có cột mã số) → nhận diện theo nhãn chỉ tiêu (BANK_LABELS).
  2. Chia văn bản theo 3 báo cáo nhờ tiêu đề: Bảng cân đối kế toán / Báo cáo tình hình tài chính,
     Báo cáo kết quả hoạt động kinh doanh, Báo cáo lưu chuyển tiền tệ. Dừng ở phần Thuyết minh.
  3. Trong từng báo cáo, tìm dòng chứa mã số chuẩn VÀ nhãn khớp từ khóa của mã đó
     (vd mã 10 trong KQKD phải có chữ "doanh thu") rồi lấy số tiền đầu tiên sau mã = kỳ này.
  4. Đọc "Đơn vị tính" để quy về VND. Kiểm tra Tổng tài sản = Nợ phải trả + VCSH.
"""
from __future__ import annotations

import io
import math
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from data.financial_mapping import strip_accents

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
    from data.pdf_ocr import INSTALL_HINT, ocr_available, ocr_pdf_pages
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
