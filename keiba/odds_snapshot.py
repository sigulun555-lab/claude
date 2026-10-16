#!/usr/bin/env python3
"""その時点の単勝オッズを全レース分、keiba/data/odds_snapshots.jsonl に保存する（朝・昼・夕に実行）。

  python3 keiba/odds_snapshot.py

あとで「発走の1時間以上前のオッズ → 締切時のオッズ」の変化を、予想の要素として試すために使う
（keiba/odds_move_test.py）。まだオッズが出ていないレースは、保存だけして要素には使わない。
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import history as H  # noqa: E402

OUT = os.path.join(HERE, "data", "odds_snapshots.jsonl")


def main():
    now = datetime.now(timezone(timedelta(hours=9)))
    day = now.date()
    ds = day.strftime("%Y/%m/%d").replace("/", "%2F")
    rows = []
    for code, vname in H.VENUES.items():
        lst = H.http(f"{H.BASE}RaceList?k_raceDate={ds}&k_babaCode={code}")
        nos = sorted({int(x) for x in re.findall(r"k_raceNo=(\d+)", lst)})
        if not nos:
            continue
        for r in nos:
            html = H.http(f"{H.BASE}DebaTable?k_raceDate={ds}&k_raceNo={r}&k_babaCode={code}")
            page = H.parse_deba(html)
            if len(page["hs"]) < 4:
                continue
            m = re.search(r"(\d{1,2}):(\d{2})発走", html[:80000])
            start = f"{int(m.group(1)):02d}:{m.group(2)}" if m else None
            rows.append({"t": now.strftime("%Y-%m-%dT%H:%M"), "d": day.strftime("%Y%m%d"), "code": code, "v": vname,
                         "r": r, "start": start, "n": len(page["hs"]),
                         "odds": {str(h["no"]): h["odds"] for h in page["hs"]}})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    got = sum(1 for r in rows if all(v is not None for v in r["odds"].values()))
    print(f"{now:%Y-%m-%d %H:%M} 保存 {len(rows)}レース（全頭のオッズが出ているレース {got}）→ {OUT}")


if __name__ == "__main__":
    main()
