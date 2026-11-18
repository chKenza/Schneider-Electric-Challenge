"""Step 1 – Load, clean and align all price sources into one monthly panel.

Run from the repo root:

    uv run python -m src.data_prep                  # forecast origin 2026-09 (submission)
    uv run python -m src.data_prep --origin 2026-06  # rerun as if at an earlier month

The data files are not in the repo: put the challenge files in Data/ (see README).
Data/data/ can be left zipped as Data/data.zip.

Outputs (in Data/processed/, not committed):
    panel_monthly.csv        one row per month up to the origin, one column per series
    data_dictionary.csv      one row per series: source, unit, licence, lag, forecast target
    sources.csv              publication lag and licence per source
    imputation_log.csv       every value that was changed or filled, and why
    rmu_prices_yearly.csv    synthetic RMU selling prices by brand and year (P10/P50/P90)
"""

import argparse
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path("Data")
RAW = DATA / "data"
RAW_ZIP = DATA / "data.zip"
OUT = DATA / "processed"

STEEL_FILE = DATA / "Copia de Europe Steel INDEXES.xlsx"
LME_FILE = DATA / "LME_Copper_Aluminium_EU_Monthly_2016_2026.xlsx"
EPOXY_FILE = DATA / "Epoxy for student.xlsx"
RMU_FILE = DATA / "RMU_IQI_EU_Price_Benchmark_2017-2026_Synthetic.xlsx"

# Forecast origin of the submission: last month of data used (client slide 17).
ORIGIN_MONTH = "2026-09"

# Month in which the snapshot was taken (RM / energy CSVs: retrieved 2026-11-12;
# LME and steel files are snapshots of the same week).
SNAPSHOT_MONTH = pd.Timestamp("2026-11-01")

# The month of the snapshot is incomplete in the LME and CRU files (month-to-date).
DROP_FROM = SNAPSHOT_MONTH

# Sheet columns kept from the steel file: (sheet, column index) -> (id, description, unit).
# Germany and France are the indices Schneider's steel contracts reference
# (Hungarian plants are indexed on German prices).
MEPS_COLS = {
    1: ("MEPS_DE_HR", "MEPS hot-rolled coil, Germany", "EUR/t"),
    2: ("MEPS_DE_CR", "MEPS cold-rolled coil, Germany", "EUR/t"),
    3: ("MEPS_DE_HDG", "MEPS hot-dip galvanised coil, Germany", "EUR/t"),
    6: ("MEPS_FR_HR", "MEPS hot-rolled coil, France", "EUR/t"),
    7: ("MEPS_FR_CR", "MEPS cold-rolled coil, France", "EUR/t"),
    8: ("MEPS_FR_HDG", "MEPS hot-dip galvanised coil, France", "EUR/t"),
}
CRU_FLAT_COLS = {
    6: (
        "CRU_DE_HR",
        "CRU hot-rolled coil, Germany, domestic (monthly avg of weekly)",
        "EUR/t",
    ),
    12: (
        "CRU_DE_CR",
        "CRU cold-rolled coil, Germany, domestic (monthly avg of weekly)",
        "EUR/t",
    ),
    18: (
        "CRU_DE_HDG",
        "CRU hot-dip galvanised coil, Germany, domestic (monthly avg of weekly)",
        "EUR/t",
    ),
    20: ("CRU_FR_HR", "CRU hot-rolled coil, France, domestic (spot)", "EUR/t"),
    21: ("CRU_FR_CR", "CRU cold-rolled coil, France, domestic (spot)", "EUR/t"),
    22: ("CRU_FR_HDG", "CRU hot-dip galvanised coil, France, domestic (spot)", "EUR/t"),
}
CRU_STAINLESS_COLS = {
    1: ("CRU_SS304_DE_BASE", "CRU stainless 304 CR 2mm, Germany, base price", "EUR/t"),
    2: (
        "CRU_SS304_DE_ALLOY",
        "CRU stainless 304 CR 2mm, Germany, alloy surcharge",
        "EUR/t",
    ),
    7: ("CRU_SS304_FR_BASE", "CRU stainless 304 CR 2mm, France, base price", "EUR/t"),
    8: (
        "CRU_SS304_FR_ALLOY",
        "CRU stainless 304 CR 2mm, France, alloy surcharge",
        "EUR/t",
    ),
}
CRU_LONG_COLS = {
    2: (
        "CRU_DE_MBAR",
        "CRU merchant bar, Germany, delivered (long history from 1997)",
        "EUR/t",
    ),
}

