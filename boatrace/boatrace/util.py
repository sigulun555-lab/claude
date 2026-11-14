import unicodedata


def norm(line: str) -> str:
    """全角英数・全角スペースを半角に揃える(漢字はそのまま、文字数は変わらない)。"""
    return unicodedata.normalize("NFKC", line).rstrip("\r\n")


def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def to_int(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def race_id(date: str, venue: int, race_no: int) -> str:
    return f"{date}_{venue:02d}_{race_no:02d}"
