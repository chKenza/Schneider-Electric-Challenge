"""Step 7 – evaluation of the Step 6 forecasts (Phase A: the metric table).

Run from the repo root, after src.models (the Step 6 predictions must exist):

    uv run python -m src.evaluation

Read-only with respect to Step 6. It reads the saved predictions
(Data/processed/models/predictions_*.csv and the Step 5 baselines) and writes only to
Data/processed/evaluation/ and report/problem1/step7_tables/. It never writes into
Data/processed/models/, whose content is fingerprinted by the Step 6 hold-out freeze,
and it chooses nothing: the final model was fixed in Step 6.

Every forecast is matched with the random walk issued for the same
(target, horizon, origin), so each model is compared with the naive baseline on exactly
the same outcomes.

Windows (by target month, as in Steps 5-6):
    backtest        target month <= select_end (2025-03): where every choice was made
    holdout         target month >  select_end: opened once in Step 6
    holdout_strict  hold-out rows whose origin is >= select_end (no part of the outcome
                    window was visible when the choices were made)

Metrics (y = log(P[T+H] / P[T]); forecasts in the same units):
    point (P50)     MAE, RMSE, MAPE on the price (|P_hat / P - 1|), MAE skill vs RW,
                    MASE (scaled by the naive H-month error, see `mase_scale`). MASE < 1
                    means errors smaller than the naive's usual historical error; in a
                    calmer or more volatile test period every model's MASE moves, the
                    random walk's too. "Beats the naive on these months" is the MAE skill
                    (= model MASE vs random-walk MASE on the same rows)
    probabilistic   pinball loss over P10 / P50 / P90, its skill vs RW, CRPS
                    approximation (`crps_from_quantiles`)
    calibration     P10-P90 coverage (target 80 %), one-sided P90 coverage (target 90 %),
                    band width
    weighted        WAPE per product, each material weighted by its euro share in the
                    Step 2 recipe (copper counts for RM6, steel for AirSeT). The random
                    walk forecasts no change, so its error is |y| and its WAPE is 1 by
                    construction: WAPE skill = 1 - WAPE
    jury table      per horizon: skill with 95 % block-bootstrap CI (Step 6
                    `beats_naive`) and Diebold-Mariano test with the Harvey-Leybourne-
                    Newbold correction (`dm_hln`)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.config import REPO_ROOT
from src.data_prep import OUT
from src.features import load_config
from src.models import (
    FINAL_MODEL,
    QCOLS,
    SETTINGS,
    _block_bootstrap_ci,
    beats_naive,
    load_predictions,
)

EVAL_DIR = OUT / "evaluation"
TABLE_DIR = REPO_ROOT / "report" / "problem1" / "step7_tables"
KEY = ["target", "horizon", "origin"]
QS = np.array([0.1, 0.5, 0.9])  # the quantiles every model and the random walk share
CRPS_GRID = np.round(np.arange(0.05, 0.951, 0.05), 2)  # levels used by the CRPS approximation

# Models shown in the jury table: the final model, its main members, the alternatives
# discussed in Step 6 and the Step 5 baselines.
JURY_MODELS = ["random_walk", FINAL_MODEL, "combo", "gjr_fhs", "garch_fhs", "ewma_fhs", "features_scaled",
               "auto_theta", "auto_ets", "auto_arima", "pooled_qr", "chronos_bolt",
               "features_qr", "hist_quantiles", "drift", "lme_forward"]


# =========================================================================== loading
def add_window(df: pd.DataFrame, select_end) -> pd.DataFrame:
    """Window of each row: backtest, holdout; plus the flag `strict` (hold-out rows whose
    origin is at or after select_end)."""
    end = pd.Timestamp(select_end)
    out = df.copy()
    tm = pd.to_datetime(out["target_month"])
    out["window"] = np.where(tm <= end, "backtest", "holdout")
    out["strict"] = (out["window"] == "holdout") & (pd.to_datetime(out["origin"]) >= end)
    return out


def mase_scale(preds: pd.DataFrame) -> pd.DataFrame:
    """Denominator of MASE for every (target, horizon, origin): the mean absolute H-month
    change over the outcomes already known at that origin (target month <= origin).

    The naive (random walk) forecast of y is 0, so its error is |y|: this is the classic
    "in-sample naive error", computed causally (expanding window). It is built from the
    random-walk rows, which cover every origin since the first one with a known outcome.
    """
    rw = (preds[preds["model"] == "random_walk"][["target", "horizon", "origin", "target_month", "y"]]
          .drop_duplicates(KEY))
    rows = []
    for (t, h), g in rw.groupby(["target", "horizon"]):
        g = g.sort_values("origin")
        known = g.dropna(subset=["y"]).sort_values("target_month")
        tm, ay = known["target_month"].to_numpy(), np.abs(known["y"].to_numpy(float))
        csum = np.concatenate([[0.0], np.cumsum(ay)])
        for o in g["origin"]:
            n = int(np.searchsorted(tm, np.datetime64(o), side="right"))
            rows.append({"target": t, "horizon": h, "origin": o,
                         "mase_scale": csum[n] / n if n else np.nan, "mase_n": n})
    return pd.DataFrame(rows)


def load_matched(models: list[str] | None = None, cfg: dict | None = None) -> pd.DataFrame:
    """Every saved forecast with a known outcome, matched with the random walk issued for
    the same (target, horizon, origin).

    One row per (model, target, horizon, origin): the model's p10 / p50 / p90 (/ p95),
    the random walk's as rw_p10 / rw_p50 / rw_p90, the outcome y, the window, and the MASE
    scale. The random walk itself is included (its skill is 0 by construction). Rows with
    no matching random-walk forecast are dropped.
    """
    cfg = cfg or load_config()
    preds = load_predictions()
    scale = mase_scale(preds)
    preds = preds.dropna(subset=["y"])
    if models is not None:
        preds = preds[preds["model"].isin(set(models) | {"random_walk"})]
    rw = (preds[preds["model"] == "random_walk"][KEY + ["p10", "p50", "p90"]]
          .drop_duplicates(KEY).rename(columns={c: f"rw_{c}" for c in ["p10", "p50", "p90"]}))
    cols = ["model", "target", "horizon", "origin", "target_month", "y"] + [c for c in QCOLS if c in preds]
    out = preds[cols].merge(rw, on=KEY, how="inner").merge(scale, on=KEY, how="left")
    return add_window(out, cfg["selection"]["select_end"])


def restrict_common(matched: pd.DataFrame, models: list[str]) -> pd.DataFrame:
    """Keep only the (target, horizon, origin) rows forecast by every model in `models`,
    so that models are compared on identical outcomes."""
    sub = matched[matched["model"].isin(models)]
    n = sub.groupby(KEY)["model"].nunique()
    keep = n[n == len(set(models))].index
    return sub.set_index(KEY).loc[keep].reset_index()


# =========================================================================== scores
def pinball(y: np.ndarray, q: np.ndarray, levels: np.ndarray = QS) -> np.ndarray:
    """Mean pinball (quantile) loss per row; q has one column per level."""
    d = np.asarray(y, float)[:, None] - np.asarray(q, float)
    return np.maximum(levels * d, (levels - 1) * d).mean(axis=1)


def crps_from_quantiles(y: np.ndarray, q: np.ndarray, levels: np.ndarray = QS,
                        grid: np.ndarray = CRPS_GRID) -> np.ndarray:
    """Approximate CRPS per row from a few quantiles.

    CRPS = 2 x the integral of the pinball loss over all levels. We only have P10 / P50 /
    P90, so the quantile function is interpolated linearly between them (and extended
    linearly beyond P10 and P90, with the neighbouring slope) on the grid 0.05 ... 0.95,
    and CRPS ~ 2 x mean pinball over that grid. The tails beyond 5 % / 95 % are left out,
    so this is an approximation, comparable across models that report the same quantiles.
    Same units as y (log change).
    """
    q = np.sort(np.asarray(q, float), axis=1)
    lv = np.asarray(levels, float)
    qg = np.empty((len(q), len(grid)))
    for j, tau in enumerate(grid):
        k = int(np.clip(np.searchsorted(lv, tau) - 1, 0, len(lv) - 2))
        w = (tau - lv[k]) / (lv[k + 1] - lv[k])
        qg[:, j] = q[:, k] + w * (q[:, k + 1] - q[:, k])
    return 2 * pinball(y, qg, grid)


def _row_scores(m: pd.DataFrame) -> pd.DataFrame:
    """Per-row scores of the model and of the matched random walk."""
    y = m["y"].to_numpy(float)
    q, rq = m[["p10", "p50", "p90"]].to_numpy(float), m[["rw_p10", "rw_p50", "rw_p90"]].to_numpy(float)
    out = m.copy()
    out["pin"], out["pin_rw"] = pinball(y, q), pinball(y, rq)
    out["crps"], out["crps_rw"] = crps_from_quantiles(y, q), crps_from_quantiles(y, rq)
    out["err"] = y - q[:, 1]
    out["ae"], out["ae_rw"] = np.abs(out["err"]), np.abs(y - rq[:, 1])
    out["ape"] = np.abs(np.exp(q[:, 1] - y) - 1)  # |forecast price / actual price - 1|
    out["cov80"] = ((y >= q[:, 0]) & (y <= q[:, 2])).astype(float)
    out["cov90"] = (y <= q[:, 2]).astype(float)
    out["width"] = q[:, 2] - q[:, 0]
    out["scaled_ae"] = out["ae"] / out["mase_scale"]
    return out


def _aggregate(g: pd.DataFrame) -> pd.Series:
    """Summary of a block of scored rows. Skills are ratios of totals (1 - sum model loss /
    sum random-walk loss), the same definition as the Step 6 jury table."""
    return pd.Series({
        "n": len(g),
        "mae_pct": 100 * g["ae"].mean(),
        "rmse_pct": 100 * np.sqrt((g["err"] ** 2).mean()),
        "mape_pct": 100 * g["ape"].mean(),
        "mae_skill": 1 - g["ae"].sum() / g["ae_rw"].sum(),
        "mase": g["scaled_ae"].mean(),
        "pinball_pct": 100 * g["pin"].mean(),
        "pinball_skill": 1 - g["pin"].sum() / g["pin_rw"].sum(),
        "crps_pct": 100 * g["crps"].mean(),
        "crps_skill": 1 - g["crps"].sum() / g["crps_rw"].sum(),
        "coverage_80": g["cov80"].mean(),
        "coverage_p90": g["cov90"].mean(),
        "width_80_pct": 100 * g["width"].mean(),
    })


def metric_table(matched: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """The full metric table at any level, e.g. by = ["model", "window", "horizon",
    "target"] (the plan's model x horizon x target table) or ["model", "window",
    "horizon"]. MASE < 1 means the median beats the in-sample naive error."""
    scored = _row_scores(matched)
    rows = [{**dict(zip(by, k if isinstance(k, tuple) else (k,))), **_aggregate(g).to_dict()}
            for k, g in scored.groupby(by)]
    return pd.DataFrame(rows)


# =========================================================================== weighted error
def bom_weights(cfg: dict | None = None) -> pd.DataFrame:
    """Euro share of each forecast target in each product's raw-material cost (Step 2 recipe
    at the Sep 2026 origin). Materials driven by the same target are added up (carbon steel
    and stainless both move with S09); unpriced plastics are left out, as in Step 2."""
    import src.cost_model as cm

    panel = cm.load_panel()
    rows = []
    for case, bom in cm.CASES.items():
        b = cm.cost_breakdown(bom, panel).dropna(subset=["cost_eur"])
        w = b.groupby("driver")["cost_eur"].sum()
        for target, v in (w / w.sum()).items():
            rows.append({"product": case, "target": target, "weight": v})
    return pd.DataFrame(rows)


def wape_by_product(matched: pd.DataFrame, weights: pd.DataFrame,
                    by: list[str] = ("model", "window", "horizon")) -> pd.DataFrame:
    """WAPE per product: sum_i w_i |e_i| / sum_i w_i |y_i| over the product's driver
    targets and all origins, with w_i the target's euro share in that product. Also the
    random walk's WAPE on the same rows and the skill 1 - WAPE / WAPE_rw."""
    scored = _row_scores(matched)
    rows = []
    for product, w in weights.groupby("product"):
        d = scored.merge(w[["target", "weight"]], on="target", how="inner")
        for k, g in d.groupby(list(by)):
            num, num_rw = (g["weight"] * g["ae"]).sum(), (g["weight"] * g["ae_rw"]).sum()
            den = (g["weight"] * g["y"].abs()).sum()
            rows.append({"product": product, **dict(zip(by, k)), "n": len(g),
                         "wape": num / den, "wape_rw": num_rw / den, "wape_skill": 1 - num / num_rw})
    return pd.DataFrame(rows)


