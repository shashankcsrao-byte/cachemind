"""CacheMind simulation engine.

Pure Python, no UI imports, so it can be unit-tested on its own.

Assumptions (stated, then validated):
* Memory is byte-addressable.
* Main memory size, cache size, block size and the number of ways are
  powers of two, so every address field is a whole number of bits.
* Address arithmetic uses integers and bit operations only.
"""
from dataclasses import dataclass, replace
import re

MAPPINGS = ("direct", "fully", "set")
MAPPING_LABELS = {
    "direct": "Direct mapping",
    "fully": "Fully associative",
    "set": "Set associative",
}
POLICIES = ("FIFO", "LRU")


def is_pow2(n):
    return isinstance(n, int) and n > 0 and n & (n - 1) == 0


def log2(n):
    """Exact log2 of a power of two."""
    return n.bit_length() - 1


@dataclass(frozen=True)
class Config:
    mem_size: int  # bytes
    cache_size: int  # bytes
    block_size: int  # bytes
    mapping: str = "direct"
    ways: int = 1  # used only by set-associative mapping
    policy: str = "LRU"


@dataclass(frozen=True)
class Geometry:
    mem_blocks: int
    lines: int
    sets: int
    ways: int
    addr_bits: int
    offset_bits: int
    index_bits: int
    tag_bits: int


@dataclass(frozen=True)
class Address:
    address: int
    binary: str
    block: int
    offset: int
    index: int  # line (direct), set (set-assoc), always 0 for fully assoc
    tag: int


@dataclass(frozen=True)
class Line:
    valid: bool = False
    tag: int = 0
    block: int = -1
    loaded_at: int = 0
    last_used: int = 0


@dataclass(frozen=True)
class AccessResult:
    step: int
    addr: Address
    hit: bool
    set_index: int
    way: int
    line: int  # global line number = set * ways + way
    replaced: bool
    evicted_block: int  # -1 when nothing was evicted
    explanation: str


# ---------------------------------------------------------------- validation

def validate(cfg):
    """Return a list of human-readable problems. Empty list means valid."""
    errors = []
    sizes = (
        ("Main memory size", cfg.mem_size),
        ("Cache size", cfg.cache_size),
        ("Block size", cfg.block_size),
    )
    for label, value in sizes:
        if not is_pow2(value):
            errors.append(f"{label} must be a positive power of two (got {value}).")
    if cfg.mapping not in MAPPINGS:
        errors.append(f"Unknown mapping '{cfg.mapping}'.")
    if cfg.policy not in POLICIES:
        errors.append(f"Unknown replacement policy '{cfg.policy}'.")
    if errors:
        return errors

    if cfg.block_size > cfg.cache_size:
        errors.append("Block size cannot be larger than the cache size.")
    if cfg.cache_size > cfg.mem_size:
        errors.append("Cache size cannot be larger than main memory.")
    if cfg.cache_size % cfg.block_size:
        errors.append("Cache size must be divisible by block size.")
    if cfg.mapping == "set" and not errors:
        lines = cfg.cache_size // cfg.block_size
        if not is_pow2(cfg.ways):
            errors.append(f"Number of ways must be a power of two (got {cfg.ways}).")
        elif cfg.ways > lines:
            errors.append(f"{cfg.ways} ways is more than the {lines} cache lines available.")
        elif lines % cfg.ways:
            errors.append("Cache lines must divide evenly into sets.")
    return errors


def geometry(cfg):
    errors = validate(cfg)
    if errors:
        raise ValueError(" ".join(errors))
    lines = cfg.cache_size // cfg.block_size
    ways = {"direct": 1, "fully": lines, "set": cfg.ways}[cfg.mapping]
    sets = lines // ways
    addr_bits = log2(cfg.mem_size)
    offset_bits = log2(cfg.block_size)
    index_bits = log2(sets)
    return Geometry(
        mem_blocks=cfg.mem_size // cfg.block_size,
        lines=lines,
        sets=sets,
        ways=ways,
        addr_bits=addr_bits,
        offset_bits=offset_bits,
        index_bits=index_bits,
        tag_bits=addr_bits - index_bits - offset_bits,
    )


def decompose(cfg, address):
    geo = geometry(cfg)
    if not isinstance(address, int) or not 0 <= address < cfg.mem_size:
        raise ValueError(
            f"Address {address} is outside main memory (valid range 0 to {cfg.mem_size - 1})."
        )
    block = address >> geo.offset_bits
    return Address(
        address=address,
        binary=format(address, f"0{max(geo.addr_bits, 1)}b"),
        block=block,
        offset=address & (cfg.block_size - 1),
        index=block & (geo.sets - 1),  # block mod sets
        tag=block >> geo.index_bits,
    )


