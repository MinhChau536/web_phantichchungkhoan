"""
tests/test_khuyen_nghi.py – kiểm thử, gộp từ 4 file (15/10/2026).

MỤC LỤC
  • tests/test_multilayer.py – Khung khuyến nghị đa lớp (15/10/2026): một nhãn duy nhất từ ma trận F × T, bộ lọc loại trừ, thiếu dữ liệu.
      hàm/lớp chính: test_strong_and_uptrend_is_buy, test_strong_but_downtrend_is_accumulate, test_weak_and_downtrend_is_avoid, test_weak_but_uptrend_is_watch_speculative, test_exclusion_blocks_buy, test_insufficient_data_label, test_unknown_checks_are_reported_not_faked, test_percentile_rank_direction, test_timing_layer_redistributes_foreign_weight
  • tests/test_personalization.py – Kiểm thử báo cáo cá nhân hóa (analytics/personalization.py).
      hàm/lớp chính: test_normalize_profile_defaults_and_invalid, test_single_label_for_every_profile_risk_only_changes_weight, test_position_sizing_lot_and_stop, test_holding_and_income_goal, test_pdf_renders_personal_section
  • tests/test_step10_action.py – Bước 10: P/E tham chiếu ≤ trung vị ngành × 1,5; hành động đề xuất (khôi phục final_action) có xét xu hướng VN-Index
      hàm/lớp chính: test_pe_reference_capped_at_peer_median_times_cap, test_risk_free_status_notes, test_valuation_carries_risk_free_note, test_production_risk_free_has_source_and_date
  • tests/test_reco_trend_backtest.py – Chạy thử công cụ backtest bộ lọc xu hướng (tools/reco_trend_backtest.py) trên dữ liệu GIẢ LẬP – chỉ kiểm tra đường
      hàm/lớp chính: test_pipeline_writes_rows_without_lookahead, test_multilayer_eval_runs
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_multilayer.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Khung khuyến nghị đa lớp (15/10/2026): một nhãn duy nhất từ ma trận F × T, bộ lọc loại trừ, thiếu dữ liệu."""
import numpy as np
import pandas as pd
import pytest

from core.khuyen_nghi import multilayer_recommendation, percentile_rank, timing_layer
from core.cau_hinh import load_config


def _px(trend: float, n: int = 400, vol: float = 5e5):
    close = 50_000 * np.cumprod(np.full(n, 1 + trend))
    return pd.DataFrame({"timestamp": pd.bdate_range("2024-01-01", periods=n), "close": close, "volume": vol})


def _annual(eq=40e12, ni=(8e12, 9e12), cfo=(9e12, 10e12)):
    return pd.DataFrame({"equity": [eq * 0.9, eq], "net_income": list(ni), "cfo": list(cfo), "revenue": [60e12, 70e12]},
                        index=[20240, 20250])


def _universe(n=20):
    """Rổ so sánh: các mã có xu hướng từ −0,2%/phiên đến +0,2%/phiên (trung vị ≈ đi ngang)."""
    return {f"S{i:02d}": _px(-0.002 + 0.004 * i / (n - 1)) for i in range(n)}


GOOD_VAL = {"methods": [], "expected_return": 25.0, "confidence": "Trung bình", "assumptions": {"ke": 0.12}}


def _run(q=80, v=80, g=80, px=None, annual=None, risk=None, quarterly=8, universe="default", valuation=None, index_df=None,
         cfg=None):
    health = {"groups": [{"key": "profitability", "label": "Sinh lời", "score": q, "weight": 50},
                         {"key": "leverage", "label": "Cơ cấu vốn", "score": q, "weight": 50},
                         {"key": "growth", "label": "Tăng trưởng", "score": g, "weight": 20}]}
    qidx = [20230 + i for i in range(1, 5)] + [20240 + i for i in range(1, 5)]
    qdf = pd.DataFrame({"revenue": 1.0}, index=qidx[:quarterly])
    return multilayer_recommendation(
        health=health, summary={}, annual=_annual() if annual is None else annual, quarterly=qdf,
        price_df=_px(0.0025) if px is None else px, index_df=_px(0.001) if index_df is None else index_df,
        valuation=GOOD_VAL if valuation is None else valuation,
        multiples={"score": v}, peers={}, company={"type": "nonfinancial"}, risk=risk or {"items": []},
        cfg=cfg or load_config(), ratios=None, universe=_universe() if universe == "default" else universe, symbol="AAA")


