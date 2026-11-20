"""Step 4 – download free external data used as forecast features.

Run from the repo root (needs internet the first time; files are cached):

    uv run python -m src.external_data            # download what is missing, rebuild outputs
    uv run python -m src.external_data --refresh  # download everything again

Outputs (in Data/external/, not committed, like the rest of Data/):
    external_monthly.csv   one row per month, one column per external series
    steo_forecasts.csv     EIA STEO forecasts: release month × target month × series
    external_sources.csv   source, licence, publication lag, URL and download date per series

Every source here is free to use with attribution. See SOURCES for licence details,
and the Step 4 report for why OECD CLI and Outokumpu/Aperam surcharges are not used.
"""

from __future__ import annotations

import argparse
import io
import json
import re
from datetime import date

import numpy as np
import pandas as pd
import requests

from src.data_prep import DATA

EXT = DATA / "external"
RAW = EXT / "raw"

# Generic client name: no personal details in requests to outside services.
HEADERS = {"User-Agent": "Mozilla/5.0 (research data download)"}

# First STEO release we need: the panel starts in Nov 2016.
STEO_FIRST = "2016-11"
STEO_SERIES = {"BREPUUS": "brent", "WTIPUUS": "wti", "NGHHUUS": "henry_hub"}

# series_id -> description, unit, source, licence, lag (months), url
SOURCES = {
    "GSCPI": {
        "description": "NY Fed Global Supply Chain Pressure Index (std. deviations from average)",
        "unit": "std dev",
        "source": "Federal Reserve Bank of New York",
        "licence": "Free to use with attribution (NY Fed website terms)",
        "lag": 3,
        "lag_note": "Published ~4th business day of the next month (true lag 1). The index is "
        "re-estimated every month and recent values are revised, so we only use a value "
        "once a later release has revised it: at origin o we use month o-1.",
        "url": "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx",
    },
    "EPU_GLOBAL": {
        "description": "Global Economic Policy Uncertainty index (GDP-weighted, current prices)",
        "unit": "index",
        "source": "Baker, Bloom & Davis – policyuncertainty.com",
        "licence": "Free to use, cite Baker, Bloom & Davis (2016) and Davis (2016)",
        "lag": 4,
        "lag_note": "Built from national indices, some of which come out late: last value "
        "Jul 2026 in a Nov 2026 download",
        "url": "https://www.policyuncertainty.com/media/Global_Policy_Uncertainty_Data.xlsx",
    },
    "EPU_EUROPE": {
        "description": "European Economic Policy Uncertainty index (news-based)",
        "unit": "index",
        "source": "Baker, Bloom & Davis – policyuncertainty.com",
        "licence": "Free to use, cite Baker, Bloom & Davis (2016)",
        "lag": 1,
        "lag_note": "Newspaper counts, published early in the next month",
        "url": "https://www.policyuncertainty.com/media/Europe_Policy_Uncertainty_Data.xlsx",
    },
    "EPU_US": {
        "description": "US Economic Policy Uncertainty index (news-based)",
        "unit": "index",
        "source": "Baker, Bloom & Davis – policyuncertainty.com",
        "licence": "Free to use, cite Baker, Bloom & Davis (2016)",
        "lag": 1,
        "lag_note": "Newspaper counts, published early in the next month",
        "url": "https://www.policyuncertainty.com/media/US_Policy_Uncertainty_Data.xlsx",
    },
    "EUA_EUR": {
        "description": "EU ETS carbon allowance (EUA) price, monthly average of daily prices",
        "unit": "EUR/t CO2",
        "source": "Ember – Carbon Price Viewer ('ETS prices – EU only' chart data)",
        "licence": "CC BY 4.0 (Ember)",
        "lag": 1,
        "lag_note": "Daily market prices; a month is complete at month end",
        "url": "https://flo.uri.sh/visualisation/30588075/embed",
    },
    "STEO": {
        "description": "EIA Short-Term Energy Outlook: forecasts of Brent, WTI and Henry Hub "
        "(one archived file per monthly release)",
        "unit": "USD/bbl, USD/MMBtu",
        "source": "US Energy Information Administration",
        "licence": "Public domain (US government work), attribution requested",
        "lag": 0,
        "lag_note": "Released in the first half of each month. We only use the release of the "
        "origin month itself, never a later one.",
        "url": "https://www.eia.gov/outlooks/steo/archives/{mon}{yy}_base.xlsx",
    },
}


