"""Problem 2 market evidence: regulation, markets, customers, competition and
lifecycle assumptions, plus the AirSeT pricing / TCO calculator built on them.

Data lives in <repo>/market_evidence as CSV so the team can edit it without touching code:
    evidence.csv             one row per sourced fact (id, value, source, url, dates, reliability)
    regulation.csv           one row per country / US state: SF6 rules, carbon pricing
    markets.csv              one row per country: data-centre market size and growth
    customers.csv            one row per data-centre operator: climate targets, SF6 policy
    competitors.csv          one row per competitor: SF6-free MV offer, and the countries
                             where it sells SF6-free / still sells SF6 / has a plant
    assumptions.csv          lifecycle + pricing parameters, 3 scenarios

Every table row cites its sources in `evidence_ids` (e.g. "E19;E21"); the
source, link, date and reliability live only in evidence.csv. A row may be
`verified=True` only if at least one cited evidence row is High or Medium
reliability; `validate()` refuses to load otherwise, and also rejects ids that
do not exist in evidence.csv.

Scenarios are named from AirSeT's point of view:
    "pessimistic" = assumptions that make the switch look least attractive
    "base"
    "optimistic"  = assumptions that make the switch look most attractive

All money is EUR per unit (one RM6 vs one RM AirSeT).

Usage:
    from src.market_evidence import MarketEvidence
    p2 = MarketEvidence.load()                  # reads <repo>/market_evidence
    p2.pricing_table("base")                    # per-country value vs price gap
    p2.customer_value("SG", "optimistic")       # breakdown for one market
    p2.evidence_for("regulation", "US-CA")      # the sources behind a row

Command line (from the repo root):
    uv run python src/market_evidence.py                 # validate + print the tables
    uv run python src/market_evidence.py --write-report  # refresh the generated report tables
"""
from __future__ import annotations

import argparse
import dataclasses
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "market_evidence"
REPORT = ROOT / "report" / "problem2" / "01_market_and_regulation.md"
SCENARIOS = ("pessimistic", "base", "optimistic")
RELIABILITY = ("high", "medium", "low", "to verify")  # best first
EVIDENCE_OK = {"high", "medium"}                      # can back verified=True
SF6_PRICING = {"none", "reporting", "priced", "unknown"}
ALLOWED = {
    ("customers", "type"): {"hyperscaler", "colocation", "utility", "industrial", "enterprise", "other"},
    ("customers", "mentions_sf6"): {"yes", "no", "unknown"},
    ("customers", "sf6_policy_scope"): {"worldwide", "eu_only", "none", "unknown"},
    ("markets", "dc_relevance"): {"high", "medium", "low", "reference", ""},
    ("markets", "schneider_presence"): {"high", "medium", "low", "unknown"},
}
GROUPS = {
    "reference": "Regulated (status 3): reference market, not voluntary",
    "regulation_coming": "Regulation is coming: sell future-proofing",
    "sf6_rules_apply": "SF6 rules short of a ban already apply (levy, leak cap, reporting): sell no SF6 paperwork",
    "leaks_cost_money": "SF6 already priced: sell TCO",
    "nothing_forces": "Nothing forces it: sell customer ESG and risk",
    "unknown": "Status not researched yet",
}
TABLES = ("regulation", "markets", "customers", "competitors", "assumptions")
# competitors.csv columns holding ';'-separated country ids
COUNTRY_LISTS = ["sf6_free_sold_in", "sf6_still_sold_in", "local_plants_in"]
# countries outside our scope that may appear in those lists (ISO codes)
OTHER_COUNTRIES = {"TH", "ZA", "VN", "NZ", "FI", "DE", "FR", "ES", "IT", "NL", "CH"}
# labels that identify a row and need no source (everything else is a researched value)
ID_COLUMNS = {"regulation": ("country", "region"),
              "customers": ("company", "type", "hq_country"),
              "competitors": ("competitor",),
              "assumptions": ("unit",)}


def _bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().map({"true": True, "false": False})


def _ids(cell) -> list[str]:
    return [] if pd.isna(cell) else [x.strip() for x in str(cell).split(";") if x.strip()]


