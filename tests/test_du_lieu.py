"""
tests/test_du_lieu.py – kiểm thử, gộp từ 8 file (15/10/2026).

MỤC LỤC
  • tests/test_database.py – Unit tests for DuckDB Database.
      hàm/lớp chính: temp_db, test_insert_and_get_prices, test_portfolio_crud
  • tests/test_ticker_directory.py – Unit tests for data.ticker_directory module.
      hàm/lớp chính: test_load_all_stocks, test_baskets_and_sectors, test_label_and_symbol_extraction, test_find_option_for_symbol
  • tests/test_pdf_ocr.py – Trích số liệu BCTC từ PDF scan (OCR) và BCTC ngân hàng (theo nhãn).
      hàm/lớp chính: test_normalize_glued_ocr_numbers, test_bank_label_extraction_tolerates_ocr_errors, test_scanned_pdf_without_ocr_gives_install_hint, test_scanned_corporate_pdf_end_to_end
  • tests/test_source_breaker.py – Cầu dao ngắt nguồn vnstock khi máy chủ không phản hồi + giá cũ nhớ tạm / dùng CSDL.
      hàm/lớp chính: test_timeout_trips_breaker_and_skips_v3, test_non_network_error_falls_through_to_v3, test_older_history_falls_back_to_db, test_hung_call_is_abandoned_after_call_timeout, test_hung_call_is_abandoned_after_call_timeout, test_short_history_filled_from_db
  • tests/test_live_bar.py – Nến ngày tạm tính trong phiên (DNSE chỉ trả nến ngày sau khi đóng cửa).
      hàm/lớp chính: test_live_bar_appended_during_session, test_no_live_bar_outside_session_or_for_past_date
  • tests/test_live_index.py – Thẻ chỉ số trong phiên: ghép phiên hôm nay từ nến phút vào chuỗi ngày.
      hàm/lớp chính: test_merge_live_appends_today_and_keeps_prev_close, test_merge_live_replaces_existing_today_row, test_merge_live_no_bar_is_noop, test_index_live_uses_minute_bars, test_live_bar_keeps_last_good_on_transient_failure, test_dnse_to_param_is_now_for_today_and_fixed_for_past
  • tests/test_dnse_realtime.py – Giá realtime DNSE OpenAPI: chữ ký, xử lý tin nhắn, giao thức với máy chủ giả lập cục bộ, ghép vào live_bar.
      hàm/lớp chính: test_signature_matches_official_format, test_trade_message_builds_today_bar_in_vnd, test_ignores_odd_lot_board_bad_price_and_old_days, test_index_message_and_alias, test_snapshot_none_unless_live_and_ping_reply, test_subscribe_messages_split_stocks_and_indexes, test_get_feed_none_without_keys, test_end_to_end_with_local_server, test_wrong_secret_stops_without_retry, test_live_bar_prefers_realtime_and_overlays_index, test_refresh_interval_falls_back_without_keys, test_decode_json_and_msgpack_frames …
  • tests/test_price_basis.py – Định giá tại ngày quá khứ: số CP phải cùng cơ sở với chuỗi giá đã điều chỉnh (15/10/2026).
      hàm/lớp chính: test_classify_events, Repo, test_fpt_like_quarter_shares_plus_bonus_minus_esop, test_listed_shares_already_current_basis_no_change, test_unadjusted_bonus_jump_divides, test_abnormal_factor_ignored, test_current_valuation_untouched, test_rf_after_valuation_date_flagged, test_charter_capital_fallback_and_unknown_flag
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_database.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Unit tests for DuckDB Database.
"""
import pytest
from core.du_lieu import Database


@pytest.fixture
def temp_db():
    db = Database(db_path=":memory:")
    yield db
    db.close()


def test_insert_and_get_prices(temp_db, sample_ohlcv_df):
    temp_db.upsert_price(sample_ohlcv_df)
    
    retrieved = temp_db.get_price("FPT")
    assert not retrieved.empty
    assert len(retrieved) == len(sample_ohlcv_df)
    assert "close" in retrieved.columns


def test_portfolio_crud(temp_db):
    temp_db.add_position("default", "FPT", quantity=1000, buy_price=95000.0, buy_date="2024-01-15")
    positions = temp_db.get_portfolio("default")
    assert len(positions) == 1
    assert positions.iloc[0]["symbol"] == "FPT"
    assert positions.iloc[0]["quantity"] == 1000
    
    pos_id = int(positions.iloc[0]["id"])
    temp_db.delete_position(pos_id)
    empty_positions = temp_db.get_portfolio("default")
    assert empty_positions.empty


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_ticker_directory.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Unit tests for data.ticker_directory module.
"""
from core.du_lieu import load_all_stocks, get_basket_names, get_tickers_for_basket, get_ticker_label, extract_symbol_from_label, find_option_for_symbol


def test_load_all_stocks():
    stocks = load_all_stocks()
    assert len(stocks) >= 10
    symbols = [s["symbol"] for s in stocks]
    assert "FPT" in symbols
    assert "HPG" in symbols
    assert "VCB" in symbols


def test_baskets_and_sectors():
    baskets = get_basket_names()
    assert len(baskets) >= 5
    assert "⭐ VN30 (Blue-chips HSX)" in baskets
    assert "🏦 Ngân hàng" in baskets

    vn30 = get_tickers_for_basket("⭐ VN30 (Blue-chips HSX)")
    assert len(vn30) == 30
    assert "FPT" in vn30
    assert "HPG" in vn30

    banks = get_tickers_for_basket("🏦 Ngân hàng")
    assert "VCB" in banks
    assert "TCB" in banks


def test_label_and_symbol_extraction():
    fpt_label = get_ticker_label("FPT")
    assert fpt_label.startswith("FPT")
    assert extract_symbol_from_label(fpt_label) == "FPT"

    assert extract_symbol_from_label("DGC") == "DGC"
    assert extract_symbol_from_label("  vre  ") == "VRE"
    assert extract_symbol_from_label("MBB - MBBank (HSX)") == "MBB"


def test_find_option_for_symbol():
    options = ["FPT - FPT Corp (HSX)", "HPG - Hoa Phat (HSX)", "VCB - Vietcombank (HSX)"]
    found = find_option_for_symbol("HPG", options)
    assert found == "HPG - Hoa Phat (HSX)"

    assert find_option_for_symbol("UNKNOWN", options) is None


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_pdf_ocr.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Trích số liệu BCTC từ PDF scan (OCR) và BCTC ngân hàng (theo nhãn)."""
import io

