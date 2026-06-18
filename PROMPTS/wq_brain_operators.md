# WorldQuant BRAIN — Operators Reference

> **Structure:** Part 1 = Quick-reference syntax table (token-safe). Part 2 = Detailed notes with examples.

---

## PART 1 — QUICK REFERENCE (Syntax + One-line description)

### Arithmetic

| Operator | Syntax | Description |
|---|---|---|
| abs | `abs(x)` | Absolute value of x |
| add | `add(x, y, filter=false)` / `x + y` | Sum all inputs (≥2). filter=true → NaN→0 before adding |
| densify | `densify(x)` | Compress grouping field with many buckets into only available buckets (0 to n-1) |
| divide | `divide(x, y)` / `x / y` | x / y |
| inverse | `inverse(x)` | 1 / x |
| log | `log(x)` | Natural logarithm of x |
| max | `max(x, y, ...)` | Maximum of all inputs (≥2 required) |
| min | `min(x, y, ...)` | Minimum of all inputs (≥2 required) |
| multiply | `multiply(x, y, ..., filter=false)` / `x * y` | Product of all inputs (≥2). filter=true → NaN→1 |
| power | `power(x, y)` | x ^ y |
| reverse | `reverse(x)` | -x |
| sigmoid | `sigmoid(x)` *(genius)* | 1 / (1 + exp(-x)) |
| sign | `sign(x)` | Returns sign of x; NaN→NaN |
| signed_power | `signed_power(x, y)` | sign(x) * (abs(x) ^ y) — sign-preserving power |
| sqrt | `sqrt(x)` | Square root of x |
| subtract | `subtract(x, y, filter=false)` / `x - y` | x - y. filter=true → NaN→0 before subtracting |
| tanh | `tanh(x)` *(genius)* | Hyperbolic tangent; output in (-1, 1) |

---

### Logical

| Operator | Syntax | Description |
|---|---|---|
| and | `and(input1, input2)` | Logical AND — true if both are true |
| if_else | `if_else(condition, expr1, expr2)` | Returns expr1 if condition true, else expr2 |
| less than | `input1 < input2` | True if input1 < input2 |
| less eq | `input1 <= input2` | True if input1 <= input2 |
| equal | `input1 == input2` | True if inputs are equal |
| greater | `input1 > input2` | True if input1 > input2 |
| greater eq | `input1 >= input2` | True if input1 >= input2 |
| not equal | `input1 != input2` | True if inputs are NOT equal |
| is_nan | `is_nan(input)` | Returns 1 if input==NaN, else 0 |
| not | `not(x)` | Logical negation: true→false, false→true |
| or | `or(input1, input2)` | Logical OR — true if either is true |

---

### Time Series

