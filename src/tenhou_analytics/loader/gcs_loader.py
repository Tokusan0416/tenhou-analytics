"""GCSへのmjlogファイルアップロードおよびGCS経由のBigQueryロード。"""

from __future__ import annotations

import tempfile
from pathlib import Path

from google.cloud import storage

from tenhou_analytics.loader.bq_loader import DEFAULT_PROJECT, load_game_to_bigquery
from tenhou_analytics.parser.mjlog import Game, _extract_game_date, parse_mjlog

DEFAULT_BUCKET = "tenhou-log-raw"


def upload_to_gcs(
    filepath: Path,
    *,
    bucket_name: str = DEFAULT_BUCKET,
) -> bool:
    """mjlogファイルをGCSにアップロードする。既存ファイルはスキップ。

    Returns:
        True: アップロードした, False: スキップした
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob_name = filepath.name
    blob = bucket.blob(blob_name)

    if blob.exists():
        return False

    blob.upload_from_filename(str(filepath))
    return True


def list_gcs_files(
    *,
    bucket_name: str = DEFAULT_BUCKET,
) -> list[str]:
    """GCSバケット内のmjlogファイル一覧を取得。"""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs()
    return [blob.name for blob in blobs if blob.name.endswith(".mjlog")]


def load_from_gcs(
    *,
    bucket_name: str = DEFAULT_BUCKET,
    project: str = DEFAULT_PROJECT,
    dataset: str = "tenhou_raw",
    dry_run: bool = False,
) -> list[dict]:
    """GCS上の未処理mjlogファイルをパースしてBigQueryにロードする。

    Returns:
        各ファイルの処理結果リスト
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    gcs_files = list_gcs_files(bucket_name=bucket_name)

    results = []
    for blob_name in sorted(gcs_files):
        blob = bucket.blob(blob_name)

        # GCSからtempfileにダウンロードしてパース
        with tempfile.NamedTemporaryFile(suffix=".mjlog", delete=True) as tmp:
            blob.download_to_filename(tmp.name)
            game = parse_mjlog(tmp.name)
            # ファイル名からmy_seatを復元（tmpだとパスが変わるため）
            game.game_id = _extract_game_id_from_blob(blob_name)
            game.game_date = _extract_game_date(game.game_id)
            game.my_seat = _extract_my_seat_from_blob(blob_name)

        my_player = game.players[game.my_seat]
        entry = {
            "file": blob_name,
            "game_id": game.game_id,
            "player": my_player.name,
            "rounds": len(game.rounds),
            "point": game.final_points[game.my_seat],
        }

        if dry_run:
            entry["status"] = "dry_run"
        else:
            result = load_game_to_bigquery(game, project=project, dataset=dataset)
            if result["raw_games"] > 0:
                entry["status"] = "loaded"
                entry["detail"] = result
            else:
                entry["status"] = "skipped"

        results.append(entry)

    return results


def _extract_game_id_from_blob(blob_name: str) -> str:
    """blobファイル名からgame_idを抽出。"""
    stem = blob_name.replace(".mjlog", "")
    return stem.split("&")[0]


def _extract_my_seat_from_blob(blob_name: str) -> int:
    """blobファイル名からtw=の値を取得。"""
    if "tw=" in blob_name:
        tw_part = blob_name.split("tw=")[1]
        return int(tw_part.replace(".mjlog", ""))
    return 0
