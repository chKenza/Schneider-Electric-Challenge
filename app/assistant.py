"""Assistant: one sidebar panel, available on every page.

- Suggested questions are always answered by the app itself, from the live numbers on screen.
- Free-text questions go to the engine chosen in Settings:
    * Built-in search (default, offline): matches a suggested question, or shows the closest
      passages of our reports.
    * Claude Code (this laptop): the `claude` CLI, logged in with the user's Claude plan.
    * Claude API: an Anthropic API key (session only, or ANTHROPIC_API_KEY in
      .streamlit/secrets.toml).
- What an LLM sees: the question, the numbers on screen and passages of our written reports
  (report/problem1, report/problem2). Never the files in Data/.
"""

import glob
import math
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

from app.ui import action_text, eur, month_label
from src import quote_engine as q
from src.config import REPO_ROOT

REPORT_DIRS = [REPO_ROOT / "report" / "problem1", REPO_ROOT / "report" / "problem2"]
# Paragraphs quoting the superseded BOM (before v1) are left out of the search.
STALE = ("€795", "€583", "€981", "epoxy low", "epoxy high", "629 kg", "86 kg")
ENGINES = ["Built-in search (offline)", "Claude Code (this laptop)", "Claude API"]
API_MODEL = "claude-opus-5-5"
DEFAULT_QUOTE = dict(product="RM6", h=9, price=q.BASE_PRICE["RM6"], tol=0.5, conf=0.90,
                     max_up=1.0, clause_ok=True, scenario=False, pct={})
SEGMENTS = ["Australia colocation", "Johor-Singapore data centres", "Australia utilities",
            "Gulf data centres"]

SYSTEM = """You are the assistant inside Schneider Electric's ETO quote-pricing tool \
(RM6 and RM AirSeT ring main units). Users are sales, pricing and procurement staff, not \
data scientists.

Answer only from the CURRENT SCREEN numbers and the REPORT PASSAGES given with each question. \
If they do not contain the answer, say so in one sentence and suggest which input or page to \
look at. Never invent numbers.

Style: at most 120 words, plain business English, the client's terms (quotation validity, \
margin at risk, price adjustment, risk buffer, indexation clause, BOM cost exposure). Give \
margins in points and in € per unit. No headings. When you use a report passage, name its \
file at the end, e.g. (source: 04_strategy.md)."""


# ------------------------------------------------------------------ context
def quote_ctx() -> dict:
    return {**DEFAULT_QUOTE, **st.session_state.get("asst_ctx_quote", {})}


def airset_ctx() -> dict:
    return {"segment": SEGMENTS[0], "extra": 10.0, **st.session_state.get("asst_ctx_airset", {})}


def terms(c: dict, **over):
    a = {**c, **over}
    return q.quote_terms(a["product"], a["h"], a["price"], a["tol"], a["conf"], a["max_up"],
                         a["clause_ok"])


@st.cache_data
def price_window() -> pd.DataFrame:
    return pd.read_csv(REPO_ROOT / "report/problem2/03_tables/price_window.csv")


def ceilings() -> pd.Series:
    return price_window().groupby("segment")["ceiling_pct"].first().reindex(SEGMENTS)


