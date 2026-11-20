# Problem 2 – Market & Regulation (Steps 1–3)

*Owners: Kenza, Chloe · Status: Step 1 plan written, research to do · Steps 2–3 to come*

---

# Step 1 – Evidence inventory

**Goal:** gather every fact the strategy rests on, each one with a **source and a date**, before building the regulation map (Step 2), the market scoring (Step 3) and the lifetime-cost model (Step 4).

**Output:** one evidence table (section 4), filled in by the end of **Sat 21 Nov**.

---

## 1. What we already have (internal)

| Source | What it gives Problem 2 | Used in |
|---|---|---|
| Price benchmark (`RMU_IQI_EU_Price_Benchmark…`, synthetic) | Selling prices for 6 brands, 2017–2026. The SF6-free premium (Eaton vs Schneider) was +38 % in 2017, +22 % in 2025 and −5 % in 2026, after the EU ban. | Price gap (Steps 4, 7) |
| Teardown benchmark (`benchmark-…rm6-ne-iqi…xlsx`) | SF6 fill per unit: RM6 1.5 kg, Ormazabal 1.2 kg, Siemens 2.5 kg, ABB 3.24 kg, Eaton 0 kg (estimated, not measured). Insulation technology of each competitor; GWP 22,800. | Lifetime cost (Step 4), competitors (Step 2) |
| BOM (`bom_materials.csv`) and the Problem 1 cost model | Raw-material cost per unit: RM6 €795 vs AirSeT €583–981. Copper-heavy RM6 vs steel-heavy AirSeT. | Cost gap (Steps 4–5) |
| Problem 1 EDA | AirSeT's raw-material risk is ≈ 95 % steel and stainless, so a steel indexation clause covers most of it. | Pricing (Step 7) |
| Schneider raw-materials update, Oct 2026 (`2026-10 Cu, Al, Ag, Steel and Plastics.pptx`, internal) | Procurement's view: copper pulling back from record highs with an upward medium-term bias; steel prices now set by trade policy (EU quotas, 50 % out-of-quota duty, CBAM), US rising, China soft. | Raw-material outlook (Step 5), regional story (Step 2) |
| `Supplier_balancesheet/` (PitchBook, 9 suppliers) | Financial health of suppliers, for the question "can the supply base scale AirSeT?" | Optional, barriers (Step 8) |
| Client slides | Data-centre market $584B in 2026, 25.7 % CAGR, $1.32T by 2030; 90 %+ of new capacity pre-leased. | Market size (Step 3) |

**Gaps that external research must fill:** everything outside the EU (regulation, prices, market size), SF6 lifecycle costs, carbon prices, customer commitments, and competitors' SF6-free offers.

---

## 2. External research to collect

Priority: **A** = needed for the core argument (do first), **B** = strengthens it, **C** = nice to have.

### 2.1 SF6 regulation by region (tests H2: "regulation is coming")

| What to find | Where to look | Priority |
|---|---|---|
| **EU reference:** the F-gas Regulation (EU) 2024/573 dates for SF6 in new medium-voltage switchgear (≤ 24 kV and ≤ 52 kV) | EUR-Lex (the regulation text), European Commission F-gas page | A |
| **United States:** federal rules on SF6 (EPA reporting rules for electrical equipment); state rules, especially **California (CARB regulation on SF6 in gas-insulated equipment, with its phase-out dates)** and any other state with SF6 rules or proposals | CARB website, EPA website (Greenhouse Gas Reporting Program, SF6 Emission Reduction Partnership), state environment agencies | A |
| **Other target countries:** any SF6 rule, proposal or consultation in Canada, UK and Switzerland (as non-EU references); **Japan, South Korea, Australia, Singapore, India, China; Saudi Arabia, UAE**; Brazil, Mexico, Chile | National environment ministries; search "[country] SF6 regulation switchgear"; IEA policy database; trade press (T&D World, Power Engineering International) | A |
| **Climate commitments that could lead to SF6 rules:** national net-zero targets, emissions trading schemes that cover SF6, F-gas reporting duties | UNFCCC national climate plans (NDCs), ICAP status report | B |

→ **For each country, record:** status (none / under discussion / announced / in force), date, voltage scope, source.

### 2.2 SF6 lifecycle and technical facts (tests H3: lifetime cost)