LME_COLS = {
    "Cu cash USD/t": ("LME_CU_CASH_USD", "LME copper cash, monthly avg", "USD/t"),
    "Cu 3m USD/t": ("LME_CU_3M_USD", "LME copper 3-month, monthly avg", "USD/t"),
    "Al cash USD/t": ("LME_AL_CASH_USD", "LME aluminium cash, monthly avg", "USD/t"),
    "Al 3m USD/t": ("LME_AL_3M_USD", "LME aluminium 3-month, monthly avg", "USD/t"),
    "Cu cash EUR/t": ("LME_CU_CASH_EUR", "LME copper cash in EUR", "EUR/t"),
    "Cu 3m EUR/t": ("LME_CU_3M_EUR", "LME copper 3-month in EUR", "EUR/t"),
    "Al cash EUR/t": ("LME_AL_CASH_EUR", "LME aluminium cash in EUR", "EUR/t"),
    "Al 3m EUR/t": ("LME_AL_3M_EUR", "LME aluminium 3-month in EUR", "EUR/t"),
    "Cu spread EUR/t": (
        "LME_CU_SPREAD_EUR",
        "LME copper 3-month minus cash (>0 contango)",
        "EUR/t",
    ),
    "Al spread EUR/t": (
        "LME_AL_SPREAD_EUR",
        "LME aluminium 3-month minus cash (>0 contango)",
        "EUR/t",
    ),
    "Cu avg stocks t": (
        "LME_CU_STOCKS",
        "LME copper warehouse stocks, monthly avg",
        "t",
    ),
    "Al avg stocks t": (
        "LME_AL_STOCKS",
        "LME aluminium warehouse stocks, monthly avg",
        "t",
    ),
}

EPOXY_COLS = {
    2: ("BENZENE_EUR", "Benzene, Europe", "EUR/t"),
    3: ("ACETONE_EUR", "Acetone, Europe", "EUR/t"),
    4: ("ECH_EUR", "Epichlorohydrin, Europe", "EUR/t"),
    5: ("EPOXY_OTHER_EUR", "Epoxy other costs (calculated), Europe", "EUR/t"),
    6: ("EPOXY_EUR", "Epoxy resin, Europe", "EUR/t"),
}

# USD series converted to EUR with S06 (USD per EUR).
USD_TO_EUR = {
    "S03": ("S03_EUR", "LME nickel in EUR (S03 / S06)", "EUR/t"),
    "S04": ("S04_EUR", "Iron ore 62% Fe in EUR (S04 / S06)", "EUR/dmt"),
    "S05": ("S05_EUR", "LME zinc in EUR (S05 / S06)", "EUR/t"),
}


def to_month_start(dates) -> pd.DatetimeIndex:
    """Snap any date in a month (e.g. 2026-08-15) to the first day of that month."""
    return pd.DatetimeIndex(pd.to_datetime(dates)).to_period("M").to_timestamp()


def read_raw_csv(name: str, **kwargs) -> pd.DataFrame:
    """Read a file of the challenge's data folder, from Data/data/ or else Data/data.zip."""
    if (RAW / name).exists():
        return pd.read_csv(RAW / name, **kwargs)
    with zipfile.ZipFile(RAW_ZIP) as z, z.open(f"data/{name}") as f:
        return pd.read_csv(f, **kwargs)


def _read_sheet_block(sheet: str, header_rows: int, cols: dict) -> pd.DataFrame:
    """Read selected columns of a multi-row-header sheet of the steel file."""
    raw = pd.read_excel(STEEL_FILE, sheet_name=sheet, header=None)
    body = raw.iloc[header_rows:]
    body = body[pd.to_datetime(body[0], errors="coerce").notna()]
    out = pd.DataFrame(
        {
            sid: pd.to_numeric(body[j], errors="coerce").values
            for j, (sid, _, _) in cols.items()
        },
        index=to_month_start(body[0]),
    )
    return out.dropna(how="all")