import pytest

from core.tai_lieu_bctc import extract_bank_by_label, extract_financials, is_bank_statement, normalize_ocr_line


@pytest.mark.parametrize("raw,expected", [
    ("I.Tienvacackhoantuongduongtien110V.17.1206.010", "I.Tienvacackhoantuongduongtien 110 V.1 7.120 6.010"),
    ("TONG CONG TAISAN 27070.500 61.200", "TONG CONG TAISAN 270 70.500 61.200"),
    ("10.Vayvangthuetaichinhnganhan320V.1510.6009.100", "10.Vayvangthuetaichinhnganhan 320 V.15 10.600 9.100"),
    ("Trongdo:Chiphilaivay23(720)(650)", "Trongdo:Chiphilaivay 23 (720) (650)"),
    ("Dong chu thuong khong co so", "Dong chu thuong khong co so"),
])
def test_normalize_glued_ocr_numbers(raw, expected):
    assert normalize_ocr_line(raw) == expected


def test_bank_label_extraction_tolerates_ocr_errors():
    lines = ["BAO CAO TINH HINH TAI CHINH", "Vl. Cho vay khach hang  10  580.123.456  520.000.789",
             "2. Du phong rui ro cho vay khach hang  (9.876.544)(8.000.000)",
             "TONG TAI SAN  860.111.222  780.000.333", "Ill. Tien gui cua khach hang  20  600.222.333  550.111.000",
             "Vlll. Von chu sé huru  25  80.000.000  70.000.000", "I. Thu nhap lai thuan  28  24.500.111  23.000.000",
             "Tong loi nhuan truéc thué  20.100.333  19.000.000", "Lgi nhuan sau thue  16.080.111  15.200.000"]
    assert is_bank_statement("\n".join(lines))
    v = extract_bank_by_label(lines)
    assert v["customer_loans"] == 580_123_456 and v["customer_deposits"] == 600_222_333
    assert v["equity"] == 80_000_000 and v["profit_before_tax"] == 20_100_333 and v["net_income"] == 16_080_111
    assert v["total_assets"] == 860_111_222


def test_scanned_pdf_without_ocr_gives_install_hint(monkeypatch):
    from PIL import Image
    import core.tai_lieu_bctc as ocr
    buf = io.BytesIO()
    Image.new("RGB", (400, 560), "white").save(buf, "PDF")
    monkeypatch.setattr(ocr, "ocr_available", lambda: False)
    res = extract_financials(buf.getvalue())
    assert not res["values"] and "pip install" in res["note"]


