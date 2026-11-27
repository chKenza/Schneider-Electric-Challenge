"""Step 5 – baseline forecasts for every material target at H = 3, 6, 9 months.

Run from the repo root, after src.data_prep, src.external_data and src.features:

    uv run python -m src.baselines

Every baseline predicts the P10 / P50 / P90 of y = log(P[o+H]) - log(P[o]), the same
target and timing as the Step 4 feature tables (Data/processed/features/<target>_h<H>.csv).

Baselines
    random_walk     P50 = 0 (price stays where it is); band = spread of past H-month changes
                    around their median, centred on 0
    drift           P50 = mean of past H-month changes; same band, centred on the drift
    hist_quantiles  P10 / P50 / P90 = quantiles of past H-month changes (Step 4's
                    "no feature" model)
    lme_forward     LME copper / aluminium only, H = 3 only: P50 = log(3-month price / cash)
                    at the origin; band = quantiles of past forward errors
    features_qr     linear quantile regression on the features Step 4 selected for that
                    target and horizon (report/problem1/step4_tables/selected_features.csv);
                    equal to hist_quantiles where Step 4 kept no feature

Backtest (rolling origin, expanding window)
    At each evaluation origin T, a model is fitted only on origins o whose outcome was
    known at T (o + H <= T), and refitted every month. Features are standardised with
    training-window statistics only (src.feature_selection._fit). The first evaluation
    origin is `min_train_months` after the first row, as in Step 4.
    All models of a target x horizon are scored on the same origins.
    Windows:  backtest  target month <= select_end (2025-03), the Step 4 selection window
              holdout   target month after select_end (Apr 2025 -> Sep 2026)

Outputs
    Data/processed/baselines/predictions.csv   one row per target, H, model, origin
    report/problem1/step5_tables/metrics.csv   pinball, MAE, RMSE, coverage, skill vs RW
    report/problem1/step5_tables/live_forecast_202609.csv   forecasts at the Sep 2026 origin
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import REPO_ROOT
from src.data_prep import ORIGIN_MONTH, OUT
from src.feature_selection import _fit, _predict, load_tables
from src.features import info_set, load_config, load_inputs

PRED_DIR = OUT / "baselines"
TABLE_DIR = REPO_ROOT / "report" / "problem1" / "step5_tables"
SELECTED_FILE = REPO_ROOT / "report" / "problem1" / "step4_tables" / "selected_features.csv"

# Target -> (LME 3-month price, LME cash price), same currency as the target.
FORWARD = {
    "S01": ("LME_CU_3M_USD", "LME_CU_CASH_USD"),
    "D01": ("LME_CU_3M_EUR", "LME_CU_CASH_EUR"),
    "S02": ("LME_AL_3M_USD", "LME_AL_CASH_USD"),
    "D02": ("LME_AL_3M_EUR", "LME_AL_CASH_EUR"),
}
FORWARD_H = 3  # the LME file only has a 3-month price
MIN_PAST = 12  # fewest past outcomes needed to estimate a band

MODELS = ["random_walk", "drift", "hist_quantiles", "lme_forward", "features_qr"]


# --------------------------------------------------------------------------- inputs
def load_selected() -> dict[tuple[str, int], list[str]]:
    """Step 4 selected features per (target, horizon); [] where none was kept."""
    sel = pd.read_csv(SELECTED_FILE)
    out = {}
    for r in sel.itertuples():
        feats = [] if str(r.selected).startswith("(none") else [f.strip() for f in r.selected.split(",")]
        out[(r.target, int(r.horizon))] = feats
    return out


def forward_premium(inputs, cfg: dict, target: str, origins: pd.Index) -> pd.Series:
    """log(3-month / cash) at each origin, using only LME data known at that origin."""
    fwd, cash = FORWARD[target]
    gap = cfg["settings"]["quote_gap_months"]
    vals = {}
    for o in origins:
        known = info_set(inputs, o, gap)
        f, c = known[fwd].get(o), known[cash].get(o)
        vals[o] = np.log(f / c) if pd.notna(f) and pd.notna(c) and c > 0 else np.nan
    return pd.Series(vals, name="fwd_premium")


# --------------------------------------------------------------------------- baselines
def _spread(y: np.ndarray, qs: list[float]) -> np.ndarray:
    """Quantiles of past changes minus their median: the band shape, centred on 0."""
    return np.quantile(y, qs) - np.median(y)


def predict(model: str, train: pd.DataFrame, row: pd.Series, qs: list[float],
            feats: list[str], alpha_rel: float) -> np.ndarray | None:
    """P10 / P50 / P90 of one model at one origin, or None if it cannot forecast there."""
    y = train["y"].to_numpy(float)
    if len(y) < MIN_PAST:
        return None
    if model == "random_walk":
        return 0.0 + _spread(y, qs)
    if model == "drift":
        return y.mean() + _spread(y, qs)
    if model == "hist_quantiles":
        return np.quantile(y, qs)
    if model == "lme_forward":
        if "fwd_premium" not in train or pd.isna(row.get("fwd_premium")):
            return None
        err = (train["y"] - train["fwd_premium"]).dropna().to_numpy(float)
        if len(err) < MIN_PAST:
            return None
        return row["fwd_premium"] + np.quantile(err, qs)
    if model == "features_qr":
        if not feats:
            return np.quantile(y, qs)
        tr = train.dropna(subset=feats)
        x = row[feats].to_numpy(float)
        if len(tr) < MIN_PAST or np.isnan(x).any():
            return None
        fitted = _fit(tr[feats].to_numpy(float), tr["y"].to_numpy(float), qs, alpha_rel)
        return _predict(fitted, x)
    raise ValueError(model)


def run_cell(df: pd.DataFrame, target: str, h: int, feats: list[str], cfg: dict) -> pd.DataFrame:
    """Rolling-origin predictions of every model for one target x horizon, plus the live row."""
    qs, alpha_rel = cfg["selection"]["quantiles"], cfg["selection"]["alpha_rel"]
    first_eval = df.index[0] + pd.DateOffset(months=cfg["selection"]["min_train_months"])
    known_y = df[df["y"].notna()]
    evals = list(known_y.index[known_y.index >= first_eval])
    live = df.index[-1]  # last origin: Sep 2026, y unknown
    models = [m for m in MODELS if m != "lme_forward" or (target in FORWARD and h == FORWARD_H)]
    rows = []
    for T in evals + ([live] if live not in evals else []):
        train = known_y[known_y["target_month"] <= T]
        row = df.loc[T]
        for m in models:
            p = predict(m, train, row, qs, feats, alpha_rel)
            if p is None:
                continue
            p = np.sort(p)
            rows.append({"target": target, "horizon": h, "model": m, "origin": T,
                         "target_month": row["target_month"], "y": row["y"],
                         "p10": p[0], "p50": p[1], "p90": p[2], "n_train": len(train)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- scoring
def _pinball(y: np.ndarray, p: np.ndarray, qs: list[float]) -> np.ndarray:
    """Mean pinball loss over the quantiles, per origin."""
    d = y[:, None] - p
    q = np.asarray(qs)[None, :]
    return np.maximum(q * d, (q - 1) * d).mean(axis=1)


def score(pred: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Metrics per target x horizon x model x window, on origins common to all models."""
    qs = cfg["selection"]["quantiles"]
    end = pd.Timestamp(cfg["selection"]["select_end"])
    past = pred[pred["y"].notna()].copy()
    past["window"] = np.where(pd.to_datetime(past["target_month"]) <= end, "backtest", "holdout")
    rows = []
    for (t, h, w), g in past.groupby(["target", "horizon", "window"]):
        models = g["model"].unique()
        counts = g.groupby("origin")["model"].nunique()
        common = counts.index[counts == len(models)]
        g = g[g["origin"].isin(common)]
        res = {}
        for m, gm in g.groupby("model"):
            y = gm["y"].to_numpy()
            p = gm[["p10", "p50", "p90"]].to_numpy()
            e = y - p[:, 1]
            res[m] = {"target": t, "horizon": h, "window": w, "model": m, "n": len(gm),
                      "pinball": 100 * _pinball(y, p, qs).mean(),
                      "mae": 100 * np.abs(e).mean(), "rmse": 100 * np.sqrt((e ** 2).mean()),
                      "bias": 100 * e.mean(),
                      "coverage_80": ((y >= p[:, 0]) & (y <= p[:, 2])).mean(),
                      "width_80": 100 * (p[:, 2] - p[:, 0]).mean()}
        rw = res["random_walk"]
        for r in res.values():
            r["pinball_skill_vs_rw"] = 1 - r["pinball"] / rw["pinball"]
            r["mae_skill_vs_rw"] = 1 - r["mae"] / rw["mae"]
            rows.append(r)
    return pd.DataFrame(rows)


