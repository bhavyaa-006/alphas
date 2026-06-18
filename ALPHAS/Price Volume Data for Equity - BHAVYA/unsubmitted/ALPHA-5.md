# Alpha Strategy Documentation

## Alpha Expression

```text
group_neutralize(
    rank(
        reverse(
            ts_decay_linear(
                ts_av_diff(returns,30),
                10
            )
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

This alpha exploits medium-term return deviations from their historical average, assuming that persistent short-term trends gradually exhaust and subsequently revert. It targets behavioral overreaction and delayed price correction by assigning contrarian exposures to securities exhibiting sustained abnormal return patterns.

### Rationale for Data Used

The strategy exclusively uses `returns` to isolate pure price dynamics without incorporating external liquidity or fundamental information. Industry classifications are included to remove common sector influences and preserve stock-specific mean-reversion signals.

### Rationale for Operators Used

- `ts_av_diff(returns,30)` measures the divergence of current returns from their 30-day average to identify persistent price dislocations.
- `ts_decay_linear(...,10)` assigns greater weight to recent observations while retaining temporal memory, enabling the signal to adapt to evolving market conditions.
- `reverse()` transforms prolonged return deviations into contrarian exposures.
- `rank()` standardizes the signal cross-sectionally to support robust portfolio construction.
- `group_neutralize(..., industry)` removes persistent industry biases to strengthen stock-specific alpha extraction.

## Alpha Construction Pipeline

1. Compute the deviation of current returns from their 30-day historical average using `ts_av_diff(returns,30)`.
2. Apply `ts_decay_linear(...,10)` to emphasize recent observations while preserving historical information.
3. Use `reverse()` to convert persistent return deviations into contrarian signals.
4. Rank the signal cross-sectionally using `rank()`.
5. Neutralize the ranked signal by industry using `group_neutralize(..., industry)` to remove common sector effects.

## Targeted Market Inefficiency

- Behavioral overreaction that creates persistent return deviations.
- Delayed price correction following sustained short-term trends.
- Trend exhaustion that precedes mean reversion.
- Sector-wide effects that can mask stock-specific opportunities.
- Temporary mispricing arising from investor herding behavior.

## Key Characteristics

| Characteristic | Description |
|----------------|-------------|
| Strategy Type | Cross-sectional contrarian mean reversion |
| Primary Signal Source | Deviation of returns from their 30-day historical average |
| Time Horizon | Short- to medium-term |
| Temporal Weighting | Yes, via `ts_decay_linear(...,10)` |
| Cross-Sectional Standardization | Yes, using `rank()` |
| Industry Neutralization | Yes, using `group_neutralize(..., industry)` |
| Target Exposure | Idiosyncratic return dislocations |
| Data Dependency | Price returns only |
| Market Dependency | Reduced through industry neutralization |
| Core Assumption | Persistent abnormal return patterns eventually revert toward their historical equilibrium |