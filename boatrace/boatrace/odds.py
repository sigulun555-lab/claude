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


def parse_fukusho(html):
    """{'1': (1.0, 1.1), ...}。複勝は「下限-上限」の幅で表示され、払戻はレース後に決まる。"""
    start = html.find("複勝オッズ</span>")
    if start < 0:
        return {}
    out, boat = {}, None
    for cls, text in _cells(html[start:]):
        if "is-boatColor" in cls and text.isdigit():
            boat = text
        elif "oddsPoint" in cls and boat:
            lo, _, hi = text.partition("-")
            out[boat] = (_num(lo), _num(hi))
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


def _pair_table(html):
    """6列(1着側の艇) × 5行で、各列が「相手艇 / オッズ」の並びの表。"""
    out = {}
    for row in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        cells = _cells(row)
        if not any("oddsPoint" in c for c, _ in cells):
            continue
        for col in range(1, 7):
            (_, other), (cls, odds) = cells[2 * col - 2], cells[2 * col - 1]
            if "oddsPoint" in cls:
                out[(col, int(other))] = _num(odds)
    return out


def parse_exacta(html):
    """odds2tf ページから {'2連単': {'1-2': 2.8, ...}, '2連複': {'1-2': 1.9, ...}}。"""
    i = html.find("2連単オッズ</span>")
    j = html.find("2連複オッズ</span>")
    if i < 0 or j < 0:
        return {}
    exacta = {f"{a}-{b}": v for (a, b), v in _pair_table(html[i:j]).items()}
    quinella = {f"{min(a, b)}-{max(a, b)}": v for (a, b), v in _pair_table(html[j:]).items()}
    return {"2連単": exacta, "2連複": quinella}


def parse_beforeinfo(html):
    """直前情報ページから {'exhibition': {艇: 展示タイム}, 'wind_speed', 'wave', 'wind_code', 'weather'}。

    wind_code は風向き画像の番号 (is-windN の N)。方角への対応は WIND_CODE_TO_DIR。
    """
    exhibition = {}
    for body in re.findall(r'<tbody class="is-fs12[^"]*">(.*?)</tbody>', html, re.S):
        cells = [TAG.sub("", t).replace("&nbsp;", "").strip()
                 for t in re.findall(r"<td[^>]*>(.*?)</td>", body, re.S)]
        if len(cells) > 4 and cells[0].isdigit():
            exhibition[int(cells[0])] = _num(cells[4])

    def label(title):
        m = re.search(title + r'</span>\s*<span class="weather1_bodyUnitLabelData">\s*([\d.]+)', html)
        return _num(m.group(1)) if m else None

    wind = re.search(r"is-wind(\d+)", html)
    weather = re.search(r'is-weather"?>.*?weather1_bodyUnitLabelTitle">([^<]+)<', html, re.S)
    return {
        "exhibition": exhibition,
        "wind_speed": label("風速"),
        "wave": label("波高"),
        "wind_code": int(wind.group(1)) if wind else None,
        "weather": weather.group(1).strip() if weather else None,
    }
