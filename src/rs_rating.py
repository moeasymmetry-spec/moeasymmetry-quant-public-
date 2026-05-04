#!/usr/bin/env python3
"""
recalc_rs.py — Recalculate RS Ratings from DB for all symbols
=============================================================
Reads all price data from set100_prices.db, computes IBD-style RS ratings
(Q1×2 + Q2 + Q3 + Q4 weighted score, then percentile 1-99 against all stocks),
and writes daily CSV files to set100_rs/.

Run after fetch_prices_tv.py has updated today's prices.

Flags:
  --full-history        Backfill from 2000-01-01 (skips existing CSVs)
  --start YYYY-MM-DD    Override start date for full-history mode
"""
import sqlite3, os, csv, argparse, bisect
from collections import defaultdict
from pathlib import Path

DB_PATH = Path("/Volumes/WD Blue 1 TB/set100_prices.db")
OUT_DIR = Path("/Volumes/WD Blue 1 TB/set100_rs")
OUT_DIR.mkdir(exist_ok=True)

TODAY_ONLY = True   # only recalculate the last N trading days
RECALC_DAYS = 5     # recalculate last 5 days (covers today + recent changes)

MIN_AVG_DAILY_VALUE = 10_000_000   # 10M THB/day — IBD-style liquidity floor
MIN_AVG_DAILY_VALUE_HISTORICAL = 1_000_000   # 1M THB/day for pre-2010 data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-history", action="store_true",
                        help="Backfill RS from 2000-01-01 (skip existing CSVs)")
    parser.add_argument("--start", default="2000-01-01",
                        help="Start date for --full-history (default: 2000-01-01)")
    args = parser.parse_args()

    full_history = args.full_history
    history_start = args.start
    print("Loading price data from DB...")
    conn = sqlite3.connect(str(DB_PATH))

    # Load all stock OHLCV prices
    raw = defaultdict(list)   # {symbol: [(date, close, volume), ...]}
    for sym, dt, close, vol in conn.execute(
        "SELECT symbol, date, close, volume FROM prices "
        "WHERE symbol NOT IN ('SET','SET50','SETI') AND close > 0 ORDER BY date"
    ):
        raw[sym].append((dt, float(close), float(vol or 0)))

    # Load SET index closes for context (not used in RS calc itself — RS is stock vs universe)
    set_idx = dict(conn.execute(
        "SELECT date, close FROM index_prices WHERE symbol='SET' AND close > 0 ORDER BY date"
    ).fetchall())
    conn.close()

    # Build close-only dict (existing calcs) and compute 50-day avg daily turnover
    data = defaultdict(dict)   # {symbol: {date: close}}
    vol_data = defaultdict(dict)  # {symbol: {date: volume}}
    for sym, rows in raw.items():
        for dt, close, vol in rows:
            data[sym][dt] = close
            vol_data[sym][dt] = vol

    symbols   = list(data.keys())
    all_dates = sorted(set(d for v in data.values() for d in v.keys()))
    print(f"Symbols: {len(symbols)}  Trading days: {len(all_dates)}")

    if len(all_dates) < 63:
        print("ERROR: Not enough history (need ≥ 63 trading days).")
        return

    # Build per-symbol sorted date list, trimmed to post-split data only
    # A single-day price move > ±70% signals a split / par-value change.
    # Use only data after the most recent such event; exclude if < 63 days remain.
    SPLIT_THRESHOLD = 0.70   # >70% single-day move = split event
    split_skipped   = 0

    sym_dates = {}
    for sym, sdates_raw in {s: sorted(d.keys()) for s, d in data.items()}.items():
        split_idx = None
        for i in range(1, len(sdates_raw)):
            prev_c = data[sym][sdates_raw[i - 1]]
            cur_c  = data[sym][sdates_raw[i]]
            if prev_c > 0:
                chg = abs(cur_c / prev_c - 1)
                if chg > SPLIT_THRESHOLD:
                    split_idx = i   # last split found
        if split_idx is not None:
            trimmed = sdates_raw[split_idx:]   # use only post-split dates
            if len(trimmed) < 63:
                split_skipped += 1
                continue       # too little history — drop from universe
            sym_dates[sym] = trimmed
        else:
            sym_dates[sym] = sdates_raw

    symbols = list(sym_dates.keys())
    print(f"  Split-adjusted: {split_skipped} stocks excluded (< 63 days post-split)")

    # Determine which dates to calculate
    if full_history:
        target_dates = [d for d in all_dates if d >= history_start]
        existing = {f.stem for f in OUT_DIR.glob("*.csv") if f.stem != "rs_summary"}
        target_dates = [d for d in target_dates if d not in existing]
        print(f"Full-history mode: {len(target_dates)} new dates to compute (start={history_start})")
    elif TODAY_ONLY:
        target_dates = all_dates[-RECALC_DAYS:]
    else:
        target_dates = all_dates
    if not target_dates:
        print("Nothing to compute — all dates already exist.")
        return
    print(f"Recalculating {len(target_dates)} days: {target_dates[0]} → {target_dates[-1]}")

    summary_rows = []

    for target_date in target_dates:
        scores = {}
        filtered_illiquid = 0
        liq_floor = MIN_AVG_DAILY_VALUE_HISTORICAL if target_date < "2010-01-01" else MIN_AVG_DAILY_VALUE
        for sym in symbols:
            sdates = sym_dates[sym]
            # Find closest date ≤ target_date using binary search (O(log n) vs O(n))
            bi = bisect.bisect_right(sdates, target_date) - 1
            if bi < 0:
                continue
            td  = sdates[bi]
            idx = bi

            def close_at(offset):
                i = idx - offset
                return data[sym][sdates[i]] if 0 <= i < len(sdates) else None

            c0   = close_at(0)
            c63  = close_at(63)
            c126 = close_at(126)
            c189 = close_at(189)
            c252 = close_at(252)

            if not c0 or not c63 or c63 == 0:
                continue

            # IBD-style liquidity filter: avg 50-day daily turnover (vol × close) ≥ 10M THB
            # This prevents micro-cap/illiquid stocks from inflating RS rankings
            lookback = min(50, idx + 1)
            avg_val = 0.0
            if lookback > 0:
                vals = [vol_data[sym].get(sdates[idx - k], 0) * data[sym].get(sdates[idx - k], 0)
                        for k in range(lookback)]
                avg_val = sum(vals) / lookback
            if avg_val < liq_floor:
                filtered_illiquid += 1
                continue

            # IBD weighted formula: Q1*2 + Q2 + Q3 + Q4
            # Q1 = 3-month performance (most recent, double weight = 40% of total)
            # Q2 = 6-month, Q3 = 9-month, Q4 = 12-month (each 20%)
            # IPO/short-history stocks: missing quarters score 0 (conservative —
            # no synthetic inflation; stock must earn each quarter on real price data)
            q1 = (c0 / c63  - 1) * 2
            q2 = (c0 / c126 - 1) if (c126 and c126 > 0) else 0.0
            q3 = (c0 / c189 - 1) if (c189 and c189 > 0) else 0.0
            q4 = (c0 / c252 - 1) if (c252 and c252 > 0) else 0.0
            scores[sym] = q1 + q2 + q3 + q4

        if not scores:
            print(f"  {target_date}: no scores — skipping")
            continue

        # Percentile rank 1–99
        ranked = sorted(scores.items(), key=lambda x: x[1])
        n = len(ranked)
        rs_rating = {sym: max(1, min(99, round(rank / n * 99)))
                     for rank, (sym, _) in enumerate(ranked, 1)}

        # Sort descending by RS
        sorted_rows = sorted(rs_rating.items(), key=lambda x: -x[1])

        # Write daily CSV
        csv_path = OUT_DIR / f"{target_date}.csv"
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["rank", "symbol", "rs_rating", "score"])
            for rank, (sym, rs) in enumerate(sorted_rows, 1):
                w.writerow([rank, sym, rs, round(scores[sym], 6)])

        # Track for summary
        for rank, (sym, rs) in enumerate(sorted_rows, 1):
            summary_rows.append({
                "date": target_date, "rank": rank, "symbol": sym,
                "rs_rating": rs, "score": round(scores[sym], 6)
            })

        top10 = [(sym, rs) for sym, rs in sorted_rows[:10]]
        print(f"  {target_date}: {len(scores)} stocks ranked "
              f"({filtered_illiquid} illiquid, {split_skipped} split filtered) — "
              f"Top 3: {', '.join(f'{s}({r})' for s,r in top10[:3])}")

    # Update rs_summary.csv (last date only)
    latest_csv = OUT_DIR / f"{target_dates[-1]}.csv"
    if latest_csv.exists():
        import shutil
        shutil.copy(latest_csv, OUT_DIR / "rs_summary.csv")

    print(f"\nRS ratings updated. CSV files in: {OUT_DIR}")
    print(f"Latest date: {target_dates[-1]}")

if __name__ == "__main__":
    main()
