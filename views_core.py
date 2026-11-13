"""Dashboard, cache simulator, mapping lab and address calculator pages."""
from dataclasses import asdict
import time

import altair as alt
import pandas as pd
import streamlit as st

import store
from engine import (
    Config, MAPPING_LABELS, compare_mappings, decompose, geometry, parse_int, simulate, summary,
)
import theme
from ui_common import (
    address_layout, bits_html, cache_lines_html, check_range, config_form, config_summary, esc,
    geometry_panel, persist, record_simulation, sequence_input,
)

PLAY_DELAY_S = 0.7


def go(page):
    st.session_state.nav = page


# ------------------------------------------------------------------ dashboard

MODULES = {
    "Cache Simulator": "Step through accesses and watch each cache line change.",
    "Mapping Laboratory": "Run one sequence through direct, fully and set associative.",
    "Address Calculator": "Split any address into tag, index and offset.",
    "Performance Analyzer": "Hit ratio over time and AMAT for your timings.",
    "Cache Optimiser": "Rank every cache size, block size and mapping on your workload.",
    "Learning Centre": "Eleven short topics with diagrams and worked examples.",
    "Challenge Mode": "Practice questions with instant feedback and saved scores.",
    "Settings": "Saved configurations, sequences, history and scores.",
}


def _pct(part, whole):
    return f"{part / whole:.1%}" if whole else "–"


def dashboard(pages):
    st.title("Overview")
    history = st.session_state.data["history"]
    accesses = sum(h["accesses"] for h in history)
    hits = sum(h["hits"] for h in history)
    if history:
        best = max(history, key=lambda h: (h["hits"] / h["accesses"] if h["accesses"] else 0))
        c = best["config"]
        st.caption(f"{len(history)} completed run{'' if len(history) == 1 else 's'}. Best hit ratio {_pct(best['hits'], best['accesses'])} on "
                   f"{MAPPING_LABELS[c['mapping']].lower()}, {c['cache_size']} B cache, {c['block_size']} B blocks.")
    else:
        st.caption("No runs yet. Step through an example sequence and the totals below fill in.")
    st.button("Open the simulator", type="primary", on_click=go, args=("Cache Simulator",))

    st.markdown(theme.kpi_strip([
        ("Overall hit rate", _pct(hits, accesses), ""),
        ("Overall miss rate", _pct(accesses - hits, accesses), ""),
        ("Completed runs", len(history), ""),
        ("Memory accesses", f"{accesses:,}", ""),
    ], lead="Overall hit rate"), unsafe_allow_html=True)

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Recent runs")
        recent = history[-5:][::-1]
        if recent:
            rows = [[esc(MAPPING_LABELS[h["config"]["mapping"]]) + (f' {h["config"]["ways"]}-way'
                     if h["config"]["mapping"] == "set" else ""),
                     h["config"]["cache_size"], h["config"]["block_size"], h["config"]["policy"],
                     h["accesses"], h["hits"], _pct(h["hits"], h["accesses"])] for h in recent]
            st.markdown(theme.table(["Mapping", "Cache B", "Block B", "Policy", "Accesses", "Hits", "Hit ratio"],
                                    rows, numeric={"Cache B", "Block B", "Accesses", "Hits", "Hit ratio"}),
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="cm-note">Runs appear here once a sequence is stepped to the end.</div>',
                        unsafe_allow_html=True)
    with right:
        st.subheader("Where a request goes")
        st.markdown(theme.HIERARCHY_HTML, unsafe_allow_html=True)
        st.caption("The cache answers first. On a miss the whole block comes up from RAM.")

    st.subheader("Modules")
    cols = st.columns(2, gap="large")
    for i, (page, blurb) in enumerate(MODULES.items()):
        with cols[i % 2]:
            st.button(page, key=f"quick_{page}", on_click=go, args=(page,), type="tertiary")
            st.caption(blurb)


# ------------------------------------------------------------------ simulator

