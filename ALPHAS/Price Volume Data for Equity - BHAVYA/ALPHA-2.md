# Alpha Strategy Documentation

## Alpha Expression

```text
alpha_expr = -returns;

group_neutralize(alpha_expr, densify(industry))
```

---

## Simulation Settings

| Parameter | Value |
|-----------|-------|
| Instrument Type | Equity |
| Region | GLB |
| Universe | MINVOL1M |
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

This alpha exploits short-term mean reversion by taking the inverse of recent returns, hypothesizing that securities exhibiting recent outperformance are prone to subsequent underperformance and vice versa due to temporary price overreactions. The signal is further purified by removing systematic industry effects, isolating stock-specific reversal behavior rather than sector-driven movements.

### Rationale for Data Used

The strategy exclusively uses daily returns as a direct measure of recent price displacement, since return shocks are the primary variable required to capture short-horizon overreaction and reversal dynamics. Industry classifications are incorporated to eliminate common sector exposures that could otherwise dominate individual security signals.

### Rationale for Operators Used

- The negation operator (`-returns`) transforms a momentum signal into a contrarian signal, systematically betting against recent price movements.

- The `group_neutralize()` operator removes cross-sectional industry biases by demeaning the signal within each industry group.

- The `densify(industry)` operator converts categorical industry labels into a format suitable for group-wise neutralization, improving idiosyncratic signal extraction.

---

## Alpha Construction Pipeline

1. Compute recent asset returns using the `returns` data field.
2. Apply unary negation (`-returns`) to generate a contrarian mean-reversion signal.
3. Convert industry classifications into dense group identifiers using `densify(industry)`.
4. Apply `group_neutralize()` to remove industry-level systematic effects.
5. Produce a stock-specific relative-value alpha signal.

---

## Targeted Market Inefficiency

This alpha seeks to exploit temporary price dislocations arising from:

- Short-term investor overreaction
- Liquidity-driven price overshooting
- Behavioral biases in market participants
- Temporary divergences among stocks within the same industry

By neutralizing industry exposures, the strategy focuses on capturing idiosyncratic mean-reversion opportunities rather than broad sector movements.

---

## Key Characteristics

| Attribute | Description |
|-----------|-------------|
| Strategy Type | Mean Reversion |
| Signal Source | Daily Returns |
| Holding Horizon | Short-Term |
| Risk Control | Industry Neutralization |
| Bias | Long Recent Losers / Short Recent Winners |
| Market Exposure | Reduced via Industry Neutralization |
| Alpha Style | Cross-Sectional Relative Value |

---