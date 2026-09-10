#!/usr/bin/env python3
"""note向け記事ドラフトを自動生成するスクリプト。

使い方:
    export ANTHROPIC_API_KEY=sk-ant-...
    python generate_articles.py --count 3

生成された記事は output/articles/ にMarkdownで保存される。
noteには投稿用の公開APIが無いため、生成後は手動でnoteのエディタに
貼り付けて投稿する運用を想定している(規約違反になりうる自動投稿は行わない)。
"""
import argparse
import datetime
import json
import pathlib
import re
import sys

import anthropic

ROOT = pathlib.Path(__file__).parent
TOPICS_FILE = ROOT / "topics.json"
USED_FILE = ROOT / "used_topics.json"
OUTPUT_DIR = ROOT / "output" / "articles"

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """あなたは日本語で「お金・副業・投資」ジャンルのnote記事を書くライターです。
以下のルールを厳守してください。

- 特定の金融商品・銘柄・副業案件を名指しで推奨しない(一般的な考え方や制度の説明にとどめる)
- 「絶対に儲かる」「必ず稼げる」など断定的・誇大な表現を使わない
- 具体的な金額例を出す場合は「あくまで一例」であることを明記する
- 投資は元本割れのリスクがあることに必ず触れる
- 実体験のように書く場合も、事実として断定せず一般化した書き方にする
- 読者が今日から実践できる具体的な手順を含める

出力はnoteにそのまま貼り付けられるMarkdown形式で、以下の構成にしてください。

1. タイトル (# 見出し)
2. 無料で読める導入部分(悩みへの共感 + 記事を読むメリット、400字程度)
3. 無料部分の本文(概要・背景説明、600〜800字程度)
4. `---\\n\\n### ここから先は有料エリアです\\n\\n---` という区切り
5. 有料部分の本文(具体的な手順・チェックリスト・実践のコツ、800〜1200字程度)
6. まとめ(150字程度)
7. 免責事項(投資助言でないこと、個人の見解であることを1〜2行で)
8. 想定タグを5個(#で始まる形式)
9. 想定販売価格(100円〜500円程度)の提案とその理由を1行

記事本文以外の前置き・後書きコメントは一切出力しないでください。
"""


def load_json(path: pathlib.Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: pathlib.Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\-]+", "-", text, flags=re.UNICODE).strip("-")
    return text[:40] if text else "article"


def pick_topics(topics, used_ids, count):
    unused = [t for t in topics if t["id"] not in used_ids]
    if len(unused) < count:
        unused = topics  # 使い切ったら再度ローテーションする
    return unused[:count]


def generate_one(client: "anthropic.Anthropic", topic: dict) -> str:
    user_prompt = (
        f"テーマ: {topic['title']}\n"
        f"切り口: {topic['angle']}\n"
        "このテーマで記事を1本書いてください。"
    )
    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in message.content if block.type == "text")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1, help="生成する記事数")
    args = parser.parse_args()

    topics = load_json(TOPICS_FILE, [])
    if not topics:
        print("topics.json にテーマがありません。", file=sys.stderr)
        sys.exit(1)

    used = load_json(USED_FILE, [])
    used_ids = set(used)

    targets = pick_topics(topics, used_ids, args.count)
    if not targets:
        print("生成対象のテーマがありません。", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for topic in targets:
        print(f"生成中: {topic['title']}")
        article_md = generate_one(client, topic)

        date_str = datetime.date.today().isoformat()
        filename = f"{date_str}-{slugify(topic['title'])}.md"
        out_path = OUTPUT_DIR / filename
        out_path.write_text(article_md, encoding="utf-8")
        print(f"  -> {out_path}")

        used_ids.add(topic["id"])

    save_json(USED_FILE, sorted(used_ids))
    print(f"{len(targets)}本の記事を生成しました。{OUTPUT_DIR} を確認してください。")


if __name__ == "__main__":
    main()
