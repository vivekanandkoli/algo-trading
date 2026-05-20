"""
End-to-end runner: fetch data → generate signals → backtest → plot.
"""

from backtest.engine import run_backtest, print_results
from backtest.visualise import plot_price_with_signals, plot_equity_curve

if __name__ == "__main__":
    print("Fetching 2 years of NIFTY 50 data…")
    results = run_backtest(symbol="^NSEI", period="2y")

    print_results(results)

    print("Generating charts…")
    plot_price_with_signals(results["df"])
    plot_equity_curve(results["equity"], results["bnh_equity"])

    print("\nDone. Charts saved to data/charts/")
