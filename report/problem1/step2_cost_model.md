# Step 2 – Cost decomposition model

> **Update: ** `src/cost_model.py` uses the client's corrected BOM (`RM_Prices_XHEC_Challenge_v1.xlsx`, sheet `BOM_Materials`) instead of `bom_materials.csv`. There are two cases:
> - **RM6, €931:** copper 52 %, stainless 16 %, carbon steel 13 %, epoxy 12 %, brass 3 %
> - **AirSeT, €941:** copper 38 %, carbon steel 30 %, stainless 22 %, epoxy 8 %
>
> Their nickel-check variants are `RM6, nickel check` and `AirSeT, nickel check`. The old "epoxy low / high" cases and the "unlabelled slice = carbon steel" assumption are gone. Lines the client marks as unknown ("Other", "Unidentified remainder") and plastics stay unpriced (client rule: no invented compositions). Brass has no series: it is priced as 65 % LME copper + 35 % LME zinc, moving with copper. All tables below are on BOM v1.

*Owner: Karin*

> **Run (from the repo root, after Step 1):**
> ```
> uv run python -m src.data_prep
> uv run python -m src.cost_model
> ```
> Writes 4 files to `Data/processed/`:
>
> | File | What it holds |
> |---|---|
> | `cost_breakdown.csv` | kg, €/t and € per material at the origin (Sep 2026), per product case |
> | `cost_shocks.csv` | What a +10 % move in one material does to the unit cost |
> | `bom_index_history.csv` | Monthly BOM cost index per case (Sep 2026 = 100) |
> | `bom_index_changes.csv` | Past 3/6/9-month changes of that index (P10/P50/P90/max) |

---

## 1. The formula

```
cost_i(t) = kg_i × €/t_i(Sep 2026) / 1000 × driver_i(t) / driver_i(Sep 2026)
BOM cost index(t) = Σ cost_i(t) / Σ cost_i(Sep 2026) × 100
```

- **€/t level** fixes how much each material weighs in the cost.
- **Driver** is the forecast-target series that moves the price month to month.
- The index is weighted by **euros, not kg**: 39 kg of copper costs 4× more than 144 kg of steel.

## 2. Price series used

| Material | €/t level (Sep 2026) | Driver (forecast target) |
|---|---|---|
| Carbon steel, RM6 (France) | MEPS cold-rolled coil France, €830 | S09 steel PPI EU |
| Carbon steel, AirSeT (Hungary) | MEPS cold-rolled coil Germany, €825 | S09 |
| Galvanised steel | MEPS HDG Germany, €815 | S10 steel PPI Germany |
| Stainless 304 | CRU 304 Germany, base + surcharge, €2,728 (**Aug** – latest) | S09 |
| Copper | LME in EUR (D01), €12,571 | D01 |
| Aluminium | LME in EUR (D02), €2,852 | D02 |
| Epoxy | Epoxy file, €4,866 | EPOXY_EUR |
| Brass (RM6) | 65 % LME copper + 35 % LME zinc, €9,393 (proxy) | D01 |
| Plastics (PET, PP, PBT, ETP, PE, PVC) | **None – unpriced** | S11 (ready once a level exists) |
| Unknown lines ("Other", "Unidentified remainder") | **None – unpriced** (client: no invented composition) | – |

## 3. Masses (kg per unit) and where they come from

| Material | RM6 | AirSeT | Source |
|---|---|---|---|
| Carbon steel | 144.5 | 343.7 | BOM v1 |
| Stainless steel | 55.8 | 75.3 | BOM v1 |
| Copper | 38.75 | **28.46** | BOM v1 (the old BOM had no copper for AirSeT) |
| Galvanised steel | 21.1 | – | BOM v1 |
| Epoxy | **22.3** | **16.4** | BOM v1 (the old cases were 1.6 kg for RM6 and 3.9 / 85.6 kg for AirSeT) |
| Aluminium | 5.0 | 4.9 | BOM v1 |
| Brass | 3.4 | – | BOM v1, priced as 65 % Cu + 35 % Zn |
| Plastics | 13.6 | 21.2 | BOM v1 (unpriced) |
| Unknown | 5.6 | 56.0 | BOM v1 "Unidentified remainder" / "Other" (unpriced) |
| **Total** | **310** | **547** | |

Source: client BOM v1, `RM_Prices_XHEC_Challenge_v1.xlsx`, sheet `BOM_Materials` (received 20 Nov 2026). It replaces `bom_materials.csv` and the RM6 PEP figures.

## 4. Results: raw-material cost of one unit (Sep 2026)

| | RM6 | AirSeT |
|---|---|---|
| **Total (priced materials)** | **€931** | **€941** |
| Biggest share | Copper 52 %, stainless 16 %, carbon steel 13 %, epoxy 12 % | Copper 38 %, carbon steel 30 %, stainless 22 %, epoxy 8 % |

