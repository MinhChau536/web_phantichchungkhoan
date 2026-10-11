"""
Kiểm thử Khuyến nghị đầu tư & Giá mục tiêu 12 tháng (Financial Health / Valuation / Risk / Recommendation / Backtest).
Dữ liệu ở đây là dữ liệu TỔNG HỢP cho kiểm thử (không dùng ở production).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analytics import financial_ratios as fr
from analytics.financial_health import FinancialHealthEngine, lin_score
from analytics.recommendation import recommend, recommend_investment
from analytics.reco_backtest import backtest_recommendations
from analytics.risk_assessment import assess_risk
from analytics.valuation_engine import NOT_ENOUGH, ValuationEngine12M, annual_available, point_in_time
from config.investment_model import classify_company, load_config

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
    w = make_wide(loss_years=(2024, 2025))
    v = value(w, price=50_000)
    assert "pe" not in {m["key"] for m in v["methods"]}
    assert any(m == "P/E" for m, _ in v["invalid"])


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
    w = make_wide().drop(columns=["cfo"])
    assert any(m == "DCF" and "CFO" in r for m, r in value(w)["invalid"])


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


def test_reco_thresholds():
    assert recommend_investment(H(80), _val(25), LOW_RISK)["rating"] == "MUA"
    assert recommend_investment(H(75), _val(20), LOW_RISK)["rating"] == "MUA"            # đúng ngưỡng
    assert recommend_investment(H(74.9), _val(25), LOW_RISK)["rating"] == "NẮM GIỮ"
    assert recommend_investment(H(80), _val(19.9), LOW_RISK)["rating"] == "NẮM GIỮ"
    assert recommend_investment(H(80), _val(-10.1), LOW_RISK)["rating"] == "BÁN"
    assert recommend_investment(H(80), _val(-10.0), LOW_RISK)["rating"] == "NẮM GIỮ"
    cfg = load_config({"recommendation": {"buy_min_return": 15.0}})
    assert recommend_investment(H(80), _val(16), LOW_RISK, cfg)["rating"] == "MUA"


def test_reco_good_company_but_overvalued_is_sell():
    r = recommend_investment(H(92), _val(-25), LOW_RISK)
    assert r["rating"] == "BÁN" and r["label_holder"] == "BÁN" and r["label_non_holder"] == "TRÁNH MUA"
    assert recommend_investment(H(92), _val(-25), LOW_RISK, holder=False)["label"] == "TRÁNH MUA"
    assert any("định giá đắt" in x for x in r["reasons"])


def test_reco_weak_company_high_upside_not_buy():
    r = recommend_investment(H(40), _val(60), LOW_RISK)
    assert r["rating"] == "NẮM GIỮ" and r["label_non_holder"] == "THEO DÕI"
    assert any("bẫy giá trị" in x for x in r["reasons"])


def test_reco_never_buy_on_health_only_never_sell_on_health_only():
    assert recommend_investment(H(99), _val(0, available=False), LOW_RISK)["rating"] == "CHƯA ĐỦ CƠ SỞ"
    assert recommend_investment(H(10), _val(5), LOW_RISK)["rating"] == "NẮM GIỮ"


def test_reco_insufficient_basis_cases():
    for h, v, rk in ((H(80), _val(30, price=None), LOW_RISK),          # thiếu giá
                     (H(80), _val(30, conf="Thấp"), LOW_RISK),          # độ tin cậy thấp
                     (H(None), _val(30), LOW_RISK),                     # BCTC không đủ
                     (H(90), _val(40), SEVERE)):                        # rủi ro nghiêm trọng
        r = recommend_investment(h, v, rk)
        assert r["rating"] == "CHƯA ĐỦ CƠ SỞ" and r["rule"] == "R1" and r["reasons"]


def test_reco_trace_and_legacy_kept():
    r = recommend_investment(H(80), _val(25), LOW_RISK)
    assert r["trace"] and all({"rule", "passed", "detail"} <= set(t) for t in r["trace"])
    assert recommend({"available": True, "expected_return": 20, "upside": 18, "fair_value": 1, "confidence": "Cao"})["rating"] == "MUA"


def test_end_to_end_engines_consistent():
    w = make_wide()
    ratios = fr.compute_ratios(w, "year")
    h = FinancialHealthEngine().score(ratios, w, NONFIN)
    v = value(w)
    rk = assess_risk(w, ratios, NONFIN, valuation=v, health=h, as_of=pd.Timestamp("2026-10-09"))
    r = recommend_investment(h, v, rk)
    assert r["rating"] in ("MUA", "NẮM GIỮ", "BÁN", "CHƯA ĐỦ CƠ SỞ")
    assert r["target_12m"] == v["target_12m"] and r["health_score"] == h["score"]


# ─────────────────────────── Backtest ────────────────────────────────────────

def test_backtest_runs_point_in_time_with_costs():
    w = make_wide(years=range(2014, 2026))
    px = make_prices(w, start="2014-01-02", noise=0.05)
    idx = pd.DataFrame({"timestamp": px["timestamp"], "close": np.linspace(600, 1600, len(px))})
    res = backtest_recommendations(w, px, idx, NONFIN, cost=0.003)
    assert res["available"] and res["periods"]
    for p in res["periods"]:
        assert p["data_year"] < pd.Timestamp(p["decision_date"]).year     # chỉ BCTC đã công bố
        if p["rating"] == "MUA":
            assert p["strategy_ret"] < p["stock_ret"]                       # đã trừ phí
        else:
            assert p["strategy_ret"] == 0.0
    st = res["stats"]
    assert {"strategy_cagr", "index_cagr", "strategy_mdd", "buy_win_rate"} <= set(st) and res["conclusion"]


def test_backtest_no_data():
    assert backtest_recommendations(pd.DataFrame(), pd.DataFrame(), None, NONFIN)["available"] is False


def test_service_integration_with_fake_repo():
    from data.data_repository import DataRepository
    from services.stock_service import StockService
    from tests.fakes import FakeDNSE, FakeVietstock, FakeVnstock
    repo = DataRepository(arminer_client=False, vnstock_client=FakeVnstock(), dnse_client=FakeDNSE(),
                          vietstock_client=FakeVietstock(True), use_cache=False)
    a = StockService("FPT", repository=repo).full_analysis()
    inv = a["investment"]
    assert inv and {"health", "valuation", "risk", "recommendation", "explanation", "thesis"} <= set(inv)
    assert a["fair_value"]["model"] == "12m" and a["recommendation"]["rating"] == inv["recommendation"]["label"]
    assert not a["errors"]


def test_service_as_of_valuation_date_point_in_time():
    from data.data_repository import DataRepository
    from services.stock_service import StockService
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
    from services.stock_service import StockService
    assert StockService("FPT", repository=object(), as_of=None).as_of is None
    assert StockService("FPT", repository=object(), as_of=str(pd.Timestamp.now().date())).as_of is None
