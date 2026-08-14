-- プレイヤー別スタッツ集計
-- fct_round_player_stats と fct_games から全主要スタッツを算出
WITH
    round_stats AS (
        SELECT
            player_name
            ,is_me
            ,COUNT(*) AS total_rounds
            ,AVG(score_change) AS avg_score_change
            -- アガリ
            ,AVG(CASE WHEN is_agari THEN 1.0 ELSE 0 END) AS agari_rate
            ,AVG(IF(is_agari, agari_ten, NULL)) AS avg_agari_ten
            ,AVG(IF(is_naki AND is_agari, agari_ten, NULL)) AS avg_naki_agari_ten
            ,AVG(IF(is_agari, agari_turn, NULL)) AS avg_agari_turn
            -- 放銃
            ,AVG(CASE WHEN is_houjuu THEN 1.0 ELSE 0 END) AS houjuu_rate
            ,AVG(IF(is_houjuu, houjuu_ten, NULL)) AS avg_houjuu_ten
            -- リーチ
            ,AVG(CASE WHEN is_reach THEN 1.0 ELSE 0 END) AS reach_rate
            ,AVG(CASE WHEN is_first_reach THEN 1.0 ELSE 0 END) AS first_reach_rate
            -- 副露
            ,AVG(CASE WHEN is_naki THEN 1.0 ELSE 0 END) AS naki_rate
            -- 流局
            ,AVG(
                IF(result_type = 'ryuukyoku', score_change, NULL)
            ) AS avg_ryuukyoku_score_change
            -- ドラ
            ,AVG(IF(is_agari, COALESCE(dora_count, 0), NULL)) AS avg_dora_count
        FROM
            {{ ref('fct_round_player_stats') }}
        GROUP BY
            player_name
            ,is_me
    )

    ,game_stats AS (
        SELECT
            player_name
            ,is_me
            ,COUNT(*) AS total_games
            ,AVG(final_rank) AS avg_rank
            ,SUM(final_point) AS total_point
            ,AVG(final_point) AS avg_point
            ,AVG(CASE WHEN final_rank = 1 THEN 1.0 ELSE 0 END) AS top_rate
            ,AVG(CASE WHEN final_rank <= 2 THEN 1.0 ELSE 0 END) AS rentai_rate
            ,AVG(CASE WHEN final_rank = 4 THEN 1.0 ELSE 0 END) AS last_rate
        FROM
            {{ ref('fct_games') }}
        GROUP BY
            player_name
            ,is_me
    )

SELECT
    r.player_name
    ,r.is_me
    ,g.total_games
    ,r.total_rounds

    -- 順位
    ,ROUND(g.avg_rank, 2) AS avg_rank
    ,ROUND(g.total_point, 1) AS total_point
    ,ROUND(g.avg_point, 1) AS avg_point
    ,ROUND(g.top_rate * 100, 1) AS top_rate
    ,ROUND(g.rentai_rate * 100, 1) AS rentai_rate
    ,ROUND(g.last_rate * 100, 1) AS last_rate

    -- 局収支
    ,ROUND(r.avg_score_change, 1) AS avg_score_change

    -- アガリ
    ,ROUND(r.agari_rate * 100, 1) AS agari_rate
    ,ROUND(r.avg_agari_ten, 0) AS avg_agari_ten
    ,ROUND(r.avg_naki_agari_ten, 0) AS avg_naki_agari_ten
    ,ROUND(r.avg_agari_turn, 1) AS avg_agari_turn

    -- 放銃
    ,ROUND(r.houjuu_rate * 100, 1) AS houjuu_rate
    ,ROUND(r.avg_houjuu_ten, 0) AS avg_houjuu_ten

    -- アガリ放銃差
    ,ROUND((r.agari_rate - r.houjuu_rate) * 100, 1) AS agari_houjuu_diff

    -- 調整打点効率（アガリ率×アガリ打点 − 放銃率×放銃打点）
    ,ROUND(
        r.agari_rate * COALESCE(r.avg_agari_ten, 0)
        - r.houjuu_rate * COALESCE(r.avg_houjuu_ten, 0)
    , 0) AS adjusted_score_efficiency

    -- リーチ
    ,ROUND(r.reach_rate * 100, 1) AS reach_rate
    ,ROUND(r.first_reach_rate * 100, 1) AS first_reach_rate

    -- 副露
    ,ROUND(r.naki_rate * 100, 1) AS naki_rate

    -- 流局平得
    ,ROUND(r.avg_ryuukyoku_score_change, 1) AS avg_ryuukyoku_score_change

    -- ドラ
    ,ROUND(r.avg_dora_count, 2) AS avg_dora_count

FROM
    round_stats AS r
    INNER JOIN game_stats AS g ON r.player_name = g.player_name AND r.is_me = g.is_me
