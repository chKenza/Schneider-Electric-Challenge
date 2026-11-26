# Step 3 – Exploratory Data Analysis

**Scope:** plan Step 3 (3.1 univariate, 3.2 multivariate, 3.3 business EDA) plus extra checks.
**Built on:** the Step 1 panel (`src/data_prep.py`) and the Step 2 cost model (`src/cost_model.py`), both by Karin. The EDA does no cleaning of its own.
**Code:** `src/data_loading.py`, `src/eda_cost.py`, `src/eda.py`, `src/plotting.py`, called from `analysis/03_eda.ipynb`.
**Config and assumptions:** `configs/eda.yaml`. **Plots:** `plots/step3/`. **Full tables (CSV):** `report/problem1/step3_tables/`.

**Reproduce** (from the repo root):

```bash
uv sync
uv run python -m src.data_prep     # Step 1
uv run python -m src.cost_model    # Step 2
cd analysis && uv run jupyter nbconvert --to notebook --execute --inplace 03_eda.ipynb
```

---

**What we learned**
1. Prices are hard to predict but easy to describe. Over 3–9 months most materials move only slightly up or down. When they move, though, they tend to rise much more than they fall. Steel nearly tripled in 2021, while falls are usually milder. Raw-material risk works like insurance: the danger is in rare big shocks, not in everyday movement.

2. The longer the quote, the bigger the risk. With a 3-month fixed price, the bad case (1 contract in 20) costs about 2–3 margin points. With 9 months it is about 5–7.5, and the worst historical case reached 8.5–10 points (section 4).

3. Copper is not the only problem. Copper is 52 % of the value of RM6's raw materials, but with market prices it explains only about a third of the cost risk. Stainless and carbon steel explain most of the rest (≈ 55 %), because their prices swing more. RM AirSeT also has copper in the client's corrected BOM (v1: 38 % of its value), but steel and stainless dominate its risk: about 80 % with market prices, against 16 % for copper.

4. We need the right price data. The official statistics (PPIs) for steel are too smooth and slow to show what Schneider actually pays. The market prices its suppliers really use (MEPS/CRU) show the true swings. For copper, the two give the same answer. **This matters for the Step 2 cost model**, which moves steel and stainless with the S09 PPI: it makes RM6 look like a copper-only risk and makes the 9-month bad case of AirSeT about a third smaller than with market prices (section 4).

5. Some prices give early warnings. Oil moves about a month before plastics and epoxy, and nickel moves about a month before stainless steel. These signals can help forecasting.

6. In a crisis, everything goes up together. In normal times copper and steel move fairly independently, so their swings partly cancel out. In 2021–22 they all rose at once. Planning for "average" behaviour therefore underestimates the bad case.

7. The client's corrected BOM (v1) settled the biggest open question: AirSeT has 28.5 kg of copper and 16.4 kg of epoxy, and RM6 is fully labelled (38.75 kg of copper, as its environmental profile says). AirSeT's 56 kg of "Other" stays unpriced, as the client asked, so its cost risk is a floor.

**What this means for the business**
* The safety margin added to a quote should grow with the validity period. Based on market prices: about +3 % of price at 3 months, +5–5.5 % at 6 months, +7–7.5 % at 9 months (P95, section 4).
* For long quotes (9 months), a price-adjustment clause tied to steel and copper indices is safer than a fixed price.
* RM AirSeT's risk is mostly steel and stainless, plus copper (BOM v1). A clause on MEPS CR coil, CRU stainless 304 and LME copper would remove most of its uncertainty, which matters given its thinner margin.

---

## 1. Data used

The EDA reads the Step 1 panel (`Data/processed/panel_monthly.csv`) and keeps 25 series under short names (mapping in `src/data_loading.py`). All cleaning is Step 1's:

- dates moved to the first of the month;
- USD converted with the ECB rate;
- the May-2026 epoxy typo fixed;
- data cut at the September 2026 origin.

