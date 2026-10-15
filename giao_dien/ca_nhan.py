"""
giao_dien/ca_nhan.py – gộp từ 5 module (15/10/2026).

MỤC LỤC
  • pages/watchlist.py – Trang – Danh mục theo dõi, cảnh báo giá và bảng tin hằng ngày của các mã đang theo dõi.
      hàm/lớp chính: render
  • pages/portfolio.py – Page – Portfolio Management (Danh mục đầu tư)
      hàm/lớp chính: render_portfolio
  • pages/opportunity_score.py – Page – Investment Opportunity Score (Chấm điểm cơ hội đầu tư)
      hàm/lớp chính: render_opportunity_score
  • pages/pdf_report.py – Page – PDF Report Generator
      hàm/lớp chính: render_pdf_report
  • pages/data_sources.py – Trang – Trạng thái nguồn dữ liệu, chiến lược ghép nguồn, nguồn gốc dữ liệu của từng mã, nhật ký cập nhật.
      hàm/lớp chính: render_data_sources

Tên trùng giữa các phần đã được đổi (tên cũ → tên mới trong file này):
  portfolio.render → render_portfolio
  opportunity_score.render → render_opportunity_score
  pdf_report.render → render_pdf_report
  data_sources.render → render_data_sources
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/watchlist.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Trang – Danh mục theo dõi, cảnh báo giá và bảng tin hằng ngày của các mã đang theo dõi."""


import pandas as pd
import streamlit as st

from giao_dien.chung import fmt_num, page_header
from core.cau_hinh import settings
from core.tin_tuc import CompanyNewsService
from core.thi_truong_danh_muc import CONDITIONS, WatchlistService


LIVE_MAX = 20      # số mã tối đa lấy giá trong phiên mỗi chu kỳ


def _price_table(snap: pd.DataFrame) -> None:
    """Bảng giá; trong giờ giao dịch tự cập nhật (vài giây khi có giá realtime DNSE, ngược lại ~3 phút)."""
    from core.du_lieu import _in_session
    from core import thi_truong_danh_muc as ms

    def draw(live: bool):
        d = snap.copy()
        if live:
            bars = ms.live_bars(d["symbol"].tolist()[:LIVE_MAX])
            for i, sym in d["symbol"].items():
                b = bars.get(str(sym).upper())
                if b:
                    d.at[i, "price"] = b["close"]
                    pc = d.at[i, "prev_close"] if "prev_close" in d.columns else None
                    if pc:
                        d.at[i, "change_pct"] = (b["close"] / pc - 1) * 100
        view = pd.DataFrame({
            "Mã": d["symbol"], "Giá (đ)": d["price"].map(lambda v: fmt_num(v, 0)),
            "% phiên": d["change_pct"].map(lambda v: fmt_num(v, 2, "%")),
            "% 1 tháng": d["change_1m_pct"].map(lambda v: fmt_num(v, 2, "%")),
            "RSI(14)": d["rsi"].map(lambda v: fmt_num(v, 1)),
        })
        st.dataframe(view, width="stretch", hide_index=True)

    if _in_session():
        @st.fragment(run_every=ms.live_refresh_seconds())
        def _live():
            draw(True)
        _live()
    else:
        draw(False)


