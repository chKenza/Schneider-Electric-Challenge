"""Live quote engine for the Streamlit app.

Runs the Step 9 quote rule (src/pricing.py) for ANY input instead of the fixed grid
in quote_rule.csv: acceptable margin loss, selling price, confidence, maximum uplift,
and whether the customer accepts an indexation clause. Also evaluates a custom
price scenario (a single price path set by the user).

Inputs: Data/processed/simulated_driver_ratios.csv (Step 8) and the panel.
Steel is priced at market (MEPS-like) volatility, the Step 10 headline case.

Every function takes a Dataset (default LIVE: this repo, Sep 2026):
  - Dataset(origin="2025-06", replay=True): a past month, simulated from the Step 6
    forecasts made at that month (walk-forward, no later data), to compare with what
    happened (`realised`);
  - Dataset(origin="2026-10", root=<run folder>): a monthly-update run (app/update_page.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from src import cost_model as cm
from src import pricing as p
from src.data_prep import OUT
from src.simulation import (
    ALL_CASES,
    HORIZONS,
    material_ratios,
    simulate_driver_ratios,
    steel_market,
)

# product shown in the app -> simulation case (Step 10 main cases)
CASES = {"RM6": "RM6", "RM AirSeT": "AirSeT, nickel check"}
BASE_PRICE = {"RM6": p.selling_price("RM6"), "RM AirSeT": p.selling_price("AirSeT")}
GROUPS = ["Copper", "Carbon steel", "Stainless steel", "Epoxy", "Aluminium"]
DEFAULT_MAX_UPLIFT = p.MAX_BUFFER_PTS
DEFAULT_CONFIDENCE = 0.90


def group_of(material: str) -> str:
    """BOM line -> the material group shown to users (brass moves with copper)."""
    if material in ("Copper", "Brass"):
        return "Copper"
    if material.startswith("Stainless"):
        return "Stainless steel"
    if material.startswith(("Carbon steel", "Galvanised")):
        return "Carbon steel"
    return material


# representative public price series per group, for the price-history chart
def rep_series(product: str) -> dict:
    return {
        "Copper": "D01",
        "Carbon steel": "MEPS_FR_CR" if product == "RM6" else "MEPS_DE_CR",
        "Stainless steel": "CRU_SS304_DE_TOTAL",
        "Epoxy": "EPOXY_EUR",
        "Aluminium": "D02",
    }


# ------------------------------------------------------------------ data
@dataclass(frozen=True)
class Dataset:
    origin: str = p.ORIGIN       # quote month, YYYY-MM (last month of data used)
    root: str | None = None      # repo copy of a monthly-update run; None = this repo
    replay: bool = False         # past month: paths from that month's backtest forecasts
    n_paths: int = 10_000        # replay only

    @property
    def out(self) -> Path:
        return Path(self.root) / OUT if self.root else OUT

    @property
    def horizons(self) -> list[int]:
        return sorted({h for (_, h) in sims(self)})


LIVE = Dataset()
REPLAY_MODEL = "conformal_combo"   # the final Step 6 model, as in Step 8


@lru_cache
def panel(ds: Dataset = LIVE) -> pd.DataFrame:
    if ds.root:
        return cm.add_brass(pd.read_csv(ds.out / "panel_monthly.csv", index_col=0, parse_dates=True))
    return cm.load_panel()


@lru_cache
def backtest_forecasts() -> pd.DataFrame:
    """Step 6 forecasts at every past origin (each made with the data known then)."""
    return pd.read_csv(OUT / "models" / f"predictions_{REPLAY_MODEL}.csv",
                       parse_dates=["origin", "target_month"])


def replay_months() -> list[str]:
    """Past quote months with a forecast and a known outcome at 3 months or more."""
    from src.simulation import TARGETS
    f = backtest_forecasts()
    f = f[f["y"].notna() & (f["origin"] < pd.Timestamp(p.ORIGIN))]
    full = f.groupby(["origin", "horizon"])["target"].agg(lambda x: set(TARGETS) <= set(x))
    return sorted(full[full].reset_index()["origin"].dt.strftime("%Y-%m").unique())


@lru_cache
def driver_paths(ds: Dataset = LIVE) -> dict:
    """{h: driver ratios, one row per path} (PPI steel)."""
    if ds.replay:
        residuals = pd.read_csv(OUT / "models" / "step8" / "residuals_monthly.csv",
                                index_col="month", parse_dates=True)
        return simulate_driver_ratios(ds.origin, backtest_forecasts(), residuals, n_paths=ds.n_paths)
    paths = pd.read_csv(ds.out / "simulated_driver_ratios.csv", index_col=["horizon_m", "path"])
    return {h: paths.loc[h].reset_index(drop=True) for h in HORIZONS if h in paths.index.levels[0]}


@lru_cache
def sims(ds: Dataset = LIVE) -> dict:
    """{(product, h): (delta, base)}: € change per BOM line on each simulated path."""
    out = {}
    for h, ppi in driver_paths(ds).items():
        ratios = steel_market(ppi, panel(ds), h, ds.origin)
        for product, case in CASES.items():
            out[(product, h)] = p.eur_changes(case, panel(ds), ratios, ds.origin)
    return out


@lru_cache
def hedge_rate(h: int, ds: Dataset = LIVE) -> float:
    return float(p.hedge_cost_rate(panel(ds), h).loc[: ds.origin].iloc[-1])


def realised(product: str, h: int, ds: Dataset) -> pd.DataFrame | None:
    """What happened: € change per BOM line from the quote month to delivery (one row),
    with each material moved by its own price series. None if not yet known."""
    pan = panel(LIVE)
    t1 = pd.Timestamp(ds.origin) + pd.DateOffset(months=h)
    bd = cm.cost_breakdown(ALL_CASES[CASES[product]], pan, ds.origin).dropna(subset=["cost_eur"])
    cols = bd["driver"].unique()
    if t1 not in pan.index or pan.loc[t1, cols].isna().any():
        return None
    ratios = pd.DataFrame([{d: pan.loc[t1, d] / cm.last_value(pan[d], ds.origin) for d in cols}])
    cost0 = bd.set_index("material")["cost_eur"]
    r = material_ratios(bd, ratios)[cost0.index]
    return r * cost0 - cost0


def by_group(df: pd.DataFrame) -> pd.DataFrame:
    return df.T.groupby(group_of).sum().T.reindex(columns=GROUPS, fill_value=0.0)


# ------------------------------------------------------------- the rule
@dataclass
class Option:
    name: str
    uplift: float          # points charged on the price
    adjustment: float      # expected drift (median loss)
    buffer: float          # the rest of the uplift
    fits: bool             # uplift <= maximum uplift
    kind: str              # fixed | clause | validity | hedge
    band: float | None = None
    months: int | None = None


@dataclass
class Terms:
    product: str
    h: int
    price: float
    tolerance: float
    confidence: float
    max_uplift: float
    recommended: Option
    options: list
    loss_q: float           # loss at the confidence level, fixed price, points
    loss_median: float
    p_over_limit: float     # chance the loss exceeds the tolerance with no protection
    tol_for_fixed: float    # smallest acceptable loss at which a fixed price works
    longest_fixed: int | None
    drivers: pd.Series      # € per group in the bad case
    losses: pd.Series       # fixed-price loss per path, points

    def eur(self, pts: float) -> float:
        return pts * self.price / 100


def _option(name, loss, tol, conf, max_up, kind, **kw) -> Option:
    adj, buf = p.required_uplift(loss, tol, conf)
    return Option(name, adj + buf, adj, buf, adj + buf <= max_up + 1e-9, kind, **kw)


def quote_terms(product: str, h: int, price: float, tolerance: float,
                confidence: float = DEFAULT_CONFIDENCE,
                max_uplift: float = DEFAULT_MAX_UPLIFT,
                clause_ok: bool = True, ds: Dataset = LIVE) -> Terms:
    """Step 9 rule, live: fixed price -> indexation clause -> shorter validity."""
    S = sims(ds)
    delta, base = S[(product, h)]
    case = CASES[product]
    loss = p.points(delta, price)

    fixed = _option("Fixed price + uplift", loss, tolerance, confidence, max_uplift, "fixed")
    options = [fixed]

    clauses = []
    for t in p.TRIGGERS:
        lt = p.strategy_losses(delta, base, price, case, {}, t, hedge_rate(h, ds))
        clauses.append(_option(f"Indexation clause ±{t:.0%} + uplift", lt["indexation"],
                               tolerance, confidence, max_uplift, "clause", band=t))
    fitting = [c for c in clauses if c.fits]
    clause = max(fitting, key=lambda c: c.band) if fitting else clauses[0]
    options.append(clause)

    shorter = None
    for hs in sorted([x for x in HORIZONS if x < h and (product, x) in S], reverse=True):
        o = _option(f"Fixed price, valid {hs} months", p.points(S[(product, hs)][0], price),
                    tolerance, confidence, max_uplift, "validity", months=hs)
        if o.fits:
            shorter = o
            break
    if shorter:
        options.append(shorter)

    lh = p.strategy_losses(delta, base, price, case, {}, p.MAIN_TRIGGER, hedge_rate(h, ds))
    options.append(_option("Copper hedge (procurement) + uplift", lh["copper hedge"],
                           tolerance, confidence, max_uplift, "hedge"))

    if fixed.fits:
        rec = fixed
    elif clause_ok and clause.fits:
        rec = clause
    elif shorter:
        rec = shorter
    else:  # nothing fits under the maximum uplift: cheapest available option
        allowed = [o for o in options if o.kind != "hedge" and (clause_ok or o.kind != "clause")]
        rec = min(allowed, key=lambda o: o.uplift)
    if not clause_ok:
        options = [o for o in options if o.kind != "clause"]

    q = float(loss.quantile(confidence))
    longest = None
    for hs in [x for x in HORIZONS if (product, x) in S]:
        o = _option("", p.points(S[(product, hs)][0], price), tolerance, confidence,
                    max_uplift, "fixed")
        if o.fits:
            longest = hs

    # € per group on the paths around the confidence quantile (the "bad case")
    total = delta.sum(axis=1)
    near = total.between(total.quantile(confidence - 0.05), total.quantile(min(confidence + 0.05, 1)))
    drivers = by_group(delta[near]).mean()

    return Terms(product, h, price, tolerance, confidence, max_uplift, rec, options,
                 loss_q=q, loss_median=float(loss.median()),
                 p_over_limit=float((loss > tolerance).mean()),
                 tol_for_fixed=max(0.0, q - max_uplift),
                 longest_fixed=longest, drivers=drivers, losses=loss)


def what_would_change(t: Terms) -> str:
    """One line: the nearest input change that switches the recommendation."""
    if t.recommended.kind == "fixed":
        if t.tol_for_fixed <= 0:
            return "A fixed price works here at any acceptable loss."
        return (f"Below {t.tol_for_fixed:.2f} pts of acceptable loss, a fixed price "
                f"no longer works and a clause or shorter validity is needed.")
    parts = [f"accept {t.tol_for_fixed:.2f} pts of margin loss"]
    if t.longest_fixed:
        parts.append(f"limit validity to {t.longest_fixed} months")
    return "A fixed price would work if you " + " or ".join(parts) + "."


# ----------------------------------------------------- forecast summaries
def cost_outlook(product: str, confidence: float = DEFAULT_CONFIDENCE,
                 ds: Dataset = LIVE) -> pd.DataFrame:
    """Unit raw-material cost today and P10 / P50 / bad case at 3 / 6 / 9 months."""
    rows = []
    for h in ds.horizons:
        delta, base = sims(ds)[(product, h)]
        cost = base.iloc[0].sum() + delta.sum(axis=1)
        rows.append({"h": h, "today": base.iloc[0].sum(), "p10": cost.quantile(0.10),
                     "p50": cost.median(), "bad": cost.quantile(confidence)})
    return pd.DataFrame(rows)


def drivers_by_horizon(product: str, confidence: float = DEFAULT_CONFIDENCE) -> pd.DataFrame:
    """€ per group in the bad case, per validity."""
    rows = {}
    for h in HORIZONS:
        delta, _ = sims()[(product, h)]
        total = delta.sum(axis=1)
        near = total.between(total.quantile(confidence - 0.05), total.quantile(min(confidence + 0.05, 1)))
        rows[h] = by_group(delta[near]).mean()
    return pd.DataFrame(rows).T


def price_fan(product: str, group: str) -> tuple[pd.Series, pd.DataFrame]:
    """History (last 24 months) of the group's public price and its forecast range."""
    series = rep_series(product)[group]
    hist = panel()[series].loc[: p.ORIGIN].dropna().iloc[-24:]
    last = hist.iloc[-1]
    rows = []
    for h in HORIZONS:
        delta, base = sims()[(product, h)]
        g = by_group(delta)[group] / by_group(base)[group] + 1
        month = pd.Timestamp(p.ORIGIN) + pd.DateOffset(months=h)
        rows.append({"month": month, "p10": last * g.quantile(0.10), "p50": last * g.median(),
                     "p90": last * g.quantile(0.90)})
    return hist, pd.DataFrame(rows)


