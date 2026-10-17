"""
giao_dien/thi_truong.py – gộp từ 5 module (15/10/2026).

MỤC LỤC
  • pages/market_overview.py – Trang 1 – Tổng quan thị trường (giao diện kiểu bảng điều khiển chuyên nghiệp).
      hàm/lớp chính: render
  • components/recommendation_view.py – Thành phần hiển thị kết quả Khuyến nghị 12 tháng (dùng trong tab 🎯 Khuyến nghị của trang Phân tích cổ phiếu).
  • pages/stock_analysis.py – Trang – 🔍 Phân Tích Cổ Phiếu (giao diện bảng điều khiển).
      hàm/lớp chính: render_stock_analysis
  • pages/screener.py – Trang – Bộ lọc cổ phiếu theo chỉ số tính từ BCTC & giá, kèm xếp hạng tổng hợp.
      hàm/lớp chính: render_screener
  • pages/compare.py – Trang – So sánh 2–5 cổ phiếu (giao diện bảng điều khiển).
      hàm/lớp chính: render_compare

Tên trùng giữa các phần đã được đổi (tên cũ → tên mới trong file này):
  stock_analysis._f → _f_stock_analysis
  stock_analysis._extra_css → _extra_css_stock_analysis
  stock_analysis._gauge → _gauge_stock_analysis
  stock_analysis.render → render_stock_analysis
  stock_analysis._target_range → _target_range_stock_analysis
  screener.render → render_screener
  compare.PERIODS → PERIODS_compare
  compare._num → _num_compare
  compare.render → render_compare
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/market_overview.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Trang 1 – Tổng quan thị trường (giao diện kiểu bảng điều khiển chuyên nghiệp).

Bố cục:
  1. Tiêu đề + phiên + đồng hồ chạy từng giây + nút làm mới (st.fragment mỗi giây)
  2. Thẻ 4 chỉ số (VN-Index, VN30, HNX, UPCoM) + cổ phiếu đang theo dõi – trong phiên cập nhật ~3 phút theo nến phút DNSE
  3. Biểu đồ nến chỉ số + MA20/MA50 + khối lượng  |  Điểm sức khỏe thị trường
  4. Độ rộng thị trường (tăng/giảm/đứng, A/D, % trên MA20, đỉnh/đáy 20 phiên, GTGD)
  5. Bản đồ nhiệt theo ngành (treemap)  |  Hiệu suất ngành
  6. Top cổ phiếu: tăng mạnh / giảm mạnh / giá trị giao dịch / đột biến khối lượng
  7. So sánh hiệu suất + bảng lợi nhuận theo kỳ

Mọi con số đều tính từ dữ liệu giá thật (DNSE → vnstock → Vietstock); thiếu dữ liệu thì hiển thị "—".
"""


from giao_dien.chung import on_bg
import html
import itertools
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from giao_dien.chung import _base_layout, line_comparison_chart
from core import thi_truong_danh_muc as ms
from core.pipeline import get_repo

INDEX_ORDER = ["VNINDEX", "VN30", "HNX", "UPCOM"]
PERIODS = {"1Th": 31, "3Th": 92, "6Th": 183, "1N": 365, "3N": 1095}
SHORT_IDX = {"VNINDEX": "VNI", "VN30": "VN30", "HNX": "HNX", "UPCOM": "UPCoM"}
_uid = itertools.count()


# ─────────────────────────── Bảng màu theo giao diện ──────────────────────────
def _pal() -> Dict[str, str]:
    dark = st.session_state.get("theme", "light") == "dark"
    if dark:
        return dict(dark=True, text="#f0f6fc", muted="#b1bac4", card="rgba(22,27,34,0.78)",
                    border="rgba(48,54,61,0.95)", up="#22c55e", down="#f43f5e", ref="#f59e0b",
                    accent="#58a6ff", soft="rgba(255,255,255,0.04)", track="rgba(255,255,255,0.08)")
    # Giao diện sáng: thẻ/bảng TRONG SUỐT (thấy nền động), chữ đậm & tối hơn để nổi bật
    return dict(dark=False, text="#0b1220", muted="#334155", card="rgba(255,255,255,0)",
                border="rgba(15,23,42,0.16)", up="#15803d", down="#dc2626", ref="#b45309",
                accent="#1d4ed8", soft="rgba(255,255,255,0.22)", track="rgba(15,23,42,0.10)")


def _color(v: Optional[float], p: Dict[str, str]) -> str:
    if v is None or pd.isna(v):
        return p["muted"]
    return p["up"] if v > 0.0001 else p["down"] if v < -0.0001 else p["ref"]


def _f(v, d: int = 2, suffix: str = "", sign: bool = False) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    s = f"{v:+,.{d}f}" if sign else f"{v:,.{d}f}"
    return s + suffix


def _arrow(v: Optional[float]) -> str:
    if v is None or pd.isna(v):
        return ""
    return "▲" if v > 0.0001 else "▼" if v < -0.0001 else "■"


def _light_extra(p: Dict[str, str]) -> str:
    """Giao diện sáng: thẻ/bảng trong suốt → thêm viền sáng quanh chữ để nổi trên nền động."""
    if p["dark"]:
        return ""
    return (".mo-card,.mo-kpi,.mo-sec,.mo-head,table.mo-t,.mo-comp,.mo-meta,.mo-legend,.rc-row,.rc-list"
            "{text-shadow:0 0 2px rgba(255,255,255,.9),0 0 6px rgba(255,255,255,.55)}"
            ".mo-card,.mo-kpi{backdrop-filter:none !important;-webkit-backdrop-filter:none !important;box-shadow:none}"
            "table.mo-t td{font-weight:600}")


def _css(p: Dict[str, str]) -> str:
    return f"""<style>
.mo-head{{display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:10px;margin:0 0 14px}}
.mo-title{{font-size:24px;font-weight:800;color:{p['text']};margin:0;letter-spacing:-.3px}}
.mo-sub{{font-size:14px;color:{p['muted']};margin-top:2px}}
.mo-pills{{display:flex;gap:6px;flex-wrap:wrap}}
.mo-pill{{font-size:12.5px;font-weight:600;padding:4px 10px;border-radius:999px;border:1px solid {p['border']};
  background:{p['card']};color:{p['muted']};display:inline-flex;align-items:center;gap:6px}}
.mo-dot{{width:7px;height:7px;border-radius:50%;display:inline-block}}
.mo-card{{background:{p['card']};border:1px solid {p['border']};border-radius:14px;padding:14px 16px;
  backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);transition:transform .18s, box-shadow .18s;height:100%}}
.mo-card:hover{{transform:translateY(-2px);box-shadow:0 10px 28px rgba(15,23,42,{0.35 if p['dark'] else 0.10})}}
.mo-lbl{{font-size:12px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;color:{p['muted']}}}
.mo-val{{font-size:26px;font-weight:800;color:{p['text']};line-height:1.15;margin-top:4px;font-variant-numeric:tabular-nums}}
.mo-chg{{font-size:14px;font-weight:700;font-variant-numeric:tabular-nums}}
.mo-meta{{display:flex;justify-content:space-between;font-size:12px;color:{p['muted']};margin-top:6px;font-variant-numeric:tabular-nums}}
.mo-sec{{display:flex;align-items:baseline;gap:10px;margin:22px 0 10px}}
.mo-sec h3{{font-size:17px;font-weight:800;color:{p['text']};margin:0;padding:0}}
.mo-sec span{{font-size:13px;color:{p['muted']}}}
.mo-kpi{{background:{p['card']};border:1px solid {p['border']};border-radius:12px;padding:10px 12px;height:100%}}
.mo-kpi b{{display:block;font-size:21px;font-weight:800;color:{p['text']};font-variant-numeric:tabular-nums}}
.mo-kpi small{{font-size:12px;color:{p['muted']};font-weight:600}}
.mo-bar{{display:flex;height:12px;border-radius:999px;overflow:hidden;background:{p['track']};margin:8px 0 6px}}
.mo-legend{{display:flex;justify-content:space-between;font-size:13px;font-weight:700;font-variant-numeric:tabular-nums}}
table.mo-t{{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}}
table.mo-t th{{text-align:right;font-size:12px;text-transform:uppercase;letter-spacing:.4px;color:{p['muted']};
  font-weight:700;padding:8px 10px;border-bottom:1px solid {p['border']}}}
table.mo-t th:first-child,table.mo-t td:first-child,table.mo-t th:nth-child(2),table.mo-t td:nth-child(2){{text-align:left}}
table.mo-r th:nth-child(2),table.mo-r td:nth-child(2){{text-align:right}}
table.mo-t td{{text-align:right;padding:7px 8px;border-bottom:1px solid {p['track']};color:{p['text']}}}
table.mo-t tr:hover td{{background:{p['soft']}}}
.mo-sym{{font-weight:800;color:{p['accent']}}}
.mo-badge{{display:inline-block;min-width:66px;text-align:center;padding:3px 8px;border-radius:7px;font-weight:700;color:#fff}}
.mo-comp{{display:flex;justify-content:space-between;font-size:13px;color:{p['muted']};margin:7px 0 3px}}
.mo-comp b{{color:{p['text']}}}
.mo-track{{height:6px;border-radius:999px;background:{p['track']};overflow:hidden}}
.mo-track i{{display:block;height:100%;border-radius:999px}}
html body div[data-testid="stButtonGroup"] button{{background:{p['card']} !important;border-color:{p['border']} !important}}
html body div[data-testid="stButtonGroup"] button p,html body div[data-testid="stButtonGroup"] button span{{color:{p['muted']} !important}}
html body div[data-testid="stButtonGroup"] button[aria-checked="true"]{{background:{p['accent']} !important;border-color:{p['accent']} !important}}
html body div[data-testid="stButtonGroup"] button[aria-checked="true"] p,
html body div[data-testid="stButtonGroup"] button[aria-checked="true"] span{{color:#ffffff !important;font-weight:700 !important}}
.mo-foot{{font-size:12.5px;color:{p['muted']};margin-top:18px}}
{_light_extra(p)}
</style>"""


def _md(s: str):
    # Gộp thành một dòng để Markdown không hiểu nhầm phần thụt lề là khối code
    st.markdown(" ".join(line.strip() for line in s.splitlines()), unsafe_allow_html=True)


def _section(title: str, sub: str = ""):
    _md(f'<div class="mo-sec"><h3>{title}</h3><span>{sub}</span></div>')


def _spark(values: List[float], color: str, w: int = 170, h: int = 44, fill: bool = True) -> str:
    vals = [float(v) for v in values if v is not None and not pd.isna(v)]
    if len(vals) < 2:
        return f'<svg width="{w}" height="{h}"></svg>'
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    step = w / (len(vals) - 1)
    pts = [(i * step, h - 3 - (v - lo) / rng * (h - 6)) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    gid = f"g{next(_uid)}"
    area = (f'<path d="M0,{h} L{line.replace(" ", " L")} L{w},{h} Z" fill="url(#{gid})"/>' if fill else "")
    return (f'<svg width="100%" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
            f'<defs><linearGradient id="{gid}" x1="0" x2="0" y1="0" y2="1">'
            f'<stop offset="0%" stop-color="{color}" stop-opacity=".35"/>'
            f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
            f'{area}<polyline points="{line}" fill="none" stroke="{color}" stroke-width="1.8" '
            f'stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>')


# ─────────────────────────── Tải dữ liệu (có cache) ───────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _idx(code: str, days: int) -> pd.DataFrame:
    return ms.index_history(code, days=days)


@st.cache_data(ttl=300, show_spinner=False)
def _snapshot(symbols: tuple) -> pd.DataFrame:
    return ms.universe_snapshot(list(symbols))


@st.cache_data(ttl=300, show_spinner=False)
def _stock(sym: str, days: int) -> pd.DataFrame:
    try:
        return get_repo().get_price_history(sym, days=days)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def _status() -> Dict:
    try:
        return get_repo().get_provider_status()
    except Exception as exc:
        return {"error": str(exc)}


def _clear_cache():
    for fn in (_idx, _snapshot, _stock, _status):
        fn.clear()


# ─────────────────────────── Biểu đồ ──────────────────────────────────────────
def _index_chart(df: pd.DataFrame, name: str, kind: str, p: Dict[str, str], height: int = 470) -> go.Figure:
    d = df.copy()
    d["MA20"] = d["close"].rolling(20).mean()
    d["MA50"] = d["close"].rolling(50).mean()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.76, 0.24], vertical_spacing=0.02)
    x = d["timestamp"]
    if kind == "Nến":
        fig.add_trace(go.Candlestick(x=x, open=d["open"], high=d["high"], low=d["low"], close=d["close"], name=name,
                                     increasing_line_color=p["up"], decreasing_line_color=p["down"],
                                     increasing_fillcolor=p["up"], decreasing_fillcolor=p["down"]), 1, 1)
    else:
        col = p["up"] if d["close"].iloc[-1] >= d["close"].iloc[0] else p["down"]
        fig.add_trace(go.Scatter(x=x, y=d["close"], name=name, line=dict(color=col, width=2),
                                 hovertemplate="%{x|%d/%m/%Y}<br>%{y:,.2f}<extra></extra>"), 1, 1)
        lo = float(d["low"].min() if "low" in d else d["close"].min())
        fig.update_yaxes(range=[lo * 0.98, float(d["high"].max() if "high" in d else d["close"].max()) * 1.01], row=1, col=1)
    for ma, c in (("MA20", "#f59e0b"), ("MA50", "#8b5cf6")):
        fig.add_trace(go.Scatter(x=x, y=d[ma], name=ma, line=dict(color=c, width=1.3),
                                 hovertemplate=f"{ma}: %{{y:,.2f}}<extra></extra>"), 1, 1)
    if "volume" in d.columns:
        vc = [p["up"] if c >= o else p["down"] for c, o in zip(d["close"], d["open"].fillna(d["close"]))]
        fig.add_trace(go.Bar(x=x, y=d["volume"], marker_color=vc, opacity=0.55, name="Khối lượng",
                             hovertemplate="KL: %{y:,.0f}<extra></extra>"), 2, 1)
    last = float(d["close"].iloc[-1])
    fig.add_hline(y=last, line=dict(color=p["accent"], width=1, dash="dot"), row=1, col=1,
                  annotation_text=f" {last:,.2f}", annotation_position="right",
                  annotation_font=dict(color=p["accent"], size=11))
    lay = _base_layout(height=height)
    lay.update(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=True,
               legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, xanchor="left", bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
               margin=dict(l=8, r=60, t=42, b=8), xaxis_rangeslider_visible=False, hovermode="x unified")
    fig.update_layout(**lay)
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])], showgrid=False)
    fig.update_yaxes(tickformat=",.0f", gridcolor=p["track"], row=1, col=1)
    fig.update_yaxes(tickformat=".2s", gridcolor=p["track"], row=2, col=1)
    return fig


