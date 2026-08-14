"""mjlogファイルのパーサー。

gzip圧縮されたXMLを解凍・パースし、対局データを構造化して返す。
"""

from __future__ import annotations

import gzip
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from tenhou_analytics.parser.constants import (
    YAKU_NAMES,
    parse_game_type,
    tile_id_to_name,
)

# プレイヤー番号に対応するツモ/打牌タグ
DRAW_TAGS = {0: "T", 1: "U", 2: "V", 3: "W"}
DISCARD_TAGS = {0: "D", 1: "E", 2: "F", 3: "G"}


@dataclass
class PlayerInfo:
    """プレイヤー情報。"""

    seat: int  # 席番号(0-3)
    name: str
    dan: int  # 段位
    rate: float
    sex: str


@dataclass
class Yaku:
    """役情報。"""

    id: int
    name: str
    han: int


@dataclass
class AgariResult:
    """和了結果。"""

    winner: int  # 和了者の席番号
    from_who: int  # 放銃者（ツモの場合は winner と同じ）
    is_tsumo: bool
    hand: list[str]  # 手牌（牌名リスト）
    winning_tile: str  # 和了牌
    yaku: list[Yaku]
    han: int  # 合計翻数
    ten: int  # 点数
    fu: int  # 符
    score_changes: list[int]  # 各プレイヤーの点数変動
    dora: list[str]
    ura_dora: list[str]


@dataclass
class RyuukyokuResult:
    """流局結果。"""

    reason: str | None  # 流局理由（None=通常流局）
    score_changes: list[int]
    tenpai_players: list[int]  # テンパイだったプレイヤー


@dataclass
class Action:
    """巡目内のアクション。"""

    type: str  # "draw", "discard", "chi", "pon", "kan", "reach"
    player: int  # 席番号
    tile: str | None  # 牌名（鳴きの場合はNone）
    turn: int  # 巡目


@dataclass
class Round:
    """局のデータ。"""

    round_number: int  # 局番号(0=東1局, 1=東2局, ..., 4=南1局, ...)
    honba: int  # 本場
    riichi_sticks: int  # リーチ棒
    dora_indicator: str  # ドラ表示牌
    starting_scores: list[int]  # 各プレイヤーの開始点数(百点単位)
    dealer: int  # 親の席番号
    hands: dict[int, list[str]]  # 各プレイヤーの配牌
    actions: list[Action]
    result: AgariResult | RyuukyokuResult | None
    reach_players: list[int]  # リーチしたプレイヤー


@dataclass
class Game:
    """対局全体のデータ。"""

    game_id: str  # ファイル名から抽出
    game_date: datetime | None  # 対局日時（ファイル名から抽出、時まで）
    game_type: dict  # ゲーム種別情報
    players: list[PlayerInfo]
    rounds: list[Round]
    final_scores: list[int]  # 最終点数(百点単位)
    final_points: list[float]  # 最終ポイント(ウマオカ込み)
    my_seat: int  # tw= から取得した自分の席番号


def _parse_tile_list(csv: str) -> list[str]:
    """カンマ区切りの牌IDリストを牌名リストに変換。"""
    if not csv:
        return []
    return [tile_id_to_name(int(t)) for t in csv.split(",")]


def _parse_int_list(csv: str) -> list[int]:
    """カンマ区切りの整数リストをパース。"""
    if not csv:
        return []
    return [int(x) for x in csv.split(",")]


def _parse_yaku(yaku_csv: str) -> list[Yaku]:
    """役情報のCSVをパース。(役番号,翻数) のペアが並ぶ。"""
    values = _parse_int_list(yaku_csv)
    result = []
    for i in range(0, len(values), 2):
        yaku_id = values[i]
        han = values[i + 1]
        result.append(
            Yaku(
                id=yaku_id,
                name=YAKU_NAMES.get(yaku_id, f"不明({yaku_id})"),
                han=han,
            )
        )
    return result


def _decode_naki_type(m_value: int) -> str:
    """鳴きのm属性値から鳴きの種類を判定。"""
    if m_value & 0x0004:
        return "chi"
    if m_value & 0x0008:
        return "pon"
    if m_value & 0x0010:
        return "kakan"
    if m_value & 0x0020:
        # 北抜きの可能性もあるが四麻では通常なし
        return "nuki"
    # 暗槓 or 大明槓: kui(下位2bit)が0なら暗槓、1-3なら大明槓
    kui = m_value & 0x0003
    if kui == 0:
        return "ankan"
    return "daiminkan"


