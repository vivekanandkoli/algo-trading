"""
Multi-symbol comparison: EMA v1 vs EMA v2 (ADX + RSI + ATR stop-loss).

Symbols: ^NSEI, RELIANCE.NS, HDFCBANK.NS, TCS.NS, INFY.NS
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from backtest.engine import run_backtest
from backtest.visualise import plot_comparison_equity

SYMBOLS = ["^NSEI", "RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS"]
PERIOD  = "2y"

COLS = ["Symbol", "Return v1", "Return v2", "B&H", "Sharpe v1", "Sharpe v2",
        "MaxDD v1", "MaxDD v2", "WinRate v1", "WinRate v2", "Trades v1", "Trades v2"]

COL_W = [14, 10, 10, 8, 10, 10, 10, 10, 11, 11, 10, 10]


def _fmt_row(vals):
    return "  ".join(str(v).rjust(w) for v, w in zip(vals, COL_W))


def _header():
    sep = "─" * (sum(COL_W) + 2 * (len(COL_W) - 1))
    print("\n" + sep)
    print(_fmt_row(COLS))
    print(sep)
    return sep


def main():
    all_v1, all_v2 = {}, {}

    for sym in SYMBOLS:
        print(f"  Fetching & backtesting {sym} …")
        all_v1[sym] = run_backtest(sym, period=PERIOD, version="v1")
        all_v2[sym] = run_backtest(sym, period=PERIOD, version="v2")

    sep = _header()

    for sym in SYMBOLS:
        v1 = all_v1[sym]
        v2 = all_v2[sym]
        row = [
            sym,
            f"{v1['total_return_pct']:+.1f}%",
            f"{v2['total_return_pct']:+.1f}%",
            f"{v1['bnh_return_pct']:+.1f}%",
            f"{v1['sharpe']:+.2f}",
            f"{v2['sharpe']:+.2f}",
            f"{v1['max_drawdown_pct']:.1f}%",
            f"{v2['max_drawdown_pct']:.1f}%",
            f"{v1['win_rate_pct']:.0f}%",
            f"{v2['win_rate_pct']:.0f}%",
            str(v1['num_trades']),
            str(v2['num_trades']),
        ]
        print(_fmt_row(row))

    print(sep)

    # ── legend ──────────────────────────────────────────────────────────────
    print("""
  v1 = EMA 9/21 crossover only
  v2 = + ADX>25 trend filter  +  RSI 40–70 filter  +  2×ATR stop-loss
  B&H = Buy & Hold (benchmark)
  MaxDD = max drawdown  |  WinRate = % of winning round-trips
""")

    # ── charts ───────────────────────────────────────────────────────────────
    print("Generating equity-curve comparison charts …")
    for sym in SYMBOLS:
        path = plot_comparison_equity(
            sym,
            all_v1[sym]["equity"],
            all_v2[sym]["equity"],
            all_v1[sym]["bnh_equity"],
        )
        print(f"  Saved: {path}")

    print("\nDone.  Charts saved to data/charts/\n")


if __name__ == "__main__":
    main()
