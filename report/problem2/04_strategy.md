# Problem 2 – Roadmap, win conditions and final story (Steps 9–10)

*Owner: Karin · Status: first version, BOM v1 numbers*

> **Sources:** E-numbers refer to rows of [`market_evidence/evidence.csv`](../../market_evidence/evidence.csv). Section numbers refer to the other Problem 2 reports: [01](01_market_and_regulation.md) (markets, regulation), [02](02_cost_and_tco.md) (cost gap, TCO), [03](03_value_and_pricing.md) (value proposition, pricing, levers). Problem 1 figures come from the Step 8 and Step 9 tables, regenerated on the corrected BOM (v1).
>
> No new code: this step combines the results of Steps 1–8 and Problem 1.

---

## Summary

**The client's question:** where SF6 is not banned, how does Schneider get customers to switch voluntarily from RM6 to RM AirSeT, and stay profitable?

**Our answer:**

1. **AirSeT's premium is not a raw-material problem.** With the corrected BOM, both units cost about the same in raw materials: RM6 €931, AirSeT €941. That €9 difference is 0.5 % of the €1,921 premium. The premium sits in components, process and volume.
2. **On cost alone, customers won't pay today's 22 % premium.** Over its life, AirSeT saves a customer €31 if only leaks count (02 §4). The premium a customer can justify rises to **≈ 9 % if it counts the whole SF6 fill** as a liability, and to ≈ 17 % where SF6 also costs it upkeep (Australia).
3. **So: price on TCO, segment by segment, and invest margin only where it buys volume.**
   - **Australia colocation:** profitable now at a TCO price of up to ≈ 16 %.
   - **Johor–Singapore data centres:** a TCO price of ≈ 9 % costs about 1 point of margin at a 10 % extra unit cost. That is the targeted investment, with AirTrunk as the lead customer.
   - **Gulf:** don't buy share there. Reference projects and future-proofing only.
4. **The investment pays back through volume, not raw materials.** It stops when AirSeT's extra unit cost vs RM6 falls below ≈ 9 %. The UK government review expects SF6-free premiums to fall to 5–10 % at scale (E166).
5. **Problem 1 protects the margin on the sharper price.** A 9-month AirSeT quote at a fixed price lost up to 3.3 points of margin on past prices. With a **copper + steel + stainless indexation clause**, at most 0.6 points.
6. **The biggest lever is not price but accounting:** getting data-centre operators to count the whole SF6 fill raises what they should accept from 0.4 % to ≈ 9 % (03 §8).

---

# Step 9 – Roadmap and win conditions

## 9.1 Margin investment: where it pays and where it doesn't

The client gives no margin target and asks how the recommendation changes with the constraint. Two numbers decide it:
- **AirSeT's extra unit cost vs RM6** (unknown; the client won't share a cost overview), and
- **the margin Schneider accepts to give up per unit** during the launch phase.

**AirSeT's margin vs RM6 at the TCO-based price**, in points of the RM6 price, for three levels of extra unit cost (from `03_tables/price_window.csv`). Negative = the margin Schneider invests per unit.

| Segment | TCO-based price | Extra cost 5 % | 10 % | 15 % | Profitable if extra cost below |
|---|---|---|---|---|---|
| Australia colocation | ≈ 16.6 % above RM6 | +11.5 | **+6.5** | +1.5 | **16.5 %** |
| Johor–Singapore data centres | ≈ 8.9 % | +3.9 | **−1.1** (≈ €95/unit) | −6.1 | **8.9 %** |
| Australia utilities | ≈ 8.0 % | +2.9 | **−2.0** (≈ €180/unit) | −7.0 | **7.9 %** |
| Gulf data centres | ≈ 0.4 % | −4.7 | **−9.7** (≈ €850/unit) | −14.7 | **0.3 %** |

Raw-material risk barely enters: on a 9-month quote, it costs AirSeT 0.03 points more than RM6 (Problem 1 Step 9, with indexation).

**Decision rule:**
- **Invest** where the gap is small and the segment builds volume or references: Johor–Singapore (≈ 1 point) and, later, Australian utilities (≈ 2 points).
- **Don't invest** where the gap is large: the Gulf would need ≈ 10 points per unit. Win there on future-proofing and reporting, not price (03 §7.4).
- **Cap the investment** in points per unit and in number of projects, and **end it** when the extra cost falls below the segment's threshold (last column).

## 9.2 Roadmap

