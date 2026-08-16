-- 対局の正確な時系列順序を判定
-- 同一時間帯（同じgame_date）の複数試合をrateの変動方向で順序付け
-- ロジック: 前試合の順位が1-2位→rate上昇、3-4位→rate下降 が整合する並びを採用
WITH
    -- stg_gamesから自分のrate・順位を取得（fct_gamesの循環参照を避ける）
    all_players AS (
        SELECT
            game_id
            ,game_date
            ,my_seat
            ,p.seat
            ,p.rate
            ,p.final_score
            ,RANK() OVER (PARTITION BY game_id ORDER BY p.final_score DESC) AS final_rank
        FROM
            {{ ref('stg_games') }}
        CROSS JOIN UNNEST([
            STRUCT(0 AS seat, player0_rate AS rate, final_score0 AS final_score)
            ,STRUCT(1, player1_rate, final_score1)
            ,STRUCT(2, player2_rate, final_score2)
            ,STRUCT(3, player3_rate, final_score3)
        ]) AS p
    )

    ,my_games AS (
        SELECT
            game_id
            ,game_date
            ,rate
            ,final_rank
        FROM
            all_players
        WHERE
            seat = my_seat
    )

    -- 同一時間帯の試合をグルーピング
    ,with_group AS (
        SELECT
            game_id
            ,game_date
            ,rate
            ,final_rank
            ,COUNT(*) OVER (PARTITION BY game_date) AS games_in_hour
        FROM
            my_games
    )

    -- 同一時間帯に1試合の場合はそのまま、2試合の場合はrate整合性で判定
    ,ordered AS (
        SELECT
            game_id
            ,game_date
            ,rate
            ,final_rank
            ,games_in_hour
            ,CASE
                -- 同一時間帯に1試合: そのまま
                WHEN games_in_hour = 1 THEN 0
                -- 同一時間帯に2試合: rateが低い方を仮に1番目として
                -- 1番目の順位が1-2位 かつ rate差が正 → 昇順が正しい
                -- 1番目の順位が3-4位 かつ rate差が負 → 昇順が正しい
                -- それ以外 → 降順が正しい
                ELSE ROW_NUMBER() OVER (
                    PARTITION BY game_date
                    ORDER BY rate
                )
            END AS rate_order
        FROM
            with_group
    )

    -- 2試合ペアの整合性チェック
    ,pair_check AS (
        SELECT
            o1.game_date
            ,o1.game_id AS first_game_id
            ,o1.rate AS first_rate
            ,o1.final_rank AS first_rank
            ,o2.game_id AS second_game_id
            ,o2.rate AS second_rate
            -- 昇順（rate低い方が先）が正しいか判定
            -- 先の試合が1-2位→rateが上がる（second_rate > first_rate）なら整合
            -- 先の試合が3-4位→rateが下がる（second_rate < first_rate）なら整合
            ,CASE
                WHEN o1.final_rank <= 2 AND o2.rate > o1.rate THEN TRUE
                WHEN o1.final_rank >= 3 AND o2.rate < o1.rate THEN TRUE
                ELSE FALSE
            END AS asc_is_correct
        FROM
            ordered AS o1
            INNER JOIN ordered AS o2
                ON o1.game_date = o2.game_date
                AND o1.rate_order = 1
                AND o2.rate_order = 2
        WHERE
            o1.games_in_hour = 2
    )

    -- 最終的な順序を決定
    ,final_order AS (
        SELECT
            o.game_id
            ,o.game_date
            ,CASE
                WHEN o.games_in_hour = 1 THEN 0
                WHEN pc.asc_is_correct THEN o.rate_order
                ELSE 3 - o.rate_order  -- 逆順にする（1→2, 2→1）
            END AS order_in_hour
        FROM
            ordered AS o
            LEFT JOIN pair_check AS pc ON o.game_date = pc.game_date
    )

SELECT
    game_id
    ,game_date
    ,order_in_hour
    ,ROW_NUMBER() OVER (
        ORDER BY game_date, order_in_hour
    ) AS game_order
FROM
    final_order
