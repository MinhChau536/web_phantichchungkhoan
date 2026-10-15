"""
Trang – So sánh 2–5 cổ phiếu (giao diện bảng điều khiển).

  1. Chọn mã (gõ tay hoặc thêm nhanh các mã cùng ngành)
  2. Thẻ từng mã: giá, biến động, sparkline, P/E, ROE, vốn hóa, hạng tổng hợp trong nhóm
  3. Nhận xét nhanh (rút ra từ số liệu: rẻ nhất, sinh lời cao nhất, động lượng mạnh nhất, rủi ro thấp nhất)
  4. Bảng so sánh theo nhóm chỉ tiêu – tô nổi giá trị tốt nhất / kém nhất mỗi dòng
  5. Hiệu suất giá chuẩn hóa (chọn kỳ) + radar điểm tương đối 6 khía cạnh
  6. Rủi ro – lợi nhuận (biến động, sụt giảm tối đa, tương quan)
  7. Biểu đồ theo từng tiêu chí

Toàn bộ số liệu lấy từ BCTC & giá thật qua ScreenerService; thiếu số liệu hiển thị "—", không tự điền.
"""
from __future__ import annotations

import html
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.charts import _base_layout
from pages.market_overview import _color, _css, _f, _md, _pal, _section, _spark
from services.screener_service import PROFILE_COLUMNS, ScreenerService, compare

