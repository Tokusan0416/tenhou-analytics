# CLAUDE.md

このファイルはClaude Codeへのガイダンスを提供する。

## プロジェクト概要

天鳳の対局ログ（mjlog）を解析し、BigQuery + dbtで麻雀の成績を分析する個人プロジェクト。

## 技術スタック

- **言語**: Python 3.11+
- **パッケージ管理**: uv
- **データウェアハウス**: BigQuery（無料枠内）
- **データモデリング**: dbt-core
- **可視化**: Streamlit（将来）

## ディレクトリ構成

```
src/tenhou_analytics/parser/   # mjlogパーサー（gzip XML → 構造化データ）
src/tenhou_analytics/loader/   # BigQueryローダー
dbt/                           # dbtプロジェクト（staging/intermediate/marts）
streamlit/                     # 可視化（将来）
data/                          # mjlogファイル（git管理外）
tests/                         # テスト
```

## mjlogフォーマット

- gzip圧縮されたXML
- 牌ID: 0-135の整数。`ID // 4` = 牌種（0-33）
- プレイヤー0-3に対応: ツモ=T/U/V/W、打牌=D/E/F/G
- 主要要素: GO(ゲーム種別), UN(プレイヤー情報), INIT(局初期状態), N(鳴き), AGARI(和了), RYUUKYOKU(流局)

## GCPプロジェクト

- プロジェクトID: `invertible-vine-477701-j8`（名前: tokusan-private-lab）
- リージョン: asia-northeast1

## BigQueryデータセット・テーブル設計

- `tenhou_raw`: Pythonローダーが書き込むrawデータ
  - `raw_games`: 対局メタ情報（プレイヤー、ルール、最終スコア）
  - `raw_rounds`: 局ごとの情報（局、本場、配牌、ドラ、和了/流局結果）
  - `raw_actions`: 巡目ごとのアクション（ツモ/打牌/鳴き）
- `tenhou_staging`: dbt staging層
- `tenhou_marts`: dbt分析用テーブル

## CLI

- `tenhou-load data/` — mjlogファイルをパースしBigQueryにロード（重複自動スキップ）
- `tenhou-load data/ --dry-run` — パースのみ実行

## パーサーの主要データモデル

- `Game`: 対局全体（game_id, players, rounds, final_scores/points, my_seat）
- `Round`: 局単位（round_number, honba, hands, actions, result, reach_players）
- `AgariResult`: 和了（winner, from_who, yaku, han, ten, fu, score_changes）
- `RyuukyokuResult`: 流局（reason, score_changes, tenpai_players）
- `Action`: アクション（type=draw/discard/chi/pon/kan/reach, player, tile, turn）
- `PlayerInfo`: プレイヤー（seat, name, dan, rate）

## コーディング規約

- Python: ruffでフォーマット・リント
- テスト: pytest
- 型ヒント: 使用する
- dbt: SQLFluffでリント（将来）

## 開発ワークフロー

- 作業完了時には必ずREADME.mdとclaude.mdを最新の状態に更新すること
- コミットは機能単位でまとめる

## 現在の開発状況

- [x] mjlogパーサー（constants.py, mjlog.py）
- [x] BigQueryローダー（bq_loader.py, cli.py）
- [ ] dbtプロジェクト
- [ ] Streamlit可視化
