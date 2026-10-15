"""
STOCK ANALYTICS – HỆ THỐNG PHÂN TÍCH CƠ HỘI ĐẦU TƯ CỔ PHIẾU VIỆT NAM
Main Application Entry Point.
"""


import logging
import sys
from pathlib import Path
import streamlit as st

# Configure base path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.cau_hinh import settings
from giao_dien.chung import load_css
from core.du_lieu import get_formatted_options, get_ticker_label, extract_symbol_from_label, find_option_for_symbol

# Import pages
from giao_dien import ca_nhan, chung, doanh_nghiep, thi_truong

# Optional option_menu
try:
    from streamlit_option_menu import option_menu
    HAS_OPTION_MENU = True
except ImportError:
    HAS_OPTION_MENU = False

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

# ─── Page Configuration ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Analytics - Phân Tích Cổ Phiếu Việt Nam",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Session State Initialization ───────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state["theme"] = "light"

if "current_symbol" not in st.session_state:
    st.session_state["current_symbol"] = "FPT"

if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = "🏛️ Tổng Quan Thị Trường"
chung.resolve_legacy()        # tên trang cũ (trước khi gộp) → trang gộp + phần con tương ứng

# Inject Active Theme CSS
st.markdown(load_css(st.session_state["theme"]), unsafe_allow_html=True)

# Hiệu ứng nền động (aurora + mạng hạt phản ứng theo chuột) – bật/tắt ở thanh bên
from giao_dien.chung import inject_background
if "bg_fx" not in st.session_state:
    st.session_state["bg_fx"] = False          # mặc định TẮT hiệu ứng nền động
inject_background(st.session_state["theme"], st.session_state["bg_fx"])


