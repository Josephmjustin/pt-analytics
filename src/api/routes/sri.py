from fastapi import APIRouter, HTTPException, Query
from src.api.database import get_db_connection
from src.api.operator_context import get_current_operator, apply_operator_filter
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/sri", tags=["sri"])

@router.get("/network")
def get_network_sri(
    year: Optional[int] = None,
    month: Optional[int] = None
):
    """Get network-level SRI summary"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Use current year/month if not specified
    if year is None or month is None:
        now = datetime.now()
        year = year or now.year
        month = month or now.month
    
    # Get current operator context
    operator = get_current_operator()
    
    # Get most recent network aggregate for specified period
    # Using monthly aggregates (day_of_week=NULL, hour=NULL)
    base_query = """
        SELECT 
            network_name,
            network_sri_score,
            network_grade,
            total_routes,
            routes_grade_a,
            routes_grade_b,
            routes_grade_c,
            routes_grade_d,
            routes_grade_f,
            avg_headway_score,
            avg_schedule_score,
            avg_journey_time_score,
            avg_service_delivery_score,
            calculation_timestamp
        FROM network_reliability_index
        WHERE year = %s 
            AND month = %s
            AND day_of_week IS NULL
            AND hour IS NULL
        ORDER BY calculation_timestamp DESC
        LIMIT 1
    """
    
    # Apply operator filter for non-transport-authority users
    # Transport authority sees network-wide, operators see only their data
    params = [year, month]
    if operator.role == "operator":
        # For operators, we need to calculate network metrics from their routes only
        # This requires a different query that aggregates from service_reliability_index
        cur.execute("""
            SELECT 
                %s as network_name,
                ROUND(AVG(sri_score)::numeric, 1) as network_sri_score,
                CASE 
                    WHEN AVG(sri_score) >= 90 THEN 'A'
                    WHEN AVG(sri_score) >= 80 THEN 'B'
                    WHEN AVG(sri_score) >= 70 THEN 'C'
                    WHEN AVG(sri_score) >= 60 THEN 'D'
                    ELSE 'F'
                END as network_grade,
                COUNT(DISTINCT route_name) as total_routes,
                COUNT(*) FILTER (WHERE sri_grade = 'A') as routes_grade_a,
                COUNT(*) FILTER (WHERE sri_grade = 'B') as routes_grade_b,
                COUNT(*) FILTER (WHERE sri_grade = 'C') as routes_grade_c,
                COUNT(*) FILTER (WHERE sri_grade = 'D') as routes_grade_d,
                COUNT(*) FILTER (WHERE sri_grade = 'F') as routes_grade_f,
                ROUND(AVG(headway_consistency_score)::numeric, 1) as avg_headway_score,
                ROUND(AVG(schedule_adherence_score)::numeric, 1) as avg_schedule_score,
                ROUND(AVG(journey_time_consistency_score)::numeric, 1) as avg_journey_time_score,
                ROUND(AVG(service_delivery_score)::numeric, 1) as avg_service_delivery_score,
                MAX(calculation_timestamp) as calculation_timestamp
            FROM service_reliability_index
            WHERE year = %s 
                AND month = %s
                AND operator = %s
        """, (operator.operator_name, year, month, operator.operator_name))
    else:
        # Transport authority sees actual network aggregate
        cur.execute(base_query, params)
    
    result = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if not result:
        raise HTTPException(
            status_code=404, 
            detail=f"No network SRI data found for {year}-{month:02d}"
        )
    
    return result

@router.get("/routes")
def get_all_routes_sri(
    year: Optional[int] = None,
    month: Optional[int] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    grade: Optional[str] = None,
    limit: int = Query(default=100, le=1000)
):
    """Get all route-level SRI scores with optional filters"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Use current year/month if not specified
    if year is None or month is None:
        now = datetime.now()
        year = year or now.year
        month = month or now.month
    
    # Get current operator context
    operator = get_current_operator()
    
    # Build query with filters
    base_query = """
        SELECT 
            route_name,
            direction,
            operator,
            sri_score,
            sri_grade,
            headway_consistency_score,
            schedule_adherence_score,
            journey_time_consistency_score,
            service_delivery_score,
            observation_count,
            data_completeness,
            calculation_timestamp
        FROM service_reliability_index
        WHERE year = %s 
            AND month = %s
            AND day_of_week IS NULL
            AND hour IS NULL
    """
    
    params = [year, month]
    
    # Apply operator filter
    query, params = apply_operator_filter(base_query, params)
    
    if min_score is not None:
        query += " AND sri_score >= %s"
        params.append(min_score)
    
    if max_score is not None:
        query += " AND sri_score <= %s"
        params.append(max_score)
    
    if grade:
        query += " AND sri_grade = %s"
        params.append(grade.upper())
    
    query += " ORDER BY sri_score DESC LIMIT %s"
    params.append(limit)
    
    cur.execute(query, params)
    routes = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        "routes": routes,
        "count": len(routes),
        "year": year,
        "month": month
    }

