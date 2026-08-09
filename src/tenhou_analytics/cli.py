"""CLIエントリポイント。

mjlogファイルをパースしてBigQueryにロードする。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tenhou_analytics.loader import load_game_to_bigquery
from tenhou_analytics.parser import parse_mjlog


def main() -> None:
    parser = argparse.ArgumentParser(
        description="天鳳mjlogファイルをパースしてBigQueryにロード",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="mjlogファイルまたはディレクトリのパス",
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

    # ファイル一覧を収集
    files: list[Path] = []
    for p in args.paths:
        path = Path(p)
        if path.is_dir():
            files.extend(sorted(path.glob("*.mjlog")))
        elif path.is_file() and path.suffix == ".mjlog":
            files.append(path)
        else:
            print(f"Skipping: {p}", file=sys.stderr)

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


if __name__ == "__main__":
    main()