**What +10 % on one material does to the unit cost** (index points = % of raw-material cost):

| Material +10 % | RM6 | AirSeT |
|---|---|---|
| Copper (+ brass for RM6) | **+5.6 pts (€52)** | **+3.8 pts (€36)** |
| Carbon steel | +1.3 (€12) | +3.0 (€28) |
| Stainless | +1.6 (€15) | +2.2 (€21) |
| Epoxy | +1.2 (€11) | +0.8 (€8) |
| Galvanised, aluminium | ≤ 0.2 each | ≤ 0.2 |

> **The two products now cost about the same in raw materials** (€931 vs €941: AirSeT is €9 more). AirSeT's figure is still a floor: ≈ 14 % of its mass (56 kg "Other" + 21 kg plastics) is unpriced, against ≈ 6 % for RM6.

- **RM6 is a copper bet.** Copper and brass make up 56 % of its raw-material cost; a +10 % copper move costs €52 per unit, 3× more than any other material.
- **AirSeT is a copper + steel bet.** Copper is still its largest single material (38 %), but carbon steel and stainless together weigh more (52 %), so its risk is spread across copper, steel and nickel.

## 5. Nickel check (stainless)

≈ 80 % of the stainless price is the alloy surcharge (€2,228 of €2,728), and the surcharge follows **nickel**, not the steel PPI. The "nickel check" cases price stainless as base (driven by S09) + surcharge (driven by nickel in EUR).

| AirSeT | Stainless driven by S09 | Base S09 + surcharge nickel |
|---|---|---|
| 3-month change, P10 / P90 | −4.5 % / +10.4 % | −7.2 % / +10.4 % |
| 9-month change, P10 / P90 | −10.1 % / +27.9 % | −12.1 % / +28.9 % |
| 3-month change, worst | +16.7 % | **+25.8 %** |

→ Using S09 alone **understates AirSeT's risk**: it hides the nickel spikes, and the worst 3-month rise is ≈ 1.5× larger with nickel. The forecasting team (Steps 5–7) forecasts nickel (S03, already a target) and Steps 8–9 feed the surcharge through it.

## 6. History of the index (descriptive, not a forecast)

Past H-month changes of the BOM cost index, Apr 2018 → Sep 2026 (start limited by the epoxy series):

| Change over | RM6 P10 / P50 / P90 | AirSeT P10 / P50 / P90 |
|---|---|---|
| 3 months | −4.9 / +0.8 / **+9.7 %** | −4.5 / +0.1 / **+10.4 %** |
| 6 months | −6.4 / −0.5 / **+17.1 %** | −7.3 / −0.3 / **+19.1 %** |
| 9 months | −9.4 / −0.3 / **+26.0 %** | −10.1 / −0.5 / **+27.9 %** |

- Over 2018–2026, 1 fixed-price offer in 10 would have seen its raw-material cost rise by more than these P90s.
- The fat right tail comes from the 2021–22 surge. The forecast must decide how much weight that regime gets.
- With copper now in both BOMs, the two products' indices move much more alike than before.

## 7. For the next steps: the reusable function

`bom_index(breakdown, ratios)` in `src/cost_model.py` turns material price moves into a BOM index:
- `ratios` = one column per material (driver ÷ driver at Sep 2026), one row per month, scenario or **simulated path**.
- For the BOM rows of the submission CSV: simulate joint material paths, run each through `bom_index`, then take P10/P50/P90. **Do not add up material P90s**: that overstates the risk.

## 8. What this model leaves out

| Item | Why | Effect |
|---|---|---|
| Plastics (13.6 kg RM6, 21.2 kg AirSeT) | No public €/t level yet | Small by mass (4 % of each unit); € effect unknown until a level is found |
| Unknown lines (5.6 kg RM6, 56 kg AirSeT) | Client: unknown composition, do not invent one | Unknown; AirSeT's cost is a floor |
| Electronics | Client Q&A: minimal impact, ignore | – |
| Non-material cost (labour, overhead, purchased parts) | No reliable should-cost (the teardown's is inflated: 500 kg of screws, €1,073 packaging) | The buffer is stated on raw-material cost; turning it into margin points needs the raw-material share of total cost |

## 9. Decisions to revisit

| Decision | Current choice | Alternative |
|---|---|---|
| BOM | Client BOM v1 | – |
| Brass | 65 % copper + 35 % zinc proxy | Client's alloy, if they share it |
| Unknown lines and plastics | Unpriced (client rule) | Public €/t level × S11 for plastics |
| Steel €/t country | RM6 France, AirSeT Germany (no Hungary series) | Germany for both |
| Stainless driver | S09 main, nickel as a check; Steps 8–9 use the nickel split as the main case | – |
| Stainless level | Aug 2026 (latest CRU), not Sep | – |