def _sim_state(cfg, seq):
    sig = (cfg, tuple(seq))
    if st.session_state.get("sim_sig") != sig:
        st.session_state.sim_sig = sig
        st.session_state.sim_pos = 0
        st.session_state.playing = False
        st.session_state.recorded = False


def _step(n):
    st.session_state.sim_pos = min(st.session_state.sim_pos + n, st.session_state.sim_len)


def _reset():
    st.session_state.sim_pos = 0
    st.session_state.playing = False
    st.session_state.recorded = False


def _toggle_play():
    st.session_state.playing = not st.session_state.playing


def _add_address():
    token = st.session_state.manual_addr.strip()
    if token:
        current = st.session_state.seq_text.strip()
        st.session_state.seq_text = f"{current} {token}".strip()
        st.session_state.manual_addr = ""
        st.session_state.pending_step = True


def _access_panel(cfg, last, next_address):
    st.subheader("This access")
    if last is None:
        hint = f" Step reads address {next_address} first." if next_address is not None else ""
        st.markdown(f'<div class="cm-note">Nothing accessed yet. The cache starts empty, every valid bit 0.'
                    f'{esc(hint)}</div>', unsafe_allow_html=True)
        return
    a = last.addr
    state = "hit" if last.hit else "replace" if last.replaced else "load"
    st.markdown(f'<div class="cm-verdict"><code>{a.address}</code><span class="dim">0x{a.address:X}</span>'
                f"{theme.state_pill(state)}</div>", unsafe_allow_html=True)
    index_value = a.index if cfg.mapping != "fully" else None
    st.markdown(bits_html(cfg, a.address, (a.tag, index_value if index_value is not None else "-", a.offset)),
                unsafe_allow_html=True)
    where = {"direct": "Cache line", "fully": "Placement", "set": "Set"}[cfg.mapping]
    where_value = a.index if cfg.mapping != "fully" else "any line"
    replaced = f"block {last.evicted_block} evicted" if last.replaced else "none"
    st.markdown(
        f'<dl class="cm-kv"><dt>Memory block</dt><dd>{a.block}</dd><dt>{where}</dt><dd>{where_value}</dd>'
        f"<dt>Line used</dt><dd>{last.line}</dd><dt>Replacement</dt><dd>{replaced}</dd></dl>"
        f'<div class="cm-note">{esc(last.explanation)}</div>', unsafe_allow_html=True)


