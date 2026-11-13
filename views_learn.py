"""Learning centre, challenge mode and settings pages."""
from datetime import datetime
import random

import streamlit as st

import questions
import store
import theme
from ui_common import bound, esc, persist

DOT = "digraph {{ rankdir=LR; " + theme.DOT_STYLE.replace("{", "{{").replace("}", "}}") + " {} }}"

TOPICS = [
    ("What is cache memory?",
     "A cache is a small, fast memory between the CPU and main memory (RAM). It keeps copies of "
     "recently used blocks so most requests never travel to slow RAM.",
     'CPU -> Cache [label="1 ns"]; Cache -> RAM [label="100 ns"];', None,
     "A loop reads the same array 1000 times. After the first pass the array sits in cache and "
     "later passes run at cache speed.", "Cache Simulator"),
    ("Memory hierarchy",
     "Storage is arranged from small/fast/expensive to large/slow/cheap: registers, L1, L2, L3, "
     "RAM, disk. Each level caches the one below.",
     'Registers -> L1 -> L2 -> L3 -> RAM -> SSD;', None,
     "L1 ~ 32 KB at ~1 ns, RAM ~ 16 GB at ~100 ns, SSD ~ 1 TB at ~100 us.", "Dashboard"),
    ("Cache hits and misses",
     "A hit means the requested block is already in the cache. A miss means it must be fetched "
     "from RAM, possibly evicting another block.",
     'Request -> "In cache?"; "In cache?" -> HIT [label="yes"]; "In cache?" -> MISS [label="no"]; '
     'MISS -> "Fetch block from RAM";', r"\text{Hit ratio} = \frac{\text{Hits}}{\text{Accesses}}",
     "8 accesses, 6 hits: hit ratio = 6/8 = 75%, miss ratio = 25%.", "Cache Simulator"),
    ("Direct mapping",
     "Every memory block has exactly one possible cache line. Simple and fast, but blocks that share a "
     "line keep evicting each other (conflict misses).",
     'B0 -> L0; B8 -> L0; B1 -> L1; B9 -> L1;', r"\text{line} = \text{block} \bmod \text{lines}",
     "8 lines, block 19: line = 19 mod 8 = 3.", "Mapping Laboratory"),
    ("Associative mapping",
     "Fully associative: a block may go in any line. The cache compares the tag against every line. "
     "No conflict misses, but many comparators.",
     'B19 -> L0; B19 -> L1; B19 -> "L...";', r"\text{index bits} = 0",
     "8 lines, block 19: search all 8 tags for 19. If absent and full, evict by FIFO/LRU.", "Mapping Laboratory"),
    ("Set associative mapping",
     "Lines are grouped into sets of k ways. A block maps to one set, but may use any way in it. "
     "A balance between direct and fully associative.",
     'B19 -> "Set 3 (way 0)"; B19 -> "Set 3 (way 1)";',
     r"\text{sets} = \frac{\text{lines}}{k}, \quad \text{set} = \text{block} \bmod \text{sets}",
     "8 lines, 2-way: 4 sets. Block 19 goes to set 19 mod 4 = 3.", "Mapping Laboratory"),
    ("Tag, index and offset",
     "An address splits into tag | index | offset. Offset picks the byte in the block, index picks the "
     "line or set, tag identifies which block is stored there.",
     'Address -> Tag; Address -> Index; Address -> Offset;',
     r"\text{offset} = \log_2 B,\ \text{index} = \log_2 S,\ \text{tag} = n - \text{index} - \text{offset}",
     "256 B memory (8 bits), 4 B blocks, 8 lines direct: offset 2, index 3, tag 3. "
     "Address 156 = 100|111|00: tag 4, line 7, offset 0.", "Address Calculator"),
    ("FIFO replacement",
     "First In, First Out evicts the block that was loaded earliest, even if it is still being used.",
     'A -> B -> C [label="C evicts A"];', None,
     "2 ways, accesses A B A C: C evicts A (oldest load), so the next A misses.", "Cache Simulator"),
    ("LRU replacement",
     "Least Recently Used evicts the block that has gone unused the longest. It usually beats FIFO "
     "because recently used data is likely reused.",
     'A -> B -> A -> C [label="C evicts B"];', None,
     "2 ways, accesses A B A C: A was used at step 3, B at step 2, so C evicts B. Next A hits.", "Cache Simulator"),
    ("Cache performance",
     "Performance depends on the miss types (3C model): compulsory (first touch), capacity "
     "(cache too small) and conflict (too many blocks in one set).",
     'Misses -> Compulsory; Misses -> Capacity; Misses -> Conflict;', None,
     "Bigger blocks cut compulsory misses, bigger caches cut capacity misses, more ways cut conflict misses.",
     "Cache Optimiser"),
    ("AMAT",
     "Average Memory Access Time combines hit time, miss rate and miss penalty into one number.",
     'Access -> "Hit time"; Access -> "Miss rate x Miss penalty";',
     r"AMAT = T_{hit} + \text{Miss rate} \times T_{penalty}",
     "Hit 1 ns, miss rate 5%, penalty 100 ns: AMAT = 1 + 0.05 x 100 = 6 ns.", "Performance Analyzer"),
]


def go(page):
    st.session_state.nav = page


