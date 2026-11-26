# Problem 2 – Strategy: roadmap and win conditions (Step 9)

*Owner: Karin · Status: draft (Step 9). Step 10, the final story, comes later.*

> **Sources:** E-numbers refer to rows of [`market_evidence/evidence.csv`](../../market_evidence/evidence.csv). "01 §3.4" means section 3.4 of [01_market_and_regulation.md](01_market_and_regulation.md); likewise for [02](02_cost_and_tco.md) and [03](03_value_and_pricing.md). H1–H6 are the hypotheses in the [problem framing](00_problem_framing.md) (§6).

> **Run from the repo root:**
>
> ```bash
> uv run python -m src.strategy          # win conditions, window opening, triggers, CO2 KPI
> uv run python -m src.strategy_plots    # charts 12-13
> uv run python -m pytest tests/test_strategy.py
> ```

| What | Where |
|---|---|
| Code | [`src/strategy.py`](../../src/strategy.py), [`src/strategy_plots.py`](../../src/strategy_plots.py) |
| Tests | [`tests/test_strategy.py`](../../tests/test_strategy.py) |
| Tables | [`04_tables/`](04_tables/) |
| Charts | `plots/problem2/12_window_opening.png`, `13_roadmap.png` |
| Inputs | TCO model (`src/tco.py`), Step 7 price window (`src/value_pricing.py`), Problem 1 Step 9 tables (`quote_rule.csv`, `outlook_2027.csv`) |

> **SF6 and carbon prices, in brief.** SF6 is the insulating gas sealed inside each RM6 (≈ 1.5 kg). It is not bought or sold by the customer; it matters because it is a very strong greenhouse gas: 1 kg ≈ 23.5 t of CO₂-equivalent, so one RM6 holds ≈ 35 t CO₂e. A **carbon price** (€/t CO₂e) is the cost a company puts on its emissions in its decisions, usually an internal "shadow" price (median ≈ €22/t, E56), not a market price for the gas. How much of the gas a customer **counts** as an emission decides what avoiding it is worth (02 §4.4):
>
> | View | What is counted | t CO₂e per unit | Value at €22/t |
> |---|---|---|---|
> | Leaks only | Gas leaking during use (Scope 1) | ≈ 2.8 over 40 years | ≈ €21 |
> | Leaks + end of life | Plus the gas released when the unit is scrapped | ≈ 6 | ≈ €25 (discounted) |
> | Whole fill | All the gas in the unit, as a liability from day one | ≈ 35 | ≈ €776 |

`src/strategy.py` adds no new model. It reuses the Step 4 TCO model and the Step 7 price window without changing their settings, and turns them into thresholds. Its tests check that it reproduces the Step 7 windows exactly.

---

## Summary

- **Where to play:** start where SF6 already costs the customer something or where a customer already counts it.
  - **2027:** Australia colocation, and Johor–Singapore with AirTrunk as lead customer.
  - **Gulf data centres:** a volume and reference market, not a margin market.
  - **Later:** Australian utilities, then the US data-centre states and the UK if their regulation moves.
- **The one number that decides the roadmap is AirSeT's extra unit cost compared with RM6.** It is not the carbon price or raw materials. Each segment opens below a threshold:

  | Segment | Opens when AirSeT's extra cost is below |
  |---|---|
  | Australia colocation | **16.7 %** |
  | Johor–Singapore data centres | **9.1 %** |
  | Australia utilities | **8.1 %** |
  | Gulf data centres | **0.5 %**: never, on cost alone |

  If the cost falls as the UK review expects at scale (E166), Johor–Singapore opens in **2028** and Australian utilities in **2029** (chart 12).