def render():
    page_header("⭐ Danh Mục Theo Dõi & Cảnh Báo", "Theo dõi giá (trong phiên tự cập nhật: realtime nếu có API key DNSE, ngược lại ~3 phút), đặt cảnh báo, xem tin tức mới mỗi ngày")
    ws = WatchlistService()

    c1, c2, c3 = st.columns([2, 3, 1])
    with c1:
        new = st.text_input("Thêm mã", value="", placeholder="VD: FPT").upper().strip()
    with c2:
        note = st.text_input("Ghi chú", value="")
    with c3:
        st.write("")
        if st.button("➕ Thêm", width="stretch") and new:
            ws.add(new, note)
            st.rerun()

    syms = ws.symbols()
    if not syms:
        st.info("Danh mục trống. Thêm mã để theo dõi; script cập nhật hằng ngày sẽ lấy giá và tin tức cho các mã này.")
        return

    # Cảnh báo vừa kích hoạt
    triggered = ws.evaluate()
    for t in triggered:
        st.warning(f"🔔 {t['symbol']}: {t['condition']} {fmt_num(t['threshold'], 2)} — giá hiện tại "
                   f"{fmt_num(t['price'], 0)} đ, thay đổi {fmt_num(t['change_pct'], 2, '%')}, RSI {fmt_num(t['rsi'], 1)}")

    with st.spinner("Đang cập nhật giá..."):
        snap = ws.snapshot()
    if not snap.empty:
        _price_table(snap)
    rm = st.selectbox("Bỏ theo dõi mã", [""] + syms)
    if rm and st.button("Xóa khỏi danh mục"):
        ws.remove(rm)
        st.rerun()

    st.markdown("#### 🔔 Cảnh báo giá")
    c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
    with c1:
        a_sym = st.selectbox("Mã", syms, key="al_sym")
    with c2:
        cond = st.selectbox("Điều kiện", list(CONDITIONS), format_func=CONDITIONS.get)
    with c3:
        thr = st.number_input("Ngưỡng", value=0.0, step=100.0 if cond.startswith("price") else 1.0)
    with c4:
        st.write("")
        if st.button("Tạo cảnh báo", width="stretch"):
            ws.add_alert(a_sym, cond, thr)
            st.rerun()
    al = ws.alerts()
    if not al.empty:
        al_view = al[["id", "symbol", "condition_label", "threshold", "active", "triggered_at", "triggered_price"]]
        st.dataframe(al_view.rename(columns={"symbol": "Mã", "condition_label": "Điều kiện", "threshold": "Ngưỡng",
                                             "active": "Đang bật", "triggered_at": "Kích hoạt lúc",
                                             "triggered_price": "Giá khi kích hoạt"}),
                     width="stretch", hide_index=True)
        del_id = st.selectbox("Xóa cảnh báo #", [None] + al["id"].tolist())
        if del_id and st.button("Xóa cảnh báo"):
            ws.delete_alert(int(del_id))
            st.rerun()

    st.markdown("#### 📰 Bảng tin các mã đang theo dõi")
    days = st.select_slider("Trong vòng", [1, 3, 7, 14, 30], value=7, format_func=lambda d: f"{d} ngày")
    if st.button("🔄 Thu thập tin mới"):
        svc = CompanyNewsService()
        with st.spinner("Đang thu thập tin..."):
            for s in syms:
                svc.get_company_news(s, force_refresh=True)
    feed = CompanyNewsService.feed(syms, days=days)
    if feed.empty:
        st.info("Chưa có tin đã lưu trong khoảng này. Bấm “Thu thập tin mới” hoặc chạy script cập nhật hằng ngày.")
        return
    icon = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}
    for _, n in feed.head(60).iterrows():
        when = pd.to_datetime(n["published_at"]).strftime("%d/%m %H:%M") if pd.notna(n["published_at"]) else "—"
        title = f"[{n['title']}]({n['url']})" if n.get("url") else n["title"]
        st.markdown(f"{icon.get(n['sentiment'], '⚪')} **{n['symbol']}** · {when} · {title}  "
                    f"<span style='font-size:12px;color:#64748b'>({n['source']})</span>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/portfolio.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Page – Portfolio Management (Danh mục đầu tư)
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from core.thi_truong_danh_muc import PortfolioService
from giao_dien.chung import portfolio_pie
from giao_dien.chung import section_header, warning_box, format_vnd

svc = PortfolioService()


def render_portfolio():
    st.markdown("""
    <div class="page-header">
        <h1 style="font-size:22px;font-weight:800;color:#e6edf3;margin:0">
            💼 Danh Mục Đầu Tư
        </h1>
        <p style="font-size:14px;color:#8b949e;margin:4px 0 0 0">
            Theo dõi danh mục cổ phiếu cá nhân
        </p>
    </div>
    """, unsafe_allow_html=True)

    portfolio_name = st.text_input("Tên danh mục", value="default", key="portfolio_name_input")

    # ── Add position ──
    with st.expander("➕ Thêm vị thế mới"):
        col1, col2, col3 = st.columns(3)
        with col1:
            new_symbol = st.text_input("Mã CP", key="new_sym").upper()
            new_qty = st.number_input("Số lượng (CP)", min_value=100, step=100, value=1000)
        with col2:
            new_price = st.number_input("Giá mua (VND)", min_value=1000, step=100, value=50000)
            new_date = st.date_input("Ngày mua", value=datetime.now())
        with col3:
            new_fee = st.number_input("Phí GD (%)", min_value=0.0, max_value=1.0,
                                       value=0.15, step=0.01, format="%.2f") / 100
            new_notes = st.text_area("Ghi chú", height=75)

        if st.button("Thêm vào danh mục", type="primary"):
            if new_symbol and new_qty > 0 and new_price > 0:
                svc.add_position(new_symbol, new_qty, new_price,
                                  str(new_date), new_fee, new_notes, portfolio_name)
                st.success(f"Đã thêm {new_symbol} vào danh mục '{portfolio_name}'")
                st.rerun()
            else:
                warning_box("Vui lòng nhập đầy đủ thông tin")

    st.markdown("---")

    # ── Portfolio display ──
    summary = svc.get_portfolio_summary(portfolio_name)

    if summary.get("empty"):
        st.info("Danh mục trống. Hãy thêm cổ phiếu bên trên.")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Tổng vốn bỏ ra", format_vnd(summary["total_cost"], "tỷ"))
    with col2:
        st.metric("Giá trị hiện tại", format_vnd(summary["total_value"], "tỷ"))
    with col3:
        pnl = summary["total_pnl"]
        st.metric("Lãi/Lỗ chưa thực", format_vnd(pnl, "tỷ"),
                  delta=f"{summary['total_pct']:+.2f}%",
                  delta_color="normal" if pnl >= 0 else "inverse")
    with col4:
        st.metric("Số vị thế", summary["n_positions"])

    # Charts
    col_chart, col_table = st.columns([1, 2])
    positions_df = summary.get("positions", pd.DataFrame())

    with col_chart:
        if not positions_df.empty:
            fig = portfolio_pie(positions_df)
            st.plotly_chart(fig, width="stretch")

    with col_table:
        section_header("Chi tiết danh mục")
        if not positions_df.empty:
            display_df = positions_df[[
                "symbol", "quantity", "buy_price", "current_price",
                "unrealized_pnl", "unrealized_pct"
            ]].copy()
            display_df.columns = ["Mã", "Số lượng", "Giá mua", "Giá hiện tại", "Lãi/Lỗ", "% L/L"]
            st.dataframe(display_df, width="stretch", hide_index=True)

    # Delete
    section_header("Xóa vị thế")
    if not positions_df.empty:
        del_id = st.selectbox(
            "Chọn vị thế cần xóa",
            options=positions_df["id"].tolist(),
            format_func=lambda x: f"ID {x}: {positions_df[positions_df['id']==x]['symbol'].values[0]}",
        )
        if st.button("🗑️ Xóa vị thế", type="secondary"):
            svc.delete_position(del_id)
            st.success("Đã xóa vị thế")
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/opportunity_score.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Page – Investment Opportunity Score (Chấm điểm cơ hội đầu tư)
"""
import streamlit as st
import pandas as pd

from core.pipeline import StockService
from giao_dien.chung import score_gauge
from giao_dien.chung import section_header, warning_box, score_badge, render_score_breakdown
from core.cau_hinh import SCORE_CATEGORIES


def render_opportunity_score():
    st.markdown("""
    <div class="page-header">
        <h1 style="font-size:22px;font-weight:800;color:#e6edf3;margin:0">
            🎯 Chấm Điểm Cơ Hội Đầu Tư
        </h1>
        <p style="font-size:14px;color:#8b949e;margin:4px 0 0 0">
            Mô hình chấm điểm 0–100 dựa trên quy tắc minh bạch
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Legend
    with st.expander("📋 Phân loại điểm"):
        cols = st.columns(5)
        cats = list(SCORE_CATEGORIES.items())
        for i, ((lo, hi), (label, color, emoji)) in enumerate(cats):
            with cols[i]:
                st.markdown(
                    f'<div style="background:{color}20;border:1px solid {color};border-radius:8px;'
                    f'padding:8px;text-align:center">'
                    f'<div style="font-size:19px">{emoji}</div>'
                    f'<div style="color:{color};font-weight:700">{lo}–{hi}</div>'
                    f'<div style="font-size:13px;opacity:0.9">{label}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    col1, col2 = st.columns([2, 1])
    with col1:
        symbol = st.text_input("Mã cổ phiếu", value=st.session_state.get("current_symbol", "FPT"),
                               key="score_symbol").upper().strip()
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("🎯 Tính điểm", type="primary", width="stretch")

    if not symbol:
        st.info("Nhập mã cổ phiếu để chấm điểm.")
        return

    if run_btn or True:
        with st.spinner(f"Đang tính điểm cho {symbol}..."):
            try:
                svc = StockService(symbol, days=365)
                result = svc.compute_opportunity_score()
            except Exception as e:
                st.error(f"Lỗi: {e}")
                return

        composite = result.get("composite", {})
        sub_scores = result.get("sub_scores", {})
        score = composite.get("score")
        classification = composite.get("classification", {})
        components = composite.get("components", {})
        coverage = composite.get("coverage_pct", 0)

        # ── Main score display ──
        col_gauge, col_detail = st.columns([1, 2])
        with col_gauge:
            st.plotly_chart(score_gauge(score, "Điểm cơ hội"), width="stretch")
            if score is not None:
                badge = score_badge(score, classification.get("label", ""))
                st.markdown(badge, unsafe_allow_html=True)
            st.metric("Độ phủ dữ liệu", f"{coverage}%")

        with col_detail:
            section_header("Điểm thành phần")
            weights = {"technical": 25, "momentum": 20, "fundamental": 25, "valuation": 20, "risk": 10}
            labels = {
                "technical": "🔧 Kỹ thuật",
                "momentum": "⚡ Động lượng",
                "fundamental": "📊 Cơ bản",
                "valuation": "💰 Định giá",
                "risk": "⚠️ Rủi ro",
            }
            for key, label in labels.items():
                val = sub_scores.get(key)
                weight = weights.get(key, 0)
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.markdown(f"**{label}**")
                with c2:
                    st.markdown(f"{val:.0f}/100" if val is not None else "N/A")
                with c3:
                    if val is not None:
                        st.progress(val / 100)
                    else:
                        st.caption("Thiếu DL")

        # ── Note / disclaimer ──
        if composite.get("note"):
            st.info(f"📌 {composite['note']}")

        st.caption(composite.get("disclaimer", ""))

        # ── Component breakdown ──
        if components:
            section_header("Chi tiết tính điểm từng nhóm")
            comp_rows = []
            for key, data in components.items():
                comp_rows.append({
                    "Nhóm": key.replace("_", " ").title(),
                    "Trọng số": f"{data.get('weight', 0):.0f}%",
                    "Điểm (0-100)": f"{data.get('score', 'N/A')}",
                    "Đóng góp": f"{data.get('contribution', 'N/A'):.1f}" if data.get('contribution') else "N/A",
                    "Trạng thái": "✅" if data.get("status") == "ok" else "⚠️",
                })
            st.dataframe(pd.DataFrame(comp_rows), width="stretch", hide_index=True)

        # ── Formula explanation ──
        with st.expander("📐 Công thức và ngưỡng tính điểm"):
            st.markdown("""
            ### Công thức tổng quát
            ```
            Điểm_composite = Σ (Điểm_nhóm_i × Trọng_số_i) / Tổng_trọng_số_có_dữ_liệu
            ```

            ### Trọng số mặc định
            | Nhóm | Trọng số |
            |------|----------|
            | Kỹ thuật (Technical) | 25% |
            | Động lượng (Momentum) | 20% |
            | Cơ bản (Fundamental) | 25% |
            | Định giá (Valuation) | 20% |
            | Rủi ro (Risk) | 10% |

            ### Xử lý dữ liệu thiếu
            - Nếu một nhóm thiếu dữ liệu → **không gán điểm 0**
            - Điểm được chuẩn hóa trên tổng trọng số có dữ liệu
            - Báo cáo rõ % độ phủ dữ liệu

            ### Lưu ý quan trọng
            > Đây là điểm quy tắc nội bộ, **KHÔNG phải xác suất sinh lời**.
            > Điểm cao không đảm bảo lợi nhuận. Luôn xem xét rủi ro.
            """)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/pdf_report.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Page – PDF Report Generator
"""
import streamlit as st
from datetime import datetime
from pathlib import Path
import re

from core.pipeline import StockService
from core.du_lieu import Database
from giao_dien.chung import section_header, warning_box
from giao_dien.chung import safe_html

db = Database()


def render_pdf_report():
    st.markdown("""
    <div class="page-header">
        <h1 style="font-size:22px;font-weight:800;color:#e6edf3;margin:0">
            📄 Tạo Báo Cáo Phân Tích PDF
        </h1>
        <p style="font-size:14px;color:#8b949e;margin:4px 0 0 0">
            Xuất báo cáo theo phong cách công ty chứng khoán chuyên nghiệp
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.text_input("Mã cổ phiếu", value=st.session_state.get("current_symbol", "FPT"),
                               key="pdf_symbol").upper().strip()
    with col2:
        report_type = st.selectbox("Loại báo cáo", ["full", "short"],
                                    format_func=lambda x: "Báo cáo đầy đủ (12 mục)" if x == "full" else "Báo cáo ngắn (tóm tắt, KQKD, kỹ thuật, định giá, rủi ro, kết luận)")
    with col3:
        days = st.selectbox("Khoảng thời gian phân tích", [90, 180, 365, 730], index=2,
                             format_func=lambda d: f"{d} ngày ({d//365} năm)" if d >= 365 else f"{d} ngày")

    # Chọn mục theo nhu cầu (có tác dụng thật khi tạo PDF)
    from core.bao_cao_pdf import PDFReportGenerator as _G
    default = _G.DEFAULT_SECTIONS if report_type == "full" else _G.SHORT_SECTIONS
    c_a, c_b = st.columns([3, 1])
    with c_a:
        sections = st.multiselect("📋 Các mục cần xuất", list(_G.SECTIONS), default=default,
                                  format_func=_G.SECTIONS.get)
    with c_b:
        fin_period = st.selectbox("Kỳ BCTC", ["year", "quarter"], format_func=lambda p: "Năm" if p == "year" else "Quý (TTM)")
    from giao_dien.chung import as_of_picker
    c_d, _c_sp = st.columns([2.2, 3])
    with c_d:
        as_of = as_of_picker("pdf_asof", "Giá tại ngày: toàn bộ báo cáo (giá, biểu đồ, chỉ báo, BCTC, định giá, khuyến nghị) "
                                         "được cắt về ngày chọn – dùng để chốt số liệu cho bài nộp. Tin tức chỉ lấy tin đến ngày đó.")
    c_n, c_c = st.columns(2)
    with c_n:
        include_news = st.checkbox("Kèm tin tức doanh nghiệp mới nhất", value=True)
    with c_c:
        include_cover = st.checkbox("Kèm trang bìa (mã, tên DN, ngày & giờ xuất)", value=True)

    # Cá nhân hóa theo hồ sơ nhà đầu tư (core/khuyen_nghi.py)
    from core.khuyen_nghi import RISK_LABEL, HORIZON_LABEL, GOAL_LABEL
    with st.expander("👤 Cá nhân hóa báo cáo theo hồ sơ nhà đầu tư", expanded=st.session_state.get("pdf_personal_on", False)):
        use_personal = st.checkbox("Bật báo cáo cá nhân hóa (thêm mục \"Báo cáo cá nhân hóa\" vào PDF)", key="pdf_personal_on")
        p1, p2 = st.columns(2)
        with p1:
            inv_name = st.text_input("Tên nhà đầu tư (hiển thị trên báo cáo)", key="pdf_inv_name")
            risk_pf = st.radio("Khẩu vị rủi ro", list(RISK_LABEL), index=1, format_func=RISK_LABEL.get,
                               horizontal=True, key="pdf_inv_risk",
                               help="Thận trọng: ngưỡng MUA chặt hơn, tỷ trọng ≤ 5%, cắt lỗ 7%. "
                                    "Cân bằng: ngưỡng chuẩn, ≤ 10%, cắt lỗ 10%. Mạo hiểm: ngưỡng nới, ≤ 15%, cắt lỗ 15%.")
            horizon = st.selectbox("Kỳ hạn đầu tư", list(HORIZON_LABEL), index=1, format_func=HORIZON_LABEL.get,
                                   key="pdf_inv_horizon")
            goal = st.selectbox("Mục tiêu đầu tư", list(GOAL_LABEL), index=2, format_func=GOAL_LABEL.get, key="pdf_inv_goal")
        with p2:
            capital = st.number_input("Tổng vốn đầu tư (đồng, 0 = không khai báo)", min_value=0.0, value=0.0,
                                      step=10_000_000.0, format="%.0f", key="pdf_inv_capital")
            holder = st.checkbox("Tôi đang nắm giữ cổ phiếu này", key="pdf_inv_holder")
            cost = st.number_input("Giá vốn (đ/cp)", min_value=0.0, value=0.0, step=100.0, format="%.0f",
                                   key="pdf_inv_cost", disabled=not holder)
            qty = st.number_input("Số cổ phiếu đang có", min_value=0, value=0, step=100, key="pdf_inv_qty",
                                  disabled=not holder)
        st.caption("Báo cáo cá nhân hóa dùng lại kết quả định giá, sức khỏe tài chính và rủi ro; chỉ thay đổi ngưỡng khuyến nghị, "
                   "đánh giá mức phù hợp và kế hoạch hành động (tỷ trọng, vùng mua, cắt lỗ, chốt lời) theo hồ sơ. "
                   "Mang tính tham khảo, không phải tư vấn đầu tư.")
    profile = {"name": inv_name, "risk": risk_pf, "horizon": horizon, "goal": goal, "holder": holder,
               "cost": cost or None, "qty": qty or None, "capital": capital or None} if use_personal else None

    if not symbol:
        st.info("Nhập mã cổ phiếu để tạo báo cáo.")
        return

    # Kiểm tra file giao diện báo cáo (thiếu thì bìa thành nền trơn & phông mặc định)
    _root = Path(__file__).resolve().parent.parent
    _need = [_root / "assets" / "report" / "cover_bg.jpg", _root / "assets" / "report" / "page_bg.jpg",
             _root / "assets" / "fonts" / "BeVietnamPro-Bold.ttf",
             _root / "reports" / "cover.py"]
    _missing = [str(p.relative_to(_root)) for p in _need if not p.exists()]
    if _missing:
        st.warning("⚠️ Thiếu file giao diện báo cáo: " + ", ".join(f"`{m}`" for m in _missing)
                   + ". Báo cáo vẫn xuất được nhưng bìa/các trang sẽ là nền trơn và dùng phông mặc định. "
                   "Hãy chép đè cả thư mục `assets` (và `reports`) từ bản zip mới nhất.")

    generate_btn = st.button(
        f"📄 TẠO BÁO CÁO PDF – {symbol}",
        type="primary",
        width="stretch",
    )

    if generate_btn:
        with st.spinner(f"Đang thu thập dữ liệu và tạo báo cáo cho {symbol}..."):
            try:
                # Run full analysis
                # tải ≥ ~3 năm giá để MA200, beta… đủ dữ liệu ngay từ đầu khung biểu đồ; biểu đồ chỉ hiển thị `days` ngày cuối
                svc = StockService(symbol, days=max(int(days), 1100), fin_period=fin_period, as_of=as_of)
                analysis = svc.full_analysis()
                analysis["chart_days"] = int(days)

                # Tin tức thật cho mục "Bối cảnh & Tin tức" (không có thì PDF ghi rõ là chưa thu thập được)
                analysis["news"] = []
                if include_news:
                    try:
                        from core.tin_tuc import CompanyNewsService
                        analysis["news"] = CompanyNewsService().get_company_news(symbol).get("news", [])
                    except Exception:
                        pass
                    if as_of:   # chỉ giữ tin đến ngày định giá (tin không rõ ngày bị bỏ)
                        import pandas as _pd
                        lim = _pd.Timestamp(as_of) + _pd.Timedelta(days=1)
                        def _dt(it):
                            d = it.get("timestamp_dt") or it.get("published") or it.get("date")
                            try:
                                return _pd.Timestamp(d).tz_localize(None) if _pd.Timestamp(d).tzinfo else _pd.Timestamp(d)
                            except Exception:
                                return None
                        analysis["news"] = [it for it in analysis["news"] if _dt(it) is not None and _dt(it) < lim]

                if profile:
                    from core.khuyen_nghi import build_personal_report
                    analysis["personal"] = build_personal_report(analysis, profile)
                    if "personal" not in sections:
                        sections = list(sections) + ["personal"]

                # Generate PDF
                from core.bao_cao_pdf import PDFReportGenerator
                generator = PDFReportGenerator()
                pdf_bytes = generator.generate(analysis, report_type=report_type, sections=sections,
                                               cover=include_cover)

                # Log to DB
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{symbol}_{report_type}_{ts}.pdf" if not as_of else f"{symbol}_{report_type}_ngay{as_of.replace('-', '')}_{ts}.pdf"
                if profile:
                    filename = filename.replace(f"_{ts}.pdf", f"_canhan_{ts}.pdf")
                db.log_report(symbol, report_type, filename)

                st.success(f"✅ Báo cáo đã tạo thành công! ({len(pdf_bytes):,} bytes)")

                # Download button
                st.download_button(
                    label=f"⬇️ Tải báo cáo {symbol}.pdf",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    type="primary",
                )

                # Preview summary
                section_header("Tóm tắt báo cáo")
                opp = analysis.get("opportunity_score", {})
                composite = opp.get("composite", {})
                score = composite.get("score")
                rec = analysis.get("recommendation") or {}
                fv = analysis.get("fair_value") or {}
                m1, m2, m3 = st.columns(3)
                _ml = (analysis.get("investment") or {}).get("multilayer")
                if _ml:
                    m1.metric("Khuyến nghị", _ml["label"], delta=f"F {_ml.get('F') or 0:.0f} · R {_ml.get('R') or 0:.0f}",
                              delta_color="off")
                else:
                    m1.metric("Khuyến nghị", rec.get("rating", "—"),
                              delta=f"LN kỳ vọng {rec['expected_return']:+.1f}%" if rec.get("expected_return") is not None else None)
                m2.metric("Giá mục tiêu" if fv.get("model") == "12m" else "Giá trị hợp lý",
                          f"{fv['fair_value']:,.0f}" if fv.get("available") else "—",
                          delta=f"{fv['upside']:+.1f}%" if fv.get("available") else None)
                if score is not None:
                    m3.metric("Điểm cơ hội đầu tư", f"{score}/100",
                              delta=composite.get("classification", {}).get("label", ""))

                ps = analysis.get("personal")
                if ps:
                    section_header("Báo cáo cá nhân hóa")
                    color = ps.get("hex") if isinstance(ps.get("hex"), str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", ps["hex"]) else "#2563eb"
                    fit_text = safe_html(ps.get("fit_text"))
                    st.markdown(f"<div style='border-left:4px solid {color};padding:8px 12px;margin-bottom:8px'>"
                                f"<b style='color:{color};font-size:19px'>{safe_html(ps.get('label'))}</b> · mức phù hợp "
                                f"<b>{ps['fit_score'] if ps.get('fit_score') is not None else '—'}/100</b> ({fit_text})<br>"
                                f"{safe_html(ps.get('summary'))}</div>", unsafe_allow_html=True)
                    _st = {"ok": "✅ Đạt", "warn": "⚠️ Cần lưu ý", "bad": "❌ Không đạt"}
                    import pandas as _pd
                    st.dataframe(_pd.DataFrame([{"Tiêu chí": f["criterion"], "Yêu cầu hồ sơ": f["profile"],
                                                 "Cổ phiếu": f["stock"], "Đánh giá": _st[f["status"]], "Ghi chú": f["note"]}
                                                for f in ps["fit"]]), width="stretch", hide_index=True)
                    pl = ps["plan"]
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Tỷ trọng tối đa", f"{pl['weight'] * 100:.1f}%")
                    k2.metric("Số CP gợi ý", f"{pl['shares']:,}" if pl.get("shares") else "—")
                    k3.metric("Cắt lỗ", f"{pl['stop']:,.0f}" if pl.get("stop") else "—")
                    k4.metric("Chốt lời", f"{pl['take_profit']:,.0f}" if pl.get("take_profit") else "—")
                    if ps.get("holding"):
                        hd = ps["holding"]
                        st.info(f"Vị thế: lãi/lỗ tạm tính {hd['pnl_pct']:+.1f}% · {hd['action']}")

                company = analysis.get("company_info", {})
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Thông tin doanh nghiệp:**")
                    st.write(f"Tên: {company.get('company_name', company.get('name', 'N/A'))}")
                    st.write(f"Sàn: {company.get('exchange', 'N/A')}")
                    st.write(f"Ngành: {company.get('sector', 'N/A')}")
                with col2:
                    current = analysis.get("current_price", {})
                    if current and current.get("price"):
                        st.markdown("**Giá tham chiếu:**")
                        st.write(f"{current['price']:,.0f} VND")
                        st.write(f"Thời điểm: {current.get('timestamp', 'N/A')}")

            except ImportError as e:
                name = getattr(e, "name", "") or ""
                if name.split(".")[0] in ("reports", "services", "data", "analytics", "components", "pages", "config"):
                    st.error(f"❌ Thiếu file trong dự án: `{name.replace('.', '/')}.py`. "
                             "Hãy giải nén lại bản zip mới nhất và chép đè TOÀN BỘ thư mục GPM1.")
                else:
                    st.error(f"❌ Thiếu thư viện: {e}. Chạy: `pip install -r requirements.txt`")
            except Exception as e:
                st.error(f"❌ Lỗi tạo báo cáo: {e}")
                import traceback
                with st.expander("Chi tiết lỗi"):
                    st.code(traceback.format_exc())

    # ── Report history ──
    st.markdown("---")
    section_header("Lịch sử báo cáo")
    history_df = db.get_reports_history(limit=20)
    if not history_df.empty:
        st.dataframe(history_df, width="stretch", hide_index=True)
    else:
        st.caption("Chưa có báo cáo nào được tạo.")


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/data_sources.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Trang – Trạng thái nguồn dữ liệu, chiến lược ghép nguồn, nguồn gốc dữ liệu của từng mã, nhật ký cập nhật."""


import pandas as pd
import streamlit as st

from giao_dien.chung import page_header, symbol_input
from core.cau_hinh import settings
from core.du_lieu import cache
from core.du_lieu import Database
from core.pipeline import StockService, get_repo


def render_data_sources():
    page_header("🛰️ Nguồn Dữ Liệu", "Kiểm tra từng nguồn, xem dữ liệu của mỗi mã đến từ đâu, nhật ký cập nhật tự động")

    st.markdown("#### Chiến lược kết hợp nguồn")
    st.markdown(f"""
| Loại dữ liệu | Thứ tự ưu tiên | Ghi chú |
|---|---|---|
| Giá {settings.DNSE_RECENT_DAYS} ngày gần nhất | **DNSE** → nguồn lịch sử | giá khớp gần nhất cũng lấy từ DNSE |
| Giá lịch sử (cũ hơn) | {' → '.join(settings.PRICE_HISTORY_SOURCES)} | tự điều chỉnh hệ số ở điểm nối nếu hai nguồn lệch (cổ tức / chia tách) |
| BCTC năm & quý | {' → '.join(settings.FINANCIAL_SOURCES)} | nguồn sau bù kỳ/chỉ tiêu nguồn trước thiếu |
| Tài liệu PDF | {' → '.join(settings.DOCUMENT_SOURCES)} → website DN | luôn có thể tải lên tay |
""")
    st.caption("Đổi thứ tự trong file .env: DNSE_RECENT_DAYS, PRICE_HISTORY_SOURCES, FINANCIAL_SOURCES, DOCUMENT_SOURCES.")

    st.markdown("#### Giá realtime (DNSE OpenAPI)")
    _realtime_status()

    if st.button("🩺 Kiểm tra kết nối các nguồn"):
        with st.spinner("Đang kiểm tra..."):
            status = get_repo().get_provider_status()
        rows = []
        for name in ("dnse", "vnstock", "vietstock"):
            s = status.get(name, {})
            rows.append({"Nguồn": name, "Sẵn sàng": s.get("available"), "Phiên bản": s.get("version", ""),
                         "Lỗi gần nhất": s.get("last_error", ""), "Ghi chú": s.get("note", s.get("base_url", ""))})
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.markdown("#### Nguồn gốc dữ liệu của một mã")
    symbol = symbol_input("src_symbol")
    if symbol and st.button("Xem nguồn gốc"):
        svc = StockService(symbol, days=1095)
        px = svc.get_price_df()
        st.markdown("**Giá (3 năm)**")
        st.dataframe(pd.DataFrame(px.attrs.get("provenance", [])), width="stretch", hide_index=True)
        k = px.attrs.get("stitch_factor")
        if k:
            st.info(f"Đã nhân giá đoạn cũ với hệ số {k:.4f} để nối liền với dữ liệu DNSE (hai nguồn lệch nhau ở các phiên trùng).")
        fin = svc.get_financials("year")
        st.markdown("**BCTC năm – nhật ký thử nguồn**")
        st.dataframe(pd.DataFrame(fin.get("attempts", [])), width="stretch", hide_index=True)

    st.markdown("#### Nhật ký cập nhật tự động")
    log = Database().get_update_log()
    if log.empty:
        st.caption("Chưa có lần cập nhật dữ liệu nào được ghi lại.")
    else:
        st.dataframe(log, width="stretch", hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Số mục trong bộ nhớ đệm", cache.stats().get("size", 0))
    with c2:
        if st.button("🧹 Xóa bộ nhớ đệm"):
            cache.clear_all()
            st.success("Đã xóa – lần xem tiếp theo sẽ tải lại từ nguồn.")


def _realtime_status() -> None:
    """Trạng thái kết nối giá realtime DNSE – không hiển thị key/secret."""
    from datetime import datetime
    from core import nguon_du_lieu as rt
    s = rt.status()
    labels = {"off": "⚪ Chưa bật", "connecting": "🟡 Đang kết nối", "live": "🟢 Đang nhận giá realtime",
              "auth_failed": "🔴 Sai API key / secret", "error": "🟠 Mất kết nối – đang thử lại", "stopped": "⚪ Đã dừng"}
    st.markdown(f"**Trạng thái:** {labels.get(s.get('state'), s.get('state'))}")
    if s.get("state") == "off":
        st.caption(f"Lý do: {s.get('message')}. App đang dùng giá gần realtime (API biểu đồ công khai DNSE, "
                   f"~{settings.LIVE_REFRESH_SECONDS // 60} phút/lần). Để bật: thêm DNSE_API_KEY và DNSE_API_SECRET vào .env "
                   "(lấy tại Entrade X → Thông tin cá nhân → Light Speed) rồi chạy lại app.")
        return
    fmt = lambda t: datetime.fromtimestamp(t).strftime("%H:%M:%S %d/%m") if t else "–"  # noqa: E731
    st.caption(f"Kết nối lúc: {fmt(s.get('connected_at'))} · tin nhắn gần nhất: {fmt(s.get('last_message_at'))} · "
               f"đã nhận {s.get('messages', 0):,} tin · đang theo dõi {s.get('symbols_wanted', 0)} mã, "
               f"có giá {s.get('symbols_with_price', 0)} mã · làm mới trang mỗi {settings.REALTIME_REFRESH_SECONDS} giây")
    if s.get("message"):
        st.caption(f"Thông báo gần nhất: {s['message']}")
    if s.get("state") == "auth_failed":
        st.warning("DNSE từ chối API key / secret. Kiểm tra lại 2 dòng DNSE_API_KEY, DNSE_API_SECRET trong .env "
                   "(key Production, không phải Sandbox), rồi tắt và chạy lại app. Trong lúc đó app dùng giá ~3 phút/lần.")
