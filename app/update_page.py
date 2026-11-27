"""Monthly update: replay a held-back month, or add a new month of prices and rerun."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.ui import (
    BAND,
    CSS,
    INK,
    MUTED,
    SE_GREEN,
    action_text,
    base_fig,
    chart,
    chart_title,
    eur,
)
from src import monthly_update as mu
from src import quote_engine as q
from src.pipeline import NAMES as STAGES

st.markdown(CSS, unsafe_allow_html=True)
st.markdown(f"""<style>
.st-key-card_hit {{ border-top: 4px solid {SE_GREEN} !important; }}
.st-key-card_miss {{ border-top: 4px solid #B42318 !important; }}
</style>""", unsafe_allow_html=True)
LAST = pd.Timestamp(q.p.ORIGIN)          # last month of data in the submitted forecast
RED = "#B42318"


def mlabel(m) -> str:
    return pd.Timestamp(m).strftime("%b %Y")


def seur(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}€{abs(x):,.0f}"


def plus(m, h) -> pd.Timestamp:
    return pd.Timestamp(m) + pd.DateOffset(months=h)


left, right = st.columns([2, 1], vertical_alignment="bottom")
left.title("Monthly update")
right.caption("Prices up to Sep 2026 · replay a past month or add a new one")

tab_replay, tab_new = st.tabs(["Replay a past month", "Add a new month"])

# ================================================================ replay
with tab_replay:
    st.caption("Quote as if it were that month: forecasts made with only the data known then "
               "(walk-forward backtest, final model), then compare with what happened.")
    months = q.replay_months()
    with st.container(border=True):
        c = st.columns([1.1, 1.2, 1.6, 0.9], gap="medium")
        product = c[0].segmented_control("Product", ["RM6", "RM AirSeT"], default="RM6",
                                         key="rp_product") or "RM6"
        origin = c[1].selectbox("Quote month", months[::-1], format_func=mlabel, key="rp_month",
                                index=months[::-1].index("2025-12"))
        ds = q.Dataset(origin=origin, replay=True)
        with st.spinner(f"Simulating 10,000 price paths as of {mlabel(origin)}…"):
            hs = [h for h in ds.horizons if plus(origin, h) <= LAST]
        h = c[2].segmented_control("Quotation validity", hs, default=hs[-1], key=f"rp_h_{len(hs)}",
                                   format_func=lambda x: f"{x} months") or hs[-1]
        tol = c[3].number_input("Acceptable margin loss (pts)", 0.0, 3.0, 0.5, 0.05,
                                format="%.2f", key="rp_tol")

    price = q.BASE_PRICE[product]
    t = q.quote_terms(product, h, price, tol, ds=ds)
    r = q.realised_result(t, ds)
    out = q.cost_outlook(product, ds=ds).set_index("h")
    delivery = mlabel(plus(origin, h))

    a, b = st.columns(2)
    with a.container(border=True, key="card_quote"):
        st.caption(f"AT THE QUOTE · {mlabel(origin)}, data up to {mlabel(origin)}")
        st.markdown(f"#### {action_text(t, t.recommended)}")
        st.markdown(f"Unit raw-material cost **{eur(out.loc[h, 'today'])}** at the quote, forecast "
                    f"**{eur(out.loc[h, 'p10'])}–{eur(out.loc[h, 'bad'])}** (P10–P90) by {delivery}.")
        st.markdown(f"With a fixed price and no uplift, the margin loss could reach "
                    f"**{t.loss_q:.2f} pts** at 90 % confidence.")
    ok = r["within"]
    with b.container(border=True, key="card_hit" if ok else "card_miss"):
        st.caption(f"WHAT HAPPENED · by {delivery}")
        st.markdown("#### " + ("Margin loss stayed within the acceptable loss" if ok else
                               "Margin loss went beyond the acceptable loss"))
        g = r["by_group"]
        st.markdown(f"Raw-material cost changed by **{r['eur_change']:+,.0f} €** per unit "
                    f"({r['loss_fixed']:+.2f} pts of the price); largest move: "
                    f"**{g.abs().idxmax()}** ({g[g.abs().idxmax()]:+,.0f} €).")
        st.markdown(f"Margin result with the recommended terms: **{r['result']:+.2f} pts** "
                    f"({seur(r['result'] * price / 100)}), against {-r['loss_fixed']:+.2f} pts "
                    f"with a fixed price and no uplift. Acceptable: ≥ {-tol:.2f} pts.")
        st.markdown(f"↳ The actual cost change was at the **P{100 * r['percentile']:.0f}** "
                    f"of the forecast range.")

    # chart: actual cost vs the forecast made at the quote
    path = q.cost_path(product, ds)
    fig = base_fig()
    pts = [pd.Timestamp(origin)] + [plus(origin, x) for x in out.index]
    lo = [out["today"].iloc[0]] + list(out["p10"])
    hi = [out["today"].iloc[0]] + list(out["bad"])
    fig.add_trace(go.Scatter(x=pts + pts[::-1], y=hi + lo[::-1], fill="toself", mode="lines",
                             line=dict(width=0), fillcolor=BAND, hoverinfo="skip",
                             name="Forecast P10–P90"))
    fig.add_trace(go.Scatter(x=pts, y=[out["today"].iloc[0]] + list(out["p50"]), mode="lines+markers",
                             line=dict(color=MUTED, dash="dot"), name="Forecast median",
                             hovertemplate="%{y:,.0f} €"))
    fig.add_trace(go.Scatter(x=path.index, y=path.values, mode="lines", name="Actual",
                             line=dict(color=INK, width=2.5), hovertemplate="%{y:,.0f} €"))
    fig.add_vline(x=pd.Timestamp(origin), line=dict(color="#C9CED6", dash="dash"))
    fig.add_vline(x=plus(origin, h), line=dict(color=SE_GREEN, dash="dash"))
    fig.update_layout(showlegend=True)
    fig.update_yaxes(title="€ per unit", tickformat=",.0f")
    chart_title(f"{product} raw-material cost per unit: forecast at {mlabel(origin)} vs actual")
    chart(fig)

    # track record over every past month
    st.subheader("Track record")
    st.caption(f"The same rule ({product}, valid {h} months, acceptable loss {tol:.2f} pts, 90 % "
               "confidence) on every past quote month whose outcome is known. 2,000 paths "
               "per month to keep it fast.")

    @st.cache_data(show_spinner=False)
    def track(product: str, h: int, tol: float) -> pd.DataFrame:
        rows = []
        for m in q.replay_months():
            if plus(m, h) > LAST:
                continue
            d = q.Dataset(origin=m, replay=True, n_paths=2000)
            if h not in d.horizons:
                continue
            tt = q.quote_terms(product, h, q.BASE_PRICE[product], tol, ds=d)
            rr = q.realised_result(tt, d)
            rows.append({"month": pd.Timestamp(m), "terms": tt.recommended.kind,
                         "uplift": tt.recommended.uplift, "result": rr["result"],
                         "no_protection": -rr["loss_fixed"], "within": rr["within"]})
        return pd.DataFrame(rows)

    key = (product, h, round(tol, 2))
    if st.session_state.get("rp_track") != key:
        if st.button("Run on every past month (about 30 s)"):
            st.session_state.rp_track = key
            st.rerun()
    else:
        with st.spinner("Replaying every past month…"):
            tr = track(*key)
        n, k = len(tr), int(tr["within"].sum())
        k0 = int((tr["no_protection"] >= -tol).sum())
        m1, m2, m3 = st.columns(3)
        m1.metric("Within the acceptable loss, recommended terms", f"{k} of {n}", f"{k / n:.0%}",
                  delta_color="off")
        m2.metric("Same, fixed price and no uplift", f"{k0} of {n}", f"{k0 / n:.0%}",
                  delta_color="off")
        m3.metric("Average uplift charged", f"{tr['uplift'].mean():.2f} pts",
                  eur(tr["uplift"].mean() * q.BASE_PRICE[product] / 100), delta_color="off")
        fig = base_fig()
        fig.add_trace(go.Bar(x=tr["month"], y=tr["result"], name="Recommended terms",
                             marker_color=[SE_GREEN if w else RED for w in tr["within"]],
                             hovertemplate="%{y:+.2f} pts"))
        fig.add_trace(go.Scatter(x=tr["month"], y=tr["no_protection"], mode="markers",
                                 name="Fixed price, no uplift", marker=dict(color=MUTED, size=6),
                                 hovertemplate="%{y:+.2f} pts"))
        fig.add_hline(y=-tol, line=dict(color=RED, dash="dash"),
                      annotation_text="acceptable loss", annotation_position="bottom right")
        fig.update_layout(showlegend=True)
        fig.update_yaxes(title="margin result (pts)", zeroline=True, zerolinecolor="#C9CED6")
        chart_title(f"Margin result at delivery, by quote month ({product}, {h} months)")
        chart(fig)
        st.caption("Green: within the acceptable loss. Red: beyond it. The target is 9 quotes "
                   "out of 10 (90 % confidence).")

# ============================================================ new month
with tab_new:
    st.caption("Give the next month of prices in Schneider's format "
               "(rm_prices_monthly_wide.csv or rm_prices_monthly_long.csv). The app checks it, "
               "then reruns every step, from data preparation to the forecast CSV and the "
               "quote terms. The submitted Sep 2026 results are never changed: each run "
               "works in its own copy.")
    hist = mu.history()
    last_full = hist[mu.REQUIRED].dropna().index.max()
    nxt = plus(last_full, 1)

    st.markdown("**1 · Get a file in Schneider's format**")
    with st.container(border=True):
        c1, c2 = st.columns(2, gap="large")
        c1.markdown(f"**Next month ({mlabel(nxt)})**: empty template, one row, the columns of "
                    "the client's file.")
        c1.download_button("Download the template", mu.template(f"{nxt:%Y-%m}"),
                           f"rm_prices_{nxt:%Y-%m}.csv", "text/csv")
        c2.markdown("**Test with a held-back month**: that month exactly as received, to "
                    "rerun the forecast as if it were the newest month.")
        cc = c2.columns([1, 1], vertical_alignment="bottom")
        recent = [f"{m:%Y-%m}" for m in hist[mu.REQUIRED].dropna().index[-12:]][::-1]
        hb = cc[0].selectbox("Held-back month", recent, format_func=mlabel, key="hb_month")
        cc[1].download_button("Download this month", mu.held_back_file(hb),
                              f"rm_prices_{hb}.csv", "text/csv", width="stretch")

    st.markdown("**2 · Upload and check**")
    up = st.file_uploader("Monthly price file (CSV)", type="csv", key="upload",
                          label_visibility="collapsed")
    chk = None
    if up is not None:
        try:
            chk = mu.check(mu.read_upload(up.getvalue()))
        except Exception as e:
            st.error(f"Could not read the file: {e}")
    if chk is not None:
        icon = {"ok": "✓", "warn": "⚠", "error": "✗"}
        mark = {"ok": ":green[✓]", "warn": ":orange[⚠]", "error": ":red[✗]"}
        with st.container(border=True):
            st.markdown("  \n".join(
                f"{mark[x.status]} **{x.rule}**" + (f" · {x.detail}" if x.detail else "")
                for x in chk.rows.itertuples()))
        if len(chk.values):
            v = chk.values.copy()
            v["status"] = v["status"].map(icon)
            with st.expander(f"Values by series ({mlabel(chk.month)})",
                             expanded=bool((chk.values["status"] != "ok").any())):
                st.dataframe(v, hide_index=True, width="stretch", column_config={
                    "status": st.column_config.TextColumn("", width=40),
                    "previous": st.column_config.NumberColumn("Previous month", format="%.2f"),
                    "new": st.column_config.NumberColumn("New value", format="%.2f"),
                    "change": st.column_config.NumberColumn("Change", format="percent"),
                    "largest change on file": st.column_config.NumberColumn(
                        "Largest monthly change on file", format="percent")})
        st.caption("Epoxy and the MEPS / CRU steel prices come from their own Schneider "
                   "files, not this one: their latest month on file is used.")

    st.markdown("**3 · Run the forecast**")
    run_label = f"Run the forecast as of {mlabel(chk.month)}" if chk and chk.ok else "Run the forecast"
    if st.button(run_label, type="primary", disabled=not (chk and chk.ok)):
        st.session_state.run_name = mu.start_run(chk)
        st.rerun()
    st.caption("About 5 minutes. Data preparation → external data → features → baselines → "
               "models → cost model → simulation → forecast CSV, the same command as "
               "`make forecast`.")

    runs = mu.runs()
    names = [x["name"] for x in runs]
    if names:
        cur = st.session_state.get("run_name")
        sel = st.selectbox(
            "Run", names, index=names.index(cur) if cur in names else 0,
            format_func=lambda n: next(f"As of {mlabel(x['month'])} · started {x['started']} · "
                                       f"{x['status']}" for x in runs if x["name"] == n))
        info = mu.run_info(sel)

        @st.fragment(run_every=3 if info["status"] == "running" else None)
        def progress(name: str):
            i = mu.run_info(name)
            if i["status"] == "running":
                done = len(i["stages_done"])
                now = i["stages_started"][-1] if i["stages_started"] else "starting"
                st.progress(done / len(STAGES), text=f"Step {min(done + 1, len(STAGES))} of "
                            f"{len(STAGES)}: {now.replace('_', ' ')}")
                with st.expander("Log"):
                    st.code(i["log"][-3000:] or "…", language=None)
            elif info["status"] == "running":   # it just finished: redraw the page
                st.rerun(scope="app")

        progress(sel)
        if info["status"] == "failed":
            st.error("The pipeline stopped. The end of its log:")
            st.code(info["log"][-3000:], language=None)
        elif info["status"] == "done":
            month = info["month"]
            st.success(f"Forecast as of {mlabel(month)} ready.")
            csv = pd.read_csv(info["csv"])
            sub = mu.REPO_ROOT / "submissions" / f"group_6_forecast_{month.replace('-', '')}.csv"
            if sub.exists():
                ref = pd.read_csv(sub)
                num = ["p10", "p50", "p90"]
                same_keys = ref.drop(columns=num).equals(csv.drop(columns=num))
                gap = (ref[num] - csv[num]).abs().to_numpy().max() if same_keys else None
                if gap == 0:
                    st.success(f"Identical to the submitted file {sub.name}: the pipeline "
                               "reproduces it from the uploaded month.")
                elif gap is not None and gap <= 0.011:
                    n = int(((ref[num] - csv[num]).abs() > 0).to_numpy().sum())
                    st.success(f"Matches the submitted file {sub.name}: same rows, {n} of "
                               f"{ref[num].size} values differ in the last digit (rounding "
                               "between machines).")
                else:
                    st.warning(f"Differs from the submitted file {sub.name}.")

            rds = q.Dataset(origin=month, root=info["root"])
            rows = []
            for prod in ("RM6", "RM AirSeT"):
                for hh in rds.horizons:
                    tn = q.quote_terms(prod, hh, q.BASE_PRICE[prod], 0.5, ds=rds)
                    row = {"Product": prod, "Validity": f"{hh} months",
                           "Recommended terms": action_text(tn, tn.recommended),
                           "Loss at 90 % (fixed price)": f"{tn.loss_q:.2f} pts"}
                    if month != q.p.ORIGIN:
                        ts = q.quote_terms(prod, hh, q.BASE_PRICE[prod], 0.5)
                        row["Submitted (Sep 2026)"] = action_text(ts, ts.recommended)
                    rows.append(row)
            st.markdown(f"**Quote terms with data up to {mlabel(month)}** (list price, "
                        "acceptable loss 0.50 pts)")
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            st.markdown(f"**Forecast CSV** ({len(csv)} rows: material series and the RM6 / "
                        "RM AirSeT cost index)")
            st.dataframe(csv, hide_index=True, width="stretch", height=260)
            st.download_button("Download the forecast CSV", Path(info["csv"]).read_bytes(),
                               f"group_6_forecast_{month.replace('-', '')}.csv", "text/csv")