def _treemap(snap: pd.DataFrame, p: Dict[str, str]) -> go.Figure:
    d = snap.copy()
    d["size"] = d["value_bn"].clip(lower=0.05)
    d["label"] = d["symbol"]
    fig = px.treemap(d, path=[px.Constant("Thị trường"), "sector", "label"], values="size", color="change_pct",
                     color_continuous_scale=[[0, "#b91c1c"], [0.35, "#ef4444"], [0.5, "#eab308"],
                                             [0.65, "#22c55e"], [1, "#15803d"]],
                     range_color=[-5, 5], color_continuous_midpoint=0,
                     custom_data=["change_pct", "close", "value_bn"])
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", textposition="middle center",
        hovertemplate="<b>%{label}</b><br>Thay đổi: %{customdata[0]:+.2f}%<br>Giá: %{customdata[1]:,.0f}"
                      "<br>GTGD: %{customdata[2]:,.1f} tỷ<extra></extra>",
        marker=dict(line=dict(width=1.5, color="rgba(0,0,0,0.25)" if p["dark"] else "#ffffff")),
        root_color="rgba(0,0,0,0)", tiling=dict(pad=2), insidetextfont=dict(color="#ffffff", size=13))
    lay = _base_layout(height=440)
    lay.update(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=6, b=0),
               coloraxis_colorbar=dict(title="%", thickness=10, len=0.8, ticksuffix="%"))
    fig.update_layout(**lay)
    return fig


# Dựng hình Plotly tốn ~0,2–0,5 giây mỗi biểu đồ ở MỖI lần trang chạy lại (14/10/2026: đo ~1,1 giây cho cả trang). Cùng dữ
# liệu + cùng tùy chọn → dùng lại hình đã dựng (lưu dạng dict, st.plotly_chart vẽ thẳng không phải kiểm tra lại).
@st.cache_data(ttl=180, max_entries=32, show_spinner=False)
def _index_chart_cached(df: pd.DataFrame, name: str, kind: str, p: Dict[str, str], x0, x1) -> dict:
    fig = _index_chart(df, name, kind, p)
    fig.update_xaxes(range=[x0, x1])
    return fig.to_dict()


@st.cache_data(ttl=180, max_entries=16, show_spinner=False)
def _treemap_cached(snap: pd.DataFrame, p: Dict[str, str]) -> dict:
    return _treemap(snap, p).to_dict()


def _sector_bars(sec: pd.DataFrame, col: str, p: Dict[str, str]) -> go.Figure:
    d = sec.dropna(subset=[col]).sort_values(col)
    names = [s.split(" ", 1)[1] if " " in s and not s[0].isalnum() else s for s in d["sector"]]
    fig = go.Figure(go.Bar(
        x=d[col], y=names, orientation="h", marker_color=[_color(v, p) for v in d[col]],
        text=[f"{v:+.2f}%" for v in d[col]], textposition="outside", cliponaxis=False,
        customdata=d[["n", "adv", "dec"]].values,
        hovertemplate="<b>%{y}</b><br>%{x:+.2f}%<br>%{customdata[0]} mã · %{customdata[1]} tăng / "
                      "%{customdata[2]} giảm<extra></extra>"))
    lay = _base_layout(height=max(300, 34 * len(d) + 60))
    lay.update(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False,
               margin=dict(l=8, r=50, t=6, b=8))
    fig.update_layout(**lay)
    lo, hi = min(0.0, float(d[col].min())), max(0.0, float(d[col].max()))
    pad = (hi - lo) * 0.35 + 0.3
    fig.update_xaxes(ticksuffix="%", zeroline=True, zerolinecolor=p["muted"], gridcolor=p["track"],
                     range=[lo - (pad if lo < 0 else 0.15), hi + (pad if hi > 0 else 0.15)])
    fig.update_yaxes(showgrid=False, automargin=True, ticklabelstandoff=8)
    return fig


