-- 対局結果一覧（自分の対局のみ）
-- Streamlitでの対局履歴表示や順位推移グラフに使用
WITH
    -- 対局ごとの局単位集計
    game_round_agg AS (
        SELECT
            game_id
            ,COUNTIF(is_agari) AS agari_count
            ,COUNTIF(is_houjuu) AS houjuu_count
            ,COUNTIF(is_reach) AS reach_count
            ,COUNTIF(is_naki) AS naki_count
            ,COUNTIF(is_hi_tsumo) AS hi_tsumo_count
            ,COUNT(*) AS round_count
        FROM
            {{ ref('fct_round_player_stats') }}
        WHERE
            is_me
        GROUP BY
            game_id
    )

SELECT
    g.game_id
    ,g.game_date
    ,g.game_date_jst
    ,g.game_hour
    ,g.game_order
    ,g.player_name
    ,g.seat
    ,g.dan
    ,g.rate
    ,g.final_rank
    ,g.final_score
    ,g.final_point
    ,g.is_tonnansen
    ,g.lobby
    ,g.num_rounds
    -- 局単位の集計
    ,ra.agari_count
    ,ra.houjuu_count
    ,ra.reach_count
    ,ra.naki_count
    ,ra.hi_tsumo_count
    -- 同卓者情報
    ,o1.player_name AS opponent1_name
    ,o1.dan AS opponent1_dan
    ,o1.rate AS opponent1_rate
    ,o1.final_rank AS opponent1_rank
    ,o2.player_name AS opponent2_name
    ,o2.dan AS opponent2_dan
    ,o2.rate AS opponent2_rate
    ,o2.final_rank AS opponent2_rank
    ,o3.player_name AS opponent3_name
    ,o3.dan AS opponent3_dan
    ,o3.rate AS opponent3_rate
    ,o3.final_rank AS opponent3_rank
    -- 累積ポイント（対局順に累積）
    ,SUM(g.final_point) OVER (
        ORDER BY g.game_order
        ROWS UNBOUNDED PRECEDING
    ) AS cumulative_point
FROM
    {{ ref('fct_games') }} AS g
    LEFT JOIN game_round_agg AS ra ON g.game_id = ra.game_id
    LEFT JOIN {{ ref('fct_games') }} AS o1 ON g.game_id = o1.game_id AND o1.seat = MOD(g.seat + 1, 4)
    LEFT JOIN {{ ref('fct_games') }} AS o2 ON g.game_id = o2.game_id AND o2.seat = MOD(g.seat + 2, 4)
    LEFT JOIN {{ ref('fct_games') }} AS o3 ON g.game_id = o3.game_id AND o3.seat = MOD(g.seat + 3, 4)
WHERE
    g.is_me
