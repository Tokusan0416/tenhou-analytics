-- 対局結果一覧（自分の対局のみ）
-- Streamlitでの対局履歴表示や順位推移グラフに使用
SELECT
    g.game_id
    ,g.game_date
    ,g.game_date_jst
    ,g.game_hour
    ,g.game_order
    ,g.player_name
    ,g.final_rank
    ,g.final_score
    ,g.final_point
    ,g.is_tonnansen
    ,g.lobby
    ,g.num_rounds
    -- 同卓者情報
    ,o1.player_name AS opponent1_name
    ,o1.final_rank AS opponent1_rank
    ,o2.player_name AS opponent2_name
    ,o2.final_rank AS opponent2_rank
    ,o3.player_name AS opponent3_name
    ,o3.final_rank AS opponent3_rank
    -- 累積ポイント（対局順に累積）
    ,SUM(g.final_point) OVER (
        ORDER BY g.game_id
        ROWS UNBOUNDED PRECEDING
    ) AS cumulative_point
FROM
    {{ ref('fct_games') }} AS g
    LEFT JOIN {{ ref('fct_games') }} AS o1 ON g.game_id = o1.game_id AND o1.seat = MOD(g.seat + 1, 4)
    LEFT JOIN {{ ref('fct_games') }} AS o2 ON g.game_id = o2.game_id AND o2.seat = MOD(g.seat + 2, 4)
    LEFT JOIN {{ ref('fct_games') }} AS o3 ON g.game_id = o3.game_id AND o3.seat = MOD(g.seat + 3, 4)
WHERE
    g.is_me
