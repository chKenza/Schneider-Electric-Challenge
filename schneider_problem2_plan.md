# Schneider Electric – Problem 2: Winning the Voluntary SF6-Free Switch

## What Problem 2 is

**The client's question** (slides 12, 13, 15):
> In markets with **no SF6 regulation** (APAC, Middle East, Americas; except California and New York, which regulate SF6), what strategy wins the **voluntary** switch from RM6 (SF6-insulated) to **RM AirSeT** (SF6-free)? Which markets, value proposition, pricing and go-to-market accelerate the switch **profitably**?

**Context:**
- SF6 is the insulating gas in most medium-voltage switchgear. It is the most potent greenhouse gas known (GWP-100 = 22,800 in IPCC AR4, 23,500 in AR5, 24,300 in AR6), and leaks over the equipment's 30–40-year life and at end of life.
- In the EU, regulation is phasing SF6 out of new equipment, so customers there **must** switch. Elsewhere, nothing forces them to: the switch has to be **sold** on its own merits.
- The SF6-free technology (RM AirSeT: pure-air insulation + vacuum interruption; the slide says "solid insulation") has a **higher upfront cost** and gives Schneider a **thinner margin** (slide 12).
- The client suggests the arguments: **total cost of ownership (TCO)**, **customer ESG and decarbonisation goals** (data-centre operators especially), **avoided SF6 lifecycle risks**, regulation, competition, and the **raw-material (RM) outlook** (slide 13, 15).

**What the jury expects** (slide 13, "Goal B"): target markets & segments · value proposition · commercial & pricing approach · adoption levers · roadmap & win conditions.

**How it is evaluated:** equally with Problem 1 (slide 14: "3/6/9-month forecast accuracy AND quality of the non-regulated-market business strategy — both matter equally"). It is a **strategy case**: market research, a TCO comparison, a clear argument. It needs far less code than Problem 1.

**How it relates to Problem 1** ("two goals, one model", slide 13): Problem 1's raw-material forecasts feed the cost-gap and TCO arguments ("leverage RM price convergence … show how RM prediction supports the argument", slide 15), and Problem 1's pricing rules tell us how to price AirSeT without losing margin. Most of Problem 2 does **not** need Problem 1 and can start now.

> **External facts in this plan** (regulation dates, GWP values, market figures) are from general knowledge: verify each one with a source before using it in the presentation.

---

## Dependencies on Problem 1 at a glance

