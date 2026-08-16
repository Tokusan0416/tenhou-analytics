"""手牌追跡エンジン。

各局の配牌からアクションを順に適用し、各プレイヤーの手牌状態・
シャンテン数を算出する。
"""

from __future__ import annotations

from dataclasses import dataclass

from mahjong.shanten import Shanten

from tenhou_analytics.parser.constants import TILE_TYPES
from tenhou_analytics.parser.mjlog import Game, Round


@dataclass
class HandState:
    """ある巡目でのプレイヤーの手牌状態。"""

    game_id: str
    round_index: int
    action_index: int
    player: int
    action_type: str  # このアクション後の状態
    hand_tiles: list[str]  # 手牌の牌名リスト
    shanten: int  # シャンテン数（-1=和了, 0=テンパイ, 1=イーシャンテン...）
    is_tenpai: bool
    wait_tiles: list[str]  # 待ち牌名リスト（テンパイ時のみ）
    wait_count: int  # 待ち枚数


def _34_array_to_names(arr: list[int]) -> list[str]:
    """34種配列を牌名リストに変換。"""
    names = []
    for i, count in enumerate(arr):
        for _ in range(count):
            names.append(TILE_TYPES[i])
    return names


def _name_to_kind(tile_name: str) -> int | None:
    """牌名を34種インデックスに変換。"""
    if tile_name in ("0m", "0p", "0s"):
        return {"0m": 4, "0p": 13, "0s": 22}[tile_name]
    try:
        return TILE_TYPES.index(tile_name)
    except ValueError:
        return None


def _calc_waits(
    arr: list[int], shanten: int, tile_count: int, shanten_calc: Shanten
) -> tuple[list[str], int]:
    """テンパイ時の待ち牌と枚数を算出。"""
    if shanten != 0 or tile_count not in {1, 4, 7, 10, 13}:
        return [], 0
    waits: list[str] = []
    wait_count = 0
    for i in range(34):
        if arr[i] < 4:
            arr[i] += 1
            try:
                if shanten_calc.calculate_shanten(arr) == -1:
                    waits.append(TILE_TYPES[i])
                    wait_count += 4 - arr[i]
            except ValueError:
                pass
            arr[i] -= 1
    return waits, wait_count


def track_hands_for_round(
    game_id: str,
    round_index: int,
    round_data: Round,
) -> list[HandState]:
    """1局分の全プレイヤーの手牌状態を追跡する。"""
    results: list[HandState] = []
    shanten_calc = Shanten()

    # 34種配列で手牌を管理
    hands_34: dict[int, list[int]] = {}
    for player, tile_names in round_data.hands.items():
        arr = [0] * 34
        for name in tile_names:
            kind = _name_to_kind(name)
            if kind is not None:
                arr[kind] += 1
        hands_34[player] = arr

    # 配牌時点のシャンテン数を記録
    for player, arr in hands_34.items():
        tile_count = sum(arr)
        if tile_count not in {1, 2, 4, 5, 7, 8, 10, 11, 13, 14}:
            continue
        try:
            sh = shanten_calc.calculate_shanten(arr)
        except ValueError:
            sh = -2

        waits, wcount = _calc_waits(arr, sh, tile_count, shanten_calc)
        results.append(
            HandState(
                game_id=game_id,
                round_index=round_index,
                action_index=-1,
                player=player,
                action_type="haipai",
                hand_tiles=_34_array_to_names(arr),
                shanten=sh,
                is_tenpai=sh == 0,
                wait_tiles=waits,
                wait_count=wcount,
            )
        )

    # アクションを順に適用
    for action_idx, action in enumerate(round_data.actions):
        if action.type == "draw" and action.player in hands_34:
            tile_name = action.tile
            if tile_name:
                kind = _name_to_kind(tile_name)
                if kind is not None:
                    hands_34[action.player][kind] += 1

        elif action.type == "discard" and action.player in hands_34:
            tile_name = action.tile
            if tile_name:
                kind = _name_to_kind(tile_name)
                if kind is not None and hands_34[action.player][kind] > 0:
                    hands_34[action.player][kind] -= 1

            # 打牌後のシャンテン数を記録
            arr = hands_34[action.player]
            tile_count = sum(arr)
            if tile_count in {1, 4, 7, 10, 13}:
                try:
                    sh = shanten_calc.calculate_shanten(arr)
                except ValueError:
                    sh = -2

                waits, wcount = _calc_waits(arr, sh, tile_count, shanten_calc)
                results.append(
                    HandState(
                        game_id=game_id,
                        round_index=round_index,
                        action_index=action_idx,
                        player=action.player,
                        action_type="discard",
                        hand_tiles=_34_array_to_names(arr),
                        shanten=sh,
                        is_tenpai=sh == 0,
                        wait_tiles=waits,
                        wait_count=wcount,
                    )
                )

        elif action.type in ("chi", "pon", "daiminkan") and action.player in hands_34:
            # 副露: 自分の手牌から出した牌を除去
            if action.naki_tiles:
                skipped_called = False
                for nt in action.naki_tiles:
                    kind = _name_to_kind(nt)
                    if kind is not None:
                        if not skipped_called and nt == action.called_tile:
                            skipped_called = True
                            continue
                        if hands_34[action.player][kind] > 0:
                            hands_34[action.player][kind] -= 1

        elif action.type == "ankan" and action.player in hands_34:
            if action.naki_tiles:
                kind = _name_to_kind(action.naki_tiles[0])
                if kind is not None:
                    hands_34[action.player][kind] = 0

        elif action.type == "kakan" and action.player in hands_34:
            if action.called_tile:
                kind = _name_to_kind(action.called_tile)
                if kind is not None and hands_34[action.player][kind] > 0:
                    hands_34[action.player][kind] -= 1

    return results


def track_all_hands(game: Game) -> list[HandState]:
    """1対局分の全局・全プレイヤーの手牌状態を追跡する。"""
    all_states: list[HandState] = []
    for round_idx, round_data in enumerate(game.rounds):
        states = track_hands_for_round(game.game_id, round_idx, round_data)
        all_states.extend(states)
    return all_states
