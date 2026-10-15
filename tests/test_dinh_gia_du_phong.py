"""
tests/test_dinh_gia_du_phong.py – kiểm thử, gộp từ 11 file (15/10/2026).

MỤC LỤC
  • tests/test_investment_model.py – Kiểm thử Khuyến nghị đầu tư & Giá mục tiêu 12 tháng (Financial Health / Valuation / Risk / Recommendation / Backtest).
      hàm/lớp chính: make_wide, make_bank, make_prices, value, health_of, test_lin_score_direction_and_clip, test_health_nonfinancial_groups_weights_and_explain, test_health_custom_weights_change_score, test_health_negative_eps_previous_year_skips_growth, test_health_negative_equity_scores_zero_leverage, test_health_missing_data_no_misleading_total, test_health_bank_model …
  • tests/test_valuation.py – Unit tests for ValuationEngine (định giá tương đối – snapshot).
      hàm/lớp chính: test_relative_valuation_without_peers_has_no_default_multiple, test_relative_valuation_uses_real_peer_median, test_dcf_valuation_removed
  • tests/test_hybrid_valuation.py – Kiểm thử Bước 7 – Hybrid Valuation (Forecast Engine → Valuation Engine).
      hàm/lớp chính: val, fc, test_profile_selection, test_profile_weights_are_documented_and_default_unchanged, test_methods_use_forecast_inputs_and_period_labels, test_fair_value_today_vs_target_consistent, test_dcf_discounts_dated_flows_from_valuation_date, test_weights_follow_profile_and_sum_to_one, test_bank_uses_only_pb_pe, test_scenarios_ordered, test_missing_capex_blocks_dcf_not_zero, test_missing_growth_history_blocks_all_forward_methods …
  • tests/test_valuation_step8.py – Kiểm thử Bước 8 – kiểm chứng Hybrid Valuation: số CP cùng cơ sở thị giá (lỗi đã xác nhận & sửa), kiểm tra chuỗi giá
      hàm/lớp chính: test_stale_share_count_inflates_absolute_value_methods, test_latest_shares_prefers_latest_published_quarter, test_latest_shares_point_in_time, test_price_series_check_flags_unadjusted_split, test_price_series_check_ignores_normal_and_quarterly, test_unadjusted_price_warning_in_valuation
  • tests/test_valuation_step9.py – Kiểm thử Bước 9 – nâng cấp định giá (Hybrid):
      hàm/lớp chính: run, method, with_financial_income, test_core_ebit_excludes_financial_income_and_associates, test_dcf_unchanged_when_interest_income_rises_but_deposits_do_not, test_more_financial_assets_raise_equity_value_exactly, test_missing_core_ebit_excludes_dcf_and_ev_not_total_ebit, test_bridge_uses_latest_published_quarter_not_unpublished, test_cyclical_full_normalization_5_years, test_cyclical_3_to_4_years_caps_confidence_medium, test_cyclical_under_3_years_drops_pe_ev_and_low_confidence, test_peer_group_under_3_uses_own_history_only …
  • tests/test_valuation_round4.py – 15/10/2026 – hiệu chỉnh định giá theo chẩn đoán (tools/valuation_diag.py): cổ tức tiền mặt trong giá quá khứ, bội số
      hàm/lớp chính: test_recency_weighted_multiple, test_blume_beta, test_two_stage_justified_pb_and_roe_term, test_classification_securities_insurance_and_airline, test_cash_dividend_basis_backtest, test_cash_dividend_not_applied_when_series_unadjusted, test_cash_dividend_fallback_from_cashflow
  • tests/test_valuation_fixes.py – Kiểm thử các sửa lỗi sau kiểm toán định giá (L1 beta, L2 EBITDA, L3 ghép kỳ năm, L5 DCF cũ).
      hàm/lớp chính: align, test_flow_items_sum_four_quarters, test_flow_items_incomplete_year_not_created, test_flow_item_missing_one_quarter_left_blank, test_stock_items_take_q4_only, test_annual_rows_from_source_take_priority, test_unknown_basis_never_summed_into_year, test_eps_not_summed_into_year, test_quarter_mode_unchanged, test_detect_discrete_by_shape, test_detect_cumulative_by_shape_and_decumulate, test_detect_cumulative_by_annual_crosscheck …
  • tests/test_financial_forecast.py – Kiểm thử Forecast Engine (analytics/financial_forecast.py).
      hàm/lớp chính: nonfin, run_test_financial_forecast, test_nonfinancial_year1_formulas_exact, test_growth_fades_to_terminal_growth_and_horizon, test_scenarios_ordered_and_explained, test_valuation_inputs_schema, test_ntm_interpolation, quarters, test_build_ttm_requires_four_consecutive_quarters, test_ttm_base_used_when_newer_and_discrete, test_ttm_not_used_when_quarter_basis_unknown, test_annual_not_released_is_excluded …
  • tests/test_forecast_step6.py – Kiểm thử hồi quy Bước 6 – hiệu chỉnh Forecast Engine (co tăng trưởng, neo biên/tỷ lệ kỳ gốc, khoảng kịch bản theo
      hàm/lớp chính: test_growth_shrink_toward_terminal_growth, test_consistent_grower_shrinks_less, test_bank_growth_not_shrunk, test_margin_anchored_to_base_and_reverts_to_long_run, test_ratio_anchor_uses_base_tax_rate, test_scenarios_use_calibrated_group_bands, test_cyclical_group_detected_from_published_data_only, test_ntm_and_fy1_are_distinct_and_labelled, test_ntm_equals_fy1_when_window_matches_fiscal_year, test_ntm_roe_uses_ntm_window_equity, test_path_value_does_not_guess_missing_endpoint, test_ntm_interpolation_validated_on_real_vietcap_ttm …
  • tests/test_review_round1.py – Đợt 1 sửa theo nhận xét báo cáo FPT (14/10/2026): chất lượng lợi nhuận, số CP hiện hành, cổ tức công bố,
      hàm/lớp chính: fpt_wide, test_earnings_quality_flags_fpt_2025, test_health_uses_core_growth_and_quality_penalty, test_snapshot_uses_current_share_count, test_parse_dividends_percent_and_value, test_bear_capped_at_current_multiple_and_confidence_rules, test_dcf_sensitivity_grid, test_detect_scope_change_fpt_2026, test_scope_change_blocks_revenue_based_methods, test_share_and_cash_dividend_events, test_bonus_shares_applied_after_listed_count, test_source_conflict_rejects_mislabeled_quarters …
  • tests/test_review_gk.py – Sửa theo file góp ý GK (BÀI GK – GPM1, 15/10/2026): EPS/BVPS điều chỉnh cùng mẫu số, điểm Định giá dự phòng,
      hàm/lớp chính: test_adjusted_eps_matches_valuation_eps, test_no_adjustment_when_shares_constant, test_fallback_valuation_score_uses_history_and_profile, test_weighted_median_by_market_cap, test_mdd_one_year_window_in_risk_pillar

Tên trùng giữa các phần đã được đổi (tên cũ → tên mới trong file này):
  test_valuation_step8._val → _val_test_valuation_step8
  test_valuation_round4.T → T_test_valuation_round4
  test_valuation_fixes._quarters → _quarters_test_valuation_fixes
  test_financial_forecast.run → run_test_financial_forecast
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_investment_model.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Kiểm thử Khuyến nghị đầu tư & Giá mục tiêu 12 tháng (Financial Health / Valuation / Risk / Recommendation / Backtest).
Dữ liệu ở đây là dữ liệu TỔNG HỢP cho kiểm thử (không dùng ở production).
"""


import numpy as np
import pandas as pd
import pytest

from core import phan_tich_co_ban as fr
from core.phan_tich_co_ban import FinancialHealthEngine, lin_score
from core.khuyen_nghi import assess_risk
from core.dinh_gia import NOT_ENOUGH, ValuationEngine12M, annual_available, point_in_time
from core.cau_hinh import classify_company, load_config

SHARES = 1_000_000_000          # 1 tỷ CP (vốn điều lệ 10.000 tỷ)
NONFIN = {"type": "nonfinancial", "sector": "default"}
BANK = {"type": "bank", "sector": "default"}


def make_wide(years=range(2018, 2026), rev0=20_000e9, g=0.12, margin=0.12, cfo_ratio=1.1, loss_years=(),
              neg_cfo_years=(), equity_override=None, debt=4_000e9, div_ratio=0.4):
    rows = {}
    for i, y in enumerate(years):
        rev = rev0 * (1 + g) ** i
        ni = rev * margin * (-1 if y in loss_years else 1)
        eq = 15_000e9 * (1 + g) ** i if equity_override is None else equity_override
        cfo = (-abs(ni) * 0.5) if y in neg_cfo_years else abs(ni) * cfo_ratio
        rows[y * 10] = {
            "revenue": rev, "gross_profit": rev * 0.3, "operating_profit": ni * 1.25, "profit_before_tax": ni * 1.25,
            "income_tax": abs(ni) * 0.25, "net_income": ni, "net_income_parent": ni, "interest_expense": debt * 0.07,
            "depreciation": rev * 0.03, "cash": 3_000e9, "short_term_investments": 1_000e9, "inventory": rev * 0.08,
            "receivables": rev * 0.1, "current_assets": rev * 0.5, "current_liabilities": rev * 0.3,
            "total_assets": eq + debt + rev * 0.3, "equity": eq, "minority_interest": 0.0,
            "short_term_debt": debt * 0.6, "long_term_debt": debt * 0.4, "charter_capital": SHARES * 10_000,
            "retained_earnings": eq * 0.3, "cfo": cfo, "capex": -rev * 0.04,
            "dividends_paid": -abs(ni) * div_ratio if ni > 0 else 0.0,
        }
        # không có thu nhập tài chính → EBIT cốt lõi (LN gộp − CPBH − CPQL) = EBIT toàn phần = LNTT + lãi vay
        sga = rev * 0.3 - (ni * 1.25 + debt * 0.07)
        rows[y * 10].update(selling_expense=-sga * 0.7, admin_expense=-sga * 0.3, long_term_investments=0.0)
    return pd.DataFrame.from_dict(rows, orient="index").sort_index()


def make_bank(years=range(2018, 2026)):
    rows = {}
    for i, y in enumerate(years):
        toi = 20_000e9 * 1.12 ** i
        ni = toi * 0.45
        eq = 50_000e9 * 1.15 ** i
        ta = eq * 11
        rows[y * 10] = {"total_operating_income": toi, "net_interest_income": toi * 0.8, "net_income": ni,
                        "net_income_parent": ni, "provision_expense": -toi * 0.12, "equity": eq, "total_assets": ta,
                        "customer_loans": ta * 0.65, "customer_deposits": ta * 0.72, "charter_capital": 3e9 * 10_000,
                        "dividends_paid": -ni * 0.15}
    return pd.DataFrame.from_dict(rows, orient="index").sort_index()


