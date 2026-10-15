"""
core/phan_tich_ky_thuat.py – gộp từ 3 module (15/10/2026).

MỤC LỤC
  • analytics/indicators.py – Shared indicator primitives.
      hàm/lớp chính: rsi_wilder
  • analytics/technical.py – Technical Analysis engine using pandas-ta.
      hàm/lớp chính: TechnicalAnalyzer
  • analytics/momentum.py – Momentum analysis.
      hàm/lớp chính: MomentumAnalyzer
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/indicators.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Shared indicator primitives.

Mọi module (kỹ thuật, động lượng, backtest) dùng CHUNG các hàm ở đây để cùng
một mã cổ phiếu luôn cho ra cùng một giá trị chỉ báo.
"""


import numpy as np
import pandas as pd


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    """
    RSI theo phương pháp gốc của J. Welles Wilder (1978).

    avg_gain, avg_loss được làm mượt bằng RMA (EWM với alpha = 1/period),
    đây cũng là cách pandas-ta / TradingView / Amibroker tính RSI.

    Quy ước biên:
      - Chưa đủ `period` phiên  -> NaN (không gán giá trị giả)
      - avg_loss = 0, avg_gain > 0 -> 100
      - avg_loss = 0, avg_gain = 0 -> 50 (giá đi ngang tuyệt đối)
    """
    close = pd.to_numeric(close, errors="coerce")
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    ready = avg_gain.notna() & avg_loss.notna()
    rsi = rsi.where(~(ready & (avg_loss == 0) & (avg_gain > 0)), 100.0)
    rsi = rsi.where(~(ready & (avg_loss == 0) & (avg_gain == 0)), 50.0)
    return rsi


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/technical.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Technical Analysis engine using pandas-ta.

