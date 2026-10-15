# 毎時オッズお願い (合言葉の手順)

ユーザーが「毎時オッズお願い」と言ったら、その日のぶんの定時トリガー(1回きりのルーティン)を作る。

## 作り方
1. `data` ブランチの `yosou/latest.json` を読み、今日 (日本時間) の分であることを確認する。
   そうでなければ、先に朝の予想表を作る (boatrace/morning_date.txt に今日の日付を書いてプッシュ)。
2. 全レースのうち一番遅い締切 `L` を調べる。
3. 日本時間の毎時50分のうち、「今より後」かつ「L の60分前まで」のものすべてに、
   1回きり (`run_once_at`) のルーティンを作る。`create_new_session_on_fire=true` (毎回まっさらなセッション) にして、
   会話の長い文脈を毎回読み込ませない (そのぶんクレジットが少なくて済む)。
   あわせて、今すぐの1回目はこのセッションで実行する。
4. 作ったルーティンの時刻と、最後の回の時刻をユーザーに伝える。

## ルーティンのプロンプト (そのまま使う)
```
競艇の毎時オッズ取得です。次の手順だけを行い、うまくいったときはユーザーに返事をしないでください。
1. cd /home/user/claude && git checkout boatrace-app && git pull origin boatrace-app
2. 直前の boatrace-data の最新コミットを控える (git fetch origin boatrace-data; git rev-parse origin/boatrace-data)。
3. 日本時間の現在時刻を boatrace/live_request.txt に書き、コミットして boatrace-app にプッシュする。
   (GitHub Actions の boatrace-live が動き、これから75分以内に締切のレースの単勝オッズが
    boatrace-data の live/latest.json に保存される。5〜8分かかる)
4. boatrace-data の最新コミットが手順2から変わるまで待つ (20秒おきに確認、最長12分)。
5. git show origin/boatrace-data:live/latest.json をスクラッチパッドのファイルに保存する。
6. ArtifactData で https://claude.ai/artifact/SVHsxz7oEsskdyY8jbR2Ud の collection=sheets, doc_id=live を
   まず get (なければそのまま set)、続けて set (file_path は手順5のファイル、既存なら if_version を付ける)。
7. 失敗したときだけ、何が失敗したかを1〜2行で報告してください。
```

## 注意 (データの質)
- 締切までが遠いレースは購入が少なく、6艇のうち一部にしかオッズが付かない (1.0倍などの当てにならない値も出る)。
  ページは5艇以上にオッズが付いたものだけを使う。
- 実行の合図に GitHub の schedule は使わない (数時間遅れることがある)。Claude 側の定時トリガーを使う。
