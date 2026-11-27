"""Step 6 – probabilistic forecasting models for every material target at H = 3, 6, 9.

Run from the repo root, after src.data_prep, src.external_data, src.features and
src.baselines:

    uv run python -m src.models                          # every model, then calibration + combination
    uv run python -m src.models --model ewma_fhs         # one base model
    uv run python -m src.models --model ewma_fhs garch --targets S09 S08 --horizons 3
    uv run python -m src.models --stage post             # only conformal + combination
    uv run python -m src.models --check-leakage          # poisoned-future test on every model

Same target, timing and backtest as Steps 4 and 5:
    y = log(P[o+H]) - log(P[o]), P10 / P50 / P90 (+ P95 for the Step 9 buffer).
    At each origin T a model only sees what was published by the forecast date (T + 2
    months, never after month T) and only trains on origins with o + H <= T.

Two stages
    1. Base models (one function each, registered with @register). Each one receives a
       Context holding ONLY the information known at the origin, and returns the
       quantiles of y. Models never see the full panel, so they cannot leak.
    2. Post-processing on the saved base predictions, also causal in time:
         conformal_<model>   adaptive conformal calibration of one base model
         combo               equal-weight average of the quantiles of the best models

Hold-out discipline
    Anything that is CHOSEN (EWMA lambda, conformal learning rate, combination members)
    is chosen on the backtest window only (target month <= select_end). The hold-out
    (Apr 2025 -> Sep 2026) is scored once, at the end. `backtest_only()` enforces it.

Technical traps (from the Step 5 review)
    - Do not scale monthly volatility by sqrt(H): PPIs have lag-1 autocorrelation
      0.5-0.8, so H-month variance is far above H x monthly variance. Volatility-scaled
      models work on H-month changes directly (filtered historical simulation on
      standardised H-month changes, see `standardised_h_changes`).
    - lambda = 0.97 (half-life ~23 months) may react too slowly; compare 0.94 / 0.97 on
      the backtest only.

Outputs
    Data/processed/models/predictions_<model>.csv   one row per target, H, origin
    Data/processed/models/step8/                    Step 8 inputs (export_residuals): monthly
                                                    residuals, joint H-month z, live marginals
    report/problem1/step6_tables/metrics.csv        same metrics as Step 5, incl. baselines
    report/problem1/step6_tables/conformal_gamma.csv  backtest choice of the conformal gamma
    report/problem1/step6_tables/leakage_test.csv   poisoned-future test
    report/problem1/step6_tables/holdout_*.csv      the single hold-out evaluation (--stage holdout)
"""

from __future__ import annotations

import argparse
import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd

from src.baselines import PRED_DIR as BASELINE_DIR
from src.baselines import load_selected, score
from src.config import REPO_ROOT
from src.data_prep import OUT
from src.feature_selection import load_tables
from src.features import Inputs, info_set, load_config, load_inputs

MODEL_DIR = OUT / "models"
TABLE_DIR = REPO_ROOT / "report" / "problem1" / "step6_tables"

QUANTILES = [0.1, 0.5, 0.9, 0.95]  # P95 is kept for the Step 9 pricing buffer
QCOLS = ["p10", "p50", "p90", "p95"]
MIN_PAST = 12  # fewest past outcomes needed to estimate a band (as in Step 5)
EWMA_INIT = 12  # months of returns used to start the EWMA recursion

# Default settings. Anything tuned is tuned on the backtest window only.
SETTINGS = {
    "ewma_lambda": 0.97,  # backtest: 0.97 slightly ahead of 0.94 (within noise); plan default
    "ewma_lambdas_to_compare": [0.94, 0.97],
    "garch_min_obs": 60,  # below this, or if the fit fails, fall back to EWMA
    "garch_o": 0,  # 0 = GARCH(1,1); 1 = GJR-GARCH (rises raise volatility more than falls)
    "garch_dist": "t",  # Student-t innovations
    "ets_max_order": 2,  # cap ARIMA p, q (unstable order selection on short series)
    # Chronos-Bolt (Apache-2.0), optional extra: uv sync --extra chronos. Pinned revision.
    "chronos_model": "amazon/chronos-bolt-small",
    "chronos_revision": "772f3d25d38aec6d914c8949dab4462e2d46f5d8",
    "chronos_device": "cpu",  # ~14 ms per forecast on an M2 CPU; "mps" also possible
    # Learning rate of adaptive conformal, chosen per model on the backtest (0 = off).
    "conformal_gammas": [0.0, 0.02, 0.05, 0.1, 0.2],
    "combo_sizes": [3, 4],  # best N base models in the combination; N chosen on the backtest
    "combo_coverage_tol": 0.10,  # acceptable: mean backtest P10-P90 coverage within 80 % +- 10
    # Cells where features_scaled forecasts: None = every cell where Step 4 kept features.
    # Do NOT restrict it to the cells that did well in the Step 5 hold-out (S08/S09/S10
    # at 3 m): that would be a choice made on the hold-out. Restrict on backtest evidence.
    "feature_median_cells": None,
    "features_band": "residual",  # band from residuals of the median model, or "raw" y
    "features_alpha_rel": 0.02,  # L1 penalty, same as configs/features.yaml (Step 4)
    # Pooled model: every target stacked, with a material-group indicator.
    "pooled_groups": {
        "market": ["S01", "D01", "S02", "D02", "S03", "S04", "S05"],
        "ppi": ["S07", "S08", "S09", "S10", "S11", "S12", "S13"],
        "epoxy": ["EPOXY_EUR"],
    },
    "pooled_alpha_rel": 0.02,
    # Pools: which groups are fitted together. One pool = every target in one model.
    "pooled_pools": [["market", "ppi", "epoxy"]],
    "seed": 0,
}


# =========================================================================== context
@dataclass(frozen=True)
class Context:
    """Everything a model may use at one origin. Built only from data known at `origin`."""

    target: str
    h: int
    origin: pd.Timestamp
    history: pd.Series  # monthly level of the target known at the origin (index <= origin)
    known: pd.DataFrame  # every panel / external series known at the origin (info_set)
    train: pd.DataFrame  # Step 4 feature-table rows with target_month <= origin (y known)
    row: pd.Series  # Step 4 features at the origin (no y)
    features: list[str] = field(default_factory=list)  # Step 4 selected features
    quantiles: tuple[float, ...] = tuple(QUANTILES)


ModelFn = Callable[[Context, dict], "np.ndarray | tuple[np.ndarray, str] | None"]
MODELS: dict[str, dict] = {}


def unpack(out) -> tuple[np.ndarray | None, str]:
    """A model returns quantiles, (quantiles, note) or None. The note (e.g. 'ewma
    fallback: no convergence') is saved in the `note` column of the predictions."""
    if out is None:
        return None, ""
    if isinstance(out, tuple):
        return out[0], out[1]
    return out, ""


def register(name: str, approach: str, needs: tuple[str, ...] = ()):
    """Register a base model.

    approach: "direct" (one model per H) or "recursive" (iterates 1-month forecasts);
              reported in the Step 6 table as the plan asks.
    needs:    optional packages (e.g. ("statsforecast",), ("torch", "chronos")), imported
              lazily so the core pipeline does not depend on them.
    """

    def deco(fn: ModelFn) -> ModelFn:
        MODELS[name] = {"fn": fn, "approach": approach, "needs": needs}
        return fn

    return deco


def build_context(inputs: Inputs, table: pd.DataFrame, target: str, h: int, origin,
                  features: list[str], cfg: dict, known: pd.DataFrame | None = None) -> Context:
    """The information set at `origin` for one target and horizon."""
    origin = pd.Timestamp(origin)
    if known is None:
        known = info_set(inputs, origin, cfg["settings"]["quote_gap_months"])
    past = table[table["y"].notna() & (table["target_month"] <= origin)]
    row = table.loc[origin].drop(["y", "target_month"])
    return Context(target=target, h=h, origin=origin,
                   history=known[target].loc[:origin].dropna(), known=known,
                   train=past, row=row, features=features)


def evaluation_origins(table: pd.DataFrame, cfg: dict) -> list[pd.Timestamp]:
    """Same origins as Step 5: from min_train_months after the first row, plus the live row."""
    first_eval = table.index[0] + pd.DateOffset(months=cfg["selection"]["min_train_months"])
    known_y = table[table["y"].notna()]
    evals = list(known_y.index[known_y.index >= first_eval])
    live = table.index[-1]
    return evals + ([live] if live not in evals else [])