def split_binary(cfg, address):
    """Return (tag_bits, index_bits, offset_bits) as binary strings."""
    geo = geometry(cfg)
    bits = decompose(cfg, address).binary[-geo.addr_bits:] if geo.addr_bits else ""
    tag = bits[: geo.tag_bits]
    index = bits[geo.tag_bits: geo.tag_bits + geo.index_bits]
    offset = bits[geo.tag_bits + geo.index_bits:]
    return tag, index, offset


# ------------------------------------------------------------------- parsing

def parse_int(token):
    tok = token.strip().lower().replace("_", "")
    try:
        if tok.startswith("0x"):
            return int(tok[2:], 16)
        if tok.startswith("0b"):
            return int(tok[2:], 2)
        if tok.endswith("h") and len(tok) > 1:
            return int(tok[:-1], 16)
        return int(tok, 10)
    except ValueError:
        raise ValueError(f"'{token}' is not a valid address (use decimal, 0x hex or 0b binary).")


def parse_addresses(text):
    tokens = [t for t in re.split(r"[\s,;]+", text.strip()) if t]
    return [parse_int(t) for t in tokens]


# ----------------------------------------------------------------- simulator

class CacheSim:
    """Cache state machine. Lines are frozen; each change builds new tuples."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.geo = geometry(cfg)
        self.sets = tuple(tuple(Line() for _ in range(self.geo.ways)) for _ in range(self.geo.sets))
        self.clock = 0
        self.history = ()

    def _where(self, a):
        if self.cfg.mapping == "direct":
            return f"Block {a.block} maps to line {a.block} mod {self.geo.lines} = {a.index}"
        if self.cfg.mapping == "fully":
            return f"Block {a.block} may sit in any of the {self.geo.lines} lines (no index bits)"
        return f"Block {a.block} maps to set {a.block} mod {self.geo.sets} = {a.index}"

    def _set_lines(self, set_index, way, line):
        ways = self.sets[set_index]
        new_set = ways[:way] + (line,) + ways[way + 1:]
        self.sets = self.sets[:set_index] + (new_set,) + self.sets[set_index + 1:]

    def _choose_victim(self, ways):
        empty = next((w for w, line in enumerate(ways) if not line.valid), None)
        if empty is not None:
            return empty, False
        if self.cfg.policy == "FIFO":
            return min(range(len(ways)), key=lambda w: ways[w].loaded_at), True
        return min(range(len(ways)), key=lambda w: ways[w].last_used), True

    def access(self, address):
        a = decompose(self.cfg, address)
        self.clock += 1
        ways = self.sets[a.index]
        where = self._where(a)
        hit_way = next((w for w, ln in enumerate(ways) if ln.valid and ln.tag == a.tag), None)

        if hit_way is not None:
            self._set_lines(a.index, hit_way, replace(ways[hit_way], last_used=self.clock))
            line_no = a.index * self.geo.ways + hit_way
            text = f"{where}. Tag {a.tag} is already in line {line_no}, so this is a HIT."
            result = AccessResult(self.clock, a, True, a.index, hit_way, line_no, False, -1, text)
        else:
            way, replaced = self._choose_victim(ways)
            line_no = a.index * self.geo.ways + way
            victim = ways[way]
            new_line = Line(True, a.tag, a.block, self.clock, self.clock)
            self._set_lines(a.index, way, new_line)
            if replaced:
                reason = (
                    f"loaded first, at step {victim.loaded_at}"
                    if self.cfg.policy == "FIFO"
                    else f"least recently used, last at step {victim.last_used}"
                )
                text = (
                    f"{where}. Tag {a.tag} not found, so this is a MISS. "
                    f"No empty line is left, so {self.cfg.policy} evicts block {victim.block} "
                    f"({reason}) from line {line_no} and loads block {a.block} from RAM."
                )
            else:
                text = (
                    f"{where}. Tag {a.tag} not found, so this is a MISS. "
                    f"Block {a.block} is fetched from RAM into empty line {line_no}."
                )
            evicted = victim.block if replaced else -1
            result = AccessResult(self.clock, a, False, a.index, way, line_no, replaced, evicted, text)

        self.history = self.history + (result,)
        return result

    def lines_view(self):
        rows = []
        for s, ways in enumerate(self.sets):
            for w, ln in enumerate(ways):
                start = ln.block * self.cfg.block_size
                rows.append({
                    "line": s * self.geo.ways + w,
                    "set": s,
                    "way": w,
                    "valid": int(ln.valid),
                    "tag": ln.tag if ln.valid else None,
                    "block": ln.block if ln.valid else None,
                    "data": f"M[{start}..{start + self.cfg.block_size - 1}]" if ln.valid else "-",
                    "loaded at": ln.loaded_at if ln.valid else None,
                    "last used": ln.last_used if ln.valid else None,
                })
        return rows


def simulate(cfg, addresses):
    sim = CacheSim(cfg)
    for address in addresses:
        sim.access(address)
    return sim


# --------------------------------------------------------------- statistics

def summary(results):
    total = len(results)
    hits = sum(1 for r in results if r.hit)
    misses = total - hits
    return {
        "accesses": total,
        "hits": hits,
        "misses": misses,
        "replacements": sum(1 for r in results if r.replaced),
        "hit_ratio": hits / total if total else 0.0,
        "miss_ratio": misses / total if total else 0.0,
    }


def amat(hit_time, miss_ratio, miss_penalty):
    """AMAT = Hit time + Miss rate x Miss penalty."""
    return hit_time + miss_ratio * miss_penalty


def classify_misses(cfg, addresses):
    """3C model: compulsory, capacity and conflict misses."""
    sim = simulate(cfg, addresses)
    misses = summary(sim.history)["misses"]
    compulsory = len({a >> log2(cfg.block_size) for a in addresses})
    full_cfg = replace(cfg, mapping="fully", policy="LRU")
    full_misses = summary(simulate(full_cfg, addresses).history)["misses"]
    capacity = max(full_misses - compulsory, 0)
    conflict = max(misses - compulsory - capacity, 0)
    return {"compulsory": compulsory, "capacity": capacity, "conflict": conflict}


def compare_mappings(cfg, addresses, ways=2):
    """Run one sequence through all three mappings with the same sizes and policy."""
    rows = []
    for mapping in MAPPINGS:
        lines = cfg.cache_size // cfg.block_size
        mcfg = replace(cfg, mapping=mapping, ways=min(ways, lines) if mapping == "set" else cfg.ways)
        stats = summary(simulate(mcfg, addresses).history)
        label = MAPPING_LABELS[mapping] + (f" ({mcfg.ways}-way)" if mapping == "set" else "")
        rows.append({"mapping": label, **stats})
    return rows


# ---------------------------------------------------------------- optimiser

def optimise(addresses, mem_size, cache_sizes, block_sizes, mappings, ways_options,
             policy="LRU", hit_time=1, miss_penalty=100):
    """Simulate every valid configuration and rank them. Returns (rows, skipped)."""
    candidates = []
    for cs in cache_sizes:
        for bs in block_sizes:
            for mapping in mappings:
                for ways in (ways_options if mapping == "set" else [1]):
                    candidates.append(Config(mem_size, cs, bs, mapping, ways, policy))

    rows, skipped = [], []
    for cfg in candidates:
        errors = validate(cfg)
        if errors:
            skipped.append((cfg, errors[0]))
            continue
        stats = summary(simulate(cfg, addresses).history)
        geo = geometry(cfg)
        label = MAPPING_LABELS[cfg.mapping] + (f" {cfg.ways}-way" if cfg.mapping == "set" else "")
        rows.append({
            "cache size": cfg.cache_size,
            "block size": cfg.block_size,
            "mapping": label,
            "ways": geo.ways,
            **stats,
            "AMAT": amat(hit_time, stats["miss_ratio"], miss_penalty),
            "_cfg": cfg,
        })
    # Fewest misses first (same workload, so same as highest hit ratio and
    # lowest AMAT). Ties go to the smaller, simpler cache.
    rows.sort(key=lambda r: (r["misses"], r["cache size"], r["ways"], r["block size"]))
    return [{"rank": i + 1, **r} for i, r in enumerate(rows)], skipped


def explain_best(rows, addresses):
    if not rows:
        return "No valid configuration to rank."
    best, worst = rows[0], rows[-1]
    cfg = best["_cfg"]
    c3 = classify_misses(cfg, addresses)
    parts = [
        f"{best['mapping']}, {best['cache size']} B cache, {best['block size']} B blocks had "
        f"{best['misses']} misses out of {best['accesses']} accesses "
        f"(hit ratio {best['hit_ratio']:.2%}).",
        f"Its misses split into {c3['compulsory']} compulsory (first touch of a block), "
        f"{c3['capacity']} capacity and {c3['conflict']} conflict.",
    ]
    if len(rows) > 1:
        wc = classify_misses(worst["_cfg"], addresses)
        parts.append(
            f"The worst option ({worst['mapping']}, {worst['cache size']} B, {worst['block size']} B blocks) "
            f"had {worst['misses']} misses: {wc['compulsory']} compulsory, {wc['capacity']} capacity, "
            f"{wc['conflict']} conflict."
        )
        if wc["compulsory"] > c3["compulsory"]:
            parts.append("Larger blocks cut compulsory misses by exploiting spatial locality.")
        if wc["conflict"] > c3["conflict"]:
            parts.append("Higher associativity removed conflict misses (blocks fighting for one line).")
        if wc["capacity"] > c3["capacity"]:
            parts.append("A bigger cache held more of the working set, cutting capacity misses.")
    return " ".join(parts)
