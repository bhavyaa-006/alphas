# Alpha Strategy Documentation

## Alpha Expression

```text
group_neutralize(
    rank(
        reverse(
            multiply(
                ts_zscore(returns,30),
                ts_rank(
                    divide(volume,adv20),
                    20
                )
            )
        )
    ),
    industry
)
```

## Simulation Settings

| Parameter | Value |
|-----------|-------|
| Instrument Type | Equity |
| Region | GLB |
| Universe | TOP3000 |
| Language | Fast Expression |
| Decay | 4 |
| Delay | 1 |
| Truncation | 0.08 |
| Neutralization | Subindustry |
| Pasteurization | On |
| Lookback |  |
| Max Trade | Off |
| Max Position | Off |

## Strategy Description

### Idea

This alpha captures medium-term return deviations from their recent average and trades against persistent short-lived trends. The underlying hypothesis is that return anomalies gradually decay and eventually revert to their mean, allowing the strategy to exploit temporary market inefficiencies driven by investor overreaction.

### Rationale for Data Used

The strategy primarily uses returns to isolate pure price dynamics without incorporating fundamental information. Relative trading activity is introduced through the volume-to-ADV20 ratio to identify periods of abnormal participation, while industry classifications are used to remove common sector exposures and preserve stock-specific effects.

### Rationale for Operators Used

- `ts_zscore(returns,30)` standardizes returns relative to their recent 30-day history, highlighting abnormal price movements.
- `divide(volume,adv20)` measures current trading activity relative to its average level.
- `ts_rank(...,20)` ranks liquidity surges over a 20-day window to identify unusually active trading periods.
- `multiply(...)` combines abnormal returns with elevated participation, strengthening signals supported by significant market activity.
- `reverse()` converts the signal into a contrarian position to exploit potential mean reversion.
- `rank()` standardizes cross-sectional exposures across securities.
- `group_neutralize(..., industry)` removes industry-level systematic biases and enhances idiosyncratic signal quality.

## Alpha Construction Pipeline

1. Compute a 30-day z-score of stock returns to identify abnormal return behavior.
2. Calculate the ratio of current volume to 20-day average daily volume (`adv20`).
3. Rank the relative volume signal over a 20-day rolling window.
4. Multiply the abnormal return signal by the trading activity signal.
5. Reverse the combined signal to establish a contrarian exposure.
6. Rank the resulting values cross-sectionally.
7. Neutralize exposures at the industry level to remove common systematic effects.

## Targeted Market Inefficiency

- Investor overreaction to short-term price movements.
- Temporary momentum persistence that eventually weakens.
- Delayed price adjustment following abnormal trading activity.
- Excessive crowd participation that leads to subsequent reversals.
- Industry-wide effects that can mask stock-specific opportunities.

## Key Characteristics

| Characteristic | Description |
|----------------|-------------|
| Strategy Type | Contrarian / Mean Reversion |
| Primary Signal | Abnormal returns adjusted by abnormal trading activity |
| Time Horizon | Medium-term |
| Cross-Sectional Processing | Yes |
| Volume Utilization | Relative volume (`volume / adv20`) |
| Standardization | 30-day return z-score and cross-sectional ranking |
| Neutralization | Industry-level |
| Risk Control | Industry exposure removal and truncation (0.08) |
| Target Exposure | Idiosyncratic stock-specific opportunities |
| Market Coverage | Global TOP3000 equities |