def test_strong_and_stronger_than_market_is_buy():
    r = _run()
    assert r["label"] == "MUA" and r["F"] >= 70 and r["R"] >= 60 and r["relative"]["rank"][0] == 1


def test_f_between_65_and_70_stronger_than_market_is_buy():
    # 16/10/2026: ngưỡng "nền tảng mạnh" hạ 70 → 65 (VD: F 69, R 68 trước đây ra NẮM GIỮ)
    r = _run(q=68, v=68, g=68)
    assert 65 <= r["F"] < 70 and r["R"] >= 60 and r["label"] == "MUA"
    assert r["thresholds"]["f_strong"] == 65


def test_f_below_65_stronger_than_market_is_hold():
    r = _run(q=60, v=60, g=60)
    assert 55 <= r["F"] < 65 and r["R"] >= 60 and r["label"] == "NẮM GIỮ"


def test_good_company_weaker_than_market_is_watch():
    # Ví dụ FPT: doanh nghiệp tốt nhưng cổ phiếu yếu hơn đa số rổ VN30 + cùng ngành → THEO DÕI (không MUA)
    r = _run(px=_px(-0.0025))
    assert r["label"] == "THEO DÕI" and r["F"] >= 70 and r["R"] < 40 and "yếu hơn thị trường" in r["why"]


def _cfg_leader(pct):
    c = load_config()
    c["multilayer"]["leader_top_pct"] = pct
    return c


def test_strong_but_market_below_ma200_caps_to_accumulate():
    # không thuộc nhóm dẫn dắt (đặt top 0%) → thị trường dưới MA200 hạ MUA về TÍCH LŨY TỪNG PHẦN
    r = _run(index_df=_px(-0.002), cfg=_cfg_leader(0.0))
    assert r["label"] == "TÍCH LŨY TỪNG PHẦN" and "MA200" in r["why"]


def test_market_leader_still_buy_when_market_below_ma200():
    # 16/10/2026: cổ phiếu dẫn dắt (top 30% sức mạnh giá trong rổ) vẫn MUA dù VN-Index dưới MA200
    r = _run(index_df=_px(-0.002))
    assert r["relative"]["rank"][0] == 1 and r["label"] == "MUA"
    assert "nhóm dẫn dắt" in r["why"] and any("dưới MA200" in n for n in r["notes"])


def test_expected_return_below_cost_of_equity_blocks_buy():
    r = _run(valuation={"methods": [], "expected_return": 5.0, "confidence": "Trung bình", "assumptions": {"ke": 0.12}})
    assert r["label"] == "TÍCH LŨY TỪNG PHẦN" and "chi phí vốn" in r["why"]


def test_no_universe_falls_back_to_absolute_timing():
    r = _run(universe={})
    assert r["relative"]["fallback"] and r["R"] is not None


def test_weak_and_downtrend_is_avoid():
    r = _run(q=30, v=30, g=30, px=_px(-0.0025))
    assert r["label"] == "GIẢM TỶ TRỌNG / TRÁNH"


def test_weak_but_uptrend_is_watch_speculative():
    r = _run(q=30, v=30, g=30)
    assert r["label"] == "THEO DÕI" and "đầu cơ" in r["why"]


def test_exclusion_blocks_buy():
    bad = _annual(ni=(5e12, 6e12), cfo=(-1e12, -2e12))           # LNST dương, CFO âm 2 năm
    r = _run(annual=bad)
    assert r["label"] == "THEO DÕI" and r["blocked_by_exclusion"]
    low_liq = _run(px=_px(0.002, vol=10))                           # GTGD ~ 0,001 tỷ/phiên
    assert low_liq["label"] == "THEO DÕI"


def test_insufficient_data_label():
    r = _run(px=_px(0.002, n=120))
    assert r["label"] == "KHÔNG ĐỦ DỮ LIỆU" and not r["available"]


def test_unknown_checks_are_reported_not_faked():
    r = _run()
    unknown = [e for e in r["exclusions"] if e["status"] == "unknown"]
    assert any("Kiểm toán" in e["text"] for e in unknown)


