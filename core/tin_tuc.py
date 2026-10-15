"""
core/tin_tuc.py – gộp từ 2 module (15/10/2026).

MỤC LỤC
  • analytics/news_insight.py – NHẬN ĐỊNH TIN TỨC – biến danh sách tin thành vài kết luận có ích cho nhà đầu tư (dùng cho trang Tin tức và báo cáo PDF).
      hàm/lớp chính: cluster_news, summarize_events, news_insight
  • services/company_news_service.py – Company News & Intelligence Service.
      hàm/lớp chính: get_repo, news_id, is_relevant, classify_sentiment, deduplicate_news, CompanyNewsService
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/news_insight.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
NHẬN ĐỊNH TIN TỨC – biến danh sách tin thành vài kết luận có ích cho nhà đầu tư (dùng cho trang Tin tức và báo cáo PDF).

Hoàn toàn theo QUY TẮC (không gọi AI bên ngoài, không bịa số):
  1. Gộp tin trùng chủ đề: nhiều báo đưa cùng một sự kiện → 1 nhóm (độ giống tiêu đề Jaccard ≥ 0,35 hoặc cùng một con số
     đặc trưng như "1.300 tỷ" kèm ≥ 2 từ chung).
  2. Tâm lý tin tức: số bài Tích cực / Trung tính / Tiêu cực, chỉ số ròng = (tích cực − tiêu cực) / tổng.
  3. Chủ đề & ý nghĩa: từ khóa → nhóm chủ đề (đầu tư mở rộng, mở rộng thị trường, hợp đồng, kết quả kinh doanh, huy động
     vốn, cổ tức, M&A, pháp lý…) kèm ý nghĩa thường gặp với cổ phiếu; chủ đề có thể làm đổi giả định định giá được gắn cờ.
  4. Sự kiện doanh nghiệp: tổng hợp giao dịch nội bộ (đăng ký mua/bán, số người, tổng khối lượng), cổ phiếu thưởng,
     phát hành ESOP, niêm yết bổ sung.
"""


import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

SENT_NORM = {"positive": "pos", "tích cực": "pos", "negative": "neg", "tiêu cực": "neg", "neutral": "neu", "trung tính": "neu"}

STOP = set("""và của cho các những một với tại trong trên từ đến được là có này đã sẽ khi theo về như ra vào lên
the of to in for on at by a an fpt công ty cổ phần ctcp tập đoàn năm tháng ngày mới""".split())