def screen_text() -> str:
    """The numbers on screen, as plain text for the LLM."""
    c, a = quote_ctx(), airset_ctx()
    t = terms(c)
    rec, month = t.recommended, month_label(c["h"])
    co = q.cost_outlook(c["product"], c["conf"]).set_index("h").loc[c["h"]]
    lines = [
        f"Quote: {c['product']}, quotation validity {c['h']} months (to {month}), selling price "
        f"{eur(c['price'])}, acceptable margin loss {c['tol']:.2f} pts, confidence "
        f"{c['conf']:.0%}, max. uplift {c['max_up']:.2f} pts, customer accepts an indexation "
        f"clause: {'yes' if c['clause_ok'] else 'no'}.",
        f"Recommended quote terms: {action_text(t, rec)}. Price adjustment {rec.adjustment:.2f} "
        f"pts (expected cost increase), risk buffer {rec.buffer:.2f} pts.",
        f"What would change it: {q.what_would_change(t)}",
        "Options: " + "; ".join(f"{o.name}: uplift {o.uplift:.2f} pts ({eur(t.eur(o.uplift))}), "
                                f"{'within' if o.fits else 'above'} max. uplift" for o in t.options),
        f"Margin at risk with a fixed price and no uplift: {t.loss_q:.2f} pts "
        f"({eur(t.eur(t.loss_q))}) at {c['conf']:.0%} confidence; expected loss "
        f"{t.loss_median:.2f} pts; share of simulated paths above the acceptable loss "
        f"{t.p_over_limit:.0%}.",
        "Cost increase in the bad case by material: " + ", ".join(
            f"{g} {eur(v)}" for g, v in t.drivers.sort_values(ascending=False).items()),
        f"Raw-material cost of one {c['product']}: today {eur(co.today)}, expected "
        f"{eur(co.p50)} by {month}, high case {eur(co.bad)}.",
        "Forecast price change by " + month + " (10th / 50th / 90th percentile): " + "; ".join(
            "{} {:+.0f} % / {:+.0f} % / {:+.0f} %".format(g, *q.group_change_range(c["product"], c["h"], g))
            for g in q.GROUPS),
    ]
    if c["scenario"] and any(c["pct"].values()):
        s = q.scenario_result(t, c["pct"])
        lines.append("Custom scenario (not a forecast): " + ", ".join(
            f"{g} {v:+d} %" for g, v in c["pct"].items() if v) +
            f"; cost change {eur(s['eur_change'])}; this large or larger in "
            f"{s['share_worse']:.0%} of simulations.")
    ce = ceilings()
    lines.append(
        f"RM AirSeT page: segment {a['segment']}, AirSeT extra unit cost vs RM6 {a['extra']:.1f} %. "
        "Highest premium justified by customer lifetime savings (TCO): " + "; ".join(
            f"{s} {v:.1f} %" for s, v in ce.items()) + ".")
    return "\n".join(f"- {x}" for x in lines)


# ---------------------------------------------------------- report search
def _tokens(text: str) -> list[str]:
    stop = {"the", "a", "an", "of", "to", "in", "and", "or", "is", "are", "for", "on", "at",
            "by", "it", "we", "be", "this", "that", "with", "as", "what", "why", "how", "do",
            "does", "can", "if", "our", "from", "which", "would", "should", "there", "not"}
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in stop and len(w) > 1]


@st.cache_resource
def report_index():
    chunks = []
    for d in REPORT_DIRS:
        for f in sorted(d.glob("*.md")):
            heading, buf = f.stem, []

            def flush():
                text = "\n".join(buf).strip()
                if len(text) > 120 and not any(s in text for s in STALE):
                    chunks.append({"file": f.name, "heading": heading, "text": text})

            for line in f.read_text(encoding="utf-8").splitlines():
                if line.startswith("#"):
                    flush()
                    heading, buf = line.lstrip("#").strip(), []
                else:
                    buf.append(line)
            flush()
    toks = [Counter(_tokens(c["heading"] + " " + c["text"])) for c in chunks]
    df = Counter(w for t in toks for w in t)
    avg = sum(sum(t.values()) for t in toks) / max(len(toks), 1)
    return chunks, toks, df, avg


def search(question: str, k: int = 4) -> list[dict]:
    chunks, toks, df, avg = report_index()
    n, words = len(chunks), set(_tokens(question))
    scores = []
    for i, t in enumerate(toks):
        length, s = sum(t.values()), 0.0
        for w in words:
            if w in t:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * t[w] * 2.2 / (t[w] + 1.2 * (0.25 + 0.75 * length / avg))
        scores.append(s)
    best = sorted(range(n), key=lambda i: -scores[i])[:k]
    return [chunks[i] for i in best if scores[i] > 0]