def test_percentile_rank_direction():
    assert percentile_rank(10, [5, 8, 12, 15, 20], higher_better=True) == pytest.approx(40.0)
    assert percentile_rank(10, [5, 8, 12, 15, 20], higher_better=False) == pytest.approx(60.0)
    assert percentile_rank(10, [5, 8], min_n=5) is None


def test_quality_layer_does_not_double_count_fscore():
    r = _run()
    names = [row["name"] for row in r["layers"]["Q"]]
    assert not any("F-score" in n for n in names)
    assert sum(row["weight"] for row in r["layers"]["Q"]) == pytest.approx(100)


def test_pros_and_cons_are_readable_sentences():
    r = _run(q=90, v=30, g=90)
    assert r["pros"] and all(x.endswith("/100)") for x in r["pros"] + r["cons"])
    assert any(x.startswith("Cơ cấu vốn an toàn") or x.startswith("Đà tăng giá") for x in r["pros"])
    assert any(x.startswith("Định giá đắt") for x in r["cons"])


def test_timing_layer_redistributes_foreign_weight():
    t = timing_layer(_px(0.002), None, load_config()["multilayer"])
    foreign = next(c for c in t["components"] if "khối ngoại" in c["name"])
    assert foreign["score"] is None and t["score"] is not None


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_personalization.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Kiểm thử báo cáo cá nhân hóa (analytics/personalization.py)."""
import numpy as np
import pandas as pd

from core.khuyen_nghi import build_personal_report, normalize_profile


def _analysis(er=22.0, hs=85.0, level="Thấp", dy=1.5, conf="Cao", price=100_000.0, label="MUA"):
    rng = np.random.default_rng(0)
    close = price * np.exp(np.cumsum(rng.normal(0, 0.015, 300)))
    close = close / close[-1] * price
    px = pd.DataFrame({"close": close, "high": close * 1.01, "low": close * 0.99, "open": close})
    target = price * (1 + er / 100) - price * dy / 100
    return {
        "current_price": {"price": price},
        "technical": {"available": True, "data": px,
                      "signals": {"trend": {"name": "Tăng"}, "support_resistance": {"support": [price * 0.95]}}},
        "investment": {
            "health": {"score": hs, "groups": [{"key": "growth", "score": 70, "label": "Tăng trưởng", "metrics": []}]},
            "valuation": {"available": True, "price": price, "target_12m": target, "expected_return": er,
                          "upside": (target / price - 1) * 100, "dividend_yield": dy, "confidence": conf,
                          "scenarios": {"bear": {"target": target * 0.8}, "base": {"target": target},
                                        "bull": {"target": target * 1.2}}},
            "risk": {"level": level, "items": []},
            "recommendation": {"label": label},
            "multilayer": {"label": label, "why": f"Điểm cơ bản F … → {label}.", "hex": "#16a34a"},
        },
    }


def test_normalize_profile_defaults_and_invalid():
    p = normalize_profile({"risk": "xyz", "holder": False, "cost": 5, "capital": -1})
    assert p["risk"] == "balanced" and p["cost"] is None and p["capital"] is None


def test_single_label_for_every_profile_risk_only_changes_weight():
    a = _analysis(er=22.0, hs=78.0, level="Cao")
    bal = build_personal_report(a, {"risk": "balanced", "capital": 1e9})
    con = build_personal_report(a, {"risk": "conservative", "capital": 1e9})
    assert bal["label"] == con["label"] == "MUA"                      # một nhãn chung (khung đa lớp)
    assert con["plan"]["weight"] < bal["plan"]["weight"]               # rủi ro vượt khẩu vị → tỷ trọng thấp hơn




def test_position_sizing_lot_and_stop():
    ps = build_personal_report(_analysis(er=30.0, hs=90.0, level="Trung bình"),
                               {"risk": "balanced", "capital": 1_000_000_000})
    pl = ps["plan"]
    assert abs(pl["weight"] - 0.075) < 1e-9 and pl["shares"] % 100 == 0 and pl["shares"] * 100_000 <= 75_000_000
    assert 90_000 <= pl["stop"] < 100_000 and pl["take_profit"] > 100_000


def test_holding_and_income_goal():
    ps = build_personal_report(_analysis(er=-20.0, dy=0.5, label="GIẢM TỶ TRỌNG / TRÁNH"),
                               {"holder": True, "cost": 80_000, "qty": 1000, "goal": "income", "capital": 500e6})
    assert ps["label"] == "GIẢM TỶ TRỌNG / TRÁNH" and round(ps["holding"]["pnl_pct"]) == 25 and "bán" in ps["holding"]["action"].lower()
    assert any(f["criterion"] == "Mục tiêu cổ tức" and f["status"] == "bad" for f in ps["fit"])


def test_pdf_renders_personal_section():
    from core.bao_cao_pdf import PDFReportGenerator, EquityReportPDF
    gen = PDFReportGenerator()
    a = _analysis()
    ps = build_personal_report(a, {"risk": "aggressive", "capital": 300e6, "holder": True, "cost": 90_000, "qty": 500,
                                   "name": "Test"})
    pdf = EquityReportPDF({"ticker": "TST", "name": "Test"})
    pdf.alias_nb_pages()
    pdf.add_page()
    gen._render_personal(pdf, {}, {"personal": ps})
    assert len(bytes(pdf.output())) > 1000


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_step10_action.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Bước 10: P/E tham chiếu ≤ trung vị ngành × 1,5; hành động đề xuất (khôi phục final_action) có xét xu hướng VN-Index
(MA50); Rf cấu hình có ngày/nguồn và cảnh báo khi cũ > 3 tháng. Dữ liệu tổng hợp (không dùng ở production).
"""


