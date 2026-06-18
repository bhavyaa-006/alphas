# Alpha Strategy Documentation

## Alpha Expression

```python
group_neutralize(
    rank(ts_delta(star_val_piv_region_rank,10)),
    bucket(rank(star_val_piv_region_rank), range="0,1,0.1")
)

```

## Simulation Settings

| Instrument Type | Region | Universe | Language | Decay | Delay | Truncation | Neutralization | Pasteurization | Lookback | Max Trade | Max Position |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Equity | GLB | TOP3000 | Fast Expression | 4 | 1 | 0.08 | Sector | On |  | Off | Off |

## Strategy Description

### Idea

This alpha strategy captures intra-group momentum by calculating the 10-day rate of change of a ranked feature and subsequently neutralizing that signal against the asset's current broad-feature decile. It aims to extract alpha from assets that deviate from the internal momentum trends of their specific value-pivot cohorts.

### Rationale for Data Used

The model relies heavily on the `star_val_piv_region_rank` feature, which functions dually as the target for momentum measurement and the basis for cohort partitioning. This duality allows the strategy to precisely isolate relative performance shifts while controlling for any inherent statistical biases introduced by the asset's current valuation or pivot state.

### Rationale for Operators Used

* **`ts_delta(..., 10)`:** Deployed to quantify short-term temporal acceleration over a 10-day lookback window.
* **`rank()`:** Transforms the time-series change into a normalized cross-sectional signal, ensuring comparability across the universe.
* **`group_neutralize` & `bucket(...)`:** Mapped against a 10-decile segment (using `range="0,1,0.1"`), these operators perform a sophisticated orthogonalization. This process systematically strips away performance attribution tied solely to the asset’s starting bucket, cleanly isolating idiosyncratic momentum.

## Alpha Construction Pipeline

1. **Ingest Base Signal:** Retrieve the `star_val_piv_region_rank` feature for the target asset universe.
2. **Calculate Momentum:** Apply a 10-day time-series difference (`ts_delta`) to the base feature to measure short-term temporal acceleration.
3. **Cross-Sectional Normalization:** Rank the resulting 10-day delta across the entire cross-section to generate the primary momentum signal.
4. **Establish Cohorts:** Independently rank the original `star_val_piv_region_rank` and partition it into 10 distinct deciles using the `bucket` operator.
5. **Orthogonalize Signal:** Apply `group_neutralize` to the ranked momentum signal (Step 3) with respect to the generated decile cohorts (Step 4) to produce the final, neutralized alpha score.

## Targeted Market Inefficiency

* **Intra-Cohort Divergence:** Exploits localized momentum variations by identifying assets that are accelerating or decelerating relative to peers within their exact same valuation group.
* **Valuation Bias Mitigation:** Overcomes inefficiencies where the broader market overly attributes an asset's performance to its baseline valuation state, missing short-term idiosyncratic shifts.
* **Delayed Pricing of Relative Shifts:** Capitalizes on the market's delayed reaction to short-term, asset-specific rate-of-change anomalies that occur within heavily clustered peer groups.

## Key Characteristics

| Characteristic | Specification |
| --- | --- |
| **Primary Factor / Style** | Intra-Group Momentum |
| **Time Horizon** | Short-term (10-day parameter) |
| **Underlying Data Feature** | `star_val_piv_region_rank` |
| **Signal Transformation** | Cross-sectional Ranking (`rank`) |
| **Risk Control Method** | Decile-based Group Neutralization (`group_neutralize`, `bucket`) |