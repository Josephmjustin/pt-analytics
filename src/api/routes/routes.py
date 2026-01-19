"""
Route information endpoints (TXC data only)
"""
from fastapi import APIRouter, HTTPException
from src.api.database import get_db_connection

router = APIRouter(prefix="/routes", tags=["routes"])

@router.get("/")
def get_all_routes():
    """Get all unique routes"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT DISTINCT
            route_name,
            STRING_AGG(DISTINCT operator_name, ', ') as operators,
            COUNT(DISTINCT pattern_id) as variants
        FROM txc_route_patterns
        GROUP BY route_name
        ORDER BY route_name
    """)
    
    routes = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {"routes": routes, "count": len(routes)}

@router.get("/{route_name}")
def get_route_details(route_name: str):
    """Get route details with all variants and stops"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get route variants
    cur.execute("""
        SELECT DISTINCT
            pattern_id,
            operator_name,
            direction,
            origin,
            destination
        FROM txc_route_patterns
        WHERE route_name = %s
        ORDER BY operator_name, direction
    """, (route_name,))
    
    variants = cur.fetchall()
    
    if not variants:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Get stops for first variant (as example)
    cur.execute("""
        SELECT 
            ps.naptan_id,
            ts.stop_name,
            ps.stop_sequence,
            ts.latitude,
            ts.longitude
        FROM txc_pattern_stops ps
        JOIN txc_stops ts ON ps.naptan_id = ts.naptan_id
        WHERE ps.pattern_id = %s
        ORDER BY ps.stop_sequence
    """, (variants[0]['pattern_id'],))
    
    stops = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        "route_name": route_name,
        "variants": variants,
        "example_stops": stops,
        "variant_count": len(variants)
    }