@pytest.mark.skipif(not __import__("core.tai_lieu_bctc", fromlist=["x"]).ocr_available(), reason="chưa cài thư viện OCR")
def test_scanned_corporate_pdf_end_to_end():
    import pypdfium2 as pdfium
    from tests.pdf_samples import make_vas_pdf
    text_pdf = make_vas_pdf()
    doc = pdfium.PdfDocument(text_pdf)
    ims = [doc[i].render(scale=200 / 72).to_pil().convert("RGB") for i in range(len(doc))]
    buf = io.BytesIO()
    ims[0].save(buf, "PDF", save_all=True, append_images=ims[1:], resolution=200)
    ref = extract_financials(text_pdf)["values"]
    res = extract_financials(buf.getvalue())
    assert res["method"] == "ocr" and len(res["values"]) >= 25
    assert all(res["values"][k] == ref[k] for k in res["values"] if k in ref)   # không đọc sai số nào


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_source_breaker.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Cầu dao ngắt nguồn vnstock khi máy chủ không phản hồi + giá cũ nhớ tạm / dùng CSDL."""
import time

import pandas as pd
import pytest

from core import nguon_du_lieu as vc


@pytest.fixture(autouse=True)
def _reset():
    vc._COOLDOWN.clear()
    yield
    vc._COOLDOWN.clear()


def test_timeout_trips_breaker_and_skips_v3():
    c = vc.VnstockClient()
    c._available = True
    calls = []

    def v4():
        calls.append("v4")
        raise Exception("HTTPSConnectionPool(host='iq.vietcap.com.vn', port=443): Read timed out. (read timeout=30)")

    def v3():
        calls.append("v3")
        return pd.DataFrame({"a": [1]})

    assert c._try("history[vci]", v4, v3) is None
    assert calls == ["v4"]                       # không gọi v3 (cùng máy chủ)
    assert "vci" in vc.source_cooldowns()
    t0 = time.time()
    assert c._try("history[vci]", v4, v3) is None
    assert calls == ["v4"] and time.time() - t0 < 0.1     # bỏ qua ngay, không chờ
    # nguồn khác vẫn chạy
    assert c._try("history[kbs]", lambda: pd.DataFrame({"a": [1]})) is not None


def test_non_network_error_falls_through_to_v3():
    c = vc.VnstockClient()
    c._available = True
    res = c._try("history[vci]", lambda: (_ for _ in ()).throw(KeyError("time")), lambda: pd.DataFrame({"a": [1]}))
    assert res is not None and not vc.source_cooldowns()


def test_older_history_falls_back_to_db(monkeypatch):
    from core import du_lieu as dr
    from tests.fakes import FakeDNSE, FakeVietstock, FakeVnstock
    repo = dr.DataRepository(arminer_client=False, vnstock_client=FakeVnstock(), dnse_client=FakeDNSE(),
                             vietstock_client=FakeVietstock(True), use_cache=False)
    monkeypatch.setattr(repo, "_history_chain", lambda *a, **k: pd.DataFrame())
    ts = pd.bdate_range("2023-01-02", "2023-06-30")
    stored = pd.DataFrame({"timestamp": ts, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0,
                           "symbol": "AAA", "source": "dnse"})
    monkeypatch.setattr(dr.db, "get_price", lambda s, a=None, b=None, table="price_daily": stored)
    out = repo._older_history("AAA", pd.Timestamp("2023-01-01"), pd.Timestamp("2023-06-30"), "1D", final=True)
    assert len(out) == len(stored)
    # CSDL không phủ đầu kỳ → không dùng (tránh chuỗi thiếu mà tưởng đủ)
    out2 = repo._older_history("AAA", pd.Timestamp("2022-01-01"), pd.Timestamp("2023-06-30"), "1D", final=True)
    assert out2.empty


def test_hung_call_is_abandoned_after_call_timeout(monkeypatch):
    monkeypatch.setattr(vc, "CALL_TIMEOUT", 0.5)
    c = vc.VnstockClient()
    c._available = True

    def hang():
        time.sleep(3)          # mô phỏng vnstock chờ máy chủ VCI
        return pd.DataFrame({"a": [1]})

    t0 = time.time()
    assert c._try("company.overview[vci]", hang, hang) is None
    assert time.time() - t0 < 1.5                     # không đợi hết 3 giây, không gọi cách thứ 2
    assert "vci" in vc.source_cooldowns()


def test_hung_call_is_abandoned_after_call_timeout(monkeypatch):
    monkeypatch.setattr(vc, "CALL_TIMEOUT", 0.5)
    c = vc.VnstockClient()
    c._available = True

    def hang():
        time.sleep(3)          # mô phỏng vnstock chờ máy chủ VCI
        return pd.DataFrame({"a": [1]})

    t0 = time.time()
    assert c._try("company.overview[vci]", hang, hang) is None
    assert time.time() - t0 < 1.5                     # không đợi hết 3 giây, không gọi cách thứ 2
    assert "vci" in vc.source_cooldowns()


def test_short_history_filled_from_db(monkeypatch):
    from core import du_lieu as dr
    from tests.fakes import FakeDNSE, FakeVietstock, FakeVnstock
    repo = dr.DataRepository(arminer_client=False, vnstock_client=FakeVnstock(), dnse_client=FakeDNSE(),
                             vietstock_client=FakeVietstock(True), use_cache=False)
    recent = pd.DataFrame({"timestamp": pd.bdate_range("2026-08-10", "2026-10-09"), "close": 2.0, "source": "dnse"})
    old = pd.DataFrame({"timestamp": pd.bdate_range("2025-10-13", "2026-08-07"), "close": 1.0, "source": "dnse"})
    monkeypatch.setattr(dr.db, "get_price", lambda s, a=None, b=None, table="price_daily": old)
    out = repo._fill_from_db(recent, "AAA", pd.Timestamp("2025-10-12"), pd.Timestamp("2026-10-12"), "1D")
    assert out["timestamp"].min() == pd.Timestamp("2025-10-13") and len(out) == len(old) + len(recent)
    assert out["timestamp"].is_monotonic_increasing


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_live_bar.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Nến ngày tạm tính trong phiên (DNSE chỉ trả nến ngày sau khi đóng cửa)."""
from datetime import datetime

import numpy as np
import pandas as pd

import core.du_lieu as dr


class _FakeNow(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 12, 10, 17)


class _DNSE:
    def get_price_history(self, symbol, start, end, interval="1D"):
        if interval == "1m":
            ts = pd.date_range("2026-10-12 09:15", "2026-10-12 10:17", freq="1min")
            c = np.linspace(57.9, 58.3, len(ts))
            return pd.DataFrame({"timestamp": ts, "open": c, "high": c + 0.1, "low": c - 0.2, "close": c,
                                 "volume": 1000.0, "symbol": symbol, "source": "dnse"})
        d = pd.bdate_range(end="2026-10-09", periods=30)
        c = np.full(len(d), 57.9)
        return pd.DataFrame({"timestamp": d, "open": c, "high": c, "low": c, "close": c, "volume": 1e6,
                             "symbol": symbol, "source": "dnse"})