| Group | Series (Step 1 ID) | From |
|---|---|---|
| LME metals in EUR | copper, aluminium cash (LME_*_CASH_EUR); nickel, zinc, iron ore (S03/S05/S04_EUR) | 2016 |
| Steel market prices | MEPS CR / HDG / HR coil Germany and France | Nov 2012 |
| Stainless | CRU 304 Germany, base + alloy surcharge | Jan 2008 |
| Producer price indices | S07–S13 | Nov 2016 |
| Epoxy chain | epoxy resin, benzene | Jan 2018 |
| Energy | Brent EUR, TTF gas EUR/MWh, day-ahead power DE / FR / HU | Nov 2016 |

- **Checks:** the Westmetall LME copper and aluminium prices match the IMF-based D01/D02 within a median 0.12 % / 0.18 % (max 0.8 % / 1.1 %).
- **Coverage:** every series ends in September 2026, except CRU stainless (August 2026).
- **Publication lags are not applied in the EDA.** They are handled in Step 4. The lead–lag results below are on reference months.

---

## 2. Univariate analysis (3.1)

![Price history](../../plots/step3/01_price_history.png)

**Regimes.** Every series shows the 2021–22 surge, but its size differs a lot: CR coil ×2.7 and stainless ×2.5 at the peak, power and gas ×10–20. Copper is the only series at a record high now (12,580 €/t in September 2026). Steel is recovering (CR coil 825 €/t), and power and gas are rising again (Hungarian power 179 €/MWh in September).

**Monthly log-returns** (full table: `step3_tables/return_summary.csv`):

| | vol %/yr | skew | excess kurtosis | lag-1 autocorr. of returns |
|---|---|---|---|---|
| Copper | 15.2 | −0.2 | 1.6 | 0.20 |
| Aluminium | 15.9 | −0.2 | 0.9 | 0.30 |
| Nickel | 24.8 | +1.2 | 5.1 | 0.28 |
| CR coil DE (MEPS) | 17.7 | +0.6 | 3.7 | **0.54** |
| Stainless 304 (since 2008) | 17.1 | −0.4 | 2.1 | **0.47** |
| Epoxy | 9.8 | +0.1 | 0.8 | 0.09 |
| PPI steel EU | 7.4 | +1.3 | 2.1 | **0.79** |
| TTF gas / Power HU | 71 / 75 | – | – | ~0 |

* Most series are not normal (Jarque–Bera p < 0.01): steel, stainless, nickel, iron ore, copper, the PPIs, oil, gas and German power. Aluminium, zinc, epoxy, EUR/USD and French and Hungarian power are not rejected at 1 %. Quantile and bootstrap methods fit better than Gaussian intervals.
* **Steel and PPIs have strong momentum.** Their monthly returns are autocorrelated (0.5–0.8) because MEPS and CRU are price assessments and PPIs are smoothed contract prices. Recent trend is therefore a real predictive feature for steel. LME metals behave much more like a random walk.

### Distribution of H-month changes: a naive cost-at-risk

![H-month distributions](../../plots/step3/03_h_month_change_distributions.png)

* x-axis: the % price change over the horizon. Left of 0, the material got cheaper (good for your margin); right of 0, it got more expensive (margin loss).
* y-axis: how many past signature months gave that change.
* Dashed vertical lines: the 95th percentile for each horizon. Only 5 % of past contracts saw a rise bigger than that.

| H-month change (%) | q05 3m | q95 3m | q05 6m | q95 6m | q05 9m | q95 9m |
|---|---|---|---|---|---|---|
| Copper | −9 | +19 | −10 | +30 | −10 | +40 |
| Aluminium | −11 | +18 | −14 | +29 | −15 | +38 |
| CR coil DE | −15 | +27 | −18 | +53 | −20 | +54 |
| Stainless 304 (since 2008) | −18 | +22 | −25 | +38 | −28 | +44 |
| Epoxy | −7 | +10 | −11 | +20 | −15 | +28 |
| PPI steel EU (S09) | −6 | +15 | −11 | +28 | −14 | +40 |

