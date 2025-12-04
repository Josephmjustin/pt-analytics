from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.api.database import get_db_connection
import io
import csv

router = APIRouter(prefix="/routes", tags=["routes"])

@router.get("/")
def get_all_routes():
    """Get all routes with headway baselines"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
        SELECT DISTINCT
            r.route_id,
            r.route_short_name,
            r.route_long_name,
            COUNT(DISTINCT rhb.stop_id) as stops_with_baseline,
            ROUND(AVG(rhb.median_headway_minutes)::numeric, 1) as avg_median_headway
        FROM gtfs_routes r
        INNER JOIN route_headway_baselines rhb ON r.route_id = rhb.route_id
        GROUP BY r.route_id, r.route_short_name, r.route_long_name
        HAVING COUNT(DISTINCT rhb.stop_id) > 0
        ORDER BY r.route_short_name
    """
    
    cur.execute(query)
    routes = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {"routes": routes, "count": len(routes)}

@router.get("/{route_id}")
def get_route_details(route_id: str):
    """Get route details with all stops and their headway baselines"""
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
    
    # Get stops on this route with headway baselines
    cur.execute("""
        SELECT DISTINCT ON (rhb.stop_id)
            rhb.stop_id,
            rhb.stop_name,
            rhb.median_headway_minutes,
            rhb.avg_headway_minutes,
            rhb.observation_count,
            rhb.last_updated,
            bs.avg_bunching_rate,
            bs.total_count
        FROM route_headway_baselines rhb
        LEFT JOIN bunching_by_stop bs ON rhb.stop_id::TEXT = bs.stop_id::TEXT
        WHERE rhb.route_id = %s
        ORDER BY rhb.stop_id, rhb.last_updated DESC
    """, (route_id,))
    
    stops = cur.fetchall()
    
    # Get route-level summary
    cur.execute("""
        SELECT 
            COUNT(*) as total_baselines,
            ROUND(AVG(median_headway_minutes)::numeric, 1) as avg_median_headway,
            ROUND(MIN(median_headway_minutes)::numeric, 1) as min_headway,
            ROUND(MAX(median_headway_minutes)::numeric, 1) as max_headway,
            SUM(observation_count) as total_observations
        FROM route_headway_baselines
        WHERE route_id = %s
    """, (route_id,))
    
    summary = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return {
        "route": route_info,
        "stops": stops,
        "stop_count": len(stops),
        "summary": summary
    }

@router.get("/{route_id}/csv")
def download_route_csv(route_id: str):
    """Download route details as CSV"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get route name
    cur.execute("""
        SELECT route_short_name, route_long_name
        FROM gtfs_routes
        WHERE route_id = %s
    """, (route_id,))
    
    route_info = cur.fetchone()
    if not route_info:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Get detailed stop data
    cur.execute("""
        SELECT DISTINCT ON (rhb.stop_id)
            rhb.stop_id,
            rhb.stop_name,
            rhb.median_headway_minutes,
            rhb.avg_headway_minutes,
            rhb.observation_count,
            rhb.last_updated,
            bs.avg_bunching_rate,
            bs.total_count as bunching_observations
        FROM route_headway_baselines rhb
        LEFT JOIN bunching_by_stop bs ON rhb.stop_id::TEXT = bs.stop_id::TEXT
        WHERE rhb.route_id = %s
        ORDER BY rhb.stop_id, rhb.last_updated DESC
    """, (route_id,))
    
    stops = cur.fetchall()
    
    cur.close()
    conn.close()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow([
        'Stop ID',
        'Stop Name',
        'Median Headway (min)',
        'Avg Headway (min)',
        'Headway Observations',
        'Last Updated',
        'Bunching Rate (%)',
        'Bunching Observations'
    ])
    
    # Write data
    for stop in stops:
        writer.writerow([
            stop['stop_id'],
            stop['stop_name'],
            stop['median_headway_minutes'] or 'N/A',
            stop['avg_headway_minutes'] or 'N/A',
            stop['observation_count'] or 0,
            stop['last_updated'] or 'N/A',
            f"{stop['avg_bunching_rate']:.1f}" if stop['avg_bunching_rate'] else 'N/A',
            stop['bunching_observations'] or 0
        ])
    
    output.seek(0)
    
    filename = f"route_{route_info['route_short_name']}_analytics.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
