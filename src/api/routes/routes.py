from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.api.database import get_db_connection
import io
import csv
import urllib.parse

router = APIRouter(prefix="/routes", tags=["routes"])

@router.get("/")
def get_all_routes():
    """Get all unique routes (operator-agnostic for bunching)"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = f"""
        SELECT DISTINCT
            rp.route_name as route_id,
            rp.route_name,
            STRING_AGG(DISTINCT rp.operator_name, ', ') as operators,
            COUNT(DISTINCT ps.naptan_id) as total_stops,
            COUNT(DISTINCT rp.service_code) as variants
        FROM txc_route_patterns rp
        JOIN txc_pattern_stops ps ON rp.pattern_id = ps.pattern_id
        GROUP BY rp.route_name
        ORDER BY rp.route_name
    """
    
    cur.execute(query)
    routes = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {"routes": routes, "count": len(routes)}

@router.get("/{route_id}")
def get_route_details(route_id: str):
    """Get route details with all operators and variants"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all service codes for this route (all operators)
    query = f"""
        SELECT DISTINCT
            service_code,
            operator_name,
            direction,
            origin,
            destination
        FROM txc_route_patterns
        WHERE route_name = %s
        ORDER BY operator_name, direction, service_code
    """
    
    cur.execute(query, (route_id,))
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
            FROM txc_route_patterns rp
            JOIN txc_pattern_stops ps ON rp.pattern_id = ps.pattern_id
            JOIN txc_stops ts ON ps.naptan_id = ts.naptan_id
            LEFT JOIN bunching_by_stop bs ON ps.naptan_id = bs.stop_id
            WHERE rp.service_code = %s
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
        "route_name": route_id,
        "operators": list(set([v['operator_name'] for v in variants])),
        "variants": all_stops,
        "variant_count": len(variants)
    }

@router.get("/{route_id}/stops-with-bunching")
def get_route_stops_with_bunching(route_id: str, hour: int = None):
    """Get all stops on route with bunching scores (operator-agnostic)"""
    from datetime import datetime
    
    if hour is None:
        hour = datetime.now().hour
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get stops with bunching (all operators combined)
    query = f"""
        SELECT 
            MIN(ps.stop_sequence) as stop_sequence,
            ps.naptan_id,
            MAX(ts.stop_name) as stop_name,
            MAX(ts.latitude) as latitude,
            MAX(ts.longitude) as longitude,
            MAX(brsh.bunching_rate_pct) as bunching_rate_pct,
            MAX(brsh.expected_headway_minutes) as expected_headway_minutes,
            STRING_AGG(DISTINCT rp.operator_name, ', ') as operators
        FROM txc_route_patterns rp
        JOIN txc_pattern_stops ps ON rp.pattern_id = ps.pattern_id
        JOIN txc_stops ts ON ps.naptan_id = ts.naptan_id
        LEFT JOIN bunching_by_route_stop_hour brsh 
            ON brsh.route_id = rp.route_name 
            AND brsh.stop_id = ps.naptan_id
            AND brsh.hour_of_day = %s
        WHERE rp.route_name = %s
        GROUP BY ps.naptan_id
        ORDER BY MIN(ps.stop_sequence)
    """
    
    cur.execute(query, (hour, route_id))
    stops = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if not stops:
        raise HTTPException(status_code=404, detail="No stops found for this route")
    
    return {
        "route_name": route_id,
        "hour": hour,
        "stops": stops,
        "total_stops": len(stops)
    }

@router.get("/{route_id}/csv")
def download_route_csv(route_id: str):
    """Download route details as CSV (all operators)"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all stops for all operators
    query = f"""
        SELECT 
            rp.service_code,
            rp.operator_name,
            rp.direction,
            ps.stop_sequence,
            ps.naptan_id,
            ts.stop_name,
            bs.avg_bunching_rate,
            bs.total_count
        FROM txc_route_patterns rp
        JOIN txc_pattern_stops ps ON rp.pattern_id = ps.pattern_id
        JOIN txc_stops ts ON ps.naptan_id = ts.naptan_id
        LEFT JOIN bunching_by_stop bs ON ps.naptan_id = bs.stop_id
        WHERE rp.route_name = %s
        ORDER BY rp.operator_name, rp.service_code, ps.stop_sequence
    """
    
    cur.execute(query, (route_id,))
    stops = cur.fetchall()
    
    cur.close()
    conn.close()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow([
        'Service Code',
        'Operator',
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
            stop['operator_name'],
            stop['direction'] or 'N/A',
            stop['stop_sequence'],
            stop['naptan_id'],
            stop['stop_name'],
            f"{stop['avg_bunching_rate']:.1f}" if stop['avg_bunching_rate'] else 'N/A',
            stop['total_count'] or 0
        ])
    
    output.seek(0)
    
    filename = f"route_{route_id}_analytics.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )