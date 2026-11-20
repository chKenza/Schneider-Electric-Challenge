"""Problem 2 inputs: regulation, competition and lifecycle assumptions for the
AirSeT pricing / TCO model.

Data lives in ./data as CSV so the team can edit it without touching code:
    regulation.csv           one row per country / US state
    competitors.csv          one row per competitor offer
    competitor_presence.csv  long format: country x competitor
    assumptions.csv          lifecycle + pricing parameters, 3 scenarios

Scenarios are named from AirSeT's point of view:
    "pessimistic" = assumptions that make the switch look least attractive
    "base"
    "optimistic"  = assumptions that make the switch look most attractive

All money is EUR per unit (one RM6 vs one RM AirSeT). Every row carries a
`verified` flag: run `unverified_report()` before using numbers on a slide.

Usage:
    from p2_inputs import P2Inputs
    p2 = P2Inputs.load("data")
    p2.pricing_table("base")              # per-country value vs price gap
    p2.customer_value("SG", "optimistic") # breakdown for one market
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

SCENARIOS = ("pessimistic", "base", "optimistic")
SF6_PRICING = {"none", "reporting", "priced", "unknown"}
GROUPS = {
    "reference": "Regulated (status 3): reference market, not voluntary",
    "regulation_coming": "Regulation is coming: sell future-proofing",
    "leaks_cost_money": "SF6 already priced: sell TCO",
    "nothing_forces": "Nothing forces it: sell customer ESG and risk",
    "unknown": "Status not researched yet",
}


def _bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().map({"true": True, "false": False})


@dataclass
class P2Inputs:
    regulation: pd.DataFrame
    competitors: pd.DataFrame
    presence: pd.DataFrame
    assumptions: pd.DataFrame

    # ------------------------------------------------------------------ load
    @classmethod
    def load(cls, data_dir: str | Path = "data") -> "P2Inputs":
        d = Path(data_dir)
        reg = pd.read_csv(d / "regulation.csv", dtype={"country_id": str})
        comp = pd.read_csv(d / "competitors.csv")
        pres = pd.read_csv(d / "competitor_presence.csv")
        ass = pd.read_csv(d / "assumptions.csv").set_index("param")

        reg["verified"] = _bool(reg["verified"])
        comp["verified"] = _bool(comp["verified"])
        comp["in_scope_mv"] = _bool(comp["in_scope_mv"])
        ass["verified"] = _bool(ass["verified"])
        for c in ("sf6_free_sold", "sf6_still_sold", "local_plant"):
            pres[c] = pres[c].astype(str).str.lower().map(
                {"true": True, "false": False}).astype("boolean")

        obj = cls(reg.set_index("country_id"), comp.set_index("competitor_id"),
                  pres, ass)
        obj.validate()
        return obj

    def validate(self) -> None:
        r = self.regulation
        errs = []
        for col in ("status_min", "status_max"):
            bad = r[col].dropna()
            bad = bad[~bad.isin([0, 1, 2, 3])]
            if len(bad):
                errs.append(f"{col} outside 0-3: {list(bad.index)}")
        both = r[["status_min", "status_max"]].dropna()
        if (both.status_min > both.status_max).any():
            errs.append("status_min > status_max for "
                        f"{list(both[both.status_min > both.status_max].index)}")
        bad = set(r["sf6_pricing"]) - SF6_PRICING
        if bad:
            errs.append(f"unknown sf6_pricing values: {bad}")
        missing = set(self.presence.country_id) - set(r.index)
        if missing:
            errs.append(f"presence countries not in regulation.csv: {missing}")
        missing = set(self.presence.competitor_id) - set(self.competitors.index)
        if missing:
            errs.append(f"presence competitors not in competitors.csv: {missing}")
        for s in SCENARIOS:
            if self.assumptions[s].isna().any():
                errs.append(f"assumptions: empty values in '{s}'")
        if errs:
            raise ValueError("Problem 2 data errors:\n- " + "\n- ".join(errs))

    # ------------------------------------------------------------ parameters
    def param(self, name: str, scenario: str = "base") -> float:
        if scenario not in SCENARIOS:
            raise ValueError(f"scenario must be one of {SCENARIOS}")
        return float(self.assumptions.loc[name, scenario])

    def unverified_report(self) -> pd.DataFrame:
        """Everything not yet backed by a checked source."""
        rows = []
        for cid, r in self.regulation[~self.regulation.verified].iterrows():
            rows.append(("regulation", cid, r.notes))
        for cid, r in self.competitors[~self.competitors.verified].iterrows():
            rows.append(("competitors", cid, r.notes))
        for p, r in self.assumptions[~self.assumptions.verified].iterrows():
            rows.append(("assumptions", p, r.source))
        return pd.DataFrame(rows, columns=["table", "id", "what_to_check"])

    # ------------------------------------------------------------ regulation
    def market_group(self, country_id: str) -> str:
        r = self.regulation.loc[country_id]
        if pd.isna(r.status_max):
            return "unknown"
        if r.status_min >= 3:
            return "reference"
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
        """Probability that a rule costly for installed SF6 arrives within the
        asset life. Pessimistic uses status_min, optimistic status_max, base
        interpolates between them."""
        r = self.regulation.loc[country_id]
        if pd.isna(r.status_max):
            return np.nan
        status = {"pessimistic": r.status_min, "optimistic": r.status_max,
                  "base": (r.status_min + r.status_max) / 2}[scenario]
        lo, hi = int(np.floor(status)), int(np.ceil(status))
        p_lo = self.param(f"reg_prob_status_{lo}", scenario)
        p_hi = self.param(f"reg_prob_status_{hi}", scenario)
        return p_lo + (p_hi - p_lo) * (status - lo)

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
        p = lambda n: self.param(n, scenario)  # noqa: E731
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
        in_scope = self.competitors[self.competitors.in_scope_mv].index.drop("schneider", errors="ignore")
        pres = self.presence[(self.presence.country_id == country_id)
                             & self.presence.competitor_id.isin(in_scope)]
        known = pres[pres.sf6_free_sold.notna() | pres.local_plant.notna()]
        return {
            "sf6_free_rivals": int(pres.sf6_free_sold.fillna(False).sum()),
            "local_plants": int(pres.local_plant.fillna(False).sum()),
            "rivals_still_selling_sf6": int(pres.sf6_still_sold.fillna(False).sum()),
            "competitors_not_researched": len(in_scope) - known.competitor_id.nunique(),
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
            cpres = self.competitive_pressure(cid)
            rows.append({
                "country_id": cid, "country": r.country, "region": r.region,
                "group": group, "status_range": (f"{r.status_min:.0f}-{r.status_max:.0f}"
                                                 if pd.notna(r.status_max) else "?"),
                "regulatory_score": self.regulatory_score(cid),
                "dc_relevance": r.dc_relevance,
                **{k: v[k] for k in ("carbon_price_eur_t", "regulation_prob",
                                     "leak_carbon_pv", "end_of_life_pv",
                                     "regulation_risk_pv", "total_value_pv")},
                "premium_eur": premium,
                "headroom_eur": v["total_value_pv"] - premium,
                "required_discount_pct": max(0.0, premium - v["total_value_pv"]) / rm6 * 100,
                "break_even_carbon_eur_t": self.break_even_carbon_price(cid, scenario),
                **cpres,
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


# ---------------------------------------------------------------- self-check
def _sanity_check(p2: P2Inputs) -> None:
    """Reproduce the framing note: valuing the full SF6 fill (1.5 kg x 22,800
    = 34.2 t CO2e) with no leaks, no discounting and no other costs, the
    EUR 1,921 premium pays back at about EUR 56/t."""
    a = p2.assumptions.copy()
    test = P2Inputs(p2.regulation, p2.competitors, p2.presence, a.copy())
    for k, v in {"leak_rate_pct_per_year": 0, "discount_rate_pct": 0,
                 "eol_recovery_cost_eur": 0, "eol_release_share": 1,
                 "regulation_cost_if_hit_eur": 0, "gwp_sf6": 22800,
                 "price_premium_pct": 1921 / 8740 * 100}.items():
        test.assumptions.loc[k, "base"] = v
    be = test.break_even_carbon_price("JP", "base")
    assert abs(be - 56.2) < 0.5, be


if __name__ == "__main__":
    here = Path(__file__).parent
    p2 = P2Inputs.load(here / "data")
    _sanity_check(p2)
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