def make_prices(wide, pe=14.0, start="2018-01-02", end="2026-10-09", shares=SHARES, noise=0.0):
    """Giá đóng cửa: P/E cuối năm ≈ `pe` (giá đi ngang trong năm). Dùng để có bội số lịch sử."""
    d = pd.bdate_range(start, end)
    eps = {int(k) // 10: wide.loc[k, "net_income_parent"] / shares for k in wide.index}
    last = max(eps)
    vals = [abs(eps.get(x.year, eps[min(max(x.year, min(eps)), last)])) * pe for x in d]
    s = np.array(vals) * (1 + noise * np.sin(np.arange(len(d)) / 30))
    return pd.DataFrame({"timestamp": d, "close": s, "volume": 2e6})


def value(wide, price=None, company=NONFIN, prices="auto", peers=None, as_of=None, cfg=None, beta=1.0):
    ratios = fr.compute_ratios(wide, "year")
    px = make_prices(wide) if isinstance(prices, str) else prices
    shares = float(fr.shares_series(wide).dropna().iloc[-1])
    if price is None:
        price = float(px["close"].iloc[-1]) if px is not None else None
    return ValuationEngine12M(cfg).value(price=price, price_date=pd.Timestamp("2026-10-09"), wide=wide, ratios=ratios,
                                         shares=shares, company=company, beta=beta, peers=peers or {}, price_df=px,
                                         as_of=as_of)


def health_of(wide, company=NONFIN):
    return FinancialHealthEngine().score(fr.compute_ratios(wide, "year"), wide, company)


# ─────────────────────────── Financial Health ────────────────────────────────

def test_lin_score_direction_and_clip():
    assert lin_score(20, 5, 20) == 100 and lin_score(5, 5, 20) == 0 and lin_score(12.5, 5, 20) == 50
    assert lin_score(0.3, 2.0, 0.3) == 100          # thấp là tốt
    assert lin_score(None, 0, 1) is None and lin_score(float("nan"), 0, 1) is None


def test_health_nonfinancial_groups_weights_and_explain():
    h = health_of(make_wide())
    assert h["available"] and 0 <= h["score"] <= 100
    assert [g["key"] for g in h["groups"]] == ["profitability", "growth", "liquidity", "leverage", "cashflow"]
    assert sum(g["weight"] for g in h["groups"]) == 100
    assert all(m["explain"] for g in h["groups"] for m in g["metrics"])


def test_health_custom_weights_change_score():
    w = make_wide()
    base = health_of(w)["score"]
    cfg = load_config({"health": {"weights": {"nonfinancial": {"profitability": 100, "growth": 0, "liquidity": 0,
                                                               "leverage": 0, "cashflow": 0}}}})
    prof = next(g["score"] for g in health_of(w)["groups"] if g["key"] == "profitability")
    s2 = FinancialHealthEngine(cfg).score(fr.compute_ratios(w, "year"), w, NONFIN)["score"]
    assert s2 == pytest.approx(prof, abs=0.11) and s2 != base


def test_health_negative_eps_previous_year_skips_growth():
    h = health_of(make_wide(loss_years=(2024,)))
    growth = next(g for g in h["groups"] if g["key"] == "growth")
    assert [m["key"] for m in growth["metrics"]] == ["revenue_growth"]
    assert any("LNST năm trước" in n for n in h["notes"])


def test_health_negative_equity_scores_zero_leverage():
    h = health_of(make_wide(equity_override=-1_000e9))
    de = next(m for g in h["groups"] for m in g["metrics"] if m["key"] == "debt_to_equity")
    assert de["score"] == 0


def test_health_missing_data_no_misleading_total():
    w = make_wide()[["revenue", "net_income", "net_income_parent", "equity", "total_assets", "charter_capital"]]
    h = health_of(w)
    assert h["score"] is None and h["available"] is False and h["coverage"] < 0.7
    assert h["partial_score"] is not None and h["missing"]


def test_health_bank_model():
    h = health_of(make_bank(), BANK)
    assert {g["key"] for g in h["groups"]} == {"profitability", "growth", "capital", "asset_quality", "funding"}
    assert h["score"] is not None


def test_classify_company():
    assert classify_company("Ngân hàng")["type"] == "bank"
    assert classify_company("Dịch vụ tài chính", "Chứng khoán")["type"] == "securities"
    assert classify_company("Bảo hiểm phi nhân thọ")["type"] == "insurance"
    assert classify_company("Thép")["sector"] == "materials"
    assert classify_company("", bank_flag=True)["type"] == "bank"


# ─────────────────────────── Valuation ───────────────────────────────────────

def test_valuation_nonfinancial_all_methods_and_combination():
    v = value(make_wide())
    keys = {m["key"] for m in v["methods"]}
    assert {"pe", "pb", "dcf", "ev_ebitda"} <= keys
    assert v["status"] == "OK" and v["available"]
    assert sum(m["weight"] for m in v["methods"]) == pytest.approx(1.0)
    assert v["target_12m"] == pytest.approx(sum(m["fair"] * m["weight"] for m in v["methods"]))
    assert v["scenarios"]["bear"]["target"] < v["scenarios"]["base"]["target"] < v["scenarios"]["bull"]["target"]
    assert v["price_date"] == "2026-10-09" and v["data_date"] == "31/12/2025" and v["horizon_months"] == 12
    assert all(m["source"] for m in v["methods"]) and v["assumptions"]["ke"] == pytest.approx(0.12)


def test_valuation_dividend_counted_once():
    v = value(make_wide())
    assert v["dividends_included"] and v["expected_dividend"] > 0
    assert v["expected_return"] == pytest.approx(v["upside"] + v["expected_dividend"] / v["price"] * 100)


def test_valuation_negative_eps_disables_pe():
    # Doanh nghiệp KHÔNG chu kỳ (tắt nhận diện chu kỳ): EPS dự báo âm → loại P/E
    w = make_wide(loss_years=(2024, 2025))
    v = value(w, price=50_000, cfg=load_config({"forecast": {"cyclical": {"cv_threshold": 99}}}))
    assert v["profile"]["key"] == "default"
    assert "pe" not in {m["key"] for m in v["methods"]}
    assert any(m == "P/E" for m, _ in v["invalid"])


def test_cyclical_losses_use_normalized_eps_for_pe():
    # Bước 9: cùng dữ liệu nhưng được nhận diện là chu kỳ (biên biến động mạnh) → P/E áp trên EPS CHUẨN HÓA giữa
    # chu kỳ (doanh thu NTM × biên ròng trung vị 5 năm), không dùng EPS năm lỗ
    w = make_wide(loss_years=(2024, 2025))
    v = value(w, price=50_000)
    assert v["profile"]["key"] == "cyclical_manufacturing" and v["cycle_normalization"]["years"] == 5
    pe = next(m for m in v["methods"] if m["key"] == "pe")
    assert "chuẩn hóa chu kỳ" in pe["base_label"] and pe["base"] > 0


def test_valuation_financial_firm_uses_pb_pe_only():
    w = make_bank()
    v = value(w, company=BANK)
    assert {m["key"] for m in v["methods"]} <= {"pb", "pe"} and v["methods"]
    assert not any(m in ("DCF", "EV/EBITDA") for m, _ in v["invalid"])
    assert v["weights"].get("pb", 0) > v["weights"].get("pe", 0)


def test_valuation_missing_industry_data_still_uses_history():
    v = value(make_wide(), peers={})
    assert all("ngành" not in m["source"] for m in v["methods"] if m["key"] == "pe")
    v2 = value(make_wide(), peers={"pe": 18.0, "pb": 3.0, "n": 5, "group": "Test"})
    assert any("P/E ngành" in m["source"] for m in v2["methods"] if m["key"] == "pe")


def test_valuation_missing_price():
    v = value(make_wide(), price=None, prices=None)
    assert v["status"] == NOT_ENOUGH and v.get("upside") is None and v.get("target_12m") is None


def test_valuation_wacc_not_determinable():
    cfg = load_config({"valuation": {"terminal_growth": {"bear": 0.10, "base": 0.10, "bull": 0.10}}})
    v = value(make_wide(), cfg=cfg)
    assert "dcf" not in {m["key"] for m in v["methods"]}
    assert any(m == "DCF" and "WACC" in r for m, r in v["invalid"])
    # Bước 7: DCF dùng FCFF của Forecast Engine (EBIT(1−t) + KH − capex − ΔVLĐ), không còn cần CFO;
    # thiếu capex là khoảng trống dữ liệu mức 'cao' → DCF bị loại, không thay bằng 0.
    w = make_wide().drop(columns=["capex"])
    assert any(m == "DCF" and "capex" in r for m, r in value(w)["invalid"])


def test_valuation_invalid_fair_value_rejected():
    v = value(make_wide(), price=500.0)            # kết quả gấp > 4 lần thị giá → bất thường, loại
    assert not v["methods"] and v["status"] == NOT_ENOUGH
    assert any("bất thường" in r for _, r in v["invalid"])
    v2 = value(make_wide(debt=5e15))                # nợ ròng khổng lồ → VCSH ước tính ≤ 0
    assert "dcf" not in {m["key"] for m in v2["methods"]}


def test_valuation_no_data_after_valuation_date():
    w = make_wide()
    as_of = pd.Timestamp("2024-04-15")
    v1 = value(w, as_of=as_of, price=100_000)
    w2 = w.copy()
    w2.loc[20240:, ["revenue", "net_income", "net_income_parent"]] *= 5     # số liệu "tương lai" thay đổi mạnh
    v2 = value(w2, as_of=as_of, price=100_000)
    assert v1["data_period"] == "2023"
    assert v1["target_12m"] == pytest.approx(v2["target_12m"])
    assert not annual_available(20240, as_of) and annual_available(20230, as_of)
    _, _, px = point_in_time(w, None, make_prices(w), as_of)
    assert pd.to_datetime(px["timestamp"]).max() <= as_of


# ─────────────────────────── Risk ────────────────────────────────────────────

def test_risk_negative_cfo_two_years_is_severe():
    w = make_wide(neg_cfo_years=(2024, 2025))
    r = assess_risk(w, fr.compute_ratios(w, "year"), NONFIN, as_of=pd.Timestamp("2026-10-09"))
    assert r["severe"] and any(i["category"] == "Dòng tiền" and i["severity"] == "Nghiêm trọng" for i in r["items"])


def test_risk_stale_data_and_negative_equity():
    w = make_wide(years=range(2016, 2024))
    r = assess_risk(w, fr.compute_ratios(w, "year"), NONFIN, as_of=pd.Timestamp("2026-10-09"))
    assert r["level"] == "Nghiêm trọng" and any(i["category"] == "Dữ liệu" for i in r["items"])
    w2 = make_wide(equity_override=-1e12)
    r2 = assess_risk(w2, fr.compute_ratios(w2, "year"), NONFIN, as_of=pd.Timestamp("2026-10-09"))
    assert r2["severe"]


def test_risk_healthy_company_not_severe():
    w = make_wide()
    r = assess_risk(w, fr.compute_ratios(w, "year"), NONFIN, as_of=pd.Timestamp("2026-10-09"), industry_text="Công nghệ")
    assert not r["severe"] and any(i["severity"] == "Cần theo dõi" for i in r["items"])


# ─────────────────────────── Recommendation ──────────────────────────────────

def _val(er, conf="Cao", price=100.0, available=True):
    return {"available": available, "status": "OK" if available else NOT_ENOUGH, "price": price,
            "target_12m": (price or 100.0) * (1 + er / 100) if available else None, "expected_return": er if available else None,
            "upside": er, "confidence": conf, "methods": [{}], "invalid": []}


H = lambda s: {"score": s, "available": s is not None, "coverage": 1.0, "groups": []}  # noqa: E731
LOW_RISK = {"level": "Thấp", "items": []}
SEVERE = {"level": "Nghiêm trọng", "items": [{"severity": "Nghiêm trọng", "text": "VCSH âm"}]}
















# ─────────────────────────── Backtest ────────────────────────────────────────





def test_service_integration_with_fake_repo():
    from core.du_lieu import DataRepository
    from core.pipeline import StockService
    from tests.fakes import FakeDNSE, FakeVietstock, FakeVnstock
    repo = DataRepository(arminer_client=False, vnstock_client=FakeVnstock(), dnse_client=FakeDNSE(),
                          vietstock_client=FakeVietstock(True), use_cache=False)
    a = StockService("FPT", repository=repo).full_analysis()
    inv = a["investment"]
    assert inv and {"health", "valuation", "risk", "recommendation", "explanation", "thesis"} <= set(inv)
    assert a["fair_value"]["model"] == "12m" and a["recommendation"]["rating"] == inv["recommendation"]["label"]
    assert not a["errors"]


def test_service_as_of_valuation_date_point_in_time():
    from core.du_lieu import DataRepository
    from core.pipeline import StockService
    from tests.fakes import FakeDNSE, FakeVietstock, FakeVnstock
    repo = DataRepository(arminer_client=False, vnstock_client=FakeVnstock(), dnse_client=FakeDNSE(),
                          vietstock_client=FakeVietstock(True), use_cache=False)
    svc = StockService("FPT", repository=repo, as_of="2025-03-15")       # thứ Bảy → lấy phiên thứ Sáu 14/3
    px = svc.get_price_df()
    assert pd.to_datetime(px["timestamp"]).max() <= pd.Timestamp("2025-03-15 23:59")
    cur = svc.get_current_price()
    assert cur["timestamp"] == "2025-03-14" and cur["price"] == pytest.approx(float(px["close"].iloc[-1]))
    annual = svc.get_financials("year")["data"]
    assert int(annual.index.max()) // 10 == 2023                         # BCTC 2024 chưa công bố trước 1/4/2025
    assert pd.to_datetime(svc.get_index_df()["timestamp"]).max() <= pd.Timestamp("2025-03-15 23:59")
    assert svc.get_peer_stats()["n"] == 0                                # ngày cũ > 30 ngày → không dùng trung vị ngành
    inv = svc.investment_analysis()
    assert inv["as_of"] == "2025-03-15" and inv["valuation"]["data_period"] == "2023"
    assert inv["valuation"]["price_date"] == "2025-03-14"
    # cùng kết quả khi truyền as_of vào hàm
    inv2 = StockService("FPT", repository=repo).investment_analysis(as_of="2025-03-15")
    assert inv2["valuation"].get("target_12m") == inv["valuation"].get("target_12m")
    a = svc.full_analysis()
    assert a["as_of"] == "2025-03-15" and a["current_price"]["timestamp"] == "2025-03-14" and not a["errors"]


def test_service_as_of_today_or_future_means_current_price():
    from core.pipeline import StockService
    assert StockService("FPT", repository=object(), as_of=None).as_of is None
    assert StockService("FPT", repository=object(), as_of=str(pd.Timestamp.now().date())).as_of is None


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_valuation.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Unit tests for ValuationEngine (định giá tương đối – snapshot).
Bước 9: không còn hệ số mặc định gõ tay (P/E 15, P/B 1,5) và đã xóa dcf_valuation() lỗi thời.
"""
import pytest
import pandas as pd
from core.dinh_gia import ValuationEngine


def _engine(sample, peer_stats=None):
    ratio_df = pd.DataFrame([{"symbol": "FPT", "pe": sample["pe"], "pb": sample["pb"],
                              "eps": sample["eps"], "bvps": sample["bvps"]}])
    return ValuationEngine(symbol="FPT", current_price=100000.0, ratio_df=ratio_df, peer_stats=peer_stats)


def test_relative_valuation_without_peers_has_no_default_multiple(sample_financial_ratios):
    res = _engine(sample_financial_ratios).relative_valuation()
    assert res["pe"] == pytest.approx(16.5, 0.1)
    assert res["pb"] == pytest.approx(3.8, 0.1)
    assert res["sector_pe"] is None and res["sector_pb"] is None
    assert "pe_fair_value" not in res and "average_fair_value" not in res
    assert "Thiếu dữ liệu" in res["sector_pe_source"]


def test_relative_valuation_uses_real_peer_median(sample_financial_ratios):
    peers = {"group": "Công nghệ", "pe": 20.0, "pb": 4.0, "n": 5, "n_pe": 5, "n_pb": 5}
    res = _engine(sample_financial_ratios, peers).relative_valuation()
    assert res["pe_fair_value"] == pytest.approx(sample_financial_ratios["eps"] * 20.0)
    assert res["pb_fair_value"] == pytest.approx(sample_financial_ratios["bvps"] * 4.0)
    assert "average_fair_value" in res


def test_dcf_valuation_removed():
    assert not hasattr(ValuationEngine, "dcf_valuation")


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_hybrid_valuation.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Kiểm thử Bước 7 – Hybrid Valuation (Forecast Engine → Valuation Engine).
Dữ liệu tổng hợp (tests/test_investment_model.make_wide…) + dữ liệu THẬT đóng gói (BCTC arminer, vốn hóa Vietcap).
"""


import copy
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core import phan_tich_co_ban as fr
from core.du_phong import FinancialForecaster
from core.dinh_gia import select_profile
from core.dinh_gia import ValuationEngine12M
from core.cau_hinh import load_config


T = pd.Timestamp("2026-10-09")


def val(wide, company=NONFIN, forecast=None, cfg=None, price=None, peers=None, prices="auto", as_of=None, beta=1.0):
    px = make_prices(wide) if isinstance(prices, str) else prices
    shares = float(fr.shares_series(wide).dropna().iloc[-1])
    price = price or float(px["close"].iloc[-1])
    return ValuationEngine12M(cfg).value(price=price, price_date=T, wide=wide, ratios=fr.compute_ratios(wide, "year"),
                                         shares=shares, company=company, beta=beta, peers=peers or {}, price_df=px,
                                         as_of=as_of, forecast=forecast)


def fc(wide, company=NONFIN, as_of=T, **kw):
    shares = float(fr.shares_series(wide).dropna().iloc[-1])
    return FinancialForecaster().forecast(annual=wide, shares=shares, company=company, as_of=as_of, **kw)


# ── chọn hồ sơ phương pháp theo ngành ────────────────────────────────────────

@pytest.mark.parametrize("company,forecast,expected", [
    ({"type": "bank", "sector": "default"}, {}, "bank"),
    ({"type": "securities", "sector": "default"}, {}, "securities"),
    ({"type": "insurance", "sector": "default"}, {}, "insurance"),
    ({"type": "nonfinancial", "sector": "real_estate"}, {}, "real_estate"),
    ({"type": "nonfinancial", "sector": "default"}, {"scenario_group": "nwc_heavy",
                                                     "drivers": {"nwc_pct_revenue": {"value": 1.9}}}, "real_estate"),
    ({"type": "nonfinancial", "sector": "technology"}, {}, "technology"),
    ({"type": "nonfinancial", "sector": "utilities"}, {}, "utilities"),
    ({"type": "nonfinancial", "sector": "materials"}, {}, "cyclical_manufacturing"),
    ({"type": "nonfinancial", "sector": "default"}, {"cyclical": True}, "cyclical_manufacturing"),
    ({"type": "nonfinancial", "sector": "retail"}, {}, "default"),
])
def test_profile_selection(company, forecast, expected):
    key, why = select_profile(company, forecast, load_config()["valuation"]["method_profiles"])
    assert key == expected and why


def test_profile_weights_are_documented_and_default_unchanged():
    v = load_config()["valuation"]
    profs = v["method_profiles"]
    # Bước 9: DDM 2 giai đoạn là phương pháp ĐỐI CHIẾU – trọng số thấp (≤ 15%), không là neo chính ở hồ sơ nào
    for p in profs.values():
        assert p["weights"].get("ddm", 0) <= 15
        assert max(p["weights"], key=p["weights"].get) != "ddm"
    # tài chính: thu nhập thặng dư (RI) có mặt, không có DCF/EV
    for k in ("bank", "securities", "insurance"):
        assert "ri" in profs[k]["weights"] and not {"dcf", "ev_ebitda"} & set(profs[k]["weights"])
    assert "industrial_park" in profs and profs["industrial_park"]["weights"]["dcf"] >= 30
    for k, p in profs.items():
        assert p["rationale"] and p["label"] and sum(p["weights"].values()) == 100
        assert not set(p["weights"]) & set(p.get("excluded") or {})


# ── công thức & kỳ dữ liệu ───────────────────────────────────────────────────

def test_methods_use_forecast_inputs_and_period_labels():
    w = make_wide()
    f = fc(w)
    v = val(w, forecast=f)
    # (14/10/2026) dữ liệu tổng hợp có Bull/Bear > 2 lần → độ tin cậy có thể "Thấp"; bài kiểm tra này chỉ kiểm tra công thức
    assert v["model"] == "hybrid" and v["target_12m"]
    vi = f["valuation_inputs"]["base"]
    m = {x["key"]: x for x in v["methods"]}
    assert m["pe"]["base"] == pytest.approx(vi["eps_fwd"])
    assert m["pe"]["fair"] == pytest.approx(vi["eps_fwd"] * m["pe"]["multiple"])
    assert m["pb"]["base"] == pytest.approx(vi["bvps_fwd"])
    assert m["ev_ebitda"]["detail"]["ebitda_fwd"] == pytest.approx(vi["ebitda_fwd"])
    assert "NTM" in m["pe"]["period"] and vi["ntm_window_end"] in m["pe"]["period"]
    assert v["target_date"] == "2027-10-09" and v["valuation_date"] == "2026-10-09"


def test_fair_value_today_vs_target_consistent():
    w = make_wide()
    v = val(w)
    ke, dps = v["scenarios"]["base"]["ke"], v["expected_dividend"]
    for m in v["methods"]:
        assert m["fair_today"] == pytest.approx((m["fair"] + dps) / (1 + ke), rel=1e-9)
    agg = sum(m["fair_today"] * m["weight"] for m in v["methods"])
    assert v["fair_value_today"] == pytest.approx(agg)
    assert v["fair_value_today"] < v["target_12m"]
    assert v["expected_return"] == pytest.approx((v["target_12m"] + dps - v["price"]) / v["price"] * 100)


def test_dcf_discounts_dated_flows_from_valuation_date():
    w = make_wide()
    f = fc(w)
    v = val(w, forecast=f)
    d = next(m for m in v["methods"] if m["key"] == "dcf")["detail"]
    vi = f["valuation_inputs"]["base"]
    wacc, g = d["wacc"], d["g_terminal"]
    pv = 0.0
    for flow, end in zip(vi["fcff_path"], vi["fcff_period_ends"]):
        tau = (pd.Timestamp(end) - T).days / 365.25
        if tau > 0:
            pv += flow * min(tau, 1) / (1 + wacc) ** tau
    tau_n = (pd.Timestamp(vi["fcff_period_ends"][-1]) - T).days / 365.25
    tv = vi["fcff_path"][-1] * (1 + g) / (wacc - g) / (1 + wacc) ** tau_n
    assert d["ev"] == pytest.approx(pv + tv, rel=1e-9)
    assert d["intrinsic"] * (1 + v["scenarios"]["base"]["ke"]) - v["expected_dividend"] == pytest.approx(
        next(m for m in v["methods"] if m["key"] == "dcf")["fair"])


def test_weights_follow_profile_and_sum_to_one():
    w = make_wide()
    v = val(w, company={"type": "nonfinancial", "sector": "technology"})
    assert v["profile"]["key"] == "technology"
    assert set(v["weights"]) <= {"pe", "dcf", "ev_ebitda", "ddm"} and abs(sum(v["weights"].values()) - 1) < 1e-9
    cfgw = v["profile"]["weights_config"]
    tot = sum(cfgw[k] for k in v["weights"])
    for k, x in v["weights"].items():
        assert x == pytest.approx(cfgw[k] / tot)
    assert any(m == "P/B" for m, _ in v["not_applicable"])
    assert not any(m == "P/B" for m, _ in v["invalid"])


def test_bank_uses_only_pb_pe():
    v = val(make_bank(), company=BANK)
    assert v["profile"]["key"] == "bank" and {m["key"] for m in v["methods"]} <= {"pb", "pe"} and v["methods"]


def test_scenarios_ordered():
    v = val(make_wide())
    t = {s: v["scenarios"][s]["target"] for s in ("bear", "base", "bull")}
    assert t["bear"] < t["base"] < t["bull"]
    assert all(v["scenarios"][s]["fair_today"] < t[s] for s in t)


# ── loại trừ: dữ liệu thiếu nghiêm trọng / dự báo không tin cậy / bất thường ──

def test_missing_capex_blocks_dcf_not_zero():
    v = val(make_wide().drop(columns=["capex"]))
    assert "dcf" not in v["weights"]
    assert any(m == "DCF" and "capex" in r for m, r in v["invalid"])


def test_missing_growth_history_blocks_all_forward_methods():
    w = make_wide(years=range(2025, 2026))                 # 1 năm: không có tăng trưởng lịch sử
    v = val(w, prices=make_prices(w))
    assert not v["methods"] and not v["available"]


def test_severe_bridge_gap_excludes_ev_methods():
    w = make_wide()
    w.loc[w.index[-1], ["short_term_debt", "long_term_debt", "total_liabilities"]] = np.nan
    v = val(w)
    assert "dcf" not in v["weights"] and "ev_ebitda" not in v["weights"]
    assert any(m in ("DCF", "EV/EBITDA") and "không xác định" in r for m, r in v["invalid"])


def test_unreliable_forecast_backtest_excludes_pe():
    w = make_wide()
    f = fc(w)
    f["backtest"] = {"summary": {"net_income_parent": {"n": 6, "median_ape": 0.8, "mape": 1.0, "bias": 0, "coverage": 0.2}}}
    v = val(w, forecast=f)
    assert "pe" not in v["weights"]
    assert any(m == "P/E" and "không đủ tin cậy" in r for m, r in v["invalid"])


def test_outlier_method_excluded():
    w = make_wide()
    f = fc(w)
    for s in ("bear", "base", "bull"):
        f["valuation_inputs"][s]["ebitda_core_fwd"] *= 3.0     # EV/EBITDA lệch mạnh so với các phương pháp khác
    v = val(w, forecast=f, cfg=load_config({"valuation": {"sanity_band": (0.01, 100.0)}}))
    assert "ev_ebitda" not in v["weights"]
    assert any(m == "EV/EBITDA" and "trung vị các phương pháp" in r for m, r in v["invalid"])
    cmp_ = {c["key"]: c for c in v["comparison"]}
    assert cmp_["ev_ebitda"]["used"] is False and cmp_["pe"]["used"] is True


def test_forecast_unavailable_means_no_target():
    w = make_wide().drop(columns=["revenue"])
    v = val(w)
    assert v["target_12m"] is None if "target_12m" in v else True
    assert not v["methods"] and any("Forecast Engine" in n for n in v["notes"])


# ── look-ahead & tương thích ─────────────────────────────────────────────────

def test_no_look_ahead_in_hybrid():
    w = make_wide()
    a = val(w, as_of="2025-03-15")
    w2 = w.copy()
    w2.loc[20240, "revenue"] *= 5                          # BCTC 2024 chưa công bố ở 15/3/2025 (từ 1/4)
    b = val(w2, as_of="2025-03-15")
    assert a["target_12m"] == pytest.approx(b["target_12m"])
    assert a["forecast_summary"]["base"]["key"] == 20230


def test_legacy_switch_kept_for_comparison():
    v_old = val(make_wide(), cfg=load_config({"valuation": {"use_forecast_engine": False}}))
    assert v_old["model"] == "legacy" and v_old["target_12m"]




# ── đối chiếu trên DỮ LIỆU THẬT (BCTC arminer + vốn hóa Vietcap) ──────────────



def test_valuation_tab_renders_hybrid_and_pdf_section():
    from streamlit.testing.v1 import AppTest

    def script():
        import sys
        sys.path.insert(0, ".")
        import pandas as pd
        from core import phan_tich_co_ban as fr
        from core.dinh_gia import ValuationEngine12M
        from giao_dien.thi_truong import _pal, _tab_val
        from tests.test_dinh_gia_du_phong import NONFIN, make_prices, make_wide
        w = make_wide()
        px = make_prices(w)
        v = ValuationEngine12M().value(price=float(px["close"].iloc[-1]), price_date=pd.Timestamp("2026-10-09"), wide=w,
                                       ratios=fr.compute_ratios(w, "year"), shares=float(fr.shares_series(w).iloc[-1]),
                                       company=NONFIN, beta=1.0, peers={}, price_df=px)
        _tab_val({"investment": {"valuation": v}, "financial_summary": {}, "peers": {}}, _pal())

    at = AppTest.from_function(script, default_timeout=90).run()
    assert not at.exception
    txt = " ".join(c.value for c in at.caption)
    assert "hồ sơ" in txt.lower() or "Chọn hồ sơ" in txt
    assert "Đầu vào từ Forecast Engine" in txt


def test_pdf_valuation_section_hybrid():
    from core.bao_cao_pdf import EquityReportPDF, PDFReportGenerator
    from core.pipeline import valuation_to_legacy
    w = make_wide()
    v = valuation_to_legacy(val(w))
    gen = PDFReportGenerator()
    pdf = EquityReportPDF({"ticker": "TST", "name": "Test"})
    pdf.add_page()
    gen._render_valuation_12m(pdf, {}, {"fv": v, "inv": {"config": load_config(), "forecast": fc(w)}})
    assert pdf.page_no() >= 1


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_valuation_step8.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Kiểm thử Bước 8 – kiểm chứng Hybrid Valuation: số CP cùng cơ sở thị giá (lỗi đã xác nhận & sửa), kiểm tra chuỗi giá
chưa điều chỉnh, P/E lịch sử khớp Vietcap, backtest giá mục tiêu không look-ahead.
"""


import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core import phan_tich_co_ban as fr
from core.dinh_gia import price_series_check
from core.dinh_gia import ValuationEngine12M, historical_multiples


ROOT = Path(__file__).resolve().parents[1]
MC = json.loads((ROOT / "tests" / "data" / "vci_marketcap_quarterly.json").read_text(encoding="utf-8"))


# ── Lỗi B1: số CP lệch cơ sở với thị giá sau chia thưởng ─────────────────────

def _val_test_valuation_step8(w, shares, price, px):
    return ValuationEngine12M().value(price=price, price_date=pd.Timestamp("2026-10-09"), wide=w,
                                      ratios=fr.compute_ratios(w, "year"), shares=shares, company=NONFIN, beta=1.0,
                                      peers={}, price_df=px)


def test_stale_share_count_inflates_absolute_value_methods():
    """Sau khi thưởng 10% CP: thị giá và chuỗi giá (đã điều chỉnh) ở cơ sở số CP MỚI. Dùng số CP CŨ làm DCF/EV/EBITDA
    mỗi CP cao hơn ~10% (lỗi); P/B lệch một phần (P/B hợp lý từ ROE không phụ thuộc số CP); P/E và EV/EBITDA gần như
    không đổi (bội số lịch sử tính bằng cùng số CP nên lệch triệt tiêu)."""
    w = make_wide()
    old = float(fr.shares_series(w).dropna().iloc[-1])
    new = old * 1.10
    px = make_prices(w)
    px["close"] = px["close"] * old / new                       # giá điều chỉnh về cơ sở số CP mới
    price = float(px["close"].iloc[-1])
    v_old, v_new = _val_test_valuation_step8(w, old, price, px), _val_test_valuation_step8(w, new, price, px)
    m_old = {m["key"]: m["fair"] for m in v_old["methods"]}
    m_new = {m["key"]: m["fair"] for m in v_new["methods"]}
    assert m_old["pe"] == pytest.approx(m_new["pe"], rel=1e-6)
    assert m_old["ev_ebitda"] == pytest.approx(m_new["ev_ebitda"], rel=0.02)
    assert m_old["pb"] > m_new["pb"]
    assert m_old["dcf"] > m_new["dcf"] * 1.05                   # DCF phóng đại ~10% khi dùng số CP cũ
    assert v_old["target_12m"] > v_new["target_12m"]


def test_latest_shares_prefers_latest_published_quarter():
    from core.pipeline import StockService

    class Svc(StockService):
        def __init__(self, annual, quarterly, as_of=None):
            super().__init__("AAA", as_of=as_of)
            self._a, self._q = annual, quarterly

        def get_financials(self, period=None, years=None):
            return {"data": self._a if period == "year" else self._q}

    a = pd.DataFrame({"shares_outstanding": [1.0e9, 1.0e9]}, index=[20240, 20250])
    q = pd.DataFrame({"shares_outstanding": [1.0e9, 1.1e9]}, index=[20261, 20262])
    s = Svc(a, q)
    s._errors, s._memo = {}, {}
    info = s.latest_shares()
    assert info["shares"] == pytest.approx(1.1e9) and "quý 2/2026" in info["source"] and "+10.0%" in info["note"]
    s2 = Svc(a, pd.DataFrame())
    s2._errors, s2._memo = {}, {}
    assert s2.latest_shares()["shares"] == pytest.approx(1.0e9)


def test_latest_shares_point_in_time():
    """Quý chưa công bố tại ngày định giá không được dùng (get_financials của dịch vụ đã lọc theo as_of)."""
    from core.du_lieu import DataRepository
    from core.pipeline import StockService
    from tests.fakes import FakeDNSE, FakeVietstock, FakeVnstock
    repo = DataRepository(arminer_client=False, vnstock_client=FakeVnstock(), dnse_client=FakeDNSE(),
                          vietstock_client=FakeVietstock(True), use_cache=False)
    s = StockService("FPT", repository=repo, as_of="2025-03-15")
    s._errors, s._memo = {}, {}
    info = s.latest_shares()
    if info.get("key"):
        y, qq = divmod(info["key"], 10)
        end = pd.Timestamp(year=y, month=12 if qq == 0 else 3 * qq, day=1) + pd.offsets.MonthEnd(0)
        assert end < pd.Timestamp("2025-03-15")


# ── Kiểm tra chuỗi giá chưa điều chỉnh ───────────────────────────────────────

def test_price_series_check_flags_unadjusted_split():
    d = pd.bdate_range("2025-01-01", periods=120)
    close = np.full(len(d), 50_000.0)
    close[60:] = 25_000.0                                       # thưởng 1:1 không điều chỉnh → −50% một phiên
    r = price_series_check(pd.DataFrame({"timestamp": d, "close": close}))
    assert r["checked"] and r["suspect_jumps"] == 1 and r["max_move"] == pytest.approx(-0.5)


def test_price_series_check_ignores_normal_and_quarterly():
    d = pd.bdate_range("2025-01-01", periods=120)
    close = 50_000 * np.cumprod(1 + np.random.default_rng(1).normal(0, 0.02, len(d)).clip(-0.07, 0.07))
    assert price_series_check(pd.DataFrame({"timestamp": d, "close": close}))["suspect_jumps"] == 0
    q = pd.DataFrame({"timestamp": pd.date_range("2018-03-31", periods=30, freq="QE"), "close": np.linspace(1, 3, 30)})
    assert price_series_check(q) == {"checked": False}


def test_unadjusted_price_warning_in_valuation():
    w = make_wide()
    px = make_prices(w)
    px.loc[px.index[len(px) // 2]:, "close"] *= 0.5
    v = _val_test_valuation_step8(w, float(fr.shares_series(w).dropna().iloc[-1]), float(px["close"].iloc[-1]), px)
    assert v.get("data_quality", {}).get("suspect_jumps", 0) >= 1
    assert any("CHƯA điều chỉnh" in n for n in v["notes"])


# ── P/E lịch sử của app khớp P/E TTM Vietcap (dữ liệu thật) ──────────────────



# ── Backtest giá mục tiêu: không look-ahead, công thức giá thực tế ───────────


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_valuation_step9.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Kiểm thử Bước 9 – nâng cấp định giá (Hybrid):
  A4  DCF/EV không tính trùng thu nhập tài chính (EBIT cốt lõi + cộng tài sản tài chính một lần)
  A3  quy tắc dự phòng khi thiếu dữ liệu (chu kỳ, DDM, bội số ngành, EBIT cốt lõi)
  A2  không còn hệ số gõ tay
  Cầu nối nợ ròng từ bảng cân đối quý mới nhất đã công bố; thu nhập thặng dư (ngân hàng); chiết khấu cổ tức 2 giai
  đoạn (tính tay); hồ sơ BĐS khu công nghiệp; độ tin cậy.
Dữ liệu TỔNG HỢP có tham số biết trước (không dùng ở production).
"""


import numpy as np
import pandas as pd
import pytest

from core import phan_tich_co_ban as fr
from core.du_phong import FinancialForecaster
from core.dinh_gia import _ddm, _ri, select_profile
from core.dinh_gia import ValuationEngine12M
from core.cau_hinh import classify_company, load_config


T = pd.Timestamp("2026-10-09")


def run(wide, company=NONFIN, price=None, px=None, quarterly=None, cfg=None, peers=None, as_of=None):
    px = make_prices(make_wide()) if px is None else px
    price = price or float(px["close"].iloc[-1])
    return ValuationEngine12M(cfg).value(price=price, price_date=T, wide=wide, ratios=fr.compute_ratios(wide, "year"),
                                         shares=SHARES, company=company, beta=1.0, peers=peers or {}, price_df=px,
                                         as_of=as_of, quarterly=quarterly)


def method(v, key):
    return next((m for m in v["methods"] if m["key"] == key), None)


def with_financial_income(w, x):
    """Thêm thu nhập tài chính x mỗi năm vào LNTT/LN thuần HĐKD (giữ thuế suất 20%), KHÔNG đổi số dư tiền gửi."""
    w = w.copy()
    w["financial_income"] = x
    w["operating_profit"] = w["operating_profit"] + x
    w["profit_before_tax"] = w["profit_before_tax"] + x
    w["income_tax"] = w["profit_before_tax"] * 0.2
    w["net_income"] = w["profit_before_tax"] * 0.8
    w["net_income_parent"] = w["net_income"]
    return w


# ── A4: không tính trùng thu nhập tài chính ──────────────────────────────────

def test_core_ebit_excludes_financial_income_and_associates():
    w = pd.DataFrame({"gross_profit": [100.0], "selling_expense": [-20.0], "admin_expense": [-10.0],
                      "operating_profit": [95.0], "financial_income": [30.0], "financial_expense": [-8.0],
                      "associates_income": [3.0], "depreciation": [5.0]}, index=[20250])
    ebit, ebitda, how = fr.core_ebit_ebitda(w)
    assert ebit.iloc[0] == 70.0 and ebitda.iloc[0] == 75.0 and how.iloc[0] == "gp_sga"
    # Cách 2 (thiếu CP bán hàng): LN thuần HĐKD − DT tài chính + |CP tài chính| − lãi công ty liên kết = 95 − 30 + 8 − 3
    w2 = w.drop(columns=["selling_expense"])
    assert fr.core_ebit_ebitda(w2)[0].iloc[0] == 70.0 and fr.core_ebit_ebitda(w2)[2].iloc[0] == "op_adj"
    # thiếu cả hai cách → NaN (không coi bằng 0)
    w3 = w2.drop(columns=["associates_income"])
    assert np.isnan(fr.core_ebit_ebitda(w3)[0].iloc[0])


def test_dcf_unchanged_when_interest_income_rises_but_deposits_do_not():
    base = make_wide()
    px = make_prices(base)
    a = run(base, px=px)
    b = run(with_financial_income(base, 800e9), px=px)
    da, db = method(a, "dcf"), method(b, "dcf")
    assert da and db
    assert db["detail"]["intrinsic"] == pytest.approx(da["detail"]["intrinsic"], rel=1e-9)
    # EBITDA cốt lõi cho EV/EBITDA cũng không đổi
    assert method(b, "ev_ebitda")["detail"]["ebitda_fwd"] == pytest.approx(method(a, "ev_ebitda")["detail"]["ebitda_fwd"])


@pytest.mark.parametrize("col", ["short_term_investments", "long_term_investments"])
def test_more_financial_assets_raise_equity_value_exactly(col):
    base = make_wide()
    px = make_prices(base)
    x = 2_000e9
    w = base.copy()
    w.loc[w.index[-1], col] = w.loc[w.index[-1], col] + x
    a, b = method(run(base, px=px), "dcf"), method(run(w, px=px), "dcf")
    assert b["detail"]["intrinsic"] - a["detail"]["intrinsic"] == pytest.approx(x / SHARES, rel=1e-9)


def test_missing_core_ebit_excludes_dcf_and_ev_not_total_ebit():
    w = make_wide().drop(columns=["selling_expense", "admin_expense"])
    v = run(w)
    assert method(v, "dcf") is None and method(v, "ev_ebitda") is None
    reasons = " ".join(r for m, r in v["invalid"] if m in ("DCF", "EV/EBITDA"))
    assert "EBIT cốt lõi" in reasons


# ── cầu nối nợ ròng từ quý mới nhất đã công bố ──────────────────────────────

def _quarters(w, cash_q2):
    last = w.iloc[-1]
    rows = {}
    for k, cash in ((20261, last["cash"]), (20262, cash_q2), (20263, 99_999e9)):
        r = {c: last[c] for c in ("total_assets", "equity", "minority_interest", "short_term_debt", "long_term_debt",
                                  "short_term_investments", "long_term_investments", "current_assets")}
        r["cash"] = cash
        rows[k] = r
    return pd.DataFrame.from_dict(rows, orient="index")


def test_bridge_uses_latest_published_quarter_not_unpublished():
    w = make_wide()
    px = make_prices(w)
    a = run(w, px=px)
    extra = 1_500e9
    q = _quarters(w, w.iloc[-1]["cash"] + extra)
    b = run(w, px=px, quarterly=q)
    d = method(b, "dcf")["detail"]
    assert d["bridge_period"] == "Q2/2026"           # Q3/2026 (30/9 + 50 ngày > 9/10) chưa công bố → không dùng
    assert d["intrinsic"] - method(a, "dcf")["detail"]["intrinsic"] == pytest.approx(extra / SHARES, rel=1e-9)
    assert any("Q2/2026" in n for n in b["notes"])


# ── chu kỳ: chuẩn hóa & quy tắc dự phòng ────────────────────────────────────

MAT = {"type": "nonfinancial", "sector": "materials"}


def test_cyclical_full_normalization_5_years():
    v = run(make_wide(), company=MAT)
    c = v["cycle_normalization"]
    assert v["profile"]["key"] == "cyclical_manufacturing" and c["ok"] and c["years"] == 5
    assert "chuẩn hóa chu kỳ" in method(v, "pe")["base_label"]


def test_cyclical_3_to_4_years_caps_confidence_medium():
    v = run(make_wide(years=range(2022, 2026)), company=MAT)
    c = v["cycle_normalization"]
    assert c["ok"] and c["years"] == 4 and c["cap"] == "Trung bình"
    assert v["confidence"] in ("Trung bình", "Thấp")
    assert any("chu kỳ" in x for x in v["confidence_detail"]["caps"]) or v["confidence"] == "Thấp"


def test_cyclical_under_3_years_drops_pe_ev_and_low_confidence():
    w = make_wide(years=range(2023, 2026))
    cfg = load_config({"valuation": {"cycle_min_years": 4}})     # 3 năm < 4 → không chuẩn hóa được
    v = run(w, company=MAT, cfg=cfg)
    assert v["cycle_normalization"]["ok"] is False
    assert method(v, "pe") is None and method(v, "ev_ebitda") is None
    assert any(m == "P/E" and "chuẩn hóa" in r for m, r in v["invalid"])
    if v.get("methods"):
        assert v["confidence"] == "Thấp"


# ── bội số ngành: dự phòng về lịch sử của chính mã ──────────────────────────

def test_peer_group_under_3_uses_own_history_only():
    v = run(make_wide(), peers={"pe": 30.0, "n": 2, "n_pe": 2})
    pe = method(v, "pe")
    assert not pe["detail"]["peer_used"] and "chỉ dùng lịch sử của chính mã" in pe["source"]
    v2 = run(make_wide(), peers={"pe": 30.0, "n": 5, "n_pe": 5})
    assert method(v2, "pe")["detail"]["peer_used"]


# ── DDM 2 giai đoạn ─────────────────────────────────────────────────────────

class _Eng:
    def __init__(self):
        self.cfg = load_config()
        self.v = self.cfg["valuation"]


def _vi(eps, roe, ends):
    return {"eps_path": eps, "roe_path": roe, "fcff_period_ends": ends}


def test_ddm_matches_hand_calculation():
    w = make_wide(div_ratio=0.5)                 # chi trả đều 50% ⇒ tỷ lệ chi trả = 0,5
    ends = [f"{2026 + t}-12-31" for t in range(1, 6)]
    Tv = pd.Timestamp("2026-12-31")              # đúng cuối kỳ gốc → mỗi năm trọn 1 năm
    eps = [1000.0, 1100.0, 1200.0, 1300.0, 1400.0]
    roe = [0.15] * 5
    ke, g = 0.13, 0.035
    r = _ddm(_vi(eps, roe, ends), {}, w, SHARES, ke, g, 0.0, Tv, _Eng())
    assert r["valid"] and r["payout"] == pytest.approx(0.5)
    tau = [(pd.Timestamp(e) - Tv).days / 365.25 for e in ends]     # cùng quy ước thời gian với DCF
    pv = sum(e * 0.5 * min(t, 1) / (1 + ke) ** t for e, t in zip(eps, tau))
    po_st = 1 - g / 0.15
    tv = 1400 * (1 + g) * po_st / (ke - g) / (1 + ke) ** tau[-1]
    assert r["intrinsic"] == pytest.approx(pv + tv, rel=1e-6)
    assert r["payout_stable"] == pytest.approx(po_st)


def test_ddm_not_applicable_rules():
    ends = [f"{2026 + t}-12-31" for t in range(1, 6)]
    vi = _vi([1000.0] * 5, [0.15] * 5, ends)
    no_div = make_wide(div_ratio=0.0)
    r = _ddm(vi, {}, no_div, SHARES, 0.13, 0.035, 0.0, T, _Eng())
    assert r.get("not_applicable") and "cổ tức tiền mặt" in r["reason"]
    erratic = make_wide(div_ratio=0.4)
    erratic["dividends_paid"] = [-x if i % 2 else -x * 0.05 for i, x in enumerate(erratic["net_income"].abs())]
    r2 = _ddm(vi, {}, erratic, SHARES, 0.13, 0.035, 0.0, T, _Eng())
    assert r2.get("not_applicable") and "thất thường" in r2["reason"]
    short = _ddm(_vi([1000.0] * 3, [0.15] * 3, ends[:3]), {}, make_wide(), SHARES, 0.13, 0.035, 0.0, T, _Eng())
    assert short.get("not_applicable") and "5 năm" in short["reason"]
    tight = _ddm(vi, {}, make_wide(), SHARES, 0.06, 0.045, 0.0, T, _Eng())
    assert not tight["valid"] and not tight.get("not_applicable")


def test_ddm_not_applicable_removed_from_weights_not_coverage_penalty():
    v = run(make_wide(div_ratio=0.0))
    assert "ddm" not in v["weights"]
    assert any(m == "DDM" for m, _ in v["not_applicable"])
    assert v["weight_coverage"] == pytest.approx(1.0)


def test_ddm_ignores_dividends_published_after_valuation_date():
    w = make_wide(div_ratio=0.4)
    w2 = w.copy()
    w2.loc[20250, "dividends_paid"] *= 5             # BCTC 2025 chưa công bố tại 15/3/2026
    a = run(w, as_of="2026-03-15")
    b = run(w2, as_of="2026-03-15")
    ma, mb = method(a, "ddm"), method(b, "ddm")
    assert (ma is None and mb is None) or ma["fair"] == pytest.approx(mb["fair"])


# ── thu nhập thặng dư (ngân hàng) ───────────────────────────────────────────

def test_residual_income_hand_calculation():
    ke, g = 0.13, 0.03
    eq0, roe, pay = 100_000.0, 0.18, 0.2
    yrs, eq = [], eq0
    for t in range(1, 6):
        ni = roe * eq
        e1 = eq + ni * (1 - pay)
        yrs.append({"net_income_parent": ni, "equity_parent": e1, "roe": ni / ((eq + e1) / 2),
                    "period_end": f"{2026 + t}-12-31"})
        eq = e1
    fc = {"scenarios": {"base": {"years": yrs}}, "drivers": {"payout": {"value": pay}}, "base": {"end": "2026-12-31"}}
    r = _ri({}, fc, "base", 1.0, ke, g, 0.0, pd.Timestamp("2026-12-31"), _Eng())
    assert r["valid"]
    b_prev = [eq0] + [y["equity_parent"] for y in yrs[:-1]]
    tau = [(pd.Timestamp(y["period_end"]) - pd.Timestamp("2026-12-31")).days / 365.25 for y in yrs]
    pv = sum((y["net_income_parent"] - ke * b) * min(t, 1) / (1 + ke) ** t for y, b, t in zip(yrs, b_prev, tau))
    roe_sus = float(np.median([y["roe"] for y in yrs[:3]]))
    # 15/10/2026: ROE dài hạn (giá trị cuối kỳ) = min(ROE dự báo, Ke + roe_fade_spread)
    sp = load_config()["valuation"].get("roe_fade_spread")
    roe_t = min(roe_sus, ke + sp) if sp is not None else roe_sus
    tv = (roe_t - ke) * yrs[-1]["equity_parent"] * (1 + g) / (ke - g) / (1 + ke) ** tau[-1]
    assert r["intrinsic"] == pytest.approx(eq0 + pv + tv, rel=1e-9)


def test_bank_uses_residual_income_and_no_dcf_ev():
    v = run(make_bank(), company=BANK, px=make_prices(make_bank()))
    keys = {m["key"] for m in v["methods"]}
    assert "ri" in keys and not keys & {"dcf", "ev_ebitda"}
    assert v["profile"]["key"] == "bank"


# ── hồ sơ & phân loại ───────────────────────────────────────────────────────

def test_industrial_park_profile_by_ticker_list():
    c = classify_company("Bất động sản", "", False, symbol="KBC")
    assert c["sector"] == "industrial_park"
    key, why = select_profile(c, {}, load_config()["valuation"]["method_profiles"])
    assert key == "industrial_park" and "INDUSTRIAL_PARK_TICKERS" in why
    assert classify_company("Bất động sản", "", False, symbol="VHM")["sector"] == "real_estate"


def test_real_estate_and_insurance_confidence_capped_medium():
    v = run(make_wide(), company={"type": "nonfinancial", "sector": "real_estate"})
    assert v["confidence"] in ("Trung bình", "Thấp")
    assert v["profile"]["key"] == "real_estate"


def test_confidence_rules_are_explained():
    w = make_wide()
    v = run(w)                                              # engine tự dự báo + kiểm định sai số của chính mã
    d = v["confidence_detail"]
    assert set(d) == {"score", "reasons", "caps"}
    assert not any("chưa kiểm định" in r for r in d["reasons"])
    # truyền dự báo KHÔNG có kiểm định → trừ 1 điểm, ghi rõ lý do
    f = FinancialForecaster().forecast(annual=w, shares=SHARES, company=NONFIN, as_of=T)
    px = make_prices(make_wide())
    v2 = ValuationEngine12M().value(price=float(px["close"].iloc[-1]), price_date=T, wide=w,
                                    ratios=fr.compute_ratios(w, "year"), shares=SHARES, company=NONFIN, beta=1.0,
                                    peers={}, price_df=px, forecast=f)
    assert any("chưa kiểm định" in r for r in v2["confidence_detail"]["reasons"])
    assert v2["confidence_detail"]["score"] == v["confidence_detail"]["score"] - 1


def test_no_hardcoded_multiples_left_in_valuation_code():
    import inspect
    import core.dinh_gia as hv
    import core.dinh_gia as sv
    src = inspect.getsource(hv) + inspect.getsource(sv)
    for bad in ("MARKET_DEFAULT_PE", "MARKET_DEFAULT_PB", "_SECTOR_MULTIPLES", "_TICKER_MULTIPLES", "BASELINE_2021"):
        assert bad not in src


# ── VCSH kỳ gốc theo bảng cân đối quý mới nhất & cảnh báo lệch cơ sở số CP ───────

def test_forecast_uses_latest_published_quarter_equity_when_base_is_fiscal_year():
    w = make_wide()
    q = pd.DataFrame({"equity": [w.iloc[-1]["equity"] + 5_000e9], "minority_interest": [0.0]}, index=[20262])
    f = FinancialForecaster().forecast(annual=w, quarterly=q, shares=SHARES, company=NONFIN, as_of=T,
                                       quarter_basis_ok=False)
    assert f["base"]["kind"] == "FY" and f["base"]["balance_from"] == "Q2/2026"
    f0 = FinancialForecaster().forecast(annual=w, shares=SHARES, company=NONFIN, as_of=T)
    y1, y0 = f["scenarios"]["base"]["years"][0], f0["scenarios"]["base"]["years"][0]
    assert y1["equity_parent"] - y0["equity_parent"] == pytest.approx(5_000e9)
    # quý chưa công bố tại ngày dự báo (Q3/2026: 30/9 + 50 ngày > 9/10) → không dùng
    q3 = q.rename(index={20262: 20263})
    f3 = FinancialForecaster().forecast(annual=w, quarterly=q3, shares=SHARES, company=NONFIN, as_of=T,
                                        quarter_basis_ok=False)
    assert "balance_from" not in f3["base"]


def test_share_count_far_above_fiscal_year_basis_lowers_confidence():
    w = make_wide()
    px = make_prices(w)
    a = run(w, px=px)
    b = ValuationEngine12M().value(price=float(px["close"].iloc[-1]), price_date=T, wide=w,
                                   ratios=fr.compute_ratios(w, "year"), shares=SHARES * 1.3, company=NONFIN, beta=1.0,
                                   peers={}, price_df=px)
    assert any("số CP hiện hành lệch +30%" in r for r in b["confidence_detail"]["reasons"])
    assert b["confidence_detail"]["score"] <= a["confidence_detail"]["score"] - 1


# ── pandas 3: chuỗi giá kiểu số nguyên (lỗi BVB 14/10/2026: "Invalid value … for dtype int64") ────────

def test_unadjusted_gap_fix_accepts_integer_price_and_volume():
    from core.du_lieu import fix_unadjusted_gaps
    d = pd.DataFrame({"timestamp": pd.bdate_range("2026-01-01", periods=6),
                      "open": [20000, 20100, 20200, 10100, 10200, 10300],
                      "high": [20100, 20200, 20300, 10200, 10300, 10400],
                      "low": [19900, 20000, 20100, 10000, 10100, 10200],
                      "close": [20050, 20150, 20200, 10150, 10250, 10300],
                      "volume": [202301, 255049, 196637, 123910, 187358, 130583]}).astype(
        {"open": "int64", "close": "int64", "volume": "int64"})
    out = fix_unadjusted_gaps(d, "BVB", band=0.15)
    assert out.attrs.get("corporate_action_adjustments")              # phát hiện bước nhảy ~50% và điều chỉnh
    assert out["close"].iloc[0] == pytest.approx(20050 * 10100 / 20200)
    assert out["volume"].iloc[0] == pytest.approx(202301 / (10100 / 20200))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_valuation_round4.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""15/10/2026 – hiệu chỉnh định giá theo chẩn đoán (tools/valuation_diag.py): cổ tức tiền mặt trong giá quá khứ, bội số
theo độ gần, tăng trưởng DN tăng đều, beta Blume, ROE dài hạn, phân loại ngành."""
import numpy as np
import pandas as pd
import pytest

from core import dinh_gia as hv
from core.dinh_gia import ValuationEngine12M
from core.cau_hinh import classify_company, load_config
from core.pipeline import StockService
from tests.test_du_lieu import FPT_EV, Repo, T as T_test_valuation_round4


def test_recency_weighted_multiple():
    hist = {2017: 8.4, 2018: 8.4, 2019: 11.1, 2020: 12.0, 2021: 18.0}
    old = hv._DECAY[0]
    try:
        hv._DECAY[0] = None
        assert hv._wq(hist, 50) == pytest.approx(11.1)
        hv._DECAY[0] = 0.5
        m = hv._wq(hist, 50)
        assert 12.0 < m < 18.0                            # nghiêng về các năm gần (FPT được định giá lại)
        derate = {2018: 3.5, 2019: 3.3, 2020: 3.0, 2021: 2.0, 2022: 1.4}
        assert hv._wq(derate, 50) < 2.5 < float(np.median(list(derate.values()))) + 0.5   # VHM giảm hạng
    finally:
        hv._DECAY[0] = old


def test_blume_beta():
    e = ValuationEngine12M()
    assert e.adj_beta(0.6) == pytest.approx(0.732)
    assert e.adj_beta(1.0) == pytest.approx(1.0)
    assert e.ke(0.6) > e.v["risk_free"] + 0.6 * e.v["equity_premium"] - 1e-12


def test_two_stage_justified_pb_and_roe_term():
    old = hv._FADE[0]
    try:
        hv._FADE[0] = 0.03
        assert hv._roe_term(0.236, 0.126) == pytest.approx(0.156)
        assert hv._roe_term(0.10, 0.126) == pytest.approx(0.10)
        jpb = hv._justified_pb(0.236, 0.126, 0.035)
        assert 1.4 < jpb < 1.75                            # 1 giai đoạn cũ: (23,6 − 3,5)/(12,6 − 3,5) = 2,21x
        hv._FADE[0] = None
        assert hv._justified_pb(0.236, 0.126, 0.035) == pytest.approx((0.236 - 0.035) / (0.126 - 0.035))
    finally:
        hv._FADE[0] = old


def test_classification_securities_insurance_and_airline():
    assert classify_company("Financial Services Financial Services", "", bank_flag=True)["type"] == "securities"
    assert classify_company("Insurance Insurance", "", bank_flag=True)["type"] == "insurance"
    assert classify_company("Banks Banks", "", bank_flag=True)["type"] == "bank"
    c = classify_company("Travel & Leisure Travel & Leisure", "", False)
    key, _ = hv.select_profile(c, {"scenario_group": "nwc_heavy", "drivers": {"nwc_pct_revenue": {"value": 0.6}}},
                               load_config()["valuation"]["method_profiles"])
    assert key != "real_estate"
    c2 = classify_company("Xây dựng", "", False)
    key2, _ = hv.select_profile(c2, {"scenario_group": "nwc_heavy", "drivers": {"nwc_pct_revenue": {"value": 0.6}}},
                                load_config()["valuation"]["method_profiles"])
    assert key2 == "real_estate"


def _series_cash_adjusted(T_div=pd.Timestamp("2024-06-03"), dps=3000.0, p_nom=60000.0):
    """Chuỗi giá nguồn đã trừ NGƯỢC cổ tức tiền mặt: trước GDKHQ = giá thật × (1 − d/P)."""
    ts = pd.bdate_range("2023-01-02", "2026-10-14")
    k = 1 - dps / p_nom
    close = np.where(ts < T_div, p_nom * k, p_nom - dps)
    return pd.DataFrame({"timestamp": ts, "open": close, "high": close, "low": close, "close": close, "volume": 1e6})


def test_cash_dividend_basis_backtest():
    ev = pd.DataFrame({"event_code": ["DIV"], "event_title_vi": ["Trả cổ tức bằng tiền mặt - 3,000 VND"],
                       "exright_date": ["2024-06-03"], "exercise_ratio": [0.3], "value_per_share": [3000.0],
                       "listing_date": [None]})
    s = StockService("VNM", repository=Repo(_series_cash_adjusted(), ev, issue_share=2.0e9), as_of=T_test_valuation_round4)
    out = s._apply_price_basis({"shares": 2.0e9})
    assert out["shares"] == pytest.approx(2.0e9 / (1 - 3000 / 60000), rel=1e-3)
    assert "cổ tức tiền mặt" in out["price_basis_method"]


def test_cash_dividend_not_applied_when_series_unadjusted():
    ts = pd.bdate_range("2023-01-02", "2026-10-14")
    close = np.where(ts < pd.Timestamp("2024-06-03"), 60000.0, 57000.0)   # giá thật, giảm đúng 3.000 ngày GDKHQ
    px = pd.DataFrame({"timestamp": ts, "open": close, "high": close, "low": close, "close": close, "volume": 1e6})
    ev = pd.DataFrame({"event_code": ["DIV"], "event_title_vi": ["Trả cổ tức bằng tiền mặt"], "exright_date": ["2024-06-03"],
                       "exercise_ratio": [0.3], "value_per_share": [3000.0], "listing_date": [None]})
    s = StockService("VNM", repository=Repo(px, ev, issue_share=2.0e9), as_of=T_test_valuation_round4)
    assert s._apply_price_basis({"shares": 2.0e9})["shares"] == pytest.approx(2.0e9)


def test_cash_dividend_fallback_from_cashflow():
    """Không có lịch sử cổ tức (bảng sự kiện trống – VNM, SAB) → ước tính từ LCTT năm (cổ tức đã trả ÷ số CP)."""
    class R(Repo):
        def get_financials(self, symbol, period="year", years=4, **kw):
            if period != "year":
                return {"data": pd.DataFrame()}
            return {"data": pd.DataFrame({"dividends_paid": [-6.0e12, -6.0e12, -6.0e12],
                                          "shares_outstanding": [2.0e9] * 3}, index=[20230, 20240, 20250])}
    ts = pd.bdate_range("2023-01-02", "2026-10-14")
    px = pd.DataFrame({"timestamp": ts, "open": 60000.0, "high": 60000.0, "low": 60000.0, "close": 60000.0, "volume": 1e6})
    s = StockService("VNM", repository=R(px, None, issue_share=2.0e9), as_of=T_test_valuation_round4)
    out = s._apply_price_basis({"shares": 2.0e9})
    assert out["shares"] > 2.0e9 * 1.10                     # ~3.000đ/năm trên ~60.000đ trong ~3,3 năm
    assert "LCTT" in out["price_basis_method"]


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_valuation_fixes.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Kiểm thử các sửa lỗi sau kiểm toán định giá (L1 beta, L2 EBITDA, L3 ghép kỳ năm, L5 DCF cũ).
Dữ liệu là dữ liệu TỔNG HỢP cho kiểm thử (không dùng ở production, không gọi mạng).
"""


import numpy as np
import pandas as pd
import pytest

from core import phan_tich_co_ban as fr
from core.dinh_gia import ValuationEngine
from core.dinh_gia import historical_multiples
from core.cau_hinh import settings
from core import du_lieu as qb
from core.du_lieu import DataRepository
from core.pipeline import StockService

D = qb.DISCRETE


def align(wide, period, statement, basis=D):
    return DataRepository._align_period(wide, period, statement, basis)


# ── L3: ghép số quý thành số năm ────────────────────────────────────────────

def _quarters_test_valuation_fixes(year, values, col="net_income"):
    return pd.DataFrame({col: values}, index=[year * 10 + q for q in range(1, len(values) + 1)], dtype=float)


def test_flow_items_sum_four_quarters():
    wide = _quarters_test_valuation_fixes(2024, [100.0, 200.0, 300.0, 400.0])
    out = align(wide, "year", "is")
    assert list(out.index) == [20240]
    assert out.loc[20240, "net_income"] == pytest.approx(1000.0)      # trước đây = 400 (quý cuối)


def test_flow_items_incomplete_year_not_created():
    wide = pd.concat([_quarters_test_valuation_fixes(2024, [1.0, 2.0, 3.0, 4.0]), _quarters_test_valuation_fixes(2025, [5.0, 6.0, 7.0])])
    out = align(wide, "year", "cf")
    assert list(out.index) == [20240]                                  # 2025 mới có 3 quý → không có số năm


def test_flow_item_missing_one_quarter_left_blank():
    wide = _quarters_test_valuation_fixes(2024, [100.0, np.nan, 300.0, 400.0])
    wide["revenue"] = [1.0, 2.0, 3.0, 4.0]
    out = align(wide, "year", "is")
    assert np.isnan(out.loc[20240, "net_income"])
    assert out.loc[20240, "revenue"] == pytest.approx(10.0)


def test_stock_items_take_q4_only():
    wide = pd.concat([_quarters_test_valuation_fixes(2024, [10.0, 20.0, 30.0, 40.0], "equity"), _quarters_test_valuation_fixes(2025, [50.0, 60.0], "equity")])
    out = align(wide, "year", "bs")
    assert list(out.index) == [20240]
    assert out.loc[20240, "equity"] == pytest.approx(40.0)


def test_annual_rows_from_source_take_priority():
    wide = pd.concat([pd.DataFrame({"net_income": [999.0]}, index=[20240]), _quarters_test_valuation_fixes(2024, [1.0, 2.0, 3.0, 4.0])])
    out = align(wide, "year", "is")
    assert out.loc[20240, "net_income"] == pytest.approx(999.0)


def test_unknown_basis_never_summed_into_year():
    wide = _quarters_test_valuation_fixes(2024, [100.0, 200.0, 300.0, 400.0])
    assert align(wide, "year", "is", qb.UNKNOWN).empty
    assert DataRepository._align_period(wide, "year", "is").empty           # mặc định an toàn = unknown


def test_eps_not_summed_into_year():
    wide = _quarters_test_valuation_fixes(2024, [1.0, 2.0, 3.0, 4.0])
    wide["eps"] = [1000.0, 1100.0, 1200.0, 1300.0]
    out = align(wide, "year", "is")
    assert "eps" not in out.columns or np.isnan(out.loc[20240, "eps"])


def test_quarter_mode_unchanged():
    wide = _quarters_test_valuation_fixes(2024, [1.0, 2.0, 3.0, 4.0])
    out = align(wide, "quarter", "is")
    assert list(out.index) == [20241, 20242, 20243, 20244]


# ── L3b: nhận dạng số quý lũy kế / độc lập và chuẩn hóa ─────────────────────

def _qframe(years, discrete_rev, cumulative=False, cols=("revenue", "cogs", "selling_expense")):
    """Bảng quý tổng hợp: discrete_rev[q-1] là doanh thu riêng quý q (các năm tăng 10%)."""
    rows = {}
    for i, y in enumerate(years):
        run = 0.0
        for q in range(1, 5):
            v = discrete_rev[q - 1] * 1.1 ** i
            run += v
            x = run if cumulative else v
            rows[y * 10 + q] = {"revenue": x, "cogs": -0.7 * x, "selling_expense": -0.1 * x, "net_income": 0.1 * x}
    return pd.DataFrame.from_dict(rows, orient="index")


def test_detect_discrete_by_shape():
    w = _qframe([2023, 2024], [100, 110, 105, 120])
    assert qb.detect_basis(w, "is")[0] == qb.DISCRETE


def test_detect_cumulative_by_shape_and_decumulate():
    disc = _qframe([2023, 2024], [100, 110, 105, 120])
    cum = _qframe([2023, 2024], [100, 110, 105, 120], cumulative=True)
    assert qb.detect_basis(cum, "is")[0] == qb.CUMULATIVE
    out, basis, why = qb.normalize_quarters(cum, "is")
    assert basis == qb.DISCRETE and "lũy kế" in why
    pd.testing.assert_frame_equal(out[disc.columns], disc, check_dtype=False)
    # sau chuẩn hóa: số năm = Σ4 quý = quý 4 lũy kế
    year = align(out, "year", "is")
    assert year.loc[20240, "revenue"] == pytest.approx(cum.loc[20244, "revenue"])


def test_detect_cumulative_by_annual_crosscheck():
    cum = _qframe([2023, 2024], [100, 300, 50, 400], cumulative=True)      # mùa vụ mạnh: hình dạng không kết luận được
    cum.loc[20230] = cum.loc[20234]
    cum.loc[20240] = cum.loc[20244]
    assert qb.detect_basis(cum.sort_index(), "is")[0] == qb.CUMULATIVE


def test_detect_discrete_by_annual_crosscheck():
    disc = _qframe([2023], [100, 300, 50, 400])
    disc.loc[20230] = disc.loc[[20231, 20232, 20233, 20234]].sum()
    assert qb.detect_basis(disc.sort_index(), "is")[0] == qb.DISCRETE


def test_cumulative_with_missing_quarter_leaves_gap():
    cum = _qframe([2023, 2024], [100, 110, 105, 120], cumulative=True).drop(index=[20242])
    out, _, _ = qb.normalize_quarters(cum, "is")
    assert np.isnan(out.loc[20243, "revenue"])                             # Q3 − Q2 không tính được
    assert out.loc[20244, "revenue"] == pytest.approx(cum.loc[20244, "revenue"] - cum.loc[20243, "revenue"])
    assert out.loc[20241, "revenue"] == pytest.approx(cum.loc[20241, "revenue"])
    assert 20240 not in align(out, "year", "is").index                     # năm thiếu quý → không có số năm


def test_ambiguous_data_is_unknown_and_not_summed():
    w = pd.DataFrame({"revenue": [100.0, 170.0]}, index=[20241, 20242])    # chỉ 2 quý, tỷ lệ 1,7 – không kết luận
    out, basis, _ = qb.normalize_quarters(w, "is")
    assert basis == qb.UNKNOWN
    pd.testing.assert_frame_equal(out, w)                                  # giữ nguyên, không đoán


def test_pdf_cash_flow_defaults_to_cumulative_income_to_discrete():
    rows = {20241: {"revenue": 100.0, "cfo": 50.0}, 20242: {"revenue": 120.0, "cfo": 90.0}}
    log = {}
    out = DataRepository._normalize_pdf_quarters(pd.DataFrame.from_dict(rows, orient="index"), log)
    assert out.loc[20242, "revenue"] == pytest.approx(120.0)               # KQKD "Quý này"
    assert out.loc[20242, "cfo"] == pytest.approx(40.0)                    # LCTT B03a lũy kế → 90 − 50
    assert log["cf"]["basis"] == qb.DISCRETE and "mẫu biểu" in log["cf"]["why"]


def test_repository_reports_quarter_basis(fake_repo):
    repo = fake_repo
    from tests.fakes import FakeVnstock, vci_income

    res = repo.get_financials("FPT", "quarter")
    assert res["quarter_basis"]["vnstock_vci"]["is"]["basis"] == qb.DISCRETE

    class CumulativeVnstock(FakeVnstock):
        def get_financial_statement(self, symbol, statement, period="year", source=None):
            df = super().get_financial_statement(symbol, statement, period, source)
            if period == "quarter" and statement == "income_statement" and not df.empty and "vci" in (source or "vci"):
                df = df.copy()
                for c in [c for c in df.columns if "-Q" in str(c) and not str(c).endswith("_1")]:
                    q = int(str(c)[-1])
                    num = pd.to_numeric(df[c], errors="coerce")
                    flow = ~df["item_id"].isin(["revenue_yoy", "eps_x"])
                    df.loc[flow, c] = num[flow] * q                         # quý độc lập phẳng → lũy kế 1:2:3:4
            return df

    from core.du_lieu import DataRepository as DR
    from tests.fakes import FakeDNSE, FakeVietstock
    cum_repo = DR(arminer_client=False, vnstock_client=CumulativeVnstock(), dnse_client=FakeDNSE(),
                  vietstock_client=FakeVietstock(False), pdf_financial_loader=lambda s, p: pd.DataFrame(), use_cache=False)
    a = repo.get_financials("FPT", "quarter")["data"]
    b = cum_repo.get_financials("FPT", "quarter")["data"]
    info = cum_repo.get_financials("FPT", "quarter")["quarter_basis"]["vnstock_vci"]["is"]
    assert "lũy kế" in info["why"]
    k = 20244
    assert b.loc[k, "revenue"] == pytest.approx(a.loc[k, "revenue"], rel=1e-9)


def test_semiannual_pdf_flow_items_dropped(monkeypatch):
    from core import tai_lieu_bctc as ds
    svc = ds.DocumentService.__new__(ds.DocumentService)
    docs = pd.DataFrame([
        {"doc_type": "fs_semiannual", "downloaded": True, "title": "BCTC bán niên hợp nhất 2024", "url": "a", "year": 2024},
        {"doc_type": "fs_quarterly", "downloaded": True, "title": "BCTC quý 1 hợp nhất 2024", "url": "b", "year": 2024, "quarter": 1},
    ])
    monkeypatch.setattr(svc, "list_documents", lambda s: docs, raising=False)
    vals = {"a": {"revenue": 600.0, "total_assets": 9000.0}, "b": {"revenue": 280.0, "total_assets": 8000.0}}
    monkeypatch.setattr(svc, "extract", lambda d, use_ocr=False: {"values": vals[d["url"]],
                                                                  "period_key": ds.period_key_for(d)}, raising=False)
    out = svc.pdf_financials("AAA", "quarter")
    assert out.loc[20242, "total_assets"] == pytest.approx(9000.0)         # số dư 30/6 giữ lại
    assert "revenue" not in out.columns or np.isnan(out.loc[20242, "revenue"])   # 6 tháng ≠ quý 2
    assert out.loc[20241, "revenue"] == pytest.approx(280.0)


# ── L2: một định nghĩa EBITDA duy nhất ──────────────────────────────────────

def _wide():
    rows = {}
    for i, y in enumerate(range(2019, 2025)):
        rev = 10_000e9 * 1.1 ** i
        rows[y * 10] = {"revenue": rev, "profit_before_tax": rev * 0.12, "operating_profit": rev * 0.10,
                        "interest_expense": -rev * 0.02, "depreciation": rev * 0.05, "net_income": rev * 0.1,
                        "net_income_parent": rev * 0.1, "equity": rev * 0.8, "total_assets": rev * 1.5,
                        "short_term_debt": rev * 0.2, "long_term_debt": rev * 0.1, "cash": rev * 0.05,
                        "short_term_investments": 0.0, "minority_interest": 0.0,
                        "shares_outstanding": 1e9, "charter_capital": 1e13}
    return pd.DataFrame.from_dict(rows, orient="index")


def test_ebitda_definition():
    w = _wide()
    ebit, ebitda = fr.ebit_ebitda(w)
    r = w.iloc[-1]
    assert ebit.iloc[-1] == pytest.approx(r.profit_before_tax + abs(r.interest_expense))
    assert ebitda.iloc[-1] == pytest.approx(r.profit_before_tax + abs(r.interest_expense) + r.depreciation)


def test_ebitda_missing_depreciation_is_nan():
    w = _wide().drop(columns=["depreciation"])
    assert fr.ebit_ebitda(w)[1].isna().all()


def test_ebitda_same_in_ratio_table_snapshot_and_valuation():
    w = _wide()
    ebitda = fr.ebit_ebitda(w)[1]
    ratios = fr.compute_ratios(w, "year")
    margin = ratios["ebitda_margin"].iloc[-1] / 100
    assert margin * w["revenue"].iloc[-1] == pytest.approx(ebitda.iloc[-1])

    price = 50_000.0
    dates = pd.date_range("2019-01-02", "2024-12-31", freq="B")
    px = pd.DataFrame({"timestamp": dates, "close": price})
    hist = historical_multiples(w, 1e9, px)
    snap = fr.valuation_snapshot(w, price, period="year")
    assert snap["ev_ebitda"] == pytest.approx(hist["ev_ebitda"][2024])


# ── L1: beta cùng cửa sổ dù trang tải số ngày giá khác nhau ─────────────────

class _Repo:
    def __init__(self):
        rng = np.random.default_rng(7)
        dates = pd.bdate_range("2021-01-04", "2025-06-30")
        m = rng.normal(0, 0.01, len(dates))
        regime = np.where(dates < pd.Timestamp("2024-06-30"), 0.6, 1.4)     # beta đổi theo thời gian
        s = regime * m + rng.normal(0, 0.005, len(dates))
        self.data = {"VNINDEX": pd.DataFrame({"timestamp": dates, "close": 1000 * np.cumprod(1 + m)}),
                     "AAA": pd.DataFrame({"timestamp": dates, "close": 20_000 * np.cumprod(1 + s)})}

    def get_price_history(self, symbol, start_date="", end_date="", days=365, interval="1D", force_refresh=False):
        df = self.data[symbol]
        end = pd.Timestamp(end_date) if end_date else df["timestamp"].max()
        return df[(df["timestamp"] > end - pd.Timedelta(days=days)) & (df["timestamp"] <= end)].reset_index(drop=True)


def test_beta_independent_of_page_days():
    repo = _Repo()
    betas = [StockService("AAA", days=d, repository=repo, as_of="2025-06-30").compute_beta() for d in (180, 365, 1100)]
    assert betas[0] is not None
    assert betas[0] == pytest.approx(betas[1]) == pytest.approx(betas[2])
    assert betas[0] == pytest.approx(1.4, abs=0.15)                   # cửa sổ 1 năm gần nhất


def test_beta_window_setting_is_one_year_by_default():
    assert settings.BETA_WINDOW_DAYS == 365


# ── L5: không còn DCF đơn giản của engine cũ trong kết quả chấm điểm ───────

def test_legacy_score_has_no_dcf():
    ratios = pd.DataFrame({"pe": [12.0], "pb": [1.5]})
    score = ValuationEngine("AAA", 50_000, ratio_df=ratios).compute_valuation_score()
    assert "dcf" not in score


# ── L1b: độ tin cậy beta (ít thanh khoản, ngừng giao dịch, thiếu phiên, độ dài dữ liệu khác nhau) ──

from core.dinh_gia import estimate_beta


def _mkt(n_days=420, seed=1, beta=1.2, end="2025-06-30"):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=end, periods=n_days)
    m = rng.normal(0, 0.01, len(dates))
    s = beta * m + rng.normal(0, 0.006, len(dates))
    idx = pd.DataFrame({"timestamp": dates, "close": 1000 * np.cumprod(1 + m), "volume": 1e8})
    stk = pd.DataFrame({"timestamp": dates, "close": 20_000 * np.cumprod(1 + s), "volume": 1e6})
    return stk, idx