def test_live_bar_appended_during_session(monkeypatch):
    monkeypatch.setattr(dr, "datetime", _FakeNow)
    repo = dr.DataRepository.__new__(dr.DataRepository)
    repo._dnse = _DNSE()
    base = dr.to_vnd(repo._dnse.get_price_history("FPT", "", "", "1D"), "FPT")
    out = repo._append_live_bar(base, "FPT", pd.Timestamp("2026-10-12"))
    last = out.iloc[-1]
    assert pd.Timestamp(last["timestamp"]) == pd.Timestamp("2026-10-12")
    assert last["close"] == 58_300 and last["open"] == 57_900 and last["session_time"] == "10:17"
    assert last["volume"] == 1000.0 * 63


def test_no_live_bar_outside_session_or_for_past_date(monkeypatch):
    repo = dr.DataRepository.__new__(dr.DataRepository)
    repo._dnse = _DNSE()
    base = dr.to_vnd(repo._dnse.get_price_history("FPT", "", "", "1D"), "FPT")
    monkeypatch.setattr(dr, "datetime", _FakeNow)
    assert len(repo._append_live_bar(base, "FPT", pd.Timestamp("2026-10-09"))) == len(base)   # định giá tại ngày cũ

    class _Sat(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 10, 10, 0)
    monkeypatch.setattr(dr, "datetime", _Sat)
    assert len(repo._append_live_bar(base, "FPT", pd.Timestamp("2026-10-10"))) == len(base)   # thứ Bảy
    assert dr._in_session(datetime(2026, 10, 12, 14, 50)) and not dr._in_session(datetime(2026, 10, 12, 16, 0))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_live_index.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Thẻ chỉ số trong phiên: ghép phiên hôm nay từ nến phút vào chuỗi ngày."""
from datetime import datetime

import pandas as pd

from core import thi_truong_danh_muc as ms


def _daily():
    ts = pd.to_datetime(["2026-10-07", "2026-10-08", "2026-10-09"])
    return pd.DataFrame({"timestamp": ts, "open": [1, 2, 3.0], "high": [1, 2, 3.0], "low": [1, 2, 3.0],
                         "close": [1000.0, 1010.0, 1020.0], "volume": [1, 1, 1.0], "symbol": "VNINDEX"})


def test_merge_live_appends_today_and_keeps_prev_close():
    bar = {"timestamp": pd.Timestamp("2026-10-12"), "open": 1021.0, "high": 1035.0, "low": 1018.0,
           "close": 1030.6, "volume": 5e8, "session_time": "11:07", "source": "dnse_1m"}
    out = ms.merge_live(_daily(), bar)
    assert len(out) == 4 and out["close"].iloc[-1] == 1030.6
    card = ms.index_card("VNINDEX", out)
    assert card["live"] and card["date"] == "12/10/2026 · 11:07"
    assert abs(card["change"] - 10.6) < 1e-9          # so với đóng cửa phiên 09/10


def test_merge_live_replaces_existing_today_row():
    d = _daily()
    bar = {"timestamp": pd.Timestamp("2026-10-09"), "open": 3.0, "high": 3.0, "low": 3.0, "close": 1025.0,
           "volume": 2.0, "session_time": "14:30"}
    out = ms.merge_live(d, bar)
    assert len(out) == 3 and out["close"].iloc[-1] == 1025.0 and out["symbol"].iloc[-1] == "VNINDEX"


def test_merge_live_no_bar_is_noop():
    d = _daily()
    assert ms.merge_live(d, None) is d


def test_index_live_uses_minute_bars(monkeypatch):
    today = pd.Timestamp(datetime.now().date())
    m = pd.DataFrame({"timestamp": [today + pd.Timedelta(hours=9, minutes=15), today + pd.Timedelta(hours=11, minutes=7)],
                      "open": [1020.0, 1028.0], "high": [1025.0, 1031.0], "low": [1019.0, 1027.0],
                      "close": [1024.0, 1030.6], "volume": [100.0, 200.0]})

    class P:
        def get_price_history(self, *a, **k):
            return m

    class R:
        _dnse = P()
        _vnstock = P()

    monkeypatch.setattr(ms, "get_repo", lambda: R())
    monkeypatch.setattr(ms, "_FastDNSE", P)
    monkeypatch.setattr("core.du_lieu._in_session", lambda now=None: True)
    ms._live_cache.clear(); ms._last_good.clear()
    monkeypatch.setattr(ms, "_poll_ttl", lambda now=None: 1.2)
    bar = ms.index_live("VN30")
    assert bar["close"] == 1030.6 and bar["high"] == 1031.0 and bar["low"] == 1019.0
    assert bar["volume"] == 300.0 and bar["session_time"] == "11:07"
    ms._live_cache.clear()


def test_live_bar_keeps_last_good_on_transient_failure(monkeypatch):
    today = pd.Timestamp(datetime.now().date())
    m = pd.DataFrame({"timestamp": [today + pd.Timedelta(hours=10)], "open": [60.0], "high": [61.0], "low": [59.5],
                      "close": [60.5], "volume": [1000.0]})
    state = {"ok": True}

    class P:
        def get_price_history(self, *a, **k):
            return m if state["ok"] else pd.DataFrame()

    class R:
        _vnstock = P()

    monkeypatch.setattr(ms, "_FastDNSE", P)
    monkeypatch.setattr(ms, "get_repo", lambda: R())
    monkeypatch.setattr("core.du_lieu._in_session", lambda now=None: True)
    monkeypatch.setattr(ms, "_poll_ttl", lambda now=None: 0.0)
    ms._live_cache.clear(); ms._last_good.clear()
    b1 = ms.live_bar("FPT")
    assert b1["close"] == 60500.0                        # giá cổ phiếu DNSE (nghìn đồng) → VND
    state["ok"] = False                                   # vd DNSE giới hạn tần suất 1 nhịp
    ms._live_cache.clear()
    assert ms.live_bar("FPT")["close"] == 60500.0       # giữ giá thật gần nhất, không nhảy về ⚠️
    ms._live_cache.clear(); ms._last_good.clear()


def test_dnse_to_param_is_now_for_today_and_fixed_for_past():
    import time as _t
    from datetime import datetime as _dt, timedelta as _td
    from core import nguon_du_lieu as dc
    now = int(_t.time())
    assert abs(dc.to_param(_dt.now()) - now) <= 1           # hôm nay → giây hiện tại (URL mới mỗi lần, không bị CDN trả bản cũ)
    past = _dt.now() - _td(days=10)
    assert dc.to_param(past) < now - 8 * 86400


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_dnse_realtime.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Giá realtime DNSE OpenAPI: chữ ký, xử lý tin nhắn, giao thức với máy chủ giả lập cục bộ, ghép vào live_bar."""


