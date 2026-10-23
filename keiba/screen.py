#!/usr/bin/env python3
"""全レースのスクリーニング（毎朝）と結果の集計（毎晩）。

  python3 keiba/screen.py screen   # 朝：全レースを計算し、1点10%以上のレースを選ぶ
  python3 keiba/screen.py settle   # 夜：払戻CSVで全レースの的中を集計する
  python3 keiba/screen.py summary  # 累計（日別の集計表）を表示する

馬単は、全レースの「1着馬→2着馬」の確度を並べて上位 EXACTA_N 点を記録する。

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

EXACTA_N = 10            # 馬単は全レース横断で確度の高い順に何点記録するか（2026-10-14 ユーザー決定）
THRESHOLD = 0.10          # 1点の馬連の複合確度がこれ以上のレースを選ぶ（2026-10-14 ユーザー決定・案A）
K = 3                     # 平滑化の強さ
URL = "https://www.keiba.go.jp/KeibaWeb/DataDownload/RaceDataDownload?type=daily"
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def jst_today():
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d")


def load_zip(retries=5):
    """ZIPを取得する。サイト側が一時的にエラーページ(HTML)を返すことがあるので、数回やり直す。"""
    import time
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=60).read()
            z = zipfile.ZipFile(io.BytesIO(data))
            break
        except (zipfile.BadZipFile, OSError) as e:
            last = e
            time.sleep(10 * (i + 1))
    else:
        raise RuntimeError(f"データダウンロードを取得できませんでした: {last}")
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


def race_exacta(horses):
    """馬単の確度（全組の合計が100%）を {(1着馬番, 2着馬番): 確度} で返す。"""
    n = len(horses)
    p = {}
    for h in horses:
        w, s, tot = record(h["全成績"])
        p[int(h["馬番"])] = ((w + K / n) / (tot + K), (s + K / n) / (tot + K))
    sc = {(a, b): p[a][0] * p[b][1] for a in p for b in p if a != b}
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
    exacta = []
    for (jo, no), horses in sorted(group_races(d["horselist"]).items()):
        for (a, b), pr in race_exacta(horses).items():
            exacta.append((pr, jo, no, a, b, len(horses)))
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
    exacta.sort(reverse=True)
    top = exacta[:EXACTA_N]
    epath = os.path.join(LOG_DIR, f"{day}_exacta.csv")
    with open(epath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["順位", "競馬場", "R", "1着", "2着", "頭数", "確度"])
        for i, (pr, jo, no, a, b, n) in enumerate(top, 1):
            w.writerow([i, jo, no, a, b, n, round(pr * 100, 1)])
    print(f"馬単 上位{EXACTA_N}点（全レース横断）：合計確度{sum(x[0] for x in top) * 100:.0f}%（{epath}）")
    for i, (pr, jo, no, a, b, n) in enumerate(top, 1):
        print(f"  {i:>2}. {jo}{no}R {n}頭 {a}→{b} 確度{pr * 100:.1f}%")
    picked = [r for r in rows if r["選出"]]
    print(f"{day}: 全{len(rows)}レースを計算 → 1点{THRESHOLD*100:.0f}%以上は{len(picked)}レース（{path}）")
    for r in sorted(picked, key=lambda x: -x["1位確度"]):
        print(f"  {r['競馬場']}{r['R']}R {r['発走']} {r['レース名']} {r['距離']}m {r['頭数']}頭 "
              f"1位 {r['1位']} {r['1位確度']}% / 2位 {r['2位']} {r['2位確度']}% / 3位 {r['3位']} {r['3位確度']}%")


SUMMARY = os.path.join(LOG_DIR, "summary.csv")
SUMMARY_COLS = ["日付", "全レース確定", "全レース最上位馬連的中", "選出レース確定", "選出的中", "選出投資", "選出払戻",
                "馬単確定点数", "馬単的中", "馬単投資", "馬単払戻"]


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
        p = pay.get((r["競馬場"], int(r["R"])))
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

    e_done = e_hit = e_stake = e_ret = 0
    epath = os.path.join(LOG_DIR, f"{day}_exacta.csv")
    if os.path.exists(epath):
        for r in csv.DictReader(open(epath, encoding="utf-8")):
            p = pay.get((r["競馬場"], int(r["R"])))
            if not p or not p["馬単組番1"].strip():
                print(f"  馬単{r['順位']}位 {r['競馬場']}{r['R']}R {r['1着']}→{r['2着']} 未確定")
                continue
            ok = (int(p["馬単組番1"]), int(p["馬単組番2"])) == (int(r["1着"]), int(r["2着"]))
            e_done += 1
            e_stake += 100
            e_hit += ok
            if ok:
                e_ret += int(p["馬単払戻金（円）"])
            print(f"  馬単{r['順位']}位 {r['競馬場']}{r['R']}R {r['1着']}→{r['2着']} 確度{r['確度']}% "
                  f"{'的中 ' + p['馬単払戻金（円）'] + '円' if ok else '外れ'}")
        print(f"  馬単{EXACTA_N}点：確定{e_done}点 的中{e_hit} 購入{e_stake}円 払戻{e_ret}円 "
              f"回収率{(e_ret / e_stake * 100 if e_stake else 0):.0f}%")

    rows = []
    if os.path.exists(SUMMARY):
        rows = [r for r in csv.DictReader(open(SUMMARY, encoding="utf-8")) if r["日付"] != day]
    rows.append(dict(zip(SUMMARY_COLS, [day, done, hit, picked_done, picked_hit, stake, ret,
                                        e_done, e_hit, e_stake, e_ret])))
    with open(SUMMARY, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"  日別集計を {SUMMARY} に保存")


def summary():
    if not os.path.exists(SUMMARY):
        sys.exit("まだ集計がありません")
    rows = list(csv.DictReader(open(SUMMARY, encoding="utf-8")))
    tot = {c: sum(int(r[c]) for r in rows) for c in SUMMARY_COLS[1:]}

    def pct(a, b):
        return f"{a / b * 100:.1f}%" if b else "-"
    print(f"累計 {len(rows)}日（{rows[0]['日付']}〜{rows[-1]['日付']}）")
    print(f"  全レース最上位馬連 : 的中率 {pct(tot['全レース最上位馬連的中'], tot['全レース確定'])} "
          f"（{tot['全レース最上位馬連的中']}/{tot['全レース確定']}）")
    print(f"  選出レース(馬連)   : 的中率 {pct(tot['選出的中'], tot['選出レース確定'])} "
          f"回収率 {pct(tot['選出払戻'], tot['選出投資'])}（{tot['選出的中']}/{tot['選出レース確定']}、投資{tot['選出投資']}円）")
    print(f"  馬単{EXACTA_N}点/日        : 的中率 {pct(tot['馬単的中'], tot['馬単確定点数'])} "
          f"回収率 {pct(tot['馬単払戻'], tot['馬単投資'])}（{tot['馬単的中']}/{tot['馬単確定点数']}、投資{tot['馬単投資']}円）")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"screen": screen, "settle": settle, "summary": summary}.get(cmd, lambda: sys.exit(__doc__))()