* **The upside tails are 2–3 times the downside tails** for most materials, so a symmetric buffer under-protects. For carbon steel, the upper tail comes almost entirely from the 2021 episode.
* **Stainless** has a longer history (from 2008), which includes the 2008–09 crash. That is why its downside is deeper than the others'.
* **Overlapping windows:** with H = 9 there are only 10–23 independent windows, so every q95 here has a wide error band.

### PPI vs market price

![PPI vs market](../../plots/step3/04_ppi_vs_market.png)

| Market vs PPI | PPI vol / market vol | corr (same month) | best lead of market | corr at that lead |
|---|---|---|---|---|
| Copper LME vs PPI Cu | 0.66 | **0.93** | 0 | 0.93 |
| Aluminium LME vs PPI Al | 0.35 | 0.42 | 1 m | 0.63 |
| CR coil DE vs PPI steel DE | 0.37 | 0.55 | 1 m | 0.58 |
| Stainless 304 vs PPI steel EU | 0.42 | 0.54 | 0 | 0.54 |

* **Steel and stainless:** the PPI is 2.4–2.7 times calmer than MEPS/CRU, lags by about a month, and has drifted away in level. After 2023 the PPI stays near 150 while CR coil is at 105–125, both rebased to Jan-2017 = 100. Schneider's steel purchases are indexed to MEPS/CRU (the `Q4-2017` sheet maps the Hungarian plant to *CR Germany* and *HDG Germany*).
* **Copper:** the PPI and the LME price are interchangeable.
* **Consequence for Step 2:** the cost model moves carbon steel and stainless with S09, because Step 8 needs drivers that are forecast targets. Section 4 measures what this costs in risk.

### Volatility clustering and stationarity

![Rolling volatility](../../plots/step3/05_rolling_volatility.png)

* **Volatility clustering.** The Ljung–Box test on squared returns is strongly significant for steel and stainless (p < 1e-9), the aluminium and steel PPIs, TTF and German power, and not significant for copper, nickel, Brent or epoxy. Forecast intervals for steel need a volatility state (GARCH or EWMA). For LME metals, constant volatility is defensible.
* **Stationarity (ADF/KPSS)** (`step3_tables/stationarity.csv`). Log levels are non-stationary or ambiguous for every series, while returns are stationary for 21 of 25. The four exceptions (MEPS CR and HDG, PPI Cu and Al) are borderline because of their strong momentum. **Modelling should use log-returns.** Cointegration was skipped, as the plan says.
* **Seasonality** (F-test on calendar-month means). It is significant only for day-ahead power (FR p = 0.001, HU p = 0.01, DE p = 0.02) and, weakly, for MEPS CR coil (p = 0.03, March peak, June trough). PPIs and metals show none. A month-of-year feature is only worth adding for energy, and Step 4 confirmed that none of the 15 targets needs one.

---

## 3. Multivariate analysis (3.2)

![Correlation heatmap](../../plots/step3/07_correlation_heatmap.png)

* **In normal times, materials form clusters:** LME metals (Cu–Zn 0.7, Cu–Al 0.6), flat steel (CR–HDG 1.0, CR–stainless 0.5), the epoxy chain (epoxy–benzene 0.65) and energy (TTF–power 0.6). Correlation between clusters is low (copper–CR coil 0.23).
* **In the 2021–22 stress period, diversification breaks down:**
  - copper–CR coil 0.23 → 0.46
  - CR coil–aluminium 0.22 → 0.45
  - CR–stainless 0.48 → 0.58
  - TTF–Hungarian power 0.61 → 0.91

  A cost simulation that assumes average correlations will understate the tail. Step 8 should use a block bootstrap or a t-copula, not a Gaussian with full-sample correlations.

### Lead–lag (correlation of Δx at t−k with Δy at t)

![Lead-lag](../../plots/step3/08_lead_lag.png)

