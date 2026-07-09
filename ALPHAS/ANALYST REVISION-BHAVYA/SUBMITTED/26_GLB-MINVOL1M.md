# Alpha Strategy Documentation

## Alpha Expression

```text id="r6b4jf"
rank(

    reverse(

        ts_zscore(

            ts_decay_linear(

                add(

                    ts_arg_max(

                        mdl26_market_cap_u,

                        126

                    ),

                    ts_arg_min(

                        mdl26_market_cap_u,

                        126

                    )

                ),

                20

            ),

            126

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

This alpha identifies stocks exhibiting unusual long-term changes in market capitalization dynamics by measuring the timing of historical size extremes and positioning against statistically abnormal patterns. The underlying hypothesis is that securities experiencing atypical shifts between recent market capitalization peaks and troughs are likely to normalize as temporary market dislocations dissipate.

### Rationale for Data Used

The strategy uses `mdl26_market_cap_u`, a market capitalization factor, because changes in firm size often reflect shifts in investor sentiment, capital flows, and market expectations. A 126-day horizon captures medium-term structural changes while preserving sufficient historical context to identify persistent anomalies rather than short-lived fluctuations.

### Rationale for Operators Used

`ts_arg_max(...,126)` and `ts_arg_min(...,126)` measure the recency of market capitalization highs and lows, respectively. `add(...)` combines these timing characteristics into a unified indicator that represents a stock's size-cycle behavior.

`ts_decay_linear(...,20)` smooths the signal while emphasizing more recent observations. `ts_zscore(...,126)` standardizes the signal relative to each stock's annual history, allowing statistically unusual behavior to be identified consistently across securities.

`reverse` imposes a mean-reversion interpretation by betting against extreme patterns, while `rank` converts the final signal into a robust cross-sectional ordering suitable for portfolio construction and reduces sensitivity to outliers.

---

## Alpha Construction Pipeline

1. Calculate the recency of the 126-day maximum market capitalization using `ts_arg_max`.
2. Calculate the recency of the 126-day minimum market capitalization using `ts_arg_min`.
3. Combine both timing measures using `add` to create a size-cycle indicator.
4. Apply a 20-day `ts_decay_linear` to smooth the signal and emphasize recent observations.
5. Standardize the smoothed signal using a 126-day `ts_zscore`.
6. Apply `reverse` to establish a mean-reversion interpretation.
7. Cross-sectionally `rank` the final signal for portfolio construction.

---

## Targeted Market Inefficiency

* Temporary dislocations in firm size caused by changing investor sentiment.
* Medium-term overreactions in capital allocation and market expectations.
* Persistent deviations in market capitalization cycles that eventually normalize.
* Inefficient pricing associated with unusual transitions between size extremes.
* Cross-sectional mispricing arising from abnormal market capitalization dynamics.

---

## Key Characteristics

| Characteristic             | Description                                             |
| -------------------------- | ------------------------------------------------------- |
| Strategy Type              | Mean Reversion                                          |
| Signal Horizon             | Medium-Term                                             |
| Primary Data Input         | `mdl26_market_cap_u`                                    |
| Core Signal                | Timing of historical market capitalization extremes     |
| Extreme Detection Window   | 126 Days                                                |
| Signal Smoothing           | 20-day `ts_decay_linear`                                |
| Standardization Method     | 126-day `ts_zscore`                                     |
| Cross-Sectional Processing | `rank`                                                  |
| Signal Interpretation      | Contrarian (`reverse`)                                  |
| Neutralization             | Sector                                                  |
| Expected Alpha Source      | Abnormal market capitalization cycles                   |
| Outlier Handling           | Cross-sectional ranking reduces sensitivity to extremes |
