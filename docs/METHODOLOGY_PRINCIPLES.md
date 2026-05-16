# Methodology Principles — The Rigor Stack

*Living document. Each principle is a rule learned the hard way. Updated 2026-05-16.*

These are the 8 binding rules I apply before accepting any "validated" claim. Every principle has an origin story — a specific moment where I had something that looked like a signal until I applied this gate, then it didn't.

---

## The Rigor Stack (apply in this order)

### 1. Don't trust the mean — use median + drop-top-3

**Why**: Heavy-tailed return distributions have outliers that move the mean but not the median. A signal that looks "great on average" can be carried by 2-3 lucky observations.

**How to apply**:
- Always report median alongside mean
- Drop the top 3 (by abs value) and check if signal still holds
- If signal disappears under drop-top-3 → outlier illusion

**Origin**: Phrase performance mining 2026-05-14 — "extended" / "new high" / "cup with handle" all looked +5pp on mean, fell to flat or negative on median.

---

### 2. Bootstrap CI before binding

**Why**: A point estimate doesn't tell you the signal's stability. Need a confidence interval to know if the edge could be sampling noise.

**How to apply**:
- 10,000 resamples of (signal cohort, baseline cohort)
- Report 95% CI on the lift
- If lower bound > 0 → robust signal
- If CI spans 0 → not statistically certain

**Origin**: PATTERN_BREAKOUT_FRESH validation 2026-05-14 — pooled +3.17pp looked great, bootstrap CI was still positive, so binding-eligible.

---

### 3. Walk-forward by year — expose regime fragility

**Why**: A signal that "works pooled across 5 years" might work in 4 bull years and fail in 1 chop year.

**How to apply**:
- Split data by year
- Report lift per year
- Drop the best year — does mean lift stay positive?
- If drop-best flips negative → bull-regime artifact

**Origin**: Thai character_change 2026-05-15 — pooled +1.31pp ⭐⭐, year-WF revealed 2023 chop = -2.27pp, drop-best flipped overall to -0.17pp.

---

### 4. Regime stratification — same setup, opposite outcomes

**Why**: Many signals work in one regime and reverse in another. Pooled stats hide this.

**How to apply**:
- Define regime explicitly (e.g., index 50d > 200d for "up")
- Stratify all observations
- A signal that REVERSES sign by regime needs the regime as a gate

**Origin**: Thai character_change — UP regime +1.47% median, DOWN regime -1.48% median. Same setup, opposite outcomes. Panic mean-reversion was FALSIFIED by this stratification.

---

### 5. Freshness gate — before any IC/alpha calculation

**Why**: Stale stocks vs fresh benchmark systematically distort relative-return comparisons. Long-horizon ICs especially affected.

**How to apply**:
- Compute benchmark's latest date
- Filter universe to stocks whose latest data is ≤ N days from benchmark (typically 1 day)
- Re-run IC/alpha on fresh-only universe
- If "best horizon" changes after gating → original was an artifact

**Origin**: 2026-05-15 — my US RS "12m_equal IC=+0.26" turned out to be stale-data artifact. After freshness filter, real best horizon is 3m IC=+0.22. **Across 26 years of historical CSVs, 92% of "Top-10" names were artifacts.** Locked Nov 2026 config had been tuned on contaminated data. Caught this 3 months before deploying real money.

---

### 6. Cross-market validation — never assume US rules transfer

**Why**: Two markets can have opposite microstructure. US is momentum; Thai is mean-reversion. Same rule, opposite outcomes.

**How to apply**:
- Before applying a US-validated rule to Thai (or vice versa), test on the home market
- Sample size ≥ 1,000 observations
- Use the same rigor stack (1-5)
- If lift sign flips → market-specific, do not import

**Origin**: 2026-05-15 — US "below 50d MA" anti-pattern (-4.91pp) does NOT transfer to Thai (+0.11pp ≈ noise). Top-decile US momentum is anti-pattern on Thai (-1.02pp).

---

### 7. Intersection > single-source — when scanners and analyst calls agree

**Why**: Single-source signals (scanner alone, analyst alone) lag random baselines. Their intersection is what works.

**How to apply**:
- Don't use analyst picks as predictor (in our tests, 13% hit rate, falsified)
- Don't expect scanners to predict analyst callouts
- Use CONVERGE tag (both fire) as upgrade signal
- Intersection signals show explosive returns on real-world examples

**Origin**: 2026-05-15 lead-indicator falsification — scanners ahead of analyst calls = 13% hit rate; intersection cases = explosive winners (LRCX, PWR, SCCO each ran 40-100%+ in 6mo).

---

### 8. Date-matched baseline — the kill switch for fake phrase-anchored signals

**Why**: Any phrase-anchored "edge" must be measured against what RANDOM RS≥80 (or equivalent quality gate) tickers did on the SAME DATE. Otherwise the apparent edge is just bull-regime baseline.

**How to apply**:
- For every phrase mention, draw 5 random qualifying tickers from the same date
- Compute identical forward returns + max run-up
- Lift = phrase median − baseline median
- Survive only if Δmedian > +3pp AND drop-top-3 Δmedian > +1pp AND Δhit≥20% > +5pp
- Apply BEFORE wiring any tag as actionable

**Origin**: 2026-05-16 phrase-lift miner — tested 28 phrases on 2,728 analyst transcripts. ONE survived initial cuts ("too extended" +13.15pp median). Bootstrap CI on the survivor returned CI95 [-29.88, +17.38]pp — even the lone survivor fell when properly tested.

**Saved from wiring 5 fake signals into the live pipeline in 36 hours**:
- ACTIONABLE_BUY ("in a buy zone") — would have added -11pp drag
- SHAKEOUT_RECLAIM ("undercut and rally") — -4.2pp
- "too extended" — CI spans zero, concentration FAIL
- VCP detector — falsified on clean data
- CWH detector — falsified on clean data

---

## How the principles interact

Principles 1-4 are post-hoc filters: apply them to any existing claim and watch the apparent edge survive or die.

Principle 5 (freshness) is upstream: applied before computing the input data, prevents bad inputs.

Principles 6-7 are scope guards: tell you when to import, when to gate, when to require conjunction.

Principle 8 is the kill switch: when in doubt about whether a phrase-tagged signal is real, compare to the same-date baseline. If it doesn't beat the baseline, it's not a signal — no matter how compelling the narrative looks.

---

## What survives this stack

The locked configuration after all 8 principles have been applied:

1. **first_pullback × Webster Power Trend exit** — +0.820R per trade on clean 20-year walk-forward
2. **failed_reentry × Minervini partial_2r_ma21 exit** — +0.297R per trade
3. **RS≥80 + RS Line slope > 0** — first validated bootstrap-CI signal
4. **200d hard veto (PTJ)** — avoided 2008 GFC entirely
5. **Kill switch -10/-15/-25** — 10/10 fire drill pass
6. **Webster character_change ∩ regime UP (Thai)** — only Thai signal to survive all 4 rigor passes

Everything else that looked like an edge died under this stack. That's the work.

---

## Source attribution

This methodology emerged from a sequence of specific incidents during the freeze-period validation (2026-04 → 2026-06). The audit trail is published at substack.com/@moeasymmetry and the code at github.com/moeasymmetry-spec/moeasymmetry-quant-public.

Every "validated" claim in the locked configuration has a falsification report against it. Every falsification has a date-matched baseline test in the repository.

Methodology IS the moat.