# =========================================================================== significance
def dm_hln(d: np.ndarray, h: int) -> dict:
    """Diebold-Mariano test of equal accuracy, with the Harvey-Leybourne-Newbold (1997)
    small-sample correction.

    d = loss(model) - loss(random walk), one value per origin, in time order. H-month
    forecasts overlap, so the long-run variance uses autocovariances up to lag h - 1.
    Statistic ~ Student t with n - 1 degrees of freedom. Negative = the model has the
    lower loss. Returns the statistic, the two-sided p-value and the one-sided p-value of
    "the model is better".
    """
    d = np.asarray(d, dtype=float)
    d = d[np.isfinite(d)]
    n = len(d)
    if n < 2 * h or np.allclose(d, 0):
        return {"dm_stat": np.nan, "dm_p_two_sided": np.nan, "dm_p_model_better": np.nan, "dm_n": n}
    dc = d - d.mean()
    lrv = np.dot(dc, dc) / n
    for k in range(1, h):
        lrv += 2 * np.dot(dc[k:], dc[:-k]) / n
    if lrv <= 0:  # the truncated estimator can turn negative: fall back to the variance
        lrv = np.dot(dc, dc) / n
    dm = d.mean() / np.sqrt(lrv / n)
    hln = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    t = dm * hln
    return {"dm_stat": t, "dm_p_two_sided": 2 * stats.t.sf(abs(t), n - 1),
            "dm_p_model_better": stats.t.cdf(t, n - 1), "dm_n": n}


def per_origin_losses(matched: pd.DataFrame, model: str, h: int) -> pd.DataFrame:
    """Losses of a model and of the random walk summed over targets, one row per origin
    (all targets of an origin are one observation, as in the block bootstrap)."""
    s = _row_scores(matched[(matched["model"] == model) & (matched["horizon"] == h)])
    return s.groupby("origin")[["pin", "pin_rw", "ae", "ae_rw"]].sum().sort_index()


