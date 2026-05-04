"""
market_condition.py — IBD Market Condition State Machine
=========================================================
Proper IBD methodology for Thai (SET) and US (SPX/DJIA/Nasdaq/RUT) markets.

SET Index source:
  - set100_prices.db → index_prices table, symbol='SET'
  - 1982–present, full OHLCV with real volume (100% coverage)

US Index source:
  - us_prices.db → prices table, symbols: US_SPX, US_DJI, US_COMP, US_RUT
  - Fetched from investing.com via fetch_us_prices.py --history-indices

State Machine:
  States   : Market in Correction / Confirmed Uptrend / Uptrend Under Pressure
  FTD      : Day 4+ of rally attempt, up ≥1.25%, volume > prev day → Confirmed Uptrend
  Dist Day : Close down ≥0.2% on volume > prev day → adds to distribution count
  Expiry   : Each dist day expires after 25 sessions OR after +5% index rally from that day
  Pressure : 5 active dist days → Uptrend Under Pressure
  Correction: 6 active dist days OR index undercuts rally attempt low → Market in Correction
"""

import sqlite3
from pathlib import Path
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
WD         = Path("/Volumes/WD Blue 1 TB")
DB_PATH    = WD / "set100_prices.db"
US_DB_PATH = WD / "us_prices.db"

# ── State constants ───────────────────────────────────────────────────────────
CONFIRMED  = "Confirmed Uptrend"
PRESSURE   = "Uptrend Under Pressure"
CORRECTION = "Market in Correction"


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def load_set_index(verbose: bool = True) -> pd.DataFrame:
    """
    Load SET Composite Index from DB (index_prices table).
    10,840 days, 1982–present, 100% volume coverage.
    """
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql(
        "SELECT date, open, high, low, close, volume FROM index_prices "
        "WHERE symbol='SET' ORDER BY date",
        conn, parse_dates=["date"], index_col="date"
    )
    conn.close()
    df = df.astype(float)
    df = df[df["close"] > 0]

    if verbose:
        vol_pct = (df["volume"] > 0).sum() / len(df) * 100
        print(f"SET Index loaded  : {len(df):,} trading days")
        print(f"Date range        : {df.index[0].date()} → {df.index[-1].date()}")
        print(f"Volume coverage   : {vol_pct:.1f}%")
    return df


def load_us_index(symbol: str, verbose: bool = True) -> pd.DataFrame:
    """
    Load a US index from us_prices.db.
    Symbols: US_SPX, US_DJI, US_COMP, US_RUT, US_NDX
    Populated by: python3 fetch_us_prices.py --history-indices
    """
    conn = sqlite3.connect(str(US_DB_PATH))
    df = pd.read_sql(
        "SELECT date, open, high, low, close, volume FROM prices "
        "WHERE symbol=? AND close > 0 ORDER BY date",
        conn, params=(symbol,), parse_dates=["date"], index_col="date"
    )
    conn.close()
    if df.empty:
        raise ValueError(f"No data for {symbol} in us_prices.db. "
                         "Run: python3 fetch_us_prices.py --history-indices")
    df = df.astype(float)
    if verbose:
        vol_pct = (df["volume"] > 0).sum() / len(df) * 100
        print(f"{symbol} loaded     : {len(df):,} trading days")
        print(f"Date range        : {df.index[0].date()} → {df.index[-1].date()}")
        print(f"Volume coverage   : {vol_pct:.1f}%")
    return df

def load_nasdaq(start: str = "2000-01-01", verbose: bool = True) -> pd.DataFrame:
    """Nasdaq Composite from us_prices.db (US_COMP). Replaces yfinance."""
    return load_us_index("US_COMP", verbose=verbose)


# ═══════════════════════════════════════════════════════════════════════════════
# IBD STATE MACHINE
# ═══════════════════════════════════════════════════════════════════════════════