def simulator():
    st.title("Cache Simulator")
    cfg = st.session_state.cfg
    with st.expander(f"Configuration: {config_summary(cfg)}", expanded=False):
        cfg, errors = config_form("sim", st.session_state.cfg)
        if errors:
            return
        st.session_state.cfg = cfg
        geometry_panel(cfg)
        if st.button("Save this configuration"):
            persist(store.append(st.session_state.data, "configs", asdict(cfg)))
            st.toast("Configuration saved")
    st.caption(address_layout(cfg))

    left, right = st.columns([3, 2], gap="large")
    with left:
        seq, err = sequence_input()
    with right:
        st.text_input("Access one more address", key="manual_addr", placeholder="0x2C or 44")
        with st.container(horizontal=True, gap="small"):
            st.button("Access", on_click=_add_address)
            save = st.button("Save sequence")
        if save and seq:
            persist(store.append(st.session_state.data, "sequences", st.session_state.seq_text))
            st.toast("Sequence saved")
    if err:
        st.error(err)
        return
    if not seq:
        st.markdown('<div class="cm-note">Enter at least one address, or load an example above.</div>',
                    unsafe_allow_html=True)
        return
    if not check_range(cfg, seq):
        return

    _sim_state(cfg, seq)
    st.session_state.sim_len = len(seq)
    if st.session_state.pop("pending_step", False):
        st.session_state.sim_pos = len(seq) - 1
        _step(1)

    pos = st.session_state.sim_pos
    done = pos >= len(seq)
    with st.container(horizontal=True, gap="small"):
        st.button("Step", type="primary", on_click=_step, args=(1,), disabled=done, width=96)
        st.button("Pause" if st.session_state.playing else "Play", on_click=_toggle_play, disabled=done, width=96)
        st.button("Run all", on_click=_step, args=(len(seq),), disabled=done, width=96)
        st.button("Reset", on_click=_reset, disabled=pos == 0, width=96)
    st.progress(pos / len(seq), text=f"Step {pos} of {len(seq)}")

    sim = simulate(cfg, seq[:pos])
    last = sim.history[-1] if sim.history else None
    stats = summary(sim.history)

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Cache lines")
        st.markdown(cache_lines_html(cfg, sim.lines_view(), last) + theme.legend([
            ("Hit", theme.POSITIVE_INK), ("Miss, loaded into an empty line", theme.WARNING_INK),
            ("Miss, replaced a block", theme.NEGATIVE_INK)]), unsafe_allow_html=True)
    with right:
        _access_panel(cfg, last, seq[pos] if not done else None)

    st.markdown(theme.kpi_strip([
        ("Accesses", stats["accesses"], ""), ("Hits", stats["hits"], ""), ("Misses", stats["misses"], ""),
        ("Hit ratio", f"{stats['hit_ratio']:.1%}" if stats["accesses"] else "–", ""),
        ("Replacements", stats["replacements"], ""),
    ]), unsafe_allow_html=True)

    if sim.history:
        with st.expander("Access log"):
            st.dataframe(pd.DataFrame([{
                "Step": r.step, "Address": r.addr.address, "Binary": r.addr.binary, "Tag": r.addr.tag,
                "Index": r.addr.index, "Offset": r.addr.offset, "Block": r.addr.block,
                "Result": "Hit" if r.hit else "Miss", "Line": r.line,
                "Evicted block": r.evicted_block if r.replaced else None,
            } for r in sim.history]), hide_index=True, use_container_width=True)

    if done and not st.session_state.recorded:
        record_simulation(cfg, stats)
        st.session_state.recorded = True
        st.session_state.playing = False

    if st.session_state.playing and not done:
        time.sleep(PLAY_DELAY_S)
        _step(1)
        st.rerun()


# ------------------------------------------------------------------ mapping lab

def comparison_chart(rows):
    """Hits and misses per mapping as one stacked bar each; hits carry the hue."""
    data = pd.DataFrame([{"Mapping": r["mapping"], "Result": k.capitalize(), "Accesses": r[k],
                          "order": i} for r in rows for i, k in enumerate(("hits", "misses"))])
    chart = alt.Chart(data).mark_bar(height=22, cornerRadius=2).encode(
        y=alt.Y("Mapping:N", sort=None, title=None),
        x=alt.X("Accesses:Q", title="Accesses", axis=alt.Axis(tickMinStep=1, grid=True)),
        color=alt.Color("Result:N", scale=alt.Scale(domain=["Hits", "Misses"],
                                                    range=[theme.ACCENT, theme.NEUTRAL_BAR])),
        order="order:Q",
        tooltip=["Mapping", "Result", "Accesses"],
    )
    return theme.style_chart(chart, height=40 * len(rows) + 50)