| Leader → follower | best lead | ρ | Useful feature? |
|---|---|---|---|
| Brent → PPI plastics EU | 1 m | 0.60 | **Yes** (confirms the data README) |
| Brent → Epoxy | 1 m | 0.57 | **Yes** |
| Benzene → Epoxy | 0 (same month) | 0.65 | Nowcast only |
| Nickel → Stainless 304 | 1 m | 0.52 | **Yes**, through the alloy surcharge |
| Iron ore → CR coil DE | 1–3 m | 0.37 | Yes (weaker) |
| TTF gas → PPI Al | 1 m | 0.37 | Yes (weaker) |
| TTF / power → PPI steel EU | up to 6 m | 0.23–0.28 | Weak; check in backtest |
| MEPS CR coil → PPI steel EU | 1 m | 0.69 | **Yes**, for forecasting the PPI |
| LME Al → PPI Al | 1 m | 0.63 | **Yes** |
| LME Cu → PPI Cu | 0 | 0.93 | Same month only |
| Zinc → HDG | – | < 0.19 | No |

The significance band is about ±0.19. These leads are measured on reference months. Step 4 tests them again with publication lags and a backtest: Brent → plastics/epoxy and LME Al → PPI Al survive; MEPS → steel PPI does not add anything once the PPI's own momentum is in the model.

---

## 4. Business EDA (3.3), using the Step 2 cost model

### How the cost is built

The raw-material cost of one unit is Karin's Step 2 model (`src/cost_model.py`), unchanged:

```
cost_i(t) = kg_i × €/t_i(Sep 2026) / 1000 × driver_i(t) / driver_i(Sep 2026)
```

- **Masses:** the client's corrected BOM (v1, 25 Nov 2026): RM6 310 kg, AirSeT 547 kg, both with copper and epoxy. Brass (RM6, 3.4 kg) is priced as 65 % copper + 35 % zinc.
- **Plastics and unknown lines** ("Other", "Unidentified remainder") have no €/t level and are left out, as in Step 2.
- `src/eda_cost.py` reproduces Step 2's BOM index to within 0.0005 points.
- **History starts in January 2018**, because epoxy is part of every case and its series starts then.

**Two ways to move prices back in time**, compared throughout this section:

| | Step 2 drivers (team definition) | Market prices (sensitivity) |
|---|---|---|
| Carbon steel, stainless | S09 EU steel PPI | MEPS CR coil, CRU stainless 304 |
| Galvanised | S10 German steel PPI | MEPS HDG Germany |
| Copper, aluminium, epoxy | D01, D02, epoxy price | same |

The market version is closer to what Schneider pays. The Step 2 version is what Step 8 can produce from the forecast targets.

**For the margin simulation only**, a constant non-raw-material cost is added so that the unit cost in September 2026 is €3,009 for RM6 (teardown should-cost) and €3,610 for AirSeT (assumption: +20 %).

![Cost history](../../plots/step3/09_unit_rm_cost_history.png)

| Sep 2026 | Raw-material cost | Share of unit cost | Value split |
|---|---|---|---|
| RM6 | €931 | 31 % | copper 52 %, stainless 16 %, carbon steel 13 %, epoxy 12 %, brass 3 %, galvanised 2 %, aluminium 2 % |
| AirSeT | €941 | 26 % | copper 38 %, carbon steel 30 %, stainless 22 %, epoxy 8 %, aluminium 1 % |

### How much the cost moves over 3, 6 and 9 months

H-month change of the raw-material cost (BOM index), January 2018 → September 2026. Full table: `step3_tables/cost_h_changes.csv`.

| | Step 2 drivers: P90 / P95 | Market prices: P90 / P95 |
|---|---|---|
| RM6, 3 m | +9.7 / +11.5 % | +12.0 / +18.0 % |
| RM6, 6 m | +17.1 / +24.2 % | +21.2 / +34.2 % |
| RM6, 9 m | +26.0 / +36.0 % | +32.9 / +48.4 % |
| AirSeT, 3 m | +10.4 / +13.4 % | +11.3 / +21.1 % |
| AirSeT, 6 m | +19.1 / +24.2 % | +23.1 / +41.0 % |
| AirSeT, 9 m | +27.9 / +39.1 % | +35.9 / +60.3 % |

