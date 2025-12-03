from fastapi import APIRouter, HTTPException
from database import get_db_connection

router = APIRouter(prefix="/routes", tags=["routes"])

@router.get("/")
def get_all_routes():
    """Get all routes with aggregated bunching scores"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
        SELECT 
            r.route_id,
            r.route_short_name,
            r.route_long_name,
            AVG(bs.avg_bunching_rate) as avg_bunching_rate,
            COUNT(DISTINCT bs.stop_id) as stop_count
        FROM gtfs_routes r
        LEFT JOIN bunching_by_stop bs ON TRUE
        GROUP BY r.route_id, r.route_short_name, r.route_long_name
        ORDER BY avg_bunching_rate DESC
    """
    
    cur.execute(query)
    routes = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {"routes": routes, "count": len(routes)}

@router.get("/{route_id}")
def get_route_details(route_id: str):
    """Get route details with all stops on the route"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Route info
    cur.execute("""
        SELECT route_id, route_short_name, route_long_name
        FROM gtfs_routes
        WHERE route_id = %s
    """, (route_id,))
    
    route_info = cur.fetchone()
    
    if not route_info:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Get stops on this route
    cur.execute("""
        SELECT DISTINCT
            gs.stop_id,
            gs.stop_name,
            bs.avg_bunching_rate,
            bs.total_count,
            MIN(st.stop_sequence) as stop_sequence
        FROM gtfs_stops gs
        JOIN gtfs_stop_times st ON gs.stop_id = st.stop_id
        JOIN gtfs_trips t ON st.trip_id = t.trip_id
        LEFT JOIN bunching_by_stop bs ON gs.stop_name = bs.stop_name
        WHERE t.route_id = %s
        GROUP BY gs.stop_id, gs.stop_name, bs.avg_bunching_rate, bs.total_count
        ORDER BY stop_sequence
    """, (route_id,))
    
    stops = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        "route": route_info,
        "stops": stops,
        "stop_count": len(stops)
    }
