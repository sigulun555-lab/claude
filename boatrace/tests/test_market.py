import pytest

from boatrace.market import blend, market_probs


def test_market_probs_normalizes_and_rejects_incomplete():
    q = market_probs({1: 2.0, 2: 4.0, 3: 8.0, 4: 16.0, 5: 32.0, 6: 64.0})
    assert sum(q.values()) == pytest.approx(1.0)
    assert q[1] > q[2] > q[6]
    assert market_probs({1: 2.0, 2: 4.0}) is None                                   # 6艇そろわない
    assert market_probs({1: 2.0, 2: 4.0, 3: 8.0, 4: 16.0, 5: 32.0, 6: 0.0}) is None  # 欠場 (0倍)
    assert market_probs({str(b): 1.0 + b for b in range(1, 7)}) is not None        # 文字列キーでもよい


def test_blend_pulls_toward_market_and_sums_to_one():
    p = {1: 0.50, 2: 0.20, 3: 0.10, 4: 0.10, 5: 0.06, 6: 0.04}
    odds = {1: 4.0, 2: 3.0, 3: 12.0, 4: 12.0, 5: 40.0, 6: 60.0}   # 市場は2号艇を高く見ている
    mix = blend(p, odds)
    assert sum(mix.values()) == pytest.approx(1.0)
    assert mix[2] > p[2]            # 市場に引っぱられて2号艇は上がる
    assert mix[1] < p[1]
    assert blend(p, {1: 4.0}) is None


def test_blend_with_one_missing_odds_uses_model_for_that_boat():
    p = {1: 0.3, 2: 0.25, 3: 0.2, 4: 0.12, 5: 0.1, 6: 0.03}
    odds = {1: 1.2, 2: 6.1, 3: 0.0, 4: 12.3, 5: 4.1, 6: 24.7}
    mix = blend(p, odds)
    assert mix is not None and abs(sum(mix.values()) - 1) < 1e-9
    assert mix[1] > p[1]  # 市場が1号艇を強く見ているので引き上がる
    assert blend(p, {**odds, 6: 0.0}) is None  # 2艇欠けたら作らない
