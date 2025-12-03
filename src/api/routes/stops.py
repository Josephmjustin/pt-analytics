from fastapi import APIRouter, HTTPException
from database import get_db_connection

router = APIRouter(prefix="/stops", tags=["stops"])

@router.get("/")
def get_all_stops():
    """Get all stops with current bunching scores"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
        SELECT DISTINCT ON (bs.stop_id)
            bs.stop_id,
            bs.stop_name,
            bs.avg_bunching_rate,
            bs.total_count,
            bs.last_updated,
            s.latitude,
            s.longitude
        FROM bunching_by_stop bs
        LEFT JOIN osm_stops s ON bs.stop_name = s.name
        WHERE s.latitude IS NOT NULL
        ORDER BY bs.stop_id, bs.avg_bunching_rate DESC
        LIMIT 100
    """
    
    cur.execute(query)
    stops = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {"stops": stops, "count": len(stops)}

@router.get("/stats")
def get_stops_stats():
    """Get statistics for all monitored stops"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Stop stats
    cur.execute("""
        SELECT 
            COUNT(*) as total_stops,
            AVG(avg_bunching_rate) as avg_bunching,
            COUNT(*) FILTER (WHERE avg_bunching_rate > 50) as high_bunching_stops,
            COUNT(*) FILTER (WHERE avg_bunching_rate < 30) as low_bunching_stops
        FROM bunching_by_stop
    """)
    stats = cur.fetchone()
    
    # Active buses count (last 5 minutes)
    from datetime import datetime, timedelta
    cutoff_time = datetime.now() - timedelta(minutes=5)
    
    cur.execute("""
        SELECT COUNT(DISTINCT vehicle_id) as active_buses
        FROM vehicle_positions
        WHERE timestamp >= %s
            AND latitude BETWEEN 53.35 AND 53.48
            AND longitude BETWEEN -3.05 AND -2.85
    """, (cutoff_time,))
    
    buses_result = cur.fetchone()
    
    cur.close()
    conn.close()
    
    result = dict(stats) if stats else {}
    result['active_buses'] = buses_result['active_buses'] if buses_result else 0
    
    return result

@router.get("/{stop_id}")
def get_stop_details(stop_id: str):
    """Get detailed analytics for a specific stop"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Overall stats
    cur.execute("""
        SELECT stop_id, stop_name, avg_bunching_rate, total_count, last_updated
        FROM bunching_by_stop
        WHERE stop_id = %s
    """, (stop_id,))
    
    stop_info = cur.fetchone()
    
    if not stop_info:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Stop not found")
    
    # Hourly pattern
    cur.execute("""
        SELECT hour_of_day, avg_bunching_rate, total_count
        FROM bunching_by_hour
        WHERE stop_id = %s
        ORDER BY hour_of_day
    """, (stop_id,))
    hourly = cur.fetchall()
    
    # Daily pattern
    cur.execute("""
        SELECT day_of_week, avg_bunching_rate, total_count
        FROM bunching_by_day
        WHERE stop_id = %s
        ORDER BY day_of_week
    """, (stop_id,))
    daily = cur.fetchall()
    
    # Monthly pattern
    cur.execute("""
        SELECT month, avg_bunching_rate, total_count
        FROM bunching_by_month
        WHERE stop_id = %s
        ORDER BY month
    """, (stop_id,))
    monthly = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        "stop": stop_info,
        "patterns": {
            "hourly": hourly,
            "daily": daily,
            "monthly": monthly
        }
    }

@router.get("/{stop_id}/routes")
def get_stop_routes(stop_id: str):
    """Get all routes passing through this stop with bunching scores"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # First get the stop name from bunching table
    cur.execute("SELECT stop_name FROM bunching_by_stop WHERE stop_id = %s", (stop_id,))
    result = cur.fetchone()
    
    if not result:
        cur.close()
        conn.close()
        return {"routes": []}
    
    stop_name = result['stop_name']
    
    # Find routes through stops with matching names
    query = """
        SELECT DISTINCT
            r.route_id,
            r.route_short_name,
            r.route_long_name,
            AVG(bs.avg_bunching_rate) as avg_bunching_rate
        FROM gtfs_stops gs
        JOIN gtfs_stop_times st ON gs.stop_id = st.stop_id
        JOIN gtfs_trips t ON st.trip_id = t.trip_id
        JOIN gtfs_routes r ON t.route_id = r.route_id
        LEFT JOIN bunching_by_stop bs ON gs.stop_name = bs.stop_name
        WHERE gs.stop_name = %s
        GROUP BY r.route_id, r.route_short_name, r.route_long_name
        ORDER BY r.route_short_name
    """
    
    cur.execute(query, (stop_name,))
    routes = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {"routes": routes}