| Operator | Syntax | Description |
|---|---|---|
| days_from_last_change | `days_from_last_change(x)` | Days since x last changed |
| hump | `hump(x, hump=0.01)` | Limits magnitude/frequency of changes (reduces turnover) |
| kth_element | `kth_element(x, d, k, ignore="")` | k-th non-ignored value over past d days; backfill when k=1 |
| last_diff_value | `last_diff_value(x, d)` | Last value of x ≠ current x within past d days |
| ts_arg_max | `ts_arg_max(x, d)` | Relative index of max value over past d days (0=today) |
| ts_arg_min | `ts_arg_min(x, d)` | Relative index of min value over past d days (0=today) |
| ts_av_diff | `ts_av_diff(x, d)` | x - ts_mean(x, d), ignoring NaNs in mean |
| ts_backfill | `ts_backfill(x, lookback=d, k=1, ignore="NAN")` | Replace NaN with most recent non-NaN within d days |
| ts_corr | `ts_corr(x, y, d)` | Pearson correlation of x and y over past d days |
| ts_count_nans | `ts_count_nans(x, d)` | Count of NaN values in x over past d days |
| ts_covariance | `ts_covariance(y, x, d)` | Covariance of y and x over past d days |
| ts_decay_linear | `ts_decay_linear(x, d, dense=false)` | Linearly-weighted decay over past d days (recent=higher weight) |
| ts_delay | `ts_delay(x, d)` | Value of x d days ago |
| ts_delta | `ts_delta(x, d)` | x - ts_delay(x, d) |
| ts_entropy | `ts_entropy(x, d)` *(genius)* | Information entropy of x distribution over past d days |
| ts_max | `ts_max(x, d)` | Max of x over past d days |
| ts_mean | `ts_mean(x, d)` | Average of x over past d days |
| ts_min | `ts_min(x, d)` | Min of x over past d days |
| ts_min_diff | `ts_min_diff(x, d)` *(genius)* | x - ts_min(x, d) |
| ts_min_max_cps | `ts_min_max_cps(x, d, f=2)` *(genius)* | (ts_min(x,d) + ts_max(x,d)) - f * x |
| ts_min_max_diff | `ts_min_max_diff(x, d, f=0.5)` *(genius)* | x - f * (ts_min(x,d) + ts_max(x,d)) |
| ts_product | `ts_product(x, d)` | Product of x over past d days |
| ts_quantile | `ts_quantile(x, d, driver="gaussian")` | ts_rank mapped through inverse CDF of driver distribution |
| ts_rank | `ts_rank(x, d, constant=0)` | Rank of current x within its past d values + constant |
| ts_regression | `ts_regression(y, x, d, lag=0, rettype=0)` | OLS regression; rettype selects output (see Part 2) |
| ts_returns | `ts_returns(x, d)` | Returns of x over d days |
| ts_scale | `ts_scale(x, d, constant=0)` | (x - ts_min(x,d)) / (ts_max(x,d) - ts_min(x,d)) + constant |
| ts_skewness | `ts_skewness(x, d)` *(genius)* | Skewness of x distribution over past d days |
| ts_std_dev | `ts_std_dev(x, d)` | Standard deviation of x over past d days |
| ts_step | `ts_step(1)` | Returns days counter |
| ts_sum | `ts_sum(x, d)` | Sum of x over past d days |
| ts_target_tvr_decay | `ts_target_tvr_decay(x, lambda_min=0, lambda_max=1, target_tvr=0.1)` *(genius)* | Tune decay to hit target turnover |
| ts_zscore | `ts_zscore(x, d)` | (x - ts_mean(x,d)) / ts_std_dev(x,d) |

---

### Cross Sectional

| Operator | Syntax | Description |
|---|---|---|
| normalize | `normalize(x, useStd=false, limit=0.0)` | Subtract cross-sectional mean; useStd=true also divides by std |
| quantile | `quantile(x, driver="gaussian", sigma=1.0)` | Rank → shift → apply distribution (gaussian/uniform/cauchy) |
| rank | `rank(x, rate=2)` | Cross-sectional rank in [0, 1]; rate=0 for precise sort |
| regression_proj | `regression_proj(y, x)` *(genius)* | Cross-sectional regression; output = a + b*x per stock |
| scale | `scale(x, scale=1, longscale=1, shortscale=1)` | Scale so sum(abs(x))=1; tune with scale/longscale/shortscale |
| vector_neut | `vector_neut(x, y)` *(genius)* | Orthogonalize x w.r.t. y (removes projection of x onto y) |
| vector_proj | `vector_proj(x, y)` *(genius)* | Vector projection of x onto y |
| winsorize | `winsorize(x, std=4)` | Clip values to ±std * stddev |
| zscore | `zscore(x)` | (x - mean(x)) / std(x) cross-sectionally |

---

### Vector

| Operator | Syntax | Description |
|---|---|---|
| vec_avg | `vec_avg(x)` | Mean of vector field x |
| vec_sum | `vec_sum(x)` | Sum of vector field x |

---

### Transformational

| Operator | Syntax | Description |
|---|---|---|
| bucket | `bucket(x, range="start,end,step")` or `bucket(x, buckets="v1,v2,v3")` | Convert floats to bucket indexes; use for custom grouping |
| trade_when | `trade_when(x, y, z)` | If z>0: Alpha=NaN; elif x>0: Alpha=y; else: hold previous Alpha |

---

### Group

