# Schneider Electric – Problem 1: Raw-Material Price Risk on Fixed-Term Offers

**Business question**
> When we quote an RM6 / RM AirSeT unit today at a fixed price valid for H = 3, 6 or 9 months, what price (or margin buffer) keeps the margin above the target with a chosen level of confidence?

**Guiding principle:** The goal is to **quantify cost uncertainty per horizon** and turn it into a **pricing decision** that sales can use.

**General Guidelines**:
- Do not push directly to main, always push to a branch and then open a pull request.
- Do not commit or push the data
- For each part make a brief report on what was done and its results in report/

**What the data tells us up front**
- The two products have **different risk drivers**. The RM6 bill of materials (BOM) includes copper (12.5 % of mass, ≈ 39 kg). The RM AirSeT BOM is ≈ 68 % carbon + stainless steel and **lists no copper**. Rough value check (mass × €/t): copper ≈ 60 % of RM6's priceable raw material; steel ≈ 85 % of AirSeT's.
- History is short: **119 monthly points (Nov 2016 → Sep 2026)**. For H = 9 that is only ≈ 13 non-overlapping windows. Simple, well-calibrated methods matter more than complex models.

---

## Step 0 – Frame the decision and align with the client

- Write down the target margin, the confidence level the business is comfortable with (e.g., P80 vs P95), and the decision the model supports (a buffer, an indexation clause, hedging).
- **Before asking the client, read what the data already answers.** The `Reference to Index Mapping`, `Q4-2017`, `Q2-2018` and `UPDATE` sheets of `Copia de Europe Steel INDEXES.xlsx` appear to link Schneider steel supply contracts (by plant and supplier, including the Hungarian plant) to MEPS/CRU indices, with update frequencies. This is direct evidence on **purchase timing and supplier indexation**.
- Open questions for Schneider / the case contact:
  - **Unprotected copy of `RMU_IQI_EU_Price_Benchmark_2017-2026_Synthetic.xlsx`.** The file is DRM-encrypted (Microsoft sensitivity label) and cannot be opened. It probably holds the selling-price series needed for the margin backtest (Step 9).
  - Target margin for RM6 vs RM AirSeT (how much thinner is AirSeT's?).
  - Do customer contracts already have **escalation / indexation clauses**? Does Schneider **hedge** metals?
  - **Lag between contract signature and material purchase.** A 9-month contract with purchases at month 2 has a 2-month exposure, not 9.
  - **BOM gaps:** RM6's labelled materials cover only 40.7 % of mass (largest unlabelled slice ≈ 45 %, "probably carbon steel"). AirSeT has unlabelled slices too. Does AirSeT really contain no copper (busbars, contacts)? Where does its epoxy solid insulation sit in the BOM?

**Output:** a one-paragraph problem statement + a list of assumptions + a list of questions sent to the client.

---

## Step 1 – Data inventory and preparation

### 1.1 Inventory (what we have, and what it is for)

| File | Content | Use in Problem 1 |
|---|---|---|
| `data.zip → rm_prices_monthly_wide.csv` | 15 free series, monthly, Nov 2016 → Sep 2026 (FX to Oct 2026): LME Cu, Al, Ni, Zn, iron ore (USD/t), EUR/USD, EU/DE/US producer price indices (PPIs) for copper, aluminium, steel, plastics; D01/D02 = Cu/Al in EUR/t. L01–L08 are empty. | Main modelling panel |
| `data.zip → energy_prices_monthly_wide.csv` | 30 energy series (Brent, TTF gas, power prices for DE / **FR (RM6 plant)** / **HU (AirSeT plant)**, energy PPIs, Russia import share) | Leading indicators (README: Brent → plastics PPI, 1-month lead, corr 0.61; TTF → aluminium and steel PPIs) |
| `data.zip → bom_materials.csv` | Schneider-internal BOM: share of mass and kg per material, plus mapping to price series | Cost weights (Step 2) |
| `Copia de Europe Steel INDEXES.xlsx` | **Actual MEPS / CRU steel prices in EUR/t**: flat products by country (from 2012), stainless 304/430/316 base + alloy surcharge (from 2008), long products (from 1997) + supplier → index mapping | **Real €/t steel levels** (replaces empty L01–L03); longer steel history; purchase-indexation evidence |
| `LME_Copper_Aluminium_EU_Monthly_2016_2026.xlsx` | LME Cu/Al cash **and 3-month forward**, in USD and EUR, LME stocks, Jan 2016 → Nov 2026 (Nov provisional) | €/t levels; 3-month futures baseline; stocks feature; nowcast of the latest month |
| `Epoxy for student.xlsx` | Epoxy resin €/t and its inputs (benzene, acetone, epichlorohydrin, other costs), Jan 2018 → Oct 2026 | Price of AirSeT solid insulation; better than the generic plastics PPI |
| `benchmark-…rm6-ne-iqi….xlsx` (+ PDF) | Teardown BOM and **should-cost** of RM6 and 5 competitors: RM6 ≈ €3,009 total = €2,404 material + €21 process + €31 labour + €553 overhead | Fixed vs variable cost split; second BOM to cross-check the internal one |
| `RMU_IQI_EU_Price_Benchmark_…_Synthetic.xlsx` | **DRM-encrypted, unreadable** | Selling prices → margin backtest (pending client) |
| `Supplier_balancesheet.zip` | Supplier financials (PitchBook) | Not used in Problem 1 |

### 1.2 Preparation
- **Extend history where possible.** The fetch scripts go back to the 1990s with a one-line change (README §9). CRU long-product steel goes back to 1997, stainless to 2008. Longer history, including 2008–09, does more for tail estimates than any model choice.
- **Units and currencies:** convert all USD prices with S06 (`EUR = USD / S06`); rebase indices (Eurostat 2021 = 100, BLS 1982 = 100) or work in growth rates only.
- **Align dates:** MEPS/CRU and epoxy use mid-month or odd dates (e.g. `2026-08-03`); snap them to month-start.
- **Missing values / imputation:** the last month (Oct 2026) is missing for most series. Nowcast it from the LME file (has Oct and provisional Nov) and FX. Document every imputation.
- **Publication lags and revisions:** IMF/Eurostat/BLS series arrive 1–2 months late and Eurostat/BLS revise recent months. Build a **vintage-aware panel**: at quote date *t*, only data up to *t − lag* is known.
- Clean the MEPS/CRU sheets (multi-row headers, ▲ change sheets are derived; keep only level sheets).

**Output:** data dictionary + one cleaned, aligned monthly panel (one row per month, one column per series, in EUR where possible) + a publication-lag table per series.

---

## Step 2 – Cost decomposition model

Express the cost of one unit as:

```
UnitCost(t) = FixedCost + Σ_i  m_i × Price_i(t) / 1000
```

- `m_i` = mass (kg) of material *i* per unit from `bom_materials.csv`; `Price_i` in **EUR/t**. **Weights are in euros, not mass %**: 39 kg of copper weighs as much in cost as several hundred kg of carbon steel.
- **Price series per material** (preferred first):

| BOM material | €/t level | Monthly dynamics / longer history |
|---|---|---|
| Carbon steel (CR coil) | MEPS/CRU flat CR (Germany / France) | S09, iron ore S04 |
| Stainless 304L | CRU stainless 304 base + alloy surcharge | S09, nickel S03 |
| Galvanised steel (HDG Germany) | MEPS/CRU HDG Germany | S10, zinc S05 |
| Copper (RM6) | LME Cu in EUR (D01) | S01, S07 |
| Aluminium | LME Al in EUR (D02) | S02, S08 |
| PBT / PET / ETP | No €/t level → assume a level (state it), move it with S11 | S11, S13, Brent |
| Epoxy (AirSeT solid insulation, RM6 insulators) | `Epoxy for student.xlsx` | Brent, benzene |

- **FixedCost and non-commodity material:** use the RM6 should-cost (≈ €3,009, of which ≈ €2,404 material) to separate raw-material value from purchased components, labour and overhead. The commodity share of total cost drives the size of the buffer. No should-cost exists for AirSeT: assume it, scaled from RM6 and the "higher cost structure" in the brief.
- **BOM scenarios (essential, not optional):**
  - RM6: the unlabelled ≈ 45 % slice treated as carbon steel (base) vs other; copper 38.8 kg (internal BOM) vs 8.6 kg (teardown BOM). The two sources disagree; show both.
  - AirSeT: no copper (BOM as given) vs a "copper busbar" scenario; add epoxy for the solid insulation.
- Do this **separately for RM6 (France) and RM AirSeT (Hungary)**.

**Output:** a transparent cost formula per product, the € share of cost exposed to each material, and a scenario table (low / base / high).

---

## Step 3 – Exploratory Data Analysis (EDA)

### 3.1 Univariate analysis (per series)
- Plot price levels and **log-returns** over time; mark the regimes in the data: COVID dip (2020), post-COVID surge (2021), Russia–Ukraine energy shock and nickel squeeze (2022), 2025–26 copper rally (record ≈ 14,470 USD/t in Sep 2026).
- Summary stats of returns: mean, volatility, skewness, **kurtosis**.
- **Distribution of H-month changes** for H = 3, 6, 9: histograms and quantiles (5 %, 50 %, 95 %). This is the first naive cost-at-risk estimate.
- **PPI vs market price:** compare the volatility of S07 (copper PPI) vs D01 (LME copper) and S09 vs MEPS/CRU steel. PPIs are smoothed contract prices; if they look calmer, decide which better reflects Schneider's purchase prices.
- Volatility clustering: rolling 12-month volatility, ACF of squared returns.
- Stationarity tests (ADF, KPSS) on levels vs returns. Skip STL seasonality except for energy-linked series; Eurostat PPIs are not seasonally adjusted, so check them quickly.

### 3.2 Multivariate analysis
- Correlation matrix of returns, overall and in stress periods (2021–22).
- Lead–lag: **energy → materials** (Brent → plastics / epoxy, TTF gas and power → aluminium and steel), nickel → stainless, LME → EU PPIs, iron ore → EU steel.
- Skip cointegration / VECM: too few observations for reliable results.

### 3.3 Business-oriented EDA
- Using the Step 2 formula: **historical unit cost series** per product and its H-month changes.
- **Risk decomposition:** which material explains most of the unit-cost variance? Expected: copper for RM6, steel / nickel for AirSeT. Check it.
- **Historical "margin gamble" simulation:** if a contract had been signed at each past month at a fixed price (cost + target margin), how much margin would have been lost / gained at 3, 6, 9 months? How often would the target have been breached? (Use real selling prices if the encrypted file is released.)

**Output:** EDA notebook + 4–6 key charts (price history with regimes, H-month change distributions, correlation heatmap, cost breakdown and risk contribution by product, historical margin erosion).

---

## Step 4 – Feature engineering (kept small on purpose)

With ≈ 120 monthly points, keep **5–10 features per model**. Build each at forecast origin *t* using **only data published by t** (Step 1 lag table).

### 4.1 Target
- `y_{t,H} = log(P_{t+H}) − log(P_t)` for H = 3, 6, 9, for each material series and for the unit cost per product.
- Direct multi-horizon (one model per horizon). Because the last known value is usually *t − 1* or *t − 2*, the effective horizon is H + lag: model it that way.

### 4.2 Price features
- Lagged returns (1, 3, 6, 12 months); price vs 12-month moving average; rolling volatility (3, 12 months) or GARCH volatility.

### 4.3 Cross-asset and energy features
- Energy: Brent (EUR), TTF gas (EUR/MWh), power prices for France and Hungary; their 1- and 3-month changes.
- Nickel for stainless, iron ore and zinc for steel, benzene for epoxy.
- EUR/USD level and change.

### 4.4 Market features (available ones only)
- **LME 3-month forward − cash spread** (contango / backwardation) for Cu and Al.
- **LME stocks** (level and change) for Cu and Al.

### 4.5 Feature hygiene
- Standardise with training-window statistics only; regularise (quantile lasso) rather than add features; keep SHAP / coefficient plots for the presentation.

**Important**: no data leakage. Common mistakes: using a PPI before it was published, using revised values instead of first releases where it matters, scaling with full-sample statistics, or overlapping H-month targets between training and test sets.

**Output:** `build_features(panel, t)` + feature table per horizon.

---

## Step 5 – Baselines

Every model must beat these, per horizon:

1. **Random walk:** `P_{t+H} = P_t` (very hard to beat for commodities).
2. **LME 3-month forward** as the forecast, for Cu / Al and **H = 3 only** (no 6/9-month curve in the data).
3. **Historical drift.**
4. **Empirical-quantile baseline** for intervals: historical distribution of H-month returns (extended history where available).

---

## Step 6 – Probabilistic forecasting models

Forecast the **5th, 50th, 95th percentiles** (or full distribution) for H = 3, 6, 9. Four families are enough for this sample size:

| Family | Models | Why |
|---|---|---|
| Volatility-scaled | **GARCH(1,1)** / EWMA volatility × √H, with Student-t or bootstrapped residuals | Captures volatility clustering; widens intervals in calm-then-stress periods |
| Linear quantile | **Quantile regression** (with L1 penalty) on 5–10 features from Step 4 | Uses energy / spread signals; interpretable |
| Foundation models | **Chronos-2** / TimesFM, zero-shot, optionally with energy covariates | Strong probabilistic benchmark with no training on our small sample |
| Joint | Bootstrap of joint monthly residuals (block bootstrap) | Keeps cross-material correlation for Step 8 |

Optional: LightGBM quantile on the **extended** history only; simple quantile averaging ensemble. Skip VAR / VECM.

---

## Step 7 – Backtesting & evaluation

- **Rolling-origin (walk-forward):** first origin after ≈ 48–60 months of training, expanding window. Respect publication lags at each origin.
- Keep the last 12–18 months (including the 2025–26 copper rally) as a **final hold-out**.
- Overlapping H-month targets make errors autocorrelated: report results with this in mind (block bootstrap for confidence intervals; don't over-read small differences).

| Type | Metrics |
|---|---|
| Point forecast | MAE, RMSE, **skill vs random walk** |
| Probabilistic | **Pinball (quantile) loss**, CRPS |
| Calibration | **Interval coverage** (does the 90 % interval contain the outcome ≈ 90 % of the time?) — the key metric for a pricing buffer |
| Stress | Coverage and loss in 2021–22 and 2025–26 |

**Output:** comparison table per model × horizon × material; selection of the final model(s).

---

## Step 8 – From material forecasts to unit-cost distribution

- **Simulate joint price paths** for all materials, preserving correlations (block bootstrap of joint residuals, or t-copula on model residuals).
- Push each path through the **Step 2 cost formula**, for each BOM scenario → distribution of unit cost at 3, 6, 9 months for RM6 and RM AirSeT.
- Shift the horizon for the purchase lag (Step 0): exposure = time between quote and material purchase, not the full validity period.
- Compute **Cost-at-Risk (CaR):**
  > "With 90 % confidence, RM AirSeT unit cost will not rise more than X % within 9 months."

**Output:** cost distribution and CaR table per product × horizon × BOM scenario, with the contribution of each material.

---

## Step 9 – Pricing rule and strategy comparison

Compare strategies on historical data (backtest), **per product**:

1. **Fixed price + risk buffer** = CaR at P75 / P90 / P95.
2. **Indexation clause:** price adjusts to an index beyond a threshold. Natural fit for **AirSeT on steel (MEPS/CRU or Eurostat S09)**, mirroring how Schneider's own steel purchases are indexed (Step 0); for RM6 on LME copper.
3. **Hedging with LME copper futures** (RM6 only: AirSeT has little or no copper). Cost of the hedge vs risk removed.
4. **Shorter or tiered validity periods.**

For each strategy measure:
- Frequency and size of **margin breaches**.
- Average margin achieved.
- **Competitiveness trade-off:** a higher buffer protects margin but loses deals → present a **curve of buffer vs breach probability**, not a single number.

Margin is computed against assumed selling prices (cost + target margin) until the encrypted price benchmark is available.

**Output:** recommended pricing policy per horizon and product.

---

## Step 10 – Story, recommendations and limitations

- **Expected key finding:** point forecasts barely beat the random walk, but **calibrated uncertainty** materially improves pricing decisions.
- **Recommendations (to confirm with results):** buffer increasing with validity period; RM6 → copper buffer or copper hedge; AirSeT → steel indexation clause; 9-month fixed prices only with indexation.
- **Link to Problem 2:** AirSeT's thinner margin makes this tool essential to price the SF6-free offer competitively without destroying margin.
- **Limitations:** BOM gaps and the conflicting copper mass, PPIs as proxies for purchase prices, short history (no 2008 in the main panel), publication lags and revisions, regime changes, no selling-price data yet.

---

## Step 11 – Streamlit app (deliverable for the sales team)

A small Streamlit app that turns Steps 2, 8 and 9 into a quote-time tool.

### 11.1 Features
- **Sidebar inputs:** product (RM6 / RM AirSeT), validity period (3 / 6 / 9 months), purchase lag (months), risk appetite (P75 / P90 / P95), target margin (%), BOM scenario (low / base / high), quote date (defaults to the latest month in the data).
- **Main page:**
  - **Recommended price adder (%)** and price (€) as headline numbers, plus the probability of breaching the target margin without a buffer.
  - **Fan chart** of unit cost over the next 9 months (P5–P95 bands).
  - **Risk drivers:** bar chart of each material's contribution to cost risk ("copper = 60 % of RM6 risk").
  - **Buffer vs breach-probability curve** (Step 9 trade-off), with the chosen point highlighted.
  - **Strategy comparison** table: fixed + buffer vs indexation vs hedge.
- **Second page "Market":** recent prices of the key materials and energy series, with the 3/6/9-month quantile forecasts.
- **Third page "Assumptions":** BOM table and price mapping, model used, backtest coverage, data freshness (last month per series). Sales must see what the number rests on.

### 11.2 Architecture
- **Precompute offline, read in the app.** A script (`src/pipeline.py`) runs Steps 1–8 and saves results to `app/data/` (simulated cost paths or quantile tables per product × horizon × scenario, as Parquet). The app only loads files and does light arithmetic, so it starts fast and needs no model libraries.
- Code layout: `src/` for data loading, cost model, models and simulation; `app/streamlit_app.py` + `app/pages/`. The app imports the cost formula from `src/` so the numbers match the notebooks.
- Use `st.cache_data` for loading; Plotly for the fan chart and curves.
- Add `streamlit` and `plotly` to `pyproject.toml` (`uv add streamlit plotly`); run with `uv run streamlit run app/streamlit_app.py`.

### 11.3 Done when
- Results for one product × horizon match the CaR table from Step 8.
- Every number shown has its assumptions on the Assumptions page.
- It runs from a clean clone with one command, and the demo is rehearsed for the final presentation (optionally deployed on Streamlit Community Cloud, without the confidential BOM file if required).

**Output:** working app + 2-minute demo script.

---

## Team split

| Workstream | Steps |
|---|---|
| Data & cost model | 0, 1, 2 |
| EDA & feature engineering | 3, 4 |
| Forecasting & backtesting | 5, 6, 7 |
| Risk simulation & pricing | 8, 9 |
| Streamlit app | 11 |
| Story (everyone) | 10 |
