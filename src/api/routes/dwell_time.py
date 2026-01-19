"""
Dwell Time Analysis API Endpoints
Provides demand proxy insights based on dwell time patterns
"""
from fastapi import APIRouter, HTTPException, Query
from src.api.database import get_db_connection
from typing import Optional

router = APIRouter(prefix="/dwell-time", tags=["dwell-time"])

@router.get("/routes")
def get_routes_with_dwell_data():
    """Get all routes with dwell time data available"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            route_name,
            COUNT(DISTINCT naptan_id) as stops_with_data,
            COUNT(DISTINCT operator) as operators,
            SUM(sample_count) as total_samples,
            ROUND(AVG(avg_dwell_seconds)::numeric, 1) as avg_dwell
        FROM dwell_time_analysis
        GROUP BY route_name
        ORDER BY route_name
    """)
    
    routes = cur.fetchall()
    cur.close()
    conn.close()
    
    return {"routes": routes, "count": len(routes)}

@router.get("/route/{route_name}/stops")
def get_route_stops_dwell(
    route_name: str,
    direction: Optional[str] = None,
    operator: Optional[str] = None,
    day_of_week: Optional[int] = Query(None, ge=0, le=6),
    hour_of_day: Optional[int] = Query(None, ge=0, le=23)
):
    """Get dwell time analysis for stops on a route"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
        SELECT 
            dta.naptan_id,
            ts.stop_name,
            ts.latitude,
            ts.longitude,
            dta.direction,
            dta.operator,
            dta.day_of_week,
            dta.hour_of_day,
            ROUND(dta.avg_dwell_seconds::numeric, 1) as avg_dwell_seconds,
            ROUND(dta.stddev_dwell_seconds::numeric, 1) as stddev_dwell_seconds,
            dta.sample_count
        FROM dwell_time_analysis dta
        JOIN txc_stops ts ON dta.naptan_id = ts.naptan_id
        WHERE dta.route_name = %s
    """
    
    params = [route_name]
    
    if direction:
        query += " AND dta.direction = %s"
        params.append(direction)
    
    if operator:
        query += " AND dta.operator = %s"
        params.append(operator)
    
    if day_of_week is not None:
        query += " AND dta.day_of_week = %s"
        params.append(day_of_week)
    
    if hour_of_day is not None:
        query += " AND dta.hour_of_day = %s"
        params.append(hour_of_day)
    
    query += " ORDER BY dta.avg_dwell_seconds DESC"
    
    cur.execute(query, params)
    stops = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        "route_name": route_name,
        "filters": {
            "direction": direction,
            "operator": operator,
            "day_of_week": day_of_week,
            "hour_of_day": hour_of_day
        },
        "stops": stops,
        "count": len(stops)
    }

@router.get("/stop/{naptan_id}/pattern")
def get_stop_dwell_pattern(
    naptan_id: str,
    route_name: Optional[str] = None
):
    """Get dwell time patterns for a specific stop across time"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get stop info
    cur.execute("""
        SELECT naptan_id, stop_name, latitude, longitude
        FROM txc_stops
        WHERE naptan_id = %s
    """, (naptan_id,))
    
    stop_info = cur.fetchone()
    
    if not stop_info:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Stop not found")
    
    query = """
        SELECT 
            route_name,
            direction,
            operator,
            day_of_week,
            hour_of_day,
            ROUND(avg_dwell_seconds::numeric, 1) as avg_dwell_seconds,
            ROUND(stddev_dwell_seconds::numeric, 1) as stddev_dwell_seconds,
            sample_count
        FROM dwell_time_analysis
        WHERE naptan_id = %s
    """
    
    params = [naptan_id]
    
    if route_name:
        query += " AND route_name = %s"
        params.append(route_name)
    
    query += " ORDER BY route_name, day_of_week, hour_of_day"
    
    cur.execute(query, params)
    patterns = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        "stop": stop_info,
        "patterns": patterns,
        "count": len(patterns)
    }

@router.get("/hotspots")
def get_high_demand_stops(
    min_samples: int = Query(10, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get stops with highest average dwell times (demand proxy)"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            dta.naptan_id,
            ts.stop_name,
            ts.latitude,
            ts.longitude,
            COUNT(DISTINCT dta.route_name) as routes_count,
            ROUND(AVG(dta.avg_dwell_seconds)::numeric, 1) as overall_avg_dwell,
            SUM(dta.sample_count) as total_samples
        FROM dwell_time_analysis dta
        JOIN txc_stops ts ON dta.naptan_id = ts.naptan_id
        GROUP BY dta.naptan_id, ts.stop_name, ts.latitude, ts.longitude
        HAVING SUM(dta.sample_count) >= %s
        ORDER BY AVG(dta.avg_dwell_seconds) DESC
        LIMIT %s
    """, (min_samples, limit))
    
    hotspots = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {"hotspots": hotspots, "count": len(hotspots)}

@router.get("/stats")
def get_dwell_time_stats():
    """Get overall dwell time statistics"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            COUNT(DISTINCT naptan_id) as unique_stops,
            COUNT(DISTINCT route_name) as unique_routes,
            COUNT(DISTINCT operator) as unique_operators,
            SUM(sample_count) as total_samples,
            ROUND(AVG(avg_dwell_seconds)::numeric, 1) as overall_avg_dwell,
            ROUND(MIN(avg_dwell_seconds)::numeric, 1) as min_avg_dwell,
            ROUND(MAX(avg_dwell_seconds)::numeric, 1) as max_avg_dwell
        FROM dwell_time_analysis
    """)
    
    stats = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return stats or {}