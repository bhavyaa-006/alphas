# Alpha Strategy Documentation

## Alpha Expression

```text
rank(ts_scale(mdl38_rel_val_global_rk,252))
```

---

## Simulation Settings

| Setting         | Value           |
| --------------- | --------------- |
| Instrument Type | Equity          |
| Region          | GLB             |
| Universe        | MINVOL1M        |
| Language        | Fast Expression |
| Decay           | 4               |
| Delay           | 1               |
| Truncation      | 0.08            |
| Neutralization  | Sector          |
| Pasteurization  | On              |
| Lookback        |                 |
| Max Trade       | Off             |
| Max Position    | Off             |

---

## Strategy Description

### Idea

The strategy seeks to capture long-term structural trends and persistent relative-value dynamics by evaluating the historical position of a global relative-value ranking signal over a one-year horizon. By normalizing the signal against its own historical distribution and subsequently ranking securities cross-sectionally, the alpha attempts to identify assets exhibiting sustained relative strength or weakness.

### Rationale for Data Used

The strategy uses `mdl38_rel_val_global_rk`, a pre-computed global relative-value ranking metric. This data field consolidates complex cross-sectional valuation relationships into a single standardized measure, providing an efficient representation of relative mispricing across the investment universe. As a result, it serves as the foundational signal from which the alpha extracts persistent valuation trends.

### Rationale for Operators Used

* **`ts_scale(..., 252)`** normalizes the underlying signal using a 252-trading-day lookback window, placing current observations in the context of their historical range. This reduces structural scale differences and improves comparability over time.
* **`rank(...)`** applies a cross-sectional ranking across the universe, transforming the normalized signal into a relative ordering of securities suitable for portfolio construction and allocation.

---

## Alpha Construction Pipeline

1. Retrieve the global relative-value ranking signal `mdl38_rel_val_global_rk`.
2. Apply `ts_scale(..., 252)` to normalize the signal relative to its own one-year historical range.
3. Generate a standardized time-series score for each security.
4. Apply cross-sectional `rank(...)` across the investment universe.
5. Produce a relative ordering of securities based on their normalized historical standing.
6. Construct positions using the ranked output while applying sector neutralization and the configured simulation constraints.

---

## Targeted Market Inefficiency

* Persistence of relative-value signals over extended time horizons.
* Slow market adjustment to evolving valuation relationships across securities.
* Structural trends embedded within globally derived relative-value metrics.
* Investor underreaction to gradual changes in relative attractiveness.
* Cross-sectional mispricings that remain observable after historical normalization.

---

## Key Characteristics

| Characteristic       | Description                                                                                                           |
| -------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Signal Type          | Relative Value                                                                                                        |
| Time Horizon         | Long-Term (252 Trading Days)                                                                                          |
| Normalization Method | Time-Series Scaling                                                                                                   |
| Portfolio Formation  | Cross-Sectional Ranking                                                                                               |
| Universe             | MINVOL1M                                                                                                              |
| Region               | Global                                                                                                                |
| Neutralization       | Sector                                                                                                                |
| Decay                | 4                                                                                                                     |
| Delay                | 1                                                                                                                     |
| Truncation           | 0.08                                                                                                                  |
| Signal Source        | `mdl38_rel_val_global_rk`                                                                                             |
| Expected Behavior    | Favors securities exhibiting persistent relative-value strength or weakness relative to their historical distribution |
