"""
core/dinh_gia.py – gộp từ 4 module (15/10/2026).

MỤC LỤC
  • analytics/beta.py – Ước lượng beta so với VN-Index kèm KIỂM TRA ĐỘ TIN CẬY.
      hàm/lớp chính: estimate_beta
  • analytics/valuation.py – Valuation analysis engine.
      hàm/lớp chính: ValuationEngine
  • analytics/valuation_engine.py – Valuation Engine – GIÁ MỤC TIÊU 12 THÁNG (độc lập, minh bạch, có điểm thời gian).
      hàm/lớp chính: annual_available, sanitize_annual, point_in_time, year_end_prices, historical_multiples, gap_impact, net_debt_at, ValuationEngine12M
  • analytics/hybrid_valuation.py – Hybrid Valuation (bước 7) – định giá 12 tháng dùng dự báo của Forecast Engine (analytics/financial_forecast.py).
      hàm/lớp chính: select_profile, risk_free_status, price_series_check, value_hybrid
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/beta.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Ước lượng beta so với VN-Index kèm KIỂM TRA ĐỘ TIN CẬY.

Beta = Cov(R_cp, R_VNIndex) / Var(R_VNIndex), lợi nhuận NGÀY trên lịch phiên của VN-Index trong cửa sổ cố định
(settings.BETA_WINDOW_DAYS ngày lịch, tính lùi từ phiên VN-Index cuối cùng ≤ ngày định giá).

Chỉ dùng lợi nhuận của hai phiên LIỀN NHAU trên lịch chỉ số: phiên cổ phiếu không giao dịch (ngừng GD, thiếu dữ
liệu) làm mất cả lợi nhuận phiên đó lẫn phiên kế tiếp, thay vì gộp nhiều ngày vào một "lợi nhuận ngày".

Không đáng tin cậy (reliable = False, kèm lý do) khi:
  • số cặp lợi nhuận hợp lệ < min_obs, hoặc phủ < MIN_COVERAGE số phiên của chỉ số (thiếu phiên / mới niêm yết);
  • tỷ lệ phiên giá đứng yên (lợi nhuận = 0) > MAX_ZERO_SHARE hoặc phiên khối lượng 0 > MAX_NO_VOLUME_SHARE
    (cổ phiếu ít thanh khoản → beta bị kéo về 0 một cách giả tạo);
  • ngừng giao dịch liên tục > MAX_GAP_SESSIONS phiên, hoặc phiên cuối của cổ phiếu cách phiên cuối chỉ số
    > MAX_STALE_SESSIONS phiên (đang bị ngừng giao dịch / dữ liệu giá bị trễ).
Sai số chuẩn lớn chỉ tạo CẢNH BÁO (không loại).
"""


from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

MIN_COVERAGE = 0.80
MAX_ZERO_SHARE = 0.30
MAX_NO_VOLUME_SHARE = 0.20
MAX_GAP_SESSIONS = 20
MAX_STALE_SESSIONS = 5
WARN_SE = 0.35


