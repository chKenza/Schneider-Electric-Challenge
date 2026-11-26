# Schneider Electric × X-HEC Data Challenge 2026 – Group 6

Raw-material price risk on fixed-price offers for medium-voltage ring main units (RM6 and the SF6-free RM AirSeT), and the go-to-market strategy for SF6-free switchgear where no regulation forces it.

- **Problem 1:** forecast raw-material prices 3, 6 and 9 months ahead, with P10 / P50 / P90, and turn them into a quote rule. Reports: [`report/problem1/`](report/problem1/).
- **Problem 2:** where and how to sell RM AirSeT without an SF6 ban. Reports: [`report/problem2/`](report/problem2/).
- **Forecast submission:** [`submissions/group_6_forecast_202609.csv`](submissions/group_6_forecast_202609.csv).

## Approach (Problem 1)

1. **Data** ([step 1](report/problem1/step1_data_preparation.md)): one monthly panel, Nov 2016 → Sep 2026, with each series' publication lag, so a forecast only uses what was published at the time.
2. **Cost model** ([step 2](report/problem1/step2_cost_model.md)): raw-material cost of one unit = Σ kg × price, from Schneider's bill of materials.
3. **Features** ([step 4](report/problem1/step4_features.md)): free public drivers (energy, supply-chain pressure, policy uncertainty, carbon price, EIA forecasts), each proven to be known at forecast time.
4. **Models** ([step 6](report/problem1/step6_models.md)): 9 probabilistic models for the 15 material series. The final model, `conformal_combo`, is an equal-weight combination of four volatility and statistical models, plus Step 4 features where they help, calibrated by adaptive conformal prediction.
5. **Evaluation** ([step 7](report/problem1/step7_evaluation.md)): rolling-origin backtest against the random walk (the naive baseline), then a hold-out (Apr 2025 → Sep 2026) frozen and opened once.

**Result against the naive baseline:**

| Horizon | Backtest skill (pinball loss) | Hold-out skill | Hold-out coverage of P10–P90 (target 80 %) |
|---|---|---|---|
| 3 months | **+4.3 %** (significant) | +2.5 % | 84 % |
| 6 months | **+7.0 %** (significant) | −0.5 % | 80 % |
| 9 months | **+10.7 %** (significant) | +0.8 % | 82 % |

The backtest beats the random walk at every horizon. The hold-out matches it: the median is no better than "no change", and the gain is in the band, which keeps the right coverage while being 20–33 % narrower than the random walk's for producer price indices and epoxy.

## How to run

