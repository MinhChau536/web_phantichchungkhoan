"""
Trang – 🔍 Phân Tích Cổ Phiếu (giao diện bảng điều khiển).

Bố cục:
  Đầu trang : thẻ mã (giá, thay đổi, biên 52 tuần, sparkline) + 5 điểm trụ cột + khuyến nghị 12T
  Tab 1  📈 Biểu đồ giá : chỉ số giá nhanh, biểu đồ nến (MA/EMA/Bollinger, khối lượng, chọn kỳ), so sánh VN-Index, hiệu suất theo kỳ
  Tab 2  🔧 Kỹ thuật    : xu hướng, điểm & thành phần điểm, bảng chỉ báo có diễn giải, hỗ trợ/kháng cự, biểu đồ RSI/MACD/Bollinger/ADX/dòng tiền
  Tab 3  📊 Cơ bản      : điểm cơ bản + Financial Health, chỉ số chính có so sánh năm trước, biểu đồ KQKD/sinh lời/dòng tiền/cơ cấu vốn,
                          DuPont, Piotroski, Altman, cảnh báo, BCTC tóm tắt
  Tab 4  💰 Định giá    : khuyến nghị & giá mục tiêu 12T, biểu đồ "football field" theo phương pháp, bảng phương pháp,
                          bội số hiện tại so với lịch sử/ngành, độ nhạy
Toàn bộ số liệu từ StockService.full_analysis() (dữ liệu thật); thiếu số liệu hiển thị "—".
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from components.charts import _base_layout, bollinger_chart, macd_chart, rsi_chart
from components.metrics import warning_box
from config.constants import TIME_RANGES
from pages.market_overview import _css, _md, _pal, _section, _spark
from services.stock_service import StockService

UP_WORDS = ("tăng", "tích cực", "vào", "trên ma", "dương", "phe mua", "mạnh hơn", "cắt lên", "quá bán", "golden")
DOWN_WORDS = ("giảm", "tiêu cực", "tiền ra", "dưới ma", "âm", "phe bán", "yếu hơn", "cắt xuống", "quá mua", "death")


# ─────────────────────────────────────────────────────────────────────────────
# Tiện ích
# ─────────────────────────────────────────────────────────────────────────────

def _e(s) -> str:
    return html.escape(str(s))


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return None if np.isnan(f) or np.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _f(v, d=0, suf="", sign=False) -> str:
    v = _num(v)
    if v is None:
        return "—"
    return (f"{v:+,.{d}f}" if sign else f"{v:,.{d}f}") + suf


def _clr(v, p) -> str:
    v = _num(v)
    if v is None:
        return p["muted"]
    return p["up"] if v > 0 else p["down"] if v < 0 else p["ref"]


def _tone(text: str) -> str:
    t = (text or "").lower()
    if "<" in t or "death" in t:
        return "down"
    if ">" in t or "golden" in t:
        return "up"
    if any(w in t for w in DOWN_WORDS) and not any(w in t for w in ("quá bán",)):
        return "down"
    if any(w in t for w in UP_WORDS):
        return "up"
    return "neutral"


def _ts(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["timestamp"] if "timestamp" in df.columns else df.index)


def _ret(close: pd.Series, days: int) -> Optional[float]:
    s = close.dropna()
    if s.empty:
        return None
    cut = s.index.max() - pd.Timedelta(days=days)
    base = s[s.index <= cut]
    if base.empty:
        return None
    return (s.iloc[-1] / base.iloc[-1] - 1) * 100


def _extra_css(p) -> str:
    chip = {"up": p["up"], "down": p["down"], "neutral": p["ref"]}
    return f"""<style>
.sa-hero{{display:grid;grid-template-columns:1.3fr 1fr;gap:16px;border:1px solid {p['border']};border-radius:16px;
  padding:18px 20px;margin-bottom:12px;background:{p['card']}}}