def _extract_game_id(filepath: Path) -> str:
    """ファイルパスからゲームIDを抽出。"""
    name = filepath.stem  # &tw=0 を含むstem
    # &tw= 以降を除去
    game_id = name.split("&")[0]
    return game_id


def _extract_game_date(game_id: str) -> datetime | None:
    """ゲームIDから対局日時を抽出。YYYYMMDDHHの10桁から日時を取得。"""
    match = re.match(r"(\d{10})", game_id)
    if match:
        date_str = match.group(1)
        return datetime.strptime(date_str, "%Y%m%d%H")  # noqa: DTZ007
    return None


def _extract_my_seat(filepath: Path) -> int:
    """ファイル名のtw=パラメータから自分の席番号を取得。"""
    name = filepath.name
    match = re.search(r"tw=(\d)", name)
    if match:
        return int(match.group(1))
    return 0


def parse_mjlog(filepath: str | Path) -> Game:
    """mjlogファイルをパースしてGameオブジェクトを返す。

    Args:
        filepath: mjlogファイルのパス

    Returns:
        Game: パース結果の対局データ
    """
    filepath = Path(filepath)

    # gzip解凍してXMLを取得
    with open(filepath, "rb") as f:
        xml_bytes = gzip.decompress(f.read())
    xml_str = xml_bytes.decode("utf-8")

    # XMLをパース（mjlogは正式なXMLではないので要素を個別にパース）
    root = ET.fromstring(xml_str)

    game_id = _extract_game_id(filepath)
    game_date = _extract_game_date(game_id)
    my_seat = _extract_my_seat(filepath)

    # ゲーム種別
    go_elem = root.find("GO")
    game_type = (
        parse_game_type(int(go_elem.get("type", "0"))) if go_elem is not None else {}
    )

    # プレイヤー情報
    un_elem = root.find("UN")
    players = _parse_players(un_elem)

    # 局のパース
    rounds: list[Round] = []
    current_round: Round | None = None

    for elem in root:
        tag = elem.tag

        if tag == "INIT":
            current_round = _parse_init(elem)
            rounds.append(current_round)
            continue

        if current_round is None:
            continue

        # ツモ（T0-T135, U0-U135, V0-V135, W0-W135）
        for player, draw_tag in DRAW_TAGS.items():
            if tag.startswith(draw_tag) and tag[1:].isdigit():
                tile_id = int(tag[1:])
                turn = sum(
                    1
                    for a in current_round.actions
                    if a.type == "draw" and a.player == player
                )
                current_round.actions.append(
                    Action(
                        type="draw",
                        player=player,
                        tile=tile_id_to_name(tile_id),
                        turn=turn,
                    )
                )
                break

        # 打牌（D0-D135, E0-E135, F0-F135, G0-G135）
        for player, discard_tag in DISCARD_TAGS.items():
            if tag.startswith(discard_tag) and tag[1:].isdigit():
                tile_id = int(tag[1:])
                turn = sum(
                    1
                    for a in current_round.actions
                    if a.type == "discard" and a.player == player
                )
                current_round.actions.append(
                    Action(
                        type="discard",
                        player=player,
                        tile=tile_id_to_name(tile_id),
                        turn=turn,
                    )
                )
                break

        # 鳴き
        if tag == "N":
            who = int(elem.get("who", "0"))
            m_value = int(elem.get("m", "0"))
            naki_type = _decode_naki_type(m_value)
            current_round.actions.append(
                Action(
                    type=naki_type,
                    player=who,
                    tile=None,
                    turn=0,
                )
            )

        # リーチ
        if tag == "REACH":
            step = int(elem.get("step", "0"))
            who = int(elem.get("who", "0"))
            if step == 1:
                current_round.reach_players.append(who)
                current_round.actions.append(
                    Action(
                        type="reach",
                        player=who,
                        tile=None,
                        turn=0,
                    )
                )

        # 和了
        if tag == "AGARI":
            current_round.result = _parse_agari(elem)

        # 流局
        if tag == "RYUUKYOKU":
            current_round.result = _parse_ryuukyoku(elem)

    # 最終結果
    final_scores, final_points = _parse_owari(root)

    return Game(
        game_id=game_id,
        game_date=game_date,
        game_type=game_type,
        players=players,
        rounds=rounds,
        final_scores=final_scores,
        final_points=final_points,
        my_seat=my_seat,
    )