import asyncio
import hashlib
import hmac
import json
import threading
import time
from datetime import datetime

import pandas as pd
import pytest

from core import nguon_du_lieu as rt


def test_signature_matches_official_format():
    msg = rt.auth_message("KEY", "SECRET", now=1_700_000_000.123456)
    payload = f"KEY:{msg['timestamp']}:{msg['nonce']}"
    assert msg["action"] == "auth" and msg["api_key"] == "KEY"
    assert msg["signature"] == hmac.new(b"SECRET", payload.encode(), hashlib.sha256).hexdigest()
    assert "SECRET" not in json.dumps(msg)                     # secret không bao giờ gửi đi / ghi ra


def _feed(now=None):
    f = rt.RealtimeFeed("k", "s", clock=(lambda: now) if now else time.time)
    f.state = "live"
    return f


def test_trade_message_builds_today_bar_in_vnd():
    f = _feed()
    f.handle({"T": "t", "symbol": "FPT", "boardId": "G1", "matchPrice": 95.3, "matchQtty": 100,
              "openPrice": 94.0, "highestPrice": 96.0, "lowestPrice": 93.5, "totalVolumeTraded": 1_234_500,
              "time": datetime.now(rt.VN_TZ).isoformat()})
    b = f.snapshot("FPT")
    assert b["close"] == pytest.approx(95_300) and b["open"] == pytest.approx(94_000)
    assert b["high"] == pytest.approx(96_000) and b["low"] == pytest.approx(93_500)
    assert b["volume"] == 1_234_500 and b["source"] == "dnse_realtime"
    assert b["timestamp"] == pd.Timestamp(datetime.now(rt.VN_TZ).date())


def test_ignores_odd_lot_board_bad_price_and_old_days():
    f = _feed()
    f.handle({"T": "t", "symbol": "HPG", "boardId": "G4", "matchPrice": 20})       # lô lẻ → bỏ
    f.handle({"T": "t", "symbol": "HPG", "boardId": "G1", "matchPrice": 0})        # giá 0 → bỏ
    assert f.snapshot("HPG") is None
    f.handle({"T": "t", "symbol": "VNM", "boardId": "G1", "matchPrice": 60, "time": "2020-01-02T03:00:00Z"})
    assert f.snapshot("VNM") is None                                               # không phải phiên hôm nay


def test_index_message_and_alias():
    f = _feed()
    f.handle({"T": "mi", "indexName": "VNINDEX", "valueIndexes": 1700.81, "highestValueIndexes": 1710.2,
              "lowestValueIndexes": 1695.0, "priorValueIndexes": 1704.87, "totalVolumeTraded": 500_000_000})
    b = f.snapshot("VN-INDEX")
    assert b["close"] == pytest.approx(1700.81) and b["open"] is None and b["reference"] == pytest.approx(1704.87)
    assert rt.is_index_dnse_realtime("HNXINDEX") and rt.canonical("HNXINDEX") == "HNX"


def test_snapshot_none_unless_live_and_ping_reply():
    f = _feed()
    f.handle({"T": "t", "symbol": "FPT", "boardId": "G1", "matchPrice": 95})
    f.state = "error"
    assert f.snapshot("FPT") is None                       # mất kết nối → không dùng giá cũ, app quay về cách cũ
    assert f.handle({"action": "ping"}) == {"action": "pong"}


def test_subscribe_messages_split_stocks_and_indexes():
    msgs = _feed().subscribe_messages({"FPT", "HPG", "VNINDEX"})
    assert msgs[0] == {"action": "subscribe", "channels": [{"name": "tick.G1.json", "symbols": ["FPT", "HPG"]}]}
    assert msgs[1]["channels"][0] == {"name": "market_index.VNINDEX.json", "symbols": []}