def compute_ibd_conditions(df: pd.DataFrame, label: str = "Index") -> pd.DataFrame:
    """
    Run the IBD state machine over a full OHLCV index DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must have columns: open, high, low, close, volume
        Index must be DatetimeIndex, sorted ascending.

    Returns
    -------
    pd.DataFrame with columns:
        close, volume, chg_pct,
        ibd_condition   — current state string
        dist_count      — number of active distribution days
        rally_day       — current rally attempt day (0 = not in attempt)
        is_dist         — True if today is a distribution day
        is_ftd          — True if today is a Follow-Through Day
        has_volume      — True if both today and yesterday have volume > 0
    """
    closes  = df["close"].values
    highs   = df["high"].values
    lows    = df["low"].values
    volumes = df["volume"].values
    dates   = df.index
    n       = len(df)

    # State machine variables
    state        = CORRECTION          # start pessimistically
    dist_days    = []                  # list of (bar_index, close_at_dist_day)
    rally_day    = 0                   # 0 = no rally attempt in progress
    rally_low    = None                # intraday low of rally attempt start day
    uptrend_day  = 0                   # days since last FTD (0 when in correction)

    records = []

    for i in range(1, n):
        c0, c1  = closes[i-1], closes[i]
        v0, v1  = volumes[i-1], volumes[i]
        lo1, hi1 = lows[i], highs[i]
        chg_pct  = (c1 - c0) / c0 * 100
        has_vol  = v0 > 0 and v1 > 0

        # ── Step 1: Expire distribution days ─────────────────────────────────
        # Rule A: older than 25 sessions
        # Rule B: index has rallied ≥ 5% from that dist day's close (absorbed)
        dist_days = [
            (di, dc) for (di, dc) in dist_days
            if (i - di) <= 25 and (c1 - dc) / dc * 100 < 5.0
        ]

        is_dist = False
        is_ftd  = False

        if state in (CONFIRMED, PRESSURE):
            # ── Step 2: Check for distribution day ───────────────────────────
            if chg_pct <= -0.2:
                if has_vol and v1 > v0:
                    # Full IBD definition: down ≥ 0.2% on higher volume
                    is_dist = True
                elif not has_vol and chg_pct <= -0.5:
                    # No volume data: use stricter -0.5% threshold as proxy
                    is_dist = True

            if is_dist:
                dist_days.append((i, c1))

            dist_count = len(dist_days)

            # ── Step 3: State transitions ─────────────────────────────────────
            if dist_count >= 6:
                state     = CORRECTION
                rally_day = 0
                rally_low = None

            elif dist_count >= 5:
                state = PRESSURE

            else:
                # Recover from Under Pressure if dist days expire down to ≤ 3
                if state == PRESSURE and dist_count <= 3:
                    state = CONFIRMED

        elif state == CORRECTION:
            dist_count = len(dist_days)

            # ── Step 4: Rally attempt tracking ───────────────────────────────
            if rally_day == 0:
                # Start rally attempt on first up-close day
                if chg_pct > 0:
                    rally_day = 1
                    rally_low = lows[i]   # track lowest intraday low of attempt
            else:
                # Check for undercut → restart rally attempt
                if lo1 < rally_low:
                    rally_day = 0
                    rally_low = None
                else:
                    rally_low = min(rally_low, lo1)
                    rally_day += 1

                    # ── Step 5: Follow-Through Day check ─────────────────────
                    # Valid FTD: day 4+, up ≥ 1.25%, volume > previous day
                    if rally_day >= 4 and chg_pct >= 1.25:
                        if has_vol and v1 > v0:
                            is_ftd = True
                        elif not has_vol and chg_pct >= 1.7:
                            # No volume: require bigger move as substitute signal
                            is_ftd = True

                    if is_ftd:
                        state      = CONFIRMED
                        dist_days  = []        # fresh slate after FTD
                        dist_count = 0
                        rally_day  = 0
                        rally_low  = None

        else:
            dist_count = len(dist_days)

        # Update uptrend_day counter
        if is_ftd:
            uptrend_day = 1
        elif state in (CONFIRMED, PRESSURE):
            uptrend_day += 1
        else:
            uptrend_day = 0

        records.append({
            "close":         c1,
            "volume":        v1,
            "chg_pct":       round(chg_pct, 3),
            "ibd_condition": state,
            "dist_count":    len(dist_days),
            "rally_day":     rally_day,
            "uptrend_day":   uptrend_day,
            "is_dist":       is_dist,
            "is_ftd":        is_ftd,
            "has_volume":    has_vol,
        })

    result = pd.DataFrame(records, index=dates[1:])
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE API
# ═══════════════════════════════════════════════════════════════════════════════

def get_set_condition(verbose: bool = True) -> dict:
    """
    Returns the current IBD market condition for the Thai SET index.

    Returns
    -------
    {
      condition  : str   — "Confirmed Uptrend" / "Uptrend Under Pressure" / "Market in Correction"
      dist_count : int   — active distribution days
      rally_day  : int   — current rally attempt day (0 if not in attempt)
      set_close  : float — latest SET close
      as_of      : str   — date of latest data point (YYYY-MM-DD)
      history    : pd.DataFrame — full condition history (for charting)
    }
    """
    df  = load_set_index(verbose=verbose)
    res = compute_ibd_conditions(df, label="SET")
    latest = res.iloc[-1]
    return {
        "condition":    latest["ibd_condition"],
        "dist_count":   int(latest["dist_count"]),
        "rally_day":    int(latest["rally_day"]),
        "uptrend_day":  int(latest["uptrend_day"]),
        "set_close":    round(float(latest["close"]), 2),
        "as_of":        str(res.index[-1].date()),
        "history":      res,
    }