# (khóa, nhãn, từ khóa, ý nghĩa với cổ phiếu, có thể làm đổi giả định định giá)
THEMES: List[Tuple[str, str, Tuple[str, ...], str, bool]] = [
    ("capex", "Đầu tư mở rộng", ("khởi công", "xây dựng", "nhà máy", "tòa nhà", "toà nhà", "trung tâm dữ liệu",
                                  "data center", "dự án", "rót", "đầu tư"),
     "Tăng chi đầu tư (capex): ngắn hạn có thể làm giảm dòng tiền tự do, dài hạn hỗ trợ năng lực tăng trưởng.", False),
    ("expansion", "Mở rộng thị trường", ("văn phòng", "mở rộng", "thị trường", "nước ngoài", "quốc tế", "chi nhánh",
                                         "khai trương", "ai cập", "nhật bản", "hoa kỳ", "châu âu"),
     "Mở rộng địa bàn/khách hàng: hỗ trợ tăng trưởng doanh thu; chi phí ban đầu có thể làm giảm biên lợi nhuận tạm thời.", False),
    ("contract", "Hợp đồng / hợp tác", ("hợp đồng", "ký kết", "trúng thầu", "đối tác", "hợp tác", "thỏa thuận", "mou"),
     "Bổ sung nguồn việc: tích cực cho doanh thu các kỳ tới (mức độ tùy giá trị hợp đồng).", False),
    ("results", "Kết quả kinh doanh", ("lợi nhuận", "doanh thu", "kết quả kinh doanh", "lãi ", "lỗ ", "quý", "kế hoạch năm"),
     "So với dự phóng của app (mục Định giá): lệch nhiều thì giả định tăng trưởng/biên cần xem lại.", True),
    ("capital", "Huy động vốn", ("phát hành", "tăng vốn", "huy động", "trái phiếu", "chào bán", "esop"),
     "Lưu ý pha loãng (cổ phiếu) hoặc tăng nợ (trái phiếu): ảnh hưởng EPS và cơ cấu vốn.", True),
    ("dividend", "Cổ tức / cổ phiếu thưởng", ("cổ tức", "chia thưởng", "cổ phiếu thưởng", "tạm ứng"),
     "Ảnh hưởng tổng lợi nhuận kỳ vọng; cổ phiếu thưởng làm giá điều chỉnh kỹ thuật, không phải giảm giá thật.", False),
    ("ma", "M&A / thay đổi cơ cấu", ("thâu tóm", "sáp nhập", "m&a", "mua lại", "thoái vốn", "công ty liên kết", "hợp nhất",
                                     "chuyển nhượng"),
     "Có thể thay đổi phạm vi hợp nhất hoặc giá trị khoản đầu tư: cần xem lại giả định định giá.", True),
    ("legal", "Pháp lý / rủi ro", ("khởi tố", "xử phạt", "vi phạm", "điều tra", "kiện", "truy thu", "đình chỉ"),
     "Rủi ro pháp lý/uy tín: theo dõi diễn biến; có thể ảnh hưởng kết quả kinh doanh.", True),
    ("award", "Thương hiệu / giải thưởng", ("giải thưởng", "vinh danh", "top ", "xếp hạng", "chuyển đổi số"),
     "Tác động trực tiếp đến định giá thấp; củng cố hình ảnh thương hiệu.", False),
    ("people", "Nhân sự cấp cao", ("bổ nhiệm", "từ nhiệm", "miễn nhiệm", "ceo", "chủ tịch", "tổng giám đốc"),
     "Thay đổi lãnh đạo: theo dõi định hướng chiến lược.", False),
]


def _strip(s: str) -> str:
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _tokens(title: str) -> set:
    t = re.sub(r"[^\w\s.,%]", " ", str(title).lower())
    out = set()
    for w in t.split():
        w = w.strip(".,")
        if w and w not in STOP and (len(w) > 1 or w.isdigit()):
            out.add(_strip(w))
    return out


def _bigrams(title: str) -> set:
    w = [_strip(x) for x in re.sub(r"[^\w\s]", " ", str(title).lower()).split() if x not in STOP]
    return {f"{a} {b}" for a, b in zip(w, w[1:]) if not ({a, b} & _GENERIC)}


_GENERIC = {"ty", "dong", "trieu", "nghin", "ha", "noi", "tp", "hcm", "tai", "cua", "va", "voi", "hon", "tren"}


def _numbers(title: str) -> set:
    return {n.replace(",", ".") for n in re.findall(r"\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?", str(title)) if len(n) >= 3}


def _sent(v: Any) -> str:
    return SENT_NORM.get(str(v or "").strip().lower(), "neu")


def _majority(c: Counter) -> str:
    """Sắc thái của CẢ NHÓM tin trùng (góp ý GK IV.4): theo số đông; hòa giữa các sắc thái → trung tính, để một sự kiện
    không hiện cùng lúc 'tích cực' và 'trung tính'."""
    top = c.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return "neu"
    return top[0][0]


