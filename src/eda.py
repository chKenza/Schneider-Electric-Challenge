"""Statistics for Step 3 – Exploratory Data Analysis (no plotting here, see ``src.plotting``)."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller, kpss

from src.data_loading import SHORT


# --------------------------------------------------------------------------- basics
def log_returns(panel: pd.DataFrame, cols: list[str] | None = None) -> pd.DataFrame:
    """Monthly log-returns ln(P_t / P_{t-1}); NaN where either month is missing."""
    p = panel[cols] if cols else panel
    return np.log(p).diff()


def h_month_changes(panel: pd.DataFrame, col: str, h: int) -> pd.Series:
    """Simple % change over H months, indexed by the ORIGIN month t: P_{t+H}/P_t − 1."""
    s = panel[col].dropna()
    return (s.shift(-h) / s - 1).dropna()


# --------------------------------------------------------------------------- 3.1 univariate
def return_summary(rets: pd.DataFrame) -> pd.DataFrame:
    """Mean, volatility, skewness, excess kurtosis and Jarque–Bera normality test of monthly log-returns."""
    rows = {}
    for c in rets.columns:
        r = rets[c].dropna()
        jb = stats.jarque_bera(r)
        rows[SHORT.get(c, c)] = {
            "n": len(r),
            "mean_%/m": 100 * r.mean(),
            "vol_%/m": 100 * r.std(),
            "vol_%/yr": 100 * r.std() * np.sqrt(12),
            "skew": stats.skew(r),
            "excess_kurt": stats.kurtosis(r),
            "JB_p": jb.pvalue,
            "worst_m_%": 100 * r.min(),
            "best_m_%": 100 * r.max(),
        }
    return pd.DataFrame(rows).T


def h_change_quantiles(panel: pd.DataFrame, cols: list[str], horizons: list[int],
                       qs: tuple[float, ...] = (0.05, 0.5, 0.95)) -> pd.DataFrame:
    """Empirical quantiles (%) of H-month changes – the first naive cost-at-risk estimate."""
    rows = []
    for c in cols:
        for h in horizons:
            ch = h_month_changes(panel, c, h)
            row = {"series": SHORT.get(c, c), "H": h, "n_overlapping": len(ch),
                   "n_independent": len(ch) // h}
            row.update({f"q{int(q * 100):02d}_%": 100 * ch.quantile(q) for q in qs})
            row["P(rise>10%)"] = (ch > 0.10).mean()
            rows.append(row)
    return pd.DataFrame(rows).set_index(["series", "H"])


def vol_comparison(panel: pd.DataFrame, pairs: list[tuple[str, str]], max_lag: int = 6) -> pd.DataFrame:
    """PPI vs market price: volatility ratio, contemporaneous corr and lag at which market best leads PPI."""
    rows = []
    r = log_returns(panel)
    for mkt, ppi in pairs:
        both = r[[mkt, ppi]].dropna()
        ccf = {k: both[ppi].corr(both[mkt].shift(k)) for k in range(max_lag + 1)}
        best = max(ccf, key=lambda k: ccf[k])
        rows.append({
            "market": SHORT[mkt], "ppi": SHORT[ppi], "n": len(both),
            "vol_market_%/yr": 100 * both[mkt].std() * np.sqrt(12),
            "vol_ppi_%/yr": 100 * both[ppi].std() * np.sqrt(12),
            "ratio_ppi/market": both[ppi].std() / both[mkt].std(),
            "corr_lag0": ccf[0], "best_lead_m": best, "corr_best": ccf[best],
            "corr_levels": np.log(panel[[mkt, ppi]].dropna()).corr().iloc[0, 1],
        })
    return pd.DataFrame(rows).set_index(["market", "ppi"])


def rolling_vol(rets: pd.DataFrame, window: int = 12) -> pd.DataFrame:
    """Rolling annualised volatility (%)."""
    return 100 * rets.rolling(window, min_periods=window).std() * np.sqrt(12)


def arch_effects(rets: pd.DataFrame, lags: int = 12) -> pd.DataFrame:
    """Volatility clustering: ACF of squared returns at lag 1/3 and Ljung–Box p-value on r² up to ``lags``."""
    rows = {}
    for c in rets.columns:
        r = rets[c].dropna()
        r2 = (r - r.mean()) ** 2
        lb = acorr_ljungbox(r2, lags=[lags], return_df=True)
        rows[SHORT.get(c, c)] = {"acf_r2_lag1": r2.autocorr(1), "acf_r2_lag3": r2.autocorr(3),
                                 f"LB_p_r2_lag{lags}": float(lb["lb_pvalue"].iloc[0]),
                                 "acf_r_lag1": r.autocorr(1)}
    return pd.DataFrame(rows).T


def stationarity(panel: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """ADF (H0: unit root) and KPSS (H0: stationary) on log levels and on monthly log-returns."""
    rows = {}
    for c in cols:
        lv = np.log(panel[c].dropna())
        rt = lv.diff().dropna()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # KPSS p-values are bounded to [0.01, 0.1]
            rows[SHORT.get(c, c)] = {
                "ADF_p_level": adfuller(lv, autolag="AIC")[1],
                "KPSS_p_level": kpss(lv, regression="c", nlags="auto")[1],
                "ADF_p_return": adfuller(rt, autolag="AIC")[1],
                "KPSS_p_return": kpss(rt, regression="c", nlags="auto")[1],
            }
    df = pd.DataFrame(rows).T
    df["level_verdict"] = np.where((df.ADF_p_level > 0.05) & (df.KPSS_p_level < 0.05), "non-stationary",
                                   np.where((df.ADF_p_level < 0.05) & (df.KPSS_p_level > 0.05),
                                            "stationary", "ambiguous"))
    df["return_verdict"] = np.where((df.ADF_p_return < 0.05) & (df.KPSS_p_return > 0.05), "stationary",
                                    "check")
    return df


def seasonality_test(rets: pd.DataFrame) -> pd.DataFrame:
    """F-test that the 12 calendar-month means of returns are equal (H0: no seasonality)."""
    rows = {}
    for c in rets.columns:
        r = rets[c].dropna()
        groups = [g.values for _, g in r.groupby(r.index.month)]
        _, p = stats.f_oneway(*groups)
        kw = stats.kruskal(*groups)
        means = r.groupby(r.index.month).mean() * 100
        rows[SHORT.get(c, c)] = {"F_p": p, "KruskalWallis_p": kw.pvalue,
                                 "max_month_mean_%": means.max(), "min_month_mean_%": means.min(),
                                 "peak_month": int(means.idxmax()), "trough_month": int(means.idxmin())}
    return pd.DataFrame(rows).T


# --------------------------------------------------------------------------- 3.2 multivariate
def correlation(rets: pd.DataFrame, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    r = rets.loc[start:end]
    return r.rename(columns=SHORT).corr(min_periods=12)


def lead_lag(panel: pd.DataFrame, pairs: list[tuple[str, str]], max_lag: int = 6,
             change_window: int = 1) -> pd.DataFrame:
    """corr(Δx_{t−k}, Δy_t) for k = 0..max_lag, where x is the candidate leader.

    ``change_window`` = 1 uses monthly log-changes; 3 uses 3-month log-changes (overlapping).
    Rows: pair; columns: lag k.
    """
    lg = np.log(panel)
    d = lg.diff(change_window)
    out = {}
    for x, y in pairs:
        both = d[[x, y]].dropna()
        out[f"{SHORT[x]} → {SHORT[y]}"] = {k: both[y].corr(both[x].shift(k)) for k in range(max_lag + 1)}
    df = pd.DataFrame(out).T
    df.columns.name = "lead (months)"
    return df


def lead_lag_summary(ll: pd.DataFrame, n: int) -> pd.DataFrame:
    """Best lag per pair, its correlation and the ±1.96/√n significance band."""
    best = ll.drop(columns=0).abs().idxmax(axis=1)
    return pd.DataFrame({
        "corr_lag0": ll[0],
        "best_lead_m(k>=1)": best,
        "corr_at_best": [ll.loc[i, k] for i, k in best.items()],
        "approx_95%_band": 1.96 / np.sqrt(n),
    })


# --------------------------------------------------------------------------- 3.3 business
def cost_h_changes(cost: pd.DataFrame, horizons: list[int], col: str = "unit_cost") -> pd.DataFrame:
    """Quantiles of H-month % change of a cost column."""
    rows = {}
    for h in horizons:
        ch = (cost[col].shift(-h) / cost[col] - 1).dropna()
        rows[h] = {"n": len(ch), "q05_%": 100 * ch.quantile(.05), "q10_%": 100 * ch.quantile(.10),
                   "q50_%": 100 * ch.quantile(.5), "q90_%": 100 * ch.quantile(.90),
                   "q95_%": 100 * ch.quantile(.95), "max_%": 100 * ch.max(), "P(rise)": (ch > 0).mean()}
    return pd.DataFrame(rows).T.rename_axis("H")


def risk_contribution(cost: pd.DataFrame, materials: list[str], h: int) -> pd.Series:
    """Euler share of each material in the variance of the H-month € change of the RM basket.

    contribution_i = cov(ΔC_i, ΔC) / var(ΔC)  (sums to 1; can be negative for hedging materials).
    """
    d = (cost[materials].shift(-h) - cost[materials]).dropna()
    tot = d.sum(axis=1)
    return d.apply(lambda s: s.cov(tot)) / tot.var()


def margin_gamble(cost: pd.DataFrame, h: int, target_margin: float) -> pd.DataFrame:
    """Historical fixed-price simulation.

    At origin t the offer is priced at P_t = C_t / (1 − m). The unit is built at t+H with
    cost C_{t+H}, so realised margin = 1 − C_{t+H}/P_t. Assumes all material is bought at
    t+H (worst case: no purchase before delivery, no indexation, no hedge).
    """
    c = cost["unit_cost"]
    price = c / (1 - target_margin)
    realised = 1 - c.shift(-h) / price
    out = pd.DataFrame({"price": price, "cost_at_delivery": c.shift(-h),
                        "realised_margin": realised, "erosion_pts": realised - target_margin})
    return out.dropna()


def margin_gamble_summary(cost: pd.DataFrame, horizons: list[int], target_margin: float,
                          tol: float) -> pd.DataFrame:
    rows = {}
    for h in horizons:
        g = margin_gamble(cost, h, target_margin)
        e = 100 * g["erosion_pts"]
        rows[h] = {"n_origins": len(g), "mean_erosion_pts": e.mean(), "p05_erosion_pts": e.quantile(.05),
                   "worst_erosion_pts": e.min(), "P(margin < target)": (e < 0).mean(),
                   f"P(erosion > {100 * tol:.0f} pts)": (e < -100 * tol).mean(),
                   "buffer_P90_%price": max(0.0, -e.quantile(.10)),
                   "buffer_P95_%price": max(0.0, -e.quantile(.05))}
    return pd.DataFrame(rows).T.rename_axis("H")


def price_vs_cost(bench: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    """Yearly selling-price P50 per brand vs RM6 yearly average costs, indexed to the first
    year where the cost history exists (= 100). `bench` is Step 1's rmu_prices_yearly.csv."""
    piv = bench.pivot(index="year", columns="brand", values="p50")
    yr = cost.groupby(cost.index.year)[["rm_cost", "unit_cost"]].mean()
    out = piv.join(yr.rename(columns={"rm_cost": "RM6 RM basket", "unit_cost": "RM6 unit cost"}))
    base = int(yr.index.min())
    return 100 * out.loc[base:] / out.loc[base]
