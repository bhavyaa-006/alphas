# WorldQuant BRAIN — SuperAlpha Documentation

> Source: platform.worldquantbrain.com/learn/documentation/superalpha
> Captured: 6/21/26

---

## Table of Contents

1. [What is a SuperAlpha?](#what-is-a-superalpha)
2. [Selection Expression](#selection-expression)
3. [Combo Expression](#combo-expression)
4. [SuperAlpha Results](#superalpha-results)
5. [Helpful Tips](#helpful-tips)
6. [SuperAlpha Operators (Appendix)](#superalpha-operators-appendix)
7. [Global SuperAlphas](#global-superalphas)

---

## What is a SuperAlpha?

*Prev: (none) | Next: Selection Expression*

### Table of Contents (in-page)
1. SuperAlpha Simulation Modes
   - What is the In-Sample (IS) Period?
   - What is the Out-of-Sample (OS) Period?
   - What does OS Start Date (os_start_date) mean?
   - What happens when the IS Period rolls forward?
2. Getting started with Component Activation modes
   - What is Component Activation?
   - Why is Component Activation important?
3. How does Activation Mode differ from filtering by os_start_date?
   - What happens when you filter by os_start_date?
   - Why is OS Component Activation mode better for SuperAlpha evaluation?
4. Advantages and Disadvantages of IS and OS Component Activation
5. Getting started with Component Activation setting
6. Summary

SuperAlpha is a new feature in BRAIN designed to help consultants realize the power of combining many, diverse signals. SuperAlpha gives you the power and flexibility to creatively manipulate and combine the Alphas you have already created and produce even stronger, more robust signals.

SuperAlphas have two main parts – a selection expression, and a combo expression. The selection expression chooses which Alphas to include in the SuperAlpha. The combo expression determines how to combine the selected Alphas. The values in the SuperAlpha settings menu constrain how the selection and combo expressions work.

**Flow diagram:**
`Submitted alphas with 'ACTIVE' status` → **1. Selection Expression** (Which alphas to include in the SuperAlpha) → **2. Combo Expression** (How to combine the selected alphas)

To simulate a SuperAlpha, on the Simulation page use the '+' button and choose 'New SuperAlpha Simulation':

- + New Single Simulation
- + New Multi-Simulation
- + New Super Simulation

Your SuperAlphas will be listed on the Alphas page with type = Super (while Alphas have type = regular).

### SuperAlpha Simulation Modes

SuperAlpha simulations in BRAIN allow you to combine multiple Alphas into a single, more robust signal. To evaluate the performance of a SuperAlpha, it is essential to understand the In-Sample (IS) and Out-of-Sample (OS) periods of the component Alphas.

#### What is the In-Sample (IS) Period?

- The IS period is a rolling 10-year simulation window.
- It starts approximately **12 years ago** and ends around **2 years ago**.
- The IS period shifts forward **2-3 times a year**, meaning the start and end dates are updated periodically.
- This period is used to simulate and evaluate Alphas based on historical data.

#### What is the Out-of-Sample (OS) Period?

- The OS period begins **after the IS end date**.
- It includes the period where the Alphas are evaluated on unseen data, providing a more realistic measure of their live performance.

**Timeline diagram:**
`IS Start Date (2012-07-16)` —[In Sample]→ `IS End Date (2022-07-15)` —[Out Sample]→ `Alpha Submission Date`

#### What does OS Start Date (os_start_date) mean?

- The OS start date is the **next date after the IS end date** at the time the Alpha was submitted.
- You can find the os_start_date for submitted Alphas:
  - Go to the **Alphas page**, switch to the **Submitted tab**, open the Alpha, and scroll to **OS Summary**.

Example API call:
```
response_json = session.get("https://api.worldquantbrain.com/alphas/{alpha_id}").json()
response_json["os"]["startDate"]
```

Example OS Summary table fields shown in UI: Start Date, Sharpe, Turnover, Fitness, Returns, Drawdown, Margin; and a yearly breakdown table with columns: Year, Sharpe, Turnover, Fitness, Returns, Drawdown, Margin, Long Count, Short Count. Also shows Sharpe 60, Sharpe 125, Sharpe 250, Sharpe 500, OS/IS Ratio, Pre-Close Sharpe, Pre-Close Ratio, Self-Correlation.

#### What happens when the IS Period rolls forward?

- If you select component Alphas created using the **current IS period**, the SuperAlpha performance will depend **only on the IS performance** of the component Alphas.
- After the IS period rolls forward, the same SuperAlpha simulation will include the **OS performance** of the component Alphas.

### Getting started with Component Activation modes

#### What is Component Activation?

The Component Activation setting gives you greater control when combining Alphas in a SuperAlpha by allowing you to manage their activation period:

- **IS** - Alphas contribute to the SuperAlpha from the start of their In-Sample (IS) period.
- **OS** - Alphas contribute to the SuperAlpha starting from their Out-of-Sample (OS) period.

#### Why is Component Activation important?

When combining Alphas in a SuperAlpha:

- Once an Alpha is selected, the same combination logic applies in both IS and OS periods of that Alpha.
- At any point in the SuperAlpha's history:
  - **Some Alphas are in IS:** Their performance can inflate SuperAlpha performance due to overfitting at both the Alpha and SuperAlpha levels. The SuperAlpha overweights IS signals because they appear stronger, creating a feedback loop that further amplifies IS performance.
  - **Some Alphas are in OS:** Their performance is likely lower, causing the SuperAlpha to underweight these signals and concentrate on IS signals.
- As a result, the back-test may look good, but OS performance can drop sharply.

### How does Activation Mode differ from filtering by os_start_date?

#### What happens when you filter by os_start_date?

- Filtering requires you to manually filter component Alphas based on their os_start_date.
- You need to match the exact os_start_date to evaluate SuperAlpha performance during the OS period.
- If component Alphas have different OS start dates, their OS performance cannot be evaluated collectively, as it gets mixed with their IS performance.

#### Why is OS Component Activation mode better for SuperAlpha evaluation?

- Automatically uses the OS start date of each component Alpha during simulation.
- This allows you to evaluate SuperAlpha performance on unseen data, even if component Alphas have varying OS start dates.
- The period where component Alphas were not fitted can be a strong predictor of your SuperAlpha's OS performance.

### Advantages and Disadvantages of IS and OS Component Activation

**IS Activation:**
- Advantages:
  - IS activation uses a longer history (10y), providing more data for research and refinement.
  - Useful for identifying promising signals during initial research.
- Disadvantages:
  - IS activation can inflate performance due to overfitting at both the Alpha and SuperAlpha levels.

**OS Activation:**
- Advantages:
  - Helps to avoid overfitting on IS period.
  - Provides a clearer picture of the true performance of the SuperAlpha.
- Disadvantages:
  - OS activation relies on a smaller history (<5y), which may limit the scope of analysis.

### Getting started with Component Activation setting

The Super Simulation Settings panel includes (among other fields) a **COMPONENT ACTIVATION** dropdown with options:
- IS
- OS

To make the most of this feature, consider following this workflow:

- **Initial research**: Start with **IS Activation**. Focus on IS Sharpe - performance on a longer history.
- **Reality check**: After finalizing any major change, switch to **OS Activation**. Check if the OS-only performance of your SuperAlpha improves. Improvements that don't translate to better OS-only performance are likely overfitted to IS and may reduce the OS performance of the SuperAlpha.

### Summary

The **Component Activation** helps you:

- Avoid overfitting by activating Alphas only from the start of their OS period.
- Gain a clearer understanding of your SuperAlpha's true performance.
- Ensure your SuperAlpha is robust, reliable, and optimized on component's OS period.

---

## Selection Expression

*Prev: What is a SuperAlpha? | Next: Combo Expression*

### Table of Contents (in-page)
1. Selection expression
2. How it Works
3. SuperAlpha Settings
4. Available Data Fields
   - Alpha Properties are listed in the Table
   - Additional SuperAlpha selection features
   - Dataset names are listed in the Table
5. Available Operators
6. Example Selection Expressions

### Selection expression

The selection expression chooses which Alphas to include in your SuperAlpha. You can select from all of your submitted Alphas with 'ACTIVE' status. Alpha selection is binary – each Alpha is either selected or excluded.

(UI: a "Selection Expression" code editor with a "Run Selection" button.)

### How it Works

The syntax for the selection expression is designed to be similar to that of Alpha expressions, and uses many of the same operators. Similar to how an Alpha expression is evaluated for each instrument in a selected universe, the Selection expression is evaluated for each of your submitted Alphas. The value of the selection expression is called "selection weight", and your Alphas are ordered by this value with the largest values first. This order, combined with some SuperAlpha settings, is used to determine which Alphas are selected.

### SuperAlpha Settings

Some SuperAlpha settings constrain the selection expression. These include Language, Instrument Type, Region, Delay, Selection Handling, and Selection Limit. You may only have one option for some of these settings. Only Alphas matching the Language, Instrument Type, Region, and Delay settings will be selected. Selection Handling and Selection Limit are discussed in more detail below.

Example settings panel shown (Super Simulation 1):

| Setting | Example Value |
|---|---|
| LANGUAGE | Fast Expression |
| INSTRUMENT TYPE | Equity |
| REGION | USA |
| DELAY | 1 |
| SELECTION HANDLING | Positive |
| SELECTION LIMIT | 10 |

Combo settings (lower section):

| Setting | Example Value |
|---|---|
| UNIVERSE | TOP3000 |
| NEUTRALIZATION | Industry |
| DECAY | 2 |
| TRUNCATION | 0.08 |
| PASTEURIZATION | On |
| UNIT HANDLING | Verify |
| NAN HANDLING | Off |

#### Selection Handling

The selection handling setting determines what types of selection weight values are included.
- The **"Positive"** setting means that only positive values are included. For example, an Alpha which evaluates to zero would be excluded from the ordered set of Alphas if selection handling is set to "Positive".
- The **"Non-Zero"** setting means that only non-zero values are included; zero and NaN values are excluded.
- The **"Non-NaN"** setting means that real numbers and +/- infinity are included; only NaN values are excluded.

Using the "Positive" or "Non-Zero" settings makes it simpler to use equalities and inequalities to select Alphas. The "Non-NaN" setting allows for the greatest flexibility, but may be more difficult to use. Refer to the Example Selection Expressions below for the details.

#### Selection Limit

The selection limit setting determines the maximum number of Alphas to select. From the ordered set of Alphas, only the top n are selected, where n is the selection limit. The required min value for the selection limit is **10**.

As a rule of thumb, the more Alphas, the better the performance, but it also means longer simulation times. So you can first start with a smaller number of Alphas to test an idea then scale the number of Alphas.

#### Booleans

Comparisons evaluate to either 1 or 0. In the selection expression, True is interpreted as 1, and False is interpreted as 0. If using the "Positive" or "Non-Zero" selection handling settings, False values will be excluded since 0.0 is not a positive or non-zero value. If using the "Non-NaN" selection handling setting, False values will not be excluded but may impact the order of your Alphas.

#### Operator Limit Constraint

A SuperAlpha is a combination of Alphas thus naturally it consumes more resources to maintain. Thus in order to handle the memory & resource constraint of the SuperAlpha we place a threshold on the number of operators which can be used inside the SuperAlpha. **Current limit is 8000 operators.** What this means is that let's say you simulate a SuperAlpha with selection_limit=50, but the total number of operators these underlying Alphas use exceeds 8000. Then the SuperAlpha simulation will automatically truncate the number of Alphas to meet this limit. In the aforementioned example, the final simulation may only have 45 Alphas.

Operator limit constraint violation will not lead to simulation error but a warning will be displayed.

**How should you avoid violating this constraint?**

One simple way is to use less number of Alphas. Another more clean approach is to use operator_count field in your selection. This way you can control the number of operators.

Operator limit constraint violation will not lead to simulation error but a warning will be displayed:

1. A warning above the Selected Alphas list on the simulate page:
   > 41 Alphas have been selected
   > **Selection limited to 7856 operator count.**

2. A warning above the Selected Alphas on the Alphas page:
   > Show [10] out of 41. Selection limited to 7856 operator count.

3. A warning at the bottom of the code editor after the simulation is complete:
   > Selection limited to 7856 operator count

4. A warning in the alphas IS Testing Status:
   > 1 WARNING
   > • Selection limited to 7856 operator count

### Available Data Fields

These Alpha properties are available to use in selection expressions. Some Alphas may not have data for all of these properties.

Example:
```
category == "PRICE_REVERSION"
```

#### Alpha Properties are listed in the Table:

| Alpha Property | Description | Acceptable Values | Example |
|---|---|---|---|
| category | User-selected category | String: "NONE", "PRICE_REVERSION", "PRICE_MOMENTUM", "VOLUME", "FUNDAMENTAL", "ANALYST", "PRICE_VOLUME", "RELATION", "SENTIMENT" | `category == "NONE"` |
| color | User-selected color | String: "NONE", "RED", "YELLOW", "GREEN", "BLUE", "PURPLE" | `color == "GREEN"` |
| dataset | Datasets used in Alpha | String: "fundamental6", "analyst4", "model26" | `in(datasets, "fundamental6")` |
| decay | Decay setting | Numeric | `decay <= 2` |
| favorite | Favorite status | 1 or 0 (true or false) | `not(favorite)` |
| long_count | IS average count of long instruments | Numeric | `long_count > 600` |
| name | Custom, user-created Alpha name. Must be an exact match. | String | `name == "good_alpha"` |
| neutralization | Neutralization setting | String: "NONE", "MARKET", "SECTOR", "INDUSTRY", "SUBINDUSTRY" | `neutralization == "MARKET"` |
| operator_count | Number of operators in Alpha expression | Numeric | `operator_count < 10` |
| short_count | IS average count of short instruments | Numeric | `short_count > 600` |
| tags | Custom, user-created tags | String | `in(tags, "my_example_tag")` |
| truncation | Truncation setting | Numeric | `truncation <= 0.06` |
| turnover | IS turnover | Numeric | `turnover < 0.30` |
| universe | Universe setting | String: "TOP200", "TOP500", "TOP1000", "TOP2000", "TOP3000" | `universe == "TOP1000"` |
| universe_size(universe) | This is an operator that interprets the universe string as a numeric value | Numeric | `universe_size(universe) >= 2000` |
| datafields | Datafields used in Alpha | String: "returns", "assets", "debt" | `in(datafields, "returns")` |
| dataset_count | Number of unique datasets in an Alpha | Numeric | `dataset_count == 1` |
| self_correlation | Self Correlation of Alphas | Numeric | `self_correlation <= 0.6` |
| prod_correlation | Prod Correlation of Alphas | Numeric | `prod_correlation < 0.5` |
| os_start_date | Out-of-Sample date of Alphas | String: date in YYYY-MM-DD format | `os_start_date > "2020-01-01"` |
| datacategories | Data Categories used in the alpha | analyst, broker, earnings, fundamental, imbalance, insiders, institutions, macro, model, news, option, other, pv, risk, sentiment, shortinterest, socialmedia | `not(in(datacategories, "fundamental"))` |
| datacategory_count | number of unique data categories in an alpha | Numeric | `datacategory_count<5` |
| datafield_count | number of unique data fields in an alpha | Numeric | `datafield_count <2` |
| classifications | Alpha classification | "POWER_POOL", "ATOM" | `in(classifications, "POWER_POOL")` |
| competitions | Competition associated with the alpha | "HCAC2025", "ACE2023" | `in(competitions, "HCAC2025")` |

#### Additional SuperAlpha selection features

| Attribute | Keyword for selection | Description | Acceptable Values |
|---|---|---|---|
| Overall Alphas Yield Rate | author_yield_rate | number of submissions / number of simulations * 10,000 | Numeric |
| Alphas Yield Rate per quarter | author_quarter_yield_rate | number of submissions / number of simulations * 10,000 for the proceeding 90 days | Numeric |
| Age of author | author_tenure | number of days difference from submission date to conditional start date | Numeric |
| Days Active | author_activity | number of distinct submission days / number of days difference from submission date to conditional start date | Numeric |
| Regions Count | author_distinct_count_regions | number of distinct regions | Numeric |
| Author Dataset Categories Count | author_distinct_count_datasetcategory | number of distinct dataset categories | Numeric |
| Author Dataset Count | author_distinct_count_dataset | number of distinct dataset | (Numeric) |
| Datafield Count | author_distinct_count_datafield | number of distinct datafield | Numeric |
| Operator Count | author_distinct_count_operator | number of distinct operator | Numeric |
| Dataset Categories Quarter Count | author_distinct_quarter_count_datasetcategory | number of distinct dataset categories for the proceeding 90 days | Numeric |
| Dataset Quarter Count | author_distinct_quarter_count_dataset | number of distinct dataset for the proceeding 90 days | Numeric |
| Datafield Quarter Count | author_distinct_quarter_count_datafield | number of distinct datafield for the proceeding 90 days | Numeric |
| Operator Quarter Count | author_distinct_quarter_count_operator | number of distinct ts operator for the proceeding 90 days | Numeric |
| Author ProdCorr | author_prod_correlation | mean of prod correlation | Numeric |
| Author SelfCorr | author_self_correlation | mean of self correlation | Numeric |
| Author Sharpe | author_sharpe | mean of Sharpe | Numeric |
| Author TurnOver | author_turnover | mean of turnover | Numeric |
| Author Fitness | author_fitness | mean of fitness | Numeric |
| Author Returns to Drawdown Ratio | author_returns_to_drawdown | mean of returns/drawdown ratio | Numeric |

> Note: The "Example" column for several of the above author_* attributes was visually cut off / truncated in the source PDF (column overflow off the right edge of the page) and could not be fully recovered via OCR.

#### Dataset names are listed in the Table:

| Dataset | Dataset name |
|---|---|
| analyst11 | ESG scores |
| analyst14 | Estimations of Key Fundamentals |
| analyst15 | Earnings forecasts |
| analyst16 | Real Time Estimates |
| analyst17 | A-shares Estimates |
| analyst2 | Analysts Estimates of Key Fundamentals |
| analyst20 | Decision Machine Data |
| analyst21 | Indicators of Interest Data |
| analyst25 | Analyst Estimates Data for Equity |
| analyst27 | Analyst Estimate Daily Data |
| analyst34 | Dividend forecasts model |
| analyst35 | ESG Model |
| analyst4 | Analyst Estimate Data for Equity |
| analyst40 | Information on board of director |
| analyst44 | Broker Estimates |
| analyst6 | Model Rating Data |
| analyst7 | Broker Estimates |
| analyst8 | Analyst Estimate Daily Data |
| analyst9 | Analyst Estimate Daily Data |
| earnings1 | Actuals and Estimates Earnings Data |
| earnings3 | Earnings Date Data |
| earnings4 | Effect of earnings announcement model |
| earnings5 | Earnings Date Breaks |
| earnings7 | Horizon Earnings and Calendar North America |
| fundamental1 | Management and Executive Data |
| fundamental11 | International Fundamental Data |
| fundamental12 | Model Data |
| fundamental13 | Comprehensive Fundamentals Dataset |
| fundamental14 | Audit Analytics Directors Data |
| fundamental17 | Direct Fundamental Data |
| fundamental2 | Report Footnotes |
| fundamental21 | ESG Scores Data |
| fundamental22 | Environmental and Social Governance Data |
| fundamental23 | Fundamental Point in Time Data |
| fundamental25 | Company Operating Metrics |
| fundamental27 | A-shares Fundamental Data |
| fundamental28 | Global Fundamental Data |
| fundamental3 | Fundamentals Data for US Equities |
| fundamental30 | Japan fundamenta data by sectors |
| fundamental31 | Additional Factor Model |
| fundamental44 | Accounting Quality Models |
| fundamental45 | Systematic mining of earnings calls data |
| fundamental5 | China Fundamentals |
| fundamental6 | Company Fundamental Data for Equity |
| fundamental65 | Factor Ratios and its Rank Model |
| fundamental7 | Comprehensive Fundamentals Data |
| insiders1 | Global Insider Trading Data |
| institutions1 | Insider Trading for Europe |
| institutions4 | Institutional Ownership Data |
| institutions5 | Insiders Model |
| institutions6 | Institutions and Beneficial Stake Ownership |
| institutions7 | Ownership Model |
| institutions8 | Insider Model Data |
| macro27 | Job records from job posting |
| macro38 | Technical Ratings Model |
| model10 | Research Indicators |
| model106 | Analysts rating model |
| model109 | Fundamentals and Technical Indicators Model |
| model11 | Revenue Forecast Data |
| model110 | Big data and machine learning based model |
| model113 | ML/AI-Estimates for Research Indicators |
| model115 | ML/AI-Estimates for Earnings Quality |
| model116 | ML/AI-Estimates for Equity Factor Model |
| model117 | NLP on 10K and 10Q Filings Data |
| model119 | Factor Score Data |
| model12 | Stock Selection Model |
| model122 | Factors for A-shares |
| model133 | Risk Parity Method Model |
| model135 | Alternative technical factror models |
| model136 | ETF Based Equity Factors |
| model139 | Inflation based stock selection model |
| model14 | Quant Model Data |
| model140 | Sensitivity to the Inflation Change |
| model141 | Interest Rate Sensitivity Measures |
| model15 | AI Driven Predictive Model |
| model16 | Fundamental Scores |
| model162 | Return prediction from conference call |
| model163 | ML/AI-Estimates for Analysts' Factor Model |
| model165 | Time-series prediction of alpha models |
| model169 | Technical and Fundamental ranking model |
| model17 | Research Analyst Estimate Factors |
| model170 | Technical and Fundamental ranking model |
| model175 | China Fundamentals and Technicals Model |
| model176 | Non-Financial Metric Models |
| model182 | Geographic network based model |
| model194 | North America CDS Factor Model |
| model2 | Brand Popularity Data |
| model20 | Fundamental & Technical Rank Model |
| model21 | Equity Focus Rank Model |
| model210 | NLP Model on Textual Data |
| model211 | Analyst estimate prediction data |
| model22 | Fundamental Focus Rank Model |
| model23 | Scorings Data |
| model25 | Earnings Quality |
| model26 | Analyst Revisions |
| model27 | Credit Risk Model |
| model28 | Structural Credit Risk Model |
| model29 | EBITDA Estimate Model |
| model30 | EPS Estimate Model |
| model31 | Earnings Quality Model |
| model32 | Price Momentum Model |
| model33 | Revenue Estimate Model |
| model36 | SmartRatios Model |
| model37 | Text Mining Data |
| model38 | Growth Valuation Model |
| model39 | Valuation Momentum Data |
| model4 | Fundamentals and Technical Indicators Model |
| model40 | Ranking & Recommendation Data |
| model42 | Equity Ranking Model |
| model43 | Insider Model for the US |
| model44 | Insider Model V2 for the US |
| model46 | Insider Data for the US |
| model47 | Ranking Model |
| model5 | Country-Specific Expectational Model |
| model50 | International Scorings Data |
| model51 | Systematic Risk Metrics |
| model52 | Creditworthiness model |
| model53 | Creditworthiness Risk Measure Model |
| model54 | Technical Indicators |
| model55 | Fundamental Indicators |
| model56 | Stock Reports Plus |
| model57 | Quantitative Stock Valuation Model |
| model58 | Implied Volatility Data |
| model7 | Value & Growth Alpha Model |
| model77 | Analysts' Factor Model |
| model8 | Fundamental Analysis Model |
| model9 | Sell Side Expectational Model |
| news12 | US News Data |
| news17 | PR Edition Data |
| news18 | Ravenpack News Data |
| news20 | Web Sources News Sentiment Data |
| news21 | Macro Economic Event Data |
| news22 | News Direct-feed Data |
| news23 | MnA Deals Data |
| news29 | Significant Developments Data |
| news3 | Dow Jones News Analytics Data |
| news31 | News Analytics on Equities |
| news42 | US/AMR news data |
| news5 | News Feed Analytics Data |
| news52 | Conference call data |
| news54 | Newa analystic data |
| news7 | Real Time News Feed Data |
| news8 | Dow Jones Press Release Data |
| news87 | Smart Conference call transcript data |
| news92 | Standardized Financial News Categorization |
| option1 | Options Volatility Surfaces Data |
| option11 | Equity Option Ratings Data |
| option14 | Implied Volatility Data for Europe |
| option4 | Implied Volatility and Pricing for Equity Options |
| option6 | Forecasted Volatility for Equity Options |
| option8 | Volatility Data |
| option9 | Options Analytics |
| other1 | Estimates for China A-Shares |
| other127 | Equity Ranking Model |
| other131 | Conviction based hedge funds selections |
| other137 | Systematic Insider Alpha Strategy |
| other143 | Transaction Volume Data for Equity |
| other15 | ETF Constituents |
| other160 | NLP on media data |
| other17 | Flow into Equities Data |
| other176 | Nonlinear adaptive model |
| other193 | Systematic Hedging for Investors to Evade Large Drawdowns |
| other238 | Event based sentiment and behavioral factors model |
| other32 | Europe Stock Pick Data |
| other326 | Intermediate Data from Events |
| other327 | Sensitivity to Interest Rates Model |
| other33 | Qualitative Alpha Model Data |
| other349 | Patent Indicators |
| other351 | International sentiment analysis NLP model |
| other376 | Aggregated Transaction Data |
| other378 | Accounting governance indicator models |
| other384 | NLP on conference conversation |
| other401 | Governance, Accounting, Management, and Equality |
| other407 | Factors Dislocations Data |
| other41 | A-Share Alpha Model |
| other411 | Linear, nonlinear, and region-specific models |
| other416 | Quantitative Filings Data |
| other419 | Analyst Estimate Daily Data |
| other42 | A-Share Index Research Data |
| other423 | Fundamental Income and Dividend Model |
| other424 | Dividend prediction model |
| other425 | Supply Chain Data |
| other427 | Quantify text part in financial reports data |
| other429 | Sentiment Data by NLP |
| other432 | DNN prediction of fundamentals |
| other434 | Credit Risk Factors |
| other455 | Relationship enhanced with AI/ML |
| other461 | Models for A-shares |
| other47 | Web Intelligence Data |
| other479 | China Classification data |
| other486 | Earnings Predictions Data |
| other492 | Stock Events Data |
| other510 | 8-K based NLP model |
| other54 | Quantitative Stock Selection Data |
| other62 | Job postings Data |
| other65 | Talent Risk Data |
| other7 | Archive News Data |
| other72 | Combined Alpha Model |
| other74 | AI/ML Web Based Mention Data |
| other76 | Employee Benefit Plan Data |
| other78 | Earnings and conference call data |
| other83 | Insider Transaction Analytics |
| other84 | Upcoming Earnings Data |
| other85 | China Flow Data |
| pv1 | Price Volume Data for Equity |
| pv103 | Interval and MOO&MOC statistics |
| pv113 | Economic MacroIndicator Data |
| pv13 | Relationship Data for Equity |
| pv24 | A-shares EDM Data |
| pv25 | A-shares Index Data |
| pv27 | A-shares Trade Data |
| pv28 | Price Volatility Predictions Data |
| pv29 | Derived Industry Classification |
| pv3 | Global Daily Pricing Data |
| pv30 | Alternate Industry Classification |
| pv7 | Relation data from Form 10-K and 20-F |
| risk64 | Fundamentals related Risk Factors |
| risk69 | Classification based on Business description |
| sentiment1 | Research Sentiment Data |
| shortinterest2 | Short Interest Model |
| shortinterest3 | Securities Lending Files Data |
| shortinterest6 | SmartHoldings Model |
| shortinterest7 | Short Selling Model |
| socialmedia12 | Sentiment Data for Equity |
| socialmedia15 | Sentiment Indicators |
| socialmedia3 | Twitter based sentiment data |
| socialmedia4 | Brands and Social Media Data |
| socialmedia5 | Lexical Breakdown Data |
| socialmedia7 | Activity Feed Data |
| socialmedia8 | Social Media Data for Equity |

### Available Operators

Selection expressions can use many of the same operators as Alpha expressions. A full list of available operators is available at Appendix: SuperAlpha Operators.

### Example Selection Expressions

| Settings | Selection Expression | Description |
|---|---|---|
| Selection Handling = "Positive", Selection Limit = 30 | `turnover` | This expression will return the 30 Alphas with the highest turnover. If there are fewer than 30 Alphas, then all Alphas will be selected. |
| Selection Handling = "Positive", Selection Limit = 20 | `long_count / sqrt(universe_size(universe)) * (turnover < 0.2)` | This expression will exclude all Alphas with turnover >= 0.2. Of those remaining Alphas with turnover < 0.2, the expression will select the 20 Alphas with the highest selection weight. If there are fewer than 20 Alphas with turnover < 0.2, then all of those Alphas will be selected. |
| Selection Handling = "Non-Zero", Selection Limit = 20 | `-turnover * (neutralization == "SUBINDUSTRY")` | This expression will only select alphas with Subindustry neutralization. Of those alphas with Subindustry neutralization, the expression will select the 20 alphas with the lowest turnover. Note that the Selection Handling must be set to "Non-Zero" for this expression to select the desired alphas. Selection Handling = "Positive" would not select any alphas, since all selection weight values are zero or negative. Selection Handling = "Non-NaN" will include alphas with all neutralization types because the selection weight for these alphas will be zero, which is included. |
| Selection Handling = "Non-Zero", Selection Limit = 10 | `(in(datasets, "analyst6") \|\| color == "RED") * (long_count-short_count)` | This expression will only select alphas that use the analyst6 dataset, or which are designated with the color red. Of those alphas, the expression will select 10 alphas for which long_count-short_count) evaluates to the largest values. Note that this expression will include alphas for which (long_count-short_count) evaluates to a negative number. To exclude negative numbers, use Selection Handling = "Positive". |
| Selection Handling = "Non-NaN", Selection Limit = 20 | `x = if_else(category == "PRICE_MOMENTUM", 2, 1); y = if_else(category == "PRICE_REVERSION", 0.5, 1); z = (long_count * x * y - short_count); if_else(turnover > 0.2, nan, z)` | This expression will only select Alphas with turnover <= 0.2. Of those Alphas with turnover <= 0.2, the expression will select the 20 Alphas for which (long_count - short_count) evaluates to the largest values, where the long_count value of Price Momentum Alphas is multiplied by 2 and the long_count value of Price Reversion Alphas is multiplied by 0.5. Note that Selection Handling is set to "Non-NaN", which means it will include Alphas for which (long_count * x * y <= short_count). |

---

## Combo Expression

*Prev: Selection Expression | Next: SuperAlpha Results*

### Table of Contents (in-page)
1. Combo Expression
2. How it Works
3. Operator generate_stats()
4. Available operators
5. SuperAlpha Combo Settings
6. Examples

### Combo Expression

The combo expression combines the selected Alphas together into one Alpha – a SuperAlpha. The output of the combo expression is a set of daily weights for each of the selected Alphas.

(UI: a "Combo Expression" code editor.)

### How it Works

The combo expression works by weighting each selected Alpha each day. Similar to how an Alpha expression is evaluated for each instrument each day, the combo expression is evaluated for each of your Alphas each day.

Typically, combo expressions take the set of selected Alphas as input. The data from the selected Alphas is held in a matrix with shape = (A x D x I), where:

- **A** is the number of selected Alphas
- **D** is the number of days
- **I** is the number of instruments in the universe

The output of the combo expression is a set of weights for each selected Alpha each day, held in a matrix with shape = (D x A). These weights determine how the scaled output of each Alpha is combined together to yield a SuperAlpha.

**Diagram description:**
- INPUT: a 3-D matrix block labeled with axes INSTRUMENTS, DAYS, ALPHAS (shape A x D x I) → passed through **Combo expression** →
- OUTPUT: a 2-D matrix with axes DAYS (rows) x ALPHAS (columns), e.g.:

| | Alpha 1 | Alpha 2 | Alpha 3 |
|---|---|---|---|
| Day 1 | 0.2 | 0.4 | 0.4 |
| Day 2 | 0.3 | 0.1 | 0.6 |
| Day 3 | 0.5 | 0.4 | 0.1 |

- Combo expressions take the set of selected Alphas as input
- The data from the selected Alphas is held in a matrix
- The output of the combo expression is a set of weights for each selected Alpha each day, held in a matrix with shape = (D x A)
- These weights determine how the scaled output of each Alpha is combined together to yield a SuperAlpha

### Operator generate_stats()

```
1  stats = generate_stats(alpha);
2  ts_ir(stats.returns, 250)
```

The generate_stats() operator calculates Alpha statistics for each day in the IS period. It takes an input of selected Alphas with shape = (A x D x I). It outputs daily statistics for each Alpha with shape = (S x D x A), where S is the number of statistics calculated.

**Diagram description:** INPUT matrix (INSTRUMENTS x DAYS x ALPHAS) → **generate_stats(alpha)** → OUTPUT matrix (INSTRUMENTS x DAYS x STATS), restated as:
- Combo expressions take the set of selected Alphas as input
- The data from the selected Alphas is held in a matrix
- The output of the combo expression is a set of stats for each selected Alpha each day, held in a matrix with shape = (S X D x A)

#### Alpha Statistics

The generate_stats() operator calculates the following daily statistics for each Alpha:

| Alpha Statistic | Description |
|---|---|
| drawdown | % difference between current cumulative PnL and maximum PnL since beginning of simulation |
| hold_pnl | PnL of shares that did not trade |
| hold_shares | Count of shares that did not trade |
| hold_value | Sum of value of shares that did not trade |
| long_count | Number of instruments with positive weight |
| long_value | Sum of positive weight |
| pnl | Net profit or loss |
| returns | PnL as percent of book size |
| short_count | Number of instruments with negative weight |
| short_value | Sum of absolute value of negative weight |
| trade_pnl | PnL of shares that did trade |
| trade_shares | Count of shares that did trade |
| trade_value | Sum of value of shares that did trade |
| turnover | Value traded as percent of book size |

### Available operators

Combo expressions can use most of the same operators as Alpha expressions. A full list of available operators is available at Appendix: SuperAlpha Operators.

### SuperAlpha Combo Settings

The lower section of the SuperAlpha settings menu applies to the combo expression and the resulting SuperAlpha.

**Combo settings panel (example values):**

| Field | Example Value |
|---|---|
| UNIVERSE | TOP3000 |
| NEUTRALIZATION | Industry |
| DECAY | 2 |
| TRUNCATION | 0.08 |
| PASTEURIZATION | On |
| UNIT HANDLING | Verify |
| NAN HANDLING | Off |

#### Universe

The selected universe setting is applied to all selected Alphas when the SuperAlpha is simulated, regardless of the original universe of those Alphas. The resulting SuperAlpha is based upon this universe.

#### Neutralization

The selected neutralization is applied to the final weighted combination of selected Alphas.

#### Decay

The decay setting applies the ts_decay() operator to the final weighted combination of selected Alphas, where the decay value is the number of lookback days. This is useful for reducing turnover, but larger values can attenuate the signal.

#### Truncation

The selected truncation is applied to the final weighted combination of selected Alphas. This is useful to reducing overfitting.

#### Pasteurization

Replaces operator input values with NaN for instruments not in the universe. Original Alpha pasteurization settings are preserved. The combo pasteurization setting applies to operators used in the combo expression.

#### NaN Handling

Allows aggregation operators to output numeric values when input values are NaN for a given instrument and date. Original Alpha NaN Handling settings are preserved. The combo NaN Handling setting applies to operators used in the combo expression.

#### Test Period

The Test Period setting offers you the flexibility to designate a separate testing period for your SuperAlpha. This period corresponds to the final 0-6 years of the In-Sample (IS) period, providing a distinct timeframe for assessing your SuperAlpha's performance before submission.

### Examples

| Combo Expression | Description |
|---|---|
| `1` | This expression evaluates to 1 for every Alpha every day. It will weight each selected Alpha equally every day. |
| `stats = generate_stats(alpha); ts_ir(stats.returns, 250)` | This expression weights each Alpha by its information ratio from the previous 250 trading days (~1 year). |
| `stats = generate_stats(alpha); innerCorr = self_corr(stats.returns, 500); ic = if_else(innerCorr == 1.0, nan, innerCorr); maxCorr = reduce_max(ic); 1 - maxCorr` | This expression weights each Alpha by the maximum correlation with all other selected Alphas over a 2 year period, with more correlated Alphas receiving less weight. |

---

## SuperAlpha Results

*Prev: Combo Expression | Next: Helpful Tips*

### Table of Contents (in-page)
1. SuperAlpha Results
2. Properties

### SuperAlpha Results

SuperAlpha results have some new features to help understand the details and performance of your SuperAlphas.

**"Selected Alphas" example panel:**

α Selected Alphas — **10 Alphas have been selected** — *View all*

| Name | Universe | Sharpe | Turnover | Fitness | Returns | Margin |
|---|---|---|---|---|---|---|
| anonymous | TOP3000 | 2.44 | 63.64% | 1.03 | 11.39% | 3.58‰ |
| anonymous | TOP3000 | 3.35 | 50.70% | 1.61 | 11.70% | 4.62‰ |
| anonymous | TOP3000 | 1.33 | 5.01% | 1.24 | 4.33% | 17.31‰ |
| anonymous | TOP3000 | 1.47 | 2.15% | 1.95 | 3.80% | 35.26‰ |
| anonymous | TOP3000 | 1.79 | 13.25% | 1.62 | 10.89% | 16.44‰ |

The selected Alphas section displays the list of Alphas included in the SuperAlpha. This information is displayed after clicking the "Run Selection" button prior to simulating the SuperAlpha, and it is also displayed as part of the SuperAlpha simulation results after simulation has completed. The top 10 selected values, ordered by the selection expression, are shown in the table. The total number of Alphas selected is noted at the top of the Selected Alphas section. You can view all of the selected Alphas by clicking the "View All" link at the top, right corner of the Selected Alphas section.

**PnL Chart example:**

N Chart [dropdown: PnL]

Tooltip example shown on chart: `03/08/2010 — IS Combo PnL: 2,891.04K — Equal Weight PnL: 2,816.57K`

Legend: — Equal Weight PnL  — Combo PnL

The PnL chart shown in SuperAlpha simulation results shows two PnL lines. The blue line is the performance of your SuperAlpha; the gray line is the performance of the same set of Alphas combined with a simple, equal-weight combo. An equal weight combo can be recreated by entering a constant as the combo expression, e.g., "1". The equal-weight combo is simple but effective, and your combo should strive to improve upon the performance of the equal-weight combo. Note that returns are not the only important measure of a good SuperAlpha.

### Properties

SuperAlpha properties are similar to Alpha properties, except that SuperAlphas have two description fields. One description field is for the selection expression, and the other description field is for the combo expression. Both of these description fields are required in order to submit a SuperAlpha.

**Properties form fields:**
- Description of Selection Expression* — *(0 / 100 character minimum)* — placeholder text: "Notes"
- Description of Combo Expression* — *(0 / 100 character minimum)* — placeholder text: "Notes"

---

## Helpful Tips

*Prev: SuperAlpha Results | Next: SuperAlpha Operators*

### Table of Contents (in-page)
1. Use Alpha Properties
2. Test First
3. Compare to Benchmarks

### Use Alpha Properties

The best SuperAlphas are made with a robust analytical approach that incorporates your personal knowledge of the selected Alphas. Before you start researching SuperAlphas, it may be helpful to fill in the Alpha properties for each Alpha. Consider assigning a category, color, and/or custom tags to each Alpha so you can easily select them with your selection expression. For example, you can select all the Alphas which have been tagged using the selection expression `in(tags, "my_example_tag")`. Think about what tags would be most useful for grouping your Alphas. Note that each Alpha can have multiple tags.

### Test First

SuperAlphas are computationally complex, and as such they can take a long time to simulate. Each person is allowed three concurrent simulations. Before you simulate a large SuperAlpha, try testing out the selection and combo expressions first. To test the selection expression, you can click on the "Run Selection" button and see the complete list of Alphas which will be included in your SuperAlpha. This takes only a few seconds, and can help you avoid a long simulations with the wrong Alphas. To test the combo expression, try setting the "Selection Limit" setting to a small number such as the minimum value, 10. Smaller SuperAlpha simulations will run much faster, allowing you to test your ideas more quickly. Once you are confident about your selection and combo expressions, then choose a larger set of Alphas to simulate.

### Compare to Benchmarks

SuperAlphas tend to perform much better than Alphas, so using Alpha performance as a benchmark may not be helpful for developing good SuperAlphas. To help with this, the PnL chart shown in SuperAlpha simulation results shows two lines. The blue line is the performance of your SuperAlpha; the gray line is the performance of the same set of Alphas combined with a simple, equal-weight combo. An equal weight combo can be recreated by entering a constant as the combo expression. Generally, a good combo expression should outperform the equal-weight combo, but keep in mind that returns are not the only important measure of performance. You may also want to create and track your own benchmarks as you research SuperAlphas.

**Process diagram description:**

`1. IDEA` —[selection]→ `2. Raw SuperAlpha` —[combo=1]→ `3. Position` —[stats]→ `4. PnL` —[analyze]→ `5. Performance (IR, tvr, ret...)` —[revise]→ back to `1. IDEA`

---

## SuperAlpha Operators (Appendix)

*Prev: Helpful Tips | Next: Global SuperAlphas*

### Table of Contents (in-page)
1. List of operators
2. Descriptions

### List of operators

SuperAlpha selection and combo expressions use most of the same operators as Alpha expressions. Here is a complete list of supported operators.

| Operator | Selection | Combo |
|---|---|---|
| abs | x | x |
| add | x | x |
| and | x | x |
| arc_cos | x | x |
| arc_sin | x | x |
| arc_tan | x | x |
| bucket | - | x |
| ceiling | x | x |
| clamp | x | x |
| combo_weight | - | x |
| convert | - | x |
| count | - | x |
| days_from_last_change | - | x |
| densify | - | x |
| divide | x | x |
| equal | x | x |
| exp | x | x |
| filter | - | x |
| floor | x | x |
| frac | x | x |
| generate_stats | - | x |
| greater | x | x |
| group_backfill | - | x |
| group_count | - | x |
| group_extra | - | x |
| group_max | - | x |
| group_mean | - | x |
| group_median | - | x |
| group_min | - | x |
| group_neutralize | - | x |
| group_normalize | - | x |
| group_percentage | - | x |
| group_rank | - | x |
| group_scale | - | x |
| group_std_dev | - | x |
| group_sum | - | x |
| group_vector_neut | - | x |
| group_vector_proj | - | x |
| group_zscore | - | x |
| hump | - | x |
| hump_decay | - | x |
| if_else | x | x |
| inst_pnl | - | x |
| inst_tvr | - | x |
| inverse | x | x |
| is_finite | x | x |
| is_nan | x | x |
| is_not_finite | x | x |
| is_not_nan | x | x |
| jump_decay | - | x |
| keep | - | x |
| kth_element | - | x |
| last_diff_value | - | x |
| left_tail | - | x |
| less | x | x |
| log | x | x |
| log_diff | - | x |
| max | x | x |
| min | x | x |
| multiply | x | x |
| nan_mask | x | x |
| nan_out | x | x |
| negate | x | x |
| normalize | - | x |
| not | x | x |
| one_side | - | x |
| or | x | x |
| pasteurize | - | x |
| position_safeguard | - | x |
| power | x | x |
| purify | x | x |
| quantile | - | x |
| rank | - | x |
| rank_by_side | - | x |
| rank_gmean_amean_diff | - | x |
| reduce_avg, reduce_choose, reduce_count, reduce_ir, reduce_kurtosis, reduce_max, reduce_min, reduce_norm, reduce_percentage, reduce_powersum, reduce_range, reduce_skewness, reduce_stddev, reduce_sum | - | x |
| regression_neut | - | x |
| regression_proj | - | x |
| replace | - | x |
| reverse | x | x |
| right_tail | - | x |
| round | x | x |
| round_down | - | x |
| s_log_1p | x | x |
| scale | - | x |
| scale_down | - | x |
| self_corr | - | x |
| sigmoid | x | x |
| sign | x | x |
| signed_power | x | x |
| sqrt | x | x |
| subtract | x | x |
| tail | - | x |
| tanh | x | x |
| to_nan | x | x |
| trade_when | - | x |
| truncate | - | x |
| ts_arg_max | - | x |
| ts_arg_min | - | x |
| ts_av_diff | - | x |
| ts_backfill | - | x |
| ts_co_kurtosis | - | x |
| ts_co_skewness | - | x |
| ts_corr | - | x |
| ts_count_nans | - | x |
| ts_covariance | - | x |
| ts_decay_exp_window | - | x |
| ts_decay_linear | - | x |
| ts_delay | - | x |
| ts_delta | - | x |
| ts_entropy | - | x |
| ts_ir | - | x |
| ts_kurtosis | - | x |
| ts_max | - | x |
| ts_max_diff | - | x |
| ts_mean | - | x |
| ts_median | - | x |
| ts_min | - | x |
| ts_min_diff | - | x |
| ts_min_max_cps | - | x |
| ts_min_max_diff | - | x |
| ts_moment | - | x |
| ts_partial_corr | - | x |
| ts_percentage | - | x |
| ts_poly_regression | - | x |
| ts_product | - | x |
| ts_quantile | - | x |
| ts_rank | - | x |
| ts_rank_gmean_amean_diff | - | x |
| ts_regression | - | x |
| ts_returns | - | x |
| ts_scale | - | x |
| ts_skewness | - | x |
| ts_std_dev | - | x |
| ts_step | - | x |
| ts_sum | - | x |
| ts_theilsen | - | x |
| ts_triple_corr | - | x |
| ts_vector_neut | - | x |
| ts_vector_proj | - | x |
| ts_weighted_decay | - | x |
| ts_zscore | - | x |
| unit | - | x |
| universe_size | x | - |
| vector_neut | - | x |
| vector_proj | - | x |
| winsorize | - | x |
| zscore | - | x |

> Note: **universe_size** operator interprets a universe string as a numeric value.

### Descriptions

Here are some descriptions:

**self_corr:** Taking an input matrix of (D x N) with lookback="K", producing an output matrix of (D x N x N), where each output(di, j, k) refers to correlation of input(di-K:di, j) and input(di-K:di, k).
Outputs (D x N x N) from the input of (D x N)

**reduce:**

- Takes an input 2-D or 3-D matrix with user-defined reducer, producing an output matrix.
- If input matrix is (D x N), output matrix (D x 1)
- If input matrix is (D x N X N), output matrix (D x N X 1)
- The defined function is applied on the last dimension : output(I) = reduce(input(I, 0:N)).

| Method | Threshold | Description |
|---|---|---|
| reduce_count | threshold=<float> | Count the number of element of d(..., :) > threshold |
| reduce_norm | | Absolute sum of number of element of d(..., :) |
| reduce_sum | | Sum the number of element of d(..., :) |
| reduce_max | | Maximum of elements of d(..., :) |
| reduce_min | | Minimum of elements of d(..., :) |
| reduce_avg | Minimum required number of valid (non-nan) values. If there is not enough valid values, then the output is nan. 0 means no limit. threshold (Default: 0) | Average of non-NAN elements of d(..., :) |
| reduce_choose | nth="<the Nth element>" (Required); ignoreNan="true\|false" (Default: true) | Choose the 'nth' element in the array, return NAN if not found |
| reduce_range | | Return the range of values in the array, return NAN if no valid value |
| reduce_percentage | percentage="<value between 0 and 1>" (Default: 0.5) | Return the value of percentage in the sorted array: e.g., median value when percentage=0.5 |
| reduce_stddev | Minimum required percentage of valid (non-nan) values. If there is not enough valid values, then the output is NAN. 0 means no limit. threshold (Default: 0) | Standard deviation of values in the array |
| reduce_ir | | IR of values in the array |
| reduce_skewness | | Skewness of values in the array |
| reduce_kurtosis | | Kurtosis of values in the array |
| reduce_powersum | precise, whether calculate power precise if constant greater than 4, default false; constant=<integer value>, default:2 | sum of power, sum(power(x, constant)) |

> Note: **d** represents an input 2-D or 3-D matrix

---

## Global SuperAlphas

*Prev: SuperAlpha Operators | Next: (none)*

Creating Global (GLB) SuperAlphas requires careful consideration, including neutralization, component Alpha selection, and simulation settings.

### Neutralization

Neutralize your SuperAlpha to **COUNTRY** to account for differences across countries in the global region.

This ensures fair comparisons and avoids biases caused by regional disparities.

Neutralization to country helps align signals across diverse regions.

### Universe selection

The MINVOL1M GLB universe contains over 9,000 instruments, which can make simulations slower.

To speed up simulations, test your SuperAlpha on the **TOP3000** universe.

Once optimized, simulate and submit your SuperAlpha on the **MINVOL1M** universe.

### Selection Expression

Select Alphas that are neutralized to country using the following methods:

- Select Alphas neutralized in expression: `in(datafields, 'country')`
- Select Alphas neutralized in settings: `neutralization == 'COUNTRY'`

Choose Alphas with 1-2 years of OS data to ensure reliability:

- Use the selection expression: `os_start_date <= '2022-01-23'`

Combine multiple selections using the OR operator to diversify your component Alphas and improve overall performance.

This allows you to include a broader range of signals in your SuperAlpha.

### Combo Expression

Use the **combo_a** operator to combine Alphas effectively.

This operator performs better when the selected Alphas are different.

Avoid selecting overly similar Alphas to maximize the effectiveness of the combo.

### Simulation settings

Enable the **Max Trade** setting during simulation, especially on the MINVOL1M universe.

This ensures your SuperAlpha meets liquidity and scalability requirements.

It validates that your SuperAlpha can handle real-world constraints.

### Tips for Success

- **Diversify selection**: Use multiple selection expressions to ensure a broad range of Alphas in your SuperAlpha.
- **Focus on liquidity**: Simulating on the **TOP3000** universe speeds up testing, while submitting on **MINVOL1M** ensures scalability. Additionally, check **Investability constrained metrics** of your SuperAlpha.
- **Test OS performance**: Prioritize Alphas with sufficient OS data to avoid overfitting and ensure robust performance.

### More concepts that you can explore

- What is a SuperAlpha?
- SuperAlpha Selection Expression
- SuperAlpha Combo Expression
- SuperAlpha Helpful Tips
- Getting Started: Global Alphas

---

*End of document.*
