# tenhou-analytics

天鳳の対局ログ（mjlogファイル）を解析し、BigQuery上で自分の麻雀を分析するための環境。

## 概要

天鳳からダウンロードしたmjlogファイルをパース・構造化し、BigQueryにロードした上でdbtによるデータモデリングを行う。
最終的にはSQLでの分析やStreamlitでの可視化を目指す。

## アーキテクチャ

```
mjlogファイル → [tenhou-upload] → GCS → [tenhou-load] → BigQuery raw tables → [dbt] → 分析用テーブル
```

### データパイプライン

1. **mjlog Parser**（Python）: gzip圧縮XMLをパースし構造化データに変換
2. **BigQuery Loader**（Python）: パース結果をBigQueryのrawテーブルにロード
3. **dbt**: rawテーブルからstaging → intermediate → martsへモデリング
4. **可視化**（将来）: Streamlit等でダッシュボード構築

### mjlogフォーマット

mjlogファイルはgzip圧縮されたXML。主要な要素:

| 要素 | 内容 |
|------|------|
| `<GO>` | ゲーム種別（四麻/三麻、東風/東南等） |
| `<UN>` | プレイヤー情報（名前、段位、レート） |
| `<INIT>` | 局の初期状態（配牌、点数、親、ドラ） |
| `<T>/<U>/<V>/<W>` | 各プレイヤー(0-3)のツモ |
| `<D>/<E>/<F>/<G>` | 各プレイヤー(0-3)の打牌 |
| `<N>` | 鳴き（ポン/チー/カン） |
| `<AGARI>` | 和了（役、点数、支払い） |
| `<RYUUKYOKU>` | 流局 |

牌IDは0-135の整数。`ID // 4` で牌種（0-33）に変換可能。

## ディレクトリ構成

```
tenhou-analytics/
├── pyproject.toml
├── data/                        # mjlogファイル（.gitignore済み）
├── src/
│   └── tenhou_analytics/
│       ├── parser/              # mjlog → 構造化データへのパース
│       └── loader/              # BigQueryへのロード
├── dbt/                         # dbtプロジェクト
│   └── models/
│       ├── staging/             # rawテーブルの型変換・リネーム
│       ├── intermediate/        # 局単位・巡目単位の中間テーブル
│       └── marts/               # 分析用の最終テーブル
├── apps/                        # Webアプリ
│   └── mahjong-dashboard/       # Streamlitダッシュボード
└── tests/
```

## セットアップ

```bash
# 依存関係のインストール
uv sync

# mjlogファイルをdata/に配置
# ファイル名例: 2026080814gm-0089-0000-fee5c4f5&tw=0.mjlog
```

## 使い方

### mjlogパーサー

```python
from tenhou_analytics.parser import parse_mjlog

game = parse_mjlog("data/2026080814gm-0089-0000-fee5c4f5&tw=0.mjlog")

# 対局情報
print(game.game_id)
print(game.players[game.my_seat].name)  # 自分のプレイヤー名
print(game.final_points)                # 最終ポイント

# 各局の結果
for r in game.rounds:
    print(f"局={r.round_number} 本場={r.honba} 結果={type(r.result).__name__}")
```

### 新しい対局ログの追加手順

対局後にmjlogファイルをダウンロードしたら、以下の3ステップで反映できます。

```bash
# 1. mjlogファイルをdata/に配置してGCSにアップロード
uv run tenhou-upload data/

# 2. GCSからBigQueryにロード（既存データはスキップ）
uv run tenhou-load --source gcs

# 3. dbtモデルを更新
cd dbt && uv run --group dbt dbt run --profiles-dir . && cd ..
```

Streamlitを開けば新しいデータが反映されています。

### その他のコマンド

```bash
# ローカルファイルから直接BigQueryにロード（GCS経由しない場合）
uv run tenhou-load data/

# パースのみ確認（BigQueryにはロードしない）
uv run tenhou-load --source gcs --dry-run

# dbt フルリフレッシュ（テーブルを再作成）
cd dbt && uv run --group dbt dbt run --profiles-dir . --full-refresh && cd ..
```

### Streamlitダッシュボード