| What to find | Where to look | Priority |
|---|---|---|
| **GWP of SF6:** values from IPCC AR4 (22,800, used in the benchmark), AR5 and AR6; which one reporting rules use | IPCC AR6 Working Group I, chapter 7 (GWP tables); GHG Protocol | A |
| **Leak rates:** the standard maximum for sealed-for-life equipment and real-world rates measured on installed equipment | IEC 62271-1 / 62271-200 (via summaries or manufacturer docs); EPA SF6 Partnership reports; CIGRE technical brochures on SF6 handling | A |
| **End of life:** cost of recovering and recycling SF6 per kg or per unit; how much is actually recovered; rules on handling (certified staff) | IEC 62271-4 (SF6 handling); SF6 recycler price lists or case studies; T&D Europe / NEMA guides | A |
| **Emissions reporting:** whether SF6 leaks from switchgear the operator owns count in its **own direct emissions (Scope 1)** | GHG Protocol Corporate Standard; SBTi guidance | A |
| **SF6 gas price** per kg (for repairs and refills) | Industry price reports, distributors | C |
| **Product life** of MV switchgear (often quoted 30–40 years) | Manufacturer documentation, CIGRE | B |

### 2.3 Carbon prices (tests H3: break-even carbon price)

| What to find | Where to look | Priority |
|---|---|---|
| **Compliance carbon prices** by country or region (EU ETS as reference; California cap-and-trade; Canada; UK; South Korea; China national ETS; Japan; Singapore carbon tax) | World Bank "State and Trends of Carbon Pricing" and Carbon Pricing Dashboard; ICAP status report | A |
| **Internal carbon prices** used by data-centre operators and large tech companies | Company sustainability reports; CDP disclosures | A |
| **Social cost of carbon** as an upper reference (e.g. US EPA estimate) | US EPA | B |

→ **What we need:** compare these prices with the break-even computed in Step 0 (≈ €56 / t CO₂e if the full SF6 content is counted; ≈ €1,900 / t if only leaks are counted).

### 2.4 Data-centre market by region (Step 3: where to play)

| What to find | Where to look | Priority |
|---|---|---|
| **Capacity under construction and planned (MW) by country**, growth rates, vacancy | Colliers 2026 Data Center Marketplace Report (slide reference [5], free); CBRE Global Data Center Trends; JLL Data Center Outlook | A |
| **Market value by region** (to split the $584B) | Research and Markets 2026 report (slide reference [4], free summary page) | A |
| **Electricity demand from data centres by region** | IEA "Energy and AI" report | B |
| **Hot spots** to check: US (Northern Virginia, Texas, Arizona, Ohio), Japan, Singapore, Malaysia (Johor), India, Australia, Saudi Arabia, UAE, Brazil, Mexico | The same reports; trade press (DatacenterDynamics, Data Center Frontier) | A |

### 2.5 Customer commitments (tests H1: "global operators apply one standard")

| What to find | Where to look | Priority |
|---|---|---|
| **Hyperscalers' climate targets** (net zero, Scope 1 targets) and whether they **mention SF6** or switchgear | Sustainability reports and supplier codes of conduct of Microsoft, Google, Amazon (AWS), Meta, Oracle; search the PDFs for "SF6" and "sulfur hexafluoride" | A |
| **Colocation providers:** same check | Equinix, Digital Realty, NTT, STACK, AirTrunk, Iron Mountain sustainability reports | A |
| **Industry pledges and standards** that could include SF6 | iMasons Climate Accord, Climate Neutral Data Centre Pact (EU, as reference), Open Compute Project, LEED / BREEAM credits for low-GWP equipment | B |
| **Announced SF6-free projects** by data-centre operators (any region) | Press releases; Schneider, Siemens, ABB and Hitachi Energy case studies | A |

→ **For each company, record:** target, year, whether SF6 is mentioned, whether it applies worldwide or only in the EU.

### 2.6 Competitors' SF6-free offers (tests H6, Step 2)

| What to find | Where to look | Priority |
|---|---|---|
| **Who sells SF6-free medium-voltage switchgear**, in which regions, at which voltages: ABB, Siemens, Hitachi Energy, Eaton, Ormazabal (Velatia), Lucy Electric, Mitsubishi Electric, Toshiba, Meidensha, LS Electric, Hyundai Electric, and Chinese makers | Company product pages and press releases; trade press | A |
| **Their technology** (pure air, dry air, other gas mixtures) and their **price or lifetime-cost claims** | Brochures, white papers | B |
| **Who still pushes SF6** in the target regions (low-cost competitors) | Distributor catalogues, tenders | B |

### 2.7 Schneider's own public material

| What to find | Where to look | Priority |
|---|---|---|
| **Environmental profiles (PEPs)** of RM AirSeT, SM AirSeT and SM6: material composition, **SF6 per panel for SM6** | Schneider PEP ecopassport library (se.com); RM6 profile ENVPEP1511010 already used in Step 2 | A |
| **AirSeT claims:** lifetime cost, digital features, footprint, data-centre case studies outside the EU | se.com product pages, white papers, press releases | A |
| **Schneider's SF6-free commitments** and targets | Schneider sustainability report | B |
| **What RMX is** (named on the "References" slide) | se.com, press | C |