def test_beta_reliable_liquid_stock():
    stk, idx = _mkt()
    r = estimate_beta(stk, idx, 365)
    assert r["reliable"] and r["beta"] == pytest.approx(1.2, abs=0.15) and r["coverage"] > 0.95


def test_beta_few_missing_sessions_still_reliable_and_no_multiday_returns():
    stk, idx = _mkt()
    stk = stk.drop(index=stk.index[[50, 120, 200, 300]])
    r = estimate_beta(stk, idx, 365)
    assert r["reliable"] and r["max_gap_sessions"] == 1
    assert r["obs"] < r["index_sessions"] - 1                 # phiên thiếu không bị gộp thành lợi nhuận nhiều ngày


def test_beta_illiquid_flat_price_flagged():
    stk, idx = _mkt()
    flat = stk.copy()
    keep = np.arange(len(flat)) % 2 == 0                      # một nửa số phiên giá đứng yên
    flat["close"] = flat["close"].where(keep).ffill()
    r = estimate_beta(flat, idx, 365)
    assert not r["reliable"] and r["beta"] is None and "ít thanh khoản" in r["warnings"][0]


def test_beta_zero_volume_flagged():
    stk, idx = _mkt()
    stk.loc[stk.index % 3 == 0, "volume"] = 0
    r = estimate_beta(stk, idx, 365)
    assert not r["reliable"] and "khối lượng" in r["warnings"][0]