| Operator | Syntax | Description |
|---|---|---|
| group_backfill | `group_backfill(x, group, d, std=4.0)` | Fill NaN with winsorized mean of same-group instruments over d days |
| group_cartesian_product | `group_cartesian_product(g1, g2)` *(genius)* | Merge two groups; new group has len1 × len2 indices |
| group_extra | `group_extra(x, weight, group)` *(genius)* | Replace NaN with group mean |
| group_mean | `group_mean(x, weight, group)` | All elements in group set equal to weighted group mean |
| group_neutralize | `group_neutralize(x, group)` | Subtract group mean from each element (within-group demean) |
| group_rank | `group_rank(x, group)` | Rank within group → [0, 1] |
| group_scale | `group_scale(x, group)` | (x - groupmin) / (groupmax - groupmin) within group |
| group_zscore | `group_zscore(x, group)` | (x - group_mean) / group_stddev |

---

### Special

| Operator | Syntax | Description |
|---|---|---|
| inst_pnl | `inst_pnl(x)` *(genius)* | Per-instrument PnL (uses pv1 dataset) |

---

---

## PART 2 — DETAILED NOTES & EXAMPLES

### Arithmetic

#### `densify(x)`
Converts a grouping field with many sparse buckets into compact sequential indices (0 to n-1). Order of magnitude not preserved. Useful before passing grouping fields to group operators.
```
# If unique values are {0, 1, 2, 99} → densify maps to {0, 1, 2, 3}
```

#### `power(x, y)`
Can implement mathematical functions not directly available:
```
# Sigmoid via power:
1/(1 + power(2.7182, -close))

# Example alpha:
power(returns, volume/adv20)
power(returns, volume/adv20, precise=true)
```

#### `signed_power(x, y)`
Unlike `power`, preserves the sign of x. For y=2, `power` gives a parabola (not one-to-one), `signed_power` gives an odd, one-to-one function.
```
# If x=3, y=2:  abs(3)^2=9, sign(3)=+1 → signed_power=9
# If x=-9, y=0.5: abs(-9)^0.5=3, sign(-9)=-1 → signed_power=-3
```

#### `tanh(x)` *(genius)*
Output bounded in (-1, 1). For small x: tanh(x) ≈ x. Odd and one-to-one.
```
tanh(0)  = 0
tanh(2)  = 0.964
tanh(-2) = -0.964
```

---

### Logical

#### `if_else(condition, expr1, expr2)`
```
Event = volume > adv20;
alpha_1 = 2 * (-ts_delta(close, 3));
alpha_2 = (-ts_delta(close, 3));
if_else(Event, alpha_1, alpha_2)
```

#### `is_nan(input)`
Use with `if_else` to replace NaN with a default:
```
if_else(is_nan(rank(sales)), 0.5, rank(sales))
# If sales rank is NaN → use 0.5 (cross-sectional mean), else use rank
```

---

### Time Series

#### `hump(x, hump=0.01)`
Limits how much the alpha can change per day relative to a threshold. If change < threshold → retain yesterday's value. If change > threshold → yesterday's value ± threshold in direction of change.
- Threshold = hump × group_sum(abs(alpha), market)
- Reduces turnover and drawdown.
```
hump(-ts_delta(close, 5), hump=0.00001)
```

#### `kth_element(x, d, k, ignore="")`
Returns the k-th value (ignoring specified scalars) looking back d days. Doubles as a backfill operator when k=1.
```
kth_element(sales/assets, 252, k="1", ignore="NAN 0")
# Returns most recent non-NaN, non-zero sales/assets within 252 days
```

#### `ts_arg_max(x, d)` / `ts_arg_min(x, d)`
Returns relative index of max/min in past d days. Index 0 = today, 1 = yesterday, etc.
```
# d=6, values=[6,2,8,5,9,4] (index 0 = today):
# max=9 at index 4 → ts_arg_max = 4
# min=2 at index 1 → ts_arg_min = 1
```

#### `ts_av_diff(x, d)`
x - ts_mean(x, d), but NaNs are excluded from the mean computation.
```
# d=6, values=[6,2,8,5,9,NaN]: mean=6 (NaN ignored)
# ts_av_diff = 6 - 6 = 0
```

#### `ts_backfill(x, lookback=d, k=1, ignore="NAN")`
Replaces NaN with the most recent available non-NaN value within the lookback window. k controls which recent value (1=most recent). Improves weight coverage and reduces drawdown risk.
```
ts_backfill(sales, 252)
# If today's value = NaN → output = most recent non-NaN within 252 days
# If today's value = non-NaN → output = x
```

