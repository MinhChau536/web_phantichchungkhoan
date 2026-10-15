"""
tests/test_giao_dien_bao_cao.py – kiểm thử, gộp từ 8 file (15/10/2026).

MỤC LỤC
  • tests/test_pdf_report.py – Unit test for PDFReportGenerator.
      hàm/lớp chính: test_pdf_report_generation
  • tests/test_market_overview.py – Kiểm thử phần tính toán và trang Tổng quan thị trường (dữ liệu giả lập, không gọi mạng).
      hàm/lớp chính: test_period_returns_and_card, test_universe_breadth_sector_health, test_health_without_data, test_market_overview_page_renders, test_compare_page_helpers, test_compare_page_renders
  • tests/test_logo.py – Logo doanh nghiệp: chỉ nhận ảnh thật, lưu một lần, không có thì hiện huy hiệu chữ.
      hàm/lớp chính: test_only_real_images_accepted, test_logo_downloaded_once_and_cached, test_missing_logo_shows_badge_and_is_not_refetched, test_bad_symbol_never_fetches, test_cover_with_logo_renders
  • tests/test_thesis.py – Thuyết minh đề án: nội dung dùng chung (trang app + phụ lục PDF) lấy tham số từ cấu hình, công thức LaTeX hợp lệ.
      hàm/lớp chính: test_sections_complete_and_formulas_have_plain_text, test_parameters_come_from_config, test_explain_symbol_handles_missing_data
  • tests/test_fixes.py – Kiểm thử cho 7 điểm đã sửa:
      hàm/lớp chính: test_rsi_same_value_across_modules, test_rsi_edge_cases, test_technical_score_uses_adx_and_money_flow, test_risk_score_reaches_100_with_partial_data, test_risk_score_none_when_no_data, test_parse_period_key, test_revenue_growth_is_yoy_even_if_source_is_newest_first, test_matrix_format_period_columns_ordered, test_peer_stats_and_sector_based_valuation, test_valuation_without_peers_reports_missing_not_default, test_pdf_has_no_fabricated_values_when_data_missing, test_pdf_full_pipeline_uses_real_components
  • tests/test_audit_fixes.py – Kiểm thử các lỗi tìm thấy khi rà soát dữ liệu (giá, BCTC, chỉ số).
      hàm/lớp chính: test_eps_growth_ignores_bonus_shares, test_piotroski_issuance_uses_cash_raised, test_dilution_risk_distinguishes_bonus_from_issuance, test_drawdown_is_one_year_only, test_gap_fix_adjusts_unadjusted_bonus_share
  • tests/test_hardening.py – Regression tests cho các lớp bảo vệ dữ liệu/UI được bổ sung ở bản hardening.
      hàm/lớp chính: test_html_and_external_url_are_sanitized, test_document_url_rejects_local_targets, test_document_response_has_hard_size_limit, test_point_in_time_prefers_actual_release_date, test_screener_rank_normalizes_only_available_metrics
  • tests/test_v2_platform.py – Kiểm thử nền tảng v2: nguồn dữ liệu lai ghép, BCTC nhiều nguồn, bộ chuẩn hóa, bộ tính chỉ số,
      hàm/lớp chính: test_canonical_vci_matrix_picks_net_revenue_not_growth_row, test_canonical_kbs_ids_and_v3_tabular_units, test_infer_scale, test_to_vnd_scales_stocks_not_indices, test_stitch_prices_adjusts_older_segment, test_hybrid_price_uses_dnse_recent_and_history_older, test_price_falls_back_when_dnse_or_vnstock_fails, test_financials_merge_sources_and_track_provenance, test_financials_fallback_to_kbs_when_vci_missing, test_quarter_mode_maps_year_end_balances_to_q4, test_merge_priority, hand_data …
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_pdf_report.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Unit test for PDFReportGenerator.
"""
from core.bao_cao_pdf import PDFReportGenerator


def test_pdf_report_generation():
    generator = PDFReportGenerator()
    mock_analysis = {
        "symbol": "FPT",
        "company_info": {
            "symbol": "FPT",
            "company_name": "Công ty Cổ phần FPT",
            "exchange": "HOSE",
            "industry": "Công nghệ thông tin",
        },
        "current_price": {
            "price": 105000.0,
            "change": 1500.0,
            "change_pct": 1.45,
        },
        "technical_score": {"score": 75, "rating": "Tích cực"},
        "opportunity_score": {
            "score": 78,
            "classification": {"label": "Tích cực", "color": "#69f0ae"},
            "coverage_pct": 100,
        },
        "signals": {
            "trend": {"name": "Tăng mạnh", "color": "#00e676"},
            "rsi": {"value": 58.5, "signal": "Tích cực"},
        },
    }
    
    pdf_bytes = generator.generate(mock_analysis, report_type="short")
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_market_overview.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Kiểm thử phần tính toán và trang Tổng quan thị trường (dữ liệu giả lập, không gọi mạng)."""
import numpy as np
import pandas as pd
import pytest

import core.thi_truong_danh_muc as ms
import core.pipeline as ss


@pytest.fixture(autouse=True)
def _use_fake(fake_repo, monkeypatch):
    monkeypatch.setattr(ss, "_default_repo", fake_repo)


def _df(closes):
    d = pd.bdate_range(end="2026-10-09", periods=len(closes))
    c = np.array(closes, dtype=float)
    return pd.DataFrame({"timestamp": d, "open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1e6})


def test_period_returns_and_card():
    df = _df(np.linspace(100, 120, 300))
    r = ms.period_returns(df)
    assert r["1T"] > 0 and r["1N"] > 0 and r["YTD"] > 0
    card = ms.index_card("VNINDEX", df)
    assert card["available"] and card["close"] == pytest.approx(120) and len(card["spark"]) == 60


def test_universe_breadth_sector_health():
    snap = ms.universe_snapshot(["FPT", "VCB", "HPG", "SSI"])
    assert len(snap) == 4 and {"change_pct", "value_bn", "sector", "spark"} <= set(snap.columns)
    assert snap.set_index("symbol").loc["VCB", "sector"] == "🏦 Ngân hàng"
    b = ms.breadth_stats(snap)
    assert b["available"] and b["advancing"] + b["declining"] + b["unchanged"] == b["total"] == 4
    sec = ms.sector_performance(snap)
    assert not sec.empty and "1D" in sec.columns
    h = ms.market_health(_df(np.linspace(100, 130, 250)), b)
    assert h["available"] and 0 <= h["score"] <= 100 and h["components"]["trend"]["score"] == 100


def test_health_without_data():
    assert ms.market_health(pd.DataFrame(), {"available": False})["available"] is False
    assert ms.breadth_stats(pd.DataFrame())["available"] is False


def test_market_overview_page_renders():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(
        "import streamlit as st\n"
        "st.session_state.setdefault('current_symbol', 'FPT')\n"
        "from giao_dien import thi_truong as market_overview\n"
        "market_overview.render()\n", default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "Tổng Quan Thị Trường" in html and "mo-card" in html


def test_compare_page_helpers():
    import pandas as pd
    from giao_dien.thi_truong import _best_worst, _relative_scores, _risk_metrics
    assert _best_worst([10.0, -5.0, 8.0], "low", "pe") == (2, 0)      # P/E âm không được coi là rẻ nhất
    assert _best_worst([1.0, 1.0], "high", "roe") == (None, None)       # bằng nhau thì không tô
    t = pd.DataFrame({"pe": [10, 20], "pb": [1, 2], "roe": [20, 10]}, index=["A", "B"])
    sc = _relative_scores(t)
    assert sc.loc["A", "Định giá"] == 100 and sc.loc["B", "Sinh lời"] == 0
    px = pd.DataFrame({"A": np.linspace(100, 120, 260)}, index=pd.bdate_range(end="2026-10-09", periods=260))
    r = _risk_metrics(px)["A"]
    assert r["mdd"] == pytest.approx(0) and r["vol"] is not None


def test_compare_page_renders():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string("from giao_dien import thi_truong as compare\ncompare.render_compare()\n", default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    at.button[1].click().run()          # nút "So sánh"
    assert not at.exception, at.exception


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_logo.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Logo doanh nghiệp: chỉ nhận ảnh thật, lưu một lần, không có thì hiện huy hiệu chữ."""
import io

