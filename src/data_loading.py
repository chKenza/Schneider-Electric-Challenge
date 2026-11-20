"""Data access for the EDA.

The EDA does not clean raw files itself any more: it reads the Step 1 outputs of
src/data_prep.py (Karin) and only renames columns to short, readable EDA names.
Run `uv run python -m src.data_prep` first.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# EDA name -> column of Data/processed/panel_monthly.csv (Step 1)
PANEL_COLUMNS = {
    "cu_eur": "LME_CU_CASH_EUR",
    "al_eur": "LME_AL_CASH_EUR",
    "ni_eur": "S03_EUR",
    "zn_eur": "S05_EUR",
    "iron_ore_eur": "S04_EUR",
    "eurusd": "S06",
    "steel_cr_de": "MEPS_DE_CR",
    "steel_cr_fr": "MEPS_FR_CR",
    "steel_hdg_de": "MEPS_DE_HDG",
    "steel_hr_de": "MEPS_DE_HR",
    "ss304_de": "CRU_SS304_DE_TOTAL",
    "epoxy": "EPOXY_EUR",
    "benzene": "BENZENE_EUR",
    "ppi_cu": "S07",
    "ppi_al": "S08",
    "ppi_steel": "S09",
    "ppi_steel_de": "S10",
    "ppi_plastics": "S11",
    "ppi_steel_us": "S12",
    "ppi_plastics_us": "S13",
    "brent_eur": "ED01",
    "ttf_eur": "ED02",
    "power_de": "E09",
    "power_fr": "E10",
    "power_hu": "E11",
}

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


def load_step1_panel(paths: dict) -> pd.DataFrame:
    """The full Step 1 panel (series IDs as in data_dictionary.csv)."""
    return pd.read_csv(paths["panel"], index_col=0, parse_dates=True)


def build_eur_panel(paths: dict) -> pd.DataFrame:
    """EDA panel: the Step 1 panel restricted to the 25 EDA series, with short names.

    All cleaning (date alignment, EUR conversion, the May-2026 epoxy fix, cut-off at the
    Sep-2026 origin) is done in src/data_prep.py. Rows start at the first month where any
    of these series has a value (Nov 2012, MEPS).
    """
    p = load_step1_panel(paths)[list(PANEL_COLUMNS.values())]
    p.columns = list(PANEL_COLUMNS)
    p = p.loc[p.dropna(how="all").index[0]:]
    p.index.name = "month"
    return p


def coverage_table(panel: pd.DataFrame) -> pd.DataFrame:
    """First / last observed month, count and number of internal gaps per series."""
    rows = []
    for c in panel.columns:
        s = panel[c]
        first, last = s.first_valid_index(), s.last_valid_index()
        inside = s.loc[first:last]
        rows.append({"series": c, "step1_id": PANEL_COLUMNS.get(c, c),
                     "label": SERIES_LABELS.get(c, c),
                     "first": first.strftime("%Y-%m"), "last": last.strftime("%Y-%m"),
                     "n_obs": int(inside.notna().sum()), "internal_gaps": int(inside.isna().sum())})
    return pd.DataFrame(rows).set_index("series")


def lme_vs_imf_check(paths: dict) -> pd.DataFrame:
    """Relative difference between Westmetall LME cash (EUR) and IMF-based D01/D02."""
    p = load_step1_panel(paths)
    out = {}
    for metal, d, col in [("copper", "D01", "LME_CU_CASH_EUR"), ("aluminium", "D02", "LME_AL_CASH_EUR")]:
        diff = (p[col] / p[d] - 1).dropna()
        out[metal] = {"n_months": len(diff), "median_abs_diff_pct": 100 * diff.abs().median(),
                      "max_abs_diff_pct": 100 * diff.abs().max()}
    return pd.DataFrame(out).T


# --------------------------------------------------------------------------- data quality
def isolated_spikes(s: pd.Series, threshold: float = 0.5) -> pd.Series:
    """Boolean mask of one-month spikes: |ln(x_t / mean(x_{t-1}, x_{t+1}))| > threshold while
    the two neighbours agree with each other (|ln(x_{t-1}/x_{t+1})| < threshold / 2).
    Catches typos such as a dropped digit; a genuine crash that persists is not flagged."""
    prev, nxt = s.shift(1), s.shift(-1)
    jump = np.log(s / ((prev + nxt) / 2)).abs()
    calm = np.log(prev / nxt).abs()
    return (jump > threshold) & (calm < threshold / 2)


def load_epoxy_raw(paths: dict) -> pd.DataFrame:
    """The raw epoxy file, untouched, to show the May-2026 typo that Step 1 fixed."""
    df = pd.read_excel(paths["epoxy_raw"], header=0)
    df = df.rename(columns={df.columns[0]: "month"}).drop(columns=df.columns[1])
    df.columns = ["month", "benzene", "acetone", "epichlorohydrin", "epoxy_other_costs", "epoxy"]
    df = df[pd.to_datetime(df["month"], errors="coerce").notna()].copy()
    df["month"] = pd.to_datetime(df["month"]).dt.to_period("M").dt.to_timestamp()
    return df.set_index("month").astype(float)


# --------------------------------------------------------------------------- benchmarks
def load_rmu_benchmark(paths: dict) -> pd.DataFrame:
    """Synthetic yearly RMU selling prices by brand (Step 1 output)."""
    return pd.read_csv(paths["rmu_prices"])


def load_teardown_costs(paths: dict) -> pd.DataFrame:
    """Teardown should-cost split (EUR) for RM6 and five competitors."""
    raw = pd.read_excel(paths["teardown"], sheet_name="Benchmark", header=None)
    brands = [str(b).split("\n")[0] for b in raw.iloc[4, 1:7]]
    rows = {str(raw.iat[r, 0]).strip(): raw.iloc[r, 1:7].values for r in range(6, 11)}
    out = pd.DataFrame(rows, index=brands).apply(pd.to_numeric, errors="coerce")
    insul = raw.iloc[24, 1:7].astype(str).values
    out["insulation"] = ["SF6" if "SF6" in s else "Air/vacuum" for s in insul]
    return out
