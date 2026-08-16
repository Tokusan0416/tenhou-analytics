# CLAUDE.md

このファイルはClaude Codeへのガイダンスを提供する。

## プロジェクト概要

天鳳の対局ログ（mjlog）を解析し、BigQuery + dbtで麻雀の成績を分析する個人プロジェクト。

## 技術スタック

- **言語**: Python 3.11+
- **パッケージ管理**: uv
- **データウェアハウス**: BigQuery
- **データモデリング**: dbt-core
- **可視化**: Streamlit

## ディレクトリ構成

```
src/tenhou_analytics/parser/   # mjlogパーサー（gzip XML → 構造化データ）
src/tenhou_analytics/loader/   # BigQueryローダー
dbt/                           # dbtプロジェクト（staging/intermediate/warehouse/marts）
apps/mahjong-dashboard/        # Streamlitダッシュボード
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
- `tenhou_staging`: dbt staging層 + intermediate層（ビュー）
- `tenhou_warehouse`: DIM/FACTテーブル（ディメンショナルモデル）
  - `dim_players`: プレイヤーディメンション
  - `dim_game_types`: ゲーム種別ディメンション
  - `dim_rounds`: 局ディメンション（局ラベル・東場南場・オーラス）
  - `fct_games`: 対局×プレイヤーファクト（順位・ポイント・game_date・game_order）
  - `fct_rounds`: 局ファクト
  - `fct_round_player_stats`: プレイヤー×局ファクト（アガリ/放銃/被ツモ/横移動/副露/リーチ/順位状況/本場/供託）
- `tenhou_marts`: レポート・可視化用の集計テーブル
  - `mart_player_stats`: プレイヤー別スタッツ集計
  - `mart_game_results`: 対局結果一覧（累積ポイント付き）
  - `mart_yaku_stats`: 役別アガリ集計（カテゴリ・門前副露判定付き）

## GCSバケット

- `tenhou-log-raw`: mjlogファイルの保管先

## CLI

- `tenhou-upload data/` — mjlogファイルをGCSにアップロード（既存スキップ）
- `tenhou-load --source gcs` — GCSからBigQueryにロード（重複自動スキップ）
- `tenhou-load data/` — ローカルファイルから直接BigQueryにロード
- `--dry-run` — パースのみ実行

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
- SQL: 予約語・関数は大文字、Leading comma、テーブルにはASエイリアス、GROUP BYはカラムごと改行、WITH内はインデント
- dbt: SQLFluffでリント（将来）

## 開発ワークフロー

- 作業完了時には必ずREADME.mdとclaude.mdを最新の状態に更新すること
- コミットは機能単位でまとめる
- dbtモデルの追加・編集時は必ず対応する `_model_name.yml` のメタデータ（description, テスト）も更新すること
- `persist_docs` 有効のため、dbt run時にBigQueryのテーブル/カラム説明に自動反映される

### ブランチ運用

- mainへの直接pushは禁止。必ず **feature/xxx ブランチを作成しPR経由でマージ** する
- CIが通ったことを確認してからセルフマージ
- Claude Codeでの作業時も同様：
  1. `git checkout -b feature/xxx` でブランチ作成
  2. 作業・コミット
  3. `git push -u origin feature/xxx` でpush
  4. `gh pr create` でPR作成
  5. CI通過を確認後、マージ

## 現在の開発状況

- [x] mjlogパーサー（constants.py, mjlog.py）
- [x] BigQueryローダー（bq_loader.py, cli.py）
- [x] GCS連携（gcs_loader.py, tenhou-upload CLI）
- [x] dbtプロジェクト（staging/intermediate/warehouse）
- [x] martsモデル（mart_player_stats, mart_game_results, mart_yaku_stats）
- [x] Streamlitアプリ（ローカル）— apps/mahjong-dashboard/
- [x] dbt schema.yml / テスト整備（persist_docs有効、42テスト、codegen導入）
- [x] Docker化
- [x] Cloud Runデプロイ（手動）
- [x] CI/CD（GitHub Actions: ruff + pytest + dbt compile + Cloud Runデプロイ）
- [x] dbt実行の自動化
- [x] テンパイ判定/シャンテン数（mahjongライブラリ、手牌追跡エンジン実装済み）
- [ ] 待ち形判定（面子分解ベースの正確な実装が必要、副露後の短い手牌への対応が課題）
- [ ] SHUFFLE（牌山生成）の実装
