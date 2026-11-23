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
  - 🧭 *Causal logic: for each lead–lag pair kept, write the mechanism in one sentence (e.g. "gas is burnt to reheat steel, so a gas price rise raises steel producers' costs, which they pass on with a delay of a few months"). A correlation with no mechanism is treated as chance.*
- Skip cointegration / VECM: too few observations for reliable results.

### 3.3 Business-oriented EDA
- Using the Step 2 formula: **historical unit cost series** per product and its H-month changes.
- **Risk decomposition:** which material explains most of the unit-cost variance? Expected: copper for RM6, steel / nickel for AirSeT. Check it.
- **Historical "margin gamble" simulation:** if a contract had been signed at each past month at a fixed price (cost + target margin), how much margin would have been lost / gained at 3, 6, 9 months? How often would the target have been breached? (Use real selling prices if the encrypted file is released.)

**Output:** EDA notebook + 4–6 key charts (price history with regimes, H-month change distributions, correlation heatmap, cost breakdown and risk contribution by product, historical margin erosion).

---

## Step 4 – Forecast targets and feature engineering

### 4.1 What we forecast (set by the submission format, slide 17)
- **Material rows:** every priceable BOM material proxy, **EU and WW**, as mapped in `bom_materials.csv`:
  - EU: D01 (copper), D02 (aluminium), S09 (carbon + stainless steel), S10 (galvanised steel), S11 (plastics); optionally S07 / S08 (Cu / Al PPIs).
  - WW: S01, S02 (LME Cu / Al), S03 (nickel), S04 (iron ore), S05 (zinc), S12 (US steel PPI), S13 (US plastics PPI).
  - **Insulating materials (named in the brief, slide 14):** add **epoxy resin** (EU, EUR/t, from `Epoxy for student.xlsx`), the AirSeT solid-insulation material. S11 (plastics PPI) covers PBT / PET / ETP.
  - **Electronics (also named in the brief):** no price series in the data → not forecast; say so explicitly in the README and the presentation (data limit).
  - Final list = the BOM mapping; confirm with Step 2 owner. **Units must be one of the two allowed in the CSV: `EUR/t` or `index (origin=100)`.** EUR prices (D01, D02, epoxy) in EUR/t; PPIs as index (origin = 100); USD-priced WW series (S01–S05) as **index (origin = 100)**, so no USD unit and no FX forecast is needed (or convert to EUR/t with an FX assumption, stated).
- **BOM rows:** the **BOM cost index** for RM6 and RM AirSeT (raw-material cost ÷ its Sep 2026 value × 100), from Step 8.
- **Origin = last data month (2026-09)**; horizons +3 / +6 / +9 → target months 2026-12, 2027-03, 2027-06. In the backtest, the origin is the last month **published** at that date (Step 1 lag table), so the horizon is always counted from the last known value, as in the CSV.
- **Modelling target:** `y_{t,H} = log(P_{t+H}) − log(P_t)`, one model per horizon (direct). Quantiles of `y` are converted back to levels: `P_t × exp(q)`. This keeps the order p10 ≤ p50 ≤ p90.
- **Log transform = variance stabilisation (course: Box-Cox with λ = 0).** Working on log changes also makes the series stationary (differencing, course); confirm with the ADF / KPSS tests of Step 3.
- **Multi-step strategy (course):** feature-based models use the **direct** approach (one model per horizon H = 3, 6, 9), so features are built once per origin and errors do not accumulate. Recursive forecasting (iterating a one-month model) is left to ETS / ARIMA / GARCH in Step 6. Multi-output models (one model predicting all three horizons) are not needed.

