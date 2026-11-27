# 第1675回 totoGOAL3（Claude側予測、2026-11-27 締切前日自動配信）

`round1674_totoGOAL3_claude_predictions.json`（既存）に続くtotoGOAL3（指定3試合のみ・
ホーム/アウェイそれぞれのチームの自チーム得点数0点/1点/2点/3点以上を当てる方式）の予測です。
今回追加した `round1675_totoGOAL3_claude_predictions.json` も同じ方式で、probabilitiesのキーが
`{"0","1","2","3"}`（4バケット）です。

- 対象：第1675回 totoGOAL3、指定3試合（開催 2026-11-28(土)・2026-11-29(日)、販売終了
  2026-11-28(土) ネット決済13:50、締切 2026-11-28T04:50:00Z）
  - 京都サンガ(home) vs セレッソ大阪(away)
  - 横浜F・マリノス(home) vs FC東京(away)
  - 名古屋グランパス(home) vs アビスパ福岡(away)

  今回は通常toto13試合側の第1675回と同一回・同一締切で、対象3試合も13試合中の
  1試合目・3試合目・5試合目と同じ組み合わせです（toto公式サイト store.toto-dream.com、
  holdCntId=1675 で確認）。

- 確率値：totoGOALアプリ（claude.ai/code/artifact/2d0d0f2e-aece-437a-9bac-ea829805d7c4）本番モデルの
  predictScore()をPlaywrightでアプリのHTMLファイルをそのまま開いて呼び出し、戻り値の
  homeProbs/awayProbs（calculateScoreProbabilities()・poissonProbability()・teamDatabaseの
  該当6クラブの既存登録値を使用）を転記した実際の値（アプリ自体は変更していない）。

- 同じ内容を、Claude/ChatGPT比較基盤リポジトリ `sigulun555-lab/toto-lab` にも
  totoGOAL3専用スキーマ（`schemas/prediction_goal3.schema.json`）形式で保存済み
  （`predictions/round_1675_Claude_goal3.jsonl`）。比較・採点はtoto-lab側で行う。
  このリポジトリ（`claude`）への保存は、ChatGPT側リポジトリ（`sigulun555-lab/gpt`）との
  直接比較に使っていた既存の`toto/`フォルダの運用パターンに揃えるためのもの。

- matchNumber（1〜3）は、toto公式サイト（store.toto-dream.com、holdCntId=1675）の
  第1675回totoGOAL3指定試合表で確認した表示順：
  1試合目=京都vsＣ大阪、2試合目=横浜FMvsFC東京、3試合目=名古屋vs福岡（いずれも
  通常toto13試合側の1・3・5試合目と同一カード）。

- 本ファイルは、締切前日22時頃に実行される自動配信タスクによって生成されました
  （売上・投票率などの確定後の情報は一切使用せず、締切前の時点での予測を確定・保存したものです）。

- 補足：アプリ内部のroundsData（第1675回）には、本タスク実行時点で `injuryPresets` の登録が
  無かったため、怪我人補正は適用されていません（対象0名のため、アプリ本番値と同一）。
  負傷・出場停止情報の追加調査はこのタスクの担当外（別スケジュールタスクが対象）です。
