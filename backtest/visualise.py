"""
Chart generation for the EMA crossover backtest.

Chart 1 — NIFTY price with EMA lines and buy/sell markers.
Chart 2 — Portfolio equity curve vs buy-and-hold.

Charts saved to data/charts/.
"""

import os
import sys
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CHARTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "charts")


def _ensure_charts_dir() -> str:
    os.makedirs(CHARTS_DIR, exist_ok=True)
    return CHARTS_DIR


# ── Chart 1: Price + EMAs + signals ──────────────────────────────────────────

def plot_price_with_signals(df: pd.DataFrame, save: bool = True) -> str:
    """
    Plot NIFTY Close with 9 & 21 EMA, buy markers (^) and sell markers (v).
    Returns the saved file path.
    """
    charts_dir = _ensure_charts_dir()
    outpath = os.path.join(charts_dir, "ema_signals.png")

    buys = df[df["signal"] == 1]
    sells = df[df["signal"] == -1]

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")

    ax.plot(df.index, df["Close"], color="#8b9dc3", linewidth=1.0, label="NIFTY 50", zorder=1)
    ax.plot(df.index, df["EMA_9"], color="#f0b429", linewidth=1.4, label="EMA 9", zorder=2)
    ax.plot(df.index, df["EMA_21"], color="#4db8ff", linewidth=1.4, label="EMA 21", zorder=2)

    ax.scatter(buys.index, buys["Close"], marker="^", color="#00c853",
               s=80, zorder=5, label="Buy", linewidths=0.5, edgecolors="#ffffff")
    ax.scatter(sells.index, sells["Close"], marker="v", color="#ff1744",
               s=80, zorder=5, label="Sell", linewidths=0.5, edgecolors="#ffffff")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=30, ha="right")

    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")
    ax.tick_params(colors="#8b9dc3")
    ax.yaxis.label.set_color("#8b9dc3")
    ax.xaxis.label.set_color("#8b9dc3")
    ax.set_ylabel("Index Points")
    ax.set_title("NIFTY 50 — EMA Crossover Signals (9 / 21)", color="#e6edf3", fontsize=13, pad=12)
    ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="#e6edf3", fontsize=9)
    ax.grid(color="#21262d", linewidth=0.5, zorder=0)

    plt.tight_layout()
    if save:
        plt.savefig(outpath, dpi=150, bbox_inches="tight")
        print(f"Saved: {outpath}")
    plt.close()
    return outpath


# ── Chart 2: Equity curve ─────────────────────────────────────────────────────

def plot_equity_curve(equity: pd.Series, bnh_equity: pd.Series,
                      save: bool = True) -> str:
    """
    Plot strategy equity curve vs buy-and-hold.
    Returns the saved file path.
    """
    charts_dir = _ensure_charts_dir()
    outpath = os.path.join(charts_dir, "equity_curve.png")

    fig, ax = plt.subplots(figsize=(14, 5))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")

    ax.plot(equity.index, equity, color="#00c853", linewidth=1.6,
            label="EMA Strategy", zorder=2)
    ax.plot(bnh_equity.index, bnh_equity, color="#4db8ff", linewidth=1.6,
            linestyle="--", label="Buy & Hold", zorder=2)

    ax.fill_between(equity.index, equity, bnh_equity,
                    where=(equity >= bnh_equity), interpolate=True,
                    color="#00c853", alpha=0.08, label="Outperformance")
    ax.fill_between(equity.index, equity, bnh_equity,
                    where=(equity < bnh_equity), interpolate=True,
                    color="#ff1744", alpha=0.08, label="Underperformance")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=30, ha="right")

    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")
    ax.tick_params(colors="#8b9dc3")
    ax.set_ylabel("Portfolio Value (₹)", color="#8b9dc3")
    ax.set_title("Equity Curve — EMA Strategy vs Buy & Hold", color="#e6edf3", fontsize=13, pad=12)
    ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="#e6edf3", fontsize=9)
    ax.grid(color="#21262d", linewidth=0.5, zorder=0)

    plt.tight_layout()
    if save:
        plt.savefig(outpath, dpi=150, bbox_inches="tight")
        print(f"Saved: {outpath}")
    plt.close()
    return outpath


# ── Chart 3: v1 vs v2 vs B&H equity comparison ───────────────────────────────

def plot_comparison_equity(symbol: str,
                           equity_v1: pd.Series,
                           equity_v2: pd.Series,
                           bnh_equity: pd.Series,
                           save: bool = True) -> str:
    """
    Three-line equity curve: v1, v2, and buy-and-hold.
    One chart per symbol, saved to data/charts/compare_<symbol>.png.
    """
    charts_dir = _ensure_charts_dir()
    safe_sym   = symbol.replace("^", "").replace(".", "_")
    outpath    = os.path.join(charts_dir, f"compare_{safe_sym}.png")

    fig, ax = plt.subplots(figsize=(14, 5))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")

    ax.plot(equity_v1.index, equity_v1, color="#f0b429", linewidth=1.5,
            label="v1 · EMA crossover only", zorder=3)
    ax.plot(equity_v2.index, equity_v2, color="#00c853", linewidth=1.5,
            label="v2 · + ADX / RSI / ATR stop", zorder=4)
    ax.plot(bnh_equity.index, bnh_equity, color="#4db8ff", linewidth=1.3,
            linestyle="--", label="Buy & Hold", zorder=2)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=30, ha="right")

    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")
    ax.tick_params(colors="#8b9dc3")
    ax.set_ylabel("Portfolio Value (₹)", color="#8b9dc3")
    ax.set_title(f"v1 vs v2 vs Buy & Hold — {symbol}",
                 color="#e6edf3", fontsize=13, pad=12)
    ax.legend(facecolor="#161b22", edgecolor="#30363d",
              labelcolor="#e6edf3", fontsize=9)
    ax.grid(color="#21262d", linewidth=0.5, zorder=0)

    plt.tight_layout()
    if save:
        plt.savefig(outpath, dpi=150, bbox_inches="tight")
    plt.close()
    return outpath


if __name__ == "__main__":
    from engine import run_backtest
    r = run_backtest()
    plot_price_with_signals(r["df"])
    plot_equity_curve(r["equity"], r["bnh_equity"])