* The P90 values with Step 2 drivers are exactly Step 2's own table (`bom_index_changes.csv`).
* **With market prices, the tail is much fatter**, by 35–70 % at the 95th percentile. AirSeT is the most affected because 52 % of its value is steel and stainless, the two materials the PPI smooths.
* On the **total unit cost**, raw materials are only 26–31 %, so the moves are much smaller. The 9-month P95 is +7.6 % (RM6) and +6.8 % (AirSeT) with Step 2 drivers, and +10.2 % and +11.0 % with market prices.

![Unit cost change](../../plots/step3/10_unit_cost_change_distributions.png)

### Which material drives the cost risk?

![Risk contribution](../../plots/step3/11_risk_contribution.png)

This is an Euler decomposition: each material's share of the variance of the H-month € change of the raw-material cost.

| Case | Step 2 drivers | Market prices |
|---|---|---|
| RM6 | copper 41–53 %, stainless 17–22 %, carbon steel 13–17 %, epoxy 9–12 % | **copper 31–33 %, stainless 31–32 %, carbon steel 23–25 %** |
| AirSeT | carbon steel 37–39 %, stainless 27–28 %, copper 22–28 %, epoxy 7–8 % | carbon steel 46–50 %, stainless 32–33 %, copper 15–16 % |
| RM6, nickel check (Step 2) | copper 35–39 %, nickel-driven surcharge 30–41 %, carbon steel 8–15 % | – |

* **RM6:** with the Step 2 drivers, RM6 looks like a copper bet, as the Step 2 report says. With market prices, copper is only a third of the risk; stainless and carbon steel together are 55 %. The difference comes entirely from the smoothing of the steel PPI.
* **AirSeT:** with BOM v1, copper is AirSeT's largest single material by value (38 %), but steel and stainless still carry most of the risk: 65–67 % with Step 2 drivers and about 80 % with market prices, because their prices swing more than copper's relative to their weight.
* **Nickel check:** if the stainless surcharge followed nickel one for one, it would be as large a risk as copper even for RM6. The real CRU surcharge (market version) moves less than nickel, so this case is an upper bound.

### Historical "margin gamble"

At each past month, the price is set at unit cost / (1 − 30 %) and held for H months, with material bought at delivery. This is the worst case: no early purchasing, no indexation, no hedge.

![Margin gamble](../../plots/step3/12_margin_gamble.png)

Loss in margin points (negative = margin below the 30 % target). Full table: `step3_tables/margin_gamble_summary.csv`.

| | H | P95 loss, Step 2 drivers | P95 loss, market prices | Worst, market prices | P(loss > 2 pts), market |
|---|---|---|---|---|---|
| RM6 | 3 | −2.0 | −2.9 | −3.7 | 12 % |
| | 6 | −3.5 | −5.0 | −7.2 | 22 % |
| | 9 | −5.3 | −7.2 | −8.7 | 28 % |
| AirSeT | 3 | −2.0 | −3.0 | −4.4 | 10 % |
| | 6 | −3.4 | −5.4 | −7.7 | 19 % |
| | 9 | −4.8 | −7.7 | −9.8 | 24 % |

* **On average the gamble is close to neutral** (mean loss below 1 point). The risk is in regime shifts:
  - contracts signed between August and December 2020 lost the most: up to 6 points with Step 2 drivers, 8.5–10 points with market prices;
  - contracts signed in spring 2022 gained up to 3 points (Step 2) or 6–7 points (market) when prices fell back;
  - contracts signed in autumn 2025 are losing again because of the copper rally: about −3.5 to −5 points at 9 months for RM6, and −2.5 to −4 for AirSeT, which now carries copper too.
