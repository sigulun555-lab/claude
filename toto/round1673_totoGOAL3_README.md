# 第1673回 totoGOAL3（Claude側予測、2026-11-20 締切前日自動配信）

`round1668_totoGOAL3_claude_predictions.json`（既存）に続くtotoGOAL3（指定3試合のみ・
ホーム/アウェイそれぞれのチームの自チーム得点数0点/1点/2点/3点以上を当てる方式）の予測です。
今回追加した `round1673_totoGOAL3_claude_predictions.json` も同じ方式で、probabilitiesのキーが
`{"0","1","2","3"}`（4バケット）です。

- 対象：第1673回 totoGOAL3、指定3試合（販売終了 2026-11-21(土)　ネット決済13:50、締切 2026-11-21T04:50:00Z）
  - FC町田ゼルビア(home) vs V・ファーレン長崎(away)
  - サンフレッチェ広島(home) vs 横浜F・マリノス(away)
  - ガンバ大阪(home) vs ファジアーノ岡山(away)
- 確率値：totoGOAL3アプリ（claude.ai/code/artifact/2d0d0f2e-aece-437a-9bac-ea829805d7c4）本番モデルの
  predictScore()をPlaywrightでアプリのHTMLファイルをそのまま開いて呼び出し、戻り値の
  homeProbs/awayProbs（calculateScoreProbabilities()・poissonProbability()・teamDatabaseの
  該当6クラブの既存登録値を使用）を転記した実際の値（アプリ自体は変更していない）。
- 同じ内容を、Claude/ChatGPT比較基盤リポジトリ `sigulun555-lab/toto-lab` にも
  totoGOAL3専用スキーマ（`schemas/prediction_goal3.schema.json`）形式で保存済み
  （`predictions/round_1673_Claude_goal3.jsonl`）。比較・採点はtoto-lab側で行う。
  このリポジトリ（`claude`）への保存は、ChatGPT側リポジトリ（`sigulun555-lab/gpt`）との
  直接比較に使っていた既存の`toto/`フォルダの運用パターンに揃えるためのもの。
- matchNumber（1〜3）は、toto公式サイト（store.toto-dream.com、holdCntId=1673）の
  第1673回totoGOAL3指定試合表で確認した表示順：
  1試合目=町田vs長崎、2試合目=広島vs横浜FM、3試合目=Ｇ大阪vs岡山（3試合すべて11/21(土)開催）。
- 本ファイルは、締切前日22時頃に実行される自動配信タスクによって生成されました
  （売上・投票率などの確定後の情報は一切使用せず、締切前の時点での予測を確定・保存したものです）。
- 補足：アプリ内部のroundsData（通常toto13試合・miniToto A/B組）側で現在表示されているラウンドは
  第1672回（開催11/14・15、既に販売締切済み）のままで、このタスクではroundsDataの更新は一切
  行っていません（対戦カード自体の更新は別のスケジュールタスクの担当のため）。totoGOAL3の
  第1673回は、通常toto13試合側とは別回・別締切として公式サイトで直接確認したもので、
  teamDatabase内に既存登録済みの6クラブ（machida/nagasaki/hiroshima/yokohama/gamba/okayama）の
  データのみを使って計算しています。