- **The cheapest win condition is changing how customers account for the SF6 gas in their emissions.** If a data-centre operator treats the whole SF6 fill of a unit (35 t CO₂-equivalent) as a liability, instead of only the small amount that leaks, AirSeT's value rises from about €21 to about €776 per unit.
  - At the 10 % placeholder for the extra cost, Johor–Singapore opens if the customer applies an internal carbon price of **€24/t** CO₂-equivalent instead of the €22/t median, provided it counts the whole fill.
  - The Gulf has the same 9.1 % threshold as Johor–Singapore if its customers count the whole fill. Counting only leaks and end-of-life release, the threshold is 0.5 %.
  - So getting SF6 into operators' accounting is worth more than any discount (03 §8).
- **Problem 1 protects the margin; it doesn't close the gap.**
  - Every 9-month AirSeT quote carries a steel and stainless indexation clause.
  - Problem 1's monthly forecast is the alarm: AirSeT's raw-material cost is €583 today, with a 9-month P90 of **€688** by June 2027.
  - The raw-material gap between RM6 and AirSeT is **not** a reason to move: it changes by at most €105 (P90), under 6 % of the premium.
- **Success measure (framing §7):** AirSeT's share of new medium-voltage orders in the target markets by 2030, with the margin on each offer kept at or above RM6's. The only exception is up to 1 point on named lead-customer deals.

---

## 9.1 The strategy on one page

| Deliverable | Answer | From |
|---|---|---|
| **Target markets and segments** | 1. Johor–Singapore data centres · 2. Gulf (Saudi Arabia, UAE) data centres · 3. Australia colocation. Second segment: utilities in Australia, Saudi Arabia and Japan. Later: US data-centre states, UK. China opportunistic only. | 01 §3.4 |
| **Value proposition** | "Same job, same footprint, no SF6." Sell on (1) the whole SF6 fill as a liability, 35 t CO₂e per unit; (2) no SF6 paperwork where rules apply; (3) future-proof. **Don't** sell on leak-based TCO or raw-material convergence. | 03 §6 |
| **Pricing** | A TCO-based premium per segment: ≈ 9 % Johor–Singapore, up to ≈ 16 % Australia colocation, ≈ 8 % Australian utilities. No price competition in the Gulf. Bundles (take-back, monitoring, leasing) where the window is shut. | 03 §7 |
| **Offer structure (Problem 1)** | Quotes up to 6 months: fixed price plus ≤ 0.6 points. 9-month quotes: steel and stainless indexation clause plus a small uplift. | 03 §7.5, P1 Step 9 |
| **Adoption levers** | SF6 into operators' accounting (iMasons declarations) · "SF6-free" in specifications and framework agreements · AirTrunk reference site · SEC pilot · take-back · training · channel incentives | 03 §8 |
| **Roadmap and win conditions** | This report: §9.2–9.5 | – |

---

## 9.2 Roadmap

![Roadmap](../../plots/problem2/13_roadmap.png)

### Phase 1 – Prove (2027)

**Goal:** a profitable first market, two public references, and the real AirSeT cost.

| Market | Move | Price | Why now |
|---|---|---|---|
| **Australia colocation** | Sell AirSeT as the default offer to colocation operators; price just under Eaton | TCO-based, up to ≈ 16 % | The only window open today: import licence, levy and upkeep already cost the customer (03 §7.2). ⚠️ Rests on €50/yr of SF6 upkeep; without it the threshold is 9.1 %, as in Johor (§9.3). |
| **Johor–Singapore** | **AirTrunk lead deal and reference site** in Johor. AirTrunk counts SF6 in Scope 1 and is exploring SF6-free equipment (E85) | ≈ 9 %, accepting up to 1 margin point as an entry price | With a 1-point entry give, the window opens up to a 10.1 % extra cost, so it is open at the placeholder (§9.3) |
| **Gulf** | Framework agreements with private AI and data-centre campus developers; join SEC's SF6-free pilots | List price for customers with their own SF6 policy; otherwise a few reference projects only | Fastest growth (Saudi Arabia ≈ +59 %/yr). Build volume; don't buy share. SEC's RMU specification still requires SF6 (E28). |