def learning():
    st.title("Learning Centre")
    st.caption("Eleven short topics. Each ends in the module where you can try it.")
    titles = [t[0] for t in TOPICS]
    nav, body = st.columns([1, 3], gap="large")
    with nav:
        st.session_state.setdefault("topic", titles[0])
        choice = st.radio("Topic", titles, label_visibility="collapsed", **bound("topic"))
    title, text, diagram, formula, example, page = TOPICS[titles.index(choice)]
    with body:
        st.markdown(f'<h2 class="cm-topic">{esc(title)}</h2>', unsafe_allow_html=True)
        st.write(text)
        st.graphviz_chart(DOT.format(diagram))
        if formula:
            st.latex(formula)
        st.markdown(f'<div class="cm-note"><b>Worked example.</b> {esc(example)}</div>', unsafe_allow_html=True)
        st.write("")
        st.button(f"Try it in {page}", on_click=go, args=(page,))


# ------------------------------------------------------------------ challenge

def _new_question():
    st.session_state.question = questions.generate(st.session_state.difficulty, random.randrange(10**9))
    st.session_state.answered = None
    st.session_state.choice = None


def _submit():
    q = st.session_state.question
    choice = st.session_state.get("choice")
    if choice is None:
        return
    correct = q.options.index(choice) == q.answer
    st.session_state.answered = correct
    st.session_state.round = {
        "correct": st.session_state.round["correct"] + correct,
        "total": st.session_state.round["total"] + 1,
    }


def _save_score():
    r = st.session_state.round
    if r["total"]:
        entry = {"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "difficulty": st.session_state.difficulty, **r}
        persist(store.append(st.session_state.data, "scores", entry))
    st.session_state.round = {"correct": 0, "total": 0}
    _new_question()


def challenge():
    st.title("Challenge Mode")
    st.session_state.setdefault("difficulty", "Easy")
    st.session_state.setdefault("round", {"correct": 0, "total": 0})
    st.radio("Difficulty", list(questions.DIFFICULTY), horizontal=True, **bound("difficulty"))
    if st.session_state.get("question_difficulty") != st.session_state.difficulty:
        st.session_state.question_difficulty = st.session_state.difficulty
        _new_question()

    r = st.session_state.round
    q = st.session_state.question
    left, right = st.columns([3, 2], gap="large")
    with left:
        context, _, question = q.prompt.partition("] ")
        if not question:
            context, question = "", q.prompt
        st.subheader(q.kind)
        if context:
            st.caption(context.lstrip("["))
        st.markdown(f'<p class="cm-question">{esc(question)}</p>', unsafe_allow_html=True)
        st.radio("Answer", q.options, index=None, key="choice", disabled=st.session_state.answered is not None)
        if st.session_state.answered is None:
            st.button("Submit", on_click=_submit, type="primary")
        else:
            verdict = (theme.pill("Correct", theme.POSITIVE_BG, theme.POSITIVE_INK) if st.session_state.answered
                       else theme.pill(f"Not quite. Answer: {q.options[q.answer]}", theme.NEGATIVE_BG,
                                       theme.NEGATIVE_INK))
            st.markdown(f'{verdict}<div class="cm-note" style="margin-top:10px">{esc(q.explanation)}</div>',
                        unsafe_allow_html=True)
            st.write("")
            st.button("Next question", on_click=_new_question, type="primary")
    with right:
        st.subheader("This round")
        st.markdown(theme.kpi_strip([
            ("Correct", r["correct"], f"/ {r['total']}"),
            ("Accuracy", f"{r['correct'] / r['total']:.0%}" if r["total"] else "–", ""),
        ], lead="Correct"), unsafe_allow_html=True)
        st.button("Finish round and save score", on_click=_save_score, disabled=not r["total"])
        scores = st.session_state.data["scores"]
        if scores:
            st.subheader("Saved scores")
            st.markdown(theme.table(
                ["Date", "Difficulty", "Correct", "Total"],
                [[esc(x["date"]), esc(x["difficulty"]), x["correct"], x["total"]] for x in scores[::-1][:8]],
                numeric={"Correct", "Total"}), unsafe_allow_html=True)


# ------------------------------------------------------------------ settings

LABELS = {"configs": "Saved configurations", "sequences": "Saved address sequences",
          "history": "Simulation history", "scores": "Challenge scores"}


def settings():
    st.title("Settings & Saved Data")
    st.caption(f"Data is stored locally in {store.DATA_FILE}." if store.STORAGE_MODE == "file"
               else "This shared copy keeps your data for this browser session only. It clears on reload.")
    data = st.session_state.data
    for key, label in LABELS.items():
        with st.expander(f"{label} ({len(data[key])})"):
            for i, item in enumerate(data[key]):
                a, b = st.columns([6, 1])
                a.code(str(item), language=None)
                if b.button("Delete", key=f"del_{key}_{i}"):
                    persist(store.remove(data, key, i))
                    st.rerun()
            if data[key] and st.button(f"Clear all {label.lower()}", key=f"clear_{key}"):
                persist(store.cleared(key, data))
                st.rerun()
    st.divider()
    confirm = st.checkbox("I understand this deletes all saved data permanently.")
    if st.button("Reset application", type="primary", disabled=not confirm):
        persist(store.cleared())
        for k in list(st.session_state.keys()):
            if k != "data":
                del st.session_state[k]
        st.rerun()
