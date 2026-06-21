# Alpha Strategy Documentation

## Alpha Expression

```text
group_neutralize(
    rank(
        reverse(
            ts_zscore(
                vec_avg(
                    anl69_best_cur_ev_to_ebitda
                ),
                252
            )
        )
    ),
    densify(sector)
)
```

---

## Simulation Settings

| Parameter       | Value           |
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

This alpha exploits long-horizon valuation mean reversion by identifying stocks whose analyst-derived forward EV/EBITDA estimates are statistically extreme relative to their own one-year history. The underlying hypothesis is that unusually expensive or cheap valuation regimes eventually normalize as market prices adjust toward fundamental values.

### Rationale for Data Used

The strategy uses `anl69_best_cur_ev_to_ebitda`, an analyst-based forward Enterprise Value to EBITDA valuation metric. The metric is aggregated using `vec_avg` to obtain a more stable consensus estimate across available analyst inputs.

A 252-day lookback window (approximately one trading year) provides sufficient historical context to identify persistent valuation anomalies rather than temporary fluctuations, helping distinguish structural mispricing from short-term noise.

### Rationale for Operators Used

* `ts_zscore(vec_avg(anl69_best_cur_ev_to_ebitda),252)` standardizes the valuation metric relative to its own annual historical distribution, enabling the identification of statistically significant valuation extremes.
* `reverse` applies a contrarian interpretation by favoring relatively cheaper securities over more expensive ones.
* `rank` transforms the signal into a robust cross-sectional ordering suitable for portfolio construction.
* `group_neutralize(..., densify(sector))` removes sector-level structural valuation differences to isolate stock-specific mispricing opportunities.

---

## Alpha Construction Pipeline

1. Retrieve the analyst-derived forward EV/EBITDA metric (`anl69_best_cur_ev_to_ebitda`).
2. Aggregate analyst estimates using `vec_avg` to create a stable consensus valuation measure.
3. Compute a 252-day time-series z-score to identify valuation extremes relative to each stock's own historical distribution.
4. Apply `reverse` to introduce a contrarian interpretation, favoring cheaper valuations over expensive ones.
5. Rank securities cross-sectionally to normalize and standardize signal strength.
6. Neutralize sector exposures using `group_neutralize(..., densify(sector))` to remove structural industry valuation biases.
7. Generate the final alpha signal for portfolio construction.

---

## Targeted Market Inefficiency

* Slow adjustment of market prices to changes in forward fundamental valuations.
* Persistent overvaluation and undervaluation relative to historical norms.
* Behavioral overreaction that creates temporary valuation extremes.
* Structural sector valuation differences that can obscure stock-specific opportunities.
* Delayed convergence of analyst expectations and market pricing.

---

## Key Characteristics

| Characteristic             | Description                                    |
| -------------------------- | ---------------------------------------------- |
| Alpha Type                 | Fundamental Mean Reversion                     |
| Signal Horizon             | Long-term                                      |
| Core Data Source           | Analyst-derived forward EV/EBITDA              |
| Primary Factor             | Relative valuation                             |
| Signal Direction           | Contrarian                                     |
| Standardization Method     | 252-day time-series z-score                    |
| Cross-Sectional Processing | Rank                                           |
| Risk Control               | Sector neutralization                          |
| Diversification Mechanism  | Sector-adjusted stock selection                |
| Intended Edge              | Exploiting normalization of valuation extremes |
