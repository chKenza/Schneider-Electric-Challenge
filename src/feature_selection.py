"""Step 4 – choose 5-8 features per target and horizon, with the evidence for each choice.

Run from the repo root, after src.features:

    uv run python -m src.feature_selection

Evidence collected for every candidate (selection window only; the last 18 months are
kept for the Step 7 hold-out and never used here):
  1. economic logic       configs/features.yaml (why, expected sign, delay)
  2. own-price lags       ACF / PACF of monthly log changes
  3. lead-lag             rank correlation between the feature and the H-month change
  4. Granger test         does the driver's past help predict the target beyond its own past?
                          (lags 1-3, Holm correction over all tests)
  5. backtest gain        rolling-origin quantile regression: % change in pinball loss
                          when the feature is added
  6. sign check           the fitted effect must have the sign economics predicts

Selection: forward selection on the backtest pinball loss, first among own-price
features (from an intercept-only model), then among drivers that pass checks 4 or 3
and check 6. A feature must cut the loss by at least 1 %. At most 4 + 4 features.
Robustness gate at the end: each kept feature, tested last, must still cut the loss by
1 %, help in at least 80 % of block-bootstrap resamples, and (volatility features only)
widen the P10-P90 band.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy import stats
from sklearn.linear_model import QuantileRegressor
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.stattools import acf, grangercausalitytests, pacf

from src.data_prep import OUT
from src.features import FEATURE_DIR, candidate_specs, load_config

SELECTION_DIR = OUT / "feature_selection"


def load_tables(cfg: dict) -> dict:
    tables = {}
    for t in cfg["targets"]:
        for h in cfg["settings"]["horizons"]:
            df = pd.read_csv(FEATURE_DIR / f"{t}_h{h}.csv", index_col=0, parse_dates=["origin", "target_month"])
            tables[(t, h)] = df
    return tables


def monthly_change(data: pd.DataFrame, target: str, end: str) -> pd.Series:
    return np.log(data[target]).diff().loc[:end].dropna()


# --------------------------------------------------------------------------- 2. ACF / PACF
def acf_pacf_table(data: pd.DataFrame, cfg: dict, nlags: int = 12) -> pd.DataFrame:
    end = cfg["selection"]["select_end"]
    rows = []
    for t in cfg["targets"]:
        r = monthly_change(data, t, end)
        a, p = acf(r, nlags=nlags), pacf(r, nlags=nlags, method="ywm")
        band = 1.96 / np.sqrt(len(r))
        for k in range(1, nlags + 1):
            rows.append({"target": t, "lag": k, "acf": a[k], "pacf": p[k], "band": band, "n": len(r)})
    return pd.DataFrame(rows)


def own_lag_decision(ap: pd.DataFrame) -> pd.DataFrame:
    """own_chg_1m is a candidate only if the lag-1 partial autocorrelation is significant."""
    lag1 = ap[ap["lag"] == 1].set_index("target")
    out = lag1[["pacf", "band"]].copy()
    out["own_chg_1m_candidate"] = lag1["pacf"].abs() > lag1["band"]
    sig = ap[ap["pacf"].abs() > ap["band"]].groupby("target")["lag"].apply(lambda s: ", ".join(map(str, s)))
    out["significant_pacf_lags"] = sig.reindex(out.index).fillna("none")
    return out


# --------------------------------------------------------------------------- seasonality
def seasonality_table(data: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """F-test that the 12 calendar-month means of monthly changes are equal; Holm over targets."""
    end = cfg["selection"]["select_end"]
    rows = []
    for t in cfg["targets"]:
        r = monthly_change(data, t, end)
        _, p = stats.f_oneway(*[g.values for _, g in r.groupby(r.index.month)])
        rows.append({"target": t, "p_value": p})
    df = pd.DataFrame(rows).set_index("target")
    df["p_holm"] = multipletests(df["p_value"], method="holm")[1]
    df["calendar_features"] = df["p_holm"] < 0.05
    return df


# --------------------------------------------------------------------------- 3. lead-lag
def selection_rows(df: pd.DataFrame, end: str) -> pd.DataFrame:
    return df[df["y"].notna() & (df["target_month"] <= pd.Timestamp(end))]


def correlation_table(tables: dict, cfg: dict) -> pd.DataFrame:
    end = cfg["selection"]["select_end"]
    rows = []
    for (t, h), df in tables.items():
        sel = selection_rows(df, end)
        for f in candidate_specs(cfg, t):
            pair = sel[[f, "y"]].dropna()
            rho = stats.spearmanr(pair[f], pair["y"]).statistic if len(pair) > 10 else np.nan
            n_eff = len(pair) / h  # overlapping H-month windows
            rows.append({"target": t, "horizon": h, "feature": f, "n": len(pair),
                         "spearman": rho, "band": 1.96 / np.sqrt(max(n_eff, 1))})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- 4. Granger
def granger_table(data: pd.DataFrame, tables: dict, cfg: dict) -> pd.DataFrame:
    """Granger test: driver values at o-1..o-3 → target change into month o.

    Uses the H=3 table only for the feature values (drivers do not depend on H, except
    STEO forecasts, which are not a past series and are not tested).
    """
    sel = cfg["selection"]
    rows = []
    for t in cfg["targets"]:
        df = tables[(t, cfg["settings"]["horizons"][0])]
        # Change of the target into month o. The test regresses it on its own 3 past
        # values and on the driver's value at o-1, o-2, o-3 (each known at that origin).
        dy = np.log(data[t]).diff()
        for f, spec in candidate_specs(cfg, t).items():
            if spec["group"] != "driver" or spec["kind"] == "steo_change":
                continue
            arr = pd.concat([dy.rename("y"), df[f]], axis=1).loc[: sel["select_end"]].dropna()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = grangercausalitytests(arr.values, maxlag=[sel["granger_lags"]])
            p = res[sel["granger_lags"]][0]["ssr_ftest"][1]
            rows.append({"target": t, "feature": f, "n": len(arr), "granger_p": p})
    df = pd.DataFrame(rows)
    df["granger_p_holm"] = multipletests(df["granger_p"], method="holm")[1]
    return df


# --------------------------------------------------------------------------- 5. backtest
def pinball(y: float, q_pred: np.ndarray, qs: list[float]) -> float:
    return float(np.mean([max(q * (y - p), (q - 1) * (y - p)) for q, p in zip(qs, q_pred)]))


def _fit(Xtr: np.ndarray, ytr: np.ndarray, qs: list[float], alpha_rel: float):
    """Quantile regressions on standardised features (training-window mean and std only)."""
    if Xtr.shape[1] == 0:
        return {"quantiles": np.array([np.quantile(ytr, q) for q in qs])}
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd == 0] = 1
    alpha = alpha_rel * np.mean(np.abs(ytr - np.median(ytr)))
    models = [QuantileRegressor(quantile=q, alpha=alpha, solver="highs").fit((Xtr - mu) / sd, ytr)
              for q in qs]
    return {"mu": mu, "sd": sd, "models": models}


def _predict(fitted: dict, x: np.ndarray) -> np.ndarray:
    if "quantiles" in fitted:
        return fitted["quantiles"]
    z = ((x - fitted["mu"]) / fitted["sd"]).reshape(1, -1)
    return np.sort([m.predict(z)[0] for m in fitted["models"]])  # p10 <= p50 <= p90


def backtest_loss(df: pd.DataFrame, feats: list[str], h: int, cfg: dict, end: str,
                  rows_mask: pd.Series | None = None, per_origin: bool = False):
    """Mean pinball loss of a rolling-origin quantile regression using `feats`.

    At each evaluation origin T, the model is trained on origins o with o + H <= T
    (their y is already known at T) and predicts y at T. Refit every `refit_every` months.
    """
    sel = cfg["selection"]
    qs = sel["quantiles"]
    data = selection_rows(df, end)
    if rows_mask is not None:
        data = data[rows_mask.reindex(data.index).fillna(False)]
    data = data.dropna(subset=feats)
    if len(data) < sel["min_train_months"] + 6:
        return pd.Series(dtype=float) if per_origin else np.nan
    first_eval = data.index[0] + pd.DateOffset(months=sel["min_train_months"])
    evals = data.index[data.index >= first_eval]
    losses, fitted, last_fit = [], None, None
    for T in evals:
        if last_fit is None or (T - last_fit).days >= 28 * sel["refit_every"]:
            train = data[data["target_month"] <= T]
            fitted = _fit(train[feats].to_numpy(float), train["y"].to_numpy(float),
                          qs, sel["alpha_rel"])
            last_fit = T
        pred = _predict(fitted, data.loc[T, feats].to_numpy(float))
        losses.append(pinball(data.loc[T, "y"], pred, qs))
    if per_origin:
        return pd.Series(losses, index=evals)
    return float(np.mean(losses))


def gain(df, base, add, h, cfg, end) -> float:
    """% change in backtest pinball loss when `add` is added to `base` (same rows for both)."""
    mask = df[base + [add]].notna().all(axis=1)
    l0 = backtest_loss(df, base, h, cfg, end, mask)
    l1 = backtest_loss(df, base + [add], h, cfg, end, mask)
    return l1 / l0 - 1 if l0 and not np.isnan(l0) else np.nan


def gain_confidence(df, base, add, h, cfg, end, n_boot: int = 2000, seed: int = 0) -> dict:
    """How sure are we that adding `add` really helps? Moving-block bootstrap of the
    per-origin loss differences (blocks of H months, because H-month targets overlap).

    Returns the gain (% change in loss) and the share of bootstrap samples where the
    feature lowers the loss.
    """
    mask = df[base + [add]].notna().all(axis=1)
    l0 = backtest_loss(df, base, h, cfg, end, mask, per_origin=True)
    l1 = backtest_loss(df, base + [add], h, cfg, end, mask, per_origin=True)
    d = (l1 - l0).dropna().to_numpy()
    if len(d) < 2 * h:
        return {"gain": np.nan, "p_helps": np.nan, "n_eval": len(d)}
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(len(d) / h))
    starts = rng.integers(0, len(d) - h + 1, size=(n_boot, n_blocks))
    idx = (starts[:, :, None] + np.arange(h)).reshape(n_boot, -1)[:, : len(d)]
    means = d[idx].mean(axis=1)
    return {"gain": float(d.sum() / l0.sum()), "p_helps": float((means < 0).mean()),
            "n_eval": len(d)}


def band_widening(df, feats, f, cfg, end) -> float:
    """P90 coefficient minus P10 coefficient of f (standardised): > 0 means a higher value
    of f widens the forecast band, which is what a volatility feature should do."""
    data = selection_rows(df, end).dropna(subset=feats)
    fit = _fit(data[feats].to_numpy(float), data["y"].to_numpy(float), [0.1, 0.9],
               cfg["selection"]["alpha_rel"])
    j = feats.index(f)
    return float(fit["models"][1].coef_[j] - fit["models"][0].coef_[j])


def fitted_sign(df, feats, f, h, cfg, end) -> float:
    """Median-quantile coefficient of f (standardised) fitted on the whole selection window."""
    data = selection_rows(df, end).dropna(subset=feats)
    fitted = _fit(data[feats].to_numpy(float), data["y"].to_numpy(float), [0.5],
                  cfg["selection"]["alpha_rel"])
    return float(fitted["models"][0].coef_[feats.index(f)])


def _sign_ok(expected: str, coef: float) -> bool:
    if expected == "0":
        return True
    return (coef > 0) if expected == "+" else (coef < 0)


def select_one(t: str, h: int, df: pd.DataFrame, cfg: dict, end: str,
               own_1m_ok: bool, stat_ok: dict) -> tuple[list[str], list[dict], list[str]]:
    """Forward selection for one target and horizon.

    Returns (selected, evidence rows, shortlist). The shortlist is what forward selection
    picked before the robustness gate; Step 6 can still try it, e.g. as model covariates.
    """
    sel = cfg["selection"]
    specs = candidate_specs(cfg, t)
    own = [f for f, s in specs.items() if s["group"] == "own" and (f != "own_chg_1m" or own_1m_ok)]
    drivers = [f for f, s in specs.items() if s["group"] == "driver"]
    log = {f: {"target": t, "horizon": h, "feature": f, "group": specs[f]["group"],
               "sign_expected": specs[f]["sign"]} for f in specs}
    if not own_1m_ok:
        log["own_chg_1m"]["decision"] = "not a candidate"
        log["own_chg_1m"]["reason"] = "lag-1 partial autocorrelation not significant"

    chosen: list[str] = []
    # Stage 1: own-price features, starting from an intercept-only model.
    for f in own:
        log[f]["gain_alone"] = gain(df, [], f, h, cfg, end)
    pool = list(own)
    while pool and len(chosen) < sel["max_own"]:
        g = {f: gain(df, chosen, f, h, cfg, end) for f in pool}
        best = min(g, key=lambda k: np.inf if np.isnan(g[k]) else g[k])
        if np.isnan(g[best]) or g[best] > sel["gain_threshold"]:
            break
        chosen.append(best)
        log[best]["gain_when_added"] = g[best]
        pool.remove(best)
    for f in own:
        log[f].setdefault("decision", "kept" if f in chosen else "dropped")
        if f not in chosen and "reason" not in log[f]:
            log[f]["reason"] = "does not lower the backtest loss by 1 % once better features are in"
    own_chosen = list(chosen)

    # Stage 2: drivers on top of the own-price features.
    for f in drivers:
        log[f]["gain_alone"] = gain(df, own_chosen, f, h, cfg, end)
        log[f]["stat_signal"] = stat_ok.get((t, h, f), False)
    pool = [f for f in drivers if log[f]["stat_signal"]]
    for f in drivers:
        if f not in pool:
            log[f]["decision"] = "dropped"
            log[f]["reason"] = "no statistical signal (Granger and lead-lag both weak)"
    n_drv = 0
    while pool and n_drv < sel["max_drivers"]:
        g = {f: gain(df, chosen, f, h, cfg, end) for f in pool}
        ranked = sorted([f for f in g if not np.isnan(g[f])], key=g.get)
        added = False
        for f in ranked:
            if g[f] > sel["gain_threshold"]:
                break
            coef = fitted_sign(df, chosen + [f], f, h, cfg, end)
            log[f]["coef_median_std"] = coef
            if not _sign_ok(specs[f]["sign"], coef):
                log[f]["decision"] = "dropped"
                log[f]["reason"] = "fitted effect has the wrong sign (or is zero)"
                pool.remove(f)
                continue
            chosen.append(f)
            log[f]["gain_when_added"] = g[f]
            log[f]["decision"] = "kept"
            pool.remove(f)
            n_drv += 1
            added = True
            break
        if not added:
            break
    for f in drivers:
        if "decision" not in log[f]:
            log[f]["decision"] = "dropped"
            log[f]["reason"] = "does not lower the backtest loss by 1 %"

    shortlist = list(chosen)
    # Robustness gate: every kept feature, tested last, must still help (gain <= threshold),
    # help in >= p_helps_min of bootstrap resamples, and a volatility feature must widen
    # the P10-P90 band. The weakest failing feature is dropped, then the check is redone.
    while chosen:
        checks = {}
        for f in chosen:
            others = [x for x in chosen if x != f]
            conf = gain_confidence(df, others, f, h, cfg, end)
            ok = (conf["gain"] <= sel["gain_threshold"]) and (conf["p_helps"] >= sel["p_helps_min"])
            why = f"tested last: loss change {conf['gain']:+.1%}, helps in {conf['p_helps']:.0%} of resamples"
            if ok and specs[f]["kind"] == "vol":
                widen = band_widening(df, chosen, f, cfg, end)
                ok = widen > 0
                why += f"; P90 minus P10 effect {widen:+.3f}"
            checks[f] = (ok, conf["p_helps"], why)
        failing = [f for f, c in checks.items() if not c[0]]
        if not failing:
            break
        worst = min(failing, key=lambda f: checks[f][1])
        chosen.remove(worst)
        log[worst]["decision"] = "shortlist"
        log[worst]["reason"] = "won forward selection but not robust: " + checks[worst][2]

    # Final model: coefficient of every kept feature.
    if chosen:
        for f in chosen:
            log[f]["coef_median_std"] = fitted_sign(df, chosen, f, h, cfg, end)
            log[f]["sign_ok"] = _sign_ok(specs[f]["sign"], log[f]["coef_median_std"])
    return chosen, list(log.values()), shortlist


def run_selection(data: pd.DataFrame, tables: dict, cfg: dict, end: str | None = None,
                  n_jobs: int = -1) -> dict:
    """All evidence tables and the selected features, for one selection window."""
    end = end or cfg["selection"]["select_end"]
    ap = acf_pacf_table(data, cfg)
    lagdec = own_lag_decision(ap)
    season = seasonality_table(data, cfg)
    corr = correlation_table(tables, cfg)
    gr = granger_table(data, tables, cfg)
    th = cfg["selection"]["holm_threshold"]
    stat_ok = {}
    for r in corr.itertuples():
        g = gr[(gr.target == r.target) & (gr.feature == r.feature)]
        granger_ok = (len(g) > 0) and (g["granger_p_holm"].iloc[0] < th)
        stat_ok[(r.target, r.horizon, r.feature)] = bool(granger_ok or abs(r.spearman) > r.band)
    jobs = [(t, h) for t in cfg["targets"] for h in cfg["settings"]["horizons"]]
    res = Parallel(n_jobs=n_jobs)(
        delayed(select_one)(t, h, tables[(t, h)], cfg, end,
                            bool(lagdec.loc[t, "own_chg_1m_candidate"]), stat_ok)
        for t, h in jobs)
    selected = {k: r[0] for k, r in zip(jobs, res)}
    shortlist = {k: r[2] for k, r in zip(jobs, res)}
    evidence = pd.DataFrame([row for r in res for row in r[1]])
    evidence = (evidence.merge(corr, on=["target", "horizon", "feature"], how="left")
                .merge(gr[["target", "feature", "granger_p", "granger_p_holm"]],
                       on=["target", "feature"], how="left"))
    # Overall skill of the selected set vs the intercept-only model (historical quantiles).
    skill = []
    for (t, h), feats in selected.items():
        df = tables[(t, h)]
        mask = df[feats].notna().all(axis=1) if feats else None
        l0 = backtest_loss(df, [], h, cfg, end, mask)
        l1 = backtest_loss(df, feats, h, cfg, end, mask) if feats else l0
        skill.append({"target": t, "horizon": h, "n_features": len(feats),
                      "features": ", ".join(feats), "loss_hist_quantiles": l0,
                      "loss_selected": l1, "gain_vs_hist_quantiles": l1 / l0 - 1})
    return {"acf_pacf": ap, "own_lag_decision": lagdec, "seasonality": season,
            "correlation": corr, "granger": gr, "evidence": evidence,
            "selected": selected, "shortlist": shortlist, "skill": pd.DataFrame(skill)}


def _feature_checks(t, h, feats, df, cfg, end, early_end):
    rows = []
    for f in feats:
        others = [x for x in feats if x != f]
        conf = gain_confidence(df, others, f, h, cfg, end)
        rows.append({"target": t, "horizon": h, "feature": f,
                     "gain_added_last": conf["gain"], "p_helps": conf["p_helps"],
                     "n_eval": conf["n_eval"],
                     "gain_added_last_early_window": gain(df, others, f, h, cfg, early_end)})
    return rows


def robustness(tables: dict, cfg: dict, selected: dict, n_jobs: int = -1) -> pd.DataFrame:
    """For each kept feature, added last to the final set:
    gain and bootstrap confidence on the selection window, and gain on an earlier window."""
    end, early = cfg["selection"]["select_end"], cfg["selection"]["early_select_end"]
    res = Parallel(n_jobs=n_jobs)(
        delayed(_feature_checks)(t, h, feats, tables[(t, h)], cfg, end, early)
        for (t, h), feats in selected.items() if feats)
    return pd.DataFrame([r for rows in res for r in rows])


def effects(tables: dict, cfg: dict, selected: dict) -> pd.DataFrame:
    """Business reading of each kept feature: effect of a typical move on the forecast.

    The median model is refitted on the whole selection window. A 'typical move' is one
    standard deviation of the feature. The effect is the change in the median forecast
    of the H-month price change, in %.
    """
    end = cfg["selection"]["select_end"]
    rows = []
    for (t, h), feats in selected.items():
        if not feats:
            continue
        data = selection_rows(tables[(t, h)], end).dropna(subset=feats)
        X, y = data[feats].to_numpy(float), data["y"].to_numpy(float)
        fit = _fit(X, y, cfg["selection"]["quantiles"], cfg["selection"]["alpha_rel"])
        for j, f in enumerate(feats):
            coefs = [m.coef_[j] for m in fit["models"]]
            rows.append({"target": t, "horizon": h, "feature": f,
                         "typical_move": float(fit["sd"][j]),
                         "effect_p10_pct": 100 * (np.exp(coefs[0]) - 1),
                         "effect_p50_pct": 100 * (np.exp(coefs[1]) - 1),
                         "effect_p90_pct": 100 * (np.exp(coefs[2]) - 1),
                         "latest_value": float(tables[(t, h)][f].iloc[-1]),
                         "n_train": len(data)})
    return pd.DataFrame(rows)


def main() -> None:
    from src.features import load_inputs

    cfg = load_config()
    inputs = load_inputs()
    tables = load_tables(cfg)
    out = run_selection(inputs.data, tables, cfg)
    out["robustness"] = robustness(tables, cfg, out["selected"])
    out["effects"] = effects(tables, cfg, out["selected"])
    SELECTION_DIR.mkdir(parents=True, exist_ok=True)
    for name, obj in out.items():
        if isinstance(obj, pd.DataFrame):
            obj.to_csv(SELECTION_DIR / f"{name}.csv")
    sel = pd.DataFrame([{"target": t, "horizon": h, "selected": ", ".join(f),
                         "shortlist_only": ", ".join(x for x in out["shortlist"][(t, h)] if x not in f)}
                        for (t, h), f in out["selected"].items()])
    sel.to_csv(SELECTION_DIR / "selected_features.csv", index=False)
    print(sel.to_string(index=False))


if __name__ == "__main__":
    main()
