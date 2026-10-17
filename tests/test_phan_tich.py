"""
tests/test_phan_tich.py – kiểm thử, gộp từ 5 file (15/10/2026).

MỤC LỤC
  • tests/test_core_ebit_sign.py – EBIT cốt lõi – cách 2 (thiếu LN gộp/CP bán hàng/CP quản lý): CP tài chính quy về dương theo quy ước dấu của chuỗi.
      hàm/lớp chính: test_negative_convention_with_reversal_year, test_positive_convention_with_reversal_year, test_expense_positive_keeps_nan_and_zero
  • tests/test_technical.py – Unit tests for TechnicalAnalyzer.
      hàm/lớp chính: test_technical_indicators_calculation, test_signals_detection, test_technical_scoring_bounds
  • tests/test_opportunity_score.py – Unit tests for OpportunityScorer.
      hàm/lớp chính: test_scorer_all_dimensions, test_scorer_with_missing_groups
  • tests/test_strategies.py – Kiểm thử chiến lược nhóm (File 1). Bot 4 tầng (File 2) đã bỏ khỏi app (14/10/2026).
      hàm/lớp chính: test_indicators_liquidity_and_data_rules, test_rs_lagged_returns_and_cross_rank, test_signal_rules_buy_and_sell, test_position_size_caps, test_backtest_next_open_costs_and_t2, test_latest_signals_priority
  • tests/test_news_insight.py – Nhận định tin tức: gộp tin trùng chủ đề, tâm lý, chủ đề – ý nghĩa, tóm tắt giao dịch nội bộ / cổ phiếu thưởng.
      hàm/lớp chính: test_clusters_sentiment_and_themes, test_event_summary
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_core_ebit_sign.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""EBIT cốt lõi – cách 2 (thiếu LN gộp/CP bán hàng/CP quản lý): CP tài chính quy về dương theo quy ước dấu của chuỗi."""
import numpy as np
import pandas as pd
import pytest

from core.phan_tich_co_ban import core_ebit_ebitda, expense_positive


def _wide(fe):
    idx = [20210, 20220, 20230, 20240]
    return pd.DataFrame({"operating_profit": [100.0] * 4, "financial_income": [10.0] * 4,
                         "financial_expense": fe, "associates_income": [0.0] * 4, "depreciation": [5.0] * 4},
                        index=idx)


def test_negative_convention_with_reversal_year():
    # quy ước "chi phí ghi âm" (vnstock); năm 2024 hoàn nhập → CP tài chính = +8 (thu nhập)
    ebit, _, m = core_ebit_ebitda(_wide([-20.0, -25.0, -30.0, 8.0]))
    assert list(ebit.iloc[:3]) == pytest.approx([110.0, 115.0, 120.0])
    assert ebit.iloc[3] == pytest.approx(100 - 10 - 8)       # trị tuyệt đối cũ cho 100 − 10 + 8 = 98
    assert m.iloc[0] == "op_adj"


def test_positive_convention_with_reversal_year():
    ebit, _, _ = core_ebit_ebitda(_wide([20.0, 25.0, 30.0, -8.0]))
    assert list(ebit.iloc[:3]) == pytest.approx([110.0, 115.0, 120.0])
    assert ebit.iloc[3] == pytest.approx(100 - 10 - 8)