Requirements: Python 3.12 and [uv](https://docs.astral.sh/uv/).

1. **Put the challenge files in `Data/`** (not in the repo: see [Data and licences](#data-and-licences)):

2. **One command from the raw data to the forecast CSV** (about 5 minutes; the first run needs internet to download the free external data, then it is cached):
   ```bash
   uv run python -m src.pipeline
   ```
   It runs data preparation → external data → features → baselines → models → CSV, then validates the CSV against the submission format. `--list` prints the stages; `--from models` resumes from a stage.
3. **Tests** (leakage and format checks; the leakage tests re-run every model, so this takes 10–15 minutes):
   ```bash
   uv run pytest tests/
   ```

Without uv: `pip install -r requirements.txt` (pinned versions, exported from `uv.lock`), then `python -m src.pipeline`.

**Reproducibility:** every model is deterministic or seeded. From a clean start (no processed data), the pipeline rebuilds a CSV identical to the committed one. The optional pretrained model Chronos is not in the final forecast, so the CSV is the same with or without it; `uv run --extra chronos python -m src.pipeline` also reproduces the Step 6 comparison tables exactly.

## The forecast CSV

Format : one row per target × horizon, origin September 2026, horizons 3 / 6 / 9 months (Dec 2026, Mar 2027, Jun 2027), P10 / P50 / P90.

- **15 material series:** copper and aluminium (EU in EUR, global LME), nickel, iron ore, zinc, EU and US producer price indices for steel, copper, aluminium and plastics, and epoxy resin.
- **Units:** EUR/t for copper and aluminium in EUR (D01, D02). Index (origin = 100) for the others: producer price indices, USD-priced series (no exchange-rate forecast needed) and epoxy, whose EUR/t level is Schneider-confidential.
- **BOM cost index for RM6 (`RM6_NE_IQI_433520`) and RM AirSeT (`RMAirSeT IIQ 24kV IEC`),** index (origin = 100): the raw-material cost of one unit from the client's corrected bill of materials, simulated jointly over 10,000 price paths with each material matching its forecast ([step 8](report/problem1/step8_simulation.md)). Steel is at producer prices (S09 / S10), the case backtested in [step 7, §6.1](report/problem1/step7_evaluation.md).

## Data and licences

`Data/` is not committed: the Schneider files are confidential, and the MEPS and CRU steel prices are licensed. The forecast targets are free public series, so the material forecasts reproduce from public data plus the challenge files.

| Data | Source | Licence / use |
|---|---|---|
| Copper, aluminium, nickel, iron ore, zinc (global) | IMF Primary Commodity Prices, via FRED | Free, with attribution |
| EU producer price indices (steel, copper, aluminium, plastics); EU imports | Eurostat | CC BY 4.0 |
| US producer price indices (steel, plastics) | US Bureau of Labor Statistics, via FRED | Public domain, with attribution |
| EUR/USD and other exchange rates | European Central Bank | Free reuse with source acknowledgement |
| Energy prices (gas, power, coal, oil) | IMF via FRED, Ember, Eurostat, Bank of Japan, JEPX | Free / CC BY 4.0, source cited |
| EU carbon price (EUA) | Ember | CC BY 4.0 |
| Brent, WTI and gas price forecasts | US EIA Short-Term Energy Outlook | Public domain, attribution requested |
| Global Supply Chain Pressure Index | Federal Reserve Bank of New York | Free, with attribution |
| Economic Policy Uncertainty indices | Baker, Bloom & Davis, policyuncertainty.com | Free, cite the authors |
| LME copper and aluminium (cash, 3-month, stocks) | LME via Westmetall, provided with the challenge | Licensed: not redistributed |
| MEPS and CRU steel prices | Provided by Schneider | Licensed, confidential: not redistributed, not a forecast target |
| Epoxy resin prices | Provided by Schneider | Confidential: only its relative change is published |
| Bill of materials, RMU price benchmark (synthetic), teardown benchmark | Provided by Schneider | Confidential: not committed |

**Models and packages** (all open source; versions pinned in `uv.lock` and `requirements.txt`):

| Package | Used for | Licence |
|---|---|---|
| pandas, NumPy, SciPy, scikit-learn, statsmodels | Data, quantile regression, tests | BSD-3-Clause |
| statsforecast | AutoETS, AutoARIMA, AutoTheta | Apache-2.0 |
| arch | GARCH and GJR-GARCH | NCSA |
| matplotlib | Charts | PSF-based (matplotlib licence) |
| requests, openpyxl, PyYAML, xlrd | Downloads, Excel and config files | Apache-2.0, MIT, MIT, BSD |
| Chronos-Bolt small (`amazon/chronos-bolt-small`, pinned revision), optional | Pretrained candidate model, not in the final forecast | Apache-2.0 |

## Data limits

- **Short history:** about 119 months per series, so 38 backtest and 18 hold-out origins per series and horizon, which overlap. Most differences between models are within noise.
- **Proxies, not purchase prices:** producer price indices and exchange prices stand in for what Schneider actually pays.
- **Revised data:** producer price indices are today's values, not the first releases a buyer saw at the time.
- **One regime in the hold-out:** a copper rally and calm steel. Copper ended above its 9-month P90 in 35–41 % of hold-out cases, against a 10 % target.
- **Bill of materials:** copper mass in RM6 differs between Schneider's bill of materials (38.8 kg) and the teardown benchmark (8.6–13.8 kg); we use Schneider's. Only the 3-function IQI configuration is modelled.
- **Not forecast:** electronics (no price series in the data) and the licensed MEPS / CRU steel prices.
- **Selling prices are synthetic** (Schneider benchmark), with no AirSeT price.

## Compute and CO₂

Measured on a laptop CPU (8-core CPU, 10-core GPU unused, 8 GB memory), with energy = run time × 20 W ([step 7, §7](report/problem1/step7_evaluation.md)):

- **The full pipeline:** about 5 minutes, ≈ 1.6 Wh, ≈ 0.1 g CO₂ on the French grid (≈ 0.4 g at the EU average).
- **All 9 models' full backtest:** 3.2 minutes, 1.1 Wh. The full leakage test suite: about 11 minutes, 3.7 Wh.

## AI tools

- **Coding assistant:** Claude Code (Anthropic), used to write and review code, run analyses and draft reports. Every number in the reports comes from code in this repo, and every external fact in Problem 2 is sourced and was checked.
- **Pretrained model:** Chronos-Bolt was tested as a candidate (Step 6) and is not in the final forecast.

## Repository

| Folder | Content |
|---|---|
| `src/` | All code: data preparation, cost model, features, baselines, models, evaluation, submission, pipeline; Problem 2 market evidence and scoring |
| `tests/` | Leakage tests (poisoned future), formula checks, submission format |
| `report/` | Step-by-step reports and their tables, Problem 1 and Problem 2 |
| `plots/` | Every chart in the reports |
| `analysis/` | Notebooks that display the tables and charts |
| `configs/` | Settings (horizons, paths, feature definitions) |
| `market_evidence/` | Problem 2 sourced facts (one row per fact, with source and link) |
| `submissions/` | The forecast CSV |

Step-by-step setup (installing uv, placing the data, running each step, troubleshooting) and how to propose a change: [`CONTRIBUTING.md`](CONTRIBUTING.md).
