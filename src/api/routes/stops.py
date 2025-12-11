from fastapi import APIRouter, HTTPException
from src.api.database import get_db_connection
from src.config.operator_mappings import get_sql_case_statement

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

@router.get("/{stop_id}/routes-bunching")
def get_stop_routes_with_bunching(stop_id: str, hour: int = None):
    """
    Get routes serving this stop with CURRENT HOUR bunching scores.
    Used for real-time passenger information displays.
    
    If hour not provided, uses current hour.
    Returns route-specific bunching for the specified hour.
    """
    from datetime import datetime
    
    if hour is None:
        hour = datetime.now().hour
    
    if hour < 0 or hour > 23:
        raise HTTPException(status_code=400, detail="Hour must be between 0 and 23")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get stop info
    cur.execute("""
        SELECT naptan_id, stop_name, latitude, longitude
        FROM txc_stops
        WHERE naptan_id = %s
    """, (stop_id,))
    
    stop_info = cur.fetchone()
    
    if not stop_info:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Stop not found")
    
    # Get operator name mapping SQL
    operator_case = get_sql_case_statement()
    
    # Get routes with hour-specific bunching scores
    query = f"""
        SELECT DISTINCT
            rp.route_name,
            {operator_case} as operator_name,
            rp.direction,
            rp.origin,
            rp.destination,
            brsh.bunching_rate_pct,
            brsh.expected_headway_minutes,
            brsh.observation_count,
            brsh.last_updated
        FROM txc_pattern_stops ps
        JOIN txc_route_patterns rp ON ps.service_code = rp.service_code
        LEFT JOIN bunching_by_route_stop_hour brsh 
            ON brsh.route_id = rp.route_name 
            AND brsh.stop_id = ps.naptan_id
            AND brsh.hour_of_day = %s
        WHERE ps.naptan_id = %s
        ORDER BY rp.route_name, rp.direction
    """
    
    cur.execute(query, (hour, stop_id))
    routes = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        "stop": stop_info,
        "hour": hour,
        "routes": routes,
        "route_count": len(routes)
    }

@router.get("/{stop_id}/route/{route_id}/hourly-pattern")
def get_stop_route_hourly_pattern(stop_id: str, route_id: str):
    """
    Get 24-hour bunching pattern for a specific route at a specific stop.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get stop info
    cur.execute("""
        SELECT naptan_id, stop_name
        FROM txc_stops
        WHERE naptan_id = %s
    """, (stop_id,))
    
    stop_info = cur.fetchone()
    
    if not stop_info:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Stop not found")
    
    # Get hourly pattern
    cur.execute("""
        SELECT 
            hour_of_day,
            bunching_rate_pct,
            expected_headway_minutes,
            observation_count
        FROM bunching_by_route_stop_hour
        WHERE route_id = %s AND stop_id = %s
        ORDER BY hour_of_day
    """, (route_id, stop_id))
    
    hourly_data = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        "stop": stop_info,
        "route_id": route_id,
        "hourly_pattern": hourly_data
    }

@router.get("/{stop_id}/routes")
def get_stop_routes(stop_id: str):
    """Get all routes passing through this stop with bunching scores"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get operator name mapping SQL
    operator_case = get_sql_case_statement()
    
    # Get routes from TransXChange pattern_stops
    query = f"""
        SELECT DISTINCT
            rp.service_code,
            rp.route_name,
            {operator_case} as operator_name,
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
    """Get detailed analytics for a specific stop (even if no bunching data)"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get stop basic info from txc_stops first
    cur.execute("""
        SELECT naptan_id as stop_id, stop_name
        FROM txc_stops
        WHERE naptan_id = %s
    """, (stop_id,))
    
    stop_basic = cur.fetchone()
    
    if not stop_basic:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Stop not found")
    
    # Try to get bunching stats if available
    cur.execute("""
        SELECT avg_bunching_rate, total_count, last_updated
        FROM bunching_by_stop
        WHERE stop_id = %s
        ORDER BY last_updated DESC
        LIMIT 1
    """, (stop_id,))
    
    bunching_stats = cur.fetchone()
    
    # Combine basic info with bunching stats
    stop_info = dict(stop_basic)
    if bunching_stats:
        stop_info.update(bunching_stats)
    else:
        stop_info['avg_bunching_rate'] = None
        stop_info['total_count'] = 0
        stop_info['last_updated'] = None
    
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