def _get_us_index_condition(symbol: str, label: str, close_key: str,
                            verbose: bool = True) -> dict:
    """Generic IBD condition for any US index in us_prices.db."""
    df  = load_us_index(symbol, verbose=verbose)
    res = compute_ibd_conditions(df, label=label)
    latest = res.iloc[-1]
    as_of  = str(res.index[-1].date())
    return {
        "condition":   latest["ibd_condition"],
        "dist_count":  int(latest["dist_count"]),
        "rally_day":   int(latest["rally_day"]),
        "uptrend_day": int(latest["uptrend_day"]),
        close_key:     round(float(latest["close"]), 2),
        "as_of":       as_of,
        "stale":       (pd.Timestamp.today() - res.index[-1]).days > 5,
        "history":     res,
    }

def get_nasdaq_condition(verbose: bool = True) -> dict:
    """IBD market condition for Nasdaq Composite (US_COMP)."""
    r = _get_us_index_condition("US_COMP", "Nasdaq", "nasdaq_close", verbose)
    return r

def get_spx_condition(verbose: bool = True) -> dict:
    """IBD market condition for S&P 500 (US_SPX)."""
    return _get_us_index_condition("US_SPX", "S&P 500", "spx_close", verbose)

def get_djia_condition(verbose: bool = True) -> dict:
    """IBD market condition for Dow Jones Industrial Average (US_DJI)."""
    return _get_us_index_condition("US_DJI", "DJIA", "djia_close", verbose)

def get_rut_condition(verbose: bool = True) -> dict:
    """IBD market condition for Russell 2000 (US_RUT)."""
    return _get_us_index_condition("US_RUT", "Russell 2000", "rut_close", verbose)


def get_conditions_for_backtest(start: str = "2015-01-01") -> dict:
    """
    Returns daily IBD conditions for a date range — for use in backtest engine.

    Parameters
    ----------
    start : str  — ISO date, how far back to start (warm-up included from 1982/2000)

    Returns
    -------
    {
      "SET": pd.DataFrame  — indexed by date, columns: ibd_condition, dist_count, ...
      "US":  pd.DataFrame  — same for Nasdaq
    }
    """
    # SET — load full history for proper state machine warm-up
    set_df  = load_set_index(verbose=False)
    set_res = compute_ibd_conditions(set_df)
    set_res = set_res[set_res.index >= pd.Timestamp(start)]

    # Nasdaq
    us_df   = load_nasdaq(start="2000-01-01", verbose=False)
    us_res  = compute_ibd_conditions(us_df)
    us_res  = us_res[us_res.index >= pd.Timestamp(start)]

    return {"SET": set_res, "US": us_res}


# ═══════════════════════════════════════════════════════════════════════════════
# SELF-TEST / REPORT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("IBD Market Condition — SET Index")
    print("=" * 60)

    set_result = get_set_condition(verbose=True)

    print(f"\nCurrent condition : {set_result['condition']}")
    print(f"Distribution days : {set_result['dist_count']}")
    print(f"Rally attempt day : {set_result['rally_day']} "
          f"({'in progress' if set_result['rally_day'] > 0 else 'none'})")
    print(f"SET close         : {set_result['set_close']}")
    print(f"As of             : {set_result['as_of']}")

    hist = set_result["history"]

    # Show last 10 FTDs
    ftds = hist[hist["is_ftd"]].tail(10)
    print(f"\nLast {len(ftds)} Follow-Through Days:")
    for d, row in ftds.iterrows():
        print(f"  {str(d.date())}  +{row['chg_pct']:.2f}%  "
              f"→ {row['ibd_condition']}")

    # Show last 10 distribution days
    dists = hist[hist["is_dist"]].tail(10)
    print(f"\nLast {len(dists)} Distribution Days:")
    for d, row in dists.iterrows():
        print(f"  {str(d.date())}  {row['chg_pct']:.2f}%  "
              f"dist_count={row['dist_count']}  state={row['ibd_condition']}")

    # Condition breakdown (last 252 days)
    last252 = hist.tail(252)
    counts = last252["ibd_condition"].value_counts()
    total  = len(last252)
    print(f"\nCondition breakdown (last 252 sessions):")
    for cond, cnt in counts.items():
        print(f"  {cond:35s}  {cnt:4d} days  ({cnt/total*100:.1f}%)")

    print("\n" + "=" * 60)
    print("IBD Market Condition — Nasdaq Composite")
    print("=" * 60)

    us_result = get_nasdaq_condition(verbose=True)

    print(f"\nCurrent condition : {us_result['condition']}")
    print(f"Distribution days : {us_result['dist_count']}")
    print(f"Rally attempt day : {us_result['rally_day']}")
    print(f"Nasdaq close      : {us_result['nasdaq_close']}")
    print(f"As of             : {us_result['as_of']}")

    us_hist = us_result["history"]
    last252_us = us_hist.tail(252)
    counts_us  = last252_us["ibd_condition"].value_counts()
    total_us   = len(last252_us)
    print(f"\nCondition breakdown (last 252 sessions):")
    for cond, cnt in counts_us.items():
        print(f"  {cond:35s}  {cnt:4d} days  ({cnt/total_us*100:.1f}%)")