### 4.2 Features (5–10 per model)
- **Own price — lags:** returns over 1, 3, 6, 12 months. **Choose the lags from the ACF / PACF of monthly log changes** (course) and economic sense (quarterly steel price resets → lag 3), not by habit. ⚠️ *Small data: with ≈ 120 points, ACF / PACF bands are wide (± 2/√120 ≈ ± 0.18); a lag that looks significant may be noise. Prefer a few standard lags over many lags chosen from the plot.*
- **Own price — rolling window statistics (course):** price vs 12-month mean; **distance from the 12-month max and min**; rolling volatility (3, 12 months) or GARCH volatility. These summarise many lags in a few features, which limits overfitting.
- **Energy:** Brent (EUR), TTF gas (EUR/MWh), power prices for France and Hungary; 1- and 3-month changes (README leads: Brent → plastics, TTF → aluminium and steel).
- **Drivers:** nickel for stainless, iron ore and zinc for steel, benzene for epoxy; EUR/USD level and change.
- 🧭 *Causal logic: for every energy / driver feature, state explicitly the cause → effect chain and the expected sign and delay, e.g. "nickel is ≈ 8–10 % of 304L stainless → nickel ↑ raises the alloy surcharge → stainless price ↑ within 1–2 months"; "EUR/USD ↓ (weaker euro) → USD-priced metals cost more in EUR → EUR copper price ↑ immediately". Check that the fitted sign matches; if it doesn't, drop the feature or explain why.*
- **LME market data (Cu, Al only):** 3-month forward − cash spread; stocks (level and change).
- **Calendar features (course):** **only if Step 3 finds seasonality**, most likely in the Eurostat PPIs, which are not seasonally adjusted. Encode the month as **sine / cosine** (cyclical encoding, course) rather than 12 dummies (2 features instead of 11). ⚠️ *Small data: 10 years = only 10 observations per calendar month, so a seasonal pattern needs to be strong to be trusted.*

### 4.3 Feature selection
- **Start from economic logic** (which driver should move which material), then check with data. 🧭 *Causal logic: write it as a small cause → effect diagram per material (driver → producer cost → material price, with the delay), and note common causes that could create a misleading correlation (e.g. global demand / China growth moves both copper and oil, so oil "predicting" copper may only reflect that shared cause). Put the diagrams in the Step 4 report: they justify each feature to the jury.*
- **Lead–lag analysis** from Step 3 (cross-correlations at lags 1–6).
- **Granger causality test (course):** does the past of a driver (e.g. TTF gas) improve the forecast of a material (e.g. S09) beyond the material's own past? Run it on the training window only, at each re-selection. ⚠️ *Small data: low power with ≈ 120 points, and testing many drivers × lags gives false positives (with 20 tests at 5 %, one passes by chance). Use it as one signal among three (logic, lead–lag, Granger), correct for multiple tests (e.g. Holm), and keep a feature only if it also improves the backtest pinball loss.* "Granger-causes" means "helps predict", **not** "causes".
- **Regularisation (course: L1 / L2):** quantile lasso shrinks useless features to zero; prefer this to adding features.
- **Cap:** 5–10 features per model. Rule of thumb: at least 10–15 observations per feature; with ≈ 60–110 training months per origin, 5–8 features is the realistic maximum.

### 4.4 Proof that each feature was known at forecast time (slide 16, item 3)
- Every feature uses data up to **origin − publication lag** of its own series (Step 1 lag table).
- Automated check in the code: for each origin, assert that no input date is later than its publication date. Save the result as a table in `report/` (one row per feature: source, publication lag, last date used at a sample origin).
- Scaling statistics come from the training window only.

### 4.5 Feature hygiene
- **Missing values in features:** never fill with future values (no backward fill, no interpolation across the origin); carry the last published value forward and add the publication lag (Step 1).
- Keep coefficient / SHAP plots for the technical appendix; for the business audience, explain drivers in **€ per material** (Step 8).

**Important**: no data leakage. Common mistakes: using a PPI before it was published, using revised values instead of first releases where it matters, scaling with full-sample statistics, or overlapping H-month targets between training and test sets.

**Output:** `build_features(panel, origin)` + feature table per horizon + the "known at forecast time" proof table + the selected features per material with the reason (logic / lead–lag / Granger / backtest gain).

---

## Step 5 – Baselines

Every model must beat these, per horizon. **The jury requires beating a naive baseline on at least one horizon; all three is better** (slide 17).

