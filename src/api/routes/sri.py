from fastapi import APIRouter, HTTPException, Query
from src.api.database import get_db_connection
from src.api.operator_context import get_current_operator, apply_operator_filter
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/sri", tags=["sri"])

# Normalize operator names to canonical form
OPERATOR_NORMALIZATION = {
    'Arriva Merseyside': 'Arriva',
    'Arriva Northwest': 'Arriva',
    'Arriva North West': 'Arriva',
    'ARRIVA NORTH WEST': 'Arriva',
    'Arriva Buses Wales': 'Arriva',
    'Stagecoach Merseyside': 'Stagecoach',
    'Stagecoach Merseyside and South Lancashire': 'Stagecoach',
}

def normalize_operator(operator: str) -> str:
    """Normalize operator name to canonical form"""
    return OPERATOR_NORMALIZATION.get(operator, operator)

@router.get("/network")
def get_network_sri(
    year: Optional[int] = None,
    month: Optional[int] = None
):
    """Get network-level SRI summary (monthly aggregate)"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Use current year/month if not specified
    if year is None or month is None:
        now = datetime.now()
        year = year or now.year
        month = month or now.month
    
    # Get current operator context
    operator = get_current_operator()
    
    # Monthly aggregate query (day_of_week=NULL, hour=NULL)
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
    
    params = [year, month]
    
    if operator.role == "operator":
        # For operators, calculate from their routes
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
                AND day_of_week IS NULL
                AND hour IS NULL
                AND operator = %s
        """, (operator.operator_name, year, month, operator.operator_name))
    else:
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
    """Get all route-level SRI scores (monthly aggregates)"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if year is None or month is None:
        now = datetime.now()
        year = year or now.year
        month = month or now.month
    
    operator = get_current_operator()
    
    # Query monthly aggregates with deduplication
    # Group by normalized operator name and take the best data quality entry
    base_query = """
        WITH normalized_routes AS (
            SELECT 
                route_name,
                direction,
                CASE 
                    WHEN operator IN ('Arriva Merseyside', 'Arriva Northwest', 'Arriva North West', 'ARRIVA NORTH WEST', 'Arriva Buses Wales') THEN 'Arriva'
                    WHEN operator IN ('Stagecoach Merseyside', 'Stagecoach Merseyside and South Lancashire') THEN 'Stagecoach'
                    ELSE operator
                END as operator,
                sri_score,
                sri_grade,
                headway_consistency_score,
                schedule_adherence_score,
                journey_time_consistency_score,
                service_delivery_score,
                observation_count,
                data_completeness,
                calculation_timestamp,
                ROW_NUMBER() OVER (
                    PARTITION BY route_name, direction, 
                    CASE 
                        WHEN operator IN ('Arriva Merseyside', 'Arriva Northwest', 'Arriva North West', 'ARRIVA NORTH WEST', 'Arriva Buses Wales') THEN 'Arriva'
                        WHEN operator IN ('Stagecoach Merseyside', 'Stagecoach Merseyside and South Lancashire') THEN 'Stagecoach'
                        ELSE operator
                    END
                    ORDER BY data_completeness DESC, observation_count DESC
                ) as rn
            FROM service_reliability_index
            WHERE year = %s 
                AND month = %s
                AND day_of_week IS NULL
                AND hour IS NULL
        )
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
        FROM normalized_routes
        WHERE rn = 1
    """
    
    params = [year, month]
    query = base_query
    
    # Apply operator filter for non-TA users
    if operator.role == "operator":
        query = f"""
            WITH normalized_routes AS (
                SELECT 
                    route_name,
                    direction,
                    CASE 
                        WHEN operator IN ('Arriva Merseyside', 'Arriva Northwest', 'Arriva North West', 'ARRIVA NORTH WEST', 'Arriva Buses Wales') THEN 'Arriva'
                        WHEN operator IN ('Stagecoach Merseyside', 'Stagecoach Merseyside and South Lancashire') THEN 'Stagecoach'
                        ELSE operator
                    END as operator,
                    sri_score,
                    sri_grade,
                    headway_consistency_score,
                    schedule_adherence_score,
                    journey_time_consistency_score,
                    service_delivery_score,
                    observation_count,
                    data_completeness,
                    calculation_timestamp,
                    ROW_NUMBER() OVER (
                        PARTITION BY route_name, direction, 
                        CASE 
                            WHEN operator IN ('Arriva Merseyside', 'Arriva Northwest', 'Arriva North West', 'ARRIVA NORTH WEST', 'Arriva Buses Wales') THEN 'Arriva'
                            WHEN operator IN ('Stagecoach Merseyside', 'Stagecoach Merseyside and South Lancashire') THEN 'Stagecoach'
                            ELSE operator
                        END
                        ORDER BY data_completeness DESC, observation_count DESC
                    ) as rn
                FROM service_reliability_index
                WHERE year = %s 
                    AND month = %s
                    AND day_of_week IS NULL
                    AND hour IS NULL
                    AND operator = %s
            )
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
            FROM normalized_routes
            WHERE rn = 1
        """
        params.append(operator.operator_name)
    
    # Add score filters
    filters = []
    if min_score is not None:
        filters.append(f"sri_score >= %s")
        params.append(min_score)
    
    if max_score is not None:
        filters.append(f"sri_score <= %s")
        params.append(max_score)
    
    if grade:
        filters.append(f"sri_grade = %s")
        params.append(grade.upper())
    
    if filters:
        # Wrap query to apply filters
        query = f"SELECT * FROM ({query}) AS filtered WHERE {' AND '.join(filters)}"
    
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


@router.get("/routes/{route_name}/temporal")
def get_route_temporal_sri(
    route_name: str,
    operator_param: str,
    direction: str,
    year: Optional[int] = None,
    month: Optional[int] = None
):
    """Get hourly/daily breakdown for a route"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if year is None or month is None:
        now = datetime.now()
        year = year or now.year
        month = month or now.month
    
    operator = get_current_operator()
    
    if not operator.can_access_operator(operator_param):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Hourly breakdown
    cur.execute("""
        SELECT 
            hour,
            sri_score,
            observation_count
        FROM service_reliability_index
        WHERE route_name = %s
            AND operator = %s
            AND direction = %s
            AND year = %s 
            AND month = %s
            AND day_of_week IS NOT NULL
            AND hour IS NOT NULL
        ORDER BY day_of_week, hour
    """, (route_name, operator_param, direction, year, month))
    
    hourly = cur.fetchall()
    
    # Daily breakdown
    cur.execute("""
        SELECT 
            day_of_week,
            sri_score,
            observation_count
        FROM service_reliability_index
        WHERE route_name = %s
            AND operator = %s
            AND direction = %s
            AND year = %s 
            AND month = %s
            AND day_of_week IS NOT NULL
            AND hour IS NULL
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


@router.get("/operators/summary")
def get_operators_summary(
    year: Optional[int] = None,
    month: Optional[int] = None
):
    """
    Get operator-level performance summary (Transport Authority only)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    if year is None or month is None:
        now = datetime.now()
        year = year or now.year
        month = month or now.month
    
    operator = get_current_operator()
    
    if operator.role == "operator":
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only available to Transport Authority users"
        )
    
    # Get monthly aggregates grouped by normalized operator
    cur.execute("""
        WITH normalized_data AS (
            SELECT 
                CASE 
                    WHEN operator IN ('Arriva Merseyside', 'Arriva Northwest', 'Arriva North West', 'ARRIVA NORTH WEST', 'Arriva Buses Wales') THEN 'Arriva'
                    WHEN operator IN ('Stagecoach Merseyside', 'Stagecoach Merseyside and South Lancashire') THEN 'Stagecoach'
                    ELSE operator
                END as operator,
                route_name,
                direction,
                sri_score,
                sri_grade,
                headway_consistency_score,
                schedule_adherence_score,
                journey_time_consistency_score,
                service_delivery_score
            FROM service_reliability_index
            WHERE year = %s 
                AND month = %s
                AND day_of_week IS NULL
                AND hour IS NULL
        ),
        operator_stats AS (
            SELECT 
                operator,
                COUNT(DISTINCT route_name) as total_routes,
                ROUND(AVG(sri_score)::numeric, 2) as avg_sri_score,
                CASE 
                    WHEN AVG(sri_score) >= 90 THEN 'A'
                    WHEN AVG(sri_score) >= 80 THEN 'B'
                    WHEN AVG(sri_score) >= 70 THEN 'C'
                    WHEN AVG(sri_score) >= 60 THEN 'D'
                    ELSE 'F'
                END as avg_grade,
                
                COUNT(*) FILTER (WHERE sri_grade = 'A') as routes_grade_a,
                COUNT(*) FILTER (WHERE sri_grade = 'B') as routes_grade_b,
                COUNT(*) FILTER (WHERE sri_grade = 'C') as routes_grade_c,
                COUNT(*) FILTER (WHERE sri_grade = 'D') as routes_grade_d,
                COUNT(*) FILTER (WHERE sri_grade = 'F') as routes_grade_f,
                
                ROUND(AVG(headway_consistency_score)::numeric, 1) as avg_headway_score,
                ROUND(AVG(schedule_adherence_score)::numeric, 1) as avg_schedule_score,
                ROUND(AVG(journey_time_consistency_score)::numeric, 1) as avg_journey_time_score,
                ROUND(AVG(service_delivery_score)::numeric, 1) as avg_service_delivery_score,
                
                ROUND(MIN(sri_score)::numeric, 1) as worst_route_score,
                ROUND(MAX(sri_score)::numeric, 1) as best_route_score
                
            FROM normalized_data
            GROUP BY operator
        )
        SELECT * FROM operator_stats
        ORDER BY avg_sri_score DESC
    """, (year, month))
    
    operators = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        "operators": operators,
        "count": len(operators),
        "year": year,
        "month": month
    }