#### `ts_corr(x, y, d)`
Pearson correlation. Best for linearly related, normally distributed variables.
```
ts_corr(vwap, close, 20)
```
Formula: `Σ(xi-x̄)(yi-ȳ) / sqrt(Σ(xi-x̄)² · Σ(yi-ȳ)²)` over past d days.

#### `ts_decay_linear(x, d, dense=false)`
Weighted average: recent days get higher weight. Weight of day i ago = (d-i). dense=false treats NaN as 0.
```
# d=5, values=[30,5,4,5,6] (30=today):
# Numerator = 30×5 + 5×4 + 4×3 + 5×2 + 6×1 = 198
# Denominator = 5+4+3+2+1 = 15
# Output = 198/15 = 13.2  (outlier 30 is dampened)
```

#### `ts_entropy(x, d)` *(genius)*
Calculates information entropy via histogram of past d values. Default 10 buckets.
Formula: `log(d) - (1/d) * Σ H[i]*log(H[i])`

#### `ts_product(x, d)`
Useful for geometric mean: `power(ts_product(returns, 10), 1/10)`

#### `ts_quantile(x, d, driver="gaussian")`
Computes ts_rank then maps through inverse CDF of driver distribution (gaussian/uniform/cauchy).

#### `ts_rank(x, d, constant=0)`
Ranks current value of x among its own past d values. Returns value in [0, 1].

#### `ts_regression(y, x, d, lag=0, rettype=0)`
OLS regression of y on x over past d days: ŷᵢ = β·xᵢ + α

**rettype values:**
| rettype | Output |
|---|---|
| 0 | Error term (residual) |
| 1 | y-intercept (α) |
| 2 | Slope (β) |
| 3 | y-estimate (ŷ) |
| 4 | Sum of Squares of Error (SSE) |
| 5 | Sum of Squares of Total (SST) |
| 6 | R-squared |
| 7 | Mean Square Error (MSE) |
| 8 | Standard Error of β |
| 9 | Standard Error of α |

`lag` shifts x: ŷᵢ = β·x_(i-lag) + α

```
ts_regression(est_netprofit, est_netdebt, 252, lag=0, rettype=2)
# Returns β coefficient over 1 year of data

ts_regression(ts_mean(volume, 2), ts_returns(close, 2), 252)
```

#### `ts_scale(x, d, constant=0)`
Min-max normalization in time series space.
```
# d=6, values=[6,2,8,5,9,4]: min=2, max=9
# ts_scale(x, d, constant=1) = 1 + (6-2)/(9-2) = 1.57
```

#### `ts_skewness(x, d)` *(genius)*
Third central standardized moment. Positive skew → mean > median > mode. Negative skew → mean < median < mode. Negative skew signals higher tail risk for investors.
```
ts_skewness(returns, 60)
```

#### `ts_zscore(x, d)`
`(x - ts_mean(x,d)) / ts_std_dev(x,d)` — z-score in time series window. Reduces outliers and drawdown.

---

### Cross Sectional

#### `normalize(x, useStd=false, limit=0.0)`
- useStd=false: subtract cross-sectional mean
- useStd=true: also divide by cross-sectional std
- limit≠0: clip result to [-limit, +limit]
```
# x=[3,5,6,2], mean=4, std=1.82
normalize(x, useStd=false) = [-1, 1, 2, -2]
normalize(x, useStd=true)  = [-0.55, 0.55, 1.1, -1.1]
```

#### `quantile(x, driver="gaussian", sigma=1.0)`
1. Rank raw alpha → [0,1]
2. Shift: value = 1/N + value*(1-2/N) → [1/N, 1-1/N]
3. Apply inverse CDF of driver (gaussian/uniform/cauchy). sigma scales output.
```
quantile(close, driver=gaussian, sigma=0.5)
```

#### `rank(x, rate=2)`
Cross-sectional rank in [0, 1]. rate=0 for precise sort (no ties). Default rate=2. Reduces outliers and drawdown, improves Sharpe.
```
rank(close)           # approximate
rank(close, rate=0)   # precise

# X=(4,3,6,10,2) → rank(X)=(0.5, 0.25, 0.75, 1.0, 0.0)
```

