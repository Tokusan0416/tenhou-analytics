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
            ,g.lobby
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

    -- 他家のリーチ数を局単位で集計
    ,opponents_reach AS (
        SELECT
            rp.game_id
            ,rp.round_index
            ,rp.player_seat
            ,COUNT(reach_other.player) AS opponents_reach_count
        FROM
            round_players AS rp
            LEFT JOIN {{ ref('int_round_reach_order') }} AS reach_other
                ON rp.game_id = reach_other.game_id
                AND rp.round_index = reach_other.round_index
                AND reach_other.player != rp.player_seat
        GROUP BY
            rp.game_id
            ,rp.round_index
            ,rp.player_seat
    )

    -- 他家の副露数を局単位で集計
    ,opponents_naki AS (
        SELECT
            rp.game_id
            ,rp.round_index
            ,rp.player_seat
            ,COUNT(naki_other.player) AS opponents_naki_count
        FROM
            round_players AS rp
            LEFT JOIN {{ ref('int_round_naki_flags') }} AS naki_other
                ON rp.game_id = naki_other.game_id
                AND rp.round_index = naki_other.round_index
                AND naki_other.player != rp.player_seat
        GROUP BY
            rp.game_id
            ,rp.round_index
            ,rp.player_seat
    )

    ,base AS (
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
            ,rp.lobby
            ,rp.result_type

            -- アガリ
            ,COALESCE(r.agari_winner = rp.player_seat, FALSE) AS is_agari
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
            ,COALESCE(r.result_type = 'agari' AND r.agari_from_who = rp.player_seat AND r.agari_winner != rp.player_seat, FALSE) AS is_houjuu
            ,CASE
                WHEN r.result_type = 'agari' AND r.agari_from_who = rp.player_seat AND r.agari_winner != rp.player_seat THEN r.agari_ten
            END AS houjuu_ten
            ,CASE
                WHEN r.result_type = 'agari' AND r.agari_from_who = rp.player_seat AND r.agari_winner != rp.player_seat THEN agt_winner.agari_turn
            END AS houjuu_turn
            ,CASE
                WHEN r.result_type = 'agari' AND r.agari_from_who = rp.player_seat AND r.agari_winner != rp.player_seat THEN r.agari_han
            END AS houjuu_han

            -- 被ツモ（他家ツモで失点、自分は放銃者ではない）
            ,COALESCE(r.result_type = 'agari'
                AND r.agari_is_tsumo
                AND r.agari_winner != rp.player_seat, FALSE) AS is_hi_tsumo
            ,CASE
                WHEN r.result_type = 'agari' AND r.agari_is_tsumo AND r.agari_winner != rp.player_seat
                THEN ABS(sc.score_change)
            END AS hi_tsumo_ten

            -- 横移動（他家間のロンで自分は無関係）
            ,COALESCE(r.result_type = 'agari'
                AND NOT r.agari_is_tsumo
                AND r.agari_winner != rp.player_seat
                AND r.agari_from_who != rp.player_seat, FALSE) AS is_yoko_ido

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
            LEFT JOIN {{ ref('int_round_agari_turn') }} AS agt_winner ON rp.game_id = agt_winner.game_id AND rp.round_index = agt_winner.round_index AND r.agari_winner = agt_winner.player
            INNER JOIN score_changes AS sc ON rp.game_id = sc.game_id AND rp.round_index = sc.round_index AND rp.player_seat = sc.seat
            INNER JOIN starting_ranks AS sr ON rp.game_id = sr.game_id AND rp.round_index = sr.round_index AND rp.player_seat = sr.seat
    )

    -- 放銃先（和了者）のリーチ/副露状態を取得
    ,winner_status AS (
        SELECT
            b.game_id
            ,b.round_index
            ,r.agari_winner AS winner_seat
            ,COALESCE(w_reach.player IS NOT NULL, FALSE) AS winner_is_reach
            ,COALESCE(w_naki.is_naki, FALSE) AS winner_is_naki
        FROM
            base AS b
            INNER JOIN {{ ref('fct_rounds') }} AS r
                ON b.game_id = r.game_id AND b.round_index = r.round_index
            LEFT JOIN {{ ref('int_round_reach_order') }} AS w_reach
                ON b.game_id = w_reach.game_id AND b.round_index = w_reach.round_index AND r.agari_winner = w_reach.player
            LEFT JOIN {{ ref('int_round_naki_flags') }} AS w_naki
                ON b.game_id = w_naki.game_id AND b.round_index = w_naki.round_index AND r.agari_winner = w_naki.player
        WHERE
            r.result_type = 'agari'
            AND NOT r.agari_is_tsumo
        GROUP BY
            b.game_id
            ,b.round_index
            ,r.agari_winner
            ,w_reach.player
            ,w_naki.is_naki
    )

SELECT
    b.*

    -- 局ディメンション
    ,dr.round_label
    ,dr.wind
    ,dr.is_ouras

    -- アガリ種別（リーチ / ダマ / 副露）
    ,CASE
        WHEN b.is_agari AND b.is_reach THEN 'リーチ'
        WHEN b.is_agari AND b.is_naki THEN '副露'
        WHEN b.is_agari THEN 'ダマ'
    END AS agari_type

    -- 放銃種別（放銃先がリーチ / 副露 / ダマ）
    ,CASE
        WHEN b.is_houjuu AND ws.winner_is_reach THEN 'リーチ'
        WHEN b.is_houjuu AND ws.winner_is_naki THEN '副露'
        WHEN b.is_houjuu THEN 'ダマ'
    END AS houjuu_to_type

    -- 他家状況
    ,COALESCE(opr.opponents_reach_count, 0) AS opponents_reach_count
    ,COALESCE(opn.opponents_naki_count, 0) AS opponents_naki_count

FROM
    base AS b
    INNER JOIN {{ ref('dim_rounds') }} AS dr ON b.round_number = dr.round_number
    LEFT JOIN winner_status AS ws
        ON b.game_id = ws.game_id
        AND b.round_index = ws.round_index
    LEFT JOIN opponents_reach AS opr
        ON b.game_id = opr.game_id
        AND b.round_index = opr.round_index
        AND b.player_seat = opr.player_seat
    LEFT JOIN opponents_naki AS opn
        ON b.game_id = opn.game_id
        AND b.round_index = opn.round_index
        AND b.player_seat = opn.player_seat
