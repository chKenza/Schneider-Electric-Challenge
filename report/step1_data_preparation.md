# Step 1 – Data inventory and preparation

*Owner: Karin · Status: done*

> **To get the data, run this once from the repo root:**
>
> ```bash
> uv run python -m src.data_prep
> ```
>
> It needs these files from the data Schneider gave us, placed in `Data/` (they are not in the repo, ask Karin):
>
> - `data.zip` (or the unzipped `data/` folder)
> - `Copia de Europe Steel INDEXES.xlsx`
> - `LME_Copper_Aluminium_EU_Monthly_2016_2026.xlsx`
> - `Epoxy for student.xlsx`
> - `RMU_IQI_EU_Price_Benchmark_2017-2026_Synthetic.xlsx` (the unlocked version)
>
> It writes the cleaned data to `Data/processed/`. Rerun it after pulling any change to `src/data_prep.py`.

---

## 1. What was done

All price sources were loaded, cleaned and aligned into **one monthly panel**, ending at the **forecast origin** (September 2026, the last month of data the client asks us to use). Every series is documented with its source, licence and publication lag. The selling-price file was also loaded.

**How to run** (from the repo root):

```bash
uv run python -m src.data_prep                  # origin 2026-09 (submission)
uv run python -m src.data_prep --origin 2026-06 # as if we were in an earlier month
```

- **Code:** `src/data_prep.py`.
- **Inputs:** the challenge files in `Data/`. The `Data/data/` folder can stay zipped (`Data/data.zip`), so the pipeline also works from a clean clone.
- **Outputs:** `Data/processed/`, not committed (`Data/` is gitignored).

| Output file | Content |
|---|---|
| `panel_monthly.csv` | 357 months (Jan 1997 → Sep 2026) × 84 series |
| `data_dictionary.csv` | Per series: description, unit, source, **licence**, publication lag, **forecast target (yes/no, EU/WW)**, first/last month |
| `sources.csv` | Per source: publication lag and **licence**. This is the licence table the client asks for. |
| `imputation_log.csv` | Every value that was changed or filled, and why |
| `rmu_prices_yearly.csv` | Synthetic selling prices by brand and year (P10/P50/P90) |

---

## 2. What is in the panel

| Group | Series | Unit | History from | Role |
|---|---|---|---|---|
| Free metal prices (IMF) | S01–S05: copper, aluminium, nickel, iron ore, zinc | USD/t | Nov 2016 | **Targets (WW)** |
| Same, in EUR | D01, D02 (Cu, Al) | EUR/t | Nov 2016 | **Targets (EU)** |
| | S03_EUR, S04_EUR, S05_EUR (Ni, iron ore, Zn) | EUR/t | Nov 2016 | Input |
| FX | S06 (USD per EUR) | – | Nov 2016 | Input |
| Producer price indices (PPI) | S07–S11: EU copper, aluminium, steel, plastics; Germany steel | Index | Nov 2016 | **Targets (EU)** |
| | S12, S13: US steel, US plastics | Index | Nov 2016 | **Targets (WW)** |
| Energy | E01–E24, ED01–ED06: oil, gas, power (incl. FR and HU), energy PPIs | Mixed | Nov 2016 | Input |
| Flat steel – MEPS | HR, CR, HDG coil; Germany and France | EUR/t | Nov 2012 | Input |
| Flat steel – CRU | HR, CR, HDG coil; Germany and France | EUR/t | May 2012 | Input |
| Stainless 304 – CRU | Base, alloy surcharge, total; Germany and France | EUR/t | Jan 2008 | Input |
| Long steel – CRU | Merchant bar, Germany (long history) | EUR/t | Jan 1997 | Input |
| LME copper and aluminium | Cash, 3-month, spread, stocks | USD/t, EUR/t, t | Jan 2016 | Input |
| Epoxy | Epoxy resin and its inputs | EUR/t | Jan 2018 | Input |

**The 14 forecast targets** are the priceable BOM proxies listed in `bom_materials.csv`:
- **EU:** D01, S07, D02, S08, S09, S10, S11
- **WW:** S01, S02, S03, S04, S05, S12, S13

All other series are inputs that help forecast them.

---