SERIES = ["#2563eb", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6"]
PERIODS = {"1Th": 31, "3Th": 92, "6Th": 183, "1N": 365}

# (khóa, nhãn, định dạng, chiều tốt: "high" | "low" | None)
GROUPS = [
    ("Định giá", [("pe", "P/E", "x", "low"), ("pb", "P/B", "x", "low"), ("ev_ebitda", "EV/EBITDA", "x", "low"),
                  ("dividend_yield", "Tỷ suất cổ tức", "%", "high"), ("market_cap", "Vốn hóa (tỷ đồng)", "bn", None)]),
    ("Khả năng sinh lời", [("roe", "ROE", "%", "high"), ("roa", "ROA", "%", "high"),
                           ("gross_margin", "Biên LN gộp", "%", "high"), ("net_margin", "Biên LN ròng", "%", "high")]),
    ("Tăng trưởng", [("revenue_growth", "Tăng trưởng doanh thu", "%s", "high"),
                     ("net_income_growth", "Tăng trưởng LNST", "%s", "high")]),
    ("Sức khỏe tài chính", [("debt_to_equity", "Nợ vay / VCSH", "x", "low"),
                            ("current_ratio", "Thanh toán hiện hành", "x", "high"),
                            ("fscore", "Piotroski F-score (0–9)", "int", "high"), ("zscore", "Altman Z''-score", "x", "high")]),
    ("Hiệu suất giá", [("change_1m", "1 tháng", "%s", "high"), ("change_3m", "3 tháng", "%s", "high"),
                       ("change_1y", "12 tháng", "%s", "high")]),
    ("Rủi ro (1 năm)", [("vol", "Biến động năm hóa", "%", "low"), ("mdd", "Sụt giảm tối đa", "%s", "high")]),
]

# Khía cạnh radar: (nhãn, [(khóa, chiều tốt)])
RADAR = [
    ("Định giá", [("pe", "low"), ("pb", "low")]),
    ("Sinh lời", [("roe", "high"), ("net_margin", "high")]),
    ("Tăng trưởng", [("revenue_growth", "high"), ("net_income_growth", "high")]),
    ("Sức khỏe TC", [("debt_to_equity", "low"), ("current_ratio", "high"), ("fscore", "high")]),
    ("Động lượng", [("change_3m", "high"), ("change_1y", "high")]),
    ("Ổn định giá", [("vol", "low"), ("mdd", "high")]),
]


def _fmt(v, kind: str) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if kind == "x":
        return f"{v:,.2f}x"
    if kind == "%":
        return f"{v:,.1f}%"
    if kind == "%s":
        return f"{v:+,.1f}%"
    if kind == "bn":
        return f"{v / 1e9:,.0f}"
    if kind == "int":
        return f"{v:.0f}"
    return f"{v:,.2f}"


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return None if np.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _risk_metrics(prices: pd.DataFrame) -> Dict[str, Dict[str, Optional[float]]]:
    out = {}
    for c in prices.columns:
        s = prices[c].dropna().astype(float)
        if len(s) < 30:
            out[c] = {"vol": None, "mdd": None}
            continue
        s = s[s.index >= s.index.max() - pd.Timedelta(days=365)]
        r = s.pct_change().dropna()
        out[c] = {"vol": float(r.std() * np.sqrt(252) * 100),
                  "mdd": float((s / s.cummax() - 1).min() * 100)}
    return out


def _relative_scores(table: pd.DataFrame) -> pd.DataFrame:
    """Điểm 0–100 trong NHÓM đang so sánh cho từng khía cạnh radar (min–max, đảo chiều nếu thấp là tốt)."""
    out = pd.DataFrame(index=table.index)
    for label, items in RADAR:
        parts = []
        for key, good in items:
            if key not in table.columns:
                continue
            v = pd.to_numeric(table[key], errors="coerce")
            if key == "pe":
                v = v.where(v > 0)                      # P/E âm (lỗ) không coi là "rẻ"
            if v.notna().sum() < 2:
                continue
            lo, hi = v.min(), v.max()
            sc = (v - lo) / (hi - lo) * 100 if hi > lo else pd.Series(50.0, index=v.index).where(v.notna())
            parts.append(100 - sc if good == "low" else sc)
        out[label] = pd.concat(parts, axis=1).mean(axis=1) if parts else np.nan
    return out


def _best_worst(vals: List[Optional[float]], good: Optional[str], key: str):
    clean = [(i, v) for i, v in enumerate(vals) if v is not None and not (key == "pe" and v <= 0)]
    if good is None or len(clean) < 2 or len({round(v, 6) for _, v in clean}) == 1:
        return None, None
    best = (min if good == "low" else max)(clean, key=lambda t: t[1])[0]
    worst = (max if good == "low" else min)(clean, key=lambda t: t[1])[0]
    return best, (worst if worst != best else None)


# ─────────────────────────── Khối giao diện ───────────────────────────────────
def _cards(table: pd.DataFrame, prices: pd.DataFrame, ranks: Dict[str, int], p: Dict[str, str]):
    syms = table.index.tolist()
    cols = st.columns(len(syms))
    for i, (col, sym) in enumerate(zip(cols, syms)):
        r = table.loc[sym]
        color = SERIES[i % len(SERIES)]
        s = prices[sym].dropna().tail(60).tolist() if sym in prices.columns else []
        price = _num(r.get("price"))
        ch1 = _num(r.get("change_1m"))
        rk = ranks.get(sym)
        badge = (f'<span style="background:{p["accent"]};color:#fff;font-size:10.5px;font-weight:800;'
                 f'padding:2px 8px;border-radius:999px">#{rk} tổng hợp</span>' if rk else "")
        mc = _num(r.get("market_cap"))
        with col:
            _md(f'<div class="mo-card" style="border-top:4px solid {color}">'
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'<div style="font-size:20px;font-weight:900;color:{p["text"]}">{html.escape(sym)}</div>{badge}</div>'
                f'<div class="mo-val" style="font-size:22px">{_f(price, 0)}</div>'
                f'<div class="mo-chg" style="color:{_color(ch1, p)}">1 tháng: {_f(ch1, 1, "%", True)}</div>'
                f'<div style="margin-top:4px">{_spark(s, color, h=38)}</div>'
                f'<div class="mo-meta"><span>P/E <b style="color:{p["text"]}">{_fmt(_num(r.get("pe")), "x")}</b></span>'
                f'<span>ROE <b style="color:{p["text"]}">{_fmt(_num(r.get("roe")), "%")}</b></span></div>'
                f'<div class="mo-meta"><span>Vốn hóa</span><b style="color:{p["text"]}">'
                f'{_fmt(mc, "bn") + " tỷ" if mc else "—"}</b></div></div>')


def _insights(table: pd.DataFrame, p: Dict[str, str]):
    def pick(key, good, fmt, text):
        v = pd.to_numeric(table.get(key), errors="coerce") if key in table.columns else pd.Series(dtype=float)
        if key == "pe":
            v = v.where(v > 0)
        v = v.dropna()
        if len(v) < 2:
            return None
        sym = v.idxmin() if good == "low" else v.idxmax()
        return f'<b style="color:{p["accent"]}">{html.escape(sym)}</b> {text} <b>{_fmt(v[sym], fmt)}</b>'
    items = [
        ("💰", pick("pe", "low", "x", "định giá rẻ nhất theo P/E:")),
        ("🏆", pick("roe", "high", "%", "sinh lời trên vốn cao nhất, ROE")),
        ("📈", pick("revenue_growth", "high", "%s", "tăng trưởng doanh thu nhanh nhất:")),
        ("🚀", pick("change_3m", "high", "%s", "động lượng 3 tháng mạnh nhất:")),
        ("🛡️", pick("vol", "low", "%", "biến động giá thấp nhất:")),
        ("🏦", pick("debt_to_equity", "low", "x", "đòn bẩy thấp nhất, Nợ vay/VCSH")),
    ]
    rows = "".join(f'<div style="display:flex;gap:10px;padding:7px 0;border-bottom:1px solid {p["track"]};'
                   f'font-size:13px;color:{p["text"]}"><span>{ic}</span><span>{t}</span></div>'
                   for ic, t in items if t)
    if rows:
        _md(f'<div class="mo-card"><div class="mo-lbl" style="margin-bottom:4px">Nhận xét nhanh</div>{rows}'
            f'<div style="font-size:11px;color:{p["muted"]};margin-top:6px">So sánh trong nhóm đang chọn, '
            f'dựa trên BCTC năm gần nhất và giá 1 năm.</div></div>')


def _compare_table(table: pd.DataFrame, p: Dict[str, str]) -> str:
    syms = table.index.tolist()
    head = "".join(f'<th style="text-align:right"><span style="display:inline-block;width:8px;height:8px;'
                   f'border-radius:50%;background:{SERIES[i % len(SERIES)]};margin-right:6px"></span>'
                   f'{html.escape(s)}</th>' for i, s in enumerate(syms))
    good_bg = "rgba(34,197,94,0.16)" if p["dark"] else "rgba(22,163,74,0.10)"
    body = ""
    for gname, items in GROUPS:
        body += (f'<tr><td colspan="{len(syms) + 1}" style="background:{p["soft"]};color:{p["accent"]};'
                 f'font-weight:800;font-size:11.5px;text-transform:uppercase;letter-spacing:.5px;text-align:left">'
                 f'{gname}</td></tr>')
        for key, label, kind, good in items:
            vals = [_num(table.loc[s].get(key)) if key in table.columns else None for s in syms]
            if all(v is None for v in vals):
                continue
            b, w = _best_worst(vals, good, key)
            cells = ""
            for i, v in enumerate(vals):
                txt = _fmt(v, kind)
                if i == b:
                    cells += (f'<td><span style="background:{good_bg};color:{p["up"]};font-weight:800;'
                              f'padding:2px 8px;border-radius:6px">★ {txt}</span></td>')
                elif i == w:
                    cells += f'<td style="color:{p["down"]}">{txt}</td>'
                else:
                    cells += f'<td>{txt}</td>'
            hint = {"low": " ↓", "high": " ↑"}.get(good, "")
            body += (f'<tr><td style="text-align:left;color:{p["muted"]}">{label}'
                     f'<small style="opacity:.7">{hint}</small></td>{cells}</tr>')
    return (f'<div class="mo-card" style="padding:6px 8px;overflow-x:auto"><table class="mo-t mo-r">'
            f'<thead><tr><th style="text-align:left">Chỉ tiêu</th>{head}</tr></thead><tbody>{body}</tbody></table>'
            f'<div style="font-size:11px;color:{p["muted"]};padding:6px 10px">★ tốt nhất trong nhóm · '
            f'<span style="color:{p["down"]}">đỏ</span> kém nhất · ↑ cao là tốt · ↓ thấp là tốt · '
            f'P/E âm (doanh nghiệp lỗ) không xếp hạng</div></div>')


def _perf_chart(prices: pd.DataFrame, days: int, p: Dict[str, str]) -> go.Figure:
    end = prices.index.max()
    d = prices[prices.index >= end - pd.Timedelta(days=days)].ffill().dropna(how="any")
    fig = go.Figure()
    if d.empty:
        return fig
    norm = d / d.iloc[0] * 100
    for i, c in enumerate(norm.columns):
        last = float(norm[c].iloc[-1])
        fig.add_trace(go.Scatter(x=norm.index, y=norm[c], name=f"{c}  {last - 100:+.1f}%",
                                 line=dict(color=SERIES[i % len(SERIES)], width=2.2),
                                 hovertemplate=f"<b>{c}</b> %{{y:.1f}}<extra></extra>"))
    fig.add_hline(y=100, line=dict(color=p["muted"], width=1, dash="dot"))
    lay = _base_layout(height=380)
    lay.update(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", hovermode="x unified",
               margin=dict(l=8, r=8, t=10, b=8), legend=dict(orientation="h", y=1.08, x=0, bgcolor="rgba(0,0,0,0)"))
    fig.update_layout(**lay)
    fig.update_yaxes(gridcolor=p["track"], ticksuffix="")
    fig.update_xaxes(showgrid=False)
    return fig


def _radar(scores: pd.DataFrame, p: Dict[str, str]) -> go.Figure:
    cats = list(scores.columns)
    fig = go.Figure()
    for i, sym in enumerate(scores.index):
        vals = scores.loc[sym].fillna(0).tolist()
        c = SERIES[i % len(SERIES)]
        fig.add_trace(go.Scatterpolar(r=vals + vals[:1], theta=cats + cats[:1], name=sym, fill="toself",
                                      line=dict(color=c, width=2), opacity=0.55,
                                      hovertemplate=f"<b>{sym}</b> %{{theta}}: %{{r:.0f}}/100<extra></extra>"))
    fig.update_layout(height=380, paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=80, r=80, t=30, b=20),
                      font=dict(color=p["text"]), showlegend=True,
                      legend=dict(orientation="h", y=-0.08, bgcolor="rgba(0,0,0,0)"),
                      polar=dict(bgcolor="rgba(0,0,0,0)",
                                 radialaxis=dict(range=[0, 100], showticklabels=False, gridcolor=p["track"]),
                                 angularaxis=dict(gridcolor=p["track"], tickfont=dict(size=12, color=p["text"]))))
    return fig


