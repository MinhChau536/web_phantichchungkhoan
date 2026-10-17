"""
core/pipeline.py – gộp từ 1 module (15/10/2026).

MỤC LỤC
  • services/stock_service.py – StockService – điều phối dữ liệu & toàn bộ phân tích cho MỘT mã cổ phiếu.
      hàm/lớp chính: get_repo, StockService, valuation_to_legacy
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: services/stock_service.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
StockService – điều phối dữ liệu & toàn bộ phân tích cho MỘT mã cổ phiếu.

Luồng:
  Giá (DNSE gần nhất + vnstock/Vietstock lịch sử) ─► Kỹ thuật, Động lượng, Rủi ro
  BCTC nhiều nguồn đã chuẩn hóa ─► Bộ tính chỉ số (financial_ratios) ─► Cơ bản, Định giá
  Nhóm ngành ─► Trung vị ngành ─► Định giá tương đối
  Tất cả ─► Điểm cơ hội đầu tư tổng hợp
"""


import logging
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from core import phan_tich_co_ban as fr
from core.phan_tich_co_ban import FundamentalAnalyzer
from core.phan_tich_ky_thuat import MomentumAnalyzer
from core.khuyen_nghi import OpportunityScorer
from core.phan_tich_co_ban import compute_peer_stats
from core.phan_tich_ky_thuat import TechnicalAnalyzer
from core.dinh_gia import ValuationEngine
from core.cau_hinh import settings
from core.du_lieu import DataRepository

logger = logging.getLogger(__name__)
_default_repo: Optional[DataRepository] = None
scorer = OpportunityScorer()


def get_repo() -> DataRepository:
    global _default_repo
    if _default_repo is None:
        _default_repo = DataRepository()
    return _default_repo


