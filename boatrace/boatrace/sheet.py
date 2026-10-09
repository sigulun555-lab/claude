"""朝の予想表: その日の全レースで「この艇がこのオッズ以上なら単勝を買い」を出す。

ルールはペーパートレードと同じ (期待値1.2以上、6号艇と50倍超は買わない)。
必要オッズ = 1.2 / 勝つ確率。締切前のオッズがこれ以上なら買い、届かなければ見送り。
"""
import pandas as pd

from . import VENUES
from .model import predict_win_prob
from .papertrade import EV_MIN, ODDS_MAX


def sheet_data(con, model, feats: pd.DataFrame, date: str) -> dict:
    """予想表のデータ。{date, venues: [{code, name, races: [{no, deadline, picks: [...]}]}]}"""
    day = feats[feats["date"] == date].copy()
    day = day[day.groupby("race_id")["boat"].transform("size") == 6]
    out = {"date": f"{date[:4]}-{date[4:6]}-{date[6:]}", "venues": []}
    if day.empty:
        return out
    day["p"] = predict_win_prob(model, day)
    deadline = dict(con.execute("SELECT race_id, deadline FROM races WHERE date = ?", [date]))
    for venue, vg in day.groupby("venue", observed=True):
        races = []
        for race_id, g in vg.groupby("race_id"):
            picks = []
            for _, r in g.sort_values("p", ascending=False).iterrows():
                need = EV_MIN / r["p"]
                if r["boat"] == 6 or need > ODDS_MAX:
                    continue
                picks.append({"boat": int(r["boat"]), "name": r["name"], "grade": r["grade"],
                              "p": round(float(r["p"]), 3), "need": round(need, 1)})
                if len(picks) >= 3:
                    break
            races.append({"no": int(g["race_no"].iloc[0]), "deadline": deadline.get(race_id) or "",
                          "picks": picks})
        out["venues"].append({"code": int(venue), "name": VENUES.get(int(venue), str(venue)),
                              "races": sorted(races, key=lambda r: r["no"])})
    return out


def to_markdown(data: dict) -> str:
    d = data["date"].replace("-", "/")
    if not data["venues"]:
        return f"# {d} の予想表\n\n対象レースがありません。\n"
    lines = [
        f"# {d} の予想表 (単勝)",
        "",
        "締切前のオッズが **必要オッズ以上** なら買い、届かなければ見送り。",
        "展示タイムを使わない朝の予想です。気になるレースは「○○ ○R 直前」で直前チェックできます。",
        "",
    ]
    for v in data["venues"]:
        lines += [f"## {v['name']}", "",
                  "| R | 締切 | 艇 | 選手 | 勝つ確率 | 必要オッズ |", "|---|---|---|---|---|---|"]
        for r in v["races"]:
            for pk in r["picks"]:
                lines.append(f"| {r['no']} | {r['deadline']} | {pk['boat']} | {pk['name']} | "
                             f"{pk['p']:.0%} | **{pk['need']:.1f}倍** |")
        lines.append("")
    lines += ["---", "お金を賭けるかどうかはご自身の判断で。20歳未満は舟券を買えません。", ""]
    return "\n".join(lines)


def make_sheet(con, model, feats: pd.DataFrame, date: str) -> str:
    return to_markdown(sheet_data(con, model, feats, date))