def _risk_scatter(table: pd.DataFrame, p: Dict[str, str]) -> go.Figure:
    fig = go.Figure()
    for i, sym in enumerate(table.index):
        vol, ret = _num(table.loc[sym].get("vol")), _num(table.loc[sym].get("change_1y"))
        if vol is None or ret is None:
            continue
        mc = _num(table.loc[sym].get("market_cap")) or 0
        size = 18 + (np.sqrt(mc / 1e12) * 6 if mc else 0)
        fig.add_trace(go.Scatter(x=[vol], y=[ret], mode="markers+text", text=[sym], textposition="top center",
                                 marker=dict(size=min(size, 60), color=SERIES[i % len(SERIES)], opacity=0.85,
                                             line=dict(color="#fff", width=1.5)), name=sym,
                                 hovertemplate=f"<b>{sym}</b><br>Biến động: %{{x:.1f}}%<br>Lợi nhuận 12T: %{{y:+.1f}}%<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=p["muted"], width=1, dash="dot"))
    lay = _base_layout(height=340)
    lay.update(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False,
               margin=dict(l=8, r=8, t=10, b=8))
    fig.update_layout(**lay)
    fig.update_xaxes(title_text="Biến động năm hóa (%)", gridcolor=p["track"])
    fig.update_yaxes(title_text="Lợi nhuận 12 tháng (%)", gridcolor=p["track"], ticksuffix="%")
    return fig


def _corr_heatmap(prices: pd.DataFrame, p: Dict[str, str]) -> Optional[go.Figure]:
    d = prices[prices.index >= prices.index.max() - pd.Timedelta(days=365)]
    r = d.pct_change().dropna(how="all")
    if r.shape[1] < 2 or len(r) < 30:
        return None
    cm = r.corr()
    fig = go.Figure(go.Heatmap(z=cm.values, x=cm.columns, y=cm.index, zmin=-1, zmax=1,
                               colorscale=[[0, "#dc2626"], [0.5, "#f8fafc" if not p["dark"] else "#1f2937"], [1, "#2563eb"]],
                               text=np.round(cm.values, 2), texttemplate="%{text:.2f}", showscale=False,
                               hovertemplate="%{y} – %{x}: %{z:.2f}<extra></extra>"))
    fig.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=8, r=8, t=10, b=8), font=dict(color=p["text"]))
    fig.update_yaxes(autorange="reversed")
    return fig