def test_expense_positive_keeps_nan_and_zero():
    s = expense_positive(pd.Series([np.nan, 0.0, -5.0, -7.0]))
    assert np.isnan(s.iloc[0]) and s.iloc[1] == 0 and list(s.iloc[2:]) == [5.0, 7.0]


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_technical.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Unit tests for TechnicalAnalyzer.
"""
from core.phan_tich_ky_thuat import TechnicalAnalyzer


def test_technical_indicators_calculation(sample_ohlcv_df):
    analyzer = TechnicalAnalyzer(sample_ohlcv_df)
    enriched = analyzer.compute_all()
    
    # Assert columns added
    assert "SMA_20" in enriched.columns
    assert "SMA_50" in enriched.columns
    assert "EMA_12" in enriched.columns
    assert "RSI" in enriched.columns
    assert "MACD" in enriched.columns
    assert "MACD_signal" in enriched.columns
    assert "BB_upper" in enriched.columns
    assert "BB_lower" in enriched.columns
    assert "ATR" in enriched.columns
    assert "OBV" in enriched.columns
    
    # Check RSI range [0, 100]
    valid_rsi = enriched["RSI"].dropna()
    assert len(valid_rsi) > 0
    assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all()


def test_signals_detection(sample_ohlcv_df):
    analyzer = TechnicalAnalyzer(sample_ohlcv_df)
    analyzer.compute_all()
    signals = analyzer.get_signals()
    
    assert "trend" in signals
    assert "rsi" in signals
    assert "macd" in signals
    assert "bollinger" in signals
    assert "support_resistance" in signals
    assert isinstance(signals["trend"]["score"], (int, float))


def test_technical_scoring_bounds(sample_ohlcv_df):
    analyzer = TechnicalAnalyzer(sample_ohlcv_df)
    analyzer.compute_all()
    score_res = analyzer.compute_technical_score()
    
    assert "score" in score_res
    score = score_res["score"]
    assert 0 <= score <= 100


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_opportunity_score.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Unit tests for OpportunityScorer.
"""
from core.khuyen_nghi import OpportunityScorer


def test_scorer_all_dimensions():
    scorer = OpportunityScorer()
    res = scorer.compute(
        technical_score=80.0,
        momentum_score=75.0,
        fundamental_score=85.0,
        valuation_score=70.0,
        risk_score=90.0,
    )
    
    assert "score" in res
    score = res["score"]
    assert 0 <= score <= 100
    assert "classification" in res
    assert "label" in res["classification"]
    assert "color" in res["classification"]
    assert res["coverage_pct"] == 100


