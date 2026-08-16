-- テンパイ情報ファクト（1行=1局×1プレイヤー）
-- 配牌シャンテン数、最初のテンパイ巡目、待ち形、局結果を集約
WITH
    -- 配牌時のシャンテン数
    haipai_shanten AS (
        SELECT
            game_id
            ,round_index
            ,player
            ,shanten AS haipai_shanten
        FROM
            {{ ref('stg_hand_states') }}
        WHERE
            action_type = 'haipai'
    )

    -- 最初のテンパイ
    ,first_tenpai AS (
        SELECT
            game_id
            ,round_index
            ,player
            ,MIN(action_index) AS first_tenpai_action_index
        FROM
            {{ ref('stg_hand_states') }}
        WHERE
            is_tenpai
            AND action_type = 'discard'
        GROUP BY
            game_id
            ,round_index
            ,player
    )

    -- 最初のテンパイ時の詳細
    ,first_tenpai_detail AS (
        SELECT
            hs.game_id
            ,hs.round_index
            ,hs.player
            ,hs.wait_tiles
            ,hs.wait_count
            ,hs.wait_type
        FROM
            {{ ref('stg_hand_states') }} AS hs
            INNER JOIN first_tenpai AS ft
                ON hs.game_id = ft.game_id
                AND hs.round_index = ft.round_index
                AND hs.player = ft.player
                AND hs.action_index = ft.first_tenpai_action_index
    )

    -- 打牌回数（巡目の近似）
    ,discard_counts AS (
        SELECT
            game_id
            ,round_index
            ,player
            ,action_index
            ,ROW_NUMBER() OVER (
                PARTITION BY game_id, round_index, player
                ORDER BY action_index
            ) AS discard_turn
        FROM
            {{ ref('stg_hand_states') }}
        WHERE
            action_type = 'discard'
    )

SELECT
    h.game_id
    ,h.round_index
    ,h.player
    ,rps.player_name
    ,rps.is_me

    -- 配牌シャンテン数
    ,h.haipai_shanten

    -- テンパイ情報
    ,ft.first_tenpai_action_index IS NOT NULL AS reached_tenpai
    ,dc.discard_turn AS tenpai_turn
    ,ftd.wait_tiles AS tenpai_wait_tiles
    ,ftd.wait_count AS tenpai_wait_count
    ,ftd.wait_type AS tenpai_wait_type

    -- 局の結果（fct_round_player_statsから）
    ,rps.is_agari
    ,rps.agari_type
    ,rps.agari_ten
    ,rps.is_houjuu
    ,rps.houjuu_ten
    ,rps.is_reach
    ,rps.is_naki
    ,rps.score_change

    -- 放銃先の待ち形（和了者のテンパイ情報）
    ,winner_tenpai.wait_type AS houjuu_opponent_wait_type

FROM
    haipai_shanten AS h
    INNER JOIN {{ ref('fct_round_player_stats') }} AS rps
        ON h.game_id = rps.game_id
        AND h.round_index = rps.round_index
        AND h.player = rps.player_seat
    LEFT JOIN first_tenpai AS ft
        ON h.game_id = ft.game_id AND h.round_index = ft.round_index AND h.player = ft.player
    LEFT JOIN first_tenpai_detail AS ftd
        ON h.game_id = ftd.game_id AND h.round_index = ftd.round_index AND h.player = ftd.player
    LEFT JOIN discard_counts AS dc
        ON ft.game_id = dc.game_id AND ft.round_index = dc.round_index AND ft.player = dc.player AND ft.first_tenpai_action_index = dc.action_index
    -- 放銃時: 和了者のテンパイ情報を取得
    LEFT JOIN {{ ref('fct_rounds') }} AS fr
        ON h.game_id = fr.game_id AND h.round_index = fr.round_index
    LEFT JOIN first_tenpai_detail AS winner_tenpai
        ON h.game_id = winner_tenpai.game_id
        AND h.round_index = winner_tenpai.round_index
        AND fr.agari_winner = winner_tenpai.player
        AND rps.is_houjuu