def _metric_bars(table: pd.DataFrame, key: str, label: str, kind: str, good: Optional[str], p: Dict[str, str]) -> go.Figure:
    v = pd.to_numeric(table[key], errors="coerce") if key in table.columns else pd.Series(dtype=float)
    syms = table.index.tolist()
    colors = [SERIES[i % len(SERIES)] for i in range(len(syms))]
    vals = v.reindex(syms)
    scale = 1e9 if kind == "bn" else 1
    fig = go.Figure(go.Bar(x=syms, y=vals / scale, marker_color=colors,
                           text=[_fmt(x, kind) for x in vals], textposition="outside", cliponaxis=False,
                           hovertemplate="<b>%{x}</b>: %{text}<extra></extra>"))
    med = vals.median()
    if pd.notna(med):
        fig.add_hline(y=med / scale, line=dict(color=p["muted"], width=1, dash="dash"),
                      annotation_text=f"Trung vị nhóm {_fmt(med, kind)}", annotation_position="top left",
                      annotation_font=dict(size=11, color=p["muted"]))
    lay = _base_layout(height=330)
    lay.update(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False,
               margin=dict(l=8, r=8, t=30, b=8))
    fig.update_layout(**lay)
    fig.update_yaxes(gridcolor=p["track"], zeroline=True, zerolinecolor=p["muted"])
    fig.update_xaxes(showgrid=False)
    return fig


