# Problem 2 – market evidence and the pricing / TCO model

All Step 1 research lives in [`market_evidence/`](../../market_evidence/) as CSV files. [`src/market_evidence.py`](../../src/market_evidence.py) loads them, checks them, and turns them into the per-country pricing / lifetime-cost numbers.

## Files

| File | One row per | Key columns | Topic (report section) |
|---|---|---|---|
| `evidence.csv` | sourced fact | `id, fact, value, unit, region, source, url, publication_date, accessed, reliability, used_in` | All topics |
| `regulation.csv` | country / US state | `status_min, status_max` (0–3), `mv_new_ban_year`, `sf6_rules_in_force` (an SF6-specific rule already applies: ban, levy, leak cap or reporting), `sf6_pricing`, `compliance_carbon_price_eur_t` | Regulation (01 §5); carbon prices (§6) |
| `markets.csv` | country (same ids as `regulation.csv`) | `dc_relevance`, `dc_capacity_operational_mw`, `dc_capacity_under_construction_mw`, `dc_capacity_planned_mw`, `dc_growth_pct_per_year`, `schneider_presence` | Data-centre markets (01 §8) |
| `customers.csv` | customer (data-centre operator or utility) | `type`, `net_zero_year`, `scope1_target`, `internal_carbon_price_eur_t`, `mentions_sf6`, `sf6_policy_scope`, `sf6_free_projects_outside_eu` | Customer commitments (01 §7); carbon prices (§6) |
| `competitors.csv` | competitor | `sf6_free_products`, `technology_family`, `voltage_max_kv`, `in_scope_mv`, `sells_sf6_in_parallel`, premiums; where it is present as country lists: `sf6_free_sold_in`, `sf6_still_sold_in`, `local_plants_in` (e.g. `AE;SA;IN`, ids from `regulation.csv`) | Competitors (01 §9) |
| `assumptions.csv` | model parameter | `pessimistic, base, optimistic` (named from AirSeT's point of view) | SF6 lifecycle facts (01 §4); carbon prices (§6) |

Every table except `evidence.csv` ends with `evidence_ids, verified, notes`.

## How to add a fact

1. **Add a row to `evidence.csv`** with the next free id (`E46`, `E47`, …), the source, its link, the publication date, the date you read it, and its reliability:
   - **High:** official or primary source (law, regulator, IPCC, company's own report).
   - **Medium:** reputable secondary source, or Schneider data.
   - **Low:** estimate, vendor or trader blog, single unverified source.
   - **To verify:** found but not read yet.
2. **Put the value in the table it belongs to**, and add the id to that row's `evidence_ids` (separate several with `;`). Every row that holds a value must cite at least one source: the loader refuses rows with values but no `evidence_ids`. No value is a placeholder or a team guess: if a value cannot be sourced yet, leave the cell empty. When a better source replaces a weaker one, **keep the old evidence row and its id in `evidence_ids`** (mark it "superseded by …"); never delete a source.
3. **Set `verified=True`** only when the row is settled. The loader refuses `verified=True` unless at least one cited source is High or Medium, and refuses ids that are not in `evidence.csv`.
4. **Run** `uv run python src/market_evidence.py --write-report` from the repo root. It validates everything, re-checks the framing's €54/t break-even, refreshes the generated tables in [`01_market_and_regulation.md`](01_market_and_regulation.md), and prints the per-country tables. Never edit the tables between `<!-- BEGIN -->` / `<!-- END -->` markers by hand.
5. `uv run pytest tests/test_market_evidence.py` checks the rules.

`compliance_carbon_price_eur_t` holds the price of the jurisdiction's main carbon pricing scheme, whether or not it reaches a data centre; the model uses it only where `sf6_pricing` = priced. Allowed values: `sf6_pricing` = none / reporting / priced / unknown (from the **data-centre customer's** side: a carbon price that exists but does not reach a data centre is `none`); `mentions_sf6` = yes / no / unknown; `sf6_policy_scope` = worldwide / eu_only / none / unknown; `schneider_presence` = high / medium / low / unknown; `type` = hyperscaler / colocation / utility / industrial / enterprise / other. Use a range (`status_min` < `status_max`) while the evidence cannot decide: pessimistic uses the low end, optimistic the high end.

## Main calls

| Call | Returns | Used for |
|---|---|---|
| `p2.pricing_table(scenario)` | one row per market: group, regulatory score, data-centre relevance, carbon price, lifecycle value (leaks, end of life, regulation risk), premium, **headroom**, **required discount**, break-even carbon price, competitive pressure | Steps 3, 4, 7 |
| `p2.customer_value(country, scenario)` | PV breakdown of what the customer avoids by buying AirSeT (EUR / unit) | Step 4 TCO |
| `p2.break_even_carbon_price(country, scenario)` | EUR / t at which lifecycle value = premium | Step 4 chart |
| `p2.scenario_table(country)` | the three scenarios side by side | sensitivity slide |
| `p2.market_group(country)` | `regulation_coming` / `leaks_cost_money` / `nothing_forces` / `reference` / `unknown` | value proposition per group (Step 6) |
| `p2.evidence_for(table, key)` | the evidence rows behind one row | citing a fact on a slide |
| `p2.reliability(evidence_ids)` | the best reliability among the cited sources | report tables |
| `p2.unverified_report()` | every row not yet verified, with what to check | before any slide |

## Hooking in Problem 1

`required_discount_pct` is in points of RM6 price, the same unit as the Problem 1 margin points. The pricing rule is:
`max discount = AirSeT margin − Problem 1 risk buffer − margin floor`. If `required_discount_pct` is above that, the market cannot be won on TCO alone at an acceptable margin: it needs ESG value, steel indexation (to shrink the buffer) or a lower premium.
