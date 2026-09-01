"""手牌追跡エンジン。

各局の配牌からアクションを順に適用し、各プレイヤーの手牌状態・
シャンテン数・待ち牌・待ち枚数を算出する。
待ち枚数は「見た目枚数」と「山残り枚数」の2種類を提供。
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
    action_type: str
    hand_tiles: list[str]
    shanten: int
    is_tenpai: bool
    wait_tiles: list[str] = field(default_factory=list)
    wait_count: int = 0  # 山残り枚数（全員の手牌・河・副露・ドラ表示を考慮）
    wait_count_visible: int = 0  # 見た目枚数（自分の手牌・河・副露・ドラ表示のみ）


def _34_array_to_names(arr: list[int]) -> list[str]:
    names = []
    for i, count in enumerate(arr):
        for _ in range(count):
            names.append(TILE_TYPES[i])
    return names


def _name_to_kind(tile_name: str) -> int | None:
    if tile_name in ("0m", "0p", "0s"):
        return {"0m": 4, "0p": 13, "0s": 22}[tile_name]
    try:
        return TILE_TYPES.index(tile_name)
    except ValueError:
        return None


def _calc_waits(
    hand: list[int],
    all_known: list[int],
    visible: list[int],
    shanten_val: int,
    tile_count: int,
    shanten_calc: Shanten,
) -> tuple[list[str], int, int]:
    """テンパイ時の待ち牌と枚数を算出。

    Args:
        hand: 自分の手牌(34種)
        all_known: 全ての見えている牌(全員の手牌+河+副露+ドラ表示)(34種)
        visible: 自分から見える牌(自分の手牌+河+副露+ドラ表示)(34種)
        shanten_val: シャンテン数
        tile_count: 手牌枚数
        shanten_calc: Shantenインスタンス

    Returns:
        (待ち牌リスト, 山残り枚数, 見た目枚数)
    """
    if shanten_val != 0 or tile_count not in {1, 4, 7, 10, 13}:
        return [], 0, 0
    waits: list[str] = []
    wait_count = 0
    wait_count_visible = 0
    for i in range(34):
        if hand[i] < 4:
            hand[i] += 1
            try:
                if shanten_calc.calculate_shanten(hand) == -1:
                    waits.append(TILE_TYPES[i])
                    wait_count += max(0, 4 - all_known[i])
                    wait_count_visible += max(0, 4 - visible[i])
            except ValueError:
                pass
            hand[i] -= 1
    return waits, wait_count, wait_count_visible


def _build_all_known(
    hands_34: dict[int, list[int]],
    discards: list[int],
    dora_indicators: list[int],
) -> list[int]:
    """全ての見えている牌の34種配列を構築。"""
    known = [0] * 34
    # 全プレイヤーの手牌
    for arr in hands_34.values():
        for i in range(34):
            known[i] += arr[i]
    # 河（打牌された牌）
    for i in range(34):
        known[i] += discards[i]
    # ドラ表示牌
    for i in range(34):
        known[i] += dora_indicators[i]
    return known


def _build_visible(
    my_hand: list[int],
    discards: list[int],
    dora_indicators: list[int],
) -> list[int]:
    """自分から見える牌の34種配列を構築（自分の手牌+全員の河+副露+ドラ表示）。"""
    vis = [0] * 34
    for i in range(34):
        vis[i] = my_hand[i] + discards[i] + dora_indicators[i]
    return vis


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

    # 河（打牌された牌、鳴かれた牌も含む）
    discards: list[int] = [0] * 34

    # ドラ表示牌
    dora_indicators: list[int] = [0] * 34
    dora_kind = _name_to_kind(round_data.dora_indicator)
    if dora_kind is not None:
        dora_indicators[dora_kind] += 1

    # 配牌時点のシャンテン数を記録
    for player, arr in hands_34.items():
        tile_count = sum(arr)
        if tile_count not in {1, 2, 4, 5, 7, 8, 10, 11, 13, 14}:
            continue
        try:
            sh = shanten_calc.calculate_shanten(arr)
        except ValueError:
            sh = -2

        all_known = _build_all_known(hands_34, discards, dora_indicators)
        visible = _build_visible(arr, discards, dora_indicators)
        waits, wcount, wcount_vis = _calc_waits(arr, all_known, visible, sh, tile_count, shanten_calc)
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
                wait_count_visible=wcount_vis,
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
                    discards[kind] += 1

            # 打牌後のシャンテン数を記録
            arr = hands_34[action.player]
            tile_count = sum(arr)
            if tile_count in {1, 4, 7, 10, 13}:
                try:
                    sh = shanten_calc.calculate_shanten(arr)
                except ValueError:
                    sh = -2

                all_known = _build_all_known(hands_34, discards, dora_indicators)
                visible = _build_visible(arr, discards, dora_indicators)
                waits, wcount, wcount_vis = _calc_waits(
                    arr, all_known, visible, sh, tile_count, shanten_calc
                )
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
                        wait_count_visible=wcount_vis,
                    )
                )

        elif action.type in ("chi", "pon", "daiminkan") and action.player in hands_34:
            # 副露: 自分の手牌から出した牌を除去
            # 鳴かれた牌は河から除去（河にあったものが副露に移る）
            if action.naki_tiles:
                skipped_called = False
                for nt in action.naki_tiles:
                    kind = _name_to_kind(nt)
                    if kind is not None:
                        if not skipped_called and nt == action.called_tile:
                            skipped_called = True
                            # 鳴かれた牌を河から除去（副露として扱われる）
                            if discards[kind] > 0:
                                discards[kind] -= 1
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

        elif action.type == "dora":
            # 槓ドラ表示牌
            if action.tile:
                kind = _name_to_kind(action.tile)
                if kind is not None:
                    dora_indicators[kind] += 1

    return results


def track_all_hands(game: Game) -> list[HandState]:
    """1対局分の全局・全プレイヤーの手牌状態を追跡する。"""
    all_states: list[HandState] = []
    for round_idx, round_data in enumerate(game.rounds):
        states = track_hands_for_round(game.game_id, round_idx, round_data)
        all_states.extend(states)
    return all_states
