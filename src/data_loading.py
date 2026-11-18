"""Loaders for every raw source and a monthly EUR panel used by the EDA.

Every transformation applied to the raw files is listed in the docstring of the
function that performs it. Dates are always snapped to the first day of the month.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


def _month_start(s: pd.Series) -> pd.Series:
    """Snap any date (mid-month 15th, 3rd, 4th…) to the first day of its month."""
    return pd.to_datetime(s).dt.to_period("M").dt.to_timestamp()


# --------------------------------------------------------------------------- CSVs
def load_rm_wide(paths: dict) -> pd.DataFrame:
    """Raw-material wide CSV (S01–S13, D01–D02). Empty licensed columns L01–L08 are dropped."""
    df = pd.read_csv(paths["rm_wide"], parse_dates=["month"], index_col="month")
    df = df.drop(columns=["year", "month_num"])
    return df.dropna(axis=1, how="all")


def load_energy_wide(paths: dict) -> pd.DataFrame:
    return pd.read_csv(paths["energy_wide"], parse_dates=["month"], index_col="month")


def load_bom(paths: dict) -> pd.DataFrame:
    """BOM table without the three trailing 'Total …' rows."""
    bom = pd.read_csv(paths["bom"])
    return bom[bom["product_ref"].str.startswith(("RM6", "RMAirSeT"))].reset_index(drop=True)


# --------------------------------------------------------------------------- Excel
def load_lme(paths: dict, completed_only: bool = True) -> pd.DataFrame:
    """LME Cu/Al cash & 3-month (Westmetall) in USD and EUR plus LME stocks.

    The Nov-2026 row is month-to-date (provisional) and is dropped by default.
    """
    df = pd.read_excel(paths["lme"], sheet_name="Monthly Prices", header=4)
    df = df[pd.to_datetime(df["Month"], errors="coerce").notna()].copy()
    if completed_only:
        df = df[df["Period status"] == "Completed month"]
    df["month"] = _month_start(df["Month"])
    rename = {
        "Cu cash EUR/t": "cu_cash_eur", "Cu 3m EUR/t": "cu_3m_eur",
        "Al cash EUR/t": "al_cash_eur", "Al 3m EUR/t": "al_3m_eur",
        "Cu cash USD/t": "cu_cash_usd", "Al cash USD/t": "al_cash_usd",
        "Cu avg stocks t": "cu_stocks_t", "Al avg stocks t": "al_stocks_t",
        "USD per EUR": "usd_per_eur",
    }
    return df.set_index("month")[list(rename)].rename(columns=rename).astype(float)


def _check_header(raw: pd.DataFrame, row: int, col: int, expected: str) -> None:
    got = str(raw.iat[row, col]).strip()
    if expected.lower() not in got.lower():
        raise ValueError(f"Unexpected layout: cell ({row},{col}) = {got!r}, expected {expected!r}")


def load_meps(paths: dict) -> pd.DataFrame:
    """MEPS flat-product prices (EUR/t), Germany and France: HR, CR, HDG coil.

    The sheet has a 5-row header; column positions are checked against the labels.
    """
    raw = pd.read_excel(paths["steel"], sheet_name="MEPS", header=None)
    _check_header(raw, 0, 1, "Germany")
    _check_header(raw, 0, 6, "France")
    for c, lab in [(1, "HR"), (2, "CR"), (3, "HDG"), (6, "HR"), (7, "CR"), (8, "HDG")]:
        _check_header(raw, 4, c, lab)
    body = raw.iloc[5:, [0, 1, 2, 3, 6, 7, 8]]
    body.columns = ["month", "meps_hr_de", "meps_cr_de", "meps_hdg_de",
                    "meps_hr_fr", "meps_cr_fr", "meps_hdg_fr"]
    body = body[pd.to_datetime(body["month"], errors="coerce").notna()].copy()
    body["month"] = _month_start(body["month"])
    body = body.set_index("month").apply(pd.to_numeric, errors="coerce")
    return body.dropna(how="all")


def load_cru_flat(paths: dict) -> pd.DataFrame:
    """CRU flat products, Germany monthly AVERAGE of weekly quotes (EUR/t): HR, CR, HDG."""
    raw = pd.read_excel(paths["steel"], sheet_name="CRU Flat", header=None)
    for c, lab in [(6, "HR"), (12, "CR"), (18, "HDG")]:
        _check_header(raw, 1, c, "AVERAGE")
        _check_header(raw, 2, c, lab)
    body = raw.iloc[6:, [0, 6, 12, 18]]
    body.columns = ["month", "cru_hr_de", "cru_cr_de", "cru_hdg_de"]
    body = body[pd.to_datetime(body["month"], errors="coerce").notna()].copy()
    body["month"] = _month_start(body["month"])
    body = body.set_index("month").apply(pd.to_numeric, errors="coerce")
    return body.dropna(how="all")


def load_cru_stainless(paths: dict) -> pd.DataFrame:
    """CRU stainless 304 CR-2mm, Germany (EUR/t): base price, alloy surcharge and total.

    Dates are mid-month (15th) and are snapped to month start. Transaction price
    = base + alloy surcharge.
    """
    raw = pd.read_excel(paths["steel"], sheet_name="CRU Stainless", header=None)
    _check_header(raw, 0, 1, "Germany")
    _check_header(raw, 1, 1, "304")
    _check_header(raw, 4, 1, "BASE")
    _check_header(raw, 4, 2, "Alloy")
    body = raw.iloc[5:, [0, 1, 2]]
    body.columns = ["month", "ss304_base_de", "ss304_alloy_de"]
    body = body[pd.to_datetime(body["month"], errors="coerce").notna()].copy()
    body["month"] = _month_start(body["month"])
    body = body.set_index("month").apply(pd.to_numeric, errors="coerce").dropna(how="all")
    body["ss304_de"] = body["ss304_base_de"] + body["ss304_alloy_de"]
    return body


def isolated_spikes(s: pd.Series, threshold: float = 0.5) -> pd.Series:
    """Boolean mask of one-month spikes: |ln(x_t / mean(x_{t-1}, x_{t+1}))| > threshold while
    the two neighbours agree with each other (|ln(x_{t-1}/x_{t+1})| < threshold / 2).
    Catches typos such as a dropped digit; a genuine crash that persists is not flagged."""
    prev, nxt = s.shift(1), s.shift(-1)
    jump = np.log(s / ((prev + nxt) / 2)).abs()
    calm = np.log(prev / nxt).abs()
    return (jump > threshold) & (calm < threshold / 2)


def load_epoxy(paths: dict, mask_spikes: bool = True) -> pd.DataFrame:
    """Epoxy resin and its inputs (EUR/t). Odd dates (3rd/4th of month) snapped to month start.

    With ``mask_spikes`` an isolated input spike (see :func:`isolated_spikes`) is set to NaN,
    together with the epoxy price of that month (which is computed from the inputs).
    Known case: May-2026 epichlorohydrin = 257 €/t against ≈ 2,500 around it.
    """
    df = pd.read_excel(paths["epoxy"], header=0)
    df = df.rename(columns={df.columns[0]: "month"}).drop(columns=df.columns[1])
    df.columns = ["month", "benzene", "acetone", "epichlorohydrin", "epoxy_other_costs", "epoxy"]
    df = df[pd.to_datetime(df["month"], errors="coerce").notna()].copy()
    df["month"] = _month_start(df["month"])
    if df["month"].duplicated().any():
        raise ValueError("Two epoxy observations fall in the same month after snapping")
    df = df.set_index("month").astype(float)
    if mask_spikes:
        for c in ["benzene", "acetone", "epichlorohydrin", "epoxy_other_costs"]:
            bad = isolated_spikes(df[c])
            df.loc[bad, [c, "epoxy"]] = np.nan
    return df


def load_rmu_benchmark(paths: dict) -> pd.DataFrame:
    """Synthetic yearly RMU selling-price benchmark (EUR/unit, P10/P50/P90 per brand)."""
    df = pd.read_excel(paths["rmu_benchmark"], sheet_name="ML_Trend", header=3)
    df = df[df["Year"].apply(lambda v: isinstance(v, (int, float, np.integer)))].copy()
    df = df.rename(columns={"P10 (ML)": "p10", "P50 (ML)": "p50", "P90 (ML)": "p90"})
    df["Year"] = df["Year"].astype(int)
    return df[["ID", "Brand", "Year", "p10", "p50", "p90"]]


def load_teardown_costs(paths: dict) -> pd.DataFrame:
    """Teardown should-cost split (EUR) for RM6 and five competitors."""
    raw = pd.read_excel(paths["teardown"], sheet_name="Benchmark", header=None)
    brands = [str(b).split("\n")[0] for b in raw.iloc[4, 1:7]]
    rows = {str(raw.iat[r, 0]).strip(): raw.iloc[r, 1:7].values for r in range(6, 11)}
    out = pd.DataFrame(rows, index=brands).apply(pd.to_numeric, errors="coerce")
    insul = raw.iloc[24, 1:7].astype(str).values
    out["insulation"] = ["SF6" if "SF6" in s else "Air/vacuum" for s in insul]
    return out


# --------------------------------------------------------------------------- panel
SERIES_LABELS = {
    "cu_eur": "Copper LME (EUR/t)", "al_eur": "Aluminium LME (EUR/t)",
    "ni_eur": "Nickel LME (EUR/t)", "zn_eur": "Zinc LME (EUR/t)",
    "iron_ore_eur": "Iron ore 62% (EUR/t)", "eurusd": "EUR/USD (USD per EUR)",
    "steel_cr_de": "CR coil Germany MEPS (EUR/t)", "steel_cr_fr": "CR coil France MEPS (EUR/t)",
    "steel_hdg_de": "HDG coil Germany MEPS (EUR/t)", "steel_hr_de": "HR coil Germany MEPS (EUR/t)",
    "ss304_de": "Stainless 304 Germany CRU (EUR/t)", "epoxy": "Epoxy resin (EUR/t)",
    "benzene": "Benzene Europe (EUR/t)",
    "ppi_cu": "EU PPI copper S07", "ppi_al": "EU PPI aluminium S08",
    "ppi_steel": "EU PPI iron & steel S09", "ppi_steel_de": "DE PPI iron & steel S10",
    "ppi_plastics": "EU PPI plastics S11", "ppi_steel_us": "US PPI steel S12",
    "ppi_plastics_us": "US PPI plastics S13",
    "brent_eur": "Brent (EUR/bbl)", "ttf_eur": "TTF gas (EUR/MWh)",
    "power_de": "Power DE (EUR/MWh)", "power_fr": "Power FR (EUR/MWh)",
    "power_hu": "Power HU (EUR/MWh)",
}

# Short display names for tables and heatmaps
SHORT = {
    "cu_eur": "Copper", "al_eur": "Aluminium", "ni_eur": "Nickel", "zn_eur": "Zinc",
    "iron_ore_eur": "Iron ore", "eurusd": "EUR/USD", "steel_cr_de": "CR coil DE",
    "steel_cr_fr": "CR coil FR", "steel_hdg_de": "HDG DE", "steel_hr_de": "HR coil DE",
    "ss304_de": "Stainless 304", "epoxy": "Epoxy", "benzene": "Benzene",
    "ppi_cu": "PPI Cu", "ppi_al": "PPI Al", "ppi_steel": "PPI steel EU",
    "ppi_steel_de": "PPI steel DE", "ppi_plastics": "PPI plastics EU",
    "ppi_steel_us": "PPI steel US", "ppi_plastics_us": "PPI plastics US",
    "brent_eur": "Brent", "ttf_eur": "TTF gas", "power_de": "Power DE",
    "power_fr": "Power FR", "power_hu": "Power HU",
}


def build_eur_panel(paths: dict) -> pd.DataFrame:
    """One row per month, one column per series, in EUR where a price exists.

    Transformations:
    * Cu / Al: LME cash in EUR/t from the Westmetall file (longer: Jan-2016 → Oct-2026);
      cross-checked against D01/D02 by :func:`lme_vs_imf_check`.
    * Ni, Zn, iron ore: IMF USD/t divided by ECB EUR/USD (S06).
    * Steel: MEPS (Germany / France) and CRU stainless 304 Germany (base + alloy).
    * PPIs kept as indices (2021 = 100 or BLS base) – use returns only.
    * Energy: Brent EUR (ED01), TTF EUR/MWh (ED02), day-ahead power DE / FR / HU.
    No imputation is done here; months not yet published stay NaN.
    """
    rm = load_rm_wide(paths)
    en = load_energy_wide(paths)
    lme = load_lme(paths)
    meps = load_meps(paths)
    ss = load_cru_stainless(paths)
    ep = load_epoxy(paths)

    p = pd.DataFrame(index=pd.date_range("2012-11-01", "2026-10-01", freq="MS"))
    p.index.name = "month"
    p["cu_eur"] = lme["cu_cash_eur"]
    p["al_eur"] = lme["al_cash_eur"]
    p["ni_eur"] = rm["S03"] / rm["S06"]
    p["zn_eur"] = rm["S05"] / rm["S06"]
    p["iron_ore_eur"] = rm["S04"] / rm["S06"]
    p["eurusd"] = rm["S06"]
    p["steel_cr_de"] = meps["meps_cr_de"]
    p["steel_cr_fr"] = meps["meps_cr_fr"]
    p["steel_hdg_de"] = meps["meps_hdg_de"]
    p["steel_hr_de"] = meps["meps_hr_de"]
    p["ss304_de"] = ss["ss304_de"]
    p["epoxy"] = ep["epoxy"]
    p["benzene"] = ep["benzene"]
    for k, s in {"ppi_cu": "S07", "ppi_al": "S08", "ppi_steel": "S09", "ppi_steel_de": "S10",
                 "ppi_plastics": "S11", "ppi_steel_us": "S12", "ppi_plastics_us": "S13"}.items():
        p[k] = rm[s]
    p["brent_eur"] = en["ED01"]
    p["ttf_eur"] = en["ED02"]
    p["power_de"] = en["E09"]
    p["power_fr"] = en["E10"]
    p["power_hu"] = en["E11"]
    return p


def coverage_table(panel: pd.DataFrame) -> pd.DataFrame:
    """First / last observed month, count and number of internal gaps per series."""
    rows = []
    for c in panel.columns:
        s = panel[c]
        first, last = s.first_valid_index(), s.last_valid_index()
        inside = s.loc[first:last]
        rows.append({"series": c, "label": SERIES_LABELS.get(c, c),
                     "first": first.strftime("%Y-%m"), "last": last.strftime("%Y-%m"),
                     "n_obs": int(inside.notna().sum()), "internal_gaps": int(inside.isna().sum())})
    return pd.DataFrame(rows).set_index("series")


def lme_vs_imf_check(paths: dict) -> pd.DataFrame:
    """Relative difference between Westmetall LME cash (EUR) and IMF-based D01/D02."""
    rm = load_rm_wide(paths)
    lme = load_lme(paths)
    out = {}
    for metal, d, col in [("copper", "D01", "cu_cash_eur"), ("aluminium", "D02", "al_cash_eur")]:
        diff = (lme[col] / rm[d] - 1).dropna()
        out[metal] = {"n_months": len(diff), "median_abs_diff_pct": 100 * diff.abs().median(),
                      "max_abs_diff_pct": 100 * diff.abs().max()}
    return pd.DataFrame(out).T
