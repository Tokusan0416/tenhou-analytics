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
    ,hand_tiles
    ,shanten
    ,is_tenpai
    ,wait_tiles
    ,wait_count
FROM
    source