def _gauge(score: float, p: Dict[str, str]) -> go.Figure:
    col = p["up"] if score >= 60 else p["ref"] if score >= 40 else p["down"]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score, number=dict(font=dict(size=40, color=p["text"]), valueformat=".0f"),
        gauge=dict(axis=dict(range=[0, 100], tickwidth=0, tickfont=dict(size=10, color=p["muted"])),
                   bar=dict(color=col, thickness=0.28), bgcolor="rgba(0,0,0,0)", borderwidth=0,
                   steps=[dict(range=[0, 35], color="rgba(239,68,68,0.16)"),
                          dict(range=[35, 50], color="rgba(245,158,11,0.14)"),
                          dict(range=[50, 65], color="rgba(132,204,22,0.14)"),
                          dict(range=[65, 100], color="rgba(34,197,94,0.18)")])))
    fig.update_layout(height=190, margin=dict(l=30, r=30, t=14, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(color=p["text"]))
    return fig


# ─────────────────────────── Các khối giao diện ───────────────────────────────
def _header(p: Dict[str, str], session: str):
    pills = f'<span class="mo-pill">📅 Phiên {session}</span>' if session else ""
    pills += f'<span class="mo-pill">⏱ {datetime.now().strftime("%H:%M:%S")}</span>'
    _md(f'<div class="mo-head"><div><div class="mo-title">🏛️ Tổng Quan Thị Trường</div>'
        f'<div class="mo-sub">Toàn cảnh chứng khoán Việt Nam: chỉ số, độ rộng, dòng tiền theo ngành và cổ phiếu nổi bật'
        f'</div></div><div class="mo-pills">{pills}</div></div>')


def _session_label(cards: Dict[str, Dict]) -> str:
    avail = [c for c in cards.values() if c.get("available")]
    if not avail:
        return ""
    newest = max(avail, key=lambda c: c["day"])                      # phiên mới nhất trong các chỉ số
    return newest["date"].split(" · ")[0] + (" · đang giao dịch" if any(c.get("live") for c in avail) else "")


def _index_cards(cards: Dict[str, Dict], p: Dict[str, str]):
    cols = st.columns(4)
    for col, code in zip(cols, INDEX_ORDER):
        c = cards.get(code, {})
        with col:
            if not c.get("available"):
                _md(f'<div class="mo-card"><div class="mo-lbl">{ms.INDEX_SYMBOLS.get(code, code)}</div>'
                    f'<div class="mo-val" style="color:{p["muted"]}">—</div>'
                    f'<div class="mo-meta"><span>Không lấy được dữ liệu</span></div></div>')
                continue
            clr = _color(c["change"], p)
            r = c["returns"]
            stale = _in_session() and not c.get("live")
            date_html = (f'<span style="color:{p["muted"]}" title="Chưa lấy được giá trong phiên hôm nay – đang hiển thị '
                         f'phiên gần nhất, đang thử lại">⚠️ {c["date"]}</span>' if stale
                         else ("🟢 " if c.get("live") else "") + c["date"])
            _md(f'<div class="mo-card"><div style="display:flex;justify-content:space-between;align-items:center">'
                f'<div class="mo-lbl">{c["name"]}</div><div class="mo-lbl" style="letter-spacing:0">{date_html}</div></div>'
                f'<div class="mo-val">{c["close"]:,.2f}</div>'
                f'<div class="mo-chg" style="color:{clr}">{_arrow(c["change"])} {c["change"]:+,.2f} '
                f'({c["change_pct"]:+.2f}%)</div>'
                f'<div style="margin-top:6px">{_spark(c["spark"], clr)}</div>'
                f'<div class="mo-meta"><span>Thấp–Cao: {c["low"]:,.1f} – {c["high"]:,.1f}</span></div>'
                f'<div class="mo-meta"><span>KL: {c["volume"] / 1e6:,.1f} tr</span>'
                f'<span>1Th <b style="color:{_color(r["1Th"], p)}">{_f(r["1Th"], 1, "%", True)}</b> · '
                f'YTD <b style="color:{_color(r["YTD"], p)}">{_f(r["YTD"], 1, "%", True)}</b></span></div></div>')


CLOCK_SEC = 1             # phần đầu trang (đồng hồ, 4 thẻ chỉ số, cổ phiếu đang theo dõi) vẽ lại mỗi giây


def _in_session() -> bool:
    from core.du_lieu import _in_session as _sess
    return _sess()


def _live_top(hist: Dict[str, pd.DataFrame], p: Dict[str, str]):
    """
    Đầu trang chạy theo thời gian thật (st.fragment, chỉ phần này chạy lại mỗi giây, không tải lại cả trang):
    đồng hồ · 4 thẻ chỉ số · cổ phiếu đang theo dõi. Trong giờ giao dịch giá lấy thẳng từ nến phút DNSE
    (ms.live_bar – gọi DNSE tối đa 1 lần/3 phút mỗi mã) → trễ tối đa ~3 phút; đồng hồ vẫn chạy từng giây.
    """
    @st.fragment(run_every=CLOCK_SEC)
    def _frag():
        live_on = _in_session()
        sym = st.session_state.get("current_symbol", "FPT")
        live = ms.live_bars(INDEX_ORDER + [sym]) if live_on else {}
        cards = {code: ms.index_card(code, ms.merge_live(df, live.get(code))) for code, df in hist.items()}
        h1, h2 = st.columns([6, 1], vertical_alignment="bottom")
        with h1:
            _header(p, _session_label(cards))
        with h2:
            if st.button("🔄 Làm mới", width="stretch", key="mo_refresh",
                         help="Xóa bộ nhớ tạm của trang và tải lại dữ liệu mới nhất"):
                _clear_cache()
                st.rerun(scope="app")
        _index_cards(cards, p)
        if live_on:
            st.caption("🟢 Đang giao dịch · ⚡ giá realtime DNSE" if ms.live_mode() == "realtime"
                       else "🟢 Đang giao dịch · giá cập nhật ~3 phút (nhập API key DNSE để có giá realtime)")
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        _target_strip(p, live.get(sym.upper()) if live_on else None)

    _frag()


def _target_strip(p: Dict[str, str], bar: Optional[Dict] = None):
    sym = st.session_state.get("current_symbol", "FPT")
    try:
        from core.du_lieu import get_ticker_label
        label = get_ticker_label(sym)
    except Exception:
        label = sym
    df = ms.merge_live(_stock(sym, 90), bar)
    info = f'<span style="color:{p["muted"]}">Chưa có dữ liệu giá</span>'
    spark = ""
    if df is not None and len(df) >= 2:
        last, prev = float(df["close"].iloc[-1]), float(df["close"].iloc[-2])
        chg = last - prev
        pct = chg / prev * 100 if prev else 0
        clr = _color(chg, p)
        vol = float(df["volume"].iloc[-1]) if "volume" in df.columns else 0
        info = (f'<b style="font-size:21px;color:{p["text"]}">{last:,.0f}</b> '
                f'<span style="color:{clr};font-weight:700">{_arrow(chg)} {chg:+,.0f} ({pct:+.2f}%)</span>'
                f'<span style="color:{p["muted"]};margin-left:14px">KL {vol:,.0f} CP · '
                f'GTGD {last * vol / 1e9:,.1f} tỷ</span>')
        spark = _spark(df["close"].tail(60).tolist(), clr, w=220, h=40)
    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    with c1:
        from giao_dien.chung import logo_html
        logo = logo_html(sym, 44, dark=st.session_state.get("theme", "light") == "dark")
        _md(f'<div class="mo-card" style="display:flex;align-items:center;gap:18px;padding:10px 16px">{logo}'
            f'<div style="flex:1;min-width:0"><div class="mo-lbl">🎯 Cổ phiếu đang theo dõi</div>'
            f'<div style="font-weight:800;color:{p["accent"]};font-size:16px;white-space:nowrap;overflow:hidden;'
            f'text-overflow:ellipsis">{html.escape(label)}</div><div style="margin-top:2px">{info}</div></div>'
            f'<div style="width:220px;flex-shrink:0">{spark}</div></div>')
    with c2:
        if st.button(f"🔍 Phân tích {sym}", type="primary", width="stretch", key="mo_jump"):
            st.session_state["nav_page"] = "🔍 Phân Tích Cổ Phiếu"
            st.rerun(scope="app")


def _health_panel(health: Dict, p: Dict[str, str]):
    _md('<div class="mo-lbl" style="margin-bottom:2px">Sức khỏe thị trường</div>')
    if not health.get("available"):
        st.info("Chưa đủ dữ liệu để chấm điểm.")
        return
    st.plotly_chart(_gauge(health["score"], p), width="stretch", theme=None, config={"displayModeBar": False})
    s = health["score"]
    clr = p["up"] if s >= 60 else p["ref"] if s >= 40 else p["down"]
    rows = "".join(
        f'<div class="mo-comp"><span>{v["label"]} <small>({v["weight"]}%)</small></span><b>{v["detail"]}</b></div>'
        f'<div class="mo-track"><i style="width:{max(2, v["score"]):.0f}%;background:{_color(v["score"] - 50, p)}"></i></div>'
        for v in health["components"].values() if v.get("score") is not None and not pd.isna(v["score"]))
    _md(f'<div style="text-align:center;font-weight:800;color:{clr};margin:-8px 0 8px">{health["label"]}</div>{rows}')
    st.caption("Điểm theo quy tắc (xu hướng, RSI, độ rộng, hiệu suất 20 phiên) – chỉ để tham khảo, không phải khuyến nghị.")


def _breadth_block(b: Dict, p: Dict[str, str]):
    if not b.get("available") or not b.get("total"):
        st.warning("Không lấy được dữ liệu cổ phiếu để tính độ rộng thị trường.")
        return
    t = b["total"]
    w = lambda n: n / t * 100 if t else 0  # noqa: E731
    _md(f'<div class="mo-card"><div style="display:flex;justify-content:space-between;align-items:center">'
        f'<div class="mo-lbl">Tương quan tăng / giảm · {t} mã · phiên {b["session"]}</div>'
        f'<div class="mo-lbl" style="letter-spacing:0">A/D = {_f(b["ad_ratio"], 2) if b["ad_ratio"] else "∞"}</div></div>'
        f'<div class="mo-bar"><div style="width:{w(b["advancing"]):.2f}%;background:{p["up"]}"></div>'
        f'<div style="width:{w(b["unchanged"]):.2f}%;background:{p["ref"]}"></div>'
        f'<div style="width:{w(b["declining"]):.2f}%;background:{p["down"]}"></div></div>'
        f'<div class="mo-legend"><span style="color:{p["up"]}">▲ {b["advancing"]} tăng ({w(b["advancing"]):.0f}%)</span>'
        f'<span style="color:{p["ref"]}">■ {b["unchanged"]} đứng giá</span>'
        f'<span style="color:{p["down"]}">▼ {b["declining"]} giảm ({w(b["declining"]):.0f}%)</span></div></div>')
    k = st.columns(5)
    kpis = [
        ("Biến động bình quân", _f(b["avg_change"], 2, "%", True), _color(b["avg_change"], p)),
        ("% mã trên MA20", _f(b["pct_above_ma20"], 0, "%"), _color((b["pct_above_ma20"] or 50) - 50, p)),
        ("Vượt đỉnh 20 phiên", f'{b["new_highs"]}', p["up"]),
        ("Thủng đáy 20 phiên", f'{b["new_lows"]}', p["down"]),
        ("Tổng GTGD rổ", _f(b["value_bn"], 0, " tỷ"), p["text"]),
    ]
    for col, (lbl, val, c) in zip(k, kpis):
        with col:
            _md(f'<div class="mo-kpi" style="margin-top:10px"><small>{lbl}</small><b style="color:{c}">{val}</b></div>')


def _movers_table(df: pd.DataFrame, p: Dict[str, str], extra: str) -> str:
    if df.empty:
        return f'<div style="color:{p["muted"]};padding:12px">Không có dữ liệu</div>'
    extra_head = {"value": "GTGD (tỷ)", "vol": "KL / TB20", "chg": "GTGD (tỷ)"}[extra]
    rows = []
    for i, r in enumerate(df.itertuples(), 1):
        clr = _color(r.change_pct, p)
        sector = r.sector.split(" ", 1)[1] if " " in r.sector and not r.sector[0].isalnum() else r.sector
        ex = (f"{r.vol_ratio:,.2f}×" if extra == "vol" and r.vol_ratio else _f(r.value_bn, 1))
        rows.append(
            f'<tr><td style="color:{p["muted"]};width:28px">{i}</td>'
            f'<td><span class="mo-sym">{r.symbol}</span> <small style="color:{p["muted"]}">{html.escape(sector)}</small></td>'
            f'<td>{r.close:,.0f}</td><td style="color:{clr}">{r.change:+,.0f}</td>'
            f'<td><span class="mo-badge" style="{on_bg(clr)}">{r.change_pct:+.2f}%</span></td>'
            f'<td>{r.volume:,.0f}</td><td>{ex}</td>'
            f'<td style="color:{_color(r.ret_20d, p)}">{_f(r.ret_20d, 1, "%", True)}</td>'
            f'<td style="width:120px">{_spark(r.spark, clr, w=110, h=26, fill=False)}</td></tr>')
    return (f'<div class="mo-card" style="padding:6px 8px;overflow-x:auto"><table class="mo-t"><thead><tr>'
            f'<th>#</th><th>Mã</th><th>Giá</th><th>+/-</th><th>%</th><th>Khối lượng</th><th>{extra_head}</th>'
            f'<th>20 phiên</th><th>30 phiên gần nhất</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def _returns_table(rows: Dict[str, Dict], p: Dict[str, str]) -> str:
    keys = ["1T", "1Th", "3Th", "6Th", "YTD", "1N"]
    titles = ["1 tuần", "1 tháng", "3 tháng", "6 tháng", "Từ đầu năm", "1 năm"]
    head = "".join(f'<th title="{t}">{k}</th>' for k, t in zip(["1T", "1Th", "3Th", "6Th", "YTD", "1N"], titles))
    body = ""
    for name, r in rows.items():
        cells = "".join(f'<td style="color:{_color(r.get(k), p)};font-weight:700">{_f(r.get(k), 2, "%", True)}</td>'
                        for k in keys)
        body += f'<tr><td style="white-space:nowrap"><span class="mo-sym">{html.escape(name)}</span></td>{cells}</tr>'
    return (f'<div class="mo-card" style="padding:6px 8px;overflow-x:auto"><table class="mo-t mo-r"><thead><tr><th>Chỉ số / Mã</th>'
            f'{head}</tr></thead><tbody>{body}</tbody></table>'
            f'<div style="font-size:12px;color:{p["muted"]};padding:6px 10px">T = tuần · Th = tháng · N = năm · '
            f'YTD = từ đầu năm</div></div>')


def _open_pick():
    sym = st.session_state.get("mo_pick", "—")
    if sym and sym != "—":
        for k in ("current_symbol", "stock_symbol_input", "ta_symbol", "score_symbol", "bt_symbol", "pdf_symbol"):
            st.session_state[k] = sym
        st.session_state.pop("stock_analysis", None)
        st.session_state.pop("last_analyzed", None)
        st.session_state["nav_page"] = "🔍 Phân Tích Cổ Phiếu"
        st.session_state["mo_pick"] = "—"


# ─────────────────────────── Trang ────────────────────────────────────────────
def render():
    p = _pal()
    _md(_css(p))

    with st.spinner("Đang tải dữ liệu chỉ số..."):
        hist = {code: _idx(code, 1100 if code == "VNINDEX" else 400) for code in INDEX_ORDER}
    if _in_session():                             # phiên hôm nay lấy thẳng từ nến phút, không chờ bộ nhớ đệm 5 phút
        live = ms.live_bars(INDEX_ORDER)
        hist_now = {code: ms.merge_live(df, live.get(code)) for code, df in hist.items()}
    else:
        hist_now = hist
    cards = {code: ms.index_card(code, df) for code, df in hist_now.items()}

    _live_top(hist, p)

    # ── Độ rộng (tính trước để dùng cho điểm sức khỏe) ──
    universes = ms.universe_options()
    uni_name = st.session_state.get("mo_universe", next(iter(universes)))
    if uni_name not in universes:
        uni_name = next(iter(universes))
    with st.spinner(f"Đang tải dữ liệu {len(universes[uni_name])} cổ phiếu..."):
        snap = _snapshot(tuple(universes[uni_name]))
    breadth = ms.breadth_stats(snap)

    # ── Biểu đồ chỉ số + sức khỏe ──
    _section("Diễn biến chỉ số", "Nến ngày · MA20 · MA50 · khối lượng")
    c_chart, c_health = st.columns([3, 1], gap="medium")
    with c_chart:
        o1, o2, o3 = st.columns([2.2, 2.6, 1.3])
        with o1:
            code = st.segmented_control("Chỉ số", INDEX_ORDER, default="VNINDEX", key="mo_idx",
                                        format_func=lambda c: SHORT_IDX.get(c, c),
                                        label_visibility="collapsed") or "VNINDEX"
        with o2:
            per = st.segmented_control("Kỳ", list(PERIODS), default="6Th", key="mo_period", help="Th = tháng, N = năm",
                                       label_visibility="collapsed") or "6Th"
        with o3:
            kind = st.segmented_control("Kiểu", ["Nến", "Đường"], default="Nến", key="mo_kind",
                                        label_visibility="collapsed") or "Nến"
        df = hist_now.get(code, pd.DataFrame())
        if df is not None and not df.empty:
            cutoff = pd.to_datetime(df["timestamp"]).max() - pd.Timedelta(days=PERIODS[per])
            view = df[pd.to_datetime(df["timestamp"]) >= cutoff - pd.Timedelta(days=80)]  # dư cho MA50
            fig = _index_chart_cached(view, ms.INDEX_SYMBOLS.get(code, code), kind, p, cutoff,
                                      pd.to_datetime(df["timestamp"]).max() + pd.Timedelta(days=2))
            st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})
            if len(df) and pd.to_datetime(df["timestamp"]).min() > cutoff + pd.Timedelta(days=5):
                st.caption("Nguồn dữ liệu chỉ có lịch sử ngắn hơn kỳ đã chọn.")
        else:
            st.warning(f"Không tải được dữ liệu {ms.INDEX_SYMBOLS.get(code, code)}.")
    with c_health:
        _health_panel(ms.market_health(hist_now.get("VNINDEX"), breadth), p)

    # ── Độ rộng thị trường ──
    _section("Độ rộng thị trường", "Đo trên rổ cổ phiếu đã chọn – phiên gần nhất")
    st.selectbox("Rổ cổ phiếu", list(universes), key="mo_universe",
                 format_func=lambda n: f"{n} · {len(universes[n])} mã", label_visibility="collapsed")
    _breadth_block(breadth, p)

    if snap is None or snap.empty:
        return
    live = snap[~snap["stale"]]

    # ── Heatmap + ngành ──
    _section("Bản đồ nhiệt & dòng tiền theo ngành", "Diện tích = giá trị giao dịch · màu = % thay đổi")
    c_map, c_sec = st.columns([3, 2], gap="medium")
    with c_map:
        st.plotly_chart(_treemap_cached(live, p), width="stretch", theme=None, config={"displayModeBar": False})
    with c_sec:
        sec = ms.sector_performance(live)
        horizon = st.segmented_control("Kỳ ngành", ["1D", "5D", "20D"], default="1D", key="mo_sec_h",
                                       format_func=lambda h: {"1D": "1 phiên", "5D": "5 phiên", "20D": "20 phiên"}[h],
                                       label_visibility="collapsed") or "1D"
        if not sec.empty:
            st.plotly_chart(_sector_bars(sec, horizon, p), width="stretch", theme=None, config={"displayModeBar": False})

    # ── Top cổ phiếu ──
    _section("Cổ phiếu nổi bật", f"Trong rổ {uni_name.split(' ', 1)[-1]}")
    n = 10
    t1, t2, t3, t4 = st.tabs(["📈 Tăng mạnh nhất", "📉 Giảm mạnh nhất", "💰 Giá trị giao dịch lớn", "⚡ Đột biến khối lượng"])
    with t1:
        _md(_movers_table(live.nlargest(n, "change_pct"), p, "chg"))
    with t2:
        _md(_movers_table(live.nsmallest(n, "change_pct"), p, "chg"))
    with t3:
        _md(_movers_table(live.nlargest(n, "value_bn"), p, "value"))
    with t4:
        _md(_movers_table(live.dropna(subset=["vol_ratio"]).nlargest(n, "vol_ratio"), p, "vol"))
    st.selectbox("Mở phân tích chi tiết", ["—"] + sorted(live["symbol"].tolist()), key="mo_pick",
                 format_func=lambda s: "🔎 Chọn mã để mở phân tích chi tiết…" if s == "—" else s,
                 on_change=_open_pick, label_visibility="collapsed")

    # ── So sánh hiệu suất ──
    target = st.session_state.get("current_symbol", "FPT")
    _section("So sánh hiệu suất", f"Chuẩn hóa = 100 · chỉ số và {target}")
    series, ret_rows = {}, {}
    for code in INDEX_ORDER:
        d = hist_now.get(code)
        if d is not None and not d.empty:
            d1 = d[pd.to_datetime(d["timestamp"]) >= pd.to_datetime(d["timestamp"]).max() - pd.Timedelta(days=365)]
            if code in ("VNINDEX", "VN30"):
                series[ms.INDEX_SYMBOLS[code]] = d1.set_index("timestamp")["close"]
            ret_rows[ms.INDEX_SYMBOLS[code]] = cards[code]["returns"] if cards[code].get("available") else {}
    sd = _stock(target, 400)
    if sd is not None and not sd.empty:
        sd1 = sd[pd.to_datetime(sd["timestamp"]) >= pd.to_datetime(sd["timestamp"]).max() - pd.Timedelta(days=365)]
        series[target] = sd1.set_index("timestamp")["close"]
        ret_rows[target] = ms.period_returns(sd)
    c_l, c_r = st.columns([1, 1], gap="medium")
    with c_l:
        if series:
            fig = line_comparison_chart(series, title="", height=340)
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              margin=dict(l=8, r=8, t=10, b=8))
            st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})
    with c_r:
        if ret_rows:
            _md(_returns_table(ret_rows, p))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: components/recommendation_view.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Thành phần hiển thị kết quả Khuyến nghị 12 tháng (dùng trong tab 🎯 Khuyến nghị của trang Phân tích cổ phiếu).
Trang riêng "🎯 Khuyến Nghị Đầu Tư" (kèm tab bot 4 tầng, chiến lược nhóm) đã bỏ theo yêu cầu (14/10/2026).
"""


import html
import json
from typing import Any, Dict, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from giao_dien.chung import _base_layout
from giao_dien.chung import on_bg


def _target_range(v):
    from giao_dien.thi_truong import _target_range_stock_analysis as tr
    return tr(v)


SEV_COLOR = {"Nghiêm trọng": "#991b1b", "Cao": "#dc2626", "Trung bình": "#d97706", "Thấp": "#16a34a",
             "Cần theo dõi": "#2563eb"}
SCEN_COLOR = {"bear": "#dc2626", "base": "#d97706", "bull": "#16a34a"}


def _e(s) -> str:
    return html.escape(str(s))


def _n(v, d=0, suf="", sign=False) -> str:
    if v is None:
        return "—"
    try:
        return (f"{v:+,.{d}f}" if sign else f"{v:,.{d}f}") + suf
    except (TypeError, ValueError):
        return "—"


@st.cache_data(ttl=900, show_spinner=False)
def _extra_css(p) -> str:
    return f"""<style>
