"""
Quick fix: Create monthly and daily aggregates from existing hourly data
Run this after calculate_sri_scores.py to create monthly/daily rollups
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

def create_monthly_daily_aggregates():
    """
    Create monthly and daily aggregates from hourly SRI data
    This is needed because component scores only exist at hourly level
    """
    
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print(f"[{datetime.now()}] Creating monthly/daily aggregates...")
        print("="*60)
        
        # ========================================================================
        # 1. Create DAILY aggregates (from hourly data)
        # ========================================================================
        print("\n1. Creating daily aggregates from hourly data...")
        cur.execute("""
        INSERT INTO service_reliability_index (
            route_name, direction, operator, year, month, day_of_week, hour,
            headway_consistency_score, schedule_adherence_score,
            journey_time_consistency_score, service_delivery_score,
            headway_weight, schedule_weight, journey_time_weight, service_delivery_weight,
            sri_score, sri_grade, observation_count, data_completeness
        )
        SELECT 
            route_name,
            direction,
            operator,
            year,
            month,
            day_of_week,
            NULL as hour,  -- Daily aggregate has NULL hour
            
            ROUND(AVG(headway_consistency_score)::numeric, 2),
            ROUND(AVG(schedule_adherence_score)::numeric, 2),
            ROUND(AVG(journey_time_consistency_score)::numeric, 2),
            ROUND(AVG(service_delivery_score)::numeric, 2),
            
            AVG(headway_weight),
            AVG(schedule_weight),
            AVG(journey_time_weight),
            AVG(service_delivery_weight),
            
            ROUND(AVG(sri_score)::numeric, 2),
            CASE 
                WHEN AVG(sri_score) >= 90 THEN 'A'
                WHEN AVG(sri_score) >= 80 THEN 'B'
                WHEN AVG(sri_score) >= 70 THEN 'C'
                WHEN AVG(sri_score) >= 60 THEN 'D'
                ELSE 'F'
            END,
            
            SUM(observation_count),
            AVG(data_completeness)
            
        FROM service_reliability_index
        WHERE day_of_week IS NOT NULL 
          AND hour IS NOT NULL  -- Aggregate from hourly data
        GROUP BY route_name, direction, operator, year, month, day_of_week
        ON CONFLICT (route_name, direction, operator, year, month, day_of_week, hour)
        DO UPDATE SET
            headway_consistency_score = EXCLUDED.headway_consistency_score,
            schedule_adherence_score = EXCLUDED.schedule_adherence_score,
            journey_time_consistency_score = EXCLUDED.journey_time_consistency_score,
            service_delivery_score = EXCLUDED.service_delivery_score,
            sri_score = EXCLUDED.sri_score,
            sri_grade = EXCLUDED.sri_grade,
            observation_count = EXCLUDED.observation_count,
            calculation_timestamp = NOW()
        """)
        daily_count = cur.rowcount
        conn.commit()
        print(f"   ✓ Created {daily_count:,} daily aggregates")
        
        # ========================================================================
        # 2. Create MONTHLY aggregates (from daily data)
        # ========================================================================
        print("\n2. Creating monthly aggregates from daily data...")
        cur.execute("""
        INSERT INTO service_reliability_index (
            route_name, direction, operator, year, month, day_of_week, hour,
            headway_consistency_score, schedule_adherence_score,
            journey_time_consistency_score, service_delivery_score,
            headway_weight, schedule_weight, journey_time_weight, service_delivery_weight,
            sri_score, sri_grade, observation_count, data_completeness
        )
        SELECT 
            route_name,
            direction,
            operator,
            year,
            month,
            NULL as day_of_week,  -- Monthly aggregate has NULL day_of_week
            NULL as hour,         -- and NULL hour
            
            ROUND(AVG(headway_consistency_score)::numeric, 2),
            ROUND(AVG(schedule_adherence_score)::numeric, 2),
            ROUND(AVG(journey_time_consistency_score)::numeric, 2),
            ROUND(AVG(service_delivery_score)::numeric, 2),
            
            AVG(headway_weight),
            AVG(schedule_weight),
            AVG(journey_time_weight),
            AVG(service_delivery_weight),
            
            ROUND(AVG(sri_score)::numeric, 2),
            CASE 
                WHEN AVG(sri_score) >= 90 THEN 'A'
                WHEN AVG(sri_score) >= 80 THEN 'B'
                WHEN AVG(sri_score) >= 70 THEN 'C'
                WHEN AVG(sri_score) >= 60 THEN 'D'
                ELSE 'F'
            END,
            
            SUM(observation_count),
            AVG(data_completeness)
            
        FROM service_reliability_index
        WHERE day_of_week IS NOT NULL 
          AND hour IS NULL  -- Aggregate from daily data
        GROUP BY route_name, direction, operator, year, month
        ON CONFLICT (route_name, direction, operator, year, month, day_of_week, hour)
        DO UPDATE SET
            headway_consistency_score = EXCLUDED.headway_consistency_score,
            schedule_adherence_score = EXCLUDED.schedule_adherence_score,
            journey_time_consistency_score = EXCLUDED.journey_time_consistency_score,
            service_delivery_score = EXCLUDED.service_delivery_score,
            sri_score = EXCLUDED.sri_score,
            sri_grade = EXCLUDED.sri_grade,
            observation_count = EXCLUDED.observation_count,
            calculation_timestamp = NOW()
        """)
        monthly_count = cur.rowcount
        conn.commit()
        print(f"   ✓ Created {monthly_count:,} monthly aggregates")
        
        # ========================================================================
        # 3. Create NETWORK aggregates (all granularities)
        # ========================================================================
        print("\n3. Creating network aggregates...")
        
        # Network hourly
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
            observation_count = EXCLUDED.observation_count,
            calculation_timestamp = NOW()
        """)
        network_count = cur.rowcount
        conn.commit()
        print(f"   ✓ Created {network_count:,} network aggregate records")
        
        # ========================================================================
        # Summary
        # ========================================================================
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        
        cur.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE day_of_week IS NULL AND hour IS NULL) as monthly,
                COUNT(*) FILTER (WHERE day_of_week IS NOT NULL AND hour IS NULL) as daily,
                COUNT(*) FILTER (WHERE day_of_week IS NOT NULL AND hour IS NOT NULL) as hourly,
                COUNT(*) as total
            FROM service_reliability_index
        """)
        counts = cur.fetchone()
        
        print(f"\nService Reliability Index:")
        print(f"  Monthly: {counts[0]:,}")
        print(f"  Daily: {counts[1]:,}")
        print(f"  Hourly: {counts[2]:,}")
        print(f"  Total: {counts[3]:,}")
        
        # Show network monthly
        cur.execute("""
            SELECT 
                network_sri_score,
                network_grade,
                total_routes
            FROM network_reliability_index
            WHERE day_of_week IS NULL AND hour IS NULL
            ORDER BY calculation_timestamp DESC
            LIMIT 1
        """)
        network = cur.fetchone()
        
        if network:
            print(f"\nNetwork SRI (Monthly): {network[0]}/100 (Grade: {network[1]})")
            print(f"Total routes: {network[2]}")
        
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
    create_monthly_daily_aggregates()
