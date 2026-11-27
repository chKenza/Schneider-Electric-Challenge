"""Monthly update – check a new month of prices and rerun the pipeline on it (Level 5).

Run from the repo root:

    uv run python -m src.monthly_update new_month.csv           # check, then run (about 5 min)
    uv run python -m src.monthly_update new_month.csv --check   # check only
    uv run python -m src.monthly_update --held-back 2026-09     # write that month as a test file

The file uses the client's format (Data/data/data_dictionary.csv): the columns of
rm_prices_monthly_wide.csv (month = 1st of the month, one column per series S01…L08), or
the long format (month, series_id, value). Rules checked: S01–S13 present, numbers > 0,
blank = not available (never 0), L01–L08 left empty (licensed), the month follows the
data on file, and each change is within what the series has done before.

A run never touches this repo's outputs: it copies the code and data to runs/<month>_<time>/,
adds the file to Data/updates/ there, and runs `python -m src.pipeline` with SE_ORIGIN set
to the new month (every stage reads the origin from src.data_prep.ORIGIN_MONTH).
The decision tool's "Monthly update" page does the same from a browser.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.config import REPO_ROOT
from src.data_prep import read_raw_csv

RUNS = REPO_ROOT / "runs"
REQUIRED = [f"S{i:02d}" for i in range(1, 14)]   # free series the forecast needs
DERIVED = {"D01": ("S01", "S06"), "D02": ("S02", "S06")}   # EUR = USD / (USD per EUR)
LICENSED = [f"L{i:02d}" for i in range(1, 9)]
JUMP_SD = 4.0   # a monthly change beyond 4 standard deviations of the series' history is flagged


def history() -> pd.DataFrame:
    """The client's wide file as received (all months, all columns)."""
    return read_raw_csv("rm_prices_monthly_wide.csv", parse_dates=["month"], index_col="month")


def catalog() -> pd.DataFrame:
    return read_raw_csv("source_catalog.csv").set_index("series_id")


def held_back_file(month: str) -> bytes:
    """One month of the client's file, exactly as received: a test upload."""
    h = history()
    row = h.loc[[pd.Timestamp(month)]].reset_index()
    row["month"] = row["month"].dt.strftime("%Y-%m-%d")
    return row.to_csv(index=False, float_format="%.4f").encode()


def template(month: str) -> bytes:
    """Empty row in the client's format for the given month."""
    cols = history().columns
    t = pd.Timestamp(month)
    row = pd.DataFrame([{"month": f"{t:%Y-%m-%d}", "year": t.year, "month_num": t.month}],
                       columns=["month", *cols])
    return row.to_csv(index=False).encode()


def read_upload(data: bytes) -> pd.DataFrame:
    """Wide or long client format -> wide (index month, one column per series)."""
    df = pd.read_csv(io.BytesIO(data))
    df.columns = [str(c).strip() for c in df.columns]
    if {"series_id", "value"} <= set(df.columns):        # long format
        df = df.pivot_table(index="month", columns="series_id", values="value", aggfunc="last")
        df = df.reset_index()
    if "month" not in df.columns:
        raise ValueError("No `month` column: expected the client's format "
                         "(rm_prices_monthly_wide.csv or rm_prices_monthly_long.csv).")
    return df


@dataclass
class Check:
    month: str | None          # last month in the file (the new origin)
    months: list[str]
    rows: pd.DataFrame         # one row per rule: rule, status (ok | warn | error), detail
    values: pd.DataFrame       # one row per series: last on file, new, change, status
    clean: pd.DataFrame | None  # the file to write to Data/updates/ (client wide format)

    @property
    def ok(self) -> bool:
        return not (self.rows["status"] == "error").any()

    @property
    def replaces(self) -> bool:
        """True when the month is already on file (held-back test)."""
        return self.month is not None and pd.Timestamp(self.month) <= history().index.max()