# =========================================================================== shared helpers
def ewma_vol(returns: pd.Series, lam: float, init: int = EWMA_INIT) -> pd.Series:
    """RiskMetrics EWMA volatility of monthly log returns (zero mean).

        sigma2[t] = lam * sigma2[t-1] + (1 - lam) * r[t]^2

    Started at the mean of r^2 over the first `init` returns (value at position init - 1),
    NaN before. The recursion is causal: sigma[t] uses returns up to t only, so sigma at a
    past origin o is the same whatever later data exists.
    """
    r = returns.dropna()
    out = pd.Series(np.nan, index=r.index, name="sigma")
    if len(r) < init:
        return out
    x = r.to_numpy(float) ** 2
    s2 = np.empty(len(x))
    s2[: init - 1] = np.nan
    s2[init - 1] = x[:init].mean()
    for i in range(init, len(x)):
        s2[i] = lam * s2[i - 1] + (1 - lam) * x[i]
    out[:] = np.sqrt(s2)
    return out


def standardised_h_changes(ctx: Context, lam: float) -> tuple[np.ndarray, float]:
    """Filtered historical simulation on H-month changes (no sqrt(H) scaling).

    For every past origin o in ctx.train (o + H <= T, so the whole window is known):

        z_o = y_o / s_o,   s_o = RMS of the monthly log returns inside (o, o + H]

    i.e. each past H-month change measured in units of the volatility that prevailed
    DURING it. Returns (z, sigma_T), sigma_T = EWMA volatility at the origin, which is
    the forecast of the volatility over the coming H months. The H-month quantiles are
    then sigma_T x quantiles(z): the momentum of the PPIs stays inside z (no assumption
    that months are independent), and only the volatility level is updated.

    Rejected alternative (backtest, Step 6 report): s_o = EWMA volatility AT the origin.
    The 2021 surge started from calm months, so it became an extreme z, which was then
    multiplied by the high 2022 volatility: 9-month PPI bands twice as wide as the
    random walk's, 98 % coverage, pinball skill -23 %.

    Returns (empty array, nan) if the target's value at the origin is not known or the
    volatility cannot be estimated yet.
    """
    if ctx.history.empty or ctx.history.index[-1] != ctx.origin:
        return np.array([]), np.nan
    r = np.log(ctx.history).diff()
    sigma_T = ewma_vol(r, lam).get(ctx.origin, np.nan)
    s_o = window_rms(ctx)
    ok = s_o.notna() & (s_o > 0) & ctx.train["y"].notna()
    z = (ctx.train.loc[ok, "y"] / s_o[ok]).to_numpy(float)
    return z, float(sigma_T)


def window_rms(ctx: Context) -> pd.Series:
    """RMS of the monthly log returns inside (o, o + H] for every training origin o
    (aligned on ctx.train's index). NaN when the window goes past the origin."""
    r = np.log(ctx.history).diff()
    return np.sqrt((r ** 2).rolling(ctx.h).mean()).shift(-ctx.h).reindex(ctx.train.index)


GARCH_MAX_H = 9  # one fit per target and origin serves every horizon


def garch_variance_path(r: np.ndarray, o: int = 0, dist: str = "t") -> tuple[np.ndarray | None, str]:
    """Monthly variance forecasts for months 1..GARCH_MAX_H after the last return, from a
    zero-mean GARCH(1,1) (o=1: GJR) fitted on the returns r. (None, reason) if the fit
    fails, does not converge or is not stationary (persistence >= 0.999).

    Cached on the exact content of r: the same returns always give the same answer, and
    different (e.g. poisoned) returns can never hit the same cache entry.
    """
    return _garch_cached(np.ascontiguousarray(r, dtype=float).tobytes(), o, dist)


@lru_cache(maxsize=8192)
def _garch_cached(buf: bytes, o: int, dist: str) -> tuple[np.ndarray | None, str]:
    import warnings

    from arch import arch_model

    r = np.frombuffer(buf, dtype=float)
    # Returns in %: the optimiser is unstable on numbers of size 0.01.
    model = arch_model(100 * r, mean="Zero", vol="GARCH", p=1, o=o, q=1, dist=dist, rescale=False)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = model.fit(disp="off", show_warning=False)
    except Exception as e:  # noqa: BLE001 - any numerical failure means: fall back
        return None, f"fit error ({type(e).__name__})"
    if res.convergence_flag != 0:
        return None, "no convergence"
    prm = res.params
    persistence = prm["alpha[1]"] + prm["beta[1]"] + 0.5 * prm.get("gamma[1]", 0.0)
    if not np.isfinite(persistence) or persistence >= 0.999:
        return None, "not stationary"
    var = res.forecast(horizon=GARCH_MAX_H, reindex=False).variance.to_numpy()[-1] / 1e4
    return var, "garch"


def sort_quantiles(q: np.ndarray) -> np.ndarray:
    """Fix quantile crossing (the CSV requires p10 <= p50 <= p90)."""
    return np.sort(np.asarray(q, dtype=float))


# =========================================================================== base models
@register("ewma_fhs", approach="direct")
def ewma_fhs(ctx: Context, p: dict) -> np.ndarray | None:
    """Random-walk median (0) + EWMA-scaled band from standardised H-month changes.

    Same as the Step 5 random walk (P50 = 0, band = spread of past changes around their
    median), except that past H-month changes are first divided by the volatility during
    their window and the band is rescaled by today's volatility:

        q_k = sigma_T * (quantile_k(z) - median(z))

    So the only difference with the random walk is the volatility state: wider bands
    after volatile months, narrower in calm ones.
    """
    z, sigma_T = standardised_h_changes(ctx, p["ewma_lambda"])
    if len(z) < MIN_PAST or not np.isfinite(sigma_T) or sigma_T <= 0:
        return None
    return sigma_T * (np.quantile(z, ctx.quantiles) - np.median(z))


@register("garch_fhs", approach="direct", needs=("arch",))
def garch_fhs(ctx: Context, p: dict) -> tuple[np.ndarray, str] | None:
    """As ewma_fhs, but the volatility of the coming H months comes from a GARCH(1,1)
    with Student-t errors (GJR if garch_o = 1), fitted on the monthly returns known at T:

        sigma_H = sqrt(mean of the GARCH variance forecasts for months 1..H)
        q_k     = sigma_H * (quantile_k(z) - median(z))

    Unlike EWMA, whose forecast stays flat at today's level, GARCH volatility reverts to
    its long-run level over the horizon: after a shock the 9-month band is less extreme,
    in calm times it widens towards normal. sigma_H is the RMS volatility over the
    window, the same unit z is measured in (standardised_h_changes).

    Falls back to EWMA when history < garch_min_obs, or the fit fails / does not converge
    / is not stationary. The reason is returned as the note, so the fallback rate can be
    reported (the plan asks for it).
    """
    z, sigma_ewma = standardised_h_changes(ctx, p["ewma_lambda"])
    if len(z) < MIN_PAST or not np.isfinite(sigma_ewma) or sigma_ewma <= 0:
        return None
    r = np.log(ctx.history).diff().dropna().to_numpy(float)
    if len(r) < p["garch_min_obs"]:
        sigma, note = sigma_ewma, "ewma fallback: short history"
    else:
        var, status = garch_variance_path(r, p["garch_o"], p["garch_dist"])
        if var is None:
            sigma, note = sigma_ewma, f"ewma fallback: {status}"
        else:
            sigma, note = float(np.sqrt(var[: ctx.h].mean())), status
    return sigma * (np.quantile(z, ctx.quantiles) - np.median(z)), note


@register("gjr_fhs", approach="direct", needs=("arch",))
def gjr_fhs(ctx: Context, p: dict) -> tuple[np.ndarray, str] | None:
    """garch_fhs with GJR-GARCH(1,1,1): price rises may raise volatility more than falls,
    which is the tail that hurts the margin. Same EWMA fallback."""
    return garch_fhs(ctx, {**p, "garch_o": 1})


@register("features_scaled", approach="direct")
def features_scaled(ctx: Context, p: dict) -> np.ndarray | None:
    """Median from the Step 4 features + volatility-scaled band around it.

        m_T = median quantile regression on the Step 4 selected features (same fit as
              Step 4 / Step 5: src.feature_selection._fit, training-window scaling)
        q_k = m_T + sigma_T * (quantile_k(z) - median(z))

    features_band = "residual": z_o = (y_o - m_o) / s_o, the in-sample residuals of the
    median model, so the band only covers what the features do not explain.
    features_band = "raw": z_o = y_o / s_o, the ewma_fhs band shifted to m_T.
    s_o and sigma_T as in ewma_fhs (in-window RMS, EWMA at T).

    Returns None in cells without Step 4 features (or outside feature_median_cells).
    """
    from src.feature_selection import _fit

    cells = p["feature_median_cells"]
    feats = ctx.features
    if not feats or (cells is not None and (ctx.target, ctx.h) not in cells):
        return None
    z_raw, sigma_T = standardised_h_changes(ctx, p["ewma_lambda"])
    tr = ctx.train.dropna(subset=feats)
    x = ctx.row[feats].to_numpy(float)
    if len(tr) < MIN_PAST or np.isnan(x).any() or not np.isfinite(sigma_T) or sigma_T <= 0:
        return None
    X, y = tr[feats].to_numpy(float), tr["y"].to_numpy(float)
    fit = _fit(X, y, [0.5], p["features_alpha_rel"])
    med = fit["models"][0]
    m_T = float(med.predict(((x - fit["mu"]) / fit["sd"]).reshape(1, -1))[0])
    s_o = window_rms(ctx).reindex(tr.index)
    ok = (s_o.notna() & (s_o > 0)).to_numpy()
    if p["features_band"] == "residual":
        resid = y - med.predict((X - fit["mu"]) / fit["sd"])
        z = resid[ok] / s_o.to_numpy()[ok]
    else:
        z = z_raw
    if len(z) < MIN_PAST:
        return None
    return m_T + sigma_T * (np.quantile(z, ctx.quantiles) - np.median(z))


