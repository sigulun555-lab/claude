"""公式オッズ(市場)との合成 (Benter 方式)。

自前の予想だけで「期待値」を出すと、市場と大きく食い違う艇ばかりが選ばれ、確率が高めに出る
(2026年9月の検証で、期待値1.2以上の買い目は当たる回数が見込みより約2割少なかった)。
市場の見方も混ぜると確率のズレが消え、予想1位の的中率と回収率も上がった。

  合成した確率 ∝ (自前の確率)^a × (市場の確率)^b     (レース内で合計1になるよう揃える)

a, b は 2026年9月の単勝オッズ約4,100レースで当てはめた値。前半で当てはめて後半で、
後半で当てはめて前半で、どちらの向きで検証しても同じ傾向だった (a=0.76〜0.80, b=0.32〜0.38)。
オッズは締切に近いほど正確なので、使えるのは直前チェックのように6艇ぶんのオッズが
そろっているときだけ。朝の予想表 (オッズなし) では使えない。
"""
import math

MODEL_WEIGHT, MARKET_WEIGHT = 0.781, 0.353


def market_probs(odds: dict):
    """{艇: 単勝オッズ} → 控除分をならした市場の勝率。6艇ぶんそろわない・0以下があれば None。"""
    try:
        inv = {int(b): 1.0 / float(o) for b, o in odds.items() if o is not None and float(o) > 0}
    except (TypeError, ValueError):
        return None
    if len(inv) != 6 or len(odds) != 6:
        return None
    total = sum(inv.values())
    return {b: v / total for b, v in inv.items()}


def blend(p: dict, odds: dict):
    """自前の勝率 {艇: p} と単勝オッズ {艇: odds} から、合成した勝率 {艇: p'} を返す。作れなければ None。"""
    q = market_probs(odds)
    p = {int(b): float(v) for b, v in p.items()}
    if q is None or set(p) != set(q) or min(p.values()) <= 0:
        return None
    z = {b: MODEL_WEIGHT * math.log(p[b]) + MARKET_WEIGHT * math.log(q[b]) for b in p}
    top = max(z.values())
    e = {b: math.exp(v - top) for b, v in z.items()}
    s = sum(e.values())
    return {b: v / s for b, v in e.items()}
