-- Step 1: Join vehicle positions to scheduled stop times via trip_id
-- This avoids expensive spatial queries on the 1.7GB stop_times table

SELECT 
    vp.vehicle_id,
    vp.trip_id,
    vp.timestamp as gps_timestamp,
    st.stop_id,
    st.stop_sequence,
    st.arrival_time as scheduled_arrival,
    gs.stop_name
FROM vehicle_positions vp
JOIN gtfs_stop_times st ON vp.trip_id = st.trip_id
JOIN gtfs_stops gs ON st.stop_id = gs.stop_id
WHERE vp.trip_id IS NOT NULL
ORDER BY vp.vehicle_id, vp.trip_id, st.stop_sequence, vp.timestamp
LIMIT 100;