def test_scorer_with_missing_groups():
    scorer = OpportunityScorer()
    res = scorer.compute(
        technical_score=70.0,
        momentum_score=None,
        fundamental_score=80.0,
        valuation_score=None,
        risk_score=70.0,
    )
    
    # Check that score is re-weighted without failing
    assert "score" in res
    score = res["score"]
    assert 0 <= score <= 100
    assert res["coverage_pct"] < 100


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_strategies.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Kiểm thử chiến lược nhóm (File 1). Bot 4 tầng (File 2) đã bỏ khỏi app (14/10/2026)."""
import numpy as np
import pandas as pd

from core import kiem_chung as gs


def _px(n=400, start=20_000.0, drift=0.001, vol=0.0, volume=2_000_000, seed=0, end="2026-09-30"):
    rng = np.random.default_rng(seed)
    d = pd.bdate_range(end=end, periods=n)
    c = start * np.exp(np.cumsum(drift + rng.normal(0, vol, n)))
    return pd.DataFrame({"timestamp": d, "open": c * 0.999, "high": c * 1.01, "low": c * 0.99, "close": c,
                         "volume": np.full(n, volume, dtype=float)})


# ───────────────────────── File 1 ─────────────────────────

def test_indicators_liquidity_and_data_rules():
    ind = gs.indicators(_px(n=300, start=20_000, volume=1_000_000))       # GTGD = 20 tỷ
    last = ind.iloc[-1]
    assert bool(last["liquid"]) and bool(last["enough"])
    low_val = gs.indicators(_px(n=300, start=20_000, volume=200_000)).iloc[-1]   # GTGD ≈ 4 tỷ < 10 tỷ
    assert not bool(low_val["liquid"])
    cheap = gs.indicators(_px(n=300, start=4_000, drift=0.0, volume=5_000_000)).iloc[-1]   # giá < 5.000
    assert not bool(cheap["liquid"])
    assert not bool(gs.indicators(_px(n=200)).iloc[-1]["enough"])          # < 260 phiên


def test_rs_lagged_returns_and_cross_rank():
    prices = {f"S{i}": _px(drift=0.0002 * i, seed=i, vol=0.001) for i in range(6)}
    panel = gs.build_panel(prices)
    rs = {s: d["rs"].iloc[-1] for s, d in panel.items()}
    assert rs["S5"] > rs["S0"] and 0 < rs["S0"] <= 100
    d = panel["S3"]
    c = d["close"]
    assert abs(d["r63"].iloc[-1] - (c.iloc[-6] / c.iloc[-6 - 63] - 1)) < 1e-12     # C(t−5)/C(t−5−63) − 1


def test_signal_rules_buy_and_sell():
    prices = {f"S{i}": _px(drift=0.0003 * (i + 1), seed=i, vol=0.002) for i in range(5)}
    prices["DOWN"] = _px(drift=-0.002, seed=9, start=60_000)
    panel = gs.build_panel(prices)
    assert panel["DOWN"]["signal"].iloc[-1] == "BÁN"                     # Close < SMA200
    top = max(panel, key=lambda s: panel[s]["rs"].iloc[-1])
    r = panel[top].iloc[-1]
    expect = "MUA" if r["anti_chasing"] <= 3 else "GIỮ"
    assert panel[top]["signal"].iloc[-1] == expect
    short = gs.build_panel({"A": _px(n=150), **{k: v for k, v in list(prices.items())[:4]}})
    assert short["A"]["signal"].iloc[-1] == "THIẾU DỮ LIỆU"


def test_position_size_caps():
    # 1% × 100tr / (3 × 500) = 666 → 600 cp; 10% vốn / 20.000 = 500 cp → 500
    assert gs.position_size(20_000, 500, 1e12, 100e6) == 500
    assert gs.position_size(20_000, 2_000, 1e12, 100e6) == 100              # 1tr/6.000 = 166 → 100
    assert gs.position_size(20_000, 500, 100e6, 100e6) == 200               # 5% × 100tr GTGD / 20.000 = 250 → 200
    assert gs.position_size(20_000, 500, 1e12, 100e6, cash=5e6) == 200      # tiền mặt
    assert gs.position_size(20_000, None, 1e12, 100e6) == 0


def test_backtest_next_open_costs_and_t2():
    prices = {f"S{i}": _px(n=700, drift=0.0004 * (i % 3 + 1), seed=i, vol=0.012) for i in range(8)}
    res = gs.backtest(prices, "2025-01-01", None)
    assert res["available"]
    tr = res["trades"]
    assert not tr.empty
    for _, t in tr.iterrows():
        o_in = prices[t["symbol"]].set_index("timestamp")["open"].get(t["entry_date"])
        assert abs(t["entry_price"] - o_in * 1.001) < 1e-6                   # giá mở cửa T+1 + trượt giá
        assert len(pd.bdate_range(t["entry_date"], t["exit_date"])) - 1 >= 3   # T+2: bán sớm nhất mở cửa D+3
    st = res["stats"]
    assert {"total_return", "cagr", "mdd", "n_trades", "win_rate", "profit_factor"} <= set(st)
    no_t2 = gs.backtest(prices, "2025-01-01", None, {"t_plus": False})
    assert no_t2["available"]


def test_latest_signals_priority():
    prices = {f"S{i}": _px(drift=0.0003 * (i + 1), seed=i, vol=0.002) for i in range(6)}
    out = gs.latest_signals(prices)
    buys = out[out["signal"] == "MUA"]
    assert list(buys["rs"]) == sorted(buys["rs"], reverse=True)
    assert all(len(c) == 8 for c in out["checks"])


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_news_insight.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Nhận định tin tức: gộp tin trùng chủ đề, tâm lý, chủ đề – ý nghĩa, tóm tắt giao dịch nội bộ / cổ phiếu thưởng."""
from core.tin_tuc import news_insight

