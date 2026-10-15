from datetime import datetime, timedelta, timezone
from pathlib import Path

from boatrace.live import fetch_live, select_races

FIX = Path(__file__).parent / "fixtures"
JST = timezone(timedelta(hours=9))
SHEET = {"date": "2026-10-15", "venues": [
    {"code": 24, "name": "大村", "races": [
        {"no": 1, "deadline": "10:30", "picks": []}, {"no": 2, "deadline": "11:05", "picks": []},
        {"no": 3, "deadline": "11:40", "picks": []}, {"no": 4, "deadline": "13:00", "picks": []}]},
    {"code": 2, "name": "戸田", "races": [{"no": 1, "deadline": "11:20", "picks": []}]}]}


def test_select_races_window_and_order():
    got = select_races(SHEET, 10 * 60 + 50, window=75)   # 10:50 の75分後は 12:05
    assert [(c, n) for _, c, n in got] == [(24, 2), (2, 1), (24, 3)]   # 締切が早い順、過ぎた1Rと遠い4Rは除く


def test_fetch_live_merges_and_skips_invalid():
    html = (FIX / "oddstf_20260929_24_01.html").read_text()
    calls = []

    def fake(page, date, code, no, sleep):
        calls.append((page, date, code, no))
        if (code, no) == (2, 1):
            raise OSError("接続できません")
        return html

    now = datetime(2026, 10, 15, 10, 50, tzinfo=JST)
    res = fetch_live(SHEET, now, fetch=fake, sleep=0)
    assert res["asof"] == "10:50" and res["fetched"] == 3
    assert set(res["races"]) == {"24|2", "24|3"} and len(res["errors"]) == 1   # 失敗した戸田1Rは入らない
    assert res["races"]["24|2"]["odds"]["1"] == 1.5 and res["races"]["24|2"]["at"] == "10:50"
    assert calls[0] == ("oddstf", "20261015", 24, 2)

    later = datetime(2026, 10, 15, 11, 50, tzinfo=JST)   # 次の回: 前回分を引き継ぎ、新しく取ったレースだけ上書き
    res2 = fetch_live(SHEET, later, previous=res, fetch=lambda *a: html, sleep=0)
    assert res2["races"]["24|2"]["at"] == "10:50"          # 11:05 は過ぎているので取り直さない
    assert res2["races"]["24|4"]["at"] == "11:50"
