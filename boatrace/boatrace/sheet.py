"""朝の予想表: その日の全レースで「この艇がこのオッズ以上なら単勝を買い」を出す。

ルールはペーパートレードと同じ (期待値1.2以上、6号艇と50倍超は買わない)。
必要オッズ = 1.2 / 勝つ確率。締切前のオッズがこれ以上なら買い、届かなければ見送り。
"""
import pandas as pd

from . import VENUES
from .model import predict_win_prob
from .papertrade import EV_MIN, ODDS_MAX


def make_sheet(con, model, feats: pd.DataFrame, date: str) -> str:
    day = feats[feats["date"] == date].copy()
    day = day[day.groupby("race_id")["boat"].transform("size") == 6]
    if day.empty:
        return f"# {date[:4]}/{date[4:6]}/{date[6:]} の予想表\n\n対象レースがありません。\n"
    day["p"] = predict_win_prob(model, day)
    deadline = dict(con.execute("SELECT race_id, deadline FROM races WHERE date = ?", [date]))

    lines = [
        f"# {date[:4]}/{date[4:6]}/{date[6:]} の予想表 (単勝)",
        "",
        "締切前のオッズが **必要オッズ以上** なら買い、届かなければ見送り。",
        "展示タイムを使わない朝の予想です。気になるレースは「○○ ○R 直前」で直前チェックできます。",
        "",
    ]
    for venue, vg in day.groupby("venue", observed=True):
        lines += [f"## {VENUES.get(int(venue), venue)}", "",
                  "| R | 締切 | 艇 | 選手 | 勝つ確率 | 必要オッズ |", "|---|---|---|---|---|---|"]
        for race_id, g in vg.groupby("race_id"):
            g = g.sort_values("p", ascending=False)
            shown = 0
            for _, r in g.iterrows():
                need = EV_MIN / r["p"]
                if r["boat"] == 6 or need > ODDS_MAX:
                    continue
                lines.append(f"| {int(r['race_no'])} | {deadline.get(race_id) or ''} | {int(r['boat'])} | "
                             f"{r['name']} | {r['p']:.0%} | **{need:.1f}倍** |")
                shown += 1
                if shown >= 3:
                    break
        lines.append("")
    lines += ["---", "お金を賭けるかどうかはご自身の判断で。20歳未満は舟券を買えません。", ""]
    return "\n".join(lines)