* **A historical P95 buffer**, with market prices, is about **3 % of price at 3 months, 5–5.5 % at 6 months and 7–7.5 % at 9 months**. With the Step 2 drivers it is 25–40 % lower. These buffers scale with the raw-material share of unit cost, which is assumed for AirSeT.

---

## 5. Extra exploration

**Data quality**

* **Epoxy file typo.** In the raw file, May-2026 epichlorohydrin is 257 €/t, against about 2,500 around it, which drags epoxy from about 4,900 to 3,593 for one month. Step 1 replaces both values by interpolation. The isolated-spike scan in the notebook finds this point in the raw file and nothing left in the Step 1 panel. Without the fix, epoxy's measured volatility doubles and shows a fake spike-and-revert pattern.
* The April-2020 benzene crash (206 €/t) is real and is kept.
* The only other isolated spike is a dip in French power in May 2025. It is plausible (spring surplus) and left as is.
* **Teardown benchmark.** The SGC column has a total should-cost of €19, so it is unusable. Eaton's should-cost (€767) is also implausibly low.

**Selling price vs cost** (synthetic RMU benchmark, yearly P50, Step 1 output)

![Price vs cost](../../plots/step3/13_selling_price_vs_cost.png)

* Up to 2025, Schneider's P50 price follows the RM6 raw-material cost loosely and with a lag. The year-on-year correlation is 0.82 excluding 2026, but on only 7 points.
* Prices are sticky. Raw-material cost rose 56 % from 2018 to 2022 while the price rose 14 %. The price kept rising in 2023–25 while costs fell back, so the margin was rebuilt.
* **2026: every SF6 brand jumps by +33 % to +40 %; Eaton (SF6-free) by +8 %.** This fits the EU F-gas ban on SF6 in new ≤24 kV switchgear from 2026. It is relevant for Goal B (price convergence of SF6-free products), but the panel is synthetic and Step 1 leaves 2026 out of margin backtests.

---

## 6. Implications for the next steps

| Step | Recommendation from the EDA |
|---|---|
| 2 Cost model | Keep the S09 drivers for the forecast chain, but **report the market-price version next to it**. Better still, forecast MEPS CR coil and CRU stainless internally (not CSV targets) and use them in Step 8, because the S09 version gives a 9-month P95 25–35 % below the market-price version. AirSeT's "Other" (56 kg in BOM v1) stays unpriced, as the client asked. |
| 4 Features | Done in Step 4: own momentum for the PPIs, Brent → plastics and epoxy, LME Al → PPI Al, iron ore → US steel. No calendar features. |
| 5 Baselines | A random walk will be hard to beat for LME metals. Steel and PPIs, which have momentum, are where models can add skill. |
| 6–7 Models | Use log-returns. Use volatility-state models (GARCH or EWMA) for steel and energy. Use quantile or bootstrap intervals, not Gaussian ones. Expect few independent windows at H = 9. |
| 8 Simulation | Use stress-aware joint dependence (block bootstrap or t-copula); correlations rise sharply in crises. Never add up material P90s (Step 2 says the same). |
| 9 Pricing | The buffer must grow with H. Indexation for RM6 should cover stainless and steel as well as copper. For AirSeT, a clause on steel, stainless (MEPS CR / CRU 304) and copper covers about 95 % of raw-material risk. |

## 7. Limitations

* **Cost model gaps:** plastics are unpriced, AirSeT's "Other" (56 kg) is unknown and unpriced (client rule), and AirSeT's total unit cost (€3,610) is an assumption.
* **History:** the cost history starts in January 2018 (epoxy), so the 2008–09 crisis is only in the stainless series.
* **Margin simulation:** it assumes all material is bought at delivery, a constant non-raw-material cost, a 30 % target margin and no indexation. Real exposure is smaller if purchases happen earlier.
* **Lead–lag** results are computed on reference months, not publication vintages (handled in Step 4).
* **The RMU price benchmark** is synthetic and yearly.
