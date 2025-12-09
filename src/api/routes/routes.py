from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.api.database import get_db_connection
import io
import csv

router = APIRouter(prefix="/routes", tags=["routes"])

@router.get("/")
def get_all_routes():
    """Get all routes from TransXChange"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
        SELECT DISTINCT
            rp.route_name,
            rp.operator_name,
            COUNT(DISTINCT ps.naptan_id) as total_stops,
            COUNT(DISTINCT rp.service_code) as variants
        FROM txc_route_patterns rp
        JOIN txc_pattern_stops ps ON rp.service_code = ps.service_code
        GROUP BY rp.route_name, rp.operator_name
        ORDER BY rp.route_name
    """
    
    cur.execute(query)
    routes = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {"routes": routes, "count": len(routes)}

@router.get("/{route_name}")
def get_route_details(route_name: str):
    """Get route details with all service codes (variants) and stops"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all service codes for this route
    cur.execute("""
        SELECT DISTINCT
            service_code,
            operator_name,
            direction,
            origin,
            destination
        FROM txc_route_patterns
        WHERE route_name = %s
        ORDER BY direction, service_code
    """, (route_name,))
    
    variants = cur.fetchall()
    
    if not variants:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Get stops for each variant
    all_stops = []
    for variant in variants:
        cur.execute("""
            SELECT 
                ps.naptan_id,
                ts.stop_name,
                ps.stop_sequence,
                bs.avg_bunching_rate,
                bs.total_count
            FROM txc_pattern_stops ps
            JOIN txc_stops ts ON ps.naptan_id = ts.naptan_id
            LEFT JOIN bunching_by_stop bs ON ps.naptan_id = bs.stop_id
            WHERE ps.service_code = %s
            ORDER BY ps.stop_sequence
        """, (variant['service_code'],))
        
        stops = cur.fetchall()
        all_stops.append({
            'variant': variant,
            'stops': stops
        })
    
    cur.close()
    conn.close()
    
    return {
        "route_name": route_name,
        "variants": all_stops,
        "variant_count": len(variants)
    }

@router.get("/{route_name}/csv")
def download_route_csv(route_name: str):
    """Download route details as CSV"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if route exists
    cur.execute("""
        SELECT COUNT(*) as count
        FROM txc_route_patterns
        WHERE route_name = %s
    """, (route_name,))
    
    if cur.fetchone()['count'] == 0:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Get all stops for all variants
    cur.execute("""
        SELECT 
            rp.service_code,
            rp.direction,
            ps.stop_sequence,
            ps.naptan_id,
            ts.stop_name,
            bs.avg_bunching_rate,
            bs.total_count
        FROM txc_route_patterns rp
        JOIN txc_pattern_stops ps ON rp.service_code = ps.service_code
        JOIN txc_stops ts ON ps.naptan_id = ts.naptan_id
        LEFT JOIN bunching_by_stop bs ON ps.naptan_id = bs.stop_id
        WHERE rp.route_name = %s
        ORDER BY rp.service_code, ps.stop_sequence
    """, (route_name,))
    
    stops = cur.fetchall()
    
    cur.close()
    conn.close()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow([
        'Service Code',
        'Direction',
        'Stop Sequence',
        'NaPTAN ID',
        'Stop Name',
        'Bunching Rate (%)',
        'Observations'
    ])
    
    # Write data
    for stop in stops:
        writer.writerow([
            stop['service_code'],
            stop['direction'] or 'N/A',
            stop['stop_sequence'],
            stop['naptan_id'],
            stop['stop_name'],
            f"{stop['avg_bunching_rate']:.1f}" if stop['avg_bunching_rate'] else 'N/A',
            stop['total_count'] or 0
        ])
    
    output.seek(0)
    
    filename = f"route_{route_name}_analytics.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