def jury_table(matched: pd.DataFrame, cfg: dict, models: list[str] | None = None) -> pd.DataFrame:
    """"Beats the random walk?" per window x model x horizon: the Step 6 jury table
    (skills and coverage with 95 % block-bootstrap CIs, `beats_naive`), plus MASE and the
    Diebold-Mariano (HLN) p-values for the pinball and absolute-error losses."""
    models = [m for m in (models or JURY_MODELS) if m in set(matched["model"])]
    out = []
    windows = {"backtest": matched["window"] == "backtest",
               "holdout": matched["window"] == "holdout",
               "holdout_strict": matched["strict"]}
    for wname, mask in windows.items():
        sub = matched[mask]
        # beats_naive expects model rows + random-walk rows in the Step 6 format.
        rw = sub[sub["model"] == "random_walk"]
        for m in models:
            rows = sub[sub["model"] == m]
            if rows.empty:
                continue
            b = beats_naive(pd.concat([rows, rw]), m, cfg)
            for _, r in b.iterrows():
                h = int(r["horizon"])
                po = per_origin_losses(rows.assign(model=m), m, h)
                dm_pin = dm_hln((po["pin"] - po["pin_rw"]).to_numpy(), h)
                dm_ae = dm_hln((po["ae"] - po["ae_rw"]).to_numpy(), h)
                mase = rows[rows["horizon"] == h]
                out.append({"window": wname, **r.to_dict(),
                            "mase": (np.abs(mase["y"] - mase["p50"]) / mase["mase_scale"]).mean(),
                            "dm_pinball_p_model_better": dm_pin["dm_p_model_better"],
                            "dm_pinball_p_two_sided": dm_pin["dm_p_two_sided"],
                            "dm_mae_p_model_better": dm_ae["dm_p_model_better"],
                            "dm_mae_p_two_sided": dm_ae["dm_p_two_sided"]})
    return pd.DataFrame(out)


