# Alpha Strategy Documentation

## Alpha Expression


quantile(
  add(
    group_rank(star_val_sector_rank, sector),
    group_rank(ts_delta(star_val_sector_rank, 10), sector)
  ),
  driver="gaussian",
  sigma=1.5
)


## Simulation Settings

| Setting | Value |
| --- | --- |
| Instrument Type | Equity |
| Region | GLB |
| Universe | MINVOL1M |
| Language | Fast Expression |
| Decay | 4 |
| Delay | 1 |
| Truncation | 0.08 |
| Neutralization | Sector |
| Pasteurization | On |
| Lookback | Off |
| Max Trade | - |
| Max Position | - |

## Strategy Description

### Idea

This alpha constructs a sector-neutral valuation momentum signal by synthesizing the current cross-sectional ranking of `star_val_sector_rank` with the 10-day change in that ranking. The strategy targets relative valuation inefficiencies by identifying securities that exhibit both strong sector-adjusted valuation positioning and improving valuation rank momentum.

### Rationale for Data Used

The strategy utilizes `star_val_sector_rank`, a sector-relative valuation factor, alongside a 10-period `ts_delta` to capture both the absolute valuation state and its recent directional velocity. By grouping by sector, the alpha ensures that the signal is evaluated relative to industry peers, effectively mitigating unintended industry-level factor bias.

### Rationale for Operators Used

* **`group_rank`**: Converts raw valuation values and their temporal changes into sector-relative cross-sectional ranks, ensuring consistency across diverse sub-universes.
* **`add`**: Integrates the static (level) and dynamic (momentum) components into a unified composite signal.
* **`quantile` (Gaussian/Sigma 1.5)**: Normalizes the final distribution, effectively controlling signal scaling, moderating the impact of outliers, and improving robustness across the trading universe.

## Alpha Construction Pipeline

1. **Calculate Cross-Sectional Ranks**: Compute the cross-sectional rank of the current `star_val_sector_rank` for every security within its respective sector.
2. **Quantify Temporal Change**: Calculate the 10-day `ts_delta` of the `star_val_sector_rank`, then compute the cross-sectional rank of these changes within each sector.
3. **Aggregate Components**: Combine the static valuation rank and the dynamic momentum rank using an additive operator.
4. **Distribution Normalization**: Apply a Gaussian quantile transformation with a sigma of 1.5 to map the combined signal into a stable, normalized distribution.

## Targeted Market Inefficiency

* **Valuation Mean Reversion/Momentum**: Exploits the tendency for assets to underperform or overperform based on the velocity of their valuation adjustment relative to sector peers.
* **Sector-Relative Mispricing**: Identifies valuation discrepancies that are localized to specific industries, rather than broad-market systematic trends.
* **Inefficient Information Diffusion**: Capitalizes on the delayed reaction of market participants to changes in a security's fundamental valuation rank.

## Key Characteristics

| Characteristic | Description |
| --- | --- |
| **Factor Style** | Valuation Momentum |
| **Neutralization** | Sector-Neutral |
| **Data Sensitivity** | 10-day Lookback |
| **Signal Distribution** | Gaussian Normalized |