def group_change_range(product: str, h: int, group: str) -> tuple[float, float, float]:
    """P10 / P50 / P90 % change of a group's cost by the horizon."""
    delta, base = sims()[(product, h)]
    g = by_group(delta)[group] / by_group(base)[group] * 100
    return g.quantile(0.10), g.median(), g.quantile(0.90)


# --------------------------------------------------------- custom scenario
def scenario_result(t: Terms, pct: dict) -> dict:
    """Margin result (points; negative = margin lost) of each option on the user's path."""
    delta_sim, base = sims()[(t.product, t.h)]
    base0 = base.iloc[0]
    d = pd.Series({m: base0[m] * pct.get(group_of(m), 0) / 100 for m in base0.index})
    pts = 100 / t.price
    total = d.sum()
    case = CASES[t.product]

    def clause_loss(band):
        cov = [m for m in p.INDEXED[p.product(case)] if m in d.index]
        cap = band * base0[cov].sum()
        covered = d[cov].sum()
        return (total - covered + float(np.clip(covered, -cap, cap))) * pts

    def loss_of(o: Option) -> float:
        if o.kind == "clause":
            return clause_loss(o.band)
        if o.kind == "hedge":
            return (total - d.get("Copper", 0) + hedge_rate(t.h) * base0.get("Copper", 0)) * pts
        return total * pts

    rows = [{"option": "No protection (fixed price, no uplift)", "uplift": 0.0,
             "result": -total * pts}]
    for o in t.options:
        rows.append({"option": o.name + (" (recommended)" if o is t.recommended else ""),
                     "uplift": o.uplift, "result": o.uplift - loss_of(o)})
    sim_total = delta_sim.sum(axis=1)
    return {
        "eur_change": total,
        "by_group": d.groupby(group_of).sum().reindex(GROUPS, fill_value=0.0),
        "cost_today": base0.sum(),
        "table": pd.DataFrame(rows),
        "share_worse": float((sim_total >= total).mean()),
    }


