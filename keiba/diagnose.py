#!/usr/bin/env python3
"""馬連の予想がなぜ外れるかを、過去のレース（backtest_cache）で調べる。

  python3 keiba/diagnose.py

前提：keiba/backtest.py を先に実行して backtest_cache を作っておく。
"""
import glob
import itertools
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as B  # noqa: E402
import screen as S  # noqa: E402

CACHE = B.CACHE


def load():
    refunds = {}
    for f in glob.glob(f"{CACHE}/refund_*.html"):
        m = re.search(r"refund_(\d{8})_(\d+)\.html", f)
        rf = B.parse_refund(open(f, encoding="utf-8", errors="ignore").read())
        for r, v in rf.items():
            refunds[(m.group(1), int(m.group(2)), r)] = v
    races = []
    for (d, code, r), pay in sorted(refunds.items()):
        p = f"{CACHE}/deba_{d}_{code}_{r}.html"
        if not os.path.exists(p) or "単勝" not in pay:
            continue
        hs = [h for h in B.parse_deba(open(p, encoding="utf-8", errors="ignore").read()) if h["odds"]]
        if len(hs) < 4:
            continue
        win = pay["単勝"][0]
        a, b = pay["馬連"][0]
        if win not in (a, b):
            continue
        second = b if win == a else a
        races.append({"d": d, "code": code, "r": r, "hs": hs, "win": win, "second": second,
                      "pair": pay["馬連"][0], "pair_pay": pay["馬連"][1], "pay": pay})
    return races


def norm(d):
    t = sum(d.values())
    return {k: v / t for k, v in d.items()}


def model_p(hs):
    n = len(hs)
    p = {}
    for h in hs:
        w, s, tot = S.record(h["全成績"])
        p[int(h["馬番"])] = (w + S.K / n) / (tot + S.K)
    return norm(p)


def market_p(hs):
    return norm({int(h["馬番"]): 1.0 / h["odds"] for h in hs})


def blend(pm, pk, a):
    """a=1でモデルだけ、a=0で市場だけ（対数をまぜる）"""
    return norm({k: (pm[k] ** a) * (pk[k] ** (1 - a)) for k in pm})


def harville_pairs(p):
    out = {}
    for a, b in itertools.combinations(sorted(p), 2):
        out[(a, b)] = p[a] * p[b] / (1 - p[a]) + p[b] * p[a] / (1 - p[b])
    return out


def evaluate(races, pfun, label):
    n = hit = ret = 0
    ll = 0.0
    top1 = 0
    for r in races:
        p = pfun(r["hs"])
        ll += -math.log(max(p[r["win"]], 1e-9))
        top1 += max(p, key=p.get) == r["win"]
        pairs = harville_pairs(p)
        best = max(pairs, key=pairs.get)
        n += 1
        if best == r["pair"]:
            hit += 1
            ret += r["pair_pay"]
    print(f"{label:<26} 勝ち馬の対数損失 {ll / n:.3f}  1位が勝つ率 {top1 / n * 100:4.1f}%  "
          f"馬連1位 的中 {hit:>3}/{n} ({hit / n * 100:4.1f}%) 回収率 {ret / (100 * n) * 100:3.0f}%")
    return ll / n


def main():
    races = load()
    days = sorted({r["d"] for r in races})
    print(f"{len(races)}レース（{days[0]}〜{days[-1]}）")
    train = [r for r in races if r["d"] <= "20261007"]
    test = [r for r in races if r["d"] > "20261007"]
    print(f"前半（調整用）{len(train)}レース / 後半（確認用）{len(test)}レース\n")

    # 現行式（screen.py の馬連式そのまま）
    def current_hit(rs):
        n = hit = ret = 0
        for r in rs:
            hs = [{"馬番": h["馬番"], "全成績": h["全成績"]} for h in r["hs"]]
            pr = S.race_pairs(hs)
            best = max(pr, key=pr.get)
            n += 1
            if best == r["pair"]:
                hit += 1
                ret += r["pair_pay"]
        return n, hit, ret

    for name, rs in (("全期間", races), ("前半", train), ("後半", test)):
        n, h, ret = current_hit(rs)
        print(f"[{name}] 現行の馬連式       馬連1位 的中 {h:>3}/{n} ({h / n * 100:4.1f}%) 回収率 {ret / (100 * n) * 100:3.0f}%")
    print()
    for name, rs in (("全期間", races), ("前半", train), ("後半", test)):
        print(f"--- {name} ---")
        evaluate(rs, model_p, "全成績だけ（ハービル式）")
        evaluate(rs, market_p, "市場のオッズだけ")
        for a in (0.2, 0.4, 0.6):
            evaluate(rs, lambda hs, a=a: blend(model_p(hs), market_p(hs), a), f"全成績{int(a * 100)}%＋市場{int((1 - a) * 100)}%")
        print()

    # 較正：モデルが「勝つ」と言った確率と、実際の勝率
    print("【較正】モデルの予想勝率と、実際の勝率（全期間・馬ごと）")
    for label, f in (("全成績だけ", model_p), ("市場", market_p)):
        bucket = defaultdict(lambda: [0, 0, 0.0])
        for r in races:
            p = f(r["hs"])
            for k, v in p.items():
                b = min(int(v * 100 // 5), 8)
                bucket[b][0] += 1
                bucket[b][1] += k == r["win"]
                bucket[b][2] += v
        print(f"  {label}")
        for b in sorted(bucket):
            n, w, sp = bucket[b]
            print(f"    予想{b * 5:>2}〜{b * 5 + 5:>2}%台: {n:>4}頭  平均予想 {sp / n * 100:4.1f}% → 実際 {w / n * 100:4.1f}%")

    # 馬連オッズの推定式の精度（プロンプトの 単勝A×単勝B÷2.1）
    errs = []
    for r in races:
        o = {int(h["馬番"]): h["odds"] for h in r["hs"]}
        a, b = r["pair"]
        if a in o and b in o:
            errs.append(math.log((o[a] * o[b] / 2.1) / (r["pair_pay"] / 100)))
    errs.sort()
    print(f"\n【馬連オッズの推定式】単勝A×単勝B÷2.1 と実際の払戻の比（的中した組・{len(errs)}件）: "
          f"中央 {math.exp(errs[len(errs) // 2]):.2f}倍, 下位25% {math.exp(errs[len(errs) // 4]):.2f}倍, "
          f"上位25% {math.exp(errs[3 * len(errs) // 4]):.2f}倍")

    # 人気別：勝ち馬の人気
    pop = defaultdict(int)
    for r in races:
        w = [h for h in r["hs"] if int(h["馬番"]) == r["win"]]
        if w and w[0]["pop"]:
            pop[min(w[0]["pop"], 6)] += 1
    tot = sum(pop.values())
    print("\n【勝ち馬の人気】" + " / ".join(f"{k}人気{'以下' if k == 6 else ''} {v / tot * 100:.0f}%" for k, v in sorted(pop.items())))


if __name__ == "__main__":
    main()