from PIL import Image

from giao_dien import chung as lg


def _png(w=120, h=80):
    b = io.BytesIO()
    Image.new("RGBA", (w, h), (0, 94, 184, 255)).save(b, "PNG")
    return b.getvalue()


def test_only_real_images_accepted():
    assert lg._to_png(_png()) is not None
    assert lg._to_png(b"<html>not found</html>" * 20) is None        # trang lỗi trả HTML → loại
    assert lg._to_png(_png(8, 8)) is None                              # ảnh quá nhỏ → loại


def test_logo_downloaded_once_and_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(lg, "LOGO_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(lg, "_download", lambda url: calls.append(url) or (lg._to_png(_png()) if "good" in url else None))
    monkeypatch.setenv("LOGO_URL_TEMPLATES", "https://bad.example/{symbol}.png,https://good.example/{symbol}.png")
    p = lg.logo_path("fpt")
    assert p == tmp_path / "FPT.png" and p.exists()
    n = len(calls)
    assert lg.logo_path("FPT") == p and len(calls) == n               # lần sau đọc từ máy, không tải lại
    html = lg.logo_html("FPT", 40)
    assert "data:image/png;base64," in html


def test_missing_logo_shows_badge_and_is_not_refetched(tmp_path, monkeypatch):
    monkeypatch.setattr(lg, "LOGO_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(lg, "_download", lambda url: calls.append(url) or None)
    html = lg.logo_html("XYZ", 40)
    assert "<img" not in html and ">XYZ<" in html                     # huy hiệu chữ
    assert (tmp_path / "XYZ.none").exists()
    n = len(calls)
    lg.logo_html("XYZ", 40)
    assert len(calls) == n                                           # trong 3 ngày không thử lại


def test_bad_symbol_never_fetches(monkeypatch):
    monkeypatch.setattr(lg, "_download", lambda url: (_ for _ in ()).throw(AssertionError("không được gọi")))
    assert lg.logo_path("../etc/passwd") is None
    assert "?" in lg.logo_html("<script>")


def test_cover_with_logo_renders():
    from core.bao_cao_pdf import render_cover
    assert render_cover("FPT", "Công ty Cổ phần FPT", logo_png=lg._to_png(_png()))[:2] == b"\xff\xd8"


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_thesis.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Thuyết minh đề án: nội dung dùng chung (trang app + phụ lục PDF) lấy tham số từ cấu hình, công thức LaTeX hợp lệ."""
import re

from core import thuyet_minh as tc


def test_sections_complete_and_formulas_have_plain_text():
    secs = tc.sections()
    keys = [s["key"] for s in secs]
    for k in ("overview", "pages", "fundamental", "technical", "forecast", "valuation", "pillars", "recommendation",
              "risk", "validation"):
        assert k in keys
    for s in secs:
        assert s["pitch"] and s["blocks"]
        for b in s["blocks"]:
            if b[0] == "f":
                assert b[2], "công thức phải có bản chữ cho PDF"
                outside = re.sub(r"\\text\{[^{}]*\}", "", b[1])
                assert all(ord(ch) < 128 for ch in outside), f"chữ Việt ngoài \\text: {b[1][:60]}"
            if b[0] == "t":
                assert all(len(r) == len(b[1]) for r in b[2])


def test_parameters_come_from_config(monkeypatch):
    from core import cau_hinh as im
    from core.cau_hinh import DEFAULT_SCORE_WEIGHTS
    monkeypatch.setitem(im.DEFAULT_CONFIG["multilayer"], "min_liquidity_bn", 2.5)
    rec = tc.s_recommendation()
    txt = " ".join(x for b in rec["blocks"] if b[0] == "ul" for x in b[1])
    assert "< 2.5 tỷ đồng" in txt
    pil = tc.s_pillars()
    assert f"Cơ bản {DEFAULT_SCORE_WEIGHTS['fundamental']}%" in pil["pitch"][0]
    val = tc.s_valuation()
    labels = [r[0] for b in val["blocks"] if b[0] == "t" for r in b[2]]
    assert "Chứng khoán" in labels and "Ngân hàng" in labels


def test_explain_symbol_handles_missing_data():
    out = tc.explain_symbol({})
    assert out["valuation"] == ["Chưa có kết quả định giá cho mã này."]
    assert out["pillars"] == []


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_fixes.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Kiểm thử cho 7 điểm đã sửa:
  1. PDF không tự sinh số liệu giả khi thiếu dữ liệu
  2. Điểm rủi ro chuẩn hóa theo thành phần có dữ liệu
  3. Chiến lược Custom có tín hiệu thoát lệnh
  4. Tăng trưởng doanh thu so với cùng kỳ năm trước (YoY), sắp xếp kỳ đúng
  5. Định giá dùng trung vị ngành thật
  6. RSI thống nhất giữa các module
  7. ADX / MFI / OBV / CMF được đưa vào điểm kỹ thuật
"""
import numpy as np
import pandas as pd
import pytest

from core.phan_tich_co_ban import FundamentalAnalyzer
from core.phan_tich_ky_thuat import rsi_wilder
from core.phan_tich_ky_thuat import MomentumAnalyzer
from core.khuyen_nghi import OpportunityScorer
from core.phan_tich_co_ban import compute_peer_stats, find_sector_basket
from core.phan_tich_co_ban import growth_vs_prior, parse_period_key
from core.phan_tich_ky_thuat import TechnicalAnalyzer
from core.dinh_gia import ValuationEngine
from core.bao_cao_pdf import PDFReportGenerator


# ── 6. RSI thống nhất ────────────────────────────────────────────────────────
def test_rsi_same_value_across_modules(sample_ohlcv_df):
    ta = TechnicalAnalyzer(sample_ohlcv_df)
    tech_rsi = float(ta.compute_all()["RSI"].iloc[-1])
    mom_rsi = MomentumAnalyzer(sample_ohlcv_df).compute_rsi()
    bt_rsi = float(rsi_wilder(sample_ohlcv_df["close"], 14).iloc[-1])
    assert tech_rsi == pytest.approx(mom_rsi, abs=1e-9)
    assert tech_rsi == pytest.approx(bt_rsi, abs=1e-9)


def test_rsi_edge_cases():
    up = pd.Series(np.arange(1, 40, dtype=float))
    assert rsi_wilder(up).iloc[-1] == 100.0
    flat = pd.Series([10.0] * 40)
    assert rsi_wilder(flat).iloc[-1] == 50.0
    assert rsi_wilder(up).iloc[:13].isna().all()   # chưa đủ phiên -> NaN, không gán giả


# ── 7. ADX / dòng tiền vào điểm kỹ thuật ─────────────────────────────────────
def test_technical_score_uses_adx_and_money_flow(sample_ohlcv_df):
    ta = TechnicalAnalyzer(sample_ohlcv_df)
    ta.compute_all()
    res = ta.compute_technical_score()
    comps = res["components"]
    assert comps["adx"]["score"] is not None and comps["adx"]["max"] == 10
    assert comps["money_flow"]["score"] is not None and comps["money_flow"]["max"] == 15
    assert {"cmf", "mfi", "obv_above_ma20"} <= set(comps["money_flow"])
    # 100 phiên < 200 nên SMA200 thiếu -> mẫu số chỉ còn 15 điểm cho MA
    assert comps["ma_alignment"]["max"] == 15
    assert res["max_raw"] == 90


# ── 2. Điểm rủi ro ───────────────────────────────────────────────────────────
def test_risk_score_reaches_100_with_partial_data():
    r = OpportunityScorer.compute_risk_score(volatility_30d=0.005, max_drawdown=-0.05)
    assert r["score"] == 100            # trước khi sửa: tối đa 60
    assert r["coverage_pts"] == 60


def test_risk_score_none_when_no_data():
    assert OpportunityScorer.compute_risk_score()["score"] is None


# ── 4. Tăng trưởng YoY & thứ tự kỳ ───────────────────────────────────────────
def test_parse_period_key():
    assert parse_period_key("2024-Q3") == 20243
    assert parse_period_key("Q1/2025") == 20251
    assert parse_period_key("2023") == 20230


def test_revenue_growth_is_yoy_even_if_source_is_newest_first():
    # Nguồn trả kỳ MỚI NHẤT ĐỨNG ĐẦU (như VCI). Doanh thu có tính mùa vụ quý 4.
    rows = [
        (2025, 2, 130), (2025, 1, 110), (2024, 4, 200), (2024, 3, 120),
        (2024, 2, 100), (2024, 1, 90),
    ]
    is_df = pd.DataFrame({
        "Năm": [r[0] for r in rows], "Kỳ": [r[1] for r in rows],
        "Doanh thu thuần": [r[2] for r in rows],
        "Lợi nhuận sau thuế": [r[2] / 10 for r in rows],
    })
    fa = FundamentalAnalyzer(is_df, None, None)
    rp = fa.get_revenue_profit_trend()
    assert rp["revenue_latest"] == 130               # Q2/2025 là kỳ mới nhất
    assert rp["latest_period"] == "Q2/2025"
    assert rp["compare_period"] == "Q2/2024"
    assert rp["revenue_yoy"] == pytest.approx(30.0)  # 130 vs 100, không phải vs 110 (QoQ)
    assert rp["revenue_growth_basis"].startswith("YoY")
    assert rp["periods"][0] == "Q1/2024"


def test_matrix_format_period_columns_ordered():
    df = pd.DataFrame({
        "item": ["Doanh thu thuần"],
        "Q4/2024": [200.0], "Q1/2025": [110.0], "Q1/2024": [90.0],
    })
    s = FundamentalAnalyzer(df, None, None)._series(df, ["doanh thu"])
    g = growth_vs_prior(s)
    assert g["latest_period"] == "Q1/2025"
    assert g["pct"] == pytest.approx((110 - 90) / 90 * 100)


# ── 5. Định giá theo trung vị ngành ──────────────────────────────────────────
def _ratio(pe, pb, roe=0.18):
    return pd.DataFrame({"Năm": [2025], "Kỳ": [2], "P/E": [pe], "P/B": [pb], "ROE (%)": [roe]})


def test_peer_stats_and_sector_based_valuation():
    assert find_sector_basket("FPT") is not None
    # FOX (FPT Telecom – công ty con) bị loại khỏi nhóm so sánh của FPT (14/10/2026)
    fake = {"CMG": _ratio(20, 3), "FOX": _ratio(99, 4), "SAM": _ratio(14, 4), "ELC": _ratio(30, 2),
            "CTR": _ratio(25, 5), "VGI": _ratio(500, 1)}       # 500 là ngoại lai, bị loại
    stats = compute_peer_stats("FPT", lambda s: fake.get(s, pd.DataFrame()))
    assert "FOX" not in stats["peers"] and any("FOX" in e for e in stats["excluded"])
    assert stats["pe"] == pytest.approx(22.5)                    # median(20,14,30,25)
    assert stats["n_pe"] == 4

    ve = ValuationEngine("FPT", 100_000, ratio_df=_ratio(18, 4.5), peer_stats=stats)
    rel = ve.relative_valuation()
    assert rel["sector_pe"] == pytest.approx(22.5)
    assert "Trung vị" in rel["sector_pe_source"]
    vs = ve.compute_valuation_score()
    assert vs["components"]["pe"]["vs_sector"] == pytest.approx(18 / 22.5, abs=0.01)


def test_valuation_without_peers_reports_missing_not_default():
    # Bước 9: không dùng hệ số mặc định gõ tay (P/E 15) khi thiếu dữ liệu ngành
    rel = ValuationEngine("XYZ", 50_000, ratio_df=_ratio(10, 1)).relative_valuation()
    assert rel["sector_pe"] is None and "pe_fair_value" not in rel
    assert "Thiếu dữ liệu" in rel["sector_pe_source"]


# ── 1. PDF không bịa số ─────────────────────────────────────────────────────
def test_pdf_has_no_fabricated_values_when_data_missing():
    gen = PDFReportGenerator()
    data, a = gen._prepare_data({"symbol": "ABC", "current_price": {"price": 25000}})
    assert a["px"] is None
    # Không có kết quả mô hình → KHÔNG ĐỦ DỮ LIỆU (không suy từ mô hình khác)
    assert a["total"] is None and a["rec"] == "KHÔNG ĐỦ DỮ LIỆU"
    assert a["target"] is None and a["stop"] is None and a["upside"] is None
    assert a["last_roe"] is None and a["fin"].empty
    assert data["news_items"] == [] and data["peers"] == {}
    assert all(v is None for v in a["scores"].values())


def test_pdf_full_pipeline_uses_real_components(sample_ohlcv_df, tmp_path):
    ta = TechnicalAnalyzer(sample_ohlcv_df)
    enriched = ta.compute_all()
    tech_score = ta.compute_technical_score()
    analysis = {
        "symbol": "FPT",
        "current_price": {"price": float(sample_ohlcv_df["close"].iloc[-1])},
        "technical": {"available": True, "data": enriched, "signals": ta.get_signals(), "score": tech_score},
        "opportunity_score": {"composite": {"score": 61, "coverage_pct": 25},
                              "sub_scores": {"technical": tech_score["score"]}},
        "index_history": pd.DataFrame(),
    }
    gen = PDFReportGenerator()
    _, a = gen._prepare_data(analysis)
    tech_rows = dict(a["checks"])[f"3. Kỹ thuật – {tech_score['score']}/100"]
    assert sum(r["pts"] or 0 for r in tech_rows) == tech_score["total_raw"]
    assert a["stop"] is not None                       # có ATR thật -> có cắt lỗ
    pdf = gen.generate(analysis, report_type="test", output_path=str(tmp_path / "t.pdf"))
    assert pdf.startswith(b"%PDF")


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_audit_fixes.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Kiểm thử các lỗi tìm thấy khi rà soát dữ liệu (giá, BCTC, chỉ số)."""
import numpy as np
import pandas as pd

from core import phan_tich_co_ban as fr
from core.du_lieu import fix_unadjusted_gaps

B = 1e9


def _wide(issued=(10 * B, 10 * B, 10 * B)):
    keys = [20230, 20240, 20250]
    return pd.DataFrame({
        "revenue": [100 * B, 120 * B, 140 * B], "cogs": [-60 * B, -70 * B, -80 * B], "gross_profit": [40 * B, 50 * B, 60 * B],
        "net_income": [10 * B, 12 * B, 14.4 * B], "net_income_parent": [10 * B, 12 * B, 14.4 * B],
        "equity": [100 * B, 110 * B, 121 * B], "minority_interest": [0, 0, 0], "total_assets": [200 * B, 220 * B, 240 * B],
        "charter_capital": [10 * B, 11.5 * B, 13.225 * B],          # +15%/năm do cổ phiếu thưởng
        "equity_issued": list(issued), "cfo": [12 * B, 13 * B, 15 * B],
        "current_assets": [80 * B, 90 * B, 100 * B], "current_liabilities": [50 * B, 55 * B, 60 * B],
        "long_term_debt": [5 * B, 5 * B, 5 * B],
    }, index=keys)


def test_eps_growth_ignores_bonus_shares():
    w = _wide(issued=(0, 0, 0))
    r = fr.compute_ratios(w, "year")
    assert abs(r.loc[20250, "eps_growth"] - 20.0) < 1e-6          # LNST mẹ +20%, chỉ có CP thưởng → EPS điều chỉnh +20%
    w2 = _wide(issued=(0, 0, 11 * B))                                # phát hành thu tiền 10% VCSH đầu kỳ
    r2 = fr.compute_ratios(w2, "year")
    assert abs(r2.loc[20250, "eps_growth"] - (1.2 / 1.1 - 1) * 100) < 1e-6


def test_piotroski_issuance_uses_cash_raised():
    ok = fr.piotroski(_wide(issued=(0, 0, 0.5 * B)))                # 0,45% VCSH → không tính là huy động
    bad = fr.piotroski(_wide(issued=(0, 0, 5 * B)))
    name = "Không phát hành thêm cổ phiếu thu tiền"
    assert next(c["pass"] for c in ok["checks"] if c["name"] == name) is True
    assert next(c["pass"] for c in bad["checks"] if c["name"] == name) is False


def test_dilution_risk_distinguishes_bonus_from_issuance():
    from core.khuyen_nghi import assess_risk
    comp = {"type": "nonfinancial", "sector": "technology"}
    bonus = assess_risk(_wide(issued=(0, 0, 0)), None, comp)
    real = assess_risk(_wide(issued=(0, 20 * B, 20 * B)), None, comp)
    cat = lambda res: {i["category"]: i["severity"] for i in res["items"]}  # noqa: E731
    assert cat(bonus).get("Cơ cấu cổ phần") == "Cần theo dõi" and "Pha loãng" not in cat(bonus)
    assert cat(real).get("Pha loãng") in ("Trung bình", "Cao")


def test_drawdown_is_one_year_only():
    from core.khuyen_nghi import assess_risk
    d = pd.bdate_range(end="2026-09-30", periods=600)
    c = np.concatenate([np.linspace(100, 200, 300), np.linspace(120, 100, 300)])   # đỉnh cũ 200 ngoài cửa sổ 1 năm
    px = pd.DataFrame({"timestamp": d, "close": c * 1000, "open": c * 1000, "high": c * 1000, "low": c * 1000, "volume": 1e6})
    res = assess_risk(_wide(), None, {"type": "nonfinancial", "sector": "default"}, price_df=px)
    texts = " ".join(i["text"] for i in res["items"])
    assert "-40%" not in texts and "-50%" not in texts                 # 1 năm: 120 → 100 chỉ −17%


def test_gap_fix_adjusts_unadjusted_bonus_share():
    d = pd.bdate_range("2026-01-01", periods=40)
    c = np.full(40, 100_000.0)
    c[20:] = 100_000 / 1.2                                              # thưởng 20% chưa điều chỉnh, HOSE ±7%
    df = pd.DataFrame({"timestamp": d, "open": c, "high": c, "low": c, "close": c, "volume": 1e6})
    out = fix_unadjusted_gaps(df, "XYZ", band=0.07)
    assert out["close"].pct_change().abs().max() < 1e-9
    assert abs(out["volume"].iloc[0] - 1.2e6) < 1                       # khối lượng điều chỉnh ngược
    assert out.attrs["corporate_action_adjustments"][0]["date"] == str(d[20].date())
    normal = df.copy()
    normal["close"] = np.linspace(100_000, 106_000, 40)
    normal["open"] = normal["close"]
    assert fix_unadjusted_gaps(normal, "XYZ", band=0.07)["close"].equals(normal["close"])   # chuỗi bình thường: không đổi


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_hardening.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Regression tests cho các lớp bảo vệ dữ liệu/UI được bổ sung ở bản hardening."""


import pandas as pd
import pytest

from core.dinh_gia import point_in_time
from giao_dien.chung import safe_external_url, safe_html
from core.tai_lieu_bctc import _read_limited_response, _safe_download_url
from core.thi_truong_danh_muc import ScreenerService


def test_html_and_external_url_are_sanitized():
    assert safe_html('<img src=x onerror="alert(1)">').startswith("&lt;img")
    assert safe_external_url("javascript:alert(1)") == "#"
    assert safe_external_url("https://example.com/a?q=1").startswith("https://example.com/")


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "http://localhost/admin",
    "http://127.0.0.1/private",
    "http://169.254.169.254/latest/meta-data",
])
def test_document_url_rejects_local_targets(url):
    with pytest.raises(ValueError):
        _safe_download_url(url)


