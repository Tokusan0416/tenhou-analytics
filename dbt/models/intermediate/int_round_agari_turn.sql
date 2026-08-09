-- アガリ巡目の算出
-- アガリ局の最後のdrawまたはdiscardアクションの巡目をアガリ巡目とする
WITH
    last_actions AS (
        SELECT
            a.game_id
            ,a.round_index
            ,r.agari_winner AS player
            ,MAX(
                CASE
                    WHEN a.action_type = 'draw' AND a.player = r.agari_winner THEN a.action_index
                    WHEN a.action_type = 'discard' AND a.player = r.agari_from_who AND NOT r.agari_is_tsumo THEN a.action_index
                END
            ) AS last_action_index
        FROM
            {{ ref('stg_actions') }} AS a
            INNER JOIN {{ ref('stg_rounds') }} AS r ON a.game_id = r.game_id AND a.round_index = r.round_index
        WHERE
            r.result_type = 'agari'
        GROUP BY
            a.game_id
            ,a.round_index
            ,r.agari_winner
    )

    -- 巡目はdrawの回数で計算（プレイヤーのdrawが何回目かで近似）
    ,agari_turn_calc AS (
        SELECT
            la.game_id
            ,la.round_index
            ,la.player
            ,COUNT(*) AS agari_turn
        FROM
            last_actions AS la
            INNER JOIN {{ ref('stg_actions') }} AS a ON la.game_id = a.game_id AND la.round_index = a.round_index AND a.player = la.player AND a.action_type = 'draw' AND a.action_index <= la.last_action_index
        GROUP BY
            la.game_id
            ,la.round_index
            ,la.player
    )

SELECT
    game_id
    ,round_index
    ,player
    ,agari_turn
FROM
    agari_turn_calc