def _get(url: str) -> bytes:
    r = requests.get(url, headers=HEADERS, timeout=90)
    r.raise_for_status()
    return r.content


def _cached(name: str, url: str, refresh: bool) -> bytes:
    """Download once into Data/external/raw/ and reuse the local copy afterwards."""
    path = RAW / name
    if refresh or not path.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_get(url))
    return path.read_bytes()


def _year_month_frame(df: pd.DataFrame, value_col: str) -> pd.Series:
    """Turn a Year / Month table (with footnote rows) into a monthly series."""
    y = pd.to_numeric(df["Year"], errors="coerce")
    m = pd.to_numeric(df["Month"], errors="coerce")
    ok = y.notna() & m.notna()
    idx = pd.to_datetime(
        {"year": y[ok].astype(int), "month": m[ok].astype(int), "day": 1}
    )
    return pd.Series(pd.to_numeric(df.loc[ok, value_col]).values, index=idx).sort_index()


def load_gscpi(refresh: bool = False) -> pd.Series:
    raw = _cached("gscpi_data.xlsx", SOURCES["GSCPI"]["url"], refresh)
    df = pd.read_excel(io.BytesIO(raw), sheet_name=0, header=None, engine="xlrd")  # .xls file
    dates = pd.to_datetime(df[0], format="%d-%b-%Y", errors="coerce")
    ok = dates.notna()
    s = pd.Series(pd.to_numeric(df.loc[ok, 1]).values, index=dates[ok])
    s.index = s.index.to_period("M").to_timestamp()
    return s.sort_index()


def load_epu(refresh: bool = False) -> pd.DataFrame:
    out = {}
    raw = _cached("epu_global.xlsx", SOURCES["EPU_GLOBAL"]["url"], refresh)
    out["EPU_GLOBAL"] = _year_month_frame(pd.read_excel(io.BytesIO(raw)), "GEPU_current")
    raw = _cached("epu_europe.xlsx", SOURCES["EPU_EUROPE"]["url"], refresh)
    out["EPU_EUROPE"] = _year_month_frame(
        pd.read_excel(io.BytesIO(raw)), "European_News_Index"
    )
    raw = _cached("epu_us.xlsx", SOURCES["EPU_US"]["url"], refresh)
    out["EPU_US"] = _year_month_frame(
        pd.read_excel(io.BytesIO(raw)), "News_Based_Policy_Uncert_Index"
    )
    return pd.DataFrame(out)


def load_eua(refresh: bool = False) -> pd.Series:
    """Daily EUA prices from the data embedded in Ember's published chart → monthly average."""
    raw = _cached("ember_eua_chart.html", SOURCES["EUA_EUR"]["url"], refresh).decode("utf-8")
    m = re.search(r"_Flourish_data\s*=\s*(\{.*?\})\s*,\s*\n", raw, re.DOTALL)
    if m is None:
        raise ValueError("Ember chart layout changed: _Flourish_data not found")
    points = json.loads(m.group(1))["data"]
    daily = pd.Series(
        [float(p["value"][0]) for p in points if p["value"] and p["value"][0] not in ("", None)],
        index=pd.to_datetime(
            [p["label"] for p in points if p["value"] and p["value"][0] not in ("", None)]
        ),
    ).sort_index()
    if not points[0]["metadata"][1].startswith("€"):
        raise ValueError("Ember chart unit changed")
    monthly = daily.resample("MS").mean()
    # Drop the last month if the chart stops before its last few days (incomplete month).
    last_day = daily.index.max()
    if last_day.day < last_day.days_in_month - 3:
        monthly = monthly.iloc[:-1]
    return monthly


def _steo_release_names(first: str, last: str) -> list[tuple[pd.Timestamp, str]]:
    months = pd.date_range(first, last, freq="MS")
    return [(m, f"{m.strftime('%b').lower()}{m.strftime('%y')}_base.xlsx") for m in months]


