# Alpha Strategy Documentation

## Alpha Expression

```text id="jm7ad2"
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

The strategy aims to identify securities associated with sectors undergoing significant structural changes in valuation behavior. By measuring the historical range of standardized sector valuation rankings, it focuses on assets whose underlying sector signals have exhibited the largest valuation boundary expansions over the previous trading year. The hypothesis is that institutional hedging activity, macroeconomic regime transitions, and systematic sector rotations create persistent shifts in valuation dynamics that are not immediately reflected in prices.

### Rationale for Data Used

The strategy utilizes `star_val_piv_sector_rank`, a sector-based valuation ranking metric designed to capture relative valuation conditions across sector groups. This data field is valuable because it reflects broad macroeconomic and sector-specific pricing dynamics, allowing the alpha to target systematic valuation dislocations rather than firm-specific noise. By focusing on sector-level behavior, the signal seeks to capture persistent risk-premium changes and capital flow effects.

### Rationale for Operators Used

* **`ts_backfill(..., 252)`** fills missing observations using historical values from the previous 252 trading days, ensuring continuity and stability in the input signal.
* **`ts_zscore(..., 126)`** standardizes the sector valuation ranks relative to their trailing six-month distribution, making observations comparable through time and reducing scale-related distortions.
* **`ts_min_max_diff(..., 252)`** measures the difference between the maximum and minimum standardized values over a one-year window, quantifying the magnitude of structural range expansion within the signal.
* **`rank(...)`** applies a cross-sectional ranking across the investment universe, converting the range-expansion measure into a relative alpha signal suitable for portfolio construction.

---

## Alpha Construction Pipeline

1. Retrieve the sector valuation ranking signal `star_val_piv_sector_rank`.
2. Apply `ts_backfill(..., 252)` to replace missing values using historical observations.
3. Standardize the backfilled series with `ts_zscore(..., 126)` using a trailing six-month window.
4. Calculate the one-year peak-to-trough spread of the standardized signal using `ts_min_max_diff(..., 252)`.
5. Quantify structural valuation range expansion for each security.
6. Apply cross-sectional `rank(...)` across the universe.
7. Generate the final alpha vector and construct positions subject to sector neutralization and simulation constraints.

---

## Targeted Market Inefficiency

* Delayed market response to evolving sector-level valuation regimes.
* Persistent effects of institutional sector rotation and macro allocation flows.
* Structural expansions and contractions in sector valuation boundaries.
* Slow incorporation of changing sector risk premia into asset prices.
* Cross-sectional mispricing arising from uneven sector valuation adjustments.

---

## Key Characteristics

| Characteristic         | Description                                                                                                         |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Signal Type            | Sector Relative Valuation                                                                                           |
| Primary Data Field     | `star_val_piv_sector_rank`                                                                                          |
| Data Conditioning      | 252-Day Backfill                                                                                                    |
| Standardization Method | 126-Day Time-Series Z-Score                                                                                         |
| Core Measurement       | 252-Day Min-Max Difference                                                                                          |
| Focus                  | Structural Valuation Range Expansion                                                                                |
| Portfolio Formation    | Cross-Sectional Ranking                                                                                             |
| Universe               | MINVOL1M                                                                                                            |
| Region                 | Global                                                                                                              |
| Neutralization         | Sector                                                                                                              |
| Decay                  | 4                                                                                                                   |
| Delay                  | 1                                                                                                                   |
| Truncation             | 0.08                                                                                                                |
| Time Horizon           | Medium to Long-Term                                                                                                 |
| Expected Behavior      | Favors securities associated with sectors displaying larger historical valuation range expansions relative to peers |
