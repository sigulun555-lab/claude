from boatrace.sheet import to_markdown


def test_markdown_marks_top_pick():
    data = {"date": "2026-10-14", "venues": [{"code": 24, "name": "大村", "races": [
        {"no": 1, "deadline": "15:20", "picks": [
            {"boat": 1, "name": "大村太郎", "grade": "A1", "p": 0.5, "need": 2.4, "top": True},
            {"boat": 3, "name": "長崎三郎", "grade": "B1", "p": 0.2, "need": 6.0, "top": False}]}]}]}
    text = to_markdown(data)
    assert "大村太郎 〔予想1位〕" in text
    assert "長崎三郎 〔予想1位〕" not in text
