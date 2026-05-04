"""
Pure-Python Technical Analysis Engine
Implements standard indicators from scratch using only pandas/numpy.
No ta-lib or pandas-ta dependencies.
"""

import pandas as pd
import numpy as np


class TechnicalAnalyzer:
    """Computes technical indicators from a price DataFrame."""

    def analyze(self, ticker: str, price_df: pd.DataFrame) -> dict:
        """
        price_df must have columns: Open, High, Low, Close, Volume
        Index should be datetime.
        Returns a dict with all indicator values.
        """
        df = price_df.copy()
        if len(df) < 2:
            return {"error": "Insufficient data for technical analysis"}

        result = {}
        result.update(self._sma_crossover(df))
        result.update(self._rsi(df))
        result.update(self._macd(df))
        result.update(self._bollinger(df))
        result.update(self._volume_analysis(df))
        result.update(self._trend_detection(df))
        result.update(self._support_resistance(df))
        result.update(self._atr(df))
        result.update(self._overall_signal(result))
        return result

    # ------------------------------------------------------------------ #
    # 1. SMA Crossover
    # ------------------------------------------------------------------ #
    def _sma_crossover(self, df: pd.DataFrame) -> dict:
        close = df["Close"]
        sma_20 = close.rolling(window=20, min_periods=1).mean().iloc[-1]
        sma_50 = close.rolling(window=50, min_periods=1).mean().iloc[-1]
        sma_200 = close.rolling(window=200, min_periods=1).mean().iloc[-1]

        current_cross = sma_20 > sma_50

        if len(close) >= 6:
            past_sma_20 = close.rolling(window=20, min_periods=1).mean().iloc[-6]
            past_sma_50 = close.rolling(window=50, min_periods=1).mean().iloc[-6]
            past_cross = past_sma_20 > past_sma_50
        else:
            past_cross = current_cross

        if current_cross and not past_cross:
            signal = "bullish"
        elif not current_cross and past_cross:
            signal = "bearish"
        else:
            signal = "neutral"

        return {
            "sma_20": self._f4(sma_20),
            "sma_50": self._f4(sma_50),
            "sma_200": self._f4(sma_200),
            "sma_signal": signal,
        }

    # ------------------------------------------------------------------ #
    # 2. RSI (14-period, Wilder's smoothing)
    # ------------------------------------------------------------------ #
    def _rsi(self, df: pd.DataFrame) -> dict:
        close = df["Close"]
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        # Wilder's smoothing: alpha = 1 / 14  =>  com = 13
        avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        # Handle zero-loss edge case: RSI = 100 when no losses, 50 when neither
        zero_loss = avg_loss == 0
        rsi = rsi.where(~zero_loss, np.where(avg_gain > 0, 100.0, 50.0))
        rsi_14 = rsi.iloc[-1]

        if pd.isna(rsi_14):
            rsi_signal = "neutral"
        elif rsi_14 > 70:
            rsi_signal = "overbought"
        elif rsi_14 < 30:
            rsi_signal = "oversold"
        else:
            rsi_signal = "neutral"

        return {
            "rsi_14": self._f2(rsi_14),
            "rsi_signal": rsi_signal,
        }

    # ------------------------------------------------------------------ #
    # 3. MACD
    # ------------------------------------------------------------------ #
    def _macd(self, df: pd.DataFrame) -> dict:
        close = df["Close"]
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        macd_val = macd_line.iloc[-1]
        signal_val = signal_line.iloc[-1]

        if len(macd_line) >= 4:
            past_macd = macd_line.iloc[-4]
            past_signal = signal_line.iloc[-4]
        else:
            past_macd = macd_val
            past_signal = signal_val

        current_cross = macd_val > signal_val
        past_cross = past_macd > past_signal

        if current_cross and not past_cross:
            macd_signal = "bullish"
        elif not current_cross and past_cross:
            macd_signal = "bearish"
        else:
            macd_signal = "neutral"

        return {
            "macd": self._f4(macd_val),
            "macd_signal": macd_signal,
            "macd_histogram": self._f4(histogram.iloc[-1]),
        }

    # ------------------------------------------------------------------ #
    # 4. Bollinger Bands
    # ------------------------------------------------------------------ #
    def _bollinger(self, df: pd.DataFrame) -> dict:
        close = df["Close"]
        sma_20 = close.rolling(window=20, min_periods=1).mean()
        std_20 = close.rolling(window=20, min_periods=1).std()
        upper = sma_20 + 2 * std_20
        lower = sma_20 - 2 * std_20

        last_close = close.iloc[-1]
        upper_val = upper.iloc[-1]
        lower_val = lower.iloc[-1]
        middle_val = sma_20.iloc[-1]

        if last_close > upper_val:
            position = "upper"
        elif last_close < lower_val:
            position = "lower"
        else:
            position = "middle"

        bb_width = (upper_val - lower_val) / middle_val if middle_val and pd.notna(middle_val) else None

        return {
            "bb_position": position,
            "bb_width": self._f4(bb_width),
        }

    # ------------------------------------------------------------------ #
    # 5. Volume Analysis
    # ------------------------------------------------------------------ #
    def _volume_analysis(self, df: pd.DataFrame) -> dict:
        volume = df["Volume"]
        vol_sma_20 = volume.rolling(window=20, min_periods=1).mean().iloc[-1]
        last_vol = volume.iloc[-1]

        if pd.isna(vol_sma_20) or vol_sma_20 == 0:
            trend = "normal"
        elif last_vol > 1.5 * vol_sma_20:
            trend = "increasing"
        elif last_vol < 0.5 * vol_sma_20:
            trend = "decreasing"
        else:
            trend = "normal"

        # On-Balance Volume (cumulative)
        obv = 0
        close_vals = df["Close"].values
        vol_vals = volume.values
        for i in range(1, len(close_vals)):
            if close_vals[i] > close_vals[i - 1]:
                obv += vol_vals[i]
            elif close_vals[i] < close_vals[i - 1]:
                obv -= vol_vals[i]
            # equal: no change

        return {
            "volume_sma_20": int(vol_sma_20) if pd.notna(vol_sma_20) else None,
            "volume_trend": trend,
            "obv": int(obv),
        }

    # ------------------------------------------------------------------ #
    # 6. Trend Detection
    # ------------------------------------------------------------------ #
    def _trend_detection(self, df: pd.DataFrame) -> dict:
        if len(df) >= 5:
            highs = df["High"].iloc[-5:].values
            lows = df["Low"].iloc[-5:].values
        else:
            highs = df["High"].values
            lows = df["Low"].values

        higher_highs = all(highs[i] > highs[i - 1] for i in range(1, len(highs)))
        higher_lows = all(lows[i] > lows[i - 1] for i in range(1, len(lows)))
        lower_highs = all(highs[i] < highs[i - 1] for i in range(1, len(highs)))
        lower_lows = all(lows[i] < lows[i - 1] for i in range(1, len(lows)))

        if higher_highs and higher_lows:
            trend = "uptrend"
        elif lower_highs and lower_lows:
            trend = "downtrend"
        else:
            trend = "sideways"

        return {
            "higher_highs": bool(higher_highs),
            "higher_lows": bool(higher_lows),
            "trend": trend,
        }

    # ------------------------------------------------------------------ #
    # 7. Support / Resistance
    # ------------------------------------------------------------------ #
    def _support_resistance(self, df: pd.DataFrame) -> dict:
        window = df.iloc[-20:] if len(df) >= 20 else df
        support = window["Low"].min()
        resistance = window["High"].max()

        return {
            "support": self._f4(support),
            "resistance": self._f4(resistance),
        }

    # ------------------------------------------------------------------ #
    # 8. ATR (14-period, Wilder's smoothing)
    # ------------------------------------------------------------------ #
    def _atr(self, df: pd.DataFrame) -> dict:
        high = df["High"]
        low = df["Low"]
        close = df["Close"]

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean().iloc[-1]

        return {
            "atr_14": self._f4(atr),
        }

    # ------------------------------------------------------------------ #
    # 9. Overall Signal
    # ------------------------------------------------------------------ #
    def _overall_signal(self, result: dict) -> dict:
        score = 0

        sma_signal = result.get("sma_signal", "neutral")
        if sma_signal == "bullish":
            score += 20
        elif sma_signal == "bearish":
            score -= 20

        rsi_signal = result.get("rsi_signal", "neutral")
        if rsi_signal == "oversold":
            score += 15
        elif rsi_signal == "overbought":
            score -= 15

        macd_signal = result.get("macd_signal", "neutral")
        if macd_signal == "bullish":
            score += 20
        elif macd_signal == "bearish":
            score -= 20

        trend = result.get("trend", "sideways")
        if trend == "uptrend":
            score += 15
        elif trend == "downtrend":
            score -= 15

        bb_position = result.get("bb_position", "middle")
        if bb_position == "lower":
            score += 10
        elif bb_position == "upper":
            score -= 10

        score = max(-100, min(100, int(score)))

        if score >= 60:
            overall = "strong_buy"
        elif score >= 30:
            overall = "buy"
        elif score >= -29:
            overall = "hold"
        elif score >= -59:
            overall = "sell"
        else:
            overall = "strong_sell"

        return {
            "composite_score": score,
            "overall_signal": overall,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _f4(val):
        return round(float(val), 4) if pd.notna(val) and val is not None else None

    @staticmethod
    def _f2(val):
        return round(float(val), 2) if pd.notna(val) and val is not None else None
