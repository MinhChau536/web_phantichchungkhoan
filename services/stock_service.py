"""
StockService – điều phối dữ liệu & toàn bộ phân tích cho MỘT mã cổ phiếu.

Luồng:
  Giá (DNSE gần nhất + vnstock/Vietstock lịch sử) ─► Kỹ thuật, Động lượng, Rủi ro
  BCTC nhiều nguồn đã chuẩn hóa ─► Bộ tính chỉ số (financial_ratios) ─► Cơ bản, Định giá
  Nhóm ngành ─► Trung vị ngành ─► Định giá tương đối
  Tất cả ─► Điểm cơ hội đầu tư tổng hợp
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd

from analytics import financial_ratios as fr
from analytics.fundamental import FundamentalAnalyzer
from analytics.momentum import MomentumAnalyzer
from analytics.opportunity_score import OpportunityScorer
from analytics.peers import compute_peer_stats
from analytics.technical import TechnicalAnalyzer
from analytics.valuation import ValuationEngine
from data.data_repository import DataRepository

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
        """BCTC năm y coi như công bố từ 1/4/(y+1); BCTC quý coi như công bố 45 ngày sau khi kết thúc quý."""
        if self.as_of is None:
            return True
        from analytics.valuation_engine import annual_available
        k = int(key)
        if period == "year" or k % 10 == 0:
            return annual_available(k, self.as_of)
        q_end = pd.Timestamp(year=k // 10, month=3 * (k % 10), day=1) + pd.offsets.MonthEnd(0)
        return self.as_of >= q_end + pd.Timedelta(days=45)

    def get_price_df(self, force_refresh: bool = False) -> pd.DataFrame:
        if self._price_df is None or force_refresh:
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
            self._summary_cache[period] = fr.summarize(data, period, self._price_vnd()) if not data.empty \
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
        score = ve.compute_valuation_score()
        score["multiples_from_statements"] = {k: val.get(k) for k in ("pe", "pb", "ps", "ev_ebitda", "dividend_yield",
                                                                       "market_cap", "enterprise_value", "as_of_period")}
        return {"available": True, "score": score}

    # ─────────────────── Composite Score ─────────────────────────────────────

    def compute_beta(self, min_obs: int = 60) -> Optional[float]:
        """Beta = Cov(R_cp, R_VNIndex) / Var(R_VNIndex) trên lợi nhuận ngày cùng phiên."""
        try:
            px, idx = self.get_price_df(), self.get_index_df()
            if px.empty or idx.empty:
                return None
            s = px.set_index(pd.to_datetime(px["timestamp"]))["close"].pct_change()
            m = idx.set_index(pd.to_datetime(idx["timestamp"]))["close"].pct_change()
            j = pd.concat([s, m], axis=1, join="inner").dropna()
            if len(j) < min_obs or not j.iloc[:, 1].var():
                return None
            return float(j.iloc[:, 0].cov(j.iloc[:, 1]) / j.iloc[:, 1].var())
        except Exception as exc:
            logger.debug("Beta failed for %s: %s", self.symbol, exc)
            return None

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
            mdd = float(((price_df["close"] - price_df["close"].cummax()) / price_df["close"].cummax()).min())
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

    def fair_value_analysis(self) -> Dict[str, Any]:
        from analytics.fair_value import fair_value, historical_multiples, is_financial
        price = self._price_vnd()
        summ = self.financial_summary()
        val = summ.get("valuation") or {}
        ratios = summ.get("ratios")
        last = ratios.iloc[-1] if ratios is not None and not ratios.empty else pd.Series(dtype=float)
        annual = self.get_financials("year").get("data", pd.DataFrame())
        hist = historical_multiples(annual, val.get("shares"), self.get_long_price_df())
        peers = self.get_peer_stats() or {}
        info = self.get_company_info() or {}
        industry = str(info.get("industry") or info.get("sector") or "")
        res = fair_value(price, val.get("eps_ttm"), val.get("bvps"),
                         roe_pct=last.get("roe"), payout_pct=last.get("dividend_payout"),
                         dividend_yield_pct=val.get("dividend_yield"), beta=self.compute_beta(),
                         peer_pe=peers.get("pe"), peer_pb=peers.get("pb"),
                         peer_n=int(peers.get("n_pe", peers.get("n", 0)) or 0), peer_group=peers.get("group"),
                         hist=hist, financial=is_financial(industry, bool(summ.get("is_bank"))))
        res["history"] = hist
        res["eps_ttm"], res["bvps"] = val.get("eps_ttm"), val.get("bvps")
        res["pe_now"], res["pb_now"] = val.get("pe"), val.get("pb")
        return res

    def recommendation(self) -> Dict[str, Any]:
        from analytics.recommendation import recommend
        fv = self._safe("fair_value", self.fair_value_analysis, {"available": False})
        opp = self._safe("opportunity_score", self.compute_opportunity_score, {"composite": {}})
        tech = self._safe("technical", self.technical_analysis, {"available": False})
        trend = ((tech.get("signals") or {}).get("trend") or {}).get("name") if tech.get("available") else None
        return recommend(fv, (opp.get("composite") or {}).get("score"), trend)

    # ─────────────────── Khuyến nghị đầu tư & giá mục tiêu 12 tháng ─────────────

    def investment_analysis(self, overrides: Optional[Dict[str, Any]] = None, holder: Optional[bool] = None,
                            as_of: Optional[pd.Timestamp] = None) -> Dict[str, Any]:
        """
        Financial Health Score → Risk Assessment → Valuation Engine (12T) → Recommendation Engine.
        Dùng lại: BCTC đã chuẩn hóa (get_financials), bộ tính chỉ số (financial_ratios), beta, trung vị ngành,
        lịch sử giá dài. Không tự tạo dữ liệu: thiếu nguồn → trạng thái "CHƯA ĐỦ CƠ SỞ".
        """
        from analytics.financial_health import FinancialHealthEngine
        from analytics.recommendation import explain_recommendation, recommend_investment
        from analytics.risk_assessment import assess_risk
        from analytics.valuation_engine import ValuationEngine12M
        from config.investment_model import classify_company, load_config

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
        company = classify_company(industry, str(peers.get("group") or ""), bool(summ.get("is_bank")) if summ else False)
        cur = self.get_current_price() or {}
        price, price_date = cur.get("price"), cur.get("timestamp")
        shares = None
        if annual is not None and not annual.empty:
            sh = fr.shares_series(annual).dropna()
            shares = float(sh.iloc[-1]) if not sh.empty else None
        tech = self._safe("technical", self.technical_analysis, {"available": False})
        trend = ((tech.get("signals") or {}).get("trend") or {}).get("name") if tech.get("available") else None
        ind_text = f"{industry} {peers.get('group') or ''}"

        health = FinancialHealthEngine(cfg).score(ratios, annual, company)
        risk_kw = dict(summary=summ, price_df=price_df, health=health, industry_text=ind_text, trend=trend,
                       as_of=pd.Timestamp(as_of) if as_of is not None else None, config=cfg)
        risk0 = assess_risk(annual, ratios, company, **risk_kw)
        valuation = ValuationEngine12M(cfg).value(
            price=price, price_date=pd.Timestamp(price_date) if price_date is not None else None, wide=annual,
            ratios=ratios, shares=shares, company=company, beta=self.compute_beta(), peers=peers,
            price_df=price_df, risk_level=risk0["level"])
        if as_of is not None:
            valuation["as_of"] = str(as_of.date())
            valuation.setdefault("notes", []).insert(0, f"Định giá tại ngày {as_of:%d/%m/%Y}: dùng giá đóng cửa phiên "
                                                        f"{price_date or '—'} và chỉ BCTC đã công bố trước ngày này."
                                                        + (" Không dùng trung vị ngành (chỉ có số liệu hiện tại)."
                                                           if not peers.get("n") and peers.get("reason", "").startswith("Định giá") else ""))
        risk = assess_risk(annual, ratios, company, valuation=valuation, **risk_kw)
        rec = recommend_investment(health, valuation, risk, cfg, holder=holder)
        return {"symbol": self.symbol, "name": info.get("company_name") or info.get("short_name") or "",
                "industry": industry.strip(), "company": company, "health": health, "valuation": valuation, "risk": risk,
                "recommendation": rec, "explanation": explain_recommendation(self.symbol, rec, health, valuation, risk),
                "thesis": _thesis(health, valuation, risk), "config": cfg, "peers": peers,
                "as_of": str(as_of.date()) if as_of is not None else None,
                "generated_at": datetime.now().isoformat(timespec="seconds")}

    def recommendation_backtest(self, years: int = 8, cost: float = 0.003,
                                overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Backtest hệ thống khuyến nghị 12T theo từng năm (điểm thời gian) so với VN-Index."""
        from analytics.reco_backtest import backtest_recommendations
        from config.investment_model import classify_company, load_config
        annual = self.get_financials("year", years=max(self.fin_years, years + 3)).get("data", pd.DataFrame())
        px = self.get_long_price_df(years=years + 1)
        try:
            idx = self.repo.get_index_history("VNINDEX", days=365 * (years + 1) + 30)
        except Exception:
            idx = pd.DataFrame()
        info = self.get_company_info() or {}
        peers = self.get_peer_stats() or {}
        industry = " ".join(str(info.get(k) or "") for k in ("industry", "sector", "icb_name3", "icb_name2"))
        company = classify_company(industry, str(peers.get("group") or ""), bool(fr.is_bank(annual)) if annual is not None and not annual.empty else False)
        return backtest_recommendations(annual, px, idx, company, cost=cost, config=load_config(overrides),
                                        summary_fn=lambda w: {"altman": fr.altman_z(w)})

    def investment_compat(self) -> Dict[str, Any]:
        """Kết quả 12T ở dạng khóa cũ của 'fair_value' (để trang phân tích & PDF hiện tại dùng tiếp)."""
        inv = self._safe("investment", self.investment_analysis, None)
        if not inv:
            return {"available": False, "notes": ["Không chạy được mô hình định giá 12 tháng."]}
        return valuation_to_legacy(inv["valuation"])

    def _recommendation_compat(self) -> Dict[str, Any]:
        inv = self._safe("investment", self.investment_analysis, None)
        if not inv:
            return self.recommendation()          # dự phòng: hệ thống cũ
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
            f"Giá mục tiêu 12T {valuation['target_12m']:,.0f} ({valuation['upside']:+.1f}% so với thị giá)")
    neg += [i["text"] for i in risk.get("items", []) if i["severity"] in ("Nghiêm trọng", "Cao")][:3]
    return {"positives": pos[:6], "negatives": neg[:6]}
