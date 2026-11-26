# Running and contributing to this repo

This guide explains how to run individual modules and propose changes. The [README](README.md) explains what the project does.

## 1. Install uv

The project uses [uv](https://docs.astral.sh/uv/) to manage Python and the packages. 

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# macOS with Homebrew
brew install uv

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Check it works: `uv --version`.

## 2. Get the code and install the packages

```bash
git clone https://github.com/chKenza/Schneider-Electric-Challenge.git
cd Schneider-Electric-Challenge
uv sync
```

`uv sync` creates a `.venv/` folder with Python 3.12 and the exact package versions pinned in `uv.lock`. Every command below starts with `uv run`, which uses that environment; you don't need to activate it.

**Optional, the pretrained model Chronos-Bolt.** It was tested as a candidate but is not in the final forecast, so you only need it to reproduce the model comparison tables exactly. It installs PyTorch:

```bash
uv sync --extra chronos
```

**Without uv:** `python3.12 -m venv .venv`, activate it, then `pip install -r requirements.txt` (add `pip install pytest ruff` to run the tests). Run the commands below from the repo root, without `uv run`.

## 3. Put the data in `Data/`

The data is **not in the repository**: part of it is confidential to Schneider Electric and part is licensed. You need the files distributed with the Schneider Electric × X-HEC challenge. Place the `Data/` folder at the root of the repository.

The other data (energy, supply-chain and policy indices, carbon price, EIA forecasts) is free and public: the pipeline downloads it on the first run into `Data/external/` and reuses that copy afterwards. **The first run needs internet access.**

## 4. Run the pipeline

One command goes from the raw data to the forecast CSV (about 5 minutes on a laptop):

```bash
uv run python -m src.pipeline   # or: make forecast
```

It runs these stages in order, printing the time of each, and stops at the first one that fails:

| Stage | What it does | Writes to |
|---|---|---|
| `data_prep` | Cleans and aligns every series into one monthly panel, with each series' publication lag | `Data/processed/` |
| `external_data` | Downloads the free external drivers (cached after the first run) | `Data/external/` |
| `features` | Builds the model features and checks none uses future data | `Data/processed/features/` |
| `baselines` | Naive forecasts; the random walk is the reference every model must beat | `Data/processed/`, `report/problem1/step5_tables/` |
| `models` | Fits every forecasting model, calibrates and combines them | `Data/processed/models/`, `report/problem1/step6_tables/` |
| `cost_model` | Raw-material cost of one RM6 and one RM AirSeT, from the client's bill of materials | `Data/processed/` |
| `simulation` | 10,000 joint price paths matching the forecasts → cost index P10 / P50 / P90 per product | `Data/processed/`, `report/problem1/step8_tables/`, `plots/step8/` |
| `submission` | Builds the forecast CSV (material and BOM index rows) and checks it against the submission format | `submissions/group_6_forecast_202609.csv` |

Useful options:

```bash
uv run python -m src.pipeline --list          # show the stages
uv run python -m src.pipeline --from models   # resume from a stage (earlier outputs must exist)
uv run python -m src.submission --check-only  # re-check the CSV without rebuilding it
```

**Shortcuts:** if `make` is installed, `make help` lists them: `make forecast` (the full pipeline), `make csv` (rebuild the CSV from the saved model outputs), `make check`, `make test`, `make test-fast`, `make app`.

## 5. Run individual modules

Each module can also be run on its own, from the repo root. The command for each report is at its top, in `report/problem1/` and `report/problem2/`.

```bash
uv run python -m src.data_prep        # monthly panel
uv run python -m src.cost_model       # raw-material cost of one unit
uv run python -m src.external_data    # external drivers
uv run python -m src.features         # feature tables
uv run python -m src.baselines        # baselines
uv run python -m src.models           # models (see --help for one model, target or horizon)
uv run python -m src.evaluation       # evaluation tables and charts (after models)
uv run python -m src.simulation       # joint simulation, BOM cost index (after models)
uv run python -m src.pricing          # quote rule and strategy comparison (after simulation)
uv run python -m src.submission       # the forecast CSV (after models and simulation)
```

## 6. Run the tests

```bash
uv run pytest tests/                    # everything, 10–15 minutes
uv run pytest tests/test_submission.py  # one file, seconds
```

The leakage tests re-run every model with the future replaced by noise and check that no forecast changes.

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `FileNotFoundError` mentioning `Data/…` | A challenge file is missing or misnamed: compare with the tree in section 3 |
| A download fails in `external_data` | Check your internet connection and run again; files already downloaded are kept |
| `--from <stage>` fails on a missing file | An earlier stage has not run on this machine: run the full pipeline once |
| The latest origin is not 2026-09 (submission stage) | The data in `Data/` is not the challenge version; the CSV is defined for the September 2026 origin |
| `uv: command not found` after installing | Open a new terminal, so your shell picks up uv |
