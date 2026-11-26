# Step 0 – Framing the problem

*Owner: Karin · Status: final draft · Scope: Problem 1 only*

---

## 1. The problem in one paragraph

Schneider sells two medium-voltage switchgear units to data-centre customers:

- **RM6**, made at **SFCME** in France
- **RM AirSeT**, made at **Duna Smart Power Systems** in Hungary

The price is **fixed for 3, 6 or 9 months**, but copper, steel and other materials keep moving, so every offer is a "margin gamble".

**Our goal:** forecast raw-material prices at 3, 6 and 9 months **with their uncertainty**, turn that into the raw-material cost of one unit of each product, and from there into a **quote rule** (risk buffer, quote validity, indexation trigger) that sales can use.

---

## 2. What we deliver (from the client presentation)

1. **A forecast CSV** (`<team>_forecast_202609.csv`):
   - starting from the last data month, **September 2026**
   - horizons **+3, +6, +9 months** (Dec 2026, Mar 2027, Jun 2027)
   - **P10 / P50 / P90** for each row
   - one row per priceable **material proxy** (e.g. D01 copper, S09 steel), for EU and worldwide (WW)
   - one row per product for the **BOM cost index** (RM6 and RM AirSeT)
2. **A repo** that reproduces the CSV with **one command**, a README (approach, data limits, AI tools used), pinned requirements and a backtest against a naive baseline.
3. **A pricing recommendation** per horizon under upside / baseline / downside scenarios.
4. **Expected level: a decision tool** that a non-coder can use (e.g. a Streamlit app).

**How the forecasts are evaluated** (slides 14, 16, 17):
- 3 / 6 / 9-month **forecast accuracy**, and the CSV is tracked against real prices after the jury.
- **Uncertainty coverage**: does the P10–P90 range contain the real value about 80 % of the time?
- A **rolling backtest per horizon** that **beats a naive baseline**: at least one horizon, all three is better.

The exact metric isn't named, so we report the standard ones: error on P50 vs naive, pinball loss, coverage.

Problem 2 (SF6-free strategy) is counted separately and is out of scope for this report.

---

## 3. How the pieces fit together