@dataclass
class MarketEvidence:
    regulation: pd.DataFrame
    competitors: pd.DataFrame
    assumptions: pd.DataFrame
    evidence: pd.DataFrame
    markets: pd.DataFrame
    customers: pd.DataFrame

    # ------------------------------------------------------------------ load
    @classmethod
    def load(cls, data_dir: str | Path = DATA_DIR) -> MarketEvidence:
        d = Path(data_dir)
        reg = pd.read_csv(d / "regulation.csv", dtype={"country_id": str, "evidence_ids": str})
        comp = pd.read_csv(d / "competitors.csv", dtype={"evidence_ids": str})
        ass = pd.read_csv(d / "assumptions.csv", dtype={"evidence_ids": str}).set_index("param")
        mkt = pd.read_csv(d / "markets.csv", dtype={"country_id": str, "evidence_ids": str,
                                                    "dc_relevance": str, "schneider_presence": str})
        cus = pd.read_csv(d / "customers.csv", dtype=str)
        ev = pd.read_csv(d / "evidence.csv", dtype=str)

        for df in (reg, comp, ass, mkt, cus):
            df["verified"] = _bool(df["verified"])
        reg["sf6_rules_in_force"] = _bool(reg["sf6_rules_in_force"])
        comp["in_scope_mv"] = _bool(comp["in_scope_mv"])
        for c in ("net_zero_year", "internal_carbon_price_eur_t"):
            cus[c] = pd.to_numeric(cus[c], errors="coerce")
        for df, cols in ((mkt, ("dc_relevance", "schneider_presence")),
                         (cus, ("type", "mentions_sf6", "sf6_policy_scope"))):
            for c in cols:
                df[c] = df[c].fillna("").str.strip().str.lower()

        obj = cls(reg.set_index("country_id"), comp.set_index("competitor_id"), ass,
                  ev.set_index("id", drop=False), mkt.set_index("country_id"),
                  cus.set_index("customer_id"))
        obj.validate()
        return obj

    def validate(self) -> None:
        r, errs = self.regulation, []
        for col in ("status_min", "status_max"):
            bad = r[col].dropna()
            bad = bad[~bad.isin([0, 1, 2, 3])]
            if len(bad):
                errs.append(f"regulation: {col} outside 0-3: {list(bad.index)}")
        both = r[["status_min", "status_max"]].dropna()
        if (both.status_min > both.status_max).any():
            errs.append("regulation: status_min > status_max for "
                        f"{list(both[both.status_min > both.status_max].index)}")
        bad = set(r["sf6_pricing"].dropna()) - SF6_PRICING
        if bad:
            errs.append(f"regulation: unknown sf6_pricing values {bad}")
        if set(self.markets.index) - set(r.index):
            errs.append(f"markets: countries not in regulation.csv: {set(self.markets.index) - set(r.index)}")
        if set(r.index) - set(self.markets.index):
            errs.append(f"markets.csv is missing countries: {set(r.index) - set(self.markets.index)}")
        for col in COUNTRY_LISTS:
            bad = {c for cell in self.competitors[col] for c in _ids(cell)} - set(r.index) - OTHER_COUNTRIES
            if bad:
                errs.append(f"competitors: {col} has unknown country ids {sorted(bad)} "
                            "(use regulation.csv ids, or add to OTHER_COUNTRIES)")
        for (table, col), allowed in ALLOWED.items():
            bad = set(getattr(self, table)[col]) - allowed
            if bad:
                errs.append(f"{table}: {col} must be one of {sorted(allowed)}, got {bad}")
        for s in SCENARIOS:
            if self.assumptions[s].isna().any():
                errs.append(f"assumptions: empty values in '{s}'")
        ev = self.evidence
        dup = ev.id[ev.id.duplicated()]
        if len(dup):
            errs.append(f"evidence: duplicate ids {list(dup)}")
        bad = set(ev.reliability.fillna("").str.strip().str.lower()) - set(RELIABILITY)
        if bad:
            errs.append(f"evidence: reliability must be one of {RELIABILITY}, got {bad}")
        errs += self._check_evidence_links()
        if errs:
            raise ValueError("Problem 2 data errors:\n- " + "\n- ".join(errs))

    def _tables(self):
        yield from ((t, getattr(self, t)) for t in TABLES)

    def _check_evidence_links(self) -> list[str]:
        """Every cited id must exist; every row holding a value must cite a
        source; verified=True needs a High / Medium source."""
        errs, known = [], set(self.evidence.index)
        for table, df in self._tables():
            unknown = {i for cell in df.evidence_ids for i in _ids(cell)} - known
            if unknown:
                errs.append(f"{table}: evidence_ids not in evidence.csv: {sorted(unknown)}")
            unsourced = [k for k, row in df.iterrows() if self._has_value(table, row)
                         and not _ids(row.evidence_ids)]
            if unsourced:
                errs.append(f"{table}: rows with values but no evidence_ids: {unsourced}")
            if "verified" not in df:
                continue
            unbacked = [k for k, row in df[df.verified.fillna(False)].iterrows()
                        if self.reliability(row.evidence_ids) not in EVIDENCE_OK]
            if unbacked:
                errs.append(f"{table}: verified=True without a High/Medium source in "
                            f"evidence_ids: {unbacked}")
        return errs

    @staticmethod
    def _has_value(table: str, row: pd.Series) -> bool:
        """True if the row holds a researched value (not just its name / labels)."""
        skip = {"evidence_ids", "verified", "notes", "country_id", "competitor_id",
                "customer_id", *ID_COLUMNS.get(table, ())}
        return any(pd.notna(v) and str(v).strip().lower() not in ("", "unknown", "nan")
                   for c, v in row.items() if c not in skip)

    # -------------------------------------------------------------- evidence
    def reliability(self, evidence_ids) -> str:
        """Best reliability among the cited evidence rows ('' if none)."""
        levels = [str(self.evidence.loc[i, "reliability"]).strip().lower()
                  for i in _ids(evidence_ids) if i in self.evidence.index]
        return min(levels, key=RELIABILITY.index) if levels else ""

    def evidence_for(self, table: str, key: str) -> pd.DataFrame:
        """The evidence rows cited by one row of a table."""
        row = getattr(self, table).loc[key]
        return self.evidence.loc[[i for i in _ids(row.evidence_ids) if i in self.evidence.index]]

    def unverified_report(self) -> pd.DataFrame:
        """Everything not yet backed by a checked source."""
        rows = [(t, k, r.notes) for t, df in self._tables() if "verified" in df
                for k, r in df[~df.verified.fillna(False)].iterrows()]
        return pd.DataFrame(rows, columns=["table", "id", "what_to_check"])

    # ------------------------------------------------------------ parameters
    def param(self, name: str, scenario: str = "base") -> float:
        if scenario not in SCENARIOS:
            raise ValueError(f"scenario must be one of {SCENARIOS}")
        return float(self.assumptions.loc[name, scenario])

    # ------------------------------------------------------------ regulation
    def market_group(self, country_id: str) -> str:
        r = self.regulation.loc[country_id]
        if pd.isna(r.status_max):
            return "unknown"
        if r.status_min >= 3:
            return "reference"
        if r.status_max >= 1 and r.sf6_rules_in_force and r.status_max < 2:
            return "sf6_rules_apply"
        if r.status_max >= 1 and r.sf6_pricing != "priced":
            return "regulation_coming"
        if r.sf6_pricing == "priced":
            return "leaks_cost_money"
        return "nothing_forces"

    def regulatory_score(self, country_id: str) -> float:
        """Step 3 criterion 'regulatory trajectory', 0-3 (status 3 -> NaN,
        out of voluntary scope). Uses the midpoint of the status range."""
        r = self.regulation.loc[country_id]
        if pd.isna(r.status_max) or r.status_min >= 3:
            return np.nan
        mid = (r.status_min + r.status_max) / 2
        bonus = 0.5 if r.sf6_pricing in ("priced", "reporting") else 0.0
        return float(min(3.0, mid + 1 + bonus)) if mid > 0 else 0.5 + bonus

    def regulation_probability(self, country_id: str, scenario: str = "base") -> float:
        """1 if an SF6 rule is adopted or in force (status >= 2) in this
        scenario, else 0: only adopted rules are counted, nothing is guessed.
        Pessimistic uses status_min, optimistic status_max, base the midpoint.
        Multiplied by regulation_cost_if_hit_eur, the sourced cost such a rule
        imposes on an installed RM6 (EUR 0 today: E61)."""
        r = self.regulation.loc[country_id]
        if pd.isna(r.status_max):
            return np.nan
        status = {"pessimistic": r.status_min, "optimistic": r.status_max,
                  "base": (r.status_min + r.status_max) / 2}[scenario]
        return 1.0 if status >= 2 else 0.0

    def carbon_price(self, country_id: str, scenario: str = "base") -> float:
        """Carbon price the customer applies to SF6: the compliance price where
        one covers SF6, otherwise (or if higher) the internal carbon price."""
        r = self.regulation.loc[country_id]
        internal = self.param("internal_carbon_price_eur_t", scenario)
        compliance = r.compliance_carbon_price_eur_t
        if r.sf6_pricing == "priced" and pd.notna(compliance):
            return float(max(compliance, internal))
        return internal

    # ------------------------------------------------------------ economics
    def _pv_factors(self, scenario: str) -> tuple[float, float, float]:
        r = self.param("discount_rate_pct", scenario) / 100
        life = self.param("asset_life_years", scenario)
        annuity = life if r == 0 else (1 - (1 + r) ** -life) / r
        return annuity, (1 + r) ** -life, (1 + r) ** -(life / 2)

    def customer_value(self, country_id: str, scenario: str = "base",
                       carbon_price: float | None = None) -> dict:
        """PV of what the customer avoids by buying AirSeT instead of RM6,
        EUR per unit. This is the most the customer should rationally pay
        as a premium (before ESG / reputation value)."""
        p = lambda n: self.param(n, scenario)
        cp = self.carbon_price(country_id, scenario) if carbon_price is None else carbon_price
        annuity, df_end, df_mid = self._pv_factors(scenario)
        t_co2e_fill = p("sf6_kg_per_unit") * p("gwp_sf6") / 1000

        leak_t_per_year = t_co2e_fill * p("leak_rate_pct_per_year") / 100
        leak_pv = leak_t_per_year * cp * annuity
        eol_pv = (p("eol_recovery_cost_eur")
                  + t_co2e_fill * p("eol_release_share") * cp) * df_end
        prob = self.regulation_probability(country_id, scenario)
        reg_pv = (0.0 if np.isnan(prob) else prob) * p("regulation_cost_if_hit_eur") * df_mid

        return {
            "carbon_price_eur_t": cp,
            "sf6_fill_t_co2e": t_co2e_fill,
            "leak_carbon_pv": leak_pv,
            "end_of_life_pv": eol_pv,
            "regulation_risk_pv": reg_pv,
            "regulation_prob": prob,
            "total_value_pv": leak_pv + eol_pv + reg_pv,
        }

    def price_premium_eur(self, scenario: str = "base") -> float:
        return self.param("price_premium_pct", scenario) / 100 * self.param("rm6_price_eur", scenario)

    def break_even_carbon_price(self, country_id: str, scenario: str = "base") -> float:
        """Carbon price (EUR/t) at which customer value = upfront premium.
        Value is linear in the carbon price, so solve directly."""
        v0 = self.customer_value(country_id, scenario, carbon_price=0)["total_value_pv"]
        v1 = self.customer_value(country_id, scenario, carbon_price=1)["total_value_pv"]
        slope = v1 - v0
        return (self.price_premium_eur(scenario) - v0) / slope if slope > 0 else np.inf

    # ------------------------------------------------------------ competition
    def competitive_pressure(self, country_id: str) -> dict:
        """Rivals (MV, excluding Schneider) present in one country, counted from
        the country lists in competitors.csv."""
        rivals = self.competitors[self.competitors.in_scope_mv.fillna(False).astype(bool)]
        rivals = rivals.drop(index="schneider", errors="ignore")
        has = {col: rivals[col].map(lambda cell: country_id in _ids(cell)) for col in COUNTRY_LISTS}
        researched = rivals[COUNTRY_LISTS].notna().any(axis=1)
        return {
            "sf6_free_rivals": int(has["sf6_free_sold_in"].sum()),
            "rivals_still_selling_sf6": int(has["sf6_still_sold_in"].sum()),
            "local_plants": int(has["local_plants_in"].sum()),
            "competitors_not_researched": int((~researched).sum()),
        }

    # ------------------------------------------------------------ outputs
    def pricing_table(self, scenario: str = "base", in_scope_only: bool = True) -> pd.DataFrame:
        """One row per country: the inputs the pricing plan needs.

        headroom_eur > 0  -> lifecycle value covers the premium: AirSeT can be
                             sold at the current premium on TCO alone.
        required_discount_pct -> discount (points of RM6 price) needed so
                             that lifecycle value covers the premium. Check
                             it against the Problem 1 margin floor.
        """
        premium = self.price_premium_eur(scenario)
        rm6 = self.param("rm6_price_eur", scenario)
        rows = []
        for cid, r in self.regulation.iterrows():
            group = self.market_group(cid)
            if in_scope_only and group == "reference":
                continue
            v = self.customer_value(cid, scenario)
            rows.append({
                "country_id": cid, "country": r.country, "region": r.region,
                "group": group, "status_range": (f"{r.status_min:.0f}-{r.status_max:.0f}"
                                                 if pd.notna(r.status_max) else "?"),
                "regulatory_score": self.regulatory_score(cid),
                "dc_relevance": self.markets.loc[cid, "dc_relevance"],
                **{k: v[k] for k in ("carbon_price_eur_t", "regulation_prob",
                                     "leak_carbon_pv", "end_of_life_pv",
                                     "regulation_risk_pv", "total_value_pv")},
                "premium_eur": premium,
                "headroom_eur": v["total_value_pv"] - premium,
                "required_discount_pct": max(0.0, premium - v["total_value_pv"]) / rm6 * 100,
                "break_even_carbon_eur_t": self.break_even_carbon_price(cid, scenario),
                **self.competitive_pressure(cid),
                "verified": bool(r.verified),
            })
        return pd.DataFrame(rows).set_index("country_id")

    def scenario_table(self, country_id: str) -> pd.DataFrame:
        """The three scenarios side by side for one market (sensitivity)."""
        out = {}
        for s in SCENARIOS:
            v = self.customer_value(country_id, s)
            v["premium_eur"] = self.price_premium_eur(s)
            v["headroom_eur"] = v["total_value_pv"] - v["premium_eur"]
            v["break_even_carbon_eur_t"] = self.break_even_carbon_price(country_id, s)
            out[s] = v
        return pd.DataFrame(out)

    # ------------------------------------------------------------ landscape (Step 2)
    def landscape(self) -> pd.DataFrame:
        """One row per jurisdiction joining regulation, market size and rivals:
        the Step 2 landscape and the raw input of the Step 3 scoring.
        US-FED holds the sum of all tracked US markets, so it overlaps the
        US state rows: drop it (or the states) before summing MW."""
        rows = []
        for cid, r in self.regulation.iterrows():
            m = self.markets.loc[cid]
            op = pd.to_numeric(m.dc_capacity_operational_mw, errors="coerce")
            uc = pd.to_numeric(m.dc_capacity_under_construction_mw, errors="coerce")
            rivals = self.competitive_pressure(cid)
            rows.append({
                "country_id": cid, "country": r.country, "region": r.region,
                "status": r.status_max, "status_range": (f"{r.status_min:.0f}-{r.status_max:.0f}"
                                                         if pd.notna(r.status_max) else "?"),
                "group": self.market_group(cid), "sf6_pricing": r.sf6_pricing,
                "dc_mw": (0 if pd.isna(op) else op) + (0 if pd.isna(uc) else uc) if pd.notna(op) else np.nan,
                "dc_growth_pct": pd.to_numeric(m.dc_growth_pct_per_year, errors="coerce"),
                "dc_relevance": m.dc_relevance or "",
                "sf6_free_rivals": rivals["sf6_free_rivals"], "local_plants": rivals["local_plants"],
            })
        return pd.DataFrame(rows).set_index("country_id")

    # ------------------------------------------------------------ report tables
    def _cite(self, row) -> str:
        ids = ", ".join(_ids(row.evidence_ids)) or "–"
        rel = self.reliability(row.evidence_ids).capitalize() or "No source"
        return f"{ids} | {rel}{'' if row.verified else ' · not verified'}"

    def regulation_markdown(self) -> str:
        priced = {"priced": "Yes", "none": "No", "reporting": "Reporting only", "unknown": "?"}
        lines = [("| Country / region | Status (0–3) | MV ban year | SF6 priced for a data centre? "
                 "| What the evidence says | Evidence | Reliability |"),
                 "|---|---|---|---|---|---|---|"]
        for cid, x in self.regulation.iterrows():
            if pd.isna(x.status_max):
                st = "?"
            elif x.status_min == x.status_max:
                st = f"{x.status_min:.0f}"
            else:
                st = f"{x.status_min:.0f}–{x.status_max:.0f}"
            year = "–" if pd.isna(x.mv_new_ban_year) else f"{x.mv_new_ban_year:.0f}"
            note = "" if pd.isna(x.notes) else str(x.notes).replace("|", "/")
            lines.append(f"| {x.country} | **{st}** | {year} | {priced.get(x.sf6_pricing, '?')} "
                         f"| {note} | {self._cite(x)} |")
        return "\n".join(lines)

    def competitors_markdown(self) -> str:
        lines = [("| Competitor | SF6-free MV products | Technology | Max kV | Competes with RM AirSeT? "
                 "| What the evidence says | Evidence | Reliability |"),
                 "|---|---|---|---|---|---|---|---|"]
        for _, x in self.competitors.iterrows():
            scope = {True: "Yes", False: "No (HV)"}.get(x.in_scope_mv, "?")
            kv = "–" if pd.isna(x.voltage_max_kv) else f"{x.voltage_max_kv:.0f}"
            cell = lambda v: "–" if pd.isna(v) else str(v).replace("_", " ").replace("|", "/")
            lines.append(f"| **{x.competitor}** | {cell(x.sf6_free_products)} | "
                         f"{cell(x.technology_family)} | {kv} | {scope} | {cell(x.notes)} | {self._cite(x)} |")
        return "\n".join(lines)

    def write_report_tables(self, path: Path = REPORT) -> None:
        """Replace the text between <!-- BEGIN:name --> and <!-- END:name --> markers."""
        text = path.read_text()
        for name, table in (("regulation", self.regulation_markdown()),
                            ("competitors", self.competitors_markdown())):
            pattern = re.compile(rf"(<!-- BEGIN:{name} -->\n).*?(\n<!-- END:{name} -->)", re.DOTALL)
            if not pattern.search(text):
                raise ValueError(f"markers for '{name}' not found in {path}")
            text = pattern.sub(lambda m, t=table: m.group(1) + t + m.group(2), text)
        path.write_text(text)