| Phase | Markets and segments | What we do | Why now |
|---|---|---|---|
| **2027: prove** | **Australia colocation** | TCO-based price, just under Eaton | Profitable today; SF6 already costs a licence, a levy and upkeep (E25) |
| | **Johor–Singapore data centres** | TCO-based price (≈ 9 %), up to ≈ 1 point of margin invested, lead customer **AirTrunk** | AirTrunk already counts SF6 in Scope 1 and is exploring SF6-free (E85); no SF6-free rival found in Malaysia (E96) |
| | **Gulf** (Saudi Arabia, UAE) | 2–3 reference projects on private data-centre campuses; pilot with SEC | Fastest-growing market (≈ +59 %/yr); SEC's RMU specification still requires SF6 (E28) |
| | **All** | Copper + steel + stainless clause on quotes over 6 months; take-back and monitoring bundle; start "SF6 in Scope 1" work through iMasons (E113) | Protects the margin on a sharper price; builds the accounting lever |
| **2028–29: scale** | Johor–Singapore, Australia | **Framework agreements** with colocation operators and hyperscalers ("SF6-free" in their specification) | Locks in the volume that lowers AirSeT's extra cost |
| | **Australia utilities**, Japan utilities | TCO-based price (≈ 8 %) once extra cost < 8 %; until then, multi-year frameworks | Utilities are the only buyers already switching (E126) |
| | **Gulf** | Extend from references to framework agreements if SEC changes its specification | |
| **2030+: extend** | **US data-centre states** (Texas, Virginia), other APAC | Enter if a trigger fires (§9.5) | Rank 16–18 today: no customer pull, entrenched incumbents (01 §3.3) |
| | China | Opportunistic only | Ranks on size alone; local makers dominate (01 §3.4) |

## 9.3 Win conditions

What must be true for the strategy to work, and how we'd know.

| # | Win condition | Threshold | Status today | Source |
|---|---|---|---|---|
| W1 | AirSeT's extra unit cost vs RM6 falls with volume | < 9 % (Johor–Singapore), < 8 % (Australian utilities) | Unknown; UK expects 5–10 % at scale | 03 §7.2, E166 |
| W2 | Target customers count the **whole SF6 fill** (or have their own SF6 policy) | Ceiling rises from 0.4 % to ≈ 9 % | 1 of 11 operators (AirTrunk) | 01 §7, E85 |
| W3 | A lead customer and reference site in each priority region | ≥ 1 per region by end 2027 | None yet | 03 §8.2 |
| W4 | Customers accept an indexation clause on quotes over 6 months | Clause on most 9-month AirSeT quotes | Schneider already buys steel on an index | P1 Step 9 |
| W5 | Margin investment stays capped and temporary | e.g. ≤ 2 points per unit, ended at W1's threshold | Decision variable | §9.1 |
| W6 | Australian SF6 upkeep is real for owners | ≈ €50/yr per unit | Rules found target imports, not owners | 03 §7.2 caveat |

If **W6** fails, Australia colocation's ceiling falls from 16.6 % to 8.9 %, the same as Johor–Singapore.

## 9.4 KPIs

| KPI | Why |
|---|---|
| AirSeT share of quotes and orders, per target segment | The success measure of the strategy |
| Win rate against Eaton (Australia, Singapore) and against RM6 | Is the TCO-based price competitive? |
| Realised AirSeT margin vs RM6, in points | Is the investment within its cap? |
| AirSeT extra unit cost vs RM6 | When the investment can stop (W1) |
| Share of 9-month quotes with an indexation clause | Margin protection (W4) |
| Operators counting the whole SF6 fill | The accounting lever (W2) |
| t CO₂e avoided (≈ 35 t per unit replacing an RM6) | The ESG story for customers and Schneider |

## 9.5 Triggers to accelerate or pause

| Trigger | Action |
|---|---|
| A target country adopts an SF6 rule (status ≥ 2) | Move it to "prove"; raise the price toward the regulated-market level |
| A hyperscaler writes "SF6-free" into its global specification | Framework agreement first, then its sites in every target market |
| AirSeT's extra cost falls below a segment's threshold | End the margin investment there; price at TCO |
| Extra cost not falling after two years of framework volume | Pause the investment; keep only references |
| A low-cost dry-air rival (CHINT, Rockwill) enters a target market | Compete on service bundle and references, not price |
| Raw-material cost gap moves by > 1 point of price | Re-check prices. To mid-2027, the P90 move is 0.5 points (P1 Step 9), so this is unlikely |