def live_forecast(pred: pd.DataFrame) -> pd.DataFrame:
    """Forecasts at the last origin, as price indices (origin = 100)."""
    last = pred["origin"].max()
    live = pred[pred["origin"] == last].copy()
    for c in ["p10", "p50", "p90"]:
        live[f"index_{c}"] = 100 * np.exp(live[c])
    live[["index_p10", "index_p50", "index_p90"]] = live[["index_p10", "index_p50", "index_p90"]].round(1)
    return live[["target", "horizon", "model", "origin", "target_month",
                 "index_p10", "index_p50", "index_p90", "n_train"]]


# --------------------------------------------------------------------------- main
def run() -> dict[str, pd.DataFrame]:
    cfg = load_config()
    inputs = load_inputs()
    tables = load_tables(cfg)
    selected = load_selected()
    preds = []
    for (t, h), df in tables.items():
        df = df.copy()
        if t in FORWARD and h == FORWARD_H:
            df["fwd_premium"] = forward_premium(inputs, cfg, t, df.index)
        preds.append(run_cell(df, t, h, selected.get((t, h), []), cfg))
    pred = pd.concat(preds, ignore_index=True)
    return {"predictions": pred, "metrics": score(pred, cfg), "live": live_forecast(pred)}


def main() -> None:
    out = run()
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out["predictions"].to_csv(PRED_DIR / "predictions.csv", index=False)
    out["metrics"].round(4).to_csv(TABLE_DIR / "metrics.csv", index=False)
    out["live"].to_csv(TABLE_DIR / f"live_forecast_{ORIGIN_MONTH.replace('-', '')}.csv", index=False)
    m = out["metrics"]
    summary = (m.groupby(["window", "horizon", "model"])
               [["pinball", "pinball_skill_vs_rw", "mae_skill_vs_rw", "coverage_80"]].mean().round(3))
    print(summary.to_string())


if __name__ == "__main__":
    main()
