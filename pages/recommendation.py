"""
Trang – 🎯 Khuyến Nghị Đầu Tư & Giá Mục Tiêu 12 Tháng.

Hiển thị kết quả của 3 engine tách biệt (services.StockService.investment_analysis):
  Financial Health Score → Valuation Engine 12T → Risk Assessment → Recommendation Engine.
Không có dữ liệu giả: thiếu nguồn → hiển thị "CHƯA ĐỦ CƠ SỞ" và lý do.
"""
from __future__ import annotations

import html
import json
from typing import Any, Dict, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.charts import _base_layout
from pages.market_overview import _css, _md, _pal, _section

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
def _run(symbol: str, overrides_json: str, holder: Optional[bool], as_of: Optional[str] = None) -> Dict[str, Any]:
    from services.stock_service import StockService
    inv = StockService(symbol, days=365, as_of=as_of).investment_analysis(json.loads(overrides_json), holder=holder)
    inv.pop("peers", None)
    return inv


def _extra_css(p) -> str:
    return f"""<style>
.rc-hero{{display:grid;grid-template-columns:minmax(220px,1.1fr) 3fr;gap:14px;margin-bottom:6px}}
@media (max-width:900px){{.rc-hero{{grid-template-columns:1fr}}}}
.rc-badge{{border-radius:16px;padding:18px;color:#fff;display:flex;flex-direction:column;justify-content:center;gap:4px}}
.rc-badge .t{{font-size:11px;letter-spacing:.8px;text-transform:uppercase;opacity:.85;font-weight:700}}
.rc-badge .r{{font-size:30px;font-weight:900;line-height:1.1}}
.rc-badge .s{{font-size:12.5px;opacity:.92}}
.rc-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.rc-chip{{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:700;color:#fff;margin-right:6px}}
.rc-row{{display:flex;gap:10px;align-items:flex-start;padding:7px 0;border-bottom:1px solid {p['track']};font-size:13px;color:{p['text']}}}
.rc-row small{{color:{p['muted']}}}
.rc-list li{{font-size:13px;color:{p['text']};margin:3px 0}}
</style>"""


