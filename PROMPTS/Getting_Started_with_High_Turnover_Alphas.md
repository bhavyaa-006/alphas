# Getting Started with High Turnover Alphas
*WorldQuant BRAIN Documentation*

This guide is a BRAIN-focused starting point for researchers who want to develop high turnover Alphas.

## Table of Contents

1. [What is a High Turnover Alpha?](#what-is-a-high-turnover-alpha)
2. [Why are High Turnover Alphas important?](#why-are-high-turnover-alphas-important)
3. [Characteristics of High Turnover Alphas](#characteristics-of-high-turnover-alphas)
4. [How can you develop High Turnover Alphas?](#how-can-you-develop-high-turnover-alphas)
5. [Actionable tips to potentially improve High TVR research quality](#actionable-tips-to-potentially-improve-high-tvr-research-quality)
6. [Potential Steps to develop High TVR Alphas](#potential-steps-to-develop-high-tvr-alphas)
7. [Potential sources of ideas for High TVR Alphas](#potential-sources-of-ideas-for-high-tvr-alphas)
8. [Understanding High Turnover Alpha Classifications](#understanding-high-turnover-alpha-classifications)
9. [Common mistakes to watch for](#common-mistakes-to-watch-for)
10. [Tips for Success](#tips-for-success)

---

## What is a High Turnover Alpha?

A high turnover Alpha is an Alpha that refreshes positions frequently and derives a meaningful share of its value from short-horizon signals. **Turnover above 20%** is the main starting point for identifying this style.

We are seeking to find signals that remain economically useful even when positions update rapidly and the effective holding horizon is short.

---

## Why are High Turnover Alphas important?

- **Diversification** — High TVR alphas have different return profiles and lower correlation to traditional low-turnover signals.
- **Signal freshness** — Shorter horizons mean faster signal decay and quicker incorporation of new information.
- **Complementary approach** — Adds orthogonal return sources to existing portfolio construction.

---

## Characteristics of High Turnover Alphas

Good high turnover research usually has the following characteristics:

- Signal updates quickly enough to justify frequent re-ranking or position changes.
- Performance is not concentrated in a tiny set of dates or instruments.
- The alpha still looks sensible after realistic constraints or more investable settings are applied.
- The idea can be explained in terms of why information should arrive and decay quickly.

---

## How can you develop High Turnover Alphas?

> **The most common mistake is to target turnover directly instead of targeting a short-lived source of information.** High turnover should be a consequence of the idea, not the idea itself.

A better workflow is:

1. Start from an intuition about a fast-moving effect.
2. Choose fields that update at the right frequency and have enough breadth.
3. Build a simple alpha that expresses that effect clearly.
4. Check whether the alpha naturally lands in a high-turnover regime.
5. Stress the idea under real-world market conditions, universe, and cost-aware variants.

---

## Actionable tips to potentially improve High TVR research quality

- **Favor changes over levels** — deltas, surprises, accelerations, and revision-like constructs often suit shorter horizons better than static levels.
- **Use conditional logic carefully** — gating on liquidity, attention, or event states can help the signal act when the mechanism is most plausible.
- **Think cross-sectionally** — many high turnover ideas are strongest as relative-value rankings rather than absolute thresholds.
- **Respect real-world market conditions** — a signal that only works in the tail of the least liquid names is less useful.
- **Prefer simple, repeatable constructions** — if you cannot explain why a transform helps, it is possibly overfitting.

---

## Potential Steps to develop High TVR Alphas

### Step 1: Start with a clean base alpha
Use a simple construction first. Avoid stacking many transforms or interactions in the first version. A compact first draft makes it much easier to understand whether the underlying idea really carries short-horizon information.

### Step 2: Validate the signal mechanics
Check whether the signal is actually moving often enough, whether coverage is acceptable, and whether the cross-section behaves sensibly.

### Step 3: Observe turnover as an outcome
After building the initial alpha, inspect whether turnover naturally exceeds the threshold. Do not force turnover higher by adding unnecessary noise or unstable transforms.

### Step 4: Test for robustness under realistic variants
Good High TVR alphas should be checked in settings that make them more realistic and more investable. Important directions include after-cost behavior, behavior under constraints, performance in more liquid subuniverses, and behavior after orthogonalization.

### Step 5: Expand only after the base idea survives
Once the base version is credible, explore variants such as alternate normalizations, event windows, industry-relative forms, or interaction terms.

---

## Potential sources of ideas for High TVR Alphas

High turnover alphas tend to come from signals whose informational edge decays quickly. Useful starting directions include:

- **Event reaction** — signals linked to earnings, guidance, revisions, filings, news flow, or other updates that produce short-lived repricing.
- **Flow and activity** — changes in analyst behavior, execution-related activity, attention, or user activity proxies that may transmit information quickly.
- **Microstructure-sensitive effects** — signals that behave differently across liquidity buckets, constraints, or market regimes.
- **Short-horizon fundamental refresh** — fast-moving fundamental deltas, estimate revisions, surprise-like quantities, or near-term changes rather than slow levels.
- **Interaction ideas** — combining a fast catalyst with a slower conditioning variable such as quality, crowding, seasonality, or industry context.

---

## Understanding High Turnover Alpha Classifications

The BRAIN platform recognizes four distinct categories of High TVR alphas. Each classification targets a different aspect of robustness and real-world market conditions.

### Base Eligibility Criteria

An alpha qualifies as High TVR if it meets **ALL** of the following:

| Criterion | Requirement |
|---|---|
| Region | USA |
| Turnover | > 20% |
| Return quality | `hightvrReturns / original alpha return > 0.75` **OR** PnL Realization Horizon < 20 days |

### Classification 1: After Cost HighTVR Alphas

**Focus:** Alphas that remain profitable after accounting for execution costs.

**Criteria:** Sharpe after applying cost > 1.0

### Classification 2: Investable HighTVR Alphas

**Focus:** Alphas that maintain performance under realistic constraints.

**Criteria (one of):**
- Sharpe after maxtrade > 2.0 **AND** Turnover after maxtrade > 20%
- Sharpe after maxpos > 2.0 **AND** Turnover after maxpos > 20%

### Classification 3: Liquid HighTVR Alphas

**Focus:** Alphas that perform well in liquid instruments.

**Criteria:**
- Sharpe in TOP200 > 1.0
- Sharpe ratio: `sharpe_top500 / sharpe_top200 > 0.7`

### Classification 4: Orthogonal HighTVR Alphas

**Focus:** Alphas that provide returns orthogonal to existing production signals.

**Criteria:** Submit-able after applying RAM neutralization

---

## Common mistakes to watch for

- **Artificial turnover** — turnover rises because the alpha is noisy, unstable, or overly reactive rather than informative.
- **Single-test dependence** — performance only looks good in one universe, one cost assumption, or one constrained setting.
- **Weak economic story** — the alpha is a chain of operators without a clear reason for short-horizon predictive power.
- **Coverage fragility** — the field only works for a narrow subset of names or dates.
- **Parameter mining** — small changes in windows or ranks flip the result dramatically.

---

## Tips for Success

Before finalizing a high turnover alpha, ask yourself:

- [ ] Does the alpha naturally operate above the high-turnover threshold?
- [ ] Is there a clear short-horizon reason for why the signal should work?
- [ ] Have you checked the idea in at least one realism-aware direction?
- [ ] Is the performance not entirely dependent on a fragile parameter choice?
- [ ] Does the dataset choice make sense for a fast-decaying signal?
- [ ] Can you explain what the alpha is capturing in one or two sentences?
- [ ] Does the alpha still look reasonable when simplified?

---

> High turnover research works well when you treat it as **short-horizon information research**, not as a mechanical turnover optimization exercise. Good ideas usually come from understanding why information should arrive, how quickly it should decay, and what market frictions it may survive.
>
> If you keep the idea clear, use datasets intentionally, and test realism early, you are much more likely to produce high turnover alphas that are genuinely useful.

---

*Source: [WorldQuant BRAIN Documentation](https://platform.worldquantbrain.com/learn/documentation/discover-brain/getting-started-high-turnover-alphas)*
