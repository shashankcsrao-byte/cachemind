"""Design system for CacheMind: tokens, Streamlit overrides, chart styling, HTML parts.

Style: "data terminal" (dark). Cards sit darker than the ground, figures are
tabular, colour lives on data, and every selection is one 1px accent line.
"""
import html

import altair as alt

# --------------------------------------------------------------------- tokens
GROUND = "#171719"
SURFACE = "#131217"
RAISED = "#212023"
BORDER = "#222224"
RULE = "#1b1a1f"
CONTROL = "#3a3a3e"
TEXT = "#ffffff"
MUTED = "#8a8c92"
ACCENT = "#4a8ad6"
ACCENT_BG = "#16233a"
ACCENT_INK = "#8fb8ec"
POSITIVE_BG, POSITIVE_INK = "#1b2828", "#5fc39c"
NEGATIVE_BG, NEGATIVE_INK = "#2c1a20", "#e5566f"
WARNING_BG, WARNING_INK = "#2a2416", "#d9a441"
NEUTRAL_BAR = "#4a4a50"
FONT = '"Public Sans", Inter, system-ui, sans-serif'
MONO = '"JetBrains Mono", ui-monospace, Menlo, monospace'

# Result state of a cache access: (row tint, ink, label)
STATES = {
    "hit": (POSITIVE_BG, POSITIVE_INK, "Hit"),
    "load": (WARNING_BG, WARNING_INK, "Miss, loaded"),
    "replace": (NEGATIVE_BG, NEGATIVE_INK, "Miss, replaced"),
}