def parse_steo(raw: bytes, release: pd.Timestamp) -> pd.DataFrame:
    """Brent / WTI / Henry Hub monthly values from table 2 of one STEO release."""
    df = pd.read_excel(io.BytesIO(raw), sheet_name="2tab", header=None)
    years = pd.to_numeric(df.iloc[2], errors="coerce").ffill()
    months = df.iloc[3].astype(str).str[:3]
    cols = [
        j
        for j in range(df.shape[1])
        if pd.notna(years.iloc[j]) and months.iloc[j] in
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    ]
    dates = pd.to_datetime(
        [f"{int(years.iloc[j])}-{months.iloc[j]}-01" for j in cols], format="%Y-%b-%d"
    )
    rows = []
    for code, name in STEO_SERIES.items():
        hit = df.index[df.iloc[:, 0].astype(str).str.strip() == code]
        if len(hit) == 0:
            continue
        vals = pd.to_numeric(df.loc[hit[0], cols], errors="coerce").values
        rows += [(release, name, d, v) for d, v in zip(dates, vals) if pd.notna(v)]
    return pd.DataFrame(rows, columns=["release_month", "series", "target_month", "value"])


def load_steo(last_release: str, refresh: bool = False) -> tuple[pd.DataFrame, list[str]]:
    """All STEO releases from STEO_FIRST to last_release. Returns (forecasts, missing releases)."""
    frames, missing = [], []
    for release, name in _steo_release_names(STEO_FIRST, last_release):
        url = SOURCES["STEO"]["url"].format(mon=name[:3], yy=name[3:5])
        try:
            raw = _cached(f"steo_{name}", url, refresh)
            frames.append(parse_steo(raw, release))
        except (requests.HTTPError, ValueError, KeyError) as e:
            missing.append(f"{release:%Y-%m} ({type(e).__name__})")
    return pd.concat(frames, ignore_index=True), missing


def build(refresh: bool = False, last_release: str | None = None) -> None:
    EXT.mkdir(parents=True, exist_ok=True)
    last_release = last_release or (pd.Timestamp.today().to_period("M") - 1).strftime("%Y-%m")
    monthly = pd.concat(
        [load_gscpi(refresh).rename("GSCPI"), load_epu(refresh), load_eua(refresh).rename("EUA_EUR")],
        axis=1,
    ).sort_index()
    monthly = monthly.loc["1997-01-01":]
    monthly.index.name = "month"
    monthly.to_csv(EXT / "external_monthly.csv")

    steo, missing = load_steo(last_release, refresh)
    steo.to_csv(EXT / "steo_forecasts.csv", index=False)

    rows = []
    for sid, s in SOURCES.items():
        if sid == "STEO":
            first, last = steo["release_month"].min(), steo["release_month"].max()
        else:
            col = monthly[sid].dropna()
            first, last = col.index.min(), col.index.max()
        rows.append({"series_id": sid, **{k: v for k, v in s.items()},
                     "first_month": f"{first:%Y-%m}", "last_month": f"{last:%Y-%m}",
                     "retrieved": date.today().isoformat()})
    pd.DataFrame(rows).to_csv(EXT / "external_sources.csv", index=False)
    print(f"external_monthly: {monthly.shape[0]} months × {monthly.shape[1]} series; "
          f"STEO: {steo['release_month'].nunique()} releases"
          + (f"; missing releases: {', '.join(missing)}" if missing else ""))


def load_external() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(monthly series, STEO forecasts, sources table) from Data/external/."""
    monthly = pd.read_csv(EXT / "external_monthly.csv", index_col=0, parse_dates=True)
    steo = pd.read_csv(EXT / "steo_forecasts.csv", parse_dates=["release_month", "target_month"])
    sources = pd.read_csv(EXT / "external_sources.csv")
    return monthly, steo, sources


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--refresh", action="store_true", help="download every file again")
    p.add_argument("--last-release", default=None, help="last STEO release to fetch, YYYY-MM")
    a = p.parse_args()
    build(a.refresh, a.last_release)


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
