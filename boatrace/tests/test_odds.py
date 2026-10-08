from pathlib import Path

from boatrace.odds import parse_tansho, parse_trifecta

FIX = Path(__file__).parent / "fixtures"


def test_parse_tansho():
    odds = parse_tansho((FIX / "oddstf_20260929_24_01.html").read_text())
    assert odds == {"1": 1.5, "2": 2.1, "3": 17.8, "4": 10.7, "5": 20.9, "6": 35.6}


def test_parse_trifecta():
    odds = parse_trifecta((FIX / "odds3t_20260929_24_01.html").read_text())
    assert len(odds) == 120
    assert odds["1-2-5"] == 9.9  # 競走成績の払戻 990円 と一致
    assert odds["1-2-3"] == 10.4 and odds["6-1-2"] == 673.7
    # 控除率25%なので 1/オッズ の合計はおよそ 1/0.75
    assert 1.25 < sum(1 / v for v in odds.values()) < 1.45