#### `regression_proj(y, x)` *(genius)*
Cross-sectional OLS: fits y=a+b*x across all stocks, then outputs a+b*x per stock.
```
# Equivalent expressions:
-returns - regression_proj(-returns, ts_std_dev(returns,20))
# ≡ regression_neut(-returns, close)
```

#### `scale(x, scale=1, longscale=1, shortscale=1)`
Normalizes so sum(abs(x))=1 across all instruments. To target a specific book size: `scale(x) * booksize`.
```
scale(returns, scale=4)
scale(returns, scale=1) + scale(close, scale=20)
scale(returns, longscale=4, shortscale=3)
```

#### `vector_neut(x, y)` *(genius)*
Removes from x its component along y (orthogonalization). Output x' is perpendicular to y. Reduces correlation.
```
vector_neut(open, close)
```

#### `winsorize(x, std=4)`
Clips all values to [mean - std*σ, mean + std*σ]. Reduces impact of outliers.

#### `zscore(x)`
`(x - mean(x)) / std(x)` cross-sectionally. Mean of z-scores=0, std=1 by definition.
```
zscore(close)
```

---

### Transformational

#### `bucket(x, range="start,end,step")` / `bucket(x, buckets="v1,v2,...")`
Converts float values to bucket indexes for use as group labels.
- range mode: creates brackets from start to end with given step; adds hidden (-∞, start] and [end, +∞) buckets
- buckets mode: custom breakpoints
- `skipBegin`, `skipEnd`, `skipBoth`: remove outer hidden buckets
- `NANGroup=True`: assign NaN to a separate group (index = last bucket + 1)

```
# range mode:
# range="0.1,1,0.1", vector=[0.05,0.5,0.9] → [0, 4, 8]

# buckets mode:
# buckets="2,5,6,7,10", vector=[-1,3,6,8,12] → [0,1,2,4,5]

my_group = bucket(rank(volume), range="0.1,1,0.1");
group_neutralize(sales/assets, my_group)

my_group = bucket(rank(volume), buckets="0.2,0.5,0.7", skipBoth=True, NANGroup=True);
group_neutralize(sales/assets, my_group)
```

#### `trade_when(x, y, z)`
Logic (evaluated in order):
1. If z > 0 → Alpha = NaN (exit)
2. Elif x > 0 → Alpha = y (enter/update)
3. Else → Alpha = previous Alpha (hold)

Reduces correlation and turnover.
```
# Trade on volume signal, never exit:
trade_when(volume >= ts_sum(volume,5)/5, rank(-returns), -1)

# With exit condition:
trade_when(volume >= ts_sum(volume,5)/5, rank(-returns), abs(returns) > 0.1)
# If abs(returns)>0.1 → exit (NaN)
# elif volume above avg → take rank(-returns) position
# else → hold
```

---

### Group

#### `group_backfill(x, group, d, std=4.0)`
Fills NaN for an instrument using the winsorized mean of all non-NaN values from its group over the past d days. Winsorized = clipped at ±std*σ.
```
group_backfill(sales/assets, industry, 60)
```

#### `group_mean(x, weight, group)`
All instruments in each group are assigned that group's weighted mean. Useful for harmonic mean of ratios:
```
1 / group_mean(eps/close, 1, industry)   # Harmonic mean P/E by industry
```

#### `group_neutralize(x, group)`
Subtracts the group mean from each element (within-group demeaning). Groups: subindustry, industry, sector, country, or custom.
```
# 10 stocks, values=[3,2,6,5,8,9,1,4,8,0], first 5 in group A, last 5 in group B:
# Group A mean=4.8, Group B mean=4.4
# Output=[-1.8,-2.8,1.2,0.2,3.2, 4.6,-3.4,-0.4,3.6,-4.4]
```

#### `group_rank(x, group)`
Ranks each stock within its group → [0, 1]. Reduces outliers, drawdown, and correlation.
```
group_rank(close, subindustry)
group_rank(volume, industry)
```

#### `group_scale(x, group)`
Min-max normalization within each group: `(x - groupmin) / (groupmax - groupmin)`

#### `group_zscore(x, group)`
Z-score within each group: `(x - group_mean) / group_std`

---

## Access Levels
- **base** — available to all users
- **genius** — unlocked at Expert, Master, or Grandmaster Genius level