| Piece | What it is | Source |
|---|---|---|
| **Recipe** | kg of each material in one unit (fixed: the design doesn't change within 9 months) | Client BOM v1 (`RM_Prices_XHEC_Challenge_v1.xlsx`, 25 Nov; replaced `bom_materials.csv`) |
| **Prices** | €/t of each material, or an index (% change vs a base period) | Price files (LME, MEPS/CRU, Eurostat, …) |
| **Raw-material cost of one unit** | Σ kg × price over all materials | Computed |
| **BOM cost index** | That cost ÷ its September 2026 value × 100 | Computed |

- **Material rows** of the CSV: each material's price change on its own, e.g. "steel 120 at P90 = 10 % chance steel is more than 20 % higher".
- **BOM rows**: the same for the whole recipe of one product. Materials count by their **euro value** in the product, not their weight, and they're simulated **together**, because they rarely all hit their worst case at the same time.

---

## 4. How the answer will be phrased

We don't need Schneider's target margin. Raw-material risk is measured in euros, so we express it in **margin points lost**:

> "For a 9-month RM6 quote, raw-material cost increases will not take away more than **X points of margin**, with 90 % probability. Add X % to the price to keep your target margin, whatever it is."

- **P90 is one-sided:** a 90 % chance of staying below. P10–P90 together form an 80 % range.
- **The backtest adds a confidence interval** on that 90 %, e.g. "held 88 % of the time in past data (95 % CI: 80–94 %)". With about 13 independent 9-month windows, this interval will be wide, and we will show it.

---

## 5. What the data already tells us

### Raw materials are a small share of the selling price

The selling-price file (`RMU_IQI_EU_Price_Benchmark…`) gives a **synthetic yearly price** for an RM6-type unit, by brand, 2017–2026. It has **no AirSeT price**.

| | Value |
|---|---|
| Schneider P50 selling price, 2025 | **€8,740** |
| RM6 raw-metal cost at current prices | ≈ **€790** (≈ 9 % of price) |
| Effect of copper +30 % | ≈ **1.7 %** of the selling price |

So the buffers will be small compared with the price. The point of the model is to size them correctly per horizon.

### Selling prices are sticky

- In **2021–22**, raw materials rose 40–100 %, but Schneider's price rose only about 7 % a year.
- In **2023–25**, raw materials fell, but prices were never cut.

Cost shocks therefore squeeze margin for about a year. That's the risk we price.

### The 2026 price jump is the SF6 ban, not raw materials

In 2026, the SF6 brands' prices jump by **+32 to +40 %**, while the SF6-free brand (Eaton) moves **+8 %**. The client's chart marks the SF6 change at that point. **2026 is left out of any margin backtest.**

### Schneider buys steel on an index

From `Copia de Europe Steel INDEXES.xlsx`:
- purchase price = base price + the index change in €/t (MEPS/CRU)
- updated monthly in 2017, quarterly from 2018
- lead time of 1 month
- Hungarian plants priced on German indices

The file covers 2016–2018 and does not include SFCME or Duna.

### The two RM6 recipes disagree on copper

| Source | Copper in one RM6 | Copper share of raw-material cost | Copper +30 % → % of price |
|---|---|---|---|
| Schneider BOM v1 | **38.75 kg** | 52 % | ≈ 1.7 % |
| Benchmark "teardown" | **8.6–13.8 kg** | 20–28 % | ≈ 0.4–0.6 % |

The teardown is **not a physical teardown**. A tool generated it, with masses marked "inferred" and "not supported by a source", and it contains errors such as 500 kg of screws. So Schneider's BOM is the more credible source, but this one number changes RM6's copper risk by **3–4×**.

---

## 6. Handled by parameters, scenarios or assumptions

Instead of asking the client, these are inputs the user can change, or assumptions we state:

| Topic | How we handle it |
|---|---|
| Target margin | Not needed: result given in margin points |
| Time from signing to material purchase | Parameter (purchase-lag setting) |
| Existing customer indexation or hedging | We compare all strategies (buffer, indexation, hedge, shorter validity) |
| Steel index used in purchasing (MEPS vs CRU, 3–7 % apart) | We test both |
| RM6 copper mass | Base 38.75 kg (BOM v1); low scenario from the teardown |
| Unknown BOM lines | Left unpriced (client rule): RM6 "Unidentified remainder" 5.6 kg, AirSeT "Other" 56 kg |
| Plastics price level (no €/t, only a PPI) | Assumed starting price, with a low/high test (matters for AirSeT: ~21 kg) |
| AirSeT selling price | Assumed from RM6 and the "higher cost structure" in the brief |
| 2026 prices | Left out of the margin backtest (SF6 ban) |
| Scope | Raw materials only: no labour, plant energy, electronics |

---

## 7. Questions for the client

Only questions that change **what we build** and can't be handled by a parameter:

1. **Reproducibility vs confidentiality:** how do we make the pipeline reproducible "from a clean start" (and run it on GitHub Actions) without committing the confidential BOM and the licensed MEPS/CRU data? Can licensed MEPS/CRU prices be used as model inputs?
2. **RM6 copper:** is it 38.75 kg (internal BOM) or ≈ 9–14 kg (teardown)? It changes RM6's copper risk by 3–4×.

---

## 8. Next steps

- **Step 1** (done): one clean monthly panel, data dictionary, publication lags. See `step1_data_preparation.md`.
- **Step 2**: cost formula per product, BOM cost index, scenarios (copper mass, plastics price).
- Optional: check Schneider's public environmental profile for this RM6 (`ENVPEP1511010EN`). It lists material composition by mass and could settle the copper question without the client.
