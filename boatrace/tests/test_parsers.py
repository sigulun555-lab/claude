from pathlib import Path

import pytest

from boatrace.baseline import course_win_rates, strategies
from boatrace.db import connect, save_program, save_result
from boatrace.parse_program import parse_program
from boatrace.parse_result import parse_result

FIX = Path(__file__).parent / "fixtures"


def read(name):
    return (FIX / name).read_bytes().decode("cp932")


def test_parse_program():
    races, entries = parse_program(read("B261007.TXT"), "20261007")
    assert [r["race_id"] for r in races] == ["20261007_24_01", "20261007_24_02"]
    assert races[0]["distance"] == 1800
    assert races[0]["deadline"] == "15:17"
    assert len(entries) == 12
    e = entries[0]
    assert (e["boat"], e["reg_no"], e["name"], e["age"], e["branch"], e["weight"], e["grade"]) == \
        (1, 4320, "大村太郎", 39, "長崎", 52, "A1")
    assert (e["nat_win"], e["loc_2r"], e["motor_no"], e["motor_2r"], e["boat_no"]) == \
        (7.12, 55.00, 23, 38.46, 45)
    assert entries[5]["loc_win"] == 0.0


def test_parse_result():
    races, results, payouts = parse_result(read("K261007.TXT"), "20261007")
    assert len(races) == 2
    assert races[0]["weather"] == "晴"
    assert races[0]["wind_dir"] == "北東"
    assert (races[0]["wind_speed"], races[0]["wave"], races[0]["technique"]) == (3, 2, "逃げ")
    assert races[1]["technique"] == "まくり"
    assert len(results) == 12
    first = results[0]
    assert (first["rank"], first["boat"], first["course"], first["st"], first["exhibition"]) == \
        (1, 1, 1, 0.12, 6.75)
    flying = results[-1]
    assert flying["rank"] is None and flying["rank_raw"] == "F"
    assert flying["st"] == pytest.approx(-0.01) and flying["st_flag"] == "F"

    r1 = {(p["bet_type"], p["combo"]): p for p in payouts if p["race_id"].endswith("_01")}
    assert r1[("単勝", "1")]["amount"] == 150
    assert r1[("複勝", "3")]["amount"] == 180
    assert r1[("3連単", "1-3-2")]["popularity"] == 5
    assert {c for t, c in r1 if t == "拡連複"} == {"1-3", "1-2", "2-3"}
    assert len(r1) == 10


def test_db_and_baseline(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    save_program(con, *parse_program(read("B261007.TXT"), "20261007"))
    save_result(con, *parse_result(read("K261007.TXT"), "20261007"))
    # 番組表と成績が同じ races 行にまとまる
    row = con.execute("SELECT deadline, technique FROM races WHERE race_id='20261007_24_02'").fetchone()
    assert row == ("15:45", "まくり")

    rates = {c: rate for c, _, rate in course_win_rates(con)}
    assert rates[1] == 0.5 and rates[3] == 0.5

    s = strategies(con)
    n, hit, roi = s["1号艇の単勝"]
    assert (n, hit) == (2, 0.5) and roi == pytest.approx(150 / 200)
    n, hit, roi = s["全国勝率1位の単勝"]  # 1R: 1号艇(的中150), 2R: 2号艇(外れ)
    assert (n, hit) == (2, 0.5) and roi == pytest.approx(150 / 200)
