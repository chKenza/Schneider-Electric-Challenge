"""
Step 8 - this is the joint simulation of material prices -> BOM index as well as margin 
at risk is calculated here

from repo root run after `uv run python -m src.models --stage export`:
    uv run python -m src.simulation
"""

import numpy as np
import pandas as pd

from src.config import REPO_ROOT
from src.cost_model import CASES, bom_index, cost_breakdown, load_panel, split_stainless
from src.data_prep import OUT

STEP8 = OUT / "models" / "step8" #where bootstrapped data is in
DRIVERS = ['D01', 'D02', 'S09', 'S10', 'S03_EUR', 'EPOXY_EUR']   
# assuming EUR/USD stays flat during the period
STEP6_TARGET = {'S03_EUR': 'S03'}  # Step 6 forecasts nickel in USD
TARGETS = [STEP6_TARGET.get(d, d) for d in DRIVERS]
BLOCK = 3
N_PATHS = 10_000
SEED=42
HORIZONS = [3, 6, 9]
LEVELS = [0.10, 0.50, 0.90, 0.95]
QCOLS = ["p10", "p50", "p90", "p95"]

# RM6: Schneider P50 2025 in the price benchmark; AirSeT: assumed RM6 + 20 %
SELLING_PRICE = {"RM6": 8740, "AirSeT": 8740 * 1.2}

def with_mass(bom, material, kg, source):
    """Same BOM with one material's kg replaced."""
    return [(m, kg, source) if m == material else (m, k, src) for m, k, src in bom]

ALL_CASES = CASES | {
    "AirSeT epoxy low, nickel check": split_stainless(CASES["AirSeT epoxy low"]),
    "AirSeT epoxy high, nickel check": split_stainless(CASES["AirSeT epoxy high"]),
    "RM6 copper 13.8 kg": with_mass(CASES["RM6"], "Copper", 13.8, "teardown (high)"),
    "RM6 copper 8.6 kg": with_mass(CASES["RM6"], "Copper", 8.6, "teardown (low)"),
}

MARKET_STEEL = {"S09": "MEPS_DE_CR", "S10": "MEPS_DE_HDG"}
TABLE_DIR = REPO_ROOT / "report" / "problem1" / "step8_tables"

def selling_price(case: str) -> float:
    """Selling price (€) of the product a case belongs to."""
    return SELLING_PRICE["RM6" if case.startswith("RM6") else "AirSeT"]

def read_historical_prices() -> tuple[pd.DataFrame, pd.DataFrame]:                                     
    """
    Reading standardised monthly residuals (data we bootstrap)
    Reading forecasts (data we scale to)
    """
    residuals = pd.read_csv(STEP8 / "residuals_monthly.csv", index_col="month", parse_dates=True)
    marginals = pd.read_csv(STEP8 / "marginals_202609.csv")
    return residuals[TARGETS].dropna(), marginals