# ------------------------------------------------- suggested questions
def a_why(c):
    t = terms(c)
    rec, fixed = t.recommended, t.options[0]
    head = (f"For an {c['product']} quote valid {c['h']} months, a fixed price with no protection "
            f"could lose up to **{t.loss_q:.2f} pts** ({eur(t.eur(t.loss_q))} per unit) at "
            f"{c['conf']:.0%} confidence. Your acceptable loss is {c['tol']:.2f} pts.")
    if rec.kind == "fixed":
        why = (f"A fixed price with a {rec.uplift:.2f} pt uplift covers this and stays under the "
               f"{c['max_up']:.2f} pt maximum uplift, so no clause is needed.")
    elif rec.kind == "clause":
        why = (f"A fixed price would need {fixed.uplift:.2f} pts, above the {c['max_up']:.2f} pt "
               f"maximum. An indexation clause (±{rec.band:.0%}) passes large metal price moves "
               f"to the customer, so only **{rec.uplift:.2f} pts** of uplift is needed.")
    elif rec.kind == "validity":
        why = (f"A fixed price over {c['h']} months would need {fixed.uplift:.2f} pts. Over "
               f"{rec.months} months the risk is smaller and {rec.uplift:.2f} pts is enough.")
    else:
        why = (f"No option stays under the {c['max_up']:.2f} pt maximum uplift; the least costly "
               f"is: {action_text(t, rec).lower()}.")
    return (f"{head} {why}\n\nThe uplift = **price adjustment** {rec.adjustment:.2f} pts "
            f"(expected cost increase) + **risk buffer** {rec.buffer:.2f} pts (uncertainty). "
            "The rule tries a fixed price first, then an indexation clause, then a shorter "
            "validity.")


def a_fixed(c):
    t = terms(c)
    fixed = t.options[0]
    ok = "fits" if fixed.fits else "does not fit"
    out = (f"A fixed price needs **{fixed.uplift:.2f} pts** ({eur(t.eur(fixed.uplift))} per unit), "
           f"which {ok} under your {c['max_up']:.2f} pt maximum uplift. {q.what_would_change(t)}")
    if t.longest_fixed:
        out += f" The longest validity that works with a fixed price is {t.longest_fixed} months."
    return out


def a_driver(c):
    t = terms(c)
    d = t.drivers.clip(lower=0).sort_values(ascending=False)
    share = 100 * d / d.sum()
    items = "\n".join(f"- **{g}**: {eur(v)} per unit ({share[g]:.0f} %)" for g, v in d.items() if v > 1)
    return (f"In the bad case ({c['conf']:.0%} confidence, {c['h']} months), the raw-material "
            f"cost of one {c['product']} rises by about {eur(d.sum())}:\n{items}\n\n"
            f"**{d.index[0]}** is the material to protect in the quote (indexation clause or "
            "procurement hedge).")


def a_risk(c):
    t = terms(c)
    return (f"With a fixed price and no uplift, a {c['h']}-month {c['product']} quote could lose "
            f"up to **{t.loss_q:.2f} pts** ({eur(t.eur(t.loss_q))} per unit) at {c['conf']:.0%} "
            f"confidence. The expected loss is {t.loss_median:.2f} pts. In "
            f"**{t.p_over_limit:.0%}** of simulated price paths the loss exceeds your acceptable "
            f"loss of {c['tol']:.2f} pts.")


def a_no_clause(c):
    if not c["clause_ok"]:
        return ("The toggle *Customer accepts an indexation clause* is already off, so the "
                "current recommendation is the answer: " + action_text(terms(c), terms(c).recommended) + ".")
    t2 = terms(c, clause_ok=False)
    r = t2.recommended
    return (f"Without a clause the recommendation becomes: **{action_text(t2, r)}**"
            + ("" if r.fits else f" (above your {c['max_up']:.2f} pt maximum uplift)") +
            ". Switch off *Customer accepts an indexation clause* at the top to see it in full.")


