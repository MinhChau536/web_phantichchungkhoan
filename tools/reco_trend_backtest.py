"""
Backtest KHUNG KHUYẾN NGHỊ ĐA LỚP – CHẠY TRÊN MÁY CÓ vnstock + API key.

Tại mỗi ngày cuối tháng T (mặc định 2021-01 → 12 tháng trước hôm nay), với từng mã:
  • gọi đúng pipeline của app: StockService(mã, as_of=T).investment_analysis() → nhãn khuyến nghị, điểm Q/V/G/T/F,
    giá mục tiêu. as_of cắt mọi dữ liệu về T (không look-ahead).
  • đo kết quả SAU T trên chuỗi giá đầy đủ: lợi nhuận 3T/6T/12T của cổ phiếu và VN-Index, mức giảm sâu nhất 3 tháng.

Giá lịch sử của mỗi mã + VN-Index chỉ tải MỘT lần (toàn kỳ) rồi cắt theo T → không gọi API lặp lại theo từng tháng.
Kết quả ghi dần vào CSV (chạy lại sẽ bỏ qua các dòng đã có → dừng giữa chừng không mất kết quả).

Chạy (thư mục dự án, đã kích hoạt .venv, có file .env):
    python tools/reco_trend_backtest.py                       # rổ VN30, mỗi tháng
    python tools/reco_trend_backtest.py --symbols FPT,HPG,VCB --start 2022-01 --step 3
Đầu ra: tools/reco_trend_out/rows.csv  → chấm bằng: python tools/multilayer_eval.py
"""


import argparse
import csv
import os
import sys
import time
from typing import Any, Dict, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

OUT_DIR = os.path.join(ROOT, "tools", "reco_trend_out")
FIELDS = ["ma", "T", "gia_T", "trend_cp", "target_12m", "expected_return", "confidence", "health", "profile",
          "gia_T3", "gia_T6", "gia_T12", "ret_3T", "ret_6T", "ret_12T", "maxdd_3T",
          "cho_ngay_mua", "cho_gia_mua", "cho_ret_den_T12",
          # chẩn đoán (15/10/2026): cơ sở số CP so với giá đã điều chỉnh, lý do độ tin cậy, Rf sau ngày T
          "so_cp_dung", "he_so_co_so_gia", "cach_quy_doi", "so_dot_dieu_chinh_sau_T", "pe_cuoi_nam_truoc", "diem_tin_cay", "ly_do_tin_cay", "rf_ghi_chu",
          # khung khuyến nghị đa lớp (15/10/2026) – chấm bằng tools/multilayer_eval.py
          "ml_label", "ml_F", "ml_T", "ml_Q", "ml_V", "ml_G", "ml_penalty", "ml_blocked", "vnindex_ret_12T",
          "loi"]


PAUSE = [0.0]


def vn30() -> List[str]:
    from core.du_lieu import BASKETS
    key = next(k for k in BASKETS if "VN30" in k)
    return list(BASKETS[key])


class SlicedRepo:
    """Bọc DataRepository thật: lịch sử giá tải một lần cho toàn kỳ, các lần gọi sau cắt từ bản đã tải."""

    def __init__(self, repo, start: str):
        self._repo, self._start, self._px = repo, start, {}

    def __getattr__(self, name):
        return getattr(self._repo, name)

    def full_history(self, symbol: str) -> pd.DataFrame:
        s = symbol.upper()
        if s not in self._px:
            df = self._repo.get_price_history(s, start_date=self._start, end_date=str(pd.Timestamp.now().date()))
            df = df if df is not None else pd.DataFrame()
            if not df.empty:
                df = df.sort_values("timestamp").reset_index(drop=True)
            self._px[s] = df
        return self._px[s]

    def get_price_history(self, symbol: str, start_date: str = "", end_date: str = "", days: int = 365,
                          interval: str = "1D", force_refresh: bool = False) -> pd.DataFrame:
        if interval != "1D":
            return self._repo.get_price_history(symbol, start_date, end_date, days, interval, force_refresh)
        df = self.full_history(symbol)
        if df.empty:
            return df
        end = pd.to_datetime(end_date) if end_date else pd.Timestamp.now().normalize()
        start = pd.to_datetime(start_date) if start_date else end - pd.Timedelta(days=days)
        ts = pd.to_datetime(df["timestamp"])
        out = df[((ts >= start) & (ts <= end + pd.Timedelta(hours=23, minutes=59))).to_numpy()].copy()
        out.attrs = dict(getattr(df, "attrs", {}))
        return out.reset_index(drop=True)