def test_get_feed_none_without_keys():
    assert rt.get_feed() is None and not rt.active() and rt.status()["state"] == "off"


# ── Giao thức đầy đủ với máy chủ WebSocket giả lập (chạy cục bộ, không cần mạng) ──
def _run_server(handler):
    websockets = pytest.importorskip("websockets")
    from websockets.asyncio.server import serve
    ready, info = threading.Event(), {}

    def target():
        async def main():
            async with serve(handler, "127.0.0.1", 0) as server:
                info["port"] = server.sockets[0].getsockname()[1]
                info["loop"] = asyncio.get_running_loop()
                info["stop"] = asyncio.Event()
                ready.set()
                await info["stop"].wait()
        asyncio.run(main())

    th = threading.Thread(target=target, daemon=True)
    th.start()
    assert ready.wait(5)
    return info


def _wait(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_end_to_end_with_local_server():
    seen = {"subs": []}

    async def handler(ws):
        await ws.send(json.dumps({"session_id": "abc"}))
        auth = json.loads(await ws.recv())
        good = hmac.new(b"SECRET", f"KEY:{auth['timestamp']}:{auth['nonce']}".encode(), hashlib.sha256).hexdigest()
        if auth.get("signature") != good:
            await ws.send(json.dumps({"action": "auth_error", "message": "invalid signature"}))
            return
        await ws.send(json.dumps({"action": "auth_success"}))
        async for raw in ws:
            m = json.loads(raw)
            if m.get("action") == "subscribe":
                seen["subs"].append(m)
                for ch in m["channels"]:
                    for s in ch["symbols"]:
                        await ws.send(json.dumps({"T": "t", "symbol": s, "boardId": "G1", "matchPrice": 50.5,
                                                  "openPrice": 50, "highestPrice": 51, "lowestPrice": 49.8,
                                                  "totalVolumeTraded": 1000}))
                    if ch["name"].startswith("market_index."):
                        await ws.send(json.dumps({"T": "mi", "indexName": ch["name"].split(".")[1],
                                                  "valueIndexes": 1701.5}))

    info = _run_server(handler)
    f = rt.RealtimeFeed("KEY", "SECRET", ws_url=f"ws://127.0.0.1:{info['port']}")
    try:
        f.want("FPT", "VNINDEX")
        f.start()
        assert _wait(lambda: f.state == "live")
        assert _wait(lambda: f.snapshot("FPT") is not None)
        assert f.snapshot("FPT")["close"] == pytest.approx(50_500)
        assert _wait(lambda: f.snapshot("VNINDEX") is not None)
        f.want("HPG")                                           # mã mới khi đang chạy → đăng ký thêm
        assert _wait(lambda: f.snapshot("HPG") is not None)
        assert f.status()["symbols_with_price"] == 3
    finally:
        f.stop()
        info["loop"].call_soon_threadsafe(info["stop"].set)


def test_wrong_secret_stops_without_retry():
    attempts = []

    async def handler(ws):
        attempts.append(1)
        await ws.send(json.dumps({"session_id": "x"}))
        await ws.recv()
        await ws.send(json.dumps({"action": "auth_error", "message": "invalid api key"}))

    info = _run_server(handler)
    f = rt.RealtimeFeed("KEY", "WRONG", ws_url=f"ws://127.0.0.1:{info['port']}")
    try:
        f.start()
        assert _wait(lambda: f.state == "auth_failed")
        time.sleep(1.5)
        assert len(attempts) == 1 and "invalid api key" in f.message and not f.active()
        f.start()                                               # không tự thử lại với key sai
        assert f.state == "auth_failed"
    finally:
        info["loop"].call_soon_threadsafe(info["stop"].set)


# ── Ghép vào live_bar của app ──
def test_live_bar_prefers_realtime_and_overlays_index(monkeypatch):
    from core import thi_truong_danh_muc as ms
    import core.du_lieu as dr
    monkeypatch.setattr(dr, "_in_session", lambda now=None: True)
    today = pd.Timestamp(datetime.now().date())
    polled = {"timestamp": today, "open": 1700.0, "high": 1705.0, "low": 1698.0, "close": 1702.0, "volume": 10.0,
              "session_time": "10:00", "source": "dnse_1m"}
    calls = []
    monkeypatch.setattr(ms, "_live_bar_polled", lambda code: calls.append(code) or dict(polled))
    snaps = {
        "FPT": {"timestamp": today, "open": 94_000.0, "high": 96_000.0, "low": 93_500.0, "close": 95_300.0,
                "volume": 1000.0, "reference": None, "session_time": "10:31:05", "source": "dnse_realtime"},
        "VNINDEX": {"timestamp": today, "open": None, "high": 1710.0, "low": 1696.0, "close": 1708.5,
                    "volume": 99.0, "reference": 1704.0, "session_time": "10:31:06", "source": "dnse_realtime"},
    }
    monkeypatch.setattr(ms, "_rt_snapshot", lambda code: snaps.get(code))
    b = ms.live_bar("FPT")
    assert b["close"] == 95_300.0 and b["source"] == "dnse_realtime" and "reference" not in b and calls == []
    i = ms.live_bar("VNINDEX")
    assert calls == ["VNINDEX"] and i["open"] == 1700.0 and i["close"] == 1708.5
    assert i["high"] == 1710.0 and i["low"] == 1696.0 and i["session_time"] == "10:31:06"
    assert ms.live_bar("HPG")["source"] == "dnse_1m"          # chưa có realtime → cách cũ


def test_refresh_interval_falls_back_without_keys():
    from core.cau_hinh import settings
    from core import thi_truong_danh_muc as ms
    assert ms.live_refresh_seconds() == settings.LIVE_REFRESH_SECONDS and ms.live_mode() == "poll"


def test_decode_json_and_msgpack_frames():
    msgpack = pytest.importorskip("msgpack")
    trade = {"T": "t", "symbol": "FPT", "boardId": "G1", "matchPrice": 95.3, "openPrice": 94,
             "highestPrice": 96, "lowestPrice": 93.5, "totalVolumeTraded": 10}
    assert rt.decode(json.dumps(trade)) == trade
    assert rt.decode(json.dumps(trade).encode()) == trade
    assert rt.decode(msgpack.packb(trade)) == trade
    assert rt.decode(b"\xff\x00garbage") is None and rt.decode("[1,2]") is None


def test_end_to_end_binary_msgpack_trades():
    msgpack = pytest.importorskip("msgpack")

    async def handler(ws):
        await ws.send(json.dumps({"action": "welcome", "session_id": "s"}))
        await ws.recv()
        await ws.send(json.dumps({"action": "auth_success"}))
        async for raw in ws:
            m = json.loads(raw)
            if m.get("action") == "subscribe" and m["channels"][0]["symbols"]:
                await ws.send(json.dumps({"action": "subscribed", "channel": "tick.G1.msgpack", "status": "active"}))
                await ws.send(msgpack.packb({"T": "t", "symbol": "FPT", "boardId": "G1", "matchPrice": 57.7,
                                             "openPrice": 57.1, "highestPrice": 58, "lowestPrice": 57,
                                             "totalVolumeTraded": 2_260_700}))

    info = _run_server(handler)
    f = rt.RealtimeFeed("KEY", "SECRET", ws_url=f"ws://127.0.0.1:{info['port']}")
    try:
        f.want("FPT")
        f.start()
        assert _wait(lambda: f.snapshot("FPT") is not None)
        assert f.snapshot("FPT")["close"] == pytest.approx(57_700) and f.status()["undecoded"] == 0
    finally:
        f.stop()
        info["loop"].call_soon_threadsafe(info["stop"].set)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: tests/test_price_basis.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""Định giá tại ngày quá khứ: số CP phải cùng cơ sở với chuỗi giá đã điều chỉnh (15/10/2026).
Dữ liệu sự kiện mô phỏng theo bảng sự kiện thật của FPT/VCB (vnstock) – xem tools/check_share_basis.py."""
import numpy as np
import pandas as pd
import pytest

from core.nguon_du_lieu import classify_share_event, parse_paid_share_events, parse_share_events
from core.pipeline import StockService

T = pd.Timestamp("2023-06-30")

FPT_EV = pd.DataFrame({
    "event_code": ["ISS", "ISS", "DIV", "ISS", "DIV", "AIS"],
    "event_title_vi": ["Phát hành cổ phiếu - Cổ phiếu thưởng tỷ lệ 10.0%",
                       "Phát hành cổ phiếu - Phát hành cho CBCNV tỷ lệ 0.5%",
                       "Trả cổ tức bằng tiền mặt - Đợt 2 2025 - 1,000 VND",
                       "Phát hành cổ phiếu - Cổ phiếu thưởng tỷ lệ 15.0%",
                       "Trả cổ tức bằng tiền mặt - Đợt 1 2024 - 1,000 VND",
                       "FPT - Niêm yết bổ sung 10.819.301 cổ phiếu"],
    "exright_date": ["2026-09-21", "2026-06-24", "2026-05-28", "2025-07-21", "2024-12-02", None],
    "exercise_ratio": [0.10, 0.005, 0.10, 0.15, 0.10, np.nan],
    "listing_date": [None, "2029-06-25", None, "2025-09-12", None, None],
})


def test_classify_events():
    assert classify_share_event("DIV", "Trả cổ tức bằng tiền mặt - 1,000 VND") is None
    assert classify_share_event("ISS", "Phát hành cổ phiếu - Phát hành cho CBCNV tỷ lệ 0.5%") == "paid"
    assert classify_share_event("ISS", "Phát hành cổ phiếu - Phát hành riêng lẻ tỷ lệ 6.5%") == "paid"
    assert classify_share_event("ISS", "Phát hành cổ phiếu - Trả Cổ tức bằng Cổ phiếu tỷ lệ 49.5%") == "bonus"
    assert classify_share_event("ISS", "Phát hành cổ phiếu - Cổ phiếu thưởng tỷ lệ 10.0%") == "bonus"
    ev = parse_share_events(FPT_EV)
    assert [e["ratio"] for e in ev] == [0.15, 0.10]                  # cổ tức tiền mặt & ESOP KHÔNG phải chia CP
    assert [e["ratio"] for e in parse_paid_share_events(FPT_EV)] == [0.005]


def _series(jump_on=None, ratio=0.0, end="2026-10-14"):
    ts = pd.bdate_range("2023-01-02", end)
    close = np.full(len(ts), 50.0)
    if jump_on is not None:                     # nguồn CHƯA điều chỉnh: giá giảm theo tỷ lệ thưởng từ ngày GDKHQ
        close[ts < pd.Timestamp(jump_on)] = 50.0 * (1 + ratio)
    return pd.DataFrame({"timestamp": ts, "open": close, "high": close, "low": close, "close": close, "volume": 1e6})


class Repo:
    def __init__(self, px, events, issue_share=None, q_shares=None):
        self.px, self.events, self.issue, self.q = px, events, issue_share, q_shares

    def get_company_events(self, symbol):
        return self.events

    def get_company_info(self, symbol):
        return {"issue_share": self.issue} if self.issue else {"name": symbol}

    def get_financials(self, symbol, period="year", years=4, **kw):
        if period != "quarter" or self.q is None:
            return {"data": pd.DataFrame()}
        return {"data": pd.DataFrame({"shares_outstanding": [self.q * 0.99, self.q]}, index=[20261, 20262])}

    def get_price_history(self, symbol, start_date="", end_date="", days=365, interval="1D", force_refresh=False):
        end = pd.Timestamp(end_date) if end_date else pd.Timestamp.now()
        out = self.px[pd.to_datetime(self.px["timestamp"]) <= end].copy()
        out.attrs = dict(self.px.attrs)
        return out


def test_fpt_like_quarter_shares_plus_bonus_minus_esop():
    """Không có số CP niêm yết → số CP lưu hành Q2/2026 × thưởng 10% (sau quý) ÷ ESOP sau T; bỏ qua cổ tức tiền mặt."""
    s = StockService("FPT", repository=Repo(_series(), FPT_EV, q_shares=1.70e9), as_of=T)
    out = s._apply_price_basis({"shares": 1.097e9, "source": "BCTC năm 2022"})
    assert out["shares"] == pytest.approx(1.70e9 * 1.10 / 1.005, rel=1e-6)
    assert out["price_basis_factor"] == pytest.approx(1.70e9 * 1.10 / 1.005 / 1.097e9, rel=1e-6)


def test_listed_shares_already_current_basis_no_change():
    """VCB: số CP trong BCTC của nguồn đã là cơ sở hiện tại → không nhân thêm (lỗi trước đây nhân 1,93 lần)."""
    ev = pd.DataFrame({"event_code": ["ISS", "DIV"],
                       "event_title_vi": ["Phát hành cổ phiếu - Trả Cổ tức bằng Cổ phiếu tỷ lệ 49.5%",
                                          "Trả cổ tức bằng tiền mặt - Cả năm 2024 - 450 VND"],
                       "exright_date": ["2025-03-12", "2025-10-03"], "exercise_ratio": [0.495, 0.045],
                       "listing_date": ["2025-05-09", None]})
    s = StockService("VCB", repository=Repo(_series(), ev, issue_share=8.356e9), as_of=T)
    out = s._apply_price_basis({"shares": 8.356e9, "source": "BCTC năm 2022"})
    assert out["shares"] == pytest.approx(8.356e9) and out["price_basis_factor"] == pytest.approx(1.0)


def test_unadjusted_bonus_jump_divides():
    ev = FPT_EV.iloc[[3]]                                             # thưởng 15% ngày 21/07/2025
    s = StockService("AAA", repository=Repo(_series("2025-07-21", 0.15), ev, issue_share=2.0e9), as_of=T)
    out = s._apply_price_basis({"shares": 1.0e9})
    assert out["shares"] == pytest.approx(2.0e9 / 1.15)


def test_abnormal_factor_ignored():
    s = StockService("AAA", repository=Repo(_series(), FPT_EV.iloc[[]], issue_share=50e9), as_of=T)
    out = s._apply_price_basis({"shares": 1.0e9})
    assert out["shares"] == 1.0e9 and "bất thường" in out["price_basis_method"]


def test_current_valuation_untouched():
    s = StockService("AAA", repository=Repo(_series(), FPT_EV, issue_share=2e9))
    assert s._apply_price_basis({"shares": 1.0e9})["shares"] == 1.0e9


def test_rf_after_valuation_date_flagged():
    from core.dinh_gia import risk_free_status
    v = {"risk_free": 0.0443, "risk_free_as_of": "2026-09-30", "risk_free_source": "HNX"}
    assert "SAU ngày định giá" in risk_free_status(v, "2021-01-31")
    assert risk_free_status(v, "2026-10-14") is None


def test_charter_capital_fallback_and_unknown_flag():
    """Ngân hàng: BCTC quý không có số CP lưu hành → dùng vốn điều lệ ÷ 10.000; không có gì → đánh dấu chưa quy đổi."""
    class R(Repo):
        def get_financials(self, symbol, period="year", years=4, **kw):
            return {"data": pd.DataFrame({"charter_capital": [5.0e13]}, index=[20262])} if period == "quarter" else {}
    s = StockService("MBB", repository=R(_series(), FPT_EV.iloc[[]]), as_of=T)
    assert s._apply_price_basis({"shares": 2.0e9})["shares"] == pytest.approx(5.0e9)
    s2 = StockService("MBB", repository=Repo(_series(), FPT_EV.iloc[[]]), as_of=T)
    assert s2._apply_price_basis({"shares": 2.0e9}).get("price_basis_unknown") is True
