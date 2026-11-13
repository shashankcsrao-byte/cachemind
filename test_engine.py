import pytest

import questions
import store
from engine import (
    Config, amat, classify_misses, compare_mappings, decompose, geometry,
    optimise, parse_addresses, simulate, split_binary, summary, validate,
)

BASE = Config(mem_size=256, cache_size=32, block_size=4)


# ------------------------------------------------------------- geometry

def test_direct_geometry():
    g = geometry(BASE)
    assert (g.mem_blocks, g.lines, g.sets, g.ways) == (64, 8, 8, 1)
    assert (g.addr_bits, g.tag_bits, g.index_bits, g.offset_bits) == (8, 3, 3, 2)


def test_set_associative_geometry():
    g = geometry(Config(256, 32, 4, "set", 2))
    assert (g.sets, g.ways, g.index_bits, g.tag_bits) == (4, 2, 2, 4)


def test_fully_associative_has_no_index_bits():
    g = geometry(Config(256, 32, 4, "fully"))
    assert (g.sets, g.ways, g.index_bits, g.tag_bits) == (1, 8, 0, 6)


def test_textbook_64kb_example():
    cfg = Config(65536, 2048, 16, "direct")
    g = geometry(cfg)
    assert (g.tag_bits, g.index_bits, g.offset_bits) == (5, 7, 4)
    a = decompose(cfg, 0x1234)
    assert (a.block, a.index, a.tag, a.offset) == (291, 35, 2, 4)


# ----------------------------------------------------------- validation

@pytest.mark.parametrize("cfg, fragment", [
    (Config(256, 48, 4), "power of two"),
    (Config(256, 32, 64), "Block size cannot be larger"),
    (Config(128, 256, 4), "Cache size cannot be larger"),
    (Config(256, 32, 4, "set", 3), "power of two"),
    (Config(256, 32, 4, "set", 16), "more than"),
    (Config(256, 32, 4, policy="RANDOM"), "Unknown replacement"),
    (Config(0, 32, 4), "power of two"),
])
def test_invalid_configs_are_rejected(cfg, fragment):
    errors = validate(cfg)
    assert errors and any(fragment in e for e in errors)
    with pytest.raises(ValueError):
        geometry(cfg)


def test_valid_extremes_accepted():
    assert validate(Config(256, 32, 4, "set", 1)) == []
    assert validate(Config(256, 32, 4, "set", 8)) == []
    assert validate(Config(256, 256, 256, "direct")) == []


# ---------------------------------------------------------- decomposition

def test_decompose_direct():
    a = decompose(BASE, 156)  # 1001 1100
    assert a.binary == "10011100"
    assert (a.block, a.index, a.tag, a.offset) == (39, 7, 4, 0)
    assert split_binary(BASE, 156) == ("100", "111", "00")


def test_decompose_set_and_fully():
    a = decompose(Config(256, 32, 4, "set", 2), 156)
    assert (a.index, a.tag) == (3, 9)
    f = decompose(Config(256, 32, 4, "fully"), 156)
    assert (f.index, f.tag) == (0, 39)
    assert split_binary(Config(256, 32, 4, "fully"), 156) == ("100111", "", "00")


def test_decompose_boundaries():
    assert decompose(BASE, 0).binary == "00000000"
    assert decompose(BASE, 255).tag == 7
    for bad in (-1, 256):
        with pytest.raises(ValueError):
            decompose(BASE, bad)


def test_parse_addresses_formats():
    assert parse_addresses("12, 0x1F 0b101; 20h") == [12, 31, 5, 32]
    assert parse_addresses("  ") == []
    with pytest.raises(ValueError):
        parse_addresses("12 zz")


# ---------------------------------------------------------------- hit / miss

def test_repeated_and_same_block_accesses_hit():
    sim = simulate(BASE, [0, 0, 1, 3, 4])
    assert [r.hit for r in sim.history] == [False, True, True, True, False]


