"""
Paper trade logger for EMA v2 strategy.

Scans each symbol daily, detects signals from the v2 strategy,
and logs entries/exits to data/paper_trades.csv.

Usage:
    python3 paper_trading/logger.py           # scan all symbols
    python3 paper_trading/logger.py --dry-run # show signals without saving
"""

import os
import sys
import argparse
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kite_connector import fetch_historical
from strategies.ema_crossover_v2 import add_signals, ATR_MULTIPLIER

# ── config ────────────────────────────────────────────────────────────────────
SYMBOLS    = ["^NSEI", "RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS"]
TRADES_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "paper_trades.csv")

COLUMNS = [
    "trade_id", "symbol",
    "entry_date", "entry_price", "stop_loss",
    "exit_date",  "exit_price",  "exit_reason",
    "pnl_pct",    "status",
]


# ── CSV helpers ───────────────────────────────────────────────────────────────

def load_trades() -> pd.DataFrame:
    os.makedirs(os.path.dirname(TRADES_CSV), exist_ok=True)
    if os.path.exists(TRADES_CSV):
        df = pd.read_csv(TRADES_CSV, dtype={"trade_id": int})
        return df
    return pd.DataFrame(columns=COLUMNS)


def save_trades(df: pd.DataFrame) -> None:
    df.to_csv(TRADES_CSV, index=False)


def next_id(df: pd.DataFrame) -> int:
    return 1 if df.empty else int(df["trade_id"].max()) + 1


# ── signal detection ──────────────────────────────────────────────────────────

def get_latest_signals(symbol: str) -> dict:
    """
    Fetch latest data for *symbol* and return a dict with:
        signal      : 'BUY' | 'SELL' | None  (today's signal)
        last_close  : float
        atr         : float
        stop_loss   : float  (only meaningful on BUY)
        date        : str    (most recent bar date)
        in_uptrend  : bool   (EMA9 > EMA21 right now)
    """
    try:
        df = fetch_historical(symbol, period="6mo", interval="1d")
        df = add_signals(df)
    except Exception as e:
        print(f"  [WARN] {symbol}: {e}")
        return None

    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else latest

    sig = None
    if latest["signal"] == 1:
        sig = "BUY"
    elif latest["signal"] == -1:
        sig = "SELL"

    return {
        "signal":     sig,
        "date":       str(latest.name.date()),
        "last_close": round(float(latest["Close"]), 2),
        "atr":        round(float(latest["ATR"]), 2),
        "stop_loss":  round(float(latest["Close"]) - ATR_MULTIPLIER * float(latest["ATR"]), 2),
        "in_uptrend": bool(latest["EMA_9"] > latest["EMA_21"]),
        "adx":        round(float(latest["ADX"]), 1),
        "rsi":        round(float(latest["RSI"]), 1),
    }


def check_stop_hit(symbol: str, stop_loss: float) -> tuple:
    """
    Check if today's candle traded below stop_loss.
    Returns (hit: bool, low_price: float).
    """
    try:
        df = fetch_historical(symbol, period="5d", interval="1d")
        today_low = float(df.iloc[-1]["Low"])
        today_close = float(df.iloc[-1]["Close"])
        return today_low <= stop_loss, round(min(stop_loss, today_close), 2)
    except Exception:
        return False, stop_loss


# ── main scanner ──────────────────────────────────────────────────────────────

def scan_and_log(dry_run: bool = False) -> None:
    trades   = load_trades()
    today    = datetime.now().strftime("%Y-%m-%d")
    new_rows = []
    updates  = []

    print(f"\n{'─'*55}")
    print(f"  Paper Trade Scanner  ·  {today}")
    print(f"{'─'*55}")

    open_positions = set(
        trades.loc[trades["status"] == "OPEN", "symbol"].tolist()
    )

    for sym in SYMBOLS:
        print(f"\n  {sym}")
        info = get_latest_signals(sym)
        if info is None:
            continue

        print(f"    Close={info['last_close']}  ATR={info['atr']}"
              f"  ADX={info['adx']}  RSI={info['rsi']}"
              f"  Trend={'▲' if info['in_uptrend'] else '▼'}")

        # ── handle open position ────────────────────────────────────────
        if sym in open_positions:
            open_trade = trades[
                (trades["symbol"] == sym) & (trades["status"] == "OPEN")
            ].iloc[-1]

            sl      = float(open_trade["stop_loss"])
            ep      = float(open_trade["entry_price"])
            cur     = info["last_close"]
            unreal  = round((cur / ep - 1) * 100, 2)
            stop_hit, exit_px = check_stop_hit(sym, sl)

            if stop_hit:
                reason  = "STOP-LOSS"
                pnl     = round((exit_px / ep - 1) * 100, 2)
                print(f"    ⛔ STOP-LOSS HIT  exit={exit_px}  P&L={pnl:+.2f}%")
                updates.append((open_trade["trade_id"], today, exit_px, reason, pnl, "CLOSED"))

            elif info["signal"] == "SELL":
                reason  = "EMA-CROSSOVER"
                pnl     = round((cur / ep - 1) * 100, 2)
                print(f"    🔴 SELL SIGNAL    exit={cur}  P&L={pnl:+.2f}%")
                updates.append((open_trade["trade_id"], today, cur, reason, pnl, "CLOSED"))

            else:
                print(f"    🟡 HOLDING        stop={sl}  unrealised={unreal:+.2f}%")
        else:
            # ── check for new entry ─────────────────────────────────────
            if info["signal"] == "BUY":
                tid = next_id(trades) + len(new_rows)
                print(f"    🟢 BUY SIGNAL     price={info['last_close']}  stop={info['stop_loss']}")
                new_rows.append({
                    "trade_id":   tid,
                    "symbol":     sym,
                    "entry_date": info["date"],
                    "entry_price": info["last_close"],
                    "stop_loss":  info["stop_loss"],
                    "exit_date":  "",
                    "exit_price": "",
                    "exit_reason": "",
                    "pnl_pct":    "",
                    "status":     "OPEN",
                })
            else:
                print(f"    ⚪ No signal")

    if dry_run:
        print("\n  [DRY RUN] No changes saved.\n")
        return

    # Apply exits
    for tid, exit_date, exit_px, reason, pnl, status in updates:
        mask = trades["trade_id"] == tid
        trades.loc[mask, "exit_date"]   = exit_date
        trades.loc[mask, "exit_price"]  = exit_px
        trades.loc[mask, "exit_reason"] = reason
        trades.loc[mask, "pnl_pct"]     = pnl
        trades.loc[mask, "status"]      = status

    # Append new entries
    if new_rows:
        trades = pd.concat([trades, pd.DataFrame(new_rows)], ignore_index=True)

    save_trades(trades)

    total_new    = len(new_rows)
    total_closed = len(updates)
    print(f"\n  Saved → {TRADES_CSV}")
    print(f"  New entries: {total_new}  ·  Closed: {total_closed}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Show signals without saving to CSV")
    args = parser.parse_args()
    scan_and_log(dry_run=args.dry_run)
