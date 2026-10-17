"""
giao_dien/doanh_nghiep.py – gộp từ 4 module (15/10/2026).

MỤC LỤC
  • pages/financial_statements.py – Trang – Báo cáo tài chính nhiều năm (chuẩn hóa từ nhiều nguồn) + tải Excel.
      hàm/lớp chính: render
  • pages/financial_ratios.py – Trang – Chỉ số tài chính tính trực tiếp từ BCTC: sinh lời, thanh khoản, đòn bẩy, hiệu quả,
      hàm/lớp chính: render_financial_ratios
  • pages/documents.py – Trang – Báo cáo thường niên & BCTC dạng PDF theo năm: dò tìm, tải về, tải lên, trích số liệu.
      hàm/lớp chính: render_documents
  • pages/company_news.py – Trang Tin Tức Doanh Nghiệp (Company News & Market Intelligence).
      hàm/lớp chính: render_company_news

Tên trùng giữa các phần đã được đổi (tên cũ → tên mới trong file này):
  financial_ratios.render → render_financial_ratios
  documents.render → render_documents
  company_news.render → render_company_news
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/financial_statements.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Trang – Báo cáo tài chính nhiều năm (chuẩn hóa từ nhiều nguồn) + tải Excel.
"""


from datetime import datetime

import pandas as pd
import streamlit as st

from core.phan_tich_co_ban import key_to_label
from giao_dien.chung import bar_chart, fmt_num, page_header, source_caption, symbol_input
from core.bao_cao_pdf import export_financials, statement_table
from core.pipeline import StockService

_TABS = [("is", "📊 Kết quả kinh doanh"), ("bs", "🏦 Cân đối kế toán"), ("cf", "💸 Lưu chuyển tiền tệ")]


def _display_table(data: pd.DataFrame, sources: pd.DataFrame, st_code: str) -> pd.DataFrame:
    t = statement_table(data, st_code, unit=1e9)
    if t.empty:
        return t
    t = t.set_index("Chỉ tiêu")
    return t.apply(lambda col: col.map(lambda v: fmt_num(v, 0)))