All indicators are computed purely from price/volume data.
No AI-generated numbers – only algorithmic results.
"""


import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import pandas_ta as ta
    _TA_AVAILABLE = True
except Exception:
    _TA_AVAILABLE = False
    logging.info("pandas-ta not available or numba issue; using built-in high-performance pure-pandas algorithms.")


from core.cau_hinh import ATR_PERIOD, ADX_PERIOD, BB_PERIOD, BB_STD, CMF_PERIOD, EMA_PERIODS, MACD_FAST, MACD_SIGNAL, MACD_SLOW, MFI_PERIOD, ROC_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD, RSI_PERIOD, SMA_PERIODS, COLOR_BULLISH, COLOR_BEARISH, COLOR_NEUTRAL

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """Compute technical indicators and generate signals."""

    MIN_BARS = 30

    def __init__(self, df: pd.DataFrame):
        """
        Parameters
        ----------
        df : OHLCV DataFrame with columns: open, high, low, close, volume, timestamp
        """
        self.df = df.copy()
        self._ensure_index()

    def _ensure_index(self):
        if "timestamp" in self.df.columns:
            self.df = self.df.set_index("timestamp")
        self.df.index = pd.to_datetime(self.df.index)
        self.df = self.df.sort_index()

    @property
    def is_sufficient(self) -> bool:
        return len(self.df) >= self.MIN_BARS

    # ─────────────────── Moving Averages ─────────────────────────────────────

    def add_sma(self) -> "TechnicalAnalyzer":
        if not self.is_sufficient:
            return self
        for p in SMA_PERIODS:
            if len(self.df) >= p:
                if _TA_AVAILABLE:
                    try:
                        self.df[f"SMA_{p}"] = ta.sma(self.df["close"], length=p)
                        continue
                    except Exception:
                        pass
                self.df[f"SMA_{p}"] = self.df["close"].rolling(p).mean()
        return self

    def add_ema(self) -> "TechnicalAnalyzer":
        if not self.is_sufficient:
            return self
        for p in EMA_PERIODS:
            if len(self.df) >= p:
                if _TA_AVAILABLE:
                    try:
                        self.df[f"EMA_{p}"] = ta.ema(self.df["close"], length=p)
                        continue
                    except Exception:
                        pass
                self.df[f"EMA_{p}"] = self.df["close"].ewm(span=p, adjust=False).mean()
        return self

    # ─────────────────── Oscillators ─────────────────────────────────────────

    def add_rsi(self) -> "TechnicalAnalyzer":
        if len(self.df) < RSI_PERIOD + 1:
            return self
        # Dùng hàm RSI chung (Wilder) để kỹ thuật / động lượng / backtest cho cùng một giá trị
        self.df["RSI"] = rsi_wilder(self.df["close"], RSI_PERIOD)
        return self

    def add_macd(self) -> "TechnicalAnalyzer":
        if len(self.df) < MACD_SLOW + MACD_SIGNAL:
            return self
        if _TA_AVAILABLE:
            try:
                macd = ta.macd(self.df["close"], fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
                if macd is not None and not macd.empty:
                    self.df["MACD"] = macd.iloc[:, 0]
                    self.df["MACD_signal"] = macd.iloc[:, 1]
                    self.df["MACD_hist"] = macd.iloc[:, 2]
                    return self
            except Exception:
                pass
        ema_fast = self.df["close"].ewm(span=MACD_FAST, adjust=False).mean()
        ema_slow = self.df["close"].ewm(span=MACD_SLOW, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
        self.df["MACD"] = macd_line
        self.df["MACD_signal"] = signal_line
        self.df["MACD_hist"] = macd_line - signal_line
        return self

    def add_bollinger(self) -> "TechnicalAnalyzer":
        if len(self.df) < BB_PERIOD:
            return self
        if _TA_AVAILABLE:
            try:
                bb = ta.bbands(self.df["close"], length=BB_PERIOD, std=BB_STD)
                if bb is not None and not bb.empty:
                    cols = bb.columns.tolist()
                    self.df["BB_upper"] = bb[cols[0]]
                    self.df["BB_mid"] = bb[cols[1]]
                    self.df["BB_lower"] = bb[cols[2]]
                    self.df["BB_width"] = (self.df["BB_upper"] - self.df["BB_lower"]) / self.df["BB_mid"]
                    return self
            except Exception:
                pass
        mid = self.df["close"].rolling(BB_PERIOD).mean()
        std = self.df["close"].rolling(BB_PERIOD).std()
        self.df["BB_mid"] = mid
        self.df["BB_upper"] = mid + (std * BB_STD)
        self.df["BB_lower"] = mid - (std * BB_STD)
        self.df["BB_width"] = (self.df["BB_upper"] - self.df["BB_lower"]) / self.df["BB_mid"]
        return self

    def add_atr(self) -> "TechnicalAnalyzer":
        if len(self.df) < ATR_PERIOD:
            return self
        if _TA_AVAILABLE:
            try:
                self.df["ATR"] = ta.atr(self.df["high"], self.df["low"], self.df["close"], length=ATR_PERIOD)
                return self
            except Exception:
                pass
        hl = self.df["high"] - self.df["low"]
        hc = (self.df["high"] - self.df["close"].shift(1)).abs()
        lc = (self.df["low"] - self.df["close"].shift(1)).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        self.df["ATR"] = tr.ewm(alpha=1.0 / ATR_PERIOD, min_periods=ATR_PERIOD, adjust=False).mean()
        return self

    def add_adx(self) -> "TechnicalAnalyzer":
        """ADX kèm +DI / −DI (cần cả hai để biết xu hướng mạnh là tăng hay giảm)."""
        if len(self.df) < ADX_PERIOD * 2:
            return self
        if _TA_AVAILABLE:
            try:
                adx = ta.adx(self.df["high"], self.df["low"], self.df["close"], length=ADX_PERIOD)
                if adx is not None and not adx.empty:
                    cols = adx.columns.tolist()
                    adx_col = next((c for c in cols if c.startswith("ADX")), cols[0])
                    dmp_col = next((c for c in cols if c.startswith("DMP")), None)
                    dmn_col = next((c for c in cols if c.startswith("DMN")), None)
                    if dmp_col and dmn_col:
                        self.df["ADX"] = adx[adx_col]
                        self.df["PLUS_DI"] = adx[dmp_col]
                        self.df["MINUS_DI"] = adx[dmn_col]
                        return self
            except Exception:
                pass
        high = self.df["high"]
        low = self.df["low"]
        prev_high = high.shift(1)
        prev_low = low.shift(1)
        up_move = high - prev_high
        down_move = prev_low - low
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        hl = high - low
        hc = (high - self.df["close"].shift(1)).abs()
        lc = (low - self.df["close"].shift(1)).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1.0 / ADX_PERIOD, min_periods=ADX_PERIOD, adjust=False).mean()
        plus_di = 100.0 * (pd.Series(plus_dm, index=high.index).ewm(alpha=1.0 / ADX_PERIOD, min_periods=ADX_PERIOD, adjust=False).mean() / atr.replace(0, np.nan))
        minus_di = 100.0 * (pd.Series(minus_dm, index=high.index).ewm(alpha=1.0 / ADX_PERIOD, min_periods=ADX_PERIOD, adjust=False).mean() / atr.replace(0, np.nan))
        dx = 100.0 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
        self.df["ADX"] = dx.ewm(alpha=1.0 / ADX_PERIOD, min_periods=ADX_PERIOD, adjust=False).mean()
        self.df["PLUS_DI"] = plus_di
        self.df["MINUS_DI"] = minus_di
        return self

    def add_mfi(self) -> "TechnicalAnalyzer":
        if len(self.df) < MFI_PERIOD or "volume" not in self.df.columns:
            return self
        if _TA_AVAILABLE:
            try:
                self.df["MFI"] = ta.mfi(self.df["high"], self.df["low"], self.df["close"], self.df["volume"], length=MFI_PERIOD)
                return self
            except Exception:
                pass
        tp = (self.df["high"] + self.df["low"] + self.df["close"]) / 3.0
        mf = tp * self.df["volume"]
        pos_mf = mf.where(tp > tp.shift(1), 0.0)
        neg_mf = mf.where(tp < tp.shift(1), 0.0)
        mfr = pos_mf.rolling(MFI_PERIOD).sum() / neg_mf.rolling(MFI_PERIOD).sum().replace(0, np.nan)
        self.df["MFI"] = 100.0 - (100.0 / (1.0 + mfr))
        return self

    def add_obv(self) -> "TechnicalAnalyzer":
        if "volume" not in self.df.columns:
            return self
        if _TA_AVAILABLE:
            try:
                self.df["OBV"] = ta.obv(self.df["close"], self.df["volume"])
                return self
            except Exception:
                pass
        direction = np.sign(self.df["close"].diff()).fillna(0)
        self.df["OBV"] = (direction * self.df["volume"]).cumsum()
        return self

    def add_cmf(self) -> "TechnicalAnalyzer":
        if len(self.df) < CMF_PERIOD or "volume" not in self.df.columns:
            return self
        if _TA_AVAILABLE:
            try:
                self.df["CMF"] = ta.cmf(self.df["high"], self.df["low"], self.df["close"], self.df["volume"], length=CMF_PERIOD)
                return self
            except Exception:
                pass
        hl = self.df["high"] - self.df["low"]
        mfm = np.where(hl != 0, ((self.df["close"] - self.df["low"]) - (self.df["high"] - self.df["close"])) / hl, 0.0)
        mfv = mfm * self.df["volume"]
        self.df["CMF"] = pd.Series(mfv, index=self.df.index).rolling(CMF_PERIOD).sum() / self.df["volume"].rolling(CMF_PERIOD).sum().replace(0, np.nan)
        return self

    def add_roc(self) -> "TechnicalAnalyzer":
        if len(self.df) < ROC_PERIOD:
            return self
        if _TA_AVAILABLE:
            try:
                self.df["ROC"] = ta.roc(self.df["close"], length=ROC_PERIOD)
                return self
            except Exception:
                pass
        self.df["ROC"] = ((self.df["close"] - self.df["close"].shift(ROC_PERIOD)) / self.df["close"].shift(ROC_PERIOD)) * 100.0
        return self

    def add_relative_volume(self) -> "TechnicalAnalyzer":
        """Relative Volume = current vol / 20-day avg vol."""
        if "volume" not in self.df.columns or len(self.df) < 20:
            return self
        avg_vol = self.df["volume"].rolling(20).mean()
        self.df["RelVol"] = self.df["volume"] / avg_vol
        return self

    # ─────────────────── All indicators ──────────────────────────────────────

    def compute_all(self) -> pd.DataFrame:
        """Compute all indicators and return enriched DataFrame."""
        (
            self.add_sma()
                .add_ema()
                .add_rsi()
                .add_macd()
                .add_bollinger()
                .add_atr()
                .add_adx()
                .add_mfi()
                .add_obv()
                .add_cmf()
                .add_roc()
                .add_relative_volume()
        )
        return self.df.reset_index()

    # ─────────────────── Signal Detection ────────────────────────────────────

    def get_signals(self) -> Dict[str, Any]:
        """
        Detect trading signals from computed indicators.
        Returns a dict of signal names → {'signal': str, 'value': float, 'description': str}
        """
        df = self.df
        if df.empty or len(df) < 2:
            return {}

        last = df.iloc[-1]
        prev = df.iloc[-2]
        signals: Dict[str, Any] = {}

        # ── Trend ──
        trend = self._detect_trend(df)
        signals["trend"] = trend

        # ── RSI ──
        if "RSI" in df.columns and pd.notna(last.get("RSI")):
            rsi_val = float(last["RSI"])
            if rsi_val >= RSI_OVERBOUGHT:
                rsi_signal = "Quá mua"
                rsi_color = COLOR_BEARISH
            elif rsi_val <= RSI_OVERSOLD:
                rsi_signal = "Quá bán"
                rsi_color = COLOR_BULLISH
            elif rsi_val > 50:
                rsi_signal = "Tích cực"
                rsi_color = COLOR_BULLISH
            else:
                rsi_signal = "Tiêu cực"
                rsi_color = COLOR_BEARISH
            signals["rsi"] = {
                "value": rsi_val,
                "signal": rsi_signal,
                "color": rsi_color,
                "description": f"RSI({RSI_PERIOD}) = {rsi_val:.1f}",
            }

        # ── MACD ──
        if all(c in df.columns for c in ["MACD", "MACD_signal", "MACD_hist"]):
            if pd.notna(last.get("MACD")) and pd.notna(last.get("MACD_signal")):
                hist_now = last.get("MACD_hist", 0) or 0
                hist_prev = prev.get("MACD_hist", 0) or 0
                macd_cross = (
                    "Cắt lên" if hist_now > 0 and hist_prev <= 0
                    else "Cắt xuống" if hist_now < 0 and hist_prev >= 0
                    else "Tăng" if hist_now > hist_prev
                    else "Giảm"
                )
                signals["macd"] = {
                    "macd": round(float(last["MACD"]), 4),
                    "signal": round(float(last["MACD_signal"]), 4),
                    "histogram": round(float(hist_now), 4),
                    "cross": macd_cross,
                    "color": COLOR_BULLISH if hist_now > 0 else COLOR_BEARISH,
                }

        # ── Bollinger ──
        if all(c in df.columns for c in ["BB_upper", "BB_lower", "BB_mid"]):
            close = float(last["close"])
            bb_upper = float(last.get("BB_upper", close))
            bb_lower = float(last.get("BB_lower", close))
            bb_mid = float(last.get("BB_mid", close))
            bb_position = (close - bb_lower) / max((bb_upper - bb_lower), 1) * 100
            if close > bb_upper:
                bb_signal = "Phá vỡ dải trên"
            elif close < bb_lower:
                bb_signal = "Phá vỡ dải dưới"
            elif close > bb_mid:
                bb_signal = "Trên trung tâm"
            else:
                bb_signal = "Dưới trung tâm"
            signals["bollinger"] = {
                "upper": bb_upper,
                "mid": bb_mid,
                "lower": bb_lower,
                "position_pct": round(bb_position, 1),
                "signal": bb_signal,
            }

        # ── Volume spike ──
        if "RelVol" in df.columns and pd.notna(last.get("RelVol")):
            rel_vol = float(last["RelVol"])
            if rel_vol > 2.0:
                vol_signal = f"Đột biến khối lượng ({rel_vol:.1f}x)"
            elif rel_vol > 1.5:
                vol_signal = f"Khối lượng cao ({rel_vol:.1f}x)"
            elif rel_vol < 0.5:
                vol_signal = "Khối lượng thấp"
            else:
                vol_signal = "Bình thường"
            signals["volume"] = {
                "relative_volume": round(rel_vol, 2),
                "signal": vol_signal,
                "color": COLOR_BULLISH if rel_vol > 1.5 else COLOR_NEUTRAL,
            }

        # ── ADX (sức mạnh xu hướng) ──
        if all(c in df.columns for c in ["ADX", "PLUS_DI", "MINUS_DI"]) and pd.notna(last.get("ADX")):
            adx_v = float(last["ADX"])
            up = float(last.get("PLUS_DI") or 0) > float(last.get("MINUS_DI") or 0)
            strength = "mạnh" if adx_v >= 25 else "vừa" if adx_v >= 20 else "yếu / đi ngang"
            signals["adx"] = {
                "value": round(adx_v, 1),
                "signal": f"Xu hướng {'tăng' if up else 'giảm'} {strength}",
                "color": COLOR_BULLISH if up and adx_v >= 20 else COLOR_BEARISH if adx_v >= 20 else COLOR_NEUTRAL,
            }

        # ── Dòng tiền (CMF / MFI) ──
        if "CMF" in df.columns and pd.notna(last.get("CMF")):
            cmf_v = float(last["CMF"])
            signals["money_flow"] = {
                "cmf": round(cmf_v, 3),
                "mfi": round(float(last["MFI"]), 1) if "MFI" in df.columns and pd.notna(last.get("MFI")) else None,
                "signal": "Dòng tiền vào" if cmf_v > 0 else "Dòng tiền ra",
                "color": COLOR_BULLISH if cmf_v > 0 else COLOR_BEARISH,
            }

        # ── Support & Resistance ──
        signals["support_resistance"] = self._find_support_resistance(df)

        return signals

    def _detect_trend(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Determine trend from moving averages and price action."""
        last = df.iloc[-1]
        close = float(last["close"])

        trend_score = 0
        criteria = []

        for sma_col, weight in [("SMA_20", 1), ("SMA_50", 2), ("SMA_200", 3)]:
            if sma_col in df.columns and pd.notna(last.get(sma_col)):
                sma_val = float(last[sma_col])
                if close > sma_val:
                    trend_score += weight
                    criteria.append(f"Giá > {sma_col}")
                else:
                    trend_score -= weight
                    criteria.append(f"Giá < {sma_col}")

        # MA crossover
        if "SMA_20" in df.columns and "SMA_50" in df.columns:
            sma20 = last.get("SMA_20")
            sma50 = last.get("SMA_50")
            if pd.notna(sma20) and pd.notna(sma50):
                if float(sma20) > float(sma50):
                    trend_score += 1
                    criteria.append("SMA20 > SMA50 (Golden)")
                else:
                    trend_score -= 1
                    criteria.append("SMA20 < SMA50 (Death)")

        # 20-day high/low
        lookback = min(20, len(df))
        recent_high = df["close"].iloc[-lookback:].max()
        recent_low = df["close"].iloc[-lookback:].min()
        pct_from_high = (close - recent_high) / recent_high * 100
        pct_from_low = (close - recent_low) / recent_low * 100

        if trend_score >= 3:
            trend_name = "Tăng mạnh"
            color = COLOR_BULLISH
        elif trend_score > 0:
            trend_name = "Tăng"
            color = COLOR_BULLISH
        elif trend_score == 0:
            trend_name = "Đi ngang"
            color = COLOR_NEUTRAL
        elif trend_score > -3:
            trend_name = "Giảm"
            color = COLOR_BEARISH
        else:
            trend_name = "Giảm mạnh"
            color = COLOR_BEARISH

        return {
            "name": trend_name,
            "score": trend_score,
            "color": color,
            "criteria": criteria,
            "pct_from_high": round(pct_from_high, 2),
            "pct_from_low": round(pct_from_low, 2),
        }

    @staticmethod
    def _find_support_resistance(df: pd.DataFrame, n: int = 20) -> Dict[str, Any]:
        """Simple pivot-based S/R detection."""
        if len(df) < n:
            return {}
        recent = df.tail(min(120, len(df)))
        closes = recent["close"].values
        highs = recent["high"].values if "high" in recent.columns else closes
        lows = recent["low"].values if "low" in recent.columns else closes

        res_list = []
        sup_list = []
        m = len(highs)
        window = 5
        if m > window * 2:
            for idx in range(window, m - window):
                val_h = highs[idx]
                if val_h == max(highs[idx - window : idx + window + 1]):
                    res_list.append(float(val_h))
                val_l = lows[idx]
                if val_l == min(lows[idx - window : idx + window + 1]):
                    sup_list.append(float(val_l))
        else:
            res_list = [float(np.max(highs))]
            sup_list = [float(np.min(lows))]

        current = float(df.iloc[-1]["close"])
        resistance_levels = sorted([r for r in set(res_list) if r > current])
        support_levels = sorted([s for s in set(sup_list) if s < current], reverse=True)

        if not resistance_levels:
            resistance_levels = sorted(list(set(res_list)), reverse=True)
        if not support_levels:
            support_levels = sorted(list(set(sup_list)))

        return {
            "current_price": current,
            "resistance": resistance_levels[:2],
            "support": support_levels[:2],
        }

    # ─────────────────── Technical Score ─────────────────────────────────────

    @staticmethod
    def _val(row, col) -> Optional[float]:
        v = row.get(col) if col in row.index else None
        return float(v) if v is not None and pd.notna(v) else None

    def compute_technical_score(self) -> Dict[str, Any]:
        """
        Score technical setup 0–100.

        Components (tổng 100 điểm):
          - Vị trí giá so với MA (SMA200 10, SMA50 8, SMA20 7)   (25)
          - Vùng RSI                                            (15)
          - MACD histogram                                      (15)
          - Xác nhận khối lượng (RelVol)                        (10)
          - Vị trí trong dải Bollinger                          (10)
          - Sức mạnh xu hướng ADX + hướng +DI/−DI               (10)
          - Dòng tiền: CMF (5) + MFI (5) + OBV vs SMA20 (5)     (15)

        Thành phần nào không tính được (thiếu dữ liệu) bị loại khỏi CẢ tử số
        lẫn mẫu số – không bị gán 0 – giống cách chuẩn hóa ở các bộ chấm điểm khác.
        """
        if not self.is_sufficient:
            return {"score": None, "reason": "Không đủ dữ liệu", "components": {}}

        df = self.df
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        close = float(last["close"])
        components: Dict[str, Any] = {}

        # ── Trend / MA (25) ──
        ma_score, ma_max = 0, 0
        for col, pts in [("SMA_200", 10), ("SMA_50", 8), ("SMA_20", 7)]:
            v = self._val(last, col)
            if v is not None:
                ma_max += pts
                if close > v:
                    ma_score += pts
        components["ma_alignment"] = (
            {"score": ma_score, "max": ma_max} if ma_max else {"score": None, "max": 25}
        )

        # ── RSI (15) ──
        rsi = self._val(last, "RSI")
        if rsi is not None:
            if 50 <= rsi <= 70:
                s = 15
            elif 40 <= rsi < 50 or 70 < rsi <= 80:
                s = 8
            elif rsi > 80 or rsi < 30:
                s = 0
            else:
                s = 4
            components["rsi"] = {"score": s, "max": 15, "value": round(rsi, 1)}
        else:
            components["rsi"] = {"score": None, "max": 15}

        # ── MACD (15) ──
        hist = self._val(last, "MACD_hist")
        if hist is not None:
            prev_hist = self._val(prev, "MACD_hist")
            prev_hist = hist if prev_hist is None else prev_hist
            if hist > 0 and hist > prev_hist:
                s = 15
            elif hist > 0:
                s = 9
            elif hist > prev_hist:
                s = 6
            else:
                s = 0
            components["macd"] = {"score": s, "max": 15, "value": round(hist, 4)}
        else:
            components["macd"] = {"score": None, "max": 15}

        # ── Volume (10) ──
        rv = self._val(last, "RelVol")
        if rv is not None:
            s = 10 if rv > 1.5 else 7 if rv > 1.0 else 3 if rv > 0.7 else 0
            components["volume"] = {"score": s, "max": 10, "value": round(rv, 2)}
        else:
            components["volume"] = {"score": None, "max": 10}

        # ── Bollinger (10) ──
        bb_u, bb_l, bb_m = (self._val(last, c) for c in ("BB_upper", "BB_lower", "BB_mid"))
        if None not in (bb_u, bb_l, bb_m):
            if bb_m < close <= bb_u:
                s = 10          # nửa trên dải: xu hướng tăng lành mạnh
            elif close > bb_u:
                s = 4           # vượt dải trên: dễ điều chỉnh
            elif close > bb_l:
                s = 5           # nửa dưới dải
            else:
                s = 0           # thủng dải dưới
            components["bollinger"] = {"score": s, "max": 10}
        else:
            components["bollinger"] = {"score": None, "max": 10}

        # ── ADX (10) ──
        adx = self._val(last, "ADX")
        pdi, mdi = self._val(last, "PLUS_DI"), self._val(last, "MINUS_DI")
        if adx is not None and pdi is not None and mdi is not None:
            up = pdi > mdi
            if adx >= 25:
                s = 10 if up else 0      # xu hướng mạnh: tăng = tốt, giảm = xấu
            elif adx >= 20:
                s = 6 if up else 2
            else:
                s = 4                    # ADX < 20: không có xu hướng rõ (trung tính)
            components["adx"] = {
                "score": s, "max": 10, "value": round(adx, 1),
                "direction": "Tăng (+DI > −DI)" if up else "Giảm (−DI > +DI)",
            }
        else:
            components["adx"] = {"score": None, "max": 10}

        # ── Dòng tiền: CMF + MFI + OBV (15) ──
        mf_score, mf_max, mf_detail = 0, 0, {}
        cmf = self._val(last, "CMF")
        if cmf is not None:
            mf_max += 5
            mf_score += 5 if cmf > 0.10 else 3 if cmf > 0 else 1 if cmf > -0.10 else 0
            mf_detail["cmf"] = round(cmf, 3)
        mfi = self._val(last, "MFI")
        if mfi is not None:
            mf_max += 5
            if 50 <= mfi <= 80:
                mf_score += 5
            elif 40 <= mfi < 50:
                mf_score += 3
            elif mfi > 80:
                mf_score += 2   # quá mua theo dòng tiền
            else:
                mf_score += 0
            mf_detail["mfi"] = round(mfi, 1)
        if "OBV" in df.columns and df["OBV"].notna().sum() >= 20:
            obv = df["OBV"]
            obv_ma = obv.rolling(20).mean()
            mf_max += 5
            if obv.iloc[-1] > obv_ma.iloc[-1]:
                mf_score += 5
            elif len(obv) > 5 and obv.iloc[-1] > obv.iloc[-6]:
                mf_score += 2
            mf_detail["obv_above_ma20"] = bool(obv.iloc[-1] > obv_ma.iloc[-1])
        components["money_flow"] = (
            {"score": mf_score, "max": mf_max, **mf_detail} if mf_max else {"score": None, "max": 15}
        )

        available = [c for c in components.values() if c.get("score") is not None]
        max_raw = sum(c["max"] for c in available)
        total_raw = sum(c["score"] for c in available)
        final_score = round(total_raw / max_raw * 100) if max_raw else None

        return {
            "score": final_score,
            "components": components,
            "total_raw": total_raw,
            "max_raw": max_raw,
        }


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/momentum.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Momentum analysis.