@router.get("/routes/{route_name}")
def get_route_sri(
    route_name: str,
    year: Optional[int] = None,
    month: Optional[int] = None
):
    """Get SRI scores for a specific route (all operators/directions)"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Use current year/month if not specified
    if year is None or month is None:
        now = datetime.now()
        year = year or now.year
        month = month or now.month
    
    # Get current operator context
    operator = get_current_operator()
    
    # Get all variants of this route
    base_query = """
        SELECT 
            route_name,
            direction,
            operator,
            sri_score,
            sri_grade,
            headway_consistency_score,
            schedule_adherence_score,
            journey_time_consistency_score,
            service_delivery_score,
            observation_count,
            data_completeness,
            calculation_timestamp
        FROM service_reliability_index
        WHERE route_name = %s
            AND year = %s 
            AND month = %s
            AND day_of_week IS NULL
            AND hour IS NULL
        ORDER BY operator, direction
    """
    
    params = [route_name, year, month]
    query, params = apply_operator_filter(base_query, params)
    
    cur.execute(query, params)
    
    routes = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if not routes:
        raise HTTPException(
            status_code=404,
            detail=f"No SRI data found for route {route_name} in {year}-{month:02d}"
        )
    
    return {
        "route_name": route_name,
        "variants": routes,
        "year": year,
        "month": month
    }

@router.get("/routes/{route_name}/temporal")
def get_route_temporal_sri(
    route_name: str,
    operator_param: str,
    direction: str,
    year: Optional[int] = None,
    month: Optional[int] = None
):
    """
    Get temporal breakdown (hourly, daily) SRI scores for a specific route variant
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Use current year/month if not specified
    if year is None or month is None:
        now = datetime.now()
        year = year or now.year
        month = month or now.month
    
    # Get current operator context
    operator = get_current_operator()
    
    # Verify user can access this operator's data
    if not operator.can_access_operator(operator_param):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: Cannot view data for operator '{operator_param}'"
        )
    
    # Get hourly breakdown (averaged across all days)
    cur.execute("""
        SELECT 
            hour,
            AVG(sri_score) as avg_sri_score,
            AVG(headway_consistency_score) as avg_headway_score,
            AVG(schedule_adherence_score) as avg_schedule_score,
            AVG(journey_time_consistency_score) as avg_journey_score,
            AVG(service_delivery_score) as avg_delivery_score,
            SUM(observation_count) as total_observations
        FROM service_reliability_index
        WHERE route_name = %s
            AND operator = %s
            AND direction = %s
            AND year = %s 
            AND month = %s
            AND day_of_week IS NULL
            AND hour IS NOT NULL
        GROUP BY hour
        ORDER BY hour
    """, (route_name, operator_param, direction, year, month))
    
    hourly = cur.fetchall()
    
    # Get daily breakdown (averaged across all hours)
    cur.execute("""
        SELECT 
            day_of_week,
            AVG(sri_score) as avg_sri_score,
            AVG(headway_consistency_score) as avg_headway_score,
            AVG(schedule_adherence_score) as avg_schedule_score,
            AVG(journey_time_consistency_score) as avg_journey_score,
            AVG(service_delivery_score) as avg_delivery_score,
            SUM(observation_count) as total_observations
        FROM service_reliability_index
        WHERE route_name = %s
            AND operator = %s
            AND direction = %s
            AND year = %s 
            AND month = %s
            AND day_of_week IS NOT NULL
            AND hour IS NULL
        GROUP BY day_of_week
        ORDER BY day_of_week
    """, (route_name, operator_param, direction, year, month))
    
    daily = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        "route_name": route_name,
        "operator": operator_param,
        "direction": direction,
        "year": year,
        "month": month,
        "hourly": hourly,
        "daily": daily
    }

@router.get("/components/{component}")
def get_component_scores(
    component: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
    limit: int = Query(default=100, le=1000)
):
    """
    Get top/bottom performers for a specific component
    Components: headway, schedule, journey_time, service_delivery
    """
    # Map component to table
    table_map = {
        "headway": "headway_consistency_scores",
        "schedule": "schedule_adherence_scores",
        "journey_time": "journey_time_consistency_scores",
        "service_delivery": "service_delivery_scores"
    }
    
    if component not in table_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid component. Must be one of: {', '.join(table_map.keys())}"
        )
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Use current year/month if not specified
    if year is None or month is None:
        now = datetime.now()
        year = year or now.year
        month = month or now.month
    
    # Get current operator context
    operator = get_current_operator()
    
    table = table_map[component]
    
    base_query = f"""
        SELECT 
            route_name,
            direction,
            operator,
            score,
            grade,
            observation_count
        FROM {table}
        WHERE year = %s 
            AND month = %s
            AND day_of_week IS NULL
            AND hour IS NULL
        ORDER BY score DESC
        LIMIT %s
    """
    
    params = [year, month, limit]
    query, params = apply_operator_filter(base_query, params)
    
    cur.execute(query, params)
    
    results = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        "component": component,
        "routes": results,
        "count": len(results),
        "year": year,
        "month": month
    }

@router.get("/hotspots")
def get_hotspots(
    severity: Optional[str] = None,
    hotspot_type: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    limit: int = Query(default=50, le=500)
):
    """Get performance hotspots with optional filters"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Use current year/month if not specified
    if year is None or month is None:
        now = datetime.now()
        year = year or now.year
        month = month or now.month
    
    # Get current operator context
    operator = get_current_operator()
    
    base_query = """
        SELECT 
            hotspot_type,
            severity,
            route_name,
            direction,
            operator,
            stop_id,
            stop_name,
            primary_issue,
            issue_score,
            affected_metric,
            trend,
            last_updated
        FROM performance_hotspots
        WHERE year = %s AND month = %s
    """
    
    params = [year, month]
    
    if severity:
        query += " AND severity = %s"
        params.append(severity)
    
    if hotspot_type:
        query += " AND hotspot_type = %s"
        params.append(hotspot_type)
    
    base_query += " ORDER BY issue_score DESC LIMIT %s"
    params.append(limit)
    
    # Apply operator filter
    query, params = apply_operator_filter(base_query, params)
    
    cur.execute(query, params)
    hotspots = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        "hotspots": hotspots,
        "count": len(hotspots),
        "year": year,
        "month": month
    }