CSS = f"""
<style>
@import url("https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap");
:root {{
  --ground:{GROUND}; --surface:{SURFACE}; --raised:{RAISED}; --border:{BORDER}; --rule:{RULE};
  --control:{CONTROL}; --text:{TEXT}; --muted:{MUTED}; --accent:{ACCENT};
}}
html, body, .stApp, [data-testid="stMarkdownContainer"], button, input, textarea, select {{
  font-family:{FONT} !important; font-variant-numeric: tabular-nums;
}}
.stApp {{ background:var(--ground); }}
::selection {{ background:{ACCENT_BG}; color:var(--text); }}
* {{ scrollbar-color: var(--control) transparent; scrollbar-width: thin; }}
[data-testid="stDecoration"], [data-testid="stToolbar"] {{ display:none; }}
[data-testid="stHeader"] {{ background:transparent; }}
.block-container {{ padding:2rem 2rem 4rem; max-width:1280px; }}
@media (max-width:640px) {{ .block-container {{ padding:1.25rem 1rem 3rem; }} }}

/* type: app scale 26 / 20 / 16 / 13 / 12 */
h1 {{ font-size:26px !important; font-weight:700 !important; letter-spacing:-0.01em; padding:0 0 4px !important; }}
h2 {{ font-size:20px !important; font-weight:400 !important; color:var(--muted) !important; padding:8px 0 4px !important; }}
h3 {{ font-size:16px !important; font-weight:600 !important; padding:4px 0 !important; }}
[data-testid="stHeaderActionElements"] {{ display:none; }}
p, li, label, [data-testid="stMarkdownContainer"] {{ font-size:14px; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ color:var(--muted) !important; opacity:1 !important; font-size:14px; }}
code {{ font-family:{MONO} !important; background:var(--raised) !important; color:var(--text) !important; }}

/* sidebar: labelled list, selection = 1px accent line as wide as the label */
[data-testid="stSidebar"] {{ background:var(--ground); border-right:1px solid var(--border); }}
[data-testid="stSidebar"] [role="radiogroup"] {{ gap:0; }}
[data-testid="stSidebar"] [role="radiogroup"] label {{ padding:7px 4px; margin:0; cursor:pointer; }}
[data-testid="stSidebar"] [role="radiogroup"] label > div > div:not([data-testid="stMarkdownContainer"]) {{ display:none; }}
[data-testid="stSidebar"] [role="radiogroup"] label p {{ color:var(--muted); font-size:14px; transition:color .15s ease-out; }}
[data-testid="stSidebar"] [role="radiogroup"] label:hover p {{ color:#d6d7da; }}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {{
  color:var(--text); text-decoration:underline 1px var(--accent); text-underline-offset:7px;
}}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:focus-visible) {{ outline:2px solid var(--accent); outline-offset:2px; border-radius:4px; }}
.cm-brand {{ display:flex; gap:10px; align-items:center; margin:4px 0 6px; }}
.cm-brand b {{ font-size:16px; font-weight:600; }}
.cm-scope {{ color:var(--muted); font-size:12px; line-height:18px; margin:0 0 18px; }}

/* buttons: quiet pills; primary is inverted */
button[data-testid^="stBaseButton"] {{
  border-radius:999px; min-height:34px; font-size:13px; font-weight:500;
  transition: background-color .15s ease-out, border-color .15s ease-out, transform .1s ease-out;
}}
button[data-testid="stBaseButton-secondary"] {{ background:transparent; border:1px solid var(--control); color:var(--text); }}
button[data-testid="stBaseButton-secondary"]:hover {{ background:var(--raised); border-color:#55555b; color:var(--text); }}
button[data-testid="stBaseButton-primary"] {{ background:var(--text); border:1px solid var(--text); color:#111; }}
button[data-testid="stBaseButton-primary"]:hover {{ background:#dcdcdf; border-color:#dcdcdf; color:#111; }}
button[data-testid^="stBaseButton"]:active {{ transform:scale(.98); }}
button[data-testid^="stBaseButton"]:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; box-shadow:none; }}
button[data-testid^="stBaseButton"]:disabled {{ background:transparent; border-color:var(--border); color:#5d5e63; }}

/* surfaces */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{ border-color:var(--border) !important; }}
[data-testid="stExpander"] details {{ background:var(--surface); border:1px solid var(--border); border-radius:6px; }}
[data-testid="stExpander"] summary p {{ font-size:14px; font-weight:500; }}
[data-testid="stAlert"] {{ background:var(--raised); border-radius:6px; }}
[data-testid="stAlert"] p {{ color:var(--text); }}
[data-testid="stProgress"] [role="progressbar"] > div {{ height:3px !important; }}
[data-testid="stProgress"] p {{ color:var(--muted); font-size:12px; }}
.stTextInput input, .stNumberInput input, .stTextArea textarea {{ font-variant-numeric:tabular-nums; }}
.stTextArea textarea {{ font-family:{MONO} !important; font-size:13px; }}

/* parts */
.cm-kpis {{ display:grid; grid-template-columns:repeat(var(--n), minmax(0,1fr)); background:var(--surface);
  border:1px solid var(--border); border-radius:6px; margin:8px 0 16px; }}
.cm-kpi {{ padding:14px 18px; border-left:1px solid var(--border); min-width:0; }}
.cm-kpi:first-child {{ border-left:0; }}
.cm-kpi span {{ display:block; color:var(--muted); font-size:12px; line-height:16px; }}
.cm-kpi b {{ display:block; font-size:20px; font-weight:500; line-height:28px; margin-top:4px; white-space:nowrap; }}
.cm-kpi b small {{ color:var(--muted); font-size:13px; font-weight:400; margin-left:2px; }}
.cm-kpi.lead b {{ font-size:30px; line-height:38px; font-weight:600; }}
@media (max-width:640px) {{
  .cm-kpis {{ grid-template-columns:repeat(2, minmax(0,1fr)); }}
  .cm-kpi {{ border-left:0; border-top:1px solid var(--border); }}
  .cm-kpi:nth-child(-n+2) {{ border-top:0; }}
  .cm-kpi:nth-child(even) {{ border-left:1px solid var(--border); }}
}}
.cm-table-wrap {{ overflow-x:auto; background:var(--surface); border:1px solid var(--border); border-radius:6px; }}
.cm-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
.cm-table th {{ text-align:left; color:var(--muted); font-weight:400; font-size:12px; height:38px; padding:0 12px;
  border-bottom:1px solid var(--border); white-space:nowrap; }}
.cm-table td {{ height:40px; padding:0 12px; border-bottom:1px solid var(--rule); white-space:nowrap; }}
.cm-table tr:last-child td {{ border-bottom:0; }}
.cm-table .num {{ text-align:right; }}
.cm-table .mono {{ font-family:{MONO}; font-size:12px; }}
.cm-table .dim {{ color:#6f7076; }}
[data-baseweb="tag"] {{ background:var(--raised) !important; border:1px solid var(--control); }}
[data-baseweb="tag"] span {{ color:var(--text) !important; }}
.cm-flow {{ display:flex; flex-direction:column; align-items:stretch; gap:4px; margin:8px 0 10px; width:100%; max-width:420px; }}
.cm-flow > * {{ width:100%; box-sizing:border-box; }}
.cm-node {{ display:flex; justify-content:space-between; gap:12px; background:var(--raised); border:1px solid var(--control);
  border-radius:6px; padding:10px 14px; font-size:14px; font-weight:600; }}
.cm-node span {{ color:var(--muted); font-size:12px; font-weight:400; }}
.cm-node-key {{ border-color:var(--accent); }}
.cm-link {{ display:flex; justify-content:center; gap:24px; color:var(--muted); font-size:12px; padding:2px 0; }}
[data-testid="stElementContainer"]:has(button[data-testid="stBaseButton-tertiary"]) + [data-testid="stElementContainer"] {{ margin-top:-14px; }}
.cm-pill {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; line-height:16px; font-weight:500; }}
.cm-fields {{ display:flex; gap:4px; flex-wrap:wrap; margin:6px 0 14px; }}
.cm-field {{ border-radius:4px; padding:8px 10px 6px; min-width:0; }}
.cm-field code {{ background:transparent !important; color:inherit !important; padding:0; font-size:20px; letter-spacing:2px; }}
.cm-field span {{ display:block; font-size:12px; margin-top:4px; opacity:.85; }}
.cm-kv {{ display:grid; grid-template-columns:auto 1fr; gap:6px 16px; font-size:13px; margin:0 0 14px; }}
.cm-kv dt {{ color:var(--muted); }} .cm-kv dd {{ margin:0; text-align:right; }}
.cm-verdict {{ display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; }}
.cm-verdict code {{ font-size:22px; background:transparent !important; padding:0; }}
.cm-note {{ background:var(--raised); border-radius:6px; padding:12px 14px; font-size:13px; line-height:20px; }}
.cm-legend {{ display:flex; gap:14px; flex-wrap:wrap; color:var(--muted); font-size:12px; margin:8px 0 0; }}
.cm-legend i {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:6px; vertical-align:-1px; }}
.dim {{ color:#6f7076; }}
h2.cm-topic {{ color:var(--text) !important; font-weight:600 !important; font-size:22px !important; }}
.cm-question {{ font-size:17px !important; line-height:26px; margin:4px 0 12px; max-width:68ch; }}
.cm-verdict .dim {{ font-family:{MONO}; font-size:13px; }}
button[data-testid="stBaseButton-tertiary"] {{ padding:0; min-height:0; color:var(--text); font-size:15px; font-weight:600; }}
button[data-testid="stBaseButton-tertiary"]:hover {{ color:var(--text); text-decoration:underline 1px var(--accent); text-underline-offset:5px; }}
[data-testid="stMain"] [role="radiogroup"] label:has(input:checked) p {{ color:var(--text); }}
</style>
"""