def a_copper(c):
    t = terms(c)
    s = q.scenario_result(t, {"Copper": 30})
    tab = s["table"]
    rec_row = tab[tab.option.str.endswith("(recommended)")].iloc[0]
    none_row = tab.iloc[0]
    return (f"If copper is 30 % higher by {month_label(c['h'])}, the raw-material cost of one "
            f"{c['product']} rises by **{eur(s['eur_change'])}**. Without protection the quote "
            f"loses {-none_row.result:.2f} pts; with the recommended terms the result is "
            f"**{rec_row.result:+.2f} pts**. A move this large or larger happens in "
            f"{s['share_worse']:.0%} of our simulations. Try other moves under *Stepwise analysis "
            "→ Custom scenario*.")


def a_forecast(c):
    g = terms(c).drivers.idxmax()
    lo, mid, hi = q.group_change_range(c["product"], c["h"], g)
    return ("Each material's price is forecast at 3, 6 and 9 months as an expected value and an "
            "80 % range. In back-tests, the real price fell inside the range 80–84 % of the time, "
            "as it should. The expected value stays close to today's price, because no model "
            "predicts the direction reliably; the **width of the range** is what sets the risk "
            f"buffer. For example, {g.lower()} by {month_label(c['h'])}: {lo:+.0f} % to "
            f"{hi:+.0f} % (80 % range), expected {mid:+.0f} %.")


def a_airset(c):
    a = airset_ctx()
    ce = ceilings()
    open_ = [s for s in SEGMENTS if ce[s] >= a["extra"]]
    lines = "\n".join(f"- {s}: up to {ce[s]:.1f} % premium "
                      f"({'opens' if ce[s] >= a['extra'] else 'not yet'})" for s in SEGMENTS)
    first = ", ".join(open_) if open_ else "no segment on cost alone"
    return (f"A segment opens when the price premium its customers' lifetime savings justify "
            f"(TCO) is above AirSeT's extra unit cost, set at {a['extra']:.1f} % on the RM AirSeT "
            f"page:\n{lines}\n\nAt this extra cost: **{first}**. Start with Australia colocation "
            "(profitable now) and Johor–Singapore data centres (up to about 1 pt of margin "
            "invested); treat the Gulf as a reference market.")


def a_data(c):
    return ("- Raw-material prices: LME copper and aluminium (public), MEPS steel and CRU "
            "stainless (licensed, from Schneider Electric), epoxy (Schneider file), to Sep 2026.\n"
            "- Bill of materials: BOM v1 from Schneider Electric; unidentified mass (RM6 5.6 kg, "
            "RM AirSeT 56 kg) is not priced.\n"
            "- Selling prices: RM6 €8,740 (price benchmark); RM AirSeT assumed RM6 + 20 %.\n"
            "- Raw materials only; all other costs held constant. 10,000 simulated price paths.")


PRESETS = {
    "Why this recommendation?": (a_why, "why recommend recommendation reason explain"),
    "Can we offer a fixed price?": (a_fixed, "fixed price without clause"),
    "Which material drives the risk?": (a_driver, "material driver drives exposure main"),
    "How much margin is at risk?": (a_risk, "margin risk loss lose"),
    "What if the customer refuses the clause?": (a_no_clause, "refuse refuses reject no clause accept"),
    "What if copper rises 30 %?": (a_copper, "copper rise rises increase 30 spike"),
    "How reliable is the forecast?": (a_forecast, "reliable accurate accuracy forecast trust flat"),
    "Where should RM AirSeT start?": (a_airset, "airset segment market start where australia johor gulf"),
    "What data is behind this?": (a_data, "data source sources assumption assumptions bom"),
}


