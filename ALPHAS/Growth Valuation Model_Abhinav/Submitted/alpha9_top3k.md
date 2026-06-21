# Alpha Strategy Documentation

## Alpha Expression

```text
rank(
    ts_min_max_diff(
        ts_zscore(
            ts_backfill(star_val_piv_sector_rank,252),
            126
        ),
        252
    )
)
```

---

## Simulation Settings

| Setting         | Value           |
| --------------- | --------------- |
| Instrument Type | Equity          |
| Region          | GLB             |
| Universe        | TOP3000         |
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

The strategy seeks to identify securities associated with sectors experiencing significant structural changes in valuation dynamics. By measuring the historical range of standardized sector valuation rankings, it targets assets linked to sectors where valuation behavior has exhibited substantial expansion over the past trading year. The underlying hypothesis is that institutional portfolio rebalancing, macroeconomic regime changes, and sector rotation activity create persistent valuation boundary shifts that can be exploited systematically.

### Rationale for Data Used

The strategy uses `star_val_piv_sector_rank`, a sector-oriented valuation ranking metric that reflects relative valuation conditions across sector groups. This data field is selected because it captures broad, top-down pricing dynamics and sector-specific risk premia, allowing the alpha to focus on macro-driven valuation behavior rather than company-specific fluctuations.

### Rationale for Operators Used

* **`ts_backfill(..., 252)`** fills missing observations using historical values over a one-year window, ensuring continuity of the underlying signal.
* **`ts_zscore(..., 126)`** standardizes the backfilled series relative to its trailing six-month distribution, making observations comparable through time.
* **`ts_min_max_diff(..., 252)`** measures the difference between the maximum and minimum standardized values over a one-year lookback period, capturing the magnitude of historical range expansion.
* **`rank(...)`** applies a cross-sectional ranking across the investment universe, transforming the raw range-expansion measure into a relative portfolio signal suitable for allocation.

---

## Alpha Construction Pipeline

1. Retrieve the sector valuation ranking signal `star_val_piv_sector_rank`.
2. Apply `ts_backfill(..., 252)` to maintain continuity in the presence of missing observations.
3. Standardize the resulting series using `ts_zscore(..., 126)` based on a trailing six-month history.
4. Compute the historical range expansion using `ts_min_max_diff(..., 252)`.
5. Measure the extent of peak-to-trough variation in the standardized signal over a one-year period.
6. Apply cross-sectional `rank(...)` across the universe.
7. Generate the final alpha vector and construct positions subject to sector neutralization and simulation constraints.

---

## Targeted Market Inefficiency

* Delayed market adjustment to changing sector-level valuation regimes.
* Persistent effects of institutional sector rotation and macro reallocation flows.
* Structural expansion and contraction of sector valuation ranges.
* Slow incorporation of sector-wide risk premium changes into security prices.
* Cross-sectional mispricing created by uneven valuation normalization across sectors.

---

## Key Characteristics

| Characteristic      | Description                                                                                                         |
| ------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Signal Type         | Sector Relative Valuation                                                                                           |
| Primary Data Field  | `star_val_piv_sector_rank`                                                                                          |
| Data Treatment      | One-Year Backfill                                                                                                   |
| Standardization     | 126-Day Time-Series Z-Score                                                                                         |
| Core Measurement    | 252-Day Min-Max Range Expansion                                                                                     |
| Portfolio Formation | Cross-Sectional Ranking                                                                                             |
| Universe            | TOP3000                                                                                                             |
| Region              | Global                                                                                                              |
| Neutralization      | Sector                                                                                                              |
| Decay               | 4                                                                                                                   |
| Delay               | 1                                                                                                                   |
| Truncation          | 0.08                                                                                                                |
| Time Horizon        | Medium to Long-Term                                                                                                 |
| Expected Behavior   | Favors securities associated with sectors exhibiting larger historical valuation range expansions relative to peers |
