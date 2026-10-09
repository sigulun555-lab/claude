"""お金を賭けない記録テスト (ペーパートレード)。

ルールは 2026-10-09 時点で固定し、モデルが見ていない新しいレースで
「そのルールで買っていたらどうなったか」を毎日記録する。
"""
import csv
from pathlib import Path

import pandas as pd

from .model import harville, predict_win_prob

# 固定ルール (9月の検証で決めたもの。あとから変えない)
RULES = {
    "単勝EV1.2": "単勝で 期待値>=1.2、6号艇と50倍超は買わない",
    "2連単候補": "1着が上の単勝ルールで選ばれた艇で、2連単の 期待値>=1.2 かつ 50倍以下 (仮説の確認用)",
    "複勝EV1.1": "複勝 (2着以内) で、オッズの下限で計算した期待値>=1.1、6号艇は買わない (2026-10-09 追加)",
}
EV_MIN, ODDS_MAX = 1.2, 50.0
FUKUSHO_EV_MIN = 1.1  # 複勝は払戻が幅のどこになるか分からないので、下限オッズで見る
FIELDS = ["date", "race_id", "rule", "bet_type", "combo", "prob", "odds", "ev", "result", "payout"]


def make_picks(con, model, feats: pd.DataFrame, date: str) -> list:
    """date (YYYYMMDD) のレースのうち、オッズがあるものについて固定ルールで買い目を作る。"""
    odds = pd.read_sql_query(
        "SELECT race_id, bet_type, combo, odds FROM odds WHERE race_id LIKE ? AND odds IS NOT NULL",
        con, params=[f"{date}_%"])
    omap = {(r, b, c): o for r, b, c, o in odds.itertuples(index=False)}
    pay = {(r, b, c): a for r, b, c, a in con.execute(
        "SELECT race_id, bet_type, combo, amount FROM payouts WHERE race_id LIKE ?", [f"{date}_%"])}
    settled = {r for r, _, _ in pay}

    day = feats[(feats["date"] == date) & feats["race_id"].isin(set(odds["race_id"]))].copy()
    day = day[day.groupby("race_id")["boat"].transform("size") == 6]
    if day.empty:
        return []
    day["p_win"] = predict_win_prob(model, day)

    rows = []
    for race_id, g in day.groupby("race_id"):
        probs = harville(dict(zip(g["boat"], g["p_win"])))
        tansho_boats = set()

        def add(rule, bet_type, combo, p, o):
            result = None if race_id not in settled else (pay.get((race_id, bet_type, combo), 0) > 0)
            rows.append({
                "date": date, "race_id": race_id, "rule": rule, "bet_type": bet_type, "combo": combo,
                "prob": round(p, 4), "odds": o, "ev": round(p * o, 3),
                "result": "" if result is None else int(result),
                "payout": "" if result is None else pay.get((race_id, bet_type, combo), 0),
            })

        for combo, p in probs["単勝"].items():
            o = omap.get((race_id, "単勝", combo))
            if o and p * o >= EV_MIN and combo != "6" and o <= ODDS_MAX:
                tansho_boats.add(combo)
                add("単勝EV1.2", "単勝", combo, p, o)
        for combo, p in probs["複勝"].items():
            o = omap.get((race_id, "複勝", combo))
            if o and p * o >= FUKUSHO_EV_MIN and combo != "6":
                add("複勝EV1.1", "複勝", combo, p, o)
        for combo, p in probs["2連単"].items():
            o = omap.get((race_id, "2連単", combo))
            if o and combo.split("-")[0] in tansho_boats and p * o >= EV_MIN and o <= ODDS_MAX:
                add("2連単候補", "2連単", combo, p, o)
    return rows


def save_picks(path: Path, date: str, rows: list):
    """その日の行を入れ替えて保存する (何度実行しても同じ結果になる)。"""
    old = []
    if path.exists():
        with path.open() as f:
            old = [r for r in csv.DictReader(f) if r["date"] != date]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sorted(old + rows, key=lambda r: (r["date"], r["race_id"], r["rule"], r["combo"])))


def report(path: Path) -> str:
    if not path.exists():
        return "まだ記録がありません"
    df = pd.read_csv(path, dtype={"combo": str})
    df = df[df["result"].notna()]
    lines = [f"記録期間: {df['date'].min()} 〜 {df['date'].max()} ({df['date'].nunique()}日)"]
    for rule, g in df.groupby("rule"):
        n = len(g)
        lines.append(
            f"{rule:<10} {n:>5}点  的中 {int(g['result'].sum()):>4}  的中率 {g['result'].mean():6.1%}  "
            f"回収率 {g['payout'].sum() / (100 * n):6.1%}  収支 {int(g['payout'].sum() - 100 * n):+,}円")
    return "\n".join(lines)