# ---------------------------------------------------------------- self-check
def _sanity_check(p2: MarketEvidence) -> None:
    """Reproduce the framing note: valuing the full SF6 fill (1.5 kg x 23,500
    = 35.25 t CO2e) with no leaks, no discounting and no other costs, the
    EUR 1,921 premium pays back at about EUR 54.5/t."""
    test = dataclasses.replace(p2, assumptions=p2.assumptions.copy())
    for k, v in {"leak_rate_pct_per_year": 0, "discount_rate_pct": 0,
                 "eol_recovery_cost_eur": 0, "eol_release_share": 1,
                 "regulation_cost_if_hit_eur": 0, "gwp_sf6": 23500,
                 "price_premium_pct": 1921 / 8740 * 100}.items():
        test.assumptions.loc[k, "base"] = v
    be = test.break_even_carbon_price("JP", "base")
    assert abs(be - 54.5) < 0.5, be


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write-report", action="store_true",
                    help="refresh the generated tables in 01_market_and_regulation.md")
    args = ap.parse_args()
    p2 = MarketEvidence.load()
    _sanity_check(p2)
    if args.write_report:
        p2.write_report_tables()
        print(f"Report tables refreshed in {REPORT.relative_to(ROOT)}")
    pd.set_option("display.width", 200, "display.max_columns", 30)
    cols = ["group", "status_range", "carbon_price_eur_t", "regulation_prob",
            "total_value_pv", "premium_eur", "headroom_eur",
            "required_discount_pct", "break_even_carbon_eur_t"]
    for s in SCENARIOS:
        print(f"\n=== {s} ===")
        print(p2.pricing_table(s)[cols].round(1))
    print("\n=== Singapore, all scenarios ===")
    print(p2.scenario_table("SG").round(2))
    print(f"\n{len(p2.unverified_report())} rows still unverified.")
