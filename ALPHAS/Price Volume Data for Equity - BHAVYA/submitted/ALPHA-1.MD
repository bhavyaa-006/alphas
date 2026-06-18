# Alpha Strategy Documentation

## Alpha Expression

```text
alpha_expr = -returns;

group_neutralize(alpha_expr, densify(subindustry))
```

---

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
| Neutralization | Sector |
| Pasteurization | On |
| Lookback | Default |
| Max Trade | Off |
| Max Position | Off |

---

## Strategy Description

### Idea

The strategy exploits short-term mean reversion under the hypothesis that recent asset price changes are overextended and will systematically reverse over the next period. It targets market inefficiencies caused by localized liquidity imbalances or transient overreactions within specific market segments.

### Rationale for Data Used

The strategy relies on historical asset returns to quantify recent price direction and magnitude, capturing the exact behavioral footprint of the overreaction. Sub-industry classification data is utilized to map assets into granular structural peers, ensuring that the detected price anomalies are evaluated relative to fundamentally similar companies.

### Rationale for Operators Used

- The unary negation operator (`-`) is applied to invert recent returns, transforming positive momentum into a short signal and negative momentum into a long signal to capture the mean-reverting edge.

- The `group_neutralize()` operator dynamically cross-sectionally de-means the signal within each subindustry group, stripping away sector-wide systematic risk and exposing pure, idiosyncratic relative-value alpha.

---

## Alpha Construction Pipeline

1. Compute each asset's recent return (`returns`).
2. Invert the return signal using unary negation (`-returns`) to capture mean reversion.
3. Convert subindustry classifications into dense group identifiers using `densify(subindustry)`.
4. Apply `group_neutralize()` within each subindustry.
5. Generate a cross-sectional relative-value alpha signal.

---

## Targeted Market Inefficiency

This alpha seeks to exploit temporary price dislocations arising from:

- Short-term investor overreaction
- Liquidity imbalances
- Behavioral biases
- Transient deviations among structurally similar companies

By neutralizing subindustry effects, the strategy isolates security-specific mispricings rather than broad industry movements.

---

## Key Characteristics

| Attribute | Description |
|-----------|-------------|
| Strategy Type | Mean Reversion |
| Signal Source | Recent Returns |
| Holding Horizon | Short-Term |
| Risk Control | Subindustry Neutralization |
| Bias | Long Recent Losers / Short Recent Winners |
| Market Exposure | Reduced via Group Neutralization |
| Alpha Style | Cross-Sectional Relative Value |

---