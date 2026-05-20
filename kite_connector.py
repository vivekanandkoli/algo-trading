"""
Data pipeline for NSE historical data.

Uses yfinance in paper/simulation mode.
For live trading, swap in Zerodha Kite Connect using credentials from .env
"""

import yfinance as yf
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# NSE symbol helpers
NIFTY_INDEX = "^NSEI"

def nse_symbol(ticker: str) -> str:
    """Convert bare NSE ticker to yfinance format, e.g. RELIANCE -> RELIANCE.NS"""
    if ticker.startswith("^") or ticker.endswith(".NS") or ticker.endswith(".BO"):
        return ticker
    return f"{ticker}.NS"


def fetch_historical(
    symbol: str,
    period: str = "2y",
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Fetch OHLCV data from Yahoo Finance (NSE paper-mode).

    Args:
        symbol: NSE ticker (e.g. "RELIANCE") or index ("^NSEI"). ".NS" appended automatically.
        period:  yfinance period string — "1y", "2y", "5y", "max", etc.
        interval: "1d", "1wk", "1mo", etc.

    Returns:
        DataFrame with columns [Date, Open, High, Low, Close, Volume], Date as index.
    """
    yfin_symbol = nse_symbol(symbol)
    ticker = yf.Ticker(yfin_symbol)
    df = ticker.history(period=period, interval=interval, auto_adjust=True)

    if df.empty:
        raise ValueError(f"No data returned for symbol '{yfin_symbol}'. Check ticker.")

    # Normalise column names and drop unwanted columns
    df.index.name = "Date"
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = df.index.tz_localize(None)  # strip timezone for cleaner downstream use

    # Drop rows with missing Close
    df.dropna(subset=["Close"], inplace=True)

    return df


if __name__ == "__main__":
    df = fetch_historical("^NSEI", period="2y")
    print(f"Fetched {len(df)} rows for ^NSEI")
    print(df.tail())
