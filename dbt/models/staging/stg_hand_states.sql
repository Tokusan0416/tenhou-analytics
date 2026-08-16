WITH
    source AS (
        SELECT
            *
        FROM
            {{ source('tenhou_raw', 'raw_hand_states') }}
    )

SELECT
    game_id
    ,round_index
    ,action_index
    ,player
    ,action_type
    ,shanten
    ,is_tenpai
    ,wait_tiles
    ,wait_count
    ,wait_type
FROM
    source