**Enablers, all markets, 2027:**
- **Get SF6 into operators' accounting:** propose an SF6 line in iMasons environmental declarations (E113), and give customers a per-unit figure of 35 t CO₂e.
- **Bundle:** take-back of old SF6 units (≥ 99 % recovered, E17) and a monitoring service contract.
- **Steel and stainless indexation clause** as standard on every 9-month AirSeT quote (P1 Step 9).
- **Get the real AirSeT extra unit cost** from the organisers' cost overview. It replaces the 10 % placeholder that every threshold depends on.
- **Footprint check** on each tender (E171 vs E168) before claiming "same footprint".

### Phase 2 – Scale (2028–2029)

**Goal:** volume brings AirSeT's extra cost below the next thresholds.

| Market | Move | When it opens (at-scale / slow path) |
|---|---|---|
| **Johor–Singapore** | Move from the entry price to the TCO-based price (≈ 9 %) across operators, not only AirTrunk | **2028 / 2029** |
| **Australian utilities** | Multi-year framework agreements, extending their high-voltage SF6-free choice to distribution | **2029 / 2030** |
| **Gulf** | Price like Johor–Singapore **only if** customers start counting the whole fill. Otherwise stay a volume market | 2028 / 2029 in the whole-fill case; never otherwise |
| **Utilities in Saudi Arabia and Japan** | From pilot to specification change (SEC) | Not on cost: ceiling ≈ 0 % (03 §6.2) |

### Phase 3 – Extend (2029–2030+)

**Goal:** enter large markets when a trigger fires (§9.5), not before.

- **US data-centre states (Texas, Virginia, Ohio):** the largest voluntary market, but there are gas-free incumbents (S&C, G&W) and no customer pull. Move when another state adopts a phase-out after New York, or when a US operator starts counting SF6 (01 §3.4).
- **UK:** if the phase-out under study becomes a proposal (E71), treat it as a "regulation coming" market.
- **China:** opportunistic only. It ranks on size alone, and local makers dominate (01 §3.3).

---

## 9.3 Win conditions

### What must be true, per segment

([`win_conditions.csv`](04_tables/win_conditions.csv); carbon price €22/t, Problem 1 raw-material risk at 9 months)

| Segment | How SF6 is counted | Customer ceiling | **Opens if AirSeT's extra cost <** | … with 1-point entry give | Or if the carbon price ≥ (at 10 % extra cost) | Carbon price for today's 22 % premium |
|---|---|---|---|---|---|---|
| Australia colocation | Whole fill + SF6 upkeep | 16.6 % | **16.7 %** | 17.7 % | €5/t (already met) | €35/t |
| Johor–Singapore data centres | Whole fill | 8.9 % | **9.1 %** | 10.1 % | **€24/t** | €54/t |
| Australia utilities | Leaks + end of life + upkeep | 8.0 % | **8.1 %** | 9.1 % | €165/t | €1,080/t |
| Gulf data centres | Leaks + end of life | 0.4 % | **0.5 %** | 1.5 % | €741/t | €1,657/t |
| *Gulf, if it counts the whole fill* | Whole fill | 8.9 % | 9.1 % | 10.1 % | €24/t | €54/t |
| *Australia colocation, without SF6 upkeep* | Whole fill | 8.9 % | 9.1 % | 10.1 % | €24/t | €54/t |

How to read it:
- **"Opens if AirSeT's extra cost <":** below this, there is a premium at which the customer saves over the unit's life **and** Schneider keeps RM6's margin. It doesn't depend on the 10 % placeholder.
- **"Or if the carbon price ≥":** if the extra cost stays at 10 %, the carbon price the customer would need to apply to SF6 for the window to open.
- **Johor–Singapore is close:** €24/t against a €22/t median internal price, or 1 point of margin.
- **The Gulf and utilities can't be opened by carbon prices.** €165–741/t is far above any price that reaches them (01 §6). They need volume, bundles, or a change in how they count SF6.

