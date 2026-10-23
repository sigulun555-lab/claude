#!/usr/bin/env python3
"""ペーパートレード（お金を賭けない記録）。締切時のオッズで、全レースの馬連・馬単を記録する。

  python3 keiba/paper.py run [YYYY-MM-DD]   # 全レースが終わった夜に実行（省略時は日本時間の今日）
  python3 keiba/paper.py summary            # 累計

競艇のペーパートレードと同じ考え方：各レースの最終オッズ（締切時）で買ったことにして、払戻と比べる。
予想は3つの方法を並べて比べる（どれが当たりやすく、回収できるか）。
  旧式  : 全成績の1着率だけで計算（これまでの式）
  市場  : 市場の単勝オッズ（1÷オッズ）で計算 = 基準
  追加  : 市場＋ab_test.py で「良くなった」と確かめた要素（model.json に要素がある場合だけ）
馬連・馬単の確度はハービル式。オッズは馬連・馬単のオッズページの実際の値を使う。
"""
import csv
import itertools
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ab_test as AB  # noqa: E402
import history as H  # noqa: E402

LOG = os.path.join(HERE, "logs")
SUMMARY = os.path.join(LOG, "paper_summary.csv")
TOPN = 10
EV_MIN_PROB = 0.02   # 期待値で選ぶときは、確度2%以上の組だけ（極端な大穴のオッズの偶然に引っぱられないため）
COLS = ["日付", "グループ", "方法", "戦略", "点数", "的中", "投資", "払戻"]


def group_of(race):
    return "ばんえい" if race["code"] == 3 else "平地"
STRATS = {
    "馬連 確度1位（全レース）": ("馬連", "prob", "race"),
    "馬単 確度1位（全レース）": ("馬単", "prob", "race"),
    "馬連 確度上位10点/日": ("馬連", "prob", "day"),
    "馬単 確度上位10点/日": ("馬単", "prob", "day"),
    "馬連 期待値上位10点/日": ("馬連", "ev", "day"),
    "馬単 期待値上位10点/日": ("馬単", "ev", "day"),
}


def jst_today():
    return datetime.now(timezone(timedelta(hours=9))).date()


def norm(d):
    t = sum(d.values())
    return {k: v / t for k, v in d.items()}


def odds_table(race, kind):
    ds = f"20{race['d'][2:4]}%2F{race['d'][4:6]}%2F{race['d'][6:8]}"
    url = f"{H.BASE}{kind}?k_raceDate={ds}&k_raceNo={race['r']}&k_babaCode={race['code']}"
    html = H.http(url)
    out = {}
    for a, o in re.findall(r'<td align="center" width="20%">(\d+-\d+)</td><td class="[^"]*">([\d.]+)</td>', html):
        x, y = map(int, a.split("-"))
        out[(x, y)] = float(o)
    return out


def old_p(race):
    n = len(race["hs"])
    p = {}
    for h in race["hs"]:
        w, s, t, x = h["all"]
        p[h["no"]] = (w + 3 / n) / (w + s + t + x + 3)
    return norm(p)


def market_p(race):
    return norm({h["no"]: 1.0 / h["odds"] for h in race["hs"]})


def plus_p(race, model):
    names = model["features"]
    X, mask, _ = AB.pack([dict(race, win=race["hs"][0]["no"])], names, model["jockey"] or None, loo=False,
                         gs=model.get("gate_stats") or None)
    p = AB.predict(X, mask, np.array(model["beta"]), np.array(model["mu"]), np.array(model["sd"]))[0]
    return norm({h["no"]: float(p[i]) for i, h in enumerate(race["hs"])})


def pair_probs(p, kind):
    out = {}
    for a, b in itertools.permutations(p, 2):
        if kind == "馬単":
            out[(a, b)] = p[a] * p[b] / (1 - p[a])
        elif a < b:
            out[(a, b)] = p[a] * p[b] / (1 - p[a]) + p[b] * p[a] / (1 - p[b])
    return out


def load_model(group="平地"):
    name = "model.json" if group == "平地" else "model_banei.json"
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return None
    m = json.load(open(path, encoding="utf-8"))
    return m if m.get("features") else None