def check(df: pd.DataFrame) -> Check:
    rows: list[tuple[str, str, str]] = []

    def add(rule: str, status: str, detail: str = "") -> None:
        rows.append((rule, status, detail))

    h = history()
    cols = list(h.columns)

    # 1. columns
    unknown = [c for c in df.columns if c not in ["month", *cols]]
    missing = [c for c in REQUIRED if c not in df.columns]
    add("Columns in the client's format",
        "error" if missing else ("warn" if unknown else "ok"),
        (f"missing {', '.join(missing)}. " if missing else "")
        + (f"Ignored: {', '.join(unknown)}." if unknown else "")
        or f"{len([c for c in df.columns if c in cols])} series columns recognised")

    # 2. months
    m = pd.to_datetime(df["month"].astype(str), errors="coerce")
    if m.isna().any():
        add("Month as yyyy-mm-01", "error", f"{int(m.isna().sum())} row(s) without a valid month")
        return Check(None, [], pd.DataFrame(rows, columns=["rule", "status", "detail"]),
                     pd.DataFrame(), None)
    not_first = (m.dt.day != 1).sum()
    m = m.dt.to_period("M").dt.to_timestamp()
    add("Month as yyyy-mm-01", "warn" if not_first else "ok",
        f"{not_first} date(s) moved to the 1st of the month" if not_first else "")
    df = df.assign(month=m).drop_duplicates("month", keep="last").set_index("month").sort_index()
    months = list(df.index)
    full = h[REQUIRED].dropna(how="any")
    last_full = full.index.max()          # last month with every free series on file
    first = months[0]
    expected = last_full + pd.DateOffset(months=1)
    gaps = pd.date_range(first, months[-1], freq="MS").difference(df.index)
    if first > expected or len(gaps):
        add("Month follows the data on file", "error",
            f"data on file ends {last_full:%b %Y}; the file starts {first:%b %Y}"
            + (f" and skips {', '.join(f'{g:%b %Y}' for g in gaps)}" if len(gaps) else ""))
    elif first <= last_full:
        add("Month follows the data on file", "warn",
            f"{first:%b %Y} is already on file: test with a held-back month. The forecast "
            f"is rerun as of {months[-1]:%b %Y}, using only data up to that month.")
    else:
        add("Month follows the data on file", "ok", f"data on file ends {last_full:%b %Y}")

    # 3. values: numbers, > 0, required present
    body = df.reindex(columns=cols).drop(columns=["year", "month_num"], errors="ignore")
    cols_s = list(body.columns)
    num = body.apply(pd.to_numeric, errors="coerce")
    bad_text = [c for c in cols_s if (body[c].notna() & num[c].isna()).any()]
    zeros = [c for c in cols_s if (num[c] <= 0).any()]
    empty = [c for c in REQUIRED if num[c].isna().any()]
    add("Values are numbers above 0 (blank = not available, never 0)",
        "error" if bad_text or zeros else "ok",
        "; ".join(filter(None, [f"not a number: {', '.join(bad_text)}" if bad_text else "",
                                f"0 or negative: {', '.join(zeros)}" if zeros else ""])))
    add("Every free series S01–S13 filled", "error" if empty else "ok",
        f"blank: {', '.join(empty)} (the forecast needs all of them)" if empty else "")
    lic = [c for c in LICENSED if num[c].notna().any()]
    add("Licensed series L01–L08 left empty", "warn" if lic else "ok",
        f"{', '.join(lic)} filled: ignored (not redistributable)" if lic else "")
    num[LICENSED] = np.nan

    # 4. derived D01 / D02 recomputed; flag if the file disagrees by > 1 %
    off = []
    for d, (usd, fx) in DERIVED.items():
        calc = num[usd] / num[fx]
        far = (num[d] / calc - 1).abs() > 0.01
        if far.any():
            off.append(d)
        num[d] = num[d].where(num[d].notna() & ~far, calc)   # blank or wrong: the formula
    add("D01 / D02 = USD price ÷ EUR/USD", "warn" if off else "ok",
        f"{', '.join(off)} differ from the formula by > 1 %: recomputed" if off
        else "consistent (blanks are computed)")

    # 5. plausibility: change vs the previous month, against the series' own history
    cat = catalog()
    vals, flagged = [], []
    for c in REQUIRED + list(DERIVED):
        past = h[c].loc[: first - pd.DateOffset(months=1)].dropna()
        if past.empty or num[c].isna().all():
            continue
        r = np.log(past).diff().dropna()
        prev = past.iloc[-1]
        for t, v in num[c].dropna().items():
            ch = np.log(v / prev)
            z = ch / r.std()
            status = "warn" if abs(z) > JUMP_SD else "ok"
            if status == "warn":
                flagged.append(f"{c} {np.expm1(ch):+.0%}")
            vals.append({"series": c, "material": cat["material"].get(c, ""),
                         "unit": cat["unit"].get(c, "EUR/t"), "month": f"{t:%b %Y}",
                         "previous": prev, "new": v, "change": np.expm1(ch),
                         "largest change on file": np.expm1(r.abs().max()), "status": status})
            prev = v
    add(f"Monthly change within {JUMP_SD:.0f} standard deviations of the series' history",
        "warn" if flagged else "ok",
        ("unusual: " + ", ".join(flagged) + ". Check the unit and the decimal point.")
        if flagged else "")

    clean = num.copy()
    clean["year"], clean["month_num"] = clean.index.year, clean.index.month
    clean = clean[cols]
    return Check(f"{months[-1]:%Y-%m}", [f"{x:%Y-%m}" for x in months],
                 pd.DataFrame(rows, columns=["rule", "status", "detail"]),
                 pd.DataFrame(vals), clean)


