# Problem 2 – Framing the problem

*Owners: Kenza, Chloe · Status: draft*

---

## 1. The problem in one paragraph

Schneider leads in **SF6-free medium-voltage switchgear**. In the EU, regulation is phasing SF6 out of new equipment, so customers there must switch. In markets with **no SF6 regulation (APAC, Middle East, Americas)**, nothing forces them to. The SF6-free product has a **higher upfront cost and a thinner margin**, so it has to win on its own merits.

**Our goal:** recommend **which markets to target, with what value proposition, at what price and through which levers**, so that customers switch voluntarily from **SM6 (SF6) to SM AirSeT (SF6-free)**, and so that Schneider stays **profitable** doing it. The client also asks us to **show how the raw-material forecast (Problem 1) supports the argument**.

---

## 2. What we deliver (from the client presentation)

**The five outputs** ("Two goals, one model" slide, Goal B):
1. **Target markets and segments**
2. **Value proposition**
3. **Commercial and pricing approach**
4. **Adoption levers**
5. **Roadmap and win conditions**

**The arguments the client points us to** ("Business case" and "Three questions" slides):
- **Total cost of ownership (TCO):** what the equipment costs the customer over its life, not just at purchase.
- **Customer ESG and decarbonisation goals**, especially data-centre operators.
- **Avoided SF6 lifecycle risks:** leaks, handling, end of life.
- **Regulation and competition.**
- **Raw-material (RM) outlook:** "leverage RM price convergence … and show how RM prediction supports the argument".

**How it is evaluated:** "3/6/9-month forecast accuracy **AND** quality of the non-regulated-market business strategy – both matter equally". There is no metric for the strategy, so section 7 sets our own test of a good answer.

---

## 3. Scope decisions

| Topic | Decision | Why |
|---|---|---|
| **Products** | The slides name **SM6 → SM AirSeT** for Problem 2, but the headline question is about "winning **RM AirSeT** proposals" and all our data is on **RM6 / RM AirSeT**. Until the organisers answer (section 8, question 1), every number is for **RM6 / RM AirSeT**. The qualitative strategy (markets, value proposition, levers) applies to both families; the figures (SF6 per unit, cost gap, price gap) do **not** transfer to SM without SM data. | RM6 is a compact ring main unit with all functions in one SF6 tank; SM6 is a line-up of air-insulated panels with SF6 only in each switch. Same SF6-free technology (pure air + vacuum; the client slide says "solid insulation, vacuum interruption") and same customers, but different SF6 amounts and cost structure. |
| **Markets** | **APAC, Middle East, Americas.** The EU is used only as the reference: what happens to prices and demand once SF6 is regulated. | Slide "Three questions", question 3. |
| **Customers** | **Data centres first**, other segments (utilities, industry, infrastructure) as later targets. | The whole case is framed on the data-centre boom: $584B market in 2026, 25.7 % CAGR, and every new data centre needs medium-voltage switchgear. |
| **Point of view** | Two sides: the **customer** (TCO, ESG, risk) and **Schneider** (margin, measured in margin points as in Problem 1). | "Accelerate the switch **profitably**". |
| **Time horizon** | Offers signed **2027** (Problem 1 forecasts run to Jun 2027); strategy roadmap **2027–2030**. | Matches Problem 1 and the 2030 market projection on the slides. |
| **External facts** | Every regulation date, GWP value, carbon price or market figure gets a **source and a date**. Values we have not yet checked are marked *(to verify)*. | Slide "What good looks like": state data limits; disclose AI tools, including for research. |

---

## 4. What the data already tells us

### The upfront price gap is about 20 % outside the EU, and has closed inside it

The synthetic price benchmark (`RMU_IQI_EU_Price_Benchmark…`) has no AirSeT price, but it has **Eaton**, the only SF6-free brand in the panel. It is our proxy for "SF6-free vs SF6" pricing.

| Year | Schneider P50 (SF6) | Eaton P50 (SF6-free) | SF6-free premium |
|---|---|---|---|
| 2017 | €7,230 | €9,948 | **+38 %** |
| 2025 | €8,740 | €10,661 | **+22 %** (+€1,921) |
| 2026 | €12,233 | €11,560 | **−5 %** |

