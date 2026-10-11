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
from __future__ import annotations

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