# ---------------------------------------------------------------- runs
COPY = ["src", "configs", "report", "plots", "submissions", "pyproject.toml"]
SKIP_DATA = {"processed", "external"}   # rebuilt by the pipeline; raw downloads are linked


def start_run(c: Check) -> str:
    """Copy the repo, add the update file, start the pipeline in the background."""
    assert c.ok and c.clean is not None
    name = f"{c.month}_{time.strftime('%Y%m%d-%H%M%S')}"
    run = RUNS / name
    run.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", ".DS_Store")
    for item in COPY:
        src = REPO_ROOT / item
        if src.is_dir():
            shutil.copytree(src, run / item, ignore=ignore)
        elif src.exists():
            shutil.copy2(src, run / item)
    data = run / "Data"
    data.mkdir()
    for p in (REPO_ROOT / "Data").iterdir():
        if p.name in SKIP_DATA or p.name == "updates" or p.name.startswith("."):
            continue
        (shutil.copytree if p.is_dir() else shutil.copy2)(p, data / p.name)
    ext = data / "external"
    ext.mkdir()
    for p in (REPO_ROOT / "Data" / "external").iterdir():
        if p.name == "raw":
            (ext / "raw").symlink_to(p)      # cached downloads, read only
        elif p.is_file():
            shutil.copy2(p, ext / p.name)
    (data / "updates").mkdir()
    out = c.clean.reset_index()
    out["month"] = out["month"].dt.strftime("%Y-%m-%d")
    out.to_csv(data / "updates" / f"rm_prices_{c.month}.csv", index=False)

    env = {**os.environ, "SE_ORIGIN": c.month, "PYTHONUNBUFFERED": "1"}
    with open(run / "pipeline.log", "w") as log:   # the child keeps its own handle
        proc = subprocess.Popen([sys.executable, "-m", "src.pipeline"], cwd=run, env=env,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    (run / "run.json").write_text(json.dumps({
        "month": c.month, "months": c.months, "replaces": c.replaces,
        "started": time.strftime("%Y-%m-%d %H:%M"), "pid": proc.pid}))
    return name


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:   # a finished child stays a zombie until reaped
        return os.waitpid(pid, os.WNOHANG) == (0, 0)
    except ChildProcessError:
        return True


def run_info(name: str) -> dict:
    run = RUNS / name
    info = json.loads((run / "run.json").read_text())
    log = (run / "pipeline.log").read_text(errors="replace") if (run / "pipeline.log").exists() else ""
    if "Pipeline finished" in log:
        status = "done"
    elif "Pipeline stopped" in log or "Traceback" in log and not _alive(info["pid"]):
        status = "failed"
    elif _alive(info["pid"]):
        status = "running"
    else:
        status = "failed"
    stages = [ln.split("=== ")[1].split(" (")[0] for ln in log.splitlines()
              if ln.startswith("=== ") and " done in " not in ln]
    done = [ln.split("=== ")[1].split(" done")[0] for ln in log.splitlines() if " done in " in ln]
    sub = run / "submissions" / f"group_6_forecast_{info['month'].replace('-', '')}.csv"
    return {**info, "name": name, "root": str(run), "status": status, "log": log,
            "stages_started": stages, "stages_done": done,
            "csv": str(sub) if sub.exists() else None}


def runs() -> list[dict]:
    if not RUNS.exists():
        return []
    names = sorted((p.name for p in RUNS.iterdir() if (p / "run.json").exists()), reverse=True)
    return [run_info(n) for n in names]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", nargs="?", help="new month(s), client wide or long format")
    ap.add_argument("--check", action="store_true", help="check the file only")
    ap.add_argument("--held-back", metavar="YYYY-MM", help="write that month as a test file")
    a = ap.parse_args()
    if a.held_back:
        out = REPO_ROOT / f"rm_prices_{a.held_back}.csv"
        out.write_bytes(held_back_file(a.held_back))
        print(f"wrote {out}")
        return
    if not a.file:
        ap.error("give a file, or --held-back YYYY-MM")
    with open(a.file, "rb") as f:
        c = check(read_upload(f.read()))
    print(c.rows.to_string(index=False))
    if not c.ok:
        sys.exit("\nThe file does not pass the checks: nothing was run.")
    if a.check:
        return
    name = start_run(c)
    print(f"\nrunning the pipeline as of {c.month} in runs/{name}/ (log: pipeline.log)")
    while (info := run_info(name))["status"] == "running":
        time.sleep(5)
    print(info["log"][-1500:])
    print(f"\n{info['status']}: {info['csv'] or 'no CSV'}")


if __name__ == "__main__":
    main()