### The win conditions, as statements

| # | Win condition | Threshold | Status today | Owner of the evidence |
|---|---|---|---|---|
| W1 | AirSeT's extra unit cost vs RM6 falls with volume | < 9.1 % for Johor–Singapore, < 8.1 % for Australian utilities | **Unknown** (10 % placeholder) | Organisers' cost overview (framing §8) |
| W2 | Target data-centre operators count the **whole SF6 fill**, not only leaks | Ceiling rises from 0.4 % to 8.9 % | 1 of 11 operators counts SF6 at all (AirTrunk) | 01 §7 |
| W3 | A lead customer signs and becomes a public reference | AirTrunk in Johor in 2027 | No contact yet (03 §6.4) | Sales |
| W4 | Raw-material risk stays priced, not absorbed | Every 9-month AirSeT quote has a steel and stainless clause; realised erosion stays within the quote rule's accepted loss | Rule exists (P1 Step 9) | Problem 1 |
| W5 | AirSeT keeps the same footprint as RM6 in data-centre electrical rooms | Vendor claim holds per project | Schneider claim (E171) vs UK review +20–30 % (E168) | Product team |
| W6 | AirSeT's price stays at or below Eaton's in Australia and Singapore | Rival price ≥ AirSeT's TCO-based price | Not observed (synthetic EU prices only) | Sales intelligence |

### When each segment opens, if AirSeT gets cheaper with volume

![Window opening](../../plots/problem2/12_window_opening.png)

([`window_opening.csv`](04_tables/window_opening.csv))

| Segment | No volume gain (10 % flat) | Slow (→ 7.5 % in 2030) | At scale (→ 5 % in 2030) | At scale, with 1-point entry give |
|---|---|---|---|---|
| Australia colocation | 2027 | 2027 | 2027 | 2027 |
| Johor–Singapore data centres | never | 2029 | **2028** | 2027 |
| Australia utilities | never | 2030 | **2029** | 2028 |
| Gulf data centres | never | never | never | never |

**The paths are illustrative, not a forecast.** They start at the 10 % placeholder and assume AirSeT's extra cost falls in the same proportion as the UK review's expected premium, from 15–30 % today to 5–10 % at scale (E166). The thresholds hold whatever the path. Once the real extra cost is known, read the opening year off chart 12.

---

## 9.4 KPIs

| KPI | Why | Target | Source / frequency |
|---|---|---|---|
| **AirSeT share of RMU orders** in each target market | The success measure (framing §7) | Baseline in 2027; target **to agree** with the client | Sales, quarterly |
| AirSeT share of RMU **quotes**, and **win rate** on AirSeT quotes vs Eaton | Leading indicator of share; tests W6 | Win rate ≥ RM6's in the same market | Sales, quarterly |
| **Margin vs RM6 per offer** (points) | "Profitably" | ≥ 0 points; ≥ −1 point on named lead-customer deals | Finance, per offer |
| **AirSeT extra unit cost vs RM6** | W1: decides when each segment opens | < 9.1 % (Johor–Singapore), < 8.1 % (Australian utilities) | Finance, half-yearly |
| **Target customers counting SF6** (whole fill) | W2: raises the ceiling from 0.4 % to 8.9 % | 1 of 11 today (AirTrunk); target **to agree** | Sustainability reports, yearly |
| **Reference sites** | W3 | ≥ 1 per priority market by end 2027 (proposed) | Sales |
| **9-month AirSeT quotes with a steel and stainless clause** | W4 | 100 % | Sales ops, per quote |
| **Realised raw-material erosion on AirSeT quotes** | W4: checks Problem 1's buffer | Within the quote rule's accepted loss | Problem 1 monthly run |
| **CO₂e avoided** | ESG claim to customers | 35 t per unit (whole fill); 2.8 t (leaks over 40 years) | [`co2_avoided.csv`](04_tables/co2_avoided.csv) |

