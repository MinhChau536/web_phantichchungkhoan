"""
giao_dien/chung.py – gộp từ 11 module (15/10/2026).

MỤC LỤC
  • assets/styles/main_style.py – Global CSS for Stock Analytics (Light and Dark themes with interactive hover micro-animations).
      hàm/lớp chính: load_css
  • assets/styles.py – Global CSS styles and loader for Stock Analytics.
  • components/contrast.py – Màu chữ tương phản cho các ô / nhãn có nền màu (14/10/2026).
      hàm/lớp chính: contrast_ratio, text_on, on_bg
  • components/charts.py – Plotly chart factory for Stock Analytics.
      hàm/lớp chính: candlestick_chart, rsi_chart, macd_chart, bollinger_chart, financial_bar_chart, portfolio_pie, line_comparison_chart, score_gauge
  • components/ui.py – Tiện ích giao diện dùng chung cho các trang mới.
      hàm/lớp chính: safe_html, safe_external_url, page_header, symbol_input, fmt_num, fmt_bil, bar_chart, line_chart, source_caption, unique_columns, as_of_picker
  • components/metrics.py – Reusable Streamlit UI components / widgets.
      hàm/lớp chính: metric_card, score_badge, data_status_badge, warning_box, info_box, error_box, section_header, render_score_breakdown, render_signal_row, pct_color, format_vnd, render_company_header
  • components/logo.py – Logo doanh nghiệp theo mã cổ phiếu.
      hàm/lớp chính: logo_path, badge_color, logo_html
  • components/background_fx.py – Hiệu ứng nền động cho toàn bộ app:
      hàm/lớp chính: inject_background
  • components/price_chart.py – Biểu đồ giá tương tác "tất cả trong một" cho trang 🔍 Phân Tích Cổ Phiếu.
      hàm/lớp chính: build_figure, render, render_cached
  • components/sidebar_nav.py – Thanh bên trái kiểu "VN Stock Pro" (15/10/2026): nền xanh lá đậm (màu chứng khoán) cố định (không phụ thuộc chế độ Sáng/Tối của nội dung),
      hàm/lớp chính: nav_groups, all_pages, render_nav
  • pages/hub.py – Trang gộp (14/10/2026) – mỗi trang gộp có thanh chọn ngang ở đầu trang; CHỈ phần đang chọn được chạy.
      hàm/lớp chính: resolve_legacy, render_financials, render_screen_compare, render_portfolio
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: assets/styles/main_style.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Global CSS for Stock Analytics (Light and Dark themes with interactive hover micro-animations).
"""

COMMON_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* ── Khung st.iframe 1px chỉ để chạy mã (hiệu ứng nền) → ẩn hẳn, không chiếm chỗ ── */
div[data-testid="stElementContainer"][height="1px"]:has(> iframe[data-testid="stIFrame"]) {
    display: none !important;
}

/* ── Hide default Streamlit navigation on sidebar top-left ── */
[data-testid="stSidebarNav"],
ul[data-testid="stSidebarNavItems"],
div[data-testid="stSidebarNavSeparator"] {
    display: none !important;
    height: 0px !important;
    visibility: hidden !important;
    margin: 0 !important;
    padding: 0 !important;
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

[data-testid="stMetricDelta"] svg { display: none; }

::-webkit-scrollbar { width: 7px; height: 7px; }
"""

LIGHT_CSS = COMMON_CSS + """
/* ==============================================================================
   LIGHT THEME (Sáng: Nền sáng tinh khôi, chữ tối đậm nét, độ tương phản cao)
   ============================================================================== */
.stApp {
    background: #f8fafc !important;
    color: #0f172a !important;
}

/* ── Streamlit Header / Top Bar Light ── */
header,
header[data-testid="stHeader"],
[data-testid="stAppHeader"],
.stAppHeader {
    background: #f8fafc !important;
    background-color: #f8fafc !important;
    border-bottom: 1px solid #e2e8f0 !important;
}
[data-testid="stToolbar"],
[data-testid="stHeaderActionElements"],
[data-testid="stStatusWidget"] {
    background: transparent !important;
}
[data-testid="stToolbar"] *,
header * {
    color: #475569 !important;
    fill: #475569 !important;
}
[data-testid="stDecoration"] {
    display: none !important;
}

/* ── Typography Light: Chữ tối nổi bật ── */
h1, h2, h3, h4, h5, h6 {
    color: #0f172a !important;
    font-weight: 800 !important;
    letter-spacing: -0.3px;
}
p, span, label {
    color: #334155 !important;
}

/* ── Metric Cards Light (Chữ tối đậm, hover nổi bật) ── */
[data-testid="stMetric"] {
    background: transparent !important;
    border: 1px solid rgba(15, 23, 42, 0.16) !important;
    border-radius: 14px !important;
    padding: 14px 18px !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05) !important;
    transition: all 0.28s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
    cursor: pointer;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-5px) scale(1.015) !important;
    border-color: #0284c7 !important;
    box-shadow: 0 12px 28px -6px rgba(2, 132, 199, 0.22), 0 0 0 1.5px #0284c7 !important;
}
[data-testid="stMetricValue"] {
    color: #0f172a !important;
    font-weight: 800 !important;
    font-size: 30px !important;
    line-height: 1.2 !important;
}
[data-testid="stMetricLabel"] {
    color: #1e293b !important;
    font-weight: 700 !important;
    font-size: 15px !important;
}

/* ── Sidebar (15/10/2026: luôn nền tối ở cả chế độ Sáng – giao_dien/chung.py) ── */
[data-testid="stSidebar"] {
    background: #0b3b2c !important;
    border-right: 1px solid #1d6149 !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #ffffff !important;
}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
    color: #c9d1d9 !important;
}

/* ── Cards Light ── */
.metric-card {
    background: transparent !important;
    border: 1px solid rgba(15, 23, 42, 0.16) !important;
    border-radius: 14px !important;
    padding: 16px 20px !important;
    margin-bottom: 14px !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05) !important;
    transition: all 0.28s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
}
.metric-card:hover {
    transform: translateY(-4px) !important;
    border-color: #0284c7 !important;
    box-shadow: 0 12px 28px -6px rgba(2, 132, 199, 0.2) !important;
}

/* ── Page Header Light ── */
.page-header {
    background: transparent !important;
    border-radius: 14px !important;
    padding: 20px 24px !important;
    border: 1px solid rgba(15, 23, 42, 0.16) !important;
    margin-bottom: 20px !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04) !important;
    transition: all 0.28s ease !important;
}
.page-header:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(2, 132, 199, 0.12) !important;
    border-color: #bae6fd !important;
}
.page-header h1 {
    color: #0f172a !important;
}
.page-header p {
    color: #475569 !important;
}

/* ── Buttons Light (Hover effect) ── */
.stButton > button {
    background: linear-gradient(135deg, #0284c7, #2563eb) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 9px 22px !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
    box-shadow: 0 2px 8px rgba(2, 132, 199, 0.25) !important;
}
.stButton > button:hover {
    transform: translateY(-2px) scale(1.02) !important;
    box-shadow: 0 8px 20px rgba(2, 132, 199, 0.4) !important;
    filter: brightness(1.08) !important;
}
.stButton > button:active {
    transform: translateY(0px) scale(0.98) !important;
}

/* ── Inputs & Selects Light ── */
.stTextInput input, .stSelectbox select, div[data-baseweb="select"] {
    background: transparent !important;
    border: 1px solid #94a3b8 !important;
    color: #0f172a !important;
    border-radius: 10px !important;
    transition: all 0.2s ease !important;
}
.stTextInput input:hover, div[data-baseweb="select"]:hover {
    border-color: #0284c7 !important;
    box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.12) !important;
}
.stTextInput input:focus {
    border-color: #0284c7 !important;
    box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.2) !important;
}

/* ── Tabs Light ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border: 1px solid rgba(15, 23, 42, 0.14) !important;
    border-radius: 10px !important;
    padding: 5px !important;
    gap: 6px !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 8px !important;
    color: #475569 !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #0284c7 !important;
    transform: translateY(-1px) !important;
}
.stTabs [aria-selected="true"] {
    background: #0284c7 !important;
    color: #ffffff !important;
    box-shadow: 0 2px 6px rgba(2, 132, 199, 0.3) !important;
}

/* ── DataFrames Light ── */
.stDataFrame {
    border: 1px solid rgba(15, 23, 42, 0.16) !important;
    border-radius: 10px !important;
    background: transparent !important;
    transition: all 0.25s ease !important;
}
.stDataFrame:hover {
    border-color: #0284c7 !important;
    box-shadow: 0 6px 18px rgba(2, 132, 199, 0.1) !important;
}
[data-testid="stDataFrame"] thead tr th {
    background: transparent !important;
    color: #0b1220 !important;
    font-weight: 700 !important;
}

/* ── Bảng / khung TRONG SUỐT trên nền động + chữ nổi bật (giao diện sáng) ── */
/* Bảng st.dataframe vẽ bằng canvas: hòa trộn "multiply" làm nền trắng của ô trở nên trong suốt, chữ tối giữ nguyên */
[data-testid="stDataFrame"] canvas, [data-testid="stDataFrameResizable"] canvas { mix-blend-mode: multiply; }
[data-testid="stDataFrame"] > div, [data-testid="stDataFrameResizable"] { background: transparent !important; }
[data-testid="stTable"] table, [data-testid="stTable"] th, [data-testid="stTable"] td,
[data-testid="stMarkdownContainer"] table, [data-testid="stMarkdownContainer"] th, [data-testid="stMarkdownContainer"] td {
    background: transparent !important; color: #0b1220 !important; border-color: rgba(15, 23, 42, 0.14) !important;
}
[data-testid="stExpander"] details, [data-testid="stExpander"] summary, [data-testid="stExpanderDetails"],
[data-testid="stForm"], [data-testid="stVerticalBlockBorderWrapper"], [data-testid="stFileUploaderDropzone"],
div[data-baseweb="input"], div[data-baseweb="base-input"], div[data-baseweb="textarea"], div[data-baseweb="select"] > div,
[data-testid="stNumberInput"] input, [data-testid="stNumberInput"] button, [data-testid="stDateInput"] input,
.stTextArea textarea, [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    background: transparent !important; background-color: transparent !important;
}
[data-testid="stExpander"] details { border-color: rgba(15, 23, 42, 0.16) !important; }
/* viền sáng nhẹ quanh chữ TỐI (tiêu đề, nhãn ô nhập, số liệu, chú thích, bảng) để nổi trên nền động –
   không áp cho chữ trắng trên nền màu (nhãn khuyến nghị, nút…) */