def test_beta_suspension_flagged():
    stk, idx = _mkt()
    stk = stk.drop(index=stk.index[250:290])                  # ngừng giao dịch 40 phiên
    r = estimate_beta(stk, idx, 365)
    assert not r["reliable"] and r["max_gap_sessions"] >= 40 and "ngừng giao dịch" in r["warnings"][0]


def test_beta_currently_suspended_flagged():
    stk, idx = _mkt()
    stk = stk.iloc[:-10]                                       # 10 phiên gần nhất không có giá
    r = estimate_beta(stk, idx, 365)
    assert not r["reliable"] and r["stale_sessions"] == 10


def test_beta_new_listing_short_history_flagged():
    stk, idx = _mkt()
    stk = stk.iloc[-90:]                                       # mới niêm yết ~4 tháng
    r = estimate_beta(stk, idx, 365)
    assert not r["reliable"] and "lịch sử giao dịch ngắn" in r["warnings"][0]


def test_beta_same_result_whatever_history_length_supplied():
    stk, idx = _mkt(n_days=900)
    full = estimate_beta(stk, idx, 365)["beta"]
    assert estimate_beta(stk.iloc[-300:], idx, 365)["beta"] == pytest.approx(full)
    assert estimate_beta(stk, idx.iloc[-300:], 365)["beta"] == pytest.approx(full)