## 3. Cleaning decisions

1. **Dates:** all dates snapped to the first day of the month (CRU uses the 15th, epoxy uses odd days).
2. **Cut-off:** the panel stops at the origin month (default Sep 2026). November 2026 is month-to-date in the LME and CRU files and is never used.
3. **Currency:** USD prices converted with S06 (`EUR = USD / S06`). The USD series are kept.
4. **Market prices and PPIs kept side by side** (e.g. LME copper and the copper PPI). The targets are fixed, and the others can help forecast them.
5. **Weekly CRU prices:** the monthly "AVERAGE" column for Germany. France has one spot price per month.
6. **Not kept:**
   - empty licensed columns L01–L08
   - UK prices (GBP)
   - Nordic and Swedish prices (18–30 months only)
   - wire rod
   - Turkish prices
   - the "▲" sheets, which are differences of the level sheets
7. **No gaps inside any series.**

---

## 4. Values changed or filled (`imputation_log.csv`)

| Month | Series | Before → after | Why |
|---|---|---|---|
| May 2026 | Epichlorohydrin | 257 → 2,543 | Entry error: neighbours are ~2,500 (likely a ×10 typo). Replaced by the average of Apr and Jun. |
| May 2026 | Epoxy resin | 3,593 → 4,956 | −27 % then +39 % in the same month as the typo. Same fix. |

- **If the origin is May 2026,** June isn't known yet, so these two values are left empty instead of interpolated.
- **For a later origin (October 2026 or after),** missing IMF copper/aluminium months are filled from the LME file. The two sources differ by 0.06 % on median over 120 months. This has **no effect at the September 2026 origin**.

---

## 5. Publication lags: what was known when

At a quote date, the latest prices are not yet published. Backtests must not use them, otherwise results look better than reality.

**Rule:** the value for month *m* can be used at quote month *t* only if *m* ≤ *t* − lag.

| Source | Lag (months) | Comment |
|---|---|---|
| IMF metals and energy prices, Eurostat PPIs, US PPIs | 2 | PPIs are also revised over the next 2–4 months |
| ECB FX, Ember power, Bank of Japan, JEPX | 1 | |
| LME, MEPS, CRU flat steel, epoxy | 1 | |
| CRU long steel | 2 | |
| CRU stainless | 3 | Last value Aug 2026; to confirm |
| Eurostat oil imports | 4 | |
| Derived series (e.g. D01 = S01 / S06) | Lag of the slowest input | |

**For the modelling steps:** `available_at(panel, dictionary, quote_month)` in `src/data_prep.py` returns only what was known at a given quote month. Use it in every backtest.

---

## 6. Licences (`sources.csv`)

| Source | Licence | Can go in a public repo? |
|---|---|---|
| Eurostat, Ember | CC BY 4.0 | Yes, with attribution |
| IMF and US BLS via FRED, ECB, Bank of Japan, JEPX | Free, attribution | Yes, with attribution |
| LME via Westmetall | LME data is licensed | **Check first** |
| MEPS, CRU | Licensed, provided by Schneider | **No** |
| Epoxy file | Provided by Schneider, source unknown | **No** (treat as confidential) |
| Schneider BOM, RMU price benchmark | Schneider internal | **No** |

This is why the data stays out of the repo. How to make the pipeline reproducible without it is an open question for the client (Step 0, question 1).

---

## 7. Checks between sources

| Comparison | Median level gap | Correlation of monthly changes |
|---|---|---|
| IMF copper (D01) vs LME file copper | +0.06 % | 0.998 |
| IMF aluminium (D02) vs LME file aluminium | +0.05 % | 0.997 |
| MEPS vs CRU, CR coil Germany | −3.0 % | 0.93 |
| MEPS vs CRU, CR coil France | +2.2 % | 0.89 |
| MEPS vs CRU, HDG coil Germany | −6.8 % | 0.92 |
| CRU stainless 304, Germany vs France | +0.3 % | 0.98 |

- **Copper and aluminium:** the sources agree.
- **Steel:** MEPS and CRU move together but differ in level by 3–7 %.
- **Stainless and nickel:** the 304 alloy surcharge follows nickel with a **1–2 month delay** (correlation 0.09 in the same month, **0.71 one month later**, 0.87 on 3-month changes). So nickel is an early warning for stainless.

