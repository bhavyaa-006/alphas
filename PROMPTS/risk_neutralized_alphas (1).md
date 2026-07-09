# WorldQuant BRAIN — Risk-Neutralized Alphas Documentation

## ⚠️ What's Possible in FASTEXPR Syntax vs. Settings-Only

This is the key practical distinction for anyone trying to control neutralization purely through alpha code (FASTEXPR) instead of the simulation `neutralization` setting.

### ✅ Possible via FASTEXPR (expression-level, manual neutralization)
These are **operators you can call directly inside your alpha expression**, for known/disclosed groupings:

```fastexpr
group_neutralize(alpha, industry)
group_neutralize(alpha, sector)
group_neutralize(alpha, subindustry)
group_neutralize(alpha, market)
group_neutralize(alpha, my_custom_group)   // e.g. a self-defined cap/size bucket
vector_neut(alpha, some_vector)             // neutralize against a custom factor vector you define
```

The docs describe this as the "rudimentary"/manual approach that existed **before** the built-in risk-neutralization feature: *"More advanced users may build their own set of risk factors, for example they may neutralize their alphas against the common size factor by defining a new group based on capitalization, and manually apply a layer of `group_neutralize` or `vector_neut` on their alpha."*
→ In this setup you'd keep `neutralization: NONE` in settings and do all the neutralization work inside the alpha expression.

### ❌ NOT possible via FASTEXPR (settings-only, proprietary risk models)
There is **no documented expression-level function or operator** — no `neutralize(alpha, STATISTICAL)`, no `neutralize(alpha, RAM)`, etc. — for the platform's built-in risk-neutralization models:

- `Slow Factors`
- `Fast Factors`
- `Slow + Fast Factors`
- `RAM` (`REVERSION_AND_MOMENTUM`)
- `Statistical` (`STATISTICAL`)
- `Crowding` (`CROWDING`)

These can **only** be activated by setting the `neutralization` field in the **simulation settings**, not written into the alpha code itself. The documentation explicitly states BRAIN **"cannot share granular details, due to confidentiality of the risk neutralized models and to prevent any potential overfitting"** — meaning the factor construction is a black box applied server-side at simulation time, with no exposed syntax to call it from within an expression.

**Bottom line:** If an AI (or you) wants to change *only* the alpha code and leave settings fixed, that only works for plain Market/Sector/Industry/Subindustry/custom-group neutralization via `group_neutralize`/`vector_neut`. For Statistical, Crowding, RAM, Slow Factors, or Fast Factors, the `neutralization` setting field itself must be changed — there is no in-expression equivalent.

---

## 1. Risk Neutralized Alphas (Overview)

### Introduction
Academic studies decompose stock returns into risk factor drivers. In the classical Fama-French model, a multi-linear regression on stock returns (Rᵢₜ) yields:

```
Rᵢₜ - R_riskfree = αᵢₜ + β1·R_marketpremium + β2·R_sizepremium + β3·R_valuepremium + εᵢₜ
```

Applying this to alphas: the **beta** of each risk factor shows its importance to the alpha's return.
- If an alpha's return is fully explained by well-documented risk factors → it adds no value (easily replicated).
- If an alpha shows a significant positive **residual (ε)** → it captures market anomalies not yet documented in risk factor databases.

BRAIN's risk-neutralization feature lets researchers explore a risk-neutralized world and find unique, previously-uncaptured returns.

### What Are Risk-Neutralized Alphas?
Available for **USA, EUR, ASI, CHN, and GLB** regions. In addition to existing neutralizations (Market, Sector, Industry, Subindustry), new risk factor sets are available:
- **Slow Factors**
- **Fast Factors**
- **Slow + Fast Factors**
- **RAM** (Reversion and Momentum)
- **Statistical**
- **Crowding**

Previously, risk-handling was rudimentary (e.g., neutralizing by industry, or manually building custom factors with `group_neutralize`/`vector_neut`). Now an alpha can be simultaneously controlled against a wide, comprehensive set of common risk factors — producing returns more representative of what the alpha actually intends to capture, reducing exposure to unwanted risk factors that may not show up in-sample but could cause drawdowns out-of-sample.

### Risk Factors' Sets — Guidance
- **Turnover space** should guide your choice of factor set.
- **Slow Factors** → recommended for **low-turnover** signals.
- **Fast Factors** / **Slow + Fast Factors** → recommended for **high-turnover** signals.
- No universal rule — experimentation is encouraged.
- Neutralizing to **Fast Factors** tends to **increase output alpha turnover** more than Slow Factors (since Fast Factors include high-turnover components like reversion).
- Use Fast/Slow+Fast neutralization only when the turnover increase is justified by a corresponding Sharpe improvement — balance risk-neutralization benefits (higher Sharpe, lower drawdown) against increased turnover.
- If an alpha isn't naturally susceptible to certain fast factors (e.g., reversion) by design, neutralizing to Fast Factors may be redundant.
- All risk factor settings assume **long-short balanced** with market neutralization, and include industry + market risk in addition to style factors.

### Summary Table