.rc-hero{{display:grid;grid-template-columns:minmax(220px,1.1fr) 3fr;gap:14px;margin-bottom:6px}}
@media (max-width:900px){{.rc-hero{{grid-template-columns:1fr}}}}
.rc-badge{{border-radius:16px;padding:18px;color:#fff;display:flex;flex-direction:column;justify-content:center;gap:4px}}
.rc-badge *{{color:inherit !important;-webkit-text-fill-color:inherit}}
.rc-badge .t{{font-size:13px;letter-spacing:.8px;text-transform:uppercase;opacity:.85;font-weight:700}}
.rc-badge .r{{font-size:30px;font-weight:900;line-height:1.1}}
.rc-badge .s{{font-size:15px;opacity:.95}}
.rc-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.rc-chip{{display:inline-block;padding:3px 10px;border-radius:999px;font-size:13px;font-weight:700;color:#fff;margin-right:6px;
  white-space:nowrap;flex-shrink:0}}
.rc-row{{display:flex;gap:10px;align-items:flex-start;padding:7px 0;border-bottom:1px solid {p['track']};font-size:15px;color:{p['text']}}}
.rc-row small{{color:{p['muted']}}}
.rc-list li{{font-size:15px;color:{p['text']};margin:3px 0}}
</style>"""


def _scenario_chart(v: Dict[str, Any], p) -> Optional[go.Figure]:
    sc = v.get("scenarios") or {}
    price = v.get("price")
    keys = [k for k in ("bear", "base", "bull") if (sc.get(k) or {}).get("target")]
    if not keys or not price:
        return None
    from core.dinh_gia import SCEN_LABEL
    labels = ["Thị giá"] + [SCEN_LABEL[k] for k in keys]
    vals = [price] + [sc[k]["target"] for k in keys]
    colors = ["#64748b"] + [SCEN_COLOR[k] for k in keys]
    text = [f"{price:,.0f}"] + [f"{sc[k]['target']:,.0f}<br>({sc[k]['upside']:+.1f}%)" for k in keys]
    fig = go.Figure(go.Bar(x=labels, y=vals, marker_color=colors, text=text, textposition="outside",
                           hovertemplate="%{x}: %{y:,.0f} VND<extra></extra>"))
    fig.add_hline(y=price, line_dash="dash", line_color="#64748b")
    fig.update_layout(**_base_layout(height=330, margin={"l": 40, "r": 10, "t": 30, "b": 30}, showlegend=False,
                                     yaxis={"title": "VND/cp", "range": [0, max(vals) * 1.22]}))
    return fig


def _render_ml(ml: Dict[str, Any], p) -> None:
    """Khung khuyến nghị đa lớp: lý do, các lớp điểm, ma trận F × R, bộ lọc loại trừ, khoảng định giá, ủng hộ/rủi ro, điều kiện sai."""
    from core.khuyen_nghi import MATRIX_ROWS
    _md(f'<div style="margin:10px 0 4px;padding:10px 14px;border-radius:10px;border-left:6px solid {ml["hex"]};'
        f'background:{ml["hex"]}1f"><b style="color:{p["text"]} !important">Khuyến nghị: {_e(ml["label"])}</b>'
        f'<br><span style="color:{p["text"]}">{_e(ml["why"])}</span><br><small>{_e(ml["action"])}</small></div>')
    left, right = st.columns([1, 1])
    with left:
        _section("Điểm khuyến nghị đa lớp", "F = 0,40·Q + 0,35·V + 0,25·G − điểm trừ rủi ro")
        for k, lbl in (("Q", "Chất lượng (Q)"), ("V", "Định giá (V)"), ("G", "Tăng trưởng (G)"), ("F", "Điểm cơ bản F"),
                       ("R", "So với thị trường (R)")):
            v = ml.get(k)
            col = "#16a34a" if (v or 0) >= 70 else "#d97706" if (v or 0) >= 55 else "#dc2626"
            _md(f'<div class="mo-comp"><span>{"<b>" if k == "F" else ""}{_e(lbl)}{"</b>" if k == "F" else ""}</span>'
                f'<b>{_n(v, 0)}</b></div><div class="mo-track"><i style="width:{v or 0:.0f}%;background:{col}"></i></div>')
        if ml.get("penalties"):
            st.caption("Điểm trừ rủi ro: " + "; ".join(f"{x['text']} (−{x['points']})" for x in ml["penalties"]))
        with st.expander("Thành phần từng lớp"):
            for k, lbl in (("Q", "Chất lượng"), ("V", "Định giá"), ("G", "Tăng trưởng"), ("R", "So với thị trường")):
                st.markdown(f"**{lbl}**")
                for r in (ml.get("layers") or {}).get(k, []):
                    st.markdown(f"- {r['name']}: **{_n(r['score'], 0) if r['score'] is not None else 'thiếu dữ liệu'}**"
                                + (f" · <small>{_e(r.get('detail'))}</small>" if r.get("detail") else ""), unsafe_allow_html=True)
    with right:
        _section("Ma trận khuyến nghị", "điểm cơ bản F × sức mạnh so với thị trường R")
        rk = {"strong": 0, "mid": 1, "weak": 2}.get(ml.get("row"))
        ck = {"good": 1, "mid": 2, "bad": 3}.get(ml.get("col"))
        th = ml["thresholds"]
        rows = ""
        for i, r in enumerate(MATRIX_ROWS):
            cells = "".join(
                (f'<td><span style="background:{ml["hex"]};color:#fff;-webkit-text-fill-color:#fff;font-weight:800;'
                 f'padding:3px 10px;border-radius:8px;display:inline-block">▶ {_e(r[j])}</span></td>'
                 if (i == rk and j == ck) else f'<td>{_e(r[j])}</td>')
                for j in (1, 2, 3))
            rows += f"<tr><td style='text-align:left'>{_e(r[0])}</td>{cells}</tr>"
        _md(f'<table class="mo-t"><tr><th></th><th>R ≥ {th["r_strong"]:.0f}</th><th>{th["r_weak"]:.0f}–{th["r_strong"]:.0f}</th>'
            f'<th>R &lt; {th["r_weak"]:.0f}</th></tr>{rows}</table>')
        relx = ml.get("relative") or {}
        bits = []
        if relx.get("rank") and not relx.get("fallback"):
            bits.append(f"Xếp hạng sức mạnh giá **{relx['rank'][0]}/{relx['rank'][1]}** trong rổ {relx.get('universe')}")
        mk = relx.get("market") or {}
        if mk:
            bits.append(f"VN-Index {mk['close']:,.0f} {'**dưới**' if mk['below'] else 'trên'} MA200 ({mk['ma200']:,.0f})")
        hd = relx.get("hurdle") or {}
        if hd.get("gap") is not None:
            bits.append(f"LN kỳ vọng {hd['er']:+.1f}% {'≥' if hd['pass'] else '<'} Ke {hd['ke']:.1f}%")
        if bits:
            st.markdown(" · ".join(bits))
        _th = ml.get("thresholds") or {}
        st.caption(f"MUA cần đủ: F ≥ {_th.get('f_strong', 65):g}, R ≥ {_th.get('r_strong', 60):g}, VN-Index trên MA200 (hoặc mã thuộc top 30% sức mạnh giá trong rổ) và lợi nhuận kỳ vọng ≥ chi phí vốn Ke.")
        vr = ml.get("valuation_range") or {}
        if vr.get("available"):
            st.markdown(f"**Khoảng định giá** ({_e(vr['source'])}): {_n(vr['low'])} – {_n(vr['high'])} đ/cp · biên an toàn "
                        f"{_n(vr.get('margin_of_safety'), 1, '%', True)} · độ phân tán {_n((vr.get('dispersion') or 0) * 100, 0, '%')}")
        rel = ml.get("reliability") or {}
        st.caption(f"Độ tin cậy khuyến nghị: {rel.get('level')} – dữ liệu đủ {rel.get('coverage')}%, "
                   f"{rel.get('peers')} doanh nghiệp cùng ngành.")
    a, b = st.columns(2)
    with a:
        _section("Bộ lọc loại trừ")
        icon = {"pass": "🟢", "hit": "🔴", "unknown": "⚪"}
        for e in ml.get("exclusions") or []:
            st.markdown(f"{icon[e['status']]} {e['text']}" + (f" · <small>{_e(e['detail'])}</small>" if e.get("detail") else ""),
                        unsafe_allow_html=True)
    with b:
        _section("Lý do ủng hộ · rủi ro · điều kiện làm luận điểm sai")
        for x in ml.get("pros") or []:
            st.markdown(f"✅ {x}")
        for x in ml.get("cons") or []:
            st.markdown(f"⚠️ {x}")
        for x in ml.get("invalidation") or []:
            st.markdown(f"🔁 {x}")
    for n in ml.get("notes") or []:
        st.caption("⚠️ " + n)
    st.caption(ml.get("disclaimer", ""))


def _render_result(inv: Dict[str, Any], p) -> None:
    h, v, risk, rec = inv["health"], inv["valuation"], inv["risk"], inv["recommendation"]
    sym = inv["symbol"]
    if inv.get("as_of"):
        st.info(f"📅 Định giá tại ngày **{pd.Timestamp(inv['as_of']):%d/%m/%Y}** – giá đóng cửa phiên {v.get('price_date') or '—'}, "
                f"BCTC năm gần nhất được dùng: {v.get('data_period') or '—'}. Không dùng thông tin công bố sau ngày này.")
    methods_txt = ", ".join(m["name"] for m in v.get("methods", [])) or "—"
    hs = h.get("score")
    tiles = [
        ("Thị giá", _n(v.get("price")), f"Ngày giá {v.get('price_date') or '—'}"),
        ("Giá mục tiêu", _n(v.get("target_12m")), _target_range(v)) if v.get("available") or not v.get("target_12m") else
        ("Giá mục tiêu", _n(v.get("target_12m")), f"Độ tin cậy {str(v.get('confidence') or 'thấp').lower()} – chỉ tham khảo"),
        ("Upside", _n(v.get("upside"), 1, "%", True),
         "Giá mục tiêu / thị giá − 1"),
        ("Tổng LN kỳ vọng", _n(v.get("expected_return"), 1, "%", True),
         f"Gồm cổ tức {_n(v.get('expected_dividend'))} đ/cp" if v.get("dividends_included") else "Không gồm cổ tức"),
        ("Sức khỏe tài chính", f"{hs:.1f}/100" if hs is not None else "—", h.get("rating_text", "")),
        ("Mức rủi ro", risk.get("level", "—"), " · ".join(
            f"{risk['counts'].get(k, 0)} rủi ro {k.lower()}" for k in ("Nghiêm trọng", "Cao") if risk["counts"].get(k))),
        ("Độ tin cậy định giá", v.get("confidence") or "—", methods_txt),
        ("Dữ liệu BCTC", v.get("data_date") or "—", f"Kỳ hạn {v.get('horizon_months', 12)} tháng"),
    ]
    tiles_html = "".join(f'<div class="mo-kpi"><small>{_e(a)}</small><b>{_e(b)}</b><small>{_e(c)}</small></div>' for a, b, c in tiles)
    ml = inv.get("multilayer")
    # 15/10/2026: khung khuyến nghị đa lớp → MỘT nhãn duy nhất (thay hành động đề xuất + khuyến nghị 12T)
    if ml:
        badge_hex, badge_txt = ml["hex"], ml["label"]
        rel = ml.get("reliability") or {}
        sub = (f"Cơ bản F {_n(ml.get('F'), 0)} · So với thị trường R {_n(ml.get('R'), 0)} · độ tin cậy "
               f"{_e(str(rel.get('level', '—')).lower())}")
    else:
        badge_hex, badge_txt = rec["hex"], rec["label"]
        sub = "Không chạy được khung khuyến nghị đa lớp"
    _md(f'<div class="rc-hero"><div class="rc-badge" style="{on_bg(badge_hex)}">'
        f'<div class="t">{_e(sym)} · {_e(inv.get("name") or "")}</div><div class="r">{_e(badge_txt)}</div>'
        f'<div class="s">{sub}</div></div><div class="rc-grid">{tiles_html}</div></div>')

    if ml:
        _render_ml(ml, p)
    for r in ([] if ml else rec["reasons"]):
        st.markdown(f"**→** {r}")


    left, right = st.columns([1.05, 1])
    with left:
        _section("Kịch bản Bear / Base / Bull", "thay đổi bộ giả định, không cộng trừ thẳng vào giá")
        fig = _scenario_chart(v, p)
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Chưa có kịch bản định giá (thiếu thị giá hoặc phương pháp hợp lệ).")
        sc = v.get("scenarios") or {}
        if sc and any((sc.get(k) or {}).get("target") for k in sc):
            from core.dinh_gia import SCEN_LABEL
            rows = "".join(
                f"<tr><td>{SCEN_LABEL[k]}</td><td>{_n((sc[k].get('growth') or 0) * 100, 1, '%', True)}</td>"
                f"<td>{_n(sc[k]['margin'] * 100, 1, '%') if sc[k].get('margin') is not None else '—'}</td>"
                f"<td>{_n(sc[k]['ke'] * 100, 1, '%')}</td><td>{_n(sc[k].get('eps_fwd'))}</td>"
                f"<td><b>{_n(sc[k].get('target'))}</b></td><td>{_n(sc[k].get('upside'), 1, '%', True)}</td></tr>"
                for k in ("bear", "base", "bull") if k in sc)
            _md('<div style="overflow-x:auto"><table class="mo-t mo-r" style="min-width:560px"><tr><th>Kịch bản</th><th>Tăng trưởng</th><th>Biên LN</th><th>Ke</th>'
                f'<th>EPS dự phóng</th><th>Giá mục tiêu</th><th>Upside</th></tr>{rows}</table></div>')
    with right:
        _section("Financial Health Score", f"{hs:.1f}/100 · {h.get('rating_text', '')}" if hs is not None
                 else f"chưa công bố – độ phủ {h.get('coverage', 0) * 100:.0f}%")
        for g in h.get("groups", []):
            gs = g.get("score")
            col = "#16a34a" if (gs or 0) >= 75 else "#d97706" if (gs or 0) >= 50 else "#dc2626"
            _md(f'<div class="mo-comp"><span>{_e(g["label"])} <small>({g["weight"]}%)</small></span>'
                f'<b>{_n(gs, 0) if gs is not None else "—"}</b></div>'
                f'<div class="mo-track"><i style="width:{gs or 0:.0f}%;background:{col}"></i></div>')
        with st.expander("Chi tiết từng chỉ tiêu"):
            for g in h.get("groups", []):
                st.markdown(f"**{g['label']}**")
                for m in g["metrics"]:
                    st.markdown(f"- {m['label']}: **{m['display']}** → {_n(m['score'], 0) if m['score'] is not None else 'không chấm'} "
                                f"điểm · <small>{_e(m['explain'])}</small>", unsafe_allow_html=True)
            for n in h.get("notes", []):
                st.caption("⚠️ " + n)

    _section("Phương pháp định giá", "chỉ dùng phương pháp hợp lệ, trọng số chuẩn hóa lại")
    if v.get("methods"):
        rows = "".join(
            f"<tr><td>{_e(m['name'])}</td><td>{_e(m.get('base_label') or '')} {_n(m.get('base'))}</td>"
            f"<td>{_n(m['multiple'], 2, 'x') if m.get('multiple') else '—'}</td><td><b>{_n(m['fair'])}</b></td>"
            f"<td>{m['weight'] * 100:.0f}%</td><td>{_n(m['upside'], 1, '%', True)}</td>"
            f"<td style='text-align:left;font-size:13px'>{_e(m['source'])}</td></tr>" for m in v["methods"])
        _md('<div style="overflow-x:auto"><table class="mo-t mo-r" style="min-width:560px"><tr><th>Phương pháp</th><th>Cơ sở</th><th>Hệ số</th><th>Giá trị</th>'
            f'<th>Trọng số</th><th>Upside</th><th style="text-align:left">Nguồn / giả định</th></tr>{rows}</table></div>')
    for m, r in v.get("invalid", []):
        st.caption(f"✖ Không dùng {m}: {r}")
    for n in v.get("notes", []):
        st.caption("⚠️ " + n)

    a, b = st.columns(2)
    with a:
        _section("Luận điểm đầu tư")
        th = inv.get("thesis") or {}
        items = "".join(f"<li>✅ {_e(x)}</li>" for x in th.get("positives", [])) + \
            "".join(f"<li>⚠️ {_e(x)}</li>" for x in th.get("negatives", []))
        _md(f'<ul class="rc-list" style="padding-left:4px;list-style:none">{items or "<li>—</li>"}</ul>')
    with b:
        _section("Rủi ro", f"mức tổng thể: {risk.get('level')}")
        for it in risk.get("items", []):
            _md(f'<div class="rc-row"><span class="rc-chip" style="{on_bg(SEV_COLOR[it["severity"]])}">'
                f'{_e(it["severity"])}</span><div>{_e(it["text"])}<br><small>{_e(it["category"])} · {_e(it["source"])}</small></div></div>')
        st.caption(risk.get("rule", ""))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/stock_analysis.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Trang – 🔍 Phân Tích Cổ Phiếu (giao diện bảng điều khiển).

Bố cục:
  Đầu trang : thẻ mã (giá, thay đổi, biên 52 tuần, sparkline) + 5 điểm trụ cột + khuyến nghị 12T
  Tab 💰 Định giá           : giá mục tiêu, biểu đồ "football field" theo phương pháp, bảng phương pháp, kịch bản,
                             bội số hiện tại so với lịch sử/ngành, độ nhạy
  Tab 📊 Phân tích cơ bản  : điểm cơ bản + Financial Health, chỉ số chính, biểu đồ KQKD/sinh lời/dòng tiền/cơ cấu vốn,
                             DuPont, Piotroski, Altman, cảnh báo, BCTC tóm tắt
  Tab 📈 Phân tích kỹ thuật: biểu đồ giá (nến + MA/EMA/Bollinger, các khung chỉ báo RSI/MACD/ADX/MFI/OBV xem cùng lúc),
                             so sánh VN-Index, hiệu suất theo kỳ, xu hướng, điểm kỹ thuật, bảng chỉ báo, hỗ trợ/kháng cự
                             (đã gộp tab "Biểu đồ giá" cũ và trang "Phân tích kỹ thuật" ở thanh bên)
  Tab 🎯 Khuyến nghị       : MỘT khuyến nghị theo khung đa lớp (ma trận F × R)
Toàn bộ số liệu từ StockService.full_analysis() (dữ liệu thật); thiếu số liệu hiển thị "—".
"""


import html
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from giao_dien.chung import _base_layout
from giao_dien.chung import warning_box

from core.pipeline import StockService

PRICE_HISTORY_DAYS = 1100      # ~3 năm giá: đủ cho SMA200, beta và kéo xem lịch sử trên biểu đồ

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


def _f_stock_analysis(v, d=0, suf="", sign=False) -> str:
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


def _extra_css_stock_analysis(p) -> str:
    from giao_dien.chung import text_on
    chip = {"up": p["up"], "down": p["down"], "neutral": p["ref"]}
    return f"""<style>
.sa-hero{{display:grid;grid-template-columns:1.3fr 1fr;gap:16px;border:1px solid {p['border']};border-radius:16px;
  padding:18px 20px;margin-bottom:12px;background:{p['card']}}}
@media (max-width:900px){{.sa-hero{{grid-template-columns:1fr}}}}
.sa-sym{{font-size:30px;font-weight:900;color:{p['text']};letter-spacing:-.5px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.sa-chip{{font-size:12px;font-weight:700;padding:3px 9px;border-radius:999px;border:1px solid {p['border']};color:{p['muted']}}}
.sa-name{{font-size:15px;color:{p['muted']};margin-top:2px}}
.sa-price{{font-size:34px;font-weight:900;color:{p['text']};margin-top:10px;font-variant-numeric:tabular-nums}}
.sa-chg{{font-size:16px;font-weight:800;margin-left:8px}}
.sa-range{{margin-top:10px;font-size:12.5px;color:{p['muted']}}}
.sa-range .bar{{position:relative;height:8px;border-radius:999px;background:linear-gradient(90deg,{p['down']},{p['ref']},{p['up']});opacity:.75;margin:5px 0}}
.sa-range .dot{{position:absolute;top:-4px;width:4px;height:16px;border-radius:2px;background:{p['text']}}}
.sa-scores{{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin:4px 0 10px}}
@media (max-width:1100px){{.sa-scores{{grid-template-columns:repeat(3,minmax(0,1fr))}}}}
.sa-sc{{border:1px solid {p['border']};border-radius:12px;padding:10px 12px;background:{p['card']}}}
.sa-sc small{{font-size:12px;font-weight:700;color:{p['muted']};text-transform:uppercase;letter-spacing:.4px}}
.sa-sc b{{display:block;font-size:24px;font-weight:900;color:{p['text']};margin:2px 0 6px;font-variant-numeric:tabular-nums}}
.sa-tag{{display:inline-block;padding:3px 10px;border-radius:8px;font-size:14px;font-weight:800;color:#fff;margin-right:6px}}
.sa-tags{{display:grid;gap:10px;margin:4px 0 12px}}
.sa-tagbox{{border-radius:12px;padding:9px 14px;min-height:62px;display:flex;flex-direction:column;justify-content:center;text-align:center}}
.sa-tagbox small{{font-size:13px;font-weight:700;opacity:.85;text-transform:uppercase;letter-spacing:.4px;color:inherit !important}}
.sa-tagbox b{{font-size:18px;font-weight:900;line-height:1.25;color:inherit !important}}
@media (max-width:700px){{.sa-tags{{grid-template-columns:1fr !important}}}}
.sa-pill{{display:inline-block;padding:2px 9px;border-radius:999px;font-size:13.5px;font-weight:700;color:#fff}}
.sa-pill.up{{background:{chip['up']};color:{text_on(chip['up'])} !important}} .sa-pill.down{{background:{chip['down']};color:{text_on(chip['down'])} !important}}
.sa-pill.neutral{{background:{chip['neutral']};color:{text_on(chip['neutral'])} !important}}
.sa-note{{font-size:13px;color:{p['muted']};margin-top:6px}}
.sa-ladder .row{{display:flex;justify-content:space-between;align-items:center;padding:6px 10px;border-bottom:1px dashed {p['track']};
  font-size:14px;color:{p['text']};font-variant-numeric:tabular-nums}}
.sa-ladder .now{{background:{p['soft']};border:1px solid {p['accent']};border-radius:8px;font-weight:800}}
.sa-big{{font-size:21px;font-weight:900;color:{p['text']}}}
.sa-grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
@media (max-width:900px){{.sa-kgrid{{grid-template-columns:repeat(2,minmax(0,1fr)) !important}}}}
.mo-bar i{{display:block;height:100%}}
.sa-pill,.sa-tag{{text-shadow:none !important}}
.sa-warn{{border-left:3px solid {p['ref']};padding:6px 10px;margin:6px 0;font-size:14px;color:{p['text']}}}
</style>"""


def _kpis(items, p) -> None:
    """items: [(nhãn, giá trị, chú thích, màu chú thích)]"""
    cells = "".join(
        f'<div class="mo-kpi"><small>{_e(a)}</small><b>{_e(b)}</b>'
        f'<small style="color:{d or p["muted"]}">{_e(c)}</small></div>' for a, b, c, d in items)
    # số ô chia đều thành hàng (8 ô → 4 + 4, 6 ô → 6 hoặc 3 + 3) thay vì tự xuống dòng lẻ 7 + 1
    n = len(items)
    cols = 4 if n == 8 else 6 if n in (6, 12) else 5 if n in (5, 10) else n if n <= 4 else 4
    _md(f'<div class="sa-grid2 sa-kgrid" style="grid-template-columns:repeat({cols},minmax(0,1fr))">{cells}</div>')


def _table(headers: List[str], rows: List[List[str]], aligns: Optional[List[str]] = None, raw: bool = False,
           min_w: int = 520) -> None:
    aligns = aligns or (["left"] + ["right"] * (len(headers) - 1))
    th = "".join(f'<th style="text-align:{a}">{_e(h)}</th>' for h, a in zip(headers, aligns))
    body = "".join("<tr>" + "".join(f'<td style="text-align:{a}">{c if raw else _e(c)}</td>' for c, a in zip(r, aligns)) + "</tr>"
                   for r in rows)
    _md(f'<div style="overflow-x:auto"><table class="mo-t" style="min-width:{min_w}px">'
        f'<tr>{th}</tr>{body}</table></div>')


def _gauge_stock_analysis(score: Optional[float], title: str, p) -> go.Figure:
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
        out.append(f'<div class="mo-comp"><span>{_e(lbl)} <small>{_e(note)}</small></span><b>{_f_stock_analysis(s, 0) if s is not None else "—"}</b></div>'
                   f'<div class="mo-track"><i style="width:{s or 0:.0f}%;background:{col}"></i></div>')
    _md("".join(out))


# ─────────────────────────────────────────────────────────────────────────────
# Trang
# ─────────────────────────────────────────────────────────────────────────────

def render_stock_analysis():
    p = _pal()
    _md(_css(p))
    _md(_extra_css_stock_analysis(p))
    _md('<div class="mo-head"><div><div class="mo-title">🔍 Phân Tích Cổ Phiếu</div>'
        '<div class="mo-sub">Định giá · phân tích cơ bản · phân tích kỹ thuật (biểu đồ giá & chỉ báo) · khuyến nghị 12 tháng cho một mã</div></div></div>')

    # Ô "Khoảng thời gian" đã bỏ (14/10/2026): app luôn tải ~3 năm giá; định giá, phân tích cơ bản, beta, điểm kỹ thuật
    # và khuyến nghị không phụ thuộc vào nó; biểu đồ giá có nút chọn khoảng hiển thị riêng.
    col1, col3 = st.columns([3, 1], vertical_alignment="bottom")
    with col1:
        symbol = st.text_input("Nhập mã cổ phiếu", value=st.session_state.get("current_symbol", "FPT"),
                               placeholder="VD: FPT, HPG, VCB...", key="stock_symbol_input").upper().strip()
    with col3:
        analyze_btn = st.button("🔍 Phân Tích", type="primary", width="stretch")
    days = PRICE_HISTORY_DAYS

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
                svc = StockService(symbol, days=days)   # ~3 năm để kéo xem lịch sử trên biểu đồ
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

    # Thanh chọn 4 mục – CHỈ vẽ mục đang mở (14/10/2026). st.tabs chạy nội dung của cả 4 tab ở mỗi lần tương tác
    # (đo được ~1,6 giây dựng biểu đồ Plotly, riêng tab Kỹ thuật ~0,9 giây) dù người dùng chỉ xem một tab.
    names = list(SA_TABS)
    want = st.session_state.pop("sa_tab", None)        # vd. chuyển từ mục cũ "Phân tích kỹ thuật" → mở đúng mục
    if want in names:
        st.session_state["sa_tab_pick"] = st.session_state["sa_tab_last"] = want
    elif st.session_state.get("sa_tab_pick") not in names:
        # lần đầu, hoặc bấm lại mục đang chọn (segmented_control bỏ chọn → None) → giữ mục trước đó
        last = st.session_state.get("sa_tab_last")
        st.session_state["sa_tab_pick"] = last if last in names else names[0]
    pick = st.segmented_control("Mục phân tích", options=names, key="sa_tab_pick", label_visibility="collapsed",
                                width="stretch")
    pick = pick if pick in names else st.session_state.get("sa_tab_last", names[0])
    st.session_state["sa_tab_last"] = pick
    if pick == names[0]:
        _tab_val(analysis, p)
    elif pick == names[1]:
        _tab_fund(analysis, p)
    elif pick == names[2]:
        _tab_technical(symbol, analysis, px, p)
    else:
        _tab_rec(analysis, p)


SA_TABS = ("💰 Định giá", "📊 Phân tích cơ bản", "📈 Phân tích kỹ thuật", "🎯 Khuyến nghị")


def _tab_technical(symbol, analysis, px, p) -> None:
    """Phân tích kỹ thuật = biểu đồ giá (nến + các khung chỉ báo, so sánh VN-Index) + tín hiệu & bảng chỉ báo."""
    _tab_price(symbol, analysis, px, p)
    if px is None:
        return
    _section("Tín hiệu kỹ thuật", "xu hướng · điểm kỹ thuật · bảng chỉ báo · hỗ trợ/kháng cự")
    _tab_tech(symbol, analysis, px, p)


def _tab_rec(analysis, p) -> None:
    """Khuyến nghị duy nhất theo khung đa lớp + định giá, sức khỏe tài chính, rủi ro."""
    inv = analysis.get("investment") or {}
    if not inv or not inv.get("recommendation") or not inv.get("valuation"):
        st.info("Chưa đủ dữ liệu để đưa ra khuyến nghị 12 tháng cho mã này (thiếu BCTC hoặc giá).")
        return
    from giao_dien import thi_truong as rc
    _md(rc._extra_css(p))
    try:
        rc._render_result(inv, p)
    except Exception as exc:  # pragma: no cover - dữ liệu thiếu trường
        st.warning(f"Không hiển thị được khuyến nghị: {exc}")
        return


# ─────────────────────────────────────────────────────────────────────────────
# Đầu trang
# ─────────────────────────────────────────────────────────────────────────────

def _hero(symbol, analysis, px, p) -> None:
    from core.du_lieu import _in_session
    from core import thi_truong_danh_muc as ms

    if _in_session() and px is not None:
        # Trong giờ giao dịch: khối giá đầu trang tự cập nhật – vài giây/lần khi có giá realtime DNSE (API key),
        # ngược lại theo LIVE_REFRESH_SECONDS (mặc định 3 phút) từ nến phút DNSE
        @st.fragment(run_every=ms.live_refresh_seconds())
        def _live_price():
            bar = ms.live_bar(symbol)
            _hero_price(symbol, analysis, ms.merge_live(px, bar) if bar else px, p, live=bar is not None)
        _live_price()
    else:
        _hero_price(symbol, analysis, px, p, live=False)
    _hero_scores(analysis, p)


def _hero_price(symbol, analysis, px, p, live: bool) -> None:
    info = analysis.get("company_info") or {}
    cur = analysis.get("current_price") or {}
    name = info.get("company_name") or info.get("short_name") or ""
    price = _num(cur.get("price"))
    chg, chg_pct = _num(cur.get("change")), _num(cur.get("change_pct"))
    if px is not None and len(px) >= 2 and (live or chg is None or chg_pct is None):
        c0, c1 = float(px["close"].iloc[-2]), float(px["close"].iloc[-1])
        price = c1 if live else (price or c1)
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
    from core.bao_cao_pdf import _exchange_name
    chips = "".join(f'<span class="sa-chip">{_e(x)}</span>' for x in (_exchange_name(info.get("exchange")), ind) if x)
    sess = ""
    if px is not None:
        sess = f"Phiên {pd.Timestamp(_ts(px).iloc[-1]):%d/%m/%Y}"
        st_ = px["session_time"].iloc[-1] if "session_time" in px.columns else None
        if isinstance(st_, str) and st_:
            rt_on = "source" in px.columns and px["source"].iloc[-1] == "dnse_realtime"
            sess += f" · đang giao dịch, {'⚡ realtime ' if rt_on else 'cập nhật '}{st_}"
    from giao_dien.chung import logo_html
    dark = st.session_state.get("theme", "light") == "dark"
    _md(f'<div class="sa-hero"><div><div class="sa-sym">{logo_html(symbol, 46, dark)}{_e(symbol)} {chips}</div><div class="sa-name">{_e(name)}</div>'
        f'<div class="sa-price">{_f_stock_analysis(price)}<span class="sa-chg" style="color:{col}">{arrow} {_f_stock_analysis(chg, 0, "", True)} '
        f'({_f_stock_analysis(chg_pct, 2, "%", True)})</span></div><div class="sa-note">{_e(sess)} · đơn vị VND</div>{range_html}</div>'
        f'<div style="display:flex;align-items:flex-end">{spark}</div></div>')


def _hero_scores(analysis, p) -> None:
    opp = analysis.get("opportunity_score", {}) or {}
    comp = opp.get("composite", {}) or {}
    sub = opp.get("sub_scores", {}) or {}
    inv = analysis.get("investment") or {}
    rec = analysis.get("recommendation") or {}
    hs = ((inv.get("health") or {}).get("score"))
    items = [("Sàng lọc 5 trụ cột", comp.get("score")), ("Kỹ thuật", sub.get("technical")), ("Động lượng", sub.get("momentum")),
             ("Cơ bản", sub.get("fundamental")), ("Định giá", sub.get("valuation")), ("Sức khỏe TC", hs)]
    cells = ""
    for lbl, v in items:
        s = _num(v)
        c = p["up"] if (s or 0) >= 65 else p["ref"] if (s or 0) >= 45 else p["down"]
        cells += (f'<div class="sa-sc"><small>{_e(lbl)}</small><b>{_f_stock_analysis(s, 0)}<span style="font-size:14px;color:{p["muted"]}">/100</span></b>'
                  f'<div class="mo-track"><i style="width:{s or 0:.0f}%;background:{c}"></i></div></div>')
    _md(f'<div class="sa-scores">{cells}</div>')
    # 15/10/2026: không còn ô nhãn ở đầu trang – khuyến nghị duy nhất (khung đa lớp) xem ở tab 🎯 Khuyến nghị




# ─────────────────────────────────────────────────────────────────────────────
# Phân tích kỹ thuật (phần 1) – Biểu đồ giá
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
    live = "session_time" in px.columns and isinstance(px["session_time"].iloc[-1], str)
    _kpis([("Giá khớp gần nhất" if live else "Giá đóng cửa", _f_stock_analysis(c),
            f"Phiên {ts.iloc[-1]:%d/%m/%Y}" + (f" · {px['session_time'].iloc[-1]}" if live else ""), None),
           ("Hiệu suất 1T / 3T", f"{_f_stock_analysis(r1m, 1, '%', True)} / {_f_stock_analysis(r3m, 1, '%', True)}", f"12 tháng {_f_stock_analysis(r1y, 1, '%', True)}", _clr(r1y, p)),
           ("Cách đỉnh 52 tuần", _f_stock_analysis((c / hi52 - 1) * 100, 1, "%", True), f"Đỉnh {hi52:,.0f}", None),
           ("Cách đáy 52 tuần", _f_stock_analysis((c / lo52 - 1) * 100, 1, "%", True), f"Đáy {lo52:,.0f}", None),
           ("KL bình quân 20 phiên", _f_stock_analysis(v20), f"GTGD ~{_f_stock_analysis(gt20, 1)} tỷ/phiên", None),
           ("Biến động năm hóa", _f_stock_analysis(vol, 1, "%"), f"Sụt giảm tối đa 1 năm {_f_stock_analysis(mdd, 1, '%')}", p["down"])], p)

    _section("Biểu đồ giá & chỉ báo kỹ thuật", "kéo sang trái để xem giai đoạn trước · cuộn chuột để phóng to/thu nhỏ · "
             "nháy đúp để xem toàn bộ")
    from giao_dien import chung as price_chart
    c1, c2 = st.columns([1.3, 1])
    with c1:
        overlays = st.multiselect("Chỉ báo trên biểu đồ giá", ["MA20", "MA50", "MA200", "EMA12", "EMA26", "Bollinger"],
                                  default=["MA20", "MA50"], key="sa_overlays")
    with c2:
        span = st.segmented_control("Khung nhìn ban đầu", ["1T", "3T", "6T", "1N", "Tất cả"], default="6T", key="sa_span") or "6T"
    panels = st.multiselect("Khung chỉ báo bên dưới (xem cùng lúc, chung trục thời gian)", price_chart.PANELS,
                            default=price_chart.DEFAULT_PANELS, key="sa_panels")
    days = {"1T": 31, "3T": 92, "6T": 183, "1N": 366}.get(span)
    d = px[(ts >= ts.max() - pd.Timedelta(days=days)).to_numpy()] if days else px
    price_chart.render_cached(px, overlays, panels, days, p, _base_layout())
    st.caption(f"Đã tải {len(px):,} phiên ({ts.min():%d/%m/%Y} – {ts.max():%d/%m/%Y}). Trục giá và các chỉ báo tự co giãn theo "
               "đoạn đang xem; RSI cố định 0–100 (vùng 30/70).")
    if (ts.max() - ts.min()).days < 300:
        st.warning(f"Lịch sử giá của {symbol} mới tải được từ {ts.min():%d/%m/%Y} (nguồn dữ liệu lỗi tạm thời hoặc mã mới niêm "
                   f"yết) nên kéo sang trái chỉ tới ngày này. Bấm **🔍 Phân Tích** để tải lại đầy đủ.")

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
        fig.update_layout(**_base_layout(height=300, margin=dict(l=40, r=10, t=40, b=30), hovermode="x unified",
                                         legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, xanchor="left", bgcolor="rgba(0,0,0,0)", font=dict(color=p["text"]))))
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
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
            rows.append([lbl, f'<b style="font-weight:600;color:{_clr(a, p)}">{_f_stock_analysis(a, 1, "%", True)}</b>',
                         f'<b style="font-weight:600;color:{_clr(b, p)}">{_f_stock_analysis(b, 1, "%", True)}</b>',
                         f'<b style="color:{_clr(ex, p)}">{_f_stock_analysis(ex, 1, " đ%", True)}</b>'])
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
    fig.update_layout(**_base_layout(height=560, margin=dict(l=50, r=60, t=40, b=20), hovermode="x unified",
                                     legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, xanchor="left", bgcolor="rgba(0,0,0,0)", font=dict(color=p["text"])),
                                     xaxis_rangeslider_visible=False))
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])], showgrid=False)
    fig.update_yaxes(gridcolor=p["track"])
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Phân tích kỹ thuật (phần 2) – Tín hiệu
# ─────────────────────────────────────────────────────────────────────────────

