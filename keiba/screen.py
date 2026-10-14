#!/usr/bin/env python3
"""全レースのスクリーニング（毎朝）と結果の集計（毎晩）。

  python3 keiba/screen.py screen   # 朝：全レースを計算し、1点10%以上のレースを選ぶ
  python3 keiba/screen.py settle   # 夜：払戻CSVで全レースの的中を集計する

データ元は keiba.go.jp の「データダウンロード（当日分）」。
基礎確度は prompt.md STEP19a の式を使い、走数が少ない馬の2着率が0%になるのを
防ぐため (回数 + 3/頭数) ÷ (走数 + 3) で平滑化する。近走・馬場・斤量の倍率は
このスクリーニングでは掛けない（選ばれたレースの詳細予想で掛ける）。
"""
import csv
import io
import itertools
import os
import sys
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone

THRESHOLD = 0.10          # 1点の馬連の複合確度がこれ以上のレースを選ぶ（2026-10-14 ユーザー決定・案A）
K = 3                     # 平滑化の強さ
URL = "https://www.keiba.go.jp/KeibaWeb/DataDownload/RaceDataDownload?type=daily"
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def jst_today():
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d")


def load_zip():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=60).read()
    z = zipfile.ZipFile(io.BytesIO(data))
    out = {}
    for name in z.namelist():
        kind = name.rsplit("_", 1)[-1].replace(".csv", "")
        text = z.read(name).decode("utf-8-sig")
        out[kind] = list(csv.DictReader(io.StringIO(text)))
    return out


def record(s):
    try:
        a, b, c, d = [int(x) for x in s.split("-")]
    except ValueError:
        return 0, 0, 0
    return a, b, a + b + c + d


def race_pairs(horses):
    """馬連の複合確度（全組の合計が100%）を {(馬番a, 馬番b): 確度} で返す。"""
    n = len(horses)
    p = {}
    for h in horses:
        w, s, tot = record(h["全成績"])
        p[int(h["馬番"])] = ((w + K / n) / (tot + K), (s + K / n) / (tot + K))
    sc = {}
    for a, b in itertools.combinations(sorted(p), 2):
        sc[(a, b)] = p[a][0] * p[b][1] + p[b][0] * p[a][1]
    total = sum(sc.values())
    return {k: v / total for k, v in sc.items()}


def group_races(horselist):
    races = {}
    for h in horselist:
        if h["馬番"].strip():
            races.setdefault((h["競馬場"], int(h["レース番号"])), []).append(h)
    return races


def screen():
    day = jst_today()
    d = load_zip()
    info = {(r["競馬場"], int(r["レース番号"])): r for r in d["racelist"]}
    rows = []
    for (jo, no), horses in sorted(group_races(d["horselist"]).items()):
        pairs = race_pairs(horses)
        top = sorted(pairs.items(), key=lambda x: -x[1])[:3]
        r = info.get((jo, no), {})
        rows.append({
            "競馬場": jo, "R": no, "発走": r.get("発走時刻", ""), "レース名": r.get("レース名", ""),
            "距離": r.get("距離", ""), "頭数": len(horses),
            "1位": "-".join(map(str, top[0][0])), "1位確度": round(top[0][1] * 100, 1),
            "2位": "-".join(map(str, top[1][0])), "2位確度": round(top[1][1] * 100, 1),
            "3位": "-".join(map(str, top[2][0])), "3位確度": round(top[2][1] * 100, 1),
            "選出": "○" if top[0][1] >= THRESHOLD else "",
        })
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, f"{day}_screen.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    picked = [r for r in rows if r["選出"]]
    print(f"{day}: 全{len(rows)}レースを計算 → 1点{THRESHOLD*100:.0f}%以上は{len(picked)}レース（{path}）")
    for r in sorted(picked, key=lambda x: -x["1位確度"]):
        print(f"  {r['競馬場']}{r['R']}R {r['発走']} {r['レース名']} {r['距離']}m {r['頭数']}頭 "
              f"1位 {r['1位']} {r['1位確度']}% / 2位 {r['2位']} {r['2位確度']}% / 3位 {r['3位']} {r['3位確度']}%")


def settle():
    day = jst_today()
    path = os.path.join(LOG_DIR, f"{day}_screen.csv")
    if not os.path.exists(path):
        sys.exit(f"{path} がありません（朝のスクリーニングが未実行）")
    screen_rows = list(csv.DictReader(open(path, encoding="utf-8")))
    pay = {(r["競馬場"], int(r["レース番号"])): r for r in load_zip()["payback"]}
    done = hit = picked_done = picked_hit = 0
    stake = ret = 0
    for r in screen_rows:
        key = (r["競馬場"], int(r["R"]))
        p = pay.get(key)
        if not p or not p["馬複組番1"].strip():
            continue
        win = {int(p["馬複組番1"]), int(p["馬複組番2"])}
        ok = {int(x) for x in r["1位"].split("-")} == win
        done += 1
        hit += ok
        if r["選出"]:
            picked_done += 1
            picked_hit += ok
            stake += 100
            if ok:
                ret += int(p["馬複払戻金（円）"])
    print(f"{day} 結果確定 {done}/{len(screen_rows)}レース")
    print(f"  全レースの最上位馬連：的中 {hit}/{done}")
    print(f"  選出レース（1点10%以上）：的中 {picked_hit}/{picked_done}  "
          f"購入{stake}円 払戻{ret}円 回収率{(ret / stake * 100 if stake else 0):.0f}%")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"screen": screen, "settle": settle}.get(cmd, lambda: sys.exit(__doc__))()