BRAND_MARK = f"""<svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
<g fill="{RAISED}" stroke="{CONTROL}" stroke-width="1">
<rect x="1.5" y="1.5" width="8" height="4" rx="1"/><rect x="12.5" y="1.5" width="8" height="4" rx="1"/>
<rect x="1.5" y="9" width="8" height="4" rx="1"/><rect x="1.5" y="16.5" width="8" height="4" rx="1"/>
<rect x="12.5" y="16.5" width="8" height="4" rx="1"/></g>
<rect x="12" y="8.5" width="9" height="5" rx="1" fill="{ACCENT}"/></svg>"""


def esc(value):
    return html.escape(str(value))


def pill(text, bg, ink):
    return f'<span class="cm-pill" style="background:{bg};color:{ink}">{esc(text)}</span>'


def state_pill(state, detail=""):
    bg, ink, label = STATES[state]
    return pill(f"{label}{detail}", bg, ink)


def kpi_strip(items, lead=None):
    """items: list of (label, value, unit). lead: label of the answer figure."""
    cells = "".join(
        f'<div class="cm-kpi{" lead" if label == lead else ""}"><span>{esc(label)}</span>'
        f'<b>{esc(value)}{f"<small>{esc(unit)}</small>" if unit else ""}</b></div>'
        for label, value, unit in items
    )
    return f'<div class="cm-kpis" style="--n:{len(items)}">{cells}</div>'