_COMP_LABEL = {"ma_alignment": "Đường trung bình (MA)", "rsi": "RSI", "macd": "MACD", "volume": "Khối lượng",
               "bollinger": "Bollinger", "adx": "ADX ± DI", "money_flow": "Dòng tiền (CMF/MFI/OBV)"}


def _tab_tech(symbol, analysis, px, p) -> None:
    tech = analysis.get("technical") or {}
    if not tech.get("available") or px is None:
        warning_box(f"Không có dữ liệu kỹ thuật: {tech.get('reason', '')}")
        return
    from core.bao_cao_pdf import _tech_rows
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
    wait = False
    rows = _tech_rows(px, idx, signals, stop, r1m, r3m, r1y, rs6, wait=wait)
    tones = [_tone(r[2]) for r in rows if r[2]]
    n_up, n_dn, n_nt = tones.count("up"), tones.count("down"), tones.count("neutral")

    c1, c2, c3 = st.columns([1.25, 1, 1.15])
    with c1:
        tc = trend.get("color", p["muted"])
        crit = "".join(f'<b class="sa-pill {_tone(x)}" style="margin:2px">{_e(x)}</b>' for x in trend.get("criteria", []))
        _md(f'<div class="mo-card"><div class="mo-lbl">Xu hướng tổng hợp</div>'
            f'<div style="font-size:28px;font-weight:900;color:{tc};margin:4px 0">{_e(trend.get("name", "—"))}</div>'
            f'<div>{crit}</div><div class="sa-note">Cách đỉnh 20 phiên {_f_stock_analysis(trend.get("pct_from_high"), 1, "%", True)} · '
            f'cách đáy {_f_stock_analysis(trend.get("pct_from_low"), 1, "%", True)}</div></div>')
    with c2:
        st.plotly_chart(_gauge_stock_analysis(score.get("score"), "Điểm kỹ thuật", p), width="stretch", config={"displayModeBar": False})
    with c3:
        tot = max(n_up + n_dn + n_nt, 1)
        _md(f'<div class="mo-card"><div class="mo-lbl">Tổng hợp tín hiệu ({tot} chỉ báo)</div>'
            f'<div class="mo-bar"><i style="width:{n_up / tot * 100:.0f}%;background:{p["up"]}"></i>'
            f'<i style="width:{n_nt / tot * 100:.0f}%;background:{p["ref"]}"></i><i style="width:{n_dn / tot * 100:.0f}%;background:{p["down"]}"></i></div>'
            f'<div class="mo-legend"><b style="font-weight:600;color:{p["up"]}">▲ {n_up} tích cực</b><b style="font-weight:600;color:{p["ref"]}">■ {n_nt} trung tính</b>'
            f'<b style="font-weight:600;color:{p["down"]}">▼ {n_dn} tiêu cực</b></div>'
            + ('<div class="sa-note">Cắt lỗ: <b>chưa áp dụng</b> – đang chờ điểm mua</div></div>' if wait else
               f'<div class="sa-note">Cắt lỗ gợi ý (giá − 2×ATR): <b>{_f_stock_analysis(stop)}</b></div></div>'))
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
                f'{"" if t == "Giá hiện tại" else _f_stock_analysis((v / cnow - 1) * 100, 1, "%", True)}</b></div>' for v, t in lv)
            _md(f'<div class="sa-ladder">{rows_h}</div>')
        else:
            st.caption("Chưa xác định được vùng hỗ trợ/kháng cự.")



