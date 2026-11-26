"""RM AirSeT market strategy in markets without an SF6 rule (Problem 2)."""

import pandas as pd
import streamlit as st

from app.ui import CSS, eur
from src.config import REPO_ROOT

st.markdown(CSS, unsafe_allow_html=True)
RM6_PRICE = 8740

win = pd.read_csv(REPO_ROOT / "report/problem2/03_tables/price_window.csv")
ceiling = win.groupby("segment")["ceiling_pct"].first()
order = ["Australia colocation", "Johor-Singapore data centres", "Australia utilities",
         "Gulf data centres"]

st.title("RM AirSeT market strategy")
st.caption("Markets without an SF6 rule. Price premiums in % of the RM6 price "
           f"({eur(RM6_PRICE)}); carbon at €22/t.")

with st.container(border=True):
    c1, c2 = st.columns(2)
    seg = c1.selectbox("Target segment", order)
    extra = c2.slider("AirSeT extra unit cost vs RM6 (%)", 0.0, 20.0, 10.0, 0.5,
                      help="Unknown today; the UK expects 5–10 % at scale.")

ceil = ceiling[seg]
margin = ceil - extra
with st.container(border=True):
    st.caption(f"RECOMMENDED PRICING · {seg}")
    if margin >= 0:
        st.markdown(f"#### TCO-based price: up to {ceil:.1f} % above RM6, "
                    f"{margin:.1f} pts more margin than RM6")
    else:
        st.markdown(f"#### Price at {ceil:.1f} % above RM6 and invest {-margin:.1f} pts of "
                    f"margin ({eur(-margin * RM6_PRICE / 100)} per unit)")
    st.markdown(f"Highest premium the customer's lifetime savings justify: **{ceil:.1f} %**. "
                f"Extra cost to cover: **{extra:.1f} %**.")
    st.markdown(f"↳ The margin investment ends when AirSeT's extra cost falls below "
                f"{ceil:.1f} %.")

st.subheader("All segments at this extra cost")
tab = pd.DataFrame({
    "Segment": order,
    "Highest justified premium": [f"{ceiling[s]:.1f} %" for s in order],
    "Margin vs RM6": [f"{ceiling[s] - extra:+.1f} pts" for s in order],
    "Decision": ["Profitable at TCO price" if ceiling[s] >= extra
                 else ("Invest margin (≤ 2 pts, temporary)" if extra - ceiling[s] <= 2
                       else "References only; lead with bundles and ESG") for s in order],
})
st.dataframe(tab, hide_index=True, width="stretch")

st.subheader("Win conditions")
st.dataframe(pd.DataFrame([
    ["W1", "AirSeT extra unit cost falls with volume", "< 9 % (Johor–SG), < 8 % (AU utilities)", "Unknown"],
    ["W2", "Customers count the whole SF6 fill", "Premium ceiling 0.4 % → ≈ 9 %", "1 of 11 operators"],
    ["W3", "Lead customer and reference site per region", "≥ 1 per region by end 2027", "None yet"],
    ["W4", "Customers accept an indexation clause (> 6 months)", "Most 9-month quotes", "Steel already bought on an index"],
    ["W5", "Margin investment capped and temporary", "≤ 2 pts per unit, ends at W1", "Decision variable"],
    ["W6", "Australian SF6 upkeep is real for owners", "≈ €50/yr per unit", "Unconfirmed"],
], columns=["#", "Condition", "Threshold", "Status today"]), hide_index=True, width="stretch")
