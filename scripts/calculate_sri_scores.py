"""
Calculate SRI - Version 4
- All scores calculated on-the-fly from patterns tables
- No intermediate score tables
- Fixed table size with proper ON CONFLICT
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
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print(f"[{datetime.now()}] Calculating SRI scores...")
        print("="*60)
        
        # Get config weights and thresholds
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
        
        print(f"Using weights: H:{weights['headway']*100:.0f}% S:{weights['schedule']*100:.0f}% " +
              f"J:{weights['journey']*100:.0f}% D:{weights['service']*100:.0f}%\n")
        
        # ========================================================================
        # Step 1: Calculate Route SRI from component patterns (hourly granularity)
        # ========================================================================
        print("Step 1: Calculating route SRI from component patterns (hourly)...")
        cur.execute(f"""
        WITH component_scores AS (
            SELECT 
                COALESCE(hp.route_name, sa.route_name, jt.route_name) as route_name,
                COALESCE(hp.direction, sa.direction, jt.direction) as direction,
                COALESCE(hp.operator, sa.operator, jt.operator) as operator,
                COALESCE(hp.year, sa.year, jt.year) as year,
                COALESCE(hp.month, sa.month, jt.month) as month,
                COALESCE(hp.day_of_week, sa.day_of_week, jt.day_of_week) as day_of_week,
                COALESCE(hp.hour, sa.hour, jt.hour) as hour,
                
                -- Calculate headway score on-the-fly
                COALESCE(
                    GREATEST(0, LEAST(100,
                        100 - ((hp.coefficient_of_variation - {config[7]}) / ({config[8]} - {config[7]})) * 100
                    )),
                    50.0
                ) as headway_score,
                
                -- Calculate schedule score on-the-fly
                COALESCE(
                    GREATEST(0, LEAST(100,
                        ((sa.on_time_percentage - {config[10]}) / ({config[9]} - {config[10]})) * 100
                    )),
                    50.0
                ) as schedule_score,
                
                -- Calculate journey time score on-the-fly
                COALESCE(
                    GREATEST(0, LEAST(100,
                        100 - ((jt.coefficient_of_variation - {config[11]}) / ({config[12]} - {config[11]})) * 100
                    )),
                    50.0
                ) as journey_score,
                
                -- Service delivery: default 50 (network-level only, not route-level)
                50.0 as service_score,
                
                COALESCE(hp.observation_count, 0) + COALESCE(sa.observation_count, 0) + 
                COALESCE(jt.observation_count, 0) as total_observations,
                
                (CASE WHEN hp.coefficient_of_variation IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN sa.on_time_percentage IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN jt.coefficient_of_variation IS NOT NULL THEN 1 ELSE 0 END) * 33.3 as data_completeness
                
            FROM (
                -- Aggregate headway_patterns to route level
                SELECT 
                    route_name, direction, operator, year, month, day_of_week, hour,
                    AVG(coefficient_of_variation) as coefficient_of_variation,
                    SUM(observation_count) as observation_count
                FROM headway_patterns
                WHERE coefficient_of_variation IS NOT NULL
                GROUP BY route_name, direction, operator, year, month, day_of_week, hour
            ) hp
            FULL OUTER JOIN (
                -- Aggregate schedule_adherence_patterns to route level
                SELECT 
                    route_name, direction, operator, year, month, day_of_week, hour,
                    AVG(on_time_percentage) as on_time_percentage,
                    SUM(observation_count) as observation_count
                FROM schedule_adherence_patterns
                WHERE on_time_percentage IS NOT NULL
                GROUP BY route_name, direction, operator, year, month, day_of_week, hour
            ) sa
                ON hp.route_name = sa.route_name AND hp.direction = sa.direction
                AND hp.operator = sa.operator AND hp.year = sa.year AND hp.month = sa.month
                AND hp.day_of_week IS NOT DISTINCT FROM sa.day_of_week
                AND hp.hour IS NOT DISTINCT FROM sa.hour
            FULL OUTER JOIN (
                -- Aggregate journey_time_patterns to route level
                SELECT 
                    route_name, direction, operator, year, month, day_of_week, hour,
                    AVG(coefficient_of_variation) as coefficient_of_variation,
                    SUM(observation_count) as observation_count
                FROM journey_time_patterns
                WHERE coefficient_of_variation IS NOT NULL
                GROUP BY route_name, direction, operator, year, month, day_of_week, hour
            ) jt
                ON COALESCE(hp.route_name, sa.route_name) = jt.route_name
                AND COALESCE(hp.direction, sa.direction) = jt.direction
                AND COALESCE(hp.operator, sa.operator) = jt.operator
                AND COALESCE(hp.year, sa.year) = jt.year
                AND COALESCE(hp.month, sa.month) = jt.month
                AND COALESCE(hp.day_of_week, sa.day_of_week) IS NOT DISTINCT FROM jt.day_of_week
                AND COALESCE(hp.hour, sa.hour) IS NOT DISTINCT FROM jt.hour
        )
        INSERT INTO service_reliability_index (
            route_name, direction, operator, year, month, day_of_week, hour,
            headway_consistency_score, schedule_adherence_score, 
            journey_time_consistency_score, service_delivery_score,
            headway_weight, schedule_weight, journey_time_weight, service_delivery_weight,
            sri_score, sri_grade, observation_count, data_completeness
        )
        SELECT 
            route_name, direction, operator, year, month, day_of_week, hour,
            headway_score, schedule_score, journey_score, service_score,
            {weights['headway']}, {weights['schedule']}, {weights['journey']}, {weights['service']},
            (headway_score * {weights['headway']} + schedule_score * {weights['schedule']} +
             journey_score * {weights['journey']} + service_score * {weights['service']})::DECIMAL(5,2),
            CASE 
                WHEN (headway_score * {weights['headway']} + schedule_score * {weights['schedule']} +
                      journey_score * {weights['journey']} + service_score * {weights['service']}) >= 90 THEN 'A'
                WHEN (headway_score * {weights['headway']} + schedule_score * {weights['schedule']} +
                      journey_score * {weights['journey']} + service_score * {weights['service']}) >= 80 THEN 'B'
                WHEN (headway_score * {weights['headway']} + schedule_score * {weights['schedule']} +
                      journey_score * {weights['journey']} + service_score * {weights['service']}) >= 70 THEN 'C'
                WHEN (headway_score * {weights['headway']} + schedule_score * {weights['schedule']} +
                      journey_score * {weights['journey']} + service_score * {weights['service']}) >= 60 THEN 'D'
                ELSE 'F'
            END,
            total_observations, data_completeness
        FROM component_scores
        WHERE total_observations >= 10
        ON CONFLICT (route_name, direction, operator, year, month, day_of_week, hour)
        DO UPDATE SET
            headway_consistency_score = EXCLUDED.headway_consistency_score,
            schedule_adherence_score = EXCLUDED.schedule_adherence_score,
            journey_time_consistency_score = EXCLUDED.journey_time_consistency_score,
            service_delivery_score = EXCLUDED.service_delivery_score,
            sri_score = EXCLUDED.sri_score,
            sri_grade = EXCLUDED.sri_grade,
            observation_count = service_reliability_index.observation_count + EXCLUDED.observation_count,
            data_completeness = EXCLUDED.data_completeness,
            calculation_timestamp = NOW()
        """)
        route_count = cur.rowcount
        conn.commit()
        print(f"  ✓ Upserted {route_count:,} route SRI records (hourly)")
        
        # ========================================================================
        # Step 2: Create Route MONTHLY aggregates (DELETE + INSERT)
        # ========================================================================
        print("Step 2: Creating route monthly aggregates...")
        
        cur.execute("""
            DELETE FROM service_reliability_index 
            WHERE day_of_week IS NULL AND hour IS NULL
        """)
        deleted_routes = cur.rowcount
        
        cur.execute(f"""
        INSERT INTO service_reliability_index (
            route_name, direction, operator, year, month, day_of_week, hour,
            headway_consistency_score, schedule_adherence_score, 
            journey_time_consistency_score, service_delivery_score,
            headway_weight, schedule_weight, journey_time_weight, service_delivery_weight,
            sri_score, sri_grade, observation_count, data_completeness
        )
        SELECT 
            route_name, direction, operator, year, month, 
            NULL, NULL,
            ROUND(AVG(headway_consistency_score)::numeric, 2),
            ROUND(AVG(schedule_adherence_score)::numeric, 2),
            ROUND(AVG(journey_time_consistency_score)::numeric, 2),
            ROUND(AVG(service_delivery_score)::numeric, 2),
            {weights['headway']}, {weights['schedule']}, {weights['journey']}, {weights['service']},
            ROUND(AVG(sri_score)::numeric, 2),
            CASE 
                WHEN AVG(sri_score) >= 90 THEN 'A'
                WHEN AVG(sri_score) >= 80 THEN 'B'
                WHEN AVG(sri_score) >= 70 THEN 'C'
                WHEN AVG(sri_score) >= 60 THEN 'D'
                ELSE 'F'
            END,
            SUM(observation_count),
            ROUND(AVG(data_completeness)::numeric, 2)
        FROM service_reliability_index
        WHERE hour IS NOT NULL AND day_of_week IS NOT NULL
        GROUP BY route_name, direction, operator, year, month
        """)
        monthly_route_count = cur.rowcount
        conn.commit()
        print(f"  ✓ Deleted {deleted_routes}, inserted {monthly_route_count} route monthly aggregates")
        
        # ========================================================================
        # Step 3: Calculate Network SRI (hourly/daily with running average)
        # ========================================================================
        print("Step 3: Calculating network SRI (hourly/daily)...")
        cur.execute("""
        INSERT INTO network_reliability_index (
            network_name, year, month, day_of_week, hour,
            network_sri_score, network_grade, total_routes,
            routes_grade_a, routes_grade_b, routes_grade_c, routes_grade_d, routes_grade_f,
            avg_headway_score, avg_schedule_score, avg_journey_time_score, avg_service_delivery_score,
            observation_count
        )
        SELECT 
            'Merseyside', year, month, day_of_week, hour,
            ROUND(AVG(sri_score)::numeric, 2),
            CASE 
                WHEN AVG(sri_score) >= 90 THEN 'A'
                WHEN AVG(sri_score) >= 80 THEN 'B'
                WHEN AVG(sri_score) >= 70 THEN 'C'
                WHEN AVG(sri_score) >= 60 THEN 'D'
                ELSE 'F'
            END,
            COUNT(DISTINCT (route_name, direction, operator)),
            COUNT(*) FILTER (WHERE sri_grade = 'A'),
            COUNT(*) FILTER (WHERE sri_grade = 'B'),
            COUNT(*) FILTER (WHERE sri_grade = 'C'),
            COUNT(*) FILTER (WHERE sri_grade = 'D'),
            COUNT(*) FILTER (WHERE sri_grade = 'F'),
            ROUND(AVG(headway_consistency_score)::numeric, 1),
            ROUND(AVG(schedule_adherence_score)::numeric, 1),
            ROUND(AVG(journey_time_consistency_score)::numeric, 1),
            ROUND(AVG(service_delivery_score)::numeric, 1),
            SUM(observation_count)
        FROM service_reliability_index
        WHERE day_of_week IS NOT NULL AND hour IS NOT NULL
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
            observation_count = network_reliability_index.observation_count + EXCLUDED.observation_count,
            calculation_timestamp = NOW()
        """)
        network_count = cur.rowcount
        conn.commit()
        print(f"  ✓ Upserted {network_count:,} network records (hourly/daily)")
        
        # ========================================================================
        # Step 4: Create Network MONTHLY aggregate (DELETE + INSERT)
        # ========================================================================
        print("Step 4: Creating network monthly aggregate...")
        
        cur.execute("""
            DELETE FROM network_reliability_index 
            WHERE day_of_week IS NULL AND hour IS NULL
        """)
        deleted_network = cur.rowcount
        
        cur.execute("""
        INSERT INTO network_reliability_index (
            network_name, year, month, day_of_week, hour,
            network_sri_score, network_grade, total_routes,
            routes_grade_a, routes_grade_b, routes_grade_c, routes_grade_d, routes_grade_f,
            avg_headway_score, avg_schedule_score, avg_journey_time_score, avg_service_delivery_score,
            observation_count
        )
        SELECT 
            'Merseyside', year, month, NULL, NULL,
            ROUND(AVG(network_sri_score)::numeric, 2),
            CASE 
                WHEN AVG(network_sri_score) >= 90 THEN 'A'
                WHEN AVG(network_sri_score) >= 80 THEN 'B'
                WHEN AVG(network_sri_score) >= 70 THEN 'C'
                WHEN AVG(network_sri_score) >= 60 THEN 'D'
                ELSE 'F'
            END,
            MAX(total_routes),
            SUM(routes_grade_a),
            SUM(routes_grade_b),
            SUM(routes_grade_c),
            SUM(routes_grade_d),
            SUM(routes_grade_f),
            ROUND(AVG(avg_headway_score)::numeric, 1),
            ROUND(AVG(avg_schedule_score)::numeric, 1),
            ROUND(AVG(avg_journey_time_score)::numeric, 1),
            ROUND(AVG(avg_service_delivery_score)::numeric, 1),
            SUM(observation_count)
        FROM network_reliability_index
        WHERE day_of_week IS NOT NULL AND hour IS NOT NULL
        GROUP BY year, month
        """)
        monthly_network_count = cur.rowcount
        conn.commit()
        print(f"  ✓ Deleted {deleted_network}, inserted {monthly_network_count} network monthly aggregates")
        
        # ========================================================================
        # Summary
        # ========================================================================
        print("\n" + "="*60)
        print("SRI SUMMARY")
        print("="*60)
        
        cur.execute("""
            SELECT 
                year, month,
                network_sri_score,
                network_grade,
                total_routes,
                routes_grade_a,
                routes_grade_b,
                routes_grade_c,
                routes_grade_d,
                routes_grade_f
            FROM network_reliability_index
            WHERE day_of_week IS NULL AND hour IS NULL
            ORDER BY year DESC, month DESC
        """)
        results = cur.fetchall()
        
        for row in results:
            year, month, sri, grade, total, a, b, c, d, f = row
            print(f"\n{year}-{month:02d}: SRI {sri}/100 (Grade {grade})")
            print(f"  Routes: {total} | A:{a} B:{b} C:{c} D:{d} F:{f}")
        
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