---

# Step 10 – Final story

## 10.1 One engine, two outcomes

The client's chain: **RM forecast → BOM exposure → product-cost evolution → margin at risk → pricing decision → AirSeT market strategy**. One number per link:

| Link | Result | Where |
|---|---|---|
| **1. RM forecast** | The median is no better than "no change", but the P10–P90 band is calibrated (80–84 % coverage on the hold-out) and narrower than the naive forecast's | P1 Steps 6–7 |
| **2. BOM exposure** | RM6 €931, copper 52 %. AirSeT €941, copper 38 %, steel and stainless 52 % | P1 Step 2 (BOM v1) |
| **3. Product-cost evolution** | To June 2027: P50 +2–3 %; P90 €1,098 (RM6), €1,105 (AirSeT) | P1 Step 8 |
| **4. Margin at risk** | A 9-month fixed price risks 1.9 points (RM6) and 1.6 points (AirSeT) at P90 | P1 Step 8 |
| **5. Pricing decision** | Up to 6 months: fixed price + uplift (≤ 1 point). 9 months: indexation clause (±10–15 %) + uplift of 0.8–1.0 points. AirSeT's clause follows copper, steel and stainless: worst past loss 0.6 points, against 3.3 at a fixed price | P1 Step 9 |
| **6. AirSeT strategy** | Raw materials explain 0.5 % of the premium and won't converge (gap moves €7 at P50 to mid-2027). So: TCO-based price per segment, targeted margin investment where volume follows, and the clause from link 5 to protect the sharper price | This report, 02, 03 |

**The message for the jury:** the same engine that tells sales how to price a 9-month quote also tells strategy how much margin AirSeT can afford to give up. The forecast doesn't make AirSeT cheaper. It makes a sharper AirSeT price safe.

## 10.2 Hypotheses: what we found

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | Global data-centre operators apply one SF6-free standard worldwide | **Not supported** | 9 of 11 never mention SF6 (01 §7) |
| H2 | Some non-EU markets will regulate SF6 soon | **Partly** | Bans only in the EU, Switzerland, California; phase-out in New York; rules short of a ban in the UK and Australia (01 §5) |
| H3 | TCO favours AirSeT once the whole SF6 fill is valued | **Supported, at a ≈ 9 % premium, not 22 %** | Break-even €54/t on the whole fill vs €1,657/t on leaks (02 §4) |
| H4 | The raw-material outlook narrows the cost gap | **Not supported** | Right direction (RM6 rises more in 59 % of paths) but €7 at P50: 0.3 % of the premium (02 §5, P1 Step 9) |
| H5 | AirSeT can be priced closer to RM6 without losing margin | **Partly** | Yes in Australia colocation; elsewhere only once extra cost falls below 8–9 % (§9.1) |
| H6 | The EU price convergence will repeat elsewhere | **Through volume, not raw materials** | EU convergence came from the ban (02 §5); UK expects 5–10 % premiums at scale (E166) |

## 10.3 Problem 2 in the final presentation (8 slides)

1. **The question:** voluntary switch, profitably. Today's 22 % premium against a customer saving of €31.
2. **Raw materials aren't the reason:** RM6 €931 vs AirSeT €941; the forecast moves the gap by €7.
3. **How customers count SF6 decides the price:** 0.4 % (leaks) → ≈ 9 % (whole fill) → ≈ 17 % (with upkeep).
4. **Where to play:** Johor–Singapore, Australia, Gulf (scoring and stability, 01 §3).
5. **Value proposition per segment** (03 §6).
6. **Price window and margin investment:** the §9.1 table; the "profitable if extra cost below" column.
7. **Roadmap, win conditions and triggers** (§9.2–9.5).
8. **One engine, two outcomes:** the §10.1 chain, with the clause as the bridge.

## 10.4 Limits

- **AirSeT's unit cost is unknown.** We show the threshold extra cost at which each segment works, not one answer.
- **Synthetic, EU-only price data.** The AirSeT premium is proxied by Eaton (+22 %), and the willingness to pay (+20 %) comes from EU buyers (E173).
- **Unknown BOM lines stay unpriced:** 56 kg of "Other" on AirSeT, 5.6 kg on RM6, plus plastics.
- **External facts have ranges**, each with a source and date in `evidence.csv`. No customer interviews.
- **The 2027 phase rests on one lead customer** (AirTrunk), approached through its public report only.
