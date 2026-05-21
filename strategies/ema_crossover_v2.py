"""
EMA Crossover v2 — ADX trend filter + RSI filter + ATR stop-loss.

Entry rules (ALL must pass):
  1. EMA 9 crosses above EMA 21        — momentum signal
  2. ADX(14) > 25                      — confirms a real trend, filters sideways chop
  3. RSI(14) between 40 and 70         — avoids overbought entries & deep oversold traps

Exit rules (first hit wins):
  A. EMA 9 crosses below EMA 21        — original trend-reversal exit
  B. Low price ≤ entry − 2 × ATR      — stop-loss; handled in the backtester loop
"""

import pandas as pd
import numpy as np

# ── parameters ────────────────────────────────────────────────────────────────
FAST_EMA       = 9
SLOW_EMA       = 21
ADX_PERIOD     = 14
ADX_THRESHOLD  = 25
RSI_PERIOD     = 14
RSI_LOW        = 40
RSI_HIGH       = 70
ATR_PERIOD     = 14
ATR_MULTIPLIER = 2.0   # exported so engine.py can import it


# ── indicator helpers ─────────────────────────────────────────────────────────

def _wilder(series: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothed moving average (alpha = 1/period)."""
    return series.ewm(alpha=1.0 / period, adjust=False).mean()


def compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """Average True Range."""
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift(1)).abs(),
        (df["Low"]  - df["Close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    return _wilder(tr, period)


def compute_adx(df: pd.DataFrame, period: int = ADX_PERIOD) -> pd.Series:
    """Average Directional Index."""
    up   = df["High"] - df["High"].shift(1)
    down = df["Low"].shift(1) - df["Low"]

    plus_dm  = pd.Series(0.0, index=df.index)
    minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[ (up > down)   & (up > 0)]   = up[  (up > down)   & (up > 0)]
    minus_dm[(down > up)   & (down > 0)] = down[(down > up)   & (down > 0)]

    atr          = compute_atr(df, period)
    plus_di      = 100 * _wilder(plus_dm,  period) / atr
    minus_di     = 100 * _wilder(minus_dm, period) / atr

    denom = (plus_di + minus_di).replace(0, np.nan)
    dx    = 100 * (plus_di - minus_di).abs() / denom
    return _wilder(dx.fillna(0), period)


def compute_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Relative Strength Index."""
    delta    = close.diff()
    avg_gain = delta.clip(lower=0).ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = (-delta).clip(lower=0).ewm(alpha=1.0 / period, adjust=False).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


# ── main signal builder ───────────────────────────────────────────────────────

def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds indicators and filtered signals to a copy of *df*.

    Extra columns vs v1:  ADX, ATR, RSI
    signal: 1 = filtered buy, -1 = sell, 0 = hold
    """
    df = df.copy()

    df["EMA_9"]  = df["Close"].ewm(span=FAST_EMA, adjust=False).mean()
    df["EMA_21"] = df["Close"].ewm(span=SLOW_EMA, adjust=False).mean()
    df["ADX"]    = compute_adx(df)
    df["ATR"]    = compute_atr(df)
    df["RSI"]    = compute_rsi(df["Close"])

    prev_fast = df["EMA_9"].shift(1)
    prev_slow = df["EMA_21"].shift(1)

    cross_above = (df["EMA_9"] > df["EMA_21"]) & (prev_fast <= prev_slow)
    cross_below = (df["EMA_9"] < df["EMA_21"]) & (prev_fast >= prev_slow)

    # Filters on the buy side only
    adx_ok  = df["ADX"] > ADX_THRESHOLD
    rsi_ok  = df["RSI"].between(RSI_LOW, RSI_HIGH)

    df["signal"] = 0
    df.loc[cross_above & adx_ok & rsi_ok, "signal"] = 1
    df.loc[cross_below,                   "signal"] = -1

    df.dropna(subset=["EMA_9", "EMA_21", "ADX", "ATR", "RSI"], inplace=True)
    return df
