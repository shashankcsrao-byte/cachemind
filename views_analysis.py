"""Performance analyzer and cache optimiser pages."""
import altair as alt
import pandas as pd
import streamlit as st

import theme
from engine import Config, MAPPING_LABELS, amat, compare_mappings, explain_best, geometry, optimise, simulate, summary
from ui_common import bound, check_range, config_summary, esc, sequence_input

POW2_SIZES = [2 ** i for i in range(2, 13)]
MAX_RANKED_BARS = 10


def timing_inputs():
    c1, c2 = st.columns(2)
    c1.number_input("Hit time (cycles or ns)", 0.0, 1e6, step=1.0, **bound("hit_time"))
    c2.number_input("Miss penalty (cycles or ns)", 0.0, 1e6, step=10.0, **bound("miss_penalty"))
    return st.session_state.hit_time, st.session_state.miss_penalty


def hit_ratio_chart(history):
    rows, hits = [], 0
    for i, r in enumerate(history, 1):
        hits += r.hit
        rows.append({"Access": i, "Hit ratio": hits / i, "Result": "Hit" if r.hit else "Miss"})
    base = alt.Chart(pd.DataFrame(rows)).encode(
        x=alt.X("Access:Q", axis=alt.Axis(tickMinStep=1, grid=False), scale=alt.Scale(domain=[1, len(rows)])),
        y=alt.Y("Hit ratio:Q", axis=alt.Axis(format="%", tickCount=5), scale=alt.Scale(domain=[0, 1])),
        tooltip=["Access", "Result", alt.Tooltip("Hit ratio:Q", format=".1%")],
    )
    return theme.style_chart(base.mark_line(color=theme.ACCENT, strokeWidth=2), height=240)


def ranked_bars(data, label, value, fmt, highlight, title):
    """Horizontal bars, one hue: the highlighted rows in the accent, the rest neutral."""
    chart = alt.Chart(data).mark_bar(height=18, cornerRadius=2).encode(
        y=alt.Y(f"{label}:N", sort=None, title=None, axis=alt.Axis(labelLimit=320)),
        x=alt.X(f"{value}:Q", title=title, axis=alt.Axis(format=fmt, tickCount=5)),
        color=alt.condition(alt.FieldOneOfPredicate(field=label, oneOf=list(highlight)),
                            alt.value(theme.ACCENT), alt.value(theme.NEUTRAL_BAR)),
        tooltip=[label, alt.Tooltip(f"{value}:Q", format=fmt)],
    )
    return theme.style_chart(chart, height=30 * len(data) + 50)


def performance():
    st.title("Performance Analyzer")
    finding = st.empty()
    cfg = st.session_state.cfg
    hit_time, penalty = timing_inputs()
    seq, err = sequence_input()
    if err:
        st.error(err)
        return
    if not seq or not check_range(cfg, seq):
        return

    sim = simulate(cfg, seq)
    s = summary(sim.history)
    t = amat(hit_time, s["miss_ratio"], penalty)
    finding.caption(f"{config_summary(cfg)}. AMAT {t:.2f} with {s['misses']} misses in {s['accesses']} accesses.")
    st.markdown(theme.kpi_strip([
        ("AMAT", f"{t:.2f}", "cycles"), ("Hit ratio", f"{s['hit_ratio']:.1%}", ""),
        ("Miss ratio", f"{s['miss_ratio']:.1%}", ""), ("Hits", s["hits"], f"/ {s['accesses']}"),
        ("Misses", s["misses"], ""), ("Replacements", s["replacements"], ""),
    ], lead="AMAT"), unsafe_allow_html=True)
    st.latex(rf"AMAT = T_{{hit}} + \text{{miss ratio}} \times T_{{penalty}} = {hit_time:g} + "
             rf"{s['misses']}/{s['accesses']} \times {penalty:g} = {t:.2f}")

    st.subheader("Hit ratio after each access")
    st.altair_chart(hit_ratio_chart(sim.history), use_container_width=True, theme=None)

    geo = geometry(cfg)
    ways = cfg.ways if cfg.mapping == "set" else min(2, geo.lines)
    rows = [{**r, "AMAT": amat(hit_time, r["miss_ratio"], penalty)} for r in compare_mappings(cfg, seq, ways)]
    low = min(r["AMAT"] for r in rows)
    best = [r["mapping"] for r in rows if r["AMAT"] == low]
    st.subheader(f"Lowest AMAT on this sequence: {best[0]}, {low:.2f}" if len(best) == 1
                 else f"{len(best)} mappings tie at AMAT {low:.2f} on this sequence")
    df = pd.DataFrame(rows)
    st.altair_chart(ranked_bars(df, "mapping", "AMAT", ".2f", best, "AMAT (cycles)"),
                    use_container_width=True, theme=None)
    st.markdown(theme.table(
        ["Mapping", "Hits", "Misses", "Hit ratio", "Miss ratio", "AMAT"],
        [[esc(r["mapping"]), r["hits"], r["misses"], f"{r['hit_ratio']:.1%}", f"{r['miss_ratio']:.1%}",
          f"{r['AMAT']:.2f}"] for r in rows],
        numeric={"Hits", "Misses", "Hit ratio", "Miss ratio", "AMAT"}), unsafe_allow_html=True)