def cluster_news(items: Sequence[Dict[str, Any]], threshold: float = 0.35) -> List[Dict[str, Any]]:
    """Gộp tin cùng chủ đề. Giữ thứ tự xuất hiện (tin đầu tiên của nhóm làm tiêu đề đại diện)."""
    groups: List[Dict[str, Any]] = []
    for it in items:
        title = str(it.get("title") or "").strip()
        if not title:
            continue
        tk, nums, bg = _tokens(title), _numbers(title), _bigrams(title)
        best, best_sim = None, 0.0
        for g in groups:
            sim = 0.0
            for m in g["members"]:                       # so với TỪNG tin trong nhóm (không phải hợp các từ)
                inter = len(tk & m[0])
                s_ = inter / max(1, len(tk | m[0]))
                if (nums & m[1]) and inter >= 2:
                    s_ = max(s_, threshold)
                if len(bg & m[2]) >= 2:                 # chung ≥ 2 cụm 2 từ, vd "khởi công" + "tòa nhà"
                    s_ = max(s_, threshold)
                sim = max(sim, s_)
            if sim > best_sim:
                best, best_sim = g, sim
        if best is not None and best_sim >= threshold:
            best["items"].append(it)
            best["members"].append((tk, nums, bg))
        else:
            groups.append({"members": [(tk, nums, bg)], "items": [it]})
    out = []
    for g in groups:
        its = g["items"]
        sents = Counter(_sent(i.get("sentiment")) for i in its)
        text = " ".join(str(i.get("title", "")) for i in its).lower()
        themes = [k for k, _, kws, _, _ in THEMES if any(kw in text for kw in kws)]
        out.append({"title": its[0].get("title"), "url": its[0].get("url") or its[0].get("link") or "",
                    "date": its[0].get("date"), "n": len(its),
                    "sources": list(dict.fromkeys(str(i.get("source") or "") for i in its if i.get("source"))),
                    "sentiment": _majority(sents), "themes": themes, "items": its})
    return out


def _event_rows(events: Any) -> List[Tuple[str, str]]:
    """Bảng sự kiện (DataFrame của vnstock hoặc list (ngày, tiêu đề)) → [(dd/mm/yyyy, tiêu đề chi tiết)]."""
    if events is None:
        return []
    if isinstance(events, (list, tuple)):
        return [(str(d), str(t)) for d, t in events]
    if not isinstance(events, pd.DataFrame) or events.empty:
        return []
    cols = list(events.columns)
    low = {str(c).lower(): c for c in cols}
    title_c = next((low[k] for k in ("event_title_vi", "event_title", "title", "event_title_en") if k in low), None) \
        or next((c for c in cols if any(k in str(c).lower() for k in ("title", "event_name", "name"))), cols[0])
    kind_c = low.get("event_name_vi")
    date_c = next((low[k] for k in ("display_date1", "public_date", "exright_date") if k in low), None) \
        or next((c for c in cols if "date" in str(c).lower()), None)
    rows, seen = [], set()
    for _, r in events.iterrows():
        d = str(r.get(date_c, ""))[:10] if date_c else ""
        t = str(r.get(title_c, "") or "").strip()
        k = str(r.get(kind_c, "") or "").strip() if kind_c else ""
        if k and t and k.split(":")[0].lower() not in t.lower():
            t = f"{k.split(':')[0]}: {t}"
        if not t or (d, t) in seen:
            continue
        seen.add((d, t))
        dt = pd.to_datetime(d, errors="coerce")
        rows.append((dt.strftime("%d/%m/%Y") if pd.notna(dt) else d, t))
    return rows


def _num(s: str) -> Optional[float]:
    try:
        return float(s.replace(".", "").replace(",", ""))
    except ValueError:
        return None