[data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3, [data-testid="stMain"] h4,
[data-testid="stMain"] [data-testid="stWidgetLabel"], [data-testid="stMetricValue"], [data-testid="stMetricLabel"],
[data-testid="stMain"] [data-testid="stCaptionContainer"], [data-testid="stMain"] .page-header p,
[data-testid="stMain"] [data-testid="stMarkdownContainer"] td, [data-testid="stMain"] [data-testid="stMarkdownContainer"] th,
[data-testid="stMain"] [data-testid="stMarkdownContainer"] > p, [data-testid="stMain"] [data-testid="stMarkdownContainer"] li,
[data-testid="stMain"] [data-testid="stExpander"] summary {
    text-shadow: 0 0 2px rgba(255, 255, 255, 0.9), 0 0 6px rgba(255, 255, 255, 0.55);
}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] span[style*="background"], [data-testid="stMain"] [style*="color: rgb(255, 255, 255)"],
[data-testid="stMain"] [data-testid="stMarkdownContainer"] div[style*="background"] * { text-shadow: none !important; }
/* chữ trắng viết trực tiếp trong HTML (nhãn khuyến nghị, thẻ màu) giữ màu trắng */
[data-testid="stMain"] [style*="color:#fff"], [data-testid="stMain"] [style*="color: #fff"],
[data-testid="stMain"] [style*="color:#ffffff"], [data-testid="stMain"] [style*="color: #ffffff"],
[data-testid="stMain"] [style*="color:#fff"] *, [data-testid="stMain"] [style*="color: #fff"] *,
[data-testid="stMain"] [style*="color: rgb(255, 255, 255)"], [data-testid="stMain"] [style*="color: rgb(255, 255, 255)"] * { color: #ffffff !important; }
[data-testid="stMain"] p, [data-testid="stMain"] li, [data-testid="stMain"] label { color: #1e293b !important; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: #334155 !important; }
/* chữ trắng trên nền màu (nút, nhãn, tab đang chọn) không cần viền sáng */
[data-testid="stMain"] button, [data-testid="stMain"] button *, .mo-badge, .rc-chip, .rc-badge, .rc-badge *,
[data-testid="stMain"] [aria-selected="true"], [data-testid="stMain"] [aria-selected="true"] *,
[data-testid="stMain"] [aria-checked="true"], [data-testid="stMain"] [aria-checked="true"] * { text-shadow: none !important; }
/* nút phụ (màu trắng) và ô chọn → trong suốt có viền */
[data-testid="stMain"] button[data-testid="stBaseButton-secondary"], [data-testid="stMain"] button[kind="secondary"] {
    background: transparent !important; border: 1px solid rgba(15, 23, 42, 0.28) !important; color: #0b1220 !important;
    box-shadow: none !important;
}
[data-testid="stMain"] button[data-testid="stBaseButton-secondary"] p, [data-testid="stMain"] button[kind="secondary"] p { color: #0b1220 !important; font-weight: 700 !important; }
[data-testid="stMain"] [data-baseweb="input"], [data-testid="stMain"] [data-baseweb="input"] *,
[data-testid="stMain"] [data-baseweb="select"], [data-testid="stMain"] [data-baseweb="select"] *,
[data-testid="stMain"] [data-baseweb="textarea"], [data-testid="stMain"] [data-baseweb="textarea"] *,
[data-testid="stMain"] [data-testid="stTextInput"] div, [data-testid="stMain"] [data-testid="stSelectbox"] div,
[data-testid="stMain"] [data-testid="stNumberInput"] div, [data-testid="stMain"] [data-testid="stDateInput"] div,
[data-testid="stMain"] [data-testid="stTextArea"] div, [data-testid="stMain"] [data-testid="stMultiSelect"] div {
    background: transparent !important; background-color: transparent !important;
}
[data-testid="stMain"] [data-testid="stTextInput"] input, [data-testid="stMain"] [data-testid="stNumberInput"] input,
[data-testid="stMain"] [data-testid="stDateInput"] input { color: #0b1220 !important; font-weight: 600 !important; }
[data-testid="stMain"] [data-baseweb="input"], [data-testid="stMain"] [data-baseweb="select"] > div,
[data-testid="stMain"] [data-baseweb="textarea"] { border: 1px solid #94a3b8 !important; border-radius: 10px !important; }
[data-testid="stMain"] [data-baseweb="input"] input, [data-testid="stMain"] [data-baseweb="select"] div[value],
[data-testid="stMain"] [data-baseweb="select"] span { color: #0b1220 !important; font-weight: 600 !important; }
div[data-baseweb="select"] > div, div[data-baseweb="select"] > div > div { background: transparent !important; background-color: transparent !important; }
div[data-baseweb="select"] { border-color: #94a3b8 !important; }

/* ── Radio buttons hover in Sidebar ── */
div[role="radiogroup"] label {
    transition: all 0.2s ease !important;
}
div[role="radiogroup"] label:hover {
    transform: translateX(3px) !important;
}

/* ── Numbers & Status Colors Light ── */
.positive { color: #15803d !important; font-weight: 700 !important; }
.negative { color: #dc2626 !important; font-weight: 700 !important; }
.status-ok { color: #15803d !important; font-weight: 700 !important; }
.status-error { color: #dc2626 !important; font-weight: 700 !important; }
.status-warning { color: #d97706 !important; font-weight: 700 !important; }

::-webkit-scrollbar-track { background: #f8fafc; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #0284c7; }

/* ── DỄ ĐỌC KHI TRÌNH CHIẾU (giao diện sáng): chữ đậm hơn, to hơn, không mờ ── */
[data-testid="stCaptionContainer"] { opacity: 1 !important; }
[data-testid="stMain"] [data-testid="stCaptionContainer"], [data-testid="stMain"] [data-testid="stCaptionContainer"] p,
[data-testid="stMain"] [data-testid="stCaptionContainer"] li {
    color: #0f172a !important; font-size: 16px !important; font-weight: 500 !important; line-height: 1.6 !important;
}
[data-testid="stMain"] [data-testid="stCaptionContainer"] strong, [data-testid="stMain"] [data-testid="stCaptionContainer"] b { font-weight: 800 !important; }
[data-testid="stMain"] [data-testid="stWidgetLabel"], [data-testid="stMain"] [data-testid="stWidgetLabel"] p {
    color: #0b1220 !important; font-size: 16.5px !important; font-weight: 700 !important;
}
[data-testid="stMain"] [role="radiogroup"] label p, [data-testid="stMain"] [data-testid="stCheckbox"] label p {
    color: #0b1220 !important; font-size: 16px !important; font-weight: 600 !important;
}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] > p, [data-testid="stMain"] [data-testid="stMarkdownContainer"] li {
    font-size: 16.5px !important; color: #0b1220 !important;
}
[data-testid="stMain"] [data-testid="stExpander"] summary p { font-size: 16.5px !important; font-weight: 700 !important; color: #0b1220 !important; }
[data-testid="stMain"] [role="tablist"] { gap: 6px !important; border-bottom: 2px solid rgba(15, 23, 42, 0.18) !important; }
[data-testid="stMain"] [role="tab"] { padding: 8px 14px !important; border-radius: 8px 8px 0 0 !important; }
[data-testid="stMain"] [role="tab"] p { font-size: 17px !important; font-weight: 700 !important; color: #0f172a !important; }
[data-testid="stMain"] [role="tab"]:hover p { color: #0369a1 !important; }
[data-testid="stMain"] [role="tab"][aria-selected="true"] { background: #0369a1 !important; }
[data-testid="stMain"] [role="tab"][aria-selected="true"] p { color: #ffffff !important; }
[data-testid="stMain"] [data-testid="stMetricLabel"] p { font-size: 16px !important; font-weight: 700 !important; color: #1e293b !important; }
[data-testid="stMain"] .mo-kpi small, [data-testid="stMain"] .rc-row small, [data-testid="stMain"] .mo-sub {
    color: #1e293b !important; font-size: 14.5px !important; font-weight: 500 !important;
}
[data-testid="stMain"] .rc-row { font-size: 15.5px !important; color: #0b1220 !important; font-weight: 600 !important; }
[data-testid="stMain"] .mo-kpi b { color: #0b1220 !important; }
[data-testid="stMain"] .mo-sec h3, [data-testid="stMain"] .mo-sec h3 * { font-size: 19px !important; font-weight: 800 !important; color: #0b1220 !important; }
[data-testid="stMain"] .mo-sec > span { font-size: 15px !important; font-weight: 500 !important; color: #1e293b !important; }
[data-testid="stMain"] .mo-sub { font-size: 16px !important; }
[data-testid="stMain"] .mo-kpi b { font-size: 22px !important; }
[data-testid="stMain"] .rc-badge .s { font-size: 15px !important; }
</style>
"""

DARK_CSS = COMMON_CSS + """
/* ==============================================================================
   DARK THEME (Tối: Nền tối sang trọng, chữ sáng trắng nổi bật, tương phản cao)
   ============================================================================== */
.stApp {
    background: #0d1117 !important;
    color: #f0f6fc !important;
}

/* ── Streamlit Header / Top Bar Dark ── */
header,
header[data-testid="stHeader"],
[data-testid="stAppHeader"],
.stAppHeader {
    background: #0d1117 !important;
    background-color: #0d1117 !important;
    border-bottom: 1px solid #21262d !important;
}
[data-testid="stToolbar"],
[data-testid="stHeaderActionElements"],
[data-testid="stStatusWidget"] {
    background: transparent !important;
}
[data-testid="stToolbar"] *,
header * {
    color: #e6edf3 !important;
    fill: #e6edf3 !important;
}
[data-testid="stDecoration"] {
    display: none !important;
}

/* ── Typography Dark: Chữ sáng nổi bật ── */
h1, h2, h3, h4, h5, h6 {
    color: #ffffff !important;
    font-weight: 800 !important;
    letter-spacing: -0.3px;
}
p, span, label {
    color: #dde3ea !important;
}

/* ── Metric Cards Dark (Chữ sáng rực, hover nổi bật) ── */
[data-testid="stMetric"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 14px !important;
    padding: 14px 18px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3) !important;
    transition: all 0.28s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
    cursor: pointer;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-5px) scale(1.015) !important;
    border-color: #58a6ff !important;
    box-shadow: 0 12px 28px -6px rgba(88, 166, 255, 0.32), 0 0 0 1.5px #58a6ff !important;
}
[data-testid="stMetricValue"] {
    color: #ffffff !important;
    font-weight: 800 !important;
    font-size: 30px !important;
    line-height: 1.2 !important;
    text-shadow: 0 2px 6px rgba(0, 0, 0, 0.5);
}
[data-testid="stMetricLabel"] {
    color: #f0f6fc !important;
    font-weight: 700 !important;
    font-size: 15px !important;
}

/* ── Sidebar Dark ── */
[data-testid="stSidebar"] {
    background: #0b3b2c !important;
    border-right: 1px solid #1d6149 !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #ffffff !important;
}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
    color: #c9d1d9 !important;
}

/* ── Cards Dark ── */
.metric-card {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 14px !important;
    padding: 16px 20px !important;
    margin-bottom: 14px !important;
    transition: all 0.28s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
}
.metric-card:hover {
    transform: translateY(-4px) !important;
    border-color: #58a6ff !important;
    box-shadow: 0 12px 28px -6px rgba(88, 166, 255, 0.25) !important;
}

/* ── Page Header Dark ── */
.page-header {
    background: linear-gradient(135deg, #161b22, #1c2128) !important;
    border-radius: 14px !important;
    padding: 20px 24px !important;
    border: 1px solid #30363d !important;
    margin-bottom: 20px !important;
    transition: all 0.28s ease !important;
}
.page-header:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(88, 166, 255, 0.15) !important;
    border-color: #58a6ff !important;
}
.page-header h1 {
    color: #ffffff !important;
}
.page-header p {
    color: #8b949e !important;
}

/* ── Buttons Dark (Hover effect) ── */
.stButton > button {
    background: linear-gradient(135deg, #1f6feb, #238636) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 9px 22px !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
    box-shadow: 0 2px 8px rgba(31, 111, 235, 0.3) !important;
}
.stButton > button:hover {
    transform: translateY(-2px) scale(1.02) !important;
    box-shadow: 0 8px 22px rgba(88, 166, 255, 0.45) !important;
    filter: brightness(1.12) !important;
}
.stButton > button:active {
    transform: translateY(0px) scale(0.98) !important;
}

/* ── Inputs & Selects Dark ── */
.stTextInput input, .stSelectbox select, div[data-baseweb="select"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    color: #ffffff !important;
    border-radius: 10px !important;
    transition: all 0.2s ease !important;
}
.stTextInput input:hover, div[data-baseweb="select"]:hover {
    border-color: #58a6ff !important;
    box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.2) !important;
}
.stTextInput input:focus {
    border-color: #58a6ff !important;
    box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.3) !important;
}

/* ── Tabs Dark ── */
.stTabs [data-baseweb="tab-list"] {
    background: #161b22 !important;
    border-radius: 10px !important;
    padding: 5px !important;
    gap: 6px !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 8px !important;
    color: #8b949e !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #58a6ff !important;
    transform: translateY(-1px) !important;
}
.stTabs [aria-selected="true"] {
    background: #1f6feb !important;
    color: #ffffff !important;
    box-shadow: 0 2px 6px rgba(31, 111, 235, 0.4) !important;
}

/* ── DataFrames Dark ── */
.stDataFrame {
    border: 1px solid #30363d !important;
    border-radius: 10px !important;
    background: #161b22 !important;
    transition: all 0.25s ease !important;
}
.stDataFrame:hover {
    border-color: #58a6ff !important;
    box-shadow: 0 6px 18px rgba(88, 166, 255, 0.15) !important;
}
[data-testid="stDataFrame"] thead tr th {
    background: #21262d !important;
    color: #ffffff !important;
    font-weight: 700 !important;
}
[data-testid="stMain"] [data-testid="stSelectbox"] div, [data-testid="stMain"] [data-testid="stMultiSelect"] div,
[data-testid="stMain"] [data-testid="stDateInput"] div, [data-testid="stMain"] [data-testid="stNumberInput"] div {
    background-color: #161b22 !important;
}
[data-testid="stMain"] [data-testid="stSelectbox"] *, [data-testid="stMain"] [data-testid="stMultiSelect"] input,
[data-testid="stMain"] [data-testid="stDateInput"] input, [data-testid="stMain"] [data-testid="stNumberInput"] input { color: #f0f6fc !important; }
/* st.dataframe vẽ bằng canvas theo giao diện sáng của Streamlit → đảo màu để thành nền tối, chữ sáng */
[data-testid="stDataFrame"] canvas, [data-testid="stDataFrameResizable"] canvas { filter: invert(0.9) hue-rotate(180deg); }

/* ── Radio buttons hover in Sidebar ── */
div[role="radiogroup"] label {
    transition: all 0.2s ease !important;
}
div[role="radiogroup"] label:hover {
    transform: translateX(3px) !important;
}

/* ── Numbers & Status Colors Dark ── */
.positive { color: #00e676 !important; font-weight: 700 !important; }
.negative { color: #ff5252 !important; font-weight: 700 !important; }
.status-ok { color: #00e676 !important; font-weight: 700 !important; }
.status-error { color: #ff5252 !important; font-weight: 700 !important; }
.status-warning { color: #ffd740 !important; font-weight: 700 !important; }

::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #58a6ff; }

/* ── DỄ ĐỌC KHI TRÌNH CHIẾU (giao diện tối): chữ sáng hơn, to hơn, không mờ ── */
[data-testid="stCaptionContainer"] { opacity: 1 !important; }
[data-testid="stMain"] [data-testid="stCaptionContainer"], [data-testid="stMain"] [data-testid="stCaptionContainer"] p,
[data-testid="stMain"] [data-testid="stCaptionContainer"] li {
    color: #e6edf3 !important; font-size: 16px !important; font-weight: 500 !important; line-height: 1.6 !important;
}
[data-testid="stMain"] [data-testid="stCaptionContainer"] strong, [data-testid="stMain"] [data-testid="stCaptionContainer"] b { font-weight: 800 !important; color: #ffffff !important; }
[data-testid="stMain"] [data-testid="stWidgetLabel"], [data-testid="stMain"] [data-testid="stWidgetLabel"] p {
    color: #ffffff !important; font-size: 16.5px !important; font-weight: 700 !important;
}
[data-testid="stMain"] [role="radiogroup"] label p, [data-testid="stMain"] [data-testid="stCheckbox"] label p {
    color: #f0f6fc !important; font-size: 16px !important; font-weight: 600 !important;
}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] > p, [data-testid="stMain"] [data-testid="stMarkdownContainer"] li {
    font-size: 16.5px !important; color: #f0f6fc !important;
}
[data-testid="stMain"] [data-testid="stExpander"] summary p { font-size: 16.5px !important; font-weight: 700 !important; color: #ffffff !important; }
[data-testid="stMain"] [role="tablist"] { gap: 6px !important; border-bottom: 2px solid #30363d !important; }
[data-testid="stMain"] [role="tab"] { padding: 8px 14px !important; border-radius: 8px 8px 0 0 !important; }
[data-testid="stMain"] [role="tab"] p { font-size: 17px !important; font-weight: 700 !important; color: #e6edf3 !important; }
[data-testid="stMain"] [role="tab"]:hover p { color: #79c0ff !important; }
[data-testid="stMain"] [role="tab"][aria-selected="true"] { background: #1f6feb !important; }
[data-testid="stMain"] [role="tab"][aria-selected="true"] p { color: #ffffff !important; }
[data-testid="stMain"] [data-testid="stMetricLabel"] p { font-size: 16px !important; font-weight: 700 !important; color: #e6edf3 !important; }
[data-testid="stMain"] .mo-kpi small, [data-testid="stMain"] .rc-row small, [data-testid="stMain"] .mo-sub {
    color: #c9d1d9 !important; font-size: 14.5px !important; font-weight: 500 !important;
}
[data-testid="stMain"] .rc-row { font-size: 15.5px !important; color: #f0f6fc !important; font-weight: 600 !important; }
[data-testid="stMain"] .mo-sec h3, [data-testid="stMain"] .mo-sec h3 * { font-size: 19px !important; font-weight: 800 !important; color: #ffffff !important; }
[data-testid="stMain"] .mo-sec > span { font-size: 15px !important; font-weight: 500 !important; color: #c9d1d9 !important; }
[data-testid="stMain"] .mo-sub { font-size: 16px !important; }
[data-testid="stMain"] .mo-kpi b { font-size: 22px !important; }
[data-testid="stMain"] .rc-badge .s { font-size: 15px !important; }
</style>
"""


def load_css(theme: str = "light") -> str:
    """Return CSS styling corresponding to active theme."""
    if theme == "dark":
        return DARK_CSS
    return LIGHT_CSS


# Backward compatibility alias
CSS = LIGHT_CSS


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: assets/styles.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Global CSS styles and loader for Stock Analytics.
"""


__all__ = ["load_css", "CSS", "LIGHT_CSS", "DARK_CSS"]


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: components/contrast.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Màu chữ tương phản cho các ô / nhãn có nền màu (14/10/2026).

Vấn đề: CSS chung của app (giao_dien/chung.py) ép màu chữ tối cho p/li/span trong vùng nội dung → nhãn nền
đậm (xám, xanh dương, đỏ…) có chữ tối bị "chìm". Cách sửa: chọn màu chữ theo ĐỘ SÁNG của nền (WCAG relative
luminance) – nền sáng → chữ tối, nền tối → chữ trắng – và ghi THẲNG vào thẻ với !important (inline !important thắng
mọi luật !important trong stylesheet).
"""


DARK = "#0f172a"
LIGHT = "#ffffff"


def _rgb(color: str):
    c = (color or "").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) == 8:            # #rrggbbaa → bỏ alpha
        c = c[:6]
    if len(c) != 6:
        return None
    try:
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _lum(rgb) -> float:
    def ch(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    ra, rb = _rgb(a), _rgb(b)
    if ra is None or rb is None:
        return 1.0
    la, lb = sorted((_lum(ra), _lum(rb)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def text_on(bg: str) -> str:
    """Màu chữ (tối/trắng) có độ tương phản cao hơn trên nền bg. Không đọc được màu → chữ trắng."""
    if _rgb(bg) is None:
        return LIGHT
    return DARK if contrast_ratio(bg, DARK) > contrast_ratio(bg, LIGHT) else LIGHT


def on_bg(bg: str) -> str:
    """Chuỗi style inline: nền + màu chữ tương phản (kèm !important để không bị CSS chung đè)."""
    fg = text_on(bg)
    return f"background:{bg};color:{fg} !important;-webkit-text-fill-color:{fg}"


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: components/charts.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Plotly chart factory for Stock Analytics.

All charts use the dark Plotly template.
No random data – all inputs must come from real DataFrames.
"""


from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.cau_hinh import COLOR_BEARISH, COLOR_BULLISH, COLOR_NEUTRAL, PLOTLY_TEMPLATE

import streamlit as st

# ─────────────────── Module-level fallback color tokens ──────────────────────
_BG = "#ffffff"
_CARD = "#ffffff"
_GRID = "#f1f5f9"
_TEXT = "#0f172a"
_AXIS = "#64748b"

# ─────────────────── Dynamic Base layout ─────────────────────────────────────
def _get_theme_colors() -> dict:
    try:
        theme = st.session_state.get("theme", "light")
    except Exception:
        theme = "light"

    if theme == "dark":
        return {
            "template": "plotly_dark",
            "bg": "#0d1117",
            "card": "#161b22",
            "grid": "#30363d",
            "text": "#e6edf3",
            "axis": "#8b949e",
            "legend_bg": "rgba(22,27,34,0.8)",
        }
    return {
        "template": "plotly_white",
        "bg": "rgba(0,0,0,0)",            # trong suốt: thấy nền động phía sau
        "card": "rgba(0,0,0,0)",
        "grid": "rgba(15,23,42,0.10)",
        "text": "#0b1220",
        "axis": "#334155",
        "legend_bg": "rgba(0,0,0,0)",
        "hover_bg": "#ffffff",
    }


def _base_layout(**kwargs) -> dict:
    colors = _get_theme_colors()
    layout = {
        "template": colors["template"],
        "paper_bgcolor": colors["bg"],
        "plot_bgcolor": colors["card"],
        "font": {"color": colors["text"], "family": "Inter, Roboto, sans-serif", "size": 12},
        "margin": {"l": 60, "r": 20, "t": 50, "b": 40},
        "xaxis": {"gridcolor": colors["grid"], "zerolinecolor": colors["grid"], "tickfont": {"color": colors["axis"]}},
        "yaxis": {"gridcolor": colors["grid"], "zerolinecolor": colors["grid"], "tickfont": {"color": colors["axis"]}},
        "legend": {"bgcolor": colors["legend_bg"], "bordercolor": colors["grid"], "borderwidth": 1},
        "hoverlabel": {"bgcolor": colors.get("hover_bg", colors["card"]), "bordercolor": colors["grid"], "font_color": colors["text"]},
    }
    layout.update(kwargs)
    return layout


# ─────────────────── Candlestick Chart ────────────────────────────────────────

def candlestick_chart(
    df: pd.DataFrame,
    symbol: str = "",
    show_volume: bool = True,
    ma_cols: Optional[List[str]] = None,
    height: int = 600,
) -> go.Figure:
    """
    Full candlestick chart with optional MA overlays and volume.

    Parameters
    ----------
    df       : DataFrame with columns: timestamp/index, open, high, low, close, volume
    symbol   : Title prefix
    show_volume : Attach volume subplot
    ma_cols  : List of MA column names in df to overlay, e.g. ['SMA_20', 'SMA_50']
    """
    if df.empty:
        return _empty_chart("Không có dữ liệu giá")

    # Prepare x-axis
    x_col = "timestamp" if "timestamp" in df.columns else df.index

    row_heights = [0.7, 0.3] if show_volume else [1.0]
    rows = 2 if show_volume else 1
    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True,
        row_heights=row_heights,
        vertical_spacing=0.03,
    )

    # ── Candlestick ──
    fig.add_trace(
        go.Candlestick(
            x=df[x_col] if isinstance(x_col, str) else x_col,
            open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name=symbol,
            increasing_line_color=COLOR_BULLISH, decreasing_line_color=COLOR_BEARISH,
            increasing_fillcolor=COLOR_BULLISH, decreasing_fillcolor=COLOR_BEARISH,
        ),
        row=1, col=1,
    )

    # ── MA overlays ──
    ma_colors = {
        "SMA_10": "#ffffff", "SMA_20": "#2979ff", "SMA_50": "#ff9800",
        "SMA_100": "#e91e63", "SMA_200": "#9c27b0",
        "EMA_12": "#00bcd4", "EMA_26": "#ff5722",
    }
    if ma_cols:
        for col in ma_cols:
            if col in df.columns:
                color = ma_colors.get(col, "#aaaaaa")
                fig.add_trace(
                    go.Scatter(
                        x=df[x_col] if isinstance(x_col, str) else x_col,
                        y=df[col],
                        name=col,
                        line={"color": color, "width": 1.2},
                        hovertemplate=f"{col}: %{{y:,.0f}}<extra></extra>",
                    ),
                    row=1, col=1,
                )

    # ── Volume ──
    if show_volume and "volume" in df.columns:
        colors = [
            COLOR_BULLISH if (c >= o) else COLOR_BEARISH
            for c, o in zip(df["close"].fillna(0), df["open"].fillna(0))
        ]
        fig.add_trace(
            go.Bar(
                x=df[x_col] if isinstance(x_col, str) else x_col,
                y=df["volume"],
                name="Khối lượng",
                marker_color=colors,
                opacity=0.7,
                hovertemplate="KL: %{y:,.0f}<extra></extra>",
            ),
            row=2, col=1,
        )

    layout = _base_layout(
        title={"text": f"📈 Biểu đồ nến – {symbol}", "font_size": 14},
        height=height,
        xaxis_rangeslider_visible=False,
    )
    fig.update_layout(**layout)
    fig.update_yaxes(tickformat=",.0f", row=1, col=1)
    if show_volume:
        fig.update_yaxes(tickformat=",.0f", row=2, col=1, title_text="Khối lượng")
    return fig


# ─────────────────── RSI Chart ────────────────────────────────────────────────

def rsi_chart(df: pd.DataFrame, height: int = 250) -> go.Figure:
    if df.empty or "RSI" not in df.columns:
        return _empty_chart("Chưa tính RSI")
    x = df.get("timestamp", df.index)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=df["RSI"], name="RSI",
        line={"color": "#f06292", "width": 1.5},
        hovertemplate="RSI: %{y:.1f}<extra></extra>",
    ))
    for level, color, dash in [(70, COLOR_BEARISH, "dash"), (50, _AXIS, "dot"), (30, COLOR_BULLISH, "dash")]:
        fig.add_hline(y=level, line_dash=dash, line_color=color, opacity=0.6)
    fig.update_layout(**_base_layout(title_text="RSI (14)", height=height))
    fig.update_yaxes(range=[0, 100])
    return fig


# ─────────────────── MACD Chart ──────────────────────────────────────────────

def macd_chart(df: pd.DataFrame, height: int = 250) -> go.Figure:
    if df.empty or "MACD" not in df.columns:
        return _empty_chart("Chưa tính MACD")
    x = df.get("timestamp", df.index)
    fig = go.Figure()

    if "MACD_hist" in df.columns:
        hist = df["MACD_hist"].fillna(0)
        colors = [COLOR_BULLISH if v >= 0 else COLOR_BEARISH for v in hist]
        fig.add_trace(go.Bar(x=x, y=hist, name="Histogram",
                             marker_color=colors, opacity=0.8))

    fig.add_trace(go.Scatter(x=x, y=df["MACD"], name="MACD",
                             line={"color": "#2979ff", "width": 1.5}))
    if "MACD_signal" in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df["MACD_signal"], name="Signal",
                                 line={"color": "#ff9800", "width": 1.5, "dash": "dash"}))
    fig.add_hline(y=0, line_color=_AXIS, line_dash="dot", opacity=0.5)
    fig.update_layout(**_base_layout(title_text="MACD (12,26,9)", height=height))
    return fig


# ─────────────────── Bollinger Bands ─────────────────────────────────────────

def bollinger_chart(df: pd.DataFrame, symbol: str = "", height: int = 350) -> go.Figure:
    required = ["close", "BB_upper", "BB_mid", "BB_lower"]
    if df.empty or not all(c in df.columns for c in required):
        return _empty_chart("Chưa tính Bollinger Bands")
    x = df.get("timestamp", df.index)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=df["BB_upper"], name="Upper", line={"color": "#90caf9", "width": 1, "dash": "dot"}))
    fig.add_trace(go.Scatter(x=x, y=df["BB_lower"], name="Lower", line={"color": "#90caf9", "width": 1, "dash": "dot"},
                             fill="tonexty", fillcolor="rgba(41,121,255,0.08)"))
    fig.add_trace(go.Scatter(x=x, y=df["BB_mid"], name="Mid", line={"color": "#2979ff", "width": 1}))
    fig.add_trace(go.Scatter(x=x, y=df["close"], name="Giá", line={"color": COLOR_BULLISH, "width": 1.5}))
    fig.update_layout(**_base_layout(title_text=f"Bollinger Bands – {symbol}", height=height))
    return fig


# ─────────────────── Financial Bar Chart ─────────────────────────────────────

def financial_bar_chart(
    series: pd.Series, title: str = "", unit: str = "Tỷ VND",
    color: str = COLOR_BULLISH, height: int = 300
) -> go.Figure:
    if series is None or series.empty:
        return _empty_chart("Không có dữ liệu tài chính")
    fig = go.Figure(go.Bar(
        x=list(range(len(series))),
        y=series.values / 1e9,
        marker_color=[COLOR_BULLISH if v >= 0 else COLOR_BEARISH for v in series.values],
        hovertemplate=f"%{{y:,.1f}} {unit}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(title_text=title, height=height))
    fig.update_yaxes(title_text=unit)
    return fig


# ─────────────────── Portfolio Pie ────────────────────────────────────────────

def portfolio_pie(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty_chart("Danh mục trống")
    fig = go.Figure(go.Pie(
        labels=df["symbol"], values=df["current_value"],
        hole=0.4,
        textinfo="label+percent",
        hovertemplate="%{label}: %{value:,.0f} VND<extra></extra>",
    ))
    fig.update_layout(**_base_layout(title_text="Phân bổ danh mục"))
    return fig


# ─────────────────── Line comparison chart ───────────────────────────────────

def line_comparison_chart(
    series_dict: Dict[str, pd.Series],
    title: str = "",
    height: int = 400,
    pct_normalize: bool = True,
) -> go.Figure:
    """Plot multiple series, optionally normalised to 100 at start."""
    if not series_dict:
        return _empty_chart("Không có dữ liệu")
    colors = ["#2979ff", "#00e676", "#ff9800", "#e91e63", "#9c27b0"]
    fig = go.Figure()
    for i, (name, s) in enumerate(series_dict.items()):
        if s is None or s.empty:
            continue
        y = s / s.iloc[0] * 100 if pct_normalize else s
        fig.add_trace(go.Scatter(
            x=s.index, y=y, name=name,
            line={"color": colors[i % len(colors)], "width": 1.8},
            hovertemplate=f"{name}: %{{y:.1f}}<extra></extra>",
        ))
    if pct_normalize:
        fig.add_hline(y=100, line_color=_get_theme_colors()["axis"], line_dash="dot", opacity=0.4)
    fig.update_layout(**_base_layout(title_text=title, height=height))
    return fig


# ─────────────────── Score gauge ─────────────────────────────────────────────

def score_gauge(score: Optional[float], title: str = "Score", height: int = 250) -> go.Figure:
    if score is None:
        return _empty_chart("Chưa có điểm")
    if score >= 80:
        color = COLOR_BULLISH
    elif score >= 65:
        color = "#69f0ae"
    elif score >= 50:
        color = "#ffd740"
    elif score >= 35:
        color = "#ff8f00"
    else:
        color = COLOR_BEARISH

    c = _get_theme_colors()

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": title, "font": {"color": c["text"], "size": 14}},
        number={"font": {"color": color, "size": 36}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": c["axis"]},
            "bar": {"color": color},
            "bgcolor": c["card"],
            "borderwidth": 1,
            "bordercolor": c["grid"],
            "steps": [
                {"range": [0, 35], "color": "rgba(255,23,68,0.15)"},
                {"range": [35, 50], "color": "rgba(255,143,0,0.15)"},
                {"range": [50, 65], "color": "rgba(255,215,64,0.15)"},
                {"range": [65, 80], "color": "rgba(105,240,174,0.15)"},
                {"range": [80, 100], "color": "rgba(0,230,118,0.2)"},
            ],
        },
    ))
    fig.update_layout(
        paper_bgcolor=c["bg"], font={"color": c["text"], "family": "Inter, sans-serif"},
        height=height, margin={"t": 30, "b": 10, "l": 30, "r": 30},
    )
    return fig


# ─────────────────── Backtest equity curve ───────────────────────────────────

def _empty_chart(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message, showarrow=False,
        x=0.5, y=0.5, xref="paper", yref="paper",
        font={"size": 14, "color": _AXIS},
    )
    fig.update_layout(**_base_layout(height=300))
    return fig


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: components/ui.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Tiện ích giao diện dùng chung cho các trang mới."""


import html
from urllib.parse import urlparse
from typing import Dict, Iterable, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st



PALETTE = ["#2563eb", "#16a34a", "#ea580c", "#9333ea", "#0891b2", "#dc2626"]


def safe_html(value: object) -> str:
    """Escape dữ liệu động trước khi đưa vào st.markdown(unsafe_allow_html=True)."""
    return html.escape("" if value is None else str(value), quote=True)


def safe_external_url(value: object, fallback: str = "#") -> str:
    """Chỉ cho liên kết web tuyệt đối; loại javascript:, data: và URL tương đối."""
    raw = "" if value is None else str(value).strip()
    try:
        parsed = urlparse(raw)
    except ValueError:
        return fallback
    return safe_html(raw) if parsed.scheme.lower() in {"http", "https"} and parsed.netloc else fallback


def page_header(title: str, subtitle: str = ""):
    is_light = st.session_state.get("theme", "light") == "light"
    st.markdown(f"""
    <div class="page-header">
        <h1 style="font-size:22px;font-weight:800;color:{'#0f172a' if is_light else '#e6edf3'};margin:0">{safe_html(title)}</h1>
        <p style="font-size:14px;color:{'#475569' if is_light else '#8b949e'};margin:4px 0 0 0">{safe_html(subtitle)}</p>
    </div>
    """, unsafe_allow_html=True)


def symbol_input(key: str, label: str = "Mã cổ phiếu") -> str:
    """Ô nhập mã đồng bộ với mã đang chọn ở thanh bên."""
    sym = st.text_input(label, value=st.session_state.get("current_symbol", "FPT"), key=key).upper().strip()
    if sym and sym != st.session_state.get("current_symbol"):
        st.session_state["current_symbol"] = sym
    return sym


def fmt_num(v, d: int = 0, suffix: str = "") -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "–"
    try:
        return f"{float(v):,.{d}f}{suffix}"
    except (TypeError, ValueError):
        return str(v)


def fmt_bil(v) -> str:
    return fmt_num(v / 1e9 if v is not None and pd.notna(v) else None, 0)


def bar_chart(x: List, series: Dict[str, Iterable], title: str = "", unit: str = "", height: int = 320,
              barmode: str = "group") -> go.Figure:
    if not x:
        return _empty_chart("Không có dữ liệu")
    fig = go.Figure()
    for i, (name, ys) in enumerate(series.items()):
        fig.add_trace(go.Bar(x=x, y=list(ys), name=name, marker_color=PALETTE[i % len(PALETTE)],
                             hovertemplate=f"{name}: %{{y:,.2f}} {unit}<extra></extra>"))
    fig.update_layout(**_base_layout(title_text=title, height=height, barmode=barmode))
    if unit:
        fig.update_yaxes(title_text=unit)
    return fig


def line_chart(x: List, series: Dict[str, Iterable], title: str = "", unit: str = "", height: int = 320) -> go.Figure:
    if not x:
        return _empty_chart("Không có dữ liệu")
    fig = go.Figure()
    for i, (name, ys) in enumerate(series.items()):
        fig.add_trace(go.Scatter(x=x, y=list(ys), name=name, mode="lines+markers",
                                 line={"color": PALETTE[i % len(PALETTE)], "width": 2},
                                 hovertemplate=f"{name}: %{{y:,.2f}} {unit}<extra></extra>"))
    fig.update_layout(**_base_layout(title_text=title, height=height))
    if unit:
        fig.update_yaxes(title_text=unit)
    return fig


def source_caption(text: str):
    st.caption(f"ℹ️ {text}")


def unique_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Đổi tên cột trùng (vd '2018', '2018' → '2018', '2018 (2)') để Streamlit/Excel hiển thị được."""
    if df is None or df.empty or not df.columns.duplicated().any():
        return df
    seen: Dict[str, int] = {}
    cols = []
    for c in map(str, df.columns):
        seen[c] = seen.get(c, 0) + 1
        cols.append(c if seen[c] == 1 else f"{c} ({seen[c]})")
    out = df.copy()
    out.columns = cols
    return out


def as_of_picker(key: str, help_text: str = "") -> "str | None":
    """Chọn thời điểm định giá: giá hiện tại (None) hoặc giá đóng cửa tại một ngày → 'YYYY-MM-DD'."""
    import datetime as _dt
    mode = st.radio("Giá dùng để định giá", ["Giá hiện tại", "Giá tại ngày"], horizontal=True, key=f"{key}_mode",
                    help=help_text or "Giá tại ngày: lấy giá đóng cửa phiên gần nhất ≤ ngày chọn và chỉ dùng BCTC đã công bố "
                                      "trước ngày đó (BCTC năm tính từ 1/4 năm sau, BCTC quý 45 ngày sau khi hết quý). "
                                      "Dùng để chốt số liệu cho bài nộp/thuyết trình.")
    if mode == "Giá hiện tại":
        return None
    today = _dt.date.today()
    d = st.date_input("Ngày định giá", value=today - _dt.timedelta(days=1), min_value=today - _dt.timedelta(days=365 * 6),
                      max_value=today - _dt.timedelta(days=1), format="DD/MM/YYYY", key=f"{key}_date")
    if (today - d).days > 30:
        st.caption("ℹ️ Ngày cũ hơn 30 ngày: không dùng trung vị ngành (chỉ có số liệu hiện tại) để tránh dùng thông tin tương lai.")
    return d.isoformat()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: components/metrics.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Reusable Streamlit UI components / widgets.
"""


from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from core.cau_hinh import COLOR_BEARISH, COLOR_BULLISH, COLOR_NEUTRAL


def metric_card(label: str, value: str, delta: Optional[str] = None,
                delta_color: str = "normal", icon: str = ""):
    """Styled metric card using st.metric with icon prefix."""
    display_label = f"{icon} {label}" if icon else label
    st.metric(label=display_label, value=value, delta=delta, delta_color=delta_color)


def score_badge(score: Optional[float], label: str = "") -> str:
    """Return HTML badge string for a score."""
    try:
        is_light = st.session_state.get("theme", "light") == "light"
    except Exception:
        is_light = True

    if score is None:
        bg = "#f1f5f9" if is_light else "#30363d"
        fg = "#64748b" if is_light else "#8b949e"
        return f'<span style="background:{bg};color:{fg};padding:3px 10px;border-radius:12px;font-size:14px">N/A</span>'
    
    if is_light:
        if score >= 80:
            bg, fg = "#dcfce7", "#15803d"
        elif score >= 65:
            bg, fg = "#ecfdf5", "#16a34a"
        elif score >= 50:
            bg, fg = "#fef9c3", "#854d0e"
        elif score >= 35:
            bg, fg = "#ffedd5", "#c2410c"
        else:
            bg, fg = "#fee2e2", "#b91c1c"
    else:
        if score >= 80:
            bg, fg = "#1a472a", "#00e676"
        elif score >= 65:
            bg, fg = "#0d3321", "#69f0ae"
        elif score >= 50:
            bg, fg = "#3d2c00", "#ffd740"
        elif score >= 35:
            bg, fg = "#3d1a00", "#ff8f00"
        else:
            bg, fg = "#3d0014", "#ff1744"

    return (
        f'<span style="background:{bg};color:{fg};padding:4px 12px;'
        f'border-radius:12px;font-size:15px;font-weight:600">'
        f'{score:.0f} – {label}</span>'
    )


def data_status_badge(source: str, timestamp: str, color: str = "#0284c7") -> None:
    """Display data source and freshness."""
    try:
        is_light = st.session_state.get("theme", "light") == "light"
    except Exception:
        is_light = True
    txt_color = "#64748b" if is_light else "#8b949e"
    st.markdown(
        f'<div style="font-size:12px;color:{txt_color};margin-bottom:6px">'
        f'📡 Nguồn: <b style="color:{color}">{source}</b> &nbsp;|&nbsp; '
        f'⏱ Cập nhật: <b>{timestamp}</b></div>',
        unsafe_allow_html=True,
    )


def warning_box(message: str):
    """Display a styled warning."""
    st.warning(f"⚠️ {message}")


def info_box(message: str):
    st.info(f"ℹ️ {message}")


def error_box(message: str):
    st.error(f"❌ {message}")


def section_header(title: str, subtitle: str = ""):
    """Render a styled section header."""
    try:
        is_light = st.session_state.get("theme", "light") == "light"
    except Exception:
        is_light = True
    title_color = "#0f172a" if is_light else "#e6edf3"
    sub_color = "#475569" if is_light else "#8b949e"
    accent = "#0284c7" if is_light else "#2979ff"
    sub = f"<br><span style='font-size:13px;color:{sub_color}'>{subtitle}</span>" if subtitle else ""
    st.markdown(f'<div style="border-left:3px solid {accent};padding-left:12px;margin:16px 0 8px 0">'
                f'<span style="font-size:19px;font-weight:700;color:{title_color}">{title}</span>{sub}</div>',
                unsafe_allow_html=True)


def render_score_breakdown(components: Dict[str, Any]):
    """Render score component table."""
    rows = []
    for group, data in components.items():
        score = data.get("score")
        max_pts = data.get("max", 100)
        status = data.get("status", "ok")
        reason = data.get("reason", "")
        row = {
            "Nhóm": group.replace("_", " ").title(),
            "Điểm": f"{score:.0f} / {max_pts}" if score is not None else "N/A",
            "Trạng thái": "✅" if status == "ok" else "⚠️ Thiếu dữ liệu",
            "Ghi chú": reason,
        }
        rows.append(row)
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_signal_row(signals: Dict[str, Any]):
    """Render signal indicators in a row."""
    cols = st.columns(len(signals))
    for i, (name, data) in enumerate(signals.items()):
        if not isinstance(data, dict):
            continue
        signal = data.get("signal", data.get("name", "N/A"))
        color = data.get("color", COLOR_NEUTRAL)
        with cols[i]:
            st.markdown(
                f'<div style="background:#161b22;border-radius:8px;padding:10px;text-align:center">'
                f'<div style="font-size:12px;color:#8b949e">{name.upper()}</div>'
                f'<div style="font-size:14px;font-weight:600;color:{color}">{signal}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def pct_color(val: Optional[float]) -> str:
    """Return colored string for a percentage change."""
    if val is None:
        return "N/A"
    color = COLOR_BULLISH if val >= 0 else COLOR_BEARISH
    sign = "+" if val >= 0 else ""
    return f'<span style="color:{color}">{sign}{val:.2f}%</span>'


def format_vnd(val: Optional[float], unit: str = "tỷ") -> str:
    """Format VND value with unit."""
    if val is None or pd.isna(val):
        return "N/A"
    if unit == "tỷ":
        return f"{val / 1e9:,.1f} tỷ"
    if unit == "triệu":
        return f"{val / 1e6:,.1f} triệu"
    return f"{val:,.0f}"


def render_company_header(info: Dict[str, Any], current_price: Optional[Dict] = None):
    """Render company name, exchange, sector and price."""
    symbol = info.get("symbol", "")
    name = info.get("company_name", info.get("short_name", info.get("name", symbol)))
    exchange = info.get("exchange", "")
    sector = info.get("sector", "")

    price_str = "N/A"
    change_str = ""
    if current_price and current_price.get("price"):
        p = current_price["price"]
        p_vnd = p * 1000 if (0 < p < 1000) else p
        price_str = f"{p_vnd:,.0f}"
        chg = current_price.get("change")
        chg_pct = current_price.get("change_pct")
        if chg is not None and chg_pct is not None:
            chg_vnd = chg * 1000 if (0 < abs(chg) < 1000 and 0 < p < 1000) else chg
            color = COLOR_BULLISH if chg >= 0 else COLOR_BEARISH
            sign = "+" if chg >= 0 else ""
            change_str = f'<span style="color:{color};font-size:17px"> {sign}{chg_vnd:,.0f} ({sign}{chg_pct:.2f}%)</span>'

    st.markdown(f"""
    <div style="background:#161b22;border-radius:12px;padding:20px 24px;margin-bottom:16px">
        <div style="font-size:26px;font-weight:800;color:#e6edf3">
            {symbol}
            <span style="font-size:15px;background:#21262d;color:#8b949e;padding:3px 10px;border-radius:8px;margin-left:10px">{exchange}</span>
        </div>
        <div style="font-size:16px;color:#8b949e;margin-top:4px">{name}</div>
        <div style="font-size:13px;color:#58a6ff;margin-top:2px">{sector}</div>
        <div style="font-size:30px;font-weight:700;color:#e6edf3;margin-top:12px">
            {price_str} VND{change_str}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: components/logo.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Logo doanh nghiệp theo mã cổ phiếu.

• Nguồn: ảnh logo công khai của các trang chứng khoán (vnstock không trả logo). Thứ tự thử theo LOGO_URL_TEMPLATES trong
  .env (mỗi mẫu có {symbol}); mặc định thử vài nguồn quen thuộc.
• Tải MỘT lần rồi lưu thành PNG trong data/logos/<MÃ>.png (thu nhỏ ≤ 160px). Chỉ nhận dữ liệu là ảnh thật (mở được bằng
  Pillow), ≤ 1 MB – trang lỗi/HTML bị loại.
• Không tìm được → ghi dấu data/logos/<MÃ>.none, 3 ngày sau mới thử lại (không làm chậm trang mỗi lần mở).
• Giao diện dùng logo_html(): có logo → ảnh; không có → huy hiệu chữ (ô tròn màu có mã) để không bao giờ trống/ảnh lỗi.
"""


import base64
import hashlib
import html
import io
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from core.cau_hinh import settings

logger = logging.getLogger(__name__)

LOGO_DIR: Path = settings.DATA_DIR / "logos"
DEFAULT_TEMPLATES = (
    "https://cdn.simplize.vn/simplizevn/logo/{symbol}.jpeg",
    "https://vietcap-documents.s3.ap-southeast-1.amazonaws.com/sentiment/logo/{symbol}.jpeg",
    "https://static.fireant.vn/Upload/Companies/Images/{symbol}.png",
)
RETRY_MISSING_SEC = 3 * 86400
MAX_BYTES = 1024 * 1024
TIMEOUT = 4
_SYM_RE = re.compile(r"^[A-Z0-9]{2,10}$")
_BADGE_COLORS = ("#2563eb", "#16a34a", "#ea580c", "#9333ea", "#0891b2", "#dc2626", "#ca8a04", "#4f46e5", "#0d9488")


def _templates() -> List[str]:
    raw = os.getenv("LOGO_URL_TEMPLATES", "").strip()
    items = [t.strip() for t in raw.split(",") if t.strip()] if raw else list(DEFAULT_TEMPLATES)
    return [t for t in items if t.startswith("https://") and "{symbol}" in t]


def _clean(symbol: str) -> Optional[str]:
    sym = (symbol or "").upper().strip()
    return sym if _SYM_RE.match(sym) else None


def _to_png(data: bytes) -> Optional[bytes]:
    """Kiểm tra là ảnh thật, chuẩn hóa về PNG nền trong suốt, cạnh dài ≤ 160px."""
    if not data or len(data) > MAX_BYTES or len(data) < 100:
        return None
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        img.load()
        if img.width < 16 or img.height < 16:
            return None
        img = img.convert("RGBA")
        img.thumbnail((160, 160))
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()
    except Exception:
        return None


def _download(url: str) -> Optional[bytes]:
    try:
        import requests
        r = requests.get(url, timeout=TIMEOUT, stream=True,
                         headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"})
        if r.status_code != 200:
            return None
        body, total = [], 0
        for chunk in r.iter_content(64 * 1024):
            total += len(chunk)
            if total > MAX_BYTES:
                return None
            body.append(chunk)
        return _to_png(b"".join(body))
    except Exception as exc:
        logger.debug("logo %s: %s", url, exc)
        return None


def logo_path(symbol: str, fetch: bool = True) -> Optional[Path]:
    """Đường dẫn PNG logo trong máy; chưa có thì (fetch=True) tải từ các nguồn theo thứ tự ưu tiên."""
    sym = _clean(symbol)
    if not sym:
        return None
    path, miss = LOGO_DIR / f"{sym}.png", LOGO_DIR / f"{sym}.none"
    if path.exists() and path.stat().st_size > 0:
        return path
    if not fetch or (miss.exists() and time.time() - miss.stat().st_mtime < RETRY_MISSING_SEC):
        return None
    urls = [t.format(symbol=sym) for t in _templates()]
    if not urls:
        return None
    with ThreadPoolExecutor(max_workers=len(urls)) as ex:          # thử song song, lấy nguồn ưu tiên cao nhất có ảnh
        results = list(ex.map(_download, urls))
    png = next((r for r in results if r), None)
    try:
        LOGO_DIR.mkdir(parents=True, exist_ok=True)
        if png:
            path.write_bytes(png)
            miss.unlink(missing_ok=True)
            return path
        miss.write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
    except OSError as exc:
        logger.debug("logo save %s: %s", sym, exc)
    return None


@lru_cache(maxsize=256)
def _data_uri(path_str: str, mtime: float) -> str:
    return "data:image/png;base64," + base64.b64encode(Path(path_str).read_bytes()).decode("ascii")


def badge_color(symbol: str) -> str:
    h = int(hashlib.md5((symbol or "?").encode("utf-8")).hexdigest(), 16)
    return _BADGE_COLORS[h % len(_BADGE_COLORS)]


def logo_html(symbol: str, size: int = 44, dark: bool = False, fetch: bool = True) -> str:
    """Thẻ HTML: logo (nếu có) trong khung trắng bo góc; không có → huy hiệu chữ màu theo mã."""
    sym = _clean(symbol) or "?"
    path = logo_path(sym, fetch=fetch) if sym != "?" else None
    border = "#30363d" if dark else "#e2e8f0"
    box = (f"width:{size}px;height:{size}px;border-radius:{max(6, size // 4)}px;flex-shrink:0;display:inline-flex;"
           f"align-items:center;justify-content:center;vertical-align:middle;overflow:hidden;")
    if path:
        uri = _data_uri(str(path), path.stat().st_mtime)
        return (f'<span style="{box}background:#ffffff;border:1px solid {border};padding:{max(2, size // 14)}px;'
                f'box-sizing:border-box"><img src="{uri}" alt="{html.escape(sym)}" '
                f'style="max-width:100%;max-height:100%;object-fit:contain"></span>')
    label = html.escape(sym[:3])
    fs = max(10, int(size * (0.36 if len(label) >= 3 else 0.44)))
    return (f'<span style="{box}background:{badge_color(sym)};color:#ffffff;font-weight:800;font-size:{fs}px;'
            f'letter-spacing:.3px;font-family:inherit">{label}</span>')


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: components/background_fx.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Hiệu ứng nền động cho toàn bộ app:
  • Các mảng màu gradient mờ trôi chậm (aurora)
  • Mạng hạt nối nhau bằng đường mảnh, phản ứng với chuột (nối về con trỏ, bị đẩy nhẹ)
  • Quầng sáng đi theo con trỏ + gợn sóng khi bấm chuột

Cách hoạt động: Streamlit không chạy <script> trong st.markdown, nên dùng st.iframe (trước đây components.html)
(iframe cùng origin) để chèn MỘT LẦN đoạn mã lõi vào trang chính (window.parent). Mã lõi chạy
trong trang chính nên không bị dừng khi Streamlit tạo lại iframe; các lần sau iframe chỉ gửi
cấu hình mới (đổi giao diện Sáng/Tối, bật/tắt) qua sự kiện "fxcfg".
Tự tạm dừng khi tab bị ẩn; tôn trọng cài đặt "giảm chuyển động" của hệ điều hành.
"""


import json

import streamlit as st

_THEMES = {
    "light": {
        "blobs": ["rgba(37,99,235,0.30)", "rgba(6,182,212,0.26)", "rgba(139,92,246,0.24)", "rgba(16,185,129,0.20)"],
        "dot": "37,99,235", "line": "37,99,235", "glow": "rgba(37,99,235,0.18)",
        "bg": "#f4f7fb", "glass": "rgba(255,255,255,0.72)", "glass_border": "rgba(226,232,240,0.9)",
    },
    "dark": {
        "blobs": ["rgba(37,99,235,0.38)", "rgba(6,182,212,0.26)", "rgba(139,92,246,0.32)", "rgba(16,185,129,0.22)"],
        "dot": "125,170,255", "line": "96,150,255", "glow": "rgba(88,166,255,0.22)",
        "bg": "#0b1020", "glass": "rgba(13,17,23,0.72)", "glass_border": "rgba(48,54,61,0.9)",
    },
}

# Mã lõi – chạy trong trang chính, chỉ khởi tạo một lần
_CORE = r"""
(function () {
  if (window.__fxLoaded) return; window.__fxLoaded = true;
  const doc = document;
  let root = null, glow = null, cv = null, ctx = null, running = false;
  let W = 0, H = 0, pts = [], ripples = [];
  const mouse = { x: -9999, y: -9999, active: false };
  const reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const LINK = 130, MOUSE_R = 170;

  function css(c) {
    let st = doc.getElementById("fx-style");
    if (!st) { st = doc.createElement("style"); st.id = "fx-style"; doc.head.appendChild(st); }
    // Selector có độ ưu tiên cao hơn CSS giao diện sẵn có (cũng dùng !important)
    st.textContent = `
      html body { background: ${c.bg} !important; }
      html body .stApp, html body [data-testid="stAppViewContainer"], html body [data-testid="stMain"],
      html body .main { background: transparent !important; background-color: transparent !important; }
      html body header, html body header[data-testid="stHeader"], html body [data-testid="stAppHeader"],
      html body .stAppHeader { background: ${c.glass} !important; background-color: ${c.glass} !important;
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); }
      html body section[data-testid="stSidebar"] { background: ${c.glass} !important;
        backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); border-right: 1px solid ${c.glass_border} !important; }
      html body div[data-testid="stElementContainer"]:has(> iframe[height="0"]),
      html body div.element-container:has(> iframe[height="0"]),
      html body div[data-testid="stElementContainer"][height="1px"]:has(> iframe[data-testid="stIFrame"]) { display: none !important; }
      /* Lớp nền nằm DƯỚI toàn bộ nội dung (z-index âm) – không thay đổi position của các khối
         Streamlit, nên thanh bên / trang chính vẫn cuộn bình thường */
      #fx-root { position: fixed; inset: 0; z-index: -1; pointer-events: none; overflow: hidden; }
      #fx-root .blob { position: absolute; width: 46vmax; height: 46vmax; border-radius: 50%;
        filter: blur(70px); will-change: transform; transition: background 1s; }
      #fx-root canvas { position: absolute; inset: 0; }
      #fx-glow { position: absolute; left: 0; top: 0; width: 520px; height: 520px; margin: -260px 0 0 -260px;
        border-radius: 50%; background: radial-gradient(circle, ${c.glow} 0%, transparent 65%);
        transition: opacity .4s; opacity: 0; }
      @keyframes fxa { 0%{transform:translate(0,0) scale(1)} 33%{transform:translate(18vw,12vh) scale(1.15)}
                       66%{transform:translate(-12vw,20vh) scale(.9)} 100%{transform:translate(0,0) scale(1)} }
      @keyframes fxb { 0%{transform:translate(0,0) scale(1)} 50%{transform:translate(-20vw,-14vh) scale(1.2)}
                       100%{transform:translate(0,0) scale(1)} }
      @media (prefers-reduced-motion: reduce) { #fx-root .blob { animation: none !important; } }`;
  }

  function build(c) {
    root = doc.createElement("div"); root.id = "fx-root";
    const spots = [
      { top: "-12vmax", left: "-10vmax", anim: "fxa 26s" }, { top: "-8vmax", right: "-14vmax", anim: "fxb 32s" },
      { top: "40vh", left: "30vw", anim: "fxa 38s reverse" }, { bottom: "-16vmax", right: "-6vmax", anim: "fxb 30s reverse" }];
    spots.forEach((s, i) => {
      const b = doc.createElement("div"); b.className = "blob";
      Object.assign(b.style, { top: s.top || "", left: s.left || "", right: s.right || "", bottom: s.bottom || "",
        background: c.blobs[i], animation: s.anim + " ease-in-out infinite" });
      root.appendChild(b);
    });
    glow = doc.createElement("div"); glow.id = "fx-glow"; root.appendChild(glow);
    cv = doc.createElement("canvas"); root.appendChild(cv); ctx = cv.getContext("2d");
    doc.body.prepend(root); resize();
  }

  function resize() {
    if (!cv) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = innerWidth; H = innerHeight;
    cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + "px"; cv.style.height = H + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const n = Math.round(Math.min(90, (W * H) / 16000));
    pts = Array.from({ length: n }, () => ({ x: Math.random() * W, y: Math.random() * H,
      vx: (Math.random() - .5) * .35, vy: (Math.random() - .5) * .35, r: Math.random() * 1.6 + .8 }));
  }

  function frame() {
    if (!running) return;
    const c = window.__fxCfg;
    ctx.clearRect(0, 0, W, H);
    for (const p of pts) {
      if (!reduce) { p.x += p.vx; p.y += p.vy; }
      if (p.x < 0 || p.x > W) p.vx *= -1;
      if (p.y < 0 || p.y > H) p.vy *= -1;
      if (mouse.active) {
        const dx = p.x - mouse.x, dy = p.y - mouse.y, d = Math.hypot(dx, dy);
        if (d < MOUSE_R && d > .1) { const f = (MOUSE_R - d) / MOUSE_R * .9; p.x += dx / d * f; p.y += dy / d * f; }
      }
    }
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i];
      for (let j = i + 1; j < pts.length; j++) {
        const b = pts[j], d = Math.hypot(a.x - b.x, a.y - b.y);
        if (d < LINK) { ctx.strokeStyle = `rgba(${c.line},${(1 - d / LINK) * .22})`; ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
      }
      if (mouse.active) {
        const d = Math.hypot(a.x - mouse.x, a.y - mouse.y), R = MOUSE_R * 1.3;
        if (d < R) { ctx.strokeStyle = `rgba(${c.line},${(1 - d / R) * .55})`; ctx.lineWidth = 1.1;
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(mouse.x, mouse.y); ctx.stroke(); }
      }
      ctx.fillStyle = `rgba(${c.dot},.55)`; ctx.beginPath(); ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2); ctx.fill();
    }
    ripples = ripples.filter(r => r.a > .01);
    for (const r of ripples) { r.r += 6; r.a *= .93; ctx.strokeStyle = `rgba(${c.line},${r.a})`; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(r.x, r.y, r.r, 0, Math.PI * 2); ctx.stroke(); }
    if (doc.hidden) setTimeout(() => requestAnimationFrame(frame), 500); else requestAnimationFrame(frame);
  }

  function apply() {
    const c = window.__fxCfg;
    if (!c.enabled) {
      running = false;
      if (root) { root.remove(); root = null; cv = null; }
      const st = doc.getElementById("fx-style"); if (st) st.remove();
      return;
    }
    css(c);
    if (!root) build(c);
    else root.querySelectorAll(".blob").forEach((b, i) => b.style.background = c.blobs[i % c.blobs.length]);
    if (!running) { running = true; requestAnimationFrame(frame); }
  }

  addEventListener("resize", resize);
  doc.addEventListener("mousemove", e => {
    mouse.x = e.clientX; mouse.y = e.clientY; mouse.active = true;
    if (glow) { glow.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`; glow.style.opacity = 1; }
  }, { passive: true });
  doc.addEventListener("mouseleave", () => { mouse.active = false; if (glow) glow.style.opacity = 0; });
  doc.addEventListener("mousedown", e => ripples.push({ x: e.clientX, y: e.clientY, r: 0, a: .5 }), { passive: true });
  addEventListener("fxcfg", apply);
  apply();
})();
"""

_LOADER = """
<script>
(function () {
  const P = window.parent;
  P.__fxCfg = __CFG__;
  if (!P.__fxLoaded) {
    const s = P.document.createElement("script");
    s.textContent = __CORE__;
    P.document.head.appendChild(s);
  } else {
    P.dispatchEvent(new P.Event("fxcfg"));
  }
})();
</script>
"""


def inject_background(theme: str = "light", enabled: bool = True):
    cfg = dict(_THEMES.get(theme, _THEMES["light"]))
    cfg["enabled"] = bool(enabled)
    html = _LOADER.replace("__CFG__", json.dumps(cfg)).replace("__CORE__", json.dumps(_CORE))
    st.iframe(html, height=1)          # thay components.html (Streamlit đã ngừng hỗ trợ); khung 1px vô hình


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: components/price_chart.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Biểu đồ giá tương tác "tất cả trong một" cho trang 🔍 Phân Tích Cổ Phiếu.

• Vẽ TOÀN BỘ lịch sử giá đã tải; nút khoảng (1T/3T/6T/1N) chỉ đặt KHUNG NHÌN ban đầu → kéo (pan) sang trái vẫn thấy nến cũ.
• Trục giá và trục các chỉ báo TỰ CO GIÃN theo đoạn đang xem mỗi khi kéo/zoom (JS chạy trong iframe), RSI cố định 0–100.
• Các chỉ báo kỹ thuật (Khối lượng, RSI, MACD, ADX ± DI, MFI & CMF, OBV) là các khung con dùng chung trục thời gian,
  rê chuột hiện giá trị của mọi khung cùng lúc.
"""


import hashlib
import json
from functools import lru_cache
from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

PANELS = ["Khối lượng", "RSI", "MACD", "ADX ± DI", "MFI & CMF", "OBV"]
DEFAULT_PANELS = ["Khối lượng", "RSI", "MACD"]
OVERLAY_COL = {"MA20": "SMA_20", "MA50": "SMA_50", "MA200": "SMA_200", "EMA12": "EMA_12", "EMA26": "EMA_26"}
OVERLAY_CLR = {"MA20": "#2563eb", "MA50": "#f59e0b", "MA200": "#8b5cf6", "EMA12": "#06b6d4", "EMA26": "#ec4899"}


def _ts(d: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(d["timestamp"] if "timestamp" in d.columns else d.index)


def _lst(s) -> list:
    """Chuỗi số → list Python (None cho NaN) để JSON không dùng mã hóa nhị phân."""
    return [None if pd.isna(v) else float(v) for v in s]


def build_figure(px: pd.DataFrame, overlays: List[str], panels: List[str], window_days: Optional[int], p: Dict[str, str],
                 base_layout: dict) -> go.Figure:
    d = px.copy()
    x = [t.strftime("%Y-%m-%d") for t in _ts(d)]
    panels = [q for q in PANELS if q in panels]
    avail = {"Khối lượng": "volume" in d, "RSI": "RSI" in d, "MACD": "MACD" in d, "ADX ± DI": "ADX" in d,
             "MFI & CMF": "MFI" in d or "CMF" in d, "OBV": "OBV" in d}
    panels = [q for q in panels if avail.get(q)]
    n = 1 + len(panels)
    heights = [0.52] + [0.48 / len(panels)] * len(panels) if panels else [1.0]
    fig = make_subplots(rows=n, cols=1, shared_xaxes=True, vertical_spacing=0.025, row_heights=heights,
                        subplot_titles=[""] + panels)
    fig.add_trace(go.Candlestick(x=x, open=_lst(d["open"]), high=_lst(d["high"]), low=_lst(d["low"]), close=_lst(d["close"]),
                                 name="Giá", increasing_line_color=p["up"], decreasing_line_color=p["down"],
                                 increasing_fillcolor=p["up"], decreasing_fillcolor=p["down"]), row=1, col=1)
    for o in overlays:
        col = OVERLAY_COL.get(o)
        if col and col in d:
            fig.add_scatter(x=x, y=_lst(d[col]), name=o, line=dict(color=OVERLAY_CLR[o], width=1.4), row=1, col=1)
    if "Bollinger" in overlays and {"BB_upper", "BB_lower"} <= set(d.columns):
        fig.add_scatter(x=x, y=_lst(d["BB_upper"]), name="BB trên", line=dict(color="#94a3b8", width=1, dash="dot"), row=1, col=1)
        fig.add_scatter(x=x, y=_lst(d["BB_lower"]), name="BB dưới", line=dict(color="#94a3b8", width=1, dash="dot"),
                        fill="tonexty", fillcolor="rgba(148,163,184,0.12)", row=1, col=1)
    last = float(d["close"].iloc[-1])
    fig.add_hline(y=last, line_dash="dot", line_color=p["accent"], row=1, col=1,
                  annotation_text=f"{last:,.0f}", annotation_position="right", annotation_font_color=p["accent"])
    fixed = []
    for i, q in enumerate(panels, start=2):
        if q == "Khối lượng":
            vc = [p["up"] if c >= o else p["down"] for c, o in zip(d["close"], d["open"])]
            fig.add_bar(x=x, y=_lst(d["volume"]), name="Khối lượng", marker_color=vc, opacity=0.6, row=i, col=1)
        elif q == "RSI":
            fig.add_scatter(x=x, y=_lst(d["RSI"]), name="RSI (14)", line=dict(color="#8b5cf6", width=1.5), row=i, col=1)
            for lv, c in ((70, p["down"]), (30, p["up"])):
                fig.add_hline(y=lv, line_dash="dot", line_color=c, opacity=0.7, row=i, col=1)
            fig.update_yaxes(range=[0, 100], row=i, col=1)
            fixed.append(i)
        elif q == "MACD":
            if "MACD_hist" in d:
                fig.add_bar(x=x, y=_lst(d["MACD_hist"]), name="Histogram",
                            marker_color=[p["up"] if (v or 0) >= 0 else p["down"] for v in d["MACD_hist"].fillna(0)],
                            opacity=0.55, row=i, col=1)
            fig.add_scatter(x=x, y=_lst(d["MACD"]), name="MACD", line=dict(color="#2563eb", width=1.4), row=i, col=1)
            if "MACD_signal" in d:
                fig.add_scatter(x=x, y=_lst(d["MACD_signal"]), name="Signal", line=dict(color="#f59e0b", width=1.2), row=i, col=1)
        elif q == "ADX ± DI":
            for col, name, color in (("ADX", "ADX", p["text"]), ("PLUS_DI", "+DI", p["up"]), ("MINUS_DI", "−DI", p["down"])):
                if col in d:
                    fig.add_scatter(x=x, y=_lst(d[col]), name=name, line=dict(color=color, width=1.3), row=i, col=1)
            fig.add_hline(y=25, line_dash="dot", line_color=p["muted"], row=i, col=1)
        elif q == "MFI & CMF":
            if "MFI" in d:
                fig.add_scatter(x=x, y=_lst(d["MFI"]), name="MFI (14)", line=dict(color="#0ea5e9", width=1.4), row=i, col=1)
            if "CMF" in d:
                fig.add_bar(x=x, y=_lst(d["CMF"] * 100), name="CMF ×100",
                            marker_color=[p["up"] if (v or 0) > 0 else p["down"] for v in d["CMF"].fillna(0)],
                            opacity=0.5, row=i, col=1)
        elif q == "OBV":
            fig.add_scatter(x=x, y=_lst(d["OBV"]), name="OBV", line=dict(color="#14b8a6", width=1.4), row=i, col=1)
    ts = _ts(d)
    end = ts.max() + pd.Timedelta(days=2)
    start = ts.max() - pd.Timedelta(days=window_days) if window_days else ts.min()
    legend_rows = -(-len(fig.data) // 8)                      # chú thích nằm TRÊN biểu đồ, ~8 mục mỗi dòng
    top = 24 + 24 * legend_rows
    h = 430 + 150 * len(panels) + top - 30
    fig.update_layout(**{**base_layout, "height": h, "margin": dict(l=55, r=70, t=top, b=25), "hovermode": "x unified",
                         "hoversubplots": "axis", "dragmode": "pan", "showlegend": True,
                         "legend": dict(orientation="h", yanchor="bottom", y=1.01, x=0, xanchor="left", bgcolor="rgba(0,0,0,0)", borderwidth=0, font=dict(color=p["text"], size=12), itemsizing="constant")})
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])], showgrid=False, rangeslider_visible=False,
                     range=[start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")],
                     showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1, spikedash="dot",
                     spikecolor=p["muted"])
    fig.update_yaxes(gridcolor=p["track"], fixedrange=False)
    for a in fig.layout.annotations:          # tiêu đề khung con: nhỏ, căn trái
        if a.text in PANELS:
            a.update(x=0, xanchor="left", font=dict(size=12, color=p["muted"]))
    fig.layout.meta = {"fixed_rows": fixed}
    return fig


@lru_cache(maxsize=1)
def _plotly_js() -> str:
    from plotly.offline import get_plotlyjs
    return get_plotlyjs()


def _spec(fig: go.Figure, height: Optional[int] = None):
    """Hình → (JSON dữ liệu + bố cục, các trục Y cố định, chiều cao)."""
    fixed = (fig.layout.meta or {}).get("fixed_rows", []) if fig.layout.meta else []
    fixed_keys = ["yaxis" + ("" if r == 1 else str(r)) for r in fixed]
    h = height or int(fig.layout.height or 600)
    spec = fig.to_plotly_json()
    payload = json.dumps({"data": spec["data"], "layout": spec["layout"]}, default=str)
    return payload, fixed_keys, h


def render(fig: go.Figure, height: Optional[int] = None) -> None:
    """Hiển thị biểu đồ bằng plotly.js nhúng sẵn (chạy được offline) + tự co giãn trục Y khi kéo/zoom."""
    _show(*_spec(fig, height))


def render_cached(px: pd.DataFrame, overlays: List[str], panels: List[str], window_days: Optional[int],
                  p: Dict[str, str], base_layout: dict, height: Optional[int] = None) -> None:
    """Như render(build_figure(...)) nhưng NHỚ kết quả dựng hình (14/10/2026): dựng biểu đồ Plotly ~0,6–0,9 giây mỗi lần
    trang chạy lại; cùng dữ liệu + cùng tùy chọn → dùng lại JSON đã dựng."""
    _show(*_cached_spec(px, tuple(overlays), tuple(panels), window_days, p, base_layout, height))


@st.cache_data(ttl=1800, max_entries=24, show_spinner=False)
def _cached_spec(px, overlays, panels, window_days, p, base_layout, height):
    return _spec(build_figure(px, list(overlays), list(panels), window_days, p, base_layout), height)


def _show(payload: str, fixed_keys: List[str], h: int) -> None:
    # id cố định theo nội dung → biểu đồ không đổi thì Streamlit KHÔNG tải lại khung khi trang chạy lại
    div = "pc_" + hashlib.md5(payload.encode("utf-8")).hexdigest()[:10]
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<style>html,body{{margin:0;background:transparent;overflow:hidden}}</style>
<script>{_plotly_js()}</script></head><body>
<div id="{div}" style="width:100%;height:{h}px"></div>
<script>
const spec = {payload};
const FIXED = {json.dumps(fixed_keys)};
const gd = document.getElementById("{div}");
let busy = false, drawn = false;
// Vẽ khi khung đã HIỆN (biểu đồ nằm trong tab chưa mở thì iframe rộng 0 → Plotly đo sai chữ, chú thích chồng lên nhau)
function draw() {{
  if (drawn || gd.clientWidth < 50) return;
  drawn = true;
  Plotly.newPlot(gd, spec.data, spec.layout, {{responsive:true, displaylogo:false, scrollZoom:true,
    modeBarButtonsToRemove:["select2d","lasso2d","autoScale2d"]}}).then(() => {{
    gd.on("plotly_relayout", ev => {{
      if (busy) return;
      if (Object.keys(ev).some(k => k.startsWith("xaxis") || k === "autosize")) fitY();
    }});
    fitY();
  }});
}}
new ResizeObserver(() => {{ if (!drawn) draw(); else Plotly.Plots.resize(gd); }}).observe(document.body);
function fitY() {{
  const xr = gd._fullLayout.xaxis.range; if (!xr) return;
  const x0 = new Date(xr[0]).getTime(), x1 = new Date(xr[1]).getTime();
  const box = {{}};
  gd._fullData.forEach(tr => {{
    if (tr.visible === false || tr.visible === "legendonly") return;
    const ax = "yaxis" + ((tr.yaxis || "y").slice(1));
    if (!box[ax]) box[ax] = [Infinity, -Infinity];
    const hi = tr.type === "candlestick" ? tr.high : tr.y, lo = tr.type === "candlestick" ? tr.low : tr.y;
    if (!hi || !tr.x) return;
    for (let i = 0; i < tr.x.length; i++) {{
      const t = new Date(tr.x[i]).getTime(); if (t < x0 || t > x1) continue;
      const a = +hi[i], b = +lo[i];
      if (hi[i] !== null && isFinite(a)) box[ax][1] = Math.max(box[ax][1], a);
      if (lo[i] !== null && isFinite(b)) box[ax][0] = Math.min(box[ax][0], b);
    }}
    if (tr.type === "bar") box[ax][0] = Math.min(box[ax][0], 0);
  }});
  const upd = {{}};
  for (const [ax, [lo, hi]] of Object.entries(box)) {{
    if (FIXED.includes(ax) || !isFinite(lo) || !isFinite(hi)) continue;
    const pad = (hi - lo) * 0.07 || Math.abs(hi) * 0.02 || 1;
    upd[ax + ".range"] = [lo - pad, hi + pad];
  }}
  busy = true; Plotly.relayout(gd, upd).then(() => {{ busy = false; }});
}}
draw();
</script></body></html>"""
    import streamlit as st
    st.iframe(html, height=h + 10)          # thay components.html (Streamlit đã ngừng hỗ trợ)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: components/sidebar_nav.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Thanh bên trái kiểu "VN Stock Pro" (15/10/2026): nền xanh lá đậm (màu chứng khoán) cố định (không phụ thuộc chế độ Sáng/Tối của nội dung),
menu chia nhóm, mỗi mục 1 icon (Material Symbols) + tên ngắn; mục đang chọn nền xanh đậm, chữ xanh sáng.

Giá trị lưu trong st.session_state["nav_page"] GIỮ NGUYÊN tên trang cũ (có emoji) để không phá điều hướng ở chỗ khác
(nút "Phân tích FPT", hub.resolve_legacy, …) – chỉ đổi phần hiển thị.
"""


from typing import List, Optional, Tuple

import streamlit as st

# (nhóm, [(giá trị nav_page, nhãn hiển thị, icon Material)])
def nav_groups() -> List[Tuple[str, List[Tuple[str, str, str]]]]:
    from giao_dien import chung as hub
    return [
        ("Thị trường", [
            ("🏛️ Tổng Quan Thị Trường", "Tổng quan thị trường", ":material/account_balance:"),
            ("🔍 Phân Tích Cổ Phiếu", "Phân tích cổ phiếu", ":material/tune:"),
            (hub.SCREEN, "Lọc và so sánh", ":material/filter_alt:"),
        ]),
        ("Dữ liệu doanh nghiệp", [
            (hub.FIN, "Chỉ số tài chính", ":material/assignment:"),
            ("📚 Tài Liệu BCTN & BCTC", "Tài liệu BCTN, BCTC", ":material/folder_open:"),
            ("📰 Tin Tức Doanh Nghiệp", "Tin tức doanh nghiệp", ":material/article:"),
        ]),
        ("Cá nhân", [
            (hub.PORT, "Danh mục theo dõi", ":material/work_outline:"),
            ("📄 Xuất Báo Cáo PDF", "Xuất báo cáo PDF", ":material/picture_as_pdf:"),
            ("🛰️ Nguồn Dữ Liệu", "Nguồn dữ liệu", ":material/database:"),
        ]),
        ("Đề án", [
            ("🎓 Thuyết Minh Đề Án", "Thuyết minh đề án", ":material/school:"),
        ]),
    ]


def all_pages() -> List[str]:
    return [v for _, items in nav_groups() for v, _, _ in items]


BG = "#0b3b2c"
BG_CARD = "#0f4a37"
LINE = "#1d6149"
TEXT = "#eaf7f0"
MUTED = "#9fcdb6"
ACTIVE_BG = "#1a7f55"
ACTIVE_TX = "#ffffff"
HOVER = "#135741"

SIDEBAR_CSS = f"""
<style>
section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {{
    background: {BG} !important; border-right: 1px solid {LINE} !important;
}}
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div, section[data-testid="stSidebar"] b {{ color: {TEXT}; }}
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {{
    color: #ffffff !important;
}}
section[data-testid="stSidebar"] hr {{ border-color: {LINE} !important; }}
/* Ô tìm mã + popover cài đặt */
section[data-testid="stSidebar"] [data-baseweb="select"], section[data-testid="stSidebar"] [data-baseweb="select"] > div,
section[data-testid="stSidebar"] [data-baseweb="select"] > div > div, section[data-testid="stSidebar"] [data-baseweb="select"] input {{
    background: {BG_CARD} !important; background-color: {BG_CARD} !important; border-color: {LINE} !important;
}}
section[data-testid="stSidebar"] [data-baseweb="select"] * {{ color: {TEXT} !important; }}
section[data-testid="stSidebar"] [data-testid="stSelectbox"] div {{
    background: {BG_CARD} !important; background-color: {BG_CARD} !important; border-color: {LINE} !important;
}}
section[data-testid="stSidebar"] [data-testid="stSelectbox"] * {{ color: {TEXT} !important; }}
section[data-testid="stSidebar"] [data-testid="stPopover"] button {{
    background: {BG_CARD} !important; border: 1px solid {LINE} !important; color: {TEXT} !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] * {{ color: {MUTED} !important; }}
/* Tiêu đề nhóm */
.sbn-group {{ font-size: 12.5px; font-weight: 600; color: {MUTED} !important; margin: 14px 4px 4px; letter-spacing: .2px; }}
/* Mục menu */
section[data-testid="stSidebar"] [class*="st-key-sbnav_"] .stButton > button {{
    width: 100%; justify-content: flex-start !important; text-align: left; border: none !important;
    background: transparent !important; color: {TEXT} !important; padding: 7px 12px !important; min-height: 38px;
    border-radius: 9px !important; box-shadow: none !important; font-weight: 500 !important; transform: none !important;
    filter: none !important; transition: background .15s ease !important;
}}
[class*="st-key-sbnav_"] button > div, [class*="st-key-sbnav_"] button p {{
    justify-content: flex-start !important; text-align: left !important; font-size: 15px !important; color: inherit !important;
}}
[class*="st-key-sbnav_"] button [data-testid="stIconMaterial"] {{ color: {MUTED} !important; font-size: 20px !important;
    margin-right: 6px; }}
section[data-testid="stSidebar"] [class*="st-key-sbnav_"] .stButton > button:hover {{ background: {HOVER} !important; transform: none !important; }}
section[data-testid="stSidebar"] [class*="st-key-sbnav_"] .stButton > button[data-testid="stBaseButton-primary"] {{
    background: {ACTIVE_BG} !important; color: {ACTIVE_TX} !important; font-weight: 600 !important;
}}
[class*="st-key-sbnav_"] button[data-testid="stBaseButton-primary"] [data-testid="stIconMaterial"],
[class*="st-key-sbnav_"] button[data-testid="stBaseButton-primary"] p {{ color: {ACTIVE_TX} !important; }}
[class*="st-key-sbnav_"] {{ margin-bottom: -10px; }}
</style>
"""


def render_nav(current: Optional[str]) -> str:
    """Vẽ menu chia nhóm trong thanh bên; trả về trang đang chọn (đã cập nhật nếu người dùng bấm)."""
    st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)
    pages = all_pages()
    current = current if current in pages else pages[0]
    for gi, (group, items) in enumerate(nav_groups()):
        st.markdown(f'<div class="sbn-group">{group}</div>', unsafe_allow_html=True)
        for ii, (value, label, icon) in enumerate(items):
            active = value == current
            if st.button(label, key=f"sbnav_{gi}_{ii}", icon=icon, type="primary" if active else "tertiary",
                         width="stretch") and not active:
                st.session_state["nav_page"] = value
                st.rerun()
    return current


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: pages/hub.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Trang gộp (14/10/2026) – mỗi trang gộp có thanh chọn ngang ở đầu trang; CHỈ phần đang chọn được chạy.

Không dùng st.tabs: Streamlit chạy nội dung của TẤT CẢ các tab ở mỗi lần tương tác → Điểm cơ hội đầu tư và Backtest
(tính nặng) sẽ chạy lại mỗi lần bấm nút ở phần khác.

  📑 Báo Cáo & Chỉ Số Tài Chính : Báo cáo tài chính · Chỉ số tài chính
  🔎 Lọc & So Sánh Cổ Phiếu     : Bộ lọc cổ phiếu · So sánh cổ phiếu
  💼 Danh Mục & Theo Dõi        : Theo dõi & cảnh báo · Quản lý danh mục · Điểm cơ hội đầu tư
"""


from typing import Callable, List, Tuple

import streamlit as st

FIN = "📑 Báo Cáo & Chỉ Số Tài Chính"
SCREEN = "🔎 Lọc & So Sánh Cổ Phiếu"
PORT = "💼 Danh Mục & Theo Dõi"

SUBS = {
    FIN: ["📑 Báo cáo tài chính", "🧮 Chỉ số tài chính"],
    SCREEN: ["🔎 Bộ lọc cổ phiếu", "⚖️ So sánh cổ phiếu"],
    PORT: ["👁️ Theo dõi & cảnh báo", "💼 Quản lý danh mục", "⭐ Điểm cơ hội đầu tư"],
}

# Tên trang cũ → (trang gộp, phần con). Dùng khi session/nút ở trang khác còn trỏ tới tên cũ.
LEGACY = {
    "📑 Báo Cáo Tài Chính": (FIN, 0), "🧮 Chỉ Số Tài Chính": (FIN, 1),
    "🔎 Bộ Lọc Cổ Phiếu": (SCREEN, 0), "⚖️ So Sánh Cổ Phiếu": (SCREEN, 1),
    "👁️ Theo Dõi & Cảnh Báo": (PORT, 0), "💼 Quản Lý Danh Mục": (PORT, 1),
    "⭐ Điểm Cơ Hội Đầu Tư": (PORT, 2), "🔬 Backtest Khuyến Nghị": (PORT, 0),
}


def _key(page: str) -> str:
    return "hub_sub_" + {FIN: "fin", SCREEN: "screen", PORT: "port"}[page]


def resolve_legacy() -> None:
    """Gọi đầu app: nav_page là tên trang cũ → đổi sang trang gộp và chọn sẵn phần con tương ứng."""
    cur = st.session_state.get("nav_page")
    if cur in LEGACY:
        page, i = LEGACY[cur]
        st.session_state["nav_page"] = page
        st.session_state[_key(page)] = st.session_state[_key(page) + "_last"] = SUBS[page][i]


def _render(page: str, parts: List[Tuple[str, Callable[[], None]]]) -> None:
    labels = [lbl for lbl, _ in parts]
    key, last_key = _key(page), _key(page) + "_last"
    if st.session_state.get(key) not in labels:
        # chưa chọn, hoặc người dùng bấm lại mục đang chọn (segmented_control bỏ chọn → None) → giữ mục trước đó
        st.session_state[key] = st.session_state.get(last_key) if st.session_state.get(last_key) in labels else labels[0]
    pick = st.segmented_control(page, options=labels, key=key, label_visibility="collapsed", width="stretch")
    pick = pick if pick in labels else st.session_state.get(last_key, labels[0])
    st.session_state[last_key] = pick
    st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
    dict(parts)[pick]()


def render_financials() -> None:
    from giao_dien import doanh_nghiep as financial_ratios, doanh_nghiep as financial_statements
    _render(FIN, list(zip(SUBS[FIN], (financial_statements.render, financial_ratios.render_financial_ratios))))


def render_screen_compare() -> None:
    from giao_dien import thi_truong as compare, thi_truong as screener
    _render(SCREEN, list(zip(SUBS[SCREEN], (screener.render_screener, compare.render_compare))))


def render_portfolio() -> None:
    from giao_dien import ca_nhan as opportunity_score, ca_nhan as portfolio, ca_nhan as watchlist
    _render(PORT, list(zip(SUBS[PORT], (watchlist.render, portfolio.render_portfolio, opportunity_score.render_opportunity_score))))