ITEMS = [
    {"title": "3 sản phẩm, dịch vụ FPT ghi dấu ấn tại Giải thưởng Chuyển đổi số Việt Nam 2026", "source": "Chungta", "sentiment": "Trung tính"},
    {"title": "Huyền Linh và gần một thập kỷ trưởng thành từ nhà F", "source": "Chungta", "sentiment": "Trung tính"},
    {"title": "FPT khởi công tòa nhà công nghệ số hơn 1.300 tỷ đồng tại Hà Nội", "source": "Mekong ASEAN", "sentiment": "Tích cực"},
    {"title": "FPT rót 1.300 tỷ đồng xây tòa nhà công nghệ số tại phía tây Hà Nội", "source": "VnExpress", "sentiment": "Trung tính"},
    {"title": "FPT khai trương văn phòng đầu tiên tại Ai Cập", "source": "24HMoney", "sentiment": "Tích cực"},
    {"title": "Tài chính doanh nghiệp 24/7: EVF dự kiến huy động hơn 1.147 tỷ đồng, FPT khởi công", "source": "Tài chính Online", "sentiment": "Tích cực"},
    {"title": "FPT khởi công tòa nhà đầu tiên trong siêu dự án 86.000 tỷ đồng tại Hà Nội", "source": "MoneyF", "sentiment": "Tích cực"},
    {"title": "FPT bất ngờ mở văn phòng tại 'thành phố nghìn ngọn tháp', hé lộ kế hoạch tuyển dụng", "source": "CafeF", "sentiment": "Trung tính"},
    {"title": "FPT khởi công Tòa nhà Công nghệ số 01, bước đầu hiện thực hóa Khu đô thị Công viên công nghệ", "source": "CafeF", "sentiment": "Tích cực"},
    {"title": "FPT khởi công tòa nhà công nghệ ở Hà Nội", "source": "VietnamBiz", "sentiment": "Tích cực"},
]
EVENTS = [("21/09/2026", "Phát hành cổ phiếu: Cổ phiếu thưởng tỉ lệ 10.0%"),
          ("24/06/2026", "Giao dịch nội bộ: Nguyễn Văn Khoa - Đăng kí Mua 428,368 FPT"),
          ("24/06/2026", "Giao dịch nội bộ: Phạm Minh Tuấn - Đăng kí Mua 490,082 FPT"),
          ("24/06/2026", "Phát hành cổ phiếu: Phát hành cho CBCNV tỉ lệ 0.1%")]


def test_clusters_sentiment_and_themes():
    r = news_insight(ITEMS, EVENTS)
    assert r["counts"] == {"pos": 6, "neu": 4, "neg": 0} and r["tone"] == "Nghiêng tích cực"
    top = r["top"][0]
    assert top["n"] >= 4 and "capex" in top["themes"]            # các tin "khởi công tòa nhà" gộp chung
    assert r["n_topics"] < r["n"]
    assert r["themes"][0]["key"] == "capex"
    assert "Huy động vốn" not in r["flags"]                       # 1 bài tổng hợp lẻ → chưa gắn cờ


def test_event_summary():
    ev = news_insight([], EVENTS)["events"]
    assert any("2 người đăng ký MUA" in e and "0,92 triệu CP" in e for e in ev)
    assert any("Cổ phiếu thưởng tỷ lệ 10.0%" in e for e in ev)
    assert any("ESOP" in e for e in ev)
    assert news_insight([], None)["tone"] == "Chưa có tin"


def test_bank_specific_ratios_and_hidden_manufacturing_ratios():
    import pandas as pd
    from core.phan_tich_co_ban import compute_ratios, ratio_meta_for, BANK_HIDDEN_RATIOS
    w = pd.DataFrame({
        "total_operating_income": [40e12, 44e12], "net_interest_income": [30e12, 33e12],
        "profit_before_tax": [20e12, 22e12], "provision_expense": [-4e12, -4.4e12],
        "customer_loans": [500e12, 560e12], "customer_deposits": [450e12, 500e12],
        "total_assets": [800e12, 880e12], "equity": [100e12, 115e12], "net_income": [16e12, 17.6e12],
        "net_income_parent": [16e12, 17.6e12], "revenue": [40e12, 44e12],
    }, index=[20240, 20250])
    r = compute_ratios(w, "year").loc[20250]
    assert r["nim"] == pytest.approx(33e12 / 840e12 * 100)
    assert r["cir"] == pytest.approx((44e12 - 22e12 - 4.4e12) / 44e12 * 100)
    assert r["credit_cost"] == pytest.approx(4.4e12 / 530e12 * 100)
    meta = ratio_meta_for(True)
    assert list(meta)[0] in {"loan_to_deposit", "equity_to_assets", "provision_to_income", "nim", "cir", "credit_cost", "nii_share"}
    assert not (BANK_HIDDEN_RATIOS & set(meta))