@router.get("/trends")
def get_sri_trends(
    year: Optional[int] = None,
    month: Optional[int] = None
):
    """
    Get network SRI trends - hourly, daily (day of week), and monthly
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    if year is None or month is None:
        now = datetime.now()
        year = year or now.year
        month = month or now.month
    
    operator = get_current_operator()
    
    # Hourly pattern (average SRI by hour of day)
    hourly_query = """
        SELECT 
            hour,
            ROUND(AVG(network_sri_score)::numeric, 1) as sri
        FROM network_reliability_index
        WHERE year = %s 
            AND month = %s
            AND day_of_week IS NOT NULL
            AND hour IS NOT NULL
        GROUP BY hour
        ORDER BY hour
    """
    
    cur.execute(hourly_query, (year, month))
    hourly_data = cur.fetchall()
    
    # Daily pattern (day of week)
    daily_query = """
        SELECT 
            day_of_week,
            ROUND(AVG(network_sri_score)::numeric, 1) as sri
        FROM network_reliability_index
        WHERE year = %s 
            AND month = %s
            AND day_of_week IS NOT NULL
            AND hour IS NULL
        GROUP BY day_of_week
        ORDER BY day_of_week
    """
    
    cur.execute(daily_query, (year, month))
    daily_data = cur.fetchall()
    
    # Monthly pattern (all available months)
    monthly_query = """
        SELECT 
            year,
            month,
            network_sri_score as sri
        FROM network_reliability_index
        WHERE day_of_week IS NULL
            AND hour IS NULL
        ORDER BY year, month
    """
    
    cur.execute(monthly_query)
    monthly_data = cur.fetchall()
    
    cur.close()
    conn.close()
    
    # Format hourly data
    day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    hourly_formatted = [
        {"time": f"{row['hour']:02d}:00", "sri": float(row['sri'])}
        for row in hourly_data
    ] if hourly_data else []
    
    daily_formatted = [
        {"time": day_names[row['day_of_week']], "sri": float(row['sri'])}
        for row in daily_data
    ] if daily_data else []
    
    monthly_formatted = [
        {"time": month_names[row['month'] - 1], "sri": float(row['sri']), "year": row['year']}
        for row in monthly_data
    ] if monthly_data else []
    
    return {
        "hourly": hourly_formatted,
        "daily": daily_formatted,
        "monthly": monthly_formatted,
        "year": year,
        "month": month,
        "has_data": len(hourly_formatted) > 0 or len(daily_formatted) > 0 or len(monthly_formatted) > 0
    }