1. **Naive / random walk:** `P_{t+H} = P_t` — **the reference baseline for the jury**. Its interval version uses the historical spread of H-month changes around it. (It is also ARIMA(0,1,0) on log prices, which links it to the ARIMA family in Step 6.)
2. **Seasonal naive** for the non-seasonally-adjusted Eurostat PPIs (value 12 months earlier, adjusted) — only if Step 3 found seasonality.
3. **LME 3-month forward** as the forecast, for Cu / Al and **H = 3 only** (no 6/9-month curve in the data).
4. **Historical drift** (random walk with drift: the average past monthly change × H).
5. **Simple exponential smoothing (SES)** on log prices: a smoothed naive that weights recent months more (course, "exponential smoothing"). If the fitted α is close to 1, it collapses to the random walk, which is itself a finding.
6. **Empirical-quantile baseline** for intervals: historical distribution of H-month returns (extended history where available).
7. **Unconditional volatility baseline:** P_t × exp(± z × σ × √H) with σ = full-history monthly volatility. GARCH / EWMA (Step 6) must beat this to show that time-varying volatility helps.

**Output:** baseline forecasts for every target × horizon × backtest origin, in the same format as the models (P10 / P50 / P90).

---

## Step 6 – Probabilistic forecasting models

Forecast **P10, P50, P90** for H = 3, 6, 9 (the submission quantiles). Also keep **P95** for the pricing buffer if the business wants a stricter level (Step 9).

| Family | Models | Why |
|---|---|---|
| Classical statistical (course) | **AutoETS** (Holt with damped trend; no seasonal term, since Step 3 found none), **AutoARIMA** and **AutoTheta** on log prices, with their built-in prediction intervals (`statsforecast`) | Standard statistical benchmarks the jury expects; quick to fit; tell us whether there is any autocorrelation to exploit beyond the random walk. Theta: very simple (≈ 2 parameters), won the M3 competition (Assimakopoulos & Nikolopoulos, 2000, *IJF*). ⚠️ *Small data: automatic order selection is unstable on short series (the chosen order can change from one origin to the next); cap the orders (p, q ≤ 2)* |
| Volatility-scaled | **EWMA** (RiskMetrics, λ ≈ 0.97 monthly), **GARCH(1,1)** and **GJR-GARCH** volatility with Student-t errors, combined with bootstrapped standardised H-month changes (filtered historical simulation) | Captures volatility clustering; GARCH(1,1) is hard to beat (Hansen & Lunde, 2005); GJR tests whether price **spikes** raise volatility more than falls, which is the tail that hurts our margin. ⚠️ *Do not scale monthly volatility by √H: the PPIs move in trends, so H-month variance is far above H × monthly variance. ⚠️ Small data: GARCH needs ≈ 100+ points to estimate reliably; early backtest origins (≈ 50–60 months) may not converge or give unstable values. Fall back to EWMA (no estimation) when the fit fails, and log how often it happens* |
| Linear quantile | **Quantile regression** (with L1 penalty) on the features Step 4 selected (0–2 per model), with a volatility-scaled band around its median | Uses energy / market signals; interpretable; same loss as the evaluation (pinball). ⚠️ *Small data: a P90 fitted on ≈ 100 months rests on ≈ 10 observations above it, so P10 / P90 coefficients are noisy; keep features few and penalised* |
| Pooled ("global") model | One quantile regression fitted on **all materials stacked together** (≈ 15 series × 90 months), on volatility-standardised changes, with a material-group indicator | Multiplies the training data by ≈ 15 (Montero-Manso & Hyndman, 2021, *IJF*). Assumes materials share dynamics after scaling: check per-material coverage |
| Pretrained (foundation) model | **Chronos-Bolt**, zero-shot (optional install: `--extra chronos`) | State of the art with no training on our small sample; strong on monthly commodity prices (Wang & Zhang, 2026) but weak on daily financial returns (Rahimikia et al., 2025), so validate on equal terms; rewarded as "AI-heavy" bonus if disclosed. ⚠️ *Small data: short history at early origins, uncalibrated tails, possible pretraining leakage (judge on the 2025–26 hold-out); pin the version* |
| Equal-weight combination | Average of the quantiles of the best 3–4 models, chosen on the backtest | Combinations of simple models are robust in small samples (M4); no weights to estimate |
| Joint (for Step 8) | Standardised monthly residuals and joint H-month scenarios of all materials, exported for the Step 8 block bootstrap / empirical copula | Keeps cross-material correlation for Step 8 |

