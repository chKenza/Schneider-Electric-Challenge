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




## 1. SF6 regulation by country / region

**Legend used in the PDF**
- **Yes**: highly regulated or no ban
- **No**: complete ban or phasing out

> Note: some regions may be in the process of phasing out SF6. The status of these regions is automatically assumed as "No" (no use allowed).

**Status scale (0–3)** — replaces the Yes/No column for the analysis, because Yes/No mixes "heavily regulated" with "nothing at all" and hides the countries where regulation is coming (the "future-proof" argument, H2):

| Status | Meaning | What it means for Problem 2 |
|---|---|---|
| **0** | No SF6 rule and no discussion (at most broad GHG rules or voluntary action) | Voluntary market: sell ESG and risk |
| **1** | Under discussion / consultation, or SF6-specific rules short of a ban (handling, reporting, quotas) | Voluntary market: "regulation is coming" |
| **2** | Phase-out announced / adopted, not yet in force | Voluntary for now, best future-proof story |
| **3** | Ban or phase-out in force for new MV equipment | Not voluntary: reference market only |

- A range (e.g. **0–1**) means the current source is too weak to decide. The low end is used in the pessimistic scenario, the high end in the optimistic one (same as `status_min` / `status_max` in `data/regulation.csv`).
- Every status is **to verify** against a primary source (research rules, section 3). Most current sources are vendor or gas-seller blogs (reliability Low).

SF6 regulation by US state: <https://www.climatepolicydashboard.org/policies/industry-materials-waste/sf6-regulations>

| Country / region | Is SF6 allowed? (PDF) | Status (0–3) | Why this status / what to verify | Key dates | Details / notes | Source |
|---|---|---|---|---|---|---|
| EU | No | **3** | In force. "By 2032" is likely the HV end date; for MV ≤ 24 kV (RM6, SM6) the ban on new equipment should be 2026, 24–52 kV 2030. Verify on EUR-Lex 2024/573. Reference only. | By 2032 | Getting phased out | <https://www.milesgroup.fr/en/blog/fin-sf6-appareillage-electrique-reglementation> |
| USA – California | No | **3** | CARB phase-out started 2025. Verify the dates by voltage tier. "The Americas have no SF6 regulation" is therefore not fully true. | Start 2025 | Getting phased out, allowed for very specific use | <https://www.climatepolicydashboard.org/policies/industry-materials-waste/sf6-regulations> |
| USA – federal | Yes | **0** | No federal ban found; check EPA reporting (GHGRP Subpart DD). Other states (incl. data-centre hotspots Virginia, Texas, Arizona, Ohio) to score from the state dashboard. | | Seems like there is no blanket regulation, no clear source on this !! | |
| Canada | Yes | **1** | SF6 is on the CEPA toxic list, which allows regulation; check whether a switchgear-specific rule or proposal exists, and what "a certain amount" refers to. | | Highly regulated, can only use a certain amount | <https://www.canada.ca/en/environment-climate-change/services/management-toxic-substances/list-canadian-environmental-protection-act/sulphur-hexafluoride.html> |
| UK | Yes | **1–2** | F-gas review covers SF6 in switchgear: check on gov.uk (DEFRA) whether the phase-out is adopted (→ 2) or only consulted on (→ 1). | | Regulated | <https://www.nuventura.com/news/sf6-regulations-whats-changing-2026-2035-and-where> |
| Japan | Yes | **0** | Voluntary reduction only. Check whether mandatory GHG reporting covers SF6. | | No regulations but voluntary reduction of SF6 use | <https://aktif.net/en/the-changing-landscape-of-sf6-regulation-a-global-overview/> |
| China | Yes | **0–1** | No phase-out; handling standards exist. 1 if SF6-specific rules are confirmed by a government source. | | No phase-out program but regulated | <https://www.sf6relations.com/china-sf6-gas-management-and-sf6-standard/> |
| South Korea | Yes | **0** | No SF6 rule. Check whether K-ETS covers SF6 (would make leaks cost real money: TCO argument). | | No official regulations but voluntary transition away from SF6 | <https://aktif.net/en/the-changing-landscape-of-sf6-regulation-a-global-overview/> |
| Australia | Yes | **0** | Reporting only (NGER). Check the synthetic-GHG import levy. | | Must report | <https://www.nuventura.com/news/sf6-regulations-whats-changing-2026-2035-and-where> |
| Singapore | Yes | **0–1** | Source is the NDC (a target, not a rule). Check whether the carbon tax covers SF6 and its price path. | | Highly regulated | <https://www.fao.org/faolex/fr/documents/LEX-FAOC219309/singapore-s-second-update-of-its-first-nationally-determined-sgp-2021> |
| India | No | **0–1** | Re-coded from "No": the only source is a vendor blog on potential carbon credits, and no ban was found. Coding it as banned would wrongly drop a data-centre hotspot from our voluntary scope. Check MoEFCC / CEA. | Reduce by 2030 | Phasing out | <https://www.nuventura.com/news/environmental-advantages-and-potential-carbon-credits-to-sf6-free-switchgear-in-the-indian-context> |
| UAE | Yes | **0–1** | "Increasing regulation" from a gas trader's article. Check the Ministry of Climate Change & Environment. | | Increasing regulation | <https://starfreighttrading.com/sf6-gas-in-uae-how-it-improves-high-voltage-equipment-performance/> |
| Saudi Arabia | Yes | **0–1** | Broad GHG rules only; no SF6-specific rule found. | | Some broad regulation on greenhouse gases | <https://albuad.sa/en/sf6-emissions-management/> |
| Brazil | Yes | **1** | New national ETS (SBCE) under way; check whether it covers SF6 and from when. | | Some broad regulation on greenhouse gases | <https://climatepolicydatabase.org/policies/brazilian-greenhouse-gas-emissions-trading-system-sbce> |
| Mexico | Yes | **0–1** | Broad GHG rules; pilot ETS status to check. Weak source (SF6 seller). | | Some broad regulation on greenhouse gases | <https://www.sulphurhexafluoride.com/blog/586.html> |

