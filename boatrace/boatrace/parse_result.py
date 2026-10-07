"""競走成績 (Kファイル, KYYMMDD.TXT) のパーサ。"""
import re

from .util import norm, race_id, to_float, to_int

BLOCK_BEGIN = re.compile(r"^(\d{2})KBGN")
BLOCK_END = re.compile(r"^(\d{2})KEND")
RACE_HEADER = re.compile(
    r"^\s*(\d{1,2})R\s+(.+?)\s+H(\d{4})m\s+(\S+)\s+風\s+(\S+)\s+(\d+)m\s+波\s+(\d+)cm(?:\s+(\S+))?"
)
ENTRY = re.compile(
    r"^\s*(\S{1,2})\s+([1-6])\s+(\d{4})\s+(.+?)\s+(\d{1,3})\s+(\d{1,3})\s+"
    r"(\S+)\s+(\S+)\s+(\S+)(?:\s+(.*?))?\s*$"
)
BET_TYPES = {"単勝", "複勝", "2連単", "2連複", "拡連複", "3連単", "3連複"}
PAYOUT_HEAD = re.compile(r"^\s*(単勝|複勝|2連単|2連複|拡連複|3連単|3連複)\s+(.*)$")
PAYOUT_CONT = re.compile(r"^\s+([1-6]-.*)$")
PAYOUT_ITEM = re.compile(r"([1-6](?:-[1-6]){0,2})\s+(\d+)(?:\s+人気\s+(\d+))?")


def _parse_st(s):
    """'0.12' / '.12' -> 0.12, 'F.01' -> (-0.01, 'F'), 'L' 系は None。"""
    flag = None
    if s and s[0] in "FL":
        flag, s = s[0], s[1:]
    v = to_float(s)
    if v is not None and flag == "F":
        v = -v
    return v, flag


def parse_result(text: str, date: str):
    races, results, payouts = [], [], []
    venue = None
    current = None
    bet_type = None
    for raw in text.splitlines():
        line = norm(raw)
        if m := BLOCK_BEGIN.match(line):
            venue = int(m.group(1))
            continue
        if BLOCK_END.match(line):
            venue, current, bet_type = None, None, None
            continue
        if venue is None:
            continue
        if m := RACE_HEADER.match(line):
            no = int(m.group(1))
            current = {
                "race_id": race_id(date, venue, no),
                "date": date,
                "venue": venue,
                "race_no": no,
                "weather": m.group(4),
                "wind_dir": m.group(5),
                "wind_speed": int(m.group(6)),
                "wave": int(m.group(7)),
                "technique": m.group(8),
            }
            races.append(current)
            bet_type = None
            continue
        if current is None:
            continue
        if m := PAYOUT_HEAD.match(line):
            bet_type = m.group(1)
            rest = m.group(2)
        elif bet_type and (m := PAYOUT_CONT.match(line)):
            rest = m.group(1)
        else:
            bet_type = None
            if m := ENTRY.match(line):
                g = m.groups()
                rank = to_int(g[0])
                st, st_flag = _parse_st(g[8])
                results.append({
                    "race_id": current["race_id"],
                    "boat": int(g[1]),
                    "reg_no": int(g[2]),
                    "rank": rank if rank and 1 <= rank <= 6 else None,
                    "rank_raw": g[0],
                    "exhibition": to_float(g[6]),
                    "course": to_int(g[7]),
                    "st": st,
                    "st_flag": st_flag,
                    "race_time": g[9],
                })
            continue
        for combo, amount, pop in PAYOUT_ITEM.findall(rest):
            payouts.append({
                "race_id": current["race_id"],
                "bet_type": bet_type,
                "combo": combo,
                "amount": int(amount),
                "popularity": to_int(pop),
            })
    return races, results, payouts
