# NSE Algo Trading — Project Context

> Quick-reference for anyone (or any AI session) picking this up mid-flight.

---

## Project Goal

Learn algorithmic trading on NSE using Python, starting from zero quant
knowledge but with a strong Python/QA background. Build a full pipeline:
historical data → strategy → backtest → paper trade → live (future).

**Not for live trading yet.** Everything runs in paper/simulation mode.

---

## Tech Stack

| Layer | Tool | Notes |
|---|---|---|
| Language | Python 3.9 | System Python on macOS |
| Market data | yfinance (default) | Free, NSE via `.NS` suffix |
| Live data (future) | Kite Connect API | Kite auth wired; needs ₹2000/mo plan |
| Indicators | pandas `ewm()` | No external TA lib needed |
| Backtesting | Custom engine | Vectorised (v1), event-driven (v2) |
| Visualisation | matplotlib + plotly | Static PNGs + interactive dashboard |
| Dashboard | Streamlit | `python3 -m streamlit run dashboard/app.py` |
| Pine Script | TradingView v5 | Paste into Kite chart editor |

---

## Repository Structure

```
algo-trading/
├── kite_connector.py          Data pipeline — yfinance or Kite Connect
├── kite_auth.py               OAuth flow — run once per day for Kite
├── run.py                     v1 backtest entry point
├── run_comparison.py          v1 vs v2 across all 5 symbols
│
├── strategies/
│   ├── ema_crossover.py       v1: EMA 9/21 crossover only
│   ├── ema_crossover_v2.py    v2: + ADX + RSI + ATR stop-loss
│   └── pine_v2.pine           TradingView Pine Script (paste into Kite)
│
├── backtest/
│   ├── engine.py              Backtester — vectorised (v1) + event-driven (v2)
│   └── visualise.py           matplotlib charts (static PNGs)
│
├── paper_trading/
│   ├── logger.py              Daily signal scanner → data/paper_trades.csv
│   └── tracker.py             Terminal status viewer
│
├── dashboard/
│   └── app.py                 Streamlit dashboard (4 tabs)
│
├── data/
│   ├── charts/                Generated PNG charts
│   └── paper_trades.csv       Paper trade log (auto-created)
│
├── .env                       Real credentials (gitignored)
├── .env.template              Placeholder — safe to commit
└── requirements.txt
```

---

## Strategies Tested

### v1 — EMA Crossover (baseline)

**Logic:** Buy when EMA 9 crosses above EMA 21. Sell on reverse cross.

**Parameters:** EMA fast=9, slow=21, cost=0.05%/side

**Problem:** Pure trend-following. Gets whipsawed badly in sideways/choppy markets.

### v2 — EMA Crossover + Filters (current)

**Logic:** Same EMA crossover, but three additional gates:

| Filter | Rule | Purpose |
|---|---|---|
| ADX(14) | Must be > 25 at entry | Confirms a real trend exists, blocks ranging markets |
| RSI(14) | Must be 40–70 at entry | Avoids overbought buys and deeply oversold traps |
| ATR stop-loss | Exit if Low ≤ entry − 2×ATR | Limits downside per trade |

**Backtester:** Event-driven loop (handles dynamic stop-loss exits using daily Low).

---

## Backtest Results — May 2024 → May 2026

> Market context: NIFTY was choppy/bearish through most of 2025–2026.
> Trend-following strategies generally struggled. v2's value was **capital preservation**.

| Symbol | v1 Return | v2 Return | Buy & Hold | v1 Sharpe | v2 Sharpe | v1 Trades | v2 Trades |
|---|---|---|---|---|---|---|---|
| ^NSEI | -10.7% | **-4.8%** | +5.0% | -1.14 | -1.81 | 14 | 5 |
| RELIANCE | -20.6% | **-2.9%** | -4.6% | -1.09 | 0.00 | 13 | 1 |
| HDFCBANK | +17.3% | 0.0% | +5.5% | +0.18 | 0.00 | 9 | 0 |
| TCS | -21.7% | **-3.4%** | -35.5% | -1.24 | -0.71 | 15 | 6 |
| INFY | -10.3% | **-3.5%** | -11.6% | -0.59 | 0.00 | 16 | 2 |

