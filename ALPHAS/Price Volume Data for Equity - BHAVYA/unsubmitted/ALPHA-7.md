# Alpha Strategy Documentation

## Alpha Expression

```text
group_neutralize(
    rank(
        ts_zscore(
            reverse(
                divide(
                    subtract(close,vwap),
                    vwap
                )
            ),
            20
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

This alpha exploits short-term mean reversion by identifying stocks whose closing prices deviate significantly above their VWAP and positioning for a reversal back toward their fair intraday trading level. The signal is standardized over time, cross-sectionally ranked, and industry-neutralized to isolate idiosyncratic mispricing rather than broad sector-wide effects.

### Rationale for Data Used

The strategy utilizes `close` and `vwap` because the close-to-VWAP spread captures end-of-day price dislocations relative to the market's volume-weighted consensus execution price. `industry` classifications are incorporated to remove systematic industry exposures and retain stock-specific alpha signals.

### Rationale for Operators Used

The normalized deviation `(close − vwap) / vwap` is sign-inverted using `reverse` to transform price overextensions into contrarian signals. A 20-day `ts_zscore` standardizes the signal relative to each stock's historical behavior, allowing abnormal deviations to be identified consistently across securities.

`rank` reduces sensitivity to extreme values by converting the signal into a relative cross-sectional ordering, while `group_neutralize` removes industry-level biases and improves the purity of the idiosyncratic signal.

---

## Alpha Construction Pipeline

1. Compute the normalized price deviation using `(close - vwap) / vwap`.
2. Apply `reverse` to convert price overextensions into contrarian mean-reversion signals.
3. Standardize the signal using a 20-day `ts_zscore` to measure historical abnormality.
4. Cross-sectionally `rank` the standardized values to reduce outlier influence.
5. Apply `group_neutralize` using `industry` classifications to remove industry-level exposures.
6. Generate the final stock-selection signal emphasizing idiosyncratic mean-reversion opportunities.

---

## Targeted Market Inefficiency

* End-of-day price dislocations relative to the volume-weighted consensus price.
* Temporary overreactions caused by short-term investor behavior.
* Delayed price convergence back toward fair intraday valuation levels.
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
| Cross-Sectional Processing | `rank`                                                  |
| Neutralization Method      | Industry Neutralization                                 |
| Risk Control               | Removal of industry-level exposures                     |
| Expected Alpha Source      | Idiosyncratic price dislocations                        |
| Outlier Handling           | Cross-sectional ranking reduces sensitivity to extremes |
