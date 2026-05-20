"""
EMA Crossover strategy.

Buy  signal: 9-day EMA crosses above 21-day EMA (golden cross).
Sell signal: 9-day EMA crosses below 21-day EMA (death cross).

Uses pandas ewm() for indicator calculation — no extra dependencies.
"""

import pandas as pd

FAST_EMA = 9
SLOW_EMA = 21


def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds EMA columns and buy/sell signal flags to a copy of *df*.

    New columns added:
        EMA_9   : 9-period EMA of Close
        EMA_21  : 21-period EMA of Close
        signal  : 1 = buy, -1 = sell, 0 = hold
        position: 1 = long, 0 = flat (forward-filled from signals)
    """
    df = df.copy()

    # adjust=False matches the standard EMA formula used by most charting tools
    df["EMA_9"] = df["Close"].ewm(span=FAST_EMA, adjust=False).mean()
    df["EMA_21"] = df["Close"].ewm(span=SLOW_EMA, adjust=False).mean()

    # Detect crossovers
    prev_fast = df["EMA_9"].shift(1)
    prev_slow = df["EMA_21"].shift(1)

    cross_above = (df["EMA_9"] > df["EMA_21"]) & (prev_fast <= prev_slow)
    cross_below = (df["EMA_9"] < df["EMA_21"]) & (prev_fast >= prev_slow)

    df["signal"] = 0
    df.loc[cross_above, "signal"] = 1   # buy
    df.loc[cross_below, "signal"] = -1  # sell

    # Derive current position (1 = in trade, 0 = flat)
    # Start flat; flip on each signal
    position = 0
    positions = []
    for sig in df["signal"]:
        if sig == 1:
            position = 1
        elif sig == -1:
            position = 0
        positions.append(position)
    df["position"] = positions

    # Drop rows before both EMAs are warm
    df.dropna(subset=["EMA_9", "EMA_21"], inplace=True)

    return df


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "..")
    from kite_connector import fetch_historical

    df = fetch_historical("^NSEI", period="2y")
    df = add_signals(df)
    buys = df[df["signal"] == 1]
    sells = df[df["signal"] == -1]
    print(f"Buy signals : {len(buys)}")
    print(f"Sell signals: {len(sells)}")
    print(df[df["signal"] != 0][["Close", "EMA_9", "EMA_21", "signal"]].head(10))