def _daily(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if df is None or df.empty or "close" not in df.columns:
        return pd.DataFrame(columns=["close", "volume"])
    ts = pd.DatetimeIndex(pd.to_datetime(df["timestamp"] if "timestamp" in df.columns else df.index)).normalize()
    out = pd.DataFrame({"close": pd.to_numeric(df["close"], errors="coerce").to_numpy(),
                        "volume": pd.to_numeric(df["volume"], errors="coerce").to_numpy() if "volume" in df.columns
                        else np.nan}, index=ts)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out[out["close"] > 0]


def estimate_beta(stock: Optional[pd.DataFrame], index: Optional[pd.DataFrame], window_days: int = 365,
                  min_obs: int = 60) -> Dict[str, Any]:
    res: Dict[str, Any] = {"beta": None, "reliable": False, "obs": 0, "window_days": window_days, "warnings": []}
    s, m = _daily(stock), _daily(index)
    if s.empty or m.empty:
        res["warnings"].append("Thiếu dữ liệu giá cổ phiếu hoặc VN-Index")
        return res
    end = m.index.max()
    start = end - pd.Timedelta(days=int(window_days))
    cal = m.index[(m.index > start) & (m.index <= end)]            # lịch phiên của chỉ số trong cửa sổ
    res.update(start=str(cal.min().date()) if len(cal) else None, end=str(end.date()), index_sessions=int(len(cal)))
    if len(cal) < 2:
        res["warnings"].append("Cửa sổ beta không có đủ phiên VN-Index")
        return res

    sc = s["close"].reindex(cal)
    mc = m["close"].reindex(cal)
    traded = sc.notna()
    if "volume" in s.columns and s["volume"].notna().any():
        vol = s["volume"].reindex(cal)
        no_vol = traded & (vol.fillna(0) <= 0)
    else:
        no_vol = pd.Series(False, index=cal)
    rs = sc / sc.shift(1) - 1                                      # NaN nếu phiên trước/này không có giá
    rm = mc / mc.shift(1) - 1
    j = pd.concat([rs, rm], axis=1, keys=["s", "m"]).dropna()

    n, n_cal = len(j), len(cal) - 1
    coverage = n / n_cal if n_cal else 0.0
    zero_share = float((j["s"] == 0).mean()) if n else 1.0
    no_vol_share = float(no_vol[traded].mean()) if traded.any() else 1.0
    first_trade = sc.first_valid_index()
    last_trade = sc.last_valid_index()
    gaps = (~traded)[cal >= first_trade].astype(int) if first_trade is not None else pd.Series(dtype=int)
    run = gaps.groupby((gaps == 0).cumsum()).cumsum() if len(gaps) else gaps   # số phiên trống liên tiếp (sau khi niêm yết)
    max_gap = int(run.max()) if len(run) else 0
    stale = int((cal > last_trade).sum()) if last_trade is not None else len(cal)
    res.update(obs=n, coverage=round(coverage, 3), zero_return_share=round(zero_share, 3),
               no_volume_share=round(no_vol_share, 3), max_gap_sessions=max_gap, stale_sessions=stale,
               first_trade=str(first_trade.date()) if first_trade is not None else None)

    reasons: List[str] = []
    if n < min_obs:
        reasons.append(f"chỉ có {n} cặp lợi nhuận ngày hợp lệ (< {min_obs})")
    if coverage < MIN_COVERAGE:
        short = first_trade is not None and first_trade > cal[0] + pd.Timedelta(days=30)
        reasons.append(f"chỉ phủ {coverage * 100:.0f}% số phiên VN-Index trong cửa sổ"
                       + (" (lịch sử giao dịch ngắn/mới niêm yết)" if short else " (thiếu phiên/ngừng giao dịch)"))
    if zero_share > MAX_ZERO_SHARE:
        reasons.append(f"{zero_share * 100:.0f}% phiên giá đứng yên (ít thanh khoản)")
    if no_vol_share > MAX_NO_VOLUME_SHARE:
        reasons.append(f"{no_vol_share * 100:.0f}% phiên không có khối lượng (ít thanh khoản)")
    if max_gap > MAX_GAP_SESSIONS:
        reasons.append(f"ngừng giao dịch liên tục {max_gap} phiên")
    if stale > MAX_STALE_SESSIONS:
        reasons.append(f"phiên giao dịch cuối của cổ phiếu cách phiên cuối VN-Index {stale} phiên")

    var_m = float(j["m"].var()) if n > 1 else 0.0
    if n > 2 and var_m > 0:
        beta = float(j["s"].cov(j["m"]) / var_m)
        resid = j["s"] - beta * j["m"] - (j["s"].mean() - beta * j["m"].mean())
        se = float(np.sqrt(resid.var() / ((n - 2) * var_m))) if n > 2 else None
        res.update(beta_raw=beta, se=se)
        if se is not None and se > WARN_SE:
            res["warnings"].append(f"Sai số chuẩn của beta lớn (±{se:.2f})")
    else:
        reasons.append("VN-Index không biến động trong cửa sổ")
        beta = None

    res["reliable"] = beta is not None and not reasons
    res["beta"] = beta if res["reliable"] else None
    if reasons:
        res["warnings"] = [f"Beta không đủ tin cậy: {'; '.join(reasons)}"] + res["warnings"]
    return res


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/valuation.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Valuation analysis engine.

Methods:
  - P/E, P/B relative valuation
  - EV/EBITDA (when data available)
  - Simplified DCF
  - DDM (for dividend-paying stocks)
  - 3-scenario valuation (bear/base/bull)
"""


import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.cau_hinh import FUNDAMENTAL_THRESHOLDS as THR

logger = logging.getLogger(__name__)


def _s(v) -> Optional[float]:
    try:
        return None if pd.isna(v) else float(v)
    except (TypeError, ValueError):
        return None


class ValuationEngine:
    """
    Compute stock valuation estimates.

    Parameters
    ----------
    symbol         : Ticker
    current_price  : Latest market price
    ratio_df       : Financial ratio DataFrame from provider
    is_df          : Income Statement
    bs_df          : Balance Sheet
    shares_outstanding : Number of shares
    market_cap     : Market cap (VND)
    peer_stats     : Trung vị chỉ số của nhóm ngành (analytics.peers.compute_peer_stats)
    """

    # Chỉ dùng khi KHÔNG lấy được dữ liệu ngành – được ghi rõ trong kết quả

    def __init__(
        self,
        symbol: str,
        current_price: float,
        ratio_df: pd.DataFrame = None,
        is_df: pd.DataFrame = None,
        bs_df: pd.DataFrame = None,
        shares_outstanding: Optional[float] = None,
        market_cap: Optional[float] = None,
        peer_stats: Optional[Dict[str, Any]] = None,
        eps_override: Optional[float] = None,
        bvps_override: Optional[float] = None,
    ):
        self.symbol = symbol
        # On VN exchanges, quotes < 1000 are in k VND (e.g. 19.0 = 19,000 VND)
        p = float(current_price) if current_price else 0.0
        self.price = (p * 1000.0) if (0 < p < 1000.0) else p
        self.ratio_df = order_tabular(flatten_columns(ratio_df))
        self.is_df = order_tabular(flatten_columns(is_df))
        self.bs_df = order_tabular(flatten_columns(bs_df))
        self.shares = shares_outstanding
        self.market_cap = market_cap
        self.peer_stats = peer_stats or {}
        # EPS/BVPS tính từ BCTC (TTM) được ưu tiên hơn số dựng sẵn của nhà cung cấp
        self.eps_override = eps_override if eps_override and eps_override > 0 else None
        self.bvps_override = bvps_override if bvps_override and bvps_override > 0 else None

    def _sector_multiple(self, key: str):
        """Trả về (giá trị, nguồn) cho P/E hoặc P/B tham chiếu. Bước 9: KHÔNG còn hệ số mặc định gõ tay (P/E 15, P/B 1,5)
        – nhóm ngành < 3 DN có số liệu → (None, lý do) và không tính giá trị theo bội số ngành."""
        v = self.peer_stats.get(key)
        if v is not None and v > 0:
            group = self.peer_stats.get("group", "ngành")
            n = self.peer_stats.get(f"n_{key}", self.peer_stats.get("n", 0))
            return float(v), f"Trung vị {group} ({n} DN)"
        return None, "Thiếu dữ liệu: nhóm ngành chưa đủ 3 DN có số liệu – không dùng hệ số mặc định"

    # ─────────────────── Column finder ───────────────────────────────────────

    @staticmethod
    def _match(candidate: str, target: str) -> bool:
        c_clean = candidate.lower().replace("_", "").replace(" ", "").replace("/", "").replace("%", "")
        t_clean = target.lower().replace("_", "").replace(" ", "").replace("/", "").replace("%", "")
        if c_clean == t_clean:
            return True
        if c_clean in {"pe", "pb", "ps", "eps"}:
            return t_clean.startswith(c_clean) or t_clean.endswith(c_clean)
        if len(c_clean) >= 4 and c_clean in t_clean:
            return True
        if len(t_clean) >= 4 and t_clean in c_clean:
            return True
        return False

    def _col(self, df: pd.DataFrame, names: List[str]) -> Optional[float]:
        if df is None or df.empty:
            return None

        # 1. Tabular format (columns match name)
        for n in names:
            for c in df.columns:
                if self._match(n, str(c)):
                    s = pd.to_numeric(df[c], errors="coerce").dropna()
                    if not s.empty:
                        return float(s.iloc[-1])

        # 2. Matrix format (rows have item_id / item / item_en, columns are periods)
        id_cols = [c for c in ["item_id", "item", "item_en"] if c in df.columns]
        if id_cols:
            period_cols, _ = ordered_period_columns(df)   # đúng thứ tự thời gian
            if period_cols:
                for n in names:
                    for _, row in df.iterrows():
                        rks = [str(row[ic]) for ic in id_cols if pd.notna(row[ic])]
                        if any(self._match(n, rk) for rk in rks):
                            vals = pd.to_numeric(row[period_cols], errors="coerce").dropna()
                            # filter out 0 if multiple periods available and earlier has real number
                            non_zero = vals[vals != 0]
                            if not non_zero.empty:
                                return float(non_zero.iloc[-1])
                            elif not vals.empty:
                                return float(vals.iloc[-1])
        return None

    def get_shares_outstanding(self) -> Optional[float]:
        if self.shares and self.shares > 0:
            return self.shares
        shares = self._col(self.ratio_df, ["outstanding_shares", "so cp luu hanh", "shares_outstanding"])
        if shares and shares > 0:
            return shares if shares > 10_000_000 else shares * 1e6
        return None

    # ─────────────────── P/E, P/B, EPS, BVPS ─────────────────────────────────

    def get_pe(self) -> Optional[float]:
        if self.eps_override and self.price > 0:
            return round(self.price / self.eps_override, 2)
        # 1. From ratio df
        pe = self._col(self.ratio_df, ["pe_ratio", "p/e", "pe", "price earning", "price to earnings"])
        if pe is not None and pe > 0:
            return pe
        # 2. Compute from EPS
        eps = self.get_eps()
        if eps and eps > 0 and self.price > 0:
            return round(self.price / eps, 2)
        return None

    def get_pb(self) -> Optional[float]:
        if self.bvps_override and self.price > 0:
            return round(self.price / self.bvps_override, 2)
        # 1. From ratio df
        pb = self._col(self.ratio_df, ["pb_ratio", "p/b", "pb", "price book", "price to book"])
        if pb is not None and pb > 0:
            return pb
        # 2. Compute from BVPS
        bvps = self.get_bvps()
        if bvps and bvps > 0 and self.price > 0:
            return round(self.price / bvps, 2)
        return None

    def get_eps(self) -> Optional[float]:
        if self.eps_override:
            return self.eps_override
        # 1. Direct from ratio df
        eps = self._col(self.ratio_df, ["eps", "earnings per share", "eps_basic_vnd", "lai co ban tren co phieu"])
        if eps is not None and eps > 0:
            return eps

        # 2. Direct from is_df
        eps_is = self._col(self.is_df, ["eps_basic_vnd", "eps", "lai co ban tren co phieu", "net_income_to_common_share"])
        if eps_is is not None and eps_is > 0:
            return eps_is

        # 3. Calculate from price / pe
        pe = self._col(self.ratio_df, ["pe_ratio", "p/e", "pe", "price earning"])
        if pe and pe > 0 and self.price > 0:
            return round(self.price / pe, 1)

        # 4. Calculate from net_profit / shares
        shares = self.get_shares_outstanding()
        net_profit = self._col(self.is_df, [
            "net_profit", "lợi nhuận sau thuế", "net profit", "profit after tax", "loi_nhuan", "LNST", "profit_after_tax"
        ])
        if net_profit and shares and shares > 0 and net_profit > 0:
            return round(net_profit / shares, 1)

        return None

    def get_bvps(self) -> Optional[float]:
        if self.bvps_override:
            return self.bvps_override
        # 1. Direct from ratio df
        bvps = self._col(self.ratio_df, ["bvps", "book value per share", "gia tri so sach"])
        if bvps is not None and bvps > 0:
            return bvps

        # 2. Calculate from price / pb
        pb = self._col(self.ratio_df, ["pb_ratio", "p/b", "pb", "price book"])
        if pb and pb > 0 and self.price > 0:
            return round(self.price / pb, 1)

        # 3. Calculate from balance sheet equity / shares
        shares = self.get_shares_outstanding()
        equity = self._col(self.bs_df, ["owners_equity", "equity", "vốn chủ sở hữu", "von chu so huu"])
        if equity and shares and shares > 0 and equity > 0:
            return round(equity / shares, 1)

        return None

    # ─────────────────── Relative Valuation ──────────────────────────────────

    def relative_valuation(self) -> Dict[str, Any]:
        pe = self.get_pe()
        pb = self.get_pb()
        eps = self.get_eps()
        bvps = self.get_bvps()

        result: Dict[str, Any] = {
            "current_price": self.price,
            "pe": pe,
            "pb": pb,
            "eps": eps,
            "bvps": bvps,
        }

        # Fair value estimates – dùng trung vị P/E, P/B của nhóm ngành khi có
        sector_pe, pe_src = self._sector_multiple("pe")
        sector_pb, pb_src = self._sector_multiple("pb")
        result["sector_pe"] = sector_pe
        result["sector_pe_source"] = pe_src
        result["sector_pb"] = sector_pb
        result["sector_pb_source"] = pb_src

        estimates = []
        if pe is not None and eps is not None and sector_pe is not None:
            pe_fair = eps * sector_pe
            result["pe_fair_value"] = pe_fair
            result["pe_upside"] = (pe_fair - self.price) / self.price * 100 if self.price else None
            result["pe_vs_sector"] = pe / sector_pe if pe and pe > 0 else None
            estimates.append(pe_fair)

        if pb is not None and bvps is not None and sector_pb is not None:
            pb_fair = bvps * sector_pb
            result["pb_fair_value"] = pb_fair
            result["pb_upside"] = (pb_fair - self.price) / self.price * 100 if self.price else None
            result["pb_vs_sector"] = pb / sector_pb if pb and pb > 0 else None
            estimates.append(pb_fair)

        if estimates:
            result["average_fair_value"] = np.mean(estimates)
            result["upside"] = (result["average_fair_value"] - self.price) / self.price * 100 if self.price else None

        # Valuation assessment
        if pe is not None:
            if pe > THR["pe_overvalued"]:
                result["pe_assessment"] = "Định giá cao"
            elif pe > THR["pe_fair"]:
                result["pe_assessment"] = "Hợp lý"
            elif pe > THR["pe_cheap"]:
                result["pe_assessment"] = "Rẻ hơn thị trường"
            elif pe > 0:
                result["pe_assessment"] = "Rẻ"
            else:
                result["pe_assessment"] = "Lỗ / Không xác định"

        return result

    # ─────────────────── Valuation Score ─────────────────────────────────────

    def compute_valuation_score(self, history: Optional[Dict[str, Dict[Any, float]]] = None,
                                profile_weights: Optional[Dict[str, float]] = None,
                                profile_label: Optional[str] = None) -> Dict[str, Any]:
        """Score valuation 0–100 (higher = more undervalued / reasonable) – cách chấm DỰ PHÒNG khi định giá 12T chưa đủ tin cậy.

        Góp ý GK (II.2), 15/10/2026:
          • Mỗi bội số = 50% so với LỊCH SỬ 5 NĂM của chính doanh nghiệp + 50% so với TRUNG VỊ NGÀNH (ưu tiên trung vị
            theo vốn hóa) – ngành VN thường lệch chuẩn do vài DN đầu ngành vượt trội.
          • Trọng số P/E – P/B theo HỒ SƠ NGÀNH của mô hình định giá: hồ sơ loại P/B (vd Công nghệ) → không chấm P/B.
          • Không có ngành lẫn lịch sử → ngưỡng tuyệt đối toàn thị trường (ghi rõ)."""
        rel = self.relative_valuation()
        components: Dict[str, Any] = {}
        missing: List[str] = []
        history = history or {}
        notes: List[str] = []

        def _rel_score(ratio: float) -> float:          # thang 0–1
            if ratio < 0.7:
                return 1.0      # rẻ hơn mốc so sánh > 30%
            if ratio <= 1.0:
                return 0.7      # rẻ hơn hoặc bằng
            if ratio <= 1.3:
                return 0.4      # đắt hơn ≤ 30%
            return 0.1          # đắt hơn > 30%

        def _hist_median(key: str) -> Optional[float]:
            h = history.get(key) or {}
            vals = [float(v) for _y, v in sorted(h.items(), key=lambda kv: str(kv[0]))[-5:]
                    if v is not None and pd.notna(v) and v > 0]
            return float(np.median(vals)) if len(vals) >= 3 else None

        # trọng số theo hồ sơ ngành (chỉ P/E và P/B dùng trong thẻ điểm)
        pw = profile_weights or {}
        w_pe = float(pw.get("pe", 0) or 0) if pw else 50.0
        w_pb = float(pw.get("pb", 0) or 0) if pw else 50.0
        if pw and w_pe <= 0 and w_pb <= 0:                 # hồ sơ không dùng cả hai → chia đều
            w_pe = w_pb = 50.0
        tot = w_pe + w_pb
        mx = {"pe": round(100 * w_pe / tot), "pb": 100 - round(100 * w_pe / tot)}
        if pw and w_pb <= 0:
            notes.append(f"Hồ sơ ngành '{profile_label or '—'}' không dùng P/B → thẻ điểm không chấm P/B.")

        thr = {"pe": (THR["pe_cheap"], THR["pe_fair"], THR["pe_overvalued"]),
               "pb": (THR["pb_cheap"], THR["pb_fair"], THR["pb_overvalued"])}
        for key, lbl in (("pe", "P/E"), ("pb", "P/B")):
            if mx[key] <= 0:
                components[key] = {"score": None, "max": 0, "value": rel.get(key), "note": "Không áp dụng theo hồ sơ ngành"}
                continue
            v = rel.get(key)
            if v is None:
                missing.append(lbl)
                components[key] = {"score": None, "max": mx[key]}
                continue
            if v <= 0:
                components[key] = {"score": 0, "max": mx[key], "value": v, "note": "Âm"}
                continue
            capw = self.peer_stats.get(f"{key}_capw")
            sector = capw if capw else rel.get(f"sector_{key}")
            sector_src = "trung vị ngành theo vốn hóa" if capw else "trung vị ngành"
            hist_med = _hist_median(key)
            parts, method = [], []
            if hist_med:
                parts.append(_rel_score(v / hist_med))
                method.append(f"lịch sử 5 năm {hist_med:.2f}x")
            if sector:
                parts.append(_rel_score(v / sector))
                method.append(f"{sector_src} {sector:.2f}x")
            if not parts:
                lo, mid, hi = thr[key]
                parts.append(1.0 if v < lo else 0.7 if v <= mid else 0.4 if v <= hi else 0.1)
                method.append("ngưỡng tuyệt đối thị trường")
            sc = round(float(np.mean(parts)) * mx[key])
            components[key] = {"score": sc, "max": mx[key], "value": round(v, 2),
                               "vs_sector": round(v / sector, 2) if sector else None,
                               "vs_history": round(v / hist_med, 2) if hist_med else None,
                               "method": "So với " + " + ".join(method) + (" (50/50)" if len(parts) == 2 else "")}

        available_max = sum(c["max"] for c in components.values() if c.get("score") is not None)
        available_total = sum(c["score"] for c in components.values() if c.get("score") is not None)

        final = round((available_total / available_max) * 100) if available_max > 0 else None

        return {
            "score": final,
            "components": components,
            "missing_data": missing,
            "relative_valuation": rel,
            "note": " ".join(notes),
        }


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/valuation_engine.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Valuation Engine – GIÁ MỤC TIÊU 12 THÁNG (độc lập, minh bạch, có điểm thời gian).

Phương pháp (chỉ dùng phương pháp đủ dữ liệu và cho kết quả hợp lệ; trọng số chuẩn hóa lại):
  P/E       : Giá mục tiêu = EPS dự phóng (12T tới) × P/E mục tiêu
              EPS dự phóng = Doanh thu năm gần nhất × (1 + g) × biên LN ròng giả định / số CP lưu hành
              (ngân hàng/CTCK/bảo hiểm: LNST × (1 + g)). P/E mục tiêu = trung vị {P/E lịch sử, P/E ngành},
              kịch bản dùng phân vị 25/50/75 của P/E lịch sử. Không dùng khi EPS dự phóng ≤ 0.
  P/B       : Giá mục tiêu = BVPS dự phóng × P/B mục tiêu; BVPS dự phóng = BVPS × (1 + ROE × (1 − tỷ lệ chi trả))
              P/B mục tiêu = trung vị {P/B lịch sử, P/B ngành, P/B hợp lý (ROE − g)/(Ke − g)}.
  DCF-FCFF  : FCFF = CFO + lãi vay × (1 − t) − Capex (bình quân 3 năm); tăng trưởng giảm dần về g dài hạn trong 5 năm;
              WACC = E/(D+E)·Ke + D/(D+E)·Kd·(1 − t); giá trị VCSH = EV − nợ vay + tiền & ĐTNH − lợi ích CĐ thiểu số.
              Giá trị nội tại hôm nay → giá mục tiêu = nội tại × (1 + Ke) − cổ tức dự kiến. Chỉ cho DN phi tài chính.
  EV/EBITDA : EV mục tiêu = EBITDA dự phóng × EV/EBITDA lịch sử (trung vị/phân vị); VCSH = EV − nợ vay ròng − CĐ thiểu số.
Kịch bản Bear/Base/Bull: thay đổi BỘ GIẢ ĐỊNH (tăng trưởng, biên lợi nhuận, bội số theo phân vị, Ke, ROE) – không
cộng/trừ tùy ý vào giá. Không xác định được giá đáng tin cậy → "CHƯA ĐỦ CƠ SỞ ĐỊNH GIÁ".
"""


import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.cau_hinh import load_config
from core.cau_hinh import settings

FINANCIAL_TYPES = ("bank", "securities", "insurance")
NOT_ENOUGH = "CHƯA ĐỦ CƠ SỞ ĐỊNH GIÁ"
SCEN = ("bear", "base", "bull")
SCEN_LABEL = {"bear": "Thận trọng (Bear)", "base": "Cơ sở (Base)", "bull": "Tích cực (Bull)"}


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _col(w: pd.DataFrame, c: str) -> pd.Series:
    return w[c].astype(float) if w is not None and c in w.columns else pd.Series(index=getattr(w, "index", None), dtype=float)


def _last(s: pd.Series) -> Optional[float]:
    s = s.dropna()
    return float(s.iloc[-1]) if not s.empty else None


def _cagr(s: pd.Series, years: int = 3) -> Optional[float]:
    s = s.dropna()
    if len(s) < 2:
        return None
    n = min(years, len(s) - 1)
    a, b = float(s.iloc[-1 - n]), float(s.iloc[-1])
    if a <= 0 or b <= 0:
        return None
    return (b / a) ** (1 / n) - 1


# ─────────────────────────────────────────────────────────────────────────────
# Điểm thời gian – không dùng dữ liệu công bố sau ngày định giá
# ─────────────────────────────────────────────────────────────────────────────

def annual_available(period_key: int, as_of: pd.Timestamp, release_month: Optional[int] = None,
                     available_at: Optional[Any] = None) -> bool:
    """Ưu tiên ngày công bố thật; nếu thiếu mới dùng mốc bảo thủ có thể cấu hình."""
    if available_at is not None and pd.notna(available_at):
        return pd.Timestamp(as_of).normalize() >= pd.Timestamp(available_at).normalize()
    release_month = release_month or settings.ANNUAL_RELEASE_MONTH
    y = int(period_key) // 10
    return as_of >= pd.Timestamp(year=y + 1, month=release_month, day=1)


def sanitize_annual(wide: Optional[pd.DataFrame]) -> Tuple[Optional[pd.DataFrame], List[str]]:
    """Kiểm tra chất lượng BCTC năm (bước 9) – KHÔNG sửa số liệu, chỉ bỏ số liệu không dùng được và ghi chú:
      • năm có MỌI chỉ tiêu số trùng khớp năm liền trước (≥ 8 chỉ tiêu có số) → nghi lỗi sao chép của nguồn → bỏ năm;
      • LNTT và LNST cùng đúng bằng 0 trong khi VCSH > 0 → coi lợi nhuận là THIẾU (NaN), không phải lãi 0."""
    notes: List[str] = []
    if wide is None or wide.empty:
        return wide, notes
    w = wide.copy()
    num = w.select_dtypes("number")
    drop = []
    for i in range(1, len(w)):
        a, b = num.iloc[i], num.iloc[i - 1]
        if a.notna().sum() >= 8 and a.fillna(-1.2345).equals(b.fillna(-1.2345)):
            drop.append(w.index[i])
    if drop:
        w = w.drop(index=drop)
        notes.append("BCTC năm " + ", ".join(str(int(k) // 10) for k in drop) + " trùng khớp hoàn toàn năm trước (nghi lỗi "
                     "sao chép của nguồn dữ liệu) → không dùng.")
    if {"profit_before_tax", "net_income"} <= set(w.columns):
        z = (w["profit_before_tax"] == 0) & (w["net_income"] == 0) & (w.get("equity", pd.Series(0, index=w.index)) > 0)
        if z.any():
            for c in ("profit_before_tax", "net_income", "net_income_parent", "income_tax"):
                if c in w.columns:
                    w[c] = pd.to_numeric(w[c], errors="coerce").astype("float64")
                    w.loc[z, c] = np.nan
            notes.append("Lợi nhuận bằng đúng 0 trong khi có vốn chủ (năm " + ", ".join(str(int(k) // 10) for k in w.index[z])
                         + ") → coi là thiếu số liệu, không phải lãi 0.")
    w.attrs = dict(getattr(wide, "attrs", {}))
    return w, notes


def point_in_time(wide: Optional[pd.DataFrame], ratios: Optional[pd.DataFrame], price_df: Optional[pd.DataFrame],
                  as_of: pd.Timestamp, release_month: Optional[int] = None):
    def keep(df):
        if df is None or df.empty:
            return df
        actual = getattr(df, "attrs", {}).get("available_at", {})
        mask = [annual_available(k, as_of, release_month, actual.get(k, actual.get(str(k)))) for k in df.index]
        out = df[mask].copy()
        out.attrs = dict(getattr(df, "attrs", {}))
        out.attrs["point_in_time_basis"] = "actual_release_dates" if actual else "estimated_release_dates"
        return out
    px = None
    if price_df is not None and not price_df.empty:
        ts = pd.to_datetime(price_df["timestamp"] if "timestamp" in price_df.columns else price_df.index)
        px = price_df[(ts <= as_of).to_numpy()]
    return keep(wide), keep(ratios), px


# ─────────────────────────────────────────────────────────────────────────────
# Bội số lịch sử (giá cuối năm đã điều chỉnh, số CP hiện tại)
# ─────────────────────────────────────────────────────────────────────────────

def year_end_prices(price_df: Optional[pd.DataFrame]) -> Dict[int, float]:
    if price_df is None or price_df.empty or "close" not in price_df.columns:
        return {}
    ts = pd.to_datetime(price_df["timestamp"] if "timestamp" in price_df.columns else price_df.index)
    s = pd.Series(price_df["close"].astype(float).values, index=ts).dropna().sort_index()
    if s.empty:
        return {}
    last_year = s.index.max().year
    return {int(y): float(g.iloc[-1]) for y, g in s.groupby(s.index.year) if y < last_year or g.index.max().month == 12}


def historical_multiples(wide: Optional[pd.DataFrame], shares: Optional[float], price_df: Optional[pd.DataFrame],
                         years: int = 5, core: bool = False) -> Dict[str, Dict[int, float]]:
    """P/E, P/B, EV/EBITDA cuối từng năm. core=True (Hybrid, bước 9): EV/EBITDA dùng EBITDA CỐT LÕI và EV đã trừ cả
    đầu tư tài chính dài hạn – cùng định nghĩa với EBITDA dự báo và cầu nối vốn chủ, để bội số và cơ sở khớp nhau.
    Năm thiếu số đầu tư dài hạn → bỏ năm đó (không coi = 0)."""
    out: Dict[str, Dict[int, float]] = {"pe": {}, "pb": {}, "ev_ebitda": {}}
    if wide is None or wide.empty or not shares or shares <= 0:
        return out
    prices = year_end_prices(price_df)
    ebitda_s = core_ebit_ebitda(wide)[1] if core else ebit_ebitda(wide)[1]
    for k in wide.index:
        y = int(k) // 10
        p = prices.get(y)
        if p is None:
            continue
        r = wide.loc[k]
        ni = _num(r.get("net_income_parent")) or _num(r.get("net_income"))
        eq = _num(r.get("equity"))
        mi = _num(r.get("minority_interest")) or 0.0
        mcap = p * shares
        if ni and ni > 0 and 2 <= mcap / ni <= 60:
            out["pe"][y] = mcap / ni
        if eq and eq - mi > 0 and 0.2 <= mcap / (eq - mi) <= 15:
            out["pb"][y] = mcap / (eq - mi)
        ebitda = _num(ebitda_s.get(k))
        bridge = net_debt_at(wide, k, include_lt=core)
        if core and bridge["ok"] and any(g["item"] == "đầu tư tài chính dài hạn" for g in bridge["gaps"]):
            continue
        if ebitda is not None and bridge["ok"]:          # EBITDA và cầu nối nợ vay cùng một năm
            ev = mcap + bridge["debt"] - bridge["cash"] - bridge.get("lt_investments", 0.0) + bridge["minority"]
            if ebitda > 0 and 1 <= ev / ebitda <= 40:
                out["ev_ebitda"][y] = ev / ebitda
    return {k: dict(sorted(v.items())[-years:]) for k, v in out.items()}


GAP_LOW, GAP_HIGH = 0.05, 0.15         # ảnh hưởng tối đa < 5% vốn hóa: thấp; 5–15%: trung bình; > 15%: cao


def gap_impact(bound: Optional[float], base: Optional[float]) -> Dict[str, Any]:
    """Mức ảnh hưởng của một khoản thiếu số liệu bị coi = 0: so cận trên của khoản đó với một đại lượng gốc
    (vốn hóa thị trường, EBITDA…). Không có cận trên → "không xác định" (phải coi như rủi ro)."""
    if bound is None or base is None or base <= 0:
        return {"impact": "không xác định", "impact_pct": None}
    pct = abs(bound) / base
    lvl = "thấp" if pct < GAP_LOW else "trung bình" if pct <= GAP_HIGH else "cao"
    return {"impact": lvl, "impact_pct": pct}


def net_debt_at(wide: pd.DataFrame, k, include_lt: bool = False) -> Dict[str, Any]:
    """Cầu nối EV → vốn chủ tại ĐÚNG kỳ k: nợ vay (ngắn + dài hạn), tiền + ĐTTC ngắn hạn, lợi ích CĐ thiểu số.

    Yêu cầu bảng cân đối của kỳ k tồn tại (có tổng tài sản hoặc VCSH). Không lấy số của kỳ khác. Dòng không có
    số liệu được tạm coi = 0 NHƯNG được ghi vào 'gaps' kèm cận trên (để đánh giá ảnh hưởng):
      vay nợ  ≤ tổng nợ phải trả · tiền & ĐTTC ngắn hạn ≤ tài sản ngắn hạn ·
      CĐ thiểu số ≈ VCSH × (1 − LNST cổ đông mẹ / LNST) (≈ 0 khi hai số LNST bằng nhau).
    include_lt (bước 9 – Hybrid): thêm 'lt_investments' = đầu tư tài chính dài hạn (gồm khoản đầu tư vào công ty
      liên doanh–liên kết, giá trị sổ sách) – cộng riêng vì EBIT cốt lõi đã loại thu nhập của các khoản này;
      cận trên khi thiếu = tổng tài sản − tài sản ngắn hạn − tài sản cố định."""
    if wide is None or k not in wide.index:
        return {"ok": False, "reason": "Không có số liệu kỳ gốc"}
    r = wide.loc[k]
    y = int(k) // 10
    if _num(r.get("total_assets")) is None and _num(r.get("equity")) is None:
        return {"ok": False, "reason": f"Thiếu bảng cân đối năm {y} (cùng kỳ với lợi nhuận/dòng tiền gốc)"}
    notes: List[str] = []
    gaps: List[Dict[str, Any]] = []

    ni, nip, eq = _num(r.get("net_income")), _num(r.get("net_income_parent")), _num(r.get("equity"))
    mi_bound = None
    if ni and nip is not None and eq:
        mi_bound = 0.0 if abs(ni - nip) <= 0.01 * abs(ni) else abs(eq) * max(0.0, 1 - nip / ni)
    bounds = {"vay nợ": _num(r.get("total_liabilities")),
              "tiền & ĐTTC ngắn hạn": _num(r.get("current_assets")),
              "lợi ích CĐ thiểu số": mi_bound}
    ta, ca, fa = _num(r.get("total_assets")), _num(r.get("current_assets")), _num(r.get("fixed_assets"))
    bounds["đầu tư tài chính dài hạn"] = max(ta - ca - (fa or 0.0), 0.0) if ta is not None and ca is not None else None

    def part(cols, label, absolute=False):
        vals = [_num(r.get(c)) for c in cols]
        if all(v is None for v in vals):
            notes.append(f"Năm {y} không có số liệu {label} → tạm coi bằng 0 (xem mức ảnh hưởng)")
            gaps.append({"item": label, "year": y, "treated_as": 0.0, "bound": bounds.get(label),
                         "direction": "giá trị vốn chủ có thể bị THỔI PHỒNG"
                         if label not in ("tiền & ĐTTC ngắn hạn", "đầu tư tài chính dài hạn")
                         else "giá trị vốn chủ có thể bị ĐÁNH GIÁ THẤP"})
            return 0.0
        return float(sum(abs(v) if absolute else v for v in vals if v is not None))

    debt = part(("short_term_debt", "long_term_debt"), "vay nợ", absolute=True)
    cash = part(("cash", "short_term_investments"), "tiền & ĐTTC ngắn hạn")
    mi = part(("minority_interest",), "lợi ích CĐ thiểu số")      # giữ dấu (có thể âm)
    out = {"ok": True, "debt": debt, "cash": cash, "minority": mi, "notes": notes, "gaps": gaps, "year": y,
           "key": int(k), "label": f"năm {y}" if int(k) % 10 == 0 else f"Q{int(k) % 10}/{y}"}
    if include_lt:
        out["lt_investments"] = part(("long_term_investments",), "đầu tư tài chính dài hạn")
    return out


def _pct(vals: List[float], q: float) -> Optional[float]:
    return float(np.percentile(vals, q)) if len(vals) >= 3 else None


# ─────────────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────────────

class ValuationEngine12M:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.cfg = config or load_config()
        self.v = self.cfg["valuation"]

    def adj_beta(self, beta: Optional[float]) -> Optional[float]:
        """Beta điều chỉnh (Blume): 0,67 × beta hồi quy + 0,33 – beta có xu hướng hồi quy về 1; tránh Ke quá thấp cho mã
        phòng thủ (vd VNM beta 0,6 → 0,73) và quá cao cho mã biến động."""
        if beta is None or (isinstance(beta, float) and math.isnan(beta)):
            return None
        return 0.67 * float(beta) + 0.33 if self.v.get("beta_blume") else float(beta)

    def ke(self, beta: Optional[float], shift: float = 0.0) -> float:
        lo, hi = self.v["beta_bounds"]
        beta = self.adj_beta(beta)
        b = min(max(beta, lo), hi) if beta is not None and not math.isnan(beta) else 1.0
        k = self.v["risk_free"] + b * self.v["equity_premium"] + shift
        return float(min(max(k, self.v["ke_bounds"][0]), self.v["ke_bounds"][1] + 0.01))

    def value(self, *, price: Optional[float], price_date: Optional[pd.Timestamp], wide: Optional[pd.DataFrame],
              ratios: Optional[pd.DataFrame], shares: Optional[float], company: Dict[str, str],
              beta: Optional[float] = None, peers: Optional[Dict[str, Any]] = None,
              price_df: Optional[pd.DataFrame] = None, risk_level: Optional[str] = None,
              as_of: Optional[pd.Timestamp] = None, forecast: Optional[Dict[str, Any]] = None,
              quarterly: Optional[pd.DataFrame] = None, dividends: Optional[pd.DataFrame] = None,
              share_factor: float = 1.0, dps_factor: float = 1.0, basis_unknown: bool = False) -> Dict[str, Any]:
        """Giá mục tiêu. Mặc định (valuation.use_forecast_engine = True) dùng Hybrid Valuation với dự báo của
        Forecast Engine (truyền 'forecast' đã tính sẵn – kèm TTM/backtest – hoặc engine tự tính từ BCTC năm).
        use_forecast_engine = False: mô hình cũ (dự phóng nội bộ) – chỉ giữ để đối chiếu trước/sau."""
        peers = peers or {}
        ftype = company.get("type", "nonfinancial")
        fin = ftype in FINANCIAL_TYPES
        res: Dict[str, Any] = {"available": False, "status": NOT_ENOUGH, "type": ftype, "financial": fin, "methods": [], "invalid": [],
                               "notes": [], "horizon_months": self.v["horizon_months"], "price": _num(price),
                               "price_date": str(pd.Timestamp(price_date).date()) if price_date is not None else None}
        if as_of is not None:
            wide, ratios, price_df = point_in_time(wide, ratios, price_df, pd.Timestamp(as_of))
            res["as_of"] = str(pd.Timestamp(as_of).date())
        wide, dq = sanitize_annual(wide)
        res["notes"].extend(dq)
        price = _num(price)
        if not price or price <= 0:
            res["notes"].append("Thiếu thị giá hợp lệ → không tính giá mục tiêu và upside.")
            return res
        if wide is None or wide.empty or not shares or shares <= 0:
            res["notes"].append("Thiếu BCTC năm hoặc số cổ phiếu lưu hành.")
            return res

        if self.v.get("use_forecast_engine", True):
            from core.dinh_gia import value_hybrid
            return value_hybrid(self, price=price, price_date=price_date, wide=wide, ratios=ratios, shares=shares,
                                company=company, beta=beta, peers=peers, price_df=price_df, risk_level=risk_level,
                                as_of=as_of, forecast=forecast, res=res, quarterly=quarterly, dividends=dividends,
                                share_factor=share_factor, dps_factor=dps_factor, basis_unknown=basis_unknown)
        res["model"] = "legacy"
        last_key = int(wide.index[-1])
        res["data_period"] = f"{last_key // 10}"
        res["data_date"] = f"31/12/{last_key // 10}"
        ref_date = pd.Timestamp(as_of) if as_of is not None else (pd.Timestamp(price_date) if price_date is not None else pd.Timestamp.now())
        months_old = (ref_date.year - last_key // 10) * 12 + ref_date.month - 12
        stale = months_old > self.v["stale_months"]
        if stale:
            res["notes"].append(f"BCTC năm gần nhất ({last_key // 10}) đã cũ ~{months_old} tháng → giảm độ tin cậy.")

        r_last = ratios.iloc[-1] if ratios is not None and not ratios.empty else pd.Series(dtype=float)
        ni_s = _col(wide, "net_income_parent")
        if ni_s.dropna().empty:
            ni_s = _col(wide, "net_income")
        rev_key = "total_operating_income" if fin and "total_operating_income" in wide.columns else "revenue"
        rev_s = _col(wide, rev_key)
        ni0, rev0 = _last(ni_s), _last(rev_s)
        eq_s = _col(wide, "equity") - _col(wide, "minority_interest").fillna(0)
        eq0 = _last(eq_s)
        payout_hist = ratios["dividend_payout"].dropna().tail(3) if ratios is not None and "dividend_payout" in ratios else pd.Series(dtype=float)
        payout = float(np.clip(payout_hist.mean() / 100, 0, 1)) if not payout_hist.empty else 0.3
        roe0 = _num(r_last.get("roe"))
        hist = historical_multiples(wide, shares, price_df)
        res["history"] = hist

        # ── giả định tăng trưởng gốc ──
        g_hist = (_cagr(ni_s) if fin else _cagr(rev_s)) or (_cagr(rev_s) if fin else _cagr(ni_s))
        g_sust = (roe0 / 100) * (1 - payout) if roe0 is not None else None
        parts = [(0.6, g_hist), (0.4, g_sust)]
        parts = [(w, x) for w, x in parts if x is not None]
        lo_g, hi_g = self.v["growth_bounds"]
        g_base = float(np.clip(sum(w * x for w, x in parts) / sum(w for w, _ in parts), lo_g, hi_g)) if parts else 0.0
        margins = (ni_s / rev_s).replace([np.inf, -np.inf], np.nan).dropna().tail(3)
        m_base = float(margins.mean()) if not margins.empty else None
        # Cổ tức tiền mặt/CP = cổ tức đã trả (LCTT) / số CP hiện tại (cùng cơ sở với giá đã điều chỉnh)
        dps_s = (_col(wide, "dividends_paid").abs() / shares).dropna().tail(3)
        dps = float(dps_s.iloc[-1]) if len(dps_s) and (dps_s > 0).sum() >= 2 else 0.0
        if dps < price * 0.003:          # < 0,3% thị giá: thường chỉ là cổ tức trả cho CĐ thiểu số ở công ty con
            dps = 0.0
        div_ok = dps > 0
        if not div_ok:
            res["notes"].append("Không đủ cơ sở dự phóng cổ tức tiền mặt (chưa trả đều ≥ 2/3 năm gần nhất) → tổng lợi nhuận kỳ vọng = upside giá.")
        res["assumptions"] = {
            "g_hist": g_hist, "g_sustainable": g_sust, "g_base": g_base, "net_margin_base": m_base, "payout": payout,
            "roe": roe0, "beta": beta, "ke": self.ke(beta), "dps_expected": dps, "shares": shares,
            "basis_growth": "LNST" if fin else "doanh thu",
            "risk_free": self.v["risk_free"], "equity_premium": self.v["equity_premium"],
            "beta_used": min(max(beta, self.v["beta_bounds"][0]), self.v["beta_bounds"][1]) if beta is not None and not math.isnan(beta) else 1.0,
        }

        sc_cfg = self.v["scenarios"]
        scen_rows: Dict[str, Dict[str, Any]] = {}
        for s in SCEN:
            p = sc_cfg[s]
            g = float(np.clip(g_base + p["growth_shift"], lo_g, hi_g))
            ke_s = self.ke(beta, p["ke_shift"])
            if fin:
                ni_f = ni0 * (1 + g) * p["margin_factor"] if ni0 is not None else None
                margin_s = None
            else:
                margin_s = m_base * p["margin_factor"] if m_base is not None else None
                ni_f = rev0 * (1 + g) * margin_s if rev0 is not None and margin_s is not None else None
            eps_f = ni_f / shares if ni_f is not None else None
            roe_s = (roe0 + p["roe_shift"]) if roe0 is not None else None
            scen_rows[s] = {"growth": g, "margin": margin_s, "ke": ke_s, "eps_fwd": eps_f, "roe": roe_s, "methods": {}}

            # P/E
            pe_hist = list(hist["pe"].values())
            refs_pe = [x for x in [_pct(pe_hist, 50), _num(peers.get("pe")) if (peers.get("n_pe") or peers.get("n") or 0) >= 3 else None] if x]
            if eps_f is not None and eps_f > 0 and refs_pe:
                pe_t = float(np.median(refs_pe))
                if len(pe_hist) >= 3 and p["multiple_pct"] != 50:
                    pe_t *= float(np.clip(_pct(pe_hist, p["multiple_pct"]) / _pct(pe_hist, 50), 0.7, 1.4))
                if risk_level in ("Cao", "Nghiêm trọng"):
                    pe_t *= 0.9
                if g < 0:
                    pe_t *= 0.9
                scen_rows[s]["methods"]["pe"] = {"target": eps_f * pe_t, "multiple": pe_t, "base": eps_f,
                                                 "base_label": "EPS dự phóng"}
            # P/B
            if eq0 is not None and eq0 > 0 and roe_s is not None:
                bvps = eq0 / shares
                bvps_f = bvps * (1 + (roe_s / 100) * (1 - payout))
                g_t = self.v["terminal_growth"][s]
                jpb = (roe_s / 100 - g_t) / (ke_s - g_t) if ke_s - g_t >= 0.02 and roe_s / 100 > g_t else None
                pb_hist = list(hist["pb"].values())
                h_pb = _pct(pb_hist, p["multiple_pct"]) if len(pb_hist) >= 3 else None
                refs_pb = [x for x in [h_pb, _num(peers.get("pb")) if (peers.get("n_pb") or peers.get("n") or 0) >= 3 else None, jpb] if x and x > 0]
                if refs_pb:
                    pb_t = float(np.median(refs_pb))
                    scen_rows[s]["methods"]["pb"] = {"target": bvps_f * pb_t, "multiple": pb_t, "base": bvps_f,
                                                     "base_label": "BVPS dự phóng", "justified_pb": jpb}
            if not fin:
                dcf = self._dcf(wide, shares, price, g, ke_s, self.v["terminal_growth"][s], dps)
                if dcf.get("valid"):
                    scen_rows[s]["methods"]["dcf"] = dcf
                    if s == "base":
                        res["notes"].extend(f"DCF: {n}" for n in dcf.get("bridge_notes") or []
                                            if "tạm coi bằng 0" not in n)
                elif s == "base":
                    res["invalid"].append(("DCF", dcf.get("reason")))
                ev = self._ev_ebitda(wide, shares, hist, g, p)
                if ev.get("valid"):
                    scen_rows[s]["methods"]["ev_ebitda"] = ev
                elif s == "base":
                    res["invalid"].append(("EV/EBITDA", ev.get("reason")))
        base_methods = scen_rows["base"]["methods"]
        # ── Dữ liệu thiếu bị tạm coi = 0: tổng hợp + đánh giá mức ảnh hưởng (so với vốn hóa thị trường) ──
        mcap = price * shares
        gaps: Dict[tuple, Dict[str, Any]] = {}
        for key, m in base_methods.items():
            for gp in m.get("gaps") or []:
                g0 = gaps.setdefault((gp["item"], gp["year"]), {**gp, "methods": []})
                g0["methods"].append({"dcf": "DCF", "ev_ebitda": "EV/EBITDA"}.get(key, key))
        if "pb" in base_methods and _num(wide.iloc[-1].get("minority_interest")) is None:
            b = net_debt_at(wide, wide.index[-1])
            mb = next((x.get("bound") for x in b.get("gaps", []) if x["item"] == "lợi ích CĐ thiểu số"), None)
            g0 = gaps.setdefault(("lợi ích CĐ thiểu số", int(wide.index[-1]) // 10),
                                 {"item": "lợi ích CĐ thiểu số", "year": int(wide.index[-1]) // 10, "treated_as": 0.0,
                                  "bound": mb, "direction": "giá trị vốn chủ có thể bị THỔI PHỒNG", "methods": []})
            g0["methods"].append("P/B (VCSH cổ đông mẹ)")
        res["data_gaps"] = []
        for gp in gaps.values():
            gp.update(gap_impact(gp.get("bound"), mcap))
            res["data_gaps"].append(gp)
            pct = f" ≈ {gp['impact_pct'] * 100:.1f}% vốn hóa" if gp.get("impact_pct") is not None else ""
            res["notes"].append(f"Thiếu số liệu {gp['item']} năm {gp['year']} → tạm coi = 0 trong "
                                f"{', '.join(gp['methods'])}; ảnh hưởng tối đa: {gp['impact']}{pct} – {gp['direction']}.")
        if any(gp["impact"] in ("cao", "không xác định") for gp in res["data_gaps"]):
            res["notes"].append("Có khoản thiếu số liệu với ảnh hưởng cao/không xác định → cần kiểm tra BCTC gốc "
                                "trước khi dùng giá mục tiêu.")
        if "pe" not in base_methods:
            res["invalid"].append(("P/E", "EPS dự phóng ≤ 0 hoặc không có P/E tham chiếu (lịch sử ≥ 3 năm / ngành ≥ 3 DN)"))
        if "pb" not in base_methods:
            res["invalid"].append(("P/B", "Thiếu VCSH dương/ROE hoặc không có P/B tham chiếu"))

        # ── loại kết quả bất thường ──
        lo_b, hi_b = self.v["sanity_band"]
        for k, m in list(base_methods.items()):
            ratio = m["target"] / price
            if not (lo_b <= ratio <= hi_b) or m["target"] <= 0:
                res["invalid"].append((k.upper(), f"Kết quả {m['target']:,.0f} bất thường so với thị giá ({ratio:.2f} lần) – loại"))
                for s in SCEN:
                    scen_rows[s]["methods"].pop(k, None)
        weights_cfg = self.v["method_weights"]["financial" if fin else "nonfinancial"]
        valid = [k for k in weights_cfg if k in scen_rows["base"]["methods"]]
        if not valid:
            res["notes"].append("Không có phương pháp định giá hợp lệ.")
            res["scenarios"] = scen_rows
            return res
        tw = sum(weights_cfg[k] for k in valid)
        weights = {k: weights_cfg[k] / tw for k in valid}

        names = {"pe": "P/E dự phóng", "pb": "P/B dự phóng", "dcf": "DCF (FCFF)", "ev_ebitda": "EV/EBITDA"}
        for s in SCEN:
            ms = {k: v for k, v in scen_rows[s]["methods"].items() if k in weights}
            sw = sum(weights[k] for k in ms)
            scen_rows[s]["target"] = sum(ms[k]["target"] * weights[k] for k in ms) / sw if sw else None
            scen_rows[s]["upside"] = (scen_rows[s]["target"] / price - 1) * 100 if scen_rows[s]["target"] else None
        target = scen_rows["base"]["target"]
        methods_out = []
        for k in valid:
            m = scen_rows["base"]["methods"][k]
            methods_out.append({"key": k, "name": names[k], "multiple": m.get("multiple"), "base": m.get("base"),
                                "base_label": m.get("base_label", ""), "fair": m["target"], "weight": weights[k],
                                "upside": (m["target"] / price - 1) * 100, "source": self._source(k, m, hist, peers),
                                "detail": {kk: vv for kk, vv in m.items() if kk not in ("target",)}})
        spread = max(m["fair"] for m in methods_out) / min(m["fair"] for m in methods_out)
        tv_flag = any(m["key"] == "dcf" and m["detail"].get("tv_share", 0) > self.v["dcf_max_tv_share"] for m in methods_out)
        n = len(methods_out)
        conf = "Cao" if n >= 3 and spread <= 1.6 else "Trung bình" if n >= 2 and spread <= 2.2 else "Thấp"
        if stale or tv_flag:
            conf = {"Cao": "Trung bình", "Trung bình": "Thấp"}.get(conf, conf)
        if tv_flag:
            res["notes"].append("DCF: giá trị cuối kỳ chiếm > {:.0f}% EV → nhạy với giả định dài hạn.".format(self.v["dcf_max_tv_share"] * 100))
        if spread > 2.2:
            res["notes"].append(f"Các phương pháp chênh nhau lớn (cao/thấp = {spread:.1f} lần).")
        upside = (target / price - 1) * 100
        exp_ret = ((target + dps - price) / price) * 100
        intrinsic = target / (1 + self.ke(beta))
        res.update(
            available=conf != "Thấp", status="OK" if conf != "Thấp" else NOT_ENOUGH, confidence=conf,
            target_12m=target, fair_value=target, intrinsic_today=intrinsic, upside=upside,
            expected_dividend=dps, dividends_included=div_ok, expected_return=exp_ret,
            dividend_yield=dps / price * 100, methods=methods_out, weights=weights, scenarios=scen_rows,
            group_weights={"pe": sum(w for k, w in weights.items() if k in ("pe",)),
                           "pb": sum(w for k, w in weights.items() if k in ("pb",))},
            financial=fin, sensitivity=self._sensitivity(target),
        )
        if conf == "Thấp":
            res["notes"].append("Độ tin cậy định giá thấp (ít phương pháp hợp lệ, phân tán lớn hoặc dữ liệu cũ) → "
                                f"trạng thái: {NOT_ENOUGH}. Các con số chỉ để tham khảo.")
        return res

    # ── DCF-FCFF ──
    def _dcf(self, wide, shares, price, g1, ke, g_t, dps) -> Dict[str, Any]:
        t = self.v["tax_rate"]
        need = {"cfo", "capex"}
        if not need <= set(wide.columns):
            return {"valid": False, "reason": "Thiếu CFO/Capex"}
        df = wide[["cfo", "capex"]].dropna().tail(3)
        if len(df) < 3:
            return {"valid": False, "reason": "Cần ≥ 3 năm CFO và Capex"}
        k = wide.index[-1]                     # kỳ gốc = năm BCTC gần nhất (cùng kỳ với P/E, P/B, EV/EBITDA)
        y = int(k) // 10
        gaps: List[Dict[str, Any]] = []
        notes: List[str] = []
        int_raw = _col(wide, "interest_expense").abs().reindex(df.index)
        miss_int = [int(i) // 10 for i in df.index if pd.isna(int_raw.get(i))]
        if miss_int:                            # thiếu lãi vay → FCFF bị đánh giá thấp phần lãi vay sau thuế
            fe = _col(wide, "financial_expense").abs().reindex(df.index)
            fe_miss = fe[int_raw.isna()].dropna()
            bound = float(fe_miss.mean()) if not fe_miss.empty else None
            gaps.append({"item": "chi phí lãi vay (FCFF)", "year": miss_int[-1], "years": miss_int, "treated_as": 0.0,
                         "bound": bound * (1 - t) if bound is not None else None,
                         "direction": "FCFF và giá trị DCF có thể bị ĐÁNH GIÁ THẤP"})
        interest = int_raw.fillna(0)
        fcff_hist = df["cfo"] + interest * (1 - t) - df["capex"].abs()
        fcff0 = float(fcff_hist.mean())
        if fcff0 <= 0:
            return {"valid": False, "reason": f"FCFF bình quân 3 năm âm ({fcff0 / 1e9:,.0f} tỷ)"}
        if df.index[-1] != k:
            notes.append(f"FCFF bình quân dùng các năm {', '.join(str(int(i) // 10) for i in df.index)} "
                         f"(năm gốc {y} thiếu CFO/Capex)")
        # Cầu nối EV → vốn chủ: TẤT CẢ lấy tại kỳ gốc k (không dùng _last() riêng từng cột → không trộn kỳ)
        bridge = net_debt_at(wide, k)
        if not bridge["ok"]:
            return {"valid": False, "reason": bridge["reason"]}
        debt, cash, mi = bridge["debt"], bridge["cash"], bridge["minority"]
        notes += bridge["notes"]
        gaps += bridge["gaps"]
        # Chi phí nợ = lãi vay năm gốc / nợ vay bình quân (năm gốc & năm trước) – cùng kỳ, không ghép năm khác
        int_k = _num(_col(wide, "interest_expense").abs().get(k))
        prev = wide.index[-2] if len(wide.index) >= 2 else None
        debt_prev = net_debt_at(wide, prev) if prev is not None else {"ok": False}
        debt_avg = (debt + debt_prev["debt"]) / 2 if debt_prev.get("ok") and not any(
            g["item"] == "vay nợ" for g in debt_prev["gaps"]) else debt
        if int_k is not None and debt_avg > 0:
            kd = float(np.clip(int_k / debt_avg, *self.v["kd_bounds"]))
        else:
            kd = self.v["kd_bounds"][0]
            if debt > 0:
                notes.append(f"Năm {y} thiếu chi phí lãi vay → chi phí nợ dùng cận dưới {kd * 100:.1f}% (giả định)")
        e = price * shares
        wacc = e / (e + debt) * ke + debt / (e + debt) * kd * (1 - t)
        if wacc - g_t < self.v["dcf_min_spread"]:
            return {"valid": False, "reason": f"WACC {wacc * 100:.1f}% − g {g_t * 100:.1f}% quá nhỏ"}
        years = self.v["dcf_years"]
        fcff, pv = fcff0, 0.0
        flows = []
        for i in range(1, years + 1):
            gi = g1 + (g_t - g1) * (i - 1) / max(years - 1, 1)
            fcff *= (1 + gi)
            pv += fcff / (1 + wacc) ** i
            flows.append(fcff)
        tv = fcff * (1 + g_t) / (wacc - g_t)
        pv_tv = tv / (1 + wacc) ** years
        ev = pv + pv_tv
        equity = ev - debt + cash - mi
        if equity <= 0:
            return {"valid": False, "reason": "Giá trị vốn chủ ước tính ≤ 0"}
        intrinsic = equity / shares
        target = intrinsic * (1 + ke) - dps
        return {"valid": True, "target": target, "intrinsic": intrinsic, "multiple": None, "base": fcff0 / shares,
                "base_label": "FCFF bình quân 3 năm/CP", "fcff_avg": fcff0, "wacc": wacc, "kd": kd, "g_terminal": g_t, "ev": ev,
                "tv_share": pv_tv / ev, "net_debt": debt - cash, "flows": flows, "base_year": y,
                "bridge_notes": notes, "gaps": gaps}

    # ── EV/EBITDA ──
    def _ev_ebitda(self, wide, shares, hist, g, p) -> Dict[str, Any]:
        """EV/EBITDA trên MỘT kỳ gốc duy nhất = năm BCTC gần nhất của bảng đầu vào (cùng năm gốc với P/E, P/B).
        EBITDA, nợ vay, tiền & ĐTTC ngắn hạn, lợi ích CĐ thiểu số đều lấy tại kỳ đó; thiếu → loại phương pháp
        (không lấy EBITDA/nợ vay của năm cũ hơn ghép với số dư năm mới)."""
        k = wide.index[-1]
        y = int(k) // 10
        ebitda = _num(ebit_ebitda(wide)[1].get(k))
        if ebitda is None:
            return {"valid": False, "reason": f"Năm {y} thiếu LNTT/lãi vay/khấu hao để tính EBITDA"}
        if ebitda <= 0:
            return {"valid": False, "reason": "EBITDA ≤ 0"}
        bridge = net_debt_at(wide, k)
        if not bridge["ok"]:
            return {"valid": False, "reason": bridge["reason"]}
        vals = list(hist["ev_ebitda"].values())
        if len(vals) < 3:
            return {"valid": False, "reason": "Cần ≥ 3 năm EV/EBITDA lịch sử"}
        mult = _pct(vals, p["multiple_pct"])
        ebitda_f = ebitda * (1 + g) * p["margin_factor"]
        debt, cash, mi = bridge["debt"], bridge["cash"], bridge["minority"]
        gaps = list(bridge["gaps"])
        if _num(wide.loc[k].get("interest_expense")) is None:
            # EBIT = LNTT + lãi vay; thiếu lãi vay → EBITDA thiếu phần lãi vay. Cận trên = chi phí tài chính.
            fe = _num(wide.loc[k].get("financial_expense"))
            gaps.append({"item": "chi phí lãi vay (EBITDA)", "year": y, "treated_as": 0.0,
                         "bound": abs(fe) * mult * (1 + g) * p["margin_factor"] if fe is not None else None,
                         "direction": "EBITDA và giá trị EV/EBITDA có thể bị ĐÁNH GIÁ THẤP"})
        equity = ebitda_f * mult - (debt - cash) - mi
        if equity <= 0:
            return {"valid": False, "reason": "Giá trị vốn chủ ≤ 0"}
        return {"valid": True, "target": equity / shares, "multiple": mult, "base": ebitda_f / shares,
                "base_label": "EBITDA dự phóng/CP", "ebitda_fwd": ebitda_f, "net_debt": debt - cash,
                "bridge_per_share": (-(debt - cash) - mi) / shares, "base_year": y, "bridge_notes": bridge["notes"],
                "gaps": gaps}

    @staticmethod
    def _source(k, m, hist, peers) -> str:
        def hist_txt(key, fmt):
            v = hist.get(key) or {}
            return (f"{key.upper().replace('_', '/')} lịch sử " + ", ".join(f"{y}: {x:{fmt}}x" for y, x in v.items())
                    + f" (trung vị {np.median(list(v.values())):{fmt}}x)") if len(v) >= 3 else None
        if k == "pe":
            refs = [hist_txt("pe", ".1f"), f"P/E ngành {peers['pe']:.1f}x ({peers.get('group')})" if peers.get("pe") else None]
            return "P/E mục tiêu = trung vị của: " + "; ".join(r for r in refs if r) + f" → {m['multiple']:.1f}x"
        if k == "pb":
            j = m.get("justified_pb")
            refs = [hist_txt("pb", ".2f"), f"P/B ngành {peers['pb']:.2f}x" if peers.get("pb") else None,
                    f"P/B hợp lý (ROE − g)/(Ke − g) = {j:.2f}x" if j else None]
            return "P/B mục tiêu = trung vị của: " + "; ".join(r for r in refs if r) + f" → {m['multiple']:.2f}x"
        if k == "dcf":
            return (f"WACC {m['wacc'] * 100:.1f}% (Kd {m['kd'] * 100:.1f}%), g dài hạn {m['g_terminal'] * 100:.1f}%, "
                    f"giá trị cuối kỳ {m['tv_share'] * 100:.0f}% EV; giá mục tiêu = nội tại {m['intrinsic']:,.0f} × (1 + Ke) − cổ tức")
        if k == "ev_ebitda":
            br = m.get("bridge_per_share")
            return (hist_txt("ev_ebitda", ".1f") or "") + (
                f"; giá trị/CP = EBITDA/CP × hệ số {'+' if br >= 0 else '−'} {abs(br):,.0f} (tiền ròng − lợi ích CĐ thiểu số)/CP"
                if br is not None else "")
        return ""

    @staticmethod
    def _sensitivity(target: float) -> List[Dict[str, Any]]:
        rows = []
        for mult_chg in (-0.3, -0.15, 0.0, 0.15, 0.3):
            rows.append({"mult_chg": mult_chg, **{b: target * (1 + mult_chg) * (1 + b) for b in (-0.1, 0.0, 0.1)}})
        return rows


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/hybrid_valuation.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Hybrid Valuation (bước 7) – định giá 12 tháng dùng dự báo của Forecast Engine (core/du_phong.py).

Thay thế phần dự phóng nội bộ cũ của ValuationEngine12M (tăng trưởng CAGR × biên ròng bình quân). Trả về CÙNG cấu
trúc kết quả để Recommendation Engine, Risk, giao diện và PDF dùng tiếp (hệ thống khuyến nghị không đổi).

Quy ước thời điểm (T = ngày định giá; T+12 = ngày mục tiêu)
  • P/E Forward : giá mục tiêu = P/E tham chiếu × EPS 12 tháng tới (NTM, cửa sổ T → T+12). P/E tham chiếu là P/E
                  TRAILING lịch sử (giá cuối năm / LNST năm đó) → tại T+12, EPS trailing chính là EPS NTM hôm nay.
  • P/B–ROE     : giá mục tiêu = P/B tham chiếu × BVPS tại T+12 (bvps_fwd). P/B tham chiếu = trung vị của P/B lịch sử
                  (phân vị theo kịch bản), P/B ngành (≥ 3 DN) và P/B hợp lý (ROE − g)/(Ke − g) với ROE bền vững = trung
                  vị ROE dự báo năm 1–3.
  • EV/EBITDA   : EV tại T+12 = EV/EBITDA lịch sử × EBITDA NTM; giá trị vốn chủ = EV − nợ vay ròng − CĐ thiểu số
                  (số dư tại kỳ BCTC năm gần nhất, giả định không đổi đến T+12 – Forecast Engine chưa dự báo nợ vay).
  • DCF (FCFF)  : FCFF từng năm của Forecast Engine, mỗi năm kết thúc tại fcff_period_ends; chiết khấu về T theo WACC
                  với số năm thực tế từ T (dòng tiền năm đầu chỉ tính phần còn lại sau T). Giá trị cuối kỳ Gordon trên
                  FCFF năm cuối. Giá trị hợp lý hôm nay = vốn chủ / số CP; giá mục tiêu = hôm nay × (1 + Ke) − cổ tức.
  • Mọi phương pháp: giá trị hợp lý HÔM NAY = (giá mục tiêu + cổ tức 12T) / (1 + Ke).

Kiểm soát trước khi tổng hợp
  1. Thiếu dữ liệu nghiêm trọng (khoản bị coi = 0 có ảnh hưởng 'cao'/'không xác định', hoặc khoảng trống dữ liệu
     mức 'cao' của Forecast Engine liên quan phương pháp) ⇒ LOẠI phương pháp, không thay bằng 0.
  2. Dự báo không đủ tin cậy: sai số trung vị LNST 1 năm (backtest chính mã) > ngưỡng ⇒ loại P/E Forward.
  3. Kết quả ngoài [0,25×; 4×] thị giá ⇒ loại; ≥ 3 phương pháp: lệch ngoài [½×; 2×] trung vị các phương pháp ⇒ loại.
  4. Trọng số theo hồ sơ ngành (valuation.method_profiles), chuẩn hóa lại trên các phương pháp còn lại.
"""


import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

METHOD_NAMES = {"pe": "P/E Forward", "pb": "P/B–ROE", "dcf": "DCF (FCFF)", "ev_ebitda": "EV/EBITDA",
                "ri": "Thu nhập thặng dư (RI)", "ddm": "Chiết khấu cổ tức 2 giai đoạn"}
SHORT = {"pe": "P/E", "pb": "P/B", "dcf": "DCF", "ev_ebitda": "EV/EBITDA", "ri": "RI", "ddm": "DDM"}
SCEN = ("bear", "base", "bull")
# Khoảng trống dữ liệu của Forecast Engine → phương pháp bị ảnh hưởng
FORECAST_GAP_METHODS = {"capex": ("dcf",), "vốn lưu động": ("dcf",),
                        "tăng trưởng": ("pe", "ev_ebitda", "dcf", "pb", "ri", "ddm"),
                        "chi phí lãi vay": ("pe", "dcf"), "cổ tức tiền mặt": ("pb", "ri", "ddm"),
                        "LNST cổ đông mẹ": ("pe", "pb", "ri", "ddm"), "thuế suất": ("pe", "dcf"),
                        "EBIT cốt lõi": ("dcf", "ev_ebitda")}
CONF_ORDER = ["Cao", "Trung bình", "Thấp"]


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


# Ngành dịch vụ/vận tải/tiêu dùng: vốn lưu động lớn (phải thu, trả trước…) KHÔNG có nghĩa là doanh nghiệp dự án/BĐS
# (15/10/2026: VJC – hàng không – từng bị định giá như BĐS).
NON_PROJECT_KEYWORDS = ("travel", "leisure", "hàng không", "airline", "aviation", "vận tải", "transport", "logistics",
                        "food", "beverage", "thực phẩm", "đồ uống", "retail", "bán lẻ", "media", "truyền thông")


def select_profile(company: Dict[str, str], forecast: Optional[Dict[str, Any]], profiles: Dict[str, Any]) -> Tuple[str, str]:
    """(khóa hồ sơ, lý do chọn). Ưu tiên loại hình (ngân hàng/CTCK/bảo hiểm), rồi ngành theo phân loại, rồi đặc tính dữ
    liệu đã công bố (vốn lưu động lớn ⇒ như BĐS/dự án; biên biến động mạnh ⇒ chu kỳ)."""
    t, sec = company.get("type", "nonfinancial"), company.get("sector", "default")
    fc = forecast or {}
    if t in ("bank", "securities", "insurance"):
        return t, f"Loại hình doanh nghiệp: {t}"
    if sec == "industrial_park" and "industrial_park" in profiles:
        return "industrial_park", "BĐS khu công nghiệp (danh sách mã INDUSTRIAL_PARK_TICKERS trong cấu hình)"
    if sec == "real_estate":
        return "real_estate", "Ngành bất động sản (theo phân loại ngành)"
    txt = str(company.get("industry_text") or "")
    service = any(k in txt for k in NON_PROJECT_KEYWORDS)
    if fc.get("scenario_group") == "nwc_heavy" and not service:
        nwc = ((fc.get("drivers") or {}).get("nwc_pct_revenue") or {}).get("value")
        return "real_estate", f"Vốn lưu động lớn ({nwc:.0%} doanh thu) – đặc thù dự án/BĐS (theo dữ liệu BCTC)"
    if sec == "technology":
        return "technology", "Ngành công nghệ (theo phân loại ngành)"
    if sec == "utilities":
        return "utilities", "Ngành tiện ích/năng lượng (theo phân loại ngành)"
    if sec == "materials":
        return "cyclical_manufacturing", "Ngành vật liệu/sản xuất (theo phân loại ngành)"
    if fc.get("cyclical"):
        return "cyclical_manufacturing", "Biên lợi nhuận biến động mạnh trong lịch sử (doanh nghiệp chu kỳ – theo dữ liệu BCTC)"
    return "default", "Phi tài chính, không thuộc nhóm đặc thù"


def risk_free_status(v: Dict[str, Any], ref_date) -> Optional[str]:
    """Bước 10: cảnh báo khi lãi suất phi rủi ro (Rf) chưa ghi ngày/nguồn hoặc cũ hơn risk_free_max_age_days so với ngày
    định giá. None = số liệu còn mới."""
    rf, as_of, src = v.get("risk_free"), v.get("risk_free_as_of"), v.get("risk_free_source") or ""
    max_age = int(v.get("risk_free_max_age_days") or 92)
    if not as_of:
        return (f"Lãi suất phi rủi ro Rf = {rf:.2%} là giả định cấu hình, CHƯA ghi ngày cập nhật/nguồn → cần cập nhật theo lợi "
                "suất TPCP 10 năm (core/cau_hinh.py: risk_free, risk_free_as_of, risk_free_source).")
    try:
        age = (pd.Timestamp(ref_date).normalize() - pd.Timestamp(as_of).normalize()).days
    except (TypeError, ValueError):
        return f"Ngày cập nhật Rf không hợp lệ ('{as_of}') → kiểm tra lại cấu hình."
    if age < -7:
        return (f"Lãi suất phi rủi ro Rf = {rf:.2%} là số liệu ngày {pd.Timestamp(as_of):%d/%m/%Y}, SAU ngày định giá "
                f"{pd.Timestamp(ref_date):%d/%m/%Y} (chưa có chuỗi Rf lịch sử) → kết quả quá khứ chỉ mang tính tham khảo.")
    if age > max_age:
        return (f"Lãi suất phi rủi ro Rf = {rf:.2%} cập nhật ngày {pd.Timestamp(as_of):%d/%m/%Y}"
                + (f" ({src})" if src else "") + f", đã cũ {age} ngày (> {max_age}) → nên cập nhật lợi suất TPCP 10 năm.")
    return None


def price_series_check(price_df: Optional[pd.DataFrame], limit: float = 0.16) -> Dict[str, Any]:
    """Phát hiện giá có thể CHƯA điều chỉnh: biến động một phiên vượt biên độ tối đa của sàn VN (HOSE ±7%, HNX ±10%,
    UPCoM ±15%) gần như chỉ xảy ra khi giá bị cắt theo quyền (chia tách/thưởng) mà chuỗi không điều chỉnh.
    Chỉ kiểm khi dữ liệu là theo phiên (khoảng cách trung vị ≤ 5 ngày)."""
    if price_df is None or price_df.empty or "close" not in price_df.columns:
        return {}
    ts = pd.to_datetime(price_df["timestamp"] if "timestamp" in price_df.columns else price_df.index)
    s = pd.Series(pd.to_numeric(price_df["close"], errors="coerce").to_numpy(), index=ts).dropna().sort_index()
    if len(s) < 20 or pd.Series(s.index).diff().dt.days.median() > 5:
        return {"checked": False}
    r = s.pct_change().dropna()
    bad = r[r.abs() > limit]
    return {"checked": True, "suspect_jumps": int(len(bad)), "max_move": float(bad.loc[bad.abs().idxmax()]) if len(bad) else 0.0,
            "dates": [str(d.date()) for d in bad.index[:5]]}


def _years_from(t: pd.Timestamp, end: str) -> float:
    return (pd.Timestamp(end) - t).days / 365.25


def value_hybrid(engine, **kw) -> Dict[str, Any]:
    """Đặt tham số dùng chung cho các hàm phương pháp (trọng số độ gần của bội số, ROE dài hạn) trong đúng lượt định
    giá này rồi trả lại trạng thái cũ – gọi trực tiếp từng hàm phương pháp (kiểm thử) không bị ảnh hưởng."""
    v = engine.v
    old = (_DECAY[0], _FADE[0])
    _DECAY[0], _FADE[0] = v.get("multiple_recency_decay"), v.get("roe_fade_spread")
    try:
        return _value_hybrid(engine, **kw)
    finally:
        _DECAY[0], _FADE[0] = old


def _value_hybrid(engine, *, price: float, price_date, wide: pd.DataFrame, ratios, shares: float,
                 company: Dict[str, str], beta, peers: Dict[str, Any], price_df, risk_level, as_of,
                 forecast: Optional[Dict[str, Any]], res: Dict[str, Any],
                 quarterly: Optional[pd.DataFrame] = None, dividends: Optional[pd.DataFrame] = None,
                 share_factor: float = 1.0, dps_factor: float = 1.0, basis_unknown: bool = False) -> Dict[str, Any]:
    from core.dinh_gia import NOT_ENOUGH, SCEN_LABEL, _col, gap_impact, historical_multiples, net_debt_at, _pct
    v = engine.v
    fin = res["financial"]
    T = pd.Timestamp(as_of if as_of is not None else (price_date if price_date is not None else pd.Timestamp.now())).normalize()
    res["model"] = "hybrid"
    res["valuation_date"] = str(T.date())
    res["target_date"] = str((T + pd.DateOffset(months=12)).date())

    # ── Forecast Engine ──
    if forecast is None:
        # Cùng quy trình với StockService.forecast_analysis: dự báo + kiểm định sai số 1 năm của chính mã (backtest
        # chỉ trên BCTC đã công bố trước T) – kết quả kiểm định dùng cho loại P/E và độ tin cậy.
        from core.du_phong import FinancialForecaster, backtest_forecast
        forecast = FinancialForecaster(engine.cfg).forecast(annual=wide, quarterly=quarterly, shares=shares,
                                                            company=company, as_of=T)
        if forecast.get("available"):
            try:
                bt = backtest_forecast(wide, shares, company, config=engine.cfg)
                forecast["backtest"] = {"summary": bt["summary"]}
            except Exception:                                  # kiểm định lỗi → coi như chưa kiểm định
                pass
    res["forecast_summary"] = _forecast_summary(forecast)
    if not forecast.get("available"):
        res["notes"].append("Forecast Engine không đủ dữ liệu để dự báo ("
                            + str(forecast.get("reason") or "không rõ lý do") + ") → không tính giá mục tiêu.")
        return res

    last_key = int(wide.index[-1])
    res["data_period"] = f"{last_key // 10}"
    res["data_date"] = f"31/12/{last_key // 10}"
    months_old = (T.year - last_key // 10) * 12 + T.month - 12
    stale = months_old > v["stale_months"]
    if stale:
        res["notes"].append(f"BCTC năm gần nhất ({last_key // 10}) đã cũ ~{months_old} tháng → giảm độ tin cậy.")

    # ── hồ sơ phương pháp theo ngành ──
    profiles = v["method_profiles"]
    pkey, why = select_profile(company, forecast, profiles)
    prof = profiles[pkey]
    res["profile"] = {"key": pkey, "label": prof.get("label", pkey), "reason": why,
                      "rationale": prof.get("rationale", ""), "weights_config": dict(prof["weights"]),
                      "excluded_by_profile": dict(prof.get("excluded") or {})}
    # Phương pháp KHÔNG ÁP DỤNG theo ngành (khác với 'invalid' = áp dụng được nhưng bị loại vì dữ liệu/bất thường)
    res["not_applicable"] = [(SHORT[k], f"Không áp dụng cho hồ sơ '{prof.get('label', pkey)}': {r}")
                             for k, r in (prof.get("excluded") or {}).items()]
    wcfg = dict(prof["weights"])          # có thể bớt phương pháp 'không áp dụng' theo dữ liệu (vd DDM khi không chia cổ tức)
    conf_caps: List[Tuple[str, str]] = []  # (mức tối đa, lý do)
    if prof.get("max_confidence"):
        conf_caps.append((prof["max_confidence"], f"hồ sơ '{prof.get('label', pkey)}' thiếu phương pháp chuẩn của ngành"))

    # ── dữ liệu chung ──
    dps = _dividend(wide, shares, price, res, dividends,
                    pd.Timestamp(as_of) if as_of is not None else (pd.Timestamp(price_date) if price_date is not None else None), dps_factor=dps_factor)
    hist = historical_multiples(wide, shares, price_df, core=True)
    res["history"] = hist
    pq = price_series_check(price_df)
    if pq.get("suspect_jumps"):
        res["data_quality"] = pq
        res["notes"].append(f"Chuỗi giá có {pq['suspect_jumps']} phiên biến động vượt biên độ tối đa ±15% (lớn nhất "
                            f"{pq['max_move']:+.0%} ngày {pq['dates'][0]}) – có thể là giá CHƯA điều chỉnh theo chia tách/"
                            "thưởng cổ phiếu → bội số lịch sử (P/E, P/B, EV/EBITDA) có thể sai; cần kiểm tra nguồn giá.")
    rf_note = risk_free_status(v, T)
    if rf_note:
        res["notes"].append(rf_note)
    res["risk_free_status"] = rf_note
    bridge = _select_bridge(wide, quarterly, T, res)
    cyc = _cycle_norm(engine, wide, company, pkey, forecast) if pkey == "cyclical_manufacturing" else None
    if cyc is not None:
        res["cycle_normalization"] = cyc
        res["notes"].append(cyc["note"])
        if cyc.get("cap"):
            conf_caps.append((cyc["cap"], cyc["cap_reason"]))
    asum_base = forecast["drivers"]
    res["assumptions"] = {
        "beta": beta, "ke": engine.ke(beta), "risk_free": v["risk_free"], "equity_premium": v["equity_premium"],
        "beta_used": (min(max(engine.adj_beta(beta), v["beta_bounds"][0]), v["beta_bounds"][1])
                      if beta is not None and not math.isnan(beta) else 1.0),
        "beta_adjusted": bool(v.get("beta_blume")),
        "dps_expected": dps, "shares": shares, "forecast_model": forecast.get("model"),
        "forecast_base": (forecast.get("base") or {}).get("label"),
        "g_base": (asum_base.get("growth") or {}).get("value"),
        "basis_growth": (asum_base.get("growth") or {}).get("basis"),
        "profile": pkey,
    }

    # ── loại trừ do dữ liệu/dự báo ──
    blocked: Dict[str, str] = {}
    for gp in forecast.get("data_gaps") or []:
        if gp.get("impact") == "cao":
            for key, meths in FORECAST_GAP_METHODS.items():
                if key in gp["item"]:
                    for m in meths:
                        blocked.setdefault(m, f"Dự báo thiếu dữ liệu nghiêm trọng: {gp['item']} ({gp['treatment']})")
    scope = forecast.get("scope_change") or {}
    if scope.get("active"):
        why_sc = (f"Đổi phạm vi hợp nhất từ {scope.get('since')} ({scope.get('quarters_new')}/4 quý theo cơ sở mới): "
                  "doanh thu/EBITDA/FCFF dự báo và bội số lịch sử theo cơ sở cũ, bảng cân đối theo cơ sở mới → tính trùng "
                  "giá trị khoản đầu tư vào công ty liên kết")
        for m in ("ev_ebitda", "dcf"):
            blocked.setdefault(m, why_sc)
        res["scope_change"] = scope
        res["notes"].append(scope["text"])
    bt = (forecast.get("backtest") or {}).get("summary", {}).get("net_income_parent")
    if bt and bt.get("n", 0) >= v["pe_min_backtest_years"] and bt.get("median_ape", 0) > v["pe_max_forecast_ape"]:
        blocked.setdefault("pe", f"Dự báo LNST không đủ tin cậy: sai số trung vị 1 năm của chính mã {bt['median_ape']:.0%} "
                                 f"({bt['n']} năm) > {v['pe_max_forecast_ape']:.0%}")
    elif not bt:
        res["notes"].append("Chưa có kiểm định sai số dự báo của chính mã (backtest) → không đánh giá được độ tin cậy "
                            "dự báo LNST cho P/E Forward.")

    # ── Bội số HIỆN TẠI của thị trường (trên dự phóng cơ sở) – trần bội số cho kịch bản Thận trọng ──
    # Bear dùng bội số phân vị 25 LỊCH SỬ; khi thị trường đang định giá cổ phiếu thấp hơn hẳn mức đó (vd FPT P/E dự phóng ~9x
    # so với P25 lịch sử ~15x), Bear vẫn ra gần bằng thị giá dù giá vừa giảm 30%. Kịch bản thận trọng hợp lý = "thị trường
    # tiếp tục định giá bi quan như hiện nay" → bội số Bear ≤ bội số hiện tại.
    bear_caps: Dict[str, float] = {}
    if v.get("bear_cap_current_multiple", True):
        vb = (forecast.get("valuation_inputs") or {}).get("base") or {}
        e0, b0, eb0 = _num(vb.get("eps_fwd")), _num(vb.get("bvps_fwd")), _num(vb.get("ebitda_core_fwd"))
        if e0 and e0 > 0:
            bear_caps["pe"] = price / e0
        if b0 and b0 > 0:
            bear_caps["pb"] = price / b0
        if eb0 and eb0 > 0 and bridge.get("ok"):
            debt_, cash_, lti_, mi_ = _bridge_parts(bridge)
            ev_now = price * shares + debt_ - cash_ - lti_ + mi_
            if ev_now > 0:
                bear_caps["ev_ebitda"] = ev_now / eb0
        if bear_caps:
            res["bear_caps"] = bear_caps

    # ── tính từng phương pháp, từng kịch bản ──
    sc_cfg = v["scenarios"]
    scen_rows: Dict[str, Dict[str, Any]] = {}
    for s in SCEN:
        p = sc_cfg[s]
        vi = (forecast.get("valuation_inputs") or {}).get(s) or {}
        ke_s = engine.ke(beta, p["ke_shift"])
        g_t = v["terminal_growth"][s]
        y1 = ((forecast["scenarios"].get(s) or {}).get("years") or [{}])[0]
        row = {"ke": ke_s, "eps_fwd": vi.get("eps_fwd"), "roe": vi.get("roe_fwd"), "bvps_fwd": vi.get("bvps_fwd"),
               "growth": y1.get("growth"), "methods": {}, "failed": {}}
        fsh = engine.cfg["forecast"]["scenarios"][s]["margin_shift"]
        bc = bear_caps if p["multiple_pct"] < 50 else {}
        cands = {
            "pe": lambda: _pe(vi, hist, peers, p, risk_level, y1, ke_s, dps, cyc, fsh, shares, v.get("pe_peer_cap"),
                              bear_cap=bc.get("pe"), abs_cap=(prof.get("pe_abs_cap") or v.get("pe_abs_cap"))),
            "pb": lambda: _pb(vi, forecast, s, hist, peers, p, ke_s, g_t, dps, cyc, bear_cap=bc.get("pb")),
            "ev_ebitda": lambda: _ev(vi, hist, p, bridge, shares, ke_s, dps, cyc, fsh, bear_cap=bc.get("ev_ebitda")),
            "dcf": lambda: _dcf(engine, vi, wide, bridge, shares, price, ke_s, g_t, dps, T),
            "ri": lambda: _ri(vi, forecast, s, shares, ke_s, g_t, dps, T, engine),
            "ddm": lambda: _ddm(vi, forecast, wide, shares, ke_s, g_t, dps, T, engine),
        }
        for k, fn in cands.items():
            if k not in wcfg or k in blocked:
                continue
            r = fn()
            if r.get("valid"):
                row["methods"][k] = r
            elif r.get("not_applicable"):
                row.setdefault("na", {})[k] = r.get("reason")
            else:
                row["failed"][k] = r.get("reason")
        scen_rows[s] = row
    # bảng so sánh các phương pháp TRƯỚC kiểm tra bất thường (để thấy mức chênh)
    res["comparison"] = [{"key": k, "name": METHOD_NAMES[k], "target": m["target"], "fair_today": m["fair_today"],
                          "vs_price": m["target"] / price - 1} for k, m in scen_rows["base"]["methods"].items()]
    for k, reason in blocked.items():
        if k in prof["weights"]:
            res["invalid"].append((SHORT[k], reason))
    base_methods = scen_rows["base"]["methods"]
    for k, reason in scen_rows["base"]["failed"].items():
        res["invalid"].append((SHORT[k], reason))
    for k, reason in (scen_rows["base"].get("na") or {}).items():       # không áp dụng theo dữ liệu → bỏ khỏi trọng số
        res["not_applicable"].append((SHORT[k], reason))
        wcfg.pop(k, None)
        for s in SCEN:
            scen_rows[s]["methods"].pop(k, None)

    # ── khoản bị coi = 0 trong cầu nối EV → vốn chủ: đánh giá ảnh hưởng; nghiêm trọng ⇒ loại phương pháp EV ──
    mcap = price * shares
    res["data_gaps"] = []
    ev_methods = [k for k in ("ev_ebitda", "dcf") if k in base_methods]
    if ev_methods and bridge.get("ok"):
        for gp in bridge.get("gaps") or []:
            gp = {**gp, "methods": [METHOD_NAMES[k] for k in ev_methods], **gap_impact(gp.get("bound"), mcap)}
            res["data_gaps"].append(gp)
            pct = f" ≈ {gp['impact_pct'] * 100:.1f}% vốn hóa" if gp.get("impact_pct") is not None else ""
            if gp["impact"] in ("cao", "không xác định"):
                for k in ev_methods:
                    for s in SCEN:
                        scen_rows[s]["methods"].pop(k, None)
                    res["invalid"].append((SHORT[k], f"Thiếu số liệu {gp['item']} năm {gp['year']} – ảnh hưởng "
                                                             f"{gp['impact']}{pct}: không dùng (không thay bằng 0)"))
            else:
                res["notes"].append(f"Thiếu số liệu {gp['item']} năm {gp['year']} → tạm coi = 0 trong "
                                    f"{', '.join(gp['methods'])}; ảnh hưởng tối đa: {gp['impact']}{pct} – {gp['direction']}.")
    for gp in forecast.get("data_gaps") or []:
        if gp.get("impact") != "cao":
            res["notes"].append(f"Dự báo: thiếu {gp['item']} – {gp['treatment']} (ảnh hưởng {gp['impact']}).")

    # ── kiểm tra bất thường trước khi tổng hợp ──
    lo_b, hi_b = v["sanity_band"]
    for k, m in list(base_methods.items()):
        ratio = m["target"] / price
        if not (lo_b <= ratio <= hi_b) or m["target"] <= 0:
            res["invalid"].append((SHORT[k], f"Kết quả {m['target']:,.0f} bất thường so với thị giá ({ratio:.2f} lần) – loại"))
            for s in SCEN:
                scen_rows[s]["methods"].pop(k, None)
    if len(base_methods) >= 3:
        med = float(np.median([m["target"] for m in base_methods.values()]))
        lo_o, hi_o = v["outlier_band"]
        for k, m in list(base_methods.items()):
            r = m["target"] / med
            if not (lo_o <= r <= hi_o):
                res["invalid"].append((SHORT[k], f"Lệch bất thường so với trung vị các phương pháp ({m['target']:,.0f} "
                                                         f"= {r:.2f}× trung vị {med:,.0f}) – loại"))
                for s in SCEN:
                    scen_rows[s]["methods"].pop(k, None)

    valid = [k for k in wcfg if k in base_methods]
    used = set(valid)
    for c in res["comparison"]:
        c["used"] = c["key"] in used
    if not valid:
        res["notes"].append("Không có phương pháp định giá hợp lệ sau kiểm tra dữ liệu và bất thường.")
        res["scenarios"] = scen_rows
        return res
    tw = sum(wcfg[k] for k in valid)
    weights = {k: wcfg[k] / tw for k in valid}
    coverage = tw / sum(wcfg.values())

    for s in SCEN:
        ms = {k: m for k, m in scen_rows[s]["methods"].items() if k in weights}
        sw = sum(weights[k] for k in ms)
        if sw and set(ms) != set(valid):
            res["notes"].append(f"Kịch bản {SCEN_LABEL[s]}: thiếu {', '.join(METHOD_NAMES[k] for k in valid if k not in ms)} "
                                "→ trọng số chuẩn hóa lại trên các phương pháp còn lại.")
        tgt = sum(ms[k]["target"] * weights[k] for k in ms) / sw if sw else None
        ftd = sum(ms[k]["fair_today"] * weights[k] for k in ms) / sw if sw else None
        scen_rows[s].update(target=tgt, fair_today=ftd, upside=(tgt / price - 1) * 100 if tgt else None,
                            weights_used={k: weights[k] / sw for k in ms} if sw else {})
    target = scen_rows["base"]["target"]
    fair_today = scen_rows["base"]["fair_today"]
    methods_out = []
    for k in valid:
        m = scen_rows["base"]["methods"][k]
        methods_out.append({"key": k, "name": METHOD_NAMES[k], "multiple": m.get("multiple"), "base": m.get("base"),
                            "base_label": m.get("base_label", ""), "fair": m["target"], "fair_today": m["fair_today"],
                            "weight": weights[k], "weight_config": wcfg[k] / sum(wcfg.values()),
                            "upside": (m["target"] / price - 1) * 100, "source": m.get("source", ""),
                            "period": m.get("period", ""),
                            "detail": {kk: vv for kk, vv in m.items() if kk not in ("target",)}})
    # DDM chỉ là phương pháp đối chiếu (trọng số thấp) → không tính vào độ phân tán dùng cho độ tin cậy
    core_fair = [x["fair"] for x in methods_out if x["key"] != "ddm"] or [x["fair"] for x in methods_out]
    spread = max(core_fair) / min(core_fair)
    share_gap = _share_basis_gap(wide, shares / (share_factor or 1.0), forecast)   # bỏ phần CP thưởng đã biết
    bear_t, bull_t = scen_rows.get("bear", {}).get("target"), scen_rows.get("bull", {}).get("target")
    scen_ratio = (bull_t / bear_t) if bear_t and bull_t and bear_t > 0 else None
    if basis_unknown:
        conf_caps = list(conf_caps) + [("Thấp", "định giá tại ngày quá khứ chưa quy đổi được số CP về cùng cơ sở với giá đã điều chỉnh")]
    if rf_note and v.get("risk_free_unsourced_cap"):
        conf_caps = list(conf_caps) + [(v["risk_free_unsourced_cap"], "lãi suất phi rủi ro Rf chưa có nguồn/ngày cập nhật hoặc đã cũ")]
    conf, conf_detail = _confidence(v, methods_out, spread, stale, coverage, forecast, conf_caps, res, share_gap,
                                    scen_ratio=scen_ratio, scope_change=bool(scope.get("active")))
    res["confidence_detail"] = conf_detail
    res["notes"].append(f"Hồ sơ phương pháp: {prof.get('label', pkey)} ({why}). Trọng số thực tế: "
                        + ", ".join(f"{METHOD_NAMES[k]} {w:.0%}" for k, w in weights.items()) + ".")
    upside = (target / price - 1) * 100
    exp_ret = ((target + dps - price) / price) * 100
    res.update(
        available=conf != "Thấp", status="OK" if conf != "Thấp" else NOT_ENOUGH, confidence=conf,
        target_12m=target, fair_value=target, fair_value_today=fair_today, intrinsic_today=fair_today, upside=upside,
        expected_dividend=dps, dividends_included=dps > 0, expected_return=exp_ret,
        dividend_yield=dps / price * 100, methods=methods_out, weights=weights, weight_coverage=coverage,
        scenarios=scen_rows, group_weights={"pe": weights.get("pe", 0.0), "pb": weights.get("pb", 0.0)},
        financial=fin, sensitivity=engine._sensitivity(target), spread=spread,
        dcf_sensitivity=next((x["detail"].get("sens_wacc_g") for x in methods_out if x["key"] == "dcf"), None),
        scenario_ratio=scen_ratio,
    )
    if conf == "Thấp":
        res["notes"].append("Độ tin cậy định giá thấp (ít phương pháp hợp lệ, phân tán lớn hoặc dữ liệu cũ) → "
                            f"trạng thái: {NOT_ENOUGH}. Các con số chỉ để tham khảo.")
    return res


# ─────────────────────────────────────────────────────────────────────────────
# Từng phương pháp
# ─────────────────────────────────────────────────────────────────────────────

def _today(target: float, ke: float, dps: float) -> float:
    return (target + dps) / (1 + ke)


_DECAY: List[Optional[float]] = [None]      # trọng số theo độ gần của bội số lịch sử (đặt mỗi lần định giá từ cấu hình)
_FADE: List[Optional[float]] = [None]       # ROE dài hạn = min(ROE dự báo, Ke + spread) (đặt mỗi lần định giá từ cấu hình)


def _roe_term(roe: float, ke: float, spread: Optional[float] = None) -> float:
    """ROE sau giai đoạn dự báo (15/10/2026): lợi thế cạnh tranh bị bào mòn → ROE vượt Ke quá mức không kéo dài vĩnh viễn;
    giữ tối đa Ke + spread (mặc định 3 điểm %). ROE thấp hơn mức đó giữ nguyên."""
    sp = _FADE[0] if spread is None else spread
    return min(roe, ke + sp) if sp is not None else roe


def _justified_pb(roe: float, ke: float, g: float, years: int = 5) -> Optional[float]:
    """P/B hợp lý 2 giai đoạn: 1 + Σ PV[(ROE − Ke)] trong `years` năm + PV[(ROE dài hạn − Ke)/(Ke − g)] sau đó
    (trên 1 đồng VCSH, bỏ qua tăng VCSH giai đoạn 1 – thận trọng). Không có spread → công thức 1 giai đoạn cũ."""
    if ke - g < 0.02:
        return None
    if _FADE[0] is None:
        return (roe - g) / (ke - g) if roe > g else None
    ann = (1 - (1 + ke) ** -years) / ke
    rt = _roe_term(roe, ke)
    v = 1 + (roe - ke) * ann + (rt - ke) / (ke - g) / (1 + ke) ** years
    return v if v > 0 else None


def _wq(d: Dict[Any, float], q: float) -> Optional[float]:
    """Phân vị q của bội số lịch sử {năm: giá trị}. Có hệ số suy giảm (15/10/2026): năm gần nhất trọng số 1, năm trước
    × decay… (bán kỳ 1 năm khi decay 0,5) → bội số tham chiếu bắt kịp khi thị trường định giá lại doanh nghiệp (FPT tăng
    hạng, VHM giảm hạng) thay vì neo vào trung vị 5 năm như nhau. Phân vị có trọng số, nội suy theo điểm giữa."""
    items = sorted((k, float(x)) for k, x in (d or {}).items() if x is not None and np.isfinite(x))
    if len(items) < 3:
        return None
    decay = _DECAY[0]
    if not decay or decay >= 1:
        return float(np.percentile([x for _, x in items], q))
    n = len(items)
    pts = sorted((x, decay ** (n - 1 - i)) for i, (_, x) in enumerate(items))
    vals = np.array([x for x, _ in pts])
    w = np.array([wt for _, wt in pts])
    pos = (np.cumsum(w) - w / 2) / w.sum()
    return float(np.interp(q / 100.0, pos, vals))


def _hist_txt(hist, key, fmt):
    vv = hist.get(key) or {}
    if len(vv) < 3:
        return None
    lab = "trung vị có trọng số theo độ gần" if _DECAY[0] and _DECAY[0] < 1 else "trung vị"
    return (f"{key.upper().replace('_', '/')} lịch sử " + ", ".join(f"{y}: {x:{fmt}}x" for y, x in vv.items())
            + f" ({lab} {_wq(vv, 50):{fmt}}x)")


def _pe(vi, hist, peers, p, risk_level, y1, ke, dps, cyc=None, fshift=0.0, shares=None,
        pe_cap: Optional[float] = None, bear_cap: Optional[float] = None,
        abs_cap: Optional[float] = None) -> Dict[str, Any]:
    from core.dinh_gia import _pct
    eps = _num(vi.get("eps_fwd"))
    base_label, period = "EPS NTM (dự báo)", f"NTM đến {vi.get('ntm_window_end')}"
    norm_txt = ""
    if cyc is not None:
        if not cyc.get("ok"):
            return {"valid": False, "reason": cyc["reason"]}
        rev = _num(vi.get("revenue_fwd"))
        if rev is None or not shares:
            return {"valid": False, "reason": "Không có doanh thu NTM để chuẩn hóa EPS theo chu kỳ"}
        nm = cyc["net_margin"] + fshift * (1 - cyc["tax"])
        eps = rev * nm * cyc["parent_share"] / shares
        base_label = f"EPS chuẩn hóa chu kỳ (DT NTM × biên ròng trung vị {cyc['years']} năm)"
        norm_txt = f" (chuẩn hóa: DT NTM × biên ròng {nm:.1%}, trung vị {cyc['years']} năm {cyc['span']})"
    if eps is None:
        return {"valid": False, "reason": "Không có EPS NTM từ Forecast Engine"}
    if eps <= 0:
        return {"valid": False, "reason": f"EPS dự báo ≤ 0 ({eps:,.0f})"}
    pe_hist = list(hist["pe"].values())
    peer = _num(peers.get("pe")) if (peers.get("n_pe") or peers.get("n") or 0) >= 3 else None
    refs = [x for x in [_wq(hist["pe"], 50), peer] if x]
    if not refs:
        return {"valid": False, "reason": "Không có P/E tham chiếu (lịch sử ≥ 3 năm hoặc ngành ≥ 3 DN)"}
    pe_t = float(np.median(refs))
    adj = []
    if len(pe_hist) >= 3 and p["multiple_pct"] != 50:
        f = float(np.clip(_wq(hist["pe"], p["multiple_pct"]) / _wq(hist["pe"], 50), 0.7, 1.4))
        pe_t *= f
        adj.append(f"phân vị {p['multiple_pct']} lịch sử (×{f:.2f})")
    if risk_level in ("Cao", "Nghiêm trọng"):
        pe_t *= 0.9
        adj.append("rủi ro cao ×0,9")
    if peer and pe_cap and pe_t > peer * pe_cap:      # bước 10: chặn P/E tham chiếu ở vùng bong bóng
        adj.append(f"chặn trần {pe_cap:g} × P/E ngành = {peer * pe_cap:.1f}x (từ {pe_t:.1f}x)")
        pe_t = peer * pe_cap
    if abs_cap and pe_t > abs_cap:                      # trần P/E tuyệt đối theo hồ sơ ngành (mặc định TẮT – cấu hình)
        adj.append(f"chặn trần tuyệt đối {abs_cap:g}x (từ {pe_t:.1f}x)")
        pe_t = float(abs_cap)
    if (y1.get("growth") or 0) < 0 and cyc is None:
        pe_t *= 0.9
        adj.append("tăng trưởng âm ×0,9")
    if bear_cap and pe_t > bear_cap:                    # Thận trọng: không cao hơn P/E thị trường đang trả hiện nay
        adj.append(f"Thận trọng: ≤ P/E dự phóng hiện tại {bear_cap:.1f}x (từ {pe_t:.1f}x)")
        pe_t = bear_cap
    target = eps * pe_t
    src = "P/E tham chiếu = trung vị của: " + "; ".join(r for r in [_hist_txt(hist, "pe", ".1f"),
                                                                       f"P/E ngành {peer:.1f}x" if peer else None] if r)
    if not peer:
        src += " (chưa đủ 3 DN cùng nhóm có số liệu → chỉ dùng lịch sử của chính mã)"
    src += (" · điều chỉnh: " + ", ".join(adj) if adj else "") + f" → {pe_t:.1f}x × EPS {eps:,.0f}" + norm_txt
    return {"valid": True, "target": target, "fair_today": _today(target, ke, dps), "multiple": pe_t, "base": eps,
            "base_label": base_label, "period": period, "source": src, "peer_used": bool(peer)}


def _pb(vi, forecast, s, hist, peers, p, ke, g_t, dps, cyc=None, bear_cap: Optional[float] = None) -> Dict[str, Any]:
    from core.dinh_gia import _pct
    bvps = _num(vi.get("bvps_fwd"))
    if bvps is None or bvps <= 0:
        return {"valid": False, "reason": "Không có BVPS dương tại ngày mục tiêu (VCSH thiếu/âm)"}
    if cyc is not None and cyc.get("ok") and cyc.get("roe") is not None:
        roe_sus, roe_src = cyc["roe"], f"ROE trung vị chu kỳ {cyc['years']} năm"
    else:
        roes = [y.get("roe") for y in (forecast["scenarios"][s]["years"] or [])[:3] if y.get("roe") is not None]
        roe_sus, roe_src = (float(np.median(roes)) if roes else None), "ROE dự báo năm 1–3"
    jpb = _justified_pb(roe_sus, ke, g_t) if roe_sus is not None else None
    pb_hist = list(hist["pb"].values())
    h_pb = _wq(hist["pb"], p["multiple_pct"]) if len(pb_hist) >= 3 else None
    peer = _num(peers.get("pb")) if (peers.get("n_pb") or peers.get("n") or 0) >= 3 else None
    refs = [x for x in [h_pb, peer, jpb] if x and x > 0]
    if not refs:
        return {"valid": False, "reason": "Không có P/B tham chiếu (lịch sử, ngành) và ROE dự báo ≤ g dài hạn"}
    pb_t = float(np.median(refs))
    capped = bool(bear_cap and pb_t > bear_cap)
    if capped:
        pb_t = bear_cap
    target = bvps * pb_t
    src = "P/B tham chiếu = trung vị của: " + "; ".join(r for r in [
        f"P/B lịch sử phân vị {p['multiple_pct']} = {h_pb:.2f}x" if h_pb else None,
        f"P/B ngành {peer:.2f}x" if peer else None,
        (f"P/B hợp lý 2 giai đoạn ({roe_src} {roe_sus:.1%} trong 5 năm, sau đó ROE {_roe_term(roe_sus, ke):.1%}; "
         f"Ke {ke:.1%}, g {g_t:.1%}) = {jpb:.2f}x" if _FADE[0] is not None else
         f"P/B hợp lý ({roe_src} {roe_sus:.1%} − g {g_t:.1%})/(Ke {ke:.1%} − g) = {jpb:.2f}x") if jpb else None] if r)
    src += (f" · Thận trọng: ≤ P/B dự phóng hiện tại {bear_cap:.2f}x" if capped else "") + \
        f" → {pb_t:.2f}x × BVPS tại ngày mục tiêu {bvps:,.0f}"
    return {"valid": True, "target": target, "fair_today": _today(target, ke, dps), "multiple": pb_t, "base": bvps,
            "base_label": "BVPS tại T+12 (dự báo)", "justified_pb": jpb, "roe_sustainable": roe_sus,
            "period": f"VCSH tại {vi.get('ntm_window_end')}", "source": src}


def _bridge_parts(bridge) -> Tuple[float, float, float, float]:
    """(nợ vay, tiền + ĐTTC ngắn hạn, đầu tư tài chính dài hạn, CĐ thiểu số) của cầu nối EV → vốn chủ."""
    return bridge["debt"], bridge["cash"], bridge.get("lt_investments", 0.0), bridge["minority"]


def _ev(vi, hist, p, bridge, shares, ke, dps, cyc=None, fshift=0.0, bear_cap: Optional[float] = None) -> Dict[str, Any]:
    from core.dinh_gia import _pct
    if not (vi.get("applicable") or {}).get("ev_ebitda"):
        return {"valid": False, "reason": "Forecast Engine: EBITDA không áp dụng cho loại hình này"}
    ebitda = _num(vi.get("ebitda_core_fwd"))
    label = "EBITDA cốt lõi NTM/CP (dự báo)"
    if cyc is not None:
        if not cyc.get("ok"):
            return {"valid": False, "reason": cyc["reason"]}
        rev = _num(vi.get("revenue_fwd"))
        if rev is None or cyc.get("core_margin") is None:
            return {"valid": False, "reason": "Không chuẩn hóa được EBITDA cốt lõi theo chu kỳ (thiếu biên cốt lõi lịch sử)"}
        ebitda = rev * (cyc["core_margin"] + fshift)
        label = f"EBITDA cốt lõi chuẩn hóa chu kỳ/CP (biên trung vị {cyc['years']} năm)"
    if ebitda is None:
        return {"valid": False, "reason": "Không có EBITDA cốt lõi NTM (không tách được thu nhập tài chính khỏi EBIT)"}
    if ebitda <= 0:
        return {"valid": False, "reason": "EBITDA cốt lõi dự báo ≤ 0"}
    if not bridge.get("ok"):
        return {"valid": False, "reason": bridge.get("reason")}
    vals = list(hist["ev_ebitda"].values())
    if len(vals) < 3:
        return {"valid": False, "reason": "Cần ≥ 3 năm EV/EBITDA cốt lõi lịch sử"}
    mult = _wq(hist["ev_ebitda"], p["multiple_pct"])
    capped = bool(bear_cap and mult > bear_cap)
    if capped:
        mult = bear_cap
    debt, cash, lti, mi = _bridge_parts(bridge)
    nd = debt - cash
    equity = ebitda * mult - nd + lti - mi
    if equity <= 0:
        return {"valid": False, "reason": "Giá trị vốn chủ ≤ 0 (nợ vay ròng lớn hơn EV)"}
    target = equity / shares
    src = (_hist_txt(hist, "ev_ebitda", ".1f") or "") + f" (EBITDA cốt lõi) → phân vị {p['multiple_pct']}" \
          + (", Thận trọng ≤ EV/EBITDA dự phóng hiện tại" if capped else "") + f" = {mult:.1f}x × " \
          f"{'EBITDA chuẩn hóa' if cyc is not None else 'EBITDA cốt lõi NTM'}; trừ nợ vay ròng {nd / 1e9:,.0f} tỷ, cộng " \
          f"đầu tư tài chính dài hạn {lti / 1e9:,.0f} tỷ, trừ CĐ thiểu số {mi / 1e9:,.0f} tỷ ({bridge.get('label')})"
    return {"valid": True, "target": target, "fair_today": _today(target, ke, dps), "multiple": mult,
            "base": ebitda / shares, "base_label": label, "ebitda_fwd": ebitda, "net_debt": nd,
            "bridge_per_share": (-nd + lti - mi) / shares, "bridge_year": bridge["year"],
            "bridge_period": bridge.get("label"), "period": f"NTM đến {vi.get('ntm_window_end')}", "source": src}


def _dcf(engine, vi, wide, bridge, shares, price, ke, g_t, dps, T) -> Dict[str, Any]:
    from core.dinh_gia import _col, net_debt_at
    v = engine.v
    if not (vi.get("applicable") or {}).get("dcf_fcff"):
        return {"valid": False, "reason": "Forecast Engine: FCFF không áp dụng cho loại hình này"}
    flows, ends = vi.get("fcff_path") or [], vi.get("fcff_period_ends") or []
    if not flows or len(flows) != len(ends) or any(f is None for f in flows):
        return {"valid": False, "reason": "Thiếu đường FCFF dự báo (cần EBIT cốt lõi)"}
    if flows[-1] <= 0:
        return {"valid": False, "reason": f"FCFF năm cuối dự báo ≤ 0 ({flows[-1] / 1e9:,.0f} tỷ) – không tính giá trị cuối kỳ"}
    if not bridge.get("ok"):
        return {"valid": False, "reason": bridge.get("reason")}
    t = v["tax_rate"]
    debt, cash, lti, mi = _bridge_parts(bridge)
    k = wide.index[-1]
    int_k = _num(_col(wide, "interest_expense").abs().get(k))
    prev = wide.index[-2] if len(wide.index) >= 2 else None
    dp = net_debt_at(wide, prev) if prev is not None else {"ok": False}
    debt_y = net_debt_at(wide, k)
    debt_ref = debt_y["debt"] if debt_y.get("ok") else debt
    debt_avg = (debt_ref + dp["debt"]) / 2 if dp.get("ok") and not any(g["item"] == "vay nợ" for g in dp["gaps"]) else debt_ref
    kd = float(np.clip(int_k / debt_avg, *v["kd_bounds"])) if int_k is not None and debt_avg > 0 else v["kd_bounds"][0]
    e = price * shares
    wacc = e / (e + debt) * ke + debt / (e + debt) * kd * (1 - t)
    if wacc - g_t < v["dcf_min_spread"]:
        return {"valid": False, "reason": f"WACC {wacc * 100:.1f}% − g {g_t * 100:.1f}% quá nhỏ"}
    pv, used = 0.0, []
    for f, end in zip(flows, ends):
        tau = _years_from(T, end)
        if tau <= 0:
            continue                                      # kỳ đã qua tại ngày định giá
        share = min(tau, 1.0)                             # năm đầu: chỉ phần còn lại sau T
        pv += f * share / (1 + wacc) ** tau
        used.append((end, f * share, tau))
    if not used:
        return {"valid": False, "reason": "Mọi kỳ FCFF dự báo đã qua ngày định giá (kỳ gốc quá cũ)"}
    tau_n = used[-1][2]
    tv = flows[-1] * (1 + g_t) / (wacc - g_t)
    pv_tv = tv / (1 + wacc) ** tau_n
    ev = pv + pv_tv
    # Bước 9: FCFF chỉ từ EBIT cốt lõi → cộng MỘT LẦN tiền, ĐTTC ngắn hạn và đầu tư tài chính dài hạn
    equity = ev - debt + cash + lti - mi
    if equity <= 0:
        return {"valid": False, "reason": "Giá trị vốn chủ ước tính ≤ 0"}
    intrinsic = equity / shares
    target = intrinsic * (1 + ke) - dps

    # Độ nhạy giá mục tiêu DCF theo WACC × g dài hạn (giá trị cuối kỳ thường chiếm phần lớn EV)
    def _t(w, g):
        if w - g < v["dcf_min_spread"]:
            return None
        pv_ = sum(f_ / (1 + w) ** tau_ for _, f_, tau_ in used)
        eq_ = pv_ + flows[-1] * (1 + g) / (w - g) / (1 + w) ** tau_n - debt + cash + lti - mi
        return eq_ / shares * (1 + ke) - dps if eq_ > 0 else None
    steps = (-0.01, -0.005, 0.0, 0.005, 0.01)
    sens = {"wacc": [wacc + d for d in steps], "g": [g_t + d for d in steps],
            "grid": [[_t(wacc + dw, g_t + dg) for dg in steps] for dw in steps]}
    src = (f"FCFF {len(used)} kỳ ({used[0][0]} → {used[-1][0]}) từ EBIT cốt lõi; WACC {wacc * 100:.1f}% "
           f"(Ke {ke * 100:.1f}%, Kd {kd * 100:.1f}%); g dài hạn {g_t * 100:.1f}%; giá trị cuối kỳ {pv_tv / ev * 100:.0f}% EV; "
           f"EV − nợ vay {debt / 1e9:,.0f} tỷ + tiền/ĐTTC {cash / 1e9:,.0f} tỷ + đầu tư dài hạn {lti / 1e9:,.0f} tỷ − CĐ thiểu số "
           f"({bridge.get('label')}); giá mục tiêu = giá trị hôm nay {intrinsic:,.0f} × (1 + Ke) − cổ tức")
    return {"valid": True, "target": target, "fair_today": intrinsic, "intrinsic": intrinsic, "multiple": None,
            "base": flows[0] / shares, "base_label": "FCFF năm 1/CP (dự báo)", "wacc": wacc, "kd": kd,
            "g_terminal": g_t, "ev": ev, "tv_share": pv_tv / ev, "net_debt": debt - cash, "lt_investments": lti,
            "flows": flows, "bridge_period": bridge.get("label"), "sens_wacc_g": sens,
            "period": f"FCFF {used[0][0]} → {used[-1][0]}, chiết khấu về {T.date()}", "source": src}


def _flow_pv(flows: List[float], ends: List[str], T: pd.Timestamp, r: float) -> Tuple[float, List[Tuple[str, float, float]]]:
    """PV tại T của dòng tiền năm (năm đầu chỉ tính phần còn lại sau T)."""
    pv, used = 0.0, []
    for f, end in zip(flows, ends):
        tau = _years_from(T, end)
        if tau <= 0:
            continue
        share = min(tau, 1.0)
        pv += f * share / (1 + r) ** tau
        used.append((end, f * share, tau))
    return pv, used


def _ri(vi, forecast, s, shares, ke, g_t, dps, T, engine) -> Dict[str, Any]:
    """Thu nhập thặng dư (bước 9) – cho ngân hàng/CTCK/bảo hiểm:
       Giá trị hôm nay = BVPS tại T + Σ PV[(LNST mẹ_t − Ke × VCSH_(t−1))] + PV[RI năm N+1 / (Ke − g)]
       RI năm N+1 = (ROE bền vững − Ke) × VCSH năm N; ROE bền vững = trung vị ROE dự báo năm 1–3 (như P/B hợp lý).
       VCSH tại T nội suy giữa kỳ gốc và năm 1 theo thời gian đã trôi qua. Không dùng khi Ke − g < 3 điểm %."""
    v = engine.v
    yrs = (forecast.get("scenarios", {}).get(s) or {}).get("years") or []
    ends = vi.get("fcff_period_ends") or [y.get("period_end") for y in yrs]
    eqs = [y.get("equity_parent") for y in yrs]
    nis = [y.get("net_income_parent") for y in yrs]
    base = forecast.get("base") or {}
    if not yrs or any(x is None for x in eqs + nis) or not ends or any(e is None for e in ends):
        return {"valid": False, "reason": "Thiếu đường LNST mẹ/VCSH dự báo cho thu nhập thặng dư"}
    if ke - g_t < v["dcf_min_spread"]:
        return {"valid": False, "reason": f"Ke {ke:.1%} − g {g_t:.1%} < {v['dcf_min_spread']:.0%}"}
    pay = (forecast["drivers"].get("payout") or {}).get("value", 0.0)
    eq0 = eqs[0] - nis[0] + max(nis[0], 0.0) * pay           # nghịch đảo đúng công thức VCSH của Forecast Engine
    if eq0 <= 0:
        return {"valid": False, "reason": "VCSH kỳ gốc ≤ 0"}
    b_prev = [eq0] + eqs[:-1]
    ri = [ni - ke * b for ni, b in zip(nis, b_prev)]
    pv, used = _flow_pv(ri, ends, T, ke)
    if not used:
        return {"valid": False, "reason": "Mọi kỳ dự báo đã qua ngày định giá"}
    base_end = pd.Timestamp(base.get("end")) if base.get("end") else pd.Timestamp(ends[0]) - pd.DateOffset(years=1)
    frac = float(np.clip(_years_from(base_end, str(T.date())), 0, 1))
    b_T = eq0 + (eqs[0] - eq0) * frac
    roes = [y.get("roe") for y in yrs[:3] if y.get("roe") is not None]
    roe_sus = float(np.median(roes)) if roes else None
    if roe_sus is None:
        return {"valid": False, "reason": "Không có ROE dự báo"}
    roe_t = _roe_term(roe_sus, ke, v.get("roe_fade_spread"))   # ROE sau giai đoạn dự báo hội tụ về Ke + spread
    ri_tv = (roe_t - ke) * eqs[-1]
    pv_tv = ri_tv * (1 + g_t) / (ke - g_t) / (1 + ke) ** used[-1][2]
    intrinsic = (b_T + pv + pv_tv) / shares
    if intrinsic <= 0:
        return {"valid": False, "reason": "Giá trị thu nhập thặng dư ≤ 0"}
    target = intrinsic * (1 + ke) - dps
    tot = b_T + pv + pv_tv
    src = (f"BVPS tại {T.date()} {b_T / shares:,.0f} + PV thu nhập thặng dư {len(used)} năm {pv / shares:,.0f} + giá trị cuối "
           f"kỳ {pv_tv / shares:,.0f} (ROE dự báo {roe_sus:.1%}, ROE dài hạn {roe_t:.1%} vs Ke {ke:.1%}, g {g_t:.1%}); giá mục tiêu = "
           f"hôm nay × (1+Ke) − cổ tức")
    return {"valid": True, "target": target, "fair_today": intrinsic, "intrinsic": intrinsic, "multiple": None,
            "base": b_T / shares, "base_label": "BVPS tại ngày định giá", "roe_sustainable": roe_sus,
            "tv_share": abs(pv_tv) / abs(tot) if tot else None, "period": f"{used[0][0]} → {used[-1][0]}", "source": src}


def _ddm(vi, forecast, wide, shares, ke, g_t, dps, T, engine) -> Dict[str, Any]:
    """Chiết khấu cổ tức 2 giai đoạn (bước 9) – CHỈ để đối chiếu, trọng số thấp.
       Giai đoạn 1 (5 năm, cùng kỳ hạn DCF): DPS_t = EPS dự báo_t × tỷ lệ chi trả (trung vị 3–5 năm, chỉ cổ tức TIỀN
         MẶT từ LCTT – cổ tức cổ phiếu không phải dòng tiền, đã phản ánh qua số CP).
       Giai đoạn 2: DPS_(N+1) = EPS_N × (1+g) × chi trả bền vững, chi trả bền vững = 1 − g / ROE dài hạn
         (tăng trưởng phải được tài trợ bằng lợi nhuận giữ lại); TV = DPS_(N+1) / (Ke − g).
       Không áp dụng nếu: < 3 năm trả cổ tức tiền mặt trong 5 năm, tỷ lệ chi trả quá thất thường (CV > 0,5), thiếu
       đủ 5 năm EPS dự báo, Ke − g < 3 điểm %, hoặc chi trả bền vững ngoài (0, 1]."""
    from core.dinh_gia import _col
    c = engine.v["ddm"]
    na = lambda r: {"valid": False, "not_applicable": True, "reason": r}  # noqa: E731
    divs = _col(wide, "dividends_paid").abs()
    ni = _col(wide, "net_income_parent")
    ni = ni.where(ni.notna(), _col(wide, "net_income"))
    look = pd.DataFrame({"d": divs, "n": ni}).tail(c["lookback_years"])
    paid = look[(look["d"] > 0) & (look["n"] > 0)]
    if len(paid) < c["min_div_years"]:
        return na(f"Chỉ {len(paid)}/{c['lookback_years']} năm gần nhất trả cổ tức tiền mặt (cần ≥ {c['min_div_years']})")
    po = (paid["d"] / paid["n"]).clip(upper=1.5)
    cv = float(po.std(ddof=0) / po.mean()) if po.mean() > 0 else 9.0
    if cv > c["max_payout_cv"]:
        return na(f"Tỷ lệ chi trả cổ tức thất thường (hệ số biến thiên {cv:.2f} > {c['max_payout_cv']})")
    payout = float(np.clip(po.median(), 0, 1))
    eps_path = vi.get("eps_path") or []
    ends = vi.get("fcff_period_ends") or [y.get("period_end") for y in
                                          (forecast.get("scenarios", {}).get("base") or {}).get("years") or []]
    n_need = int(engine.cfg["forecast"]["years"])
    if len(eps_path) < n_need or any(e is None for e in eps_path) or len(ends) < len(eps_path):
        return na(f"Forecast Engine chưa có đủ {n_need} năm EPS dự báo")
    if ke - g_t < c["min_spread"]:
        return {"valid": False, "reason": f"Ke {ke:.1%} − g {g_t:.1%} < {c['min_spread']:.0%}"}
    roes = [r for r in (vi.get("roe_path") or [])[-3:] if r is not None]
    roe_lr = float(np.median(roes)) if roes else None
    if roe_lr is None or roe_lr <= 0:
        return {"valid": False, "reason": "Không có ROE dài hạn dương để kiểm tra tỷ lệ chi trả bền vững"}
    po_st = 1 - g_t / roe_lr
    if not (0 < po_st <= 1):
        return {"valid": False, "reason": f"Chi trả bền vững 1 − g/ROE = {po_st:.0%} ngoài (0, 100%]"}
    dps_path = [max(e, 0.0) * payout for e in eps_path]
    pv, used = _flow_pv(dps_path, ends[:len(dps_path)], T, ke)
    if not used:
        return {"valid": False, "reason": "Mọi kỳ dự báo đã qua ngày định giá"}
    d_next = max(eps_path[-1], 0.0) * (1 + g_t) * po_st
    pv_tv = d_next / (ke - g_t) / (1 + ke) ** used[-1][2]
    intrinsic = pv + pv_tv
    if intrinsic <= 0:
        return {"valid": False, "reason": "Giá trị chiết khấu cổ tức ≤ 0"}
    dps12 = dps_path[0]
    target = intrinsic * (1 + ke) - dps           # cùng quy ước cổ tức 12T với các phương pháp khác
    src = (f"Chi trả {payout:.0%} (trung vị {len(paid)} năm, CV {cv:.2f}) × EPS dự báo {len(eps_path)} năm; giai đoạn 2: "
           f"chi trả bền vững 1 − g/ROE = {po_st:.0%} (ROE dài hạn {roe_lr:.1%}, g {g_t:.1%}); Ke {ke:.1%}; "
           f"giá trị cuối kỳ {pv_tv / intrinsic:.0%} tổng")
    return {"valid": True, "target": target, "fair_today": intrinsic, "intrinsic": intrinsic, "multiple": None,
            "base": dps12, "base_label": "DPS năm 1 (dự báo)", "payout": payout, "payout_stable": po_st,
            "tv_share": pv_tv / intrinsic, "period": f"{used[0][0]} → {used[-1][0]}", "source": src}


def _select_bridge(wide, quarterly, T, res) -> Dict[str, Any]:
    """Cầu nối EV → vốn chủ từ bảng cân đối MỚI NHẤT ĐÃ CÔNG BỐ trước T (bước 9): quý (độ trễ công bố
    QUARTER_RELEASE_LAG_DAYS) nếu mới hơn năm tài chính gần nhất, ngược lại năm. Số dư không phụ thuộc cơ sở quý
    (lũy kế/từng quý) nên dùng được kể cả khi không dùng TTM."""
    from core.du_phong import quarters_available
    from core.dinh_gia import net_debt_at
    annual_b = net_debt_at(wide, wide.index[-1], include_lt=True)
    if quarterly is None or getattr(quarterly, "empty", True):
        return annual_b
    q = quarters_available(quarterly, T)
    if q is None or q.empty:
        return annual_b
    for k in sorted(q.index, reverse=True):
        if int(k) // 10 <= int(wide.index[-1]) // 10:
            break                                         # không mới hơn cuối năm tài chính gần nhất
        b = net_debt_at(q, k, include_lt=True)
        if b.get("ok") and not any(g["item"] == "vay nợ" for g in b["gaps"]):
            res["notes"].append(f"Cầu nối EV → vốn chủ (nợ vay, tiền, đầu tư tài chính) lấy từ bảng cân đối {b['label']} "
                                f"– kỳ mới nhất đã công bố trước ngày định giá.")
            return b
    return annual_b


def _cycle_norm(engine, wide, company, pkey, forecast) -> Dict[str, Any]:
    """Chuẩn hóa chu kỳ (bước 9) cho hồ sơ sản xuất/chu kỳ: biên ròng, biên EBITDA cốt lõi và ROE = trung vị của
    N năm gần nhất (giữa chu kỳ) thay vì biên của năm đỉnh/đáy. Quy tắc dự phòng (đã chốt trước):
      ≥ cycle_years năm  → chuẩn hóa đầy đủ;
      3 … cycle_years−1  → chuẩn hóa theo số năm hiện có, độ tin cậy tối đa 'Trung bình';
      < 3 năm            → không chuẩn hóa được ⇒ loại P/E và EV/EBITDA, độ tin cậy 'Thấp'."""
    from core.dinh_gia import _col
    v = engine.v
    n_max, n_min = int(v["cycle_years"]), int(v["cycle_min_years"])
    rev = _col(wide, "revenue")
    nip = _col(wide, "net_income_parent")
    ni = _col(wide, "net_income")
    df = pd.DataFrame({"rev": rev, "ni": ni, "nip": nip.where(nip.notna(), ni),
                       "eq": _col(wide, "equity") - _col(wide, "minority_interest").fillna(0)})
    from core.phan_tich_co_ban import core_ebit_ebitda
    df["core"] = core_ebit_ebitda(wide)[1]
    df = df[(df["rev"] > 0) & df["nip"].notna()].tail(n_max)
    n = len(df)
    span = f"{int(df.index[0]) // 10}–{int(df.index[-1]) // 10}" if n else ""
    if n < n_min:
        return {"ok": False, "years": n, "cap": "Thấp",
                "cap_reason": f"chu kỳ: chỉ {n} năm dữ liệu (< {n_min}) – không chuẩn hóa được",
                "reason": f"Doanh nghiệp chu kỳ nhưng chỉ có {n} năm BCTC (< {n_min}) → không chuẩn hóa được lợi nhuận "
                          "giữa chu kỳ; không dùng phương pháp dựa trên lợi nhuận/EBITDA một năm",
                "note": f"Chu kỳ: chỉ {n} năm dữ liệu → loại P/E và EV/EBITDA, độ tin cậy 'Thấp' (quy tắc dự phòng)."}
    tax = ((forecast.get("drivers") or {}).get("tax_rate") or {}).get("value", engine.v["tax_rate"])
    ps = ((forecast.get("drivers") or {}).get("parent_share") or {}).get("value", 1.0) or 1.0
    nm = float(np.median(df["ni"].where(df["ni"].notna(), df["nip"]) / df["rev"]))
    cm = (df["core"] / df["rev"]).dropna()
    roe = (df["nip"] / df["eq"].where(df["eq"] > 0)).dropna()
    out = {"ok": True, "years": n, "span": span, "net_margin": nm, "parent_share": ps, "tax": tax,
           "core_margin": float(np.median(cm)) if len(cm) >= n_min else None,
           "roe": float(np.median(roe)) if len(roe) >= n_min else None,
           "note": (f"Chu kỳ: P/E, EV/EBITDA dùng lợi nhuận/EBITDA chuẩn hóa = doanh thu NTM × biên trung vị {n} năm "
                    f"({span}); P/B hợp lý dùng ROE trung vị chu kỳ.")}
    if n < n_max:
        out.update(cap="Trung bình", cap_reason=f"chu kỳ: chuẩn hóa trên {n} năm (< {n_max})")
        out["note"] += f" Chỉ có {n} năm (< {n_max}) → độ tin cậy tối đa 'Trung bình'."
    return out


def _share_basis_gap(wide, shares, forecast) -> Optional[float]:
    """Chênh lệch số CP hiện hành so với số CP tại kỳ của VCSH gốc (bước 9). > 10% mà VCSH vẫn là số năm tài chính
    (chưa có bảng cân đối quý mới hơn) → không biết phần CP tăng thêm có thu tiền (phát hành quyền mua – VCSH thực tế
    lớn hơn) hay không (thưởng/cổ tức CP – không ảnh hưởng) → giá trị/CP theo VCSH, lợi nhuận có thể bị lệch."""
    from core.phan_tich_co_ban import shares_series
    base = (forecast or {}).get("base") or {}
    if base.get("kind") != "FY" or base.get("balance_from"):
        return None
    sh = shares_series(wide).dropna()
    sh = sh[sh > 0]
    if sh.empty or not shares:
        return None
    return float(shares / sh.iloc[-1] - 1)


def _confidence(v, methods_out, spread, stale, coverage, forecast, caps, res, share_gap=None,
                scen_ratio: Optional[float] = None, scope_change: bool = False) -> Tuple[str, Dict[str, Any]]:
    """Độ tin cậy (bước 9) – quy tắc đặt TRƯỚC khi chạy backtest, theo logic định giá:
      điểm khởi đầu 3 (= 'Cao'); trừ điểm cho: ≤ 2 phương pháp hợp lệ, phân tán giữa các phương pháp, dự báo LNST
      của chính mã sai số lớn (hoặc chưa kiểm định được), BCTC cũ, thiếu trọng số theo hồ sơ, DCF/RI phụ thuộc giá trị
      cuối kỳ; sau đó áp mức trần (hồ sơ thiếu phương pháp chuẩn của ngành, chu kỳ thiếu năm dữ liệu).
      3 → Cao, 2 → Trung bình, ≤ 1 → Thấp."""
    score, why = 3, []
    n = len(methods_out)
    if n <= 1:
        score -= 2
        why.append("chỉ 1 phương pháp hợp lệ")
    elif n == 2:
        score -= 1
        why.append("chỉ 2 phương pháp hợp lệ")
    if spread > v["spread_mid"]:
        score -= 2
        why.append(f"các phương pháp chênh nhau {spread:.1f} lần")
        res["notes"].append(f"Các phương pháp chênh nhau lớn (cao/thấp = {spread:.1f} lần).")
    elif spread > v["spread_high"]:
        score -= 1
        why.append(f"các phương pháp chênh nhau {spread:.1f} lần")
    bt = ((forecast or {}).get("backtest") or {}).get("summary", {}).get("net_income_parent") or {}
    ape, nbt = bt.get("median_ape"), bt.get("n", 0)
    if ape is None or nbt < 3:
        score -= 1
        why.append("chưa kiểm định được sai số dự báo LNST của chính mã")
    elif ape > 0.40:
        score -= 2
        why.append(f"dự báo LNST của chính mã sai số trung vị {ape:.0%}")
    elif ape > 0.20:
        score -= 1
        why.append(f"dự báo LNST của chính mã sai số trung vị {ape:.0%}")
    if stale:
        score -= 1
        why.append("BCTC cũ")
    if coverage < v["min_weight_coverage"]:
        score -= 1
        why.append(f"chỉ còn {coverage:.0%} trọng số theo hồ sơ ngành")
    if share_gap is not None and abs(share_gap) > 0.10:
        score -= 1
        why.append(f"số CP hiện hành lệch {share_gap:+.0%} so với số CP tại kỳ BCTC năm dùng làm gốc (chưa có bảng cân "
                   "đối quý mới hơn để biết phần chênh có thu tiền hay không)")
    tv = [x for x in methods_out if x["key"] in ("dcf", "ri") and (x["detail"].get("tv_share") or 0) > v["dcf_max_tv_share"]
          and x["weight"] >= 0.2]
    if tv:
        score -= 1
        why.append("định giá dòng tiền phụ thuộc giá trị cuối kỳ")
        res["notes"].append("DCF/RI: giá trị cuối kỳ chiếm > {:.0f}% tổng giá trị → nhạy với giả định dài hạn."
                            .format(v["dcf_max_tv_share"] * 100))
    if scope_change:
        score -= 1
        why.append("doanh nghiệp vừa đổi phạm vi hợp nhất (số liệu cũ và mới khác cơ sở)")
    if scen_ratio is not None and scen_ratio > v.get("scenario_max_ratio", 99):
        score -= 1
        why.append(f"biên độ kịch bản rộng (Tích cực / Thận trọng = {scen_ratio:.1f} lần)")
    conf = CONF_ORDER[0] if score >= 3 else CONF_ORDER[1] if score == 2 else CONF_ORDER[2]
    applied = []
    for cap, reason in caps:
        if CONF_ORDER.index(cap) > CONF_ORDER.index(conf):
            conf = cap
            applied.append(reason)
    if why or applied:
        res["notes"].append("Độ tin cậy " + conf + ": " + "; ".join(why + [f"trần: {a}" for a in applied]) + ".")
    return conf, {"score": score, "reasons": why, "caps": applied}


def _dividend(wide, shares, price, res, dividends=None, ref=None, dps_factor: float = 1.0) -> float:
    """Cổ tức tiền mặt 12T (VND/cp).
    Ưu tiên CỔ TỨC ĐÃ CÔNG BỐ: tổng cổ tức tiền mặt có ngày GDKHQ trong 12 tháng trước ngày định giá (vd FPT 2.000đ/cp).
    Không có dữ liệu công bố → ước tính cũ: tiền chi cổ tức năm gần nhất ÷ số CP (trả đều ≥ 2/3 năm, ≥ 0,3% thị giá) – cách
    này dễ PHÓNG ĐẠI khi tiền chi trong năm gồm cả đợt cuối năm trước hoặc số CP tăng (ghi rõ trong ghi chú)."""
    from core.dinh_gia import _col
    if isinstance(dividends, pd.DataFrame) and not dividends.empty and {"date", "dps"} <= set(dividends.columns):
        ref = pd.Timestamp(ref) if ref is not None else pd.Timestamp.now().normalize()
        d = dividends[(pd.to_datetime(dividends["date"]) <= ref)]
        last12 = d[pd.to_datetime(d["date"]) > ref - pd.Timedelta(days=365)]
        if not last12.empty:
            dps = float(last12["dps"].sum()) / (dps_factor or 1.0)   # đ/cp lúc chi trả → cơ sở của chuỗi giá đang dùng
            src_txt = dividends.attrs.get("source") if hasattr(dividends, "attrs") else None
            res["dividend_basis"] = (f"Cổ tức tiền mặt đã công bố 12 tháng gần nhất: {dps:,.0f}đ/cp "
                                     f"({len(last12)} đợt, GDKHQ gần nhất {pd.Timestamp(last12['date'].max()):%d/%m/%Y})"
                                     + (f" – nguồn: {src_txt}" if src_txt else ""))
            res["notes"].append(res["dividend_basis"] + ".")
            return dps if dps >= price * 0.003 else 0.0
        if not d.empty:
            res["notes"].append("Không có đợt cổ tức tiền mặt nào trong 12 tháng gần nhất (theo lịch sử công bố) → "
                                "tổng lợi nhuận kỳ vọng = upside giá.")
            res["dividend_basis"] = "Không chia cổ tức tiền mặt trong 12 tháng gần nhất (lịch sử công bố)"
            return 0.0
    dps_s = (_col(wide, "dividends_paid").abs() / shares).dropna().tail(3)
    dps = float(dps_s.iloc[-1]) if len(dps_s) and (dps_s > 0).sum() >= 2 else 0.0
    if dps < price * 0.003:
        dps = 0.0
    if dps <= 0:
        res["notes"].append("Không đủ cơ sở dự phóng cổ tức tiền mặt (chưa trả đều ≥ 2/3 năm gần nhất) → "
                            "tổng lợi nhuận kỳ vọng = upside giá.")
    else:
        res["dividend_basis"] = (f"Ước tính {dps:,.0f}đ/cp = tiền chi cổ tức năm gần nhất ÷ số CP (chưa lấy được lịch sử cổ tức "
                                 "công bố – có thể cao hơn thực tế nếu tiền chi gồm cả đợt của năm trước)")
        res["notes"].append(res["dividend_basis"] + ".")
    return dps


def _forecast_summary(fc: Dict[str, Any]) -> Dict[str, Any]:
    if not fc:
        return {"available": False}
    out = {"available": fc.get("available"), "reason": fc.get("reason"), "model": fc.get("model"),
           "base": fc.get("base"), "scenario_group": fc.get("scenario_group"), "warnings": list(fc.get("warnings") or [])}
    vi = (fc.get("valuation_inputs") or {}).get("base") or {}
    out["base_inputs"] = {k: vi.get(k) for k in ("eps_fwd", "bvps_fwd", "roe_fwd", "ebitda_fwd", "ntm_window_end",
                                                 "fy1_label", "eps_fy1")}
    if fc.get("backtest"):
        out["backtest"] = fc["backtest"].get("summary")
    return out


# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Import chéo (các file import lẫn nhau) – đặt CUỐI file để tránh vòng lặp import; chỉ được dùng bên trong hàm.
# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
from core.phan_tich_co_ban import flatten_columns, order_tabular, ordered_period_columns
from core.phan_tich_co_ban import core_ebit_ebitda, ebit_ebitda
