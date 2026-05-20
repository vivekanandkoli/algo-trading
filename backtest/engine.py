"""
Backtesting engine.

Runs the EMA crossover strategy on 2 years of NIFTY 50 data
and computes standard performance metrics.
"""

import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kite_connector import fetch_historical
from strategies.ema_crossover import add_signals

TRANSACTION_COST = 0.0005   # 0.05% per trade (buy + sell = 0.10% round-trip)
INITIAL_CAPITAL = 100_000   # ₹1,00,000 notional
TRADING_DAYS_PER_YEAR = 252


# ── helpers ──────────────────────────────────────────────────────────────────

def _sharpe(returns: pd.Series, risk_free: float = 0.065) -> float:
    """Annualised Sharpe ratio. Uses 6.5% risk-free rate (approx. India 10yr)."""
    excess = returns - (risk_free / TRADING_DAYS_PER_YEAR)
    if excess.std() == 0:
        return 0.0
    return float((excess.mean() / excess.std()) * np.sqrt(TRADING_DAYS_PER_YEAR))


def _max_drawdown(equity: pd.Series) -> float:
    """Maximum peak-to-trough drawdown as a percentage."""
    roll_max = equity.cummax()
    drawdown = (equity - roll_max) / roll_max
    return float(drawdown.min() * 100)


def _win_rate(df: pd.DataFrame) -> tuple[float, int]:
    """
    Returns (win_rate_pct, num_trades) based on completed round-trip trades.
    A trade is: buy signal → next sell signal.
    """
    trades = []
    entry_price = None
    for _, row in df.iterrows():
        if row["signal"] == 1 and entry_price is None:
            entry_price = row["Close"]
        elif row["signal"] == -1 and entry_price is not None:
            exit_price = row["Close"]
            net = (exit_price / entry_price) - 1 - 2 * TRANSACTION_COST
            trades.append(net)
            entry_price = None

    if not trades:
        return 0.0, 0

    wins = sum(1 for t in trades if t > 0)
    return float(wins / len(trades) * 100), len(trades)


# ── main backtest ─────────────────────────────────────────────────────────────

def run_backtest(symbol: str = "^NSEI", period: str = "2y") -> dict:
    """
    Run the EMA crossover backtest and return a results dictionary.

    Keys:
        total_return_pct, bnh_return_pct, sharpe, max_drawdown_pct,
        win_rate_pct, num_trades, equity, bnh_equity, df
    """
    raw = fetch_historical(symbol, period=period)
    df = add_signals(raw)

    # Daily strategy returns:
    # On each day we hold the position established at the *previous* day's close.
    df["daily_return"] = df["Close"].pct_change()
    df["strategy_return"] = df["position"].shift(1) * df["daily_return"]

    # Deduct transaction cost on signal days
    df.loc[df["signal"] != 0, "strategy_return"] -= TRANSACTION_COST

    df["equity"] = INITIAL_CAPITAL * (1 + df["strategy_return"].fillna(0)).cumprod()
    df["bnh_equity"] = INITIAL_CAPITAL * (1 + df["daily_return"].fillna(0)).cumprod()

    total_return = float((df["equity"].iloc[-1] / INITIAL_CAPITAL - 1) * 100)
    bnh_return = float((df["bnh_equity"].iloc[-1] / INITIAL_CAPITAL - 1) * 100)
    sharpe = _sharpe(df["strategy_return"].dropna())
    max_dd = _max_drawdown(df["equity"])
    win_rate, num_trades = _win_rate(df)

    return {
        "total_return_pct": round(total_return, 2),
        "bnh_return_pct": round(bnh_return, 2),
        "sharpe": round(sharpe, 3),
        "max_drawdown_pct": round(max_dd, 2),
        "win_rate_pct": round(win_rate, 2),
        "num_trades": num_trades,
        "equity": df["equity"],
        "bnh_equity": df["bnh_equity"],
        "df": df,
    }


def print_results(r: dict) -> None:
    sep = "─" * 40
    print(f"\n{sep}")
    print("  EMA Crossover Backtest — NIFTY 50")
    print(sep)
    print(f"  Strategy return  : {r['total_return_pct']:+.2f}%")
    print(f"  Buy & Hold return: {r['bnh_return_pct']:+.2f}%")
    print(f"  Sharpe ratio     : {r['sharpe']:.3f}")
    print(f"  Max drawdown     : {r['max_drawdown_pct']:.2f}%")
    print(f"  Win rate         : {r['win_rate_pct']:.1f}%")
    print(f"  Number of trades : {r['num_trades']}")
    print(sep + "\n")


if __name__ == "__main__":
    results = run_backtest()
    print_results(results)
