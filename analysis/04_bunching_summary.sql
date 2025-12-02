-- Bunching summary: Statistics by stop
-- Shows which stops have the most bunching problems

WITH stop_arrivals AS (
    SELECT 
        vp.vehicle_id,
        vp.trip_id,
        vp.timestamp as arrival_time,
        st.stop_id,
        gs.stop_name,
        ST_Distance(vp.geom::geography, gs.location::geography) as distance_meters,
        ROW_NUMBER() OVER (
            PARTITION BY vp.vehicle_id, vp.trip_id, st.stop_id 
            ORDER BY vp.timestamp
        ) as ping_number
    FROM vehicle_positions vp
    JOIN gtfs_stop_times st ON vp.trip_id = st.trip_id
    JOIN gtfs_stops gs ON st.stop_id = gs.stop_id
    WHERE vp.trip_id IS NOT NULL
),
arrivals_only AS (
    SELECT *
    FROM stop_arrivals
    WHERE distance_meters < 100 AND ping_number = 1
),
headways AS (
    SELECT 
        stop_id,
        stop_name,
        arrival_time,
        arrival_time - LAG(arrival_time) OVER (
            PARTITION BY stop_id 
            ORDER BY arrival_time
        ) as headway_actual,
        EXTRACT(EPOCH FROM (
            arrival_time - LAG(arrival_time) OVER (
                PARTITION BY stop_id 
                ORDER BY arrival_time
            )
        ))/60 as headway_minutes
    FROM arrivals_only
)
SELECT 
    stop_id,
    stop_name,
    COUNT(*) as total_arrivals,
    COUNT(*) FILTER (WHERE headway_minutes < 5) as bunched_count,
    ROUND(AVG(headway_minutes)::numeric, 2) as avg_headway_minutes,
    ROUND(MIN(headway_minutes)::numeric, 2) as min_headway_minutes,
    ROUND(MAX(headway_minutes)::numeric, 2) as max_headway_minutes,
    ROUND(
        (COUNT(*) FILTER (WHERE headway_minutes < 5)::numeric / COUNT(*)::numeric * 100), 
        1
    ) as bunching_rate_pct
FROM headways
WHERE headway_minutes IS NOT NULL
GROUP BY stop_id, stop_name
HAVING COUNT(*) >= 3  -- Only stops with 3+ arrivals
ORDER BY bunching_rate_pct DESC, bunched_count DESC;