| Step | Needs Problem 1 outcome? | Which outcome | Can start now? |
|---|---|---|---|
| 0 – Framing | ❌ No | — | ✅ |
| 1 – Evidence inventory | ❌ No | (reuses Problem 1's data inventory) | ✅ |
| 2 – Regulation & market landscape | ❌ No | — | ✅ |
| 3 – Segmentation & target markets | ❌ No | — | ✅ |
| 4 – Cost gap & TCO model | ⚠️ Partly | P1 Step 2 (raw-material cost per unit), Step 8 (cost index outlook) | ✅ structure now, numbers later |
| 5 – RM outlook & price convergence | ✅ Yes | P1 Step 8 (RM6 vs AirSeT cost index, P10 / P50 / P90, to mid-2027) | ❌ wait for P1 Step 8 |
| 6 – Value proposition | ❌ No (uses Step 4) | — | ✅ |
| 7 – Commercial & pricing approach | ✅ Yes | P1 Step 8 (margin points at risk), Step 9 (quote rule: price adjustment, buffer, validity, indexation) | ⚠️ options now, numbers later |
| 8 – Adoption levers & go-to-market | ❌ No | — | ✅ |
| 9 – Roadmap & win conditions | ⚠️ Partly | P1 Step 8–9 (cost-gap and margin thresholds used as triggers) | ✅ draft now |
| 10 – Story & integration | ✅ Yes | P1 headline results (forecast, buffer, cost outlook) | ❌ end |
| 11 – (Optional) TCO tab in the app | ✅ Yes | P1 Step 11 (Streamlit app) | ❌ after P1 app |

---
# Market and Regulation (step 0-3):

## Step 0 – Frame the question and the deliverables

- Write the question in one paragraph and list the five deliverables (markets & segments, value proposition, pricing, adoption levers, roadmap & win conditions).
- **Product scope:** Problem 2 is about **RM6 → RM AirSeT** (ring main units), the same products as Problem 1. "SM6 → SM AirSeT" on the Problem 2 slides was a typo (confirmed).
- **Ask the organisers** for the two product cost overviews cited on slide 20 but not in `Data/`: "RM AirSeT and RM6 Product and Cost Overview" and "RM AirSeT vs RMX Product Cost Overview".
- Fix the time horizon of the strategy (e.g. 2027–2030) and the success measure (e.g. AirSeT share of new orders in target markets, with margin kept above a floor).

**Needs Problem 1?** ❌ No.

**Output:** one-paragraph problem statement, scope decisions, list of assumptions.

---

## Step 1 – Evidence inventory

**Internal data we already have:**

| Source | What it gives Problem 2 |
|---|---|
| `RMU_IQI_EU_Price_Benchmark_2017-2026_Synthetic.xlsx` | Selling prices by brand, 2017–2026. Key fact (from `report/step0_framing.md`): in 2026 SF6 brands jump +32 to +40 %, the SF6-free brand (Eaton) +8 % → the upfront price gap is closing in the EU |
| `benchmark-…rm6-ne-iqi….xlsx` | Competitor products (Ormazabal, SGC, ABB, Siemens, Eaton Xiria), their technology (SF6 vs air / vacuum), mass, should-cost |
| `bom_materials.csv` | RM6 vs RM AirSeT material composition (copper-heavy vs steel-heavy) |
| `Supplier_balancesheet.zip` | Supplier financial health → supply-chain capacity / risk for scaling AirSeT (optional) |
| Problem 1 data panel | Raw-material and energy prices (reused in Steps 4–5) |

**External research to collect** (cite every source):
- SF6 regulation by country / region, current and announced.
- Data-centre investment and capacity pipeline by region (slide 11 gives global figures: $584B in 2026, $1.32T by 2030; the slide's 25.7 % is the 2025→26 growth, the 2026–30 rate is 22.7 %).
- Sustainability commitments of major data-centre operators (hyperscalers, colocation providers): net-zero targets, Scope 1 reporting, SF6 policies.
- SF6 lifecycle facts: GWP, typical leakage rates, end-of-life recovery cost, handling rules.
- Carbon prices by region (EU ETS, other schemes, internal carbon prices used by companies).
- Competitors' SF6-free offers and positioning.

**Needs Problem 1?** ❌ No (the Problem 1 data inventory is reused, but nothing has to be computed first).

**Output:** evidence table (fact, value, source, date).

---

## Step 2 – Regulation and market landscape

- **Regulation map** for the candidate regions (APAC, Middle East, Americas — and the EU as the reference): no regulation / discussion / announced / in force. Look for places where regulation is **likely to come** (a strong "future-proof" argument even where it is not mandatory yet).
- **Market attractiveness** per region: data-centre construction pipeline, grid investment, medium-voltage switchgear demand.
- **Competitive landscape:** who sells SF6-free there, at what price positioning; who still pushes SF6.
- **Customer landscape:** hyperscalers (global ESG policies, often apply EU-level standards everywhere), colocation providers, utilities, industrial sites.

**Needs Problem 1?** ❌ No.

**Output:** regulation map, market and competitor overview per region.

---

## Step 3 – Segmentation and target markets

- Build a **scoring matrix**: region × customer segment, scored on:
  - market size and growth (data-centre pipeline);
  - ESG pressure (customer commitments, investor pressure);
  - regulatory trajectory (likelihood of future SF6 rules);
  - carbon price (explicit or internal);
  - price sensitivity;
  - competitive intensity;
  - Schneider's presence and channel strength.
- Choose **2–3 priority targets** (e.g. "hyperscaler data centres in [region]"), with the reasoning, plus 1–2 "later" targets.
- Keep the weights explicit and test that the ranking does not flip with reasonable weight changes.

**Needs Problem 1?** ❌ No.

**Output:** scoring matrix, shortlist of target markets / segments with rationale.

---
# Cost and TCO (step 4-5)

## Step 4 – Cost gap and TCO model

Compare RM6 (SF6) and RM AirSeT over the equipment's life, from the **customer's** point of view:

```
TCO = purchase price + installation + maintenance over life
      + SF6 handling / monitoring / leak repair
      + carbon cost of SF6 leaks (leak rate × SF6 mass × GWP × carbon price)
      + end-of-life SF6 recovery and disposal
      + risk cost of future regulation (retrofit / stranded asset)
```

- **Upfront price gap:** from the price benchmark (SF6 brands vs Eaton SF6-free) and the RM6 vs AirSeT raw-material cost difference.
- **Lifecycle terms:** from external research (Step 1); use ranges, not single values.
- **Sensitivity:** carbon price (0 / internal price / EU-level), leak rate, life length, discount rate. Show the **break-even**: "at a carbon price above €X/t CO₂, AirSeT is cheaper over its life."
- Use the RM6 SF6 mass in the teardown BOM (≈ 1.5 kg per unit) as a starting point; verify it.

**Needs Problem 1?** ⚠️ **Partly.**
- Build the model structure and the lifecycle terms **now**.
- From Problem 1: the **raw-material cost per unit** for RM6 and AirSeT (P1 Step 2) and its **outlook** (P1 Step 8) for the upfront-cost part. Use placeholders until they are ready.

**Output:** TCO model (spreadsheet or Python), break-even chart, sensitivity table.

---

## Step 5 – Raw-material outlook and price convergence

The client explicitly asks to "leverage RM price convergence" and "show how RM prediction supports the argument" (slide 15).

- From Problem 1: the **RM6 vs RM AirSeT raw-material cost index**, P10 / P50 / P90, to mid-2027.
- Question: **does the raw-material cost gap narrow?** RM6 is copper-heavy, AirSeT is steel-heavy. If copper keeps rallying while steel is flat, the SF6 unit's raw-material cost rises faster, and the gap narrows.
- Translate into the argument: "under our baseline forecast, the raw-material cost gap shrinks by X % by mid-2027; in the upside copper scenario, by Y %."
- Be honest if the forecast does **not** support convergence; then the argument rests on TCO and ESG instead.

**Needs Problem 1?** ✅ **Yes, fully.** Needs P1 Step 8 (BOM cost index outlook per product, under scenarios). Wait for it.

**Output:** cost-gap outlook chart (RM6 vs AirSeT), one-sentence finding for the story.

---
# Value and Pricing (step 6-8)

## Step 6 – Value proposition per target segment

For each priority segment from Step 3, one value proposition built on:
- **ESG / decarbonisation:** SF6 leaks count in the operator's direct emissions; avoiding them supports net-zero commitments and sustainability reporting.
- **TCO:** lifecycle cost from Step 4 (where AirSeT wins and under which carbon price).
- **Risk avoidance:** no SF6 handling, no end-of-life recovery liability, no stranded asset if regulation arrives.
- **Other benefits** to confirm with product documentation (e.g. digital monitoring, footprint, safety).
- Tailor the message: hyperscalers (global ESG standards, reputation), colocation (tenant requirements), utilities (regulatory foresight).

**Needs Problem 1?** ❌ No (uses Step 4, which can use placeholders).

**Output:** one value-proposition canvas or one-pager per segment.

---

## Step 7 – Commercial and pricing approach

- **Pricing options** to compare:
  - **Price parity** with SF6 in priority segments (absorb part of the cost gap to win share);
  - **Green premium** (charge more where ESG value is high);
  - **TCO-based pricing** (price set so the customer's lifecycle cost is lower than SF6);
  - **Bundles:** service contracts, monitoring, end-of-life take-back.
- **Margin guardrails:** AirSeT's margin is thinner (slide 12), so any discount must be checked against raw-material risk.
- **Offer structure from Problem 1:** apply the Problem 1 quote rule to AirSeT offers — price adjustment, risk buffer, quotation validity, **steel indexation clause** (AirSeT is steel-heavy and Schneider already buys steel on an index).

**Needs Problem 1?** ✅ **Yes.**
- P1 Step 8: **margin points at risk** for AirSeT per horizon (how much margin a discount leaves after raw-material risk).
- P1 Step 9: **quote rule** (price adjustment, buffer, validity, indexation trigger).
- The pricing options themselves can be drafted **now**; the numbers come from Problem 1.

**Output:** recommended pricing approach per segment, with the margin check.

---

## Step 8 – Adoption levers and go-to-market

- **Who decides:** consulting engineers who write specifications, data-centre design teams, sustainability officers, procurement. Map who to convince for each segment.
- **Levers:**
  - get "SF6-free" written into **specifications and tenders** (framework agreements with hyperscalers);
  - **pilot projects** and reference sites in each target market;
  - **training** of installers and maintenance partners;
  - **financing / leasing** to spread the upfront cost gap;
  - **take-back programmes** for old SF6 equipment;
  - support for **standards and voluntary labels**; engagement with regulators where rules are under discussion;
  - channel partner incentives.
- **Barriers and answers:** upfront price, unfamiliarity with the technology, footprint / compatibility, supply capacity (supplier health, Step 1).

**Needs Problem 1?** ❌ No.

**Output:** lever map per segment (lever, target decision-maker, expected effect, cost).

---
# Strategy (step 9-10)

## Step 9 – Roadmap and win conditions

- **Phased roadmap** (e.g. 2027 / 2028–29 / 2030+): which markets first, which levers when.
- **Win conditions:** what must be true for the strategy to work (e.g. "cost gap below X %", "carbon price above €Y/t", "N reference sites", "AirSeT in the framework agreement of hyperscaler Z").
- **KPIs:** AirSeT share of quotes and orders in target markets, win rate, margin, CO₂e avoided.
- **Triggers to accelerate or pause:** new regulation announced, raw-material cost gap crossing a threshold, competitor launch.

**Needs Problem 1?** ⚠️ **Partly.** The roadmap can be drafted now. Cost-related win conditions and triggers (cost-gap threshold, margin floor) use P1 Step 8–9 numbers.

**Output:** roadmap (one slide), win-condition and KPI table.

---

## Step 10 – Story and integration with Problem 1

- One storyline, as the client framed it: **"one engine, two outcomes"** — the same raw-material forecasting engine protects offer margin (Problem 1) and supports the SF6-free argument (Problem 2).
- Structure: market opportunity → why customers should switch (TCO, ESG, risk) → where to play (targets) → how to win (value proposition, pricing, levers) → roadmap → how the RM forecast supports it.
- **Limitations:** synthetic price data, external facts with ranges, no customer interviews.

**Needs Problem 1?** ✅ **Yes:** headline results (forecasts, buffers, cost-gap outlook) to link the two parts.

**Output:** Problem 2 section of the final presentation.

---

## Step 11 – (Optional) TCO tab in the Streamlit app

- Add a "SF6-free business case" page to the Problem 1 app: inputs = target market, carbon price, leak rate, equipment life; outputs = TCO comparison and break-even.
- Reinforces "one engine" and helps reach maturity level 4 (decision tool) for both problems.

**Needs Problem 1?** ✅ **Yes:** P1 Step 11 app and P1 Step 8 cost outlook.

**Output:** one extra app page.

---

## Suggested timing

| Phase | Problem 2 work | Waits for Problem 1? |
|---|---|---|
| Now | Steps 0–3, 6, 8; Step 4 structure; Step 7 options; Step 9 draft | No |
| When P1 Step 8 is ready | Steps 4 (numbers), 5 | Yes (cost index outlook) |
| When P1 Step 9 is ready | Steps 7 (numbers), 9 (thresholds) | Yes (quote rule) |
| Final phase | Steps 10, 11 | Yes (headline results, app) |

Team: 1–2 people from now (≈ 20–30 % of team time), whole team in the final phase.
