from fastapi import APIRouter
from src.api.database import get_db_connection
from datetime import datetime, timedelta

router = APIRouter(prefix="/vehicles", tags=["vehicles"])

@router.get("/live")
def get_live_vehicles():
    """Get current vehicle positions in Liverpool (last 2 minutes)"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cutoff_time = datetime.now() - timedelta(minutes=2)
    
    # Liverpool bounding box (Merseyside region)
    query = """
        SELECT DISTINCT ON (vehicle_id)
            vehicle_id,
            latitude,
            longitude,
            bearing,
            timestamp,
            route_name,
            direction,
            operator,
            origin,
            destination
        FROM vehicle_positions
        WHERE timestamp >= %s
            AND latitude BETWEEN 53.35 AND 53.48
            AND longitude BETWEEN -3.05 AND -2.85
        ORDER BY vehicle_id, timestamp DESC
    """
    
    cur.execute(query, (cutoff_time,))
    vehicles = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {"vehicles": vehicles, "count": len(vehicles)}
