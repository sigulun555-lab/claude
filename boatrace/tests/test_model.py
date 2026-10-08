import pytest

from boatrace.model import expected_value, harville, kelly_fraction


def test_harville_sums_to_one():
    p = {1: 0.5, 2: 0.2, 3: 0.1, 4: 0.1, 5: 0.06, 6: 0.04}
    probs = harville(p, 1.0, 1.0)
    for bet_type in ["単勝", "2連単", "2連複", "3連単", "3連複"]:
        assert sum(probs[bet_type].values()) == pytest.approx(1.0)
    assert sum(probs["複勝"].values()) == pytest.approx(2.0)   # 2艇が該当
    assert sum(probs["拡連複"].values()) == pytest.approx(3.0)  # 3組が該当
    assert probs["3連単"]["1-2-3"] == pytest.approx(0.5 * 0.2 / 0.5 * 0.1 / 0.3)
    assert probs["2連複"]["1-2"] == pytest.approx(probs["2連単"]["1-2"] + probs["2連単"]["2-1"])


def test_ev_and_kelly():
    assert expected_value(0.25, 5.0) == pytest.approx(1.25)
    assert kelly_fraction(0.25, 5.0, scale=1) == pytest.approx((0.25 * 4 - 0.75) / 4)
    assert kelly_fraction(0.1, 5.0) == 0.0  # 期待値マイナスなら賭けない


def test_harville_adjusted_sums_to_one():
    p = {1: 0.5, 2: 0.2, 3: 0.1, 4: 0.1, 5: 0.06, 6: 0.04}
    plain, adj = harville(p, 1.0, 1.0), harville(p)
    for bet_type in ["単勝", "2連単", "3連単", "3連複"]:
        assert sum(adj[bet_type].values()) == pytest.approx(1.0)
    assert adj["単勝"] == plain["単勝"]  # 1着確率は変えない
    assert adj["3連単"]["1-2-3"] < plain["3連単"]["1-2-3"]  # 本命寄りを控えめに
    assert adj["3連単"]["6-5-4"] > plain["3連単"]["6-5-4"]  # 大穴を高めに
