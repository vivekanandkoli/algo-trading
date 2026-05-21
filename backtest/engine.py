"""
Backtesting engine — supports EMA v1 (vectorised) and v2 (event-driven + stop-loss).
"""

import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kite_connector import fetch_historical

TRANSACTION_COST      = 0.0005   # 0.05% per side (0.10% round-trip)
INITIAL_CAPITAL       = 100_000  # ₹1,00,000 notional
TRADING_DAYS_PER_YEAR = 252


# ── shared metric helpers ─────────────────────────────────────────────────────

def _sharpe(returns: pd.Series, risk_free: float = 0.065) -> float:
    """Annualised Sharpe ratio (India 10-yr ≈ 6.5% risk-free).
    Returns 0 when there are fewer than 30 non-zero return days or std ≈ 0."""
    if returns.empty or (returns != 0).sum() < 30:
        return 0.0
    excess = returns - (risk_free / TRADING_DAYS_PER_YEAR)
    std = excess.std()
    if std < 1e-8:
        return 0.0
    return float((excess.mean() / std) * np.sqrt(TRADING_DAYS_PER_YEAR))


def _max_drawdown(equity: pd.Series) -> float:
    """Max peak-to-trough drawdown as a percentage (negative number)."""
    roll_max  = equity.cummax()
    drawdown  = (equity - roll_max) / roll_max
    return float(drawdown.min() * 100)


def _win_rate_from_signals(df: pd.DataFrame) -> tuple:
    """
    Win-rate for v1: scan buy→sell pairs in signal column.
    Returns (win_rate_pct, num_trades).
    """
    trades, entry_price = [], None
    for _, row in df.iterrows():
        if row["signal"] == 1 and entry_price is None:
            entry_price = row["Close"]
        elif row["signal"] == -1 and entry_price is not None:
            net = (row["Close"] / entry_price) - 1 - 2 * TRANSACTION_COST
            trades.append(net)
            entry_price = None
    if not trades:
        return 0.0, 0
    wins = sum(1 for t in trades if t > 0)
    return float(wins / len(trades) * 100), len(trades)


def _metrics(equity: pd.Series, bnh_equity: pd.Series,
             trades: list, df: pd.DataFrame, symbol: str) -> dict:
    """Assemble the standard results dict from computed equity curves."""
    total_return = (equity.iloc[-1] / INITIAL_CAPITAL - 1) * 100
    bnh_return   = (bnh_equity.iloc[-1] / INITIAL_CAPITAL - 1) * 100
    eq_returns   = equity.pct_change().dropna()
    num_trades   = len(trades)
    win_rate     = (sum(1 for t in trades if t > 0) / max(num_trades, 1)) * 100

    return {
        "symbol":           symbol,
        "total_return_pct": round(total_return, 2),
        "bnh_return_pct":   round(bnh_return,   2),
        "sharpe":           round(_sharpe(eq_returns),    3),
        "max_drawdown_pct": round(_max_drawdown(equity),  2),
        "win_rate_pct":     round(win_rate,  2),
        "num_trades":       num_trades,
        "equity":           equity,
        "bnh_equity":       bnh_equity,
        "df":               df,
    }


# ── v1: vectorised backtester ─────────────────────────────────────────────────

def _run_v1(df: pd.DataFrame, symbol: str) -> dict:
    df = df.copy()
    df["daily_return"]    = df["Close"].pct_change()
    df["strategy_return"] = df["position"].shift(1) * df["daily_return"]
    df.loc[df["signal"] != 0, "strategy_return"] -= TRANSACTION_COST

    df["equity"]     = INITIAL_CAPITAL * (1 + df["strategy_return"].fillna(0)).cumprod()
    df["bnh_equity"] = INITIAL_CAPITAL * (1 + df["daily_return"].fillna(0)).cumprod()

    win_rate, num_trades = _win_rate_from_signals(df)
    trades = [win_rate] * num_trades   # placeholder list just for count/win-rate

    # Rebuild real trade list for _metrics win-rate calc
    real_trades, ep = [], None
    for _, row in df.iterrows():
        if row["signal"] == 1 and ep is None:
            ep = row["Close"]
        elif row["signal"] == -1 and ep is not None:
            real_trades.append((row["Close"] / ep) - 1 - 2 * TRANSACTION_COST)
            ep = None

    return _metrics(df["equity"], df["bnh_equity"], real_trades, df, symbol)