def optimiser():
    st.title("Cache Optimiser")
    st.caption("Every valid combination runs on your workload and is ranked by misses, which orders hit "
               "ratio and AMAT the same way. Ties go to the smaller, simpler cache.")
    left, right = st.columns([3, 2], gap="large")
    with left:
        seq, err = sequence_input()
    with right:
        c1, c2 = st.columns(2)
        mem = c1.selectbox("Main memory (bytes)", [2 ** i for i in range(8, 21)], index=0)
        policy = c2.selectbox("Replacement", ["LRU", "FIFO"])
        hit_time, penalty = timing_inputs()
    if err:
        st.error(err)
        return
    c3, c4 = st.columns(2)
    cache_sizes = c3.multiselect("Cache sizes to try (bytes)", POW2_SIZES, [16, 32, 64])
    block_sizes = c4.multiselect("Block sizes to try (bytes)", POW2_SIZES[:7], [4, 8])
    c5, c6 = st.columns(2)
    mappings = c5.multiselect("Mappings", list(MAPPING_LABELS), list(MAPPING_LABELS), format_func=MAPPING_LABELS.get)
    ways = c6.multiselect("Ways (set associative)", [2, 4, 8, 16], [2, 4])

    missing = [name for name, chosen in (("an address sequence", seq), ("a cache size", cache_sizes),
                                         ("a block size", block_sizes), ("a mapping", mappings)) if not chosen]
    if "set" in mappings and not ways:
        missing.append("a number of ways")
    if missing:
        st.warning("Pick " + ", ".join(missing) + " to rank configurations.")
        return
    if not check_range(Config(mem, mem, 1), seq):
        return
    rows, skipped = optimise(seq, mem, cache_sizes, block_sizes, mappings, ways, policy, hit_time, penalty)
    if not rows:
        st.error("No valid configuration. Make the cache at least as big as the block and no bigger than memory.")
        return

    best = rows[0]
    st.subheader(f"Best: {best['mapping']}, {best['cache size']} B cache, {best['block size']} B blocks")
    st.markdown(theme.kpi_strip([
        ("Hit ratio", f"{best['hit_ratio']:.1%}", ""), ("Misses", best["misses"], f"/ {best['accesses']}"),
        ("AMAT", f"{best['AMAT']:.2f}", "cycles"), ("Configurations ranked", len(rows), ""),
    ], lead="Hit ratio"), unsafe_allow_html=True)
    st.markdown(f'<div class="cm-note">{esc(explain_best(rows, seq))}</div>', unsafe_allow_html=True)

    top = pd.DataFrame([{"Configuration": f"{r['rank']}. {r['mapping']} {r['cache size']} B / {r['block size']} B",
                         "Hit ratio": r["hit_ratio"]} for r in rows[:MAX_RANKED_BARS]])
    st.subheader(f"Top {len(top)} by hit ratio")
    st.altair_chart(ranked_bars(top, "Configuration", "Hit ratio", "%", [top["Configuration"][0]], "Hit ratio"),
                    use_container_width=True, theme=None)
    with st.expander(f"All {len(rows)} ranked configurations"):
        st.markdown(theme.table(
            ["Rank", "Mapping", "Cache B", "Block B", "Hits", "Misses", "Hit ratio", "AMAT"],
            [[r["rank"], esc(r["mapping"]), r["cache size"], r["block size"], r["hits"], r["misses"],
              f"{r['hit_ratio']:.1%}", f"{r['AMAT']:.2f}"] for r in rows],
            numeric={"Rank", "Cache B", "Block B", "Hits", "Misses", "Hit ratio", "AMAT"}), unsafe_allow_html=True)
    if skipped:
        with st.expander(f"{len(skipped)} combinations skipped as invalid"):
            for cfg, reason in skipped:
                st.write(f"{cfg.cache_size} B cache, {cfg.block_size} B block, {MAPPING_LABELS[cfg.mapping]}"
                         f"{f' {cfg.ways}-way' if cfg.mapping == 'set' else ''}: {reason}")
