#!/usr/bin/env python3
"""
simple_backtest.py — Educational Turtle 20-day breakout backtest

Pure Richard Dennis Turtle system: enter on close > 20-day high, exit on close < 10-day low.
Includes ATR-based position sizing (1% risk per trade) and a hard 8% stop loss.

Usage:
    python simple_backtest.py path/to/prices.csv

Input CSV format:
    date,open,high,low,close,volume
    2020-01-01,100.0,101.5,99.5,100.8,1000000

Output:
    Console summary + trades.csv
"""
import csv, sys
from collections import deque
from datetime import datetime

INITIAL_EQUITY = 100_000.0
RISK_PCT = 0.01        # 1% portfolio risk per trade
HARD_STOP = 0.08        # -8% catastrophic stop
SLIPPAGE = 0.003        # 0.3% combined slippage + commission
ATR_PERIOD = 20
ENTRY_LOOKBACK = 20     # 20-day high
EXIT_LOOKBACK = 10      # 10-day low


def load_prices(csv_path):
    bars = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                bars.append({
                    "date": row["date"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 0)),
                })
            except (ValueError, KeyError):
                continue
    bars.sort(key=lambda b: b["date"])
    return bars


def compute_atr(bars, period=ATR_PERIOD):
    """Compute Average True Range for each bar."""
    atrs = [None] * len(bars)
    if len(bars) < period + 1:
        return atrs
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["high"], bars[i]["low"], bars[i-1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    for i in range(period, len(bars)):
        atrs[i] = sum(trs[i-period:i]) / period
    return atrs


def backtest(bars):
    """Run the simple Turtle backtest."""
    atrs = compute_atr(bars)
    equity = INITIAL_EQUITY
    position = None  # dict if open, None otherwise
    trades = []
    equity_curve = []

    for i, bar in enumerate(bars):
        if i < ENTRY_LOOKBACK:
            equity_curve.append((bar["date"], equity))
            continue

        # Manage open position
        if position is not None:
            entry = position["entry"]
            shares = position["shares"]

            # Hard stop
            if bar["low"] <= entry * (1 - HARD_STOP):
                exit_price = entry * (1 - HARD_STOP) * (1 - SLIPPAGE)
                pnl = (exit_price - entry) * shares
                equity += pnl
                trades.append({
                    "entry_date": position["entry_date"],
                    "exit_date": bar["date"],
                    "entry": round(entry, 4),
                    "exit": round(exit_price, 4),
                    "shares": shares,
                    "pnl": round(pnl, 2),
                    "pct_return": round((exit_price / entry - 1) * 100, 2),
                    "reason": "stop_8pct",
                })
                position = None
            else:
                # 10-day low trail
                lows_10 = [bars[j]["low"] for j in range(i - EXIT_LOOKBACK, i)]
                min_low_10 = min(lows_10)
                if bar["close"] < min_low_10:
                    exit_price = bar["close"] * (1 - SLIPPAGE)
                    pnl = (exit_price - entry) * shares
                    equity += pnl
                    trades.append({
                        "entry_date": position["entry_date"],
                        "exit_date": bar["date"],
                        "entry": round(entry, 4),
                        "exit": round(exit_price, 4),
                        "shares": shares,
                        "pnl": round(pnl, 2),
                        "pct_return": round((exit_price / entry - 1) * 100, 2),
                        "reason": "turtle_10d_exit",
                    })
                    position = None

        # Look for new entry
        if position is None and i >= ENTRY_LOOKBACK:
            highs_20 = [bars[j]["high"] for j in range(i - ENTRY_LOOKBACK, i)]
            max_high_20 = max(highs_20)
            if bar["close"] > max_high_20:
                # Entry signal — Turtle 20-day high breakout
                entry_price = bar["close"] * (1 + SLIPPAGE)
                atr = atrs[i]
                if atr is None or atr == 0:
                    equity_curve.append((bar["date"], equity))
                    continue
                # Position size: risk 1% / (2 * ATR)
                risk_dollars = equity * RISK_PCT
                shares = int(risk_dollars / (2 * atr))
                if shares < 1:
                    equity_curve.append((bar["date"], equity))
                    continue
                # Cap at 30% of equity
                pos_value = shares * entry_price
                if pos_value > equity * 0.30:
                    shares = int((equity * 0.30) / entry_price)
                position = {
                    "entry_date": bar["date"],
                    "entry": entry_price,
                    "shares": shares,
                }

        equity_curve.append((bar["date"], equity))

    # Force close any open position at end
    if position is not None and bars:
        last = bars[-1]
        exit_price = last["close"] * (1 - SLIPPAGE)
        pnl = (exit_price - position["entry"]) * position["shares"]
        equity += pnl
        trades.append({
            "entry_date": position["entry_date"],
            "exit_date": last["date"],
            "entry": round(position["entry"], 4),
            "exit": round(exit_price, 4),
            "shares": position["shares"],
            "pnl": round(pnl, 2),
            "pct_return": round((exit_price / position["entry"] - 1) * 100, 2),
            "reason": "end_of_data",
        })

    return trades, equity, equity_curve


def summarize(trades, final_equity):
    if not trades:
        return {"n": 0, "msg": "No trades."}
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    n = len(trades)
    wr = len(wins) / n * 100
    avg_win = sum(t["pct_return"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pct_return"] for t in losses) / len(losses) if losses else 0
    expectancy = (wr/100) * avg_win + (1 - wr/100) * avg_loss
    total_return = (final_equity - INITIAL_EQUITY) / INITIAL_EQUITY * 100
    return {
        "n_trades": n,
        "win_rate": round(wr, 1),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "total_return_pct": round(total_return, 2),
        "final_equity": round(final_equity, 2),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python simple_backtest.py path/to/prices.csv")
        sys.exit(1)
    csv_path = sys.argv[1]
    print(f"Loading {csv_path}...")
    bars = load_prices(csv_path)
    print(f"  {len(bars)} bars from {bars[0]['date']} to {bars[-1]['date']}")
    print("\nRunning Turtle 20-day breakout backtest...")
    trades, final_equity, curve = backtest(bars)
    summary = summarize(trades, final_equity)
    print("\n=== RESULT ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    # Write trades CSV
    if trades:
        out_csv = csv_path.replace(".csv", "_trades.csv")
        with open(out_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
            w.writeheader()
            w.writerows(trades)
        print(f"\nTrade log: {out_csv}")


if __name__ == "__main__":
    main()
