"""直前チェック: 指定したレースの直前情報 (展示タイム・風・波) と現在のオッズで買い/見送りを判定する。"""
import pandas as pd

from . import VENUES
from .db import save_odds
from .features import build_features, load_frame
from .model import predict_win_prob
from .odds import fetch_page, parse_beforeinfo, parse_tansho
from .papertrade import EV_MIN, ODDS_MAX, STAR_ODDS
from .util import race_id as make_race_id

def parse_request(line: str):
    """'2026-10-09 大村 8' や '2026-10-09 24 8' → (YYYYMMDD, 場コード, R番号)。"""
    date, venue, race_no = line.split()[:3]
    names = {v: k for k, v in VENUES.items()}
    code = int(venue) if venue.isdigit() else names[venue]
    return date.replace("-", ""), code, int(race_no.rstrip("Rr"))


def check_races(con, model, requests, sleep=2.0) -> str:
    """requests: [(YYYYMMDD, 場コード, R番号)]。直前情報とオッズを取り、DBに入れてから判定する。"""
    fetched = {}
    for date, venue, rno in requests:
        rid = make_race_id(date, venue, rno)
        info = parse_beforeinfo(fetch_page("beforeinfo", date, venue, rno, sleep))
        odds = parse_tansho(fetch_page("oddstf", date, venue, rno, sleep))
        fetched[rid] = (info, odds)
        for boat, ex in info["exhibition"].items():
            con.execute("INSERT INTO results (race_id, boat, exhibition) VALUES (?,?,?) "
                        "ON CONFLICT(race_id, boat) DO UPDATE SET exhibition=excluded.exhibition",
                        [rid, boat, ex])
        # 風向きは使わない (CHECK_FEATURES 参照)
        con.execute("UPDATE races SET wind_speed=?, wave=? WHERE race_id=?",
                    [info["wind_speed"], info["wave"], rid])
        save_odds(con, [(rid, "単勝", c, v) for c, v in odds.items()])
    con.commit()

    feats = build_features(load_frame(con))
    out = []
    for rid, (info, odds) in fetched.items():
        g = feats[feats["race_id"] == rid].copy()
        venue, rno = int(rid[9:11]), int(rid[12:14])
        title = f"## {VENUES[venue]} {rno}R"
        if len(g) != 6:
            out += [title, "", "出走表が見つかりませんでした。", ""]
            continue
        g["p"] = predict_win_prob(model, g)
        top_boat = int(g.loc[g["p"].idxmax(), "boat"])
        missing = [b for b in range(1, 7) if b not in info["exhibition"] or info["exhibition"][b] is None]
        out += [title, "",
                f"風 {info['wind_speed'] or 0:.0f}m / 波 {info['wave'] or 0:.0f}cm"
                + (" / 展示タイム未発表の艇あり (朝の予想に近い精度です)" if missing else ""),
                "", "| 艇 | 選手 | 展示 | 勝つ確率 | 今のオッズ | 必要オッズ | 判定 |", "|---|---|---|---|---|---|---|"]
        for _, r in g.sort_values("boat").iterrows():
            o = odds.get(str(int(r["boat"])))
            need = EV_MIN / r["p"]
            ok = o and r["boat"] != 6 and o <= ODDS_MAX and r["p"] * o >= EV_MIN
            is_top = int(r["boat"]) == top_boat
            star = is_top and o and o >= STAR_ODDS
            ex = info["exhibition"].get(int(r["boat"]))
            label = f"{int(r['boat'])}{' (予想1位)' if is_top else ''}"
            verdict = ("⭐ " if star else "") + ("**買い**" if ok else "見送り")
            out.append(f"| {label} | {r['name']} | {ex or '-'} | {r['p']:.0%} | {o or '-'} | "
                       f"{need:.1f}倍 | {verdict} |")
        out.append("")
    return "\n".join(out)