def match_preset(text: str) -> str | None:
    words = set(_tokens(text))
    best, score = None, 0
    for label, (_, kw) in PRESETS.items():
        s = len(words & set(kw.split()))
        if s > score:
            best, score = label, s
    return best if score >= 2 else None


# ------------------------------------------------------------- engines
def claude_cli() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    cands = sorted(glob.glob(os.path.expanduser(
        "~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude")))
    cands += [os.path.expanduser("~/.claude/local/claude")]
    return next((c for c in reversed(cands) if os.path.isfile(c)), None)


def llm_prompt(question: str, passages: list[dict]) -> str:
    rep = "\n\n".join(f"[{p['file']} – {p['heading']}]\n{p['text'][:1500]}" for p in passages)
    return (f"CURRENT SCREEN\n{screen_text()}\n\nREPORT PASSAGES\n{rep or '(none found)'}\n\n"
            f"QUESTION\n{question}")


def history_text() -> str:
    msgs = st.session_state.asst_msgs[-7:-1]
    return "\n".join(f"{m['role'].upper()}: {m['content'][:600]}" for m in msgs)


def ask_claude_code(question: str, passages: list[dict]) -> str:
    cli = claude_cli()
    if not cli:
        raise RuntimeError("Claude Code was not found on this laptop.")
    prompt = llm_prompt(question, passages)
    if len(st.session_state.asst_msgs) > 1:
        prompt = f"EARLIER IN THIS CONVERSATION\n{history_text()}\n\n{prompt}"
    # No tools, no MCP servers, no settings, run from an empty folder: it can only read the prompt.
    with tempfile.TemporaryDirectory() as empty:
        r = subprocess.run(
            [cli, "-p", "--tools", "", "--strict-mcp-config", "--setting-sources", "",
             "--no-session-persistence", "--disable-slash-commands",
             "--system-prompt", SYSTEM, "--output-format", "text"],
            input=prompt, capture_output=True, text=True, timeout=120, cwd=empty)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError((r.stderr or r.stdout or "no answer").strip()[:300])
    return r.stdout.strip()


def api_key() -> str | None:
    key = st.session_state.get("asst_api_key") or None
    if not key:
        try:
            key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            key = None
    return key


def ask_claude_api(question: str, passages: list[dict]) -> str:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("The anthropic package is not installed: run `uv add anthropic`.")
    key = api_key()
    if not key:
        raise RuntimeError("No API key: add one in Settings.")
    client = anthropic.Anthropic(api_key=key)
    msgs = [{"role": m["role"], "content": m["content"]}
            for m in st.session_state.asst_msgs[-7:-1]]
    msgs.append({"role": "user", "content": llm_prompt(question, passages)})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    try:
        r = client.beta.messages.create(
            model=API_MODEL, max_tokens=2000, system=SYSTEM, messages=msgs,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    except anthropic.AuthenticationError:
        raise RuntimeError("The API key was rejected.")
    except anthropic.RateLimitError:
        raise RuntimeError("Rate limit reached; try again in a minute.")
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"API error {e.status_code}.")
    except anthropic.APIConnectionError:
        raise RuntimeError("No connection to the Claude API.")
    if r.stop_reason == "refusal":
        raise RuntimeError("Claude declined to answer this question.")
    return "".join(b.text for b in r.content if b.type == "text").strip()


def builtin_answer(question: str, passages: list[dict]) -> str:
    if not passages:
        return ("I can't answer that from the app. Try one of the suggested questions, or switch "
                "on Claude in Settings.")
    out = ["I can't compute that directly. The closest passages in our reports:"]
    for p in passages[:2]:
        prose = "\n".join(l for l in p["text"].splitlines() if not l.lstrip().startswith("|"))
        prose = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", prose)          # links -> their text
        text = re.sub(r"\s+", " ", re.sub(r"[*#>`]", " ", prose)).strip()
        out.append(f"**{p['heading']}** ({p['file']})\n\n{text[:420]}…")
    return "\n\n".join(out)


