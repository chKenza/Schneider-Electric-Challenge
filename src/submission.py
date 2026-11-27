"""Step 12 – the forecast CSV for the jury (slide 17): build it and validate it.

Run from the repo root, after src.models and src.simulation (it reads their saved outputs):

    uv run python -m src.submission              # build + validate submissions/group_6_forecast_202609.csv
    uv run python -m src.submission --check-only # validate the existing file

Format (slide 17), one row per target x horizon:
    team_id, target_type (material | bom_index), target_id, region (EU | WW),
    origin_month (YYYY-MM), horizon_m (3 | 6 | 9), target_month (YYYY-MM),
    unit (EUR/t | index (origin=100)), p10, p50, p90, model_name, ai_tools

Material rows come from the final Step 6 model (`models.FINAL_MODEL`) at the live origin.
The model forecasts the H-month log change q, so a level is P_origin x exp(q):
    - EUR/t   for the public EUR series (D01 copper, D02 aluminium: LME converted to EUR);
    - index (origin=100) = 100 x exp(q) for everything else: PPIs, USD-priced LME series
      (no FX forecast needed) and epoxy (its EUR/t level is Schneider-confidential, so the
      CSV gives only its relative change).
BOM index rows (RM6, RM AirSeT) come from the Step 8 joint simulation (src.simulation): the
P10 / P50 / P90 of each product's raw-material cost index (Sep 2026 = 100) over 10,000 joint
price paths, each material rescaled to the final model's forecast. Cases and steel as
backtested in Step 7 (section 6.1): the client BOM v1 ("RM6", "AirSeT"), stainless moved by
the S09 steel PPI, and steel at producer prices (PPI), the series the CSV forecasts.
Target ids are the client's product references (RM_Prices_XHEC_Challenge.xlsx, BOM_Materials).
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from src.config import REPO_ROOT
from src.data_prep import ORIGIN_MONTH, OUT
from src.models import FINAL_MODEL, MODEL_DIR

TEAM_ID = "group_6"
ORIGIN = pd.Timestamp(ORIGIN_MONTH)  # 2026-09, or SE_ORIGIN for a monthly update
HORIZONS = (3, 6, 9)
AI_TOOLS = "claude-code"  # coding assistant; no pretrained model is in the final forecast
SUBMISSION_DIR = REPO_ROOT / "submissions"
SUBMISSION = SUBMISSION_DIR / f"{TEAM_ID}_forecast_{ORIGIN:%Y%m}.csv"

COLUMNS = ["team_id", "target_type", "target_id", "region", "origin_month", "horizon_m",
           "target_month", "unit", "p10", "p50", "p90", "model_name", "ai_tools"]
EUR_T, INDEX = "EUR/t", "index (origin=100)"
EUR_LEVEL_TARGETS = {"D01", "D02"}  # public EUR/t series published as price levels

# The 15 material targets and their region, as in the Step 1 data dictionary. Kept here so
# the committed CSV can be checked without Data/ (in CI); when Data/ is present the data
# dictionary is used, and a test checks the two agree.
MATERIAL_TARGETS = {
    "D01": "EU", "D02": "EU", "EPOXY_EUR": "EU", "S07": "EU", "S08": "EU", "S09": "EU",
    "S10": "EU", "S11": "EU",
    "S01": "WW", "S02": "WW", "S03": "WW", "S04": "WW", "S05": "WW", "S12": "WW", "S13": "WW",
}

# BOM index rows: Step 8 case -> client product reference (BOM_Materials.product_ref)
BOM_TARGETS = {"RM6": "RM6_NE_IQI_433520", "AirSeT": "RMAirSeT IIQ 24kV IEC"}
BOM_STEEL = "PPI"     # steel at producer prices: S09 / S10, the steel series the CSV forecasts
BOM_REGION = "EU"     # both plants are in the EU (France, Hungary); EU price series
BOM_FILE = OUT / "bom_index_simulated.csv"  # written by src.simulation (Step 8)
BOM_MODEL = f"{FINAL_MODEL}+step8_joint_simulation"


def material_targets() -> pd.DataFrame:
    """The forecast targets of Step 1 (data dictionary), with their region. Without Data/
    (e.g. in CI), the committed list MATERIAL_TARGETS."""
    path = OUT / "data_dictionary.csv"
    if not path.exists():
        return pd.DataFrame({"target_region": MATERIAL_TARGETS}).rename_axis("series_id")
    d = pd.read_csv(path, index_col=0)
    d = d[d["forecast_target"].astype(str) == "True"]
    return d[["target_region", "unit"]]


def material_rows(model: str = FINAL_MODEL) -> pd.DataFrame:
    """Material rows of the CSV from the model's predictions at the live origin."""
    preds = pd.read_csv(MODEL_DIR / f"predictions_{model}.csv", parse_dates=["origin", "target_month"])
    live = preds[preds["origin"] == preds["origin"].max()]
    if live["origin"].iloc[0] != ORIGIN:
        raise ValueError(f"latest origin in predictions_{model}.csv is {live['origin'].iloc[0]:%Y-%m}, "
                         f"expected {ORIGIN:%Y-%m}: re-run src.models on the current data")
    targets = material_targets()
    panel = pd.read_csv(OUT / "panel_monthly.csv", index_col="month", parse_dates=["month"])

    rows = []
    for r in live.itertuples():
        if r.target not in targets.index:
            raise ValueError(f"{r.target} is predicted but is not a forecast target in the data dictionary")
        if r.target in EUR_LEVEL_TARGETS:
            base, unit, digits = panel.loc[ORIGIN, r.target], EUR_T, 1
        else:
            base, unit, digits = 100.0, INDEX, 2
        q = base * np.exp([r.p10, r.p50, r.p90])
        rows.append({
            "team_id": TEAM_ID, "target_type": "material", "target_id": r.target,
            "region": targets.loc[r.target, "target_region"],
            "origin_month": f"{r.origin:%Y-%m}", "horizon_m": int(r.horizon),
            "target_month": f"{r.target_month:%Y-%m}", "unit": unit,
            "p10": round(q[0], digits), "p50": round(q[1], digits), "p90": round(q[2], digits),
            "model_name": model, "ai_tools": AI_TOOLS,
        })
    return pd.DataFrame(rows, columns=COLUMNS).sort_values(["target_id", "horizon_m"]).reset_index(drop=True)


