"""Shared look: colours, CSS and chart defaults."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import pricing as p

GROUP_COLORS = {
    "Copper": "#C8642A",
    "Carbon steel": "#2E5A87",
    "Stainless steel": "#8FB3D9",
    "Epoxy": "#2A9D8F",
    "Aluminium": "#A0A4AB",
}
SCENARIO = "#6D28D9"        # custom scenario, used for nothing else
SCENARIO_TINT = "#F7F3FF"
BAND = "rgba(10, 47, 36, 0.10)"
INK = "#0A2F24"             # Schneider deep green, used as text colour
MUTED = "#4F5156"           # Schneider grey
SE_GREEN = "#3DCD58"        # Schneider Life Green, brand accent only
CHART_HEIGHT = 340

CSS = f"""
<style>
.block-container {{ padding-top: 2rem; }}
header[data-testid="stHeader"] {{ border-top: 4px solid {SE_GREEN}; }}
h1 {{ font-size: 2.25rem !important; }}
.st-key-card_quote, .st-key-card_airset {{ border-top: 4px solid {SE_GREEN} !important; }}
.st-key-scenario_banner {{
  background: {SCENARIO_TINT}; border: 2px solid {SCENARIO}; border-radius: 8px;
  padding: 8px 16px;
}}
.st-key-scenario_banner p {{ color: {SCENARIO}; font-weight: 600; margin: 0; }}
div[class*="st-key-scen_"] {{
  border: 2px solid {SCENARIO} !important; background: {SCENARIO_TINT};
}}
.st-key-steps [data-testid="stExpander"] summary {{ padding-top: 14px; padding-bottom: 14px; }}
.st-key-steps [data-testid="stExpander"] summary p {{ font-size: 1.125rem; font-weight: 600; }}
.chart-title {{ font-weight: 600; font-size: 0.95rem; margin: 0 0 -0.6rem 0; }}
</style>
"""


def month_label(h: int) -> str:
    return (pd.Timestamp(p.ORIGIN) + pd.DateOffset(months=h)).strftime("%b %Y")


def eur(x: float) -> str:
    return f"€{x:,.0f}"


def base_fig(top: int = 12, right: int = 8) -> go.Figure:
    """Same height and margins for every chart; no zoom or pan, hover kept."""
    fig = go.Figure()
    fig.update_layout(
        height=CHART_HEIGHT, margin=dict(l=8, r=right, t=top, b=8),
        showlegend=False, dragmode=False, hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=INK, size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, title=None),
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor="#D5D7DE", fixedrange=True,
                     title_standoff=6, ticks="")
    fig.update_yaxes(gridcolor="#EEEFF2", zeroline=False, fixedrange=True, title_standoff=6)
    return fig


def chart_title(text: str) -> None:
    st.markdown(f'<p class="chart-title">{text}</p>', unsafe_allow_html=True)


def chart(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "scrollZoom": False})