SF_MIN_OBS = 36  # fewest monthly prices for a statsforecast fit
SF_MAX_H = 9  # one fit per target and origin serves every horizon


@lru_cache(maxsize=16384)
def _sf_cached(kind: str, buf: bytes, max_order: int) -> tuple[dict | None, str]:
    """Fit one statsforecast model on log prices and forecast months 1..SF_MAX_H with
    80 % and 90 % intervals. Cached on the exact content of the series (same input,
    same answer; different, e.g. poisoned, input can never hit the same entry)."""
    import warnings

    from statsforecast.models import AutoARIMA, AutoETS, AutoTheta

    y = np.frombuffer(buf, dtype=float)
    if kind == "ets":
        model = AutoETS(model="ZZN", season_length=1)  # no season (Step 3 / Step 4)
    elif kind == "arima":
        model = AutoARIMA(max_p=max_order, max_q=max_order, seasonal=False)
    else:
        model = AutoTheta(season_length=1)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            f = model.forecast(y=y, h=SF_MAX_H, level=[80, 90])
    except Exception as e:  # noqa: BLE001 - any numerical failure: no forecast
        return None, f"fit error ({type(e).__name__})"
    out = {k: np.asarray(v, dtype=float) for k, v in f.items()}
    if not all(np.all(np.isfinite(v)) for v in out.values()):
        return None, "non-finite forecast"
    return out, ""


def statsforecast_quantiles(ctx: Context, kind: str, max_order: int) -> np.ndarray | None:
    """P10 / P50 / P90 / P95 of y = log P[T+H] - log P[T] from a statsforecast model fitted
    on the log prices known at T (recursive: the model iterates 1-month forecasts).

    The intervals are the models' own (Gaussian) prediction intervals: P10 / P90 = the
    80 % interval, P95 = upper end of the 90 % interval, P50 = point forecast.
    """
    if ctx.history.empty or ctx.history.index[-1] != ctx.origin or len(ctx.history) < SF_MIN_OBS:
        return None
    lp = np.log(ctx.history.to_numpy(float))
    f, _ = _sf_cached(kind, np.ascontiguousarray(lp).tobytes(), max_order)
    if f is None:
        return None
    i = ctx.h - 1
    level = np.array([f["lo-80"][i], f["mean"][i], f["hi-80"][i], f["hi-90"][i]])
    return level - lp[-1]


@register("auto_ets", approach="recursive", needs=("statsforecast",))
def auto_ets(ctx: Context, p: dict) -> np.ndarray | None:
    """AutoETS on log prices, no season: picks error / trend type (incl. damped trend) by
    AICc at every origin. If it picks 'no trend', it is a smoothed random walk."""
    return statsforecast_quantiles(ctx, "ets", p["ets_max_order"])


@register("auto_arima", approach="recursive", needs=("statsforecast",))
def auto_arima(ctx: Context, p: dict) -> np.ndarray | None:
    """AutoARIMA on log prices, p, q <= ets_max_order (order selection is unstable on short
    series), no season. ARIMA(0,1,0) = the random walk; ARIMA(1,1,0) captures PPI momentum."""
    return statsforecast_quantiles(ctx, "arima", p["ets_max_order"])


@register("auto_theta", approach="recursive", needs=("statsforecast",))
def auto_theta(ctx: Context, p: dict) -> np.ndarray | None:
    """AutoTheta on log prices (M3 winner, about 2 parameters), no season."""
    return statsforecast_quantiles(ctx, "theta", p["ets_max_order"])


CHRONOS_MAX_H = 9
# P95 is outside the quantiles Chronos-Bolt was trained on (0.1 ... 0.9): it would return
# P90 again. It is extrapolated from the upper half of the distribution with the normal
# ratio z(0.95) / z(0.90); the conformal layer then corrects it from realised outcomes.
P95_FROM_P90 = 1.6448536 / 1.2815516


@lru_cache(maxsize=4)
def _chronos_pipeline(model: str, revision: str, device: str):
    """Load the pretrained model once per process (weights cached by Hugging Face)."""
    import torch
    from chronos import BaseChronosPipeline

    torch.manual_seed(SETTINGS["seed"])
    return BaseChronosPipeline.from_pretrained(model, revision=revision, device_map=device,
                                               dtype=torch.float32)


@lru_cache(maxsize=16384)
def _chronos_cached(buf: bytes, model: str, revision: str, device: str) -> np.ndarray:
    """Quantiles 0.1 / 0.5 / 0.9 of the price for months 1..CHRONOS_MAX_H, shape (H, 3).
    Cached on the exact content of the context series (leakage-safe, see GARCH)."""
    import torch

    pipe = _chronos_pipeline(model, revision, device)
    context = torch.tensor(np.frombuffer(buf, dtype=float), dtype=torch.float32)
    with torch.no_grad():
        q, _ = pipe.predict_quantiles(context, prediction_length=CHRONOS_MAX_H,
                                      quantile_levels=[0.1, 0.5, 0.9])
    return q[0].cpu().numpy().astype(float)


@register("chronos_bolt", approach="direct", needs=("torch", "chronos"))
def chronos_bolt(ctx: Context, p: dict) -> np.ndarray | None:
    """Chronos-Bolt (Amazon, pretrained time-series transformer), zero-shot: no training
    on our data. Its context is the target's monthly prices known at T (ctx.history),
    and it outputs quantiles of the price 1..9 months ahead directly (no recursion).

        q_k = log(price quantile_k at T+H / price at T),  P95 extrapolated (P95_FROM_P90)

    Deterministic (Bolt predicts quantiles, it does not sample); model revision pinned.
    Judge it on the hold-out only: the years before may be in its pretraining data.
    """
    if ctx.history.empty or ctx.history.index[-1] != ctx.origin or len(ctx.history) < SF_MIN_OBS:
        return None
    prices = np.ascontiguousarray(ctx.history.to_numpy(float))
    q = _chronos_cached(prices.tobytes(), p["chronos_model"], p["chronos_revision"],
                        p["chronos_device"])[ctx.h - 1]
    if np.any(q <= 0) or not np.all(np.isfinite(q)):
        return None
    p10, p50, p90 = np.log(q / prices[-1])
    p95 = p50 + P95_FROM_P90 * max(p90 - p50, 0.0)
    return np.array([p10, p50, p90, p95])


POOLED_FEATURES = ["mom_1m", "mom_3m", "is_ppi", "is_epoxy", "mom_1m_x_ppi", "mom_3m_x_ppi"]


def pooled_frame(price: pd.Series, h: int, lam: float, group: str) -> pd.DataFrame:
    """Rows of the pooled model for one series, from its known monthly prices.

    One row per month o:
      mom_1m, mom_3m   last 1- and 3-month log change, divided by the EWMA volatility at o
                       (momentum measured in units of the series' own volatility, so that
                       a steel PPI and nickel can share one coefficient)
      is_ppi, is_epoxy material group (market prices are the reference), and momentum x
                       PPI interactions: Step 3/4 found momentum in the PPIs, not in LME
                       prices, so the PPIs get their own momentum slope
      z                y / s_o, the H-month change in units of the volatility during the
                       window (as in standardised_h_changes); NaN when o + H is not known
      sigma            EWMA volatility at o
    Every column at month o uses prices up to o, except z, which uses prices up to o + H.
    """
    lp = np.log(price.dropna().asfreq("MS"))
    r = lp.diff()
    sigma = ewma_vol(r, lam).reindex(lp.index)
    s_win = np.sqrt((r ** 2).rolling(h).mean()).shift(-h)
    f = pd.DataFrame({
        "mom_1m": r / sigma,
        "mom_3m": (lp - lp.shift(3)) / sigma,
        "is_ppi": float(group == "ppi"),
        "is_epoxy": float(group == "epoxy"),
        "z": (lp.shift(-h) - lp) / s_win,
        "sigma": sigma,
    })
    f["mom_1m_x_ppi"] = f["mom_1m"] * f["is_ppi"]
    f["mom_3m_x_ppi"] = f["mom_3m"] * f["is_ppi"]
    return f