| Risk Factor Setting | Description |
|---|---|
| **Slow Factors** | Market and industry factors plus other common lower-turnover style factors. |
| **Fast Factors** | Market, industry factors, plus higher-turnover style factors (e.g., reversion alpha). |
| **Slow + Fast Factors** | Combines both slow and fast factors. |
| **RAM** | Captures short-term mean reversion and long-term momentum trends in stock prices. |
| **Statistical** | Uses statistical techniques to identify patterns in historical returns, neutralize risks, and enhance stability. |
| **Crowding** | Captures excessive investor concentration in similar positions (reduced profitability from crowded unwinding). |

### How to Start Risk-Neutralized Research
1. Try the feature first on your **previously submitted alphas** — many show improved performance and lower correlation to the original submission.
2. Once you understand the effect, set risk-neutralized settings as your **default** simulation setting to discover new, unique alphas.
3. Review the classical 5-factor Fama-French Model for deeper understanding of style factors.
4. Choose **Slow Factors** or **Fast/Slow+Fast Factors** depending on the signal's turnover.
5. Further reading (forum): *"How to start risk neutralize research?"* and *"Risk Neutralized Alpha: How to choose risk factors' set?"*

> *WorldQuant defines alphas as mathematical models that seek to predict future price movements of financial instruments.*

---

## 2. Risk Neutralization: Default Setting (Risk-Neutralized Metrics)

### Introduction
When simulating **non**–Risk Neutralized Alphas, the platform now also shows a **hypothetical** set of PnLs and performance metrics — "what if this alpha were Risk Neutralized" (using Slow/Fast/Slow+Fast Factors, etc.). These metrics are **not** calculated for alphas already simulated *with* a Risk Neutralization setting.

### Where to Find the Metrics
- Visible on the simulation results page (new PnL chart overlay).
- The **IS Summary** includes new aggregate data blocks:
  - Standard **Aggregate Data**: Sharpe, Turnover, Fitness, Returns, Drawdown, Margin, Long/Short Count (by year).
  - New **Risk Neutralized Aggregate Data**: Sharpe, Turnover, Fitness, Returns, Drawdown, Margin (aggregate only).

Example figures from documentation: Aggregate Sharpe 2.19 vs. Risk-Neutralized Sharpe 1.86; Returns 27.62% vs. 14.82%; Drawdown 10.15% vs. 6.89%; Margin 6.30‰ vs. 3.38‰.

### How to Use These Metrics
- Use them to gauge how well your alpha captures market anomalies **not** already present in the risk factor databases.
- **Caveat:** Because Risk-Neutralized metrics use a faster approximate computation technique, results differ slightly from an actual Risk Neutralization setting — notably, **turnover does not change** in the Risk-Neutralized metrics (whereas real Risk Neutralization settings can affect turnover).
- **Selection rule:** When optimizing or selecting alphas for submission, rank by the **ratio** of:
  - Risk-Neutralized Sharpe ÷ Original Sharpe, or
  - Risk-Neutralized Returns ÷ Original Returns
  
  Prefer alphas with a **higher ratio** — this indicates the alpha retains more performance after neutralization, meaning it is less susceptible to risk factors' drawdown/volatility, and possibly less correlated to other alphas.

---

## 3. Crowding Risk-Neutralized Alphas

### What Is Crowding Risk?
Occurs when many investors hold similar positions/trades. Problems include:
- **Unraveling of Crowded Positions:** Simultaneous selling by many investors → rapid price drops → increased losses.
- **Reduced Profitability:** As more investors pile into the same trade, it becomes less profitable and more vulnerable to steep declines.

### Crowding Risk Factors
For long-short neutralized alphas, style factors (e.g., **momentum**) can indicate crowding risk — instruments with strong momentum attract many investors, raising the chance of crowded trades.

### How to Simulate
Set `neutralization` to **`CROWDING`** in the simulation settings (UI dropdown or settings object) — this is **not** a FASTEXPR function; there is no in-expression equivalent:

- `language`: `FASTEXPR`
- `neutralization`: `CROWDING`
- `instrumentType`: `EQUITY` | `region`: `USA` | `universe`: `TOP3000` | `delay`: `1` | `decay`: `0` | `truncation`: `0.1` | `pasteurization`: `ON` | `unitHandling`: `VERIFY` | `nanHandling`: `ON` | `visualization`: `False`

The alpha expression itself is written in FASTEXPR as normal (e.g. `rank(-returns)`), with `CROWDING` applied by the platform post-simulation based on the setting — it cannot be invoked as `neutralize(alpha, CROWDING)` or similar within the expression.

---

## 4. RAM Risk-Neutralized Alphas (Reversion and Momentum)

### Reversion Factor
Short-term reversion: stocks that recently **underperformed** tend to see higher near-term returns; stocks that recently **outperformed** tend to decline. Based on markets overreacting to short-term events, causing temporary mispricing that later corrects. Typically operates on a **5-day** time horizon (overweight recent underperformers, underweight recent outperformers).

### Momentum Factor
Stocks with recent positive excess returns tend to continue trending up; those with negative excess returns tend to continue down (trend-following). Momentum is typically calculated as **cumulative excess return over the last 12 months**.

