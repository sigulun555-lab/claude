#!/usr/bin/env python3
"""Daily TikTok affiliate content draft generator.

Picks a rotating gadget niche, has Claude research trending/売れ筋 products via
web search, and writes a script + caption/hashtag draft under content/<date>/.
Output is a DRAFT for human review — nothing here posts to TikTok or joins any
affiliate program automatically.
"""
import datetime
import os
import re
import sys
from pathlib import Path

import anthropic

MODEL = "claude-opus-5"
REPO_ROOT = Path(__file__).resolve().parent.parent
NICHES_FILE = REPO_ROOT / "config" / "niches.txt"
CONTENT_DIR = REPO_ROOT / "content"

SYSTEM_PROMPT = """\
あなたは日本のTikTokアフィリエイト(ガジェット・便利グッズジャンル)向けの
コンテンツストラテジストです。以下のルールを厳守してください。

- 実在しない実績・レビュー・権威付けを作らない。誇大広告や医療的効能の断定はしない。
- 景品表示法のステルスマーケティング規制に従い、投稿キャプション案には必ず
  「#PR」「#広告」等の明確な広告表示を含める。
- 商品リサーチは提供されたweb検索ツールの結果に基づき、根拠となるURLを明記する。
  検索で裏付けが取れない場合は「未確認」と明記し、断定しない。
- 出力は必ず次の3つの見出しで構成し、余計な前置き・後書きを書かない。

## RESEARCH
(トレンド商品候補を3つ、それぞれ商品名・想定価格帯・売れている理由・参考URLを箇条書き)

## SCRIPT
(RESEARCHの中から最も有望な1商品を選び、30〜45秒のTikTok動画構成案。
フック(最初の2秒)/本編/CTAの3パートに分けて書く)

## CAPTION
(投稿キャプション文言と、ハッシュタグ10〜15個。広告表示タグを含める)
"""

SECTION_PATTERN = re.compile(
    r"^##\s*(RESEARCH|SCRIPT|CAPTION)\s*$", re.MULTILINE
)


def pick_niche() -> str:
    niches = [line.strip() for line in NICHES_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    day_index = datetime.date.today().timetuple().tm_yday
    return niches[day_index % len(niches)]


def split_sections(text: str) -> dict:
    matches = list(SECTION_PATTERN.finditer(text))
    sections = {}
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip()
    return sections


def generate(niche: str) -> dict:
    client = anthropic.Anthropic()

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=SYSTEM_PROMPT,
        tools=[
            {
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": 5,
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"今日のジャンルは「{niche}」です。"
                    "このジャンルで直近トレンド・売れ筋のガジェット/便利グッズを"
                    "Web検索で調べたうえで、指定フォーマットで出力してください。"
                ),
            }
        ],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined the request: {response.stop_details}")

    text = "\n".join(block.text for block in response.content if block.type == "text")
    sections = split_sections(text)
    for required in ("RESEARCH", "SCRIPT", "CAPTION"):
        if required not in sections or not sections[required]:
            raise RuntimeError(f"Missing or empty section '{required}' in model output:\n{text}")
    return sections


def write_output(niche: str, sections: dict) -> Path:
    today = datetime.date.today().isoformat()
    slug = re.sub(r"[^0-9A-Za-z一-龯ぁ-んァ-ヶー]+", "-", niche).strip("-")[:40]
    out_dir = CONTENT_DIR / today / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "research.md").write_text(f"# リサーチ: {niche}\n\n{sections['RESEARCH']}\n", encoding="utf-8")
    (out_dir / "script.md").write_text(f"# 動画台本: {niche}\n\n{sections['SCRIPT']}\n", encoding="utf-8")
    (out_dir / "caption.md").write_text(f"# キャプション案: {niche}\n\n{sections['CAPTION']}\n", encoding="utf-8")

    return out_dir


def main() -> int:
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("ERROR: ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN) is not set.", file=sys.stderr)
        return 1

    niche = pick_niche()
    print(f"Generating draft for niche: {niche}")
    sections = generate(niche)
    out_dir = write_output(niche, sections)
    print(f"Wrote draft to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