Computes multi-period momentum, relative strength vs VN-Index,
and a Momentum Score 0–100.
"""


import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd



logger = logging.getLogger(__name__)


class MomentumAnalyzer:
    """
    Compute momentum indicators and relative strength.

    Parameters
    ----------
    price_df  : Stock OHLCV DataFrame
    index_df  : VN-Index OHLCV DataFrame (for relative strength)
    """

    def __init__(self, price_df: pd.DataFrame, index_df: pd.DataFrame = None):
        self.df = self._prepare(price_df)
        self.idx_df = self._prepare(index_df) if index_df is not None else pd.DataFrame()

    @staticmethod
    def _prepare(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        df.index = pd.to_datetime(df.index)
        return df.sort_index()

    # ─────────────────── Price Momentum ──────────────────────────────────────

    def price_momentum(self, periods: List[int] = [5, 10, 20, 60, 120]) -> Dict[str, Optional[float]]:
        """Return price returns over multiple periods."""
        if self.df.empty or "close" not in self.df.columns:
            return {}
        closes = self.df["close"].dropna()
        result = {}
        current = float(closes.iloc[-1])
        for p in periods:
            if len(closes) > p:
                past = float(closes.iloc[-p - 1])
                result[f"momentum_{p}d"] = (current - past) / past * 100 if past != 0 else None
            else:
                result[f"momentum_{p}d"] = None
        return result

    # ─────────────────── Relative Strength vs VN-Index ───────────────────────

    def relative_strength(self, period: int = 60) -> Dict[str, Any]:
        """Compute RS ratio and RS score vs VN-Index."""
        if self.df.empty or self.idx_df.empty:
            return {"available": False, "reason": "Không có dữ liệu VN-Index"}
        if "close" not in self.df.columns or "close" not in self.idx_df.columns:
            return {"available": False}

        # Align on common dates
        stock_closes = self.df["close"].dropna()
        index_closes = self.idx_df["close"].dropna()
        common = stock_closes.index.intersection(index_closes.index)
        if len(common) < period:
            return {"available": False, "reason": "Không đủ dữ liệu tương thích"}

        stock_s = stock_closes.loc[common].tail(period)
        index_s = index_closes.loc[common].tail(period)

        stock_ret = float(stock_s.iloc[-1] / stock_s.iloc[0] - 1) * 100
        index_ret = float(index_s.iloc[-1] / index_s.iloc[0] - 1) * 100
        rs_diff = stock_ret - index_ret

        # RS ratio (Mansfield-style simplified)
        rs_ratio = stock_s / index_s
        rs_normalized = (rs_ratio - rs_ratio.mean()) / rs_ratio.std() if rs_ratio.std() != 0 else rs_ratio - rs_ratio.mean()

        return {
            "available": True,
            "period": period,
            "stock_return": round(stock_ret, 2),
            "index_return": round(index_ret, 2),
            "rs_differential": round(rs_diff, 2),
            "outperforming": rs_diff > 0,
            "rs_trend": "Mạnh hơn thị trường" if rs_diff > 0 else "Yếu hơn thị trường",
        }

    # ─────────────────── RSI from price data ─────────────────────────────────

    def compute_rsi(self, period: int = 14) -> Optional[float]:
        """RSI Wilder – dùng chung hàm với TechnicalAnalyzer và Backtest."""
        if self.df.empty or "close" not in self.df.columns:
            return None
        closes = self.df["close"].dropna()
        if len(closes) < period + 1:
            return None
        rsi = rsi_wilder(closes, period)
        return float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else None

    # ─────────────────── Momentum Score ──────────────────────────────────────

    def compute_momentum_score(self) -> Dict[str, Any]:
        """
        Score momentum 0–100.

        Components:
          Short-term momentum 5/10d  (25)
          Medium-term momentum 20d   (20)
          Long-term momentum 60/120d (20)
          Relative strength          (20)
          (RSI: chỉ chấm trong điểm Kỹ thuật, không tính lại ở đây)
        """
        components: Dict[str, Any] = {}
        total = 0.0
        max_pts = 0
        missing = []

        mom = self.price_momentum()

        # ── Short momentum (25) ──
        max_pts += 25
        m5 = mom.get("momentum_5d")
        m10 = mom.get("momentum_10d")
        if m5 is not None or m10 is not None:
            val = (m5 or 0) * 0.4 + (m10 or 0) * 0.6
            if val > 5:
                s = 25
            elif val > 2:
                s = 18
            elif val > 0:
                s = 12
            elif val > -2:
                s = 6
            else:
                s = 0
            components["short_momentum"] = {"score": s, "max": 25, "value": round(val, 2)}
            total += s
        else:
            missing.append("Động lượng ngắn hạn")
            components["short_momentum"] = {"score": None, "max": 25}

        # ── Medium momentum (20) ──
        max_pts += 20
        m20 = mom.get("momentum_20d")
        if m20 is not None:
            if m20 > 10:
                s = 20
            elif m20 > 3:
                s = 14
            elif m20 > 0:
                s = 8
            elif m20 > -5:
                s = 4
            else:
                s = 0
            components["medium_momentum"] = {"score": s, "max": 20, "value": round(m20, 2)}
            total += s
        else:
            missing.append("Động lượng trung hạn")
            components["medium_momentum"] = {"score": None, "max": 20}

        # ── Long momentum (20) ──
        max_pts += 20
        m60 = mom.get("momentum_60d")
        m120 = mom.get("momentum_120d")
        if m60 is not None or m120 is not None:
            val = (m60 or 0) * 0.5 + (m120 or 0) * 0.5
            if val > 20:
                s = 20
            elif val > 5:
                s = 14
            elif val > 0:
                s = 8
            elif val > -10:
                s = 4
            else:
                s = 0
            components["long_momentum"] = {"score": s, "max": 20, "value": round(val, 2)}
            total += s
        else:
            missing.append("Động lượng dài hạn")
            components["long_momentum"] = {"score": None, "max": 20}

        # ── Relative Strength (20) ──
        max_pts += 20
        rs = self.relative_strength()
        if rs.get("available"):
            rs_diff = rs.get("rs_differential", 0)
            if rs_diff > 10:
                s = 20
            elif rs_diff > 3:
                s = 15
            elif rs_diff > 0:
                s = 10
            elif rs_diff > -5:
                s = 5
            else:
                s = 0
            components["relative_strength"] = {"score": s, "max": 20, "value": round(rs_diff, 2)}
            total += s
        else:
            missing.append("Sức mạnh tương đối")
            components["relative_strength"] = {"score": None, "max": 20}

        # RSI (14/10/2026): đã BỎ khỏi điểm động lượng – RSI đã được chấm trong điểm Kỹ thuật (tránh tính hai lần). Vẫn trả
        # giá trị RSI để hiển thị tham khảo (không tính điểm).
        rsi = self.compute_rsi()
        info = {"rsi": round(rsi, 1) if rsi is not None else None}

        available_max = sum(c["max"] for c in components.values() if c.get("score") is not None)
        available_total = sum(c["score"] for c in components.values() if c.get("score") is not None)

        if available_max == 0:
            final_score = None
            state = "Không đủ dữ liệu"
        else:
            final_score = round((available_total / available_max) * 100)
            if final_score >= 70:
                state = "Động lượng mạnh"
            elif final_score >= 55:
                state = "Động lượng tích cực"
            elif final_score >= 40:
                state = "Trung tính"
            else:
                state = "Động lượng yếu"

        return {
            "score": final_score,
            "state": state,
            "components": components,
            "rsi_info": info,
            "momentum_periods": mom,
            "relative_strength": rs,
            "rsi": rsi,
            "missing_data": missing,
        }