def _close_at(df: pd.DataFrame, d: pd.Timestamp) -> Optional[float]:
    ts = pd.to_datetime(df["timestamp"])
    sub = df[(ts <= d).to_numpy()]
    return float(sub["close"].iloc[-1]) if len(sub) else None


def forward_metrics(px: pd.DataFrame, T: pd.Timestamp, trend_fn) -> Dict[str, Any]:
    """Kết quả sau T (chỉ dùng để chấm, không đưa vào mô hình)."""
    out: Dict[str, Any] = {}
    p0 = _close_at(px, T)
    if not p0:
        return out
    for m, k in ((3, "T3"), (6, "T6"), (12, "T12")):
        d = T + pd.DateOffset(months=m)
        if d <= pd.Timestamp.now():
            p = _close_at(px, d)
            out[f"gia_{k}"] = p
            out[f"ret_{k.replace('T', '')}T"] = p / p0 - 1 if p else None
    ts = pd.to_datetime(px["timestamp"])
    win = px[((ts > T) & (ts <= T + pd.DateOffset(months=3))).to_numpy()]
    if len(win):
        out["maxdd_3T"] = float(win["close"].min()) / p0 - 1
    # "Chờ điểm mua": ngày đầu tiên trong 6 tháng sau T mà xu hướng (cùng định nghĩa app) KHÔNG còn "Giảm"
    if out.get("gia_T12"):
        idx = px.index[((ts > T) & (ts <= T + pd.DateOffset(months=6))).to_numpy()]
        for i in idx:
            name = trend_fn(i)
            if name and "giảm" not in name.lower():
                out["cho_ngay_mua"] = str(pd.Timestamp(px.loc[i, "timestamp"]).date())
                out["cho_gia_mua"] = float(px.loc[i, "close"])
                out["cho_ret_den_T12"] = out["gia_T12"] / out["cho_gia_mua"] - 1
                break
    return out


def make_trend_fn(px: pd.DataFrame):
    """Xu hướng tại phiên i theo TechnicalAnalyzer của app, tính trên chỉ báo của chuỗi đầy đủ (chỉ báo cuộn – tại
    phiên i chỉ dùng dữ liệu đến i)."""
    from core.phan_tich_ky_thuat import TechnicalAnalyzer
    ta = TechnicalAnalyzer(px.copy())
    full = ta.compute_all()
    cache: Dict[int, Optional[str]] = {}

    def fn(i: int) -> Optional[str]:
        if i not in cache:
            try:
                cache[i] = ta._detect_trend(full.iloc[: i + 1]).get("name")
            except Exception:
                cache[i] = None
        return cache[i]
    return fn


