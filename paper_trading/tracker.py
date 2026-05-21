"""
Paper trade status viewer.

Reads data/paper_trades.csv and shows a live dashboard:
  - Open positions with unrealised P&L (fetches current price)
  - Closed trade history
  - Summary statistics

Usage:
    python3 paper_trading/tracker.py
"""

import os
import sys
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kite_connector import fetch_historical

TRADES_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "paper_trades.csv")


def _current_price(symbol: str) -> float:
    """Fetch the most recent close price for a symbol."""
    try:
        df = fetch_historical(symbol, period="5d", interval="1d")
        return float(df.iloc[-1]["Close"])
    except Exception:
        return None


def _colour(val: float) -> str:
    """ANSI colour: green for positive, red for negative."""
    if val > 0:
        return f"\033[92m{val:+.2f}%\033[0m"
    elif val < 0:
        return f"\033[91m{val:+.2f}%\033[0m"
    return f"{val:+.2f}%"


def show_status() -> None:
    if not os.path.exists(TRADES_CSV):
        print("\n  No paper trades found. Run: python3 paper_trading/logger.py\n")
        return

    trades = pd.read_csv(TRADES_CSV)
    now    = datetime.now().strftime("%Y-%m-%d %H:%M")
    sep    = "─" * 70

    print(f"\n{sep}")
    print(f"  📋  Paper Trade Dashboard  ·  {now}")
    print(sep)

    # ── open positions ────────────────────────────────────────────────────
    open_df = trades[trades["status"] == "OPEN"]

    if open_df.empty:
        print("\n  OPEN POSITIONS: none\n")
    else:
        print(f"\n  OPEN POSITIONS ({len(open_df)})\n")
        print(f"  {'#':<4} {'Symbol':<14} {'Entry Date':<12} {'Entry ₹':<10}"
              f"{'Stop ₹':<10} {'Now ₹':<10} {'P&L'}")
        print(f"  {'─'*4} {'─'*14} {'─'*12} {'─'*10} {'─'*10} {'─'*10} {'─'*8}")

        for _, row in open_df.iterrows():
            cur  = _current_price(row["symbol"])
            ep   = float(row["entry_price"])
            sl   = float(row["stop_loss"])
            unrl = round((cur / ep - 1) * 100, 2) if cur else None

            cur_str  = f"{cur:.2f}" if cur else "N/A"
            pnl_str  = _colour(unrl) if unrl is not None else "N/A"
            sl_pct   = round((sl / ep - 1) * 100, 1)

            print(f"  {int(row['trade_id']):<4} {row['symbol']:<14} "
                  f"{row['entry_date']:<12} {ep:<10.2f}"
                  f"{sl:<10.2f} {cur_str:<10} {pnl_str}"
                  f"  (stop {sl_pct:.1f}%)")

    # ── closed trades ─────────────────────────────────────────────────────
    closed_df = trades[trades["status"] == "CLOSED"]

    if not closed_df.empty:
        print(f"\n  CLOSED TRADES ({len(closed_df)})\n")
        print(f"  {'#':<4} {'Symbol':<14} {'Entry':<12} {'Exit':<12}"
              f"{'Entry ₹':<10} {'Exit ₹':<10} {'P&L':<10} {'Reason'}")
        print(f"  {'─'*4} {'─'*14} {'─'*12} {'─'*12}"
              f"{'─'*10} {'─'*10} {'─'*10} {'─'*14}")

        for _, row in closed_df.sort_values("exit_date", ascending=False).iterrows():
            pnl     = float(row["pnl_pct"]) if row["pnl_pct"] != "" else 0
            pnl_str = _colour(pnl)
            print(f"  {int(row['trade_id']):<4} {row['symbol']:<14} "
                  f"{row['entry_date']:<12} {str(row['exit_date']):<12}"
                  f"{float(row['entry_price']):<10.2f} "
                  f"{float(row['exit_price']):<10.2f} "
                  f"{pnl_str:<10}  {row['exit_reason']}")

    # ── summary ───────────────────────────────────────────────────────────
    print(f"\n{sep}")
    total  = len(trades)
    closed = len(closed_df)

    if closed > 0:
        pnls     = closed_df["pnl_pct"].astype(float)
        wins     = (pnls > 0).sum()
        avg_pnl  = pnls.mean()
        total_rt = (1 + pnls / 100).prod() - 1   # compounded return

        print(f"\n  SUMMARY  ·  {total} total trades  ·  {closed} closed  ·  "
              f"{len(open_df)} open")
        print(f"  Win rate    : {wins}/{closed} ({wins/closed*100:.0f}%)")
        print(f"  Avg P&L     : {_colour(avg_pnl)}")
        print(f"  Compounded  : {_colour(total_rt * 100)}")

        # Best / worst
        best  = closed_df.loc[pnls.idxmax()]
        worst = closed_df.loc[pnls.idxmin()]
        print(f"  Best trade  : {best['symbol']} on {best['entry_date']}"
              f"  {_colour(float(best['pnl_pct']))}")
        print(f"  Worst trade : {worst['symbol']} on {worst['entry_date']}"
              f"  {_colour(float(worst['pnl_pct']))}")
    else:
        print(f"\n  {total} trade(s) logged  ·  none closed yet")

    print(f"\n  Log file: {os.path.abspath(TRADES_CSV)}\n")


if __name__ == "__main__":
    show_status()