def pooled_training_data(known: pd.DataFrame, origin, h: int, lam: float,
                         groups: dict[str, list[str]]) -> tuple[np.ndarray, np.ndarray]:
    """Stacked (X, z) of every target, for origins o with o + H <= origin (outcome known).
    Built from `known` (the information set at the origin) only."""
    origin = pd.Timestamp(origin)
    parts = []
    for group, series in groups.items():
        for s in series:
            if s not in known:
                continue
            f = pooled_frame(known[s].loc[:origin], h, lam, group)
            f = f[f.index <= origin - pd.DateOffset(months=h)]
            parts.append(f[POOLED_FEATURES + ["z"]].replace([np.inf, -np.inf], np.nan).dropna())
    data = pd.concat(parts)
    return data[POOLED_FEATURES].to_numpy(float), data["z"].to_numpy(float)


_POOLED_FITS: dict[str, dict] = {}


def _pooled_fit(X: np.ndarray, z: np.ndarray, qs: tuple[float, ...], alpha_rel: float) -> dict:
    """Quantile regressions on the stacked data, cached on the exact content of (X, z).
    Every target at the same origin and horizon shares one fit; different (e.g.
    poisoned) data can never hit the same cache entry."""
    import hashlib

    from src.feature_selection import _fit

    key = hashlib.sha1(X.tobytes() + z.tobytes() + repr((qs, alpha_rel)).encode()).hexdigest()
    if key not in _POOLED_FITS:
        if len(_POOLED_FITS) > 2000:
            _POOLED_FITS.clear()
        _POOLED_FITS[key] = _fit(X, z, list(qs), alpha_rel)
    return _POOLED_FITS[key]


@register("pooled_qr", approach="direct")
def pooled_qr(ctx: Context, p: dict) -> np.ndarray | None:
    """One quantile regression fitted on all 15 targets stacked (a "global" model,
    Montero-Manso & Hyndman, 2021), on volatility-standardised H-month changes:

        quantile_k(z | x) = linear in POOLED_FEATURES  (one fit per quantile, L1 penalty)
        q_k               = sigma_T * quantile_k(z | x_T)

    ~15 x 100 training rows instead of ~100, so the P90 rests on ~150 observations above
    it instead of ~10. Unlike ewma_fhs, the median is not forced to 0: it moves with
    standardised momentum (separately for the PPIs).

    Training rows of every target are rebuilt from ctx.known (the information set at the
    origin) with o + H <= origin, so it stays leakage-free.
    """
    groups = p["pooled_groups"]
    group = next((g for g, s in groups.items() if ctx.target in s), None)
    if group is None:
        return None
    lam = p["ewma_lambda"]
    own = pooled_frame(ctx.known[ctx.target].loc[: ctx.origin], ctx.h, lam, group)
    if ctx.origin not in own.index:
        return None
    x = own.loc[ctx.origin, POOLED_FEATURES].to_numpy(float)
    sigma_T = own.at[ctx.origin, "sigma"]
    if not np.all(np.isfinite(x)) or not np.isfinite(sigma_T) or sigma_T <= 0:
        return None
    pool = next(pl for pl in p["pooled_pools"] if group in pl)
    X, z = pooled_training_data(ctx.known, ctx.origin, ctx.h, lam, {g: groups[g] for g in pool})
    if len(z) < 10 * MIN_PAST:
        return None
    fit = _pooled_fit(X, z, tuple(ctx.quantiles), p["pooled_alpha_rel"])
    xs = ((x - fit["mu"]) / fit["sd"]).reshape(1, -1)
    return sigma_T * np.array([m.predict(xs)[0] for m in fit["models"]])


