"""CLIエントリポイント。

mjlogファイルのGCSアップロード・BigQueryロードを行う。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tenhou_analytics.loader.bq_loader import load_game_to_bigquery
from tenhou_analytics.loader.gcs_loader import (
    load_from_gcs,
    upload_to_gcs,
)
from tenhou_analytics.parser.mjlog import parse_mjlog


def main_upload() -> None:
    """tenhou-upload: ローカルのmjlogファイルをGCSにアップロード。"""
    parser = argparse.ArgumentParser(
        description="mjlogファイルをGCSにアップロード",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="mjlogファイルまたはディレクトリのパス",
    )
    parser.add_argument(
        "--bucket",
        default="tenhou-log-raw",
        help="GCSバケット名",
    )

    args = parser.parse_args()

    files = _collect_mjlog_files(args.paths)
    if not files:
        print("No mjlog files found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(files)} mjlog file(s)")

    uploaded = 0
    skipped = 0
    for filepath in files:
        if upload_to_gcs(filepath, bucket_name=args.bucket):
            print(f"  Uploaded: {filepath.name}")
            uploaded += 1
        else:
            print(f"  Skipped (already exists): {filepath.name}")
            skipped += 1

    print(f"Done. Uploaded: {uploaded}, Skipped: {skipped}")


def main_load() -> None:
    """tenhou-load: mjlogファイルをパースしてBigQueryにロード。"""
    parser = argparse.ArgumentParser(
        description="mjlogファイルをパースしてBigQueryにロード",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="mjlogファイルまたはディレクトリのパス（--source gcs 時は不要）",
    )
    parser.add_argument(
        "--source",
        choices=["local", "gcs"],
        default="local",
        help="データソース（default: local）",
    )
    parser.add_argument(
        "--bucket",
        default="tenhou-log-raw",
        help="GCSバケット名（--source gcs 時に使用）",
    )
    parser.add_argument(
        "--project",
        default="invertible-vine-477701-j8",
        help="GCPプロジェクトID",
    )
    parser.add_argument(
        "--dataset",
        default="tenhou_raw",
        help="BigQueryデータセット名",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="パースのみ実行しBigQueryにはロードしない",
    )

    args = parser.parse_args()

    if args.source == "gcs":
        _load_from_gcs(args)
    else:
        _load_from_local(args)


def _load_from_local(args: argparse.Namespace) -> None:
    """ローカルファイルからBigQueryにロード。"""
    if not args.paths:
        print("Error: paths required for local source.", file=sys.stderr)
        sys.exit(1)

    files = _collect_mjlog_files(args.paths)
    if not files:
        print("No mjlog files found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(files)} mjlog file(s)")

    for filepath in files:
        game = parse_mjlog(filepath)
        my_player = game.players[game.my_seat]
        print(f"  {filepath.name}: {my_player.name} (seat {game.my_seat}), "
              f"{len(game.rounds)} rounds, {game.final_points[game.my_seat]:+.1f}pt")

        if not args.dry_run:
            result = load_game_to_bigquery(
                game,
                project=args.project,
                dataset=args.dataset,
            )
            if result["raw_games"] > 0:
                print(f"    -> Loaded: {result}")
            else:
                print(f"    -> Skipped (already exists)")

    print("Done.")


def _load_from_gcs(args: argparse.Namespace) -> None:
    """GCSからBigQueryにロード。"""
    print(f"Loading from GCS bucket: {args.bucket}")

    results = load_from_gcs(
        bucket_name=args.bucket,
        project=args.project,
        dataset=args.dataset,
        dry_run=args.dry_run,
    )

    if not results:
        print("No mjlog files found in GCS.")
        return

    for r in results:
        status = r["status"]
        print(f"  {r['file']}: {r['player']}, "
              f"{r['rounds']} rounds, {r['point']:+.1f}pt -> {status}")

    loaded = sum(1 for r in results if r["status"] == "loaded")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    print(f"Done. Loaded: {loaded}, Skipped: {skipped}")


def _collect_mjlog_files(paths: list[str]) -> list[Path]:
    """パスリストからmjlogファイルを収集。"""
    files: list[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            files.extend(sorted(path.glob("*.mjlog")))
        elif path.is_file() and path.suffix == ".mjlog":
            files.append(path)
        else:
            print(f"Skipping: {p}", file=sys.stderr)
    return files


if __name__ == "__main__":
    main_load()