@media (max-width:900px){{.sa-hero{{grid-template-columns:1fr}}}}
.sa-sym{{font-size:30px;font-weight:900;color:{p['text']};letter-spacing:-.5px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.sa-chip{{font-size:11px;font-weight:700;padding:3px 9px;border-radius:999px;border:1px solid {p['border']};color:{p['muted']}}}
.sa-name{{font-size:14px;color:{p['muted']};margin-top:2px}}
.sa-price{{font-size:34px;font-weight:900;color:{p['text']};margin-top:10px;font-variant-numeric:tabular-nums}}
.sa-chg{{font-size:15px;font-weight:800;margin-left:8px}}
.sa-range{{margin-top:10px;font-size:11.5px;color:{p['muted']}}}
.sa-range .bar{{position:relative;height:8px;border-radius:999px;background:linear-gradient(90deg,{p['down']},{p['ref']},{p['up']});opacity:.75;margin:5px 0}}
.sa-range .dot{{position:absolute;top:-4px;width:4px;height:16px;border-radius:2px;background:{p['text']}}}
.sa-scores{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:4px 0 8px}}
.sa-sc{{border:1px solid {p['border']};border-radius:12px;padding:10px 12px;background:{p['card']}}}
.sa-sc small{{font-size:11px;font-weight:700;color:{p['muted']};text-transform:uppercase;letter-spacing:.4px}}
.sa-sc b{{display:block;font-size:24px;font-weight:900;color:{p['text']};margin:2px 0 6px;font-variant-numeric:tabular-nums}}
.sa-tag{{display:inline-block;padding:3px 10px;border-radius:8px;font-size:12px;font-weight:800;color:#fff;margin-right:6px}}
.sa-pill{{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:700;color:#fff}}
.sa-pill.up{{background:{chip['up']}}} .sa-pill.down{{background:{chip['down']}}} .sa-pill.neutral{{background:{chip['neutral']}}}
.sa-note{{font-size:12px;color:{p['muted']};margin-top:6px}}
.sa-ladder .row{{display:flex;justify-content:space-between;align-items:center;padding:6px 10px;border-bottom:1px dashed {p['track']};
  font-size:13px;color:{p['text']};font-variant-numeric:tabular-nums}}
.sa-ladder .now{{background:{p['soft']};border:1px solid {p['accent']};border-radius:8px;font-weight:800}}
.sa-big{{font-size:20px;font-weight:900;color:{p['text']}}}
.sa-grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.mo-bar i{{display:block;height:100%}}
.sa-pill,.sa-tag{{text-shadow:none !important}}
.sa-warn{{border-left:3px solid {p['ref']};padding:6px 10px;margin:6px 0;font-size:13px;color:{p['text']}}}
</style>"""


def _kpis(items, p) -> None:
    """items: [(nhãn, giá trị, chú thích, màu chú thích)]"""
    cells = "".join(
        f'<div class="mo-kpi"><small>{_e(a)}</small><b>{_e(b)}</b>'
        f'<small style="color:{d or p["muted"]}">{_e(c)}</small></div>' for a, b, c, d in items)
    _md(f'<div class="sa-grid2">{cells}</div>')


def _table(headers: List[str], rows: List[List[str]], aligns: Optional[List[str]] = None, raw: bool = False,
           min_w: int = 520) -> None:
    aligns = aligns or (["left"] + ["right"] * (len(headers) - 1))
    th = "".join(f'<th style="text-align:{a}">{_e(h)}</th>' for h, a in zip(headers, aligns))
    body = "".join("<tr>" + "".join(f'<td style="text-align:{a}">{c if raw else _e(c)}</td>' for c, a in zip(r, aligns)) + "</tr>"
                   for r in rows)
    _md(f'<div style="overflow-x:auto"><table class="mo-t" style="min-width:{min_w}px">'
        f'<tr>{th}</tr>{body}</table></div>')


def _gauge(score: Optional[float], title: str, p) -> go.Figure:
    v = _num(score)
    col = p["up"] if (v or 0) >= 65 else p["ref"] if (v or 0) >= 45 else p["down"]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=v if v is not None else 0,
        number={"font": {"size": 38, "color": col}, "suffix": "" if v is not None else " (N/A)"},
        title={"text": title, "font": {"size": 13, "color": p["muted"]}},
        gauge={"axis": {"range": [0, 100], "tickcolor": p["muted"], "tickfont": {"size": 10}},
               "bar": {"color": col, "thickness": 0.28}, "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
               "steps": [{"range": [0, 45], "color": "rgba(220,38,38,0.12)"}, {"range": [45, 65], "color": "rgba(217,119,6,0.12)"},
                         {"range": [65, 100], "color": "rgba(22,163,74,0.12)"}]}))
    fig.update_layout(height=210, margin=dict(l=24, r=24, t=40, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(color=p["text"]))
    return fig


def _bars(items, p) -> None:
    """items: [(nhãn, điểm 0–100 hoặc None, chú thích)] → thanh tiến độ."""
    out = []
    for lbl, sc, note in items:
        s = _num(sc)
        col = p["up"] if (s or 0) >= 65 else p["ref"] if (s or 0) >= 45 else p["down"]
        out.append(f'<div class="mo-comp"><span>{_e(lbl)} <small>{_e(note)}</small></span><b>{_f(s, 0) if s is not None else "—"}</b></div>'
                   f'<div class="mo-track"><i style="width:{s or 0:.0f}%;background:{col}"></i></div>')
    _md("".join(out))


# ─────────────────────────────────────────────────────────────────────────────
# Trang
# ─────────────────────────────────────────────────────────────────────────────

def render():
    p = _pal()
    _md(_css(p))
    _md(_extra_css(p))
    _md('<div class="mo-head"><div><div class="mo-title">🔍 Phân Tích Cổ Phiếu</div>'
        '<div class="mo-sub">Giá & kỹ thuật · nền tảng tài chính · định giá & khuyến nghị 12 tháng cho một mã</div></div></div>')

    col1, col2, col3 = st.columns([2, 1, 1], vertical_alignment="bottom")
    with col1:
        symbol = st.text_input("Nhập mã cổ phiếu", value=st.session_state.get("current_symbol", "FPT"),
                               placeholder="VD: FPT, HPG, VCB...", key="stock_symbol_input").upper().strip()
    with col2:
        time_range = st.selectbox("Khoảng thời gian", options=list(TIME_RANGES.keys()),
                                  format_func=lambda k: TIME_RANGES[k][0], index=2)
    with col3:
        analyze_btn = st.button("🔍 Phân Tích", type="primary", use_container_width=True)

    if time_range == "TT":
        cc1, cc2 = st.columns(2)
        with cc1:
            start_date = st.date_input("Từ ngày", value=datetime.now() - timedelta(days=365))
        with cc2:
            end_date = st.date_input("Đến ngày", value=datetime.now())
        days = (end_date - start_date).days
    else:
        days = TIME_RANGES[time_range][1]

    if not symbol:
        st.info("Vui lòng nhập mã cổ phiếu để bắt đầu phân tích.")
        return

    if analyze_btn or symbol != st.session_state.get("last_analyzed"):
        st.session_state["current_symbol"] = symbol
        st.session_state["last_analyzed"] = symbol
        st.session_state.pop("stock_analysis", None)

    if "stock_analysis" not in st.session_state or st.session_state.get("last_analyzed") != symbol:
        with st.spinner(f"Đang phân tích {symbol}..."):
            try:
                svc = StockService(symbol, days=max(days, 400))
                st.session_state["stock_analysis"] = svc.full_analysis()
                st.session_state["stock_service"] = svc
                st.session_state["last_analyzed"] = symbol
            except Exception as e:
                st.error(f"Lỗi phân tích: {e}")
                import traceback
                with st.expander("Chi tiết lỗi (gửi phần này khi báo lỗi)"):
                    st.code(traceback.format_exc())
                return

    analysis = st.session_state.get("stock_analysis", {})
    if not analysis:
        return
    if analysis.get("errors"):
        st.warning("Một số phần chưa xử lý được dữ liệu: " + ", ".join(analysis["errors"]) +
                   ". Các phần còn lại vẫn hiển thị bình thường.")
        with st.expander("Chi tiết lỗi (gửi phần này khi báo lỗi)"):
            for name, tb in analysis["errors"].items():
                st.markdown(f"**{name}**")
                st.code(tb)

    tech = analysis.get("technical", {})
    px = tech.get("data") if tech.get("available") else None
    px = px if isinstance(px, pd.DataFrame) and not px.empty else None

    _hero(symbol, analysis, px, p)

    tab1, tab2, tab3, tab4 = st.tabs(["📈 Biểu đồ giá", "🔧 Kỹ thuật", "📊 Cơ bản", "💰 Định giá"])
    with tab1:
        _tab_price(symbol, analysis, px, p)
    with tab2:
        _tab_tech(symbol, analysis, px, p)
    with tab3:
        _tab_fund(analysis, p)
    with tab4:
        _tab_val(analysis, p)


# ─────────────────────────────────────────────────────────────────────────────
# Đầu trang
# ─────────────────────────────────────────────────────────────────────────────

def _hero(symbol, analysis, px, p) -> None:
    info = analysis.get("company_info") or {}
    cur = analysis.get("current_price") or {}
    name = info.get("company_name") or info.get("short_name") or ""
    price = _num(cur.get("price"))
    if price is not None and 0 < price < 1000:
        price *= 1000
    chg, chg_pct = _num(cur.get("change")), _num(cur.get("change_pct"))
    raw_p = _num(cur.get("price"))
    if raw_p is not None and 0 < raw_p < 1000 and chg is not None:      # nguồn trả giá theo nghìn đồng
        chg *= 1000
    if px is not None and len(px) >= 2 and (chg is None or chg_pct is None):
        c0, c1 = float(px["close"].iloc[-2]), float(px["close"].iloc[-1])
        price = price or c1
        chg, chg_pct = c1 - c0, (c1 / c0 - 1) * 100
    col = _clr(chg, p)
    arrow = "▲" if (chg or 0) > 0 else "▼" if (chg or 0) < 0 else "■"
    range_html, spark = "", ""
    if px is not None:
        last = px.tail(250)
        lo = float(last["low"].min() if "low" in last else last["close"].min())
        hi = float(last["high"].max() if "high" in last else last["close"].max())
        pos = (float(last["close"].iloc[-1]) - lo) / (hi - lo) * 100 if hi > lo else 50
        range_html = (f'<div class="sa-range">Biên 52 tuần: <b>{lo:,.0f}</b> – <b>{hi:,.0f}</b> · đang ở {pos:.0f}% biên'
                      f'<div class="bar"><span class="dot" style="left:calc({pos:.1f}% - 2px)"></span></div></div>')
        spark = _spark(px["close"].tail(120).tolist(), col, w=420, h=86)
    ind = info.get("industry") or info.get("sector") or ""
    chips = "".join(f'<span class="sa-chip">{_e(x)}</span>' for x in (info.get("exchange"), ind) if x)
    sess = ""
    if px is not None:
        sess = f"Phiên {pd.Timestamp(_ts(px).iloc[-1]):%d/%m/%Y}"
    _md(f'<div class="sa-hero"><div><div class="sa-sym">{_e(symbol)} {chips}</div><div class="sa-name">{_e(name)}</div>'
        f'<div class="sa-price">{_f(price)}<span class="sa-chg" style="color:{col}">{arrow} {_f(chg, 0, "", True)} '
        f'({_f(chg_pct, 2, "%", True)})</span></div><div class="sa-note">{_e(sess)} · đơn vị VND</div>{range_html}</div>'
        f'<div style="display:flex;align-items:flex-end">{spark}</div></div>')

    opp = analysis.get("opportunity_score", {}) or {}
    comp = opp.get("composite", {}) or {}
    sub = opp.get("sub_scores", {}) or {}
    inv = analysis.get("investment") or {}
    rec = analysis.get("recommendation") or {}
    hs = ((inv.get("health") or {}).get("score"))
    items = [("Cơ hội đầu tư", comp.get("score")), ("Kỹ thuật", sub.get("technical")), ("Động lượng", sub.get("momentum")),
             ("Cơ bản", sub.get("fundamental")), ("Định giá", sub.get("valuation")), ("Sức khỏe TC", hs)]
    cells = ""
    for lbl, v in items:
        s = _num(v)
        c = p["up"] if (s or 0) >= 65 else p["ref"] if (s or 0) >= 45 else p["down"]
        cells += (f'<div class="sa-sc"><small>{_e(lbl)}</small><b>{_f(s, 0)}<span style="font-size:13px;color:{p["muted"]}">/100</span></b>'
                  f'<div class="mo-track"><i style="width:{s or 0:.0f}%;background:{c}"></i></div></div>')
    _md(f'<div class="sa-scores">{cells}</div>')
    tags = ""
    if comp.get("classification", {}).get("label"):
        tags += f'<span class="sa-tag" style="background:{comp["classification"].get("color", "#64748b")}">{_e(comp["classification"]["label"])}</span>'
    if rec.get("rating"):
        er = rec.get("expected_return")
        tags += (f'<span class="sa-tag" style="background:{rec.get("hex", "#64748b")}">Khuyến nghị 12T: {_e(rec["rating"])}'
                 + (f' · LN kỳ vọng {er:+.1f}%' if er is not None else "") + "</span>")
    if tags:
        _md(f'<div style="margin:2px 0 10px">{tags}</div>')


# ─────────────────────────────────────────────────────────────────────────────
# Tab 1 – Biểu đồ giá
# ─────────────────────────────────────────────────────────────────────────────

def _tab_price(symbol, analysis, px, p) -> None:
    if px is None:
        warning_box(f"Không có dữ liệu giá cho {symbol}: {(analysis.get('technical') or {}).get('reason', '')}")
        return
    ts = _ts(px)
    close = pd.Series(px["close"].astype(float).values, index=ts)
    last250 = px.tail(250)
    r = close.pct_change().dropna().tail(250)
    vol = float(r.std() * np.sqrt(252) * 100) if len(r) > 20 else None
    s1 = close.tail(250)
    mdd = float((s1 / s1.cummax() - 1).min() * 100) if len(s1) > 20 else None
    v20 = float(px["volume"].tail(20).mean()) if "volume" in px else None
    gt20 = float((px["close"] * px["volume"]).tail(20).mean() / 1e9) if "volume" in px else None
    hi52 = float(last250["high"].max() if "high" in last250 else last250["close"].max())
    lo52 = float(last250["low"].min() if "low" in last250 else last250["close"].min())
    c = float(close.iloc[-1])
    r1m, r3m, r1y = _ret(close, 30), _ret(close, 91), _ret(close, 365)
    _kpis([("Giá đóng cửa", _f(c), f"Phiên {ts.iloc[-1]:%d/%m/%Y}", None),
           ("Hiệu suất 1T / 3T", f"{_f(r1m, 1, '%', True)} / {_f(r3m, 1, '%', True)}", f"12 tháng {_f(r1y, 1, '%', True)}", _clr(r1y, p)),
           ("Cách đỉnh 52 tuần", _f((c / hi52 - 1) * 100, 1, "%", True), f"Đỉnh {hi52:,.0f}", None),
           ("Cách đáy 52 tuần", _f((c / lo52 - 1) * 100, 1, "%", True), f"Đáy {lo52:,.0f}", None),
           ("KL bình quân 20 phiên", _f(v20), f"GTGD ~{_f(gt20, 1)} tỷ/phiên", None),
           ("Biến động năm hóa", _f(vol, 1, "%"), f"Sụt giảm tối đa 1 năm {_f(mdd, 1, '%')}", p["down"])], p)

    _section("Biểu đồ giá", "nến ngày · chọn chỉ báo & khoảng thời gian")
    c1, c2, c3 = st.columns([2.4, 1.6, 1])
    with c1:
        overlays = st.multiselect("Chỉ báo trên biểu đồ", ["MA20", "MA50", "MA200", "EMA12", "EMA26", "Bollinger"],
                                  default=["MA20", "MA50"], key="sa_overlays")
    with c2:
        span = st.segmented_control("Khoảng", ["1T", "3T", "6T", "1N", "Tất cả"], default="6T", key="sa_span") or "6T"
    with c3:
        show_vol = st.toggle("Khối lượng", value=True, key="sa_vol")
    days = {"1T": 31, "3T": 92, "6T": 183, "1N": 366}.get(span)
    d = px[(ts >= ts.max() - pd.Timedelta(days=days)).to_numpy()] if days else px
    st.plotly_chart(_candle(d, overlays, show_vol, p), use_container_width=True, config={"displaylogo": False})

    left, right = st.columns([1.5, 1])
    idx = analysis.get("index_history")
    with left:
        _section("So sánh với VN-Index", "chuẩn hóa = 100 tại đầu kỳ đang chọn")
        fig = go.Figure()
        base = d["close"].astype(float)
        fig.add_scatter(x=_ts(d), y=base / base.iloc[0] * 100, name=symbol, line=dict(color=p["accent"], width=2.4))
        if isinstance(idx, pd.DataFrame) and not idx.empty:
            its = _ts(idx)
            ii = idx[(its >= _ts(d).min()).to_numpy()]
            if not ii.empty:
                fig.add_scatter(x=_ts(ii), y=ii["close"] / ii["close"].iloc[0] * 100, name="VN-Index",
                                line=dict(color=p["muted"], width=1.6, dash="dot"))
        fig.add_hline(y=100, line_dash="dot", line_color=p["track"])
        fig.update_layout(**_base_layout(height=300, margin=dict(l=40, r=10, t=10, b=30), hovermode="x unified",
                                         legend=dict(orientation="h", y=1.1, x=0, bgcolor="rgba(0,0,0,0)", font=dict(color=p["text"]))))
        st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
    with right:
        _section("Hiệu suất theo kỳ")
        icl = None
        if isinstance(idx, pd.DataFrame) and not idx.empty:
            icl = pd.Series(idx["close"].astype(float).values, index=_ts(idx))
        rows = []
        ytd_days = (close.index.max() - pd.Timestamp(year=close.index.max().year, month=1, day=1)).days
        for lbl, n in (("1 tuần", 7), ("1 tháng", 30), ("3 tháng", 91), ("6 tháng", 182), ("Từ đầu năm", ytd_days), ("12 tháng", 365)):
            a = _ret(close, n)
            b = _ret(icl, n) if icl is not None else None
            ex = a - b if a is not None and b is not None else None
            rows.append([lbl, f'<b style="font-weight:600;color:{_clr(a, p)}">{_f(a, 1, "%", True)}</b>',
                         f'<b style="font-weight:600;color:{_clr(b, p)}">{_f(b, 1, "%", True)}</b>',
                         f'<b style="color:{_clr(ex, p)}">{_f(ex, 1, " đ%", True)}</b>'])
        _table(["Kỳ", symbol, "VN-Index", "Vượt trội"], rows, raw=True, min_w=340)
        st.caption("Vượt trội = hiệu suất cổ phiếu − VN-Index (điểm %).")


def _candle(d: pd.DataFrame, overlays: List[str], show_vol: bool, p) -> go.Figure:
    x = _ts(d)
    rows = 2 if show_vol and "volume" in d else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.76, 0.24] if rows == 2 else [1])
    fig.add_trace(go.Candlestick(x=x, open=d["open"], high=d["high"], low=d["low"], close=d["close"], name="Giá",
                                 increasing_line_color=p["up"], decreasing_line_color=p["down"],
                                 increasing_fillcolor=p["up"], decreasing_fillcolor=p["down"]), row=1, col=1)
    colors = {"MA20": "#2563eb", "MA50": "#f59e0b", "MA200": "#8b5cf6", "EMA12": "#06b6d4", "EMA26": "#ec4899"}
    for o in overlays:
        col = {"MA20": "SMA_20", "MA50": "SMA_50", "MA200": "SMA_200", "EMA12": "EMA_12", "EMA26": "EMA_26"}.get(o)
        if col and col in d:
            fig.add_scatter(x=x, y=d[col], name=o, line=dict(color=colors[o], width=1.4), row=1, col=1)
    if "Bollinger" in overlays and {"BB_upper", "BB_lower"} <= set(d.columns):
        fig.add_scatter(x=x, y=d["BB_upper"], name="BB trên", line=dict(color="#94a3b8", width=1, dash="dot"), row=1, col=1)
        fig.add_scatter(x=x, y=d["BB_lower"], name="BB dưới", line=dict(color="#94a3b8", width=1, dash="dot"),
                        fill="tonexty", fillcolor="rgba(148,163,184,0.12)", row=1, col=1)
    if rows == 2:
        vc = [p["up"] if c >= o else p["down"] for c, o in zip(d["close"], d["open"])]
        fig.add_bar(x=x, y=d["volume"], name="Khối lượng", marker_color=vc, opacity=0.55, row=2, col=1)
    last = float(d["close"].iloc[-1])
    fig.add_hline(y=last, line_dash="dot", line_color=p["accent"], row=1, col=1,
                  annotation_text=f"{last:,.0f}", annotation_position="right", annotation_font_color=p["accent"])
    fig.update_layout(**_base_layout(height=560, margin=dict(l=50, r=60, t=10, b=20), hovermode="x unified",
                                     legend=dict(orientation="h", y=1.04, x=0, bgcolor="rgba(0,0,0,0)", font=dict(color=p["text"])),
                                     xaxis_rangeslider_visible=False))
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])], showgrid=False)
    fig.update_yaxes(gridcolor=p["track"])
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Tab 2 – Kỹ thuật
# ─────────────────────────────────────────────────────────────────────────────

_COMP_LABEL = {"ma_alignment": "Đường trung bình (MA)", "rsi": "RSI", "macd": "MACD", "volume": "Khối lượng",
               "bollinger": "Bollinger", "adx": "ADX ± DI", "money_flow": "Dòng tiền (CMF/MFI/OBV)"}


def _tab_tech(symbol, analysis, px, p) -> None:
    tech = analysis.get("technical") or {}
    if not tech.get("available") or px is None:
        warning_box(f"Không có dữ liệu kỹ thuật: {tech.get('reason', '')}")
        return
    from reports.pdf_generator import _tech_rows
    signals = tech.get("signals") or {}
    score = tech.get("score") or {}
    trend = signals.get("trend") or {}
    idx = analysis.get("index_history")
    close = pd.Series(px["close"].astype(float).values, index=_ts(px))
    r1m, r3m, r1y = _ret(close, 30), _ret(close, 91), _ret(close, 365)
    rs6 = None
    if isinstance(idx, pd.DataFrame) and not idx.empty:
        icl = pd.Series(idx["close"].astype(float).values, index=_ts(idx))
        a, b = _ret(close, 182), _ret(icl, 182)
        rs6 = a - b if a is not None and b is not None else None
    atr = _num(px["ATR"].dropna().iloc[-1]) if "ATR" in px and px["ATR"].notna().any() else None
    stop = float(close.iloc[-1]) - 2 * atr if atr else None
    rows = _tech_rows(px, idx, signals, stop, r1m, r3m, r1y, rs6)
    tones = [_tone(r[2]) for r in rows if r[2]]
    n_up, n_dn, n_nt = tones.count("up"), tones.count("down"), tones.count("neutral")

    c1, c2, c3 = st.columns([1.25, 1, 1.15])
    with c1:
        tc = trend.get("color", p["muted"])
        crit = "".join(f'<b class="sa-pill {_tone(x)}" style="margin:2px">{_e(x)}</b>' for x in trend.get("criteria", []))
        _md(f'<div class="mo-card"><div class="mo-lbl">Xu hướng tổng hợp</div>'
            f'<div style="font-size:28px;font-weight:900;color:{tc};margin:4px 0">{_e(trend.get("name", "—"))}</div>'
            f'<div>{crit}</div><div class="sa-note">Cách đỉnh 20 phiên {_f(trend.get("pct_from_high"), 1, "%", True)} · '
            f'cách đáy {_f(trend.get("pct_from_low"), 1, "%", True)}</div></div>')
    with c2:
        st.plotly_chart(_gauge(score.get("score"), "Điểm kỹ thuật", p), use_container_width=True, config={"displayModeBar": False})
    with c3:
        tot = max(n_up + n_dn + n_nt, 1)
        _md(f'<div class="mo-card"><div class="mo-lbl">Tổng hợp tín hiệu ({tot} chỉ báo)</div>'
            f'<div class="mo-bar"><i style="width:{n_up / tot * 100:.0f}%;background:{p["up"]}"></i>'
            f'<i style="width:{n_nt / tot * 100:.0f}%;background:{p["ref"]}"></i><i style="width:{n_dn / tot * 100:.0f}%;background:{p["down"]}"></i></div>'
            f'<div class="mo-legend"><b style="font-weight:600;color:{p["up"]}">▲ {n_up} tích cực</b><b style="font-weight:600;color:{p["ref"]}">■ {n_nt} trung tính</b>'
            f'<b style="font-weight:600;color:{p["down"]}">▼ {n_dn} tiêu cực</b></div>'
            f'<div class="sa-note">Cắt lỗ gợi ý (giá − 2×ATR): <b>{_f(stop)}</b></div></div>')
        st.caption("Kỹ thuật dùng để chọn thời điểm, không thay đổi khuyến nghị 12 tháng.")

    left, right = st.columns([1.6, 1])
    with left:
        _section("Bảng chỉ báo", "giá trị phiên gần nhất & diễn giải")
        body = []
        for lbl, val, note in rows:
            tone = _tone(note)
            pill = f'<b class="sa-pill {tone}">{_e(note)}</b>' if note else ""
            body.append([_e(lbl), f"<b>{_e(val)}</b>", pill])
        _table(["Chỉ báo", "Giá trị", "Diễn giải"], body, ["left", "right", "left"], raw=True, min_w=460)
    with right:
        _section("Thành phần điểm kỹ thuật")
        comps = score.get("components") or {}
        items = []
        for k, cmp_ in comps.items():
            if isinstance(cmp_, dict) and cmp_.get("max"):
                s = cmp_.get("score")
                items.append((_COMP_LABEL.get(k, k), None if s is None else s / cmp_["max"] * 100, f"({cmp_['max']} điểm)"))
        _bars(items, p) if items else st.caption("Chưa có thành phần điểm.")
        _section("Hỗ trợ / kháng cự")
        sr = signals.get("support_resistance") or {}
        cnow = float(close.iloc[-1])
        lv = [(v, "Kháng cự") for v in sr.get("resistance", []) or []] + [(v, "Hỗ trợ") for v in sr.get("support", []) or []]
        lv = sorted(lv + [(cnow, "Giá hiện tại")], key=lambda t: -t[0])
        if len(lv) > 1:
            rows_h = "".join(
                f'<div class="row{" now" if t == "Giá hiện tại" else ""}"><span>{t}</span><b>{v:,.0f}</b>'
                f'<b style="font-weight:600;color:{_clr(v - cnow, p) if t != "Giá hiện tại" else p["text"]}">'
                f'{"" if t == "Giá hiện tại" else _f((v / cnow - 1) * 100, 1, "%", True)}</b></div>' for v, t in lv)
            _md(f'<div class="sa-ladder">{rows_h}</div>')
        else:
            st.caption("Chưa xác định được vùng hỗ trợ/kháng cự.")

    _section("Biểu đồ chỉ báo")
    t1, t2, t3, t4 = st.tabs(["RSI", "MACD", "Bollinger", "ADX & dòng tiền"])
    tail = px.tail(250)
    with t1:
        st.plotly_chart(rsi_chart(tail, height=300), use_container_width=True)
    with t2:
        st.plotly_chart(macd_chart(tail, height=300), use_container_width=True)
    with t3:
        st.plotly_chart(bollinger_chart(tail, symbol, height=340), use_container_width=True)
    with t4:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                            subplot_titles=("ADX (14) · +DI / −DI", "MFI (14) & CMF (20)"))
        x = _ts(tail)
        for col, name, color in (("ADX", "ADX", p["text"]), ("PLUS_DI", "+DI", p["up"]), ("MINUS_DI", "−DI", p["down"])):
            if col in tail:
                fig.add_scatter(x=x, y=tail[col], name=name, line=dict(color=color, width=1.4), row=1, col=1)
        if "MFI" in tail:
            fig.add_scatter(x=x, y=tail["MFI"], name="MFI", line=dict(color="#8b5cf6", width=1.4), row=2, col=1)
        if "CMF" in tail:
            fig.add_bar(x=x, y=tail["CMF"] * 100, name="CMF ×100", marker_color=[p["up"] if v > 0 else p["down"] for v in tail["CMF"].fillna(0)],
                        opacity=0.5, row=2, col=1)
        fig.add_hline(y=25, line_dash="dot", line_color=p["muted"], row=1, col=1)
        fig.update_layout(**_base_layout(height=420, margin=dict(l=40, r=10, t=30, b=20), hovermode="x unified",
                                         legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)", font=dict(color=p["text"]))))
        st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# Tab 3 – Cơ bản
# ─────────────────────────────────────────────────────────────────────────────

def _tab_fund(analysis, p) -> None:
    fund = analysis.get("fundamental") or {}
    summ = analysis.get("financial_summary") or {}
    ratios = summ.get("ratios")
    wide = (analysis.get("financials") or {}).get("data")
    inv = analysis.get("investment") or {}
    health = inv.get("health") or {}
    if not fund.get("available") and (ratios is None or getattr(ratios, "empty", True)):
        st.info("Chưa lấy được BCTC – xem trang 🛰️ Nguồn dữ liệu.")
        return
    f_score = fund.get("score") or {}
    from analytics.period_utils import key_to_label

    c1, c2 = st.columns([1, 1.6])
    with c1:
        st.plotly_chart(_gauge(f_score.get("score"), "Điểm phân tích cơ bản", p), use_container_width=True,
                        config={"displayModeBar": False})
        if f_score.get("note"):
            st.caption(f_score["note"])
    with c2:
        hs = health.get("score")
        _section("Financial Health Score", f"{hs:.1f}/100 · {health.get('rating_text', '')}" if hs is not None
                 else "chưa đủ dữ liệu để công bố điểm tổng")
        _bars([(g["label"], g.get("score"), f"({g['weight']}%)") for g in health.get("groups", [])], p)

    if ratios is not None and not ratios.empty:
        last = ratios.iloc[-1]
        prev = ratios.iloc[-2] if len(ratios) > 1 else pd.Series(dtype=float)
        per = key_to_label(ratios.index[-1])

        def kp(lbl, key, unit="%", good="high", d=1):
            v, pv = _num(last.get(key)), _num(prev.get(key))
            delta = (v - pv) if v is not None and pv is not None else None
            better = None if delta is None or abs(delta) < 0.05 else (delta > 0) == (good == "high")
            col = p["muted"] if better is None else (p["up"] if better else p["down"])
            dtxt = "—" if delta is None else f"{delta:+.{d}f}{' điểm %' if unit == '%' else 'x'} so với kỳ trước"
            return (lbl, _f(v, d, unit if unit == "%" else "x"), dtxt, col)

        _section("Chỉ số chính", f"kỳ {per}")
        _kpis([kp("ROE", "roe"), kp("ROA", "roa"), kp("Biên LN gộp", "gross_margin"), kp("Biên LN ròng", "net_margin"),
               kp("Tăng trưởng doanh thu", "revenue_growth"), kp("Tăng trưởng LNST", "net_income_growth"),
               kp("Nợ vay / VCSH", "debt_to_equity", "x", "low", 2), kp("CFO / LNST", "cfo_to_net_income", "x", "high", 2)], p)

    if isinstance(wide, pd.DataFrame) and not wide.empty:
        w = wide.tail(8)
        lbl = [key_to_label(k) for k in w.index]
        g = lambda c: (w[c] / 1e9) if c in w else pd.Series([None] * len(w), index=w.index)  # noqa: E731
        a, b = st.columns(2)
        with a:
            _section("Doanh thu & lợi nhuận", "tỷ đồng · biên LN ròng (trục phải)")
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            rev_col = "revenue" if "revenue" in w else "total_operating_income"
            fig.add_bar(x=lbl, y=g(rev_col), name="Doanh thu", marker_color=p["accent"], opacity=0.85)
            ni = g("net_income_parent") if "net_income_parent" in w else g("net_income")
            fig.add_bar(x=lbl, y=ni, name="LNST cổ đông mẹ", marker_color=p["up"])
            if ratios is not None and "net_margin" in ratios:
                nm = ratios["net_margin"].reindex(w.index)
                fig.add_scatter(x=lbl, y=nm, name="Biên LN ròng %", line=dict(color=p["ref"], width=2.4), mode="lines+markers",
                                secondary_y=True)
            fig.update_layout(**_base_layout(height=320, barmode="group", margin=dict(l=40, r=40, t=10, b=30),
                                             legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)", font=dict(color=p["text"]))))
            st.plotly_chart(fig, use_container_width=True)
        with b:
            _section("Hiệu quả sinh lời", "%")
            fig = go.Figure()
            if ratios is not None:
                rr = ratios.reindex(w.index)
                for col, name, color in (("roe", "ROE", p["accent"]), ("roa", "ROA", p["up"]), ("gross_margin", "Biên LN gộp", "#8b5cf6"),
                                         ("net_margin", "Biên LN ròng", p["ref"])):
                    if col in rr and rr[col].notna().any():
                        fig.add_scatter(x=lbl, y=rr[col], name=name, mode="lines+markers", line=dict(color=color, width=2.2))
            fig.update_layout(**_base_layout(height=320, margin=dict(l=40, r=10, t=10, b=30), hovermode="x unified",
                                             legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)", font=dict(color=p["text"]))))
            st.plotly_chart(fig, use_container_width=True)
        a, b = st.columns(2)
        with a:
            _section("Dòng tiền", "tỷ đồng · FCF = CFO − Capex")
            fig = go.Figure()
            if "cfo" in w:
                cfo = g("cfo")
                capex = -g("capex").abs() if "capex" in w else None
                fig.add_bar(x=lbl, y=cfo, name="CFO", marker_color=p["accent"])
                if capex is not None:
                    fig.add_bar(x=lbl, y=capex, name="Capex", marker_color=p["down"], opacity=0.75)
                    fig.add_scatter(x=lbl, y=cfo + capex, name="FCF", mode="lines+markers", line=dict(color=p["up"], width=2.4))
            fig.update_layout(**_base_layout(height=300, barmode="relative", margin=dict(l=40, r=10, t=10, b=30),
                                             legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)", font=dict(color=p["text"]))))
            st.plotly_chart(fig, use_container_width=True)
        with b:
            _section("Cơ cấu vốn & thanh khoản", "lần")
            fig = go.Figure()
            if ratios is not None:
                rr = ratios.reindex(w.index)
                if "debt_to_equity" in rr:
                    fig.add_bar(x=lbl, y=rr["debt_to_equity"], name="Nợ vay / VCSH", marker_color=p["ref"], opacity=0.8)
                for col, name, color in (("current_ratio", "Thanh toán hiện hành", p["accent"]), ("quick_ratio", "Thanh toán nhanh", p["up"])):
                    if col in rr and rr[col].notna().any():
                        fig.add_scatter(x=lbl, y=rr[col], name=name, mode="lines+markers", line=dict(color=color, width=2.2))
            fig.update_layout(**_base_layout(height=300, margin=dict(l=40, r=10, t=10, b=30), hovermode="x unified",
                                             legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)", font=dict(color=p["text"]))))
            st.plotly_chart(fig, use_container_width=True)

    a, b, c = st.columns(3)
    pio, alt, dp = summ.get("piotroski") or {}, summ.get("altman") or {}, summ.get("dupont")
    with a:
        sc = pio.get("score")
        col = p["up"] if (sc or 0) >= 7 else p["ref"] if (sc or 0) >= 4 else p["down"]
        _md(f'<div class="mo-card"><div class="mo-lbl">Piotroski F-score</div><div class="sa-big" style="color:{col}">'
            f'{sc if sc is not None else "—"}<span style="font-size:13px;color:{p["muted"]}"> / {pio.get("max", 9)}</span></div>'
            f'<div class="sa-note">≥ 7 tốt · 4–6 trung bình · ≤ 3 yếu (Piotroski 2000)</div></div>')
    with b:
        if summ.get("is_bank"):
            _md('<div class="mo-card"><div class="mo-lbl">Altman Z\'\'-score</div><div class="sa-big">Không áp dụng</div>'
                '<div class="sa-note">Mô hình không dùng cho ngân hàng / tổ chức tài chính</div></div>')
        else:
            z = alt.get("score")
            col = p["up"] if (z or 0) > 5.85 else p["ref"] if (z or 0) >= 4.35 else p["down"]
            _md(f'<div class="mo-card"><div class="mo-lbl">Altman Z\'\'-score</div><div class="sa-big" style="color:{col}">{_f(z, 2)}</div>'
                f'<div class="sa-note">{_e(alt.get("zone", alt.get("note", "")))} · &gt; 5,85 an toàn, &lt; 4,35 nguy cơ</div></div>')
    with c:
        if isinstance(dp, pd.DataFrame) and not dp.empty:
            l_ = dp.iloc[-1]
            _md(f'<div class="mo-card"><div class="mo-lbl">DuPont (kỳ gần nhất)</div>'
                f'<div class="sa-big">{_f(l_.get("roe_dupont"), 1, "%")}</div>'
                f'<div class="sa-note">= biên LN ròng {_f(l_.get("net_margin"), 1, "%")} × vòng quay TS {_f(l_.get("asset_turnover"), 2, "x")} '
                f'× đòn bẩy {_f(l_.get("equity_multiplier"), 2, "x")}</div></div>')
        else:
            _md('<div class="mo-card"><div class="mo-lbl">DuPont</div><div class="sa-big">—</div></div>')

    m = fund.get("metrics") or {}
    warns = (m.get("revenue_profit", {}) or {}).get("warnings", []) + (m.get("debt", {}) or {}).get("warnings", []) + \
        (m.get("cashflow", {}) or {}).get("warnings", [])
    if warns:
        _section("Cảnh báo từ BCTC")
        _md("".join(f'<div class="sa-warn">⚠️ {_e(x)}</div>' for x in warns))

    if isinstance(wide, pd.DataFrame) and not wide.empty:
        from reports.excel_export import statement_table
        _section("BCTC tóm tắt", "tỷ đồng · 5 kỳ gần nhất")
        for tab, code in zip(st.tabs(["Kết quả kinh doanh", "Cân đối kế toán", "Lưu chuyển tiền tệ"]), ["is", "bs", "cf"]):
            with tab:
                t = statement_table(wide.tail(5), code)
                if t.empty:
                    st.caption("Không có số liệu")
                    continue
                cols = [c for c in t.columns if c != "Chỉ tiêu"]
                _table(["Chỉ tiêu"] + cols, [[r["Chỉ tiêu"]] + [_f(r[c], 0 if abs(_num(r[c]) or 0) >= 100 else 2) for c in cols]
                                             for _, r in t.iterrows()])
        st.caption("Xem đầy đủ nhiều năm, nguồn từng ô và tải Excel ở trang 📑 Báo Cáo Tài Chính; ~40 chỉ số ở trang 🧮 Chỉ Số Tài Chính.")


# ─────────────────────────────────────────────────────────────────────────────
# Tab 4 – Định giá
# ─────────────────────────────────────────────────────────────────────────────

def _tab_val(analysis, p) -> None:
    inv = analysis.get("investment") or {}
    v = inv.get("valuation") or {}
    rec = analysis.get("recommendation") or inv.get("recommendation") or {}
    summ = analysis.get("financial_summary") or {}
    snap = summ.get("valuation") or {}
    peers = analysis.get("peers") or {}

    c1, c2 = st.columns([1, 2.4])
    with c1:
        if rec.get("rating"):
            er = rec.get("expected_return")
            _md(f'<div style="background:{rec.get("hex", "#64748b")};color:#fff;border-radius:16px;padding:20px;text-align:center">'
                f'<div style="font-size:11px;letter-spacing:.8px;font-weight:700;opacity:.9">KHUYẾN NGHỊ 12 THÁNG</div>'
                f'<div style="font-size:28px;font-weight:900;line-height:1.2;margin:6px 0">{_e(rec["rating"])}</div>'
                + (f'<div style="font-size:13px">Tổng LN kỳ vọng {er:+.1f}%</div>' if er is not None else "")
                + (f'<div style="font-size:12px;opacity:.9">Luật {_e(rec["rule"])}</div>' if rec.get("rule") else "") + "</div>")
    with c2:
        _kpis([("Thị giá", _f(v.get("price")), f"Ngày {v.get('price_date') or '—'}", None),
               ("Giá mục tiêu 12T", _f(v.get("target_12m")), v.get("status", "—"), None),
               ("Upside", _f(v.get("upside"), 1, "%", True), "Giá mục tiêu / thị giá − 1", _clr(v.get("upside"), p)),
               ("Tổng LN kỳ vọng", _f(v.get("expected_return"), 1, "%", True),
                f"Cổ tức {_f(v.get('expected_dividend'))} đ/cp" if v.get("dividends_included") else "Không gồm cổ tức",
                _clr(v.get("expected_return"), p)),
               ("Giá trị nội tại hôm nay", _f(v.get("intrinsic_today")), "Chiết khấu bằng Ke", None),
               ("Độ tin cậy", v.get("confidence") or "—", f"{len(v.get('methods', []))} phương pháp hợp lệ", None)], p)

    methods = v.get("methods") or []
    if methods:
        a, b = st.columns([1.5, 1])
        with a:
            _section("Biên định giá theo phương pháp", "thanh: Bear → Bull · chấm: kịch bản cơ sở")
            st.plotly_chart(_football(v, p), use_container_width=True, config={"displayModeBar": False})
        with b:
            _section("Kịch bản Bear / Base / Bull")
            sc = v.get("scenarios") or {}
            from analytics.valuation_engine import SCEN_LABEL
            rows = []
            for k in ("bear", "base", "bull"):
                r = sc.get(k) or {}
                if r.get("target"):
                    rows.append([SCEN_LABEL[k], f'<b>{_f(r["target"])}</b>',
                                 f'<b style="font-weight:600;color:{_clr(r.get("upside"), p)}">{_f(r.get("upside"), 1, "%", True)}</b>',
                                 _f((r.get("growth") or 0) * 100, 1, "%", True)])
            _table(["Kịch bản", "Giá mục tiêu", "Upside", "Tăng trưởng"], rows, raw=True, min_w=340)
            st.caption("Kịch bản thay đổi bộ giả định (tăng trưởng, biên LN, bội số, Ke) – không cộng trừ thẳng vào giá.")
        _section("Chi tiết từng phương pháp", "chỉ dùng phương pháp hợp lệ, trọng số chuẩn hóa lại")
        _table(["Phương pháp", "Cơ sở", "Hệ số", "Giá trị", "Trọng số", "Upside", "Nguồn / giả định"],
               [[_e(m["name"]), _e(f"{m.get('base_label') or ''} {_f(m.get('base'))}"),
                 _f(m.get("multiple"), 2, "x") if m.get("multiple") else "—", f"<b>{_f(m['fair'])}</b>", f"{m['weight'] * 100:.0f}%",
                 f'<b style="font-weight:600;color:{_clr(m["upside"], p)}">{_f(m["upside"], 1, "%", True)}</b>',
                 f'<span style="font-size:12px">{_e(m["source"])}</span>'] for m in methods],
               ["left", "left", "right", "right", "right", "right", "left"], raw=True)
    else:
        st.info(f"{v.get('status', 'Chưa đủ cơ sở định giá')}. " + " ".join(v.get("notes", [])[:2]))
    for mth, why in v.get("invalid", []):
        st.caption(f"✖ Không dùng {mth}: {why}")

    a, b = st.columns([1.2, 1])
    hist = v.get("history") or {}
    with a:
        _section("Bội số hiện tại so với lịch sử & ngành")
        rows = []
        for key, lbl, d in (("pe", "P/E", 1), ("pb", "P/B", 2), ("ev_ebitda", "EV/EBITDA", 1), ("ps", "P/S", 2)):
            now = _num(snap.get(key))
            hv = list((hist.get(key) or {}).values())
            med = float(np.median(hv)) if len(hv) >= 3 else None
            peer = _num(peers.get(key)) if key in ("pe", "pb") and (peers.get("n") or 0) >= 3 else None
            ref = med or peer
            if now is None or ref is None or now <= 0:
                verdict = '<b class="sa-pill neutral">Chưa đủ số liệu</b>' if now is None or ref is None else '<b class="sa-pill down">Không áp dụng</b>'
            else:
                gap = (now / ref - 1) * 100
                verdict = (f'<b class="sa-pill up">Rẻ hơn {abs(gap):.0f}%</b>' if gap < -10 else
                           f'<b class="sa-pill down">Đắt hơn {gap:.0f}%</b>' if gap > 10 else
                           '<b class="sa-pill neutral">Tương đương</b>')
            rows.append([lbl, f"<b>{_f(now, d, 'x')}</b>", _f(med, d, "x"), _f(peer, d, "x"), verdict])
        _table(["Bội số", "Hiện tại", "Trung vị 5 năm", f"Ngành ({peers.get('group') or '—'})", "So sánh"], rows,
               ["left", "right", "right", "right", "left"], raw=True)
        st.caption("So sánh với trung vị lịch sử của chính doanh nghiệp (nếu có ≥ 3 năm), nếu không thì với trung vị ngành.")
    with b:
        pe_h = hist.get("pe") or {}
        if pe_h:
            _section("P/E cuối năm trong quá khứ")
            fig = go.Figure(go.Bar(x=[str(y) for y in pe_h], y=list(pe_h.values()), marker_color=p["accent"], opacity=0.8,
                                   text=[f"{x:.1f}x" for x in pe_h.values()], textposition="outside"))
            now = _num(snap.get("pe"))
            if now:
                fig.add_hline(y=now, line_dash="dash", line_color=p["ref"], annotation_text=f"Hiện tại {now:.1f}x",
                              annotation_position="top left", annotation_font_color=p["ref"])
            fig.update_layout(**_base_layout(height=290, margin=dict(l=30, r=10, t=20, b=30), showlegend=False))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    sens = v.get("sensitivity") or []
    if sens and v.get("price"):
        _section("Độ nhạy giá mục tiêu", "thay đổi bội số × thay đổi lợi nhuận/BV · xanh ≥ thị giá")
        price = v["price"]
        rows = []
        for r in sens:
            cells = []
            for k in (-0.1, 0.0, 0.1):
                val = r[k]
                col = p["up"] if val >= price else p["down"]
                cells.append(f'<b style="color:{col}">{val:,.0f}</b>')
            rows.append([f"Bội số {r['mult_chg'] * 100:+.0f}%"] + cells)
        _table(["", "Lợi nhuận/BV −10%", "Cơ sở", "Lợi nhuận/BV +10%"], rows, raw=True)

    with st.expander("❓ Vì sao ra khuyến nghị này & giá mục tiêu được tính thế nào?"):
        for line in inv.get("explanation") or rec.get("reasons") or []:
            st.markdown("• " + line)
        st.caption("Chi tiết đầy đủ (điểm sức khỏe, rủi ro, chỉnh ngưỡng, định giá tại ngày) ở trang 🎯 Khuyến Nghị Đầu Tư.")
    dcf = ((analysis.get("valuation") or {}).get("score") or {}).get("dcf") or {}
    if dcf.get("available"):
        with st.expander("DCF đơn giản theo EPS (mô hình cũ – chỉ tham khảo)"):
            cols = st.columns(3)
            for i, (name, val) in enumerate((dcf.get("scenarios") or {}).items()):
                cols[i % 3].metric(f"Kịch bản {name}", f"{val:,.0f}")
            for k, val in (dcf.get("assumptions") or {}).items():
                st.caption(f"• {k}: {val}")


def _football(v: Dict[str, Any], p) -> go.Figure:
    sc = v.get("scenarios") or {}
    names = {"pe": "P/E dự phóng", "pb": "P/B dự phóng", "dcf": "DCF (FCFF)", "ev_ebitda": "EV/EBITDA"}
    fig = go.Figure()
    ylab = []
    for m in v.get("methods", []):
        k = m["key"]
        vals = [((sc.get(s) or {}).get("methods") or {}).get(k, {}).get("target") for s in ("bear", "base", "bull")]
        vals = [x for x in vals if x]
        lo, hi = (min(vals), max(vals)) if vals else (m["fair"], m["fair"])
        lab = f"{names.get(k, k)} ({m['weight'] * 100:.0f}%)"
        ylab.append(lab)
        fig.add_bar(y=[lab], x=[max(hi - lo, 1)], base=[lo], orientation="h", marker_color=p["accent"], opacity=0.35,
                    hovertemplate=f"{lab}<br>Bear–Bull: {lo:,.0f} – {hi:,.0f}<extra></extra>", showlegend=False)
        fig.add_scatter(y=[lab], x=[m["fair"]], mode="markers+text", marker=dict(size=13, color=p["accent"], symbol="diamond"),
                        text=[f"{m['fair']:,.0f}"], textposition="top center", showlegend=False,
                        hovertemplate=f"Cơ sở: {m['fair']:,.0f}<extra></extra>")
    price, tgt = v.get("price"), v.get("target_12m")
    if price:
        fig.add_vline(x=price, line_dash="dash", line_color=p["muted"], annotation_text=f"Thị giá {price:,.0f}",
                      annotation_position="bottom right", annotation_font_color=p["muted"])
    if tgt:
        fig.add_vline(x=tgt, line_color=p["up"], annotation_text=f"Mục tiêu {tgt:,.0f}", annotation_position="top right",
                      annotation_font_color=p["up"])
    fig.update_layout(**_base_layout(height=110 + 62 * max(len(ylab), 1), margin=dict(l=10, r=20, t=30, b=40), bargap=0.45))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(gridcolor=p["track"], tickformat=",.0f")
    return fig