- 🧭 *Causal logic for covariates: when a model uses covariates (the feature quantile regression), report which ones it relies on and check that they match the cause → effect chains of Step 4. Say "helps predict", not "causes", in the results.*
- **Multi-step strategy (course):** the volatility-scaled models, quantile regressions and Chronos-Bolt use the **direct** approach (one forecast per horizon). ETS, ARIMA and Theta are **recursive** (they iterate one-month-ahead forecasts). Report which approach each model uses.
- **Covariate selection:** done in Step 4.3 (logic, lead–lag, Granger test, backtest gain).
- **Residual checks:** **Ljung-Box test** on residuals (no autocorrelation left) and on squared residuals (no volatility clustering left after GARCH). A model that fails is mis-specified, even if its backtest looks fine. ⚠️ *Small data: low power — "no autocorrelation detected" does not prove there is none.*
- **Calibration layer:** apply **adaptive conformal inference** (Gibbs & Candès, 2021) on top of each model, so P10–P90 covers ≈ 80 % in the backtest, also when the regime changes. ⚠️ *Small data: few residuals, especially for H = 9 (overlapping windows), so the correction itself is noisy; use a small learning rate and check it does not make coverage worse in the backtest.*
- **Combination:** average quantiles across the best models (Lichtendahl et al., 2013: averaging quantiles gives sharper forecasts than averaging distributions), then recalibrate. Equal weights: estimated weights are noisy in small samples.
- **Quantile crossing:** sort quantiles if a model returns p10 > p50 or p50 > p90 (the CSV requires p10 ≤ p50 ≤ p90).
- **Licence of every model / package:** record it as we go (`statsforecast`: Apache-2.0; `arch`: NCSA; Chronos: Apache-2.0; scikit-learn / `statsmodels`: BSD-3). It feeds the licence table (Step 12).

**Output:** forecasts for every target × horizon × origin × model, P10 / P50 / P90 (+ P95).

---

## Step 7 – Backtesting & evaluation

- **Rolling-origin (walk-forward) backtest per horizon:** first origin after ≈ 48–60 months of training; one forecast per month and per horizon. Respect publication lags at each origin.
- **Expanding vs sliding window (course):** expanding window by default (more data); also run a **sliding window** (e.g. last 60 months) for the best models. Regime changes (2021–22, 2025–26) may favour recent data only. Pick the window size on the backtest, not on the hold-out. ⚠️ *Small data: a 60-month window is too short for GARCH and quantile regression at P10 / P90; use it only for simple models (EWMA, empirical quantiles).*
- **Hyperparameter tuning** (e.g. quantile-regression penalty, EWMA λ, conformal learning rate): inner time-series cross-validation inside each training window, never using later data (Bergmeir, Hyndman & Koo, 2018). ⚠️ *Small data: inner folds are tiny; tune as few hyperparameters as possible and prefer standard values (e.g. λ = 0.97) when tuning does not clearly help.*
- Keep the last 12–18 months (including the 2025–26 copper rally) as a **final hold-out**, used once at the end. This is also where foundation models are judged, since earlier years may be in their pretraining data.
- Run the backtest on **material rows and on the BOM cost index** (computed historically with the fixed recipe).
- Overlapping H-month targets make errors autocorrelated: use block-bootstrap confidence intervals and don't over-read small differences.

