-- プレイヤー × 局 のファクトテーブル
-- 全スタッツの算出基盤となるテーブル
WITH
    -- 全プレイヤー × 全局の組み合わせを生成
    round_players AS (
        SELECT
            r.game_id
            ,r.round_index
            ,g.seat AS player_seat
            ,g.player_name
            ,g.is_me
            ,r.result_type
            ,r.dealer
            ,r.dealer = g.seat AS is_dealer
        FROM
            {{ ref('fct_rounds') }} AS r
            INNER JOIN {{ ref('fct_games') }} AS g ON r.game_id = g.game_id
    )

    -- 点数変動をプレイヤー別に取得
    ,score_changes AS (
        SELECT
            game_id
            ,round_index
            ,seat
            ,score_change
        FROM
            {{ ref('stg_rounds') }}
        CROSS JOIN UNNEST([
            STRUCT(0 AS seat, score_change0 AS score_change)
            ,STRUCT(1, score_change1)
            ,STRUCT(2, score_change2)
            ,STRUCT(3, score_change3)
        ])
    )

SELECT
    rp.game_id
    ,rp.round_index
    ,rp.player_seat
    ,rp.player_name
    ,rp.is_me
    ,rp.is_dealer
    ,rp.result_type

    -- アガリ
    ,r.agari_winner = rp.player_seat AS is_agari
    ,CASE WHEN r.agari_winner = rp.player_seat THEN r.agari_is_tsumo END AS is_tsumo
    ,CASE WHEN r.agari_winner = rp.player_seat THEN r.agari_ten END AS agari_ten
    ,CASE WHEN r.agari_winner = rp.player_seat THEN r.agari_han END AS agari_han
    ,CASE WHEN r.agari_winner = rp.player_seat THEN r.agari_fu END AS agari_fu
    ,CASE WHEN r.agari_winner = rp.player_seat THEN r.agari_yaku END AS agari_yaku
    ,CASE WHEN r.agari_winner = rp.player_seat THEN agt.agari_turn END AS agari_turn

    -- ドラ
    ,CASE WHEN r.agari_winner = rp.player_seat THEN r.agari_dora_count END AS dora_count
    ,CASE WHEN r.agari_winner = rp.player_seat THEN r.agari_ura_dora_count END AS ura_dora_count
    ,CASE WHEN r.agari_winner = rp.player_seat THEN r.agari_aka_dora_count END AS aka_dora_count

    -- 放銃
    ,r.result_type = 'agari' AND r.agari_from_who = rp.player_seat AND r.agari_winner != rp.player_seat AS is_houjuu
    ,CASE
        WHEN r.result_type = 'agari' AND r.agari_from_who = rp.player_seat AND r.agari_winner != rp.player_seat THEN r.agari_ten
    END AS houjuu_ten

    -- リーチ
    ,COALESCE(reach.player IS NOT NULL, FALSE) AS is_reach
    ,COALESCE(reach.is_first_reach, FALSE) AS is_first_reach

    -- 副露
    ,COALESCE(naki.is_naki, FALSE) AS is_naki
    ,COALESCE(naki.naki_count, 0) AS naki_count

    -- 流局テンパイ
    ,r.result_type = 'ryuukyoku'
        AND r.tenpai_players IS NOT NULL
        AND CAST(rp.player_seat AS STRING) IN UNNEST(SPLIT(r.tenpai_players, ',')) AS is_tenpai

    -- 点数変動
    ,sc.score_change

FROM
    round_players AS rp
    INNER JOIN {{ ref('fct_rounds') }} AS r ON rp.game_id = r.game_id AND rp.round_index = r.round_index
    LEFT JOIN {{ ref('int_round_reach_order') }} AS reach ON rp.game_id = reach.game_id AND rp.round_index = reach.round_index AND rp.player_seat = reach.player
    LEFT JOIN {{ ref('int_round_naki_flags') }} AS naki ON rp.game_id = naki.game_id AND rp.round_index = naki.round_index AND rp.player_seat = naki.player
    LEFT JOIN {{ ref('int_round_agari_turn') }} AS agt ON rp.game_id = agt.game_id AND rp.round_index = agt.round_index AND rp.player_seat = agt.player
    INNER JOIN score_changes AS sc ON rp.game_id = sc.game_id AND rp.round_index = sc.round_index AND rp.player_seat = sc.seat
