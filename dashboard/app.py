"""
NSE Algo Trading — Interactive Dashboard
Run: python3 -m streamlit run dashboard/app.py
"""

import os, sys
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from kite_connector import fetch_historical
from strategies.ema_crossover_v2 import add_signals, ATR_MULTIPLIER
from backtest.engine import run_backtest

# ── constants ──────────────────────────────────────────────────────────────────
SYMBOLS = ["^NSEI", "RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS"]
LABELS  = {"^NSEI": "NIFTY 50", "RELIANCE.NS": "RELIANCE",
           "HDFCBANK.NS": "HDFCBANK", "TCS.NS": "TCS", "INFY.NS": "INFY"}
TRADES_CSV = os.path.join(ROOT, "data", "paper_trades.csv")

C_GREEN  = "#00c853"
C_RED    = "#ff1744"
C_YELLOW = "#f0b429"
C_BLUE   = "#4db8ff"
C_PURPLE = "#b39ddb"
C_MUTED  = "#8b9dc3"

# ── page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="NSE Algo Dashboard", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")

# ── cached loaders ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_signals(symbol, period):
    return add_signals(fetch_historical(symbol, period=period))

@st.cache_data(ttl=300)
def get_backtest(symbol, period, version):
    return run_backtest(symbol, period=period, version=version)

# ── sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📈 NSE Algo")
    st.divider()
    selected = st.selectbox("Symbol", SYMBOLS, format_func=lambda s: LABELS[s])
    period   = st.selectbox("Period", ["3mo", "6mo", "1y", "2y"], index=3)
    st.divider()
    st.markdown("**Strategy v2 rules**")
    st.caption("• EMA 9 crosses above EMA 21")
    st.caption("• ADX(14) > 25  (trend filter)")
    st.caption("• RSI(14) 40–70  (momentum filter)")
    st.caption("• 2 × ATR stop-loss")
    st.divider()
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── header ─────────────────────────────────────────────────────────────────────
st.markdown("# 📈 NSE Algo Trading Dashboard")
st.caption("EMA Crossover v2 · ADX + RSI filters · ATR stop-loss · yfinance data")
st.divider()

