-- 対局ファクト
-- 1行 = 1対局 × 1プレイヤー
WITH
    games_unpivot AS (
        SELECT
            game_id
            ,my_seat
            ,is_sanma
            ,is_tonnansen
            ,is_soku
            ,is_no_red
            ,lobby
            ,num_rounds
            ,seat
            ,player_name
            ,dan
            ,rate
            ,final_score
            ,final_point
        FROM
            {{ ref('stg_games') }}
        CROSS JOIN UNNEST([
            STRUCT(0 AS seat, player0_name AS player_name, player0_dan AS dan, player0_rate AS rate, final_score0 AS final_score, final_point0 AS final_point)
            ,STRUCT(1, player1_name, player1_dan, player1_rate, final_score1, final_point1)
            ,STRUCT(2, player2_name, player2_dan, player2_rate, final_score2, final_point2)
            ,STRUCT(3, player3_name, player3_dan, player3_rate, final_score3, final_point3)
        ])
    )

    ,ranked AS (
        SELECT
            *
            ,RANK() OVER (
                PARTITION BY game_id
                ORDER BY final_score DESC
            ) AS final_rank
        FROM
            games_unpivot
    )

SELECT
    game_id
    ,seat
    ,player_name
    ,dan
    ,rate
    ,seat = my_seat AS is_me
    ,final_score
    ,final_point
    ,final_rank
    ,is_sanma
    ,is_tonnansen
    ,is_soku
    ,is_no_red
    ,lobby
    ,num_rounds
FROM
    ranked