| Type | Metrics |
|---|---|
| Point forecast (P50) | MAE, RMSE, **MAPE** (easy to read for the business: "the forecast is off by X % on average"), **skill vs naive** (1 − MAE_model / MAE_naive), per horizon |
| Scale-free comparison | **MASE** with the H-month naive error as denominator (course): comparable across materials in €/t and indices, and **MASE < 1 means the model beats the naive baseline** — a direct answer to the jury criterion. Avoid R² (measures fit, not forecast quality). |
| Weighted error | **WAPE** weighted by each material's € share in the BOM (course): errors on copper (RM6) and steel (AirSeT) count more than on aluminium |
| Probabilistic | **Pinball loss** for P10 / P50 / P90, **CRPS** (from the simulated paths), and their skill vs naive |
| Calibration | **P10–P90 coverage** (target ≈ 80 %) and **one-sided P90 coverage** (target ≈ 90 %), each with a 95 % confidence interval (≈ 13 independent 9-month windows → wide intervals, shown as such); Kupiec / Christoffersen tests; **PIT histogram** (Gneiting et al., 2007) to see whether intervals are too narrow, too wide or shifted. ⚠️ *Small data: coverage tests have low power (a badly calibrated model can pass), and the PIT histogram needs coarse bins (5, not 10–20)* |
| Significance | Diebold–Mariano with Harvey–Leybourne–Newbold correction, or Clark–West vs the random walk |
| Stability over time | Results **by sub-period** (pre-2020, 2021–22, 2023–24, 2025–26) and a rolling plot of pinball loss vs naive (Rossi, 2013): a model can win on average and lose in the period that matters. ⚠️ *Small data: each sub-period has only a few independent windows — describe, don't test* |
| Stress | Coverage and loss in 2021–22 and 2025–26 |
| Compute | Run time and estimated energy / CO₂ for each model (e.g. `codecarbon`) — slide 16, item 5 |

- **Jury check:** a table "beats naive? yes / no" per horizon, for P50 error and pinball loss. If a horizon does not beat it, say so honestly (Level 2 accepts "honestly matches").
- **Model selection:** first keep the models whose coverage is acceptable, then pick the lowest pinball loss (narrowest well-calibrated intervals = smallest buffer).
- **Final fit for the CSV:** once the model is chosen, **refit it on all data up to the origin 2026-09** (including the hold-out months) and produce the submission forecasts from there. The hold-out is for evaluation only; leaving it out of the final fit would throw away the most recent and most relevant months.

**Output:** comparison table per model × horizon × target, the "beats naive" table, coverage with confidence intervals, compute / CO₂ per model, and the selected model(s).

---

## Step 8 – From material forecasts to BOM cost index and margin at risk

- **Simulate joint price paths** for all materials, preserving correlations: GARCH-filtered block bootstrap of joint residuals (filtered historical simulation), or t-copula. ⚠️ *Small data: the bootstrap can only replay the ≈ 120 months seen (no worse joint shock than 2021–22), and a t-copula's tail parameter is hard to estimate from ≈ 120 points; fix it to a standard value (e.g. 4–6 degrees of freedom) and test sensitivity.* Scale each material's paths so its marginal P10 / P50 / P90 matches the selected Step 7 model.
- Push each path through the Step 2 recipe (**raw materials only**, € per unit = Σ kg × price) → distribution of raw-material cost at 3, 6, 9 months for RM6 and RM AirSeT.
- **BOM cost index rows of the CSV:** cost ÷ Sep 2026 cost × 100 → P10 / P50 / P90 per product and horizon.
- **Margin points at risk** (no target margin needed, see `report/step0_framing.md`): `(cost at P90 − cost today) ÷ selling price`. Selling price: RM6 from the price benchmark (Schneider P50 ≈ €8,740 in 2025); AirSeT assumed (Step 0).
  > "For a 9-month RM6 quote, raw-material increases will not take away more than X points of margin, with 90 % probability."