**Key lessons learned:**
- EMA crossover alone is a whipsaw machine in non-trending markets (v1)
- ADX filter cut trades from 13–16 to 1–6 per symbol — right call in this regime
- v2 mostly stays in cash. In a bear market, that beats active trading
- HDFCBANK v1 (+17.3%) shows filters can also block *good* trades — overfitting risk
- TCS: B&H lost -35.5%, v2 only -3.4% → ATR stop-loss working as intended
- Never evaluate a strategy on just one market regime

---

## Current Stage

```
[✅] Data pipeline      yfinance working, Kite Connect wired (auth done)
[✅] Strategy v1        EMA crossover baseline
[✅] Strategy v2        ADX + RSI + ATR stop-loss
[✅] Backtester         Vectorised + event-driven, 5 metrics
[✅] Charts             matplotlib static + Plotly interactive
[✅] Dashboard          Streamlit — 4 tabs (scanner, chart, trades, backtest)
[✅] Paper trader       Daily scanner + CSV log + terminal tracker
[✅] Pine Script        Paste into Kite chart editor to see live signals
[✅] Kite auth          OAuth flow working (free tier = no equity data yet)
[⏳] Live data          Needs Kite ₹2000/mo plan → flip USE_KITE=true
[🔲] Live orders        Not started — needs proven strategy + risk management
```

---

## Daily Workflow (Paper Trading)

```bash
# 1. Refresh Kite token (if using live data)
python3 kite_auth.py

# 2. Scan for signals and log to CSV
python3 paper_trading/logger.py

# 3. Check positions
python3 paper_trading/tracker.py

# 4. Or use the dashboard for everything
python3 -m streamlit run dashboard/app.py
```

---

## What to Build Next

### Short term (learning)

- [ ] **More symbols** — expand to NIFTY 50 constituents, find which sectors trend best
- [ ] **Walk-forward test** — split data into in-sample/out-of-sample to test overfitting
- [ ] **Intraday version** — same v2 logic on 15-min candles using Kite live data
- [ ] **Sector rotation** — scan IT / Bank / FMCG indices for strongest trend

### Strategy improvements

- [ ] **Trend regime filter** — only trade when NIFTY itself is above 200-day SMA
- [ ] **Position sizing** — Kelly criterion or fixed fractional instead of all-in/all-out
- [ ] **Mean reversion strategy** — RSI oversold bounce (complement to trend-following v2)
- [ ] **Multiple timeframe confirmation** — weekly trend + daily entry signal

### Infrastructure

- [ ] **Scheduled daily scan** — cron job to run logger.py at market close (3:30 PM IST)
- [ ] **Telegram/email alerts** — notify when a signal fires (instead of checking manually)
- [ ] **Upgrade Kite plan** — enables real-time data and live order placement
- [ ] **Paper trade for 3+ months** — validate signal quality before risking real money

### Before going live (checklist)

- [ ] Minimum 50 paper trades with positive expectancy
- [ ] Walk-forward test passing on out-of-sample data
- [ ] Risk per trade capped at 1–2% of capital
- [ ] Max drawdown limit with circuit breaker (stop trading if -15% drawdown)
- [ ] Start with ₹10,000–₹25,000 live capital only

---

## Key Concepts Learned So Far

| Concept | Lesson |
|---|---|
| Whipsaw | Trend-following fails in sideways markets — use ADX to filter |
| Win rate | Low win rate (28%) is normal for trend systems — big wins offset small losses |
| Sharpe ratio | Negative Sharpe = losing more risk-adjusted return than a risk-free deposit |
| Max drawdown | -33% drawdown (INFY v1) means you need +49% gain just to break even |
| Regime dependence | Backtest result depends heavily on the market period tested |
| Overfitting | More filters = fewer trades = risk of curve-fitting to historical data |

---

*Last updated: May 2026 · See `run_comparison.py` for latest backtest numbers*
