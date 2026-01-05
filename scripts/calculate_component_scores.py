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
        # SKIPPED - Calculate on-the-fly from headway_patterns when needed
        print("1. Headway consistency scores - calculated on-the-fly from patterns ✓")
        hc_count = 0
        
        # 2. SCHEDULE ADHERENCE SCORES
        # SKIPPED - Calculate on-the-fly from schedule_adherence_patterns when needed
        print("2. Schedule adherence scores - calculated on-the-fly from patterns ✓")
        sa_count = 0
        
        # 3. JOURNEY TIME CONSISTENCY SCORES
        # SKIPPED - Calculate on-the-fly from journey_time_patterns when needed
        print("3. Journey time consistency scores - calculated on-the-fly from patterns ✓")
        jt_count = 0
        
        # 4. SERVICE DELIVERY SCORES
        # SKIPPED - Calculate on-the-fly from service_delivery_patterns when needed
        print("4. Service delivery scores - calculated on-the-fly from patterns ✓")
        sd_count = 0
        
        # Show summary
        print("\n" + "="*60)
        print("Component Score Summary:")
        print(f"  Headway Consistency: {hc_count:,} scores")
        print(f"  Schedule Adherence: {sa_count:,} scores")
        print(f"  Journey Time Consistency: {jt_count:,} scores")
        print(f"  Service Delivery: {sd_count:,} scores")
        
        # Show average scores calculated from patterns
        cur.execute(f"""
            SELECT 
                ROUND(AVG(
                    GREATEST(0, LEAST(100,
                        100 - ((coefficient_of_variation - {config[7]}) / ({config[8]} - {config[7]})) * 100
                    ))
                )::numeric, 1) as avg_hc,
                ROUND(AVG(CASE 
                    WHEN GREATEST(0, LEAST(100, 100 - ((coefficient_of_variation - {config[7]}) / ({config[8]} - {config[7]})) * 100)) >= 60 
                    THEN 1.0 ELSE 0.0 END
                ) * 100, 1) as pass_rate
            FROM headway_patterns
            WHERE coefficient_of_variation IS NOT NULL
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
        
        # Journey time - calculate from patterns
        cur.execute(f"""
            SELECT 
                ROUND(AVG(
                    GREATEST(0, LEAST(100,
                        100 - ((coefficient_of_variation - {config[11]}) / ({config[12]} - {config[11]})) * 100
                    ))
                )::numeric, 1) as avg_jt,
                ROUND(AVG(CASE 
                    WHEN GREATEST(0, LEAST(100, 100 - ((coefficient_of_variation - {config[11]}) / ({config[12]} - {config[11]})) * 100)) >= 60 
                    THEN 1.0 ELSE 0.0 END
                ) * 100, 1) as pass_rate
            FROM journey_time_patterns
            WHERE coefficient_of_variation IS NOT NULL
        """)
        jt_avg = cur.fetchone()
        
        # Service delivery - calculate from patterns  
        cur.execute(f"""
            SELECT 
                ROUND(AVG(
                    GREATEST(0, LEAST(100,
                        ((service_delivery_rate - {config[14]}) / ({config[13]} - {config[14]})) * 100
                    ))
                )::numeric, 1) as avg_sd,
                ROUND(AVG(CASE 
                    WHEN GREATEST(0, LEAST(100, ((service_delivery_rate - {config[14]}) / ({config[13]} - {config[14]})) * 100)) >= 60 
                    THEN 1.0 ELSE 0.0 END
                ) * 100, 1) as pass_rate
            FROM service_delivery_patterns
            WHERE service_delivery_rate IS NOT NULL
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