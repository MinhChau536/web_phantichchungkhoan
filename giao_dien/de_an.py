"""
giao_dien/de_an.py – gộp từ 1 module (15/10/2026).

MỤC LỤC
  • pages/thesis.py – Trang 🎓 Thuyết Minh Đề Án – thiết kế theo mẫu đã duyệt (15/10/2026): băng tiêu đề xanh lá, mục lục dọc 01–10, thẻ ý
      hàm/lớp chính: render
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/thesis.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Trang 🎓 Thuyết Minh Đề Án – thiết kế theo mẫu đã duyệt (15/10/2026): băng tiêu đề xanh lá, mục lục dọc 01–10, thẻ ý
chính, công thức trong thẻ, bảng tiêu đề xanh, sơ đồ luồng xử lý; chế độ thuyết trình dạng slide.

Nội dung lấy từ core/thuyet_minh.py (dùng chung với phụ lục PDF; tham số đọc từ cấu hình mô hình).
"""


import html
import re
from typing import Any, Dict, List

import streamlit as st

from core import thuyet_minh as tc

EXAMPLE_SECTIONS = {"valuation", "pillars", "recommendation"}
SHORT = {"overview": "Tổng quan đề án", "pages": "Chức năng từng trang", "fundamental": "Phân tích cơ bản",
         "technical": "Phân tích kỹ thuật", "forecast": "Dự phóng tài chính", "valuation": "Định giá & giá mục tiêu",
         "pillars": "5 trụ cột", "recommendation": "Khuyến nghị", "risk": "Đánh giá rủi ro",
         "validation": "Kiểm chứng & hạn chế"}


def _e(t: Any) -> str:
    return html.escape(str(t))


