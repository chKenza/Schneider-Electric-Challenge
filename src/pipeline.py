"""Step 12 – one command from the raw data to the forecast CSV.

Run from the repo root:

    uv run python -m src.pipeline                   # every stage, then the CSV
    uv run --extra chronos python -m src.pipeline   # same, with the Chronos candidate model
    uv run python -m src.pipeline --from models     # resume from a stage
    uv run python -m src.pipeline --list            # print the stages

Each stage is the documented command of its step, run as its own process (the same
`python -m src.<module>` a teammate would type), so the pipeline adds no logic of its own:

    data_prep      Step 1   raw files in Data/ -> cleaned monthly panel, publication lags
    external_data  Step 4   free external drivers (internet on the first run, then cached)
    features       Step 4   feature tables + poisoned-future leakage test
    baselines      Step 5   naive baselines; the random walk is the reference for Step 6
    models         Step 6   base models, conformal calibration, combination, Step 8 inputs
    cost_model     Step 2   raw-material cost of one unit per product (client BOM v1)
    simulation     Step 8   10,000 joint price paths -> BOM cost index P10 / P50 / P90
    submission     Step 12  submissions/group_6_forecast_202609.csv (material + BOM rows), validated

Not re-run, because their committed outputs are what the next steps read:
    - src.feature_selection (Step 4): report/problem1/step4_tables/selected_features.csv
    - src.models --stage holdout (Step 6): the hold-out was frozen and opened once
Evaluation (Step 7: src.evaluation) and pricing (Step 9: src.pricing) are reports, not
inputs to the CSV. The simulation also rewrites its Step 8 report tables and charts.

Inputs needed from a clean clone: the challenge files in Data/ (not committed: Schneider
data is confidential and MEPS/CRU are licensed) and internet access for external_data.
Every model is deterministic or seeded (models.SETTINGS["seed"]; the Step 8 bootstrap uses
seed 42), so the same inputs give the same CSV.

Chronos is a candidate model that the final combination does not use, so the CSV is the
same with or without it (checked from a clean start: byte-identical). Without the extra,
the Step 6 tables metrics.csv and conformal_gamma.csv are rewritten without their Chronos
rows; run with `--extra chronos` to reproduce the committed tables exactly.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

from src.config import REPO_ROOT

# (stage name, step, module + arguments)
STAGES: list[tuple[str, str, list[str]]] = [
    ("data_prep", "Step 1", ["src.data_prep"]),
    ("external_data", "Step 4", ["src.external_data"]),
    ("features", "Step 4", ["src.features"]),
    ("baselines", "Step 5", ["src.baselines"]),
    ("models", "Step 6", ["src.models"]),
    ("cost_model", "Step 2", ["src.cost_model"]),
    ("simulation", "Step 8", ["src.simulation"]),
    ("submission", "Step 12", ["src.submission"]),
]
NAMES = [s[0] for s in STAGES]


def run(start: str = NAMES[0]) -> None:
    t_all = time.perf_counter()
    for name, step, cmd in STAGES[NAMES.index(start):]:
        print(f"\n=== {name} ({step}): python -m {' '.join(cmd)}", flush=True)
        t = time.perf_counter()
        subprocess.run([sys.executable, "-m", *cmd], cwd=REPO_ROOT, check=True)
        print(f"=== {name} done in {time.perf_counter() - t:.0f} s", flush=True)
    print(f"\nPipeline finished in {(time.perf_counter() - t_all) / 60:.1f} min")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--from", dest="start", choices=NAMES, default=NAMES[0], help="first stage to run")
    ap.add_argument("--list", action="store_true", help="print the stages and exit")
    args = ap.parse_args()
    if args.list:
        for name, step, cmd in STAGES:
            print(f"{name:14s} {step:8s} python -m {' '.join(cmd)}")
        return
    try:
        run(args.start)
    except subprocess.CalledProcessError as e:
        sys.exit(f"\nPipeline stopped: stage `{' '.join(e.cmd[2:])}` failed (exit code {e.returncode}).")


if __name__ == "__main__":
    main()