def render_sidebar():
    """Render modern sidebar navigation, theme switcher, and market badges."""
    with st.sidebar:
        from core.du_lieu import Database
        db_state = Database()
        if db_state.mode == "read_only":
            st.warning("CSDL đang ở chế độ chỉ đọc. Các thay đổi danh mục/cảnh báo sẽ không được lưu.")
        elif db_state.mode == "ephemeral":
            st.error("Không mở được CSDL trên đĩa. Ứng dụng đang dùng bộ nhớ tạm; dữ liệu sẽ mất khi tắt app.")
        is_light = False            # thanh bên luôn nền tối (không phụ thuộc chế độ Sáng/Tối của nội dung)

        brand_sub = "#9fcdb6"
        card_bg = "#0f4a37"
        card_border = "#1d6149"
        ticker_color = "#86efac"
        head_color = "#1e293b" if is_light else "#f1f5f9"

        # Nút ⚙️ Cài đặt nhỏ ở góc trên (chế độ hiển thị, hiệu ứng nền) – tên ứng dụng trong khung ngay bên dưới
        c_set, _sp = st.columns([1.5, 3], vertical_alignment="center")       # nút cài đặt bên TRÁI
        with c_set:
            with st.popover(":material/settings:", width="stretch", help="Cài đặt: chế độ hiển thị, hiệu ứng nền"):
                st.markdown("**⚙️ Cài đặt**")
                st.caption("Chế độ hiển thị")
                theme_pick = st.radio("Theme", options=["☀️ Chế độ Sáng", "🌙 Chế độ Tối"],
                                      index=0 if st.session_state["theme"] == "light" else 1,
                                      horizontal=True, label_visibility="collapsed", key="theme_switcher_select")
                st.toggle("✨ Hiệu ứng nền động", key="bg_fx",
                          help="Nền gradient chuyển động + mạng hạt phản ứng theo chuột. Tắt nếu máy chạy chậm.")
        frame_bg = "linear-gradient(135deg,#0f5a41 0%,#0a3426 100%)"
        frame_bd = "#2f8f68"
        accent = "#4ade80"
        # Khung tên app co giãn theo độ rộng thanh bên (container query): kéo hẹp → khung & chữ nhỏ dần, luôn căn giữa
        st.markdown(f"""
        <style>
        .sw-brand-wrap{{container-type:inline-size;width:100%;}}
        .sw-brand{{margin:2px 0 4px;padding:clamp(8px,5cqw,14px) clamp(6px,4cqw,14px);border-radius:14px;
                   background:{frame_bg};border:1px solid {frame_bd};border-left:4px solid {accent};
                   box-shadow:0 2px 10px rgba(0,0,0,0.25);text-align:center;overflow:hidden;}}
        .sw-brand .row{{display:flex;align-items:center;justify-content:center;gap:clamp(4px,3cqw,10px);}}
        .sw-brand .ic{{font-size:clamp(14px,10cqw,24px);line-height:1;}}
        .sw-brand .nm{{font-size:clamp(11px,8.5cqw,20px);font-weight:900;color:{head_color};letter-spacing:clamp(0px,0.5cqw,1px);
                       white-space:nowrap;}}
        .sw-brand .sub{{font-size:clamp(6px,4.3cqw,10px);font-weight:800;color:{accent};letter-spacing:clamp(0px,0.6cqw,1.6px);
                        margin-top:clamp(2px,2cqw,6px);white-space:nowrap;}}
        </style>
        <div class="sw-brand-wrap"><div class="sw-brand">
            <div class="row"><div class="ic">📈</div><div class="nm">STOCK ANALYTICS</div></div>
            <div class="sub">PHÂN TÍCH CỔ PHIẾU VIỆT NAM</div>
        </div></div>
        """, unsafe_allow_html=True)
        selected_theme = "light" if "Sáng" in theme_pick else "dark"
        if selected_theme != st.session_state["theme"]:
            st.session_state["theme"] = selected_theme
            st.rerun()
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # Helper to sync all page widgets & state
        def sync_active_symbol(new_sym: str, switch_page: bool = True):
            new_sym = new_sym.strip().upper()
            if not new_sym:
                return
            st.session_state["current_symbol"] = new_sym
            st.session_state["stock_symbol_input"] = new_sym
            st.session_state["ta_symbol"] = new_sym
            st.session_state["score_symbol"] = new_sym
            st.session_state["bt_symbol"] = new_sym
            st.session_state["pdf_symbol"] = new_sym

            st.session_state.pop("stock_analysis", None)
            st.session_state.pop("last_analyzed", None)

            if switch_page and st.session_state.get("nav_page") == "🏛️ Tổng Quan Thị Trường":
                st.session_state["nav_page"] = "🔍 Phân Tích Cổ Phiếu"

        # 1. Tra cứu cổ phiếu – tìm trong TOÀN BỘ mã niêm yết (HOSE, HNX, UPCoM): gõ mã hoặc tên doanh nghiệp
        st.markdown(f"<p style='font-size:13.5px; font-weight:800; color:{head_color}; margin-bottom:4px;'>🔎 Tra cứu cổ phiếu</p>",
                    unsafe_allow_html=True)
        curr_sym = st.session_state.get("current_symbol", "FPT").strip().upper()
        options = get_formatted_options()
        matched = find_option_for_symbol(curr_sym, options)
        if not matched:
            matched = get_ticker_label(curr_sym)
            options = [matched] + options
        kw = dict(options=options, index=options.index(matched), key=f"sidebar_search_{curr_sym}",
                  label_visibility="collapsed", placeholder="Gõ mã hoặc tên doanh nghiệp…",
                  help=f"Tìm trong {len(options):,} mã đang niêm yết trên HOSE, HNX, UPCoM")
        try:
            pick = st.selectbox("Tìm mã cổ phiếu", accept_new_options=True, **kw)
        except TypeError:                     # Streamlit cũ chưa có accept_new_options
            pick = st.selectbox("Tìm mã cổ phiếu", **kw)
        pick_sym = (extract_symbol_from_label(pick) if pick else "").strip().upper()
        if pick_sym and pick_sym != curr_sym:
            sync_active_symbol(pick_sym, switch_page=True)
            st.rerun()

        # Display current active stock badge
        active_label = get_ticker_label(st.session_state["current_symbol"])
        from giao_dien.chung import logo_html
        active_logo = logo_html(st.session_state["current_symbol"], 30, dark=not is_light)
        st.markdown(
            f"""
            <div style="background:{card_bg}; border:1px solid {card_border}; border-radius:8px; padding:7px 10px; margin-top:6px; margin-bottom:14px; text-align:center; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                <div style="font-size:11.5px; color:{brand_sub};">Đang chọn phân tích:</div>
                <div style="display:flex; align-items:center; justify-content:center; gap:8px; margin-top:4px;">
                    {active_logo}
                    <div style="font-size:14.5px; font-weight:800; color:{ticker_color}; letter-spacing:0.5px; word-break:break-word; text-align:left;">
                        {active_label}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 2. Menu điều hướng chia nhóm (giao_dien/chung.py – thanh bên nền tối, 15/10/2026)
        from giao_dien.chung import render_nav
        selected_page = render_nav(st.session_state.get("nav_page"))

        # System Status & Info
        st.markdown("---")
        st.markdown(f"""
        <div style="font-size:12px; color:{brand_sub}; line-height: 1.6;">
            <div>🟢 <b>Giá:</b> DNSE (gần nhất) + Vnstock/Vietstock (lịch sử)</div>
            <div>📑 <b>BCTC:</b> VCI → KBS → Vietstock → PDF</div>
            <div>⚡ <b>Bộ nhớ đệm:</b> DiskCache + Memory</div>
            <div>🏛️ <b>Cơ sở dữ liệu:</b> DuckDB OLAP</div>
        </div>
        """, unsafe_allow_html=True)

        notice_border = "#f59e0b" if is_light else "#ffab00"
        notice_bg = "#0f4a37"
        notice_color = "#92400e" if is_light else "#8b949e"
        st.markdown(f"""
        <div style="margin-top: 20px; padding: 10px; background: {notice_bg}; border-radius: 6px; font-size: 11px; color: {notice_color}; border-left: 3px solid {notice_border};">
            <b>Khuyến cáo học thuật:</b><br>
            Hệ thống phục vụ nghiên cứu & học tập. Các mô hình định lượng không đảm bảo lợi nhuận tương lai.
        </div>
        """, unsafe_allow_html=True)

    return selected_page


def main():
    selected_page = render_sidebar()

    # Route to pages
    try:
        if "Tổng Quan Thị Trường" in selected_page:
            thi_truong.render()
        elif "Phân Tích Cổ Phiếu" in selected_page:
            thi_truong.render_stock_analysis()
        elif selected_page == chung.FIN:
            chung.render_financials()
        elif "Tài Liệu" in selected_page:
            doanh_nghiep.render_documents()
        elif selected_page == chung.SCREEN:
            chung.render_screen_compare()
        elif selected_page == chung.PORT:
            chung.render_portfolio()
        elif "Nguồn Dữ Liệu" in selected_page:
            ca_nhan.render_data_sources()
        elif "Phân Tích Kỹ Thuật" in selected_page:            # đã gộp vào Phân tích cổ phiếu → tab Phân tích kỹ thuật
            st.session_state["sa_tab"] = "📈 Phân tích kỹ thuật"
            thi_truong.render_stock_analysis()
        elif "Tin Tức" in selected_page:
            doanh_nghiep.render_company_news()
        elif "Khuyến Nghị Đầu Tư" in selected_page:     # trang đã bỏ → khuyến nghị nằm ở tab 🎯 của Phân tích cổ phiếu
            st.session_state["sa_tab"] = "🎯 Khuyến nghị"
            thi_truong.render_stock_analysis()
        elif "Xuất Báo Cáo" in selected_page:
            ca_nhan.render_pdf_report()
        elif "Thuyết Minh" in selected_page:
            from giao_dien import de_an
            de_an.render()
        else:
            thi_truong.render()

    except Exception as exc:
        logger.exception("Lỗi khi render trang %s: %s", selected_page, exc)
        st.error(f"⚠️ Đã xảy ra lỗi khi tải trang: {exc}")
        with st.expander("Chi tiết lỗi kỹ thuật (Debug)"):
            st.exception(exc)


if __name__ == "__main__":
    main()