def load_rm_prices() -> pd.DataFrame:
    wide = read_raw_csv(
        "rm_prices_monthly_wide.csv", parse_dates=["month"], index_col="month"
    )
    wide = wide.drop(columns=["year", "month_num"]).dropna(
        axis=1, how="all"
    )  # drops empty L01–L08
    for usd, (eur, _, _) in USD_TO_EUR.items():
        wide[eur] = wide[usd] / wide["S06"]
    return wide


def load_energy() -> pd.DataFrame:
    wide = read_raw_csv(
        "energy_prices_monthly_wide.csv", parse_dates=["month"], index_col="month"
    )
    return wide.drop(columns=[c for c in wide.columns if not c.startswith("E")])


def load_steel() -> pd.DataFrame:
    stainless = _read_sheet_block("CRU Stainless", 5, CRU_STAINLESS_COLS)
    # Full 304 price = base + alloy surcharge (the alloy part follows nickel).
    for c in ("DE", "FR"):
        stainless[f"CRU_SS304_{c}_TOTAL"] = (
            stainless[f"CRU_SS304_{c}_BASE"] + stainless[f"CRU_SS304_{c}_ALLOY"]
        )
    return pd.concat(
        [
            _read_sheet_block("MEPS", 5, MEPS_COLS),
            _read_sheet_block("CRU Flat", 6, CRU_FLAT_COLS),
            stainless,
            _read_sheet_block("CRU Long", 5, CRU_LONG_COLS),
        ],
        axis=1,
    )


def load_lme() -> pd.DataFrame:
    raw = pd.read_excel(LME_FILE, sheet_name="Monthly Prices", header=4)
    raw = raw[pd.to_datetime(raw["Month"], errors="coerce").notna()]
    raw = raw[raw["Period status"] == "Completed month"]  # drop the month-to-date row
    out = (
        raw[list(LME_COLS)]
        .rename(columns={k: v[0] for k, v in LME_COLS.items()})
        .astype(float)
    )
    out.index = to_month_start(raw["Month"])
    return out


def load_epoxy() -> pd.DataFrame:
    raw = pd.read_excel(EPOXY_FILE, header=None).iloc[1:]
    out = pd.DataFrame(
        {
            sid: pd.to_numeric(raw[j], errors="coerce").values
            for j, (sid, _, _) in EPOXY_COLS.items()
        },
        index=to_month_start(raw[0]),
    )
    return out


def load_rmu_prices() -> pd.DataFrame:
    """Synthetic yearly EU selling price of a 24 kV IQI-type RMU, by brand (EUR ex-VAT)."""
    raw = pd.read_excel(RMU_FILE, sheet_name="ML_Trend", header=3)
    raw = raw[pd.to_numeric(raw["Year"], errors="coerce").notna()]
    out = raw[["ID", "Brand", "Year", "P10 (ML)", "P50 (ML)", "P90 (ML)"]]
    out.columns = ["brand_id", "brand", "year", "p10", "p50", "p90"]
    return out.astype({"year": int, "p10": float, "p50": float, "p90": float})