def test_document_response_has_hard_size_limit(monkeypatch):
    from core.cau_hinh import settings

    class Response:
        headers = {}

        @staticmethod
        def iter_content(chunk_size):
            yield b"x" * 8
            yield b"y" * 8

    monkeypatch.setattr(settings, "MAX_DOCUMENT_BYTES", 10)
    with pytest.raises(ValueError):
        _read_limited_response(Response())


def test_point_in_time_prefers_actual_release_date():
    wide = pd.DataFrame({"revenue": [100.0]}, index=[20240])
    wide.attrs["available_at"] = {20240: "2025-04-20"}
    before, _, _ = point_in_time(wide, None, None, pd.Timestamp("2025-04-10"))
    after, _, _ = point_in_time(wide, None, None, pd.Timestamp("2025-04-21"))
    assert before.empty
    assert len(after) == 1
    assert after.attrs["point_in_time_basis"] == "actual_release_dates"


def test_screener_rank_normalizes_only_available_metrics():
    df = pd.DataFrame([
        {"symbol": "AAA", "roe": 20, "pe": 10},
        {"symbol": "BBB", "roe": 10, "pe": None},
    ])
    ranked = ScreenerService.rank(df, {"roe": 1, "pe": 1})
    bbb = ranked.set_index("symbol").loc["BBB"]
    assert bbb["coverage_score"] == 50.0
    assert pd.isna(bbb["rank_score"])


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_v2_platform.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Kiểm thử nền tảng v2: nguồn dữ liệu lai ghép, BCTC nhiều nguồn, bộ chuẩn hóa, bộ tính chỉ số,
trích BCTC từ PDF, kho tài liệu, cảnh báo, bộ lọc, Excel, PDF theo mục, an toàn đa luồng.
Mọi dữ liệu là GIẢ LẬP theo đúng định dạng thật của vnstock 4.x – không gọi mạng.
"""
import io
import threading

import numpy as np
import pandas as pd
import pytest

from core import phan_tich_co_ban as fr
from core.du_lieu import DataRepository, merge_financial_sources, stitch_prices, to_vnd
from core.du_lieu import canonicalize, infer_scale
from core.tai_lieu_bctc import extract_financials
from core.nguon_du_lieu import DNSEClient
from core.nguon_du_lieu import VietstockClient
from tests.fakes import FakeDNSE, FakeVietstock, FakeVnstock, kbs_income, price_frame, vci_income
from tests.pdf_samples import make_vas_pdf


# ── Bộ chuẩn hóa BCTC ────────────────────────────────────────────────────────

def test_canonical_vci_matrix_picks_net_revenue_not_growth_row():
    w = canonicalize(vci_income(), "is")
    assert list(w.index) == sorted(w.index)                    # kỳ tăng dần dù nguồn để mới nhất trước
    assert w.loc[20250, "revenue"] == pytest.approx(30_000e9 * 1.15 ** 5)   # dòng "Doanh thu thuần"
    assert w.loc[20250, "net_income_parent"] < w.loc[20250, "net_income"]
    assert "2025_1" not in map(str, w.index)                    # cột trùng bị bỏ


def test_canonical_kbs_ids_and_v3_tabular_units():
    k = canonicalize(kbs_income(), "is")
    assert {"revenue", "net_income", "selling_expense"} <= set(k.columns)
    v3 = pd.DataFrame({"CP": ["FPT"] * 2, "Năm": [2024, 2023], "Kỳ": [5, 5],
                       "Tăng trưởng doanh thu (%)": [0.2, 0.1], "Doanh thu (Tỷ đồng)": [62000, 52000]})
    w = canonicalize(v3, "is")
    assert w.loc[20240, "revenue"] == 62000e9                   # "(Tỷ đồng)" → ×1e9


def test_infer_scale():
    assert infer_scale(pd.DataFrame({"total_assets": [50_000.0]})) == 1e6     # 50.000 triệu = 50 tỷ
    assert infer_scale(pd.DataFrame({"total_assets": [7e13]})) == 1.0


# ── Giá lai ghép DNSE + lịch sử ──────────────────────────────────────────────

def test_to_vnd_scales_stocks_not_indices():
    df = price_frame("2025-01-01", "2025-02-01", base=100.0)
    assert to_vnd(df, "FPT")["close"].median() > 1000
    assert to_vnd(df, "VNINDEX")["close"].median() < 1000


def test_stitch_prices_adjusts_older_segment():
    recent = price_frame("2025-06-01", "2025-08-01", base=100.0, source="dnse")
    older = recent.copy()
    older["close"] = older["close"] / 2          # nguồn cũ chưa điều chỉnh chia tách 2:1
    older = pd.concat([price_frame("2025-01-01", "2025-05-30", base=50.0), older], ignore_index=True)
    out, k = stitch_prices(recent, older)
    assert k == pytest.approx(2.0)
    assert out["timestamp"].is_monotonic_increasing and not out["timestamp"].duplicated().any()
    _, k2 = stitch_prices(recent, recent.copy())
    assert k2 is None


def test_hybrid_price_uses_dnse_recent_and_history_older(fake_repo):
    df = fake_repo.get_price_history("FPT", days=800)
    srcs = [p["source"] for p in df.attrs["provenance"]]
    assert "dnse" in srcs and any(s.startswith("vnstock") for s in srcs)
    assert df[df["source"] == "dnse"]["timestamp"].min() > df[df["source"] != "dnse"]["timestamp"].max()
    assert df["close"].median() > 1000                          # quy về VND


def test_price_falls_back_when_dnse_or_vnstock_fails():
    r = DataRepository(arminer_client=False, vnstock_client=FakeVnstock(), dnse_client=FakeDNSE(fail=True),
                       vietstock_client=FakeVietstock(), use_cache=False)
    assert set(r.get_price_history("FPT", days=100)["source"]) == {"vnstock_vci"}
    r2 = DataRepository(arminer_client=False, vnstock_client=FakeVnstock(fail_price=True), dnse_client=FakeDNSE(fail=True),
                        vietstock_client=FakeVietstock(True), use_cache=False)
    assert set(r2.get_price_history("FPT", days=100)["source"]) == {"vietstock"}


# ── BCTC nhiều nguồn ─────────────────────────────────────────────────────────

def test_financials_merge_sources_and_track_provenance(fake_repo):
    fin = fake_repo.get_financials("FPT", "year", years=10)
    d, s = fin["data"], fin["sources"]
    assert 20190 in d.index and s.loc[20190, "cfo"] == "vietstock"        # Vietstock bù năm VCI không có
    assert s.loc[20250, "revenue"] == "vnstock_vci"
    assert s.loc[20250, "selling_expense"] == "vnstock_kbs"               # KBS bù chỉ tiêu VCI thiếu
    assert all(int(k) % 10 == 0 for k in d.index)                         # chỉ kỳ năm
    assert d.loc[20250, "shares_outstanding"] == 1.2e9                    # từ bảng chỉ số theo quý → năm


def test_financials_fallback_to_kbs_when_vci_missing():
    r = DataRepository(arminer_client=False, vnstock_client=FakeVnstock(fail_vci_fin=True), dnse_client=FakeDNSE(),
                       vietstock_client=FakeVietstock(), pdf_financial_loader=lambda s, p: pd.DataFrame(),
                       use_cache=False)
    fin = r.get_financials("FPT", "year")
    assert set(fin["sources"]["revenue"].dropna()) == {"vnstock_kbs"}


def test_quarter_mode_maps_year_end_balances_to_q4(fake_repo):
    q = fake_repo.get_financials("FPT", "quarter", years=3)["data"]
    assert all(int(k) % 10 > 0 for k in q.index)
    assert pd.notna(q.loc[20254, "total_assets"]) and pd.isna(q.loc[20253].get("total_assets"))


def test_merge_priority():
    a = pd.DataFrame({"x": [1.0, np.nan]}, index=[20240, 20250])
    b = pd.DataFrame({"x": [9.0, 2.0]}, index=[20240, 20250])
    v, s = merge_financial_sources([("A", a), ("B", b)])
    assert v["x"].tolist() == [1.0, 2.0] and s["x"].tolist() == ["A", "B"]


# ── Bộ tính chỉ số từ BCTC ───────────────────────────────────────────────────

@pytest.fixture
def hand_data():
    return pd.DataFrame({
        "revenue": [1000., 1200.], "cogs": [-600., -700.], "gross_profit": [400., 500.], "operating_profit": [150., 200.],
        "profit_before_tax": [140., 190.], "interest_expense": [-10., -10.], "income_tax": [28., 38.],
        "net_income": [112., 152.], "net_income_parent": [100., 140.], "depreciation": [50., 60.],
        "cfo": [130., 180.], "capex": [-40., -60.], "dividends_paid": [-30., -50.],
        "total_assets": [2000., 2400.], "equity": [1000., 1200.], "total_liabilities": [1000., 1200.],
        "current_assets": [800., 1000.], "current_liabilities": [500., 550.], "inventory": [200., 240.],
        "receivables": [150., 180.], "payables": [100., 120.], "cash": [100., 150.],
        "short_term_debt": [200., 220.], "long_term_debt": [300., 280.], "minority_interest": [50., 60.],
        "retained_earnings": [300., 380.], "shares_outstanding": [10., 10.]}, index=[20240, 20250])


def test_ratios_match_hand_calculation(hand_data):
    r = fr.compute_ratios(hand_data, "year").loc[20250]
    assert r["roe"] == pytest.approx(140 / ((950 + 1140) / 2) * 100)       # LNST mẹ / VCSH mẹ bình quân
    assert r["roa"] == pytest.approx(152 / 2200 * 100)
    assert r["gross_margin"] == pytest.approx(500 / 1200 * 100)
    assert r["interest_coverage"] == pytest.approx(20.0)
    assert r["current_ratio"] == pytest.approx(1000 / 550)
    assert r["debt_to_equity"] == pytest.approx(500 / 1200)
    assert r["revenue_growth"] == pytest.approx(20.0)
    assert r["eps"] == pytest.approx(14.0) and r["bvps"] == pytest.approx(114.0)
    assert r["fcf"] == pytest.approx(120.0)


def test_valuation_and_health_scores(hand_data):
    v = fr.valuation_snapshot(hand_data, price=200.0, period="year")
    assert v["pe"] == pytest.approx(200 / 14) and v["pb"] == pytest.approx(200 / 114)
    assert v["enterprise_value"] == pytest.approx(2000 + 500 - 150 + 60)
    z = fr.altman_z(hand_data)
    assert z["score"] == pytest.approx(3.25 + 6.56 * 450 / 2400 + 3.26 * 380 / 2400 + 6.72 * 200 / 2400 + 1.05 * 1.0, abs=0.01)
    p = fr.piotroski(hand_data)
    assert p["max"] == 9 and 0 <= p["score"] <= 9


def test_ttm_requires_four_consecutive_quarters():
    s = pd.Series([1., 2., 3., 4., 5.], index=[20244, 20251, 20252, 20253, 20254])
    t = fr._ttm(s)
    assert pd.isna(t.loc[20252]) and t.loc[20253] == 10.0 and t.loc[20254] == 14.0
    gap = pd.Series([1., 2., 4., 5.], index=[20244, 20251, 20253, 20254])     # thiếu Q2/2025
    assert fr._ttm(gap).isna().all()


# ── PDF BCTC theo mã số VAS ──────────────────────────────────────────────────

def test_pdf_extraction_vas_codes():
    res = extract_financials(make_vas_pdf())
    v = res["values"]
    assert res["unit"] == 1e6 and res["checks"]["balance_identity"] and res["checks"]["assets_equal_sources"]
    assert v["revenue"] == 60_300e6 and v["cogs"] == -37_400e6 and v["interest_expense"] == -720e6
    assert v["total_assets"] == 70_500e6 and v["charter_capital"] == 12_700e6 and v["cfo"] == 11_900e6
    assert v["eps"] == 5986                                    # EPS không nhân đơn vị
    assert v["revenue"] != 999_999e6                           # dòng trong phần thuyết minh bị bỏ qua


def test_document_classification_and_pdf_as_last_source(tmp_path):
    from core.du_lieu import Database
    from core.tai_lieu_bctc import DocumentService, classify_document
    assert classify_document("Báo cáo thường niên 2024")["doc_type"] == "annual_report"
    q = classify_document("Báo cáo tài chính riêng Quý 3 năm 2025")
    assert (q["doc_type"], q["quarter"], q["consolidated"]) == ("fs_quarterly", 3, False)

    db = Database(":memory:")
    ds = DocumentService(db=db, base_dir=tmp_path)
    ds.save_upload("ABC", "BCTC_hop_nhat_2025.pdf", make_vas_pdf(), "fs_annual", 2025)
    wide = ds.pdf_financials("ABC", "year")
    assert wide.loc[20250, "revenue"] == 60_300e6

    r = DataRepository(arminer_client=False, vnstock_client=FakeVnstock(fail_vci_fin=True), dnse_client=FakeDNSE(),
                       vietstock_client=FakeVietstock(), pdf_financial_loader=ds.pdf_financials, use_cache=False)
    fin = r.get_financials("ABC", "year")
    assert fin["sources"].loc[20250, "total_assets"] == "pdf"   # KBS không có CĐKT → lấy từ PDF


# ── Parsers nguồn ────────────────────────────────────────────────────────────

def test_dnse_udf_and_vietstock_parsers():
    df = DNSEClient.parse_udf({"t": [1760054400, 1760140800], "o": [1, 2], "h": [1, 2], "l": [1, 2],
                               "c": [100.5, 101.0], "v": [10, 20]}, "FPT")
    assert list(df["close"]) == [100.5, 101.0] and set(df["source"]) == {"dnse"}
    vs = VietstockClient.parse_financeinfo(
        [[{"YearPeriod": 2024, "TermCode": "N"}, {"YearPeriod": 2023, "TermCode": "N"}],
         {"Kết quả kinh doanh": [{"Name": "Doanh thu thuần", "Value1": 10.0, "Value2": 8.0}]}])
    assert canonicalize(vs, "is").loc[20240, "revenue"] == 10.0


# ── Cảnh báo, bộ lọc, Excel, PDF theo mục, đa luồng ──────────────────────────

def test_alert_conditions_and_evaluate(fake_repo):
    from core.du_lieu import Database
    from core.thi_truong_danh_muc import WatchlistService, check_condition
    assert check_condition("price_above", 100, 120, None, None) is True
    assert check_condition("rsi_below", 30, None, None, None) is None
    ws = WatchlistService(repo=fake_repo, db=Database(":memory:"))
    ws.add("FPT")
    ws.add_alert("FPT", "price_above", 1000)       # giá giả lập ~105.000đ → kích hoạt
    ws.add_alert("FPT", "price_below", 1)          # không kích hoạt
    hit = ws.evaluate()
    assert len(hit) == 1 and hit[0]["price"] > 1000
    assert ws.alerts(active_only=True)["condition"].tolist() == ["price_below"]


def test_screener_filters_and_rank():
    from core.thi_truong_danh_muc import ScreenerService
    df = pd.DataFrame({"symbol": ["A", "B", "C"], "pe": [8, 25, -5], "roe": [20, 10, 30], "revenue_growth": [5, 30, None]})
    f = ScreenerService.apply_filters(df, [("pe", "<=", 15), ("roe", ">=", 15)])
    assert f["symbol"].tolist() == ["A", "C"]                # C: P/E âm vẫn ≤ 15 nhưng bị phạt khi xếp hạng
    ranked = ScreenerService.rank(df, {"pe": 1, "roe": 1})
    # A: P/E rẻ nhất (1.0) + ROE 2/3 → 83.3 · C: P/E âm bị coi 0 + ROE cao nhất → 50 · B → 41.7
    assert ranked["symbol"].tolist() == ["A", "C", "B"]
    assert ranked.set_index("symbol")["rank_score"].to_dict() == pytest.approx({"A": 83.3, "C": 50.0, "B": 41.7})


def test_excel_and_pdf_sections(fake_repo, tmp_path):
    import openpyxl
    from core.bao_cao_pdf import export_financials
    from core.bao_cao_pdf import PDFReportGenerator
    from core.pipeline import StockService
    svc = StockService("FPT", days=500, repository=fake_repo)
    wb = openpyxl.load_workbook(io.BytesIO(export_financials("FPT", svc.get_financials(), svc.financial_summary())))
    assert {"KQKD", "CDKT", "LCTT", "Chi_so", "Nguon_du_lieu"} <= set(wb.sheetnames)
    a = svc.full_analysis()
    gen = PDFReportGenerator()
    full = gen.generate(a, "full", output_path=str(tmp_path / "f.pdf"))
    part = gen.generate(a, "x", output_path=str(tmp_path / "p.pdf"), sections=["summary", "ratios"])
    from pypdf import PdfReader
    assert len(PdfReader(io.BytesIO(full)).pages) > len(PdfReader(io.BytesIO(part)).pages)
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(part)).pages)
    up = text.upper()
    assert "CHỈ SỐ TÀI CHÍNH" in up and "BÁO CÁO TÀI CHÍNH NHIỀU NĂM" not in up


def test_database_is_thread_safe():
    from core.du_lieu import Database
    db = Database(":memory:")
    errors = []

    def work(i):
        try:
            for j in range(20):
                db.add_watch(f"S{i}{j}")
                db.get_watchlist()
        except Exception as exc:     # pragma: no cover
            errors.append(exc)

    ts = [threading.Thread(target=work, args=(i,)) for i in range(6)]
    [t.start() for t in ts]
    [t.join(30) for t in ts]
    assert not errors and len(db.get_watchlist()) == 120


def test_duplicate_source_columns_are_tolerated():
    df = vci_income()
    dup = pd.concat([df, df[["2025"]]], axis=1)          # tên cột "2025" xuất hiện 2 lần
    w = canonicalize(dup, "is")
    assert w.loc[20250, "revenue"] == pytest.approx(30_000e9 * 1.15 ** 5)


def test_one_failing_section_does_not_break_full_analysis(fake_repo, monkeypatch):
    from core.pipeline import StockService
    svc = StockService("FPT", days=400, repository=fake_repo)
    monkeypatch.setattr(svc, "get_peer_stats", lambda: (_ for _ in ()).throw(ValueError("boom")))
    a = svc.full_analysis()
    assert "peers" in a["errors"] and "boom" in a["errors"]["peers"]
    assert a["technical"]["available"] and a["financial_summary"]["ratios"] is not None


def test_vci_ratio_quarterly_columns_labelled_by_year_only():
    """Lỗi thật: bảng chỉ số VCI có 16 cột quý nhưng nhãn chỉ ghi năm → 'Length of values (16)...'."""
    cols = [str(y) for y in (2025, 2024, 2023, 2022) for _ in range(4)]      # "2025" ×4, "2024" ×4 ...
    raw = pd.DataFrame([["Số CP lưu hành", "Outstanding shares", "outstanding_share"] + [1.2e9] * 16,
                        ["P/E", "P/E", "pe"] + list(range(16))],
                       columns=["item", "item_en", "item_id"] + cols)
    w = canonicalize(raw, "ratio")
    assert list(w.index) == [20220, 20230, 20240, 20250]
    assert w.loc[20250, "shares_outstanding"] == 1.2e9
    r = DataRepository(arminer_client=False, vnstock_client=FakeVnstock(), dnse_client=FakeDNSE(), vietstock_client=FakeVietstock(),
                       pdf_financial_loader=lambda s, p: pd.DataFrame(), use_cache=False)
    r._vnstock.get_financial_statement = (lambda sym, st, period="year", source=None:
                                          raw if st == "ratio" else FakeVnstock().get_financial_statement(sym, st, period, source))
    assert not r.get_financials("FPT", "year")["data"].empty


def test_degenerate_period_labels_are_ignored_and_displayable():
    from giao_dien.chung import unique_columns
    raw = pd.DataFrame([["Số CP lưu hành", None, "outstanding_share"] + [1.2e9] * 16],
                       columns=["item", "item_en", "item_id"] + ["2018"] * 16)
    assert canonicalize(raw, "ratio").empty                       # không gán nhầm vào năm 2018
    shown = unique_columns(raw)
    assert not shown.columns.duplicated().any() and shown.shape == raw.shape


def test_pdf_cover_page(fake_repo, tmp_path):
    from pypdf import PdfReader
    from core.bao_cao_pdf import render_cover, short_company_name
    from core.bao_cao_pdf import PDFReportGenerator
    from core.pipeline import StockService
    assert short_company_name("Công ty Cổ phần FPT", "FPT") == "CTCP FPT"
    assert render_cover("VCB", "Ngân hàng TMCP Ngoại thương Việt Nam").startswith(b"\xff\xd8")   # JPEG
    a = StockService("FPT", days=400, repository=fake_repo).full_analysis()
    gen = PDFReportGenerator()
    with_cover = gen.generate(a, "x", output_path=str(tmp_path / "c.pdf"), sections=["summary"])
    no_cover = gen.generate(a, "x", output_path=str(tmp_path / "n.pdf"), sections=["summary"], cover=False)
    pc, pn = PdfReader(io.BytesIO(with_cover)).pages, PdfReader(io.BytesIO(no_cover)).pages
    assert len(pc) == len(pn) + 1
    assert "STOCK ANALYTICS" not in (pc[0].extract_text() or "")   # bìa là ảnh, không có đầu trang
    assert "Trang 2/" in pc[1].extract_text()


def test_cafef_cdn_link_fix(tmp_path):
    from core.tai_lieu_bctc import DocumentService, normalize_doc_url
    bad = "https://cafefnew.mediacdn.vn/Images/Uploaded/DuLieuDownload/BCTC/X_2025.pdf"
    good = "https://cafef1.mediacdn.vn/Images/Uploaded/DuLieuDownload/BCTC/X_2025.pdf"
    assert normalize_doc_url(bad) == good
    assert normalize_doc_url("https://acb.com.vn/bctn.pdf") == "https://acb.com.vn/bctn.pdf"

    class R:
        def __init__(self, code, body): self.status_code, self.content = code, body

    class S:
        calls = []
        def get(self, url, timeout=60, **kw):      # tải theo luồng (stream=True)
            S.calls.append(url)
            return R(200, b'{"serving_error_003": "File not found"}') if "cafefnew" in url else R(200, b"%PDF-1.4 ok")

    ds = DocumentService.__new__(DocumentService)
    ds.session = S()
    ds._dir = lambda sym: tmp_path
    class DB:
        def upsert_document(self, d): self.d = d
    ds.db = DB()
    p = ds.download({"url": bad, "doc_id": "abc", "symbol": "ACB", "year": 2025, "doc_type": "fs_annual"})
    assert p is not None and p.read_bytes().startswith(b"%PDF") and S.calls[0] == good


def test_vietstock_static_annual_reports():
    from core.tai_lieu_bctc import VietstockStaticDocs, classify_document

    class R:
        def __init__(self, ok): self.status_code, self._ok = (200 if ok else 404), ok
        def iter_content(self, n): yield (b"%PDF-1.7" if self._ok else b"<html>")
        def close(self): pass

    class S:
        def get(self, url, timeout=8, stream=False):
            return R("/HOSE/" in url and ("_2023.pdf" in url or "_2024.pdf" in url))

    links = VietstockStaticDocs(S()).list("ACB", {"exchange": "VNINDEX"})
    assert sorted(t for t, _ in links) == ["Báo cáo thường niên năm 2023", "Báo cáo thường niên năm 2024"]
    meta = classify_document(*links[0])
    assert meta["doc_type"] == "annual_report" and meta["year"] in (2023, 2024)


def test_uploaded_doc_without_url_lists_and_renders(tmp_path):
    """File tải lên không có link (url = NULL/NaN) không được làm hỏng danh sách tài liệu."""
    from core.du_lieu import Database
    from core.tai_lieu_bctc import DocumentService
    ds = DocumentService(db=Database(":memory:"), base_dir=tmp_path)
    ds.save_upload("ACB", "ACB_BCTN_2024.pdf", b"%PDF-1.4 test", doc_type="annual_report", year=2024)
    ds.db.upsert_document({"doc_id": "x1", "symbol": "ACB", "year": 2025, "doc_type": "fs_annual",
                           "title": "BCTC 2025", "source": "cafef",
                           "url": "https://cafefnew.mediacdn.vn/Images/Uploaded/DuLieuDownload/BCTC/a.pdf"})
    df = ds.list_documents("ACB")
    assert len(df) == 2
    up = df[df["source"] == "upload"].iloc[0]
    assert up["url"] is None and up["downloaded"]
    assert df[df["source"] == "cafef"].iloc[0]["url"].startswith("https://cafef1.mediacdn.vn/")


def test_offline_arminer_source_fills_history():
    """Nguồn BCTC đóng gói sẵn: số liệu FPT 2025 khớp BCTC thật, có lịch sử từ 2009, ngân hàng nhận đúng chỉ tiêu."""
    from core.du_lieu import canonicalize
    from core.nguon_du_lieu import ArminerClient
    c = ArminerClient()
    assert c.available()
    is_fpt = canonicalize(c.get_financial_statement("FPT", "income_statement"), "is", unit_factor=1.0)
    assert is_fpt.loc[20250, "revenue"] == pytest.approx(70_112.8e9, rel=1e-3)
    assert is_fpt.loc[20250, "gross_profit"] == pytest.approx(25_888.5e9, rel=1e-3)
    assert is_fpt.index.min() <= 20110          # lịch sử từ 2011
    bank = canonicalize(c.get_financial_statement("ACB", "balance_sheet"), "bs", unit_factor=1.0)
    assert {"customer_loans", "customer_deposits", "total_assets"} <= set(bank.columns)
    assert c.get_financial_statement("FPT", "income_statement", period="quarter").empty


def test_repository_uses_offline_source_when_online_missing():
    from core.du_lieu import DataRepository
    from tests.fakes import FakeDNSE, FakeVietstock, FakeVnstock

    class NoFin(FakeVnstock):
        def get_financial_statement(self, *a, **k):
            return pd.DataFrame()
    r = DataRepository(vnstock_client=NoFin(), dnse_client=FakeDNSE(), vietstock_client=FakeVietstock(False),
                       pdf_financial_loader=lambda s, p: pd.DataFrame(), use_cache=False)
    res = r.get_financials("HPG", "year", years=20)
    assert not res["data"].empty and "arminer" in set(res["sources"].stack().unique())


def test_zenodo_remote_zip_extraction(tmp_path):
    """Rút đúng 1 file PDF trong ZIP từ xa qua HTTP Range (máy chủ giả lập có hỗ trợ Range)."""
    import http.server
    import threading
    import zipfile as zf_mod
    from core import tai_lieu_bctc as zs

    zpath = tmp_path / "vn_bctn_2021_2025.zip"
    with zf_mod.ZipFile(zpath, "w") as z:
        z.writestr("full_data/ACB/ACB_24CN_BCTN.pdf", b"%PDF-1.7 ACB 2024" + b"x" * 300_000)
        z.writestr("full_data/FPT/FPT_24CN_BCTN.pdf", b"%PDF-1.7 FPT 2024")
    data = zpath.read_bytes()
    hits = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            rng = self.headers.get("Range", "")
            a, b = rng.replace("bytes=", "").split("-")
            a, b = int(a), min(int(b), len(data) - 1)
            hits.append((a, b))
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {a}-{b}/{len(data)}")
            self.send_header("Content-Length", str(b - a + 1))
            self.end_headers()
            self.wfile.write(data[a:b + 1])

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}/files"
        pdf = zs.fetch_pdf("2021_2025", "FPT/FPT_24CN_BCTN.pdf", base_url=base)
        assert pdf == b"%PDF-1.7 FPT 2024"
        assert sum(b - a + 1 for a, b in hits) < len(data) * 3      # không tải lặp cả kho
    finally:
        srv.shutdown()
    reports = zs.list_reports("ACB")
    assert reports and reports[0]["year"] >= 2020 and reports[0]["relative_path"].startswith("ACB/")
    assert zs.parse_url(zs.make_url("2021_2025", "ACB/x.pdf")) == ("2021_2025", "ACB/x.pdf")


def test_vci_profit_loss_labels_not_excluded_as_ratio():
    """Nhãn 'Lãi/Lỗ…', 'LN trước thuế', 'Lợi nhuận thuần' (VCI) phải được nhận – dấu '/' không phải tỷ số."""
    from core.du_lieu import canonicalize
    rows = [("Doanh thu thuần", "Net Revenue", 100), ("Lãi/Lỗ từ hoạt động kinh doanh", "Operating Profit/Loss", 20),
            ("LN trước thuế", "Profit before tax", 19), ("Lợi nhuận thuần", "Net Profit For the Year", 15),
            ("Cổ đông của Công ty mẹ", "Attributable to parent company", 13), ("Tăng trưởng lợi nhuận (%)", "Profit growth", 9)]
    df = pd.DataFrame([{"item": a, "item_en": b, "item_id": "", "2025": v * 1e9} for a, b, v in rows])
    out = canonicalize(df, "is")
    r = out.loc[20250] if 20250 in out.index else out[20250]
    assert r["operating_profit"] == 20e9 and r["profit_before_tax"] == 19e9
    assert r["net_income"] == 15e9 and r["net_income_parent"] == 13e9


def test_profit_loss_slash_labels_and_tax_not_confused_with_pbt():
    """'Lợi nhuận/(lỗ) …' (mẫu VAS) và BCTC CTCK: thuế TNDN không được nhận nhầm dòng LN trước thuế."""
    from core.du_lieu import canonicalize
    rows = [("Doanh thu thuần về bán hàng và cung cấp dịch vụ", 100), ("Lợi nhuận/(lỗ) thuần từ hoạt động kinh doanh", 20),
            ("Tổng lợi nhuận kế toán trước thuế thu nhập doanh nghiệp", 19), ("Chi phí thuế thu nhập doanh nghiệp", 4),
            ("Lợi nhuận/(lỗ) sau thuế thu nhập doanh nghiệp", 15), ("Lợi nhuận sau thuế phân bổ cho chủ sở hữu", 13)]
    df = pd.DataFrame([{"item": a, "item_en": "", "item_id": "", "2025": v * 1e9} for a, v in rows])
    r = canonicalize(df, "is").loc[20250]
    assert (r["operating_profit"], r["profit_before_tax"], r["income_tax"], r["net_income"], r["net_income_parent"]) == \
        (20e9, 19e9, 4e9, 15e9, 13e9)