**Missing rows to add** (named in section 2.1 / 2.4 but not yet researched): US data-centre states (Virginia, Texas, Arizona, Ohio), Malaysia (Johor), Chile, Switzerland.


---

## 2. Competition – SF6-free medium-voltage offers

The PDF contains this table twice: a first, partly filled draft (section 2b) and a complete version (section 2a). The complete version is the one to use.

### 2a. Complete version

| Competitor | SF6-free product | Technology | Markets where sold | Price positioning | Still pushing SF6 there? | Source |
|---|---|---|---|---|---|---|
| **Schneider** | RM AirSeT / SM AirSeT | Pure-air insulation with vacuum interruption (Shunt Vacuum Interruption); solid insulation in selected ranges; IoT / digital monitoring | Global offering; primary and secondary distribution, utilities, industry, data centres, infrastructure and commercial buildings; up to 36 kV | Premium at initial purchase; positioned around sustainability, digitalisation and lower lifecycle cost / TCO; vendor data cited a roughly 15–20 % CAPEX premium for comparable SF6-free equipment | No, illegal | SE themselves |
| **Eaton** | Xiria / Xiria 630 / Xiria NGX; Power Xpert FMX, UX, UX36 | Vacuum switching with solid epoxy-resin insulation; compact air-GIS approach for secondary distribution | Sold in more than 60 countries; more than 3,000 reference sites; utility, industrial and critical-power applications; up to 24 kV for Xiria | ≈ +20 % vs SF6 in EU (I1) | | |
| **ABB** | SafeRing Air & SafePlus Air | Dry-air insulation with vacuum interruption; GWP = 0; same interface / footprint / operation as comparable SF6 versions | Global portfolio; secondary distribution up to 24 kV, with ZX0 up to 12 kV; targeted at most 6–24 kV switching applications | Likely premium upfront versus SF6 equivalents, but positioned as a like-for-like replacement with compliance and sustainability benefits; ABB continues selling both SF6 and SF6-free during transition | | |
| **Siemens** | Blue GIS portfolio: 8DAB 12, NXPLUS C 24; Siemens Energy 8VM1 / 8VM3 Blue GIS | "Clean Air" insulation (nitrogen / oxygen mixture) plus vacuum interrupters; zero-GWP, zero-toxicity insulation medium | Siemens Smart Infrastructure: public and industrial grids, secondary distribution, 12–24 kV. Siemens Energy: transmission / offshore wind and high-voltage applications, including 72.5 kV and 145 kV deployments | Premium technology positioning, emphasising compactness, reliability, low maintenance and zero-GWP clean-air insulation; commercial pricing is project / tender based | | |
| **Hitachi Energy** | EconiQ portfolio, including ELK-04 145 kV GIS, ELK-14 300 kV GIS, and EconiQ circuit breakers | Eco-efficient gas mixtures and vacuum-based interruption; scalable SF6-free high-voltage GIS and breakers | Global high-voltage transmission and large utility / grid markets; more than 4,000 units ordered across 40 countries; products span 72.5 kV to 550 kV | Premium, high-voltage / transmission-oriented offering; emphasises lifecycle carbon reduction, reliability, and compatibility with conventional SF6 equipment footprints | | |
| **Ormazabal** | cgm.zero24 and F-gas-free primary / secondary distribution ranges | Natural-origin gas / air-based insulation; F-gas-free GIS for primary and secondary networks up to 24 kV | Primarily public distribution networks; portfolio completed for primary and secondary distribution up to 24 kV; European / regional utility focus is implied by its F-gas transition messaging | Value-led, utility-focused positioning around accessible natural-origin gas and lower environmental impact; no public list pricing identified | | |
| **Lucy** | Sabre EcoTec; Aegis EcoTec; Nuventura-based primary dry-air GIS | Synthetic-air insulation for RMUs; dry-air technology from Nuventura for primary switchgear; vacuum interruption | Global MV distribution business active in more than 50 countries; offices / manufacturing in UK, UAE, Saudi Arabia, India, Thailand, South Africa and Brazil; utilities, renewables and grid infrastructure | Cost-effective performance and future-proofing positioning; no public list prices — sold through regional sales and project tenders | | |
