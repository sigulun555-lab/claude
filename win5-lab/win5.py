#!/usr/bin/env python3
"""WIN5（JRA指定5レースの1着をすべて当てる馬券）の買い目を組み、結果を記録する（お金は賭けない記録）。

  python3 win5.py plan examples/sample.json --budget 3000          # 予算内で的中確率が最大の買い方を出す
  python3 win5.py plan examples/sample.json --budget 3000 --save   # logs/<日付>_plan.json にも保存する
  python3 win5.py settle logs/2026-10-25_plan.json 3,5,1,12,7 [--payout 1234500]   # 結果を確かめて記録

勝率は、各レースの市場の単勝オッズ（1÷オッズ）を合計1に直したもの（keiba の調査で、全成績だけの確率より
市場のオッズの方がずっと当たると分かったため）。入力ファイルで馬ごとに "p" を書けば、そちらを使う。

WIN5の的中確率 = 5レースそれぞれで「選んだ馬のどれかが1着になる確率」の掛け算。
点数 = 各レースで選んだ頭数の掛け算、1点100円。
"""
import argparse
import csv
import itertools
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "logs")
UNIT = 100           # 1点100円
RETURN_RATE = 0.70   # WIN5の払戻率（売上の70%）
MAX_PAYOUT = 600_000_000  # 1票あたりの払戻の上限（6億円）
LEGS = 5


def jst_now():
    return datetime.now(timezone(timedelta(hours=9)))


def win_p(horses):
    """馬番→勝率。"p" があればそれを合計1に直し、なければ単勝オッズから出す。"""
    if all("p" in h for h in horses):
        t = sum(h["p"] for h in horses)
        return {h["no"]: h["p"] / t for h in horses}
    t = sum(1.0 / h["odds"] for h in horses)
    return {h["no"]: 1.0 / h["odds"] / t for h in horses}