def _bold(t: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", _e(t))


def _pal(dark: bool) -> Dict[str, str]:
    if dark:
        return dict(card="#161b22", line="#30363d", tx="#e6edf3", sub="#c9d1d9", mu="#8b949e", soft="#0f2a1f",
                    head="#86efac", zebra="#1b222c", pill="#14532d", pilltx="#bbf7d0")
    return dict(card="#ffffff", line="#e2e8f0", tx="#0f172a", sub="#334155", mu="#64748b", soft="#ecfdf3",
                head="#0b3b2c", zebra="#f6fbf8", pill="#ecfdf3", pilltx="#166534")


def _css(P: Dict[str, str]) -> None:
    st.markdown(f"""
    <style>
    .th-hero {{ background:linear-gradient(120deg,#0b3b2c 0%,#11603f 55%,#16834f 100%); border-radius:18px;
               padding:24px 28px; color:#fff; position:relative; overflow:hidden; margin-bottom:6px; }}
    .th-hero:after {{ content:""; position:absolute; right:-70px; top:-90px; width:330px; height:330px; border-radius:50%;
               background:radial-gradient(circle,rgba(74,222,128,.25),transparent 70%); }}
    .th-hero .k {{ font-size:12px; letter-spacing:2.5px; color:#86efac; font-weight:700; }}
    .th-hero .ttl {{ font-size:28px !important; line-height:1.25; color:#fff !important; }}
    .th-hero h1 {{ font-size:28px !important; font-weight:800 !important; margin:6px 0 !important; color:#fff !important; padding:0 !important; }}
    .th-hero p {{ color:#cdebdc !important; font-size:14px; max-width:800px; margin:0; }}
    .th-hero div, .th-hero span {{ color:inherit; }}
    .th-hero *, .th-slide *, table.th-t *, .th-sh *, .th-cards *, .th-flow *, .th-ex *, .th-p, .th-ul li {{ text-shadow:none !important; }}
    .th-stats {{ display:flex; gap:12px; margin-top:16px; flex-wrap:wrap; position:relative; z-index:1; }}
    .th-stat {{ background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.18); border-radius:12px; padding:9px 16px; min-width:140px; }}
    .th-stat b {{ font-size:22px; font-weight:800; color:#fff !important; }} .th-stat span {{ display:block; font-size:12px; color:#bfe6d1 !important; }}
    .th-hero .k {{ color:#86efac !important; }}
    .th-crumb {{ font-size:12.5px; color:{P['mu']}; padding-top:6px; }}
    .th-toc-t {{ font-size:11px; letter-spacing:1.8px; color:{P['mu']}; font-weight:700; margin:2px 8px 6px; }}
    [class*="st-key-thtoc_"] .stButton > button {{ width:100%; justify-content:flex-start !important; background:transparent !important;
        color:{P['sub']} !important; border:none !important; box-shadow:none !important; padding:6px 10px !important; min-height:34px;
        border-radius:9px !important; font-weight:500 !important; font-size:14px !important; transform:none !important; filter:none !important; }}
    [class*="st-key-thtoc_"] .stButton > button > div {{ justify-content:flex-start !important; width:100%; }}
    [class*="st-key-thtoc_"] .stButton > button p {{ text-align:left !important; font-size:14px !important; color:inherit !important; }}
    [class*="st-key-thtoc_"] .stButton > button:hover {{ background:{P['zebra']} !important; transform:none !important; }}
    [class*="st-key-thtoc_"] .stButton > button[data-testid="stBaseButton-primary"] {{ background:{P['soft']} !important;
        color:{P['head']} !important; font-weight:700 !important; box-shadow:inset 3px 0 0 #16a34a !important; }}
    [class*="st-key-thtoc_"] {{ margin-bottom:-12px; }}
    .st-key-th_toc {{ background:{P['card']}; border:1px solid {P['line']}; border-radius:14px; padding:10px 8px 18px; }}
    .th-sh {{ display:flex; align-items:flex-end; gap:16px; }}
    .th-sh .num {{ font-size:54px; font-weight:800; color:transparent; -webkit-text-stroke:1.6px #16a34a; line-height:.9; }}
    .th-sh h2 {{ font-size:25px !important; font-weight:800 !important; color:{P['head']} !important; margin:0 !important; padding:0 !important; }}
    .th-sh small {{ display:block; font-size:12px; color:{P['mu']}; font-weight:600; letter-spacing:1px; }}
    .th-prog {{ height:5px; background:{P['line']}; border-radius:3px; margin:10px 0 16px; }}
    .th-prog i {{ display:block; height:100%; background:#16a34a; border-radius:3px; }}
    .th-cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:12px; margin-bottom:18px; }}
    .th-card {{ background:{P['card']}; border:1px solid {P['line']}; border-radius:14px; padding:13px 15px; }}
    .th-card .ic {{ width:30px; height:30px; border-radius:9px; background:{P['soft']}; color:#16a34a; display:flex; align-items:center;
                   justify-content:center; font-weight:800; margin-bottom:7px; font-size:14px; }}
    .th-card p {{ font-size:13.5px; color:{P['sub']}; line-height:1.5; margin:0; }}
    .th-h3 {{ font-size:16.5px; font-weight:800; color:{P['head']}; margin:14px 0 10px; display:flex; align-items:center; gap:8px; }}
    .th-h3:before {{ content:""; width:4px; height:18px; background:#16a34a; border-radius:2px; }}
    [class*="st-key-thf_"] {{ background:{P['card']}; border:1px solid {P['line']} !important; border-radius:14px; padding:12px 18px 10px;
        gap:0.2rem; margin-bottom:4px; }}
    .th-flab {{ font-size:11.5px; font-weight:700; letter-spacing:1px; color:#16a34a; text-transform:uppercase; }}
    .th-fnote {{ font-size:12.5px; color:{P['mu']}; border-top:1px solid {P['line']}; padding:7px 0 4px; line-height:1.5; }}
    [class*="st-key-thf_"] .katex-display {{ overflow-x:auto; overflow-y:hidden; padding:4px 0; margin:6px 0 !important; }}
    table.th-t {{ width:100%; border-collapse:separate; border-spacing:0; background:{P['card']}; border:1px solid {P['line']};
                 border-radius:14px; overflow:hidden; font-size:13.5px; margin:4px 0 14px; }}
    table.th-t th {{ background:#0b3b2c; color:#fff; text-align:left; padding:10px 14px; font-weight:600; }}
    table.th-t td {{ padding:9px 14px; border-top:1px solid {P['line']}; color:{P['sub']}; vertical-align:top; }}
    table.th-t tr:nth-child(even) td {{ background:{P['zebra']}; }}
    table.th-t td:first-child {{ font-weight:600; color:{P['tx']}; }}
    .th-pill {{ display:inline-block; background:{P['pill']}; color:{P['pilltx']}; border-radius:20px; padding:2px 9px; font-size:12.5px;
               margin:2px 3px 2px 0; font-weight:600; white-space:nowrap; }}
    .th-flow {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:4px 0 16px; }}
    .th-step {{ background:{P['card']}; border:1px solid {P['line']}; border-top:4px solid #16a34a; border-radius:12px; padding:11px 13px; position:relative; }}
    .th-step b {{ color:{P['head']}; font-size:14px; }} .th-step p {{ font-size:12.5px; color:{P['sub']}; margin:5px 0 4px; line-height:1.45; }}
    .th-step em {{ font-style:normal; font-size:12px; color:#16a34a; font-weight:700; }}
    .th-p {{ font-size:14.5px; color:{P['sub']}; line-height:1.65; margin:0 0 10px; }}
    .th-ul li {{ font-size:14.5px; color:{P['sub']}; line-height:1.6; margin:3px 0; }}
    .th-note {{ font-size:12.5px; color:{P['mu']}; margin:-4px 0 12px; }}
    .th-ex {{ background:{P['card']}; border:1px solid #bbf7d0; border-radius:14px; padding:14px 18px; margin-top:16px; }}
    .th-ex h4 {{ color:{P['head']}; font-size:15.5px; margin:0 0 6px; padding:0; }}
    .th-row {{ display:flex; gap:12px; align-items:flex-start; font-size:14px; color:{P['sub']}; padding:7px 0; border-top:1px dashed {P['line']}; }}
    .th-row .n {{ width:24px; height:24px; border-radius:50%; background:#16a34a; color:#fff; font-size:12px; display:flex; align-items:center;
                 justify-content:center; font-weight:700; flex-shrink:0; }}
    .th-row b {{ color:{P['head']}; }}
    /* slide */
    .th-slide {{ background:{P['card']}; border:1px solid {P['line']}; border-radius:20px; overflow:hidden; box-shadow:0 10px 30px rgba(11,59,44,.08); }}
    .th-slide .top {{ background:linear-gradient(120deg,#0b3b2c,#16834f); color:#fff; padding:20px 32px; display:flex; justify-content:space-between; align-items:flex-end; }}
    .th-slide .top .num {{ font-size:62px; font-weight:800; line-height:.85; color:rgba(255,255,255,.25); }}
    .th-slide .top .st2 {{ font-size:30px; font-weight:800; color:#fff !important; line-height:1.2; }}
    .th-slide .top h2 {{ font-size:30px !important; font-weight:800 !important; color:#fff !important; margin:0 !important; padding:0 !important; }}
    .th-slide .top small {{ color:#bbf7d0 !important; font-size:13px; letter-spacing:2px; font-weight:700; }}
    .th-slide .body {{ display:grid; grid-template-columns:1.25fr 1fr; gap:26px; padding:26px 32px; }}
    .th-slide .body.one {{ grid-template-columns:1fr; }}
    .th-pts {{ list-style:none; margin:0; padding:0; }}
    .th-pts li {{ display:flex; gap:15px; margin:0 0 16px; font-size:19px; line-height:1.45; color:{P['tx']}; }}
    .th-pts li .k {{ flex-shrink:0; width:34px; height:34px; border-radius:10px; background:{P['soft']}; color:#16a34a; display:flex;
                    align-items:center; justify-content:center; font-size:16px; font-weight:800; }}
    .th-pts li b {{ color:#15803d; }}
    .th-vis {{ background:{P['zebra']}; border:1px solid {P['soft']}; border-radius:16px; padding:16px 18px; }}
    .th-vis h4 {{ font-size:12.5px; letter-spacing:1.5px; color:#16a34a; margin:0 0 12px; padding:0; }}
    .th-bar {{ display:flex; align-items:center; gap:10px; margin:8px 0; font-size:14px; color:{P['sub']}; }}
    .th-bar span {{ width:120px; flex-shrink:0; }} .th-bar i {{ display:block; height:20px; border-radius:6px; background:linear-gradient(90deg,#16a34a,#4ade80); }}
    .th-bar b {{ font-size:13px; color:{P['head']}; }}
    .th-tiles {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
    .th-tile {{ background:{P['card']}; border:1px solid {P['line']}; border-radius:12px; padding:10px 12px; }}
    .th-tile b {{ font-size:22px; color:{P['head']}; font-weight:800; }} .th-tile span {{ display:block; font-size:12.5px; color:{P['mu']}; }}
    .st-key-thesis_present label:has(input:checked) div:has(> div:empty) {{ background-color:#16a34a !important; }}
    .st-key-th_next .stButton > button, .st-key-th_next_d .stButton > button {{ background:linear-gradient(135deg,#15803d,#16a34a) !important; }}
    [class*="st-key-thf_"] .katex {{ font-size:1.08em; }}
    .th-dots {{ display:flex; gap:7px; justify-content:center; padding-top:12px; }}
    .th-dots i {{ width:9px; height:9px; border-radius:50%; background:{P['line']}; display:inline-block; }}
    .th-dots i.on {{ background:#16a34a; width:26px; border-radius:5px; }}
    </style>""", unsafe_allow_html=True)


# ── khối nội dung ──

def _cell(v: Any) -> str:
    """Ô bảng: danh sách 'Tên NN%' → nhãn nhỏ; còn lại chữ thường (cho phép **đậm**)."""
    s = str(v)
    parts = [x.strip() for x in s.split(", ")]
    if len(parts) >= 2 and all(re.search(r"\d+%$", x) for x in parts):
        return "".join(f'<span class="th-pill">{_e(x)}</span>' for x in parts)
    return _bold(s)


def _table(headers: List[str], rows: List[List[Any]]) -> str:
    th = "".join(f"<th>{_e(h)}</th>" for h in headers)
    tr = "".join("<tr>" + "".join(f"<td>{_cell(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="th-t"><tr>{th}</tr>{tr}</table>'


def _flow(rows: List[List[Any]]) -> str:
    return '<div class="th-flow">' + "".join(
        f'<div class="th-step"><b>{_e(r[0])}</b><p>{_e(r[1])}</p><em>→ {_e(r[2])}</em></div>' for r in rows) + "</div>"


def _flabel(b) -> str:
    plain = str(b[2])
    lab = re.split(r"[=:;]", plain)[0].strip()
    return lab if 2 <= len(lab) <= 46 else "Công thức"


def _blocks(sec: Dict[str, Any]) -> None:
    blocks = sec["blocks"]
    i = 0
    fidx = 0
    while i < len(blocks):
        b = blocks[i]
        kind = b[0]
        if kind == "f":                                   # gom công thức liên tiếp → lưới 2 cột
            run = []
            while i < len(blocks) and blocks[i][0] == "f":
                run.append(blocks[i])
                i += 1
            for fb in run:                                # mỗi công thức 1 thẻ toàn chiều ngang (công thức dài không bị cắt)
                with st.container(key=f"thf_{sec['key']}_{fidx}"):
                    st.markdown(f'<div class="th-flab">{_e(_flabel(fb))}</div>', unsafe_allow_html=True)
                    st.latex(fb[1])
                    if fb[3]:
                        st.markdown(f'<div class="th-fnote">{_bold(fb[3])}</div>', unsafe_allow_html=True)
                fidx += 1
            continue
        if kind == "h":
            st.markdown(f'<div class="th-h3">{_e(b[1])}</div>', unsafe_allow_html=True)
        elif kind == "p":
            st.markdown(f'<p class="th-p">{_bold(b[1])}</p>', unsafe_allow_html=True)
        elif kind == "ul":
            st.markdown('<ul class="th-ul">' + "".join(f"<li>{_bold(x)}</li>" for x in b[1]) + "</ul>", unsafe_allow_html=True)
        elif kind == "t":
            if b[1] == ["Bước", "Nội dung", "Kết quả"]:
                st.markdown(_flow(b[2]), unsafe_allow_html=True)
            else:
                st.markdown(_table(b[1], b[2]), unsafe_allow_html=True)
        elif kind == "note":
            st.markdown(f'<div class="th-note">{_bold(b[1])}</div>', unsafe_allow_html=True)
        i += 1


def _cards(sec: Dict[str, Any]) -> str:
    return '<div class="th-cards">' + "".join(
        f'<div class="th-card"><div class="ic">{k}</div><p>{_bold(x)}</p></div>' for k, x in enumerate(sec["pitch"], 1)) + "</div>"


def _visual_html(v) -> str:
    if not v:
        return ""
    if v.get("bars"):
        mx = max(x[1] for x in v["bars"]) or 1
        body = "".join(f'<div class="th-bar"><span>{_e(l)}</span><i style="width:{max(6, val / mx * 220):.0f}px"></i><b>{_e(t)}</b></div>'
                       for l, val, t in v["bars"])
    else:
        body = '<div class="th-tiles">' + "".join(f'<div class="th-tile"><b>{_e(a)}</b><span>{_e(b)}</span></div>'
                                                   for a, b in v["tiles"]) + "</div>"
    return f'<div class="th-vis"><h4>{_e(v["title"])}</h4>{body}</div>'


def _hero() -> None:
    stats = "".join(f'<div class="th-stat"><b>{_e(a)}</b><span>{_e(b)}</span></div>' for a, b in tc.hero_stats())
    st.markdown(f"""<div class="th-hero"><div class="k">THUYẾT MINH ĐỀ ÁN · STOCK ANALYTICS</div>
      <div class="ttl">Hệ thống phân tích & định giá cổ phiếu Việt Nam</div>
      <p>Từ dữ liệu thô đến khuyến nghị đầu tư: chuẩn hóa BCTC, phân tích cơ bản – kỹ thuật, dự phóng, định giá đa phương
      pháp và kiểm chứng trên dữ liệu quá khứ.</p><div class="th-stats">{stats}</div></div>""", unsafe_allow_html=True)


# ── ví dụ trực tiếp ──

def _analysis_for(symbol: str):
    if st.session_state.get("last_analyzed") == symbol and st.session_state.get("stock_analysis"):
        return st.session_state["stock_analysis"]
    if st.button(f"▶️ Chạy phân tích {symbol} để minh họa", key="thesis_run", type="primary"):
        from giao_dien.thi_truong import PRICE_HISTORY_DAYS
        from core.pipeline import StockService
        with st.spinner(f"Đang phân tích {symbol}..."):
            svc = StockService(symbol, days=PRICE_HISTORY_DAYS)
            st.session_state["stock_analysis"] = svc.full_analysis()
            st.session_state["stock_service"] = svc
            st.session_state["last_analyzed"] = symbol
        st.rerun()
    st.caption("Kết quả dùng chung với trang Phân tích cổ phiếu (đã phân tích mã này ở đó thì hiện ngay).")
    return None


def _example(part: str) -> None:
    symbol = st.session_state.get("current_symbol", "FPT")
    st.markdown(f'<div class="th-ex"><h4>🔎 Ví dụ trực tiếp với {_e(symbol)}</h4>'
                f'<div class="th-note" style="margin:0">Đổi mã ở ô tra cứu bên trái.</div></div>', unsafe_allow_html=True)
    a = _analysis_for(symbol)
    if not a:
        return
    steps = tc.explain_symbol(a).get(part) or []
    rows = "".join(f'<div class="th-row"><div class="n">{i}</div><div>{_bold(s)}</div></div>' for i, s in enumerate(steps, 1))
    st.markdown(f'<div class="th-ex" style="margin-top:-8px;border-top:none;border-radius:0 0 14px 14px">'
                f'{rows or "Chưa có dữ liệu cho phần này."}</div>', unsafe_allow_html=True)


# ── trang ──

def render():
    P = _pal(st.session_state.get("theme", "light") == "dark")
    _css(P)
    secs = tc.sections()
    keys = [s["key"] for s in secs]
    nxt = st.session_state.pop("thesis_next", None)
    if nxt in keys:
        st.session_state["thesis_cur"] = nxt
    cur = st.session_state.get("thesis_cur") if st.session_state.get("thesis_cur") in keys else keys[0]
    i = keys.index(cur)
    sec = secs[i]
    num = f"{i + 1:02d}"

    present = st.session_state.get("thesis_present", False)
    if not present:
        _hero()
    c1, c2 = st.columns([3, 1.3], vertical_alignment="center")
    c1.markdown(f'<div class="th-crumb">Thuyết minh đề án › {"Chế độ thuyết trình · " if present else ""}{num} · '
                f'{_e(SHORT[cur])}</div>', unsafe_allow_html=True)
    with c2:
        st.toggle("🎤 Chế độ thuyết trình", key="thesis_present",
                  help="Bật: mỗi mục là một slide chữ lớn để trình bày. Tắt: đầy đủ lý thuyết, công thức, bảng tham số.")

    def go(k):
        st.session_state["thesis_next"] = k
        st.rerun()

    if present:
        vis = tc.visual(cur)
        pts = "".join(f'<li><span class="k">{k}</span><div>{_bold(x)}</div></li>' for k, x in enumerate(sec["pitch"], 1))
        st.markdown(f"""<div class="th-slide"><div class="top"><div><small>MỤC {num} / {len(secs):02d}</small>
            <div class="st2">{_e(sec['title'])}</div></div><div class="num">{num}</div></div>
            <div class="body {'' if vis else 'one'}"><ul class="th-pts">{pts}</ul>{_visual_html(vis)}</div></div>""",
                    unsafe_allow_html=True)
        b1, b2, b3 = st.columns([1, 3, 1], vertical_alignment="center")
        if i > 0 and b1.button("◀ Mục trước", width="stretch", key="th_prev"):
            go(keys[i - 1])
        b2.markdown('<div class="th-dots">' + "".join(f'<i class="{"on" if j == i else ""}"></i>' for j in range(len(secs)))
                    + "</div>", unsafe_allow_html=True)
        if i < len(secs) - 1 and b3.button("Mục sau ▶", width="stretch", type="primary", key="th_next"):
            go(keys[i + 1])
        if cur in EXAMPLE_SECTIONS:
            _example(cur)
        return

    left, right = st.columns([1, 3.3], gap="medium")
    with left:
        with st.container(key="th_toc"):
            st.markdown('<div class="th-toc-t">MỤC LỤC</div>', unsafe_allow_html=True)
            for j, s in enumerate(secs):
                if st.button(f"{j + 1:02d}   {SHORT[s['key']]}", key=f"thtoc_{j}",
                             type="primary" if j == i else "tertiary", width="stretch") and j != i:
                    go(s["key"])
    with right:
        st.markdown(f'<div class="th-sh"><div class="num">{num}</div><div><small>MỤC {i + 1} / {len(secs)}</small>'
                    f'<h2>{_e(sec["title"])}</h2></div></div>'
                    f'<div class="th-prog"><i style="width:{(i + 1) / len(secs) * 100:.0f}%"></i></div>', unsafe_allow_html=True)
        st.markdown(_cards(sec), unsafe_allow_html=True)
        _blocks(sec)
        if cur == "pages":
            st.markdown('<div class="th-h3">Mở nhanh từng trang</div>', unsafe_allow_html=True)
            cols = st.columns(3)
            for j, (value, label, _, _) in enumerate(tc.PAGES[:-1]):
                if cols[j % 3].button(label, key=f"thesis_go_{j}", width="stretch"):
                    st.session_state["nav_page"] = value
                    st.rerun()
        if cur in EXAMPLE_SECTIONS:
            _example(cur)
        b1, _, b3 = st.columns([1, 2, 1])
        if i > 0 and b1.button(f"◀ {SHORT[keys[i - 1]]}", width="stretch", key="th_prev_d"):
            go(keys[i - 1])
        if i < len(secs) - 1 and b3.button(f"{SHORT[keys[i + 1]]} ▶", width="stretch", key="th_next_d"):
            go(keys[i + 1])
        st.caption("Tham số trên trang đọc trực tiếp từ cấu hình mô hình (core/cau_hinh.py) – đổi tham số thì "
                   "thuyết minh tự cập nhật.")
