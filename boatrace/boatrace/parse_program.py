"""番組表 (Bファイル, BYYMMDD.TXT) のパーサ。"""
import re

from .util import norm, race_id, to_float, to_int

BLOCK_BEGIN = re.compile(r"^(\d{2})BBGN")
BLOCK_END = re.compile(r"^(\d{2})BEND")
RACE_HEADER = re.compile(r"^\s*(\d{1,2})R\s+(.+?)\s+H(\d{4})m")
DEADLINE = re.compile(r"締切予定\s*(\d{1,2}:\d{2})")
ENTRY = re.compile(
    r"^([1-6]) (\d{4})(.{4})(\d{2})(.{2})(\d{2})([AB][12])\s*"
    r"(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+"
    r"(\d+)\s+(\d+\.\d+)\s+(\d+)\s+(\d+\.\d+)"
)


def parse_program(text: str, date: str):
    """date は YYYYMMDD。races と entries の dict リストを返す。"""
    races, entries = [], []
    venue = None
    current = None
    for raw in text.splitlines():
        line = norm(raw)
        if m := BLOCK_BEGIN.match(line):
            venue = int(m.group(1))
            continue
        if BLOCK_END.match(line):
            venue, current = None, None
            continue
        if venue is None:
            continue
        if m := RACE_HEADER.match(line):
            no = int(m.group(1))
            d = DEADLINE.search(line)
            current = {
                "race_id": race_id(date, venue, no),
                "date": date,
                "venue": venue,
                "race_no": no,
                "race_name": m.group(2).strip(),
                "distance": int(m.group(3)),
                "deadline": d.group(1) if d else None,
            }
            races.append(current)
            continue
        if current and (m := ENTRY.match(line)):
            g = m.groups()
            entries.append({
                "race_id": current["race_id"],
                "boat": int(g[0]),
                "reg_no": int(g[1]),
                "name": g[2].replace(" ", ""),
                "age": to_int(g[3]),
                "branch": g[4].strip(),
                "weight": to_int(g[5]),
                "grade": g[6],
                "nat_win": to_float(g[7]),
                "nat_2r": to_float(g[8]),
                "loc_win": to_float(g[9]),
                "loc_2r": to_float(g[10]),
                "motor_no": to_int(g[11]),
                "motor_2r": to_float(g[12]),
                "boat_no": to_int(g[13]),
                "boat_2r": to_float(g[14]),
            })
    return races, entries
