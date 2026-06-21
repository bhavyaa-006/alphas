```python
markdown_content = """# Alpha Strategy Documentation

## Alpha Expression

```

```text
File generated successfully.

```python
rank(
    ts_zscore(
        star_val_piv_region_rank,
        120
    )
)

```

## Simulation Settings

| Parameter | Value |
| --- | --- |
| **Instrument Type** | Equity |
| **Region** | GLB (Global) |
| **Universe** | MINVOL1M |
| **Language** | Fast Expression |
| **Decay** | 4 |
| **Delay** | 1 |
| **Truncation** | 0.08 |
| **Neutralization** | Sector |
| **Pasteurization** | On |
| **Lookback** | *None* |
| **Max Trade** | Off |
| **Max Position** | Off |

## Strategy Description

### Idea

The strategy capitalizes on cross-sectional relative-value anomalies by identifying assets whose localized regional valuation rankings significantly diverge from their medium-term historical baselines. The underlying core hypothesis is that these historical deviations indicate overextended mispricings or accelerating structural shifts that exhibit predictive power for future cross-sectional returns.

### Rationale for Data Used

The alpha signal utilizes `star_val_piv_region_rank`, an input that captures an asset's fundamental valuation rank localized within its specific geographic or pivot region. Utilizing this granular, region-specific ranking is essential to eliminate global macro shifts or sector-wide confounding noise, thereby isolating pure, idiosyncratic regional relative value.

### Rationale for Operators Used

* **`ts_zscore(..., 120)`**: This time-series operator acts as a statistical filter over a 120-period lookback window. It quantifies the temporal velocity and mean-reverting overextensions of the asset's regional valuation rank by measuring its distance from its historical mean in units of standard deviation. *(Note: Explanatory alignment has been applied to match the mathematical expression over preliminary text notes referencing alternative moving-average diffs).*
* **`rank(...)`**: The outer cross-sectional ranking operator applies a monotonic linear transformation across the entire active asset universe. This standardizes the raw temporal signals into a uniform distribution between 0 and 1, mitigating the impact of outliers and optimizing the signal for dollar-neutral portfolio weight construction.

## Alpha Construction Pipeline

1. **Data Ingestion**: Extract the localized fundamental valuation rank (`star_val_piv_region_rank`) for all assets within the active universe.
2. **Temporal Normalization**: Compute the 120-period rolling time-series Z-score (`ts_zscore`) for each asset to isolate historical deviations from its medium-term baseline.
3. **Cross-Sectional Standardization**: Apply the cross-sectional `rank` operator to transform the historical Z-scores into a uniform distribution across the `MINVOL1M` universe.
4. **Portfolio Optimization & Simulation**: Pass the uniform cross-sectional ranks into the simulation engine applying a 1-day execution delay, a decay factor of 4, a 0.08 truncation threshold, and sector neutralization to generate final portfolio weights.

## Targeted Market Inefficiency

* **Localized Valuation Frictions**: Information asymmetry or segmented capital flows within specific geographic/pivot regions can cause asset prices to decouple from their regional peers.
* **Delayed Fundamental Assimilation**: Market participants frequently take time to absorb region-specific fundamental shifts, leading to temporary but exploitable overextensions.
* **Macro and Sector Confounding Noise**: Systematic trading flows driven by macro headlines or broad sector trends often obscure idiosyncratic regional value, creating entry points for pure relative-value strategies.
* **Behavioral Overreaction and Mean Reversion**: Capital over-allocation or panic selling within regional clusters frequently drives valuation ranks to historical extremes that subsequently revert to the medium-term mean.

## Key Characteristics

| Characteristic | Detail |
| --- | --- |
| **Strategy Style** | Cross-Sectional Relative Value / Statistical Mean Reversion |
| **Asset Class** | Equities |
| **Geographic Mandate** | Global (GLB) |
| **Trading Universe** | MINVOL1M |
| **Signal Lookback Horizon** | 120 Periods |
| **Risk Neutralization** | Sector-Neutral Portfolio Construction |
| **Execution Mechanics** | 1-Day Delay, Decay Factor of 4, 0.08 Truncation |
| """ |  |

with open("alpha_strategy_documentation.md", "w") as f:
f.write(markdown_content)

print("File generated successfully.")

```
Your Markdown file is ready
[file-tag: code-generated-file-0-1781878791978796943]

