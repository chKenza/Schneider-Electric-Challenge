# Problem 1 – Raw-material price risk on fixed-price offers

## The problem

Schneider quotes its RM6 and RM AirSeT ring main units at a **fixed price, valid 3, 6 or 9 months**, but pays for the raw materials later. If copper or steel prices rise in between, the margin shrinks.

The client asks for two things:
1. **Forecasts:** P10 / P50 / P90 of every raw material in the two products, and of each product's raw-material cost, 3, 6 and 9 months ahead.
2. **A quote rule:** the price adjustment, risk buffer, quote validity and indexation clause to use per product and horizon.

## Our approach

We forecast the **uncertainty** of each price, not just its most likely value. The bill of materials turns it into euros per unit, then into margin points at risk, then into a quote rule that sales can apply.

The main constraint is short history: about 119 monthly points per series (Nov 2016 → Sep 2026), so only about 13 independent 9-month windows, with two regime changes (the 2021–22 surge and the 2025–26 copper rally). We therefore favour simple, well-calibrated models and test them strictly against the random walk.

## The steps

| Step | What it does | Report |
|---|---|---|
| **0. Framing** | Defines the decision to support (margin points at risk, since no target margin is given), the assumptions and the questions for the client. | [step0](step0_framing.md) |
| **1. Data preparation** | Builds one monthly panel in EUR from all sources, with each series' publication lag, so a forecast only uses what was published at the time. | [step1](step1_data_preparation.md) |
| **2. Cost model** | Computes the raw-material cost of one unit as Σ kg × price, from the client's bill of materials, and the € weight of each material. | [step2](step2_cost_model.md) |
| **3. Exploratory analysis** | Describes how prices move over 3, 6 and 9 months, their regimes and correlations, and which material drives each product's cost risk. | [step3](step3_eda.md) |
| **4. Features** | Selects free public drivers (energy, supply-chain pressure, carbon price, EIA forecasts), each with an economic mechanism and proven to be known at forecast time. | [step4](step4_features.md) |
| **5. Baselines** | Sets the random walk ("no change") as the benchmark every model must beat, with other simple references. | [step5](step5_baseline.md) |
| **6. Models** | Compares 9 probabilistic models. The final model averages four volatility and trend models, adds the drivers where they help, and recalibrates its range every month. | [step6](step6_models.md) |
| **7. Evaluation** | Backtests every model month by month against the random walk, then scores it once on an untouched 18-month hold-out; checks calibration, significance, compute and CO₂. | [step7](step7_evaluation.md) |
| **8. Simulation** | Simulates 10,000 joint price paths, matching each material's forecast, to get each product's cost index P10 / P50 / P90, the margin points at risk and the € per material. | [step8](step8_simulation.md) |
| **9. Pricing rule** | Turns the risk into a quote rule per product and validity, and compares buffers, indexation clauses, hedging and shorter validity on past and simulated quotes. | [step9](step9_pricing.md) |
| **10. Story** | States the recommendations as cause → effect chains, the limitations that could change them, and the handover to Problem 2. | [step10](step10_story.md) |
| **11. Decision tool** | A Streamlit app in which a non-coder tests a quote: product, validity, accepted loss → recommended terms. | [`app/`](../../app/) |
| **12. Submission** | The forecast CSV, a one-command pipeline that reproduces it, and a README with data limits, licences, AI-tool disclosure and CO₂. | [README](../../README.md) |

The results and recommendations are summarised in the [story report](step10_story.md).