def test_unreliable_beta_warned_in_valuation_notes():
    class IlliquidRepo(_Repo):
        def __init__(self):
            super().__init__()
            df = self.data["AAA"].copy()
            df["close"] = df["close"].where(np.arange(len(df)) % 2 == 0).ffill()
            self.data["AAA"] = df

    svc = StockService("AAA", days=365, repository=IlliquidRepo(), as_of="2025-06-30")
    assert svc.compute_beta() is None
    info = svc.beta_info()
    assert info["warnings"] and info["warnings"][0].startswith("Beta không đủ tin cậy")


# ── L2b: EV/EBITDA – mọi thành phần cùng một kỳ ───────────────────────────────

from core.dinh_gia import ValuationEngine12M, net_debt_at


def _p():
    return {"multiple_pct": 50, "margin_factor": 1.0}


def test_ev_ebitda_no_mixing_old_ebitda_with_new_balance():
    w = _wide()
    w.loc[20240, "depreciation"] = np.nan                     # năm gốc thiếu khấu hao
    hist = {"ev_ebitda": {2021: 8.0, 2022: 9.0, 2023: 10.0}}
    r = ValuationEngine12M()._ev_ebitda(w, 1e9, hist, 0.1, _p())
    assert not r["valid"] and "2024" in r["reason"]           # không lấy EBITDA 2023 ghép với nợ vay 2024