def table(columns, rows, numeric=(), mono=(), row_styles=None):
    """columns: list of names; rows: list of lists of pre-escaped HTML or plain values."""
    head = "".join(f'<th class="{"num" if c in numeric else ""}">{esc(c)}</th>' for c in columns)
    body = []
    for i, row in enumerate(rows):
        style = f' style="{row_styles[i]}"' if row_styles and row_styles[i] else ""
        cells = "".join(
            f'<td class="{" ".join(k for k, on in (("num", c in numeric), ("mono", c in mono)) if on)}">{v}</td>'
            for c, v in zip(columns, row)
        )
        body.append(f"<tr{style}>{cells}</tr>")
    return f'<div class="cm-table-wrap"><table class="cm-table"><thead><tr>{head}</tr></thead>' \
           f'<tbody>{"".join(body)}</tbody></table></div>'


def fields(parts):
    """parts: list of (bits, label, bg, ink). Renders the address split into fields."""
    cells = "".join(
        f'<div class="cm-field" style="background:{bg};color:{ink}"><code>{esc(bits)}</code>'
        f"<span>{esc(label)}</span></div>"
        for bits, label, bg, ink in parts if bits
    )
    return f'<div class="cm-fields">{cells}</div>'


FIELD_COLOURS = {"tag": (RAISED, TEXT), "index": (ACCENT_BG, ACCENT_INK), "offset": (RULE, MUTED)}


def legend(items):
    return '<div class="cm-legend">' + "".join(
        f'<span><i style="background:{c}"></i>{esc(t)}</span>' for t, c in items) + "</div>"


HIERARCHY_HTML = """<div class="cm-flow" role="img" aria-label="CPU asks the cache; on a miss the cache fetches the block from main memory">
<div class="cm-node">CPU <span>registers</span></div>
<div class="cm-link"><span>address &darr;</span><span>&uarr; data, on a hit</span></div>
<div class="cm-node cm-node-key">Cache <span>small, about 1 ns</span></div>
<div class="cm-link"><span>miss &darr;</span><span>&uarr; the whole block</span></div>
<div class="cm-node">Main memory <span>large, about 100 ns</span></div>
</div>"""


# --------------------------------------------------------------------- charts

def style_chart(chart, height=260):
    return chart.properties(height=height, background="transparent").configure_view(
        strokeWidth=0
    ).configure_axis(
        labelColor=MUTED, titleColor=MUTED, labelFont="Public Sans", titleFont="Public Sans",
        labelFontSize=12, titleFontSize=12, titleFontWeight=400, gridColor=BORDER, domain=False,
        tickColor=BORDER, labelPadding=6,
    ).configure_legend(
        labelColor=MUTED, titleColor=MUTED, labelFont="Public Sans", labelFontSize=12, orient="top",
        title=None, symbolType="square",
    )


DOT_STYLE = (f'bgcolor="transparent"; node [shape=box style="rounded,filled" fillcolor="{RAISED}" '
             f'color="{CONTROL}" fontcolor="{TEXT}" fontname="Helvetica" fontsize=16 margin="0.25,0.12"]; '
             f'edge [color="{MUTED}" fontcolor="{MUTED}" fontname="Helvetica" fontsize=14 arrowsize=0.6];')