def summarize_events(events: Any, recent: int = 30) -> List[str]:
    """Tóm tắt sự kiện doanh nghiệp đáng chú ý (tối đa `recent` sự kiện gần nhất)."""
    rows = _event_rows(events)[:recent]
    out: List[str] = []
    ins: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"vol": 0.0, "people": set(), "dates": set()})
    for d, t in rows:
        m = re.search(r"(?:đăng\s*k[íý])\s*(mua|bán)\s*([\d.,]+)", t, flags=re.I)
        if m and ("nội bộ" in t.lower() or " - " in t):
            side = m.group(1).lower()
            v = _num(m.group(2))
            if v:
                ins[side]["vol"] += v
                name = t.split(":", 1)[-1].split(" - ")[0].strip()
                ins[side]["people"].add(name)
                ins[side]["dates"].add(d)
    for side, lab, tone in (("mua", "MUA", "tín hiệu tích cực về niềm tin của người nội bộ"),
                            ("bán", "BÁN", "lưu ý áp lực cung ngắn hạn")):
        x = ins.get(side)
        if x and x["vol"]:
            dates = sorted(x["dates"], key=lambda s: pd.to_datetime(s, dayfirst=True, errors="coerce"))
            when = dates[-1] if len(dates) == 1 else f"{dates[0]}–{dates[-1]}"
            vol = f"{x['vol'] / 1e6:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            out.append(f"Giao dịch nội bộ: {len(x['people'])} người đăng ký {lab} tổng ~{vol} triệu CP ({when}) – {tone}.")
    for d, t in rows:
        tl = t.lower()
        m = re.search(r"cổ phiếu thưởng[^\d]*([\d.,]+)\s*%", tl)
        if m:
            out.append(f"Cổ phiếu thưởng tỷ lệ {m.group(1)}% (ngày {d}): giá đã được điều chỉnh tương ứng – không phải "
                       "giảm giá thật; số CP tăng nhưng EPS/BVPS so sánh trên cùng cơ sở.")
            break
    for d, t in rows:
        if "cbcnv" in t.lower() or "esop" in t.lower():
            out.append(f"Phát hành cho cán bộ nhân viên (ESOP) ngày {d}: pha loãng nhỏ, chi phí phúc lợi.")
            break
    for d, t in rows:
        if "niêm yết bổ sung" in t.lower() or "niêm yết thêm" in t.lower():
            out.append(f"Niêm yết bổ sung ({d}): {t.split(':', 1)[-1].strip()}.")
            break
    return out


def news_insight(items: Sequence[Dict[str, Any]], events: Any = None) -> Dict[str, Any]:
    items = [i for i in (items or []) if str(i.get("title") or "").strip()]
    clusters = cluster_news(items)
    cnt = Counter(_sent(i.get("sentiment")) for i in items)
    n = len(items)
    net = (cnt["pos"] - cnt["neg"]) / n if n else 0.0
    tone = ("Nghiêng tích cực" if net >= 0.3 else "Nghiêng tiêu cực" if net <= -0.3 else
            "Trung tính / lẫn lộn") if n else "Chưa có tin"
    theme_n: Dict[str, int] = Counter()
    for c in clusters:
        for k in c["themes"]:
            theme_n[k] += c["n"]
    themes = [{"key": k, "label": lab, "articles": theme_n[k], "implication": imp, "review": rev}
              for k, lab, _, imp, rev in THEMES if theme_n.get(k)]
    themes.sort(key=lambda x: -x["articles"])
    top = sorted(clusters, key=lambda c: -c["n"])
    headline = []
    if n:
        headline.append(f"{n} bài, {len(clusters)} chủ đề khác nhau; tâm lý {tone.lower()} "
                        f"({cnt['pos']} tích cực · {cnt['neu']} trung tính · {cnt['neg']} tiêu cực).")
        if top and top[0]["n"] >= 2:
            headline.append(f"Tin nổi bật nhất: \"{top[0]['title']}\" – {top[0]['n']} bài từ "
                            f"{len(top[0]['sources'])} nguồn.")
    flags = [t["label"] for t in themes if t["review"] and t["articles"] >= 2]   # 1 bài lẻ (vd tin tổng hợp) chưa gắn cờ
    return {"n": n, "n_topics": len(clusters), "counts": {"pos": cnt["pos"], "neu": cnt["neu"], "neg": cnt["neg"]},
            "net": net, "tone": tone, "clusters": clusters, "top": top[:3], "themes": themes,
            "events": summarize_events(events), "flags": flags, "headline": headline}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: services/company_news_service.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Company News & Intelligence Service.

