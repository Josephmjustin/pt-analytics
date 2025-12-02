-- Headway calculation: Time between consecutive bus arrivals at each stop
-- Uses trip_id join (fast) instead of spatial queries
-- Detects arrivals: first GPS ping within 100m of stop

WITH stop_arrivals AS (
    SELECT 
        vp.vehicle_id,
        vp.trip_id,
        vp.timestamp as arrival_time,
        st.stop_id,
        st.stop_sequence,
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
)
SELECT 
    stop_id,
    stop_name,
    arrival_time,
    arrival_time - LAG(arrival_time) OVER (
        PARTITION BY stop_id 
        ORDER BY arrival_time
    ) as headway_actual
FROM arrivals_only
ORDER BY stop_id, arrival_time;
