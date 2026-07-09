# Alpha Strategy Documentation

## Alpha Expression

```text id="l4q9xe"
rank(
    divide(
        abs(
            ts_delta(
                mdl26_market_cap_l,
                60
            )
        ),
        add(
            ts_std_dev(
                mdl26_market_cap_l,
                60
            ),
            1
        )
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
| Lookback        | Off             |
| Max Trade       | Off             |
| Max Position    | Off             |

---

## Strategy Description

### Idea

This alpha identifies stocks undergoing unusually large changes in market capitalization relative to their own historical variability. The underlying hypothesis is that exceptional size shifts, after adjusting for a stock's normal level of fluctuation, reflect meaningful changes in investor positioning or firm fundamentals that can predict subsequent cross-sectional returns.

### Rationale for Data Used

The strategy uses `mdl26_market_cap_l`, a market capitalization factor, to capture medium-term changes in firm size driven by price movements and capital flows. A 60-day lookback provides sufficient history to estimate both the magnitude of size changes and the stock-specific variability required for normalization.

### Rationale for Operators Used

`ts_delta(mdl26_market_cap_l,60)` measures the net 60-day change in market capitalization. `abs(...)` focuses on the magnitude of the change regardless of direction, allowing the signal to capture unusually large size movements without distinguishing between increases and decreases.

`ts_std_dev(mdl26_market_cap_l,60)` estimates the historical variability of market capitalization over the same period. Adding `1` to the denominator improves numerical stability by preventing extremely small denominator values. Dividing the absolute change by the adjusted standard deviation produces a volatility-adjusted measure of abnormal size movement.

Finally, `rank` transforms the normalized signal into a robust cross-sectional ordering suitable for portfolio construction while reducing sensitivity to outliers.

---

## Alpha Construction Pipeline

1. Compute the 60-day market capitalization change using `ts_delta`.
2. Apply `abs` to measure the magnitude of the change irrespective of direction.
3. Calculate the 60-day historical standard deviation using `ts_std_dev`.
4. Add `1` to the standard deviation to improve numerical stability.
5. Divide the absolute size change by the adjusted standard deviation to obtain a volatility-adjusted signal.
6. Cross-sectionally `rank` the normalized signal to generate the final alpha.

---

## Targeted Market Inefficiency

* Abnormal market capitalization changes driven by temporary investor positioning.
* Cross-sectional mispricing following unusually large firm size movements.
* Delayed market reaction to meaningful changes in firm fundamentals.
* Stocks exhibiting size changes that are exceptional relative to their historical volatility.
* Persistent return opportunities arising from normalized market capitalization anomalies.

---

## Key Characteristics

| Characteristic             | Description                                             |
| -------------------------- | ------------------------------------------------------- |
| Strategy Type              | Cross-Sectional Relative Strength / Anomaly Detection   |
| Signal Horizon             | Medium-Term                                             |
| Primary Data Input         | `mdl26_market_cap_l`                                    |
| Core Signal                | Volatility-adjusted 60-day market capitalization change |
| Change Measurement         | 60-day `ts_delta`                                       |
| Normalization Method       | 60-day `ts_std_dev`                                     |
| Directionality             | Magnitude only (`abs`)                                  |
| Cross-Sectional Processing | `rank`                                                  |
| Neutralization             | Sector                                                  |
| Expected Alpha Source      | Abnormal market capitalization dynamics                 |
| Numerical Stability        | Denominator adjusted with `+1`                          |
| Outlier Handling           | Cross-sectional ranking reduces sensitivity to extremes |