def bom_rows() -> pd.DataFrame:
    """BOM cost index rows of the CSV, from the Step 8 joint simulation (index, origin = 100)."""
    if not BOM_FILE.exists():
        raise FileNotFoundError(f"{BOM_FILE} not found: run src.simulation (Step 8) first")
    sim = pd.read_csv(BOM_FILE)
    sim = sim[sim["case"].isin(list(BOM_TARGETS)) & (sim["steel"] == BOM_STEEL)]
    rows = []
    for case, target_id in BOM_TARGETS.items():
        for h in HORIZONS:
            r = sim[(sim["case"] == case) & (sim["horizon_m"] == h)]
            if len(r) != 1:
                raise ValueError(f"{BOM_FILE.name}: expected one row for {case}, steel {BOM_STEEL}, "
                                 f"{h} months; found {len(r)}")
            r = r.iloc[0]
            rows.append({
                "team_id": TEAM_ID, "target_type": "bom_index", "target_id": target_id,
                "region": BOM_REGION, "origin_month": f"{ORIGIN:%Y-%m}", "horizon_m": h,
                "target_month": f"{ORIGIN + pd.DateOffset(months=h):%Y-%m}", "unit": INDEX,
                "p10": round(float(r.index_p10), 2), "p50": round(float(r.index_p50), 2),
                "p90": round(float(r.index_p90), 2), "model_name": BOM_MODEL, "ai_tools": AI_TOOLS,
            })
    return pd.DataFrame(rows, columns=COLUMNS)


