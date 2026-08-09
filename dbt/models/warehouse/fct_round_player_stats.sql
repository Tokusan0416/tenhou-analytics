-- プレイヤー × 局 のファクトテーブル
-- 全スタッツの算出基盤となるテーブル
WITH
    -- 全プレイヤー × 全局の組み合わせを生成
    round_players AS (
        SELECT
            r.game_id
            ,r.round_index
            ,r.round_number
            ,r.honba
            ,r.riichi_sticks
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

    -- 局開始時の各プレイヤーの順位・トップとの点差
    ,starting_ranks AS (
        SELECT
            game_id
            ,round_index
            ,seat
            ,starting_score
            ,RANK() OVER (
                PARTITION BY game_id, round_index
                ORDER BY starting_score DESC
            ) AS rank_at_start
            ,MAX(starting_score) OVER (
                PARTITION BY game_id, round_index
            ) - starting_score AS point_diff_to_top
        FROM
            {{ ref('stg_rounds') }}
        CROSS JOIN UNNEST([
            STRUCT(0 AS seat, starting_score0 AS starting_score)
            ,STRUCT(1, starting_score1)
            ,STRUCT(2, starting_score2)
            ,STRUCT(3, starting_score3)
        ])
    )

SELECT
    rp.game_id
    ,rp.round_index
    ,rp.round_number
    ,rp.honba
    ,rp.riichi_sticks
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

    -- 被ツモ（他家ツモで失点、自分は放銃者ではない）
    ,r.result_type = 'agari'
        AND r.agari_is_tsumo
        AND r.agari_winner != rp.player_seat AS is_hi_tsumo
    ,CASE
        WHEN r.result_type = 'agari' AND r.agari_is_tsumo AND r.agari_winner != rp.player_seat
        THEN ABS(sc.score_change)
    END AS hi_tsumo_ten

    -- 横移動（他家間のロンで自分は無関係）
    ,r.result_type = 'agari'
        AND NOT r.agari_is_tsumo
        AND r.agari_winner != rp.player_seat
        AND r.agari_from_who != rp.player_seat AS is_yoko_ido

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

    -- 順位状況（局開始時）
    ,sr.rank_at_start
    ,sr.point_diff_to_top

    -- 点数変動
    ,sc.score_change

FROM
    round_players AS rp
    INNER JOIN {{ ref('fct_rounds') }} AS r ON rp.game_id = r.game_id AND rp.round_index = r.round_index
    LEFT JOIN {{ ref('int_round_reach_order') }} AS reach ON rp.game_id = reach.game_id AND rp.round_index = reach.round_index AND rp.player_seat = reach.player
    LEFT JOIN {{ ref('int_round_naki_flags') }} AS naki ON rp.game_id = naki.game_id AND rp.round_index = naki.round_index AND rp.player_seat = naki.player
    LEFT JOIN {{ ref('int_round_agari_turn') }} AS agt ON rp.game_id = agt.game_id AND rp.round_index = agt.round_index AND rp.player_seat = agt.player
    INNER JOIN score_changes AS sc ON rp.game_id = sc.game_id AND rp.round_index = sc.round_index AND rp.player_seat = sc.seat
    INNER JOIN starting_ranks AS sr ON rp.game_id = sr.game_id AND rp.round_index = sr.round_index AND rp.player_seat = sr.seat