### 2.8 Project economics (to scale per-unit figures to a data centre)

| What to find | Where to look | Priority |
|---|---|---|
| **How many MV units or panels a data centre needs per MW**, and medium-voltage switchgear's share of data-centre construction cost | Schneider data-centre reference designs and white papers; Turner & Townsend Data Centre Cost Index; Uptime Institute | B |

---

## 3. Research rules

- **Primary sources first:** the regulation text, the company report, the IPCC table. A news article is only a pointer to the primary source.
- **Record the date** of every figure. Prices and regulations change; the presentation is on 27 Nov 2026.
- **Give ranges** where sources disagree (leak rates, recovery costs, carbon prices). Step 4 uses the ranges for its sensitivity analysis.
- **Disclose AI tools** used for searching or summarising (slide "What good looks like", point 7), and check every AI-found fact against its source.
- **Confidential material stays out of the repo:** the Oct 2026 procurement deck, the BOM and the price benchmark. Cite them as "Schneider internal".

---

## 4. Evidence table (to fill)

One row per fact. Keep it here, or in `report/problem2/evidence.csv` if it gets long.

| ID | Fact | Value | Region | Source (link) | Date | Reliability | Used in |
|---|---|---|---|---|---|---|---|
| E01 | SF6-free price premium, Eaton vs Schneider, 2025 | +22 % (+€1,921) | EU | Price benchmark (Schneider, synthetic) | 2025 | Medium (synthetic) | Steps 4, 7 |
| E02 | SF6 fill, RM6 | 1.5 kg | – | Teardown benchmark (inferred) | 2026 | Low (estimated) | Step 4 |
| E03 | GWP of SF6 (AR4) | 22,800 | – | Teardown benchmark; to confirm in IPCC | – | To verify | Step 4 |
| E04 | Raw-material cost per unit, RM6 vs AirSeT | €795 vs €583–981 | – | Problem 1 Step 2 | Sep 2026 | Medium | Steps 4–5 |
| E05 | … | | | | | | |

**Reliability:** High = official or primary source · Medium = reputable secondary source or Schneider data · Low = estimate or single unverified source.



### Regulation map

One row per candidate country (not "APAC"). Status levels:

**0** no regulation or discussion · **1** under discussion / consultation · **2** announced / adopted, not yet in force · **3** in force

| Country / state | Status (0–3) | What is covered (voltage, new vs installed) | Key dates | Source |
|---|---|---|---|---|
| EU (reference) | | | | E1 |
| USA – California | | | | E2 |
| USA – other states / federal | | | | E2 |
| Canada | | | | E3 |
| UK | | | | E3 |
| Japan · South Korea · Australia · Singapore · India · China | | | | E3 |
| UAE · Saudi Arabia | | | | E3 |
| Brazil · Mexico | | | | E3 |

**What to look for:** places with status 1–2 are the best "future-proof" story. A customer buying SF6 equipment in 2027 owns it until about 2060 (I4), so any rule in that window is a risk to them. If California is confirmed as status 2–3, "the Americas have no SF6 regulation" is not fully true, and we should say so.

**Map output:** one world-map slide coloured by status (simple choropleth, e.g. plotly), plus the table.


### Competitive landscape

| Competitor | SF6-free MV product | Technology | Markets where sold | Price positioning (if known) | Still pushing SF6 there? | Source |
|---|---|---|---|---|---|---|
| Schneider | RM AirSeT / SM AirSeT | Pure air + vacuum (shunt vacuum interruption) *(to verify wording)* | | | | |
| Eaton | Xiria | Air-insulated, vacuum (I6) | | ≈ +20 % vs SF6 in EU (I1) | | |
| ABB · Siemens · Hitachi Energy · Ormazabal · Lucy · local makers | | | | | | E9 |

**Key question:** in which candidate countries is Schneider the **only** or **first** SF6-free supplier? Being first is a reason to prioritise; strong local SF6 competitors on price are a reason to wait.

### Customer landscape

| Segment | Examples | SF6 / switchgear policy found? (E6–E7) | Applies globally? | Decision-makers |
|---|---|---|---|---|
| Hyperscalers | Microsoft, Google, AWS, Meta, Oracle | | | Global design standards team, sustainability |
| Colocation (global) | Equinix, Digital Realty, NTT GDC | | | Design, tenant requirements |
| Colocation (regional) | APAC / Middle East players | | | |
| Utilities | Per country | | | Regulator, network planning |
| Industry / infrastructure | Later target | | | |

**Test for H1:** count how many of the top 5 hyperscalers and top 5 colos explicitly mention SF6 or SF6-free switchgear in a document that applies worldwide. 3+ out of 10 → H1 holds; 0–1 → H1 is dropped and the "carry the EU win abroad" argument goes.