---

## 8. Selling prices (`rmu_prices_yearly.csv`)

- **What it is:** a synthetic yearly EU selling price for a 24 kV, 3-function RMU like the RM6, for 6 brands, 2017–2026, with P10/P50/P90.
- **What's missing:** no AirSeT price, no product configurations, no costs.
- **Prices are sticky:** in 2021–22 raw materials rose 40–100 %, but Schneider's price rose only about 7 % a year. In 2023–25 materials fell and prices were never cut.
- **2026 jump:** SF6 brands +32 to +40 %, the SF6-free brand +8 %. This reflects the SF6 ban, so 2026 is left out of margin backtests.

---

## 9. Data issues and limits

**Recipes (BOM):**
1. **RM6:** only 40.7 % of ≈ 310 kg has a material label. The largest unlabelled slice (≈ 45 %) is probably carbon steel.
2. **AirSeT:** 86.7 % of ≈ 629 kg is labelled, and 13.6 % is "Other".
3. **The two RM6 recipes disagree on copper:**

   | | Schneider BOM | Benchmark "teardown" |
   |---|---|---|
   | Total mass | ≈ 310 kg | 275 kg |
   | Copper | 38.8 kg | 8.6 kg Cu + 5.2 kg Cu-alloy contacts |

   The teardown isn't a physical teardown: a tool generated it, its masses are marked "inferred", and it contains errors (500 kg of screws). `share_pct` in the Schneider BOM is confirmed to be a share of **mass**: kg ÷ share gives the same total for every material.

**Other data:**

4. **The steel indexation file is old and partial:** 2016–2018, Arcelor only, and it does not include SFCME or Duna.
5. **Revisions aren't modelled.** We only have today's values, not first releases, so PPIs in backtests are slightly "too clean".
6. **History of the free series starts in Nov 2016.** The download scripts the data README mentions are not in the data folder. Only the steel series go further back (CRU stainless to 2008, CRU long to 1997).
7. **The CRU stainless lag (3 months)** is based on one snapshot.

---

## 10. Decisions to revisit

These choices were made while building this step and **have not been confirmed by the team**. Each is a small change in `src/data_prep.py`.

| # | Current choice | Alternative | Why it matters |
|---|---|---|---|
| 1 | **14 targets**: both series wherever the BOM file lists two for one material (e.g. copper D01 *and* S07, aluminium D02 *and* S08) | Only the first-listed series per material | Changes how many forecasts we submit and backtest |
| 2 | **Data stops at Sep 2026** (slide 17: "2026-09, last data used"), even though Oct 2026 exists for FX, LME, MEPS/CRU, epoxy and power | Use everything known today | We give up one fresher month for some inputs |
| 3 | **May 2026 epichlorohydrin and epoxy treated as entry errors**, replaced by the Apr–Jun average | Keep the raw values, or ask the client | Modifies data the client gave us |
| 4 | **Publication lags** measured on one snapshot (e.g. CRU stainless = 3 months) | Look up official release calendars | Decides what backtests are allowed to see |
| 5 | **Steel inputs: Germany and France only.** Italy, Spain, UK, Nordic, wire rod and Turkey dropped | Keep more countries as inputs | Fewer inputs for the forecast models |
| 6 | **CRU Germany = monthly average of weekly prices; France = spot** | Other columns of the sheet | Small |
| 7 | **Licence labels**: epoxy file "treat as confidential", LME/Westmetall "check first" | Ask the client | Decides what can go in the repo |
| 8 | **Assumptions for later steps**: RM6's unlabelled 45 % slice = carbon steel; 2026 left out of margin backtests (SF6 ban) | Other scenarios | Step 2 and Step 9 results |

**External public data: to be decided (not done):**
- Starting €/t prices for plastics (Eurostat Comext trade values) and stainless after Aug 2026 (Outokumpu / Aperam alloy surcharges)
- Longer history for the free series (FRED / Eurostat back to the 1990s); needs our own download script
- Schneider's public environmental profile for the RM6 (`ENVPEP1511010EN`), to settle the copper mass
