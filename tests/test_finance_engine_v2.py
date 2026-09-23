"""Fixture-gated tests for PURIQ Finance Engine v2.

Offline by design: the fixture lane is deterministic, so CI never depends
on stooq reachability. Anything that would touch the network is out of scope
here — the stooq adapter is exercised by deployment smoke checks, not unit tests.
"""

import os
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "services", "finance"))

from engine import (
    EngineBlocked,
    beta,
    bollinger_z,
    canonical_digest,
    max_drawdown,
    portfolio_report,
    rsi,
    sharpe,
    signal_suite,
    sma,
    volatility,
)
from feed import fixture_series, get_closes
from receipts import ReceiptChain


# ---------- known-math anchors ----------

def test_rsi_strictly_rising_is_100():
    assert rsi([float(i) for i in range(1, 60)], 14) == 100.0


def test_beta_of_series_against_itself_is_one():
    s = fixture_series("AAA")
    assert abs(beta(s, s) - 1.0) < 1e-12


def test_max_drawdown_monotone_rise_is_zero():
    assert max_drawdown([1.0, 2.0, 3.0, 4.0, 5.0]) == 0.0


def test_sma_window_math():
    assert sma([1.0, 2.0, 3.0, 4.0, 5.0], 5) == 3.0


def test_bollinger_flat_series_z_zero():
    assert bollinger_z([7.0] * 25, 20) == 0.0


# ---------- fixture lane ----------

def test_fixture_lane_is_deterministic():
    assert fixture_series("AAPL") == fixture_series("AAPL")
    assert fixture_series("AAPL") != fixture_series("MSFT")


def test_fixture_labeled_not_market_data():
    closes, lane = get_closes("AAPL", "fixture")
    assert lane == "fixture"
    assert len(closes) == 260


def test_unknown_lane_fails_closed():
    with pytest.raises(EngineBlocked):
        get_closes("AAPL", "bogus")


# ---------- five-state honesty ----------

def test_signal_suite_short_series_blocks():
    with pytest.raises(EngineBlocked):
        signal_suite([1.0, 2.0, 3.0], "X", "fixture")


def test_signal_suite_non_finite_blocks():
    with pytest.raises(EngineBlocked):
        signal_suite([float("nan")] * 40, "X", "fixture")


def test_signal_suite_measured_contract():
    closes, lane = get_closes("AAPL", "fixture")
    out = signal_suite(closes, "AAPL", lane)
    assert out["state"] == "MEASURED"
    assert out["verdict"] in ("BULLISH", "BEARISH", "NEUTRAL")
    assert out["advisory_only"] is True
    assert out["paper_only"] is True
    assert out["not_financial_advice"] is True
    assert out["input_digest"] == canonical_digest(closes)


def test_portfolio_empty_holdings_blocks():
    with pytest.raises(EngineBlocked):
        portfolio_report({})


def test_portfolio_report_digest_present():
    closes = fixture_series("AAA")
    rep = portfolio_report({"AAA": closes, "BBB": [p * 0.8 for p in closes]})
    assert rep["state"] == "MEASURED"
    assert len(rep["report_digest"]) == 64
    assert rep["constituents"] == ["AAA", "BBB"]


# ---------- receipt chain ----------

def test_clean_chain_consistent():
    c = ReceiptChain()
    c.append("signal", {"symbol": "X"})
    c.append("portfolio", {"assets": 1})
    v = ReceiptChain.verify(c.entries())
    assert v["state"] == "CONSISTENT"
    assert v["length"] == 2


def test_tampered_payload_divergent():
    c = ReceiptChain()
    c.append("signal", {"verdict": "NEUTRAL"})
    bad = [dict(e) for e in c.entries()]
    bad[0]["payload"] = {"verdict": "BULLISH"}
    v = ReceiptChain.verify(bad)
    assert v["state"] == "DIVERGENT"
    assert v["reason"] == "payload_tamper"


def test_reordered_chain_divergent():
    c = ReceiptChain()
    c.append("a", {})
    c.append("b", {})
    reordered = [c.entries()[1], c.entries()[0]]
    v = ReceiptChain.verify(reordered)
    assert v["state"] == "DIVERGENT"
    assert v["reason"] == "link_mismatch"


def test_empty_chain_consistent():
    assert ReceiptChain.verify([]) == {"state": "CONSISTENT", "length": 0}


# ---------- risk math sanity ----------

def test_volatility_and_sharpe_finite_on_fixture():
    s = fixture_series("QQQ")
    assert volatility(s) > 0.0
    assert abs(sharpe(s)) < 100.0
