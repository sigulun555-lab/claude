from boatrace.papertrade import FIELDS, report, save_picks


def _row(date, combo, result, payout):
    return {"date": date, "race_id": f"{date}_24_01", "rule": "単勝EV1.2", "bet_type": "単勝",
            "combo": combo, "prob": 0.2, "odds": 6.0, "ev": 1.2, "result": result, "payout": payout}


def test_save_picks_replaces_same_day(tmp_path):
    path = tmp_path / "picks.csv"
    save_picks(path, "20261006", [_row("20261006", "2", 0, 0)])
    save_picks(path, "20261007", [_row("20261007", "3", 1, 600)])
    save_picks(path, "20261006", [_row("20261006", "4", 1, 600)])  # 再実行で入れ替わる
    lines = path.read_text().splitlines()
    assert lines[0].split(",") == FIELDS
    assert len(lines) == 3 and ",4," in lines[1]
    text = report(path)
    assert "2点" in text and "回収率 600.0%" in text


def test_choose_venues_is_deterministic_and_not_biased_to_low_codes():
    from boatrace.cli import choose_venues
    pool = set(range(1, 25))
    assert choose_venues("20261014", pool, 2) == choose_venues("20261014", pool, 2)
    assert len(choose_venues("20261014", pool, 2)) == 2
    assert choose_venues("20261014", {5}, 2) == {5}
    picked = set()
    for day in range(1, 31):
        picked |= choose_venues(f"202610{day:02d}", pool, 2)
    assert len(picked) >= 15  # 1か月でほとんどの場が選ばれる (先頭2場に固定されない)
    assert max(picked) > 12