def run(day):
    races = H.collect_day(day)
    if not races:
        sys.exit(f"{day} は開催がないか、取得できませんでした")
    # 履歴にも追加（その日の分を入れ替える）
    dstr = day.strftime("%Y%m%d")
    keep = [l for l in open(H.DATA, encoding="utf-8")] if os.path.exists(H.DATA) else []
    os.makedirs(os.path.dirname(H.DATA), exist_ok=True)
    with open(H.DATA, "w", encoding="utf-8") as f:
        f.writelines(l for l in keep if json.loads(l)["d"] != dstr)
        for r in races:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    models = {g: load_model(g) for g in ("平地", "ばんえい")}
    methods = {"旧式（全成績）": old_p, "市場（基準）": market_p}
    if any(models.values()):
        def plus(r):
            m = models.get(group_of(r))
            return plus_p(r, m) if m else market_p(r)
        methods["追加（市場＋採用要素）"] = plus
    rows = defaultdict(list)  # (グループ, 方法, 券種) -> 候補の組のリスト（ばんえいと平地は別々に集計）
    n_ok = 0
    for race in races:
        if any(h["odds"] is None for h in race["hs"]) or "馬単" not in race["pay"]:
            continue
        n_ok += 1
        tabs = {"馬連": odds_table(race, "OddsUmLenFuku"), "馬単": odds_table(race, "OddsUmLenTan")}
        actual = {"馬連": (tuple(sorted(race["pay"]["馬連"][0])), race["pay"]["馬連"][1]),
                  "馬単": (tuple(race["pay"]["馬単"][0]), race["pay"]["馬単"][1])}
        for mname, f in methods.items():
            p = f(race)
            for kind in ("馬連", "馬単"):
                pr = pair_probs(p, kind)
                for combo, prob in pr.items():
                    o = tabs[kind].get(combo)
                    if o is None:
                        continue
                    hit = combo == actual[kind][0]
                    rows[(group_of(race), mname, kind)].append({"race": f"{race['v']}{race['r']}R", "combo": combo, "prob": prob,
                                                "odds": o, "ev": prob * o, "hit": hit,
                                                "pay": actual[kind][1] if hit else 0, "rid": (race["code"], race["r"])})
    os.makedirs(LOG, exist_ok=True)
    out_rows = []
    detail = []
    for grp in ("ばんえい", "平地"):
        for mname in methods:
            for sname, (kind, key, scope) in STRATS.items():
                allc = rows.get((grp, mname, kind), [])
                if scope == "race":
                    best = {}
                    for c in allc:
                        if c["rid"] not in best or c[key] > best[c["rid"]][key]:
                            best[c["rid"]] = c
                    chosen = list(best.values())
                else:
                    pool = [c for c in allc if c["prob"] >= EV_MIN_PROB] if key == "ev" else allc
                    chosen = sorted(pool, key=lambda c: -c[key])[:TOPN]
                out_rows.append({"日付": dstr, "グループ": grp, "方法": mname, "戦略": sname, "点数": len(chosen),
                                 "的中": sum(c["hit"] for c in chosen), "投資": 100 * len(chosen),
                                 "払戻": sum(c["pay"] for c in chosen)})
                for c in chosen:
                    if scope == "day":
                        detail.append([grp, mname, sname, c["race"], "-".join(map(str, c["combo"])), round(c["prob"] * 100, 1),
                                       c["odds"], round(c["ev"], 2), "的中" if c["hit"] else "", c["pay"]])
    with open(os.path.join(LOG, f"{dstr}_paper.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["グループ", "方法", "戦略", "レース", "組", "確度%", "オッズ", "期待値", "結果", "払戻"])
        w.writerows(detail)
    old = []
    if os.path.exists(SUMMARY):
        old = [dict(r, グループ=r.get("グループ") or "平地") for r in csv.DictReader(open(SUMMARY, encoding="utf-8"))
               if r["日付"] != dstr]
    with open(SUMMARY, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(old + out_rows)
    print(f"{dstr} 全{len(races)}レース（記録できたのは{n_ok}レース）  方法：{'・'.join(methods)}")
    show(out_rows, f"{dstr} の結果")


def show(rows, title):
    print(f"\n{title}（1点100円）")
    for grp in ("ばんえい", "平地"):
        agg = defaultdict(lambda: [0, 0, 0, 0])
        for r in rows:
            if (r.get("グループ") or "平地") != grp:
                continue
            a = agg[(r["戦略"], r["方法"])]
            a[0] += int(r["点数"])
            a[1] += int(r["的中"])
            a[2] += int(r["投資"])
            a[3] += int(r["払戻"])
        if not agg or all(v[0] == 0 for v in agg.values()):
            continue
        print(f"\n【{grp}】")
        print(f"{'戦略':<22}{'方法':<18}{'点数':>6}{'的中':>5}{'的中率':>8}{'回収率':>8}")
        last = None
        for (s_, m), (n, h, st, pay) in sorted(agg.items(), key=lambda x: (list(STRATS).index(x[0][0]), x[0][1])):
            print(f"{s_ if s_ != last else '':<22}{m:<18}{n:>6}{h:>5}{(h / n * 100 if n else 0):>7.1f}%{(pay / st * 100 if st else 0):>7.0f}%")
            last = s_


def summary():
    if not os.path.exists(SUMMARY):
        sys.exit("まだ記録がありません")
    rows = list(csv.DictReader(open(SUMMARY, encoding="utf-8")))
    days = sorted({r["日付"] for r in rows})
    show(rows, f"累計 {len(days)}日（{days[0]}〜{days[-1]}）")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "run":
        run(date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else jst_today())
    elif cmd == "summary":
        summary()
    else:
        sys.exit(__doc__)