### Benefits of RAM Neutralization
- **Neutralize Momentum Factor:** Reduces exposure to crowded trades during strong momentum trends, minimizing correction risk.
- **Neutralize Short-Term Reversion Factor:** Hedges against mean-reversion signals, reducing unwanted risk.
- **Remove Influence of Price:** Helps strip out price effects from unrelated alphas, e.g., fundamental ratios like `eps/close`.
- **Improve Performance:** Mitigates drawdown risk, improves Sharpe Ratio, and balances turnover cost vs. benefit.

### How to Simulate
Set `neutralization` to **`REVERSION_AND_MOMENTUM`** in the simulation settings — again, this is a **settings field, not a FASTEXPR function**:

- `language`: `FASTEXPR`
- `neutralization`: `REVERSION_AND_MOMENTUM`
- `instrumentType`: `EQUITY` | `region`: `USA` | `universe`: `TOP3000` | `delay`: `1` | `decay`: `0` | `truncation`: `0.1` | `pasteurization`: `ON` | `unitHandling`: `VERIFY` | `nanHandling`: `ON` | `visualization`: `false`

Your alpha expression stays plain FASTEXPR code (e.g. `ts_rank(close, 20)`); RAM neutralization is applied by the platform based on the setting, not written into the expression.

---

## 5. Statistical Risk-Neutralized Alphas

### Background: Two Categories of Factor Models

**Fundamental Factor Models**
Use company attributes that explain cross-sectional price differences: financial health, profitability, growth potential, P/E ratio, debt-to-equity, earnings growth, etc.
- Seminal reference: Fama & French, *"The Cross-Section of Expected Stock Returns"* (1992) — introduced the **Fama-French Three-Factor Model** (market risk, **SMB** = Small Minus Big / size, **HML** = High Minus Low / value).

**Statistical Factor Models**
Apply statistical techniques (e.g., **PCA**, cluster analysis) to historical return data to identify patterns/correlations and develop alphas, seeking to predict future performance or optimize risk — capturing complex, non-linear relationships.
- Reference: Roll & Ross, *"An Empirical Investigation of the Arbitrage Pricing Theory (APT)"* — uses PCA to extract key factors from historical returns and analyze their impact on asset prices.

**Why BRAIN Focuses on Statistical Models:** Fundamental models (SLOW, FAST, SLOW_AND_FAST) are already represented in BRAIN Research, so the statistical approach adds a distinctly different, diversifying perspective — capturing factors that promote portfolio diversification and adding unique alphas to the pool.

### How to Simulate
Set `neutralization` to **`STATISTICAL`** in the simulation settings — this is a **settings field, not a FASTEXPR function**:

- `language`: `FASTEXPR`
- `neutralization`: `STATISTICAL`
- `instrumentType`: `EQUITY` | `region`: `USA` | `universe`: `TOP3000` | `delay`: `1` | `decay`: `0` | `truncation`: `0.1` | `pasteurization`: `ON` | `unitHandling`: `VERIFY` | `nanHandling`: `ON` | `visualization`: `False`

The alpha itself remains ordinary FASTEXPR (e.g. `rank(ts_delta(close, 5))`); there is no `neutralize(alpha, STATISTICAL)`-style call available inside the expression — the PCA/statistical factor model is applied server-side purely based on this setting.

Notably, this feature has been shown to **retain performance while significantly reducing risk** — maintaining alpha profitability while mitigating potential risks for more stable, reliable long-term performance. Recommended to try on existing alphas; see also Roll & Ross's APT paper for further background.

---

## Quick Reference: Neutralization Setting Values (FASTEXPR Language)

| Feature | `neutralization` setting value | Callable from within FASTEXPR expression? |
|---|---|---|
| Market / Sector / Industry / Subindustry | e.g. `INDUSTRY`, `SUBINDUSTRY` | ✅ Yes — via `group_neutralize(alpha, group)` |
| Custom group (e.g. size/cap bucket) | N/A (manual) | ✅ Yes — via `group_neutralize(alpha, custom_group)` or `vector_neut(alpha, vector)` |
| Crowding | `CROWDING` | ❌ No — settings-only |
| RAM (Reversion & Momentum) | `REVERSION_AND_MOMENTUM` | ❌ No — settings-only |
| Statistical | `STATISTICAL` | ❌ No — settings-only |
| Slow Factors | `Slow Factors` (UI label) | ❌ No — settings-only |
| Fast Factors | `Fast Factors` (UI label) | ❌ No — settings-only |
| Slow + Fast Factors | `Slow + Fast Factors` (UI label) | ❌ No — settings-only |

Common simulation settings used across all examples in this doc (FASTEXPR): `language: FASTEXPR`, `instrumentType: EQUITY`, `region: USA`, `universe: TOP3000`, `delay: 1`, `decay: 0`, `truncation: 0.1`, `pasteurization: ON`, `unitHandling: VERIFY`, `nanHandling: ON`, `visualization: False` — only the `neutralization` value changes between examples.
