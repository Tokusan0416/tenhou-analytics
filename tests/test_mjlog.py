"""mjlog パーサーのテスト。

data/ディレクトリの実ファイルを使ったテスト。
"""

from pathlib import Path

import pytest

from tenhou_analytics.parser.mjlog import (
    AgariResult,
    Game,
    RyuukyokuResult,
    parse_mjlog,
)

DATA_DIR = Path(__file__).parent.parent / "data"


def _get_mjlog_files() -> list[Path]:
    if not DATA_DIR.exists():
        return []
    return sorted(DATA_DIR.glob("*.mjlog"))


# テストデータがない環境ではスキップ
requires_data = pytest.mark.skipif(
    not _get_mjlog_files(),
    reason="No mjlog files in data/",
)


@requires_data
class TestParseMjlog:
    def test_parse_first_file(self):
        filepath = _get_mjlog_files()[0]
        game = parse_mjlog(filepath)

        assert isinstance(game, Game)
        assert game.game_id
        assert len(game.players) == 4
        assert len(game.rounds) > 0
        assert len(game.final_scores) == 4
        assert len(game.final_points) == 4

    def test_all_files_parseable(self):
        for filepath in _get_mjlog_files():
            game = parse_mjlog(filepath)
            assert isinstance(game, Game)
            assert len(game.players) == 4
            assert len(game.rounds) > 0

    def test_player_info(self):
        filepath = _get_mjlog_files()[0]
        game = parse_mjlog(filepath)

        for p in game.players:
            assert p.name  # 名前が空でない
            assert p.rate > 0
            assert p.seat in range(4)

    def test_my_seat_from_filename(self):
        """tw=パラメータから自分の席番号を正しく取得できること。"""
        for filepath in _get_mjlog_files():
            game = parse_mjlog(filepath)
            # ファイル名にtw=が含まれているか確認
            name = filepath.name
            if "tw=" in name:
                expected = int(name.split("tw=")[1].split(".")[0])
                assert game.my_seat == expected

    def test_my_name_is_consistent(self):
        """全ファイルで自分のプレイヤー名が一致すること。"""
        names = set()
        for filepath in _get_mjlog_files():
            game = parse_mjlog(filepath)
            names.add(game.players[game.my_seat].name)
        assert len(names) == 1  # 全ファイルで同一プレイヤー

    def test_round_has_result(self):
        """各局に結果（和了 or 流局）があること。"""
        filepath = _get_mjlog_files()[0]
        game = parse_mjlog(filepath)

        for r in game.rounds:
            assert r.result is not None
            assert isinstance(r.result, (AgariResult, RyuukyokuResult))

    def test_agari_result(self):
        """和了結果の属性が正しいこと。"""
        filepath = _get_mjlog_files()[0]
        game = parse_mjlog(filepath)

        agari_rounds = [r for r in game.rounds if isinstance(r.result, AgariResult)]
        assert len(agari_rounds) > 0

        for r in agari_rounds:
            result = r.result
            assert isinstance(result, AgariResult)
            assert result.winner in range(4)
            assert result.from_who in range(4)
            assert result.ten > 0
            assert result.fu > 0
            assert result.han > 0
            assert len(result.yaku) > 0
            assert len(result.hand) > 0
            assert result.winning_tile

    def test_round_actions_exist(self):
        """各局にアクションが存在すること。"""
        filepath = _get_mjlog_files()[0]
        game = parse_mjlog(filepath)

        for r in game.rounds:
            assert len(r.actions) > 0
            action_types = {a.type for a in r.actions}
            assert "draw" in action_types
            assert "discard" in action_types

    def test_final_scores_sum(self):
        """最終点数の合計が1000(百点単位)であること。"""
        for filepath in _get_mjlog_files():
            game = parse_mjlog(filepath)
            if game.final_scores:
                assert sum(game.final_scores) == 1000

    def test_game_type(self):
        """ゲーム種別が正しくパースされること。"""
        filepath = _get_mjlog_files()[0]
        game = parse_mjlog(filepath)

        assert "is_sanma" in game.game_type
        assert "is_tonnansen" in game.game_type
        assert game.game_type["is_sanma"] is False  # 四麻
