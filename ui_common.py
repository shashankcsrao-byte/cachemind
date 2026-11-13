"""Shared Streamlit widgets and state helpers."""
from dataclasses import asdict
import streamlit as st

import store
import theme
from engine import MAPPING_LABELS, POLICIES, Config, geometry, parse_addresses, split_binary, validate
from theme import CSS, esc  # noqa: F401  (re-exported for views)

DEFAULT_CFG = Config(mem_size=256, cache_size=32, block_size=4, mapping="direct", ways=2, policy="LRU")

EXAMPLES = {
    "Sequential walk (spatial locality)": "0 4 8 12 16 20 24 28 32 36 40 44",
    "Loop with reuse (temporal locality)": "0 4 8 12 0 4 8 12 16 0 4",
    "Direct-mapping conflict (0 and 32 share a line)": "0 32 0 32 64 0 32",
    "FIFO vs LRU (2-way, set 0)": "0 16 0 32 0 16",
    "Hex addresses, mixed offsets": "0x00 0x05 0x20 0x26 0x9C 0x00 0x41 0x9D",
}



def _copy_state(src, dst):
    st.session_state[dst] = st.session_state[src]


def bound(store_key):
    """Widget kwargs that keep a widget in sync with a durable session key.

    Streamlit drops widget state when a page is not rendered, so the value
    lives in store_key and the widget (key "_w_<store_key>") mirrors it.
    """
    widget_key = f"_w_{store_key}"
    st.session_state[widget_key] = st.session_state[store_key]
    return {"key": widget_key, "on_change": _copy_state, "args": (widget_key, store_key)}


def init_state():
    if "data" not in st.session_state:
        try:
            st.session_state.data = store.load() if store.STORAGE_MODE == "file" else store.cleared()
        except RuntimeError as exc:
            st.error(f"{exc}. Starting with empty data.")
            st.session_state.data = store.cleared()
    st.session_state.setdefault("cfg", DEFAULT_CFG)
    st.session_state.setdefault("seq_text", EXAMPLES["Loop with reuse (temporal locality)"])
    st.session_state.setdefault("hit_time", 1.0)
    st.session_state.setdefault("miss_penalty", 100.0)


def persist(new_data):
    st.session_state.data = new_data
    if store.STORAGE_MODE != "file":
        return
    try:
        store.save(new_data)
    except OSError as exc:
        st.error(f"Could not save data: {exc}")


def record_simulation(cfg, stats):
    entry = {"config": asdict(cfg), **{k: stats[k] for k in ("accesses", "hits", "misses", "replacements")}}
    persist(store.append(st.session_state.data, "history", entry))


def config_form(prefix, cfg, show_policy=True):
    """Inputs for a cache configuration. Returns (Config, errors)."""
    c1, c2, c3 = st.columns(3)
    mem = c1.number_input("Main memory (bytes)", 1, 2**32, cfg.mem_size, key=f"{prefix}_mem")
    cache = c2.number_input("Cache size (bytes)", 1, 2**32, cfg.cache_size, key=f"{prefix}_cache")
    block = c3.number_input("Block size (bytes)", 1, 2**32, cfg.block_size, key=f"{prefix}_block")
    c4, c5, c6 = st.columns(3)
    mappings = list(MAPPING_LABELS)
    mapping = c4.selectbox("Mapping", mappings, mappings.index(cfg.mapping),
                           format_func=MAPPING_LABELS.get, key=f"{prefix}_map")
    ways = c5.number_input("Ways (set associative)", 1, 1024, cfg.ways, key=f"{prefix}_ways",
                           disabled=mapping != "set")
    policy = cfg.policy
    if show_policy:
        policy = c6.selectbox("Replacement", POLICIES, POLICIES.index(cfg.policy), key=f"{prefix}_pol")
    new_cfg = Config(int(mem), int(cache), int(block), mapping, int(ways), policy)
    errors = validate(new_cfg)
    for e in errors:
        st.error(e)
    return new_cfg, errors


def config_summary(cfg):
    g = geometry(cfg)
    ways = f", {g.ways}-way" if cfg.mapping == "set" else ""
    return (f"{MAPPING_LABELS[cfg.mapping]}{ways} · {cfg.cache_size} B cache · "
            f"{cfg.block_size} B blocks · {cfg.policy}")


def address_layout(cfg):
    g = geometry(cfg)
    return (f"{g.addr_bits}-bit address = {g.tag_bits} tag + {g.index_bits} index + {g.offset_bits} offset bits. "
            f"{g.lines} lines in {g.sets} {'set' if g.sets == 1 else 'sets'} of {g.ways}.")


