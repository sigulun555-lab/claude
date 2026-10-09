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


def test_parse_exacta():
    from boatrace.odds import parse_exacta
    odds = parse_exacta((FIX / "odds2tf_20260929_24_01.html").read_text())
    assert len(odds["2連単"]) == 30 and len(odds["2連複"]) == 15
    assert odds["2連単"]["1-2"] == 2.8  # 競走成績の払戻 280円 と一致
    assert odds["2連単"]["2-1"] == 6.8 and odds["2連単"]["6-1"] == 195.8
    assert odds["2連複"]["1-2"] == 1.9  # 払戻 190円
    assert odds["2連複"]["2-3"] == 14.6


def test_parse_beforeinfo():
    from boatrace.odds import parse_beforeinfo
    info = parse_beforeinfo((FIX / "beforeinfo_20260929_24_01.html").read_text())
    # 競走成績ファイルの展示タイムと一致
    assert info["exhibition"] == {1: 6.93, 2: 6.94, 3: 6.98, 4: 6.97, 5: 6.9, 6: 6.95}
    assert (info["wind_speed"], info["wave"], info["weather"]) == (1.0, 1.0, "晴")


def test_parse_request():
    from boatrace.check import parse_request
    assert parse_request("2026-10-09 大村 8R") == ("20261009", 24, 8)
    assert parse_request("2026-10-09 3 12") == ("20261009", 3, 12)
