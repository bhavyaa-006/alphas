# Alpha Strategy Documentation

## Alpha Expression

```python
rank(ts_delta(star_val_piv_region_rank,20))

```

## Simulation Settings

| Instrument Type | Region | Universe | Language | Decay | Delay | Truncation | Neutralization | Pasteurization | Lookback | Max Trade | Max Position |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Equity | GLB | TOP3000 | Fast Expression | 4 | 1 | 0.08 | Sector | On |  | Off | Off |

## Strategy Description

### Idea

This alpha exploits both momentum and mean-reversion characteristics within the cross-sectional distribution of `star_val_piv_region_rank`. It operates on the hypothesis that the 20-day rate of change in an asset's relative rank within this feature space provides predictive power regarding short-term alpha persistence or exhaustion.

### Rationale for Data Used

The strategy utilizes `star_val_piv_region_rank`, a ranked feature that effectively normalizes idiosyncratic asset characteristics into a standard cross-sectional distribution. This ranking is essential to enforce stationarity and mitigate the influence of outliers or regime-dependent scaling inherent in raw input data.

### Rationale for Operators Used

* **`ts_delta(..., 20)`:** Used to compute the 20-day temporal momentum of the asset's rank. This identifies assets undergoing significant relative positioning shifts over the lookback period.
* **`rank()`:** Applied as an outer operator to perform a cross-sectional transformation. This converts temporal shifts into a final relative score, ensuring the signal is market-neutral and optimized for long-short portfolio construction.

## Alpha Construction Pipeline

1. **Feature Input:** Retrieve the ranked feature `star_val_piv_region_rank` for the designated asset universe.
2. **Temporal Momentum Calculation:** Apply a 20-day time-series difference (`ts_delta`) to the input to measure the magnitude and direction of recent rank changes.
3. **Cross-Sectional Normalization:** Apply a final `rank` operator to the resulting delta values to normalize the output across the cross-section.
4. **Final Signal Generation:** Produce the alpha score, which reflects the relative strength of the asset's rank-based momentum.

## Targeted Market Inefficiency

* **Relative Positioning Persistence:** Capitalizes on trends where assets continue to improve or degrade their relative standing within the feature space over a 20-day window.
* **Mean-Reversion of Extreme Shifts:** Identifies potential exhaustion points where excessive rank movement may trigger a reversal back toward a historical mean.
* **Cross-Sectional Stationarity:** Exploits anomalies that arise when an asset's movement deviates from the normalized expectations of the broader peer group.

## Key Characteristics

| Characteristic | Specification |
| --- | --- |
| **Primary Factor / Style** | Relative Rank Momentum / Mean-Reversion |
| **Time Horizon** | Intermediate (20-day momentum window) |
| **Underlying Data Feature** | `star_val_piv_region_rank` |
| **Signal Transformation** | Cross-sectional Ranking (`rank`) |
| **Portfolio Suitability** | Long-Short (due to cross-sectional rank normalization) |

---