class StockService:
    """Full analysis pipeline for a single stock ticker."""

    def __init__(self, symbol: str, days: int = 365, fin_period: str = "year",
                 fin_years: int = 10, repository: Optional[DataRepository] = None, as_of=None):
        """as_of: "định giá tại ngày" – None = dùng giá hiện tại; một ngày (str/date/Timestamp) = mọi dữ liệu
        (giá, chỉ số, BCTC, beta) được cắt về đúng thời điểm đó, không dùng thông tin công bố sau ngày này."""
        self.symbol = symbol.upper().strip()
        self.as_of: Optional[pd.Timestamp] = None
        if as_of is not None and str(as_of).strip():
            d = pd.Timestamp(as_of).normalize()
            if d < pd.Timestamp(datetime.now().date()):
                self.as_of = d
        self.days = days
        self.fin_period = fin_period
        self.fin_years = fin_years
        self.repo = repository or get_repo()
        self._price_df: Optional[pd.DataFrame] = None
        self._index_df: Optional[pd.DataFrame] = None
        self._company_info: Optional[Dict] = None
        self._peer_stats: Optional[Dict] = None
        self._fin: Dict[str, Dict] = {}
        self._fund_cache: Optional[Dict] = None
        self._summary_cache: Dict[str, Dict] = {}
        self._current: Optional[Dict] = None
        self._errors: Dict[str, str] = {}

    # ─────────────────── Data ────────────────────────────────────────────────

    # ── Điểm thời gian (as_of) ──
    def _cut_px(self, df: Optional[pd.DataFrame]) -> pd.DataFrame:
        """Bỏ mọi phiên sau ngày định giá."""
        if df is None or df.empty or self.as_of is None:
            return df if df is not None else pd.DataFrame()
        ts = pd.to_datetime(df["timestamp"] if "timestamp" in df.columns else df.index)
        out = df[(ts <= self.as_of + pd.Timedelta(hours=23, minutes=59)).to_numpy()].copy()
        out.attrs = dict(getattr(df, "attrs", {}))
        return out.reset_index(drop=True) if "timestamp" in out.columns else out

    def _history(self, symbol: str, days: int, force_refresh: bool = False) -> pd.DataFrame:
        if self.as_of is None:
            return self.repo.get_price_history(symbol, days=days, force_refresh=force_refresh)
        return self._cut_px(self.repo.get_price_history(symbol, end_date=str(self.as_of.date()), days=days,
                                                        force_refresh=force_refresh))

    def fin_available(self, key: int, period: str) -> bool:
        """Lọc point-in-time; dùng độ trễ cấu hình khi nguồn chưa có ngày công bố thật."""
        if self.as_of is None:
            return True
        from core.dinh_gia import annual_available
        k = int(key)
        if period == "year" or k % 10 == 0:
            return annual_available(k, self.as_of)
        q_end = pd.Timestamp(year=k // 10, month=3 * (k % 10), day=1) + pd.offsets.MonthEnd(0)
        return self.as_of >= q_end + pd.Timedelta(days=settings.QUARTER_RELEASE_LAG_DAYS)

    def get_price_df(self, force_refresh: bool = False) -> pd.DataFrame:
        if self._price_df is None or force_refresh:
            self.__dict__.pop("_beta_info", None)
            self._price_df = self._history(self.symbol, self.days, force_refresh)
        return self._price_df

    def get_index_df(self) -> pd.DataFrame:
        if self._index_df is None:
            self._index_df = self._history("VNINDEX", self.days)
        return self._index_df

    def get_company_info(self) -> Dict[str, Any]:
        if self._company_info is None:
            self._company_info = self.repo.get_company_info(self.symbol)
        return self._company_info

    def get_current_price(self) -> Optional[Dict[str, Any]]:
        if self._current is None and self.as_of is not None:      # định giá tại ngày: giá đóng cửa phiên ≤ ngày đó
            px = self.get_price_df()
            self._current = ({"symbol": self.symbol, "price": float(px["close"].iloc[-1]),
                              "timestamp": str(pd.Timestamp(px["timestamp"].iloc[-1]).date()),
                              "source": f"Giá đóng cửa (định giá tại ngày {self.as_of:%d/%m/%Y})", "as_of": True}
                             if px is not None and not px.empty else {})
            return self._current or None
        if self._current is None:
            self._current = self.repo.get_current_price(self.symbol)
            if not self._current:
                px = self.get_price_df()
                if not px.empty:
                    self._current = {"symbol": self.symbol, "price": float(px["close"].iloc[-1]),
                                     "timestamp": str(px["timestamp"].iloc[-1]), "source": px["source"].iloc[-1]}
        return self._current

    def _price_vnd(self) -> Optional[float]:
        cur = self.get_current_price()
        return float(cur["price"]) if cur and cur.get("price") else None

    def get_financials(self, period: Optional[str] = None, years: Optional[int] = None) -> Dict[str, Any]:
        period = period or self.fin_period
        key = f"{period}:{years or self.fin_years}"
        if key not in self._fin:
            fin = self.repo.get_financials(self.symbol, period=period, years=years or self.fin_years)
            if self.as_of is not None and isinstance(fin, dict):
                fin = dict(fin)
                data = fin.get("data")
                if isinstance(data, pd.DataFrame) and not data.empty:
                    keep = [self.fin_available(k, period) for k in data.index]
                    fin["data"] = data[keep]
                    src = fin.get("sources")
                    if isinstance(src, pd.DataFrame) and not src.empty:
                        fin["sources"] = src.loc[[i for i in fin["data"].index if i in src.index]]
            self._fin[key] = fin
        return self._fin[key]

    def financial_summary(self, period: Optional[str] = None) -> Dict[str, Any]:
        """Chỉ số tính từ BCTC + định giá tại giá hiện tại + DuPont + F-score + Z-score."""
        period = period or self.fin_period
        if period not in self._summary_cache:
            data = self.get_financials(period).get("data", pd.DataFrame())
            self._summary_cache[period] = fr.summarize(data, period, self._price_vnd(),
                                                       shares_now=self._safe("latest_shares", self.latest_shares, None)) \
                if not data.empty \
                else {"period": period, "ratios": pd.DataFrame(), "table": pd.DataFrame(), "valuation": {},
                      "dupont": pd.DataFrame(), "piotroski": None, "altman": {}, "cagr": {}, "is_bank": False}
        return self._summary_cache[period]

    def get_peer_stats(self) -> Dict[str, Any]:
        if self._peer_stats is None and self.as_of is not None and \
                (pd.Timestamp(datetime.now().date()) - self.as_of).days > 30:
            # Trung vị ngành chỉ có số liệu HIỆN TẠI → không dùng cho ngày định giá đã quá 30 ngày
            self._peer_stats = {"group": None, "n": 0, "reason": "Định giá tại ngày quá khứ (> 30 ngày): không dùng "
                                "trung vị ngành hiện tại để tránh dùng thông tin tương lai."}
        if self._peer_stats is None:
            try:
                self._peer_stats = compute_peer_stats(self.symbol, self.repo.get_financial_ratios)
            except Exception as exc:
                logger.warning("Peer stats failed for %s: %s", self.symbol, exc)
                self._peer_stats = {"group": None, "n": 0, "reason": str(exc)}
        return self._peer_stats

    # ─────────────────── Technical ───────────────────────────────────────────

    def technical_analysis(self) -> Dict[str, Any]:
        df = self.get_price_df()
        if df.empty:
            return {"available": False, "reason": "Không có dữ liệu giá"}
        ta = TechnicalAnalyzer(df)
        enriched_df = ta.compute_all()
        return {"available": True, "data": enriched_df, "signals": ta.get_signals(),
                "score": ta.compute_technical_score(), "provenance": df.attrs.get("provenance", [])}

    # ─────────────────── Fundamental ─────────────────────────────────────────

    def fundamental_analysis(self) -> Dict[str, Any]:
        if self._fund_cache is not None:
            return self._fund_cache
        fin = self.get_financials()
        canonical = fin.get("data", pd.DataFrame())
        if canonical is not None and not canonical.empty:
            fa = FundamentalAnalyzer(None, None, None, symbol=self.symbol, canonical=canonical, period=self.fin_period)
            raw = fin.get("raw", {})
        else:   # dự phòng: đọc bảng thô theo cách cũ
            is_df = self.repo.get_income_statement(self.symbol)
            bs_df = self.repo.get_balance_sheet(self.symbol)
            cf_df = self.repo.get_cash_flow(self.symbol)
            ratio_df = self.repo.get_financial_ratios(self.symbol)
            fa = FundamentalAnalyzer(is_df, bs_df, cf_df, ratio_df, self.symbol)
            raw = {"income_statement": is_df, "balance_sheet": bs_df, "cash_flow": cf_df, "ratios": ratio_df}
        self._fund_cache = {
            "available": canonical is not None and not canonical.empty,
            "metrics": fa.compute_all(),
            "score": fa.compute_fundamental_score(),
            "raw": raw,
            "sources": fin.get("sources"),
            "attempts": fin.get("attempts", []),
        }
        return self._fund_cache

    # ─────────────────── Momentum ─────────────────────────────────────────────

    def momentum_analysis(self) -> Dict[str, Any]:
        price_df = self.get_price_df()
        ma = MomentumAnalyzer(price_df, self.get_index_df())
        return {"available": not price_df.empty, "score": ma.compute_momentum_score()}

    # ─────────────────── Valuation ────────────────────────────────────────────

    def valuation_analysis(self) -> Dict[str, Any]:
        price = self._price_vnd() or 0
        summ = self.financial_summary()
        val = summ.get("valuation") or {}
        ve = ValuationEngine(self.symbol, price, self.repo.get_financial_ratios(self.symbol),
                             peer_stats=self.get_peer_stats(),
                             eps_override=val.get("eps_ttm"), bvps_override=val.get("bvps"))
        inv = self._safe("investment", self.investment_analysis, None) or {}
        hv = inv.get("valuation") or {}
        ml = inv.get("multilayer") or {}
        # 16/10/2026: MỘT điểm Định giá duy nhất trong app = lớp V của khung khuyến nghị (trước đây trụ cột Định giá chấm
        # theo tổng LN kỳ vọng 12T, lớp V chấm theo bội số + biên an toàn + P/E ngành → hai số khác nhau trên cùng trang).
        if ml.get("V") is not None:
            comps = {}
            for r in (ml.get("layers") or {}).get("V") or []:
                comps[r.get("key") or r["name"]] = {"score": None if r["score"] is None else round(r["score"]), "max": 100,
                                                    "value": r.get("value"), "basis": f"trọng số {r['weight']:g}%",
                                                    **({} if r["score"] is not None else {"note": "Không dùng / thiếu dữ liệu"})}
            score = {"score": round(ml["V"]), "method": "multilayer_V", "components": comps,
                     "note": "Cùng điểm lớp Định giá (V) của khung khuyến nghị: 50% bội số so với lịch sử 5 năm & ngành · 30% "
                             "biên an toàn từ đầu thấp khoảng định giá (chỉ khi định giá đủ tin cậy) · 20% P/E xếp hạng % "
                             "trong ngành."}
        else:
            prof = hv.get("profile") or {}
            score = ve.compute_valuation_score(history=hv.get("history"), profile_weights=prof.get("weights_config"),
                                               profile_label=prof.get("label"))
            score["method"] = "relative_multiples"
            score["note"] = ("Chưa chạy được khung khuyến nghị → chấm theo bội số: 50% so với lịch sử 5 năm của doanh nghiệp + "
                             "50% so với trung vị ngành (theo vốn hóa khi có), trọng số P/E–P/B theo hồ sơ ngành. "
                             + (score.get("note") or ""))
        if "relative_valuation" not in score:
            # 16/10/2026: điểm lấy từ lớp V nhưng P/E, P/B hiện tại vẫn cần cho bảng "So sánh với ngành" (PDF) – trước đây
            # thiếu khóa này nên P/E, P/B của mã ra N/A.
            prof = hv.get("profile") or {}
            try:
                ms = ve.compute_valuation_score(history=hv.get("history"), profile_weights=prof.get("weights_config"),
                                                profile_label=prof.get("label"))
                score["relative_valuation"] = ms.get("relative_valuation") or {}
            except Exception as exc:                          # noqa: BLE001
                logger.debug("relative_valuation failed: %s", exc)
                score["relative_valuation"] = {}
            for k in ("pe", "pb"):                             # dự phòng: bội số tính từ BCTC tại giá hiện tại
                if score["relative_valuation"].get(k) is None and val.get(k) is not None:
                    score["relative_valuation"][k] = val.get(k)
        score["multiples_from_statements"] = {k: val.get(k) for k in ("pe", "pb", "ps", "ev_ebitda", "dividend_yield",
                                                                       "market_cap", "enterprise_value", "as_of_period")}
        return {"available": True, "score": score}

    # ─────────────────── Composite Score ─────────────────────────────────────

    def _beta_series(self, symbol: str, own: pd.DataFrame, window: int) -> pd.DataFrame:
        """Chuỗi giá đủ dài cho cửa sổ beta: dùng lại bảng đã tải nếu đủ dài, nếu không thì tải riêng."""
        need = window + 15
        if own is not None and not own.empty and self.days >= need:
            return own
        return self._history(symbol, need)

    def beta_info(self, min_obs: int = 60) -> Dict[str, Any]:
        """Beta kèm kiểm tra độ tin cậy (core/dinh_gia.py). Cửa sổ CỐ ĐỊNH settings.BETA_WINDOW_DAYS ngày lịch,
        tính lùi từ phiên VN-Index cuối cùng ≤ ngày định giá, không phụ thuộc self.days → mọi trang (Phân tích,
        Khuyến nghị, Báo cáo PDF) dùng cùng một beta."""
        if "_beta_info" in self.__dict__:
            return self._beta_info
        from core.dinh_gia import estimate_beta
        window = int(settings.BETA_WINDOW_DAYS)
        try:
            px = self._beta_series(self.symbol, self.get_price_df(), window)
            idx = self._beta_series("VNINDEX", self.get_index_df(), window)
            info = estimate_beta(px, idx, window, min_obs)
        except Exception as exc:
            logger.debug("Beta failed for %s: %s", self.symbol, exc)
            info = {"beta": None, "reliable": False, "warnings": [f"Không tính được beta: {exc}"]}
        if info.get("warnings"):
            logger.info("Beta %s: %s", self.symbol, " | ".join(info["warnings"]))
        self._beta_info = info
        return info

    BETA_SENS_POINTS = (0.8, 1.0, 1.2)

    def _annotate_beta(self, valuation: Dict[str, Any], engine, val_kw: Dict[str, Any]) -> None:
        """Ghi rõ chất lượng beta vào kết quả định giá. Khi beta không đáng tin cậy, mô hình dùng β = 1,0 –
        đây là GIẢ ĐỊNH THAY THẾ: đánh dấu, cảnh báo và kèm độ nhạy giá mục tiêu theo beta."""
        binfo = self.beta_info()
        asum = valuation.setdefault("assumptions", {})
        asum["beta_quality"] = {k: v for k, v in binfo.items() if k != "warnings"}
        notes = valuation.setdefault("notes", [])
        substituted = binfo.get("beta") is None
        asum["beta_substituted"] = substituted
        if not substituted:
            notes.extend(binfo.get("warnings") or [])           # vd sai số chuẩn lớn (chỉ cảnh báo)
            return
        raw = binfo.get("beta_raw")
        reason = "; ".join(binfo.get("warnings") or ["không tính được beta"])
        asum["beta_source"] = "Giả định thay thế β = 1,0 (bình quân thị trường) – beta đo được không đáng tin cậy"
        lo, hi = engine.v["beta_bounds"]
        points = sorted({*self.BETA_SENS_POINTS, *([round(min(max(raw, lo), hi), 2)] if raw is not None else [])})
        sens = []
        if valuation.get("target_12m"):
            for b in points:
                try:
                    alt = valuation if b == 1.0 else engine.value(beta=b, **val_kw)
                except Exception as exc:                       # độ nhạy không được làm hỏng kết quả chính
                    logger.debug("beta sensitivity %s: %s", b, exc)
                    continue
                sens.append({"beta": b, "ke": engine.ke(b), "target_12m": alt.get("target_12m"),
                             "expected_return": alt.get("expected_return"),
                             "is_measured": raw is not None and b == round(min(max(raw, lo), hi), 2),
                             "is_used": b == 1.0})
        valuation["beta_sensitivity"] = sens
        msg = (f"GIẢ ĐỊNH THAY THẾ: beta đo được không đáng tin cậy ({reason}) → Ke tính với β = 1,0 "
               f"(Ke = {engine.ke(1.0) * 100:.1f}%)" + (f"; beta đo được = {raw:.2f} chỉ để tham khảo" if raw is not None else ""))
        notes.insert(0, msg + ".")
        rows = [f"β {r['beta']:.2f} → {r['target_12m']:,.0f}" for r in sens if r.get("target_12m")]
        if rows:
            tg = [r["target_12m"] for r in sens if r.get("target_12m")]
            notes.insert(1, "Độ nhạy giá mục tiêu theo beta: " + "; ".join(rows)
                         + f" (chênh {(max(tg) / min(tg) - 1) * 100:.0f}% giữa cao nhất và thấp nhất).")

    def compute_beta(self, min_obs: int = 60) -> Optional[float]:
        """Beta đáng tin cậy, hoặc None (khi đó mô hình định giá dùng β = 1,0 và ghi cảnh báo – xem beta_info)."""
        return self.beta_info(min_obs).get("beta")

    def compute_opportunity_score(self) -> Dict[str, Any]:
        if not hasattr(self, "_errors"):
            self._errors = {}
        na = {"available": False}
        tech = self._safe("technical", self.technical_analysis, na)
        fund = self._safe("fundamental", self.fundamental_analysis, na)
        mom = self._safe("momentum", self.momentum_analysis, na)
        val = self._safe("valuation", self.valuation_analysis, na)
        pick = lambda sec: sec.get("score", {}).get("score") if sec.get("available") else None  # noqa: E731
        tech_score, fund_score, mom_score, val_score = pick(tech), pick(fund), pick(mom), pick(val)

        price_df = self.get_price_df()
        risk_result: Dict[str, Any] = {"score": None, "components": {}}
        if not price_df.empty:
            daily_ret = price_df["close"].pct_change().dropna()
            vol_30d = float(daily_ret.tail(30).std()) if len(daily_ret) >= 5 else None
            # Góp ý GK (II.4): MDD cùng khung 1 NĂM (250 phiên, đỉnh cũng trong 1 năm) với mục Rủi ro – trước đây lấy toàn bộ
            # lịch sử tải về (~3 năm) nên thẻ điểm ghi −52% trong khi mục Rủi ro ghi −41%.
            c1y = price_df["close"].astype(float).tail(250)
            mdd = float(((c1y / c1y.cummax()) - 1).min())
            de = (fund.get("metrics", {}).get("debt", {}) or {}).get("debt_to_equity")
            risk_result = scorer.compute_risk_score(volatility_30d=vol_30d, max_drawdown=mdd,
                                                    beta=self.compute_beta(), debt_to_equity=de)
        risk_result.setdefault("components", {})
        composite = scorer.compute(tech_score, mom_score, fund_score, val_score, risk_result.get("score"))
        return {"composite": composite,
                "sub_scores": {"technical": tech_score, "momentum": mom_score, "fundamental": fund_score,
                               "valuation": val_score, "risk": risk_result.get("score")},
                "risk_detail": risk_result}

    # ─────────────────── Full Report Data ────────────────────────────────────

    def _safe(self, name: str, fn, default):
        """Chạy một phần phân tích; lỗi ở phần này không làm hỏng các phần khác. Kết quả được ghi nhớ
        trong lượt phân tích (tránh tính lại kỹ thuật/cơ bản/định giá 2 lần khi chấm điểm tổng hợp)."""
        memo = self.__dict__.setdefault("_memo", {})
        if name in memo:
            return memo[name]
        try:
            memo[name] = fn()
            return memo[name]
        except Exception as exc:
            import traceback
            logger.exception("%s failed for %s", name, self.symbol)
            self._errors[name] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            return default

    # ─────────────────── Định giá nhiều phương pháp & khuyến nghị ─────────────

    def get_long_price_df(self, years: int = 6) -> pd.DataFrame:
        """Lịch sử giá dài (để tính P/E, P/B cuối năm trong quá khứ)."""
        try:
            return self._history(self.symbol, 365 * years + 30)
        except Exception as exc:
            logger.debug("long price history failed for %s: %s", self.symbol, exc)
            return pd.DataFrame()

    # ─────────────────── Khuyến nghị đầu tư & giá mục tiêu ─────────────

    def investment_analysis(self, overrides: Optional[Dict[str, Any]] = None, holder: Optional[bool] = None,
                            as_of: Optional[pd.Timestamp] = None) -> Dict[str, Any]:
        """
        Financial Health Score → Risk Assessment → Valuation Engine (12T) → Recommendation Engine.
        Dùng lại: BCTC đã chuẩn hóa (get_financials), bộ tính chỉ số (financial_ratios), beta, trung vị ngành,
        lịch sử giá dài. Không tự tạo dữ liệu: thiếu nguồn → trạng thái "CHƯA ĐỦ CƠ SỞ".
        """
        from core.phan_tich_co_ban import FinancialHealthEngine
        from core.khuyen_nghi import compat_recommendation, explain_valuation
        from core.khuyen_nghi import assess_risk
        from core.dinh_gia import ValuationEngine12M
        from core.cau_hinh import classify_company, load_config

        if as_of is not None and (self.as_of is None or pd.Timestamp(as_of).normalize() != self.as_of):
            return StockService(self.symbol, days=self.days, fin_years=self.fin_years, repository=self.repo,
                                as_of=as_of).investment_analysis(overrides, holder)
        as_of = self.as_of
        cfg = load_config(overrides)
        annual = self.get_financials("year").get("data", pd.DataFrame())
        if annual is not None and not annual.empty:
            annual = annual[[int(k) % 10 == 0 for k in annual.index]]
        summ = self.financial_summary("year") if annual is not None and not annual.empty else {}
        ratios = summ.get("ratios") if summ else None
        price_df = self.get_long_price_df()          # đã cắt về ngày định giá nếu có as_of
        info = self.get_company_info() or {}
        peers = self.get_peer_stats() or {}
        industry = " ".join(str(info.get(k) or "") for k in ("industry", "sector", "icb_name3", "icb_name2"))
        company = classify_company(industry, str(peers.get("group") or ""), bool(summ.get("is_bank")) if summ else False,
                                   symbol=self.symbol)
        cur = self.get_current_price() or {}
        price, price_date = cur.get("price"), cur.get("timestamp")
        shares_info = self.latest_shares(annual)
        shares = shares_info.get("shares")
        tech = self._safe("technical", self.technical_analysis, {"available": False})
        trend = ((tech.get("signals") or {}).get("trend") or {}).get("name") if tech.get("available") else None
        ind_text = f"{industry} {peers.get('group') or ''}"

        health = FinancialHealthEngine(cfg).score(ratios, annual, company)
        risk_kw = dict(summary=summ, price_df=price_df, health=health, industry_text=ind_text, trend=trend,
                       as_of=pd.Timestamp(as_of) if as_of is not None else None, config=cfg)
        risk0 = assess_risk(annual, ratios, company, **risk_kw)
        # Bước 7: dự báo của Forecast Engine (kèm TTM nếu có, backtest chính mã) là đầu vào của định giá
        forecast = self._safe("forecast", lambda: self.forecast_analysis(overrides=overrides),
                              {"available": False, "reason": "Lỗi khi chạy Forecast Engine"})
        engine = ValuationEngine12M(cfg)
        val_kw = dict(forecast=forecast if isinstance(forecast, dict) and forecast.get("available") else None, price=price, price_date=pd.Timestamp(price_date) if price_date is not None else None, wide=annual,
                      ratios=ratios, shares=shares, company=company, peers=peers, price_df=price_df,
                      risk_level=risk0["level"],
                      quarterly=(self._safe("financials_quarter", lambda: self.get_financials("quarter"), {}) or {}).get("data"),
                      dividends=self._safe("dividends", lambda: self.repo.get_dividends(self.symbol)
                                           if hasattr(self.repo, "get_dividends") else None, None))
        beta = self.compute_beta()
        # Hệ số CP đã biết KHÔNG thu tiền (thưởng/cổ tức CP, quy đổi cơ sở giá) → không coi là "lệch số CP" khi chấm độ tin cậy;
        # cổ tức tiền mặt (đ/cp, theo cơ sở lúc chi trả) chia cho hệ số quy đổi cơ sở giá.
        known = float(np.prod([1 + e["ratio"] for e in (shares_info.get("share_events") or [])])) * \
            float(shares_info.get("price_basis_factor") or 1.0)
        val_kw.update(share_factor=known, dps_factor=float(shares_info.get("price_basis_factor") or 1.0),
                      basis_unknown=bool(shares_info.get("price_basis_unknown")))
        valuation = engine.value(beta=beta, **val_kw)
        valuation.setdefault("assumptions", {})["price_basis_factor"] = shares_info.get("price_basis_factor")
        valuation["assumptions"]["price_basis_events"] = shares_info.get("price_basis_events") or []
        valuation["assumptions"]["price_basis_method"] = shares_info.get("price_basis_method")
        valuation.setdefault("assumptions", {})["shares_source"] = shares_info.get("source")
        if shares_info.get("note"):
            valuation.setdefault("notes", []).append(shares_info["note"])
        self._annotate_beta(valuation, engine, val_kw)
        if as_of is not None:
            valuation["as_of"] = str(as_of.date())
            valuation.setdefault("notes", []).insert(0, f"Định giá tại ngày {as_of:%d/%m/%Y}: dùng giá đóng cửa phiên "
                                                        f"{price_date or '—'} và chỉ BCTC đã công bố trước ngày này."
                                                        + (" Không dùng trung vị ngành (chỉ có số liệu hiện tại)."
                                                           if not peers.get("n") and peers.get("reason", "").startswith("Định giá") else ""))
        risk = assess_risk(annual, ratios, company, valuation=valuation, **risk_kw)
        ml = self._safe("multilayer", lambda: self._multilayer(cfg, health, summ, annual, price_df, valuation, peers,
                                                              company, risk, ratios, price), None)
        rec = compat_recommendation(ml, valuation, health, risk)
        return {"multilayer": ml, "forecast": forecast, "symbol": self.symbol, "name": info.get("company_name") or info.get("short_name") or "",
                "industry": industry.strip(), "company": company, "health": health, "valuation": valuation, "risk": risk,
                "recommendation": rec, "explanation": explain_valuation(self.symbol, health, valuation, risk),
                "thesis": _thesis(health, valuation, risk), "config": cfg, "peers": peers,
                "as_of": str(as_of.date()) if as_of is not None else None, "trend": trend,
                "generated_at": datetime.now().isoformat(timespec="seconds")}

    def _multilayer(self, cfg, health, summ, annual, price_df, valuation, peers, company, risk, ratios, price) -> Dict[str, Any]:
        """Khung khuyến nghị đa lớp (15/10/2026): MỘT nhãn duy nhất từ ma trận F × R – core/khuyen_nghi.py."""
        from core.khuyen_nghi import multilayer_recommendation
        prof = (valuation or {}).get("profile") or {}
        snap = (summ or {}).get("valuation") or {}
        ve = ValuationEngine(self.symbol, price or 0, self.repo.get_financial_ratios(self.symbol), peer_stats=peers,
                             eps_override=snap.get("eps_ttm"), bvps_override=snap.get("bvps"))
        multiples = ve.compute_valuation_score(history=(valuation or {}).get("history"),
                                               profile_weights=prof.get("weights_config"), profile_label=prof.get("label"))
        quarterly = (self._safe("financials_quarter", lambda: self.get_financials("quarter"), {}) or {}).get("data")
        universe = self._safe("relative_universe", lambda: self.relative_universe(peers), {}) or {}
        return multilayer_recommendation(health=health, summary=summ, annual=annual, quarterly=quarterly, price_df=price_df,
                                         index_df=self._safe("index_long", lambda: self._history("VNINDEX", max(self.days, 420)), None),
                                         valuation=valuation, multiples=multiples, peers=peers, company=company, risk=risk,
                                         cfg=cfg, ratios=ratios, universe=universe, symbol=self.symbol,
                                         universe_label="VN30 + cùng ngành")

    def relative_universe(self, peers: Optional[Dict[str, Any]] = None) -> Dict[str, pd.DataFrame]:
        """Rổ so sánh cho điểm R: VN30 + các mã cùng ngành (giá 365 ngày, cắt theo ngày định giá nếu có as_of).
        Chỉ cần lịch sử giá (đã có bộ nhớ đệm trong ngày) – lỗi ở một mã không làm hỏng cả rổ."""
        from core.du_lieu import BASKETS
        vn30 = next((v for k, v in BASKETS.items() if "VN30" in k), [])
        syms = list(dict.fromkeys([s for s in vn30] + list((peers or {}).get("peers") or [])))
        syms = [s for s in syms if s != self.symbol]
        # Giá đến PHIÊN TRƯỚC (không ghép nến trong phiên) và 365 ngày (nằm trọn trong đoạn DNSE → không tốn lượt vnstock)
        end = (self.as_of if self.as_of is not None else pd.Timestamp(datetime.now().date()) - pd.Timedelta(days=1))
        end_s = str(pd.Timestamp(end).date())
        # Nhớ theo (mã, ngày cuối) trên chính repository: giá đến hôm qua không đổi → phân tích mã thứ 2, 3… không tải lại.
        memo = getattr(self.repo, "_universe_px", None)
        if memo is None:
            memo = {}
            try:
                setattr(self.repo, "_universe_px", memo)
            except Exception:                              # noqa: BLE001 – repo không cho gắn thuộc tính
                pass

        def load(s):
            if (s, end_s) in memo:
                return s, memo[(s, end_s)]
            try:
                try:                                         # chỉ DNSE + CSDL, không tốn lượt vnstock
                    df = self.repo.get_price_history(s, end_date=end_s, days=365, recent_only=True)
                except TypeError:                             # repository khác (kiểm thử) chưa có tham số này
                    df = self.repo.get_price_history(s, end_date=end_s, days=365)
                df = self._cut_px(df) if self.as_of is not None else df
            except Exception as exc:                      # noqa: BLE001 – bỏ qua mã lỗi
                logger.debug("universe price %s failed: %s", s, exc)
                return s, None
            if df is not None and not df.empty:
                memo[(s, end_s)] = df
            return s, df

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as ex:        # ~40 mã: tải song song (4 luồng – nhẹ cho DNSE)
            res = list(ex.map(load, syms))
        return {s: df for s, df in res if df is not None and not df.empty}

    def latest_shares(self, annual: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Số CP dùng để quy đổi giá trị về MỖI CỔ PHIẾU – phải cùng cơ sở với thị giá hiện hành (bước 8).

        Lỗi đã xác nhận: trước đây dùng số CP của BCTC NĂM gần nhất. Sau khi chia thưởng/phát hành trong năm (vd FPT:
        1.703.507.121 CP cuối 2025 → 1.885.727.648 CP quý 2/2026 theo Vietcap), DCF/EV/EBITDA/cổ tức mỗi CP bị phóng đại
        so với thị giá (thị giá đã ở cơ sở số CP mới). Nay ưu tiên số CP lưu hành của QUÝ gần nhất đã công bố (≤ ngày
        định giá, cùng bộ lọc point-in-time), nếu không có mới dùng BCTC năm."""
        if annual is None:
            annual = self.get_financials("year").get("data", pd.DataFrame())
        out: Dict[str, Any] = {"shares": None, "source": None}
        if annual is not None and not annual.empty:
            sh = fr.shares_series(annual[[int(k) % 10 == 0 for k in annual.index]]).dropna()
            if not sh.empty:
                out.update(shares=float(sh.iloc[-1]), source=f"BCTC năm {int(sh.index[-1]) // 10}", key=int(sh.index[-1]))
        try:
            q = (self._safe("financials_quarter", lambda: self.get_financials("quarter"), {}) or {}).get("data")
        except Exception:                                   # không có số quý → giữ số CP năm
            q = None
        if q is not None and not q.empty and "shares_outstanding" in q.columns:
            qs = pd.to_numeric(q["shares_outstanding"], errors="coerce")
            qs = qs[(qs > 0).to_numpy() & np.array([int(k) % 10 > 0 for k in qs.index], dtype=bool)].dropna()
            if not qs.empty and (out.get("key") is None or int(qs.index[-1]) > out["key"]):
                k = int(qs.index[-1])
                old = out.get("shares")
                out.update(shares=float(qs.iloc[-1]), source=f"Số CP lưu hành quý {k % 10}/{k // 10}", key=k)
                if old and abs(out["shares"] / old - 1) > 0.01:
                    out["note"] = (f"Số CP dùng để định giá: {out['shares']:,.0f} ({out['source']}), khác {out['shares'] / old - 1:+.1%} "
                                   f"so với BCTC năm ({old:,.0f}) – dùng số mới để cùng cơ sở với thị giá hiện hành.")
        # Số CP lưu hành HIỆN HÀNH theo thông tin niêm yết (vnstock) – phản ánh chia thưởng/phát hành SAU kỳ BCTC gần nhất
        # (vd FPT phát hành 21/9/2026 sau BCTC Q2/2026). Chỉ dùng khi định giá ở hiện tại (thông tin niêm yết là số hôm nay).
        recent = self.as_of is None or (pd.Timestamp(datetime.now().date()) - self.as_of).days <= 30
        if recent:
            info = self._safe("company_info", self.get_company_info, {}) or {}
            try:
                live = float(info.get("issue_share") or 0)
            except (TypeError, ValueError):
                live = 0.0
            base = out.get("shares")
            if live > 0 and (base is None or 0.5 < live / base < 2.0):
                prev_src = out.get("source")
                out.update(shares=live, source="Số CP niêm yết hiện hành", key=None, base_date=pd.Timestamp.now().normalize(),
                           listed_basis=True)
                if base and abs(live / base - 1) > 0.01:
                    out["note"] = (f"Số CP niêm yết hiện hành {live:,.0f} khác {live / base - 1:+.1%} so với {prev_src} "
                                   f"({base:,.0f}) → dùng số hiện hành để cùng cơ sở với thị giá.")
        # Cổ phiếu thưởng / cổ tức bằng cổ phiếu đã qua ngày GDKHQ nhưng CHƯA có trong số CP gốc (vd FPT thưởng 10%, GDKHQ
        # 21/9/2026, chưa niêm yết bổ sung): thị giá đã điều chỉnh giảm theo quyền → số CP phải nhân (1 + tỷ lệ).
        out = self._apply_share_events(out)
        if not recent:
            out = self._apply_price_basis(out)
        return out

    def _shares_now_basis(self, events_df) -> Dict[str, Any]:
        """Số CP HIỆN HÀNH (cơ sở của chuỗi giá đã điều chỉnh về hôm nay): số CP niêm yết, nếu không có thì số CP lưu hành
        quý gần nhất (KHÔNG lọc theo as_of – chỉ dùng làm đơn vị quy đổi), cộng các đợt thưởng/cổ tức CP đã qua GDKHQ
        nhưng chưa có trong số đó."""
        from core.nguon_du_lieu import parse_share_events
        today = pd.Timestamp.now().normalize()
        bonus = parse_share_events(events_df)
        info = self._safe("company_info", self.get_company_info, {}) or {}
        try:
            live = float(info.get("issue_share") or 0)
        except (TypeError, ValueError):
            live = 0.0
        if live > 0:
            add = [e for e in bonus if e["date"] <= today and (e.get("listed") is None or e["listed"] > today)]
            return {"shares": live * float(np.prod([1 + e["ratio"] for e in add])), "source": "số CP niêm yết hiện hành",
                    "added": add}
        try:
            q = (self.repo.get_financials(self.symbol, period="quarter", years=2) or {}).get("data")
        except Exception:                                   # noqa: BLE001
            q = None
        if q is None or q.empty:
            return {}
        # số CP lưu hành; thiếu (thường gặp ở BCTC ngân hàng) → vốn điều lệ ÷ mệnh giá 10.000đ
        qs = pd.to_numeric(fr.shares_series(q), errors="coerce")
        qs = qs[(qs > 0).to_numpy() & np.array([int(k) % 10 > 0 for k in qs.index], dtype=bool)].dropna()
        if qs.empty:
            return {}
        k = int(qs.index[-1])
        q_end = pd.Timestamp(year=k // 10, month=3 * (k % 10), day=1) + pd.offsets.MonthEnd(0)
        add = [e for e in bonus if q_end < e["date"] <= today]
        return {"shares": float(qs.iloc[-1]) * float(np.prod([1 + e["ratio"] for e in add])),
                "source": f"số CP lưu hành quý {k % 10}/{k // 10}", "added": add}

    def _apply_price_basis(self, out: Dict[str, Any]) -> Dict[str, Any]:
        """Định giá tại ngày QUÁ KHỨ (as_of): chuỗi giá của nguồn đã được điều chỉnh NGƯỢC theo các đợt chia thưởng /
        cổ tức bằng CP xảy ra SAU as_of (vd giá FPT 06/2023 chỉ còn ~48.000đ thay vì giá giao dịch thật) → số CP phải ở
        CÙNG cơ sở với giá, nếu không giá trị/CP (DCF, RI, cổ tức…) bị phóng đại và bội số lịch sử bị thu nhỏ.

        Cách tính (15/10/2026, không dựa vào số CP từng kỳ trong BCTC vì có nguồn đã quy đổi sẵn về hiện tại):
          số CP theo cơ sở giá tại T = số CP hiện hành ÷ (các đợt phát hành CÓ thu tiền sau T – giá không điều chỉnh theo)
                                      ÷ (các đợt thưởng sau T mà chuỗi giá còn bước nhảy – nguồn chưa điều chỉnh).
        Chỉ là quy đổi ĐƠN VỊ (giá đã chứa sẵn thông tin này), không đưa số liệu kinh doanh sau as_of vào mô hình.
        Sai lệch còn lại: phần nguồn điều chỉnh giá theo cổ tức tiền mặt (vài %/năm)."""
        if not out.get("shares") or self.as_of is None:
            return out
        from core.nguon_du_lieu import parse_paid_share_events, parse_share_events
        T, today = self.as_of, pd.Timestamp.now().normalize()
        ev = self._safe("company_events", lambda: self.repo.get_company_events(self.symbol), None)
        now = self._shares_now_basis(ev)
        if not now.get("shares"):
            # Không quy đổi được → giá trị/CP có thể lệch nhiều lần (vd MBB, HDB trong backtest: P/E chỉ ~3 lần) →
            # đánh dấu để định giá hạ độ tin cậy xuống "Thấp" thay vì đưa ra khuyến nghị trên số CP sai cơ sở.
            out.update(price_basis_factor=1.0, price_basis_method="không có số CP hiện hành → giữ số CP tại ngày định giá",
                       price_basis_events=[], price_basis_unknown=True)
            return out
        S, steps = now["shares"], [f"{now['source']} {now['shares']:,.0f}"]
        paid = [e for e in parse_paid_share_events(ev) if T < e["date"] <= today]
        if paid:
            S /= float(np.prod([1 + e["ratio"] for e in paid]))
            steps.append(f"÷ {len(paid)} đợt phát hành có thu tiền sau T")
        try:
            full = self.repo.get_price_history(self.symbol, start_date=str((T - pd.Timedelta(days=20)).date()),
                                               end_date=str(today.date()))
        except Exception:                                   # noqa: BLE001
            full = None
        unadj = []
        if full is not None and not full.empty and {"open", "close"} <= set(full.columns):
            full = full.sort_values("timestamp").reset_index(drop=True)
            ts = pd.to_datetime(full["timestamp"])
            for e in parse_share_events(ev):
                if not (T < e["date"] <= today) or e["ratio"] < 0.05:
                    continue
                i = int(np.searchsorted(ts.values, np.datetime64(e["date"])))
                if 0 < i < len(full):
                    jump = float(full["open"].iloc[i]) / float(full["close"].iloc[i - 1]) - 1
                    if jump < -e["ratio"] / (1 + e["ratio"]) / 2:
                        unadj.append(e)              # chuỗi giá còn bước nhảy → giá trước ngày này là giá chưa điều chỉnh
            if unadj:
                S /= float(np.prod([1 + e["ratio"] for e in unadj]))
                steps.append(f"÷ {len(unadj)} đợt thưởng nguồn giá chưa điều chỉnh")
            # app tự điều chỉnh bước nhảy khi tải đến hôm nay nhưng chuỗi cắt tại T chưa có → chuỗi cắt là giá thật
            try:
                c_full = float(full.loc[(ts <= T + pd.Timedelta(hours=23, minutes=59)).to_numpy(), "close"].iloc[-1])
                c_cut = float(self.get_price_df()["close"].iloc[-1])
                adj = [a for a in (full.attrs.get("corporate_action_adjustments") or []) if pd.Timestamp(a.get("date")) > T]
                k_after = float(np.prod([float(a.get("factor") or 1.0) for a in adj])) if adj else 1.0
                r = c_full / c_cut if c_full > 0 and c_cut > 0 else 1.0
                if abs(r - 1) > 0.005 and adj and abs(r / k_after - 1) < 0.03:
                    S *= r
                    steps.append(f"× {r:.3f} (chuỗi cắt tại T chưa điều chỉnh)")
            except (IndexError, KeyError, TypeError, ValueError):
                pass
        cash = self._cash_dividend_basis(ev, full, unadj) if full is not None and not full.empty else {"c": 1.0}
        if cash.get("c") and cash["c"] < 0.999:
            S /= cash["c"]
            steps.append(f"÷ {cash['c']:.3f} ({cash['n']} {'năm cổ tức tiền mặt ước tính từ LCTT' if cash.get('from_cashflow') else 'đợt cổ tức tiền mặt'} sau T đã trừ vào giá)")
        old = float(out["shares"])
        f = S / old
        out["price_basis_events"] = [{"date": str(e["date"].date()), "ratio": e["ratio"], "title": e.get("title")}
                                     for e in paid + unadj]
        if not (0.8 <= f <= 8):
            out.update(price_basis_factor=1.0, price_basis_method=f"bỏ qua (hệ số {f:.2f} bất thường)")
            return out
        out["price_basis_factor"] = f
        out["price_basis_method"] = "; ".join(steps)
        if abs(f - 1) <= 0.005:
            return out
        out["shares"] = S
        out["source"] = f"{out.get('source')} → quy về cơ sở giá đã điều chỉnh ({'; '.join(steps)})"
        out["note"] = ((out.get("note") + " ") if out.get("note") else "") + (
            f"Định giá tại ngày quá khứ {T:%d/%m/%Y}: chuỗi giá đã điều chỉnh theo các đợt chia CP sau ngày này → dùng "
            f"{S:,.0f} CP ({'; '.join(steps)}) thay cho {old:,.0f} CP để cùng cơ sở với giá.")
        return out

    def _cash_dividend_basis(self, ev, full: pd.DataFrame, unadj) -> Dict[str, Any]:
        """Chuỗi giá của nguồn còn trừ NGƯỢC cổ tức TIỀN MẶT sau T (giá quá khứ × (1 − cổ tức / giá trước GDKHQ) cho mỗi
        đợt) → giá tại T thấp hơn giá giao dịch thật. Bội số (P/E, P/B) không bị ảnh hưởng nhiều vì bội số lịch sử cũng
        tính trên giá đã điều chỉnh, nhưng DCF/RI/DDM so giá trị theo số liệu thật với giá bị hạ → upside bị thổi phồng.
        Trả về c = Π(1 − d/giá thật trước GDKHQ) của các đợt sau T mà chuỗi giá KHÔNG còn bước giảm tương ứng
        (đã điều chỉnh). Giá thật trước GDKHQ suy ngược từ giá đã điều chỉnh, đi từ đợt gần nhất về T."""
        v = self._cfg_valuation()
        if not v.get("backtest_cash_dividend_basis", True) or self.as_of is None:
            return {"c": 1.0, "n": 0}
        from core.nguon_du_lieu import parse_cash_dividend_events, parse_share_events
        T, today = self.as_of, pd.Timestamp.now().normalize()
        frames = []
        try:
            d1 = self.repo.get_dividends(self.symbol) if hasattr(self.repo, "get_dividends") else None
            if isinstance(d1, pd.DataFrame) and not d1.empty:
                frames.append(d1[["date", "dps"]])
        except Exception:                                   # noqa: BLE001
            pass
        d2 = parse_cash_dividend_events(ev)
        if not d2.empty:
            frames.append(d2[["date", "dps"]])
        bctc = False
        recs = pd.concat(frames) if frames else pd.DataFrame(columns=["date", "dps"])
        if recs.empty or not (pd.to_datetime(recs["date"], errors="coerce") > T).any():
            # Không có lịch sử cổ tức sau T (nguồn sự kiện trống/bị cắt – vd VNM, SAB) → ước tính từ LCTT năm:
            # cổ tức đã trả trong năm ÷ số CP năm đó, coi như chi giữa năm (01/7). Kiểm chứng: giá VNM 30/9/2025 trên
            # chuỗi nguồn 55.500đ so với giá giao dịch ~60.000đ ⇒ nguồn có trừ cổ tức tiền mặt vào giá quá khứ.
            est = self._dividends_from_cashflow(T, today)
            if not est.empty:
                frames, bctc = [est], True
        if not frames:
            return {"c": 1.0, "n": 0}
        divs = pd.concat(frames)
        divs["date"] = pd.to_datetime(divs["date"], errors="coerce").dt.normalize()
        divs = divs.dropna().sort_values("date")
        divs = divs[(divs["date"] > T) & (divs["date"] <= today) & (divs["dps"] > 0)]
        uniq = []                                            # gộp cùng một đợt từ nhiều nguồn (lệch ≤ 7 ngày)
        for _, r in divs.iterrows():
            if not uniq or (r["date"] - uniq[-1][0]).days > 7:
                uniq.append((r["date"], float(r["dps"])))
        skip = {e["date"] for e in unadj}
        evs = [(d, "cash", x) for d, x in uniq] + [(e["date"], "bonus", e["ratio"]) for e in parse_share_events(ev)
                                                    if T < e["date"] <= today and e["date"] not in skip]
        ts = pd.to_datetime(full["timestamp"]).to_numpy()
        A, c, n = 1.0, 1.0, 0
        for d, kind, x in sorted(evs, key=lambda z: z[0], reverse=True):
            if kind == "bonus":
                A /= 1 + x
                continue
            i = int(np.searchsorted(ts, np.datetime64(d)))
            if not (0 < i < len(full)):
                continue
            p_prev_adj = float(full["close"].iloc[i - 1])
            p_nom = p_prev_adj / A + x                       # giá thật phiên trước GDKHQ (trước khi trừ đợt này)
            if p_nom <= x:
                continue
            yld = x / p_nom
            jump = float(full["open"].iloc[i]) / p_prev_adj - 1 if "open" in full.columns else 0.0
            if not bctc and yld >= 0.03 and jump < -0.6 * yld:
                continue                                     # chuỗi giá còn bước giảm đúng bằng cổ tức → nguồn chưa trừ đợt này
            A *= 1 - yld
            c *= 1 - yld
            n += 1
        return {"c": c, "n": n, "from_cashflow": bctc}

    def _dividends_from_cashflow(self, T: pd.Timestamp, today: pd.Timestamp) -> pd.DataFrame:
        """Cổ tức tiền mặt/CP theo năm từ LCTT (dividends_paid ÷ số CP năm đó), mốc chi 01/7; năm chứa T chỉ tính phần
        sau T. Chỉ dùng để quy đổi đơn vị giá trong định giá ngày quá khứ (không đưa vào mô hình)."""
        try:
            a = (self.repo.get_financials(self.symbol, period="year") or {}).get("data")
        except Exception:                                   # noqa: BLE001
            a = None
        if a is None or a.empty or "dividends_paid" not in a.columns:
            return pd.DataFrame(columns=["date", "dps"])
        sh = fr.shares_series(a)
        rows = []
        for k in a.index:
            if int(k) % 10:
                continue
            y = int(k) // 10
            paid, n = pd.to_numeric(a.loc[k, "dividends_paid"], errors="coerce"), pd.to_numeric(sh.get(k), errors="coerce")
            if pd.isna(paid) or pd.isna(n) or n <= 0 or paid == 0:
                continue
            start, end = pd.Timestamp(year=y, month=1, day=1), pd.Timestamp(year=y, month=12, day=31)
            if end <= T or start > today:
                continue
            frac = min(1.0, max(0.0, (end - max(T, start)).days / 365.0))
            d = pd.Timestamp(year=y, month=7, day=1)
            d = d if d > T else T + pd.Timedelta(days=1)
            if d <= today:
                rows.append({"date": d, "dps": abs(float(paid)) / float(n) * frac, "y": y,
                             "full": abs(float(paid)) / float(n)})
        # sau năm tài chính gần nhất đến hôm nay (chưa có BCTC năm) → giả định cùng mức chi trả năm gần nhất, theo thời gian
        last = [r for r in rows if r["y"] == max((r["y"] for r in rows), default=None)]
        if last:
            y0 = last[0]["y"]
            start = max(T, pd.Timestamp(year=y0 + 1, month=1, day=1))
            if start < today:
                frac = (today - start).days / 365.0
                rows.append({"date": start + (today - start) / 2, "dps": last[0]["full"] * frac, "y": y0 + 1, "full": None})
        return pd.DataFrame(rows, columns=["date", "dps"])

    def _cfg_valuation(self) -> Dict[str, Any]:
        from core.cau_hinh import load_config
        return load_config().get("valuation", {})

    def _apply_share_events(self, out: Dict[str, Any]) -> Dict[str, Any]:
        if not out.get("shares"):
            return out
        try:
            from core.nguon_du_lieu import parse_share_events
            events = parse_share_events(self._safe("company_events", lambda: self.repo.get_company_events(self.symbol), None))
        except Exception:
            return out
        if not events:
            return out
        ref = self.as_of if self.as_of is not None else pd.Timestamp.now().normalize()
        if out.get("listed_basis"):
            base_date = None                        # số CP niêm yết: thiếu các đợt CHƯA niêm yết bổ sung
        elif out.get("key"):
            k = int(out["key"])
            base_date = (pd.Timestamp(year=k // 10, month=12, day=31) if k % 10 == 0
                         else pd.Timestamp(year=k // 10, month=3 * (k % 10), day=1) + pd.offsets.MonthEnd(0))
        else:
            return out
        applied = []
        for e in events:
            if e["date"] > ref:
                continue
            if base_date is not None and e["date"] <= base_date:
                continue
            if base_date is None and e.get("listed") is not None and e["listed"] <= ref:
                continue                            # đã niêm yết bổ sung → đã nằm trong số CP niêm yết
            applied.append(e)
        if not applied:
            return out
        f = float(np.prod([1 + e["ratio"] for e in applied]))
        old = out["shares"]
        out["shares"] = old * f
        txt = "; ".join(f"{e['title'] or 'thưởng/cổ tức bằng CP'} (GDKHQ {e['date']:%d/%m/%Y}, tỷ lệ {e['ratio']:.0%})"
                        for e in applied)
        out["source"] = f"{out.get('source')} × {f:.3f} (đợt chia CP sau ngày chốt số CP)"
        out["note"] = ((out.get("note") + " ") if out.get("note") else "") + (
            f"Đã cộng {txt}: {old:,.0f} → {out['shares']:,.0f} CP, cùng cơ sở với thị giá đã điều chỉnh theo quyền.")
        out["share_events"] = applied
        return out

    def forecast_analysis(self, include_backtest: bool = True,
                          overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dự báo tài chính NTM & 3–5 năm (core/du_phong.py) – chỉ dùng dữ liệu công bố trước
        ngày định giá (as_of). KHÔNG đưa vào Valuation Engine (bước định giá chưa thay đổi)."""
        from core.du_phong import FinancialForecaster, backtest_forecast
        from core.cau_hinh import classify_company, load_config
        cfg = load_config(overrides)
        annual = self.get_financials("year").get("data", pd.DataFrame())
        if annual is None or annual.empty:
            return {"available": False, "reason": "Không có BCTC năm."}
        annual = annual[[int(k) % 10 == 0 for k in annual.index]]
        qres = self._safe("financials_quarter", lambda: self.get_financials("quarter"), {}) or {}
        quarterly = qres.get("data")
        basis = qres.get("quarter_basis") or {}
        flags = [v.get("basis") for src in basis.values() for v in src.values()]
        q_ok = bool(flags) and all(b == "discrete" for b in flags)     # không có nhật ký dạng số → không dùng TTM
        info = self.get_company_info() or {}
        peers = self.get_peer_stats() or {}
        industry = " ".join(str(info.get(k) or "") for k in ("industry", "sector", "icb_name3", "icb_name2"))
        company = classify_company(industry, str(peers.get("group") or ""), bool(fr.is_bank(annual)), symbol=self.symbol)
        shares = self.latest_shares(annual).get("shares")
        as_of = self.as_of if self.as_of is not None else pd.Timestamp(datetime.now().date())
        out = FinancialForecaster(cfg).forecast(annual=annual, quarterly=quarterly, shares=shares, company=company,
                                                as_of=as_of, quarter_basis_ok=q_ok)
        out["quarter_basis"] = basis
        if include_backtest and out.get("available") and shares:
            from core.dinh_gia import annual_available
            pit = annual[[annual_available(k, as_of) for k in annual.index]]
            bt = backtest_forecast(pit, shares, company, config=cfg)
            out["backtest"] = {"summary": bt["summary"],
                               "rows": bt["rows"].to_dict("records") if not bt["rows"].empty else [],
                               "note": "Dự báo 1 năm tới từ dữ liệu đến năm trước, so với số thực tế (cùng số CP hiện tại)."}
            names = {"revenue": "doanh thu", "total_operating_income": "tổng thu nhập hoạt động",
                     "net_income_parent": "LNST cổ đông mẹ"}
            for var, sm in bt["summary"].items():
                if sm["n"] >= 3:
                    out["warnings"].append(
                        f"Sai số dự báo 1 năm lịch sử của {names.get(var, var)}: trung vị {sm['median_ape']:.0%}, "
                        f"bình quân {sm['mape']:.0%} ({sm['n']} năm); số thực tế nằm trong khoảng Bear–Bull "
                        f"{sm['coverage']:.0%} số năm" + (" → khoảng kịch bản HẸP hơn sai số thực tế, cần thận trọng."
                                                           if sm["coverage"] < 0.5 else "."))
        return out

    def investment_compat(self) -> Dict[str, Any]:
        """Kết quả 12T ở dạng khóa cũ của 'fair_value' (để trang phân tích & PDF hiện tại dùng tiếp)."""
        inv = self._safe("investment", self.investment_analysis, None)
        if not inv:
            return {"available": False, "notes": ["Không chạy được mô hình định giá 12 tháng."]}
        return valuation_to_legacy(inv["valuation"])

    def _recommendation_compat(self) -> Dict[str, Any]:
        inv = self._safe("investment", self.investment_analysis, None)
        if not inv:
            # Không rơi về hệ thống cũ (fair_value + ngưỡng ±15%): khuyến nghị chỉ đến từ mô hình 12 tháng
            from core.khuyen_nghi import not_enough_basis
            return not_enough_basis("Không chạy được mô hình định giá & khuyến nghị 12 tháng "
                                    "(xem chi tiết lỗi ở mục Nhật ký) → chưa đủ cơ sở khuyến nghị.")
        rec = dict(inv["recommendation"])
        rec["rating"] = rec["label"]
        return rec

    def company_profile(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for key, fn in (("shareholders", self.repo.get_shareholders), ("officers", self.repo.get_officers),
                        ("events", self.repo.get_company_events)):
            try:
                df = fn(self.symbol)
                out[key] = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
            except Exception:
                out[key] = pd.DataFrame()
        return out

    def full_analysis(self) -> Dict[str, Any]:
        self._errors: Dict[str, str] = {}
        self._memo = {}
        na = lambda reason="Lỗi khi xử lý dữ liệu": {"available": False, "reason": reason}  # noqa: E731
        fin = self._safe("financials", self.get_financials, {})
        return {
            "symbol": self.symbol,
            "timestamp": datetime.now().isoformat(),
            "as_of": str(self.as_of.date()) if self.as_of is not None else None,
            "company_info": self._safe("company_info", self.get_company_info, {}) or {},
            "current_price": self._safe("current_price", self.get_current_price, None),
            "technical": self._safe("technical", self.technical_analysis, na()),
            "fundamental": self._safe("fundamental", self.fundamental_analysis, na()),
            "momentum": self._safe("momentum", self.momentum_analysis, na()),
            "valuation": self._safe("valuation", self.valuation_analysis, na()),
            "opportunity_score": self._safe("opportunity_score", self.compute_opportunity_score,
                                            {"composite": {}, "sub_scores": {}}),
            "peers": self._safe("peers", self.get_peer_stats, {}),
            "financials": {"data": fin.get("data"), "sources": fin.get("sources"),
                           "period": fin.get("period"), "attempts": fin.get("attempts", [])},
            "financial_summary": self._safe("financial_summary", self.financial_summary, {}),
            # Góp ý GK (II.3): số liệu QUÝ để báo cáo kỳ năm vẫn có bảng "cập nhật quý gần nhất" (Forecast Engine đã dùng)
            "financials_quarter": (self._safe("financials_quarter", lambda: self.get_financials("quarter"), {}) or {}).get("data")
            if self.fin_period != "quarter" else None,
            "index_history": self._safe("index_history", self.get_index_df, None),
            "investment": self._safe("investment", self.investment_analysis, None),
            "fair_value": self._safe("fair_value_12m", self.investment_compat, {"available": False}),
            "recommendation": self._safe("recommendation_12m", self._recommendation_compat, {}),
            "company_profile": self._safe("company_profile", self.company_profile, {}),
            "errors": dict(self._errors),
        }


def valuation_to_legacy(v: Dict[str, Any]) -> Dict[str, Any]:
    """Ánh xạ kết quả ValuationEngine12M sang cấu trúc 'fair_value' cũ (thêm khóa mới, không bỏ khóa cũ)."""
    out = dict(v)
    out["available"] = bool(v.get("available"))
    out["fair_value"] = v.get("target_12m")
    for m in out.get("methods", []):
        m.setdefault("group", m.get("key"))
    hist = dict(v.get("history") or {})
    for k in ("pe", "pb"):
        vals = list((hist.get(k) or {}).values())
        hist[f"{k}_median"] = float(pd.Series(vals).median()) if len(vals) >= 3 else None
    out["history"] = hist
    out["model_engine"] = v.get("model")          # 'hybrid' (bước 7) hoặc 'legacy'
    out["model"] = "12m"
    return out


def _thesis(health: Dict[str, Any], valuation: Dict[str, Any], risk: Dict[str, Any]) -> Dict[str, list]:
    """Luận điểm đầu tư rút ra từ điểm số thật (điểm mạnh ≥ 75, điểm yếu < 40)."""
    pos, neg = [], []
    for g in health.get("groups", []):
        for m in g.get("metrics", []):
            if m.get("score") is None:
                continue
            txt = f"{m['label']}: {m['display']}"
            if m["score"] >= 75:
                pos.append(txt)
            elif m["score"] < 40:
                neg.append(txt)
    if valuation.get("upside") is not None:
        (pos if valuation["upside"] > 0 else neg).append(
            f"Giá mục tiêu {valuation['target_12m']:,.0f} ({valuation['upside']:+.1f}% so với thị giá)")
    neg += [i["text"] for i in risk.get("items", []) if i["severity"] in ("Nghiêm trọng", "Cao")][:3]
    return {"positives": pos[:6], "negatives": neg[:6]}