def bootstrap_prices(horizon: int, returns: pd.DataFrame,        
                     n_paths: int = 10_000, block_size: int = 3,
                     seed: int = 42) -> np.ndarray:
    
    rng = np.random.default_rng(seed)
    n_blocks = -(-horizon // block_size)
    paths = []

    for i in range(n_paths):
        chunks = []
        for _ in range(n_blocks):
            start = rng.integers(0, len(returns) - block_size + 1)   #select random starting month
            chunks.append(returns.iloc[start:start + block_size])    #complete the chunk from start to size of block
        final_chunk = pd.concat(chunks).iloc[:horizon]               # trim to exactly H months
        paths.append(final_chunk.to_numpy())                         #store the last path

    return np.stack(paths)    # shape (n_paths, horizon, n_drivers)

def ratios_at(paths: np.ndarray, month: int, sigma: np.ndarray) -> pd.DataFrame: 
    """Ratio by which each driver grew/fell from the start to end"""
    log_change = (paths[:, :month, :] * sigma).sum(axis=1)       # residual × today's volatility = return
    return pd.DataFrame(np.exp(log_change), columns=DRIVERS)      # names, so material_ratios finds 'D01'

def scale_to_forecast(driver_ratios: pd.DataFrame, marginals: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Stretch each driver so its P10/P50/P90/p95 equal probabilistic foreacsts made, keeping each path's rank."""
    out = driver_ratios.copy()
    for d, t in zip(DRIVERS, TARGETS):
        k = marginals[(marginals["target"] == t) & (marginals["horizon"] == horizon)].iloc[0]
        want = np.maximum.accumulate(k[QCOLS].to_numpy(float))   # Step 6 log changes, kept in order
        x = np.log(out[d].to_numpy())
        have = np.quantile(x, LEVELS)                            # the simulation's own percentiles
        y = np.interp(x, have, want)                             # map between the 4 points
        lo, hi = x < have[0], x > have[-1]                       # tails: extend the end segments
        y[lo] = want[0] + (x[lo] - have[0]) * (want[1] - want[0]) / (have[1] - have[0])
        y[hi] = want[-1] + (x[hi] - have[-1]) * (want[-1] - want[-2]) / (have[-1] - have[-2])
        out[d] = np.exp(y)
    return out

def steel_market(driver_ratios, panel, h, origin="2026-09"):
    """Steel scenario: keep the S09/S10 forecast median, but widen the spread
    to the volatility of MEPS market prices over h months (≈1.7× the PPI)."""
    out = driver_ratios.copy()
    cols = list(MARKET_STEEL) + list(MARKET_STEEL.values())
    hist = np.log(panel.loc[:origin, cols])
    for ppi, market in MARKET_STEEL.items():
        k = hist[market].diff(h).std() / hist[ppi].diff(h).std()
        x = np.log(out[ppi])
        m = x.median()
        out[ppi] = np.exp(m + k * (x - m))
    return out

def material_ratios(bd: pd.DataFrame, driver_ratios: pd.DataFrame) -> pd.DataFrame:
    """Map driver columns onto material names (several share a driver)."""
    priced = bd.dropna(subset=["cost_eur"])
    return pd.DataFrame(
        {row.material: driver_ratios[row.driver] for row in priced.itertuples()}
    )

def simulate_cost(bom:list, panel:pd.DataFrame, driver_ratios:pd.DataFrame, origin="2026-09", price: float | None = None):
    """
    simulate the costs of every material 
    """

    bd = cost_breakdown(bom=bom, panel=panel, origin=origin)
    ratios = material_ratios(bd=bd, driver_ratios=driver_ratios)
    index = bom_index(breakdown=bd, ratios=ratios)

    cost0 = bd.dropna(subset=["cost_eur"]).set_index("material")["cost_eur"]
    p10, p50, p90, p95 = np.percentile(index, [10, 50, 90, 95])

    eur_change = ratios[cost0.index] * cost0 - cost0
    near_p90 = index.between(*np.percentile(index, [85, 95]))
    contribution = eur_change[near_p90].mean()

    rm0 = cost0.sum()
    c50, c90, c95 = rm0 * p50 / 100, rm0 * p90 / 100, rm0 * p95 / 100

    summary = {
        "cost_today_eur": rm0,
        "index_p10": p10,
        "index_p50": p50,
        "index_p90": p90,
        "index_p95": p95,
        "cost_p50_eur": c50,
        "cost_p90_eur": c90,
        "cost_p95_eur": c95,
    }
    if price is not None:                         
        summary |= {
            "selling_price_eur": price,
            "price_adjustment_pts": 100 * (c50 - rm0) / price,   # expected drift
            "risk_buffer_p90_pts": 100 * (c90 - c50) / price,    # bad luck at P90
            "risk_buffer_p95_pts": 100 * (c95 - c50) / price,    # bad luck at P95
            "total_at_risk_p90_pts": 100 * (c90 - rm0) / price,  # adjustment + buffer
            "total_at_risk_p95_pts": 100 * (c95 - rm0) / price,
        }
    return summary, contribution

def simulate_driver_ratios(origin, marginals: pd.DataFrame, residuals: pd.DataFrame,
                           sigma: np.ndarray | None = None,
                           n_paths: int = N_PATHS, block_size=BLOCK, seed: int = SEED) -> dict[int, pd.DataFrame]:
    """{horizon: driver ratios (one row per path)} at any forecast origin.

    marginals: Step 6 forecasts (target, horizon, p10, p50, p90, p95). If it has an
    'origin' column, only that origin's rows are used.
    Only residuals up to the origin are bootstrapped (no future data).
    Only the horizons where every driver has a forecast are returned.
    """
    origin = pd.Timestamp(origin)
    if "origin" in marginals.columns:
        marginals = marginals[pd.to_datetime(marginals["origin"]) == origin]
    hs = [h for h in HORIZONS if set(TARGETS) <= set(marginals.loc[marginals["horizon"] == h, "target"])]
    if not hs:
        raise ValueError(f"no forecast at {origin:%Y-%m} for every driver {TARGETS}")

    known = residuals.loc[:origin, TARGETS].dropna()
    if sigma is None:
        sigma = np.ones(len(TARGETS))   # no effect at 3/6/9 months: the scaling sets the level
    paths = bootstrap_prices(horizon=max(HORIZONS), returns=known, n_paths=n_paths, block_size=block_size, seed=seed)
    return {h: scale_to_forecast(ratios_at(paths, h, sigma), marginals, h) for h in hs}


def simulate_bom(origin, marginals: pd.DataFrame, residuals: pd.DataFrame,
                 panel: pd.DataFrame | None = None,
                 n_paths: int = N_PATHS, seed: int = SEED) -> pd.DataFrame:
    """P10/P50/P90/P95 of the BOM index per case and horizon, at any origin.

    `marginals` can be the Step 6 predictions file
    (Data/processed/models/predictions_conformal_combo.csv); Step 7 backtests this at past origins.
    """
    panel = load_panel() if panel is None else panel
    ratios = simulate_driver_ratios(origin, marginals, residuals, n_paths=n_paths, seed=seed)
    rows = []
    for h, driver_ratios in ratios.items():
        for case, bom in ALL_CASES.items():
            summary, _ = simulate_cost(bom, panel, driver_ratios, origin=pd.Timestamp(origin))
            rows.append({"origin": pd.Timestamp(origin), "case": case, "horizon_m": h,
                         **{q: summary[f"index_{q}"] for q in QCOLS}})
    return pd.DataFrame(rows)

def block_sensitivity(residuals, marginals, panel, sigma, blocks=(1, 3, 6, 9), h=9,
                      origin="2026-09", n_paths=N_PATHS, seed=SEED):
    """Longer blocks keep more of how materials move together over h months."""
    known = residuals.loc[:origin, TARGETS].dropna()
    hist = known.rolling(h).sum().dropna().set_axis(DRIVERS, axis=1)
    rows = [{"block": "history", "corr_D01_S09": hist.D01.corr(hist.S09, method="spearman"),
             "corr_D01_D02": hist.D01.corr(hist.D02, method="spearman")}]
    for b in blocks:
        paths = bootstrap_prices(horizon=h, returns=known, n_paths=n_paths, block_size=b, seed=seed)
        raw = pd.DataFrame(paths.sum(axis=1), columns=DRIVERS)
        ratios = scale_to_forecast(ratios_at(paths, h, sigma), marginals, h)
        row = {"block": b, "corr_D01_S09": raw.D01.corr(raw.S09, method="spearman"),
               "corr_D01_D02": raw.D01.corr(raw.D02, method="spearman")}
        for case in ["RM6", "AirSeT epoxy low, nickel check"]:
            summary, _ = simulate_cost(ALL_CASES[case], panel, ratios, price=selling_price(case))
            row[f"{case} P90 pts"] = summary["total_at_risk_p90_pts"]
        rows.append(row)
    return pd.DataFrame(rows)

def main():
    panel = load_panel()
    residuals, marginals = read_historical_prices()              
    sigma = (marginals.drop_duplicates("target").set_index("target")
             .loc[TARGETS, "sigma_T"].to_numpy())                

    print(f"history: {residuals.index[0]:%Y-%m} → {residuals.index[-1]:%Y-%m}, "
          f"{len(residuals)} months, drivers {DRIVERS}")

    summaries, contributions = [], []
    all_ratios = simulate_driver_ratios("2026-09", marginals, residuals, sigma=sigma)
    pd.concat(all_ratios, names=["horizon_m", "path"]).to_csv(OUT / "simulated_driver_ratios.csv")

    for h, ppi_ratios in all_ratios.items(): 

        steel_scenarios = {"PPI": ppi_ratios, "market": steel_market(ppi_ratios, panel, h)}
        for steel, driver_ratios in steel_scenarios.items():

            for case, bom in ALL_CASES.items():

                summary, contrib = simulate_cost(bom=bom, panel=panel, driver_ratios=driver_ratios, price=selling_price(case)) 
                summaries.append({"case": case, "steel":steel, "horizon_m": h, **summary})
                contributions.append(
                    contrib.rename("eur_at_p90").reset_index()
                    .rename(columns={"index": "material"})
                    .assign(case=case, steel=steel, horizon_m=h)
                )

    summary_df = pd.DataFrame(summaries)
    contrib_df = pd.concat(contributions)[["case", "steel", "horizon_m", "material", "eur_at_p90"]]

    summary_df.to_csv(OUT / "bom_index_simulated.csv", index=False, float_format="%.2f")
    contrib_df.to_csv(OUT / "eur_per_material_p90.csv", index=False, float_format="%.2f")
    blocks = block_sensitivity(residuals, marginals, panel, sigma)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(TABLE_DIR / "bom_index_and_margin_points.csv", index=False, float_format="%.2f")
    contrib_df.to_csv(TABLE_DIR / "eur_per_material_p90.csv", index=False, float_format="%.2f")
    blocks.to_csv(TABLE_DIR / "block_sensitivity.csv", index=False, float_format="%.3f")
    print(summary_df.round(1).to_string(index=False))
    print(f"wrote 2 files to {OUT}/ and 3 tables to {TABLE_DIR}/")

if __name__ == "__main__":
    main()