def run(symbols: List[str], start: str, step: int, out_path: str, base_repo=None, last_T=None) -> None:
    from core.du_lieu import DataRepository
    from core.pipeline import StockService
    repo = SlicedRepo(base_repo or DataRepository(), start="2017-01-01")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    done = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8-sig") as f:
            done = {(r["ma"], r["T"]) for r in csv.DictReader(f)}
    last_T = pd.Timestamp(last_T) if last_T is not None else (pd.Timestamp.now() - pd.DateOffset(months=12)).normalize()
    try:
        rng = pd.date_range(pd.Timestamp(start + "-01"), last_T, freq="ME")
    except ValueError:                                   # pandas < 2.2
        rng = pd.date_range(pd.Timestamp(start + "-01"), last_T, freq="M")
    dates = list(rng)[::step]
    new = not os.path.exists(out_path)
    f = open(out_path, "a", newline="", encoding="utf-8-sig")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if new:
        w.writeheader()
    total, t0 = len(symbols) * len(dates), time.time()
    n = 0
    repo.full_history("VNINDEX")
    for sym in symbols:
        px = repo.full_history(sym)
        if px.empty:
            print(f"[{sym}] không tải được lịch sử giá → bỏ qua")
            continue
        trend_fn = make_trend_fn(px)
        for T in dates:
            n += 1
            key = (sym, str(T.date()))
            if key in done:
                continue
            row: Dict[str, Any] = {"ma": sym, "T": str(T.date())}
            try:
                inv = None
                for attempt in range(3):
                    try:
                        inv = StockService(sym, repository=repo, as_of=T).investment_analysis()
                        break
                    except SystemExit:                  # vnstock hết hạn mức 60 lượt/phút → thư viện tự thoát chương trình
                        print("  hết hạn mức gọi vnstock → chờ 65 giây rồi thử lại…")
                        time.sleep(65)
                if inv is None:
                    raise RuntimeError("vnstock hết hạn mức sau 3 lần thử")
                v = inv.get("valuation") or {}
                row.update(gia_T=v.get("price"), trend_cp=inv.get("trend"), target_12m=v.get("target_12m"), expected_return=v.get("expected_return"),
                           confidence=v.get("confidence"), health=(inv.get("health") or {}).get("score"),
                           profile=(v.get("profile") or {}).get("key"))
                asm, cd = v.get("assumptions") or {}, v.get("confidence_detail") or {}
                sh = asm.get("shares")
                pe_hist = (v.get("history") or {}).get("pe") or {}
                row.update(so_cp_dung=sh, he_so_co_so_gia=asm.get("price_basis_factor"),
                           cach_quy_doi=asm.get("price_basis_method"),
                           so_dot_dieu_chinh_sau_T=len(asm.get("price_basis_events") or []),
                           pe_cuoi_nam_truoc=pe_hist[max(pe_hist)] if pe_hist else None,
                           diem_tin_cay=cd.get("score"),
                           ly_do_tin_cay="; ".join(list(cd.get("reasons") or []) + [f"trần: {c}" for c in cd.get("caps") or []]),
                           rf_ghi_chu=v.get("risk_free_status"))
                ml = inv.get("multilayer") or {}
                row.update(ml_label=ml.get("label"), ml_F=ml.get("F"), ml_T=ml.get("R"), ml_Q=ml.get("Q"), ml_V=ml.get("V"),
                           ml_G=ml.get("G"), ml_penalty=ml.get("penalty"), ml_blocked=ml.get("blocked_by_exclusion"))
                row.update(forward_metrics(px, T, trend_fn))
                idx_px = repo.full_history("VNINDEX")
                i0, i12 = _close_at(idx_px, T), _close_at(idx_px, T + pd.DateOffset(months=12))
                if i0 and i12 and T + pd.DateOffset(months=12) <= pd.Timestamp.now():
                    row["vnindex_ret_12T"] = i12 / i0 - 1
            except Exception as exc:                              # ghi lỗi, không dừng cả lượt chạy
                import traceback
                tb = traceback.extract_tb(exc.__traceback__)
                where = " <- ".join(f"{os.path.basename(f.filename)}:{f.lineno}" for f in tb[::-1][:3])
                row["loi"] = f"{type(exc).__name__}: {exc} @ {where}"[:300]
            w.writerow({k: row.get(k) for k in FIELDS})
            f.flush()
            if PAUSE[0]:
                time.sleep(PAUSE[0])
            el = time.time() - t0
            print(f"[{n}/{total}] {sym} {T.date()} → {row.get('ml_label') or row.get('loi')}  "
                  f"(~{el / max(n, 1) * (total - n) / 60:.0f} phút còn lại)")
    f.close()
    print(f"Xong. Kết quả: {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", default="", help="danh sách mã, cách nhau dấu phẩy (mặc định: rổ VN30 của app); "
                    "'@tệp.txt' = đọc danh sách từ tệp (bỏ dòng bắt đầu bằng #), vd @tools/oos_basket.txt")
    ap.add_argument("--start", default="2021-01", help="tháng bắt đầu YYYY-MM")
    ap.add_argument("--step", type=int, default=1, help="bước tháng (1 = mỗi tháng, 3 = mỗi quý)")
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "rows.csv"))
    ap.add_argument("--pause", type=float, default=0.0,
                    help="nghỉ N giây sau mỗi lượt phân tích (tránh hết hạn mức 60 lượt gọi/phút của vnstock, vd 2)")
    a = ap.parse_args()
    raw = a.symbols
    if raw.startswith("@"):
        with open(raw[1:], encoding="utf-8") as fh:
            raw = ",".join(ln.strip() for ln in fh if ln.strip() and not ln.lstrip().startswith("#"))
    syms = [s.strip().upper() for s in raw.split(",") if s.strip()] or vn30()
    PAUSE[0] = max(0.0, a.pause)
    run(syms, a.start, a.step, a.out)
