from fastapi import APIRouter, HTTPException
from src.api.database import get_db_connection

router = APIRouter(prefix="/stops", tags=["stops"])

@router.get("/")
def get_all_stops(search: str = None, limit: int = 50):
    """Get all stops with current bunching scores, with optional search"""
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
        LEFT JOIN txc_stops s ON bs.stop_id = s.naptan_id
        WHERE s.latitude IS NOT NULL
    """
    
    params = []
    if search:
        query += " AND LOWER(bs.stop_name) LIKE LOWER(%s)"
        params.append(f"%{search}%")
    
    query += " ORDER BY bs.stop_id, bs.avg_bunching_rate DESC LIMIT %s"
    params.append(limit)
    
    cur.execute(query, params)
    stops = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {"stops": stops, "count": len(stops)}

@router.get("/all-txc")
def get_all_txc_stops():
    """Get ALL TransXChange stops, with bunching data if available"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
        WITH latest_bunching AS (
            SELECT DISTINCT ON (stop_id)
                stop_id,
                avg_bunching_rate,
                total_count
            FROM bunching_by_stop
            ORDER BY stop_id, last_updated DESC
        )
        SELECT DISTINCT
            ts.naptan_id as stop_id,
            ts.stop_name,
            ts.latitude,
            ts.longitude,
            lb.avg_bunching_rate,
            lb.total_count
        FROM txc_stops ts
        LEFT JOIN latest_bunching lb ON ts.naptan_id = lb.stop_id
        ORDER BY ts.naptan_id
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
    
    # Active arrivals count (last 10 minutes)
    cur.execute("""
        SELECT COUNT(DISTINCT vehicle_id) as active_buses
        FROM vehicle_arrivals
        WHERE timestamp >= NOW() - INTERVAL '10 minutes'
    """)
    
    buses_result = cur.fetchone()
    
    cur.close()
    conn.close()
    
    result = dict(stats) if stats else {}
    result['active_buses'] = buses_result['active_buses'] if buses_result else 0
    
    return result

@router.get("/headways")
def get_headway_summary():
    """Get summary of route headway baselines"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_baselines,
            COUNT(DISTINCT route_id) as unique_routes,
            ROUND(AVG(median_headway_minutes)::numeric, 1) as avg_median,
            ROUND(MIN(median_headway_minutes)::numeric, 1) as min_median,
            ROUND(MAX(median_headway_minutes)::numeric, 1) as max_median,
            SUM(observation_count) as total_observations
        FROM route_headway_baselines
    """)
    
    summary = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return summary or {}

@router.get("/{stop_id}/routes")
def get_stop_routes(stop_id: str):
    """Get all routes passing through this stop with bunching scores"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get routes from TransXChange pattern_stops
    query = """
        SELECT DISTINCT
            rp.service_code,
            rp.route_name,
            rp.operator_name,
            rp.direction,
            COUNT(DISTINCT ps.naptan_id) as stop_count,
            NULL as avg_bunching_rate
        FROM txc_pattern_stops ps
        JOIN txc_route_patterns rp ON ps.service_code = rp.service_code
        WHERE ps.naptan_id = %s
        GROUP BY rp.service_code, rp.route_name, rp.operator_name, rp.direction
        ORDER BY rp.route_name, rp.direction
    """
    
    cur.execute(query, (stop_id,))
    routes = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {"routes": routes}

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