import numpy as np
import pandas as pd
import pytest

from core.dinh_gia import risk_free_status
from core.cau_hinh import load_config
from tests.test_dinh_gia_du_phong import SHARES, make_prices, make_wide
from tests.test_dinh_gia_du_phong import method, run

T = pd.Timestamp("2026-10-09")


def _index(last_vs_ma: float, n=80):
    vals = np.full(n, 1000.0)
    vals[-1] = 1000.0 * last_vs_ma
    return pd.DataFrame({"timestamp": pd.bdate_range(end=T, periods=n), "close": vals})


# ── xu hướng VN-Index ────────────────────────────────────────────────────────







# ── P/E tham chiếu bị chặn ở trung vị ngành × 1,5 ────────────────────────────

def test_pe_reference_capped_at_peer_median_times_cap():
    w = make_wide()
    px = make_prices(w, pe=40.0)               # P/E lịch sử ~40x (vùng bong bóng)
    peers = {"pe": 12.0, "n": 5, "n_pe": 5}
    v = run(w, px=px, price=float(px["close"].iloc[-1]), peers=peers)
    pe = method(v, "pe")
    assert pe["multiple"] == pytest.approx(12.0 * 1.5)
    assert "chặn trần" in pe["source"]
    # không có nhóm ngành (< 3 DN) → không chặn (không có mốc so sánh)
    v2 = run(w, px=px, price=float(px["close"].iloc[-1]), peers={"pe": 12.0, "n": 2, "n_pe": 2})
    assert method(v2, "pe")["multiple"] > 18.0
    # cấu hình tắt chặn
    v3 = run(w, px=px, price=float(px["close"].iloc[-1]), peers=peers,
             cfg=load_config({"valuation": {"pe_peer_cap": None}}))
    assert method(v3, "pe")["multiple"] > 18.0


# ── Rf: ngày cập nhật / nguồn ────────────────────────────────────────────────

def test_risk_free_status_notes():
    v = load_config()["valuation"]
    assert "CHƯA ghi ngày" in risk_free_status(v, T)
    fresh = dict(v, risk_free_as_of="2026-08-31", risk_free_source="VBMA")
    assert risk_free_status(fresh, T) is None
    old = dict(v, risk_free_as_of="2026-06-30", risk_free_source="VBMA – Bản tin tháng 6/2026")
    msg = risk_free_status(old, T)
    assert "cũ 101 ngày" in msg and "VBMA" in msg
    assert "không hợp lệ" in risk_free_status(dict(v, risk_free_as_of="31/6/2026"), T)


def test_valuation_carries_risk_free_note():
    v = run(make_wide())
    assert v["risk_free_status"] and any("phi rủi ro" in n for n in v["notes"])


# ── tích hợp dịch vụ ─────────────────────────────────────────────────────────



