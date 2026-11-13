# CacheMind – Smart Cache Memory Simulator (Python)

Streamlit app for simulating CPU cache memory: direct, fully associative and
set-associative mapping with FIFO/LRU replacement.

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/streamlit run app.py
```

## Test

```bash
.venv/bin/python -m pytest -q
```

## Layout

| File | Role |
|---|---|
| `engine.py` | Pure simulation engine (geometry, address split, FIFO/LRU, stats, AMAT, optimiser, 3C misses). No UI imports. |
| `questions.py` | Challenge question generator; answers come from the engine. |
| `store.py` | JSON persistence (`cachemind_data.json`), the Python stand-in for LocalStorage. |
| `ui_common.py` | Shared widgets, theme CSS, config form. |
| `views_core.py` | Dashboard, Cache Simulator, Mapping Laboratory, Address Calculator. |
| `views_analysis.py` | Performance Analyzer, Cache Optimiser. |
| `views_learn.py` | Learning Centre, Challenge Mode, Settings. |
| `test_engine.py` | Engine unit tests (mapping maths, hit/miss, FIFO/LRU, optimiser). |
| `test_app.py` | Headless Streamlit tests (every page renders, controls work). |

## Assumptions

Byte-addressable memory. Memory, cache, block sizes and ways must be powers of
two; invalid configurations are rejected with an error, never silently fixed.

## Deploy (Render)

`render.yaml` defines a free Python web service. It sets `CACHEMIND_STORAGE=session`, so on the
shared deployment each visitor's history and scores live only in their browser session; nothing
is written to the server's disk. Locally the default is `file` (saved to `cachemind_data.json`).
