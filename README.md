# MOEasymmetry Quant — Open Source Tools

> The transparent quant trading platform — **shows you the math AND the trades.**

This repository contains the **open foundation** of the MOEasymmetry trading system:
- IBD-style **Relative Strength (RS) Rating** calculator
- IBD **Market State** detector (Confirmed Uptrend / Pressure / Correction)
- Mike Webster's **Power Trend** signal
- A slim **backtest engine** for momentum systems
- Working examples on Thai SET and US universes

**What this is not:** the daily integrated alpha output, the proprietary System DI/U/V/W rules, or the live paper trade record. Those are gated behind the [paid platform](https://moeasymmetry.com) (coming Q1 2027).

**Why open source?** *Anyone can compute RS — what you can't easily replicate is a daily integrated pipeline + 36 years of cross-market validated backtests + a live audit trail.* See our [transparency manifesto](docs/MANIFESTO.md) and the [8 methodology principles](docs/METHODOLOGY_PRINCIPLES.md) that govern every validation claim — including the kill switch that saved us from wiring 5 fake signals into the live pipeline in 36 hours.

---

## Quick start

```bash
git clone https://github.com/MOEasymmetry/moeasymmetry-quant-public.git
cd moeasymmetry-quant-public
pip install -r requirements.txt

# Compute IBD RS Rating on a sample CSV (price history)
python src/rs_rating.py examples/sample_prices.csv

# Compute IBD market state on the S&P 500
python src/market_state.py examples/spx_history.csv

# Run a simple Turtle 20-day breakout backtest
python src/simple_backtest.py examples/sample_prices.csv
```

---

## What's inside

```
src/
  rs_rating.py        — IBD-style RS Rating: Q1×2 + Q2 + Q3 + Q4 percentile rank 1-99
  market_state.py     — IBD state machine: distribution days, FTD, Confirmed Uptrend
  power_trend.py      — Mike Webster's 4-condition Power Trend (Nasdaq variant)
  trend_template.py   — Mark Minervini's 8-criteria Trend Template
  simple_backtest.py  — Slim Turtle 20-day breakout backtest with ATR sizing
docs/
  RS_RATING.md        — Full mathematical explanation of RS calculation
  MARKET_STATE.md     — IBD state machine logic
  POWER_TREND.md      — Webster's Power Trend
  MANIFESTO.md        — Why we open-source the foundation
examples/
  sample_prices.csv   — Sample Thai stock OHLCV (anonymized real data)
  spx_history.csv     — S&P 500 daily history (1990-present)
  expected_outputs/   — What you should get when running each script
```

---

## Acknowledgments

This work stands on the shoulders of giants. We've cited each persona's foundational contribution:

- **William J. O'Neil** — Created CANSLIM + RS Rating (*How to Make Money in Stocks*, 1988)
- **Mark Minervini** — Trend Template + VCP + SEPA framework
- **Mike Webster** — Power Trend, Progressive Exposure, 8-Week Hold (IBD)
- **Stan Weinstein** — Stage Analysis + 30-week MA framework
- **Richard Dennis** — Original Turtle Trader system
- **Pradeep Bonde (Stockbee)** — Momentum Burst rules
- **Kristjan Qullamaggie** — Episodic Pivots scaling methodology
- **Jim Simons** — Quantitative rigor + ensemble + walk-forward validation
- **Charlie Munger** — INVERT, mental models, lollapalooza effect
- **Warren Buffett** — Margin of safety, circle of competence

See `docs/PERSONA_REFERENCES.md` for full reading list.

---

## License

MIT License. See [LICENSE](LICENSE). You are free to use, modify, and redistribute this code, with attribution.

**Disclaimer:** This is research and educational software. **Not investment advice.** Past performance does not guarantee future results. Use at your own risk.

---

## Contributing

We welcome:
- Bug reports
- Test cases (especially edge cases)
- Performance optimizations
- Cross-market validations (any non-US/Thai markets)
- Citations to relevant academic papers

Please open an issue or PR.

---

## Connect

- Website: https://moeasymmetry.com (in development)
- Facebook: https://www.facebook.com/profile.php?id=61560798360421
- Substack: (launching Q3 2026)

Built in Bangkok, Thailand 🇹🇭 with quantitative rigor and transparency in mind.
