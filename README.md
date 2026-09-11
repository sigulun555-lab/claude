# TikTok アフィリエイト コンテンツ自動ドラフト生成

ガジェット・便利グッズ ジャンルのTikTokアフィリエイト向けに、毎日
「トレンドリサーチ → 動画台本 → キャプション/ハッシュタグ」の**下書き**を
自動生成する仕組みです。

## 何が自動化されていて、何が手動なのか

| 工程 | 自動 / 手動 |
|---|---|
| ジャンルのローテーション | 自動(`config/niches.txt`を日替わりで選択) |
| トレンド商品リサーチ(Web検索付き) | 自動(Claude APIのWeb検索ツール) |
| 動画台本・キャプション・ハッシュタグの下書き作成 | 自動 |
| リポジトリへのコミット | 自動(毎日 06:00 JST に GitHub Actions が実行) |
| 内容の事実確認・最終チェック | **手動**(あなたのレビュー) |
| TikTok Shop / ASPへのアフィリエイト提携 | **手動**(あなた自身の申請が必要) |
| 実際の動画撮影・投稿・広告表示(#PR等) | **手動** |

このリポジトリは「量産・下書き」までを担当します。投稿・提携・課金など
実世界に影響する行為は行いません。

## セットアップ

1. GitHubリポジトリの Settings → Secrets and variables → Actions で
   `ANTHROPIC_API_KEY` を登録してください。
2. `.github/workflows/daily-content.yml` が毎日自動実行され、
   `content/<日付>/<ジャンル>/` 配下に `research.md` / `script.md` / `caption.md`
   を生成してコミットします。
3. 手動で今すぐ試したい場合は GitHub Actions の「Run workflow」から
   `Daily TikTok Affiliate Content Draft` を実行するか、ローカルで:

   ```bash
   pip install -r requirements.txt
   export ANTHROPIC_API_KEY=sk-ant-...
   python scripts/generate_content.py
   ```

## ジャンルの調整

`config/niches.txt` の各行がローテーション対象のジャンルです。
自由に追加・編集してください。

## 法令・規約に関する注意

- 生成されるキャプション案には景品表示法のステマ規制に対応した
  `#PR` 等の広告表示を含めるようプロンプトで指示していますが、
  **投稿前に必ず人間が内容を確認してください**。
- TikTok Shop / 各ASPの利用規約・審査は本リポジトリの範囲外です。
  提携申請はご自身で行ってください。
- 生成内容に実在しない実績やレビューを creator に作らせないよう
  指示していますが、最終的な事実確認の責任はご自身にあります。
