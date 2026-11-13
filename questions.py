"""Challenge-mode question generator. Every answer is computed by the engine."""
from dataclasses import dataclass
import random

from engine import Config, MAPPING_LABELS, decompose, geometry, simulate, summary

DIFFICULTY = {
    # (memory sizes, cache sizes, block sizes, sequence length)
    "Easy": ((256,), (32, 64), (4, 8), 4),
    "Medium": ((1024, 4096), (64, 128), (4, 8, 16), 6),
    "Hard": ((65536,), (256, 512, 1024), (8, 16, 32), 8),
}


@dataclass(frozen=True)
class Question:
    kind: str
    prompt: str
    options: tuple
    answer: int  # index into options
    explanation: str


def _cfg_text(cfg):
    extra = f", {cfg.ways}-way" if cfg.mapping == "set" else ""
    return (f"{cfg.mem_size} B memory, {cfg.cache_size} B cache, {cfg.block_size} B blocks, "
            f"{MAPPING_LABELS[cfg.mapping]}{extra}, {cfg.policy}")


def _fmt(addr, difficulty):
    return hex(addr) if difficulty == "Hard" else str(addr)


def _numeric_options(rng, correct, upper):
    pool = {correct}
    for delta in (1, -1, 2, -2, 4, 8, correct, -correct // 2 or 3):
        if len(pool) == 4:
            break
        candidate = correct + delta
        if 0 <= candidate <= max(upper, 3):
            pool.add(candidate)
    while len(pool) < 4:
        pool.add(rng.randint(0, max(upper, 7)))
    options = sorted(pool)
    rng.shuffle(options)
    return tuple(str(o) for o in options), options.index(correct)


def _random_cfg(rng, difficulty, mapping=None, policy=None):
    mems, caches, blocks, _ = DIFFICULTY[difficulty]
    mapping = mapping or rng.choice(("direct", "fully", "set"))
    cache = rng.choice(caches)
    block = rng.choice(blocks)
    lines = cache // block
    ways = rng.choice([w for w in (2, 4) if w <= lines]) if mapping == "set" else 1
    return Config(rng.choice(mems), cache, block, mapping, ways, policy or rng.choice(("FIFO", "LRU")))


def q_fields(rng, difficulty):
    cfg = _random_cfg(rng, difficulty, mapping=rng.choice(("direct", "set")))
    geo = geometry(cfg)
    addr = rng.randrange(cfg.mem_size)
    a = decompose(cfg, addr)
    field = rng.choice(("tag", "index", "offset"))
    value = getattr(a, field)
    upper = {"tag": 2 ** geo.tag_bits - 1, "index": geo.sets - 1, "offset": cfg.block_size - 1}[field]
    options, answer = _numeric_options(rng, value, upper)
    name = "set index" if cfg.mapping == "set" else "line index"
    label = name if field == "index" else field
    explanation = (
        f"Address {addr} = {a.binary}b. Offset = {geo.offset_bits} bits = {a.offset}; "
        f"block = {addr} div {cfg.block_size} = {a.block}; {name} = {a.block} mod {geo.sets} = {a.index}; "
        f"tag = {a.block} div {geo.sets} = {a.tag}."
    )
    prompt = f"[{_cfg_text(cfg)}] What is the {label} of address {_fmt(addr, difficulty)}?"
    return Question("Tag / index / offset", prompt, options, answer, explanation)


def q_line(rng, difficulty):
    cfg = _random_cfg(rng, difficulty, mapping="direct")
    geo = geometry(cfg)
    addr = rng.randrange(cfg.mem_size)
    a = decompose(cfg, addr)
    options, answer = _numeric_options(rng, a.index, geo.lines - 1)
    explanation = f"Block = {addr} div {cfg.block_size} = {a.block}; line = {a.block} mod {geo.lines} = {a.index}."
    prompt = f"[{_cfg_text(cfg)}] Which cache line does address {_fmt(addr, difficulty)} map to?"
    return Question("Cache line", prompt, options, answer, explanation)


def q_hit_miss(rng, difficulty):
    cfg = _random_cfg(rng, difficulty)
    n = DIFFICULTY[difficulty][3]
    span = min(cfg.mem_size, cfg.cache_size * 4)
    seq = [rng.randrange(span) for _ in range(n - 1)]
    seq.append(rng.choice(seq) if rng.random() < 0.5 else rng.randrange(span))
    last = simulate(cfg, seq).history[-1]
    prompt = (f"[{_cfg_text(cfg)}] Cache starts empty. Accesses: "
              f"{', '.join(_fmt(x, difficulty) for x in seq)}. Is the LAST access a hit or a miss?")
    return Question("Hit or miss", prompt, ("HIT", "MISS"), 0 if last.hit else 1, last.explanation)


def q_replacement(rng, difficulty):
    for _ in range(50):
        cfg = _random_cfg(rng, difficulty, mapping=rng.choice(("fully", "set")))
        geo = geometry(cfg)
        target_set = rng.randrange(geo.sets)
        # Blocks that all land in target_set: target_set + k * sets.
        max_k = geo.mem_blocks // geo.sets
        ks = rng.sample(range(max_k), min(max_k, geo.ways + 1))
        if len(ks) < geo.ways + 1 or geo.ways > 4:
            continue
        blocks = [target_set + k * geo.sets for k in ks]
        fill = blocks[: geo.ways]
        reuse = [rng.choice(fill) for _ in range(rng.randint(1, 2))]
        seq = [b * cfg.block_size for b in fill + reuse + [blocks[-1]]]
        last = simulate(cfg, seq).history[-1]
        if not last.replaced:
            continue
        options = tuple(f"Block {b}" for b in fill)
        prompt = (f"[{_cfg_text(cfg)}] Cache starts empty. Accesses: "
                  f"{', '.join(_fmt(x, difficulty) for x in seq)}. Which block is evicted by the last access?")
        return Question("Replacement", prompt, options, fill.index(last.evicted_block), last.explanation)
    return q_line(rng, difficulty)


def q_best(rng, difficulty):
    for _ in range(50):
        mem, cache = DIFFICULTY[difficulty][0][0], DIFFICULTY[difficulty][1][0]
        seq = [rng.randrange(min(mem, cache * 4)) for _ in range(DIFFICULTY[difficulty][3] + 4)]
        cfgs = [Config(mem, cache, b, m, 2, "LRU") for m, b in (("direct", 4), ("set", 4), ("fully", 8))]
        hits = [summary(simulate(c, seq).history)["hits"] for c in cfgs]
        if hits.count(max(hits)) != 1:
            continue
        options = tuple(_cfg_text(c) for c in cfgs)
        best = hits.index(max(hits))
        explanation = "Hits per option: " + ", ".join(f"option {i + 1}: {h}/{len(seq)}" for i, h in enumerate(hits))
        prompt = f"Which configuration gives the most hits for: {', '.join(_fmt(x, difficulty) for x in seq)}?"
        return Question("Best configuration", prompt, options, best, explanation)
    return q_fields(rng, difficulty)


GENERATORS = (q_fields, q_line, q_hit_miss, q_replacement, q_best)


def generate(difficulty, seed=None):
    rng = random.Random(seed)
    return rng.choice(GENERATORS)(rng, difficulty)
