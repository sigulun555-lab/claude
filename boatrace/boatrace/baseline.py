"""Phase 2: 単純な予想(ベースライン)の的中率・回収率を測る。

この数字を超えられるかどうかが、今後作るモデルの合格ラインになる。
"""


def course_win_rates(con, venue=None):
    """進入コース別の1着率。venue を指定するとその場だけ。"""
    sql = """
        SELECT res.course, COUNT(*) AS n, SUM(res.rank = 1) AS wins
        FROM results res JOIN races r USING (race_id)
        WHERE res.course BETWEEN 1 AND 6 {where}
        GROUP BY res.course ORDER BY res.course
    """.format(where="AND r.venue = ?" if venue else "")
    rows = con.execute(sql, [venue] if venue else []).fetchall()
    return [(c, n, wins / n if n else 0.0) for c, n, wins in rows]


def _evaluate(con, picks, bet_type):
    """picks: {race_id: combo}。1点100円買ったときの (レース数, 的中率, 回収率)。"""
    if not picks:
        return 0, 0.0, 0.0
    pay = {}
    for race_id, combo, amount in con.execute(
            "SELECT race_id, combo, amount FROM payouts WHERE bet_type = ?", [bet_type]):
        pay[(race_id, combo)] = amount
    # 払戻データのあるレース(=成立したレース)だけを対象にする
    settled = {rid for rid, _ in pay}
    picks = {rid: c for rid, c in picks.items() if rid in settled}
    if not picks:
        return 0, 0.0, 0.0
    hits = [pay.get((rid, c), 0) for rid, c in picks.items()]
    n = len(picks)
    return n, sum(h > 0 for h in hits) / n, sum(hits) / (100 * n)


def strategies(con):
    race_ids = [r for (r,) in con.execute("SELECT DISTINCT race_id FROM entries")]
    top_win = dict(con.execute("""
        SELECT race_id, boat FROM (
            SELECT race_id, boat,
                   ROW_NUMBER() OVER (PARTITION BY race_id ORDER BY nat_win DESC, boat) AS rk
            FROM entries)
        WHERE rk = 1
    """).fetchall())
    return {
        "1号艇の単勝": _evaluate(con, {r: "1" for r in race_ids}, "単勝"),
        "全国勝率1位の単勝": _evaluate(con, {r: str(b) for r, b in top_win.items()}, "単勝"),
        "3連単 1-2-3 固定": _evaluate(con, {r: "1-2-3" for r in race_ids}, "3連単"),
    }
