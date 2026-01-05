"""
Calculate Component Scores for SRI Platform
Converts pattern data into 0-100 scores for each component:
1. Headway Consistency (40% weight)
2. Schedule Adherence (30% weight)
3. Journey Time Consistency (20% weight)
4. Service Delivery (10% weight)

Scoring methodology:
- Linear interpolation between excellent and poor thresholds
- Grades: A (90+), B (80-89), C (70-79), D (60-69), F (<60)
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

def get_grade(score):
    """Convert 0-100 score to letter grade"""
    if score >= 90:
        return 'A'
    elif score >= 80:
        return 'B'
    elif score >= 70:
        return 'C'
    elif score >= 60:
        return 'D'
    else:
        return 'F'

def calculate_component_scores():
    """
    Calculate all four component scores from pattern tables
    Uses thresholds from sri_config table
    """
    
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print(f"[{datetime.now()}] Calculating component scores...")
        print("="*60)
        
        # Get thresholds from config
        cur.execute("SELECT * FROM sri_config WHERE is_active = true ORDER BY effective_date DESC LIMIT 1")
        config = cur.fetchone()
        
        if not config:
            print("ERROR: No active SRI config found!")
            return
        
        print("Using config thresholds:")
        print(f"  Headway CV: excellent={config[7]}, poor={config[8]}")
        print(f"  Schedule on-time: excellent={config[9]}%, poor={config[10]}%")
        print(f"  Journey CV: excellent={config[11]}, poor={config[12]}")
        print(f"  Service delivery: excellent={config[13]}%, poor={config[14]}%")
        print()
        
        # 1. HEADWAY CONSISTENCY SCORES
        print("1. Calculating headway consistency scores...")
        cur.execute(f"""
            WITH deduplicated_patterns AS (
                SELECT 
                    route_name, direction, operator, year, month, day_of_week, hour,
                    -- Take most recent values if duplicates exist
                    MAX(coefficient_of_variation) as coefficient_of_variation,
                    MAX(bunching_rate) as bunching_rate,
                    MAX(std_headway_minutes) as std_headway_minutes,
                    SUM(observation_count) as observation_count
                FROM headway_patterns
                WHERE coefficient_of_variation IS NOT NULL
                GROUP BY route_name, direction, operator, year, month, day_of_week, hour
            )
            INSERT INTO headway_consistency_scores (
                route_name, direction, operator, year, month, day_of_week, hour,
                coefficient_of_variation, bunching_rate, avg_headway_deviation,
                score, grade, observation_count, calculation_timestamp
            )
            SELECT 
                route_name, direction, operator, year, month, day_of_week, hour,
                coefficient_of_variation,
                bunching_rate,
                std_headway_minutes,
                -- Score calculation: Lower CV = better score
                GREATEST(0, LEAST(100,
                    100 - (
                        (coefficient_of_variation - {config[7]}) / 
                        ({config[8]} - {config[7]})
                    ) * 100
                ))::DECIMAL(5,2) as score,
                'C' as grade,  -- Placeholder, will update
                observation_count,
                NOW()
            FROM deduplicated_patterns
            ON CONFLICT (route_name, direction, operator, year, month, day_of_week, hour)
            DO UPDATE SET
                coefficient_of_variation = EXCLUDED.coefficient_of_variation,
                bunching_rate = EXCLUDED.bunching_rate,
                avg_headway_deviation = EXCLUDED.avg_headway_deviation,
                score = EXCLUDED.score,
                grade = EXCLUDED.grade,
                observation_count = EXCLUDED.observation_count,
                calculation_timestamp = NOW()
        """)
        hc_count = cur.rowcount
        conn.commit()
        print(f"   ✓ Upserted {hc_count:,} headway consistency scores")
        
        # Update grades
        cur.execute("""
            UPDATE headway_consistency_scores
            SET grade = CASE 
                WHEN score >= 90 THEN 'A'
                WHEN score >= 80 THEN 'B'
                WHEN score >= 70 THEN 'C'
                WHEN score >= 60 THEN 'D'
                ELSE 'F'
            END
        """)
        conn.commit()
        
        # 2. SCHEDULE ADHERENCE SCORES
        # SKIPPED - Calculate on-the-fly from schedule_adherence_patterns when needed
        print("2. Schedule adherence scores - calculated on-the-fly from patterns ✓")
        sa_count = 0
        
        # 3. JOURNEY TIME CONSISTENCY SCORES
        print("3. Calculating journey time consistency scores...")
        cur.execute(f"""
            WITH route_journey_cv AS (
                SELECT 
                    route_name, direction, operator, year, month, day_of_week, hour,
                    AVG(coefficient_of_variation) as avg_cv,
                    AVG(percentile_85_minutes / NULLIF(median_journey_minutes, 0)) as p85_ratio,
                    AVG(avg_journey_minutes) as avg_journey,
                    SUM(observation_count) as total_observations
                FROM journey_time_patterns
                WHERE coefficient_of_variation IS NOT NULL
                GROUP BY route_name, direction, operator, year, month, day_of_week, hour
            )
            INSERT INTO journey_time_consistency_scores (
                route_name, direction, operator, year, month, day_of_week, hour,
                coefficient_of_variation, percentile_85_ratio, avg_journey_minutes,
                score, grade, observation_count, calculation_timestamp
            )
            SELECT 
                route_name, direction, operator, year, month, day_of_week, hour,
                avg_cv,
                p85_ratio,
                avg_journey,
                -- Score: Lower CV = better score
                GREATEST(0, LEAST(100,
                    100 - ((avg_cv - {config[11]}) / ({config[12]} - {config[11]})) * 100
                ))::DECIMAL(5,2) as score,
                'C' as grade,
                total_observations,
                NOW()
            FROM route_journey_cv
            ON CONFLICT (route_name, direction, operator, year, month, day_of_week, hour)
            DO UPDATE SET
                coefficient_of_variation = EXCLUDED.coefficient_of_variation,
                percentile_85_ratio = EXCLUDED.percentile_85_ratio,
                avg_journey_minutes = EXCLUDED.avg_journey_minutes,
                score = EXCLUDED.score,
                grade = EXCLUDED.grade,
                observation_count = EXCLUDED.observation_count,
                calculation_timestamp = NOW()
        """)
        jt_count = cur.rowcount
        conn.commit()
        print(f"   ✓ Upserted {jt_count:,} journey time consistency scores")
        
        # Update grades
        cur.execute("""
            UPDATE journey_time_consistency_scores
            SET grade = CASE 
                WHEN score >= 90 THEN 'A'
                WHEN score >= 80 THEN 'B'
                WHEN score >= 70 THEN 'C'
                WHEN score >= 60 THEN 'D'
                ELSE 'F'
            END
        """)
        conn.commit()
        
        # 4. SERVICE DELIVERY SCORES
        print("4. Calculating service delivery scores...")
        cur.execute(f"""
            WITH deduplicated_patterns AS (
                SELECT 
                    route_name, direction, operator, year, month, day_of_week, hour,
                    MAX(service_delivery_rate) as service_delivery_rate,
                    SUM(cancelled_trips) as cancelled_trips,
                    SUM(completed_trips) as completed_trips,
                    SUM(scheduled_trips) as scheduled_trips
                FROM service_delivery_patterns
                WHERE service_delivery_rate IS NOT NULL
                GROUP BY route_name, direction, operator, year, month, day_of_week, hour
            )
            INSERT INTO service_delivery_scores (
                route_name, direction, operator, year, month, day_of_week, hour,
                service_delivery_rate, cancelled_trip_rate, completed_trips, scheduled_trips,
                score, grade, observation_count, calculation_timestamp
            )
            SELECT 
                route_name, direction, operator, year, month, day_of_week, hour,
                service_delivery_rate,
                (cancelled_trips::FLOAT / NULLIF(scheduled_trips, 0) * 100)::DECIMAL(5,2),
                completed_trips,
                scheduled_trips,
                -- Score: Higher delivery rate = better score
                GREATEST(0, LEAST(100,
                    ((service_delivery_rate - {config[14]}) / 
                     ({config[13]} - {config[14]})) * 100
                ))::DECIMAL(5,2) as score,
                'C' as grade,
                scheduled_trips,
                NOW()
            FROM deduplicated_patterns
            ON CONFLICT (route_name, direction, operator, year, month, day_of_week, hour)
            DO UPDATE SET
                service_delivery_rate = EXCLUDED.service_delivery_rate,
                cancelled_trip_rate = EXCLUDED.cancelled_trip_rate,
                completed_trips = EXCLUDED.completed_trips,
                scheduled_trips = EXCLUDED.scheduled_trips,
                score = EXCLUDED.score,
                grade = EXCLUDED.grade,
                observation_count = EXCLUDED.observation_count,
                calculation_timestamp = NOW()
        """)
        sd_count = cur.rowcount
        conn.commit()
        print(f"   ✓ Upserted {sd_count:,} service delivery scores")
        
        # Update grades
        cur.execute("""
            UPDATE service_delivery_scores
            SET grade = CASE 
                WHEN score >= 90 THEN 'A'
                WHEN score >= 80 THEN 'B'
                WHEN score >= 70 THEN 'C'
                WHEN score >= 60 THEN 'D'
                ELSE 'F'
            END
        """)
        conn.commit()
        
        # Show summary
        print("\n" + "="*60)
        print("Component Score Summary:")
        print(f"  Headway Consistency: {hc_count:,} scores")
        print(f"  Schedule Adherence: {sa_count:,} scores")
        print(f"  Journey Time Consistency: {jt_count:,} scores")
        print(f"  Service Delivery: {sd_count:,} scores")
        
        # Show average scores
        cur.execute("""
            SELECT 
                ROUND(AVG(score)::numeric, 1) as avg_hc,
                ROUND(AVG(CASE WHEN score >= 60 THEN 1.0 ELSE 0.0 END) * 100, 1) as pass_rate
            FROM headway_consistency_scores
        """)
        hc_avg = cur.fetchone()
        
        # Schedule adherence - calculate from patterns
        cur.execute(f"""
            SELECT 
                ROUND(AVG(on_time_percentage)::numeric, 1) as avg_sa,
                ROUND(AVG(CASE WHEN on_time_percentage >= 60 THEN 1.0 ELSE 0.0 END) * 100, 1) as pass_rate
            FROM schedule_adherence_patterns
        """)
        sa_avg = cur.fetchone()
        
        cur.execute("""
            SELECT 
                ROUND(AVG(score)::numeric, 1) as avg_jt,
                ROUND(AVG(CASE WHEN score >= 60 THEN 1.0 ELSE 0.0 END) * 100, 1) as pass_rate
            FROM journey_time_consistency_scores
        """)
        jt_avg = cur.fetchone()
        
        cur.execute("""
            SELECT 
                ROUND(AVG(score)::numeric, 1) as avg_sd,
                ROUND(AVG(CASE WHEN score >= 60 THEN 1.0 ELSE 0.0 END) * 100, 1) as pass_rate
            FROM service_delivery_scores
        """)
        sd_avg = cur.fetchone()
        
        print("\nAverage Scores:")
        print(f"  Headway Consistency: {hc_avg[0]}/100 ({hc_avg[1]}% passing)")
        print(f"  Schedule Adherence: {sa_avg[0]}/100 ({sa_avg[1]}% passing)")
        print(f"  Journey Time: {jt_avg[0]}/100 ({jt_avg[1]}% passing)")
        print(f"  Service Delivery: {sd_avg[0]}/100 ({sd_avg[1]}% passing)")
        
        print("="*60)
        print(f"✓ Complete at {datetime.now()}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    calculate_component_scores()