def test_ev_ebitda_no_mixing_old_debt_with_new_ebitda():
    w = _wide()
    w.loc[20240, ["total_assets", "equity", "short_term_debt", "long_term_debt", "cash",
                  "short_term_investments", "minority_interest"]] = np.nan     # chưa có bảng cân đối năm gốc
    hist = {"ev_ebitda": {2021: 8.0, 2022: 9.0, 2023: 10.0}}
    r = ValuationEngine12M()._ev_ebitda(w, 1e9, hist, 0.1, _p())
    assert not r["valid"] and "bảng cân đối" in r["reason"]


def test_ev_ebitda_uses_base_year_bridge():
    w = _wide()
    hist = {"ev_ebitda": {2021: 8.0, 2022: 9.0, 2023: 10.0}}
    r = ValuationEngine12M()._ev_ebitda(w, 1e9, hist, 0.0, _p())
    row = w.loc[20240]
    ebitda = row.profit_before_tax + abs(row.interest_expense) + row.depreciation
    net_debt = row.short_term_debt + row.long_term_debt - row.cash - row.short_term_investments
    assert r["valid"] and r["base_year"] == 2024
    assert r["target"] == pytest.approx((ebitda * 9.0 - net_debt - row.minority_interest) / 1e9)


def test_net_debt_missing_lines_noted_and_minority_sign_kept():
    w = _wide()
    w.loc[20240, ["short_term_debt", "long_term_debt"]] = np.nan
    w.loc[20240, "minority_interest"] = -5e9
    b = net_debt_at(w, 20240)
    assert b["ok"] and b["debt"] == 0 and b["minority"] == pytest.approx(-5e9)
    assert any("vay nợ" in n for n in b["notes"])


def test_snapshot_ev_ebitda_with_missing_minority():
    w = _wide()
    w["minority_interest"] = np.nan
    snap = fr.valuation_snapshot(w, 50_000.0, period="year")
    assert snap["ev_ebitda"] is not None                       # trước đây NaN "or 0" làm EV = NaN


# ── L5b: không rơi về hệ thống khuyến nghị cũ ─────────────────────────────────



# ── Lần sửa 3: DCF cùng kỳ, beta thay thế + độ nhạy, dữ liệu thiếu, mẫu BCTC quý thật ──

import json  # noqa: E402
from pathlib import Path  # noqa: E402

REAL = json.loads((Path(__file__).parent / "data" / "vci_quarter_samples.json").read_text(encoding="utf-8"))


def _real_wide(sym, with_annual=True):
    e = REAL[sym]
    y, m = e["year"], e["map"]
    rows = {y * 10 + int(q): {m[k]: float(v) for k, v in vals.items()} for q, vals in e["quarters"].items()}
    if with_annual:
        rows[y * 10] = {m[k]: float(v) for k, v in e["annual"].items()}
    return pd.DataFrame.from_dict(rows, orient="index").sort_index()


@pytest.mark.parametrize("sym", ["FPT", "HPG", "VCB"])
def test_real_vci_quarters_are_discrete(sym):
    w = _real_wide(sym)
    assert qb.detect_basis(w, "all")[0] == qb.DISCRETE
    cum = w.copy()
    qs = [k for k in w.index if k % 10]
    cum.loc[qs] = w.loc[qs].cumsum()                                   # phản chứng: nếu nguồn trả lũy kế
    assert qb.detect_basis(cum, "all")[0] == qb.CUMULATIVE
    out, basis, _ = qb.normalize_quarters(cum.drop(index=[k for k in w.index if k % 10 == 0]), "all",
                                          reference=w.loc[[k for k in w.index if k % 10 == 0]])
    assert basis == qb.DISCRETE
    pd.testing.assert_frame_equal(out, w.loc[qs], check_dtype=False)  # quy về đúng số từng quý thật


def test_real_vhm_inconsistent_quarters_stay_unknown():
    # VHM 2018: Σ4 quý khấu hao = 70% số năm, quý 4 âm (điều chỉnh) → không kết luận, không cộng ra số năm
    w = _real_wide("VHM")
    assert qb.detect_basis(w, "all")[0] == qb.UNKNOWN
    assert align(w.drop(index=[20180]), "year", "cf", qb.UNKNOWN).empty


def test_reference_annual_enables_detection_without_annual_rows():
    w = _real_wide("FPT", with_annual=False)
    assert qb.detect_basis(w, "all")[0] == qb.UNKNOWN                  # 1 năm, không có số năm → chưa đủ bằng chứng
    ref = _real_wide("FPT").loc[[20180]]
    assert qb.detect_basis(w, "all", reference=ref)[0] == qb.DISCRETE


def test_dcf_bridge_uses_base_year_only():
    w = _wide()
    w["cfo"] = w["revenue"] * 0.15
    w["capex"] = -w["revenue"] * 0.04
    w.loc[20240, ["short_term_debt", "long_term_debt"]] = np.nan       # năm gốc không có số vay
    eng = ValuationEngine12M()
    r = eng._dcf(w, 1e9, 50_000.0, 0.08, 0.13, 0.03, 0.0)
    assert r["valid"] and r["base_year"] == 2024
    assert r["net_debt"] == pytest.approx(-(w.loc[20240, "cash"] + w.loc[20240, "short_term_investments"]))
    gap = next(g for g in r["gaps"] if g["item"] == "vay nợ")
    assert gap["year"] == 2024 and gap["bound"] == pytest.approx(w.loc[20240, "total_liabilities"]
                                                                 if "total_liabilities" in w else gap["bound"])


def test_dcf_bridge_not_mixed_with_older_year():
    w = _wide()
    w["cfo"] = w["revenue"] * 0.15
    w["capex"] = -w["revenue"] * 0.04
    w.loc[20240, ["total_assets", "equity", "short_term_debt", "long_term_debt", "cash",
                  "short_term_investments", "minority_interest"]] = np.nan
    r = ValuationEngine12M()._dcf(w, 1e9, 50_000.0, 0.08, 0.13, 0.03, 0.0)
    assert not r["valid"] and "bảng cân đối" in r["reason"]


def test_gap_impact_levels():
    from core.dinh_gia import gap_impact
    assert gap_impact(1, 100)["impact"] == "thấp"
    assert gap_impact(10, 100)["impact"] == "trung bình"
    assert gap_impact(30, 100)["impact"] == "cao"
    assert gap_impact(None, 100)["impact"] == "không xác định"


def test_missing_debt_reported_with_impact_in_valuation():
    from tests.test_dinh_gia_du_phong import NONFIN, SHARES, make_wide
    w = make_wide()
    w.loc[w.index[-1], ["short_term_debt", "long_term_debt"]] = np.nan
    w.loc[w.index[-1], "total_liabilities"] = 9_000e9
    px = pd.DataFrame({"timestamp": pd.bdate_range("2018-01-01", "2026-03-31"), "close": 30_000.0})
    ratios = fr.compute_ratios(w, "year")
    v = ValuationEngine12M().value(price=30_000.0, price_date=pd.Timestamp("2026-03-31"), wide=w, ratios=ratios,
                                   shares=SHARES, company=NONFIN, price_df=px)
    gaps = [g for g in v.get("data_gaps", []) if g["item"] == "vay nợ"]
    assert gaps and gaps[0]["impact_pct"] is not None
    # Bước 7: ảnh hưởng thấp/trung bình → vẫn dùng và ghi chú; cao/không xác định → LOẠI phương pháp EV (không thay bằng 0)
    if gaps[0]["impact"] in ("thấp", "trung bình"):
        assert any("Thiếu số liệu vay nợ" in n for n in v["notes"])
    else:
        assert any(m in ("DCF", "EV/EBITDA") and "vay nợ" in r for m, r in v["invalid"])
        assert not {"dcf", "ev_ebitda"} & {m["key"] for m in v.get("methods", [])}


def test_beta_substitution_flagged_with_sensitivity(monkeypatch):
    class IlliquidRepo(_Repo):
        def __init__(self):
            super().__init__()
            df = self.data["AAA"].copy()
            df["close"] = df["close"].where(np.arange(len(df)) % 2 == 0).ffill()
            self.data["AAA"] = df

    from tests.test_dinh_gia_du_phong import NONFIN, SHARES, make_wide
    svc = StockService("AAA", days=365, repository=IlliquidRepo(), as_of="2025-06-30")
    eng = ValuationEngine12M()
    w = make_wide()
    px = pd.DataFrame({"timestamp": pd.bdate_range("2018-01-01", "2025-06-30"), "close": 30_000.0})
    kw = dict(price=30_000.0, price_date=pd.Timestamp("2025-06-30"), wide=w, ratios=fr.compute_ratios(w, "year"),
              shares=SHARES, company=NONFIN, price_df=px, peers={}, risk_level=None)
    v = eng.value(beta=svc.compute_beta(), **kw)
    svc._annotate_beta(v, eng, kw)
    assert v["assumptions"]["beta_substituted"] is True and v["assumptions"]["beta_used"] == 1.0
    assert v["notes"][0].startswith("GIẢ ĐỊNH THAY THẾ")
    if v.get("target_12m"):
        sens = v["beta_sensitivity"]
        betas = [r["beta"] for r in sens]
        assert {0.8, 1.0, 1.2} <= set(betas)
        used = next(r for r in sens if r["is_used"])
        assert used["target_12m"] == pytest.approx(v["target_12m"])
        t = {r["beta"]: r["target_12m"] for r in sens}
        # beta cao → Ke cao (giá mục tiêu thường thấp hơn, nhưng quy tắc loại phương pháp lệch > 2× trung vị có thể đổi
        # tập phương pháp ở biên → chỉ khóa Ke đơn điệu; 15/10/2026: Ke dùng beta điều chỉnh Blume)
        k = {r["beta"]: r["ke"] for r in sens}
        assert k[0.8] < k[1.0] < k[1.2]
        assert any(n.startswith("Độ nhạy giá mục tiêu theo beta") for n in v["notes"])


def test_reliable_beta_not_flagged():
    svc = StockService("AAA", days=365, repository=_Repo(), as_of="2025-06-30")
    v = {"notes": [], "assumptions": {}}
    svc._annotate_beta(v, ValuationEngine12M(), {})
    assert v["assumptions"]["beta_substituted"] is False and "beta_sensitivity" not in v


def test_snapshot_reports_missing_items():
    w = _wide()
    w.loc[20240, ["short_term_debt", "long_term_debt"]] = np.nan
    snap = fr.valuation_snapshot(w, 50_000.0, period="year")
    assert "vay nợ" in snap["data_gaps"]


def test_assumption_warnings_render():
    from streamlit.testing.v1 import AppTest

    def script():
        import sys
        sys.path.insert(0, ".")
        from giao_dien.thi_truong import _assumption_warnings
        _assumption_warnings({
            "notes": ["GIẢ ĐỊNH THAY THẾ: beta đo được không đáng tin cậy (x) → Ke tính với β = 1,0."],
            "assumptions": {"beta_substituted": True},
            "beta_sensitivity": [{"beta": 0.8, "ke": 0.104, "target_12m": 60000, "expected_return": 12.0},
                                 {"beta": 1.0, "ke": 0.12, "target_12m": 55000, "expected_return": 5.0, "is_used": True}],
            "data_gaps": [{"item": "vay nợ", "year": 2024, "methods": ["DCF"], "impact": "cao", "impact_pct": 0.2,
                           "direction": "giá trị vốn chủ có thể bị THỔI PHỒNG"}]})

    at = AppTest.from_function(script, default_timeout=60).run()
    assert not at.exception
    assert any("GIẢ ĐỊNH THAY THẾ" in w.value for w in at.warning)
    assert any("vay nợ" in e.value for e in at.error)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_financial_forecast.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Kiểm thử Forecast Engine (analytics/financial_forecast.py).
