"""constants.py のテスト。"""

from tenhou_analytics.parser.constants import (
    TILE_TYPES,
    parse_game_type,
    tile_id_to_name,
)


class TestTileIdToName:
    def test_manzu(self):
        assert tile_id_to_name(0) == "1m"
        assert tile_id_to_name(3) == "1m"  # 同じ牌種の4枚
        assert tile_id_to_name(4) == "2m"
        assert tile_id_to_name(32) == "9m"
        assert tile_id_to_name(35) == "9m"

    def test_pinzu(self):
        assert tile_id_to_name(36) == "1p"
        assert tile_id_to_name(71) == "9p"

    def test_souzu(self):
        assert tile_id_to_name(72) == "1s"
        assert tile_id_to_name(107) == "9s"

    def test_jihai(self):
        assert tile_id_to_name(108) == "東"
        assert tile_id_to_name(112) == "南"
        assert tile_id_to_name(116) == "西"
        assert tile_id_to_name(120) == "北"
        assert tile_id_to_name(124) == "白"
        assert tile_id_to_name(128) == "發"
        assert tile_id_to_name(132) == "中"
        assert tile_id_to_name(135) == "中"

    def test_red_fives(self):
        assert tile_id_to_name(16) == "0m"  # 赤五萬
        assert tile_id_to_name(52) == "0p"  # 赤五筒
        assert tile_id_to_name(88) == "0s"  # 赤五索

    def test_non_red_fives(self):
        # 赤でない5の牌
        assert tile_id_to_name(17) == "5m"
        assert tile_id_to_name(53) == "5p"
        assert tile_id_to_name(89) == "5s"

    def test_tile_types_count(self):
        assert len(TILE_TYPES) == 34


class TestParseGameType:
    def test_tonnansen_houou(self):
        # type=137 = 0b10001001 = 128+8+1 → 東南戦、速なし
        result = parse_game_type(137)
        assert result["is_tonnansen"] is True
        assert result["is_sanma"] is False
        assert result["is_soku"] is False

    def test_sanma(self):
        result = parse_game_type(0x10)
        assert result["is_sanma"] is True