def answer(msg: dict) -> dict:
    text, c = msg["content"], quote_ctx()
    label = text if msg.get("preset") else match_preset(text)
    engine = st.session_state.asst_engine
    if label and (msg.get("preset") or engine == ENGINES[0]):
        return {"role": "assistant", "content": PRESETS[label][0](c),
                "meta": "Computed by the app from the numbers on screen."}
    passages = search(text)
    files = sorted({p["file"] for p in passages})
    if engine == ENGINES[0]:
        return {"role": "assistant", "content": builtin_answer(text, passages),
                "meta": "Built-in search of our reports."}
    try:
        fn = ask_claude_code if engine == ENGINES[1] else ask_claude_api
        reply = fn(text, passages)
        meta = f"{engine.split(' (')[0]} · from the numbers on screen" + (
            f" and {', '.join(files)}" if files else "")
    except Exception as e:  # fall back to the built-in answer, say why
        reply = builtin_answer(text, passages)
        meta = f"{engine.split(' (')[0]} unavailable ({e}). Built-in search shown instead."
    return {"role": "assistant", "content": reply, "meta": meta}


# ------------------------------------------------------------------- UI
def _push(text: str, preset: bool = False):
    if text and text.strip():
        st.session_state.asst_msgs.append({"role": "user", "content": text.strip(), "preset": preset})


def _on_pill():
    _push(st.session_state.asst_pill, preset=True)
    st.session_state.asst_pill = None


def _on_input():
    _push(st.session_state.asst_input)


def _clear():
    st.session_state.asst_msgs = []


def render(page_title: str):
    st.session_state.setdefault("asst_msgs", [])
    st.session_state.setdefault("asst_engine", ENGINES[0])
    order = list(PRESETS)
    if page_title.startswith("RM AirSeT"):
        order = [order[-2]] + order[:-2] + [order[-1]]

    with st.sidebar.container(key="assistant"):
        h1, h2 = st.columns([3, 1], vertical_alignment="center")
        h1.markdown("**Assistant**")
        with h2.popover("⚙", help="Assistant settings"):
            st.radio("Answer free-text questions with", ENGINES, key="asst_engine")
            eng = st.session_state.asst_engine
            if eng == ENGINES[1]:
                cli = claude_cli()
                if cli:
                    st.caption("Found Claude Code on this laptop. Uses your Claude plan.")
                else:
                    st.caption("Claude Code not found on this laptop.")
            elif eng == ENGINES[2]:
                st.text_input("Anthropic API key", type="password", key="asst_api_key",
                              help="Kept for this session only. Or set ANTHROPIC_API_KEY in "
                                   ".streamlit/secrets.toml (not committed).")
            if eng != ENGINES[0]:
                st.caption("Sent to Anthropic: your question, the numbers on screen and passages "
                           "of our reports. Never the raw data files.")
            st.caption("Suggested questions are always computed by the app.")
            st.button("Clear conversation", on_click=_clear, width="stretch")

        msgs = st.session_state.asst_msgs
        st.chat_input("Ask about this quote…", key="asst_input", on_submit=_on_input)
        with st.expander("Suggested questions", expanded=not msgs):
            st.pills("Suggested questions", order, key="asst_pill", on_change=_on_pill,
                     label_visibility="collapsed")

        if msgs and msgs[-1]["role"] == "user":
            with st.spinner("Thinking…"):
                msgs.append(answer(msgs[-1]))
        if len(msgs) > 2:
            with st.expander("Earlier in this conversation"):
                for m in msgs[-12:-2]:
                    _show(m)
        for m in msgs[-2:]:
            _show(m)


def _show(m: dict):
    icon = ":material/person:" if m["role"] == "user" else ":material/support_agent:"
    with st.chat_message(m["role"], avatar=icon):
        st.markdown(m["content"])
        if m.get("meta"):
            st.caption(m["meta"])
