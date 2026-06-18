# Alpha Strategy Documentation

## Alpha Expression

```text
group_neutralize(
    reverse(
        ts_decay_linear(
            rank(
                ts_av_diff(returns,20)
            ),
            7
        )
    ),
    industry
)
```

## Simulation Settings

| Setting | Value |
|---------|-------|
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

This alpha exploits medium-term return deviations that persist over time, hypothesizing that sustained departures from historical return norms eventually reverse as market participants overreact. It targets temporary mispricings created by behavioral biases and delayed information assimilation while neutralizing sector-wide effects.

### Rationale for Data Used

The strategy exclusively uses `returns` to capture pure price-based anomalies without introducing liquidity or fundamental variables. Industry classifications are incorporated to remove common sector exposures and isolate idiosyncratic mean-reversion opportunities.

### Rationale for Operators Used

- `ts_av_diff(returns,20)` measures the divergence of current returns from their 20-day average to identify abnormal performance regimes.
- `rank()` converts these deviations into robust cross-sectional signals that are less sensitive to outliers.
- `ts_decay_linear(...,7)` applies greater weight to recent observations while retaining temporal memory to capture evolving return dynamics.
- `reverse()` transforms persistent return extremes into contrarian exposures.
- `group_neutralize(..., industry)` removes systematic industry biases to improve stock-specific alpha purity.

## Alpha Construction Pipeline

1. Compute the deviation of current returns from their 20-day historical average using `ts_av_diff(returns,20)`.
2. Apply `rank()` to standardize the deviations across the cross-section.
3. Use `ts_decay_linear(...,7)` to emphasize more recent observations while preserving historical information.
4. Apply `reverse()` to generate contrarian exposures from persistent return extremes.
5. Neutralize the resulting signal by industry using `group_neutralize(..., industry)` to remove common sector influences.

## Targeted Market Inefficiency

- Behavioral overreaction that causes persistent return anomalies.
- Delayed information assimilation across market participants.
- Trend exhaustion that leads to mean reversion.
- Temporary mispricing arising from investor herding behavior.
- Industry-wide effects that can obscure stock-specific opportunities.

## Key Characteristics

| Characteristic | Description |
|----------------|-------------|
| Strategy Type | Cross-sectional contrarian mean reversion |
| Primary Signal Source | Deviation of returns from their 20-day historical average |
| Time Horizon | Short- to medium-term |
| Temporal Weighting | Yes, via `ts_decay_linear(...,7)` |
| Cross-Sectional Standardization | Yes, using `rank()` |
| Industry Neutralization | Yes, using `group_neutralize(..., industry)` |
| Target Exposure | Idiosyncratic return dislocations |
| Data Dependency | Price returns only |
| Market Dependency | Reduced through industry neutralization |
| Core Assumption | Persistent return deviations eventually revert toward their historical equilibrium |