# ─────────────────────────── Trang ────────────────────────────────────────────
def _add_peers():
    from analytics.peers import find_sector_basket
    from data.ticker_directory import BASKETS
    cur = [s.strip().upper() for s in st.session_state.get("cmp_input", "").split(",") if s.strip()]
    base = cur[0] if cur else st.session_state.get("current_symbol", "FPT")
    basket = find_sector_basket(base)
    if basket:
        peers = [s for s in BASKETS.get(basket, []) if s != base][: 5 - 1]
        st.session_state["cmp_input"] = ",".join([base] + peers)


def render():
    p = _pal()
    _md(_css(p))
    _md(f'<div class="mo-head"><div><div class="mo-title">⚖️ So Sánh Cổ Phiếu</div>'
        f'<div class="mo-sub">Đặt 2–5 mã cạnh nhau: định giá, sinh lời, tăng trưởng, sức khỏe tài chính, '
        f'hiệu suất và rủi ro – tô nổi mã tốt nhất ở từng tiêu chí</div></div></div>')

    st.session_state.setdefault("cmp_input", f"{st.session_state.get('current_symbol', 'FPT')},CMG,ELC")
    c1, c2, c3 = st.columns([5, 1.6, 1.2], vertical_alignment="bottom")
    with c1:
        st.text_input("Các mã cần so sánh (2–5 mã, cách nhau dấu phẩy)", key="cmp_input")
    with c2:
        st.button("➕ Thêm mã cùng ngành", on_click=_add_peers, use_container_width=True,
                  help="Giữ mã đầu tiên và điền thêm các mã cùng rổ ngành")
    with c3:
        go_btn = st.button("So sánh", type="primary", use_container_width=True)

    symbols = list(dict.fromkeys(s.strip().upper() for s in st.session_state["cmp_input"].split(",") if s.strip()))[:5]
    if len(symbols) < 2:
        st.info("Nhập ít nhất 2 mã.")
        return

    # Giữ kết quả giữa các lần tương tác (đổi kỳ, đổi tiêu chí) – chỉ tải lại khi bấm So sánh
    if go_btn:
        with st.spinner(f"Đang tải dữ liệu {len(symbols)} mã..."):
            st.session_state["cmp_res"] = compare(symbols)
            st.session_state["cmp_syms"] = symbols
    res = st.session_state.get("cmp_res")
    if not res:
        st.caption("Bấm **So sánh** để tải dữ liệu.")
        return
    if st.session_state.get("cmp_syms") != symbols:
        st.caption("Danh sách mã đã thay đổi – bấm **So sánh** để cập nhật.")

    table = res["table"]
    if table.empty:
        st.error("Không lấy được dữ liệu.")
        return
    table = table.drop_duplicates("symbol").set_index("symbol")
    prices = res.get("prices")
    if prices is None or prices.empty:
        norm = res.get("normalized_prices", pd.DataFrame())
        prices = norm
    risk = _risk_metrics(prices) if not prices.empty else {}
    for sym in table.index:
        for k in ("vol", "mdd"):
            table.loc[sym, k] = (risk.get(sym) or {}).get(k)

    errs = table["error"].dropna() if "error" in table.columns else pd.Series(dtype=str)
    for sym, e in errs.items():
        st.warning(f"{sym}: không tải đủ dữ liệu ({e}).")

    ranked = ScreenerService.rank(table.reset_index())
    ranks = {}
    if "rank_score" in ranked.columns:
        ranked = ranked.sort_values("rank_score", ascending=False).reset_index(drop=True)
        ranks = {s: i + 1 for i, s in enumerate(ranked["symbol"]) if pd.notna(ranked.loc[i, "rank_score"])}

    _cards(table, prices, ranks, p)

    # ── Bảng so sánh + nhận xét ──
    _section("Bảng so sánh chỉ số", f"BCTC năm gần nhất{(' · ' + str(table['fin_period'].dropna().iloc[0])) if 'fin_period' in table and table['fin_period'].notna().any() else ''}")
    c_t, c_i = st.columns([2.3, 1], gap="medium")
    with c_t:
        _md(_compare_table(table, p))
    with c_i:
        _insights(table, p)
        if ranks:
            st.caption("Hạng tổng hợp: bình quân thứ hạng phân vị theo ROE, tăng trưởng DT & LNST, P/E, P/B, "
                       "Nợ/VCSH và hiệu suất 3 tháng (P/E, P/B, Nợ/VCSH thấp là tốt).")

    # ── Hiệu suất & radar ──
    _section("Hiệu suất giá & hồ sơ tương đối", "Giá chuẩn hóa = 100 tại đầu kỳ · radar chấm điểm 0–100 trong nhóm")
    c_l, c_r = st.columns([1.5, 1], gap="medium")
    with c_l:
        per = st.segmented_control("Kỳ", list(PERIODS), default="6Th", key="cmp_period",
                                   label_visibility="collapsed") or "6Th"
        if not prices.empty:
            st.plotly_chart(_perf_chart(prices, PERIODS[per], p), use_container_width=True, theme=None,
                            config={"displayModeBar": False})
    with c_r:
        scores = _relative_scores(table)
        if scores.notna().any().any():
            st.plotly_chart(_radar(scores, p), use_container_width=True, theme=None, config={"displayModeBar": False})
        st.caption("Điểm tương đối giữa các mã đang so sánh (cao nhất nhóm = 100, thấp nhất = 0), không phải điểm tuyệt đối.")

    # ── Rủi ro ──
    _section("Rủi ro – lợi nhuận", "1 năm gần nhất · kích thước bong bóng theo vốn hóa")
    c_a, c_b = st.columns([1.3, 1], gap="medium")
    with c_a:
        st.plotly_chart(_risk_scatter(table, p), use_container_width=True, theme=None, config={"displayModeBar": False})
    with c_b:
        hm = _corr_heatmap(prices, p) if not prices.empty else None
        if hm is not None:
            _md(f'<div class="mo-lbl" style="margin-bottom:2px">Tương quan lợi suất ngày</div>')
            st.plotly_chart(hm, use_container_width=True, theme=None, config={"displayModeBar": False})
            st.caption("Gần 1: biến động cùng chiều (ít đa dạng hóa) · gần 0 hoặc âm: đa dạng hóa tốt hơn.")

    # ── Theo tiêu chí ──
    _section("So sánh theo tiêu chí", "Chọn một chỉ tiêu để xem chi tiết")
    options = [(k, lbl, kind, good) for _, items in GROUPS for k, lbl, kind, good in items
               if k in table.columns and pd.to_numeric(table[k], errors="coerce").notna().any()]
    if options:
        labels = [o[1] for o in options]
        c_s, c_s2 = st.columns(2, gap="medium")
        for col, default, key in ((c_s, "ROE", "cmp_m1"), (c_s2, "P/E", "cmp_m2")):
            with col:
                idx = labels.index(default) if default in labels else 0
                lbl = st.selectbox("Chỉ tiêu", labels, index=idx, key=key, label_visibility="collapsed")
                k, l, kind, good = options[labels.index(lbl)]
                st.plotly_chart(_metric_bars(table, k, l, kind, good, p), use_container_width=True, theme=None,
                                config={"displayModeBar": False})

    # ── Tải dữ liệu ──
    export = table.drop(columns=["error"], errors="ignore").rename(columns={**PROFILE_COLUMNS, "vol": "Biến động năm hóa %",
                                                                             "mdd": "Sụt giảm tối đa %"})
    st.download_button("⬇️ Tải bảng so sánh (CSV)", export.to_csv().encode("utf-8-sig"),
                       file_name=f"so_sanh_{'_'.join(table.index)}.csv", mime="text/csv")
