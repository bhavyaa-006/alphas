# Neutralization on BRAIN

## What It Is
Neutralization splits raw Alpha values into groups and **normalizes each group** (subtracts the group mean from each value). Groups can be:
- The entire **market**
- **Sector / Industry / Sub-industry** (hierarchy: Sector ⊃ Industry ⊃ Sub-industry)
- Other classifications (e.g., country, exchange)

## Why It's Used
- Focuses the Alpha on **relative returns within a group**, reducing exposure to the group's overall movement.
- Produces a portfolio that is **half long, half short** (roughly equal capital in long and short positions).
- Guards against **market or industry shocks**.

**Example — Market Neutralization**
```
Alpha = -ts_delta(close, 5)
Neutralization = market
→ Alpha = Alpha - mean(Alpha)   # mean becomes 0
```
The resulting vector is normalized and scaled to book size to compute daily PnL.

## How It's Applied
- Setting **Neutralization** in Simulation Settings applies neutralization as the **last step** automatically, ensuring the Alpha is long-short neutral.
- `group_neutralize(x, group)` performs the **same operation**, but lets you apply it more granularly / explicitly within the Alpha expression.

### Simulation Settings vs. `group_neutralize`
They are interchangeable. Example:
```
alpha1 = -zscore(ebit/capex)
  → Neutralization = industry, Decay = 0, Truncation = 0   (in Settings)

alpha1 = group_neutralize(-zscore(ebit/capex), industry)
  → Neutralization = None, Decay = 0, Truncation = 0       (in Settings)
```

**Rule of thumb:** If `group_neutralize()` is the *last* operator in your expression, set:
- Neutralization → `None`
- Decay → `0`
- Truncation → `0`

(You can still insert decay/truncation operators earlier in the expression, before `group_neutralize`.)

## Tips
- Always select a neutralization value — leave it as `None` **only** if neutralization is already handled manually inside the Alpha.
- **Larger stock groups** → better for liquid universes (fewer stocks overall), to keep decent group sizes.
- **Smaller stock groups** → better for illiquid universes.
- Use **country** / **exchange** neutralization for EUR and ASI regions.

## Recommended Neutralization by Dataset Category

| Dataset Category | Recommended Neutralization | Rationale |
|---|---|---|
| Fundamental | Industry | Fundamentals affect stocks differently by industry |
| Analysts | Industry | Estimates of future fundamentals behave similarly to fundamentals |
| Model | Market / Sector / Industry / Sub-industry | Highly variable — test based on dataset subcategory |
| News | Sub-industry | Impact varies even within the same broad industry (e.g., a CEO change hits Twitter vs. Apple differently) |
| Options | Market / Sector | Options impact is fairly uniform across broad industries |
| Price Volume | Market / Sector | Generic ideas work broadly; Industry/Sub-industry neutralization can hurt performance |
| Social Media | Industry / Sub-industry | Impact depends on how broadly the content applies |
| Institutions | Sector / Industry | Depends on institution type and data provider |
| Short Interest | Industry | Primary recommendation; others worth testing |
| Insider | Industry / Sub-industry | Effects are not uniform across companies |
| Sentiment | Industry / Sub-industry | Similar reasoning to insider/social media data |
| Earnings | Industry | Same logic as Fundamental datasets |
| Macro | Market / Sector / Industry | Macro effects are broad; little variation across sub-industries |