Thu thập, tổng hợp và chuẩn hóa tin tức doanh nghiệp đa nguồn:
  - Vnstock Company News & Reference Data
  - Google News RSS (Vietstock, CafeF, VnExpress, Tin Nhanh Chứng Khoán, Thanh Niên, Tuổi Trẻ,...)
  - Cổng thông tin tài chính trực tiếp (CafeF, VnExpress, Tin Nhanh Chứng Khoán, VnEconomy)
  - Khử trùng lặp tiêu đề thông minh (SequenceMatcher ratio >= 0.80)
  - Phân loại sắc thái cảm xúc (Sentiment Analysis: Tích cực / Tiêu cực / Trung tính)
  - Bộ nhớ đệm DiskCache + In-Memory tối ưu tốc độ
"""


import concurrent.futures
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import email.utils
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import urllib.request
from urllib.parse import quote, urljoin, urlparse
import xml.etree.ElementTree as ET

import pandas as pd

from core.cau_hinh import settings
from core.du_lieu import cache
from core.du_lieu import Database

logger = logging.getLogger(__name__)


def get_repo():
    from core.pipeline import get_repo as _g
    return _g()


def news_id(item: Dict[str, Any], symbol: str) -> str:
    import hashlib
    key = (item.get("url") or "").split("#", 1)[0].rstrip("/") or _normalized_title(item.get("title", ""))
    return hashlib.sha1(f"{symbol}|{key}".encode("utf-8")).hexdigest()[:20]

POSITIVE_KEYWORDS = {
    "tăng trưởng", "tăng mạnh", "kỷ lục", "vượt kế hoạch", "mở rộng", "khởi công",
    "hoàn thành", "lợi nhuận tăng", "doanh thu tăng", "đơn hàng mới", "cổ tức",
    "phục hồi", "bứt phá", "mua ròng", "tăng trần", "khởi sắc", "thặng dư", "lãi lớn",
    "nâng hạng", "hợp tác", "đột phá", "triển vọng", "thành công",
    # bổ sung 14/10/2026 – cụm từ thị trường hay gặp trong tiêu đề
    "ngắt chuỗi giảm", "trở lại sắc xanh", "cuối cùng cũng xanh", "ngược dòng tăng", "tăng điểm", "gom mạnh", "mua vào",
    "khai trương", "ký kết", "trúng thầu", "lãi ròng tăng", "lợi nhuận kỷ lục", "hồi phục", "bật tăng",
}

NEGATIVE_KEYWORDS = {
    "suy giảm", "giảm mạnh", "thua lỗ", "lỗ ròng", "nợ quá hạn", "xử phạt",
    "điều tra", "đình chỉ", "rủi ro", "khó khăn", "chậm tiến độ", "thu hồi",
    "phá sản", "bán tháo", "giảm sàn", "khởi tố", "vi phạm", "lao dốc",
    "hạ giá mục tiêu", "cảnh báo", "thủng đáy",
    "chuỗi giảm", "giảm điểm", "mất điểm", "bán ròng", "suy yếu", "giảm sâu", "sụt giảm", "lợi nhuận giảm",
    "doanh thu giảm", "chậm lại", "xả mạnh",
}

# Tin KHÔNG liên quan đến hoạt động kinh doanh / cổ phiếu (thể thao, giải trí, tuyển sinh…) – loại khỏi bảng tin & báo cáo
IRRELEVANT_KEYWORDS = (
    "futsal", "bóng đá", "giải đấu", "cầu thủ", "vòng bảng", "sân cỏ", "huấn luyện viên", "tuyển sinh", "học bổng",
    "điểm chuẩn", "thi tốt nghiệp", "hoa hậu", "ca sĩ", "showbiz", "phim ",
)


def is_relevant(title: str) -> bool:
    low = (title or "").lower()
    return not any(k in low for k in IRRELEVANT_KEYWORDS)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.7",
}


def _clean_text(val: Any) -> Optional[str]:
    if val is None or pd.isna(val):
        return None
    txt = re.sub(r"\s+", " ", str(val)).strip()
    if txt.lower() in {"", "n/a", "na", "none", "null", "nan", "-"}:
        return None
    return txt


def classify_sentiment(text: str) -> str:
    """Phân loại cảm xúc rule-based theo bộ từ điển tài chính tiếng Việt."""
    low = text.lower()
    hits_pos = [kw for kw in POSITIVE_KEYWORDS if kw in low]
    pos = len(hits_pos)
    # cụm tích cực "đảo chiều" (vd "ngắt chuỗi giảm điểm") chứa từ tiêu cực → bỏ phần đã khớp trước khi đếm tiêu cực
    rest = low
    for kw in sorted(hits_pos, key=len, reverse=True):
        rest = rest.replace(kw, " ")
    neg = sum(kw in rest for kw in NEGATIVE_KEYWORDS)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _normalized_title(title: str) -> str:
    return re.sub(r"[^\w\s]", "", title.lower(), flags=re.UNICODE).strip()


def deduplicate_news(items: List[Dict[str, Any]], threshold: float = 0.80) -> List[Dict[str, Any]]:
    """Loại bỏ bài trùng lặp URL hoặc tiêu đề tương tự."""
    result: List[Dict[str, Any]] = []
    seen_urls: set = set()
    seen_titles: List[str] = []

    for item in items:
        title = _clean_text(item.get("title"))
        if not title:
            continue
        url = str(item.get("url") or "").strip()
        canonical_url = url.split("#", 1)[0].rstrip("/")
        if canonical_url and canonical_url in seen_urls:
            continue

        norm = _normalized_title(title)
        if any(SequenceMatcher(None, norm, prev).ratio() >= threshold for prev in seen_titles):
            continue

        if canonical_url:
            seen_urls.add(canonical_url)
        seen_titles.append(norm)
        result.append(item)

    return result


class CompanyNewsService:
    """Service điều phối thu thập và quản lý tin tức doanh nghiệp."""

    def __init__(self):
        pass

    def get_company_news(
        self,
        symbol: str,
        lookback_days: int = 365,
        max_news: int = 40,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Thu thập tin tức đa nguồn cho một mã cổ phiếu.
        """
        symbol = symbol.strip().upper()
        cache_key = f"company_news_data2:{symbol}"

        if not force_refresh:
            cached = cache.get(cache_key)
            if cached and isinstance(cached, dict) and cached.get("news"):
                return cached

        # Lấy thông tin công ty để làm từ khóa tìm kiếm
        company_info = get_repo().get_company_info(symbol)
        company_name = company_info.get("company_name", company_info.get("name", symbol))

        articles: List[Dict[str, Any]] = []

        # 1. Thu thập qua Google News RSS (Độ phủ rộng, tức thời, nhiều đầu báo)
        google_news = self._fetch_google_news(symbol, company_name)
        articles.extend(google_news)

        # 2. Thu thập qua vnstock Reference news
        vnstock_news = self._fetch_vnstock_news(symbol)
        articles.extend(vnstock_news)

        # 3. Thu thập qua các cổng tin tài chính CafeF, VnExpress (nếu chưa đủ)
        if len(articles) < 15:
            portal_news = self._fetch_portal_news(symbol, company_name)
            articles.extend(portal_news)

        # 4. Khử trùng lặp và sắp xếp theo thời gian mới nhất
        cleaned_articles = [a for a in deduplicate_news(articles) if is_relevant(a.get("title", ""))]

        def get_sort_key(item):
            d = item.get("timestamp_dt")
            if d is None:
                return datetime.min
            if hasattr(d, "tzinfo") and d.tzinfo is not None:
                d = d.replace(tzinfo=None)
            return d

        cleaned_articles.sort(key=get_sort_key, reverse=True)

        final_news = cleaned_articles[:max_news]

        # Thống kê cảm xúc
        pos_count = sum(1 for a in final_news if a.get("sentiment") == "positive")
        neg_count = sum(1 for a in final_news if a.get("sentiment") == "negative")
        neu_count = sum(1 for a in final_news if a.get("sentiment") == "neutral")

        # Trích xuất danh sách nguồn báo thực tế
        sources = sorted(list({a.get("source", "Báo chí") for a in final_news if a.get("source")}))

        result = {
            "symbol": symbol,
            "company_name": company_name,
            "fetched_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "news": final_news,
            "sources": sources,
            "summary": {
                "total": len(final_news),
                "positive": pos_count,
                "negative": neg_count,
                "neutral": neu_count,
            },
        }

        # Lưu cache và lưu trữ lâu dài vào DuckDB (để xem lại tin theo ngày)
        cache.set(cache_key, result, ttl=settings.CACHE_TTL_NEWS)
        self.persist(symbol, final_news)
        return result

    # ─────────────────── Lưu trữ & bảng tin ──────────────────────────────────

    def persist(self, symbol: str, items: List[Dict[str, Any]]):
        rows = []
        for it in items:
            rows.append({
                "news_id": news_id(it, symbol), "symbol": symbol, "title": it.get("title"),
                "url": it.get("url"), "source": it.get("source"),
                "published_at": it.get("timestamp_dt"), "sentiment": it.get("sentiment"),
                "summary": (it.get("summary") or "")[:1000],
            })
        Database().upsert_news(rows)

    @staticmethod
    def feed(symbols: Optional[List[str]] = None, days: int = 7, limit: int = 300) -> pd.DataFrame:
        """Bảng tin đã lưu (mọi mã hoặc danh sách mã), mới nhất trước."""
        db = Database()
        if not symbols:
            return db.get_news(days=days, limit=limit)
        frames = [db.get_news(s, days=days, limit=limit) for s in symbols]
        frames = [f for f in frames if not f.empty]
        if not frames:
            return pd.DataFrame()
        df = pd.concat(frames, ignore_index=True)
        order = pd.to_datetime(df["published_at"]).fillna(pd.to_datetime(df["fetched_at"]))
        return df.assign(_o=order).sort_values("_o", ascending=False).drop(columns="_o").head(limit)

    def _fetch_google_news(self, symbol: str, company_name: str) -> List[Dict[str, Any]]:
        """Lấy tin tức thị trường từ Google News RSS."""
        queries = [
            f"cổ phiếu {symbol}",
            f"{symbol} {company_name}",
        ]
        results = []

        for q in queries:
            try:
                enc = quote(q)
                url = f"https://news.google.com/rss/search?q={enc}&hl=vi&gl=VN&ceid=VN:vi"
                req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
                with urllib.request.urlopen(req, timeout=8) as resp:
                    xml_data = resp.read()
                tree = ET.fromstring(xml_data)

                for item in tree.findall(".//item"):
                    raw_title = item.find("title").text if item.find("title") is not None else ""
                    if not raw_title:
                        continue

                    # Tách tiêu đề và nguồn xuất bản
                    if " - " in raw_title:
                        parts = raw_title.rsplit(" - ", 1)
                        title = parts[0].strip()
                        source = parts[1].strip()
                    else:
                        title = raw_title.strip()
                        source = "Báo chí"

                    # Chuẩn hóa tên nguồn phổ biến
                    src_low = source.lower()
                    if "cafef" in src_low:
                        source = "CafeF"
                    elif "vnexpress" in src_low:
                        source = "VnExpress"
                    elif "thanh niên" in src_low:
                        source = "Thanh Niên"
                    elif "vietstock" in src_low:
                        source = "Vietstock"
                    elif "tin nhanh chứng khoán" in src_low or "đầu tư chứng khoán" in src_low:
                        source = "Tin Nhanh Chứng Khoán"
                    elif "vneconomy" in src_low:
                        source = "VnEconomy"
                    elif "tuổi trẻ" in src_low:
                        source = "Tuổi Trẻ"
                    elif "báo đầu tư" in src_low:
                        source = "Báo Đầu Tư"

                    link = item.find("link").text if item.find("link") is not None else ""
                    pub_str = item.find("pubDate").text if item.find("pubDate") is not None else ""

                    # Parse ngày giờ
                    dt = None
                    if pub_str:
                        try:
                            dt = email.utils.parsedate_to_datetime(pub_str)
                            # Convert to local time
                            if dt.tzinfo:
                                dt = dt.astimezone()
                        except Exception:
                            dt = datetime.now()
                    else:
                        dt = datetime.now()

                    date_display = dt.strftime("%d/%m/%Y %H:%M") if dt else datetime.now().strftime("%d/%m/%Y")

                    desc = item.find("description").text if item.find("description") is not None else ""
                    # Bỏ HTML tags trong description
                    desc_clean = re.sub(r"<[^>]+>", "", desc).strip() if desc else ""

                    sentiment = classify_sentiment(f"{title} {desc_clean}")

                    results.append({
                        "title": title,
                        "source": source,
                        "date": date_display,
                        "timestamp_dt": dt,
                        "summary": desc_clean or f"Tin tức sự kiện liên quan đến mã {symbol} ({source}).",
                        "sentiment": sentiment,
                        "url": link,
                    })

            except Exception as e:
                logger.debug("Lỗi lấy Google News cho %s: %s", q, e)

        return results

    def _fetch_vnstock_news(self, symbol: str) -> List[Dict[str, Any]]:
        """Tin doanh nghiệp từ vnstock 4.x (Company(source='vci').news(), dự phòng KBS)."""
        results = []
        try:
            for it in get_repo().get_vnstock_news(symbol):
                title = _clean_text(it.get("title"))
                if not title:
                    continue
                dt = it.get("published_at")
                dt = dt.to_pydatetime() if hasattr(dt, "to_pydatetime") else dt
                summary = _clean_text(it.get("summary")) or ""
                results.append({
                    "title": title,
                    "source": _clean_text(it.get("source")) or "Vnstock",
                    "date": dt.strftime("%d/%m/%Y %H:%M") if dt else "—",
                    "timestamp_dt": dt,
                    "summary": summary,
                    "sentiment": classify_sentiment(f"{title} {summary}"),
                    "url": it.get("url") or "",
                })
        except Exception as e:
            logger.debug("Lỗi vnstock news: %s", e)
        return results

    def _fetch_portal_news(self, symbol: str, company_name: str) -> List[Dict[str, Any]]:
        """Tìm kiếm bổ sung trên CafeF và VnExpress."""
        results = []
        try:
            import requests
            from bs4 import BeautifulSoup

            # CafeF search
            url = f"https://cafef.vn/tim-kiem.chn?keywords={quote(symbol)}&page=1"
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=6)
            if resp.ok:
                soup = BeautifulSoup(resp.text[:1_500_000], "html.parser")
                for item in soup.select("div.item, div.news-item, h3 a, h2 a")[:10]:
                    a_tag = item if item.name == "a" else item.find("a")
                    if a_tag and a_tag.get("href"):
                        title = _clean_text(a_tag.get_text())
                        href = a_tag["href"]
                        if title and len(title) > 15 and symbol.lower() in title.lower():
                            full_url = urljoin("https://cafef.vn", href)
                            results.append({
                                "title": title,
                                "source": "CafeF",
                                "date": "—",            # trang tìm kiếm không cho ngày đăng → không tự gán
                                "timestamp_dt": None,
                                "summary": "",
                                "sentiment": classify_sentiment(title),
                                "url": full_url,
                            })
        except Exception as e:
            logger.debug("Lỗi portal news CafeF: %s", e)

        return results
