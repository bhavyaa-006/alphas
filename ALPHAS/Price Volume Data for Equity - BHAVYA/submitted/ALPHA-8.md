# Alpha Strategy Documentation

## Alpha Expression

```text
group_neutralize(
    rank(
        ts_decay_linear(
            ts_zscore(
                reverse(
                    divide(
                        subtract(close,vwap),
                        vwap
                    )
                ),
                20
            ),
            7
        )
    ),
    industry
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
| Neutralization  | Subindustry     |
| Pasteurization  | On              |
| Lookback        | Off             |
| Max Trade       | Off             |
| Max Position    | Off             |

---

## Strategy Description

### Idea

This alpha captures short-term mean reversion by identifying stocks whose closing prices have deviated abnormally from their VWAP and assuming these dislocations will revert toward equilibrium. A linear decay component emphasizes persistent deviations while reducing sensitivity to one-day noise, while industry neutralization isolates stock-specific effects.

### Rationale for Data Used

The strategy uses `close` and `vwap` because their relative difference measures price dislocations from the market’s volume-weighted consensus price. `industry` classifications are incorporated to eliminate common sector exposures and ensure the signal reflects idiosyncratic opportunities rather than industry-wide movements.

### Rationale for Operators Used

The normalized `(close − vwap) / vwap` spread is sign-inverted with `reverse` to create a contrarian signal. A 20-day `ts_zscore` standardizes the signal to identify statistically unusual deviations relative to each stock’s historical behavior. A 7-day `ts_decay_linear` smooths the signal and prioritizes sustained patterns over transient fluctuations.

`rank` converts the signal into a robust cross-sectional ordering that reduces the influence of outliers, while `group_neutralize` removes industry-level biases and improves the purity of the stock-specific signal.

---

## Alpha Construction Pipeline

1. Compute the normalized price deviation using `(close - vwap) / vwap`.
2. Apply `reverse` to transform price overextensions into contrarian mean-reversion signals.
3. Standardize the signal using a 20-day `ts_zscore` to identify statistically abnormal deviations.
4. Apply a 7-day `ts_decay_linear` to emphasize persistent signals and suppress short-term noise.
5. Cross-sectionally `rank` the smoothed signal to reduce outlier sensitivity.
6. Apply `group_neutralize` using `industry` classifications to remove industry-level exposures.
7. Generate the final alpha signal focused on idiosyncratic mean-reversion opportunities.

---

## Targeted Market Inefficiency

* Temporary end-of-day price dislocations relative to the volume-weighted consensus price.
* Short-term investor overreactions that create mean-reversion opportunities.
* Persistent deviations that remain observable across multiple trading sessions.
* Cross-sectional mispricing that persists after removing industry effects.
* Stock-specific anomalies that are independent of broad sector movements.

---

## Key Characteristics

| Characteristic             | Description                                             |
| -------------------------- | ------------------------------------------------------- |
| Strategy Type              | Short-Term Mean Reversion                               |
| Signal Horizon             | Short-Term                                              |
| Primary Data Inputs        | `close`, `vwap`, `industry`                             |
| Core Signal                | Normalized close-to-VWAP deviation                      |
| Standardization Method     | 20-day `ts_zscore`                                      |
| Signal Smoothing           | 7-day `ts_decay_linear`                                 |
| Cross-Sectional Processing | `rank`                                                  |
| Neutralization Method      | Industry Neutralization                                 |
| Risk Control               | Removal of industry-level exposures                     |
| Expected Alpha Source      | Persistent idiosyncratic price dislocations             |
| Noise Reduction            | Linear decay weighting suppresses one-day fluctuations  |
| Outlier Handling           | Cross-sectional ranking reduces sensitivity to extremes |
