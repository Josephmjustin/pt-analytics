-- Scheduled vs Actual comparison with bunching detection
-- Shows both schedule adherence AND headway problems

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
actual_headways AS (
    SELECT 
        stop_id,
        stop_name,
        trip_id,
        arrival_time,
        arrival_time - LAG(arrival_time) OVER (
            PARTITION BY stop_id 
            ORDER BY arrival_time
        ) as headway_actual,
        LAG(arrival_time) OVER (
            PARTITION BY stop_id 
            ORDER BY arrival_time
        ) as prev_arrival_time
    FROM arrivals_only
)
SELECT 
    ah.stop_id,
    ah.stop_name,
    ah.arrival_time as actual_arrival,
    st.arrival_time as scheduled_arrival,
    ah.arrival_time::time - st.arrival_time as schedule_deviation,
    ah.headway_actual as actual_headway,
    EXTRACT(EPOCH FROM ah.headway_actual)/60 as headway_minutes,
    CASE 
        WHEN EXTRACT(EPOCH FROM ah.headway_actual)/60 < 5 THEN 'BUNCHED'
        WHEN ABS(EXTRACT(EPOCH FROM (ah.arrival_time::time - st.arrival_time))) > 300 THEN 'DELAYED'
        ELSE 'NORMAL'
    END as service_status
FROM actual_headways ah
JOIN gtfs_stop_times st ON ah.trip_id = st.trip_id AND ah.stop_id = st.stop_id
WHERE ah.headway_actual IS NOT NULL
ORDER BY ah.stop_id, ah.arrival_time;