- **Split it in two** (slide 15 asks for both a "price adjustment" and a "risk buffer"):
  - **Price adjustment** = expected change: `(cost at P50 − cost today) ÷ selling price`. Covers the drift the market already expects; applies to every quote.
  - **Risk buffer** = uncertainty on top: `(cost at P90 − cost at P50) ÷ selling price`. Covers bad luck at the chosen confidence level; this is the part an indexation clause or a hedge can replace.
  - Total margin points at risk = price adjustment + risk buffer.
- **€ per material (explainability, slide 16, item 8):** contribution of each material to the P90 cost increase, in €, e.g. "copper: +€120, steel: +€40".
  - 🧭 *Causal logic: explain each contribution as a chain the buyer recognises, from market driver to euros in the unit, e.g. "LME copper +20 % → × 38.8 kg of copper in RM6 → +€X per unit → −Y margin points". This chain is mechanical (kg × price), so it is causal by construction. The uncertain part is the driver forecast, and it should be labelled as such.*
- **Scenarios** from Step 0 / Step 2: copper mass (38.8 kg vs 8.6–13.8 kg), plastics price level (low / high), steel index (MEPS vs CRU).
- **If licensed MEPS / CRU prices cannot be used as model inputs** (open question, `report/step0_framing.md` §7): move steel with the free Eurostat indices (S09, S10) from an assumed €/t starting level, and state it. The CSV steel rows are S09 / S10 anyway, so the submission does not depend on MEPS / CRU.
- **Purchase timing:** Schneider buys steel on an index (base + index change, updated quarterly, 1-month lead), so steel cost follows the index with a delay. Exposure = time between quote and material purchase (purchase-lag parameter), not the full validity period.

**Output:** BOM cost index P10 / P50 / P90 per product × horizon, margin points at risk per product × horizon × scenario, € contribution per material.

---

## Step 9 – Pricing rule and strategy comparison

Answer the client's question 2 (slide 15): **price adjustment, quotation validity, indexation mechanism and risk buffer per horizon, under upside, baseline and downside RM scenarios.**

- **Scenarios:** upside (costs rise) = P90, baseline = P50, downside = P10 of the BOM cost index.
- **Strategies compared on historical data, per product:**
  1. **Fixed price + price adjustment + risk buffer** (Step 8 split; buffer at P90, or P75 / P95 as a sensitivity).
  2. **Indexation clause with a trigger:** the price is revised if the index moves more than a threshold. Natural fit for **AirSeT on steel** (mirrors how Schneider buys steel, Step 0), for RM6 on LME copper.
  3. **Hedging with LME copper futures** (RM6 only).
  4. **Shorter or tiered validity periods.**
- **For each strategy measure:** frequency and size of margin erosion, average margin points lost, and the **buffer vs breach-probability curve** (competitiveness trade-off).
- **The counterfactual behind the comparison** (explain it in the report and presentation):
  - **Question:** "had Schneider used strategy S instead of today's fixed price, how many margin points would it have kept?" This is a counterfactual: we never observe the same quote both with and without an indexation clause.
  - **Reference (factual) scenario:** today's practice per the brief, a fixed price for H months with no protection.
  - **Counterfactual scenarios:** the same quote, on the same date, facing the **same realised (or simulated) material price path**, but priced with strategy S (buffer added, price revised when the index trigger is hit, hedge gain / loss added, or shorter validity).
  - **Effect of S** = margin points under S − margin points under the fixed price, computed for every past quote date and horizon (historical paths) and for every simulated path (forward-looking). Report the distribution, not just the average.
  - **Why this is credible:** margin = price − cost is an accounting identity, so once the price path is fixed, the effect of each strategy on margin is mechanical. No causal effect has to be estimated from data, which we could not do anyway (no contract-level data with and without clauses).
  - **What it assumes (state these explicitly):** (1) the deal is won and its volume is the same under every strategy — false in practice, since a buffer or an indexation clause can lose deals; the buffer vs breach curve and the competitiveness discussion cover this; (2) material prices do not react to Schneider's choice (true: Schneider is a price-taker on LME / steel markets); (3) the customer accepts the clause as written; (4) the hedge is priced at the LME forward (cost of hedging = forward − cash spread), with no broker fees.