Dữ liệu TỔNG HỢP có tham số biết trước để kiểm tra công thức; không dùng ở production.
"""


import numpy as np
import pandas as pd
import pytest

from core.du_phong import FinancialForecaster, backtest_forecast, build_ttm, quarters_available, robust_growth
from core.cau_hinh import load_config

SH = 1_000_000_000
NONFIN = {"type": "nonfinancial", "sector": "default"}
G, M, DA, CAPEX, NWC, TAX, PAY = 0.10, 0.20, 0.05, 0.06, 0.10, 0.20, 0.40


def nonfin(years=range(2018, 2026), g=G, rev0=10_000e9, interest=200e9, extra=None):
    rows = {}
    eq = 8_000e9
    for i, y in enumerate(years):
        rev = rev0 * (1 + g) ** i
        ebitda = rev * M
        da = rev * DA
        pbt = ebitda - da - interest
        ni = pbt * (1 - TAX)
        eq = eq + ni * (1 - PAY)
        rows[y * 10] = {"revenue": rev, "profit_before_tax": pbt, "interest_expense": -interest, "depreciation": da,
                        "income_tax": -pbt * TAX, "net_income": ni, "net_income_parent": ni, "capex": -rev * CAPEX,
                        "receivables": rev * 0.15, "inventory": rev * 0.05, "payables": rev * 0.10,
                        "dividends_paid": -ni * PAY, "equity": eq, "minority_interest": 0.0, "total_assets": eq * 2,
                        # không có thu nhập tài chính → EBIT cốt lõi (LN gộp − CPBH − CPQL) = EBIT toàn phần
                        "gross_profit": ebitda - da + rev * 0.10, "selling_expense": -rev * 0.06,
                        "admin_expense": -rev * 0.04,
                        "shares_outstanding": SH, **(extra or {})}
    return pd.DataFrame.from_dict(rows, orient="index")


RAW = {"forecast": {"growth_shrink": 1.0, "margin_anchor": 0.0, "ratio_anchor": 0.0, "scenario_bands": None,
                    "model_overrides": None}}


def run_test_financial_forecast(w, cfg=None, **kw):
    """cfg=RAW: tắt hiệu chỉnh bước 6 để kiểm tra công thức gốc; mặc định = cấu hình hiệu chỉnh hiện hành."""
    kw.setdefault("shares", SH)
    kw.setdefault("company", NONFIN)
    kw.setdefault("as_of", "2026-06-30")
    return FinancialForecaster(load_config(cfg) if cfg else None).forecast(annual=w, **kw)


# ── công thức phi tài chính ───────────────────────────────────────────────────

def test_nonfinancial_year1_formulas_exact():
    w = nonfin()
    r = run_test_financial_forecast(w, RAW)
    assert r["available"] and r["model"] == "nonfinancial" and r["base"]["kind"] == "FY"
    d = r["drivers"]
    assert d["growth"]["value"] == pytest.approx(G)
    assert d["ebitda_margin"]["value"] == pytest.approx(M)
    assert d["tax_rate"]["value"] == pytest.approx(TAX) and d["payout"]["value"] == pytest.approx(PAY)
    b = w.iloc[-1]
    y1 = r["scenarios"]["base"]["years"][0]
    rev = b.revenue * (1 + G)
    ebit = rev * (M - DA)
    pbt = ebit - 200e9
    ni = pbt * (1 - TAX)
    assert y1["revenue"] == pytest.approx(rev)
    assert y1["ebitda"] == pytest.approx(rev * M)
    assert y1["net_income_parent"] == pytest.approx(ni)
    assert y1["eps"] == pytest.approx(ni / SH)
    fcff = ebit * (1 - TAX) + rev * DA - rev * CAPEX - NWC * (rev - b.revenue)
    assert y1["fcff"] == pytest.approx(fcff)
    eq1 = b.equity + ni * (1 - PAY)
    assert y1["bvps"] == pytest.approx(eq1 / SH)
    assert y1["roe"] == pytest.approx(ni / ((b.equity + eq1) / 2))


def test_growth_fades_to_terminal_growth_and_horizon():
    r = run_test_financial_forecast(nonfin(), RAW)
    yrs = r["scenarios"]["base"]["years"]
    assert len(yrs) == 5
    assert yrs[0]["growth"] == pytest.approx(G)
    assert yrs[-1]["growth"] == pytest.approx(FinancialForecaster().tg["base"])


def test_scenarios_ordered_and_explained():
    r = run_test_financial_forecast(nonfin())
    eps = {s: r["valuation_inputs"][s]["eps_fwd"] for s in ("bear", "base", "bull")}
    assert eps["bear"] < eps["base"] < eps["bull"]
    for s in ("bear", "base", "bull"):
        assert r["scenarios"][s]["assumptions"] and "Tăng trưởng năm 1" in r["scenarios"][s]["assumptions"][0]


def test_valuation_inputs_schema():
    vi = run_test_financial_forecast(nonfin())["valuation_inputs"]["base"]
    for k in ("eps_fwd", "net_income_fwd", "revenue_fwd", "ebitda_fwd", "roe_fwd", "bvps_fwd", "fcff_path",
              "terminal_growth", "base_period", "applicable"):
        assert k in vi
    assert len(vi["fcff_path"]) == 5 and all(vi["applicable"].values())


def test_ntm_interpolation():
    # as_of = 30/6/2026, kỳ gốc FY2025 (31/12/2025) → NTM kết thúc 30/6/2027 ≈ 1,5 năm sau kỳ gốc
    r = run_test_financial_forecast(nonfin())
    off = r["ntm_offset_years"]
    assert off == pytest.approx(1.5, abs=0.01)
    y1, y2 = r["scenarios"]["base"]["years"][:2]
    ntm = r["scenarios"]["base"]["ntm"]
    frac = off - 1
    assert ntm["revenue"] == pytest.approx(y1["revenue"] + (y2["revenue"] - y1["revenue"]) * frac, rel=1e-4)


# ── TTM & dữ liệu quý ────────────────────────────────────────────────────────

def quarters(year_from=2024, n=10, g=G, rev_q0=3_000e9):
    rows, i = {}, 0
    y, q = year_from, 1
    for _ in range(n):
        rev = rev_q0 * (1 + g) ** (i / 4)
        pbt = rev * (M - DA) - 50e9
        rows[y * 10 + q] = {"revenue": rev, "profit_before_tax": pbt, "interest_expense": -50e9,
                            "depreciation": rev * DA, "income_tax": -pbt * TAX, "net_income": pbt * (1 - TAX),
                            "net_income_parent": pbt * (1 - TAX), "capex": -rev * CAPEX, "equity": 20_000e9,
                            "minority_interest": 0.0}
        i += 1
        q += 1
        if q == 5:
            y, q = y + 1, 1
    return pd.DataFrame.from_dict(rows, orient="index")


def test_build_ttm_requires_four_consecutive_quarters():
    q = quarters()
    t = build_ttm(q)
    assert t["key"] == 20262 and t["quarters"] == [20253, 20254, 20261, 20262]
    assert t["row"]["revenue"] == pytest.approx(q.loc[[20253, 20254, 20261, 20262], "revenue"].sum())
    assert t["row"]["equity"] == pytest.approx(q.loc[20262, "equity"])
    assert build_ttm(q.drop(index=[20254])) is None


def test_ttm_base_used_when_newer_and_discrete():
    r = run_test_financial_forecast(nonfin(), quarterly=quarters(), as_of="2026-09-30")      # Q2/2026 công bố sau 50 ngày → có
    assert r["base"]["kind"] == "TTM" and r["base"]["key"] == 20262
    assert "TTM so cùng kỳ" in r["drivers"]["growth"]["basis"]


def test_ttm_not_used_when_quarter_basis_unknown():
    r = run_test_financial_forecast(nonfin(), quarterly=quarters(), as_of="2026-09-30", quarter_basis_ok=False)
    assert r["base"]["kind"] == "FY"
    assert any("không dùng TTM" in w for w in r["warnings"])


# ── không nhìn trước (look-ahead) ────────────────────────────────────────────

def test_annual_not_released_is_excluded():
    r = run_test_financial_forecast(nonfin(), as_of="2026-03-15")            # BCTC 2025 coi như công bố từ 1/4/2026
    assert r["base"]["key"] == 20240


def test_quarter_release_lag_respected():
    q = quarters()
    kept = quarters_available(q, pd.Timestamp("2026-08-15"))          # Q2/2026 kết thúc 30/6 + 50 ngày = 19/8
    assert 20262 not in kept.index and 20261 in kept.index


def test_future_data_does_not_change_forecast():
    w = nonfin()
    a = run_test_financial_forecast(w, as_of="2025-06-30")
    future = w.copy()
    future.loc[20250, "revenue"] *= 3                                   # năm chưa công bố tại ngày dự báo
    b = run_test_financial_forecast(future, as_of="2025-06-30")
    assert a["valuation_inputs"]["base"]["eps_fwd"] == pytest.approx(b["valuation_inputs"]["base"]["eps_fwd"])


def test_backtest_uses_only_prior_years(monkeypatch):
    seen = []
    orig = FinancialForecaster.forecast

    def spy(self, **kw):
        seen.append((int(kw["annual"].index.max()), pd.Timestamp(kw["as_of"]).year))
        return orig(self, **kw)
    monkeypatch.setattr(FinancialForecaster, "forecast", spy)
    backtest_forecast(nonfin(), SH, NONFIN)
    assert seen and all(max_key // 10 < year for max_key, year in seen)


def test_backtest_error_zero_on_exact_model():
    bt = backtest_forecast(nonfin(), SH, NONFIN, config=load_config(RAW))
    s = bt["summary"]
    assert s["revenue"]["n"] >= 3 and s["revenue"]["mape"] == pytest.approx(0, abs=1e-9)
    assert s["net_income_parent"]["mape"] == pytest.approx(0, abs=1e-9)


def test_backtest_detects_error_on_shock():
    w = nonfin()
    w.loc[20230, "revenue"] *= 0.7                                     # cú sốc không dự báo được
    s = backtest_forecast(w, SH, NONFIN)["summary"]["revenue"]
    assert s["mape"] > 0.05


# ── theo ngành ────────────────────────────────────────────────────────────────

def bank(years=range(2018, 2026)):
    rows, eq, loans = {}, 50_000e9, 800_000e9
    for i, y in enumerate(years):
        loans_prev, loans = loans, loans * 1.12
        toi = 40_000e9 * 1.12 ** i
        prov = 0.01 * (loans + loans_prev) / 2
        pbt = toi * 0.6 - prov
        ni = pbt * 0.8
        eq += ni
        rows[y * 10] = {"total_operating_income": toi, "provision_expense": -prov, "profit_before_tax": pbt,
                        "income_tax": -pbt * 0.2, "net_income": ni, "net_income_parent": ni, "customer_loans": loans,
                        "equity": eq, "minority_interest": 0.0, "total_assets": eq * 12}
    return pd.DataFrame.from_dict(rows, orient="index")


def test_bank_model():
    r = run_test_financial_forecast(bank(), company={"type": "bank"})
    assert r["available"] and r["model"] == "bank"
    d = r["drivers"]
    assert d["ppop_margin"]["value"] == pytest.approx(0.6)
    assert d["credit_cost"]["value"] == pytest.approx(0.01)
    vi = r["valuation_inputs"]["base"]
    assert vi["ebitda_fwd"] is None and vi["fcff_path"] is None
    assert vi["applicable"] == {"pe_forward": True, "pb_roe": True, "ev_ebitda": False, "dcf_fcff": False}
    y1 = r["scenarios"]["base"]["years"][0]
    assert y1["profit_before_tax"] == pytest.approx(y1["ppop"] - y1["provision"])
    bear, bull = r["scenarios"]["bear"]["years"][0], r["scenarios"]["bull"]["years"][0]
    assert bear["provision"] > y1["provision"] > bull["provision"]       # chi phí tín dụng theo kịch bản


def test_securities_roe_model():
    w = nonfin()
    r = run_test_financial_forecast(w, company={"type": "securities"})
    assert r["model"] == "roe" and r["valuation_inputs"]["base"]["ebitda_fwd"] is None
    roe = r["drivers"]["roe_norm"]["value"]
    y1 = r["scenarios"]["base"]["years"][0]
    assert y1["net_income_parent"] == pytest.approx(roe * w.iloc[-1].equity)


# ── dữ liệu thiếu ─────────────────────────────────────────────────────────────

def test_missing_revenue_is_not_fabricated():
    r = run_test_financial_forecast(nonfin().drop(columns=["revenue"]))
    assert not r["available"] and "doanh thu" in r["reason"]


def test_missing_optional_items_flagged():
    w = nonfin().drop(columns=["dividends_paid", "capex"])
    r = run_test_financial_forecast(w)
    items = {g["item"] for g in r["data_gaps"]}
    assert {"cổ tức tiền mặt", "capex"} <= items
    assert r["drivers"]["capex_pct_revenue"]["value"] == pytest.approx(DA)      # giả định duy trì, có ghi rõ
    assert any("capex" in w_ for w_ in r["warnings"])


def test_missing_shares_unavailable():
    r = run_test_financial_forecast(nonfin(), shares=None)
    assert not r["available"] and "cổ phiếu" in r["reason"]


def test_cyclical_margin_warning():
    w = nonfin()
    w["profit_before_tax"] = w["profit_before_tax"] * np.array([1, 0.2, 1.8, 0.3, 1.5, 0.4, 1.6, 1.0])
    assert any("biến động mạnh" in x for x in run_test_financial_forecast(w)["warnings"])


def test_robust_growth_ignores_negative_pairs():
    s = pd.Series([100.0, 110.0, -5.0, 120.0, 132.0], index=[20200, 20210, 20220, 20230, 20240])
    g, n = robust_growth(s, 5)
    assert n == 2 and g == pytest.approx(0.1)


# ── tích hợp dịch vụ: có dự báo, Valuation Engine không đổi ─────────────────

def test_service_attaches_forecast_without_changing_valuation(monkeypatch):
    from core.du_lieu import DataRepository
    from core.pipeline import StockService
    from tests.fakes import FakeDNSE, FakeVietstock, FakeVnstock

    def repo():
        return DataRepository(arminer_client=False, vnstock_client=FakeVnstock(), dnse_client=FakeDNSE(),
                              vietstock_client=FakeVietstock(True), use_cache=False)
    inv = StockService("FPT", repository=repo()).investment_analysis()
    assert inv["forecast"]["available"] and "backtest" in inv["forecast"]
    monkeypatch.setattr(StockService, "forecast_analysis", lambda self, **k: {"available": False})
    inv2 = StockService("FPT", repository=repo()).investment_analysis()
    assert inv2["valuation"].get("target_12m") == pytest.approx(inv["valuation"].get("target_12m"))
    assert inv2["recommendation"]["label"] == inv["recommendation"]["label"]


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_forecast_step6.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Kiểm thử hồi quy Bước 6 – hiệu chỉnh Forecast Engine (co tăng trưởng, neo biên/tỷ lệ kỳ gốc, khoảng kịch bản theo
nhóm, NTM ≠ năm tài chính, kiểm tra giả định). Gồm dữ liệu tổng hợp và dữ liệu THẬT đóng gói trong app.
"""


import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.du_phong import FinancialForecaster, _path_value, backtest_forecast
from core.cau_hinh import load_config


DATA = Path(__file__).parent / "data"


# ── tham số hiệu chỉnh ───────────────────────────────────────────────────────

def test_growth_shrink_toward_terminal_growth():
    """Tăng trưởng KHÔNG đều (năm tăng năm giảm) → co mạnh s = 0,25 về g dài hạn."""
    fc = FinancialForecaster()
    w = nonfin(g=0.15)
    # 2 năm giảm doanh thu trong 5 năm gần nhất → không còn là "tăng trưởng đều"
    for k, f in ((20220, 0.80), (20240, 0.80)):
        w.loc[k, "revenue"] *= f
    r = run_test_financial_forecast(w)
    s, tg = fc.f["growth_shrink"], fc.tg["base"]
    assert s == pytest.approx(0.25)
    assert "tăng trưởng đều" not in r["drivers"]["growth"]["basis"]
    assert "co về tăng trưởng dài hạn" in r["drivers"]["growth"]["basis"]
    assert r["drivers"]["growth"]["value"] < 0.15 * 0.5 + 0.5 * tg


def test_consistent_grower_shrinks_less():
    """15/10/2026: tăng đều 15%/năm (≥ 4/5 năm tăng, trung vị ≥ 8%) → s = 0,6 thay vì 0,25 (FPT bị dự báo quá thấp)."""
    fc = FinancialForecaster()
    r = run_test_financial_forecast(nonfin(g=0.15))
    s, tg = fc.f["growth_shrink_consistent"], fc.tg["base"]
    assert s == pytest.approx(0.6)
    assert r["drivers"]["growth"]["value"] == pytest.approx(s * 0.15 + (1 - s) * tg)
    assert "tăng trưởng đều" in r["drivers"]["growth"]["basis"]


def test_bank_growth_not_shrunk():
    r = run_test_financial_forecast(bank(), company={"type": "bank"})
    r_raw = run_test_financial_forecast(bank(), RAW, company={"type": "bank"})
    assert r["drivers"]["growth"]["value"] == pytest.approx(r_raw["drivers"]["growth"]["value"])


def test_margin_anchored_to_base_and_reverts_to_long_run():
    w = nonfin()
    last = w.index[-1]
    w.loc[last, "profit_before_tax"] *= 1.5                      # biên năm gốc cao bất thường
    r = run_test_financial_forecast(w)
    m0 = (w.loc[last, "profit_before_tax"] + 200e9 + w.loc[last, "depreciation"]) / w.loc[last, "revenue"]
    d = r["drivers"]["ebitda_margin"]
    assert d["value"] == pytest.approx(m0)
    yrs = r["scenarios"]["base"]["years"]
    assert yrs[0]["ebitda_margin"] == pytest.approx(m0)
    assert yrs[-1]["ebitda_margin"] == pytest.approx(d["long_run"])     # hồi quy về trung vị dài hạn ở năm cuối
    assert d["long_run"] < m0


def test_ratio_anchor_uses_base_tax_rate():
    w = nonfin()
    last = w.index[-1]
    w.loc[last, "income_tax"] = -w.loc[last, "profit_before_tax"] * 0.10
    assert run_test_financial_forecast(w)["drivers"]["tax_rate"]["value"] == pytest.approx(0.10)
    assert run_test_financial_forecast(w, RAW)["drivers"]["tax_rate"]["value"] == pytest.approx(0.20)


def test_scenarios_use_calibrated_group_bands():
    r = run_test_financial_forecast(nonfin())
    band = load_config()["forecast"]["scenario_bands"][r["scenario_group"]]
    g = r["drivers"]["growth"]["value"]
    lo, hi = FinancialForecaster().f["growth_bounds"]
    bear1 = r["scenarios"]["bear"]["years"][0]["growth"]
    bull1 = r["scenarios"]["bull"]["years"][0]["growth"]
    assert bear1 == pytest.approx(np.clip(g + band["growth"]["lo"], lo, hi))
    assert bull1 == pytest.approx(np.clip(g + band["growth"]["hi"], lo, hi))
    assert any("phân vị" in x for x in r["scenarios"]["bear"]["assumptions"])


def test_cyclical_group_detected_from_published_data_only():
    w = nonfin()
    w["profit_before_tax"] = w["profit_before_tax"] * np.array([1, 0.2, 1.8, 0.3, 1.5, 0.4, 1.6, 1.0])
    assert run_test_financial_forecast(w)["scenario_group"] == "cyclical"
    w2 = nonfin()
    w2.loc[20250, "profit_before_tax"] *= 0.1                    # năm chưa công bố ở ngày dự báo
    assert run_test_financial_forecast(w2, as_of="2026-03-15")["scenario_group"] == "stable"


# ── NTM ≠ năm tài chính ──────────────────────────────────────────────────────

def test_ntm_and_fy1_are_distinct_and_labelled():
    r = run_test_financial_forecast(nonfin(), as_of="2026-06-30")                         # kỳ gốc FY2025, NTM kết thúc 30/6/2027
    vi = r["valuation_inputs"]["base"]
    assert vi["fy1_label"] == "FY2026" and vi["fy1_period_end"] == "2026-12-31"
    assert vi["ntm_window_end"] == "2027-06-30"
    assert vi["eps_fwd"] != pytest.approx(vi["eps_fy1"])          # NTM nằm giữa FY2026 và FY2027
    y1, y2 = r["scenarios"]["base"]["years"][:2]
    assert min(y1["eps"], y2["eps"]) <= vi["eps_fwd"] <= max(y1["eps"], y2["eps"])
    assert vi["fcff_period_ends"][0] == "2026-12-31"


def test_ntm_equals_fy1_when_window_matches_fiscal_year():
    r = run_test_financial_forecast(nonfin(), as_of="2025-12-31")
    vi = r["valuation_inputs"]["base"]
    assert r["base"]["key"] == 20240                              # FY2025 chưa công bố
    assert vi["eps_fwd"] == pytest.approx(r["scenarios"]["base"]["years"][1]["eps"])   # NTM = FY2026 = năm 2 từ FY2024


def test_ntm_roe_uses_ntm_window_equity():
    r = run_test_financial_forecast(nonfin())
    ntm = r["scenarios"]["base"]["ntm"]
    assert ntm["roe"] == pytest.approx(r["valuation_inputs"]["base"]["roe_fwd"])
    assert ntm["roe"] > 0


def test_path_value_does_not_guess_missing_endpoint():
    pts = [{"x": 100.0}, {"x": None}, {"x": 300.0}]
    assert _path_value(pts, "x", 0.5) is None
    assert _path_value(pts, "x", 2.0) == pytest.approx(300.0)
    assert _path_value([{"x": 100.0}, {"x": 200.0}], "x", 0.25) == pytest.approx(125.0)


def test_ntm_interpolation_validated_on_real_vietcap_ttm():
    """EBITDA TTM thật (Vietcap): nội suy giữa hai năm tài chính THỰC TẾ ước lượng TTM giữa năm sát hơn rõ rệt so với
    dùng năm tài chính kế tiếp làm NTM (lỗi nhầm FY với NTM)."""
    d = json.loads((DATA / "vci_ttm_ebitda_samples.json").read_text(encoding="utf-8"))["data"]
    ape_i, ape_fy = [], []
    for recs in d.values():
        s = {(r["year"], r["q"]): r["ebitda"] for r in recs}
        fy = {y: v for (y, q), v in s.items() if q == 5}
        ok = {y for y in fy if (y, 4) in s and abs(s[(y, 4)] / fy[y] - 1) < 1e-6}   # bỏ năm nguồn không nhất quán
        for y in fy:
            for q in (1, 2, 3):
                if {y + 1, y + 2} <= ok and (y + 2, q) in s:
                    a, b, act = fy[y + 1], fy[y + 2], s[(y + 2, q)]
                    ape_i.append(abs(_path_value([{"x": a}, {"x": b}], "x", q / 4) / act - 1))
                    ape_fy.append(abs(a / act - 1))
    assert len(ape_i) >= 30
    assert np.median(ape_i) < 0.06 and np.median(ape_i) < np.median(ape_fy) / 2


# ── kiểm tra giả định ────────────────────────────────────────────────────────

def test_share_growth_warning_and_constant_share_assumption():
    w = nonfin()
    w["shares_outstanding"] = SH * 1.3 ** np.arange(len(w))
    r = run_test_financial_forecast(w, shares=float(w["shares_outstanding"].iloc[-1]))
    assert any("Số cổ phiếu tăng mạnh" in x for x in r["warnings"])
    assert r["drivers"]["share_count"]["hist_growth_median"] == pytest.approx(0.3)


def test_shares_vs_charter_capital_mismatch_warning():
    w = nonfin(extra={"charter_capital": SH * 10_000 * 1.2})
    assert any("vốn điều lệ" in x for x in run_test_financial_forecast(w)["warnings"])


def test_abnormal_implied_interest_rate_warning():
    w = nonfin(extra={"short_term_debt": 100e9, "long_term_debt": 0.0})     # lãi vay 200 tỷ / nợ 100 tỷ
    r = run_test_financial_forecast(w)
    assert r["drivers"]["implied_interest_rate"]["value"] == pytest.approx(2.0)
    assert any("Lãi suất ngầm định" in x for x in r["warnings"])


def test_volatile_capex_and_nwc_warnings():
    w = nonfin()
    w["capex"] = -w["revenue"] * np.array([0.01, 0.3, 0.02, 0.25, 0.01, 0.3, 0.02, 0.2])
    w["inventory"] = w["revenue"] * np.array([0.1, 0.9, 0.1, 0.8, 0.1, 0.9, 0.1, 0.9])
    ws = run_test_financial_forecast(w)["warnings"]
    assert any("CAPEX/doanh thu biến động" in x for x in ws)
    assert any("Vốn lưu động/doanh thu dao động" in x for x in ws)


# ── hồi quy trên dữ liệu THẬT đóng gói (BCTC năm arminer) ───────────────────