# ─────────────────────────────────────────────────────────────────────────────
# Phân tích cơ bản
# ─────────────────────────────────────────────────────────────────────────────

def _quality_block(q, notes, p) -> None:
    """Chất lượng lợi nhuận (analytics.financial_ratios.earnings_quality): lợi nhuận tăng nhờ đâu, có thành tiền không."""
    if not q or not q.get("available"):
        return
    vcol = {"Tốt": p["up"], "Cần lưu ý": p["ref"], "Yếu": p["down"]}.get(q.get("verdict"), p["muted"])
    _section("Chất lượng lợi nhuận", f"{q.get('prev_year')} → {q.get('year')} · đánh giá: {q.get('verdict')}")
    bn = lambda x: _f_stock_analysis(x / 1e9 if x is not None else None, 0)  # noqa: E731
    share = q.get("non_core_share_of_op_growth")
    _kpis([("LN cốt lõi (tỷ)", bn(q.get("core_profit")), f"{_f_stock_analysis(q.get('core_growth'), 1, '%', True)} so với năm trước",
            _clr(q.get("core_growth"), p)),
           ("LNST (tỷ)", bn(q.get("net_income")),
            f"{_f_stock_analysis(q.get('net_income_growth'), 1, '%', True)} · năm trước {bn(q.get('net_income_prev'))} · cốt lõi "
            f"{_f_stock_analysis(q.get('core_growth'), 1, '%', True)}", _clr(q.get("net_income_growth"), p)),
           ("Phần tăng LN HĐKD từ tài chính/khác", _f_stock_analysis(share, 0, "%") if share is not None else "—",
            f"LN HĐKD {bn(q.get('op_profit_prev'))} → {bn(q.get('op_profit'))} tỷ", p["down"] if (share or 0) >= 50 else None),
           ("CFO / LNST", _f_stock_analysis(q.get("cfo_to_ni"), 2, "x"), f"năm trước {_f_stock_analysis(q.get('cfo_to_ni_prev'), 2, 'x')} · CFO "
            f"{_f_stock_analysis(q.get('cfo_growth'), 0, '%', True)}",
            _clr(q.get("cfo_growth"), p)),
           ("FCF (tỷ)", bn(q.get("fcf")), f"{_f_stock_analysis(q.get('fcf_growth'), 0, '%', True)} · năm trước {bn(q.get('fcf_prev'))}",
            _clr(q.get("fcf_growth"), p)),
           ("Piotroski F-score", f"{q['fscore']}/{q['fscore_max']}" if q.get("fscore") is not None else "—",
            ("năm trước " + (f"{q['fscore_prev']}/{q['fscore_prev_max']}" if q.get("fscore_prev") is not None else "—")
             + " · ≥ 7 mạnh · ≤ 3 yếu"), vcol)], p)
    for f in q.get("flags", []):
        _md(f'<div class="sa-warn">{"⚠️" if f["level"] == "cao" else "•"} {_e(f["text"])}</div>')
    for n in notes:
        if n.startswith("Chất lượng lợi nhuận"):
            st.caption("Financial Health Score: " + n)


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
    from core.phan_tich_co_ban import key_to_label

    c1, c2 = st.columns([1, 1.6])
    with c1:
        st.plotly_chart(_gauge_stock_analysis(f_score.get("score"), "Điểm phân tích cơ bản", p), width="stretch",
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
            return (lbl, _f_stock_analysis(v, d, unit if unit == "%" else "x"), dtxt, col)

        _section("Chỉ số chính", f"kỳ {per}")
        _kpis([kp("ROE", "roe"), kp("ROA", "roa"), kp("Biên LN gộp", "gross_margin"), kp("Biên LN ròng", "net_margin"),
               kp("Tăng trưởng doanh thu", "revenue_growth"), kp("Tăng trưởng LNST", "net_income_growth"),
               kp("Nợ vay / VCSH", "debt_to_equity", "x", "low", 2), kp("CFO / LNST", "cfo_to_net_income", "x", "high", 2)], p)

    _quality_block(health.get("earnings_quality"), health.get("notes") or [], p)

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
            fig.update_layout(**_base_layout(height=320, barmode="group", margin=dict(l=40, r=40, t=40, b=30),
                                             legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, xanchor="left", bgcolor="rgba(0,0,0,0)", font=dict(color=p["text"]))))
            st.plotly_chart(fig, width="stretch")
        with b:
            _section("Hiệu quả sinh lời", "%")
            fig = go.Figure()
            if ratios is not None:
                rr = ratios.reindex(w.index)
                for col, name, color in (("roe", "ROE", p["accent"]), ("roa", "ROA", p["up"]), ("gross_margin", "Biên LN gộp", "#8b5cf6"),
                                         ("net_margin", "Biên LN ròng", p["ref"])):
                    if col in rr and rr[col].notna().any():
                        fig.add_scatter(x=lbl, y=rr[col], name=name, mode="lines+markers", line=dict(color=color, width=2.2))
            fig.update_layout(**_base_layout(height=320, margin=dict(l=40, r=10, t=40, b=30), hovermode="x unified",
                                             legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, xanchor="left", bgcolor="rgba(0,0,0,0)", font=dict(color=p["text"]))))
            st.plotly_chart(fig, width="stretch")
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
            fig.update_layout(**_base_layout(height=300, barmode="relative", margin=dict(l=40, r=10, t=40, b=30),
                                             legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, xanchor="left", bgcolor="rgba(0,0,0,0)", font=dict(color=p["text"]))))
            st.plotly_chart(fig, width="stretch")
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
            fig.update_layout(**_base_layout(height=300, margin=dict(l=40, r=10, t=40, b=30), hovermode="x unified",
                                             legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, xanchor="left", bgcolor="rgba(0,0,0,0)", font=dict(color=p["text"]))))
            st.plotly_chart(fig, width="stretch")

    a, b, c = st.columns(3)
    pio, alt, dp = summ.get("piotroski") or {}, summ.get("altman") or {}, summ.get("dupont")
    with a:
        sc = pio.get("score")
        col = p["up"] if (sc or 0) >= 7 else p["ref"] if (sc or 0) >= 4 else p["down"]
        _md(f'<div class="mo-card"><div class="mo-lbl">Piotroski F-score</div><div class="sa-big" style="color:{col}">'
            f'{sc if sc is not None else "—"}<span style="font-size:14px;color:{p["muted"]}"> / {pio.get("max", 9)}</span></div>'
            f'<div class="sa-note">≥ 7 tốt · 4–6 trung bình · ≤ 3 yếu (Piotroski 2000)</div></div>')
    with b:
        if summ.get("is_bank"):
            _md('<div class="mo-card"><div class="mo-lbl">Altman Z\'\'-score</div><div class="sa-big">Không áp dụng</div>'
                '<div class="sa-note">Mô hình không dùng cho ngân hàng / tổ chức tài chính</div></div>')
        else:
            z = alt.get("score")
            col = p["up"] if (z or 0) > 5.85 else p["ref"] if (z or 0) >= 4.35 else p["down"]
            _md(f'<div class="mo-card"><div class="mo-lbl">Altman Z\'\'-score</div><div class="sa-big" style="color:{col}">{_f_stock_analysis(z, 2)}</div>'
                f'<div class="sa-note">{_e(alt.get("zone", alt.get("note", "")))} · &gt; 5,85 an toàn, &lt; 4,35 nguy cơ</div></div>')
    with c:
        if isinstance(dp, pd.DataFrame) and not dp.empty:
            l_ = dp.iloc[-1]
            _md(f'<div class="mo-card"><div class="mo-lbl">DuPont (kỳ gần nhất)</div>'
                f'<div class="sa-big">{_f_stock_analysis(l_.get("roe_dupont"), 1, "%")}</div>'
                f'<div class="sa-note">= biên LN ròng {_f_stock_analysis(l_.get("net_margin"), 1, "%")} × vòng quay TS {_f_stock_analysis(l_.get("asset_turnover"), 2, "x")} '
                f'× đòn bẩy {_f_stock_analysis(l_.get("equity_multiplier"), 2, "x")}</div></div>')
        else:
            _md('<div class="mo-card"><div class="mo-lbl">DuPont</div><div class="sa-big">—</div></div>')

    m = fund.get("metrics") or {}
    warns = (m.get("revenue_profit", {}) or {}).get("warnings", []) + (m.get("debt", {}) or {}).get("warnings", []) + \
        (m.get("cashflow", {}) or {}).get("warnings", [])
    if warns:
        _section("Cảnh báo từ BCTC")
        _md("".join(f'<div class="sa-warn">⚠️ {_e(x)}</div>' for x in warns))

    if isinstance(wide, pd.DataFrame) and not wide.empty:
        from core.bao_cao_pdf import statement_table
        _section("BCTC tóm tắt", "tỷ đồng · 5 kỳ gần nhất")
        for tab, code in zip(st.tabs(["Kết quả kinh doanh", "Cân đối kế toán", "Lưu chuyển tiền tệ"]), ["is", "bs", "cf"]):
            with tab:
                t = statement_table(wide.tail(5), code)
                if t.empty:
                    st.caption("Không có số liệu")
                    continue
                cols = [c for c in t.columns if c != "Chỉ tiêu"]
                _table(["Chỉ tiêu"] + cols, [[r["Chỉ tiêu"]] + [_f_stock_analysis(r[c], 0 if abs(_num(r[c]) or 0) >= 100 else 2) for c in cols]
                                             for _, r in t.iterrows()])
        st.caption("Xem đầy đủ nhiều năm, tải Excel và ~40 chỉ số ở trang 📑 Báo Cáo & Chỉ Số Tài Chính.")