# Alpha Strategy Documentation

## Alpha Expression
```python
rank(
    ts_zscore(
        star_val_piv_region_rank,
        120
    )
)

```

## Simulation Settings

| Parameter | Value |
| --- | --- |
| **Instrument Type** | Equity |
| **Region** | GLB (Global) |
| **Universe** | MINVOL1M |
| **Language** | Fast Expression |
| **Decay** | 4 |
| **Delay** | 1 |
| **Truncation** | 0.08 |
| **Neutralization** | Sector |
| **Pasteurization** | On |
| **Lookback** | *None* |
| **Max Trade** | Off |
| **Max Position** | Off |

## Strategy Description

### Idea

The strategy capitalizes on cross-sectional relative-value anomalies by identifying assets whose localized regional valuation rankings significantly diverge from their medium-term historical baselines. The underlying core hypothesis is that these historical deviations indicate overextended mispricings or accelerating structural shifts that exhibit predictive power for future cross-sectional returns.

### Rationale for Data Used

The alpha signal utilizes `star_val_piv_region_rank`, an input that captures an asset's fundamental valuation rank localized within its specific geographic or pivot region. Utilizing this granular, region-specific ranking is essential to eliminate global macro shifts or sector-wide confounding noise, thereby isolating pure, idiosyncratic regional relative value.

### Rationale for Operators Used

* **`ts_zscore(..., 120)`**: This time-series operator acts as a statistical filter over a 120-period lookback window. It quantifies the temporal velocity and mean-reverting overextensions of the asset's regional valuation rank by measuring its distance from its historical mean in units of standard deviation. *(Note: Explanatory alignment has been applied to match the mathematical expression over preliminary text notes referencing alternative moving-average diffs).*
* **`rank(...)`**: The outer cross-sectional ranking operator applies a monotonic linear transformation across the entire active asset universe. This standardizes the raw temporal signals into a uniform distribution between 0 and 1, mitigating the impact of outliers and optimizing the signal for dollar-neutral portfolio weight construction.

## Alpha Construction Pipeline

1. **Data Ingestion**: Extract the localized fundamental valuation rank (`star_val_piv_region_rank`) for all assets within the active universe.
2. **Temporal Normalization**: Compute the 120-period rolling time-series Z-score (`ts_zscore`) for each asset to isolate historical deviations from its medium-term baseline.
3. **Cross-Sectional Standardization**: Apply the cross-sectional `rank` operator to transform the historical Z-scores into a uniform distribution across the `MINVOL1M` universe.
4. **Portfolio Optimization & Simulation**: Pass the uniform cross-sectional ranks into the simulation engine applying a 1-day execution delay, a decay factor of 4, a 0.08 truncation threshold, and sector neutralization to generate final portfolio weights.

## Targeted Market Inefficiency

* **Localized Valuation Frictions**: Information asymmetry or segmented capital flows within specific geographic/pivot regions can cause asset prices to decouple from their regional peers.
* **Delayed Fundamental Assimilation**: Market participants frequently take time to absorb region-specific fundamental shifts, leading to temporary but exploitable overextensions.
* **Macro and Sector Confounding Noise**: Systematic trading flows driven by macro headlines or broad sector trends often obscure idiosyncratic regional value, creating entry points for pure relative-value strategies.
* **Behavioral Overreaction and Mean Reversion**: Capital over-allocation or panic selling within regional clusters frequently drives valuation ranks to historical extremes that subsequently revert to the medium-term mean.

## Key Characteristics

| Characteristic | Detail |
| --- | --- |
| **Strategy Style** | Cross-Sectional Relative Value / Statistical Mean Reversion |
| **Asset Class** | Equities |
| **Geographic Mandate** | Global (GLB) |
| **Trading Universe** | MINVOL1M |
| **Signal Lookback Horizon** | 120 Periods |
| **Risk Neutralization** | Sector-Neutral Portfolio Construction |
| **Execution Mechanics** | 1-Day Delay, Decay Factor of 4, 0.08 Truncation |