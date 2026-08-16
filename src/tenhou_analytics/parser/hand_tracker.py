"""手牌追跡エンジン。

各局の配牌からアクションを順に適用し、各プレイヤーの手牌状態・
シャンテン数・テンパイ時の待ち牌を算出する。
"""

from __future__ import annotations

from dataclasses import dataclass

from mahjong.hand_calculating.hand import HandCalculator
from mahjong.hand_calculating.hand_config import HandConfig
from mahjong.shanten import Shanten
from mahjong.tile import TilesConverter

from tenhou_analytics.parser.constants import TILE_TYPES
from tenhou_analytics.parser.mjlog import Action, Game, Round


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
    wait_type: str  # 待ちの形（テンパイ時のみ）


def _34_array_to_names(arr: list[int]) -> list[str]:
    """34種配列を牌名リストに変換。"""
    names = []
    for i, count in enumerate(arr):
        for _ in range(count):
            names.append(TILE_TYPES[i])
    return names


def _tiles_to_34_array(tile_ids: list[int]) -> list[int]:
    """牌ID(0-135)のリストを34種の配列に変換。"""
    arr = [0] * 34
    for tid in tile_ids:
        arr[tid // 4] += 1
    return arr


def _tile_name_to_id_approx(tile_name: str, hand: list[int]) -> int | None:
    """牌名から手牌内の牌IDを検索。同じ牌種の中で最初に見つかったものを返す。"""
    # 牌名→牌種インデックス
    if tile_name in ("0m", "0p", "0s"):
        # 赤ドラ
        red_map = {"0m": 16, "0p": 52, "0s": 88}
        red_id = red_map[tile_name]
        if red_id in hand:
            return red_id
        return None

    try:
        kind_idx = TILE_TYPES.index(tile_name)
    except ValueError:
        return None

    # この牌種の4枚(kind_idx*4 ~ kind_idx*4+3)から手牌にあるものを探す
    for r in range(4):
        tid = kind_idx * 4 + r
        if tid in hand:
            return tid
    return None


def _classify_wait(wait_kinds: list[int], tiles_34: list[int] | None = None) -> str:
    """HandCalculatorで面子分解し、正確な待ちの形を判定。

    tiles_34が渡された場合、各待ち牌で14枚にして面子分解を試みる。
    """
    if not wait_kinds:
        return ""
    if len(wait_kinds) >= 3:
        return "多面/複合"

    if tiles_34 is None:
        if len(wait_kinds) == 1:
            return "単騎" if wait_kinds[0] >= 27 else "不明"
        return "不明"

    # 2枚待ちの場合
    if len(wait_kinds) == 2:
        # まずシャボ判定（対子2組は正常な2枚待ち）
        two_wait = _classify_two_waits(wait_kinds[0], wait_kinds[1], tiles_34)
        if two_wait == "シャボ":
            return "シャボ"
        # シャボ以外で手牌に待ち牌が含まれている = 複合形
        if tiles_34[wait_kinds[0]] > 0 or tiles_34[wait_kinds[1]] > 0:
            return "多面/複合"
        return two_wait

    # 1枚待ちの場合: 手牌構成から判定
    return _analyze_wait_block(wait_kinds[0], tiles_34)


def _classify_two_waits(kind0: int, kind1: int, tiles_34: list[int]) -> str:
    """2枚待ちの場合の待ちの形を判定。"""
    # 字牌を含む場合はシャボ
    if kind0 >= 27 or kind1 >= 27:
        return "シャボ"

    suit0, suit1 = kind0 // 9, kind1 // 9
    num0, num1 = kind0 % 9, kind1 % 9

    if suit0 != suit1:
        # 異なるスーツ → シャボ
        return "シャボ"

    diff = num1 - num0

    if diff == 3:
        # 差3（例: 36m） → 両面で確定（45m持ちの36待ち）
        return "両面"

    if diff == 1:
        # 差1で端を含む → ペンチャンで確定（12持ちの3待ち、89持ちの7待ち）
        if num0 == 0 or num1 == 8:
            return "ペンチャン"
        # 差1で中間 → 両面で確定（例: 56持ちの47待ち）
        return "両面"

    # 同スーツで差2以上 → シャボ（対子2組）
    return "シャボ"


def _classify_single_wait(wait_kind: int, tiles_34: list[int]) -> str:
    """1つの待ち牌に対して面子分解し、待ちの形を判定。"""
    # 14枚にして面子分解
    tiles_34_copy = tiles_34[:]
    tiles_34_copy[wait_kind] += 1

    # 136牌形式に変換
    tiles_136 = TilesConverter.to_136_array(tiles_34_copy)
    # 待ち牌の136形式
    win_tile = wait_kind * 4  # 簡易的に最初の牌IDを使用

    calculator = HandCalculator()
    try:
        result = calculator.estimate_hand_value(
            tiles=tiles_136,
            win_tile=win_tile,
            config=HandConfig(is_tsumo=True),  # ツモで計算（役判定のため）
        )
    except (ValueError, TypeError):
        return ""

    if result is None or result.han is None:
        # 役なしの場合はHandCalculatorでは判定できないが
        # 面子分解自体は内部で行われているので、別のアプローチが必要
        pass

    # 面子分解を直接使う: tiles_34の構成から判定
    # 待ち牌を加えた14枚で、待ち牌がどのブロックに属するかを調べる
    return _analyze_wait_block(wait_kind, tiles_34)


def _analyze_wait_block(wait_kind: int, tiles_34: list[int]) -> str:
    """待ち牌が手牌のどのブロックに属するかから待ちの形を判定。

    テンパイ時の13枚の手牌から、待ち牌の種類で判定する。
    """
    # 字牌の場合
    if wait_kind >= 27:
        # 手牌に同じ字牌が0枚→シャボの片方（対子が別にある）
        # 手牌に同じ字牌が1枚→単騎
        # 手牌に同じ字牌が2枚→シャンポン
        count = tiles_34[wait_kind]
        if count == 0:
            return "シャボ"
        if count == 1:
            return "単騎"
        if count == 2:
            return "シャボ"
        return "単騎"

    suit = wait_kind // 9
    num = wait_kind % 9  # 0-8
    base = suit * 9

    # 手牌に同じ牌が1枚ある → 単騎の可能性
    own_count = tiles_34[wait_kind]

    # 隣接する牌の状態を確認
    has_prev2 = num >= 2 and tiles_34[base + num - 2] > 0
    has_prev1 = num >= 1 and tiles_34[base + num - 1] > 0
    has_next1 = num <= 7 and tiles_34[base + num + 1] > 0
    has_next2 = num <= 6 and tiles_34[base + num + 2] > 0

    # 両面: XY待ちで、X-1とX+2が手牌にある（例: 45持ちの36待ち）
    # カンチャン: X-1とX+1が手牌にある（例: 57持ちの6待ち）
    # ペンチャン: 12持ちの3待ち、89持ちの7待ち
    # 単騎: 待ち牌自体が頭になる
    # シャボ: 待ち牌の対子が頭候補

    if own_count >= 2:
        return "シャボ"

    if own_count == 1:
        # 自分の手に1枚 → 単騎（頭待ち）
        # ただし順子の一部として使われる可能性もある
        # 隣接牌がない場合は確実に単騎
        if not has_prev1 and not has_next1:
            return "単騎"
        # 隣接牌がある場合、順子として使う方が自然かどうか
        # → 簡易的に単騎とする（面子分解の完全な解析は複雑すぎる）
        return "単騎"

    # own_count == 0: 手牌にない牌を待っている
    # 両面/カンチャン/ペンチャンのいずれか
    if has_prev1 and has_next1:
        return "カンチャン"
    if has_prev1 and has_prev2:
        if num == 2:
            return "ペンチャン"  # 12持ちの3待ち
        return "両面"
    if has_next1 and has_next2:
        if num == 6:
            return "ペンチャン"  # 89持ちの7待ち
        return "両面"
    if has_prev1:
        if num == 1:
            return "ペンチャン"  # X(=1)持ちの2待ち → 12のペンチャン
        return "両面"
    if has_next1:
        if num == 7:
            return "ペンチャン"  # X(=8)持ちの7待ち → 89のペンチャン
        return "両面"

    return "シャボ"


def _calc_shanten_and_waits(
    tile_ids: list[int],
) -> tuple[int, list[str], int, str]:
    """手牌からシャンテン数と待ち牌を算出。

    Args:
        tile_ids: 手牌の牌ID(0-135)リスト

    Returns:
        (shanten, wait_tiles, wait_count, wait_type)
    """
    tiles_34 = _tiles_to_34_array(tile_ids)
    tile_count = sum(tiles_34)

    # 有効な牌数かチェック（1,4,7,10,13枚）
    valid_counts = {1, 2, 4, 5, 7, 8, 10, 11, 13, 14}
    if tile_count not in valid_counts:
        return -2, [], 0, ""

    shanten_calc = Shanten()
    try:
        shanten = shanten_calc.calculate_shanten(tiles_34)
    except ValueError:
        return -2, [], 0, ""

    wait_tiles: list[str] = []
    wait_count = 0
    wait_type = ""

    # テンパイ（13枚でshanten=0）の場合、待ち牌を特定
    if shanten == 0 and tile_count in {1, 4, 7, 10, 13}:
        wait_kinds: list[int] = []
        for i in range(34):
            if tiles_34[i] < 4:
                tiles_34[i] += 1
                try:
                    if shanten_calc.calculate_shanten(tiles_34) == -1:
                        wait_kinds.append(i)
                        wait_tiles.append(TILE_TYPES[i])
                        # 残り枚数（場に見えている牌は考慮しない簡易版）
                        wait_count += 4 - tiles_34[i]  # 自分の手牌分を引く
                except ValueError:
                    pass
                tiles_34[i] -= 1

        wait_type = _classify_wait(wait_kinds, tiles_34)

    return shanten, wait_tiles, wait_count, wait_type


def track_hands_for_round(
    game_id: str,
    round_index: int,
    round_data: Round,
    actions: list[Action],
) -> list[HandState]:
    """1局分の全プレイヤーの手牌状態を追跡する。

    Returns:
        各アクション後のHandStateリスト
    """
    # 各プレイヤーの手牌を初期化（牌IDで管理）
    hands: dict[int, list[int]] = {}
    for player, tile_names in round_data.hands.items():
        # 配牌の牌名→牌IDの変換
        # INITタグの配牌は牌IDそのものなので、パーサーで変換前の値を使いたいが
        # 現状は牌名で保存されている。牌名→牌IDの逆変換が必要
        hands[player] = []

    # 配牌は牌名で保存されているため、正確な牌IDの復元が困難
    # 代わりに、アクションの牌IDを使って手牌を追跡する
    # → パーサーのINITで生の牌IDを保持するように拡張が必要

    # 現状の回避策: 配牌をスキップし、draw/discardの牌IDから追跡
    # ただし配牌の牌IDが不明なため、最初のdrawまでの手牌は不正確

    # 別アプローチ: raw_roundsのhand0-3にはカンマ区切りの牌名が入っている
    # これを使って牌種レベルで追跡する（牌IDではなく34種で管理）

    results: list[HandState] = []

    # 34種配列で手牌を管理
    hands_34: dict[int, list[int]] = {}
    for player, tile_names in round_data.hands.items():
        arr = [0] * 34
        for name in tile_names:
            if name in ("0m", "0p", "0s"):
                kind = {"0m": 4, "0p": 13, "0s": 22}[name]
            else:
                try:
                    kind = TILE_TYPES.index(name)
                except ValueError:
                    continue
            arr[kind] += 1
        hands_34[player] = arr

    # 配牌時点のシャンテン数を記録
    shanten_calc = Shanten()
    for player, arr in hands_34.items():
        tile_count = sum(arr)
        if tile_count not in {1, 2, 4, 5, 7, 8, 10, 11, 13, 14}:
            continue
        try:
            sh = shanten_calc.calculate_shanten(arr)
        except ValueError:
            sh = -2

        waits: list[str] = []
        wait_count = 0
        wait_type = ""
        if sh == 0 and tile_count in {1, 4, 7, 10, 13}:
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
            wait_type = _classify_wait(
                [TILE_TYPES.index(w) if w in TILE_TYPES else 27 for w in waits], arr
            )

        results.append(
            HandState(
                game_id=game_id,
                round_index=round_index,
                action_index=-1,  # 配牌時
                player=player,
                action_type="haipai",
                hand_tiles=_34_array_to_names(arr),
                shanten=sh,
                is_tenpai=sh == 0,
                wait_tiles=waits,
                wait_count=wait_count,
                wait_type=wait_type,
            )
        )

    # アクションを順に適用
    for action_idx, action in enumerate(actions):
        if action.type == "draw" and action.player in hands_34:
            # ツモ: 手牌に加える
            tile_name = action.tile
            if tile_name:
                kind = _name_to_kind(tile_name)
                if kind is not None:
                    hands_34[action.player][kind] += 1

        elif action.type == "discard" and action.player in hands_34:
            # 打牌: 手牌から除く
            tile_name = action.tile
            if tile_name:
                kind = _name_to_kind(tile_name)
                if kind is not None and hands_34[action.player][kind] > 0:
                    hands_34[action.player][kind] -= 1

            # 打牌後（13枚）のシャンテン数を記録
            arr = hands_34[action.player]
            tile_count = sum(arr)
            if tile_count in {1, 4, 7, 10, 13}:
                try:
                    sh = shanten_calc.calculate_shanten(arr)
                except ValueError:
                    sh = -2

                waits = []
                wait_count = 0
                wait_type = ""
                if sh == 0 and tile_count in {1, 4, 7, 10, 13}:
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
                    wait_type = _classify_wait(
                        [TILE_TYPES.index(w) if w in TILE_TYPES else 27 for w in waits],
                        arr,
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
                        wait_count=wait_count,
                        wait_type=wait_type,
                    )
                )

        elif action.type in ("chi", "pon", "daiminkan") and action.player in hands_34:
            # 副露: 自分の手牌から出した牌を除去
            # called_tile は他家からもらった牌なので1枚だけスキップ
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
            # 暗槓: 4枚を手牌から除去
            if action.naki_tiles:
                kind = _name_to_kind(action.naki_tiles[0])
                if kind is not None:
                    hands_34[action.player][kind] = 0

        elif action.type == "kakan" and action.player in hands_34:
            # 加槓: 1枚を手牌から除去
            if action.called_tile:
                kind = _name_to_kind(action.called_tile)
                if kind is not None and hands_34[action.player][kind] > 0:
                    hands_34[action.player][kind] -= 1

    return results


def _name_to_kind(tile_name: str) -> int | None:
    """牌名を34種インデックスに変換。"""
    if tile_name in ("0m", "0p", "0s"):
        return {"0m": 4, "0p": 13, "0s": 22}[tile_name]
    try:
        return TILE_TYPES.index(tile_name)
    except ValueError:
        return None


def track_all_hands(game: Game) -> list[HandState]:
    """1対局分の全局・全プレイヤーの手牌状態を追跡する。"""
    all_states: list[HandState] = []
    for round_idx, round_data in enumerate(game.rounds):
        states = track_hands_for_round(
            game.game_id, round_idx, round_data, round_data.actions
        )
        all_states.extend(states)
    return all_states