# ─────────────────────────────────────────────────────────────────────────────
# Định giá
# ─────────────────────────────────────────────────────────────────────────────

def _target_range_stock_analysis(v: Dict[str, Any]) -> str:
    """Chú thích dưới giá mục tiêu: khoảng Thận trọng – Tích cực (thay cho mã trạng thái nội bộ "OK")."""
    sc = v.get("scenarios") or {}
    lo, hi = (sc.get("bear") or {}).get("target"), (sc.get("bull") or {}).get("target")
    if not v.get("target_12m"):
        return v.get("status") or "Chưa đủ cơ sở định giá"
    if v.get("status") and v["status"] != "OK":
        return v["status"]
    return f"Thận trọng {_f_stock_analysis(lo)} – Tích cực {_f_stock_analysis(hi)}" if lo and hi else "Kịch bản cơ sở"


def _tab_val(analysis, p) -> None:
    inv = analysis.get("investment") or {}
    v = inv.get("valuation") or {}
    summ = analysis.get("financial_summary") or {}
    snap = summ.get("valuation") or {}
    peers = analysis.get("peers") or {}

    if v.get("scope_change"):
        st.warning("⚠️ " + v["scope_change"]["text"] + " EV/EBITDA và DCF tạm không dùng; độ tin cậy giảm một bậc.")
    _kpis([("Thị giá", _f_stock_analysis(v.get("price")), f"Ngày {v.get('price_date') or '—'}", None),
           # Độ tin cậy thấp → vẫn hiện giá mục tiêu kèm "chỉ tham khảo" (PDF làm giống)
           ("Giá mục tiêu", _f_stock_analysis(v.get("target_12m")), _target_range_stock_analysis(v), None) if v.get("available") or not v.get("target_12m") else
           ("Giá mục tiêu", _f_stock_analysis(v.get("target_12m")), f"Độ tin cậy {str(v.get('confidence') or 'thấp').lower()} – chỉ tham khảo", None),
           ("Upside", _f_stock_analysis(v.get("upside"), 1, "%", True),
            "Giá mục tiêu / thị giá − 1", _clr(v.get("upside"), p) if v.get("available") else None),
           ("Tổng LN kỳ vọng", _f_stock_analysis(v.get("expected_return"), 1, "%", True),
            f"Cổ tức {_f_stock_analysis(v.get('expected_dividend'))} đ/cp" if v.get("dividends_included") else "Không gồm cổ tức",
            _clr(v.get("expected_return"), p)),
           ("Giá trị hợp lý hôm nay", _f_stock_analysis(v.get("fair_value_today") or v.get("intrinsic_today")),
            f"Định giá ngày {v.get('valuation_date') or '—'} · (mục tiêu + cổ tức) ÷ (1 + Ke)", None),
           ("Độ tin cậy", v.get("confidence") or "—", f"{len(v.get('methods', []))} phương pháp hợp lệ", None)], p)

    methods = v.get("methods") or []
    if methods:
        a, b = st.columns([1.5, 1])
        with a:
            _section("Biên định giá theo phương pháp", "thanh: Bear → Bull · chấm: kịch bản cơ sở")
            st.plotly_chart(_football(v, p), width="stretch", config={"displayModeBar": False})
        with b:
            _section("Kịch bản Bear / Base / Bull")
            sc = v.get("scenarios") or {}
            from core.dinh_gia import SCEN_LABEL
            rows = []
            for k in ("bear", "base", "bull"):
                r = sc.get(k) or {}
                if r.get("target"):
                    rows.append([SCEN_LABEL[k], f'<b>{_f_stock_analysis(r["target"])}</b>',
                                 f'<b style="font-weight:600;color:{_clr(r.get("upside"), p)}">{_f_stock_analysis(r.get("upside"), 1, "%", True)}</b>',
                                 _f_stock_analysis((r.get("growth") or 0) * 100, 1, "%", True)])
            if v.get("model") == "hybrid":
                rows = []
                for k in ("bear", "base", "bull"):
                    r = sc.get(k) or {}
                    if r.get("target"):
                        rows.append([SCEN_LABEL[k], _f_stock_analysis(r.get("fair_today")), f'<b>{_f_stock_analysis(r["target"])}</b>',
                                     f'<b style="font-weight:600;color:{_clr(r.get("upside"), p)}">{_f_stock_analysis(r.get("upside"), 1, "%", True)}</b>',
                                     _f_stock_analysis(r.get("eps_fwd")), _f_stock_analysis((r.get("growth") or 0) * 100, 1, "%", True)])
                _table(["Kịch bản", "Hợp lý hôm nay", f"Mục tiêu {v.get('target_date') or '12T'}", "Upside", "EPS NTM",
                        "Tăng trưởng N1"], rows, raw=True, min_w=420)
                st.caption("Kịch bản lấy từ Forecast Engine (tăng trưởng, biên, ROE theo phân vị sai số lịch sử của nhóm) "
                           "kết hợp phân vị bội số và Ke của kịch bản – không cộng trừ thẳng vào giá.")
            else:
                _table(["Kịch bản", "Giá mục tiêu", "Upside", "Tăng trưởng"], rows, raw=True, min_w=340)
                st.caption("Kịch bản thay đổi bộ giả định (tăng trưởng, biên LN, bội số, Ke) – không cộng trừ thẳng vào giá.")
        prof = v.get("profile") or {}
        _section("Chi tiết từng phương pháp", "chỉ dùng phương pháp hợp lệ, trọng số chuẩn hóa lại"
                 + (f" · hồ sơ ngành: {prof.get('label')}" if prof else ""))
        if prof:
            st.caption(f"Chọn hồ sơ vì: {prof.get('reason')}. Cơ sở trọng số: {prof.get('rationale')} "
                       f"Trọng số cấu hình: " + ", ".join(f"{k.upper().replace('_', '/')} {w}" for k, w in
                                                          (prof.get("weights_config") or {}).items()) + ".")
        _table(["Phương pháp", "Cơ sở", "Hệ số", "Hợp lý hôm nay", "Mục tiêu", "Trọng số", "Upside", "Kỳ dữ liệu",
                "Nguồn / giả định"],
               [[_e(m["name"]), _e(f"{m.get('base_label') or ''} {_f_stock_analysis(m.get('base'))}"),
                 _f_stock_analysis(m.get("multiple"), 2, "x") if m.get("multiple") else "—", _f_stock_analysis(m.get("fair_today")),
                 f"<b>{_f_stock_analysis(m['fair'])}</b>", f"{m['weight'] * 100:.0f}%",
                 f'<b style="font-weight:600;color:{_clr(m["upside"], p)}">{_f_stock_analysis(m["upside"], 1, "%", True)}</b>',
                 _e(m.get("period") or "—"),
                 f'<span style="font-size:13px">{_e(m["source"])}</span>'] for m in methods],
               ["left", "left", "right", "right", "right", "right", "right", "left", "left"], raw=True)
        cmp_rows = [c for c in v.get("comparison") or [] if not c.get("used")]
        if cmp_rows:
            st.caption("Đã tính nhưng KHÔNG đưa vào tổng hợp: " + "; ".join(
                f"{c['name']} {_f_stock_analysis(c['target'])} ({c['vs_price'] * 100:+.0f}% thị giá)" for c in cmp_rows) + " – lý do bên dưới.")
    else:
        st.info(f"{v.get('status', 'Chưa đủ cơ sở định giá')}. " + " ".join(v.get("notes", [])[:2]))
    for mth, why in v.get("invalid", []):
        st.caption(f"✖ Không dùng {mth}: {why}")
    for mth, why in v.get("not_applicable", []):
        st.caption(f"– {mth}: {why}")
    fs = v.get("forecast_summary") or {}
    if fs:
        bi = fs.get("base_inputs") or {}
        st.caption(f"Đầu vào từ Forecast Engine (kịch bản cơ sở, kỳ gốc {(fs.get('base') or {}).get('label', '—')}): "
                   f"EPS NTM {_f_stock_analysis(bi.get('eps_fwd'))} (đến {bi.get('ntm_window_end') or '—'}; {bi.get('fy1_label') or 'FY1'} "
                   f"{_f_stock_analysis(bi.get('eps_fy1'))}), BVPS tại ngày mục tiêu {_f_stock_analysis(bi.get('bvps_fwd'))}, ROE NTM "
                   f"{_f_stock_analysis((bi.get('roe_fwd') or 0) * 100, 1, '%') if bi.get('roe_fwd') is not None else '—'}"
                   + (f", EBITDA NTM {_f_stock_analysis((bi.get('ebitda_fwd') or 0) / 1e9)} tỷ" if bi.get("ebitda_fwd") else "") + ".")
        for w_ in (fs.get("warnings") or [])[:6]:
            st.caption("⚠️ Dự báo: " + w_)
    _assumption_warnings(v)

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
            rows.append([lbl, f"<b>{_f_stock_analysis(now, d, 'x')}</b>", _f_stock_analysis(med, d, "x"), _f_stock_analysis(peer, d, "x"), verdict])
        _table(["Bội số", "Hiện tại", "Trung vị 5 năm", f"Ngành ({peers.get('group') or '—'})", "So sánh"], rows,
               ["left", "right", "right", "right", "left"], raw=True)
        st.caption("So sánh với trung vị lịch sử của chính doanh nghiệp (nếu có ≥ 3 năm), nếu không thì với trung vị ngành."
                   + (f" Nhóm ngành: {', '.join(peers['peers'])}." if peers.get("peers") else "")
                   + (f" Đã loại: {', '.join(peers['excluded'])}." if peers.get("excluded") else ""))
        if snap.get("data_gaps"):
            st.caption("⚠️ Bội số hiện tại: thiếu số liệu " + ", ".join(snap["data_gaps"])
                       + " → tạm coi = 0 khi tính EV/EBITDA (chỉ tham khảo).")
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
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

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

    ds = v.get("dcf_sensitivity")
    if ds and v.get("price"):
        _section("Độ nhạy giá trị DCF", "WACC × tăng trưởng dài hạn g · đ/cp · xanh ≥ thị giá")
        price = v["price"]
        rows = []
        for w_, row in zip(ds["wacc"], ds["grid"]):
            cells = [(f'<b style="color:{p["up"] if x >= price else p["down"]}">{x:,.0f}</b>' if x else "—") for x in row]
            rows.append([f"WACC {w_ * 100:.1f}%"] + cells)
        _table([""] + [f"g {g_ * 100:.1f}%" for g_ in ds["g"]], rows, raw=True)
        st.caption("Ô giữa = giả định cơ sở. Giá trị cuối kỳ thường chiếm phần lớn EV nên DCF rất nhạy với WACC và g.")

    st.caption("Khuyến nghị MUA / NẮM GIỮ / BÁN và lý do chi tiết ở tab 🎯 Khuyến nghị.")