def validate(df: pd.DataFrame) -> list[str]:
    """Every rule of slide 17 that can be checked; returns the problems (empty = valid)."""
    errs: list[str] = []
    if list(df.columns) != COLUMNS:
        return [f"columns must be exactly {COLUMNS}, got {list(df.columns)}"]
    if df.isna().any().any():
        errs.append(f"missing values in: {sorted(df.columns[df.isna().any()])}")
    checks = {
        "team_id": df["team_id"] == TEAM_ID,
        "target_type": df["target_type"].isin(["material", "bom_index"]),
        "region": df["region"].isin(["EU", "WW"]),
        "origin_month": df["origin_month"] == f"{ORIGIN:%Y-%m}",
        "horizon_m": df["horizon_m"].isin(HORIZONS),
        "unit": df["unit"].isin([EUR_T, INDEX]),
        "bom_index unit": (df["target_type"] != "bom_index") | (df["unit"] == INDEX),
        "p10 <= p50 <= p90": (df["p10"] <= df["p50"]) & (df["p50"] <= df["p90"]),
        "positive values": df[["p10", "p50", "p90"]].gt(0).all(axis=1),
    }
    expected_month = [f"{ORIGIN + pd.DateOffset(months=int(h)):%Y-%m}" if h in HORIZONS else None
                      for h in df["horizon_m"]]
    checks["target_month = origin + horizon"] = df["target_month"] == expected_month
    for name, ok in checks.items():
        if not ok.all():
            errs.append(f"{name}: {int((~ok).sum())} bad row(s), e.g. {df.loc[~ok, 'target_id'].iloc[0]}")
    dup = df.duplicated(["target_type", "target_id", "horizon_m"])
    if dup.any():
        errs.append(f"duplicate rows: {df.loc[dup, 'target_id'].tolist()}")

    mat = df[df["target_type"] == "material"]
    targets = material_targets()
    have = set(zip(mat["target_id"], mat["horizon_m"], strict=True))
    missing = [f"{t}@{h}" for t in targets.index for h in HORIZONS if (t, h) not in have]
    if missing:
        errs.append(f"missing material rows: {missing}")
    unknown = sorted(set(mat["target_id"]) - set(targets.index))
    if unknown:
        errs.append(f"material rows that are not forecast targets: {unknown}")
    wrong_region = mat[mat["region"] != mat["target_id"].map(targets["target_region"])]
    if len(wrong_region):
        errs.append(f"region differs from the data dictionary: {wrong_region['target_id'].unique().tolist()}")

    bom = df[df["target_type"] == "bom_index"]
    have = set(zip(bom["target_id"], bom["horizon_m"], strict=True))
    missing = [f"{t}@{h}" for t in BOM_TARGETS.values() for h in HORIZONS if (t, h) not in have]
    if missing:
        errs.append(f"missing bom_index rows: {missing}")
    unknown = sorted(set(bom["target_id"]) - set(BOM_TARGETS.values()))
    if unknown:
        errs.append(f"bom_index rows that are not RM6 / RM AirSeT: {unknown}")
    return errs


def build(out=SUBMISSION) -> pd.DataFrame:
    df = pd.concat([material_rows(), bom_rows()], ignore_index=True)
    errs = validate(df)
    if errs:
        raise ValueError("submission is invalid:\n  " + "\n  ".join(errs))
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check-only", action="store_true", help="validate the existing file, do not rebuild it")
    args = ap.parse_args()
    if args.check_only:
        problems = validate(pd.read_csv(SUBMISSION))
        print("\n".join(problems) if problems else f"{SUBMISSION.relative_to(REPO_ROOT)}: valid")
        raise SystemExit(1 if problems else 0)
    df = build()
    print(f"Wrote {SUBMISSION.relative_to(REPO_ROOT)}: {len(df)} rows, valid")
    print(df.drop(columns=["team_id", "origin_month", "model_name", "ai_tools"]).to_string(index=False))