- **Before the EU ban**, the premium shrank from 38 % to 22 % in eight years.
- **In 2026**, SF6 brands jump +32 to +40 % (the client's chart marks the SF6 change) while Eaton moves +8 %. In the EU, SF6-free is now the cheaper option.
- **Outside the EU** no such jump is forced, so **the 2025 gap (≈ +20 %, ≈ €1,900 per unit) is the hurdle our strategy has to overcome**.
- Caveats: the panel is **synthetic**, EU-only and yearly, and Eaton is a competitor proxy, not AirSeT.

### Raw materials alone cannot close that gap

From Problem 1 Step 2 (raw-material cost per unit, Sep 2026):

| | RM6 (SF6) | RM AirSeT |
|---|---|---|
| Raw-material cost | €795 | €583 (epoxy low) – €981 (epoxy high) |
| Gap vs RM6, % of RM6 selling price (€8,740) | – | **−2.4 to +2.1 points** |
| Main cost drivers | Copper 61 % | Stainless + carbon steel (≈ 95 % of RM risk) |

- **Raw materials are about 9 % of the selling price**, so the RM gap is ±2 points against a ≈ 20-point price gap. **AirSeT's "higher cost structure" is mostly not raw materials**: it sits in components, the insulation process and volume.
- **The direction still helps.** RM6 is a copper bet, and copper is at a record high (€12,974/t in Oct 2026). AirSeT has no copper in the BOM. A copper rally raises RM6's cost faster, so the raw-material outlook works in AirSeT's favour. But even +30 % copper only moves RM6's cost by about 1.7 points of price.
- **Two open questions change this:** AirSeT's copper (none in the BOM; Eaton's teardown suggests ≈ 26 kg) and what its 86 kg of "Other" is. AirSeT's BOM is also **twice as heavy** as RM6's (629 vs 310 kg), so the two may not be the same configuration.

→ **Framing consequence:** the RM outlook is a **supporting** argument (direction and timing), not the main one. The main arguments have to be TCO, ESG and risk. We say this honestly.

### SF6 content: the carbon arithmetic decides the TCO argument

The teardown benchmark gives the SF6 fill per unit (masses are tool-inferred, not measured):

| Product | SF6 per unit |
|---|---|
| Schneider RM6 | 1.5 kg |
| Ormazabal CGMCOSMOS | 1.2 kg |
| Siemens 8DJH | 2.5 kg |
| ABB SafePlus | 3.2 kg |
| Eaton Xiria | **None** (air / vacuum) |

**Illustration for one RM6** (GWP 22,800, as used in the benchmark file; newer IPCC reports give higher values):
- **Full SF6 content:** 1.5 kg × 22,800 ≈ **34 t CO₂e**.
- **Leaks only** (≈ 0.1 %/yr for sealed-for-life equipment *(to verify)*, over 30 years ≈ 3 %): ≈ **1 t CO₂e**.

| What the customer counts | Carbon price at which AirSeT's €1,921 premium pays back |
|---|---|
| Full content (lost at end of life, or valued as a liability) | ≈ **€56 / t CO₂e** |
| Leaks only | ≈ **€1,900 / t CO₂e** |

→ **Framing consequence:** leak carbon alone will **not** win the case. It wins only if we value the **whole SF6 content**: end-of-life recovery cost and risk, future regulation that strands SF6 assets, and SF6 counted in the operator's own emissions reporting *(to verify)*. This is the central question of Step 4 (TCO).

### Margin protection is possible on AirSeT

From the Problem 1 EDA: **AirSeT's raw-material risk is almost entirely carbon steel and stainless.** Schneider already buys steel on a MEPS/CRU index, so a **steel-linked indexation clause** would remove most of that risk. This matters because AirSeT's margin is thinner, and it is what lets us offer a sharper AirSeT price without taking the raw-material gamble. The numbers come from Problem 1 Steps 8–9.

### Supply side