def load(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    legs = d["legs"]
    if len(legs) != LEGS:
        raise SystemExit(f"WIN5は5レースです（入力は{len(legs)}レース）")
    for i, leg in enumerate(legs, 1):
        hs = [h for h in leg["horses"] if not h.get("scratched")]
        if len(hs) < 2:
            raise SystemExit(f"{i}レース目の出走馬が足りません")
        for h in hs:
            if "p" not in h and not (h.get("odds") and h["odds"] > 0):
                raise SystemExit(f"{i}レース目 {h['no']}番の単勝オッズがありません（取消なら \"scratched\": true）")
        if 0 < sum("p" in h for h in hs) < len(hs):
            raise SystemExit(f"{i}レース目：\"p\" を使うときは、出走する全馬に書いてください")
        leg["horses"] = hs
    return d


def ranked(leg):
    """勝率の高い順に [(馬番, 勝率)]。"""
    p = win_p(leg["horses"])
    return sorted(p.items(), key=lambda x: -x[1])


def plan(legs, budget, max_per_leg=8, top=5):
    """予算内で的中確率が最大になる「各レースの頭数」を全通り調べる。

    同じ頭数なら勝率の高い馬から選ぶのが常に最善なので、調べるのは頭数の組み合わせだけ。
    """
    rk = [ranked(l) for l in legs]
    cum = []
    for r in rk:
        c, s = [], 0.0
        for _, v in r:
            s += v
            c.append(s)
        cum.append(c)
    max_pts = budget // UNIT
    found = []
    ranges = [range(1, min(max_per_leg, len(r)) + 1) for r in rk]
    for ks in itertools.product(*ranges):
        pts = 1
        for k in ks:
            pts *= k
        if pts > max_pts:
            continue
        hit = 1.0
        for c, k in zip(cum, ks):
            hit *= c[k - 1]
        found.append((hit, -pts, ks))
    if not found:
        raise SystemExit(f"予算{budget}円では1点も買えません（1点{UNIT}円）")
    found.sort(reverse=True)
    out = []
    for hit, npts, ks in found[:top]:
        out.append({
            "counts": list(ks),
            "points": -npts,
            "cost": -npts * UNIT,
            "hit": hit,
            "picks": [[no for no, _ in r[:k]] for r, k in zip(rk, ks)],
            "leg_hit": [c[k - 1] for c, k in zip(cum, ks)],
        })
    return out


def theory_return(sales, carryover):
    """市場の見立てどおりに当たるとしたときの、1点あたりの理論上の還元率。

    WIN5の払戻 = (売上×70% + キャリーオーバー) ÷ 的中票数。
    みんなが市場の確率どおりに買うなら、どの買い目でも「確率×払戻」は同じになり、
    還元率 ≒ 0.70 + キャリーオーバー ÷ 売上 となる（1.0を超えれば理論上は得）。
    ※払戻の上限（6億円）や、人気の偏り（人気馬ほど買われすぎる傾向）は入れていない目安。
    """
    if not sales:
        return None
    return RETURN_RATE + carryover / sales


def label(k):
    return {1: "1頭（自信）", 2: "2頭", 3: "3頭"}.get(k, f"{k}頭（混戦）")


def fmt_plan(d, plans, budget):
    legs = d["legs"]
    lines = [f"WIN5 {d.get('date', '')}　予算{budget:,}円（1点{UNIT}円）", ""]
    best = plans[0]
    lines.append(f"【おすすめ】{best['points']}点・{best['cost']:,}円　的中確率 {best['hit'] * 100:.2f}%")
    for i, (leg, picks, k, lh) in enumerate(zip(legs, best["picks"], best["counts"], best["leg_hit"]), 1):
        name = {h["no"]: h.get("name", "") for h in leg["horses"]}
        p = win_p(leg["horses"])
        sel = " / ".join(f"{no}番{' ' + name[no] if name[no] else ''}({p[no] * 100:.0f}%)" for no in picks)
        lines.append(f" {i}. {leg.get('race', f'{i}レース目')}：{label(k)}　{sel}　→ このレースの的中 {lh * 100:.0f}%")
    lines.append("")
    if len(plans) > 1:
        lines.append("【ほかの候補】")
        for pl in plans[1:]:
            lines.append(f" 頭数 {'-'.join(map(str, pl['counts']))}　{pl['points']}点・{pl['cost']:,}円　的中確率 {pl['hit'] * 100:.2f}%")
        lines.append("")
    r = theory_return(d.get("sales"), d.get("carryover", 0))
    if r is not None:
        lines.append(f"【期待値の目安】売上{d['sales']:,}円・キャリーオーバー{d.get('carryover', 0):,}円 → 理論上の還元率 {r * 100:.0f}%"
                     + ("（100%超：理論上は得）" if r > 1 else "（100%未満：理論上は損）"))
        lines.append(f" 損をしないために必要なキャリーオーバー：売上の30%（{int(d['sales'] * (1 - RETURN_RATE)):,}円）以上")
    else:
        lines.append("【期待値の目安】売上（sales）を入れると、キャリーオーバー込みの理論上の還元率を出します")
    return "\n".join(lines)


def cmd_plan(a):
    d = load(a.input)
    plans = plan(d["legs"], a.budget, a.max_per_leg)
    print(fmt_plan(d, plans, a.budget))
    if a.save:
        os.makedirs(LOG, exist_ok=True)
        date = d.get("date") or f"{jst_now():%Y-%m-%d}"
        path = os.path.join(LOG, f"{date}_plan.json")
        rec = {"date": date, "budget": a.budget, "input": d, "plan": plans[0],
               "saved_at": jst_now().isoformat(timespec="seconds")}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        print(f"\n保存：{path}")


SUMMARY_HEAD = ["日付", "点数", "購入額", "予想的中確率%", "当たったレース数", "的中", "払戻", "勝ち馬"]


def cmd_settle(a):
    with open(a.plan, encoding="utf-8") as f:
        rec = json.load(f)
    winners = [int(x) for x in a.winners.split(",")]
    if len(winners) != LEGS:
        raise SystemExit("勝ち馬は5つ、カンマ区切りで入れてください（例：3,5,1,12,7）")
    picks = rec["plan"]["picks"]
    ok = [w in p for w, p in zip(winners, picks)]
    hit = all(ok)
    payout = (a.payout or 0) if hit else 0
    cost = rec["plan"]["cost"]
    print(f"WIN5 {rec['date']}　勝ち馬 {'-'.join(map(str, winners))}")
    for i, (w, p, o) in enumerate(zip(winners, picks, ok), 1):
        print(f" {i}. 勝ち馬 {w}番　選んだ馬 {','.join(map(str, p))}　{'✓' if o else '✗'}")
    print(f"結果：{'的中' if hit else 'はずれ'}（{sum(ok)}/5レース）　購入{cost:,}円　払戻{payout:,}円")
    if hit and not a.payout:
        print("※的中しました。払戻金額を --payout で入れると、回収率に反映されます")
    os.makedirs(LOG, exist_ok=True)
    path = os.path.join(LOG, "summary.csv")
    rows = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            rows = [r for r in csv.reader(f)][1:]
    rows = [r for r in rows if r[0] != rec["date"]]
    rows.append([rec["date"], rec["plan"]["points"], cost, round(rec["plan"]["hit"] * 100, 2),
                 sum(ok), "○" if hit else "×", payout, "-".join(map(str, winners))])
    rows.sort()
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(SUMMARY_HEAD)
        w.writerows(rows)
    spent = sum(int(r[2]) for r in rows)
    back = sum(int(r[6]) for r in rows)
    exp = sum(float(r[3]) for r in rows) / 100
    hits = sum(r[5] == "○" for r in rows)
    print(f"\n累計 {len(rows)}回：的中{hits}回（予想上の期待的中回数 {exp:.2f}回）　購入{spent:,}円　払戻{back:,}円"
          + (f"　回収率{back / spent * 100:.1f}%" if spent else ""))
    print(f"記録：{path}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="WIN5の買い目づくりと記録")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="予算内で的中確率が最大の買い方を出す")
    p.add_argument("input")
    p.add_argument("--budget", type=int, default=1000, help="予算（円）。既定1000円")
    p.add_argument("--max-per-leg", type=int, default=8, help="1レースで選ぶ最大頭数。既定8")
    p.add_argument("--save", action="store_true", help="logs/ に保存する")
    p.set_defaults(func=cmd_plan)
    s = sub.add_parser("settle", help="結果を確かめて logs/summary.csv に記録する")
    s.add_argument("plan")
    s.add_argument("winners", help="5レースの勝ち馬番号（例：3,5,1,12,7）")
    s.add_argument("--payout", type=int, help="的中したときの払戻金額（円）")
    s.set_defaults(func=cmd_settle)
    a = ap.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