# ── v2: event-driven backtester with ATR stop-loss ────────────────────────────

def _run_v2(df: pd.DataFrame, symbol: str) -> dict:
    from strategies.ema_crossover_v2 import ATR_MULTIPLIER

    capital     = float(INITIAL_CAPITAL)
    position    = 0       # 0=flat, 1=long
    entry_price = 0.0
    stop_level  = 0.0
    shares      = 0.0     # fractional units held
    inv_capital = 0.0     # capital committed at entry (after buy cost)
    trades      = []
    equity_curve = []

    for _, row in df.iterrows():
        # ── check exits ────────────────────────────────────────────────────
        if position == 1:
            stop_hit = (row["Low"] <= stop_level)
            ema_exit = (row["signal"] == -1)

            if stop_hit or ema_exit:
                exit_px  = stop_level if stop_hit else row["Close"]
                # proceeds = shares sold × exit price × (1 − sell cost)
                proceeds = shares * exit_px * (1 - TRANSACTION_COST)
                trades.append(proceeds / inv_capital - 1)
                capital  = proceeds
                position = 0

        # ── check entry ────────────────────────────────────────────────────
        if position == 0 and row["signal"] == 1:
            entry_price = row["Close"]
            stop_level  = entry_price - ATR_MULTIPLIER * row["ATR"]
            # buy: spend capital; get shares net of buy cost
            inv_capital = capital               # what we put in (before buy cost)
            shares      = capital * (1 - TRANSACTION_COST) / entry_price
            position    = 1

        # ── mark-to-market ─────────────────────────────────────────────────
        equity_curve.append(shares * row["Close"] if position == 1 else capital)

    equity     = pd.Series(equity_curve, index=df.index)
    bnh_equity = INITIAL_CAPITAL * (df["Close"] / df["Close"].iloc[0])

    return _metrics(equity, bnh_equity, trades, df, symbol)


# ── public API ────────────────────────────────────────────────────────────────

def run_backtest(symbol: str = "^NSEI", period: str = "2y",
                 version: str = "v1") -> dict:
    """
    Fetch data, apply strategy, run backtest, return results dict.

    Args:
        symbol  : NSE ticker or index ("^NSEI", "RELIANCE.NS", …)
        period  : yfinance period string ("2y", "1y", "5y", …)
        version : "v1" (original EMA crossover) | "v2" (+ ADX/RSI/ATR-stoploss)
    """
    raw = fetch_historical(symbol, period=period)

    if version == "v1":
        from strategies.ema_crossover import add_signals
        df = add_signals(raw)
        return _run_v1(df, symbol)
    elif version == "v2":
        from strategies.ema_crossover_v2 import add_signals
        df = add_signals(raw)
        return _run_v2(df, symbol)
    else:
        raise ValueError(f"Unknown version '{version}'. Use 'v1' or 'v2'.")


def print_results(r: dict, label: str = "") -> None:
    tag = f" [{label}]" if label else ""
    sep = "─" * 42
    print(f"\n{sep}")
    print(f"  EMA Crossover Backtest{tag} — {r['symbol']}")
    print(sep)
    print(f"  Strategy return  : {r['total_return_pct']:+.2f}%")
    print(f"  Buy & Hold return: {r['bnh_return_pct']:+.2f}%")
    print(f"  Sharpe ratio     : {r['sharpe']:.3f}")
    print(f"  Max drawdown     : {r['max_drawdown_pct']:.2f}%")
    print(f"  Win rate         : {r['win_rate_pct']:.1f}%")
    print(f"  Number of trades : {r['num_trades']}")
    print(sep + "\n")


if __name__ == "__main__":
    for v in ("v1", "v2"):
        print_results(run_backtest(version=v), label=v)
