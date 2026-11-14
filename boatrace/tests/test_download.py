from datetime import date

from boatrace import download
from boatrace.cli import LOOKBACK_DAYS, _live_start


def _fake_response(data):
    class R:
        def read(self): return data
        def __enter__(self): return self
        def __exit__(self, *a): return False
    return R()


def test_is_stale(tmp_path):
    small, big = tmp_path / "s.lzh", tmp_path / "b.lzh"
    small.write_bytes(b"x" * 295)
    big.write_bytes(b"x" * 30000)
    today = date(2026, 10, 12)
    assert download.is_stale("K", date(2026, 10, 9), small, today)       # ほぼ空
    assert download.is_stale("K", date(2026, 10, 12), big, today)        # 当日 (途中)
    assert download.is_stale("K", date(2026, 10, 10), big, today)        # 2日前まで
    assert not download.is_stale("K", date(2026, 10, 8), big, today)     # 確定済み
    assert not download.is_stale("B", date(2026, 10, 12), small, today)  # 番組表は対象外


def test_fetch_refreshes_stale_and_keeps_old_on_404(tmp_path, monkeypatch):
    path = tmp_path / "k261009.lzh"
    path.write_bytes(b"x" * 295)
    monkeypatch.setattr(download.urllib.request, "urlopen", lambda *a, **k: _fake_response(b"y" * 30000))
    download.fetch("K", date(2026, 10, 9), tmp_path, sleep=0, today=date(2026, 10, 12))
    assert path.stat().st_size == 30000

    def not_found(*a, **k):
        raise download.urllib.error.HTTPError("u", 404, "nf", None, None)
    monkeypatch.setattr(download.urllib.request, "urlopen", not_found)
    path.write_bytes(b"x" * 295)
    assert download.fetch("K", date(2026, 10, 9), tmp_path, sleep=0, today=date(2026, 10, 12)) == path
    assert path.stat().st_size == 295  # 取れなかったので手元のものを消さない


def test_live_start_only_for_recent_ranges(monkeypatch):
    monkeypatch.setattr(download, "today_jst", lambda: date(2026, 10, 12))
    assert _live_start(date(2026, 10, 12), date(2026, 10, 12)) == date(2026, 10, 12 - LOOKBACK_DAYS)
    assert _live_start(date(2025, 10, 1), date(2025, 10, 31)) == date(2025, 10, 1)  # 過去の月は広げない
