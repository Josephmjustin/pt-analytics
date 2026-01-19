"""
Stop information endpoints (TXC data only)
"""
from fastapi import APIRouter, HTTPException, Query
from src.api.database import get_db_connection
from typing import Optional

router = APIRouter(prefix="/stops", tags=["stops"])

@router.get("/")
def get_all_stops(
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500)
):
    """Get all TXC stops with optional search"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
        SELECT 
            naptan_id as stop_id,
            stop_name,
            latitude,
            longitude
        FROM txc_stops
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """
    
    params = []
    if search:
        query += " AND LOWER(stop_name) LIKE LOWER(%s)"
        params.append(f"%{search}%")
    
    query += " ORDER BY stop_name LIMIT %s"
    params.append(limit)
    
    cur.execute(query, params)
    stops = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {"stops": stops, "count": len(stops)}

@router.get("/{stop_id}")
def get_stop_details(stop_id: str):
    """Get stop details with routes serving it"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get stop info
    cur.execute("""
        SELECT naptan_id as stop_id, stop_name, latitude, longitude
        FROM txc_stops
        WHERE naptan_id = %s
    """, (stop_id,))
    
    stop_info = cur.fetchone()
    
    if not stop_info:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Stop not found")
    
    # Get routes serving this stop
    cur.execute("""
        SELECT DISTINCT
            rp.route_name,
            rp.operator_name,
            rp.direction
        FROM txc_pattern_stops ps
        JOIN txc_route_patterns rp ON ps.pattern_id = rp.pattern_id
        WHERE ps.naptan_id = %s
        ORDER BY rp.route_name, rp.direction
    """, (stop_id,))
    
    routes = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        "stop": stop_info,
        "routes": routes,
        "route_count": len(routes)
    }