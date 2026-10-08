"""公式サイト(boatrace.jp)のオッズページから締切時オッズを読む。

1ページで1券種の全組み合わせが取れる:
  oddstf  単勝・複勝 (6艇)
  odds3t  3連単 (120通り)
"""
import re
import time
import urllib.error
import urllib.request

from .download import USER_AGENT

URL = "https://www.boatrace.jp/owpc/pc/race/{page}?rno={rno}&jcd={jcd:02d}&hd={hd}"
TD = re.compile(r'<td class="([^"]*)"[^>]*>(.*?)</td>', re.S)
TAG = re.compile(r"<[^>]+>")


def fetch_page(page, date, venue, race_no, sleep=1.0):
    url = URL.format(page=page, rno=race_no, jcd=venue, hd=date)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return res.read().decode("utf-8", errors="replace")
    finally:
        time.sleep(sleep)  # 公式サーバに負荷をかけないよう間隔を空ける


def _num(s):
    try:
        return float(s)
    except ValueError:
        return None  # 欠場などで "-" や空欄


def _cells(html):
    return [(cls, TAG.sub("", text).strip()) for cls, text in TD.findall(html)]


def parse_tansho(html):
    """{'1': 1.5, ...}。単勝表だけを読む (複勝表は範囲表記なので別扱い)。"""
    start = html.find("単勝オッズ</span>")
    end = html.find("複勝オッズ</span>", start)
    if start < 0:
        return {}
    out, boat = {}, None
    for cls, text in _cells(html[start:end if end > 0 else None]):
        if "is-boatColor" in cls and text.isdigit():
            boat = text
        elif "oddsPoint" in cls and boat:
            out[boat] = _num(text)
            boat = None
    return out


def parse_trifecta(html):
    """{'1-2-3': 10.4, ...}。6列(1着の艇) × 20行の表を読む。

    各列は「2着艇(4行に1回, rowspan=4) / 3着艇 / オッズ」の並び。
    """
    out, second = {}, {}
    for row in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        cells = _cells(row)
        if not any("oddsPoint" in c for c, _ in cells):
            continue
        i = 0
        for col in range(1, 7):
            if "is-fs14" in cells[i][0]:
                second[col] = cells[i][1]
                i += 1
            third, odds = cells[i][1], cells[i + 1][1]
            out[f"{col}-{second[col]}-{third}"] = _num(odds)
            i += 2
    return out