- **Margin backtest with real prices:** use the synthetic selling-price series (2017–2025). **Exclude 2026** (SF6 ban price jump). Selling prices are sticky (≈ +7 %/yr in 2021–22, never cut in 2023–25), so cost shocks squeeze margin for about a year: show this in the backtest. ⚠️ *Small data: yearly prices 2017–2025 = 9 points — use them as an illustration (what happened in 2021–22), not as a statistical test of the strategies; the strategy comparison rests on the monthly cost simulation.*
- **2027 cost trajectory:** from the CSV forecasts, project the RM6 / AirSeT raw-material cost to mid-2027 under the three scenarios (slide 16: "propagate into 2027 RMU unit pricing").

**Output:** quote rule per product × horizon — **price adjustment %, risk buffer %, max quotation validity, indexation trigger** (the four items of slide 15) — under the three scenarios + backtested comparison of strategies.

---

## Step 10 – Story, recommendations and limitations

- **Expected key finding:** point forecasts barely beat the naive baseline, but **calibrated uncertainty** sizes buffers correctly per horizon. Raw materials are ≈ 9 % of the RM6 price, so buffers are small in % of price but large compared with the margin.
- 🧭 *Causal logic in the story: present each recommendation as a cause → effect chain the business can check, e.g. "AirSeT is mostly steel → Schneider already buys steel on a quarterly index → a steel indexation clause passes the same risk on to the customer → margin stays protected beyond 3 months". Separate what is mechanical (cost formula, strategy effects in Step 9) from what is predictive (forecasts, "helps predict" features).*
- **Recommendations (to confirm with results):** buffer increasing with validity period; RM6 → copper buffer, indexation or hedge; AirSeT → steel indexation clause; 9-month fixed prices only with indexation.
- **Link to Problem 2** (counts **equally** in the evaluation, slide 16): AirSeT's thinner margin makes this tool essential to price the SF6-free offer competitively. Hand the Problem 2 team one concrete output: the **RM6 vs RM AirSeT raw-material cost index outlook to mid-2027 (P10 / P50 / P90)**, which supports or rejects the "RM price convergence" argument of slide 15, question 3 (does AirSeT's steel-heavy recipe become relatively cheaper while copper rallies?).
- **Limitations:** BOM gaps and the conflicting copper mass, PPIs as proxies for purchase prices, short history, publication lags and revisions, regime changes, synthetic selling prices with no AirSeT price, 2026 excluded from the margin backtest, raw materials only (no labour, energy), **electronics not forecast (no price data)**, one product configuration only (the BOM is for the 3-function IQI unit; the benchmark's other configurations, 1F–4F, are not modelled), MEPS / CRU licence status.

---

## Step 11 – Streamlit app (decision tool, maturity level 4)

A Streamlit app that lets a non-coder test a pricing decision with our outputs (slide 18, level 4: "expected").

### 11.1 Features
- **Sidebar inputs:** product (RM6 / RM AirSeT), validity period (3 / 6 / 9 months), purchase lag (months), confidence level (P90 by default; P75 / P95 as options), scenario (upside / baseline / downside), BOM scenario (copper mass, plastics price), steel index (MEPS / CRU), selling price (default from the benchmark; editable).
- **Main page:**
  - **Margin points at risk** as the headline number, split into **price adjustment (%)** and **risk buffer (%)**.
  - **Fan chart** of the BOM cost index over the next 9 months (P10–P90 band, P50 line).
  - **€ per material:** bar chart of each material's contribution to the cost increase.
  - **Buffer vs breach-probability curve**, with the chosen point highlighted.
  - **Quote rule** table per horizon: buffer, max validity, indexation trigger.
- **Page "Market":** recent prices of key materials and energy series, with the 3/6/9-month P10 / P50 / P90 forecasts (same numbers as the CSV).
- **Page "Assumptions & model card":** BOM table and price mapping, model used and its licence, backtest results (beats naive per horizon, coverage), data freshness, AI tools used.

### 11.2 Architecture
- **Precompute offline, read in the app.** The pipeline (Step 12) saves forecasts and simulated cost paths to `outputs/`; the app only loads them, so it starts fast and needs no model libraries.
- Code layout: `src/` for data, cost model, models, simulation; `app/streamlit_app.py` + `app/pages/`. The app imports the cost formula from `src/` so its numbers match the CSV.
- `st.cache_data` for loading; Plotly for charts. `uv add streamlit plotly`; run with `uv run streamlit run app/streamlit_app.py`.
- **Confidentiality:** the BOM and MEPS/CRU data are not in the repo; the app reads them from the local `Data/` folder. If deployed publicly, use only aggregated outputs (no BOM masses).

### 11.3 Done when
- Its numbers match the CSV and the Step 8 tables.
- Every number shown has its assumptions on the Assumptions page.
- A non-team member can answer "what buffer for a 6-month AirSeT quote?" in under a minute.

**Output:** working app + 2-minute demo script.

---

## Step 12 – Submission: forecast CSV, reproducible pipeline and responsible AI

What the jury receives (slides 16–18). Target **maturity level 4** (expected), with level 5 elements if time allows.

### 12.1 Forecast CSV — `group_6_forecast_202609.csv`
- Columns: `team_id, target_type (material | bom_index), target_id, region (EU | WW), origin_month (2026-09), horizon_m (3 | 6 | 9), target_month, unit (EUR/t | index (origin=100)), p10, p50, p90, model_name, ai_tools`.
- Rows: every priceable material proxy × region × 3 horizons, plus RM6 and RM AirSeT BOM index × 3 horizons.
- **Validation script** (run in the pipeline and in CI): all rows present, p10 ≤ p50 ≤ p90, correct target months, units, no missing values.
- The CSV is tracked by Schneider against real prices after the jury: it is the true out-of-sample test.

### 12.2 One-command pipeline
- `uv run python -m src.pipeline` (or `make forecast`): load data → features → models → simulation → CSV + backtest tables + app outputs.
- Pinned dependencies: `pyproject.toml` + `uv.lock` (already in the repo); export `requirements.txt` for non-uv users.
- Fixed random seeds; same input → same CSV.
- **Confidential and licensed data:** the BOM and MEPS/CRU are not committed. The CSV material targets are free public series (D01, S09…), so the material forecasts reproduce from public data only. For the BOM index rows, either (a) the jury puts `Data/` in place locally, or (b) CI uses a GitHub secret holding the BOM — decide with the client question in `report/step0_framing.md` §7. Document the chosen option in the README.
- **GitHub Actions** (bonus): run the pipeline on push, upload the CSV as an artifact, show the green tick.

### 12.3 README (short)
- Approach in a few lines, how to run, data sources and **data limits**.
- **AI-tool disclosure:** coding assistants used, pretrained models (also in the `ai_tools` column).
- **Licence table:** every dataset (IMF/FRED, ECB, Eurostat CC BY 4.0, Ember CC BY 4.0, BOJ, JEPX, MEPS/CRU licensed, Schneider confidential) and every model / package with its licence.
- **Compute and CO₂ estimate** for the full pipeline and the backtest (from Step 7).

### 12.4 Level 5 – handover-ready (stretch)
- **Rerun on a held-back month:** run the pipeline with `--origin 2026-08` and show the result against the real Sep 2026 value; the pipeline takes the origin month as a parameter so it can be rerun next month.
- A named user and a short "how to update next month" section in the README.

**Output:** CSV, repo with one command, README with licence table / AI disclosure / CO₂, optional GitHub Actions.

---

## Team split

| Workstream | Steps | Team Member |
|---|---|---|
| Data & cost model | 0, 1, 2 | Karin |
| EDA & feature engineering | 3, 4 | Prisha |
| Baselines | 5 | Chloe |
| Forecasting & backtesting | 6, 7 | Kenza |
| Risk simulation & pricing | 8, 9 | Ion |
| Streamlit app | 11 | - |
| Submission, pipeline & README | 12 | - |
| Story | 10 | everyone |