def fill_latest_from_lme(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fill S01/S02 (and D01/D02) for months where IMF is not yet published but LME is.

    Same underlying LME cash price, different publisher (Westmetall vs IMF);
    the README measured a median gap of 0.13 % (Cu) and 0.18 % (Al).
    Has no effect when the origin is a month IMF already covers (e.g. 2026-09).
    """
    log = []
    for usd, lme, eur in (
        ("S01", "LME_CU_CASH_USD", "D01"),
        ("S02", "LME_AL_CASH_USD", "D02"),
    ):
        gap = (
            panel[usd].isna()
            & panel[lme].notna()
            & (panel.index > panel[usd].last_valid_index())
        )
        for month in panel.index[gap]:
            panel.loc[month, usd] = panel.loc[month, lme]
            panel.loc[month, eur] = panel.loc[month, usd] / panel.loc[month, "S06"]
            for sid in (usd, eur):
                log.append(
                    {
                        "month": month.date(),
                        "series_id": sid,
                        "value": panel.loc[month, sid],
                        "method": f"IMF not yet published; filled from {lme} (Westmetall)",
                    }
                )
    return panel, pd.DataFrame(log)


# Values judged to be entry errors: replaced by linear interpolation between neighbours.
SUSPECT_VALUES = [
    ("ECH_EUR", "2026-05-01", "Entry error: 257 vs ~2,500 around it (likely ×10 typo)"),
    (
        "EPOXY_EUR",
        "2026-05-01",
        "Entry error: -27 % then +39 %, same month as the ECH typo",
    ),
]


def fix_suspect_values(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    log = []
    for sid, month, reason in SUSPECT_VALUES:
        month = pd.Timestamp(month)
        if month not in panel.index:  # after the origin
            continue
        original = panel.loc[month, sid]
        panel.loc[month, sid] = np.nan
        # Interpolates only between known neighbours: left empty if it is the last month.
        panel[sid] = panel[sid].interpolate(limit_area="inside")
        method = (
            "linear interpolation" if pd.notna(panel.loc[month, sid]) else "left empty"
        )
        log.append(
            {
                "month": month.date(),
                "series_id": sid,
                "value": panel.loc[month, sid],
                "method": f"{reason}; was {original:.1f}, {method}",
            }
        )
    return panel, pd.DataFrame(log)


def build_panel(origin: str = ORIGIN_MONTH) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Monthly panel up to and including the origin month, plus the log of changes."""
    panel = pd.concat(
        [load_rm_prices(), load_energy(), load_steel(), load_lme(), load_epoxy()],
        axis=1,
    )
    panel = panel.sort_index()
    panel = panel[panel.index < DROP_FROM]  # incomplete snapshot month
    panel = panel[panel.index <= pd.Timestamp(origin)]  # nothing after the origin
    panel.index.name = "month"
    panel, log_fix = fix_suspect_values(panel)
    panel, log_fill = fill_latest_from_lme(panel)
    return panel, pd.concat([log_fix, log_fill], ignore_index=True)


# Availability rule: the value for month m can be used at quote month t if m <= t - lag.
# Lags are measured on the snapshot (last complete month vs snapshot month) and
# cross-checked with the publishers' calendars in the README.
SOURCE_LAGS = {
    "IMF via FRED": (2, "Monthly avg; Sep 2026 latest on 12 Nov 2026"),
    "Eurostat PPI": (
        2,
        "Released ~5–6 weeks after month end; last 2–3 months are revised",
    ),
    "US BLS via FRED": (2, "Released mid next month; revised 4 months later"),
    "ECB": (1, "Daily fixings; monthly mean available days after month end"),
    "Ember": (1, "Day-ahead prices; available days after month end"),
    "Bank of Japan": (1, "Released ~2 weeks after month end"),
    "JEPX": (1, "Half-hourly spot prices; available days after month end"),
    "Eurostat imports": (4, "Oil import volumes lag 3–4 months"),
    "Derived": (None, "Same lag as its slowest input"),
    "LME (Westmetall)": (1, "Daily settlement prices; month known at month end"),
    "MEPS": (1, "Monthly survey published at month end"),
    "CRU Flat": (1, "Weekly assessments; month known at month end"),
    "CRU Stainless": (
        3,
        "Last value Aug 2026 in a Nov 2026 snapshot – confirm with client",
    ),
    "CRU Long": (2, "Last value Sep 2026 in a Nov 2026 snapshot"),
    "Epoxy file": (1, "Last value Oct 2026"),
}

# Licence and confidentiality per source (client slide 16: respect data licences).
SOURCE_LICENCES = {
    "IMF via FRED": "IMF Primary Commodity Prices via FRED – free, attribution",
    "Eurostat PPI": "Eurostat – CC BY 4.0",
    "US BLS via FRED": "US BLS (public domain) via FRED – attribution",
    "ECB": "ECB Data Portal – free reuse with source acknowledgement",
    "Ember": "Ember – CC BY 4.0",
    "Bank of Japan": "Bank of Japan – free, source to be cited",
    "JEPX": "JEPX – published for public use, source to be cited",
    "Eurostat imports": "Eurostat – CC BY 4.0",
    "Derived": "Same as its inputs",
    "LME (Westmetall)": "LME prices via Westmetall – LME data is licensed; "
    "do not redistribute without checking terms",
    "MEPS": "Licensed (MEPS), provided by Schneider – confidential, do not redistribute",
    "CRU Flat": "Licensed (CRU), provided by Schneider – confidential, do not redistribute",
    "CRU Stainless": "Licensed (CRU), provided by Schneider – confidential, "
    "do not redistribute",
    "CRU Long": "Licensed (CRU), provided by Schneider – confidential, do not redistribute",
    "Epoxy file": "Provided by Schneider for the challenge – original source unknown, "
    "treat as confidential",
    "Schneider BOM": "Schneider internal (bom_materials.csv) – confidential, "
    "challenge use only",
    "RMU price benchmark": "Schneider, synthetic (RMU_IQI_EU_Price_Benchmark) – "
    "confidential, challenge use only",
}


def _source_of(provider: str, provider_code: str) -> str:
    """Map a catalog provider to a SOURCE_LAGS key."""
    if provider.startswith("Derived"):
        return "Derived"
    if "nrg_ti" in provider_code:
        return "Eurostat imports"
    for key, source in (
        ("IMF", "IMF via FRED"),
        ("Eurostat", "Eurostat PPI"),
        ("BLS", "US BLS via FRED"),
        ("Central Bank", "ECB"),
        ("Ember", "Ember"),
        ("JEPX", "JEPX"),
        ("Bank of Japan", "Bank of Japan"),
    ):
        if key in provider:
            return source
    raise ValueError(f"Unknown provider: {provider}")


def _metadata() -> pd.DataFrame:
    """One row per series: description, unit, source."""
    rows = []
    rm = read_raw_csv("source_catalog.csv")
    for _, r in rm[rm["access"] == "Free"].iterrows():
        source = _source_of(r["provider"], str(r["provider_code"]))
        rows.append((r["series_id"], r["series_name"], r["unit"], source))
    en = read_raw_csv("energy_source_catalog.csv")
    for _, r in en.iterrows():
        source = _source_of(r["provider"], str(r["provider_code"]))
        desc = f"{r['series_name']} ({r['region']})"
        rows.append((r["series_id"], desc, r["unit"], source))
    for sid, desc, unit in USD_TO_EUR.values():
        rows.append((sid, desc, unit, "Derived"))
    for cols, source in (
        (MEPS_COLS, "MEPS"),
        (CRU_FLAT_COLS, "CRU Flat"),
        (CRU_STAINLESS_COLS, "CRU Stainless"),
        (CRU_LONG_COLS, "CRU Long"),
    ):
        rows += [(sid, desc, unit, source) for sid, desc, unit in cols.values()]
    for c in ("DE", "FR"):
        rows.append(
            (
                f"CRU_SS304_{c}_TOTAL",
                f"CRU stainless 304, {c}, base + alloy surcharge",
                "EUR/t",
                "CRU Stainless",
            )
        )
    rows += [
        (sid, desc, unit, "LME (Westmetall)") for sid, desc, unit in LME_COLS.values()
    ]
    rows += [(sid, desc, unit, "Epoxy file") for sid, desc, unit in EPOXY_COLS.values()]
    return pd.DataFrame(
        rows, columns=["series_id", "description", "unit", "source"]
    ).set_index("series_id")


def forecast_targets() -> dict[str, str]:
    """Series to forecast in the submission CSV: the priceable BOM proxies, by region.

    Taken from bom_materials.csv (eu_series_ids / ww_series_ids); the licensed
    L-series are empty and skipped.
    """
    bom = read_raw_csv("bom_materials.csv")
    targets = {}
    for col, region in (("eu_series_ids", "EU"), ("ww_series_ids", "WW")):
        for ids in bom[col].dropna():
            for sid in ids.split(";"):
                if not sid.startswith("L"):
                    targets[sid] = region
    return targets


DERIVED_INPUTS = {
    "D01": ["S01", "S06"],
    "D02": ["S02", "S06"],
    "S03_EUR": ["S03", "S06"],
    "S04_EUR": ["S04", "S06"],
    "S05_EUR": ["S05", "S06"],
    "ED01": ["E01", "E23"],
    "ED02": ["E05", "E23"],
    "ED03": ["E07", "E23"],
    "ED04": ["E06", "E23"],
    "ED05": ["E12", "E24"],
    "ED06": ["E20", "E21"],
}


def build_dictionary(panel: pd.DataFrame) -> pd.DataFrame:
    meta = _metadata().reindex(panel.columns)
    targets = forecast_targets()
    meta["forecast_target"] = meta.index.isin(list(targets))
    meta["target_region"] = meta.index.map(targets)
    meta["licence"] = meta["source"].map(SOURCE_LICENCES)
    lag = meta["source"].map(lambda s: SOURCE_LAGS.get(s, (None, ""))[0])
    for sid, inputs in DERIVED_INPUTS.items():
        lag[sid] = max(SOURCE_LAGS[meta.loc[i, "source"]][0] for i in inputs)
    meta["lag_months"] = lag.astype("Int64")
    meta["first_month"] = [panel[c].first_valid_index().date() for c in panel.columns]
    meta["last_month"] = [panel[c].last_valid_index().date() for c in panel.columns]
    meta["n_obs"] = panel.notna().sum()
    meta["n_internal_gaps"] = [
        int(
            panel[c]
            .loc[panel[c].first_valid_index() : panel[c].last_valid_index()]
            .isna()
            .sum()
        )
        for c in panel.columns
    ]
    return meta


def build_sources(dictionary: pd.DataFrame) -> pd.DataFrame:
    """One row per source: publication lag, licence, number of series in the panel."""
    rows = [
        (
            source,
            SOURCE_LAGS.get(source, (None, ""))[0],
            SOURCE_LAGS.get(source, (None, "Not in the monthly panel"))[1],
            licence,
            int((dictionary["source"] == source).sum()),
        )
        for source, licence in SOURCE_LICENCES.items()
    ]
    return pd.DataFrame(
        rows, columns=["source", "lag_months", "note", "licence", "n_series"]
    ).astype({"lag_months": "Int64"})


def available_at(
    panel: pd.DataFrame, dictionary: pd.DataFrame, quote_month
) -> pd.DataFrame:
    """What was known at the start of `quote_month`: hides each series' unpublished months.

    Use this in backtests so a model at origin t never sees data published after t.
    """
    quote_month = pd.Timestamp(quote_month)
    known = panel[panel.index < quote_month].copy()
    for col, lag in dictionary["lag_months"].items():
        cutoff = quote_month - pd.DateOffset(months=int(lag))
        known.loc[known.index > cutoff, col] = np.nan
    return known


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--origin",
        default=ORIGIN_MONTH,
        help=f"last month of data used, YYYY-MM (default {ORIGIN_MONTH})",
    )
    args = parser.parse_args()

    panel, log = build_panel(args.origin)
    dictionary = build_dictionary(panel)
    OUT.mkdir(exist_ok=True)
    panel.to_csv(OUT / "panel_monthly.csv")
    dictionary.to_csv(OUT / "data_dictionary.csv")
    build_sources(dictionary).to_csv(OUT / "sources.csv", index=False)
    log.to_csv(OUT / "imputation_log.csv", index=False)
    load_rmu_prices().to_csv(OUT / "rmu_prices_yearly.csv", index=False)
    print(
        f"origin {args.origin}: {panel.shape[0]} months x {panel.shape[1]} series "
        f"({panel.index.min().date()} → {panel.index.max().date()}), "
        f"{len(log)} values changed, {int(dictionary['forecast_target'].sum())} targets"
    )


if __name__ == "__main__":
    main()
