"""
Mean Reversion Strategy — Bollinger Band + RSI

Thesis: when price compresses to the lower band AND momentum is oversold,
        it tends to revert toward the mean. Exit at the upper band or when
        momentum recovers fully.

Entry  (signal = 1):
    Close  ≤ lower Bollinger Band (20-period, 2σ)
    AND RSI(14) < 35   — confirms oversold, not just a downtrending band touch

Exit   (signal = -1):
    Close  ≥ upper Bollinger Band   — mean reversion target reached
    OR  RSI(14) > 65               — momentum reversal fading into overbought
    (ATR 2× stop-loss handled by the engine loop, same as v2)

Why this complements EMA v2:
    v2 is trend-following (needs ADX > 25 to enter).
    Mean reversion thrives in the sideways/choppy markets v2 avoids.
    They should be counter-cyclical in regime exposure.
"""

import pandas as pd
import numpy as np

# ── parameters ────────────────────────────────────────────────────────────────
BB_PERIOD      = 20      # Bollinger Band look-back
BB_MULT        = 2.0     # standard deviations
RSI_PERIOD     = 14
RSI_BUY        = 35      # enter when RSI below this
RSI_SELL       = 65      # exit when RSI above this
ATR_PERIOD     = 14
ATR_MULTIPLIER = 2.0     # exported for engine


# ── indicator helpers (self-contained, no cross-strategy imports) ─────────────

def _wilder(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(alpha=1.0 / period, adjust=False).mean()


def compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift(1)).abs(),
        (df["Low"]  - df["Close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    return _wilder(tr, period)


def compute_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta    = close.diff()
    avg_gain = delta.clip(lower=0).ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = (-delta).clip(lower=0).ewm(alpha=1.0 / period, adjust=False).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


# ── main signal builder ───────────────────────────────────────────────────────

def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds Bollinger Band, RSI, ATR columns and mean-reversion signals.

    New columns:
        BB_MID, BB_UPPER, BB_LOWER   : 20-period Bollinger Bands
        BB_WIDTH                     : normalised band width (volatility proxy)
        RSI                          : 14-period RSI
        ATR                          : 14-period ATR (for stop-loss in engine)
        signal : 1 = buy, -1 = sell/exit, 0 = hold
    """
    df = df.copy()

    # Bollinger Bands
    rolling      = df["Close"].rolling(BB_PERIOD)
    df["BB_MID"]   = rolling.mean()
    bb_std         = rolling.std()
    df["BB_UPPER"] = df["BB_MID"] + BB_MULT * bb_std
    df["BB_LOWER"] = df["BB_MID"] - BB_MULT * bb_std
    df["BB_WIDTH"] = (df["BB_UPPER"] - df["BB_LOWER"]) / df["BB_MID"]

    df["RSI"] = compute_rsi(df["Close"])
    df["ATR"] = compute_atr(df)

    # Signal conditions
    at_lower_band = df["Close"] <= df["BB_LOWER"]
    oversold      = df["RSI"] < RSI_BUY

    at_upper_band = df["Close"] >= df["BB_UPPER"]
    overbought    = df["RSI"] > RSI_SELL

    buy_cond  = at_lower_band & oversold
    sell_cond = at_upper_band | overbought

    df["signal"] = 0
    df.loc[buy_cond,              "signal"] = 1
    df.loc[sell_cond & ~buy_cond, "signal"] = -1

    df.dropna(subset=["BB_MID", "RSI", "ATR"], inplace=True)
    return df


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "..")
    from kite_connector import fetch_historical

    df = fetch_historical("^NSEI", period="2y")
    df = add_signals(df)
    print(f"Buy signals : {(df['signal'] == 1).sum()}")
    print(f"Sell signals: {(df['signal'] == -1).sum()}")
    print(df[df["signal"] != 0][["Close", "BB_LOWER", "BB_UPPER", "RSI", "signal"]].head(10))
