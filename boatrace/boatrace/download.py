"""BOAT RACE 公式のダウンロードデータ (番組表 B / 競走成績 K の LZH) を取得・展開する。"""
import io
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import lhafile

BASE_URL = "http://www1.mbrace.or.jp/od2/{kind}/{yyyymm}/{prefix}{yymmdd}.lzh"
USER_AGENT = "boatrace-yosou/0.1 (personal research)"


def lzh_url(kind: str, d: date) -> str:
    return BASE_URL.format(kind=kind, yyyymm=d.strftime("%Y%m"),
                           prefix=kind.lower(), yymmdd=d.strftime("%y%m%d"))


def fetch(kind: str, d: date, raw_dir: Path, sleep: float = 1.0):
    """LZH を取得して raw_dir にキャッシュし、パスを返す。開催なし(404)なら None。"""
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{kind.lower()}{d:%y%m%d}.lzh"
    if path.exists():
        return path
    req = urllib.request.Request(lzh_url(kind, d), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            path.write_bytes(res.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    finally:
        time.sleep(sleep)  # 公式サーバに負荷をかけないよう間隔を空ける
    return path


def extract_text(lzh_path: Path) -> str:
    """LZH 内の TXT (Shift_JIS) を文字列で返す。"""
    archive = lhafile.Lhafile(io.BytesIO(lzh_path.read_bytes()))
    name = archive.namelist()[0]
    return archive.read(name).decode("cp932", errors="replace")


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)