def mapping_lab():
    st.title("Mapping Laboratory")
    cfg = st.session_state.cfg
    st.caption(f"Same sequence, same sizes: {cfg.mem_size} B memory, {cfg.cache_size} B cache, "
               f"{cfg.block_size} B blocks, {cfg.policy}. Change sizes in the simulator.")
    geo = geometry(cfg)
    ways_choices = [w for w in (2, 4, 8, 16) if w <= geo.lines] or [1]
    left, right = st.columns([3, 1], gap="large")
    with right:
        ways = st.selectbox("Ways for set associative", ways_choices)
    with left:
        seq, err = sequence_input()
    if err:
        st.error(err)
        return
    if not seq or not check_range(cfg, seq):
        return
    rows = compare_mappings(cfg, seq, ways)
    best = max(rows, key=lambda r: r["hits"])
    ties = [r for r in rows if r["hits"] == best["hits"]]
    finding = (f"{best['mapping']} hits most: {best['hits']} of {best['accesses']}." if len(ties) == 1
               else f"{len(ties)} mappings tie at {best['hits']} hits of {best['accesses']}.")
    st.subheader(finding)
    st.altair_chart(comparison_chart(rows), use_container_width=True, theme=None)
    st.markdown(theme.table(
        ["Mapping", "Hits", "Misses", "Hit ratio", "Miss ratio", "Replacements"],
        [[esc(r["mapping"]), r["hits"], r["misses"], f"{r['hit_ratio']:.1%}", f"{r['miss_ratio']:.1%}",
          r["replacements"]] for r in rows],
        numeric={"Hits", "Misses", "Hit ratio", "Miss ratio", "Replacements"}), unsafe_allow_html=True)
    st.markdown("""
- **Direct**: line = block mod lines. Cheap, but two busy blocks on one line evict each other.
- **Fully associative**: any line; every tag is searched. No conflict misses, costly hardware.
- **Set associative**: set = block mod sets; only that set is searched. The usual compromise.
""")
    with st.expander("Hit and miss per step"):
        trace = []
        for mapping in ("direct", "fully", "set"):
            mcfg = Config(cfg.mem_size, cfg.cache_size, cfg.block_size, mapping, ways, cfg.policy)
            trace.append([esc(MAPPING_LABELS[mapping])] + [
                theme.state_pill("hit") if r.hit else theme.state_pill("replace" if r.replaced else "load")
                for r in simulate(mcfg, seq).history])
        st.markdown(theme.table(["Mapping"] + [str(a) for a in seq], trace), unsafe_allow_html=True)


# ------------------------------------------------------------- address calculator

def address_calculator():
    st.title("Address Calculator")
    st.caption("Any address, split into the fields the cache hardware reads.")
    cfg, errors = config_form("calc", st.session_state.get("calc_cfg", st.session_state.cfg), show_policy=False)
    if errors:
        return
    st.session_state.calc_cfg = cfg
    text = st.text_input("Memory address (decimal, 0x hex or 0b binary)", "0x9C")
    try:
        address = parse_int(text)
        a = decompose(cfg, address)
    except ValueError as exc:
        st.error(str(exc))
        return
    g = geometry(cfg)
    where = {"direct": "Cache line", "fully": "Placement", "set": "Set"}[cfg.mapping]
    st.markdown(bits_html(cfg, address, (a.tag, a.index if cfg.mapping != "fully" else "-", a.offset)),
                unsafe_allow_html=True)
    st.markdown(theme.kpi_strip([
        ("Address", address, f"0x{address:X}"), ("Block number", a.block, ""),
        (where, a.index if cfg.mapping != "fully" else "any", ""), ("Offset in block", a.offset, "bytes"),
    ]), unsafe_allow_html=True)
    rule = {
        "direct": f"Line = block mod lines = {a.block} mod {g.lines} = **{a.index}**.",
        "fully": "Fully associative has no index. The block can go in any line; the whole block number is the tag.",
        "set": f"Set = block mod sets = {a.block} mod {g.sets} = **{a.index}**. It may use any of the {g.ways} ways.",
    }[cfg.mapping]
    st.markdown(f"""
1. Binary address ({g.addr_bits} bits, since log2({cfg.mem_size}) = {g.addr_bits}): `{esc(a.binary)}`
2. **Offset** = lowest {g.offset_bits} bits = address mod {cfg.block_size} = **{a.offset}**, the byte inside the block.
3. **Block number** = address div {cfg.block_size} = **{a.block}**.
4. {rule}
5. **Tag** = remaining {g.tag_bits} high bits = block div {g.sets} = **{a.tag}**.
""")
    geometry_panel(cfg)
