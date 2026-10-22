#!/usr/bin/env python3
"""出走表を取ったあと、「的中する確率が50%以上」の買い目を拾って報告する（お金は賭けない記録）。

  python3 keiba/picks.py            # 今日の出走表から拾う（締切に近いほど正確。logs/<日付>_picks.csv に保存）
  python3 keiba/picks.py settle [YYYY-MM-DD]   # 結果が出たあと、拾った買い目の的中・回収を確かめる

確率は、市場の単勝オッズ（1÷オッズ）を合計1に直した勝率から、ハービル式で計算する。
  単勝：その馬が1着になる確率      複勝：その馬が3着以内に入る確率（出走5頭以下は2着以内）
馬連・馬単は50%を超える組がほぼ出ないので、出たときだけ載せる。ばんえい→平地の順に並べる。
"""
import csv
import itertools
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import history as H  # noqa: E402

LOG = os.path.join(HERE, "logs")
THRESH = 0.5


def jst_now():
    return datetime.now(timezone(timedelta(hours=9)))


def win_p(hs):
    t = sum(1.0 / h["odds"] for h in hs)
    return {h["no"]: 1.0 / h["odds"] / t for h in hs}


def top_k_p(p, k):
    out = {}
    nos = list(p)
    for a in nos:
        tot = p[a]
        if k >= 2:
            for b in nos:
                if b == a:
                    continue
                tot += p[b] * p[a] / (1 - p[b])
        if k >= 3:
            for b, c in itertools.permutations([x for x in nos if x != a], 2):
                tot += p[b] * p[c] / (1 - p[b]) * p[a] / (1 - p[b] - p[c])
        out[a] = tot
    return out


def collect(day):
    ds = day.strftime("%Y/%m/%d").replace("/", "%2F")
    rows = []
    for code, vname in H.VENUES.items():
        lst = H.http(f"{H.BASE}RaceList?k_raceDate={ds}&k_babaCode={code}")
        for r in sorted({int(x) for x in re.findall(r"k_raceNo=(\d+)", lst)}):
            html = H.http(f"{H.BASE}DebaTable?k_raceDate={ds}&k_raceNo={r}&k_babaCode={code}")
            page = H.parse_deba(html)
            hs = page["hs"]
            if len(hs) < 4 or any(h["odds"] is None or h["odds"] <= 0 for h in hs):
                continue
            m = re.search(r"(\d{1,2}):(\d{2})発走", html[:80000])
            start = f"{int(m.group(1)):02d}:{m.group(2)}" if m else ""
            p = win_p(hs)
            name = {h["no"]: h["name"] for h in hs}
            grp = "ばんえい" if code == 3 else "平地"
            for no, v in p.items():
                if v >= THRESH:
                    rows.append([grp, vname, r, start, "単勝", str(no), name[no], round(v * 100, 1), next(h["odds"] for h in hs if h["no"] == no)])
            for no, v in top_k_p(p, 3 if len(hs) >= 8 else 2).items():
                if v >= THRESH:
                    rows.append([grp, vname, r, start, "複勝", str(no), name[no], round(v * 100, 1), ""])
            for a, b in itertools.permutations(p, 2):
                v = p[a] * p[b] / (1 - p[a])
                if v >= THRESH:
                    rows.append([grp, vname, r, start, "馬単", f"{a}-{b}", f"{name[a]}→{name[b]}", round(v * 100, 1), ""])
                if a < b:
                    v = p[a] * p[b] / (1 - p[a]) + p[b] * p[a] / (1 - p[b])
                    if v >= THRESH:
                        rows.append([grp, vname, r, start, "馬連", f"{a}-{b}", f"{name[a]}・{name[b]}", round(v * 100, 1), ""])
    return rows


HEAD = ["グループ", "場", "R", "発走", "券種", "買い目", "馬名", "確率%", "単勝オッズ"]


def run():
    now = jst_now()
    rows = collect(now.date())
    order = {"ばんえい": 0, "平地": 1}
    rows.sort(key=lambda x: (order[x[0]], x[4] != "単勝", x[3] or "99", x[2], -x[7]))
    os.makedirs(LOG, exist_ok=True)
    path = os.path.join(LOG, f"{now:%Y%m%d}_picks.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEAD)
        w.writerows(rows)
    print(f"{now:%Y-%m-%d %H:%M} 時点：的中確率50%以上の買い目 {len(rows)}件（締切オッズではない場合は、夜の記録で変わります）")
    for grp in ("ばんえい", "平地"):
        sub = [r for r in rows if r[0] == grp]
        print(f"\n【{grp}】{len(sub)}件")
        for kind in ("単勝", "複勝", "馬連", "馬単"):
            ks = [r for r in sub if r[4] == kind]
            if not ks:
                continue
            print(f" ▼{kind} {len(ks)}件")
            for r in ks[:25]:
                print(f"  {r[1]}{r[2]}R {r[3]} {r[5]} {r[6]}  確率{r[7]}%" + (f" 単勝{r[8]}倍" if r[8] != "" else ""))
            if len(ks) > 25:
                print(f"  …ほか{len(ks) - 25}件（CSVに全件）")
    print(f"\n保存：{path}")


def settle(dstr):
    path = os.path.join(LOG, f"{dstr}_picks.csv")
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    res = {}
    for l in open(H.DATA, encoding="utf-8"):
        r = json.loads(l)
        if r["d"] == dstr:
            res[(r["v"], r["r"])] = r["pay"]
    agg = {}
    for r in rows:
        pay = res.get((r["場"], int(r["R"])))
        if not pay:
            continue
        kind, key = r["券種"], r["買い目"]
        hit, amt = False, 0
        if kind == "単勝":
            hit = pay["単勝"][0] == int(key)
            amt = pay["単勝"][1] if hit else 0
        elif kind == "複勝":
            amt = pay.get("複勝", {}).get(key, 0)
            hit = amt > 0
        elif kind == "馬連":
            hit = sorted(pay["馬連"][0]) == sorted(map(int, key.split("-")))
            amt = pay["馬連"][1] if hit else 0
        elif kind == "馬単":
            hit = pay["馬単"][0] == list(map(int, key.split("-")))
            amt = pay["馬単"][1] if hit else 0
        a = agg.setdefault((r["グループ"], kind), [0, 0, 0.0, 0])
        a[0] += 1
        a[1] += hit
        a[2] += float(r["確率%"])
        a[3] += amt
    print(f"{dstr} 拾った買い目の結果（1点100円）")
    for (grp, kind), (n, h, ps, pay) in sorted(agg.items(), key=lambda x: (x[0][0] != "ばんえい", x[0][1])):
        print(f" {grp} {kind}: {n}件 的中{h}（{h / n * 100:.0f}%／予想の平均{ps / n:.0f}%） 回収{pay / (n * 100) * 100:.0f}%")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "settle":
        settle((sys.argv[2] if len(sys.argv) > 2 else jst_now().strftime("%Y-%m-%d")).replace("-", ""))
    else:
        run()