def test_production_risk_free_has_source_and_date():
    """Rf thật trong cấu hình (không qua fixture ghim) phải có nguồn và ngày."""
    import importlib
    import core.cau_hinh as im
    src = open(im.__file__, encoding="utf-8").read()
    assert '"risk_free_as_of": "20' in src and 'risk_free_source": "HNX' in src


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_reco_trend_backtest.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Chạy thử công cụ backtest bộ lọc xu hướng (tools/reco_trend_backtest.py) trên dữ liệu GIẢ LẬP – chỉ kiểm tra đường
ống (không look-ahead, ghi CSV, chạy lại không trùng, chấm tiêu chí), không phải kết quả thật."""
import csv
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def _repo():
    from core.du_lieu import DataRepository
    from tests.fakes import FakeDNSE, FakeVietstock, FakeVnstock
    return DataRepository(arminer_client=False, vnstock_client=FakeVnstock(), dnse_client=FakeDNSE(),
                          vietstock_client=FakeVietstock(True), use_cache=False)


def test_pipeline_writes_rows_without_lookahead(tmp_path, monkeypatch):
    import reco_trend_backtest as rb
    from core.pipeline import StockService
    seen = []
    orig = StockService.investment_analysis

    def spy(self, *a, **k):
        out = orig(self, *a, **k)
        px = self.get_price_df()
        seen.append((self.as_of, pd.to_datetime(px["timestamp"]).max() if not px.empty else None))
        return out
    monkeypatch.setattr(StockService, "investment_analysis", spy)
    out = tmp_path / "rows.csv"
    rb.run(["FPT"], "2024-01", 6, str(out), base_repo=_repo(), last_T="2024-12-31")
    rows = list(csv.DictReader(open(out, encoding="utf-8-sig")))
    assert [r["T"] for r in rows] == ["2024-01-31", "2024-07-31"]
    assert all(mx is None or mx <= T + pd.Timedelta(days=1) for T, mx in seen)       # app chỉ thấy giá ≤ T
    assert all(r["ml_label"] or r["loi"] for r in rows)
    rb.run(["FPT"], "2024-01", 6, str(out), base_repo=_repo(), last_T="2024-12-31")  # chạy lại → không ghi trùng
    assert len(list(csv.DictReader(open(out, encoding="utf-8-sig")))) == 2


def test_multilayer_eval_runs(tmp_path):
    import multilayer_eval as ev
    p = tmp_path / "rows.csv"
    rows = [{"ma": m, "T": f"202{y}-0{k}-28", "ml_label": "MUA" if k % 2 else "THEO DÕI", "ml_F": 50 + k + y + len(m) * 0 + ord(m[0]) % 7,
             "ret_12T": 0.01 * (ord(m[0]) % 7) + 0.001 * k, "vnindex_ret_12T": 0.05, "loi": None}
            for m in ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF") for y in (1, 2) for k in range(1, 9)]
    pd.DataFrame(rows).to_csv(p, index=False)
    r = ev.evaluate(str(p))
    assert r["co_nhan_da_lop"] == 96 and "MUA" in r["theo_nhan"] and r["rank_ic_theo_thang"]["so_thang"] > 0


def test_valuation_pillar_uses_same_score_as_layer_v():
    from core.du_lieu import DataRepository
    from core.pipeline import StockService
    from tests.fakes import FakeDNSE, FakeVietstock, FakeVnstock
    repo = DataRepository(arminer_client=False, vnstock_client=FakeVnstock(), dnse_client=FakeDNSE(),
                          vietstock_client=FakeVietstock(True), pdf_financial_loader=lambda s, p: pd.DataFrame(),
                          use_cache=False)
    s = StockService("FPT", days=1100, repository=repo)
    ml = s.investment_analysis()["multilayer"]
    va = s.valuation_analysis()["score"]
    assert ml["V"] is not None and va["method"] == "multilayer_V" and va["score"] == round(ml["V"])
    rv = va.get("relative_valuation") or {}
    assert rv.get("pe") is not None and rv.get("pb") is not None   # bảng "So sánh với ngành" trong PDF cần P/E, P/B
    assert getattr(repo, "_universe_px", None)          # rổ so sánh được nhớ lại cho lần phân tích sau
