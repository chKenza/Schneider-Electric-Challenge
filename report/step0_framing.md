# Step 0 – Framing the problem

*Owner: Karin · Status: draft, to update after the client Q&A*

---

## 1. The problem in one paragraph

Schneider sells two medium-voltage switchgear units to data-centre customers:

- **RM6**, made at **SFCME** in France
- **RM AirSeT**, made at **Duna Smart Power Systems** in Hungary

The price is **fixed for 3, 6 or 9 months**, but copper, steel and other materials keep moving, so every offer is a "margin gamble". AirSeT has a higher cost and a thinner margin, so it is the more exposed of the two.

**Our goal:** for each product and horizon, estimate how much material cost could rise. Then turn that into a **pricing rule**: a risk buffer, an indexation clause or a hedge that keeps the margin above target with a chosen confidence (e.g. 90 %).

---

## 2. The decision to frame

| Element | What we need to decide | Status |
|---|---|---|
| Target margin | Margin to protect, per product | Unknown → Q2 |
| Confidence level | How often a margin breach is acceptable (P80 / P90 / P95) | Unknown → Q5 |
| Decision supported | Price buffer, indexation clause, hedging, or shorter validity | Unknown → Q4, Q5 |
| Exposure period | Time from quote to material purchase, not the full validity | Unknown → Q3 |

---

## 3. What the data already tells us about purchasing

From `Copia de Europe Steel INDEXES.xlsx` (sheets *Reference to Index Mapping*, *Q4-2017*, *Q2-2018*, *UPDATE*):

- Schneider buys steel **on an index**: each part (663 in total) is linked to a MEPS/CRU index (e.g. "CR Germany").
- Purchase price = base price + the index change in €/t.
- Prices were updated **monthly in 2017**, then **quarterly from 2018**.
- **Lead time: 1 month** for most parts.
- Hungarian plants are priced on **German indices**.
- The price change passed on is **negotiated per plant**, not copied 1:1 from the index.

⚠️ **Limit:** the file covers **2016–2018** and **does not include SFCME or Duna**. It shows how Schneider bought steel in general, not necessarily how these two plants buy it today (→ Q10).

---

## 4. Other points the client needs to clarify

Each point comes from a first look at the files. The details are in the Step 1 and Step 2 notes.

| What we saw | Question |
|---|---|
| The file with selling prices is locked ("Confidential – Internal to SE") | Q1 |
| The two RM6 BOMs disagree on copper: 38.8 kg vs ≈ 10 kg | Q6 |
| RM6: only 41 % of the mass has a material label | Q6 |
| AirSeT lists no copper and has 13.6 % "Other" | Q7 |
| The RM6 teardown cost breakdown can't be used to split fixed vs variable cost | Q8 |
| The brief mentions electronics, but there is no data on them | Q9 |

---

## 5. Working assumptions (until the client confirms)

| Topic | Assumption |
|---|---|
| Target margin | Kept as a parameter (e.g. 25 % RM6, 15 % AirSeT) |
| Confidence level | P90 as the base case; P75 and P95 also shown |
| Exposure | From quote to material purchase, roughly H minus 1 month |
| Steel purchasing | On index, 1-month lag, monthly or quarterly updates |
| Copper purchasing | LME price + a premium |
| Customer contracts | No indexation clause and no hedging today |
| BOM | RM6's unlabelled slice is carbon steel; AirSeT has no copper |
| Scope | Raw materials only (no labour, plant energy or electronics) |

---

## 6. Questions for the client

### Top priority (these change the answer)

1. Can we get an **unlocked copy** of the RMU price benchmark file? What is in it?
2. What is the **target margin** for RM6 and for AirSeT?
3. How long after signing is the **material bought** or its price locked?
4. Do customer contracts already have **indexation clauses**? Does Schneider **hedge** copper or nickel?
5. What **confidence level** does sales want (P80 / P90 / P95), and in what form (a % added to the price, or a price)?

### BOM and costs

6. RM6 copper: is it **38.8 kg or about 10 kg**? Is the unlabelled 45 % carbon steel?
7. AirSeT: really **no copper**? Where are the epoxy insulation and vacuum interrupters? What is the 13.6 % "Other"?
8. What share of unit cost is **raw material** vs bought components, labour and overhead?
9. The brief mentions **electronics**. Is that in scope? Is there data on it?

### Purchasing

10. Do **SFCME and Duna** buy steel with the same index system today? Which supplier and index?
11. How is **copper** priced in purchases (which LME average, which premium)?
12. Which is closer to what Schneider actually pays: **market prices** (LME/MEPS) or the **PPI** indices?

### Deliverable

13. Only these two products, or a method for all ETO products?
14. Should the final output be a **tool for sales** (app), a report, or both?

> **If time is short, ask 1, 3, 4 and 6.**

---

## 7. Next steps

- Update this report after the Q&A.
- Step 1: data inventory and clean monthly panel (see `step1_notes.md`).
- Step 2: cost formula per product (see `step2_notes.md`).