def render():
    page_header("📑 Báo Cáo Tài Chính Nhiều Năm",
                "Kết quả kinh doanh · Cân đối kế toán · Lưu chuyển tiền tệ theo năm hoặc theo quý")

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        symbol = symbol_input("fs_symbol")
    with c2:
        period = st.selectbox("Kỳ báo cáo", ["year", "quarter"], format_func=lambda p: "Năm" if p == "year" else "Quý")
    with c3:
        years = st.slider("Số năm", 3, 15, 8)
    with c4:
        st.write("")
        refresh = st.button("🔄 Làm mới", help="Bỏ qua bộ nhớ đệm, tải lại từ các nguồn")
    if not symbol:
        return

    with st.spinner(f"Đang tổng hợp BCTC {symbol} từ các nguồn..."):
        svc = StockService(symbol, fin_period=period, fin_years=years)
        if refresh:
            svc.repo.get_financials(symbol, period=period, years=years, force_refresh=True)
        fin = svc.get_financials(period, years)
    data, sources = fin.get("data", pd.DataFrame()), fin.get("sources", pd.DataFrame())

    if data is None or data.empty:
        st.error("Không lấy được BCTC. Xem trạng thái dữ liệu ở trang 🛰️ Nguồn dữ liệu, "
                 "hoặc tải BCTC dạng PDF ở trang 📚 Tài liệu để hệ thống tự trích số liệu.")
        return

    source_caption(f"{len(data)} kỳ ({key_to_label(data.index[0])} → {key_to_label(data.index[-1])}) · "
                   f"đơn vị: tỷ đồng (EPS: đồng/cp)")

    # Biểu đồ nhanh
    periods = [key_to_label(k) for k in data.index]
    g1, g2 = st.columns(2)
    with g1:
        series = {}
        for k, name in (("revenue", "Doanh thu thuần"), ("total_operating_income", "Tổng thu nhập HĐ"),
                        ("net_income_parent", "LNST cổ đông mẹ"), ("net_income", "LNST")):
            if k in data.columns and data[k].notna().any() and len(series) < 2:
                series[name] = (data[k] / 1e9).tolist()
        st.plotly_chart(bar_chart(periods, series, "Doanh thu & Lợi nhuận", "tỷ đồng"), width="stretch")
    with g2:
        series = {}
        for k, name in (("total_assets", "Tổng tài sản"), ("equity", "Vốn chủ sở hữu"), ("total_liabilities", "Nợ phải trả")):
            if k in data.columns and data[k].notna().any():
                series[name] = (data[k] / 1e9).tolist()
        st.plotly_chart(bar_chart(periods, series, "Cơ cấu tài sản – nguồn vốn", "tỷ đồng"), width="stretch")

    tabs = st.tabs([t[1] for t in _TABS])
    for (code, _), tab in zip(_TABS, tabs):
        with tab:
            t = _display_table(data, sources, code)
            if t.empty:
                st.info("Không có số liệu cho báo cáo này.")
            else:
                st.dataframe(t, width="stretch", height=min(700, 38 + 35 * len(t)))

    st.download_button(
        "⬇️ Tải Excel (BCTC + Chỉ số)",
        data=export_financials(symbol, fin, svc.financial_summary(period)),
        file_name=f"{symbol}_BCTC_{'nam' if period == 'year' else 'quy'}_{datetime.now():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/financial_ratios.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Trang – Chỉ số tài chính tính trực tiếp từ BCTC: sinh lời, thanh khoản, đòn bẩy, hiệu quả,
tăng trưởng, dòng tiền, định giá tại giá hiện tại, DuPont, Piotroski F-score, Altman Z''-score.
"""


import pandas as pd
import streamlit as st

from core.phan_tich_co_ban import RATIO_META, VALUATION_META
from core.phan_tich_co_ban import key_to_label
from giao_dien.chung import bar_chart, fmt_num, line_chart, page_header, source_caption, symbol_input
from core.pipeline import StockService


def _fmt(v, fmt):
    if fmt == "%":
        return fmt_num(v, 1, "%")
    if fmt == "x":
        return fmt_num(v, 2, "x")
    if fmt == "days":
        return fmt_num(v, 0)
    if fmt == "vnd":
        return fmt_num(v / 1e9, 0, " tỷ") if v is not None and pd.notna(v) and abs(v) > 1e7 else fmt_num(v, 0)
    return fmt_num(v, 2)


def render_financial_ratios():
    page_header("🧮 Chỉ Số Tài Chính", "Tính trực tiếp từ BCTC đã chuẩn hóa – không phụ thuộc bảng chỉ số dựng sẵn của nhà cung cấp")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        symbol = symbol_input("fr_symbol")
    with c2:
        period = st.selectbox("Kỳ", ["year", "quarter"], format_func=lambda p: "Năm" if p == "year" else "Quý (TTM)",
                              key="fr_period")
    with c3:
        years = st.slider("Số năm", 3, 15, 8, key="fr_years")
    if not symbol:
        return
    with st.spinner("Đang tính chỉ số..."):
        svc = StockService(symbol, fin_period=period, fin_years=years)
        summ = svc.financial_summary(period)
    ratios = summ.get("ratios", pd.DataFrame())
    if ratios is None or ratios.empty:
        st.error("Không đủ BCTC để tính chỉ số. Kiểm tra trang 📑 Báo cáo tài chính.")
        return
    if summ.get("is_bank"):
        st.info("🏦 Doanh nghiệp ngân hàng: một số chỉ số phi tài chính (biên gộp, vòng quay tồn kho, Z-score) không áp dụng.")

    # ── Định giá tại giá hiện tại ──
    val = summ.get("valuation") or {}
    st.markdown("#### 💰 Định giá tại giá hiện tại")
    cols = st.columns(6)
    for col, key in zip(cols, ["pe", "pb", "ps", "ev_ebitda", "dividend_yield", "earnings_yield"]):
        label, fmt = VALUATION_META[key]
        col.metric(label, _fmt(val.get(key), fmt))
    source_caption(f"Vốn hóa {fmt_num((val.get('market_cap') or 0) / 1e9, 0) if val.get('market_cap') else '–'} tỷ đ · "
                   f"Giá {fmt_num(val.get('price'), 0)} đ · EPS {fmt_num(val.get('eps_ttm'), 0)} đ · BVPS "
                   f"{fmt_num(val.get('bvps'), 0)} đ · BCTC kỳ {val.get('as_of_period') or '–'}"
                   + (" (TTM)" if period == "quarter" else ""))

    # ── Bảng chỉ số theo nhóm ──
    st.markdown("#### 📋 Bảng chỉ số theo kỳ")
    r = ratios.iloc[-(years if period == "year" else years * 4):]
    periods = [key_to_label(k) for k in r.index]
    groups = {}
    from core.phan_tich_co_ban import ratio_meta_for
    for key, (label, group, fmt, better) in ratio_meta_for(bool(summ.get("is_bank"))).items():
        if key in r.columns and r[key].notna().any():
            groups.setdefault(group, []).append((key, label, fmt))
    tabs = st.tabs(list(groups))
    for tab, (group, items) in zip(tabs, groups.items()):
        with tab:
            table = pd.DataFrame({label: [_fmt(v, fmt) for v in r[key].tolist()] for key, label, fmt in items},
                                 index=periods).T
            st.dataframe(table, width="stretch")
            plot_keys = [(k, l) for k, l, f in items if f in ("%", "x")][:4]
            if plot_keys:
                st.plotly_chart(line_chart(periods, {l: r[k].tolist() for k, l in plot_keys}, group),
                                width="stretch")

    # ── DuPont ──
    d = summ.get("dupont")
    if d is not None and not d.empty:
        st.markdown("#### 🔍 Phân tích DuPont (ROE = Biên LN ròng × Vòng quay tài sản × Đòn bẩy)")
        d = d.loc[d.index.isin(r.index)]
        dp = [key_to_label(k) for k in d.index]
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(line_chart(dp, {"ROE theo DuPont (%)": d["roe_dupont"].tolist(),
                                            "Biên LN ròng (%)": d["net_margin"].tolist()}, "ROE & biên lợi nhuận"),
                            width="stretch")
        with c2:
            st.plotly_chart(line_chart(dp, {"Vòng quay tài sản (x)": d["asset_turnover"].tolist(),
                                            "Đòn bẩy TTS/VCSH (x)": d["equity_multiplier"].tolist()}, "Hiệu quả & đòn bẩy"),
                            width="stretch")
        st.caption("DuPont dùng LNST toàn công ty và VCSH bình quân nên có thể chênh nhẹ so với ROE tính trên LNST cổ đông mẹ.")

    # ── Sức khỏe tài chính ──
    st.markdown("#### 🩺 Sức khỏe tài chính")
    c1, c2, c3 = st.columns(3)
    pio = summ.get("piotroski") or {}
    with c1:
        st.metric("Piotroski F-score", f"{pio['score']}/{pio['max']}" if pio.get("score") is not None else "N/A",
                  help="9 tiêu chí về lợi nhuận, đòn bẩy/thanh khoản và hiệu quả hoạt động (cần BCTC năm)")
        for chk in pio.get("checks", []):
            icon = "✅" if chk["pass"] else ("❌" if chk["pass"] is False else "➖")
            st.caption(f"{icon} {chk['name']}")
    alt = summ.get("altman") or {}
    with c2:
        st.metric("Altman Z''-score", fmt_num(alt.get("score"), 2), alt.get("zone") or alt.get("note"),
                  delta_color="off")
        st.caption("> 5,85 an toàn · 4,35–5,85 cảnh báo · < 4,35 nguy cơ (bản cho thị trường mới nổi)")
    with c3:
        cg = summ.get("cagr") or {}
        st.metric("CAGR doanh thu 3 năm", fmt_num(cg.get("revenue_3y"), 1, "%"))
        st.metric("CAGR LNST 5 năm", fmt_num(cg.get("net_income_5y"), 1, "%"))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/documents.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Trang – Báo cáo thường niên & BCTC dạng PDF theo năm: dò tìm, tải về, tải lên, trích số liệu.
"""


from pathlib import Path

import pandas as pd
import streamlit as st

from giao_dien.chung import fmt_num, page_header, symbol_input
from core.du_lieu import ITEMS_BY_KEY
from core.tai_lieu_bctc import DOC_TYPES, DocumentService, period_key_for
from core.pipeline import StockService


def render_documents():
    page_header("📚 Báo Cáo Thường Niên & BCTC (PDF)",
                "Dò tìm và tải báo cáo thường niên, BCTC dạng PDF theo năm · trích số liệu BCTC từ PDF theo mã số VAS")
    symbol = symbol_input("doc_symbol")
    if not symbol:
        return
    ds = DocumentService()

    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("🔎 Dò tìm tài liệu", type="primary", width="stretch"):
            with st.spinner("Đang dò tìm trên các nguồn..."):
                info = StockService(symbol).get_company_info()
                found = ds.discover(symbol, info)
            st.toast(f"Đã dò xong: {len(found)} tài liệu cho {symbol}")

    docs = ds.list_documents(symbol)
    if not docs.empty:
        cnt = docs["doc_type"].value_counts()
        parts = [f"**{int(cnt.get(k, 0))}** {DOC_TYPES[k]}" for k in ("annual_report", "fs_annual", "fs_semiannual", "fs_quarterly")]
        st.success(f"Kho tài liệu của {symbol}: **{len(docs)}** tài liệu – " + " · ".join(parts))
        if int(cnt.get("annual_report", 0)) == 0:
            st.info("Chưa tìm thấy Báo cáo thường niên cho mã này trên các nguồn tự động. Bấm **Dò tìm tài liệu** "
                    "để dò lại.")
    tab_list, tab_extract = st.tabs(["📂 Danh sách tài liệu", "🧾 Trích số liệu từ PDF"])

    with tab_list:
        if docs.empty:
            st.info("Chưa có tài liệu. Bấm “Dò tìm tài liệu” để tìm trên các nguồn tự động.")
        else:
            types = st.multiselect("Loại tài liệu", list(DOC_TYPES), default=["annual_report", "fs_annual"],
                                   format_func=DOC_TYPES.get)
            years = sorted({int(y) for y in docs["year"].dropna()}, reverse=True)
            view = docs[docs["doc_type"].isin(types)] if types else docs
            st.caption(f"Đang hiển thị {len(view)} / {len(docs)} tài liệu theo bộ lọc.")
            if view.empty:
                st.warning("Không có tài liệu nào thuộc loại đã chọn. Hãy chọn thêm loại khác hoặc dò tìm lại.")
            for y in years + [None]:
                sub = view[view["year"] == y] if y is not None else view[view["year"].isna()]
                if sub.empty:
                    continue
                st.markdown(f"**{y if y else 'Không rõ năm'}**")
                for _, d in sub.iterrows():
                    a, b, c = st.columns([5, 2, 2])
                    a.markdown(f"{d['doc_type_label']} · {d['title'] or ''}")
                    if d["url"] and str(d["url"]).startswith("zenodo://"):
                        from core.tai_lieu_bctc import RECORD_URL
                        b.link_button("🌐 Kho Zenodo", RECORD_URL, width="stretch",
                                      help="File nằm trong kho ZIP trên Zenodo – bấm “Lưu về máy chủ” để rút đúng file này")
                    elif d["url"]:
                        b.link_button("🌐 Mở link gốc", d["url"], width="stretch")
                    if d["downloaded"]:
                        path = Path(d["local_path"])
                        c.download_button("⬇️ Tải file", path.read_bytes(), file_name=path.name,
                                          key=f"dl_{d['doc_id']}", width="stretch")
                    elif d["url"] and c.button("💾 Lưu về máy chủ", key=f"save_{d['doc_id']}", width="stretch"):
                        with st.spinner("Đang tải..."):
                            p = ds.download(d.to_dict())
                        st.success("Đã lưu.") if p else st.error("Không tải được file từ nguồn.")
                        st.rerun()

    with tab_extract:
        fs_docs = docs[docs["doc_type"].str.startswith("fs_") & docs["downloaded"]] if not docs.empty else docs
        if fs_docs.empty:
            st.info("Cần ít nhất một file BCTC (PDF) đã lưu về máy chủ.")
            return
        pick = st.selectbox("Chọn BCTC", fs_docs["doc_id"].tolist(),
                            format_func=lambda i: f"{fs_docs.set_index('doc_id').loc[i, 'doc_type_label']} "
                                                  f"{fs_docs.set_index('doc_id').loc[i, 'year']} – "
                                                  f"{fs_docs.set_index('doc_id').loc[i, 'title']}")
        if st.button("Trích số liệu", type="primary"):
            doc = fs_docs.set_index("doc_id").loc[pick].to_dict()
            doc["doc_id"] = pick
            bar = st.progress(0.0, text="Đang đọc PDF...")

            def _prog(i, n):
                bar.progress(i / n, text=f"PDF scan – đang nhận dạng chữ (OCR) trang {i}/{n}...")
            with st.spinner("Đang đọc PDF..."):
                res = ds.extract(doc, progress=_prog)
            bar.empty()
            if res.get("bank"):
                st.info("🏦 Nhận diện BCTC ngân hàng (mẫu tổ chức tín dụng, không có cột mã số) – trích theo tên chỉ tiêu.")
            if not res.get("values"):
                st.warning(res.get("note") or "Không trích được số liệu (PDF có thể là bản scan hoặc khác mẫu VAS).")
                return
            chk = res.get("checks", {})
            via = " · đọc bằng OCR (bản scan) – nên đối chiếu lại với file gốc" if res.get("method") == "ocr" else ""
            st.success(f"Trích được {len(res['values'])} chỉ tiêu{via} · đơn vị gốc ×{fmt_num(res['unit'], 0)} · "
                       f"kiểm tra cân đối: {'✅ khớp' if chk.get('balance_identity') else '⚠️ chưa khớp / thiếu'}")
            rows = [{"Chỉ tiêu": ITEMS_BY_KEY[k].label_vi if k in ITEMS_BY_KEY else k,
                     "Giá trị (tỷ đồng)": fmt_num(v / 1e9, 1) if k != "eps" else fmt_num(v, 0) + " đ/cp"}
                    for k, v in res["values"].items()]
            # Đối chiếu với số liệu từ nguồn trực tuyến
            pk = period_key_for(doc)
            online = StockService(symbol).get_financials("year" if doc["doc_type"] == "fs_annual" else "quarter")
            data = online.get("data", pd.DataFrame())
            if pk and data is not None and not data.empty and pk in data.index:
                for row, (k, v) in zip(rows, res["values"].items()):
                    ov = data.loc[pk].get(k)
                    if ov is not None and pd.notna(ov) and k != "eps":
                        row["Dữ liệu hệ thống (tỷ)"] = fmt_num(ov / 1e9, 1)
                        row["Chênh lệch %"] = fmt_num((v - ov) / abs(ov) * 100, 2, "%") if ov else "–"
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/company_news.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Trang Tin Tức Doanh Nghiệp (Company News & Market Intelligence).
Giao diện đồng bộ chuẩn xác theo thiết kế Stock Analytics.
"""


from datetime import datetime
import streamlit as st

from giao_dien.chung import safe_external_url, safe_html
from core.tin_tuc import CompanyNewsService

news_service = CompanyNewsService()
SENTIMENTS = {"positive": "🟢 Tích cực", "neutral": "⚪ Trung tính", "negative": "🔴 Tiêu cực"}


def _theme() -> dict:
    """Màu chữ theo giao diện: nền tối → chữ sáng, tương phản cao (dễ đọc khi trình chiếu)."""
    if st.session_state.get("theme", "light") == "dark":
        return dict(head="#ffffff", text="#f0f6fc", sub="#d0d7de", muted="#b1bac4", link="#79c0ff",
                    line="rgba(255,255,255,0.14)", line2="rgba(255,255,255,0.08)",
                    pos=("#4ade80", "rgba(34,197,94,0.18)"), neg=("#fb7185", "rgba(244,63,94,0.18)"),
                    neu=("#e2e8f0", "rgba(148,163,184,0.22)"))
    return dict(head="#0b1220", text="#0f172a", sub="#1e293b", muted="#334155", link="#0369a1",
                line="rgba(15,23,42,0.16)", line2="rgba(15,23,42,0.08)",
                pos=("#15803d", "#dcfce7"), neg=("#b91c1c", "#fee2e2"), neu=("#334155", "#e2e8f0"))



def render_company_news():
    curr_sym = st.session_state.get("current_symbol", "PNJ").strip().upper()

    T = _theme()
    try:
        from core.du_lieu import get_ticker_label
        label = get_ticker_label(curr_sym)
    except Exception:
        label = curr_sym
    st.markdown(f"""
    <div style="margin-bottom: 10px;">
        <div style="font-size: 24px; font-weight: 800; color: {T['head']};">📰 Tin Tức Doanh Nghiệp</div>
        <div style="font-size: 16px; color: {T['sub']}; margin-top: 2px;">{label} · tin mới nhất, phân loại sắc thái
        Tích cực / Trung tính / Tiêu cực</div>
    </div>
    """, unsafe_allow_html=True)
    col_left, col_right = st.columns([1.1, 1.0])

    # Lấy tin tức (có hỗ trợ force refresh)
    force_refresh = st.session_state.get(f"force_refresh_news_{curr_sym}", False)
    if force_refresh:
        st.session_state[f"force_refresh_news_{curr_sym}"] = False

    news_data = news_service.get_company_news(curr_sym, force_refresh=force_refresh)
    all_articles = news_data.get("news", [])
    available_sources = news_data.get("sources", ["CafeF", "VnExpress", "Thanh Niên", "Vietstock", "Tin Nhanh Chứng Khoán"])
    if not available_sources:
        available_sources = ["CafeF", "VnExpress", "Thanh Niên", "Vietstock"]

    # Đảm bảo nguồn mặc định đẹp mắt như trong ảnh
    default_sources = [s for s in ["CafeF", "VnExpress", "Thanh Niên"] if s in available_sources]
    if not default_sources:
        default_sources = available_sources[:3]

    with col_right:
        st.markdown(f"<p style='font-size: 16px; font-weight: 700; color: {T['head']}; margin-bottom: 4px;'>Chọn nguồn báo</p>", unsafe_allow_html=True)
        selected_sources = st.multiselect(
            "Chọn nguồn báo",
            options=available_sources,
            default=default_sources,
            key=f"news_sources_select_{curr_sym}",
            label_visibility="collapsed",
        )

        c_space, c_btn = st.columns([1, 2])
        with c_btn:
            if st.button("🔄 Làm mới tin tức", key=f"btn_refresh_news_{curr_sym}", width="stretch"):
                st.session_state[f"force_refresh_news_{curr_sym}"] = True
                st.rerun()

    # Lọc danh sách bài viết theo nguồn đã chọn
    if selected_sources:
        filtered_articles = [a for a in all_articles if a.get("source") in selected_sources]
    else:
        filtered_articles = all_articles

    # Lọc theo sắc thái bài báo (Tích cực / Trung tính / Tiêu cực)
    def _sent(a):
        v = a.get("sentiment", "neutral")
        return v if v in SENTIMENTS else "neutral"
    counts = {k: sum(1 for a in filtered_articles if _sent(a) == k) for k in SENTIMENTS}
    with col_left:
        st.markdown(f"<p style='font-size: 16px; font-weight: 700; color: {T['head']}; margin-bottom: 4px;'>"
                    f"Lọc theo sắc thái bài báo</p>", unsafe_allow_html=True)
        picked = st.pills(
            "Lọc theo sắc thái bài báo", options=list(SENTIMENTS), selection_mode="multi",
            default=list(SENTIMENTS), key=f"news_sentiment_{curr_sym}", label_visibility="collapsed",
            format_func=lambda k: f"{SENTIMENTS[k]} ({counts[k]})",
        ) or []
        st.caption("Bấm để bật/tắt từng loại; bỏ chọn hết = xem tất cả.")
    if picked:
        filtered_articles = [a for a in filtered_articles if _sent(a) in picked]

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    group = st.toggle("Gộp tin trùng chủ đề", value=True, key=f"news_group_{curr_sym}",
                      help="Nhiều báo đưa cùng một sự kiện → chỉ hiện 1 bài đại diện, ghi số bài cùng chủ đề.")
    if group and filtered_articles:
        from core.tin_tuc import cluster_news
        filtered_articles = [{**c["items"][0], "_dup": c["n"] - 1} for c in cluster_news(filtered_articles)]

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # ── Feed Header ──
    count_found = len(filtered_articles)
    st.markdown(f"""
    <div style="font-size: 15.5px; color: {T['sub']}; margin-bottom: 16px; border-bottom: 1px solid {T['line']}; padding-bottom: 8px;">
        <b>{count_found} bài liên quan tìm thấy</b> • Sắp xếp theo thời gian đăng (mới nhất trước)
    </div>
    """, unsafe_allow_html=True)

    # ── News Feed Items (Render theo đúng format mẫu ảnh) ──
    if not filtered_articles:
        st.info(f"Không có bài viết nào cho mã {curr_sym} với nguồn báo và sắc thái đã chọn. Hãy chọn thêm nguồn báo hoặc loại tin khác.")
        return

    for item in filtered_articles:
        title = safe_html(item.get("title", ""))
        source = safe_html(item.get("source", "Báo chí"))
        date_str = safe_html(item.get("date", datetime.now().strftime("%d/%m/%Y %H:%M")))
        url = safe_external_url(item.get("url"))
        summary = safe_html(item.get("summary") or "")
        sentiment = item.get("sentiment", "neutral")

        # Màu sắc tag cảm xúc (theo giao diện sáng / tối)
        if sentiment == "positive":
            (tag_color, tag_bg), tag_text = T["pos"], "Tích cực"
        elif sentiment == "negative":
            (tag_color, tag_bg), tag_text = T["neg"], "Tiêu cực"
        else:
            (tag_color, tag_bg), tag_text = T["neu"], "Trung tính"

        dup = (f'<span style="font-size:13px;color:{T["muted"]};">· +{item["_dup"]} bài cùng chủ đề</span>'
               if item.get("_dup") else "")
        summ = (f'<div style="font-size:15.5px;color:{T["sub"]};margin-top:6px;line-height:1.6;">{summary[:260]}...</div>'
                if len(summary) > 20 else "")
        # Dựng HTML trên MỘT dòng: trước đây chuỗi nhiều dòng thụt lề + dòng trống (khi không có "_dup") làm Markdown kết
        # thúc khối HTML sớm → phần tóm tắt phía sau hiện thành khối code "</div><div style=...".
        st.markdown(
            f'<div style="margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid {T["line2"]};">'
            f'<div style="margin-bottom:4px;"><a href="{url}" target="_blank" rel="noopener noreferrer" '
            f'style="color:{T["link"]};font-size:18px;font-weight:700;text-decoration:none;line-height:1.45;">{title}</a></div>'
            f'<div style="font-size:14.5px;color:{T["muted"]};font-weight:500;display:flex;align-items:center;gap:8px;'
            f'flex-wrap:wrap;margin-top:4px;"><span>{source}</span><span>•</span><span>{date_str}</span><span>•</span>'
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="color:{T["link"]};text-decoration:none;'
            f'font-weight:600;">Mở bài gốc ↗</a>'
            f'<b style="margin-left:6px;padding:2px 9px;background:{tag_bg};color:{tag_color};border-radius:6px;'
            f'font-size:13.5px;font-weight:700;">{tag_text}</b>{dup}</div>{summ}</div>',
            unsafe_allow_html=True)