# =========================================================================== post-processing
def backtest_only(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Rows usable for choosing anything: target month <= select_end. Raises on hold-out rows."""
    end = pd.Timestamp(cfg["selection"]["select_end"])
    out = df[pd.to_datetime(df["target_month"]) <= end]
    if out.empty:
        raise ValueError("No backtest rows: nothing may be chosen on the hold-out.")
    return out


def _tail_targets(cols: list[str]) -> dict[str, tuple[str, float]]:
    """Each non-median quantile column -> (side, target miss rate): p10 -> lower 10 %,
    p90 -> upper 10 %, p95 -> upper 5 %."""
    out = {}
    for c, q in zip(QCOLS, QUANTILES):
        if c in cols and c != "p50":
            out[c] = ("lower", q) if q < 0.5 else ("upper", 1 - q)
    return out


def _conformal_cell(g: pd.DataFrame, gamma: float, clip: float) -> pd.DataFrame:
    """Adaptive conformal on one target x horizon, walking forward in origin order."""
    g = g.sort_values("origin").reset_index(drop=True)
    tails = _tail_targets(list(g.columns))
    log_s = dict.fromkeys(tails, 0.0)
    cal = {c: np.full(len(g), np.nan) for c in tails}
    scale = {c: np.full(len(g), np.nan) for c in tails}
    origins = g["origin"].to_numpy()
    target_months = g["target_month"].to_numpy()
    y = g["y"].to_numpy(float)
    order = np.argsort(target_months, kind="stable")  # outcomes in the order they arrive
    next_out = 0
    for i, T in enumerate(origins):
        # 1. Learn from every outcome published by T (target month <= T), oldest first.
        #    Those forecasts were issued at origins <= T - H < T, so already calibrated.
        while next_out < len(order) and target_months[order[next_out]] <= T:
            j = order[next_out]
            next_out += 1
            if np.isnan(y[j]):
                continue
            for c, (side, rate) in tails.items():
                miss = y[j] < cal[c][j] if side == "lower" else y[j] > cal[c][j]
                log_s[c] = float(np.clip(log_s[c] + gamma * (miss - rate), -clip, clip))
        # 2. Calibrate the forecast issued at T with what has been learnt so far.
        p50 = g.at[i, "p50"]
        for c in tails:
            scale[c][i] = np.exp(log_s[c])
            cal[c][i] = p50 + scale[c][i] * (g.at[i, c] - p50)
    out = g.copy()
    for c in tails:
        out[c] = cal[c]
        out[f"scale_{c}"] = scale[c]
    cols = [c for c in QCOLS if c in out]
    out[cols] = np.sort(out[cols].to_numpy(float), axis=1)
    return out


def adaptive_conformal(pred: pd.DataFrame, gamma: float, clip: float = 2.0) -> pd.DataFrame:
    """Adaptive conformal calibration (in the spirit of Gibbs & Candes, 2021) of one
    model's quantiles. Works on any base model, since it only reads its predictions.

    Each tail is rescaled around the median by its own factor s, learnt online:

        p_c' = p50 + s_c * (p_c - p50)
        log s_c <- log s_c + gamma * (miss_c - target_c)

    with miss_c = 1 when the outcome fell outside the calibrated quantile c, and
    target_c = 10 % for p10 and p90, 5 % for p95. Each miss widens that tail by about
    gamma, each hit narrows it by gamma x target, so in the long run each tail is missed
    at its target rate, even when the regime changes. Tails are separate because price
    risk is skewed (Step 3). P50 is not changed, so the pinball gain comes from the band.

    Causal: the factor used at origin T only learns from outcomes with target_month <= T
    (forecasts issued at o <= T - H). s starts at 1 (trust the base model), log s is
    clipped to +-clip. Outcomes of H-month windows arrive in overlapping clumps, so gamma
    should stay small; it is chosen on the backtest (`tune_gamma`).
    """
    cells = [_conformal_cell(g, gamma, clip) for _, g in pred.groupby(["target", "horizon"])]
    out = pd.concat(cells, ignore_index=True)
    out["model"] = "conformal_" + out["model"].astype(str)
    return out


def _pinball_rows(df: pd.DataFrame) -> np.ndarray:
    qs = np.array([0.1, 0.5, 0.9])
    d = df["y"].to_numpy(float)[:, None] - df[["p10", "p50", "p90"]].to_numpy(float)
    return np.maximum(qs * d, (qs - 1) * d).mean(axis=1)


def tune_gamma(pred: pd.DataFrame, cfg: dict, grid: list[float] | None = None) -> pd.DataFrame:
    """Backtest pinball loss and coverage of the calibrated model for each gamma.

    gamma = 0 is the uncalibrated base model. Scored on backtest rows only
    (backtest_only), so the hold-out plays no part in the choice.
    """
    grid = grid if grid is not None else SETTINGS["conformal_gammas"]
    rows = []
    for gamma in grid:
        cal = adaptive_conformal(pred, gamma) if gamma > 0 else pred
        bt = backtest_only(cal.dropna(subset=["y"]), cfg)
        loss = bt.assign(loss=_pinball_rows(bt)).groupby(["target", "horizon"])["loss"].mean()
        cov = bt.assign(cov=(bt["y"] >= bt["p10"]) & (bt["y"] <= bt["p90"]))
        cov = cov.groupby(["target", "horizon"])["cov"].mean()
        rows.append({"gamma": gamma, "pinball": 100 * loss.mean(),
                     "coverage_80": cov.mean(), "coverage_gap": (cov - 0.8).abs().mean(),
                     "coverage_p90": (bt["y"] <= bt["p90"]).mean(),
                     "coverage_p95": (bt["y"] <= bt["p95"]).mean() if "p95" in bt else np.nan})
    return pd.DataFrame(rows)


def best_gamma(table: pd.DataFrame) -> float:
    """Lowest backtest pinball loss (calibration does not move P50, so pinball rewards
    the band that is both right and narrow)."""
    return float(table.loc[table["pinball"].idxmin(), "gamma"])


def conformal_leakage_check(pred: pd.DataFrame, gammas: list[float] | None = None,
                            origins: list | None = None, seed: int = 0,
                            calibrate: Callable | None = None) -> pd.DataFrame:
    """Poisoned-future test of the conformal layer, by default on EVERY origin and EVERY
    gamma of the tuning grid.

    For each origin T: every outcome not known at T (target_month > T) and every forecast
    issued after T is replaced with random numbers. Then every calibrated forecast issued
    at T or BEFORE must be identical to the clean run (not only the one at T: earlier
    forecasts must not move either). One row per (gamma, T).

    `calibrate` defaults to adaptive_conformal; the tests pass a deliberately leaky
    version to show the check has the power to catch one.
    """
    calibrate = calibrate or adaptive_conformal
    rng = np.random.default_rng(seed)
    gammas = gammas if gammas is not None else [g for g in SETTINGS["conformal_gammas"] if g > 0]
    origins = sorted(pd.to_datetime(origins if origins is not None else pred["origin"].unique()))
    cols = [c for c in QCOLS if c in pred]
    key = ["target", "horizon", "origin"]
    clean = {g: calibrate(pred, g).sort_values(key).reset_index(drop=True) for g in gammas}
    rows = []
    for T in origins:
        bad = pred.copy()
        hidden = bad["target_month"] > T
        bad.loc[hidden, "y"] = rng.uniform(-5, 5, hidden.sum())
        later = bad["origin"] > T
        bad.loc[later, cols] = np.sort(rng.uniform(-5, 5, (later.sum(), len(cols))), axis=1)
        n_hidden = int(hidden.sum() + later.sum())
        for g in gammas:
            poisoned = calibrate(bad, g).sort_values(key).reset_index(drop=True)
            upto = clean[g]["origin"] <= T
            a = clean[g].loc[upto, cols].to_numpy(float)
            b = poisoned.loc[upto.to_numpy(), cols].to_numpy(float)
            rows.append({"gamma": g, "origin": f"{T:%Y-%m}", "n_forecasts_checked": len(a),
                         "n_values_poisoned": n_hidden,
                         "unchanged": bool(len(a) and np.allclose(a, b, equal_nan=True))})
    return pd.DataFrame(rows)


def _backtest_metrics(preds: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Step 5 metrics (common origins per cell, skill vs random walk) on backtest rows only.
    `preds` must contain the random_walk baseline."""
    m = score(backtest_only(preds.dropna(subset=["y"]), cfg), cfg)
    return m[m["window"] == "backtest"]


def model_summary(metrics: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """One row per model: cells covered, mean backtest pinball skill vs random walk, mean
    P10-P90 coverage, and whether the coverage is acceptable (80 % +- combo_coverage_tol)."""
    n_cells = metrics.groupby(["target", "horizon"]).ngroups
    tol = SETTINGS["combo_coverage_tol"]
    out = metrics.groupby("model").agg(cells=("pinball", "size"),
                                       skill=("pinball_skill_vs_rw", "mean"),
                                       coverage=("coverage_80", "mean"))
    out["all_cells"] = out["cells"] == n_cells
    out["coverage_ok"] = (out["coverage"] - 0.8).abs() <= tol
    return out.sort_values("skill", ascending=False)


def select_members(metrics: pd.DataFrame, cfg: dict, n: int,
                   candidates: list[str] | None = None) -> list[str]:
    """The n "generalist" members of the combination, by the plan's rule (Step 7):
    first keep models whose coverage is acceptable, then take the lowest pinball loss
    (highest mean skill vs the random walk). Only models that forecast in EVERY
    target x horizon cell are generalists, so the ranking compares like with like.

    `metrics` must be backtest metrics (_backtest_metrics): never the hold-out.
    """
    if (metrics["window"] != "backtest").any():
        raise ValueError("select_members only accepts backtest metrics.")
    summ = model_summary(metrics, cfg)
    summ = summ[summ["all_cells"] & summ["coverage_ok"] & (summ.index != "random_walk")]
    if candidates is not None:
        summ = summ[summ.index.isin(candidates)]
    return list(summ.index[:n])


def combine(preds: pd.DataFrame, members: list[str], name: str = "combo",
            min_members: int = 2) -> pd.DataFrame:
    """Equal-weight average of the members' quantiles per target x horizon x origin
    (Lichtendahl et al., 2013: averaging quantiles), then sort_quantiles.

    Members that do not forecast a cell (e.g. a specialist outside its cells) or an
    origin are simply absent from that average; rows with fewer than `min_members`
    members are dropped. Each row only uses forecasts issued at that origin, so the
    combination is as causal as its members. `n_members` records how many were averaged.
    """
    cols = [c for c in QCOLS if c in preds]
    sub = preds[preds["model"].isin(members)]
    key = ["target", "horizon", "origin"]
    out = sub.groupby(key).agg(target_month=("target_month", "first"), y=("y", "first"),
                               n_members=("model", "nunique"),
                               **{c: (c, "mean") for c in cols}).reset_index()
    out = out[out["n_members"] >= min_members].copy()
    out[cols] = np.sort(out[cols].to_numpy(float), axis=1)
    out["model"] = name
    out["members"] = ", ".join(members)
    return out


def build_combination(preds: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Choose the combination on the backtest and return (combo predictions, decision log).

    1. Generalists: for each size N in combo_sizes, the best N models (select_members);
       keep the N with the lowest backtest pinball loss.
    2. Specialists (models covering only some cells, e.g. features_scaled) with acceptable
       coverage join as one extra equal-weight member in their own cells, only if their
       mean backtest skill on those cells beats the generalist combination on the same
       cells. One yes/no decision per specialist, not per cell (too few outcomes).
    Every choice uses backtest metrics only.
    """
    # Candidates: Step 6 base models only (+ the random walk, needed as the reference).
    preds = preds[preds["model"].isin(list(MODELS) + ["random_walk"])]
    metrics = _backtest_metrics(preds, cfg)
    summ = model_summary(metrics, cfg)
    log = []
    best = None
    for n in SETTINGS["combo_sizes"]:
        members = select_members(metrics, cfg, n)
        combo = combine(preds, members, name=f"combo_{n}")
        m = _backtest_metrics(pd.concat([preds, combo]), cfg)
        skill = m.loc[m["model"] == f"combo_{n}", "pinball_skill_vs_rw"].mean()
        log.append({"step": "size", "candidate": f"best {n}: {', '.join(members)}",
                    "backtest_skill": skill, "chosen": False})
        if best is None or skill > best[0]:
            best = (skill, n, members)
    _, n, members = best
    log[SETTINGS["combo_sizes"].index(n)]["chosen"] = True

    combo = combine(preds, members, name="combo")
    specialists = summ[~summ["all_cells"] & summ["coverage_ok"]].index
    for spec in specialists:
        m = _backtest_metrics(pd.concat([preds, combo]), cfg)
        cells = m.loc[m["model"] == spec, ["target", "horizon"]]
        on_cells = m.merge(cells, on=["target", "horizon"])
        s_spec = on_cells.loc[on_cells["model"] == spec, "pinball_skill_vs_rw"].mean()
        s_combo = on_cells.loc[on_cells["model"] == "combo", "pinball_skill_vs_rw"].mean()
        keep = bool(s_spec > s_combo)
        log.append({"step": "specialist", "candidate": f"{spec} on its {len(cells)} cells",
                    "backtest_skill": s_spec, "combo_skill_same_cells": s_combo, "chosen": keep})
        if keep:
            members = members + [spec]
            combo = combine(preds, members, name="combo")
    return combo, pd.DataFrame(log)


# =========================================================================== runners
def run_model(name: str, inputs: Inputs, tables: dict, selected: dict, cfg: dict,
              params: dict | None = None, targets: list[str] | None = None,
              horizons: list[int] | None = None) -> pd.DataFrame:
    """Rolling-origin predictions of one base model (same format as Step 5)."""
    params = {**SETTINGS, **(params or {})}
    fn = MODELS[name]["fn"]
    gap = cfg["settings"]["quote_gap_months"]
    keys = [(t, h) for (t, h) in tables
            if (targets is None or t in targets) and (horizons is None or h in horizons)]
    known_cache: dict[pd.Timestamp, pd.DataFrame] = {}
    rows = []
    for t, h in keys:
        table = tables[(t, h)]
        for T in evaluation_origins(table, cfg):
            if T not in known_cache:
                known_cache[T] = info_set(inputs, T, gap)
            ctx = build_context(inputs, table, t, h, T, selected.get((t, h), []), cfg,
                                known=known_cache[T])
            q, note = unpack(fn(ctx, params))
            if q is None:
                continue
            q = sort_quantiles(q)
            rows.append({"target": t, "horizon": h, "model": name, "origin": T,
                         "target_month": table.loc[T, "target_month"], "y": table.loc[T, "y"],
                         **dict(zip(QCOLS, q)), "n_train": len(ctx.train), "note": note})
    return pd.DataFrame(rows)


def load_predictions(models: list[str] | None = None, with_baselines: bool = True) -> pd.DataFrame:
    """Saved base / post-processed predictions, plus Step 5 baselines for comparison."""
    files = sorted(MODEL_DIR.glob("predictions_*.csv"))
    frames = [pd.read_csv(f, parse_dates=["origin", "target_month"]) for f in files]
    if with_baselines:
        frames.append(pd.read_csv(BASELINE_DIR / "predictions.csv",
                                  parse_dates=["origin", "target_month"]))
    pred = pd.concat(frames, ignore_index=True)
    if models is not None:
        pred = pred[pred["model"].isin(models + ["random_walk"])]
    return pred


def run_post(cfg: dict, models: list[str] | None = None) -> pd.DataFrame:
    """Stage 2, on the saved base-model predictions:
      1. conformal version of every base model (gamma tuned per model on the backtest);
      2. equal-weight combination of the best base models (build_combination), then its
         own conformal calibration (the plan: average quantiles, then recalibrate).
    Writes predictions_conformal_<model>.csv, predictions_combo.csv,
    predictions_conformal_combo.csv, conformal_gamma.csv and combo_selection.csv.

    Returns the gamma table (one row per model x gamma, `chosen` marks the selection).
    """
    tables = []
    for f in sorted(MODEL_DIR.glob("predictions_*.csv")):
        name = f.stem.removeprefix("predictions_")
        if name not in MODELS or (models is not None and name not in models):
            continue  # only base models are calibrated (not conformal_* or combo files)
        pred = pd.read_csv(f, parse_dates=["origin", "target_month"])
        table = tune_gamma(pred, cfg)
        gamma = best_gamma(table)
        table["model"], table["chosen"] = name, table["gamma"] == gamma
        tables.append(table)
        cal = adaptive_conformal(pred, gamma)
        cal["gamma"] = gamma
        cal.to_csv(MODEL_DIR / f"predictions_conformal_{name}.csv", index=False)
        print(f"conformal_{name}: gamma = {gamma} (chosen on the backtest)")

    base = load_predictions(models=[m for m in MODELS if (MODEL_DIR / f"predictions_{m}.csv").exists()])
    if base["model"].nunique() > 2:
        combo, decisions = build_combination(base, cfg)
        combo.to_csv(MODEL_DIR / "predictions_combo.csv", index=False)
        TABLE_DIR.mkdir(parents=True, exist_ok=True)
        decisions.round(4).to_csv(TABLE_DIR / "combo_selection.csv", index=False)
        table = tune_gamma(combo, cfg)
        gamma = best_gamma(table)
        table["model"], table["chosen"] = "combo", table["gamma"] == gamma
        tables.append(table)
        cal = adaptive_conformal(combo, gamma)
        cal["gamma"] = gamma
        cal.to_csv(MODEL_DIR / "predictions_conformal_combo.csv", index=False)
        print(f"combo: {combo['members'].iloc[0]}; conformal gamma = {gamma}")
    out = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
    if not out.empty:
        TABLE_DIR.mkdir(parents=True, exist_ok=True)
        out.round(4).to_csv(TABLE_DIR / "conformal_gamma.csv", index=False)
    return out


STEP8_DIR = MODEL_DIR / "step8"
STEP8_MODEL = "conformal_combo"  # the model whose marginals Step 8 rescales to


def export_residuals(cfg: dict, inputs: Inputs | None = None, model: str = STEP8_MODEL,
                     out_dir=STEP8_DIR) -> dict[str, pd.DataFrame]:
    """Inputs for the Step 8 joint simulation (PROPOSED format, to confirm with Step 8).

    Everything uses only data known at the live origin (Sep 2026, info_set). Targets are
    the 15 forecast targets; one column per target (wide), so a row is a joint draw.

    residuals_monthly.csv   month x target. e_t = r_t / sigma_{t-1}: monthly log return
                            divided by the EWMA volatility known the month before
                            (filtered historical simulation). Rows of the same month keep
                            the cross-material dependence, including the 2021-22 crisis
                            co-movement; block bootstrap them (blocks of 3-6 months keep
                            the PPI momentum). NaN before a series starts (epoxy: 2018).
    joint_z_h{H}.csv        origin x target. z_o = (log P[o+H] - log P[o]) / RMS of the
                            monthly returns inside (o, o+H]: the standardised H-month
                            changes the Step 6 models use. A row is one historical joint
                            H-month scenario (overlapping windows). Ready for an empirical
                            copula / Schaake shuffle: use the ranks of a row to order
                            draws from each material's marginal below.
    marginals_202609.csv    target x horizon from `model`: P10 / P50 / P90 / P95 of the
                            H-month log change, the same as price ratios exp(q) = driver at
                            T+H / driver at T (what cost_model.bom_index takes), and
                            sigma_T, the EWMA monthly volatility at the origin (to rescale
                            residuals: r = sigma_T x e).
    """
    from src.features import load_inputs

    inputs = inputs if inputs is not None else load_inputs()
    lam = SETTINGS["ewma_lambda"]
    targets = [t for g in SETTINGS["pooled_groups"].values() for t in g]
    preds = pd.read_csv(MODEL_DIR / f"predictions_{model}.csv", parse_dates=["origin", "target_month"])
    origin = preds["origin"].max()
    known = info_set(inputs, origin, cfg["settings"]["quote_gap_months"])

    resid, sigma_T, joint = {}, {}, {h: {} for h in cfg["settings"]["horizons"]}
    for t in targets:
        lp = np.log(known[t].loc[:origin].dropna().asfreq("MS"))
        r = lp.diff()
        sigma = ewma_vol(r, lam).reindex(lp.index)
        resid[t] = r / sigma.shift(1)
        sigma_T[t] = sigma.get(origin, np.nan)
        for h, cols in joint.items():
            s_win = np.sqrt((r ** 2).rolling(h).mean()).shift(-h)
            cols[t] = (lp.shift(-h) - lp) / s_win
    out = {"residuals_monthly": pd.DataFrame(resid).loc[:origin]}
    for h, cols in joint.items():
        z = pd.DataFrame(cols).loc[: origin - pd.DateOffset(months=h)]
        out[f"joint_z_h{h}"] = z.replace([np.inf, -np.inf], np.nan).dropna(how="all")
    out["residuals_monthly"] = out["residuals_monthly"].replace([np.inf, -np.inf], np.nan).dropna(how="all")

    live = preds[preds["origin"] == origin].copy()
    marg = live[["target", "horizon", "origin", "target_month"] + QCOLS].copy()
    for c in QCOLS:
        marg[f"ratio_{c}"] = np.exp(marg[c])
    marg["sigma_T"] = marg["target"].map(sigma_T)
    marg["model"] = model
    marg = marg.sort_values(["target", "horizon"]).reset_index(drop=True)
    out["marginals_202609"] = marg  # key kept for the tests; the file is named by the origin

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in out.items():
        if name == "marginals_202609":
            df.to_csv(out_dir / f"marginals_{origin:%Y%m}.csv", index=False)
        else:
            df.to_csv(out_dir / f"{name}.csv", index_label="month")
    return out


# =========================================================================== diagnostics
def residual_checks(inputs: Inputs, cfg: dict, lags: tuple[int, ...] = (6, 12)) -> pd.DataFrame:
    """Ljung-Box tests on the residuals and squared residuals of the models (plan Step 6),
    per target, on the data known at the end of the backtest window (select_end).

    Rows ("series"):
      returns            monthly log returns: the starting point (autocorrelation and
                         volatility clustering present before any model)
      ewma_standardised  e_t = r_t / sigma_{t-1}, EWMA (ewma_fhs and the combination):
                         squared e must show no clustering left; e itself may stay
                         autocorrelated for the PPIs, which the direct H-month models handle
      garch_standardised standardised residuals of the GARCH(1,1)-t fit (garch_fhs), when
                         it converges and is stationary
      arima, ets         in-sample one-step residuals of AutoARIMA / AutoETS
    A p-value below 0.05 means autocorrelation is left. Small samples: the tests have low
    power, so "not rejected" does not prove there is none.
    """
    import warnings

    from statsforecast.models import AutoARIMA, AutoETS
    from statsmodels.stats.diagnostic import acorr_ljungbox

    end = pd.Timestamp(cfg["selection"]["select_end"])
    known = info_set(inputs, end, cfg["settings"]["quote_gap_months"])
    rows = []

    def lb(x: np.ndarray, target: str, series: str) -> None:
        x = np.asarray(x, dtype=float)
        x = x[np.isfinite(x)]
        if len(x) < 3 * max(lags):
            return
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            p_lin = acorr_ljungbox(x, lags=list(lags), return_df=True)["lb_pvalue"]
            p_sq = acorr_ljungbox(x ** 2, lags=list(lags), return_df=True)["lb_pvalue"]
        row = {"target": target, "series": series, "n": len(x)}
        for k in lags:
            row[f"p_resid_lag{k}"] = float(p_lin[k])
            row[f"p_squared_lag{k}"] = float(p_sq[k])
        rows.append(row)

    for t in [t for g in SETTINGS["pooled_groups"].values() for t in g]:
        lp = np.log(known[t].loc[:end].dropna().asfreq("MS"))
        r = lp.diff()
        lb(r.dropna(), t, "returns")
        sigma = ewma_vol(r, SETTINGS["ewma_lambda"]).reindex(lp.index)
        lb((r / sigma.shift(1)).dropna(), t, "ewma_standardised")
        rr = r.dropna().to_numpy(float)
        # No GARCH row when the fit fails or is not stationary (the model then uses EWMA).
        with contextlib.suppress(Exception), warnings.catch_warnings():
            from arch import arch_model

            warnings.simplefilter("ignore")
            res = arch_model(100 * rr, mean="Zero", vol="GARCH", p=1, q=1, dist="t",
                             rescale=False).fit(disp="off", show_warning=False)
            prm = res.params
            if res.convergence_flag == 0 and prm["alpha[1]"] + prm["beta[1]"] < 0.999:
                lb(res.std_resid, t, "garch_standardised")
        y = lp.dropna().to_numpy(float)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            a = AutoARIMA(max_p=SETTINGS["ets_max_order"], max_q=SETTINGS["ets_max_order"],
                          seasonal=False).fit(y)
            e = AutoETS(model="ZZN", season_length=1).fit(y)
        lb(np.asarray(a.model_["residuals"])[1:], t, "arima")
        lb((y - e.predict_in_sample()["fitted"])[1:], t, "ets")
    return pd.DataFrame(rows)


def covariate_check(inputs: Inputs, tables: dict, selected: dict, cfg: dict) -> pd.DataFrame:
    """Which covariates features_scaled relies on, and whether the fitted effect on the
    median has the sign the Step 4 cause -> effect chain predicts (configs/features.yaml).

    Fitted twice with the model's own code: on the backtest window (end of select_end)
    and at the live origin (all data). The coefficient is per one standard deviation of
    the feature, in log-change units. Wording: the feature "helps predict", not "causes".
    """
    from src.feature_selection import _fit
    from src.features import candidate_specs

    end = pd.Timestamp(cfg["selection"]["select_end"])
    rows = []
    for (t, h), feats in selected.items():
        if not feats:
            continue
        specs = candidate_specs(cfg, t)
        table = tables[(t, h)]
        for label, T in [("backtest", end), ("live", table.index[-1])]:
            tr = table[table["y"].notna() & (table["target_month"] <= T)].dropna(subset=feats)
            fit = _fit(tr[feats].to_numpy(float), tr["y"].to_numpy(float), [0.5],
                       SETTINGS["features_alpha_rel"])
            for j, f in enumerate(feats):
                coef = float(fit["models"][0].coef_[j])
                exp = str(specs[f]["sign"])
                agrees = True if exp not in ("+", "-") else (coef > 0 if exp == "+" else coef < 0)
                rows.append({"target": t, "horizon": h, "feature": f, "fit": label,
                             "group": specs[f]["group"], "expected_sign": exp,
                             "coef_median_per_sd": coef, "sign_agrees": agrees,
                             "label": specs[f].get("label", "")})
    return pd.DataFrame(rows)


# =========================================================================== hold-out
FINAL_MODEL = "conformal_combo"
FREEZE_FILE = TABLE_DIR / "holdout_freeze.json"


def freeze_manifest(cfg: dict) -> dict:
    """Fingerprint (sha256) of every prediction file and decision table, plus the settings.
    Written BEFORE the hold-out is opened: if any of these changes afterwards, a choice
    was made after seeing the hold-out, and holdout_evaluation refuses to run."""
    import hashlib

    files = sorted(MODEL_DIR.glob("predictions_*.csv")) + [
        BASELINE_DIR / "predictions.csv", TABLE_DIR / "combo_selection.csv",
        TABLE_DIR / "conformal_gamma.csv"]
    missing = [str(f) for f in files if not f.exists()]
    if missing:
        raise FileNotFoundError(f"Run the full pipeline first; missing: {missing}")
    return {"final_model": FINAL_MODEL, "select_end": cfg["selection"]["select_end"],
            "settings": {k: v for k, v in SETTINGS.items()},
            "files": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}


def _block_bootstrap_ci(per_origin: pd.DataFrame, stat: Callable, block: int,
                        n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95 % moving-block bootstrap CI of stat(rows), resampling whole origins (all targets
    of an origin move together) in blocks of `block` months (overlapping H-month windows)."""
    rng = np.random.default_rng(seed)
    n = len(per_origin)
    if n < 2 * block:
        return np.nan, np.nan
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(n_boot, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)).reshape(n_boot, -1)[:, :n]
    vals = np.array([stat(per_origin.iloc[i]) for i in idx])
    return tuple(np.nanpercentile(vals, [2.5, 97.5]))


def beats_naive(preds: pd.DataFrame, model: str, cfg: dict) -> pd.DataFrame:
    """The jury table, per horizon over all targets: pinball and MAE skill vs the random
    walk, P10-P90 coverage (target 80 %) and one-sided P90 coverage (target 90 %), each with
    a 95 % block-bootstrap CI. Rows are matched with the random walk on (target, H, origin)."""
    qs = np.array([0.1, 0.5, 0.9])
    rows = []
    for h, g in preds[preds["model"].isin([model, "random_walk"])].groupby("horizon"):
        m = g[g["model"] == model].merge(g[g["model"] == "random_walk"],
                                         on=["target", "horizon", "origin"], suffixes=("", "_rw"))
        if m.empty:
            continue
        for sfx in ("", "_rw"):
            d = m["y"].to_numpy(float)[:, None] - m[[f"p10{sfx}", f"p50{sfx}", f"p90{sfx}"]].to_numpy(float)
            m[f"pin{sfx}"] = np.maximum(qs * d, (qs - 1) * d).mean(axis=1)
            m[f"ae{sfx}"] = np.abs(m["y"] - m[f"p50{sfx}"])
        m["cov80"] = ((m["y"] >= m["p10"]) & (m["y"] <= m["p90"])).astype(float)
        m["cov90"] = (m["y"] <= m["p90"]).astype(float)
        po = m.groupby("origin")[["pin", "pin_rw", "ae", "ae_rw", "cov80", "cov90"]].agg(["sum", "count"])
        po = pd.DataFrame({c: po[(c, "sum")] for c in ["pin", "pin_rw", "ae", "ae_rw", "cov80", "cov90"]}
                          | {"n": po[("cov80", "count")]})
        stats = {
            "pinball_skill": lambda x: 1 - x["pin"].sum() / x["pin_rw"].sum(),
            "mae_skill": lambda x: 1 - x["ae"].sum() / x["ae_rw"].sum(),
            "coverage_80": lambda x: x["cov80"].sum() / x["n"].sum(),
            "coverage_p90": lambda x: x["cov90"].sum() / x["n"].sum(),
        }
        row = {"model": model, "horizon": h, "n_forecasts": int(po["n"].sum()),
               "n_origins": len(po), "independent_windows": round(len(po) / h, 1)}
        for name, f in stats.items():
            lo, hi = _block_bootstrap_ci(po, f, block=h)
            row[name], row[f"{name}_lo"], row[f"{name}_hi"] = f(po), lo, hi
        row["beats_naive_pinball"] = row["pinball_skill"] > 0
        row["beats_naive_pinball_ci"] = bool(row["pinball_skill_lo"] > 0)
        row["beats_naive_mae"] = row["mae_skill"] > 0
        rows.append(row)
    return pd.DataFrame(rows)


def holdout_evaluation(cfg: dict) -> dict[str, pd.DataFrame]:
    """The single hold-out evaluation (Apr 2025 -> Sep 2026 target months).

    1. Freeze: writes holdout_freeze.json (hashes of every prediction file and decision
       table + settings) before any hold-out outcome is read. If the file already exists
       and anything has changed since, it refuses: a choice was changed after the
       hold-out was opened. Re-running with nothing changed reproduces the same numbers.
    2. Scores every model on the hold-out (Step 5 metrics, common origins per cell).
    3. "Beats the random walk?" per horizon for the final model and the main
       alternatives, with block-bootstrap CIs.
    4. The same on the STRICT hold-out: origins from select_end on, so that no part of
       an outcome window was visible when anything was chosen (relevant for H = 6, 9).
    """
    import json

    manifest = freeze_manifest(cfg)
    if FREEZE_FILE.exists():
        old = json.loads(FREEZE_FILE.read_text())
        changed = [f for f, h in manifest["files"].items() if old["files"].get(f) != h]
        if changed or old["settings"] != json.loads(json.dumps(manifest["settings"], default=str)):
            raise RuntimeError(
                "The hold-out was already opened with different predictions or settings "
                f"(changed: {changed or 'settings'}). Results after that are no longer a clean "
                f"hold-out. Delete {FREEZE_FILE.name} only if you accept that and say so in the report.")
    else:
        TABLE_DIR.mkdir(parents=True, exist_ok=True)
        FREEZE_FILE.write_text(json.dumps(manifest, indent=2, default=str))

    end = pd.Timestamp(cfg["selection"]["select_end"])
    preds = load_predictions().dropna(subset=["y"])
    hold = preds[preds["target_month"] > end]
    strict = hold[hold["origin"] >= end]
    out = {}
    for name, df in [("holdout", hold), ("holdout_strict", strict)]:
        m = score(df, cfg)
        out[f"{name}_metrics"] = m
        compare = [FINAL_MODEL, "combo", "gjr_fhs", "ewma_fhs", "chronos_bolt", "auto_theta",
                   "features_qr", "lme_forward"]
        out[f"{name}_beats_naive"] = pd.concat(
            [beats_naive(df, mdl, cfg) for mdl in compare if mdl in set(df["model"])],
            ignore_index=True)
    bt = _backtest_metrics(preds, cfg).groupby("model")[["pinball_skill_vs_rw", "coverage_80"]].mean()
    ho = out["holdout_metrics"].groupby("model")[["pinball_skill_vs_rw", "coverage_80"]].mean()
    out["backtest_vs_holdout"] = bt.add_suffix("_backtest").join(ho.add_suffix("_holdout")).sort_values(
        "pinball_skill_vs_rw_holdout", ascending=False)
    for name, df in out.items():
        df.round(4).to_csv(TABLE_DIR / f"{name}.csv", index=name == "backtest_vs_holdout")
    return out


# =========================================================================== leakage test
def poisoned_future_check(name: str, inputs: Inputs, tables: dict, selected: dict, cfg: dict,
                          n: int | None = None, seed: int = 0, targets: list[str] | None = None,
                          horizons: list[int] | None = None,
                          params: dict | None = None) -> pd.DataFrame:
    """Replace everything NOT known at origin T with random numbers; the forecast at T
    must not change. Covers the panel (values not yet published at T), the feature tables
    (rows after T, and y of rows whose target month is after T) and any model state.

    By default EVERY origin where any target x horizon is forecast (backtest, hold-out and
    the live Sep 2026 row) is tested; `n` draws a random subset for a quick run.

    The shared objects themselves (inputs.data and the tables) are poisoned IN PLACE and
    restored afterwards, so a model that reads them through a global or a cached
    reference, instead of through its Context, is caught too.
    """
    rng = np.random.default_rng(seed)
    gap = cfg["settings"]["quote_gap_months"]
    params = {**SETTINGS, **(params or {})}
    fn = MODELS[name]["fn"]
    rows = []
    keys = [(t, h) for (t, h) in tables
            if (targets is None or t in targets) and (horizons is None or h in horizons)]
    candidates = sorted({T for k in keys for T in evaluation_origins(tables[k], cfg)})
    if n is not None and n < len(candidates):
        candidates = sorted(rng.choice(candidates, size=n, replace=False))
    for T in candidates:
        T = pd.Timestamp(T)
        clean = {}
        for t, h in keys:
            if T in tables[(t, h)].index:
                ctx = build_context(inputs, tables[(t, h)], t, h, T, selected.get((t, h), []), cfg)
                clean[(t, h)] = unpack(fn(ctx, params))
        data_orig = inputs.data.copy()
        tables_orig = {k: tables[k].copy() for k in clean}
        try:
            hidden = info_set(inputs, T, gap).reindex(inputs.data.index).isna() & inputs.data.notna()
            noise = rng.uniform(1, 1e6, inputs.data.shape)
            inputs.data[:] = np.where(hidden.to_numpy(), noise, inputs.data.to_numpy())
            for k in clean:
                df = tables[k]
                num = df.columns.drop(["y", "target_month"])
                later = df.index > T
                df.loc[later, num] = rng.uniform(-5, 5, (later.sum(), len(num)))
                future_y = df["target_month"] > T
                df.loc[future_y, "y"] = rng.uniform(-5, 5, future_y.sum())
            for (t, h), a in clean.items():
                ctx = build_context(inputs, tables[(t, h)], t, h, T, selected.get((t, h), []), cfg)
                (qa, na), (qb, nb) = a, unpack(fn(ctx, params))
                same = na == nb and ((qa is None and qb is None) or (
                    qa is not None and qb is not None and np.allclose(qa, qb, equal_nan=True)))
                rows.append({"model": name, "origin": f"{T:%Y-%m}", "target": t, "horizon": h,
                             "unchanged": bool(same)})
        finally:
            inputs.data[:] = data_orig.to_numpy()
            for k, df in tables_orig.items():
                tables[k].loc[:, :] = df
    return pd.DataFrame(rows)


# =========================================================================== CLI
def main() -> None:
    parser = argparse.ArgumentParser(description="Step 6 forecasting models")
    parser.add_argument("--model", nargs="+", choices=sorted(MODELS), help="base models to run (default: all)")
    parser.add_argument("--targets", nargs="+", help="e.g. S09 D01 (default: all 15)")
    parser.add_argument("--horizons", nargs="+", type=int, choices=[3, 6, 9])
    parser.add_argument("--stage", choices=["base", "post", "export", "all", "holdout"], default="all",
                        help="base models, post (conformal + combination), export (Step 8 "
                             "inputs); holdout = the single final evaluation (not part of all)")
    parser.add_argument("--check-leakage", action="store_true", help="run the poisoned-future test")
    args = parser.parse_args()

    cfg = load_config()
    inputs = load_inputs()
    tables = load_tables(cfg)
    selected = load_selected()
    names = args.model or sorted(MODELS)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    if args.check_leakage:
        # Every origin. Base models: poisoned panel + tables. Conformal layer: every gamma
        # of the grid, on the model's saved predictions (run the model first).
        parts = []
        for m in names:
            try:
                parts.append(poisoned_future_check(m, inputs, tables, selected, cfg,
                                                   targets=args.targets, horizons=args.horizons))
            except (NotImplementedError, ImportError) as e:
                print(f"{m}: skipped ({type(e).__name__})")
                continue
            f = MODEL_DIR / f"predictions_{m}.csv"
            if f.exists():
                pred = pd.read_csv(f, parse_dates=["origin", "target_month"])
                parts.append(conformal_leakage_check(pred).assign(model=f"conformal_{m}"))
        test = pd.concat(parts, ignore_index=True)
        test.to_csv(TABLE_DIR / "leakage_test.csv", index=False)
        print(test.groupby("model")["unchanged"].agg(["sum", "count"]).to_string())
        if not test["unchanged"].all():
            raise AssertionError("Leakage: a forecast changed when future data was altered")
        return

    if args.stage == "holdout":
        out = holdout_evaluation(cfg)
        cols = ["model", "horizon", "pinball_skill", "pinball_skill_lo", "pinball_skill_hi",
                "coverage_80", "coverage_p90", "beats_naive_pinball_ci"]
        print(out["holdout_beats_naive"][cols].round(3).to_string(index=False))
        return

    if args.stage in ("base", "all"):
        for m in names:
            try:
                pred = run_model(m, inputs, tables, selected, cfg,
                                 targets=args.targets, horizons=args.horizons)
            except (NotImplementedError, ImportError) as e:
                print(f"{m}: skipped ({type(e).__name__})")
                continue
            pred.to_csv(MODEL_DIR / f"predictions_{m}.csv", index=False)
            print(f"{m}: {len(pred)} forecasts")
    if args.stage in ("post", "all"):
        run_post(cfg)
    if args.stage in ("export", "all"):
        export_residuals(cfg, inputs)
        print(f"Step 8 inputs written to {STEP8_DIR}")
        if args.stage == "export":
            return
    metrics = score(load_predictions(), cfg)
    metrics.round(4).to_csv(TABLE_DIR / "metrics.csv", index=False)


if __name__ == "__main__":
    main()