def skill_ci(matched: pd.DataFrame, model: str, h: int, loss: str = "pin",
             n_boot: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """Skill vs the random walk on any rows (e.g. a group of materials), with its 95 %
    moving-block bootstrap CI (blocks of h months, whole origins resampled)."""
    po = per_origin_losses(matched, model, h)
    if po.empty:
        return np.nan, np.nan, np.nan
    f = lambda x: 1 - x[loss].sum() / x[f"{loss}_rw"].sum()
    lo, hi = _block_bootstrap_ci(po, f, block=h, n_boot=n_boot, seed=seed)
    return f(po), lo, hi


# =========================================================================== calibration
# Where an outcome can fall relative to the forecast quantiles, and how often it should.
PIT_BINS = [("below P10", 0.10), ("P10-P50", 0.40), ("P50-P90", 0.40), ("P90-P95", 0.05),
            ("above P95", 0.05)]
# The models whose calibration is reported (P95 only exists for the Step 6 models).
CALIBRATION_MODELS = ["random_walk", FINAL_MODEL, "gjr_fhs", "ewma_fhs", "features_scaled",
                      "auto_theta", "chronos_bolt", "features_qr"]


def kupiec(hits: np.ndarray, rate: float) -> dict:
    """Kupiec (1995) proportion-of-failures test: is the miss rate equal to `rate`?
    LR = -2 log[ L(rate) / L(observed rate) ] ~ chi2(1)."""
    hits = np.asarray(hits, dtype=float)
    n, x = len(hits), hits.sum()
    if n == 0:
        return {"n": 0, "misses": 0, "miss_rate": np.nan, "kupiec_p": np.nan}
    pi = x / n

    def ll(p: float) -> float:
        p = min(max(p, 1e-12), 1 - 1e-12)
        return (n - x) * np.log(1 - p) + x * np.log(p)

    lr = -2 * (ll(rate) - ll(pi))
    return {"n": n, "misses": int(x), "miss_rate": pi, "kupiec_p": float(stats.chi2.sf(lr, 1))}


def christoffersen(sequences: list[np.ndarray]) -> dict:
    """Christoffersen (1998) independence test: is a miss more likely right after a miss?
    Transition counts are added up over the sequences (one per target, each in time
    order); LR ~ chi2(1). With very few misses the test is uninformative (returns NaN)."""
    n00 = n01 = n10 = n11 = 0
    for s in sequences:
        s = np.asarray(s, dtype=int)
        a, b = s[:-1], s[1:]
        n00 += int(((a == 0) & (b == 0)).sum())
        n01 += int(((a == 0) & (b == 1)).sum())
        n10 += int(((a == 1) & (b == 0)).sum())
        n11 += int(((a == 1) & (b == 1)).sum())
    if (n01 + n11) == 0 or (n00 + n01) == 0 or (n10 + n11) == 0:
        return {"miss_after_miss": np.nan, "miss_after_hit": np.nan, "christoffersen_p": np.nan}
    p01, p11 = n01 / (n00 + n01), n11 / (n10 + n11)
    p = (n01 + n11) / (n00 + n01 + n10 + n11)

    def lg(k: int, q: float) -> float:
        return k * np.log(min(max(q, 1e-12), 1 - 1e-12)) if k else 0.0

    ll_ind = lg(n00, 1 - p01) + lg(n01, p01) + lg(n10, 1 - p11) + lg(n11, p11)
    ll_0 = lg(n00 + n10, 1 - p) + lg(n01 + n11, p)
    lr = -2 * (ll_0 - ll_ind)
    return {"miss_after_miss": p11, "miss_after_hit": p01,
            "christoffersen_p": float(stats.chi2.sf(max(lr, 0.0), 1))}


def non_overlapping(rows: pd.DataFrame, h: int, offset: int = 0) -> pd.DataFrame:
    """Every h-th origin of each target (starting at `offset`), so that the H-month
    outcome windows do not overlap and the misses can be treated as independent in time."""
    out = []
    for _, g in rows.sort_values("origin").groupby("target"):
        out.append(g.iloc[offset::h])
    return pd.concat(out) if out else rows.iloc[:0]


def calibration_tests(matched: pd.DataFrame, models: list[str] | None = None) -> pd.DataFrame:
    """Kupiec and Christoffersen tests per window x model x horizon, for two kinds of miss:
    outcome outside the P10-P90 band (target 20 %) and outcome above P90 (target 10 %, the
    pricing-buffer side). Run on non-overlapping origins (every H-th one); since the choice
    of the first origin is arbitrary, the test is run for each of the H possible offsets
    and the median p-value is reported, with the pooled miss rate over all offsets.
    Misses of different materials at the same origin are correlated (common shocks), so
    the p-values are optimistic: they describe, they do not prove."""
    models = [m for m in (models or CALIBRATION_MODELS) if m in set(matched["model"])]
    rows = []
    for (w, m, h), g in matched[matched["model"].isin(models)].groupby(["window", "model", "horizon"]):
        y = g["y"].to_numpy(float)
        g = g.assign(miss_band=((y < g["p10"]) | (y > g["p90"])).astype(int),
                     miss_p90=(y > g["p90"]).astype(int))
        for kind, col, rate in [("P10-P90 band", "miss_band", 0.20), ("above P90", "miss_p90", 0.10)]:
            ku, ch, misses, n = [], [], 0, 0
            for off in range(h):
                sub = non_overlapping(g, h, off)
                ku.append(kupiec(sub[col].to_numpy(), rate))
                seqs = [s.sort_values("origin")[col].to_numpy() for _, s in sub.groupby("target")]
                ch.append(christoffersen(seqs))
                misses += int(sub[col].sum())
                n += len(sub)
            rows.append({"window": w, "model": m, "horizon": h, "miss": kind, "target_rate": rate,
                         "n_per_offset": n / h, "miss_rate": misses / n if n else np.nan,
                         "kupiec_p": np.nanmedian([k["kupiec_p"] for k in ku]),
                         "miss_after_miss": np.nanmedian([c["miss_after_miss"] for c in ch]),
                         "miss_after_hit": np.nanmedian([c["miss_after_hit"] for c in ch]),
                         "christoffersen_p": np.nanmedian([c["christoffersen_p"] for c in ch])})
    return pd.DataFrame(rows)


def pit_bins(matched: pd.DataFrame, models: list[str] | None = None) -> pd.DataFrame:
    """Where the outcome fell relative to the forecast quantiles (a 5-bin PIT histogram,
    coarse because samples are small): below P10, P10-P50, P50-P90, P90-P95, above P95,
    with the expected shares 10 / 40 / 40 / 5 / 5 %. Too many outcomes in the outer bins =
    band too narrow; too few = too wide; lopsided = shifted. Models without P95 (the
    random walk) get "P90-P95" and "above P95" merged into "above P90"."""
    models = [m for m in (models or CALIBRATION_MODELS) if m in set(matched["model"])]
    rows = []
    for (w, m, h), g in matched[matched["model"].isin(models)].groupby(["window", "model", "horizon"]):
        y = g["y"].to_numpy(float)
        has95 = "p95" in g and g["p95"].notna().all()
        b = np.select([y < g["p10"], y < g["p50"], y <= g["p90"]], [0, 1, 2], default=3)
        if has95:
            b = np.where((b == 3) & (y > g["p95"]), 4, b)
        for k, (name, expected) in enumerate(PIT_BINS):
            if not has95 and k == 4:
                continue
            exp = expected if has95 or k < 3 else 0.10
            label = name if has95 or k < 3 else "above P90"
            rows.append({"window": w, "model": m, "horizon": h, "bin": label,
                         "observed": float((b == k).mean()), "expected": exp, "n": len(g)})
    return pd.DataFrame(rows)


def calibration_table(matched: pd.DataFrame, cfg: dict, models: list[str] | None = None) -> pd.DataFrame:
    """Coverage of the P10-P90 band and one-sided P90 coverage, with 95 % block-bootstrap
    CIs, per window x model x horizon (Step 6 `beats_naive`), next to the test p-values."""
    models = [m for m in (models or CALIBRATION_MODELS) if m in set(matched["model"])]
    j = jury_table(matched, cfg, models)
    keep = ["window", "model", "horizon", "n_forecasts", "independent_windows",
            "coverage_80", "coverage_80_lo", "coverage_80_hi",
            "coverage_p90", "coverage_p90_lo", "coverage_p90_hi"]
    return j[keep]


# =========================================================================== over time
def sub_period(target_month: pd.Series) -> pd.Series:
    """Sub-periods of the plan (by target month). The first outcome is Feb 2022, so there
    is no pre-2020 period. The 2025-26 period is exactly the hold-out (from Apr 2025);
    Jan-Mar 2025 stay with 2023-24, in the backtest."""
    tm = pd.to_datetime(target_month)
    return pd.Series(np.select(
        [tm <= "2022-12-01", tm <= "2025-03-01"],
        ["2022 (shock and peak)", "2023 - Mar 2025 (decline, calm)"],
        default="Apr 2025 - Sep 2026 (hold-out, copper rally)"), index=target_month.index)


def subperiod_table(matched: pd.DataFrame, models: list[str] | None = None) -> pd.DataFrame:
    """Metrics by sub-period x model x horizon (describe, don't test: each sub-period has
    only a few independent H-month windows, given in the table)."""
    models = [m for m in (models or CALIBRATION_MODELS) if m in set(matched["model"])]
    d = matched[matched["model"].isin(models)].assign(period=lambda x: sub_period(x["target_month"]))
    t = metric_table(d, ["period", "model", "horizon"])
    n_orig = d.groupby(["period", "model", "horizon"])["origin"].nunique().rename("n_origins").reset_index()
    t = t.merge(n_orig, on=["period", "model", "horizon"])
    t["independent_windows"] = (t["n_origins"] / t["horizon"]).round(1)
    return t


def rolling_loss_ratio(matched: pd.DataFrame, model: str = FINAL_MODEL,
                       window_months: int = 12) -> pd.DataFrame:
    """Rolling ratio of the model's pinball loss to the random walk's (Rossi, 2013 style),
    per horizon: over the last `window_months` target months, all targets, sum of model
    losses / sum of random-walk losses. Below 1 = the model is doing better."""
    s = _row_scores(matched[matched["model"] == model])
    m = s.groupby(["horizon", "target_month"])[["pin", "pin_rw"]].sum().reset_index()
    out = []
    for h, g in m.groupby("horizon"):
        g = g.set_index("target_month").sort_index().asfreq("MS")
        r = g.rolling(window_months, min_periods=window_months // 2).sum()
        out.append(pd.DataFrame({"horizon": h, "target_month": r.index,
                                 "loss_ratio": r["pin"] / r["pin_rw"],
                                 "months_in_window": g["pin"].notna().rolling(window_months, min_periods=1).sum()}))
    return pd.concat(out, ignore_index=True).dropna(subset=["loss_ratio"])


# =========================================================================== BOM index
BOM_SERIES = {"RM6": "BOM_RM6", "AirSeT": "BOM_AIRSET"}  # BOM v1 cases (src.cost_model)
BOM_BASE_MODELS = ["gjr_fhs", "garch_fhs", "ewma_fhs", "auto_theta"]  # Step 6 combo generalists


def bom_history() -> pd.DataFrame:
    """Historical BOM cost index of each product (Sep 2026 = 100), one column per product,
    from Step 2 exactly: cost_breakdown (fixed recipe, euro weights at the Sep 2026 prices)
    + driver_ratios + bom_index.

    The basket is fixed at today's (Sep 2026) prices, as in Step 2: the TARGET is defined
    once, and the models only see its history known at each origin. (A basket re-weighted
    at each origin's prices would be stricter; with a fixed recipe the difference is in the
    weights, not in the price paths.)"""
    import src.cost_model as cm

    panel = cm.load_panel()
    out = {}
    for case, col in BOM_SERIES.items():
        br = cm.cost_breakdown(cm.CASES[case], panel)
        out[col] = cm.bom_index(br, cm.driver_ratios(br, panel))
    return pd.DataFrame(out)


def bom_inputs(cfg: dict):
    """Step 4/6 Inputs with the three BOM indices added as extra series. Their publication
    lag is that of their slowest driver (2 months: S09, S10, D01, D02), so the Step 4
    information-set rule (info_set) applies to them exactly as to the materials."""
    import src.cost_model as cm
    from src.features import Inputs, load_inputs

    inputs = load_inputs()
    hist = bom_history().reindex(inputs.data.index)
    lags, sources = inputs.lags.copy(), inputs.sources.copy()
    panel = cm.load_panel()
    for case, col in BOM_SERIES.items():
        drivers = cm.cost_breakdown(cm.CASES[case], panel).dropna(subset=["cost_eur"])["driver"]
        lags[col] = int(inputs.lags.reindex(drivers.unique()).max())
        sources[col] = "Step 2 BOM index (fixed recipe)"
    return Inputs(pd.concat([inputs.data, hist], axis=1), lags, sources, inputs.steo)


def bom_tables(inputs, cfg: dict) -> dict:
    """Step 4-style tables (origin, y, target_month) for the BOM indices, at H = 3, 6, 9:
    y = log(index[o+H] / index[o]); origins from 12 months after the first value, as for
    the materials (no features: the BOM models are univariate)."""
    from src.features import target_change

    gap = cfg["settings"]["quote_gap_months"]
    tables = {}
    for col in BOM_SERIES.values():
        s = inputs.data[col]
        first = s.first_valid_index() + pd.DateOffset(months=12)
        for h in cfg["settings"]["horizons"]:
            rows = []
            for o in s.index[(s.index >= first) & s.notna()]:
                # the index must be published by the forecast date (lag <= quote gap)
                if inputs.lags[col] > gap:
                    continue
                rows.append({"origin": o, "y": target_change(inputs.data, col, o, h),
                             "target_month": o + pd.DateOffset(months=h)})
            tables[(col, h)] = pd.DataFrame(rows).set_index("origin")
    return tables


def bom_backtest(cfg: dict) -> tuple[pd.DataFrame, dict]:
    """Backtest of the BOM cost index forecast directly as its own series.

    Models: the Step 5 baselines (random walk, drift, historical quantiles; run_cell), the
    four generalist members of the Step 6 final model, their equal-weight combination and
    its conformal calibration with the gamma frozen in Step 6. Nothing is re-chosen here.
    Same rolling origins, information sets and Context as Step 6.

    Returns (predictions in the Step 5/6 format, the tables). The real BOM forecast of the
    CSV comes from the Step 8 joint simulation; this is the direct check of the same target.
    """
    from src import models as M
    from src.baselines import run_cell

    inputs = bom_inputs(cfg)
    tables = bom_tables(inputs, cfg)
    base = [run_cell(df.copy(), col, h, [], cfg) for (col, h), df in tables.items()]
    preds = [pd.concat(base, ignore_index=True)]
    for m in BOM_BASE_MODELS:
        preds.append(M.run_model(m, inputs, tables, {}, cfg))
    preds = pd.concat(preds, ignore_index=True)
    combo = M.combine(preds, BOM_BASE_MODELS, name="combo")
    gam = pd.read_csv(M.TABLE_DIR / "conformal_gamma.csv")
    gamma = float(gam[(gam["model"] == "combo") & gam["chosen"]]["gamma"].iloc[0])
    cal = M.adaptive_conformal(combo, gamma)
    out = pd.concat([preds, combo, cal], ignore_index=True)
    out["product"] = out["target"].map({v: k for k, v in BOM_SERIES.items()})
    return out, {"inputs": inputs, "tables": tables}


def bom_leakage_check(cfg: dict, n: int | None = None) -> pd.DataFrame:
    """Step 6 poisoned-future check on the BOM indices, for every model run on them."""
    from src import models as M

    inputs = bom_inputs(cfg)
    tables = bom_tables(inputs, cfg)
    return pd.concat([M.poisoned_future_check(m, inputs, tables, {}, cfg, n=n).assign(model=m)
                      for m in BOM_BASE_MODELS], ignore_index=True)


STEP8_MODEL = "step8_simulation"


def _origin_weights(breakdown: pd.DataFrame, panel: pd.DataFrame, origin) -> pd.DataFrame:
    """The breakdown re-valued at the origin: each material's euro cost moved by its driver,
    driver(origin) / driver(Sep 2026). These are the weights of the BOM index target in
    bom_tables, since index[o+H] / index[o] = sum(cost_i x driver_i(o)) x ratio_i / sum(...)."""
    import src.cost_model as cm

    out = breakdown.copy()
    r = cm.driver_ratios(breakdown, panel).loc[pd.Timestamp(origin)]
    priced = out["cost_eur"].notna()
    out.loc[priced, "cost_eur"] = out.loc[priced, "cost_eur"] * out.loc[priced, "material"].map(r).to_numpy()
    return out


def step8_forecasts(origins, marginals: pd.DataFrame | None = None, residuals: pd.DataFrame | None = None,
                    n_paths: int | None = None) -> pd.DataFrame:
    """The Step 8 joint simulation of the BOM index (the method behind the CSV's BOM rows),
    re-run at past origins, for the three products of bom_backtest.

    At each origin: Step 8 bootstraps the residuals known at that origin and rescales each
    driver to the final model's forecast made at that origin (src.simulation). The paths go
    through the same weights as the target of bom_tables (`_origin_weights`), so forecast
    and outcome are the same quantity and the random walk of bom_backtest is the reference.
    At the live origin (Sep 2026) these weights are Step 8's own, and the result is Step 8's.
    Origins where a driver has no forecast (epoxy before 2023) are skipped.
    Returns log changes (p10 / p50 / p90 / p95) in the Step 6 format, without y.
    """
    import src.cost_model as cm
    from src import simulation as S
    from src.models import MODEL_DIR

    panel = cm.load_panel()
    if residuals is None:
        residuals, _ = S.read_historical_prices()
    if marginals is None:
        marginals = pd.read_csv(MODEL_DIR / f"predictions_{FINAL_MODEL}.csv", parse_dates=["origin"])
    breakdowns = {col: cm.cost_breakdown(cm.CASES[case], panel) for case, col in BOM_SERIES.items()}
    marginals = marginals.assign(origin=pd.to_datetime(marginals["origin"]))
    rows = []
    for o in sorted(pd.to_datetime(pd.Series(origins)).unique()):
        try:
            ratios = S.simulate_driver_ratios(o, marginals, residuals, n_paths=n_paths or S.N_PATHS)
        except ValueError:  # a driver has no forecast at this origin (epoxy before 2023)
            continue
        for col, br in breakdowns.items():
            bd = _origin_weights(br, panel, o)
            for h, dr in ratios.items():
                q = np.log(np.percentile(cm.bom_index(bd, S.material_ratios(bd, dr)), [10, 50, 90, 95]) / 100)
                rows.append({"model": STEP8_MODEL, "target": col, "horizon": h, "origin": o,
                             **dict(zip(QCOLS, q))})
    return pd.DataFrame(rows)


def step8_backtest(bom_preds: pd.DataFrame, n_paths: int | None = None) -> pd.DataFrame:
    """Step 8 forecasts at every origin of bom_backtest, with the outcome y and target month
    of the same rows (taken from the random walk, so the target is identical)."""
    target = bom_preds[bom_preds["model"] == "random_walk"][KEY + ["target_month", "y"]].drop_duplicates(KEY)
    target["origin"] = pd.to_datetime(target["origin"])
    sim = step8_forecasts(target["origin"].unique(), n_paths=n_paths)
    out = sim.merge(target, on=KEY, how="inner")
    out["product"] = out["target"].map({v: k for k, v in BOM_SERIES.items()})
    return out


def step8_leakage_check(n_origins: int = 6, n_paths: int = 500, seed: int = 0) -> pd.DataFrame:
    """Poisoned-future check of step8_forecasts: at each tested origin, replace every
    residual after the origin and every forecast made at another origin (and all outcomes)
    with noise; the forecast at that origin must not change."""
    from src import simulation as S
    from src.models import MODEL_DIR

    residuals, _ = S.read_historical_prices()
    marg = pd.read_csv(MODEL_DIR / f"predictions_{FINAL_MODEL}.csv", parse_dates=["origin"])
    ok = marg.groupby("origin")["target"].apply(lambda t: set(S.TARGETS) <= set(t))
    origins = ok[ok].index
    origins = origins[np.linspace(0, len(origins) - 2, n_origins).round().astype(int)]  # not the last
    rng = np.random.default_rng(seed)
    rows = []
    for o in origins:
        clean = step8_forecasts([o], marg, residuals, n_paths=n_paths)
        res_p = residuals.copy()
        later = res_p.index > o
        res_p.loc[later] = rng.normal(0, 5, size=(later.sum(), res_p.shape[1]))
        marg_p = marg.copy()
        other = marg_p["origin"] != o
        for c in QCOLS:
            marg_p.loc[other, c] = rng.normal(0, 1, other.sum())
        marg_p["y"] = rng.normal(0, 1, len(marg_p))
        poisoned = step8_forecasts([o], marg_p, res_p, n_paths=n_paths)
        same = np.allclose(clean[QCOLS].to_numpy(), poisoned[QCOLS].to_numpy())
        rows.append({"origin": o, "forecasts": len(clean), "unchanged": bool(same)})
    return pd.DataFrame(rows)


def bom_metrics(preds: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Metric table (product x model x window x horizon) and jury table of the BOM backtest,
    with the same functions as for the materials."""
    rw = (preds[preds["model"] == "random_walk"][KEY + ["p10", "p50", "p90"]].drop_duplicates(KEY)
          .rename(columns={c: f"rw_{c}" for c in ["p10", "p50", "p90"]}))
    p = preds.dropna(subset=["y"])
    cols = ["model", "target", "horizon", "origin", "target_month", "y"] + [c for c in QCOLS if c in p]
    m = p[cols].merge(rw, on=KEY).merge(mase_scale(preds), on=KEY, how="left")
    m = add_window(m, cfg["selection"]["select_end"])
    m["product"] = m["target"].map({v: k for k, v in BOM_SERIES.items()})
    table = metric_table(m, ["product", "model", "window", "horizon"])
    jury = []
    for prod, g in m.groupby("product"):
        j = jury_table(g, cfg, ["random_walk", FINAL_MODEL, STEP8_MODEL, "combo", "ewma_fhs", "gjr_fhs",
                                "auto_theta", "hist_quantiles", "drift"])
        jury.append(j.assign(product=prod))
    return table, pd.concat(jury, ignore_index=True)


# =========================================================================== compute
def compute_footprint(cfg: dict | None = None, power_w: float = 20.0,
                      grid_g_per_kwh: dict | None = None) -> pd.DataFrame:
    """Run time, energy and CO2 of a full backtest run of every Step 6 model (all 15
    targets x 3 horizons x every origin), in memory: nothing is saved.

    Energy = wall time x `power_w`, the average power drawn by the computer during the run
    (default 20 W: a laptop CPU under load, e.g. Apple M2 package power; set it for other
    machines). CO2 = energy x grid carbon intensity (default: France ~ 50 gCO2/kWh, EU
    average ~ 250 gCO2/kWh). The caches of fitted models are cleared first, so each model
    is timed from scratch. Chronos is skipped if its optional extra is not installed.
    An estimate, not a measurement: codecarbon would give the same order of magnitude on a
    laptop (it also falls back on a constant CPU power when no power sensor is readable).
    """
    import time

    from src import models as M
    from src.baselines import load_selected
    from src.baselines import run as run_baselines
    from src.feature_selection import load_tables
    from src.features import load_inputs

    cfg = cfg or load_config()
    grid = grid_g_per_kwh or {"France": 50.0, "EU average": 250.0}
    inputs, tables, selected = load_inputs(), load_tables(cfg), load_selected()
    rows = []

    def record(name: str, approach: str, seconds: float, cpu: float, n: int) -> None:
        kwh = seconds * power_w / 3.6e6
        rows.append({"model": name, "approach": approach, "forecasts": n,
                     "wall_seconds": seconds, "cpu_seconds": cpu,
                     "ms_per_forecast": 1000 * seconds / n if n else np.nan, "energy_wh": 1000 * kwh,
                     **{f"co2_g_{k.lower().replace(' ', '_')}": kwh * v for k, v in grid.items()}})

    t0, c0 = time.perf_counter(), time.process_time()
    b = run_baselines()["predictions"]
    record("Step 5 baselines (all 5)", "direct", time.perf_counter() - t0, time.process_time() - c0, len(b))
    for name, spec in M.MODELS.items():
        if name.startswith("_"):
            continue
        M._garch_cached.cache_clear()
        M._sf_cached.cache_clear()
        M._chronos_cached.cache_clear()
        M._POOLED_FITS.clear()
        t0, c0 = time.perf_counter(), time.process_time()
        try:
            p = M.run_model(name, inputs, tables, selected, cfg)
        except ImportError:
            continue  # optional extra (Chronos) not installed
        record(name, spec["approach"], time.perf_counter() - t0, time.process_time() - c0, len(p))
    t0, c0 = time.perf_counter(), time.process_time()
    preds = M.load_predictions(models=[m for m in M.MODELS if (M.MODEL_DIR / f"predictions_{m}.csv").exists()])
    combo, _ = M.build_combination(preds, cfg)
    M.adaptive_conformal(combo, 0.02)
    record("combination + conformal (post-processing)", "-", time.perf_counter() - t0,
           time.process_time() - c0, len(combo))
    out = pd.DataFrame(rows)
    total = out.drop(columns=["model", "approach"]).sum(numeric_only=True)
    total["ms_per_forecast"] = np.nan
    out = pd.concat([out, pd.DataFrame([{"model": "TOTAL (one full Step 5 + 6 run)", "approach": "", **total}])],
                    ignore_index=True)
    out["power_w_assumed"] = power_w
    return out


# =========================================================================== sensitivity
# Phase D: checks that could have changed Step 6 choices. They are REPORTED, not acted on
# (the hold-out is frozen). Nothing here touches src.models.SETTINGS (fingerprinted by the
# freeze) or Data/processed/models/: variants are passed as call-time parameters or
# wrappers, and results go to Data/processed/evaluation/ and step7_tables/.
SLIDING_MONTHS = 60
GENERALISTS = ["ewma_fhs", "garch_fhs", "gjr_fhs", "auto_ets", "auto_arima", "auto_theta",
               "chronos_bolt", "pooled_qr"]  # Step 6 models that forecast every cell
LAMBDA_FAMILIES = ["ewma_fhs", "garch_fhs", "gjr_fhs", "features_scaled"]  # models using lambda
MIN_KNOWN_ORIGINS = 6  # months of known 3-month outcomes before anything is chosen


def _sliding(fn, months: int):
    """Wrap a Step 6 model so that it only learns from the last `months` of training
    origins (the outcome distribution); the volatility estimate itself is unchanged."""
    import dataclasses

    def wrapped(ctx, p):
        start = ctx.origin - pd.DateOffset(months=months)
        return fn(dataclasses.replace(ctx, train=ctx.train[ctx.train.index > start]), p)

    return wrapped


def _hist_quantiles(ctx, p):
    """Step 5 historical quantiles (quantiles of past H-month changes), in Step 6 form."""
    y = ctx.train["y"].to_numpy(float)
    return np.quantile(y, ctx.quantiles) if len(y) >= 12 else None


def sliding_window_check(cfg: dict | None = None, months: int = SLIDING_MONTHS,
                         check_leakage: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Expanding vs sliding (last `months`) training window for ewma_fhs and the
    historical quantiles (the plan: too short for GARCH and quantile regression).

    Returns (predictions of the four variants, metrics per variant x window x horizon).
    The four variants run through the Step 6 runner and Context, and the sliding ones are
    put through the poisoned-future check (every origin)."""
    from src import models as M
    from src.baselines import load_selected
    from src.feature_selection import load_tables
    from src.features import load_inputs

    cfg = cfg or load_config()
    inputs, tables, selected = load_inputs(), load_tables(cfg), load_selected()
    variants = {"ewma_fhs (expanding)": M.ewma_fhs,
                f"ewma_fhs (last {months} m)": _sliding(M.ewma_fhs, months),
                "hist_quantiles (expanding)": _hist_quantiles,
                f"hist_quantiles (last {months} m)": _sliding(_hist_quantiles, months)}
    preds, leaks = [], []
    try:
        for name, fn in variants.items():
            key = "_sens_" + name
            M.MODELS[key] = {"fn": fn, "approach": "direct", "needs": ()}
            preds.append(M.run_model(key, inputs, tables, selected, cfg).assign(model=name))
            if check_leakage and "last" in name:
                leaks.append(M.poisoned_future_check(key, inputs, tables, selected, cfg).assign(model=name))
    finally:
        for name in variants:
            M.MODELS.pop("_sens_" + name, None)
    rw = load_predictions(models=["random_walk"])
    rw = rw[rw["model"] == "random_walk"]
    pr = pd.concat(preds + [rw], ignore_index=True)
    matched = _match(pr, cfg)
    table = metric_table(matched[matched["model"] != "random_walk"], ["model", "window", "horizon"])
    if leaks:
        lk = pd.concat(leaks)
        if not lk["unchanged"].all():
            raise AssertionError("Leakage in a sliding-window variant")
        table.attrs["leakage_checked"] = len(lk)
    return pr, table


def _match(preds: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """load_matched for an arbitrary prediction frame (must contain the random walk)."""
    scale = mase_scale(preds)
    p = preds.dropna(subset=["y"])
    rw = (p[p["model"] == "random_walk"][KEY + ["p10", "p50", "p90"]].drop_duplicates(KEY)
          .rename(columns={c: f"rw_{c}" for c in ["p10", "p50", "p90"]}))
    cols = ["model", "target", "horizon", "origin", "target_month", "y"] + [c for c in QCOLS if c in p]
    out = p[cols].merge(rw, on=KEY).merge(scale, on=KEY, how="left")
    return add_window(out, cfg["selection"]["select_end"])


def lambda_variants(cfg: dict, lambdas=(0.94,)) -> pd.DataFrame:
    """Predictions of the lambda-dependent Step 6 models for other lambdas (call-time
    parameter, SETTINGS untouched), named e.g. "ewma_fhs@0.94"."""
    from src import models as M
    from src.baselines import load_selected
    from src.feature_selection import load_tables
    from src.features import load_inputs

    inputs, tables, selected = load_inputs(), load_tables(cfg), load_selected()
    out = []
    for lam in lambdas:
        for m in LAMBDA_FAMILIES:
            p = M.run_model(m, inputs, tables, selected, cfg, params={"ewma_lambda": lam})
            out.append(p.assign(model=f"{m}@{lam}"))
    return pd.concat(out, ignore_index=True)


def _cell_skill(sc: pd.DataFrame) -> pd.DataFrame:
    """Per model: cells covered, mean over cells of the pinball skill vs RW, mean coverage."""
    c = sc.groupby(["model", "target", "horizon"]).agg(pin=("pin", "sum"), pin_rw=("pin_rw", "sum"),
                                                       cov=("cov80", "mean"))
    c["skill"] = 1 - c["pin"] / c["pin_rw"]
    return c.groupby("model").agg(cells=("skill", "size"), skill=("skill", "mean"), coverage=("cov", "mean"))


def causal_tuning(cfg: dict | None = None, extra: pd.DataFrame | None = None,
                  origins: list | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Step 6's choices re-made at EVERY origin T from the outcomes known at T only
    (target month <= T): lambda per model (0.94 / 0.97), the combination members (coverage
    within 80 % +- 10 first, then skill; sizes 3 and 4), the features_scaled yes/no rule,
    and the conformal gamma of the combination. The forecast issued at T uses those
    choices. Before MIN_KNOWN_ORIGINS months of outcomes are known, a neutral default is
    used: equal weight of every generalist, lambda = 0.97, no calibration.

    Every input path is causal: base forecasts (Step 6, tested), combinations (row-wise)
    and conformal paths (tested). Returns (the causal forecasts, one row per target x H x
    origin, model "causal_combo"; the log of choices per origin).
    """
    from src import models as M

    cfg = cfg or load_config()
    base = load_predictions(models=GENERALISTS + ["features_scaled"])
    base = base[base["model"].isin(GENERALISTS + ["features_scaled", "random_walk"])].copy()
    lam_models = base["model"].isin(LAMBDA_FAMILIES)
    base.loc[lam_models, "model"] = base.loc[lam_models, "model"] + "@0.97"
    extra = extra if extra is not None else lambda_variants(cfg)
    preds = pd.concat([base, extra], ignore_index=True)
    rw = preds[preds["model"] == "random_walk"]
    scored = _row_scores(_match(preds, cfg))
    grid = [g for g in M.SETTINGS["conformal_gammas"]]
    tol = M.SETTINGS["combo_coverage_tol"]
    combos, cals = {}, {}

    def combo(members: tuple) -> pd.DataFrame:
        if members not in combos:
            combos[members] = M.combine(preds, list(members), name="causal")
        return combos[members]

    def calibrated(members: tuple, g: float) -> pd.DataFrame:
        if (members, g) not in cals:
            c = combo(members)
            cals[(members, g)] = M.adaptive_conformal(c, g) if g > 0 else c
        return cals[(members, g)]

    def known_skill(frame: pd.DataFrame, T, rows=None) -> float:
        k = frame[(frame["target_month"] <= T) & frame["y"].notna()]
        if rows is not None:
            k = k.merge(rows, on=["target", "horizon"])
        if k.empty:
            return -np.inf
        sc = _row_scores(_match(pd.concat([k, rw]), cfg))
        sc = sc[sc["model"] == frame["model"].iloc[0]]
        return _cell_skill(sc)["skill"].iloc[0]

    origins = sorted(pd.to_datetime(origins if origins is not None else base.loc[base["model"] != "random_walk", "origin"].unique()))
    out, log = [], []
    for T in origins:
        known = scored[scored["target_month"] <= T]
        n_known = known[known["horizon"] == 3]["origin"].nunique()
        if n_known < MIN_KNOWN_ORIGINS:
            lam = dict.fromkeys(LAMBDA_FAMILIES, "0.97")
            members = tuple(sorted(f"{m}@0.97" if m in LAMBDA_FAMILIES else m for m in GENERALISTS))
            gamma, note = 0.0, "default (too few known outcomes)"
        else:
            # 1. lambda per model family, on the rows both variants forecast
            lam = {}
            for fam in LAMBDA_FAMILIES:
                a, b = known[known["model"] == f"{fam}@0.97"], known[known["model"] == f"{fam}@0.94"]
                common = a[KEY].merge(b[KEY], on=KEY)
                la = a.merge(common, on=KEY)["pin"].mean()
                lb = b.merge(common, on=KEY)["pin"].mean()
                lam[fam] = "0.94" if lb < la else "0.97"
            chosen = {m: (f"{m}@{lam[m]}" if m in LAMBDA_FAMILIES else m) for m in GENERALISTS + ["features_scaled"]}
            summ = _cell_skill(known[known["model"].isin(chosen.values())])
            gen = [chosen[m] for m in GENERALISTS if chosen[m] in summ.index]
            ok = summ.loc[gen]
            ok = ok[(ok["coverage"] - 0.8).abs() <= tol].sort_values("skill", ascending=False)
            # 2. size 3 or 4, by the skill of the combination on the known rows
            best = None
            for n in M.SETTINGS["combo_sizes"]:
                mem = tuple(sorted(ok.index[:n]))
                if len(mem) < 2:
                    continue
                sk = known_skill(combo(mem), T)
                if best is None or sk > best[0]:
                    best = (sk, mem)
            members = best[1] if best else tuple(sorted(gen))
            # 3. specialist yes / no on its own cells
            spec = chosen["features_scaled"]
            if spec in summ.index and abs(summ.loc[spec, "coverage"] - 0.8) <= tol:
                cells = known[known["model"] == spec][["target", "horizon"]].drop_duplicates()
                if summ.loc[spec, "skill"] > known_skill(combo(members), T, cells):
                    members = tuple(sorted(members + (spec,)))
            # 4. gamma of the combination
            losses = {}
            for g in grid:
                k = calibrated(members, g)
                k = k[(k["target_month"] <= T) & k["y"].notna()]
                losses[g] = pinball(k["y"], k[["p10", "p50", "p90"]].to_numpy()).mean() if len(k) else np.inf
            gamma = min(losses, key=losses.get)
            note = ""
        rows = calibrated(members, gamma)
        rows = rows[rows["origin"] == T].assign(model="causal_combo")
        out.append(rows)
        log.append({"origin": T, "known_3m_origins": n_known, "members": ", ".join(members),
                    "gamma": gamma, **{f"lambda_{k}": v for k, v in lam.items()}, "note": note})
    res = pd.concat(out, ignore_index=True)
    return res, pd.DataFrame(log)


def causal_vs_hindsight(causal: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """The Step 6 final model (choices made with hindsight on the whole backtest) vs the
    same procedure re-run causally, on identical rows: mean over cells of the pinball skill
    (the Step 6 figure, +8.5 % on the backtest) and pooled skill per horizon."""
    hind = load_predictions(models=[FINAL_MODEL])
    hind = hind[hind["model"].isin([FINAL_MODEL, "random_walk"])]
    m = _match(pd.concat([hind, causal], ignore_index=True), cfg)
    m = restrict_common(m, [FINAL_MODEL, "causal_combo"]).merge(
        m[KEY + ["model", "window"]].drop_duplicates(), how="left")
    sc = _row_scores(m)
    rows = []
    for w in ["backtest", "holdout"]:
        for mod in [FINAL_MODEL, "causal_combo"]:
            g = sc[(sc["window"] == w) & (sc["model"] == mod)]
            r = {"window": w, "model": mod, "mean_cell_skill": _cell_skill(g)["skill"].iloc[0],
                 "coverage_80": g["cov80"].mean()}
            for h in (3, 6, 9):
                gh = g[g["horizon"] == h]
                r[f"skill_{h}m"] = 1 - gh["pin"].sum() / gh["pin_rw"].sum()
            rows.append(r)
    return pd.DataFrame(rows)


def causal_leakage_check(cfg: dict, extra: pd.DataFrame, origins: list) -> pd.DataFrame:
    """Poison every outcome not known at T and every base forecast issued after T: the
    causal forecast issued at T must not change. Runs the procedure only at the tested
    origins (it reads the saved predictions through load_predictions, so the poisoning is
    applied to the extra lambda variants and through a patched loader)."""
    module = globals()  # causal_tuning reads predictions through this module's loader
    rng = np.random.default_rng(0)
    clean, _ = causal_tuning(cfg, extra, origins)
    real_loader = module["load_predictions"]
    rows = []
    try:
        for T in origins:
            T = pd.Timestamp(T)
            full = real_loader()

            def poison(df: pd.DataFrame, T=T) -> pd.DataFrame:
                df = df.copy()
                h = df["target_month"] > T
                df.loc[h, "y"] = rng.uniform(-5, 5, h.sum())
                later = df["origin"] > T
                c = [q for q in QCOLS if q in df]
                df.loc[later, c] = np.sort(rng.uniform(-5, 5, (later.sum(), len(c))), axis=1)
                return df

            bad_all = poison(full)
            module["load_predictions"] = lambda models=None, with_baselines=True, _b=bad_all: (
                _b if models is None else _b[_b["model"].isin(list(models) + ["random_walk"])])
            bad, _ = causal_tuning(cfg, poison(extra), [T])
            a = clean[clean["origin"] == T].sort_values(KEY)[["p10", "p50", "p90"]].to_numpy()
            b = bad.sort_values(KEY)[["p10", "p50", "p90"]].to_numpy()
            rows.append({"origin": f"{T:%Y-%m}", "n": len(a),
                         "unchanged": bool(len(a) == len(b) and np.allclose(a, b))})
    finally:
        module["load_predictions"] = real_loader
    return pd.DataFrame(rows)


# =========================================================================== main
def run(cfg: dict | None = None) -> dict[str, pd.DataFrame]:
    """Phase A tables (metrics at three levels, WAPE per product, the jury table) and
    Phase B tables (calibration, its tests, the 5-bin histogram, sub-periods, the
    rolling loss ratio)."""
    cfg = cfg or load_config()
    matched = load_matched(cfg=cfg)
    groups = {t: g for g, ts in SETTINGS["pooled_groups"].items() for t in ts}
    matched["group"] = matched["target"].map(groups)
    return {
        "metrics_by_target": metric_table(matched, ["model", "window", "horizon", "target"]),
        "metrics_by_group": metric_table(matched, ["model", "window", "horizon", "group"]),
        "metrics_by_horizon": metric_table(matched, ["model", "window", "horizon"]),
        "wape_by_product": wape_by_product(matched, bom_weights(cfg)),
        "jury_table": jury_table(matched, cfg),
        "calibration": calibration_table(matched, cfg),
        "calibration_tests": calibration_tests(matched),
        "pit_bins": pit_bins(matched),
        "subperiods": subperiod_table(matched),
        "rolling_loss_ratio": rolling_loss_ratio(matched),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Step 7 evaluation")
    parser.add_argument("--compute", action="store_true",
                        help="also time every model and estimate energy / CO2 (~5 min)")
    parser.add_argument("--sensitivity", action="store_true",
                        help="also run the Phase D checks: sliding window, causal tuning (~3 min)")
    args = parser.parse_args()
    cfg = load_config()
    out = run(cfg)
    bom_preds, _ = bom_backtest(cfg)
    bom_preds = pd.concat([bom_preds, step8_backtest(bom_preds)], ignore_index=True)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    bom_preds.to_csv(EVAL_DIR / "bom_predictions.csv", index=False)
    out["bom_metrics"], out["bom_jury_table"] = bom_metrics(bom_preds, cfg)
    if args.compute:
        out["compute_footprint"] = compute_footprint(cfg)
    if args.sensitivity:
        sw_preds, out["sliding_window"] = sliding_window_check(cfg)
        sw_preds.to_csv(EVAL_DIR / "sliding_window_predictions.csv", index=False)
        extra = lambda_variants(cfg)
        extra.to_csv(EVAL_DIR / "lambda_variant_predictions.csv", index=False)
        causal, out["causal_choices"] = causal_tuning(cfg, extra)
        causal.to_csv(EVAL_DIR / "causal_combo_predictions.csv", index=False)
        out["causal_vs_hindsight"] = causal_vs_hindsight(causal, cfg)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in out.items():
        df.round(4).to_csv(TABLE_DIR / f"{name}.csv", index=False)
    j = out["jury_table"]
    cols = ["window", "model", "horizon", "pinball_skill", "pinball_skill_lo", "pinball_skill_hi",
            "dm_pinball_p_model_better", "mae_skill", "mase", "coverage_80", "coverage_p90"]
    print(j[j["model"].isin([FINAL_MODEL, "random_walk"])][cols].round(3).to_string(index=False))
    print(f"\nTables written to {TABLE_DIR}")
    from src import evaluation_plots as EP

    EP.make_all(out)
    print(f"Charts written to {EP.PLOT_DIR}")


if __name__ == "__main__":
    main()