**CO₂e avoided per AirSeT unit sold instead of an RM6** (t CO₂e):

| View | Pessimistic | Base | Optimistic |
|---|---|---|---|
| Leaks over the life | 1.0 | **2.8** | 12.8 |
| Leaks + end-of-life release | 1.2 | **6.1** | 32.0 |
| Whole fill | 16.4 | **35.2** | 60.8 |

Report the **whole-fill** figure as "SF6 kept out of the installed base", and the **leaks** figure as "Scope 1 emissions avoided". Mixing them up would overstate the Scope 1 claim by 12×.

---

## 9.5 Triggers to accelerate or pause

([`triggers.csv`](04_tables/triggers.csv); thresholds computed from the Problem 1 and Step 4 tables)

| Watch | Threshold | Action | Source |
|---|---|---|---|
| **AirSeT raw-material cost** (Problem 1 monthly run) | > **€688** by Jun 2027 (9-month P90; €583 today) | The steel and stainless clause triggers; re-quote fixed-price offers; check the price floor | P1 Step 9 |
| **RM6 raw-material cost** | > **€946** by Jun 2027 (9-month P90; a floor, because copper's upside tail was underestimated) | Copper clause on RM6 quotes. The gap narrows, so mention it in tenders | P1 Step 9 |
| **RM6 − AirSeT raw-material gap** | Change > **+€105** (P90) or < **−€66** (P10) | Above: "convergence" can be mentioned, but it is still < 6 % of the premium. Below: AirSeT is relatively dearer; re-check the floor | P1 Step 9 |
| **AirSeT extra unit cost** | < **9.1 %** (< 10.1 % with entry give) | **Accelerate:** open Johor–Singapore at the TCO-based price (Phase 2) | §9.3 |
| **Carbon price a target customer applies to SF6** | ≥ **€24/t**, counting the whole fill | **Accelerate:** the Johor–Singapore window opens at today's cost | §9.3 |
| **Carbon price that justifies today's 22 % premium** | ≥ **€54/t** (whole fill) | Move ESG-led segments from the TCO-based price to the list price | 02 §4.4 |
| **SF6 rule in a target market** | Status 0/1 → 2 or 3 (phase-out adopted, or a ban) | **Accelerate:** future-proof pitch, list price, more sales capacity. Candidates: US states, UK (01 §2.1) | `regulation.csv` |
| **SF6-free rival price** (Eaton, Chinese dry-air RMUs) | Below AirSeT's TCO-based price in a target market | Defend with the bundle before cutting price. **Pause** the market if the price would have to go below the floor | `competitors.csv` |
| **Footprint** | A tender where AirSeT is larger than the RM6 it replaces | Price the extra space into the TCO; don't claim "same footprint" there | E171, E168 |

---

## 9.6 Hypotheses: final status

| # | Hypothesis | Result |
|---|---|---|
| H1 | Operators apply one SF6-free standard worldwide | **Not supported:** 9 of 11 never mention SF6 (01 §7). Hence lever W2 |
| H2 | Non-EU markets will regulate soon | **Partly:** US states and the UK; not Asia or the Middle East before 2030 (01 §2.1). Hence Phase 3 triggers |
| H3 | TCO favours AirSeT once the whole fill is valued | **Only in the whole-fill view:** break-even €54/t; ≈ 9 % premium at €22/t (02 §4.4) |
| H4 | The raw-material outlook narrows the cost gap | **Direction yes, size no:** 0.5 % of the premium at P50 (02 §5) |
| H5 | AirSeT can be priced closer to RM6 without losing margin | **Yes where the extra cost allows:** today in Australia colocation; in Johor–Singapore below 9.1 %. Raw-material risk is not the obstacle: €53 for AirSeT vs €64 for RM6 on a 9-month quote, covered by the clause (03 §7). **The extra unit cost is.** |
| H6 | EU convergence repeats elsewhere | **Not through raw materials.** Through volume (the extra-cost path, §9.3) or regulation (triggers, §9.5) |

---

## 9.7 Check against "what a good answer looks like" (framing §7)

| Criterion | Met by |
|---|---|
| Specific: 2–3 named market × segment targets | Australia colocation, Johor–Singapore with AirTrunk, Gulf private data centres (§9.2) |
| Quantified, with ranges and sources | Thresholds and carbon prices per segment (§9.3); every input sourced in `assumptions.csv` |
| Profitable: every pricing move checked against margin after the risk buffer | Thresholds include Problem 1's 9-month raw-material risk; KPI "margin vs RM6 ≥ 0" |
| Linked to Problem 1 | Indexation clause on every 9-month quote; raw-material triggers from the Problem 1 forecast (§9.5) |
| Actionable: dated roadmap, KPIs, triggers | §9.2, §9.4, §9.5 |
| Honest | The 10 % placeholder, the Australian upkeep caveat and the illustrative cost paths are flagged; limits in §9.9 |

---

## 9.8 Assumptions

| Assumption | Value | Effect | Status |
|---|---|---|---|
| AirSeT's extra unit cost vs RM6, 2027 | **10 %** (Step 7 placeholder) | Decides which segments open when. The thresholds don't depend on it; the opening years do | **To replace** with the organisers' cost overview |
| Extra-cost paths to 2030 | Flat 10 %, → 7.5 %, → 5 % | Opening years in §9.3 | Illustrative: UK review premium ratio (E166) applied to cost |
| Margin given up vs RM6 | 0 points; 1 point for named lead-customer deals | +1 point on each threshold | **To agree** with the team |
| Customer carbon price | €22/t (CDP median internal price, E56) | Ceilings | Sourced |
| SF6 upkeep in Australia | €50/yr (optimistic value) | Australia colocation 16.7 % vs 9.1 % without | The rules found target imports, not owners (03 §7.2); **to confirm** |
| Problem 1 raw-material risk | 9-month quote, 0.5 points accepted loss, 90 % confidence, steel PPI | ±0.1 point on every threshold | As in Step 7 |

## 9.9 Limits

- **Everything hinges on one unknown,** AirSeT's real extra unit cost. That is why the roadmap is expressed as thresholds and triggers, not as fixed dates.
- **Synthetic, EU-only prices,** and Eaton stands in for AirSeT (02 §4.6).
- **No customer interviews.** Willingness to pay is stated (EU buyers, E173), and no contact with AirTrunk has been made.
- **One unit, one configuration.** No fleet, volume-discount or portfolio effects, so the TCO is conservative for AirSeT.
- **KPI targets for share and customers counting SF6 are not set.** There is no baseline data; agree them with the client.
- **Supply capacity is not analysed.** The supplier balance sheets (`Supplier_balancesheet/`) could test whether the supply base can follow Phase 2.

## 9.10 Open points for the team

1. **Organisers' cost overview** ("RM AirSeT and RM6 Product and Cost Overview"). Rerun `src.value_pricing` and `src.strategy` with the real extra cost, then update §9.2–9.3.
2. **Margin give for lead customers (1 point):** agree it with the team. It opens Johor–Singapore in 2027.
3. **Australian SF6 upkeep:** confirm whether any owner-side rule applies. If not, Australia colocation moves to the Johor–Singapore timeline (2028 at scale).
4. **KPI targets:** set the order-share and reference-site targets with the client.
5. **Problem 1 dependencies:** if the corrected BOM (`a_v1`) arrives, rerun P1 Steps 8–9, then `src.value_pricing` and `src.strategy`. The raw-material triggers in §9.5 will move.

---

**AI use:** Claude helped write `src/strategy.py`, its tests and charts, and draft this report from the Step 1–8 reports. Every figure is computed by the code from the committed tables, or quoted from the earlier reports with its section.