def _real_annual(sym):
    from core.du_lieu import DataRepository, _STATEMENT_CODE
    from core.du_lieu import canonicalize
    from core.nguon_du_lieu import ArminerClient
    c, parts = ArminerClient(), []
    if not c.available():
        pytest.skip("Không có dữ liệu BCTC đóng gói")
    for st in ("income_statement", "balance_sheet", "cash_flow"):
        df = c.get_financial_statement(sym, st)
        if df is not None and not df.empty:
            w = canonicalize(df, _STATEMENT_CODE[st], unit_factor=1.0)
            parts.append(DataRepository._align_period(w, "year", _STATEMENT_CODE[st]))
    out = parts[0]
    for p in parts[1:]:
        out = out.combine_first(p)
    return out.sort_index()


@pytest.mark.parametrize("sym,ctype", [("FPT", "nonfinancial"), ("VNM", "nonfinancial"), ("VCB", "bank"),
                                       ("HPG", "nonfinancial")])
def test_real_backtest_no_worse_than_step5(sym, ctype):
    from core.phan_tich_co_ban import shares_series
    w = _real_annual(sym)
    sh = float(shares_series(w).dropna().iloc[-1])
    comp = {"type": ctype, "sector": "default"}
    new = backtest_forecast(w, sh, comp)["summary"]["net_income_parent"]
    old = backtest_forecast(w, sh, comp, config=load_config(RAW))["summary"]["net_income_parent"]
    assert new["n"] == old["n"] >= 8
    assert new["median_ape"] <= old["median_ape"] + 0.02          # không xấu đi (dung sai 2 điểm %)
    assert new["coverage"] >= old["coverage"]                      # khoảng kịch bản phủ thực tế tốt hơn hoặc bằng


def test_negative_growth_shrunk_asymmetrically():
    """Kẽ hở 3: tăng trưởng âm không bị kéo về ≈ 0% bởi g dài hạn dương (co bất đối xứng, s = 0,75)."""
    fc = FinancialForecaster()
    r = run_test_financial_forecast(nonfin(g=-0.08))
    d = r["drivers"]["growth"]
    s_neg, tg = fc.f["growth_shrink_negative"], fc.tg["base"]
    assert s_neg == pytest.approx(0.75)
    assert d["value"] == pytest.approx(s_neg * -0.08 + (1 - s_neg) * tg, abs=1e-9)
    assert d["value"] < -0.05                       # co đối xứng (0,25) sẽ cho ≈ +0,6%
    assert "bất đối xứng" in d["basis"]


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_review_round1.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Đợt 1 sửa theo nhận xét báo cáo FPT (14/10/2026): chất lượng lợi nhuận, số CP hiện hành, cổ tức công bố,
độ tin cậy (Bull/Bear, giá trị cuối kỳ, Rf), Bear theo bội số hiện tại, độ nhạy DCF WACC × g."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core import phan_tich_co_ban as fr
from core.phan_tich_co_ban import FinancialHealthEngine
from core.dinh_gia import _dividend
from core.nguon_du_lieu import parse_dividends


B = 1e9
FPT = {   # số liệu FPT 2024–2025 (tỷ đồng) theo báo cáo người dùng xuất
    "revenue": [62849, 70113], "gross_profit": [23698, 25889], "selling_expense": [-6116, -7563],
    "admin_expense": [-7074, -7337], "operating_profit": [11025, 12952], "financial_income": [1936, 2977],
    "financial_expense": [-1812, -1672], "associates_income": [0, 0], "profit_before_tax": [11070, 13044],
    "net_income": [9427, 11232], "net_income_parent": [7857, 9376], "cfo": [11704, 10136], "capex": [-3275, -5098],
    "total_assets": [72000, 88142], "equity": [35728, 43748], "current_assets": [45536, 58137],
    "current_liabilities": [34836, 41525], "long_term_debt": [501, 1904], "equity_issued": [163, 1196],
    "charter_capital": [14711, 17035],
}


def fpt_wide():
    w = pd.DataFrame({k: [x * B for x in v] for k, v in FPT.items()}, index=[20240, 20250])
    w["shares_outstanding"] = w["charter_capital"] / 10000
    return w


def test_earnings_quality_flags_fpt_2025():
    q = fr.earnings_quality(fpt_wide())
    assert q["core_growth"] == pytest.approx((10989 / 10508 - 1) * 100, rel=1e-3)
    assert q["non_core_share_of_op_growth"] == pytest.approx(75.0, abs=0.5)
    assert q["fcf_growth"] == pytest.approx((5038 / 8429 - 1) * 100, rel=1e-3)
    texts = " ".join(f["text"] for f in q["flags"])
    assert "thu nhập tài chính" in texts and "FCF giảm 40%" in texts and "CFO giảm 13%" in texts
    assert q["verdict"] in ("Yếu", "Cần lưu ý")


def test_health_uses_core_growth_and_quality_penalty():
    w = pd.concat([pd.DataFrame({"cfo": [9517 * B]}, index=[20230]), fpt_wide()]).sort_index()
    h = FinancialHealthEngine().score(fr.compute_ratios(w, "year"), w, {"type": "nonfinancial", "sector": "technology"})
    growth = next(g for g in h["groups"] if g["key"] == "growth")
    keys = [m["key"] for m in growth["metrics"]]
    assert "core_profit_growth" in keys and "net_income_growth" not in keys
    assert any("thu nhập tài chính" in n for n in h["notes"])
    assert h.get("quality_penalty", 0) >= 5
    cfo = next(m for g in h["groups"] for m in g["metrics"] if m["key"] == "cfo_trend")
    assert "-13%" in cfo["display"]                         # không còn ghi "tăng" khi CFO giảm so với năm trước


def test_snapshot_uses_current_share_count():
    w = fpt_wide()
    now = {"shares": 1_703.5e6 * 1.15, "source": "test"}
    v0 = fr.valuation_snapshot(w, 57_100, "year")
    v1 = fr.valuation_snapshot(w, 57_100, "year", shares_now=now)
    assert v1["market_cap"] == pytest.approx(57_100 * now["shares"])
    assert v1["pe"] == pytest.approx(v0["pe"] * 1.15, rel=1e-6)
    assert v1["share_note"] and v0["eps_basis"] == "năm 2025"


def test_parse_dividends_percent_and_value():
    tcbs = pd.DataFrame({"exercise_date": ["15/08/2026", "10/12/2025", "01/06/2025"], "cash_year": [2026, 2025, 2025],
                         "cash_dividend_percentage": [0.1, 0.1, 0.15], "issue_method": ["cash", "cash", "share"]})
    d = parse_dividends(tcbs)
    assert list(d["dps"]) == [1000.0, 1000.0]
    res = {"notes": []}
    dps = _dividend(pd.DataFrame(), 1e9, 57_100, res, d, pd.Timestamp("2026-10-14"))
    assert dps == 2000.0 and "đã công bố" in res["dividend_basis"]


def test_bear_capped_at_current_multiple_and_confidence_rules():
    w = make_wide()
    f = fc(w)
    v = val(w, forecast=f)
    caps = v.get("bear_caps") or {}
    assert "pe" in caps
    bear_pe = v["scenarios"]["bear"]["methods"].get("pe")
    if bear_pe:
        assert bear_pe["multiple"] <= caps["pe"] + 1e-9
    # Rf chưa có nguồn → trần "Trung bình"; Bull/Bear vượt ngưỡng cấu hình (4 lần từ 15/10/2026) → bị trừ điểm
    assert v["confidence"] in ("Trung bình", "Thấp")
    lim = v["assumptions"].get("scenario_max_ratio") or 4.0
    hit = any("biên độ kịch bản" in r for r in v["confidence_detail"]["reasons"])
    if v.get("scenario_ratio"):
        assert hit == (v["scenario_ratio"] > lim)


def test_dcf_sensitivity_grid():
    w = make_wide()
    v = val(w, forecast=fc(w))
    s = v.get("dcf_sensitivity")
    if s is None:
        pytest.skip("DCF không hợp lệ trên dữ liệu tổng hợp")
    mid = s["grid"][2][2]
    dcf = next(m for m in v["methods"] if m["key"] == "dcf")
    assert mid == pytest.approx(dcf["fair"], rel=1e-6)
    assert s["grid"][0][2] > mid > s["grid"][4][2]          # WACC cao hơn → giá trị thấp hơn


# ── Đợt 2: đổi phạm vi hợp nhất (FPT Telecom → công ty liên kết từ 1/1/2026), số liệu quý thật từ check_FPT.txt ──
FPT_Q = pd.DataFrame({
    "revenue": [15902.8, 17607.8, 16058.1, 16624.7, 17204.5, 20225.4, 12480.0, 13788.5],
    "net_income": [2478.6, 2500.8, 2595.6, 2740.3, 2901.5, 2995.0, 2476.8, 2570.3],
    "net_income_parent": [2088.9, 2094.7, 2174.3, 2257.5, 2434.8, 2509.5, 2487.4, 2567.6],
}, index=[20243, 20244, 20251, 20252, 20253, 20254, 20261, 20262]) * B


def test_detect_scope_change_fpt_2026():
    sc = fr.detect_scope_change(FPT_Q)
    assert sc["detected"] and sc["active"] and sc["quarters_new"] == 2
    assert "Q1/2026" in sc["since"] or "2026" in sc["since"]
    # chưa có quý 2026 → không phát hiện
    assert not fr.detect_scope_change(FPT_Q.iloc[:6])["detected"]


def test_scope_change_blocks_revenue_based_methods():
    w = make_wide()
    f = fc(w)
    f["scope_change"] = {"active": True, "detected": True, "since": "Q1/2026", "quarters_new": 2, "text": "đổi phạm vi"}
    v = val(w, forecast=f)
    keys = {m["key"] for m in v["methods"]}
    assert "ev_ebitda" not in keys and "dcf" not in keys
    assert any("phạm vi hợp nhất" in r for r in v["confidence_detail"]["reasons"])


EVENTS = pd.DataFrame({
    "event_code": ["ISS", "AIS", "DDIND", "DIV"],
    "category": ["DIVIDEND", "OTHER", "MAJOR_SHAREHOLDER_TRADING", "DIVIDEND"],
    "event_title_vi": ["Phát hành cổ phiếu - Cổ phiếu thưởng tỷ lệ 10.0%", "FPT - Niêm yết bổ sung 10.819.301 cổ phiếu",
                       "Nguyễn Văn Khoa - Đăng kí Mua 428,368 FPT", "Trả cổ tức đợt 2/2025 bằng tiền, 1.000 đồng/CP"],
    "exright_date": ["2026-09-21T00:00:00", None, None, "2026-06-10T00:00:00"],
    "exercise_ratio": [0.1, np.nan, np.nan, np.nan],
    "listing_date": [np.nan, np.nan, np.nan, np.nan],
    "value_per_share": [np.nan, np.nan, np.nan, 1000.0],
})


def test_share_and_cash_dividend_events():
    from core.nguon_du_lieu import parse_cash_dividend_events, parse_share_events
    ev = parse_share_events(EVENTS)
    assert len(ev) == 1 and ev[0]["ratio"] == pytest.approx(0.1) and ev[0]["listed"] is None
    d = parse_cash_dividend_events(EVENTS)
    assert list(d["dps"]) == [1000.0]


def test_bonus_shares_applied_after_listed_count():
    from core.pipeline import StockService

    class Repo:
        def get_company_events(self, s):
            return EVENTS
    svc = StockService.__new__(StockService)
    svc.symbol, svc.as_of, svc.repo = "FPT", pd.Timestamp("2026-10-14"), Repo()
    out = svc._apply_share_events({"shares": 1_714_326_422.0, "source": "Số CP niêm yết hiện hành", "listed_basis": True})
    assert out["shares"] == pytest.approx(1_714_326_422 * 1.1)
    assert "21/09/2026" in out["note"]
    # số CP quý 2/2026 (trước GDKHQ) cũng phải cộng; số CP quý 4/2026 (sau GDKHQ) thì không
    q2 = svc._apply_share_events({"shares": 1.7e9, "source": "Q2", "key": 20262})
    assert q2["shares"] == pytest.approx(1.87e9)
    svc.as_of = pd.Timestamp("2027-03-01")
    q4 = svc._apply_share_events({"shares": 1.9e9, "source": "Q4", "key": 20264})
    assert q4["shares"] == pytest.approx(1.9e9)


def test_source_conflict_rejects_mislabeled_quarters():
    from core.du_lieu import merge_financial_sources, source_conflict
    vci = FPT_Q.copy()
    kbs = pd.DataFrame({"revenue": [13788.5, 16058.1, 20225.5, 17204.5], "net_income": [2570.4, 2595.6, 2988.1, 2901.5]},
                       index=[20253, 20254, 20261, 20262]) * B          # KBS gắn sai kỳ (thật ra Q2/26, Q1/25, Q4/25, Q3/25)
    assert source_conflict(vci, kbs)
    rej = []
    vals, src = merge_financial_sources([("vnstock_vci", vci), ("vnstock_kbs", kbs)], rej)
    assert rej and rej[0]["source"] == "vnstock_kbs"
    assert set(pd.unique(src.values.ravel())) == {"vnstock_vci"}
    ok = vci.loc[[20253, 20254]].copy()
    assert source_conflict(vci, ok) is None


def test_earnings_quality_negative_prior_year_no_crash():
    """VJC 2021: LN cốt lõi & LNST năm trước âm → % tăng trưởng không tính được (None) – không được lỗi định dạng."""
    w = fpt_wide()
    w.loc[20240, ["gross_profit", "net_income", "net_income_parent"]] = [5000 * B, -2000 * B, -2000 * B]
    w.loc[20240, "operating_profit"] = -30000 * B           # LN HĐKD năm trước lỗ nặng → phần tăng ngoài cốt lõi ≥ 50%
    q = fr.earnings_quality(w)
    assert q["core_growth"] is None and q["net_income_growth"] is None
    assert any("—" in f["text"] for f in q["flags"])


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_review_gk.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Sửa theo file góp ý GK (BÀI GK – GPM1, 15/10/2026): EPS/BVPS điều chỉnh cùng mẫu số, điểm Định giá dự phòng,
MDD cùng khung 1 năm, giải thích điểm cơ hội ↔ khuyến nghị 12 tháng."""
import numpy as np
import pandas as pd
import pytest

from core import phan_tich_co_ban as fr



def test_adjusted_eps_matches_valuation_eps():
    w = fpt_wide()
    now = {"shares": 1_885.8e6, "source": "test"}
    s = fr.summarize(w, "year", 58_000, shares_now=now)
    r = s["ratios"]
    # kỳ gần nhất: EPS điều chỉnh = LNST mẹ / CP hiện hành = EPS dùng cho P/E
    assert r.loc[20250, "eps"] == pytest.approx(9376e9 / 1_885.8e6, rel=1e-6)
    assert r.loc[20250, "eps"] == pytest.approx(s["valuation"]["eps_ttm"], rel=1e-6)
    assert r.loc[20250, "bvps"] == pytest.approx(s["valuation"]["bvps"], rel=1e-6)
    # cột gốc vẫn giữ
    assert r.loc[20250, "eps_reported"] == pytest.approx(9376e9 / 1_703.5e6, rel=1e-6)
    # kỳ trước: hồi tố phần CP thưởng (loại phần phát hành thu tiền), EPS điều chỉnh < EPS báo cáo
    bonus = (1_703.5 / 1_471.1) / (1 + 1196 / 35728)
    exp = 7857e9 / (1_471.1e6 * bonus * (1_885.8 / 1_703.5))
    assert r.loc[20240, "eps"] == pytest.approx(exp, rel=1e-4)


def test_no_adjustment_when_shares_constant():
    w = fpt_wide()
    w["shares_outstanding"] = 1_703.5e6
    s = fr.summarize(w, "year", 58_000)
    assert "eps_reported" not in s["ratios"].columns


def test_fallback_valuation_score_uses_history_and_profile():
    from core.dinh_gia import ValuationEngine
    peers = {"pe": 9.1, "pb": 0.75, "pe_capw": 14.0, "pb_capw": 2.5}
    ve = ValuationEngine("FPT", 58_000, peer_stats=peers, eps_override=4_972, bvps_override=19_347)
    hist = {"pe": {2021: 20.0, 2022: 18.0, 2023: 19.0, 2024: 21.0, 2025: 17.0}, "pb": {}}
    tech = {"pe": 40, "dcf": 30, "ev_ebitda": 20, "ddm": 10}
    s = ve.compute_valuation_score(history=hist, profile_weights=tech, profile_label="Công nghệ / dịch vụ")
    assert s["components"]["pb"]["score"] is None and s["components"]["pb"]["max"] == 0
    pe = s["components"]["pe"]
    assert pe["max"] == 100 and pe["vs_history"] < 1 and "lịch sử 5 năm" in pe["method"] and "vốn hóa" in pe["method"]
    # P/E 11,7x: rẻ hơn lịch sử (19x) > 30% → 1.0; so với trung vị vốn hóa 14x → 0.7 → (1+0.7)/2 = 85
    assert s["score"] == 85
    old = ValuationEngine("FPT", 58_000, peer_stats={"pe": 9.1, "pb": 0.75}, eps_override=4_972,
                          bvps_override=19_347).compute_valuation_score()
    assert old["score"] < s["score"]                     # cách cũ (chỉ trung vị cào bằng, P/B 50%) chấm rất thấp


def test_weighted_median_by_market_cap():
    from core.phan_tich_co_ban import weighted_median
    vals, caps = [5.0, 6.0, 7.0, 20.0], [1.0, 1.0, 1.0, 100.0]
    assert weighted_median(vals, caps, "pe") == 20.0
    assert weighted_median([5.0, 6.0], [1.0, 1.0], "pe") is None


def test_mdd_one_year_window_in_risk_pillar():
    from core.du_lieu import DataRepository
    from core.pipeline import StockService
    from tests.fakes import FakeDNSE, FakeVietstock, FakeVnstock
    repo = DataRepository(arminer_client=False, vnstock_client=FakeVnstock(), dnse_client=FakeDNSE(),
                          vietstock_client=FakeVietstock(True), pdf_financial_loader=lambda s, p: pd.DataFrame(),
                          use_cache=False)
    svc = StockService("FPT", days=1100, repository=repo)
    px = svc.get_price_df()["close"].astype(float).tail(250)
    exp = abs(float(((px / px.cummax()) - 1).min()) * 100)
    a = svc.full_analysis()
    comp = (a.get("opportunity_score") or {}).get("risk_detail", {}).get("components", {}).get("drawdown")
    assert comp is not None
    assert comp["max_drawdown_pct"] == pytest.approx(exp, abs=0.1)
