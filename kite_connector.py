"""
Data pipeline for NSE historical data.

Default mode  : yfinance (free, no auth, great for backtesting)
Live mode     : Zerodha Kite Connect (real NSE data, requires API keys + daily auth)

Switch by setting USE_KITE=true in your .env file.
Run kite_auth.py once per day to refresh the access token.
"""

import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ── config ────────────────────────────────────────────────────────────────────
NIFTY_INDEX = "^NSEI"
USE_KITE    = os.getenv("USE_KITE", "false").lower() == "true"

# Kite instrument tokens for indices (these are permanent, never change)
# Equity tokens are fetched dynamically via the instruments API and cached.
KITE_INDEX_TOKENS = {
    "^NSEI":    256265,   # NIFTY 50
    "^NSEBANK": 260105,   # BANK NIFTY
    "^CNXIT":   519937,   # NIFTY IT
}

# yfinance period → number of calendar days
PERIOD_DAYS = {
    # yfinance-style period strings → calendar days for Kite date range
    "1mo": 30,  "3mo": 90,  "6mo": 180,
    "1y":  365, "2y":  730, "3y":  1095, "5y": 1825, "max": 3650,
    # short aliases also accepted
    "1m": 30, "3m": 90, "6m": 180,
}

# yfinance interval → Kite interval
KITE_INTERVAL = {
    "1d": "day", "1wk": "week", "1mo": "month",
    "5m": "5minute", "15m": "15minute",
    "30m": "30minute", "60m": "60minute",
}


# ── yfinance path (default) ───────────────────────────────────────────────────

def _yf_symbol(symbol: str) -> str:
    """Add .NS suffix for yfinance if needed."""
    if symbol.startswith("^") or symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol
    return f"{symbol}.NS"


def _fetch_yfinance(symbol: str, period: str, interval: str) -> pd.DataFrame:
    yfin_sym = _yf_symbol(symbol)
    df = yf.Ticker(yfin_sym).history(period=period, interval=interval, auto_adjust=True)

    if df.empty:
        raise ValueError(f"yfinance returned no data for '{yfin_sym}'. Check symbol.")

    df.index.name = "Date"
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = df.index.tz_localize(None)
    df.dropna(subset=["Close"], inplace=True)
    return df


# ── Kite Connect path ─────────────────────────────────────────────────────────

def _get_kite_client():
    """Return an authenticated KiteConnect instance."""
    try:
        from kiteconnect import KiteConnect
    except ImportError:
        raise ImportError("kiteconnect not installed. Run: pip install kiteconnect")

    api_key      = os.getenv("KITE_API_KEY", "").strip()
    access_token = os.getenv("KITE_ACCESS_TOKEN", "").strip()

    if not api_key:
        raise ValueError("KITE_API_KEY not found in .env")
    if not access_token:
        raise ValueError(
            "KITE_ACCESS_TOKEN not found in .env.\n"
            "Run 'python3 kite_auth.py' to authenticate."
        )

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return kite


def _get_instrument_token(kite, symbol: str) -> int:
    """Return Kite instrument token for a symbol. Caches instrument list locally."""
    # Indices are hardcoded (no need for API lookup)
    if symbol in KITE_INDEX_TOKENS:
        return KITE_INDEX_TOKENS[symbol]

    cache_path = os.path.join(os.path.dirname(__file__), "data", "kite_instruments.csv")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    # Refresh cache if missing or older than 7 days
    if not os.path.exists(cache_path) or \
       (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_path))).days > 7:
        print("Refreshing Kite instruments cache …")
        instruments = pd.DataFrame(kite.instruments("NSE"))
        instruments.to_csv(cache_path, index=False)
    else:
        instruments = pd.read_csv(cache_path)

    # Strip .NS suffix for lookup (Kite uses bare ticker names)
    bare = symbol.replace(".NS", "").replace(".BO", "").upper()
    match = instruments[
        (instruments["tradingsymbol"] == bare) &
        (instruments["exchange"] == "NSE") &
        (instruments["instrument_type"] == "EQ")
    ]

    if match.empty:
        raise ValueError(
            f"Symbol '{symbol}' (looked up as '{bare}') not found in NSE instruments.\n"
            f"Delete {cache_path} to force a cache refresh."
        )

    return int(match.iloc[0]["instrument_token"])


def _fetch_kite(symbol: str, period: str, interval: str) -> pd.DataFrame:
    kite          = _get_kite_client()
    token         = _get_instrument_token(kite, symbol)
    kite_interval = KITE_INTERVAL.get(interval, "day")
    days          = PERIOD_DAYS.get(period, 730)
    to_dt         = datetime.now()
    from_dt       = to_dt - timedelta(days=days)

    raw = kite.historical_data(
        instrument_token=token,
        from_date=from_dt,
        to_date=to_dt,
        interval=kite_interval,
    )

    if not raw:
        raise ValueError(f"Kite returned no data for '{symbol}' (token {token}).")

    df = pd.DataFrame(raw)
    df = df.rename(columns={
        "date": "Date", "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume",
    })
    df.set_index("Date", inplace=True)
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.dropna(subset=["Close"], inplace=True)
    return df


# ── public API ────────────────────────────────────────────────────────────────

def fetch_historical(symbol: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """
    Fetch OHLCV data for an NSE symbol.

    Automatically uses Kite Connect when USE_KITE=true in .env,
    otherwise falls back to yfinance (free, no auth needed).

    Args:
        symbol  : "^NSEI", "RELIANCE.NS", "TCS.NS", etc.
        period  : "1y", "2y", "5y", "max"  (or any yfinance period string)
        interval: "1d", "1wk", "5m", "15m", etc.

    Returns:
        DataFrame indexed by Date with columns [Open, High, Low, Close, Volume].
    """
    if USE_KITE:
        print(f"[Kite] Fetching {symbol} …")
        return _fetch_kite(symbol, period, interval)
    else:
        return _fetch_yfinance(symbol, period, interval)


def nse_symbol(ticker: str) -> str:
    """Convenience: bare ticker → yfinance symbol (e.g. RELIANCE → RELIANCE.NS)."""
    return _yf_symbol(ticker)


if __name__ == "__main__":
    src = "Kite Connect" if USE_KITE else "yfinance"
    print(f"Data source: {src}")
    df = fetch_historical("^NSEI", period="2y")
    print(f"Fetched {len(df)} rows  |  {df.index[0].date()} → {df.index[-1].date()}")
    print(df.tail(3))
