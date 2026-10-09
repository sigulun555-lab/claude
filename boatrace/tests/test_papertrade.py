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