`Supplier_balancesheet/` holds PitchBook financials for **9 suppliers** (e.g. Electris, Green Transfo, KUVAG). They can show whether the supply base can support scaling AirSeT. This is optional, for Step 1.

---

## 5. What we don't have, and how we handle it

| Missing | How we handle it |
|---|---|
| The two product cost overviews cited on the "References" slide ("RM AirSeT and RM6 Product and Cost Overview", "RM AirSeT vs RMX Product Cost Overview") | Ask the organisers (section 8). Meanwhile, use the Step 2 cost model and the Eaton price proxy. |
| Any SM6 / SM AirSeT data | RM used as the proxy (section 3). |
| AirSeT selling price and margin | Range from the Eaton premium (+20 %) and "thinner margin" in the brief; tested in the sensitivity analysis. |
| Prices outside the EU | Assume the 2025 EU gap holds where SF6 is not regulated; test ±10 points. |
| Market sizes per region, customer commitments, regulation status, carbon prices | External research in Steps 1–2, each fact sourced and dated. |
| Product configurations (1F–4F, mentioned on the "Your challenge" slide) | Not in the data; we work on the single 3-function unit, as in Problem 1. |
| Customer interviews | None possible; stated as a limitation. |

---

## 6. Hypotheses to test

The strategy is built by testing these hypotheses. Each one is either confirmed or dropped, with the evidence.

| # | Hypothesis | Tested in | It is wrong if… |
|---|---|---|---|
| H1 | **Global data-centre operators apply one SF6-free standard worldwide**, so an EU win carries over to their sites in APAC, the Middle East and the Americas. | Step 2 | Their procurement or ESG policies don't mention SF6 or switchgear. |
| H2 | **Some non-EU markets are likely to regulate SF6 soon**, so "future-proof" is a real argument there. | Step 2 | No regulation is discussed or announced in the target regions. |
| H3 | **TCO favours AirSeT once the whole SF6 content is valued** at a realistic or internal carbon price. | Step 4 | Break-even needs a carbon price far above what customers use. |
| H4 | **The raw-material outlook narrows the cost gap** (copper rising faster than steel). | Step 5 (needs P1 Step 8) | Problem 1 forecasts show steel or stainless rising faster than copper. |
| H5 | **AirSeT can be priced closer to SM6 without losing margin**, thanks to steel indexation and volume. | Step 7 (needs P1 Steps 8–9) | The margin left after the risk buffer falls below the floor. |
| H6 | **The EU price convergence (2026) will repeat elsewhere** as volume grows and regulation spreads. | Steps 2, 5 | Gap drivers are structural (components, process), not volume or regulation. |

---

## 7. What a good answer looks like

- **Specific:** names 2–3 priority market × segment targets, not "APAC".
- **Quantified:** the price gap, the TCO break-even and the margin impact, each with ranges and sources.
- **Profitable:** every pricing move is checked against AirSeT's margin after the Problem 1 risk buffer.
- **Linked to Problem 1:** at least one decision uses the raw-material forecast (the cost-gap outlook, or the indexation clause).
- **Actionable:** a roadmap with dated steps, KPIs and the triggers that would make Schneider speed up or pause.
- **Honest:** says where the evidence is weak (synthetic prices, product proxy, inferred SF6 masses).

**Success measure for the strategy itself:** AirSeT's share of new medium-voltage orders in the target markets by 2030, with offer margin kept at or above an agreed floor.

---

## 8. Questions for the organisers

Only questions that change **what we build**:

1. **Which product is Problem 2 about?** The Problem 2 slides say **SM6 → SM AirSeT**, but the headline question ("winning **RM AirSeT** proposals") and all the data are about **RM6 / RM AirSeT**. Is Problem 2 meant to be about RM (and SM is a slip), or about SM? If SM, is there SM data (SF6 per panel, cost gap, prices) we should have?
2. **Missing documents:** can we get the two product cost overviews listed on the "References" slide? They would replace our proxies for the AirSeT cost gap.
3. **AirSeT price gap:** is the order of magnitude of the SF6-free premium in the synthetic benchmark (≈ +20 % before 2026) representative of AirSeT outside the EU?