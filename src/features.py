"""Step 4 – forecast features, built only from data known at the forecast origin.

Run from the repo root, after src.data_prep and src.external_data:

    uv run python -m src.features

Writes, for every target and horizon, Data/processed/features/<target>_h<H>.csv:
one row per origin month, one column per candidate feature, plus the target y.

Timing rule (same as the submission CSV):
    origin o      = last month of the target that we know (Sep 2026 in the submission)
    quote month   = o + 2: the slowest targets (IMF, Eurostat, BLS) publish month o then
    a series with publication lag L is known up to month o + 2 - L, and never after o
    target        y = log(P[o+H]) - log(P[o])   (one model per horizon H)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.data_prep import OUT, available_at
from src.external_data import SOURCES as EXT_SOURCES
from src.external_data import load_external

CONFIG_FILE = Path(__file__).resolve().parents[1] / "configs" / "features.yaml"
FEATURE_DIR = OUT / "features"


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class Inputs:
    data: pd.DataFrame  # panel + external monthly series, one column per series
    lags: pd.Series  # publication lag in months per column
    sources: pd.Series  # source name per column
    steo: pd.DataFrame  # release_month, series, target_month, value


def load_inputs() -> Inputs:
    panel = pd.read_csv(OUT / "panel_monthly.csv", index_col=0, parse_dates=True)
    dictionary = pd.read_csv(OUT / "data_dictionary.csv", index_col=0)
    ext, steo, ext_sources = load_external()
    ext = ext.reindex(panel.index)  # nothing after the panel's last month
    data = pd.concat([panel, ext], axis=1)
    ext_meta = ext_sources.set_index("series_id")
    lags = pd.concat([dictionary["lag_months"], ext_meta["lag"].drop("STEO")]).astype(int)
    sources = pd.concat([dictionary["source"], ext_meta["source"].drop("STEO")])
    # STEO releases after the last panel month are never used.
    steo = steo[steo["release_month"] <= panel.index.max()]
    return Inputs(data, lags.reindex(data.columns), sources.reindex(data.columns), steo)


def info_set(inputs: Inputs, origin, quote_gap: int) -> pd.DataFrame:
    """Everything known at origin o: published by the start of month o + quote_gap, up to o."""
    origin = pd.Timestamp(origin)
    quote = origin + pd.DateOffset(months=quote_gap)
    lag_table = pd.DataFrame({"lag_months": inputs.lags})
    return available_at(inputs.data, lag_table, quote).loc[:origin]


def steo_release(steo: pd.DataFrame, origin) -> pd.DataFrame:
    """The STEO published in the origin month (never a later one)."""
    return steo[steo["release_month"] == pd.Timestamp(origin)]


# --------------------------------------------------------------------------- feature kinds
def _last(s: pd.Series, origin, max_stale: int) -> pd.Timestamp | None:
    """Last month with a value, or None if it is older than max_stale months."""
    last = s.last_valid_index()
    if last is None or last < pd.Timestamp(origin) - pd.DateOffset(months=max_stale):
        return None
    return last


def _change(s: pd.Series, last: pd.Timestamp, months: int) -> float:
    prev = last - pd.DateOffset(months=months)
    if prev not in s.index or pd.isna(s[prev]) or s[prev] <= 0 or s[last] <= 0:
        return np.nan
    return float(np.log(s[last] / s[prev]))


def _window(s: pd.Series, last: pd.Timestamp, months: int) -> pd.Series:
    w = s.loc[last - pd.DateOffset(months=months - 1): last]
    return w if w.notna().sum() == months else pd.Series(dtype=float)


def compute_feature(spec: dict, series: pd.Series | None, known: pd.DataFrame,
                    steo: pd.DataFrame, origin, h: int, max_stale: int) -> tuple[float, str]:
    """Value of one feature and the last data month it used ('' if none)."""
    kind = spec["kind"]
    if kind == "steo_change":
        rel = steo_release(steo, origin)
        f = rel[rel["series"] == spec["steo"]].set_index("target_month")["value"]
        o, t = pd.Timestamp(origin), pd.Timestamp(origin) + pd.DateOffset(months=h)
        if o not in f.index or t not in f.index:
            return np.nan, ""
        return float(np.log(f[t] / f[o])), f"STEO release {o:%Y-%m}"

    last = _last(series, origin, max_stale)
    if last is None:
        return np.nan, ""
    used = f"{last:%Y-%m}"
    if kind == "change":
        return _change(series, last, spec["months"]), used
    if kind == "level":
        return float(series[last]), used
    if kind == "vs_avg":
        w = _window(series, last, spec["months"])
        return (float(np.log(series[last] / w.mean())) if len(w) else np.nan), used
    if kind == "range_pos":
        w = _window(series, last, spec["months"])
        if not len(w) or w.max() == w.min():
            return np.nan, used
        return float((series[last] - w.min()) / (w.max() - w.min())), used
    if kind == "vol":
        w = _window(np.log(series).diff(), last, spec["months"])
        return (float(w.std()) if len(w) else np.nan), used
    if kind == "spread_pct":
        base = known[spec["base"]]
        if last not in base.index or pd.isna(base[last]):
            return np.nan, used
        return float(series[last] / base[last]), used
    if kind == "gap":
        other = known[spec["other"]]
        last_o = _last(other, origin, max_stale)
        if last_o is None:
            return np.nan, used
        val = _change(other, last_o, spec["months"]) - _change(series, last, spec["months"])
        return val, f"{used} / {last_o:%Y-%m}"
    raise ValueError(f"Unknown feature kind: {kind}")


def candidate_specs(cfg: dict, target: str) -> dict[str, dict]:
    """All candidate features of a target: own-price features + its listed drivers."""
    specs = {name: {**s, "series": target, "group": "own"} for name, s in cfg["own_features"].items()}
    for d in cfg["targets"][target]["drivers"]:
        specs[d] = {**cfg["drivers"][d], "group": "driver"}
    return specs


def features_at(inputs: Inputs, cfg: dict, origin, target: str, h: int,
                known: pd.DataFrame | None = None) -> tuple[pd.Series, pd.Series]:
    """(feature values, last month used per feature) for one target, horizon and origin."""
    st = cfg["settings"]
    if known is None:
        known = info_set(inputs, origin, st["quote_gap_months"])
    vals, used = {}, {}
    for name, spec in candidate_specs(cfg, target).items():
        series = known[spec["series"]] if "series" in spec else None
        vals[name], used[name] = compute_feature(
            spec, series, known, inputs.steo, origin, h, st["max_staleness_months"])
    return pd.Series(vals, name=pd.Timestamp(origin)), pd.Series(used, name=pd.Timestamp(origin))


def target_change(data: pd.DataFrame, target: str, origin, h: int) -> float:
    """y = log(P[o+H]) - log(P[o]); NaN if o+H is after the last month of data."""
    s = data[target]
    o, t = pd.Timestamp(origin), pd.Timestamp(origin) + pd.DateOffset(months=h)
    if t not in s.index or pd.isna(s.get(t)) or pd.isna(s.get(o)):
        return np.nan
    return float(np.log(s[t] / s[o]))


def build_tables(inputs: Inputs, cfg: dict, targets: list[str] | None = None) -> dict:
    """{(target, H): table}. Each row is an origin: candidate features, y and target month.

    Origins start 12 months after the target's first value (12-month features need it)
    and run to the last month of data (rows without y are the live forecast rows).
    """
    st = cfg["settings"]
    targets = targets or list(cfg["targets"])
    first = {t: inputs.data[t].first_valid_index() + pd.DateOffset(months=12) for t in targets}
    origins = inputs.data.index[inputs.data.index >= min(first.values())]
    rows = {(t, h): [] for t in targets for h in st["horizons"]}
    for o in origins:
        known = info_set(inputs, o, st["quote_gap_months"])
        for t in targets:
            if o < first[t] or pd.isna(known[t].get(o)):
                continue
            for h in st["horizons"]:
                vals, _ = features_at(inputs, cfg, o, t, h, known)
                vals["y"] = target_change(inputs.data, t, o, h)
                vals["target_month"] = o + pd.DateOffset(months=h)
                rows[(t, h)].append(vals)
    out = {}
    for key, r in rows.items():
        df = pd.DataFrame(r)
        df.index.name = "origin"
        out[key] = df
    return out


# --------------------------------------------------------------------------- leakage proof
def known_at_forecast_time(inputs: Inputs, cfg: dict, origins: list[str]) -> pd.DataFrame:
    """One row per (target, feature, origin): data used, its lag, last month used, rule check."""
    st = cfg["settings"]
    rows = []
    for o in origins:
        o = pd.Timestamp(o)
        quote = o + pd.DateOffset(months=st["quote_gap_months"])
        known = info_set(inputs, o, st["quote_gap_months"])
        for t in cfg["targets"]:
            _, used = features_at(inputs, cfg, o, t, cfg["settings"]["horizons"][0], known)
            for name, spec in candidate_specs(cfg, t).items():
                series = spec.get("series", f"STEO {spec.get('steo', '')}")
                if spec["kind"] == "steo_change":
                    lag, source = 0, EXT_SOURCES["STEO"]["source"]
                    allowed = o
                else:
                    lag, source = int(inputs.lags[series]), inputs.sources[series]
                    allowed = min(o, quote - pd.DateOffset(months=lag))
                last_used = used[name]
                months_used = [pd.Timestamp(p.strip()) for p in last_used.replace("STEO release", "")
                               .split("/") if p.strip()]
                ok = all(m <= allowed for m in months_used)
                rows.append({"origin": f"{o:%Y-%m}", "quote_month": f"{quote:%Y-%m}",
                             "target": t, "feature": name, "series": series, "source": source,
                             "lag_months": lag, "latest_allowed": f"{allowed:%Y-%m}",
                             "last_month_used": last_used or "(missing)", "rule_ok": ok})
    return pd.DataFrame(rows)


def poisoned_future_test(inputs: Inputs, cfg: dict, n: int = 12, seed: int = 0) -> pd.DataFrame:
    """Replace every value NOT known at the origin with random garbage; features must not change.

    This proves that features at origin o only read data published by then, whatever
    the code path (masks, windows, gaps, STEO releases).
    """
    rng = np.random.default_rng(seed)
    st = cfg["settings"]
    idx = inputs.data.index
    origins = rng.choice(idx[(idx >= "2018-06-01") & (idx <= idx.max())], size=n, replace=False)
    rows = []
    for o in sorted(pd.to_datetime(origins)):
        known = info_set(inputs, o, st["quote_gap_months"])
        poisoned = inputs.data.copy()
        hidden = known.reindex(poisoned.index).isna() & poisoned.notna()
        poisoned = poisoned.mask(hidden, pd.DataFrame(rng.uniform(1, 1e6, poisoned.shape),
                                                      index=poisoned.index, columns=poisoned.columns))
        steo = inputs.steo.copy()
        later = steo["release_month"] > o
        steo.loc[later, "value"] = rng.uniform(1, 1e6, later.sum())
        bad = Inputs(poisoned, inputs.lags, inputs.sources, steo)
        for t in cfg["targets"]:
            for h in st["horizons"]:
                a, _ = features_at(inputs, cfg, o, t, h)
                b, _ = features_at(bad, cfg, o, t, h)
                same = np.allclose(a.values.astype(float), b.values.astype(float), equal_nan=True)
                rows.append({"origin": f"{o:%Y-%m}", "target": t, "horizon": h,
                             "n_hidden_values_poisoned": int(hidden.values.sum()),
                             "features_unchanged": bool(same)})
    return pd.DataFrame(rows)


def main() -> None:
    cfg = load_config()
    inputs = load_inputs()
    tables = build_tables(inputs, cfg)
    FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    for (t, h), df in tables.items():
        df.to_csv(FEATURE_DIR / f"{t}_h{h}.csv")
    test = poisoned_future_test(inputs, cfg)
    if not test["features_unchanged"].all():
        raise AssertionError("Leakage: a feature changed when future data was altered")
    n_rows = sum(len(df) for df in tables.values())
    print(f"{len(tables)} feature tables ({n_rows} rows) written to {FEATURE_DIR}; "
          f"poisoned-future test passed on {len(test)} cases")


if __name__ == "__main__":
    main()
