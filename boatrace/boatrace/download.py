"""BOAT RACE 公式のダウンロードデータ (番組表 B / 競走成績 K の LZH) を取得・展開する。"""
import io
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import lhafile

BASE_URL = "http://www1.mbrace.or.jp/od2/{kind}/{yyyymm}/{prefix}{yymmdd}.lzh"
USER_AGENT = "boatrace-yosou/0.1 (personal research)"


def lzh_url(kind: str, d: date) -> str:
    return BASE_URL.format(kind=kind, yyyymm=d.strftime("%Y%m"),
                           prefix=kind.lower(), yymmdd=d.strftime("%y%m%d"))


JST = timezone(timedelta(hours=9))
EMPTY_K_BYTES = 2000      # 成績ファイルがこれより小さければ、結果がまだ入っていない
RECENT_DAYS = 2           # この日数以内の成績ファイルは、レースが進むたびに中身が増える


def today_jst() -> date:
    return datetime.now(JST).date()


def is_stale(kind: str, d: date, path: Path, today: date) -> bool:
    """キャッシュ済みの成績ファイルが未完成の可能性があるか。

    成績 (K) はその日のレースが進むにつれて中身が増え、始まる前はほぼ空のファイルが返る。
    取得した時点のものを一度保存すると、あとで取り直されず結果が欠けたままになるため、
    ほぼ空のものと、直近のものは取り直す。番組表 (B) は当日朝に確定するので対象外。
    """
    if kind != "K":
        return False
    return path.stat().st_size < EMPTY_K_BYTES or (today - d).days <= RECENT_DAYS


def fetch(kind: str, d: date, raw_dir: Path, sleep: float = 1.0, today: date = None):
    """LZH を取得して raw_dir にキャッシュし、パスを返す。開催なし(404)なら None。"""
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{kind.lower()}{d:%y%m%d}.lzh"
    if path.exists() and not is_stale(kind, d, path, today or today_jst()):
        return path
    req = urllib.request.Request(lzh_url(kind, d), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = res.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return path if path.exists() else None  # 取り直せなければ手元のものを使う
        raise
    finally:
        time.sleep(sleep)  # 公式サーバに負荷をかけないよう間隔を空ける
    path.write_bytes(data)
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
