# Problem 2 – coded inputs for the pricing / TCO model

```
data/regulation.csv           country x SF6 rules (status 0-3 as a range, SF6 carbon pricing, data-centre relevance)
data/competitors.csv          competitor offers (technology, voltage, MV scope, premium, positioning, local plants)
data/competitor_presence.csv  country x competitor (SF6-free sold? SF6 still sold? local plant?) - mostly to fill
data/assumptions.csv          lifecycle + pricing parameters, 3 scenarios (pessimistic / base / optimistic for AirSeT)
p2_inputs.py                  loader, validation, and the functions the pricing model calls
```

Run `python p2_inputs.py`: it validates the CSVs, re-checks the framing note's €56/t break-even, and prints the per-country table for each scenario.

## Main calls

| Call | Returns | Used for |
|---|---|---|
| `p2.pricing_table(scenario)` | one row per market: group, regulatory score, carbon price, lifecycle value (leaks, end of life, regulation risk), premium, **headroom**, **required discount**, break-even carbon price, competitive pressure | Steps 3, 4, 7 |
| `p2.customer_value(country, scenario)` | PV breakdown of what the customer avoids by buying AirSeT (EUR / unit) | Step 4 TCO |
| `p2.break_even_carbon_price(country, scenario)` | EUR / t at which lifecycle value = premium | Step 4 chart |
| `p2.scenario_table(country)` | the three scenarios side by side | sensitivity slide |
| `p2.market_group(country)` | `regulation_coming` / `leaks_cost_money` / `nothing_forces` / `reference` / `unknown` | value proposition per group (Step 6) |
| `p2.unverified_report()` | every row without a checked source | before any slide |

## Hooking in Problem 1

`required_discount_pct` is in points of RM6 price, the same unit as the Problem 1 margin points. The pricing rule is:
`max discount = AirSeT margin − Problem 1 risk buffer − margin floor`. If `required_discount_pct` is above that, the market cannot be won on TCO alone at an acceptable margin: it needs ESG value, steel indexation (to shrink the buffer) or a lower premium.

## Editing rules

- Change numbers in the CSVs, not in the code. Set `verified=True` only once a primary source is in `source_url` / `source`.
- `status_min` / `status_max`: use a range while unsure. Pessimistic uses the min, optimistic the max.
- `sf6_pricing`: `none` / `reporting` / `priced` / `unknown`. Fill `compliance_carbon_price_eur_t` (EUR / t) only for `priced`.
- Every row marked PLACEHOLDER in `assumptions.csv` is a guess to replace with Step 1 research.