def _overrides_ui(p) -> Dict[str, Any]:
    from config.investment_model import load_config
    base = load_config()
    rc, hv = base["recommendation"], base["valuation"]
    with st.expander("⚙️ Ngưỡng khuyến nghị & giả định (có thể chỉnh)", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        bh = c1.slider("MUA: sức khỏe tối thiểu", 50, 95, int(rc["buy_min_health"]), 1)
        br = c2.slider("MUA: lợi nhuận kỳ vọng tối thiểu (%)", 5, 50, int(rc["buy_min_return"]), 1)
        sr = c3.slider("BÁN: lợi nhuận kỳ vọng dưới (%)", -40, 0, int(rc["sell_max_return"]), 1)
        mc = c4.selectbox("Độ tin cậy định giá tối thiểu", ["Thấp", "Trung bình", "Cao"],
                          index=["Thấp", "Trung bình", "Cao"].index(rc["min_confidence"]))
        d1, d2, d3 = st.columns(3)
        rf = d1.number_input("Lãi suất phi rủi ro (%)", 1.0, 10.0, hv["risk_free"] * 100, 0.25)
        erp = d2.number_input("Phần bù rủi ro thị trường (%)", 3.0, 14.0, hv["equity_premium"] * 100, 0.5)
        tg = d3.number_input("Tăng trưởng dài hạn – kịch bản cơ sở (%)", 0.0, 6.0, hv["terminal_growth"]["base"] * 100, 0.25)
        st.caption("Trọng số Financial Health (doanh nghiệp phi tài chính, %) – tự chuẩn hóa về 100:")
        w = base["health"]["weights"]["nonfinancial"]
        cols = st.columns(5)
        labels = {"profitability": "Sinh lời", "growth": "Tăng trưởng", "liquidity": "Thanh toán",
                  "leverage": "Cơ cấu vốn", "cashflow": "Dòng tiền"}
        new_w = {k: cols[i].number_input(labels[k], 0, 60, int(w[k]), 5, key=f"rc_w_{k}") for i, k in enumerate(labels)}
    ov: Dict[str, Any] = {}
    if (bh, br, sr, mc) != (rc["buy_min_health"], rc["buy_min_return"], rc["sell_max_return"], rc["min_confidence"]):
        ov["recommendation"] = {"buy_min_health": bh, "buy_min_return": float(br), "sell_max_return": float(sr),
                                "min_confidence": mc}
    val = {}
    if abs(rf / 100 - hv["risk_free"]) > 1e-9:
        val["risk_free"] = rf / 100
    if abs(erp / 100 - hv["equity_premium"]) > 1e-9:
        val["equity_premium"] = erp / 100
    if abs(tg / 100 - hv["terminal_growth"]["base"]) > 1e-9:
        val["terminal_growth"] = {"base": tg / 100}
    if val:
        ov["valuation"] = val
    if new_w != w and sum(new_w.values()) > 0:
        ov["health"] = {"weights": {"nonfinancial": new_w}}
    return ov


def _scenario_chart(v: Dict[str, Any], p) -> Optional[go.Figure]:
    sc = v.get("scenarios") or {}
    price = v.get("price")
    keys = [k for k in ("bear", "base", "bull") if (sc.get(k) or {}).get("target")]
    if not keys or not price:
        return None
    from analytics.valuation_engine import SCEN_LABEL
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


def render():
    p = _pal()
    _md(_css(p))
    _md(_extra_css(p))
    _md('<div class="mo-head"><div><div class="mo-title">🎯 Khuyến Nghị Đầu Tư & Giá Mục Tiêu 12 Tháng</div>'
        '<div class="mo-sub">Sức khỏe tài chính · Định giá độc lập nhiều phương pháp · Rủi ro → MUA / NẮM GIỮ / BÁN – '
        'minh bạch từng giả định</div></div></div>')

    c1, c2, c3 = st.columns([3, 2.2, 1.2], vertical_alignment="bottom")
    with c1:
        symbol = st.text_input("Mã cổ phiếu", value=st.session_state.get("current_symbol", "FPT"),
                               key="rc_symbol").upper().strip()
    with c2:
        hold = st.radio("Tình trạng", ["Chưa nắm giữ", "Đang nắm giữ"], horizontal=True, key="rc_holder")
    with c3:
        run = st.button("Phân tích", type="primary", use_container_width=True)
    from components.ui import as_of_picker
    d1, d2 = st.columns([2.2, 3])
    with d1:
        as_of = as_of_picker("rc_asof")
    overrides = _overrides_ui(p)
    if not symbol:
        st.info("Nhập mã cổ phiếu.")
        return
    req = (symbol, json.dumps(overrides, sort_keys=True), hold == "Đang nắm giữ", as_of)
    prev = st.session_state.get("rc_req")
    if run or (prev is not None and prev[0] == symbol):     # đã chạy mã này → đổi ngưỡng tự cập nhật
        st.session_state["rc_req"] = req
    if st.session_state.get("rc_req") is None or st.session_state["rc_req"][0] != symbol:
        st.caption("Bấm **Phân tích** để chạy mô hình.")
        return
    with st.spinner(f"Đang phân tích {symbol}…"):
        try:
            inv = _run(*st.session_state["rc_req"])
        except Exception as exc:
            st.error(f"Không chạy được mô hình: {exc}")
            return
    _render_result(inv, p)


def _render_result(inv: Dict[str, Any], p) -> None:
    h, v, risk, rec = inv["health"], inv["valuation"], inv["risk"], inv["recommendation"]
    sym = inv["symbol"]
    if inv.get("as_of"):
        st.info(f"📅 Định giá tại ngày **{pd.Timestamp(inv['as_of']):%d/%m/%Y}** – giá đóng cửa phiên {v.get('price_date') or '—'}, "
                f"BCTC năm gần nhất được dùng: {v.get('data_period') or '—'}. Không dùng thông tin công bố sau ngày này.")
    methods_txt = ", ".join(m["name"] for m in v.get("methods", [])) or "—"
    sub = f"Luật {rec['rule']}" + (f" · Đang nắm giữ: {_e(rec['label_holder'])} · Chưa nắm giữ: {_e(rec['label_non_holder'])}"
                                   if rec["label_holder"] != rec["label_non_holder"] else "")
    hs = h.get("score")
    tiles = [
        ("Thị giá", _n(v.get("price")), f"Ngày giá {v.get('price_date') or '—'}"),
        ("Giá mục tiêu 12T", _n(v.get("target_12m")), v.get("status", "")),
        ("Upside", _n(v.get("upside"), 1, "%", True), "Giá mục tiêu / thị giá − 1"),
        ("Tổng LN kỳ vọng", _n(v.get("expected_return"), 1, "%", True),
         f"Gồm cổ tức {_n(v.get('expected_dividend'))} đ/cp" if v.get("dividends_included") else "Không gồm cổ tức"),
        ("Sức khỏe tài chính", f"{hs:.1f}/100" if hs is not None else "—", h.get("rating_text", "")),
        ("Mức rủi ro", risk.get("level", "—"), f"{risk['counts'].get('Nghiêm trọng', 0)} nghiêm trọng · {risk['counts'].get('Cao', 0)} cao"),
        ("Độ tin cậy định giá", v.get("confidence") or "—", methods_txt),
        ("Dữ liệu BCTC", v.get("data_date") or "—", f"Kỳ hạn {v.get('horizon_months', 12)} tháng"),
    ]
    tiles_html = "".join(f'<div class="mo-kpi"><small>{_e(a)}</small><b>{_e(b)}</b><small>{_e(c)}</small></div>' for a, b, c in tiles)
    _md(f'<div class="rc-hero"><div class="rc-badge" style="background:{rec["hex"]}">'
        f'<div class="t">{_e(sym)} · {_e(inv.get("name") or "")}</div><div class="r">{_e(rec["label"])}</div>'
        f'<div class="s">{sub}</div></div><div class="rc-grid">{tiles_html}</div></div>')

    for r in rec["reasons"]:
        st.markdown(f"**→** {r}")

    left, right = st.columns([1.05, 1])
    with left:
        _section("Kịch bản Bear / Base / Bull", "thay đổi bộ giả định, không cộng trừ thẳng vào giá")
        fig = _scenario_chart(v, p)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Chưa có kịch bản định giá (thiếu thị giá hoặc phương pháp hợp lệ).")
        sc = v.get("scenarios") or {}
        if sc and any((sc.get(k) or {}).get("target") for k in sc):
            from analytics.valuation_engine import SCEN_LABEL
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
            f"<td style='text-align:left;font-size:12px'>{_e(m['source'])}</td></tr>" for m in v["methods"])
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
            _md(f'<div class="rc-row"><span class="rc-chip" style="background:{SEV_COLOR[it["severity"]]}">'
                f'{_e(it["severity"])}</span><div>{_e(it["text"])}<br><small>{_e(it["category"])} · {_e(it["source"])}</small></div></div>')
        st.caption(risk.get("rule", ""))

    with st.expander("❓ Tại sao cổ phiếu này được khuyến nghị như vậy, và giá mục tiêu 12 tháng được tính thế nào?", expanded=True):
        for line in inv.get("explanation", []):
            st.markdown("• " + line)
        st.markdown("**Các điều kiện đã kiểm tra (theo thứ tự luật R1 → R4):**")
        for t in rec["trace"]:
            st.markdown(f"{'🟢 Đúng' if t['passed'] else '⚪ Sai'} · {t['rule']} — {t['detail']}")
        from analytics.recommendation import investment_system_text
        st.markdown("**Hệ thống khuyến nghị:**")
        for k, txt in investment_system_text(inv.get("config")):
            st.markdown(f"- **{k}**: {txt}")
    with st.expander("📐 Giả định & dữ liệu trung gian"):
        asum = v.get("assumptions") or {}
        fmt = {"g_hist": "%", "g_sustainable": "%", "g_base": "%", "net_margin_base": "%", "payout": "%", "ke": "%",
               "risk_free": "%", "equity_premium": "%"}
        lines = []
        for k, val in asum.items():
            if val is None:
                lines.append(f"- {k}: —")
            elif fmt.get(k) == "%":
                lines.append(f"- {k}: {val * 100:.2f}%")
            elif isinstance(val, (int, float)):
                lines.append(f"- {k}: {val:,.2f}")
            else:
                lines.append(f"- {k}: {val}")
        st.markdown("\n".join(lines) or "—")
        hist = v.get("history") or {}
        for k in ("pe", "pb", "ev_ebitda"):
            if hist.get(k):
                st.caption(f"{k.upper()} lịch sử: " + ", ".join(f"{y}: {x:.2f}x" for y, x in hist[k].items()))
        st.caption(f"Ngày tạo: {inv.get('generated_at')} · Phân loại: {inv['company']['type']} / {inv['company']['sector']}")
    _md('<div class="mo-foot">Mô hình định lượng dựa trên BCTC và giá thật; không phải lời khuyên đầu tư. Các ngưỡng là giả định '
        'thiết kế, có thể chỉnh ở phần ⚙️ hoặc config/investment_model.py. Kiểm chứng hiệu quả ở trang 🔬 Backtest.</div>')
