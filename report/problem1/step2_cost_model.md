# Step 2 – Cost decomposition model

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
- The index is weighted by **euros, not kg**: 39 kg of copper costs more than 140 kg of steel.

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
| Plastics (PET, PBT, ETP) | **None – unpriced** | S11 (ready once a level exists) |

## 3. Masses (kg per unit) and where they come from

| Material | RM6 | AirSeT | Source |
|---|---|---|---|
| Carbon steel | 139.7 | 327.2 | RM6: unlabelled 45 % slice × 310 kg, read as carbon steel (the RM6 PEP shows 51 % steel). AirSeT: BOM |
| Stainless steel | 55.8 | 102.6 | BOM |
| Copper | 38.8 | – | BOM; RM6 PEP gives ≈ 38.7 kg |
| Galvanised steel | 21.1 | – | BOM |
| Aluminium | 5.0 | 5.0 | BOM |
| Plastics | 5.6 | 25.1 | BOM (unpriced) |
| Epoxy | **1.6** | **3.9 (low) / 85.6 (high)** | RM6: PEP, 0.62 % of 255 kg. AirSeT low: same 0.62 % × 629 kg. AirSeT high: all of BOM "Other" |

Sources:
- `bom_materials.csv`
- RM6 Product Environmental Profile ENVPEP1511010_V2 (Schneider, 07/2023)

**AirSeT epoxy is unknown.** No AirSeT composition is public. The client slides say "solid insulation, vacuum interruption", and the IDC white paper (Sept 2026, p. 31) says "pure air insulation". So we carry two cases.

## 4. Results: raw-material cost of one unit (Sep 2026)

| | RM6 | AirSeT, epoxy low | AirSeT, epoxy high |
|---|---|---|---|
| **Total (priced materials)** | **€795** | **€583** | **€981** |
| Biggest share | Copper 61 % | Stainless 48 %, carbon steel 46 % | Epoxy 42 %, stainless 29 %, carbon steel 28 % |

**What +10 % on one material does to the unit cost** (index points = % of raw-material cost):

| Material +10 % | RM6 | AirSeT low | AirSeT high |
|---|---|---|---|
| Copper | **+6.1 pts (€49)** | – | – |
| Stainless | +1.9 (€15) | **+4.8 (€28)** | +2.9 (€28) |
| Carbon steel | +1.5 (€12) | **+4.6 (€27)** | +2.8 (€27) |
| Epoxy | +0.1 (€1) | +0.3 (€2) | **+4.2 (€42)** |
| Galvanised, aluminium | ≤ 0.2 each | ≤ 0.2 | ≤ 0.2 |

> **AirSeT's figures are a floor, not a comparison with RM6.** The BOM lists no copper for AirSeT, and ≈ 27 % of its mass ("Other" + unlabelled slices) is unpriced. An RMU almost certainly has copper (busbars, vacuum interrupters; the Eaton Xiria teardown lists ≈ 26 kg). We're asking the client before adding a copper case.

- **RM6 is a copper bet.** Copper alone moves its cost 3× more than anything else.
- **AirSeT is a steel + stainless bet**, unless its epoxy is large. The epoxy question moves AirSeT's cost by €400 (+68 %).

## 5. Nickel check (stainless)

≈ 80 % of the stainless price is the alloy surcharge (€2,228 of €2,728), and the surcharge follows **nickel**, not the steel PPI. The "nickel check" cases price stainless as base (driven by S09) + surcharge (driven by nickel in EUR).

| AirSeT, epoxy low | Stainless driven by S09 | Base S09 + surcharge nickel |
|---|---|---|
| 3-month change, P10 / P90 | −4.5 % / +12.2 % | −8.7 % / +11.6 % |
| 9-month change, P10 / P90 | −11.9 % / +32.4 % | −15.0 % / +32.0 % |
| 3-month change, worst | +19.6 % | **+38.7 %** |

→ Using S09 alone **understates AirSeT's risk**: it hides the nickel spikes, with the worst 3-month rise twice as large. The forecasting team (Steps 5–7) should forecast nickel (S03, already a target) and feed the surcharge through it.

## 6. History of the index (descriptive, not a forecast)

Past H-month changes of the BOM cost index, Apr 2018 → Sep 2026 (start limited by the epoxy series):

| Change over | RM6 P10 / P50 / P90 | AirSeT low P10 / P50 / P90 |
|---|---|---|
| 3 months | −5.0 / +0.8 / **+10.5 %** | −4.5 / −0.9 / **+12.2 %** |
| 6 months | −7.2 / −0.4 / **+17.4 %** | −8.4 / −1.7 / **+22.4 %** |
| 9 months | −8.8 / +0.1 / **+27.3 %** | −11.9 / −2.3 / **+32.4 %** |

- Over 2018–2026, 1 fixed-price offer in 10 would have seen its raw-material cost rise by more than these P90s.
- The fat right tail comes from the 2021–22 surge. The forecast must decide how much weight that regime gets.

## 7. For the next steps: the reusable function

`bom_index(breakdown, ratios)` in `src/cost_model.py` turns material price moves into a BOM index:
- `ratios` = one column per material (driver ÷ driver at Sep 2026), one row per month, scenario or **simulated path**.
- For the BOM rows of the submission CSV: simulate joint material paths, run each through `bom_index`, then take P10/P50/P90. **Do not add up material P90s**: that overstates the risk.

## 8. What this model leaves out

| Item | Why | Effect |
|---|---|---|
| Plastics (5.6 kg RM6, 25.1 kg AirSeT) | No public €/t level yet (external data TBD) | Small by mass (2 % RM6, 4 % AirSeT); € effect unknown until a level is found |
| Unlabelled slices (rest of RM6, ≈ 13 % of AirSeT) | Unknown composition | Unknown |
| Electronics | Client Q&A: minimal impact, ignore | – |
| Non-material cost (labour, overhead, purchased parts) | No reliable should-cost (the teardown's is inflated: 500 kg of screws, €1,073 packaging) | The buffer is stated on raw-material cost; turning it into margin points needs the raw-material share of total cost |

## 9. Decisions to revisit

| Decision | Current choice | Alternative |
|---|---|---|
| RM6 unlabelled 45 % slice | Carbon steel | Ask client; PEP supports steel |
| RM6 epoxy | 1.6 kg (PEP) | 11 kg teardown (rejected: its copper was wrong too) |
| AirSeT epoxy | Two cases: 3.9 / 85.6 kg | Client's composition, if they share it |
| AirSeT copper | None (as in the BOM) | Asking the client; else add a 26 kg case (Eaton Xiria teardown) |
| Steel €/t country | RM6 France, AirSeT Germany (no Hungary series) | Germany for both |
| Stainless driver | S09 main, nickel as a check | Make the nickel split the main case (section 5 suggests it) |
| Plastics | Unpriced | Public €/t level × S11 |
| Stainless level | Aug 2026 (latest CRU), not Sep | – |