def test_direct_conflict_misses():
    sim = simulate(BASE, [0, 32, 0, 32])
    s = summary(sim.history)
    assert (s["hits"], s["misses"], s["replacements"]) == (0, 4, 3)
    assert all(r.line == 0 for r in sim.history)
    assert sim.history[1].evicted_block == 0


def test_set_associative_removes_conflict():
    sim = simulate(Config(256, 32, 4, "set", 2), [0, 32, 0, 32])
    assert [r.hit for r in sim.history] == [False, False, True, True]


def test_lines_view_reflects_state():
    rows = simulate(BASE, [8]).lines_view()
    assert rows[2]["valid"] == 1 and rows[2]["block"] == 2 and rows[2]["data"] == "M[8..11]"
    assert sum(r["valid"] for r in rows) == 1


# ----------------------------------------------------------- FIFO vs LRU

def test_lru_vs_fifo_in_set():
    seq = [0, 16, 0, 32, 0]  # blocks 0, 4, 0, 8, 0 all in set 0 (4 sets, 2 ways)
    lru = simulate(Config(256, 32, 4, "set", 2, "LRU"), seq)
    fifo = simulate(Config(256, 32, 4, "set", 2, "FIFO"), seq)
    assert [r.hit for r in lru.history] == [False, False, True, False, True]
    assert [r.hit for r in fifo.history] == [False, False, True, False, False]
    assert lru.history[3].evicted_block == 4
    assert fifo.history[3].evicted_block == 0
    assert fifo.history[4].evicted_block == 4


def test_fully_associative_replacement():
    cfg = Config(256, 8, 4, "fully")  # 2 lines
    seq = [0, 4, 0, 8]
    assert simulate(cfg, seq).history[-1].evicted_block == 1  # LRU drops block 1
    fifo = Config(256, 8, 4, "fully", policy="FIFO")
    assert simulate(fifo, seq).history[-1].evicted_block == 0  # FIFO drops oldest


def test_empty_lines_filled_before_replacement():
    sim = simulate(Config(256, 32, 4, "fully"), [i * 4 for i in range(8)])
    assert not any(r.replaced for r in sim.history)
    assert [r.line for r in sim.history] == list(range(8))


# ------------------------------------------------------------- statistics

def test_summary_and_amat():
    s = summary(simulate(BASE, [0, 0, 0, 32]).history)
    assert (s["accesses"], s["hits"], s["misses"]) == (4, 2, 2)
    assert s["hit_ratio"] == 0.5 and s["miss_ratio"] == 0.5
    assert amat(1, 0.5, 100) == 51
    assert summary([])["hit_ratio"] == 0.0


def test_compare_mappings_uses_same_sequence():
    rows = compare_mappings(BASE, [0, 32, 0, 32], ways=2)
    assert [r["hits"] for r in rows] == [0, 2, 2]
    assert all(r["accesses"] == 4 for r in rows)


def test_classify_misses():
    c = classify_misses(BASE, [0, 32, 0, 32])
    assert c == {"compulsory": 2, "capacity": 0, "conflict": 2}


def test_optimiser_ranks_and_skips_invalid():
    rows, skipped = optimise([0, 32, 0, 32], 256, [32, 48], [4], ["direct", "set"], [2])
    assert rows[0]["misses"] == 2 and rows[-1]["misses"] == 4
    assert len(skipped) == 2  # 48 B cache is not a power of two
    assert [r["rank"] for r in rows] == [1, 2]


# ------------------------------------------------------------- questions

@pytest.mark.parametrize("difficulty", ["Easy", "Medium", "Hard"])
def test_questions_are_well_formed(difficulty):
    for seed in range(60):
        q = questions.generate(difficulty, seed)
        assert 0 <= q.answer < len(q.options)
        assert len(set(q.options)) == len(q.options)


# ---------------------------------------------------------------- store

def test_store_roundtrip(tmp_path):
    path = tmp_path / "d.json"
    data = store.load(path)
    data = store.append(data, "scores", {"score": 3})
    store.save(data, path)
    assert store.load(path)["scores"] == [{"score": 3}]
    assert store.remove(data, "scores", 0)["scores"] == []
    assert store.cleared() == {k: [] for k in store.DEFAULT}