```bash
# ローカル
uv run streamlit run apps/mahjong-dashboard/app.py

# Docker
cd apps/mahjong-dashboard
docker build --platform linux/amd64 -t mahjong-dashboard .
docker run -p 8080:8080 -v $HOME/.config/gcloud:/root/.config/gcloud:ro \
  -e GCP_PROJECT_ID=your-project-id mahjong-dashboard

# Cloud Runへのデプロイ
IMAGE=asia-northeast1-docker.pkg.dev/$GCP_PROJECT_ID/tenhou-apps/mahjong-dashboard:latest
docker build --platform linux/amd64 -t $IMAGE apps/mahjong-dashboard/
docker push $IMAGE
gcloud run deploy mahjong-dashboard --image=$IMAGE --region=asia-northeast1 \
  --service-account=mahjong-dashboard@$GCP_PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars="GCP_PROJECT_ID=$GCP_PROJECT_ID" \
  --port=8080 --memory=512Mi --allow-unauthenticated
```

### テスト

```bash
# Pythonテスト
uv run pytest -v

# dbtテスト（not_null, unique, accepted_values等）
cd dbt && uv run --group dbt dbt test --profiles-dir . && cd ..
```

### dbt Docs（ドキュメント・リネージュ）

```bash
cd dbt && uv run --group dbt dbt docs generate --profiles-dir . && uv run --group dbt dbt docs serve --profiles-dir . && cd ..
```

### schema.ymlひな型の自動生成

新しいモデルを追加した際に、codegenでyamlのひな型を生成できます。

```bash
cd dbt && ./scripts/generate_schema.sh <model_name> && cd ..

# 全モデル一括
cd dbt && ./scripts/generate_schema.sh --all && cd ..
```

生成されたひな型に `description` とテストを追記し、`_<model_name>.yml` として保存してください。

## dbtレイヤー構成

| レイヤー | データセット | 内容 |
|---|---|---|
| staging | `tenhou_staging` | rawテーブルの1:1変換 |
| intermediate | `tenhou_staging` | 副露/リーチ順序/アガリ巡目の導出 |
| warehouse | `tenhou_warehouse` | DIM/FACTテーブル |
| marts | `tenhou_marts` | レポート・可視化用の集計テーブル |

### warehouseのテーブル

- `dim_players`: プレイヤーディメンション
- `dim_game_types`: ゲーム種別ディメンション
- `fct_games`: 対局 × プレイヤーのファクト（順位・ポイント）
- `fct_rounds`: 局ファクト
- `fct_round_player_stats`: プレイヤー × 局のファクト（全スタッツの算出基盤）

### martsのテーブル

- `mart_player_stats`: プレイヤー別スタッツ集計（平均順位、アガリ率、放銃率、副露率、リーチ率等）
- `mart_game_results`: 対局結果一覧（順位推移・累積ポイント付き）
- `mart_yaku_stats`: 役別アガリ回数集計

## CI/CD

GitHub Actionsで自動化しています。認証はWorkload Identity Federation（サービスアカウントキー不要）。

### PR時（ci.yml）

| ステップ | 内容 |
|---|---|
| ruff lint + format check | Pythonコードの品質チェック |
| pytest | パーサーのユニットテスト |
| dbt compile | SQLの構文チェック |
| dbt test | not_null / unique / accepted_values テスト（BQ接続） |

### mainマージ時（deploy.yml）

| ジョブ | 内容 |
|---|---|
| lint-and-test | ruff + pytest |
| deploy | Docker build → Artifact Registry push → Cloud Run デプロイ |
| dbt-run | dbt run（BQテーブル更新） + dbt test |

### ブランチ運用

mainへの直接pushは禁止。`feature/xxx` ブランチでPRを作成し、CIが通ったことを確認してからマージ。

## コスト

- **BigQuery**: 無料枠（10GBストレージ、1TBクエリ/月）で十分
- **Cloud Run**: スケールtoゼロで使わない時はコスト0
- **dbt-core**: OSS版を使用（無料）
- **GCS**: 必要に応じて利用（無料枠5GB）
- **GitHub Actions**: パブリックリポジトリは無料

## 開発状況

### 完了

- [x] mjlogパーサー実装
- [x] BigQueryローダー / GCS連携
- [x] dbtプロジェクト（staging/intermediate/warehouse/marts）
- [x] Streamlitダッシュボード（apps/mahjong-dashboard/）
- [x] dbt schema.yml / テスト整備（persist_docs有効、53テスト、codegen導入）
- [x] Docker化 / Cloud Runデプロイ
- [x] CI/CD（GitHub Actions + Workload Identity Federation）
- [x] 手牌追跡・シャンテン分析・待ち形分析（mahjongライブラリ）

### 今後のステップ

1. **待ち形判定の精度改善** — HandCalculatorによる面子分解ベースに置き換え
2. **SHUFFLE（牌山生成）** — 牌山を再現し残り枚数・ツモ期待値を計算
