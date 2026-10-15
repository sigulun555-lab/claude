# 毎時オッズお願い (合言葉の手順)

ユーザーが「毎時オッズお願い」と言ったら、その日のぶんの定時トリガーを作る。

## 仕組み (2026-10-15 に動作確認済み)
- 毎時50分に「毎時オッズ係」セッションへ「毎時オッズ実行」というメッセージを送る、1回きりのルーティンを作る。
- 「毎時オッズ係」は、このリポジトリ(boatrace-app)を取得済みで GitHub に書き込める、専用の小さなセッション。
  手順(下)は、このセッションを作るときの最初のメッセージに書いてある。
- **毎回まっさらなセッションを起こすルーティンは使えない**。リポジトリも GitHub の認証も持たないため、
  最初のクローンで失敗する (試して確認済み。失敗1回で約0.1ドル、スマホにも失敗の通知が届く)。
- 実行の合図に GitHub の schedule は使わない (数時間遅れることがある)。

## 作り方
1. 「毎時オッズ係」セッションがなければ作る (`create_session`: source_url=このリポジトリ、source_revision と
   outcome_branch は boatrace-app、permission_mode=auto、最初のメッセージに下の手順を書く。
   セッションIDは 2026-10-15 時点で session_01Y5kzRvHNikSuskpsAUPeLs)。
2. `data` ブランチの `yosou/latest.json` を読み、今日 (日本時間) の分であることを確認する。
   そうでなければ、先に朝の予想表を作る (boatrace/morning_date.txt に今日の日付を書いてプッシュ)。
3. 全レースのうち一番遅い締切 L を調べる。
4. 日本時間の毎時50分のうち「今より後」かつ「L の60分前まで」のものすべてに、1回きり (`run_once_at`) の
   ルーティンを作る。`persistent_session_id` に「毎時オッズ係」のIDを指定し、プロンプトは「毎時オッズ実行」だけ。
5. 作ったルーティンの時刻と最後の回の時刻をユーザーに伝える。

## 「毎時オッズ係」の手順 (1回分)
1. git checkout boatrace-app && git pull origin boatrace-app
2. git fetch origin boatrace-data && git rev-parse origin/boatrace-data で、いまの最新コミットを控える。
3. 日本時間の現在時刻を boatrace/live_request.txt に書き、コミットして boatrace-app にプッシュする。
   GitHub Actions の boatrace-live が動き、これから75分以内に締切のレースの単勝オッズが
   boatrace-data の live/latest.json に保存される (4〜8分)。
4. boatrace-data の最新コミットが変わるまで待つ (20秒おき、最長12分)。
5. git show origin/boatrace-data:live/latest.json を保存する。
6. ArtifactData で、予想表ページの collection=sheets、doc_id=live を get (version を調べる) してから set する。
7. 失敗したときだけ報告する。

## 費用の目安 (API の定価換算)
- 毎時オッズ係の1回: 約0.1〜0.16ドル。1日8回で約1ドル前後。
- Actions: 1回約4分 (1日約32分)。

## 注意 (データの質)
- 締切までが遠いレースは購入が少なく、6艇のうち一部にしかオッズが付かない (1.0倍などの当てにならない値も出る)。
  ページは5艇以上にオッズが付いたものだけを使う。