def geometry_panel(cfg):
    g = geometry(cfg)
    st.markdown(theme.kpi_strip([
        ("Memory blocks", g.mem_blocks, ""), ("Cache lines", g.lines, ""), ("Sets", g.sets, ""),
        ("Address", g.addr_bits, "bits"), ("Tag", g.tag_bits, "bits"),
        ("Index", g.index_bits, "bits"), ("Offset", g.offset_bits, "bits"),
    ]), unsafe_allow_html=True)
    with st.expander("How these numbers are calculated"):
        idx = {
            "direct": f"log2(lines) = log2({g.lines}) = {g.index_bits}. Each block has exactly one line.",
            "fully": "0. A block may go in any line, so no index is needed.",
            "set": f"log2(sets) = log2({g.lines} / {g.ways}) = log2({g.sets}) = {g.index_bits}",
        }[cfg.mapping]
        st.markdown(f"""
- **Memory blocks** = memory / block = {cfg.mem_size} / {cfg.block_size} = **{g.mem_blocks}**
- **Cache lines** = cache / block = {cfg.cache_size} / {cfg.block_size} = **{g.lines}**
- **Sets** = lines / ways = {g.lines} / {g.ways} = **{g.sets}**
- **Address bits** = log2(memory) = log2({cfg.mem_size}) = **{g.addr_bits}**
- **Offset bits** = log2(block) = log2({cfg.block_size}) = **{g.offset_bits}**
- **Index bits** = {idx}
- **Tag bits** = address − index − offset = {g.addr_bits} − {g.index_bits} − {g.offset_bits} = **{g.tag_bits}**

All sizes must be powers of two so each field is a whole number of bits.
""")


def bits_html(cfg, address, values=None):
    """The address split into coloured fields. values: optional (tag, index, offset) decimals."""
    tag, idx, off = split_binary(cfg, address)
    names = ("tag", "index", "offset")
    parts = []
    for i, (bits, name) in enumerate(zip((tag, idx, off), names)):
        label = f"{name} · {len(bits)} bits" + (f" = {values[i]}" if values else "")
        parts.append((bits, label, *theme.FIELD_COLOURS[name]))
    return theme.fields(parts)


def sequence_input(key="seq_text", label="Address sequence (decimal, 0x hex or 0b binary)"):
    st.session_state.setdefault(key, EXAMPLES["Loop with reuse (temporal locality)"])
    saved = st.session_state.data["sequences"]
    choices = ["-"] + list(EXAMPLES) + [f"Saved: {s}" for s in saved]
    example = st.selectbox("Load example or saved sequence", choices, key=f"{key}_example")
    if example != "-" and st.session_state.get(f"{key}_last_example") != example:
        st.session_state[key] = EXAMPLES.get(example, example.removeprefix("Saved: "))
    st.session_state[f"{key}_last_example"] = example
    text = st.text_area(label, height=80, **bound(key))
    try:
        return parse_addresses(text), None
    except ValueError as exc:
        return [], str(exc)


def check_range(cfg, addresses):
    bad = [a for a in addresses if not 0 <= a < cfg.mem_size]
    if bad:
        st.error(f"Addresses outside memory 0 to {cfg.mem_size - 1}: {', '.join(map(str, bad[:10]))}")
        return False
    return True


def cache_lines_html(cfg, rows, last=None):
    """The cache as its lines. The line touched by `last` carries its result state."""
    g = geometry(cfg)
    show_set = cfg.mapping != "direct"
    columns = ["Line"] + (["Set", "Way"] if show_set else []) + ["V", "Tag", "Block", "Holds bytes",
                                                                 "Loaded", "Last used", "This step"]
    state = None
    if last is not None:
        state = "hit" if last.hit else "replace" if last.replaced else "load"
    body, styles = [], []
    for r in rows:
        valid = r["valid"] == 1
        dash = '<span class="dim">–</span>'
        tag_bits = format(r["tag"], f"0{g.tag_bits}b") if valid and g.tag_bits else ""
        tag_cell = f'{tag_bits} <span class="dim">({r["tag"]})</span>' if valid and g.tag_bits else (
            "0 bits" if valid else dash)
        cells = [r["line"]] + ([r["set"], r["way"]] if show_set else []) + [
            "1" if valid else '<span class="dim">0</span>',
            tag_cell,
            r["block"] if valid else dash,
            esc(r["data"]) if valid else dash,
            r["loaded at"] if valid else dash,
            r["last used"] if valid else dash,
            "",
        ]
        style = ""
        if last is not None and r["line"] == last.line:
            bg = theme.STATES[state][0]
            detail = f" (block {last.evicted_block} out)" if state == "replace" else ""
            cells[-1] = theme.state_pill(state, detail)
            style = f"background:{bg}"
        body.append(cells)
        styles.append(style)
    numeric = {"Line", "Set", "Way", "Block", "Loaded", "Last used"}
    return theme.table(columns, body, numeric=numeric, mono={"Tag", "V"}, row_styles=styles)