def _parse_players(un_elem: ET.Element | None) -> list[PlayerInfo]:
    """UNタグからプレイヤー情報をパース。"""
    if un_elem is None:
        return []

    dans = _parse_int_list(un_elem.get("dan", ""))
    rates = [float(r) for r in un_elem.get("rate", "").split(",")]
    sexes = un_elem.get("sx", "").split(",")

    players = []
    for i in range(4):
        name_encoded = un_elem.get(f"n{i}", "")
        name = unquote(name_encoded)
        players.append(
            PlayerInfo(
                seat=i,
                name=name,
                dan=dans[i] if i < len(dans) else 0,
                rate=rates[i] if i < len(rates) else 0.0,
                sex=sexes[i] if i < len(sexes) else "",
            )
        )

    return players


def _parse_init(elem: ET.Element) -> Round:
    """INITタグをパースしてRoundオブジェクトを生成。"""
    seed = _parse_int_list(elem.get("seed", ""))
    ten = _parse_int_list(elem.get("ten", ""))
    oya = int(elem.get("oya", "0"))

    # seed: [局番号, 本場, リーチ棒, サイコロ1, サイコロ2, ドラ表示牌]
    round_number = seed[0] if len(seed) > 0 else 0
    honba = seed[1] if len(seed) > 1 else 0
    riichi_sticks = seed[2] if len(seed) > 2 else 0
    dora_indicator_id = seed[5] if len(seed) > 5 else 0

    hands: dict[int, list[str]] = {}
    for i in range(4):
        hai_csv = elem.get(f"hai{i}", "")
        if hai_csv:
            hands[i] = _parse_tile_list(hai_csv)

    return Round(
        round_number=round_number,
        honba=honba,
        riichi_sticks=riichi_sticks,
        dora_indicator=tile_id_to_name(dora_indicator_id),
        starting_scores=ten,
        dealer=oya,
        hands=hands,
        actions=[],
        result=None,
        reach_players=[],
    )


def _parse_agari(elem: ET.Element) -> AgariResult:
    """AGARIタグをパース。"""
    who = int(elem.get("who", "0"))
    from_who = int(elem.get("fromWho", "0"))
    hand = _parse_tile_list(elem.get("hai", ""))
    machi_id = int(elem.get("machi", "0"))
    winning_tile = tile_id_to_name(machi_id)

    ten_values = _parse_int_list(elem.get("ten", ""))
    fu = ten_values[0] if len(ten_values) > 0 else 0
    score = ten_values[1] if len(ten_values) > 1 else 0

    yaku_list = _parse_yaku(elem.get("yaku", ""))
    total_han = sum(y.han for y in yaku_list)

    sc = _parse_int_list(elem.get("sc", ""))
    score_changes = [sc[i * 2 + 1] for i in range(4)] if len(sc) >= 8 else []

    dora = _parse_tile_list(elem.get("doraHai", ""))
    ura_dora = _parse_tile_list(elem.get("doraHaiUra", ""))

    return AgariResult(
        winner=who,
        from_who=from_who,
        is_tsumo=who == from_who,
        hand=hand,
        winning_tile=winning_tile,
        yaku=yaku_list,
        han=total_han,
        ten=score,
        fu=fu,
        score_changes=score_changes,
        dora=dora,
        ura_dora=ura_dora,
    )


def _parse_ryuukyoku(elem: ET.Element) -> RyuukyokuResult:
    """RYUUKYOKUタグをパース。"""
    sc = _parse_int_list(elem.get("sc", ""))
    score_changes = [sc[i * 2 + 1] for i in range(4)] if len(sc) >= 8 else []

    reason = elem.get("type")  # "yao9", "reach4", "ron3", "kan4", "kaze4", "nm" など

    # テンパイ者: hai属性が存在するプレイヤー
    tenpai_players = []
    for i in range(4):
        if elem.get(f"hai{i}") is not None:
            tenpai_players.append(i)

    return RyuukyokuResult(
        reason=reason,
        score_changes=score_changes,
        tenpai_players=tenpai_players,
    )


def _parse_owari(root: ET.Element) -> tuple[list[int], list[float]]:
    """最終結果(owari属性)をパース。最後のAGARIまたはRYUUKYOKUから取得。"""
    owari_str = ""
    for elem in root:
        if elem.tag in ("AGARI", "RYUUKYOKU"):
            o = elem.get("owari")
            if o:
                owari_str = o

    if not owari_str:
        return [], []

    values = owari_str.split(",")
    scores = [int(values[i * 2]) for i in range(4)]
    points = [float(values[i * 2 + 1]) for i in range(4)]
    return scores, points
