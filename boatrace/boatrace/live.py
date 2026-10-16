"""毎時のオッズ取得: 朝の予想表の各レースのうち、これから締切になるレースの今の単勝オッズを取る。

朝の予想表の「必要オッズ」と、実際のオッズのズレを見るためのもの。
公式サイトに負担をかけないよう、取るのは「今から WINDOW_MIN 分以内に締切になるレース」だけで、
1件ずつ間隔を空けて取る。
"""
from .market import blend
from .odds import fetch_page, parse_tansho
from .papertrade import EV_MIN
from .sheet import is_candidate

WINDOW_MIN = 20  # 今から何分以内に締切になるレースのオッズを取るか (締切の直前のオッズが一番正確)
LEAD_MIN = 2     # 締切まであと何分より近いレースは取らない (取っても予想表に間に合わない)


def to_minutes(hhmm):
    try:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)
    except (AttributeError, ValueError):
        return None


def select_races(sheet: dict, now_min: int, window: int = WINDOW_MIN, lead: int = 0, cand_only: bool = False):
    """[(締切の分, 場コード, R番号)] を締切の早い順に返す。締切を過ぎたレースは含めない。

    締切まで lead〜window 分のレースだけ。cand_only なら🔴 (予想1位の必要オッズが高いレース) だけ。
    """
    out = []
    for v in sheet["venues"]:
        for r in v["races"]:
            if cand_only and not is_candidate(r):
                continue
            dl = to_minutes(r.get("deadline"))
            if dl is not None and now_min + lead <= dl <= now_min + window:
                out.append((dl, v["code"], r["no"]))
    return sorted(out)


def mixed_probs(pall, odds):
    """朝の6艇ぶんの勝率と今のオッズを市場と合成した {艇: 勝率}。オッズが5艇未満・勝率がなければ None。"""
    if not pall or len(odds) < 5:
        return None
    full = {str(b): odds.get(str(b), 0.0) for b in range(1, 7)}
    mix = blend({int(b): p for b, p in pall.items()}, full)
    return {str(b): p for b, p in mix.items()} if mix else None


def fetch_live(sheet: dict, now, previous=None, window: int = WINDOW_MIN, sleep: float = 1.5,
               fetch=fetch_page, lead: int = LEAD_MIN, cand_only: bool = True) -> dict:
    """{date, asof, fetched, races: {"場コード|R": {at, odds: {艇: オッズ}}}}。

    同じ日の前回の結果があれば引き継ぎ、取り直したレースだけ新しい値にする。
    欠場などでオッズが 0 や空の艇は含めない。
    """
    result = previous if previous and previous.get("date") == sheet["date"] else {"date": sheet["date"], "races": {}}
    result["errors"] = []
    date = sheet["date"].replace("-", "")
    targets = select_races(sheet, now.hour * 60 + now.minute, window, lead, cand_only)
    pall = {f"{v['code']}|{r['no']}": r.get("pall") for v in sheet["venues"] for r in v["races"]}
    for _, code, no in targets:
        try:
            odds = parse_tansho(fetch("oddstf", date, code, no, sleep))
        except Exception as e:  # 1レースの失敗で全体を止めない
            result["errors"].append(f"{code}|{no}: {e}")
            continue
        valid = {b: o for b, o in odds.items() if o and o > 0}
        if valid:
            entry = {"at": now.strftime("%H:%M"), "odds": valid}
            mix = mixed_probs(pall.get(f"{code}|{no}"), valid)
            if mix:
                entry["mix"] = {b: {"p": round(p, 3), "need": round(EV_MIN / p, 1)} for b, p in mix.items()}
            result["races"][f"{code}|{no}"] = entry
    result["asof"] = now.strftime("%H:%M")
    result["fetched"] = len(targets)
    return result
