# Schneider Electric × X-HEC Data Challenge 2026

[![CI](https://github.com/chKenza/Schneider-Electric-Challenge/actions/workflows/ci.yml/badge.svg)](https://github.com/chKenza/Schneider-Electric-Challenge/actions/workflows/ci.yml)

Raw-material price risk on fixed-price offers for medium-voltage ring main units (RM6 and the SF6-free RM AirSeT), and the go-to-market strategy for SF6-free switchgear where no regulation forces it.

- **Problem 1:** forecast raw-material prices 3, 6 and 9 months ahead, with P10 / P50 / P90, and turn them into a quote rule. Reports: [`report/problem1/`](report/problem1/).
- **Problem 2:** where and how to sell RM AirSeT without an SF6 ban. Reports: [`report/problem2/`](report/problem2/).
- **Forecast submission:** [`submissions/group_6_forecast_202609.csv`](submissions/group_6_forecast_202609.csv): 15 materials and the RM6 / RM AirSeT cost index, 3 / 6 / 9 months.
- **Decision tool:** a Streamlit app that turns the forecasts into quote terms (`make app`, see [How to run](#how-to-run)).

## Approach (Problem 1)

1. **Data** ([report](report/problem1/step1_data_preparation.md)): one monthly panel, Nov 2016 → Sep 2026, with each series' publication lag, so a forecast only uses what was published at the time.
2. **Cost model** ([report](report/problem1/step2_cost_model.md)): raw-material cost of one unit = Σ kg × price, from Schneider's corrected bill of materials (v1): RM6 €931 (copper 52 %), RM AirSeT €941 (copper 38 %, steel and stainless 52 %), Sep 2026.
3. **Features** ([report](report/problem1/step4_features.md)): free public drivers (energy, supply-chain pressure, policy uncertainty, carbon price, EIA forecasts), each proven to be known at forecast time.
4. **Models** ([report](report/problem1/step6_models.md)): 9 probabilistic models for the 15 material series. The final model, `conformal_combo`, is an equal-weight combination of four volatility and statistical models, plus the public drivers where they help, calibrated by adaptive conformal prediction.
5. **Evaluation** ([report](report/problem1/step7_evaluation.md)): rolling-origin backtest against the random walk (the naive baseline), then a hold-out (Apr 2025 → Sep 2026) frozen and opened once.
6. **Product cost and margin at risk** ([report](report/problem1/step8_simulation.md)): 10,000 joint price paths, each material matching its forecast, pushed through the bill of materials. A 9-month fixed price risks up to **2.1 margin points** on RM6 and **1.8** on RM AirSeT at 90 % confidence (steel at market prices).
7. **Quote rule** ([report](report/problem1/step9_pricing.md); the full story and recommendations are in the [story report](report/problem1/step10_story.md)): up to 6 months, a fixed price plus a small uplift (≤ 1 point); 9 months, an indexation clause (copper for RM6; copper, steel and stainless for RM AirSeT) plus an uplift of 0.8–1.0 points.

**Result against the naive baseline:**

| Horizon | Backtest skill (pinball loss) | Hold-out skill | Hold-out coverage of P10–P90 (target 80 %) |
|---|---|---|---|
| 3 months | **+4.3 %** (significant) | +2.5 % | 84 % |
| 6 months | **+7.0 %** (significant) | −0.5 % | 80 % |
| 9 months | **+10.7 %** (significant) | +0.8 % | 82 % |

The backtest beats the random walk at every horizon. The hold-out matches it: the median is no better than "no change", and the gain is in the band, which keeps the right coverage while being 20–33 % narrower than the random walk's for producer price indices and epoxy.

## Approach (Problem 2)

Where SF6 is not banned, how to win the voluntary switch from RM6 to RM AirSeT, profitably ([framing](report/problem2/00_problem_framing.md)):

1. **Markets and regulation** ([01](report/problem2/01_market_and_regulation.md)): sourced facts in [`market_evidence/`](market_evidence/) (one row per fact, with source and date), and a scored ranking of regions × segments.
2. **Cost gap and TCO** ([02](report/problem2/02_cost_and_tco.md)): raw materials explain 0.5 % of AirSeT's €1,921 premium, and the forecast barely moves that gap to mid-2027. On lifetime cost AirSeT wins only if the customer counts the whole SF6 fill (35 t CO₂e per unit) as a liability: that supports a premium of ≈ 9 %, not 22 %.
3. **Value proposition and pricing** ([03](report/problem2/03_value_and_pricing.md)): a TCO-based price per segment. Whether it is profitable depends on AirSeT's extra unit cost compared with RM6.
4. **Roadmap and win conditions** ([04](report/problem2/04_strategy.md)): Australia colocation and Johor–Singapore (with AirTrunk as lead customer) first, the Gulf as a volume market; each segment opens below an extra-cost threshold. Problem 1 links in through the indexation clause, which protects the margin on the sharper AirSeT price.

## How to run

Requirements: Python 3.12 and [uv](https://docs.astral.sh/uv/).

1. **Put the challenge files in `Data/`** at the root of the repo (not committed: see [Data and licences](#data-and-licences); the expected layout is in [`CONTRIBUTING.md`](CONTRIBUTING.md), section 3).

2. **One command from the raw data to the forecast CSV** (about 5 minutes; the first run needs internet to download the free external data, then it is cached):
   ```bash
   uv run python -m src.pipeline   # or: make forecast
   ```
   It runs data preparation → external data → features → baselines → models → cost model → joint simulation → CSV, then validates the CSV against the submission format. `--list` prints the stages; `--from models` resumes from a stage. `make help` lists the other shortcuts (`make check`, `make test`, `make app`).
3. **Tests** (leakage and format checks; the leakage tests re-run every model, so this takes 10–15 minutes; `make test-fast` runs the quick ones in seconds):
   ```bash
   uv run pytest tests/
   ```
4. **Decision tool** (after the pipeline): pick a product, a quote validity and the loss you accept, and read the recommended quote terms (uplift, indexation clause), with the analysis behind them and the RM AirSeT pricing window.
   ```bash
   uv run streamlit run app/streamlit_app.py   # or: make app, then open http://localhost:8501
   ```
5. **Problem 2 tables and charts:** `make problem2` (after the pipeline, whose outputs it reads).

Without uv: `pip install -r requirements.txt` (pinned versions, exported from `uv.lock`, including the app's Streamlit and Plotly), then `python -m src.pipeline`.

**Reproducibility:** every model is deterministic or seeded, including the joint price simulation (seed 42). From a clean start (no processed data), the pipeline rebuilds a CSV byte-identical to the committed one: checked twice in a row on 26 Nov 2026. The optional pretrained model Chronos is not in the final forecast, so the CSV is the same with or without it; `uv run --extra chronos python -m src.pipeline` also reproduces the model comparison tables exactly.

**GitHub Actions** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs on every push and pull request: lint, every test that needs no confidential data, and the format check of the committed CSV, which it publishes as an artifact. The full pipeline can't run there, because `Data/` is not in the repo; tests that need it skip themselves.

## The forecast CSV

Format : one row per target × horizon, origin September 2026, horizons 3 / 6 / 9 months (Dec 2026, Mar 2027, Jun 2027), P10 / P50 / P90.

- **15 material series:** copper and aluminium (EU in EUR, global LME), nickel, iron ore, zinc, EU and US producer price indices for steel, copper, aluminium and plastics, and epoxy resin.
- **Units:** EUR/t for copper and aluminium in EUR (D01, D02). Index (origin = 100) for the others: producer price indices, USD-priced series (no exchange-rate forecast needed) and epoxy, whose EUR/t level is Schneider-confidential.
- **BOM cost index for RM6 (`RM6_NE_IQI_433520`) and RM AirSeT (`RMAirSeT IIQ 24kV IEC`),** index (origin = 100): the raw-material cost of one unit from the client's corrected bill of materials, simulated jointly over 10,000 price paths with each material matching its forecast ([simulation report](report/problem1/step8_simulation.md)). Steel is at producer prices (S09 / S10), the case backtested in the [evaluation report, §6.1](report/problem1/step7_evaluation.md).

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
| MEPS and CRU steel prices | Provided by Schneider | Confidential, Licensed |
| Epoxy resin prices | Provided by Schneider | Confidential |
| Bill of materials, RMU price benchmark (synthetic), teardown benchmark | Provided by Schneider | Confidential |
| Problem 2 market facts (regulation, data-centre markets, operators' commitments, competitors) | Public reports, regulations and company publications, listed in [`market_evidence/evidence.csv`](market_evidence/evidence.csv) | Quoted with source and date, not redistributed |

**Models and packages** (all open source; versions pinned in `uv.lock` and `requirements.txt`):

| Package | Used for | Licence |
|---|---|---|
| pandas, NumPy, SciPy, scikit-learn, statsmodels | Data, quantile regression, tests | BSD-3-Clause |
| statsforecast | AutoETS, AutoARIMA, AutoTheta | Apache-2.0 |
| arch | GARCH and GJR-GARCH | NCSA |
| matplotlib | Charts | PSF-based (matplotlib licence) |
| Streamlit, Plotly | Decision tool (app) | Apache-2.0, MIT |
| requests, openpyxl, PyYAML, xlrd | Downloads, Excel and config files | Apache-2.0, MIT, MIT, BSD |
| Chronos-Bolt small (`amazon/chronos-bolt-small`, pinned revision), optional | Pretrained candidate model, not in the final forecast | Apache-2.0 |

## Data limits

- **Short history:** about 119 months per series, so 38 backtest and 18 hold-out origins per series and horizon, which overlap. Most differences between models are within noise.
- **Proxies, not purchase prices:** producer price indices and exchange prices stand in for what Schneider actually pays.
- **Revised data:** producer price indices are today's values, not the first releases a buyer saw at the time.
- **One regime in the hold-out:** a copper rally and calm steel. Copper ended above its 9-month P90 in 35–41 % of hold-out cases, against a 10 % target.
- **Not forecast:** electronics (no price series in the data) and the licensed MEPS / CRU steel prices.
- **Selling prices are synthetic** (Schneider benchmark), with no AirSeT price: RM AirSeT is assumed at RM6 + 20 %, and its extra unit cost vs RM6 (10 %) is a placeholder that every Problem 2 threshold is shown against.
- **Purchase timing is not modelled:** material is assumed bought at the end of the quote's validity, which overstates the exposure if Schneider buys earlier.

## Compute and CO₂

Measured on a laptop CPU (8-core CPU, 10-core GPU unused, 8 GB memory), with energy = run time × 20 W ([evaluation report, §7](report/problem1/step7_evaluation.md)):

- **The full pipeline:** about 5 minutes (4.6 measured, of which 10 s for the joint price simulation), ≈ 1.6 Wh, ≈ 0.1 g CO₂ on the French grid (≈ 0.4 g at the EU average).
- **All 9 models' full backtest:** 3.2 minutes, 1.1 Wh. The full leakage test suite: about 11 minutes, 3.7 Wh.

## AI tools

- **Coding assistant:** Claude Code (Anthropic) helped in writing and reviewing code, running analyses and drafting reports.
- **Pretrained model:** Chronos-Bolt was tested as a candidate model and is not in the final forecast.
- Every number in the reports comes from code in this repo, and every external fact in Problem 2 is sourced and was checked.

## Repository

| Folder | Content |
|---|---|
| `src/` | All code: data preparation, cost model, features, baselines, models, evaluation, simulation, pricing, story, submission, pipeline; Problem 2 market evidence, scoring, TCO, pricing window and strategy |
| `app/` | The Streamlit decision tool (theme in `.streamlit/`) |
| `tests/` | Leakage tests (poisoned future), formula checks, submission format |
| `report/` | Reports and their tables, Problem 1 and Problem 2 |
| `plots/` | Every chart in the reports |
| `analysis/` | Notebooks that display the tables and charts |
| `configs/` | Settings (horizons, paths, feature definitions) |
| `market_evidence/` | Problem 2 sourced facts (one row per fact, with source and link) |
| `submissions/` | The forecast CSV |
| `Makefile` | Shortcuts for the commands above (`make help`) |
| `.github/workflows/` | GitHub Actions: lint, tests, CSV check and artifact |

Detailed setup (installing uv, placing the data, running each module, troubleshooting) and how to propose a change: [`CONTRIBUTING.md`](CONTRIBUTING.md).