def _assumption_warnings(v: Dict[str, Any]) -> None:
    """Cảnh báo giả định thay thế (beta) và dữ liệu thiếu bị tạm coi = 0, kèm độ nhạy / mức ảnh hưởng."""
    asum = v.get("assumptions") or {}
    if asum.get("beta_substituted"):
        msg = next((n for n in v.get("notes", []) if n.startswith("GIẢ ĐỊNH THAY THẾ")), "Beta không đáng tin cậy → dùng β = 1,0.")
        st.warning("⚠️ " + msg)
        sens = [r for r in v.get("beta_sensitivity") or [] if r.get("target_12m")]
        if sens:
            st.caption("Độ nhạy giá mục tiêu theo beta (các yếu tố khác giữ nguyên):")
            _table(["Beta", "Ke", "Giá mục tiêu", "Tổng LN kỳ vọng", "Ghi chú"],
                   [[f"{r['beta']:.2f}", f"{r['ke'] * 100:.1f}%", _f_stock_analysis(r["target_12m"]),
                     _f_stock_analysis(r.get("expected_return"), 1, "%", True),
                     "đang dùng (giả định)" if r.get("is_used") else "beta đo được (không tin cậy)" if r.get("is_measured") else ""]
                    for r in sens], ["right", "right", "right", "right", "left"])
    gaps = v.get("data_gaps") or []
    if gaps:
        lines = []
        for gp in gaps:
            pct = f" (≈ {gp['impact_pct'] * 100:.1f}% vốn hóa)" if gp.get("impact_pct") is not None else ""
            lines.append(f"• {gp['item']} năm {gp['year']} – dùng trong {', '.join(gp.get('methods') or [])}: "
                         f"tạm coi = 0, ảnh hưởng tối đa **{gp['impact']}**{pct}; {gp['direction']}.")
        box = st.error if any(g["impact"] in ("cao", "không xác định") for g in gaps) else st.warning
        box("⚠️ Dữ liệu tài chính thiếu (không phải số 0 thực tế):\n\n" + "\n\n".join(lines))


def _football(v: Dict[str, Any], p) -> go.Figure:
    sc = v.get("scenarios") or {}
    names = {"pe": "P/E dự phóng", "pb": "P/B dự phóng", "dcf": "DCF (FCFF)", "ev_ebitda": "EV/EBITDA",
             "ri": "Thu nhập thặng dư", "ddm": "Cổ tức 2 giai đoạn"}
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


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/screener.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Trang – Bộ lọc cổ phiếu theo chỉ số tính từ BCTC & giá, kèm xếp hạng tổng hợp.
"""


from datetime import datetime

import pandas as pd
import streamlit as st

from giao_dien.chung import page_header
from core.du_lieu import Database
from core.du_lieu import BASKETS, get_basket_names
from core.thi_truong_danh_muc import PRESETS, PROFILE_COLUMNS, ScreenerService

_FILTERABLE = {
    "pe": ("P/E ≤", "<=", 0.0, 60.0, 15.0), "pb": ("P/B ≤", "<=", 0.0, 10.0, 2.0),
    "roe": ("ROE % ≥", ">=", -20.0, 50.0, 15.0), "net_margin": ("Biên LN ròng % ≥", ">=", -20.0, 60.0, 8.0),
    "revenue_growth": ("Tăng trưởng DT % ≥", ">=", -50.0, 100.0, 10.0),
    "net_income_growth": ("Tăng trưởng LNST % ≥", ">=", -50.0, 150.0, 10.0),
    "debt_to_equity": ("Nợ vay/VCSH ≤", "<=", 0.0, 5.0, 1.0), "dividend_yield": ("Tỷ suất cổ tức % ≥", ">=", 0.0, 15.0, 3.0),
    "fscore": ("F-score ≥", ">=", 0.0, 9.0, 6.0), "change_3m": ("% 3 tháng ≥", ">=", -50.0, 100.0, 0.0),
}


def render_screener():
    page_header("🔎 Bộ Lọc Cổ Phiếu", "Lọc & xếp hạng theo chỉ số tính từ BCTC năm gần nhất và diễn biến giá")
    c1, c2 = st.columns([2, 2])
    with c1:
        universes = [b for b in get_basket_names() if "Tất cả" not in b] + ["⭐ Danh mục theo dõi", "✍️ Tự nhập"]
        uni = st.selectbox("Phạm vi cổ phiếu", universes)
    with c2:
        preset = st.selectbox("Bộ lọc mẫu", ["(Tự chọn)"] + list(PRESETS))
    if uni == "✍️ Tự nhập":
        symbols = [s.strip().upper() for s in st.text_input("Danh sách mã (cách nhau dấu phẩy)", "FPT,HPG,VCB,MWG").split(",")]
    elif uni == "⭐ Danh mục theo dõi":
        wl = Database().get_watchlist()
        symbols = wl["symbol"].tolist() if not wl.empty else []
    else:
        symbols = BASKETS.get(uni, [])
    st.caption(f"{len(symbols)} mã · mỗi mã cần vài lượt gọi dữ liệu nên nhóm lớn sẽ mất vài phút ở lần đầu; "
               "kết quả được lưu trong ngày.")

    filters = list(PRESETS.get(preset, []))
    with st.expander("⚙️ Điều kiện lọc", expanded=preset == "(Tự chọn)"):
        cols = st.columns(2)
        for i, (key, (label, op, lo, hi, default)) in enumerate(_FILTERABLE.items()):
            with cols[i % 2]:
                preset_thr = next((t for c, o, t in filters if c == key), None)
                on = st.checkbox(label, value=preset_thr is not None, key=f"f_on_{key}")
                thr = st.slider(label, lo, hi, float(preset_thr if preset_thr is not None else default),
                                key=f"f_thr_{key}", label_visibility="collapsed")
                filters = [f for f in filters if f[0] != key]
                if on:
                    filters.append((key, op, thr))

    if st.button("▶️ Chạy bộ lọc", type="primary") and symbols:
        bar = st.progress(0.0, text="Đang tính chỉ số...")
        df = ScreenerService().run(symbols, progress=lambda i, n: bar.progress(i / n, text=f"Đã xử lý {i}/{n} mã"))
        bar.empty()
        st.session_state["screener_df"] = df

    df = st.session_state.get("screener_df")
    if df is None or df.empty:
        return
    res = ScreenerService.rank(ScreenerService.apply_filters(df, filters))
    st.markdown(f"**{len(res)}/{len(df)} mã đạt điều kiện**")
    # bản lọc cũ (session) có thể còn cột chiến lược nhóm → bỏ
    res = res.drop(columns=[c for c in ("rs_group", "group_signal") if c in res.columns])
    show = res.rename(columns={**PROFILE_COLUMNS, "rank_score": "Điểm xếp hạng"})
    st.dataframe(show.round(2), width="stretch", hide_index=True)
    errors = df[df.get("error").notna()] if "error" in df.columns else pd.DataFrame()
    if not errors.empty:
        with st.expander(f"⚠️ {len(errors)} mã lỗi dữ liệu"):
            st.dataframe(errors[["symbol", "error"]], hide_index=True)
    st.download_button("⬇️ Tải CSV", show.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"loc_co_phieu_{datetime.now():%Y%m%d}.csv", mime="text/csv")
    st.caption("Điểm xếp hạng = bình quân thứ hạng phần trăm của ROE, tăng trưởng, P/E, P/B, nợ vay, động lượng "
               "trong nhóm đã lọc (P/E âm không được coi là rẻ). Mã thiếu số liệu ở tiêu chí nào thì bị loại khỏi tiêu chí đó.")


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/compare.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
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


import html
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from giao_dien.chung import _base_layout

from core.thi_truong_danh_muc import PROFILE_COLUMNS, ScreenerService, compare

SERIES = ["#2563eb", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6"]
PERIODS_compare = {"1Th": 31, "3Th": 92, "6Th": 183, "1N": 365}

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


def _num_compare(v) -> Optional[float]:
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
        price = _num_compare(r.get("price"))
        ch1 = _num_compare(r.get("change_1m"))
        rk = ranks.get(sym)
        badge = (f'<span style="background:{p["accent"]};color:#fff;font-size:11.5px;font-weight:800;'
                 f'padding:2px 8px;border-radius:999px">#{rk} tổng hợp</span>' if rk else "")
        mc = _num_compare(r.get("market_cap"))
        with col:
            _md(f'<div class="mo-card" style="border-top:4px solid {color}">'
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'<div style="font-size:21px;font-weight:900;color:{p["text"]}">{html.escape(sym)}</div>{badge}</div>'
                f'<div class="mo-val" style="font-size:22px">{_f(price, 0)}</div>'
                f'<div class="mo-chg" style="color:{_color(ch1, p)}">1 tháng: {_f(ch1, 1, "%", True)}</div>'
                f'<div style="margin-top:4px">{_spark(s, color, h=38)}</div>'
                f'<div class="mo-meta"><span>P/E <b style="color:{p["text"]}">{_fmt(_num_compare(r.get("pe")), "x")}</b></span>'
                f'<span>ROE <b style="color:{p["text"]}">{_fmt(_num_compare(r.get("roe")), "%")}</b></span></div>'
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
                   f'font-size:14px;color:{p["text"]}"><span>{ic}</span><span>{t}</span></div>'
                   for ic, t in items if t)
    if rows:
        _md(f'<div class="mo-card"><div class="mo-lbl" style="margin-bottom:4px">Nhận xét nhanh</div>{rows}'
            f'<div style="font-size:12px;color:{p["muted"]};margin-top:6px">So sánh trong nhóm đang chọn, '
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
                 f'font-weight:800;font-size:12.5px;text-transform:uppercase;letter-spacing:.5px;text-align:left">'
                 f'{gname}</td></tr>')
        for key, label, kind, good in items:
            vals = [_num_compare(table.loc[s].get(key)) if key in table.columns else None for s in syms]
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
            f'<div style="font-size:12px;color:{p["muted"]};padding:6px 10px">★ tốt nhất trong nhóm · '
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
               margin=dict(l=8, r=8, t=40, b=8), legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, xanchor="left", bgcolor="rgba(0,0,0,0)"))
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
        vol, ret = _num_compare(table.loc[sym].get("vol")), _num_compare(table.loc[sym].get("change_1y"))
        if vol is None or ret is None:
            continue
        mc = _num_compare(table.loc[sym].get("market_cap")) or 0
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
    from core.phan_tich_co_ban import find_sector_basket
    from core.du_lieu import BASKETS
    cur = [s.strip().upper() for s in st.session_state.get("cmp_input", "").split(",") if s.strip()]
    base = cur[0] if cur else st.session_state.get("current_symbol", "FPT")
    basket = find_sector_basket(base)
    if basket:
        peers = [s for s in BASKETS.get(basket, []) if s != base][: 5 - 1]
        st.session_state["cmp_input"] = ",".join([base] + peers)


def render_compare():
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
        st.button("➕ Thêm mã cùng ngành", on_click=_add_peers, width="stretch",
                  help="Giữ mã đầu tiên và điền thêm các mã cùng rổ ngành")
    with c3:
        go_btn = st.button("So sánh", type="primary", width="stretch")

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
        per = st.segmented_control("Kỳ", list(PERIODS_compare), default="6Th", key="cmp_period",
                                   label_visibility="collapsed") or "6Th"
        if not prices.empty:
            st.plotly_chart(_perf_chart(prices, PERIODS_compare[per], p), width="stretch", theme=None,
                            config={"displayModeBar": False})
    with c_r:
        scores = _relative_scores(table)
        if scores.notna().any().any():
            st.plotly_chart(_radar(scores, p), width="stretch", theme=None, config={"displayModeBar": False})
        st.caption("Điểm tương đối giữa các mã đang so sánh (cao nhất nhóm = 100, thấp nhất = 0), không phải điểm tuyệt đối.")

    # ── Rủi ro ──
    _section("Rủi ro – lợi nhuận", "1 năm gần nhất · kích thước bong bóng theo vốn hóa")
    c_a, c_b = st.columns([1.3, 1], gap="medium")
    with c_a:
        st.plotly_chart(_risk_scatter(table, p), width="stretch", theme=None, config={"displayModeBar": False})
    with c_b:
        hm = _corr_heatmap(prices, p) if not prices.empty else None
        if hm is not None:
            _md(f'<div class="mo-lbl" style="margin-bottom:2px">Tương quan lợi suất ngày</div>')
            st.plotly_chart(hm, width="stretch", theme=None, config={"displayModeBar": False})
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
                st.plotly_chart(_metric_bars(table, k, l, kind, good, p), width="stretch", theme=None,
                                config={"displayModeBar": False})

    # ── Tải dữ liệu ──
    export = table.drop(columns=["error"], errors="ignore").rename(columns={**PROFILE_COLUMNS, "vol": "Biến động năm hóa %",
                                                                             "mdd": "Sụt giảm tối đa %"})
    st.download_button("⬇️ Tải bảng so sánh (CSV)", export.to_csv().encode("utf-8-sig"),
                       file_name=f"so_sanh_{'_'.join(table.index)}.csv", mime="text/csv")