tab_scan, tab_chart, tab_trades, tab_bt = st.tabs(
    ["📡 Scanner", "📊 Strategy Chart", "📋 Paper Trades", "🔬 Backtest"]
)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SCANNER
# ══════════════════════════════════════════════════════════════════════════════
with tab_scan:
    st.subheader("Live Market Scanner — all 5 symbols")

    rows = []
    metric_cols = st.columns(5)

    with st.spinner("Fetching market data…"):
        for i, sym in enumerate(SYMBOLS):
            try:
                df  = get_signals(sym, "6mo")
                lat = df.iloc[-1]
                price = float(lat["Close"])
                adx   = float(lat["ADX"])
                rsi   = float(lat["RSI"])
                atr   = float(lat["ATR"])
                sig   = int(lat["signal"])
                up    = lat["EMA_9"] > lat["EMA_21"]
                prev_close = float(df.iloc[-2]["Close"])
                day_chg = (price / prev_close - 1) * 100

                sig_label = "🟢 BUY" if sig == 1 else ("🔴 SELL" if sig == -1 else "⚪ Hold")
                adx_ok    = adx > 25
                rsi_ok    = 40 <= rsi <= 70

                with metric_cols[i]:
                    st.metric(
                        label=f"**{LABELS[sym]}**",
                        value=f"₹{price:,.1f}",
                        delta=f"{day_chg:+.2f}%",
                    )
                    st.markdown(f"**{sig_label}**")
                    adx_color = "green" if adx_ok else "red"
                    rsi_color = "green" if rsi_ok else "red"
                    st.markdown(
                        f"ADX :{adx_color}[{adx:.1f}{'✓' if adx_ok else '✗'}] &nbsp; "
                        f"RSI :{rsi_color}[{rsi:.1f}{'✓' if rsi_ok else '✗'}]"
                    )
                    st.caption(f"{'▲ Uptrend' if up else '▼ Downtrend'} · ATR {atr:.1f}")

                rows.append({
                    "Symbol":  LABELS[sym],
                    "Price ₹": f"{price:,.1f}",
                    "Day %":   f"{day_chg:+.2f}%",
                    "Trend":   "▲ Up" if up else "▼ Down",
                    "Signal":  sig_label,
                    "ADX":     f"{adx:.1f} {'✓' if adx_ok else '✗'}",
                    "RSI":     f"{rsi:.1f} {'✓' if rsi_ok else '✗'}",
                    "ATR":     f"{atr:.1f}",
                    "Stop if entry": f"₹{price - ATR_MULTIPLIER * atr:,.1f}",
                })
            except Exception as e:
                with metric_cols[i]:
                    st.error(f"{LABELS[sym]}\n{e}")

    st.divider()
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("✓ = filter passes · ✗ = filter blocks entry · data cached 5 min")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — STRATEGY CHART
# ══════════════════════════════════════════════════════════════════════════════
with tab_chart:
    st.subheader(f"Strategy Chart — {LABELS[selected]}")

    try:
        df = get_signals(selected, period)

        buys  = df[df["signal"] == 1]
        sells = df[df["signal"] == -1]

        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            row_heights=[0.60, 0.20, 0.20],
            subplot_titles=("Price + EMA 9/21", "ADX (threshold: 25)", "RSI (band: 40–70)"),
        )

        # ── price + EMAs ───────────────────────────────────────────────────
        fig.add_trace(go.Scatter(
            x=df.index, y=df["Close"], name="Close",
            line=dict(color=C_MUTED, width=1.2)), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df.index, y=df["EMA_9"], name="EMA 9",
            line=dict(color=C_YELLOW, width=1.8)), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df.index, y=df["EMA_21"], name="EMA 21",
            line=dict(color=C_BLUE, width=1.8)), row=1, col=1)

        # EMA ribbon fill
        fig.add_trace(go.Scatter(
            x=pd.concat([df.index.to_series(), df.index.to_series()[::-1]]),
            y=pd.concat([df["EMA_9"], df["EMA_21"][::-1]]),
            fill="toself",
            fillcolor="rgba(0,200,83,0.07)",
            line=dict(color="rgba(0,0,0,0)"),
            showlegend=False, name="Ribbon"), row=1, col=1)

        # Buy / sell markers
        if not buys.empty:
            fig.add_trace(go.Scatter(
                x=buys.index, y=buys["Close"], mode="markers", name="BUY",
                marker=dict(symbol="triangle-up", size=12, color=C_GREEN,
                            line=dict(width=1, color="white"))), row=1, col=1)

        if not sells.empty:
            fig.add_trace(go.Scatter(
                x=sells.index, y=sells["Close"], mode="markers", name="SELL",
                marker=dict(symbol="triangle-down", size=12, color=C_RED,
                            line=dict(width=1, color="white"))), row=1, col=1)

        # ── ADX ────────────────────────────────────────────────────────────
        fig.add_trace(go.Scatter(
            x=df.index, y=df["ADX"], name="ADX",
            line=dict(color=C_PURPLE, width=1.5)), row=2, col=1)

        fig.add_hline(y=25, line_dash="dash", line_color="gray",
                      annotation_text="25", row=2, col=1)

        # ── RSI ────────────────────────────────────────────────────────────
        fig.add_trace(go.Scatter(
            x=df.index, y=df["RSI"], name="RSI",
            line=dict(color="#ff9800", width=1.5)), row=3, col=1)

        fig.add_hrect(y0=40, y1=70, row=3, col=1,
                      fillcolor="rgba(0,200,83,0.08)",
                      line_width=0, annotation_text="Buy zone")

        fig.add_hline(y=70, line_dash="dot", line_color=C_RED,    row=3, col=1)
        fig.add_hline(y=40, line_dash="dot", line_color=C_GREEN,  row=3, col=1)
        fig.add_hline(y=50, line_dash="dash", line_color="gray",  row=3, col=1)

        fig.update_layout(
            template="plotly_dark",
            height=680,
            margin=dict(l=0, r=0, t=40, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis3_rangeslider_visible=False,
            hovermode="x unified",
        )
        fig.update_yaxes(title_text="Price ₹", row=1, col=1)
        fig.update_yaxes(title_text="ADX",     row=2, col=1)
        fig.update_yaxes(title_text="RSI",     row=3, col=1)

        st.plotly_chart(fig, use_container_width=True)

        # summary below chart
        lat = df.iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("EMA 9",  f"{lat['EMA_9']:.1f}")
        c2.metric("EMA 21", f"{lat['EMA_21']:.1f}")
        c3.metric("ADX",    f"{lat['ADX']:.1f}",
                  delta="✓ trend" if lat["ADX"] > 25 else "✗ weak",
                  delta_color="normal" if lat["ADX"] > 25 else "inverse")
        c4.metric("RSI",    f"{lat['RSI']:.1f}",
                  delta="✓ in zone" if 40 <= lat["RSI"] <= 70 else "✗ out",
                  delta_color="normal" if 40 <= lat["RSI"] <= 70 else "inverse")

    except Exception as e:
        st.error(f"Chart error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — PAPER TRADES
# ══════════════════════════════════════════════════════════════════════════════
with tab_trades:
    st.subheader("Paper Trade Log")

    if not os.path.exists(TRADES_CSV):
        st.info("No paper trades yet. Run:  `python3 paper_trading/logger.py`")
    else:
        trades = pd.read_csv(TRADES_CSV)

        open_df   = trades[trades["status"] == "OPEN"]
        closed_df = trades[trades["status"] == "CLOSED"]

        # ── summary metrics ────────────────────────────────────────────────
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Total trades",  len(trades))
        mc2.metric("Open",          len(open_df))
        mc3.metric("Closed",        len(closed_df))

        if len(closed_df) > 0:
            pnls    = closed_df["pnl_pct"].astype(float)
            win_rt  = (pnls > 0).sum() / len(pnls) * 100
            avg_pnl = pnls.mean()
            mc4.metric("Win rate", f"{win_rt:.0f}%",
                       delta=f"avg {avg_pnl:+.2f}%",
                       delta_color="normal" if avg_pnl > 0 else "inverse")
        else:
            mc4.metric("Win rate", "—")

        st.divider()

        # ── open positions ─────────────────────────────────────────────────
        st.markdown("#### 🟡 Open Positions")
        if open_df.empty:
            st.info("No open positions. Scanner will log entries when signals fire.")
        else:
            display_open = open_df.copy()
            # Fetch current prices for unrealised P&L
            cur_prices = []
            for _, row in display_open.iterrows():
                try:
                    tmp = fetch_historical(row["symbol"], period="5d")
                    cur_prices.append(round(float(tmp.iloc[-1]["Close"]), 2))
                except Exception:
                    cur_prices.append(None)

            display_open["Current ₹"] = cur_prices
            display_open["Unrealised %"] = display_open.apply(
                lambda r: f"{(r['Current ₹']/r['entry_price']-1)*100:+.2f}%"
                          if r["Current ₹"] else "N/A", axis=1
            )
            st.dataframe(
                display_open[["trade_id","symbol","entry_date","entry_price",
                               "stop_loss","Current ₹","Unrealised %"]],
                use_container_width=True, hide_index=True
            )

        st.divider()

        # ── closed trades ──────────────────────────────────────────────────
        st.markdown("#### ✅ Closed Trades")
        if closed_df.empty:
            st.info("No closed trades yet.")
        else:
            disp = closed_df.copy()
            disp["pnl_pct"] = disp["pnl_pct"].astype(float)
            st.dataframe(
                disp[["trade_id","symbol","entry_date","exit_date",
                       "entry_price","exit_price","pnl_pct","exit_reason"]]
                .sort_values("exit_date", ascending=False),
                use_container_width=True, hide_index=True
            )

            # P&L bar chart
            fig_pnl = go.Figure(go.Bar(
                x=disp["symbol"] + " #" + disp["trade_id"].astype(str),
                y=disp["pnl_pct"],
                marker_color=[C_GREEN if v > 0 else C_RED for v in disp["pnl_pct"]],
                text=[f"{v:+.2f}%" for v in disp["pnl_pct"]],
                textposition="outside",
            ))
            fig_pnl.update_layout(
                template="plotly_dark", height=300,
                title="P&L per trade (%)",
                margin=dict(l=0, r=0, t=40, b=0),
                yaxis_title="P&L %",
                showlegend=False,
            )
            st.plotly_chart(fig_pnl, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — BACKTEST
# ══════════════════════════════════════════════════════════════════════════════
with tab_bt:
    st.subheader(f"Backtest — {LABELS[selected]}  ·  {period}")

    with st.spinner("Running v1 and v2 backtests…"):
        try:
            r1 = get_backtest(selected, period, "v1")
            r2 = get_backtest(selected, period, "v2")

            # ── metrics comparison ─────────────────────────────────────────
            st.markdown("#### Results vs Buy & Hold")
            hdr, c_v1, c_v2, c_bh = st.columns([2, 1, 1, 1])
            hdr.markdown("**Metric**")
            c_v1.markdown("**v1** · EMA only")
            c_v2.markdown("**v2** · Filtered")
            c_bh.markdown("**Buy & Hold**")

            metrics = [
                ("Total return",  "total_return_pct", "%"),
                ("Sharpe ratio",  "sharpe",           ""),
                ("Max drawdown",  "max_drawdown_pct", "%"),
                ("Win rate",      "win_rate_pct",     "%"),
                ("# Trades",      "num_trades",       ""),
            ]
            for label, key, unit in metrics:
                hdr.write(label)
                v1_val = r1[key]
                v2_val = r2[key]
                bh_val = r1["bnh_return_pct"] if key == "total_return_pct" else "—"

                def _fmt(v, u):
                    if isinstance(v, (int, float)):
                        return f"{v:+.2f}{u}" if u else f"{v:.2f}"
                    return str(v)

                c_v1.write(_fmt(v1_val, unit))
                c_v2.write(_fmt(v2_val, unit))
                c_bh.write(_fmt(bh_val, unit) if bh_val != "—" else "—")

            st.divider()

            # ── equity curve ───────────────────────────────────────────────
            st.markdown("#### Equity Curve")
            fig_eq = go.Figure()

            fig_eq.add_trace(go.Scatter(
                x=r1["equity"].index, y=r1["equity"],
                name="v1 · EMA only",
                line=dict(color=C_YELLOW, width=1.8)))

            fig_eq.add_trace(go.Scatter(
                x=r2["equity"].index, y=r2["equity"],
                name="v2 · Filtered",
                line=dict(color=C_GREEN, width=2.2)))

            fig_eq.add_trace(go.Scatter(
                x=r1["bnh_equity"].index, y=r1["bnh_equity"],
                name="Buy & Hold",
                line=dict(color=C_BLUE, width=1.8, dash="dash")))

            fig_eq.add_hline(y=100_000, line_dash="dot", line_color="gray",
                             annotation_text="Initial ₹1L")

            fig_eq.update_layout(
                template="plotly_dark",
                height=380,
                margin=dict(l=0, r=0, t=20, b=0),
                yaxis_title="Portfolio Value (₹)",
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            xanchor="right", x=1),
            )
            st.plotly_chart(fig_eq, use_container_width=True)

            # ── all symbols quick table ────────────────────────────────────
            st.divider()
            st.markdown("#### All Symbols Snapshot")
            if st.button("Run all 5 symbols (takes ~30s)"):
                all_rows = []
                prog = st.progress(0)
                for idx, sym in enumerate(SYMBOLS):
                    rv1 = get_backtest(sym, period, "v1")
                    rv2 = get_backtest(sym, period, "v2")
                    all_rows.append({
                        "Symbol":     LABELS[sym],
                        "v1 Return":  f"{rv1['total_return_pct']:+.1f}%",
                        "v2 Return":  f"{rv2['total_return_pct']:+.1f}%",
                        "B&H":        f"{rv1['bnh_return_pct']:+.1f}%",
                        "v1 Sharpe":  f"{rv1['sharpe']:+.2f}",
                        "v2 Sharpe":  f"{rv2['sharpe']:+.2f}",
                        "v1 MaxDD":   f"{rv1['max_drawdown_pct']:.1f}%",
                        "v2 MaxDD":   f"{rv2['max_drawdown_pct']:.1f}%",
                        "v1 WinRate": f"{rv1['win_rate_pct']:.0f}%",
                        "v2 WinRate": f"{rv2['win_rate_pct']:.0f}%",
                        "v1 Trades":  rv1["num_trades"],
                        "v2 Trades":  rv2["num_trades"],
                    })
                    prog.progress((idx + 1) / len(SYMBOLS))
                st.dataframe(pd.DataFrame(all_rows),
                             use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"Backtest error: {e}")