def scenario_gap_change(h: int, pct: dict) -> float:
    """Change of the AirSeT minus RM6 raw-material cost gap (€) on the user's path."""
    out = []
    for product in ("RM AirSeT", "RM6"):
        base0 = sims()[(product, h)][1].iloc[0]
        out.append(sum(base0[m] * pct.get(group_of(m), 0) / 100 for m in base0.index))
    return out[0] - out[1]


# ------------------------------------------------------- replay a past month
def realised_result(t: Terms, ds: Dataset) -> dict | None:
    """Margin result (points; negative = lost) of the recommended terms on what happened.
    None if the outcome at the quote's validity is not known yet."""
    d = realised(t.product, t.h, ds)
    if d is None:
        return None
    o, case, pts = t.recommended, CASES[t.product], 100 / t.price
    base = pd.DataFrame([sims(ds)[(t.product, t.h)][1].iloc[0]])
    total = float(d.sum(axis=1).iloc[0])
    if o.kind == "clause":
        loss = float(p.strategy_losses(d, base, t.price, case, {}, o.band,
                                       hedge_rate(t.h, ds))["indexation"].iloc[0])
    elif o.kind == "hedge":
        loss = float(p.strategy_losses(d, base, t.price, case, {}, p.MAIN_TRIGGER,
                                       hedge_rate(t.h, ds))["copper hedge"].iloc[0])
    elif o.kind == "validity":   # re-quoted after o.months: only that change is lost
        loss = float(realised(t.product, o.months, ds).sum(axis=1).iloc[0]) * pts
    else:
        loss = total * pts
    return {"eur_change": total, "loss_fixed": total * pts, "loss": loss,
            "result": o.uplift - loss, "within": o.uplift - loss >= -t.tolerance - 1e-9,
            "by_group": by_group(d).iloc[0],
            "percentile": float((t.losses < total * pts).mean())}


def cost_path(product: str, ds: Dataset, months_before: int = 12, h: int = 9) -> pd.Series:
    """Unit raw-material cost (€, fixed BOM, prices of each month) around the quote month."""
    pan = panel(LIVE)
    bd = cm.cost_breakdown(ALL_CASES[CASES[product]], pan, ds.origin).dropna(subset=["cost_eur"])
    t0 = pd.Timestamp(ds.origin)
    idx = pd.date_range(t0 - pd.DateOffset(months=months_before), t0 + pd.DateOffset(months=h),
                        freq="MS").intersection(pan.index)
    cost = pd.Series(0.0, index=idx)
    for r in bd.itertuples():
        s = pan[r.driver].ffill().reindex(idx)
        cost += r.cost_eur * s / cm.last_value(pan[r.driver], ds.origin)
    return cost
