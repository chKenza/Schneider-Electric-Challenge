"""Quote pricing: recommended quote terms first, then the stepwise analysis."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.ui import (BAND, CSS, GROUP_COLORS, INK, MUTED, SCENARIO, base_fig, chart,
                    chart_title, eur, month_label)
from app.ui import action_text as ui_action_text
from src import quote_engine as q
from src.simulation import HORIZONS

SOURCES = {
    "Copper": "LME copper, cash settlement price, monthly average, converted to €/t "
              "(LME via Westmetall; ECB exchange rate).",
    "Carbon steel": "MEPS cold-rolled steel coil, €/t ({country}); licensed data provided by "
                    "Schneider Electric.",
    "Stainless steel": "CRU stainless steel 304, Germany, base price + alloy surcharge, €/t; "
                       "licensed data provided by Schneider Electric. Latest month: Aug 2026.",
    "Epoxy": "Epoxy resin, Europe, €/t; price file provided by Schneider Electric.",
    "Aluminium": "LME aluminium, cash settlement price, monthly average, converted to €/t "
                 "(LME via Westmetall; ECB exchange rate).",
}


@st.cache_resource(show_spinner="Loading simulated price paths…")
def warm_up():
    q.sims()
    return True


warm_up()
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------- state
DEFAULTS = {"basis": "Forecast", "confidence": 90, "max_uplift": 1.0,
            **{f"pct_{g}": 0 for g in q.GROUPS}}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def back_to_forecast():
    st.session_state.basis = "Forecast"


def set_preset(values: dict):
    for g in q.GROUPS:
        st.session_state[f"pct_{g}"] = int(round(values.get(g, 0)))


# ---------------------------------------------------------------- inputs
left, right = st.columns([2, 1], vertical_alignment="bottom")
left.title("ETO Quote Risk & Pricing")
right.caption("Raw-material prices up to Sep 2026 · forecast to Jun 2027")

with st.container(border=True):
    c = st.columns([1.1, 1.7, 0.8, 0.9], gap="medium")
    product = c[0].segmented_control("Product", ["RM6", "RM AirSeT"], default="RM6") or "RM6"
    h = c[1].segmented_control("Quotation validity", HORIZONS, default=9,
                               format_func=lambda x: f"{x} months") or 9
    price = c[2].number_input("Selling price (€/unit)", min_value=1000.0, step=100.0,
                              value=float(q.BASE_PRICE[product]), format="%.0f",
                              key=f"price_{product}")
    tol = c[3].number_input(
        "Acceptable margin loss (pts)", min_value=0.0, max_value=3.0, value=0.5, step=0.05,
        format="%.2f", key="tol",
        help="Largest raw-material margin loss you accept on this quote, in points of the "
             "selling price (1 pt = 1 % of the price), at the confidence level set in "
             f"Advanced parameters. At the current price, "
             f"{st.session_state.get('tol', 0.5):.2f} pts = "
             f"{eur(st.session_state.get('tol', 0.5) * st.session_state.get(f'price_{product}', q.BASE_PRICE[product]) / 100)} per unit.")
    d1, d2 = st.columns([3, 1], vertical_alignment="center")
    clause_ok = d1.toggle("Customer accepts an indexation clause", value=True)
    with d2.popover("Advanced parameters", width="stretch"):
        st.slider("Confidence level (%)", 80, 97, key="confidence",
                  help="How sure you want to be that the loss stays within your acceptable "
                       "margin loss. 90 % means it stays within it in 9 quotes out of 10.")
        st.slider("Max. uplift the customer accepts (pts)", 0.25, 2.0, step=0.05,
                  key="max_uplift",
                  help="Largest price increase we assume the customer accepts. Above it, the "
                       "recommendation switches to an indexation clause or a shorter validity.")

conf = st.session_state.confidence / 100
max_up = st.session_state.max_uplift
scenario = st.session_state.basis == "Custom scenario"
pct = {g: st.session_state[f"pct_{g}"] for g in q.GROUPS}
month = month_label(h)

t = q.quote_terms(product, h, price, tol, conf, max_up, clause_ok)
rec = t.recommended
top = t.drivers.idxmax()
top_share = 100 * t.drivers.max() / t.drivers.sum()
scen = q.scenario_result(t, pct) if scenario else None

# ------------------------------------------------------- scenario banner
if scenario:
    moved = ", ".join(f"{g} {v:+d} %" for g, v in pct.items() if v) or "no price change set yet"
    with st.container(key="scenario_banner"):
        b1, b2 = st.columns([5, 1], vertical_alignment="center")
        b1.markdown(f"CUSTOM SCENARIO · {moved} by {month} · not a forecast")
        b2.button("Return to forecast", on_click=back_to_forecast, width="stretch")


# --------------------------------------------------------- recommendation
def action_text(o) -> str:
    return ui_action_text(t, o)


# the sidebar assistant answers from these inputs
st.session_state.asst_ctx_quote = dict(product=product, h=h, price=price, tol=tol, conf=conf,
                                       max_up=max_up, clause_ok=clause_ok, scenario=scenario,
                                       pct=pct)

st.subheader("Recommendation")
col_q, col_a = st.columns(2)

with col_q.container(border=True, key="scen_quote" if scenario else "card_quote"):
    st.caption(f"RECOMMENDED QUOTE TERMS · {product}, valid {h} months")
    if not rec.fits:
        st.markdown(f"#### No option stays under the {max_up:.2f} pt maximum uplift")
        st.markdown(f"Least costly: {action_text(rec).lower()}. "
                    "Discuss a copper hedge with procurement (see options).")
    else:
        st.markdown(f"#### {action_text(rec)}")
    st.markdown(
        f"Price adjustment **{rec.adjustment:.2f} pts** (expected cost increase) · "
        f"Risk buffer **{rec.buffer:.2f} pts** · Main driver: **{top}** "
        f"({top_share:.0f} % of the cost increase)")
    st.markdown(f"↳ {q.what_would_change(t)}")

    if scenario:
        st.markdown("**Tested on your custom scenario**")
        tab = scen["table"][~scen["table"].option.str.startswith("Fixed price, valid")].copy()
        tab["Margin result"] = tab.result.map(lambda x: f"{x:+.2f} pts ({eur(x * price / 100)})")
        tab["Within your acceptable loss"] = np.where(tab.result >= -tol, "Yes", "No")
        st.dataframe(tab[["option", "Margin result", "Within your acceptable loss"]]
                     .rename(columns={"option": "Option"}), hide_index=True, width="stretch")
        st.caption(f"In our simulations, a cost increase this large or larger happens in "
                   f"{100 * scen['share_worse']:.0f} % of cases.")

    with st.expander("Compare options"):
        opt = pd.DataFrame([{
            "Option": o.name + (" (recommended)" if o is rec else ""),
            "Uplift needed": f"{o.uplift:.2f} pts ({eur(t.eur(o.uplift))})",
            f"Within max. uplift ({max_up:.2f} pts)": "Yes" if o.fits else "No",
        } for o in t.options])
        st.dataframe(opt, hide_index=True, width="stretch")
        st.caption(
            f"Uplift needed so the loss stays within {tol:.2f} pts at {conf:.0%} confidence. "
            "The copper hedge is a procurement lever: copper is bought forward when the quote "
            "is signed.")

# AirSeT card: cost-gap change between the two products on the same price paths
gap = (q.sims()[("RM AirSeT", h)][0].sum(axis=1) - q.sims()[("RM6", h)][0].sum(axis=1))
gap_p50, gap_bad = gap.median(), gap.quantile(conf)
gap_pts = 100 * gap_bad / q.BASE_PRICE["RM6"]
with col_a.container(border=True, key="scen_airset" if scenario else "card_airset"):
    st.caption("RM AIRSET MARKET STRATEGY · markets without an SF6 rule")
    st.markdown("#### " + (
        f"The AirSeT–RM6 cost gap stays stable to {month}, so the AirSeT pricing plan holds"
        if gap_pts < 1 else
        f"The AirSeT–RM6 cost gap could move by {gap_pts:.1f} pts by {month}: review AirSeT prices"))
    st.markdown(f"Change in the raw-material cost gap by {month}: expected "
                f"{gap_p50:+,.0f} €, at most {gap_bad:+,.0f} € ({gap_pts:.2f} pts of the RM6 price) "
                f"at {conf:.0%} confidence.")
    if scenario:
        g = q.scenario_gap_change(h, pct)
        st.markdown(f"**Under your custom scenario:** the gap changes by {g:+,.0f} € "
                    f"({100 * g / q.BASE_PRICE['RM6']:+.2f} pts).")
    st.markdown("Start with **Australia colocation** (profitable at a TCO-based price today) "
                "and **Johor–Singapore data centres** (up to about 1 pt of margin invested).")
    st.page_link("airset_page.py", label="Open the RM AirSeT strategy ›")

# ------------------------------------------------------ stepwise analysis
st.write("")
s1, s2 = st.columns([3, 2], vertical_alignment="bottom")
s1.subheader("Stepwise analysis")
s2.segmented_control("Price basis", ["Forecast", "Custom scenario"], key="basis")


def how(text: str):
    with st.popover("How we calculated this"):
        st.markdown(text)


def end_label(fig, x, y, text, color=INK, yshift=0):
    fig.add_annotation(x=x, y=y, text=text, showarrow=False, xanchor="left", xshift=8,
                       yshift=yshift, font=dict(color=color, size=12))


steps = st.container(key="steps")

# 1  Raw-material price forecast
with steps.expander("1\\. Raw-material price forecast", expanded=scenario):
    if scenario:
        a, b = st.columns([1, 2])
        with a:
            st.markdown("**Price change by delivery**")
            for g in q.GROUPS:
                st.slider(g, -40, 80, step=1, format="%d %%", key=f"pct_{g}")
            st.button("Reset all to 0 %", on_click=set_preset, args=({},))
        chart_col = b
        group = max(pct, key=lambda g: abs(pct[g])) if any(pct.values()) else top
    else:
        group = st.segmented_control("Material", q.GROUPS, default=top, key="fan_group") or top
        chart_col = st.container()

    hist, fan = q.price_fan(product, group)
    last_x, last_y = hist.index[-1], hist.iloc[-1]
    end = fan.iloc[-1]
    with chart_col:
        chart_title(f"{group} price (€ per tonne): last 24 months and forecast to {month_label(9)}")
        fig = base_fig(right=170)
        fig.add_trace(go.Scatter(
            x=[last_x, *fan.month, *fan.month[::-1], last_x],
            y=[last_y, *fan.p90, *fan.p10[::-1], last_y],
            mode="lines", fill="toself", fillcolor=BAND, line=dict(width=0), hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=hist.index, y=hist.values, mode="lines", name="Actual",
                                 line=dict(color=GROUP_COLORS[group], width=2),
                                 hovertemplate="€%{y:,.0f}"))
        for col, name in (("p90", "Upper end"), ("p50", "Expected"), ("p10", "Lower end")):
            fig.add_trace(go.Scatter(
                x=[last_x, *fan.month], y=[last_y, *fan[col]], name=name,
                mode="lines+markers" if col == "p50" else "lines",
                line=dict(color=GROUP_COLORS[group] if col == "p50" else "rgba(0,0,0,0)",
                          dash="dot"),
                hovertemplate="€%{y:,.0f}"))
        end_label(fig, end.month, end.p90, f"Upper end €{end.p90:,.0f}", MUTED)
        end_label(fig, end.month, end.p50, f"Expected €{end.p50:,.0f}", GROUP_COLORS[group])
        end_label(fig, end.month, end.p10, f"Lower end €{end.p10:,.0f}", MUTED)
        end_label(fig, last_x, last_y, f"Sep 2026 €{last_y:,.0f}", INK, yshift=16)
        if scenario and pct[group]:
            target = pd.Timestamp(last_x) + pd.DateOffset(months=h)
            yv = last_y * (1 + pct[group] / 100)
            fig.add_trace(go.Scatter(x=[last_x, target], y=[last_y, yv], name="Your scenario",
                                     mode="lines+markers", line=dict(color=SCENARIO, width=2),
                                     marker=dict(size=[0, 10]), hovertemplate="€%{y:,.0f}"))
            end_label(fig, target, yv, f"Your scenario €{yv:,.0f}", SCENARIO, yshift=14)
        fig.update_yaxes(title="€ per tonne", tickformat=",.0f")
        chart(fig)

    lo_g, mid_g, hi_g = q.group_change_range(product, h, group)
    row = fan.iloc[HORIZONS.index(h)]
    st.markdown(
        f"There is an 80 % chance that the {group.lower()} price in {month} lies between "
        f"**€{row.p10:,.0f}** and **€{row.p90:,.0f}** ({lo_g:+.0f} % to {hi_g:+.0f} % vs Sep 2026, "
        f"shaded area). The expected price is €{row.p50:,.0f}.")
    country = "France" if product == "RM6" else "Germany"
    st.caption("Source: " + SOURCES[group].format(country=country))
    how("We forecast each material's price at 3, 6 and 9 months, as an expected value and an "
        "80 % range. In back-tests on past data, the real price fell inside this range 80–84 % "
        "of the time, as it should. The expected value is close to today's price: no model "
        "predicts the direction reliably, but the width of the range is what sets the risk "
        "buffer.\n\nWe then simulate 10,000 joint price paths that keep the usual co-movement "
        "between materials (for example copper and aluminium).")

# 2  BOM cost exposure
dh = q.drivers_by_horizon(product, conf)
base0 = q.by_group(q.sims()[(product, h)][1].iloc[[0]]).iloc[0]
with steps.expander("2\\. BOM cost exposure"):
    st.markdown(f"For {product}, **{top}** drives {top_share:.0f} % of the possible cost "
                f"increase, so it is the material to protect in the quote.")
    a, b = st.columns(2)
    with a:
        chart_title(f"Raw-material cost of one {product} today: {eur(base0.sum())}")
        fig = base_fig(top=40, right=60)
        for g in q.GROUPS[::-1]:
            fig.add_trace(go.Bar(y=[g], x=[base0[g]], orientation="h", name=g,
                                 marker_color=GROUP_COLORS[g], text=[eur(base0[g])],
                                 textposition="outside", cliponaxis=False,
                                 hovertemplate="€%{x:,.0f}<extra></extra>"))
        fig.update_layout(hovermode="closest", bargap=0.4)   # bar ≈ 30 px, as on the right
        fig.update_xaxes(title="€ per unit")
        chart(fig)
    with b:
        chart_title(f"Possible cost increase by quotation validity ({conf:.0%} confidence)")
        fig = base_fig(top=40, right=60)
        for g in q.GROUPS:
            fig.add_trace(go.Bar(y=[f"{x} months" for x in dh.index], x=dh[g], name=g,
                                 orientation="h", marker_color=GROUP_COLORS[g],
                                 hovertemplate=g + ": €%{x:,.0f}<extra></extra>"))
        totals = dh.sum(axis=1)
        fig.add_trace(go.Scatter(y=[f"{x} months" for x in dh.index], x=totals, mode="text",
                                 text=[eur(v) for v in totals], textposition="middle right",
                                 hoverinfo="skip", showlegend=False, cliponaxis=False))
        fig.update_layout(barmode="stack", showlegend=True, hovermode="closest", bargap=0.63)
        fig.update_xaxes(title="€ per unit")
        chart(fig)
    how("Cost today = mass of each material in the bill of materials (BOM v1, provided by "
        "Schneider Electric) × its price in Sep 2026. Possible increase = average € change per "
        f"material on the simulated paths where the total cost lands near the {conf:.0%} level. "
        "Plastics and unidentified mass (RM6 5.6 kg, RM AirSeT 56 kg) have no price series and "
        "are left out.")

# 3  Unit cost outlook
co = q.cost_outlook(product, conf)
today = co.today.iloc[0]
with steps.expander("3\\. Unit cost outlook"):
    bad_h = co.set_index("h").loc[h, "bad"]
    st.markdown(f"The raw-material cost of one {product} is {eur(today)} today. By {month} it "
                f"is expected at {eur(co.set_index('h').loc[h, 'p50'])}, and could reach "
                f"**{eur(bad_h)}** ({conf:.0%} confidence).")
    xs = ["Sep 2026", *[month_label(x) for x in co.h]]
    chart_title(f"Raw-material cost of one {product} (€ per unit)")
    fig = base_fig(right=190)
    fig.add_trace(go.Scatter(x=xs + xs[::-1], y=[today, *co.bad, *co.p10[::-1], today],
                             mode="lines", fill="toself", fillcolor=BAND, line=dict(width=0), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=xs, y=[today, *co.bad], mode="lines", name="High case",
                             line=dict(color=INK, dash="dot"), hovertemplate="€%{y:,.0f}"))
    fig.add_trace(go.Scatter(x=xs, y=[today, *co.p50], mode="lines+markers", name="Expected",
                             line=dict(color=INK, width=2), hovertemplate="€%{y:,.0f}"))
    fig.add_trace(go.Scatter(x=xs, y=[today, *co.p10], mode="lines", name="Low case",
                             line=dict(color=MUTED, dash="dot", width=1),
                             hovertemplate="€%{y:,.0f}"))
    end_label(fig, xs[-1], co.bad.iloc[-1], f"High case ({conf:.0%}) €{co.bad.iloc[-1]:,.0f}")
    end_label(fig, xs[-1], co.p50.iloc[-1], f"Expected €{co.p50.iloc[-1]:,.0f}")
    end_label(fig, xs[-1], co.p10.iloc[-1], f"Low case (10 %) €{co.p10.iloc[-1]:,.0f}", MUTED)
    if scenario:
        yv = scen["cost_today"] + scen["eur_change"]
        fig.add_trace(go.Scatter(x=[month], y=[yv], mode="markers", name="Your scenario",
                                 marker=dict(color=SCENARIO, size=12), hovertemplate="€%{y:,.0f}"))
        end_label(fig, month, yv, f"Your scenario €{yv:,.0f}", SCENARIO, yshift=14)
    fig.update_yaxes(title="€ per unit", tickformat=",.0f")
    chart(fig)
    how("Sum over all priced materials of today's cost × simulated price change, on each of "
        f"the 10,000 paths. Expected = middle path; high case = {conf:.0%} level; low case = "
        "10 % level.")

# 4  Margin at risk
with steps.expander("4\\. Margin at risk"):
    rows = []
    for x in HORIZONS:
        tx = t if x == h else q.quote_terms(product, x, price, tol, conf, max_up, clause_ok)
        drift = max(0.0, tx.loss_median)
        rows.append({"h": x, "drift": drift, "risk": max(0.0, tx.loss_q - drift), "total": tx.loss_q})
    mr = pd.DataFrame(rows)
    a, b = st.columns([3, 2])
    with a:
        chart_title(f"Margin at risk without protection, {product} ({conf:.0%} confidence)")
        fig = base_fig(top=40)
        labels = [f"{x} months" for x in mr.h]
        opac = [1.0 if x == h else 0.45 for x in mr.h]
        fig.add_trace(go.Bar(x=labels, y=mr.drift, name="Expected cost increase",
                             marker=dict(color=INK, opacity=opac),
                             hovertemplate="%{y:.2f} pts<extra></extra>"))
        fig.add_trace(go.Bar(x=labels, y=mr.risk, name="Uncertainty",
                             marker=dict(color="#8C8F99", opacity=opac),
                             hovertemplate="%{y:.2f} pts<extra></extra>"))
        fig.add_trace(go.Scatter(x=labels, y=mr.total, mode="text", showlegend=False,
                                 text=[f"{v:.2f} pts ({eur(v * price / 100)})" for v in mr.total],
                                 textposition="top center", hoverinfo="skip", cliponaxis=False))
        fig.add_hline(y=tol, line=dict(color=INK, dash="dash", width=1),
                      annotation_text=f"Your acceptable loss: {tol:.2f} pts",
                      annotation_position="top left")
        if scenario:
            sl = scen["eur_change"] * 100 / price
            fig.add_hline(y=sl, line=dict(color=SCENARIO, width=2),
                          annotation_text=f"Your scenario: {sl:.2f} pts",
                          annotation_font_color=SCENARIO, annotation_position="bottom right")
        fig.update_layout(barmode="stack", showlegend=True, hovermode="closest")
        fig.update_yaxes(title="margin points", range=[0, max(mr.total.max(), tol) * 1.3])
        chart(fig)
    with b:
        st.write("")
        st.metric(f"Margin at risk, {h}-month quote", f"{t.loss_q:.2f} pts",
                  help=f"Largest margin loss at {conf:.0%} confidence if the price is fixed "
                       "with no uplift.")
        st.caption(f"= {eur(t.eur(t.loss_q))} per unit")
        st.metric("Quotes that would exceed your acceptable loss", f"{100 * t.p_over_limit:.0f} %",
                  help="Share of simulated price paths where a fixed price with no uplift loses "
                       "more than your acceptable margin loss.")
        st.markdown("The **price adjustment** covers the expected cost increase. The **risk "
                    "buffer** or an **indexation clause** covers the uncertainty, down to your "
                    "acceptable loss.")
    how("Margin points lost = raw-material cost change ÷ selling price × 100, on each simulated "
        "path. The recommendation then picks the simplest protection that keeps the loss within "
        f"your acceptable loss at {conf:.0%} confidence: fixed price with an uplift, then an "
        "indexation clause, then a shorter validity.")

# ----------------------------------------------------------- assumptions
st.write("")
with st.expander("Data and assumptions"):
    st.markdown(
        "- Steel priced with market (MEPS) volatility; stainless steel includes the nickel "
        "alloy surcharge.\n"
        "- Bill of materials: BOM v1 from Schneider Electric. Unpriced lines: plastics and "
        "unidentified mass (RM6 5.6 kg, RM AirSeT 56 kg).\n"
        "- Selling prices: RM6 €8,740 (price benchmark); RM AirSeT assumed RM6 + 20 %.\n"
        "- Raw materials only; all other costs held constant.")
