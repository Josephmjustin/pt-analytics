"""
Calculate Service Reliability Index (SRI) - Final Scores
Combines 4 component scores into final 0-100 SRI score with letter grade

Weighting (default):
- Headway Consistency: 40%
- Schedule Adherence: 30%
- Journey Time Consistency: 20%
- Service Delivery: 10%

Outputs:
- service_reliability_index: Route-level SRI scores
- network_reliability_index: Network-wide aggregates
"""

import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'pt_analytics'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD')
}

def calculate_sri_scores():
    """
    Calculate final SRI scores from component scores
    Applies weighted combination based on sri_config
    """
    
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print(f"[{datetime.now()}] Calculating SRI scores...")
        print("="*60)
        
        # Get config weights
        cur.execute("SELECT * FROM sri_config WHERE is_active = true ORDER BY effective_date DESC LIMIT 1")
        config = cur.fetchone()
        
        if not config:
            print("ERROR: No active SRI config found!")
            return
        
        weights = {
            'headway': config[3],
            'schedule': config[4],
            'journey': config[5],
            'service': config[6]
        }
        
        print(f"Using weights from config v{config[1]}:")
        print(f"  Headway Consistency: {weights['headway']*100}%")
        print(f"  Schedule Adherence: {weights['schedule']*100}%")
        print(f"  Journey Time: {weights['journey']*100}%")
        print(f"  Service Delivery: {weights['service']*100}%")
        print()
        
        # Calculate SRI by combining all component scores
        print("Calculating route-level SRI scores...")
        query = f"""
        WITH component_scores AS (
            SELECT 
                COALESCE(hc.route_name, sa.route_name, jt.route_name, sd.route_name) as route_name,
                COALESCE(hc.direction, sa.direction, jt.direction, sd.direction) as direction,
                COALESCE(hc.operator, sa.operator, jt.operator, sd.operator) as operator,
                COALESCE(hc.year, sa.year, jt.year, sd.year) as year,
                COALESCE(hc.month, sa.month, jt.month, sd.month) as month,
                COALESCE(hc.day_of_week, sa.day_of_week, jt.day_of_week, sd.day_of_week) as day_of_week,
                COALESCE(hc.hour, sa.hour, jt.hour, sd.hour) as hour,
                
                -- Component scores
                COALESCE(hc.score, 50.0) as headway_score,
                COALESCE(sa.score, 50.0) as schedule_score,
                COALESCE(jt.score, 50.0) as journey_score,
                COALESCE(sd.score, 50.0) as service_score,
                
                -- Observation counts
                COALESCE(hc.observation_count, 0) + 
                COALESCE(sa.observation_count, 0) + 
                COALESCE(jt.observation_count, 0) + 
                COALESCE(sd.observation_count, 0) as total_observations,
                
                -- Data completeness (what % of components have data)
                (CASE WHEN hc.score IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN sa.score IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN jt.score IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN sd.score IS NOT NULL THEN 1 ELSE 0 END) * 25.0 as data_completeness
                
            FROM headway_consistency_scores hc
            FULL OUTER JOIN schedule_adherence_scores sa 
                ON hc.route_name = sa.route_name 
                AND hc.direction = sa.direction
                AND hc.operator = sa.operator
                AND hc.year = sa.year 
                AND hc.month = sa.month
                AND hc.day_of_week IS NOT DISTINCT FROM sa.day_of_week
                AND hc.hour IS NOT DISTINCT FROM sa.hour
            FULL OUTER JOIN journey_time_consistency_scores jt
                ON COALESCE(hc.route_name, sa.route_name) = jt.route_name
                AND COALESCE(hc.direction, sa.direction) = jt.direction
                AND COALESCE(hc.operator, sa.operator) = jt.operator
                AND COALESCE(hc.year, sa.year) = jt.year
                AND COALESCE(hc.month, sa.month) = jt.month
                AND COALESCE(hc.day_of_week, sa.day_of_week) IS NOT DISTINCT FROM jt.day_of_week
                AND COALESCE(hc.hour, sa.hour) IS NOT DISTINCT FROM jt.hour
            FULL OUTER JOIN service_delivery_scores sd
                ON COALESCE(hc.route_name, sa.route_name, jt.route_name) = sd.route_name
                AND COALESCE(hc.direction, sa.direction, jt.direction) = sd.direction
                AND COALESCE(hc.operator, sa.operator, jt.operator) = sd.operator
                AND COALESCE(hc.year, sa.year, jt.year) = sd.year
                AND COALESCE(hc.month, sa.month, jt.month) = sd.month
                AND COALESCE(hc.day_of_week, sa.day_of_week, jt.day_of_week) IS NOT DISTINCT FROM sd.day_of_week
                AND COALESCE(hc.hour, sa.hour, jt.hour) IS NOT DISTINCT FROM sd.hour
        )
        INSERT INTO service_reliability_index (
            route_name, direction, operator, year, month, day_of_week, hour,
            headway_consistency_score, schedule_adherence_score, 
            journey_time_consistency_score, service_delivery_score,
            headway_weight, schedule_weight, journey_time_weight, service_delivery_weight,
            sri_score, sri_grade,
            observation_count, data_completeness,
            calculation_timestamp
        )
        SELECT 
            route_name, direction, operator, year, month, day_of_week, hour,
            headway_score, schedule_score, journey_score, service_score,
            {weights['headway']}, {weights['schedule']}, {weights['journey']}, {weights['service']},
            -- Weighted SRI calculation
            (headway_score * {weights['headway']} +
             schedule_score * {weights['schedule']} +
             journey_score * {weights['journey']} +
             service_score * {weights['service']})::DECIMAL(5,2) as sri_score,
            -- Letter grade
            CASE 
                WHEN (headway_score * {weights['headway']} +
                      schedule_score * {weights['schedule']} +
                      journey_score * {weights['journey']} +
                      service_score * {weights['service']}) >= 90 THEN 'A'
                WHEN (headway_score * {weights['headway']} +
                      schedule_score * {weights['schedule']} +
                      journey_score * {weights['journey']} +
                      service_score * {weights['service']}) >= 80 THEN 'B'
                WHEN (headway_score * {weights['headway']} +
                      schedule_score * {weights['schedule']} +
                      journey_score * {weights['journey']} +
                      service_score * {weights['service']}) >= 70 THEN 'C'
                WHEN (headway_score * {weights['headway']} +
                      schedule_score * {weights['schedule']} +
                      journey_score * {weights['journey']} +
                      service_score * {weights['service']}) >= 60 THEN 'D'
                ELSE 'F'
            END as sri_grade,
            total_observations,
            data_completeness,
            NOW()
        FROM component_scores
        WHERE total_observations >= 10  -- Need sufficient data
        ON CONFLICT (route_name, direction, operator, year, month, day_of_week, hour)
        DO UPDATE SET
            headway_consistency_score = EXCLUDED.headway_consistency_score,
            schedule_adherence_score = EXCLUDED.schedule_adherence_score,
            journey_time_consistency_score = EXCLUDED.journey_time_consistency_score,
            service_delivery_score = EXCLUDED.service_delivery_score,
            sri_score = EXCLUDED.sri_score,
            sri_grade = EXCLUDED.sri_grade,
            observation_count = EXCLUDED.observation_count,
            data_completeness = EXCLUDED.data_completeness,
            calculation_timestamp = NOW()
        """
        
        cur.execute(query)
        sri_count = cur.rowcount
        conn.commit()
        print(f"✓ Upserted {sri_count:,} SRI scores")
        
        # Calculate network-level aggregates (granular - every hour/day)
        print("\nCalculating network-level aggregates (hourly/daily)...")
        cur.execute("""
            INSERT INTO network_reliability_index (
                network_name, year, month, day_of_week, hour,
                network_sri_score, network_grade,
                total_routes,
                routes_grade_a, routes_grade_b, routes_grade_c, routes_grade_d, routes_grade_f,
                avg_headway_score, avg_schedule_score, avg_journey_time_score, avg_service_delivery_score,
                calculation_timestamp
            )
            SELECT 
                'Merseyside' as network_name,
                year, month, day_of_week, hour,
                ROUND(AVG(sri_score)::numeric, 2) as network_sri,
                CASE 
                    WHEN AVG(sri_score) >= 90 THEN 'A'
                    WHEN AVG(sri_score) >= 80 THEN 'B'
                    WHEN AVG(sri_score) >= 70 THEN 'C'
                    WHEN AVG(sri_score) >= 60 THEN 'D'
                    ELSE 'F'
                END as network_grade,
                COUNT(DISTINCT (route_name, direction, operator)) as total_routes,
                COUNT(*) FILTER (WHERE sri_grade = 'A') as grade_a,
                COUNT(*) FILTER (WHERE sri_grade = 'B') as grade_b,
                COUNT(*) FILTER (WHERE sri_grade = 'C') as grade_c,
                COUNT(*) FILTER (WHERE sri_grade = 'D') as grade_d,
                COUNT(*) FILTER (WHERE sri_grade = 'F') as grade_f,
                ROUND(AVG(headway_consistency_score)::numeric, 1) as avg_headway,
                ROUND(AVG(schedule_adherence_score)::numeric, 1) as avg_schedule,
                ROUND(AVG(journey_time_consistency_score)::numeric, 1) as avg_journey,
                ROUND(AVG(service_delivery_score)::numeric, 1) as avg_service,
                NOW()
            FROM service_reliability_index
            GROUP BY year, month, day_of_week, hour
            ON CONFLICT (network_name, year, month, day_of_week, hour)
            DO UPDATE SET
                network_sri_score = EXCLUDED.network_sri_score,
                network_grade = EXCLUDED.network_grade,
                total_routes = EXCLUDED.total_routes,
                routes_grade_a = EXCLUDED.routes_grade_a,
                routes_grade_b = EXCLUDED.routes_grade_b,
                routes_grade_c = EXCLUDED.routes_grade_c,
                routes_grade_d = EXCLUDED.routes_grade_d,
                routes_grade_f = EXCLUDED.routes_grade_f,
                avg_headway_score = EXCLUDED.avg_headway_score,
                avg_schedule_score = EXCLUDED.avg_schedule_score,
                avg_journey_time_score = EXCLUDED.avg_journey_time_score,
                avg_service_delivery_score = EXCLUDED.avg_service_delivery_score,
                calculation_timestamp = NOW()
        """)
        network_count = cur.rowcount
        conn.commit()
        print(f"✓ Upserted {network_count:,} hourly/daily network records")
        
        # Calculate MONTHLY aggregates (day_of_week=NULL, hour=NULL) - THIS IS WHAT API NEEDS
        print("\nCalculating monthly aggregates (for API)...")
        cur.execute("""
            INSERT INTO network_reliability_index (
                network_name, year, month, day_of_week, hour,
                network_sri_score, network_grade,
                total_routes,
                routes_grade_a, routes_grade_b, routes_grade_c, routes_grade_d, routes_grade_f,
                avg_headway_score, avg_schedule_score, avg_journey_time_score, avg_service_delivery_score,
                calculation_timestamp
            )
            SELECT 
                'Merseyside' as network_name,
                year, month, 
                NULL as day_of_week,  -- Monthly aggregate
                NULL as hour,         -- Monthly aggregate
                ROUND(AVG(sri_score)::numeric, 2) as network_sri,
                CASE 
                    WHEN AVG(sri_score) >= 90 THEN 'A'
                    WHEN AVG(sri_score) >= 80 THEN 'B'
                    WHEN AVG(sri_score) >= 70 THEN 'C'
                    WHEN AVG(sri_score) >= 60 THEN 'D'
                    ELSE 'F'
                END as network_grade,
                COUNT(DISTINCT (route_name, direction, operator)) as total_routes,
                COUNT(*) FILTER (WHERE sri_grade = 'A') as grade_a,
                COUNT(*) FILTER (WHERE sri_grade = 'B') as grade_b,
                COUNT(*) FILTER (WHERE sri_grade = 'C') as grade_c,
                COUNT(*) FILTER (WHERE sri_grade = 'D') as grade_d,
                COUNT(*) FILTER (WHERE sri_grade = 'F') as grade_f,
                ROUND(AVG(headway_consistency_score)::numeric, 1) as avg_headway,
                ROUND(AVG(schedule_adherence_score)::numeric, 1) as avg_schedule,
                ROUND(AVG(journey_time_consistency_score)::numeric, 1) as avg_journey,
                ROUND(AVG(service_delivery_score)::numeric, 1) as avg_service,
                NOW()
            FROM service_reliability_index
            WHERE day_of_week IS NULL AND hour IS NULL  -- Only use monthly route data
            GROUP BY year, month
            ON CONFLICT (network_name, year, month, day_of_week, hour)
            DO UPDATE SET
                network_sri_score = EXCLUDED.network_sri_score,
                network_grade = EXCLUDED.network_grade,
                total_routes = EXCLUDED.total_routes,
                routes_grade_a = EXCLUDED.routes_grade_a,
                routes_grade_b = EXCLUDED.routes_grade_b,
                routes_grade_c = EXCLUDED.routes_grade_c,
                routes_grade_d = EXCLUDED.routes_grade_d,
                routes_grade_f = EXCLUDED.routes_grade_f,
                avg_headway_score = EXCLUDED.avg_headway_score,
                avg_schedule_score = EXCLUDED.avg_schedule_score,
                avg_journey_time_score = EXCLUDED.avg_journey_time_score,
                avg_service_delivery_score = EXCLUDED.avg_service_delivery_score,
                calculation_timestamp = NOW()
        """)
        monthly_count = cur.rowcount
        conn.commit()
        print(f"✓ Upserted {monthly_count:,} monthly network records")
        
        # Calculate DAILY aggregates (hour=NULL only)
        print("\nCalculating daily aggregates...")
        cur.execute("""
            INSERT INTO network_reliability_index (
                network_name, year, month, day_of_week, hour,
                network_sri_score, network_grade,
                total_routes,
                routes_grade_a, routes_grade_b, routes_grade_c, routes_grade_d, routes_grade_f,
                avg_headway_score, avg_schedule_score, avg_journey_time_score, avg_service_delivery_score,
                calculation_timestamp
            )
            SELECT 
                'Merseyside' as network_name,
                year, month, day_of_week,
                NULL as hour,  -- Daily aggregate (averaged across hours)
                ROUND(AVG(sri_score)::numeric, 2) as network_sri,
                CASE 
                    WHEN AVG(sri_score) >= 90 THEN 'A'
                    WHEN AVG(sri_score) >= 80 THEN 'B'
                    WHEN AVG(sri_score) >= 70 THEN 'C'
                    WHEN AVG(sri_score) >= 60 THEN 'D'
                    ELSE 'F'
                END as network_grade,
                COUNT(DISTINCT (route_name, direction, operator)) as total_routes,
                COUNT(*) FILTER (WHERE sri_grade = 'A') as grade_a,
                COUNT(*) FILTER (WHERE sri_grade = 'B') as grade_b,
                COUNT(*) FILTER (WHERE sri_grade = 'C') as grade_c,
                COUNT(*) FILTER (WHERE sri_grade = 'D') as grade_d,
                COUNT(*) FILTER (WHERE sri_grade = 'F') as grade_f,
                ROUND(AVG(headway_consistency_score)::numeric, 1) as avg_headway,
                ROUND(AVG(schedule_adherence_score)::numeric, 1) as avg_schedule,
                ROUND(AVG(journey_time_consistency_score)::numeric, 1) as avg_journey,
                ROUND(AVG(service_delivery_score)::numeric, 1) as avg_service,
                NOW()
            FROM service_reliability_index
            WHERE hour IS NULL  -- Only use daily route data
            GROUP BY year, month, day_of_week
            ON CONFLICT (network_name, year, month, day_of_week, hour)
            DO UPDATE SET
                network_sri_score = EXCLUDED.network_sri_score,
                network_grade = EXCLUDED.network_grade,
                total_routes = EXCLUDED.total_routes,
                routes_grade_a = EXCLUDED.routes_grade_a,
                routes_grade_b = EXCLUDED.routes_grade_b,
                routes_grade_c = EXCLUDED.routes_grade_c,
                routes_grade_d = EXCLUDED.routes_grade_d,
                routes_grade_f = EXCLUDED.routes_grade_f,
                avg_headway_score = EXCLUDED.avg_headway_score,
                avg_schedule_score = EXCLUDED.avg_schedule_score,
                avg_journey_time_score = EXCLUDED.avg_journey_time_score,
                avg_service_delivery_score = EXCLUDED.avg_service_delivery_score,
                calculation_timestamp = NOW()
        """)
        daily_count = cur.rowcount
        conn.commit()
        print(f"✓ Upserted {daily_count:,} daily network records")
        
        # Show summary statistics
        print("\n" + "="*60)
        print("SRI SUMMARY")
        print("="*60)
        
        # Overall network score
        cur.execute("""
            SELECT 
                ROUND(AVG(sri_score)::numeric, 1) as avg_sri,
                network_grade,
                COUNT(DISTINCT (route_name, direction, operator)) as unique_services
            FROM service_reliability_index
            CROSS JOIN (
                SELECT network_grade 
                FROM network_reliability_index 
                ORDER BY calculation_timestamp DESC 
                LIMIT 1
            ) ng
            GROUP BY network_grade
        """)
        overall = cur.fetchone()
        print(f"\nOverall Network SRI: {overall[0]}/100 (Grade: {overall[1]})")
        print(f"Services analyzed: {overall[2]}")
        
        # Grade distribution
        cur.execute("""
            SELECT 
                sri_grade,
                COUNT(*) as count,
                ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 1) as percentage
            FROM service_reliability_index
            GROUP BY sri_grade
            ORDER BY sri_grade
        """)
        
        print("\nGrade Distribution:")
        for row in cur.fetchall():
            print(f"  Grade {row[0]}: {row[1]:,} services ({row[2]}%)")
        
        # Top 5 and bottom 5 routes
        print("\nTop 5 Routes:")
        cur.execute("""
            SELECT 
                route_name, direction, operator,
                ROUND(AVG(sri_score)::numeric, 1) as avg_sri,
                MODE() WITHIN GROUP (ORDER BY sri_grade) as most_common_grade
            FROM service_reliability_index
            GROUP BY route_name, direction, operator
            ORDER BY avg_sri DESC
            LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"  {row[0]} ({row[1]}) - {row[2]}: {row[3]}/100 (Grade: {row[4]})")
        
        print("\nBottom 5 Routes:")
        cur.execute("""
            SELECT 
                route_name, direction, operator,
                ROUND(AVG(sri_score)::numeric, 1) as avg_sri,
                MODE() WITHIN GROUP (ORDER BY sri_grade) as most_common_grade
            FROM service_reliability_index
            GROUP BY route_name, direction, operator
            ORDER BY avg_sri ASC
            LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"  {row[0]} ({row[1]}) - {row[2]}: {row[3]}/100 (Grade: {row[4]})")
        
        print("\n" + "="*60)
        print(f"✓ Complete at {datetime.now()}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    calculate_sri_scores()