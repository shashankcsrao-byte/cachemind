"""Headless smoke tests: every page renders and core buttons work."""
import pytest
from streamlit.testing.v1 import AppTest

import store

PAGES = ["Overview", "Cache Simulator", "Mapping Laboratory", "Address Calculator",
         "Performance Analyzer", "Cache Optimiser", "Learning Centre", "Challenge Mode", "Settings"]


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_FILE", tmp_path / "data.json")
    monkeypatch.setattr(store.load, "__defaults__", (tmp_path / "data.json",))
    monkeypatch.setattr(store.save, "__defaults__", (tmp_path / "data.json",))


def open_page(page):
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["nav"] = page
    return at.run()


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_error(page):
    at = open_page(page)
    assert not at.exception, at.exception
    assert at.title[0].value


def test_simulator_run_all_records_history():
    at = open_page("Cache Simulator")
    run_all = next(b for b in at.button if b.label == "Run all")
    run_all.click().run()
    assert not at.exception
    assert at.session_state["sim_pos"] == 11
    assert len(at.session_state["data"]["history"]) == 1
    html = " ".join(m.value for m in at.markdown)
    assert "<span>Accesses</span><b>11</b>" in html and "<span>Hits</span><b>6</b>" in html


def test_simulator_step_shows_explanation():
    at = open_page("Cache Simulator")
    next(b for b in at.button if b.label == "Step").click().run()
    html = " ".join(m.value for m in at.markdown)
    assert "Tag 0 not found, so this is a MISS" in html and "Miss, loaded" in html


def test_challenge_submit():
    at = open_page("Challenge Mode")
    q = at.session_state["question"]
    at.radio(key="choice").set_value(q.options[q.answer]).run()
    next(b for b in at.button if b.label == "Submit").click().run()
    assert not at.exception
    assert at.session_state["round"] == {"correct": 1, "total": 1}


def test_sidebar_navigation_switches_page():
    at = open_page("Overview")
    at.sidebar.radio[0].set_value("Address Calculator").run()
    assert at.title[0].value == "Address Calculator"
    at.sidebar.radio[0].set_value("Settings").run()
    assert at.title[0].value == "Settings & Saved Data"


def test_sequence_edit_survives_rerun_and_page_change():
    at = open_page("Cache Simulator")
    at.text_area[0].set_value("0 32 0 32").run()
    assert at.session_state["seq_text"] == "0 32 0 32"
    at.sidebar.radio[0].set_value("Mapping Laboratory").run()
    assert at.text_area[0].value == "0 32 0 32"
    assert not at.exception


def test_timing_inputs_update_amat():
    at = open_page("Performance Analyzer")
    at.number_input(key="_w_miss_penalty").set_value(10.0).run()
    assert at.session_state["miss_penalty"] == 10.0
    html = " ".join(m.value for m in at.markdown)
    assert f"<span>AMAT</span><b>{1 + (5 / 11) * 10:.2f}" in html


def test_invalid_config_shows_error():
    at = open_page("Address Calculator")
    at.number_input(key="calc_cache").set_value(48).run()
    assert any("power of two" in e.value for e in at.error)


def test_session_mode_never_writes_file(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "STORAGE_MODE", "session")
    at = open_page("Cache Simulator")
    next(b for b in at.button if b.label == "Run all").click().run()
    assert len(at.session_state["data"]["history"]) == 1
    assert not (tmp_path / "data.json").exists()
