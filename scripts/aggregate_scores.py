"""
Aggregate bunching scores into running averages
Updates pattern tables and deletes processed scores
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

def aggregate_scores():
    """Aggregate latest bunching scores into pattern tables using running averages"""
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Get latest scores that haven't been aggregated yet
        cur.execute("""
            SELECT 
                stop_id,
                stop_name,
                bunching_rate_pct,
                analysis_timestamp,
                EXTRACT(HOUR FROM analysis_timestamp) as hour,
                EXTRACT(DOW FROM analysis_timestamp) as day_of_week,
                EXTRACT(MONTH FROM analysis_timestamp) as month
            FROM bunching_scores
            WHERE analysis_timestamp > (
                SELECT COALESCE(MAX(last_updated), '1970-01-01') 
                FROM bunching_by_stop
            )
            ORDER BY analysis_timestamp
        """)
        
        new_scores = cur.fetchall()
        
        if not new_scores:
            print("No new scores to aggregate")
            return
        
        print(f"Aggregating {len(new_scores)} new scores...")
        
        aggregated = 0
        
        for score in new_scores:
            stop_id, stop_name, bunching_rate, timestamp, hour, day_of_week, month = score
            
            # 1. Update by_hour
            cur.execute("""
                INSERT INTO bunching_by_hour (stop_id, hour_of_day, avg_bunching_rate, total_count)
                VALUES (%s, %s, %s, 1)
                ON CONFLICT (stop_id, hour_of_day) 
                DO UPDATE SET 
                    avg_bunching_rate = (
                        bunching_by_hour.avg_bunching_rate * bunching_by_hour.total_count + EXCLUDED.avg_bunching_rate
                    ) / (bunching_by_hour.total_count + 1),
                    total_count = bunching_by_hour.total_count + 1,
                    last_updated = NOW()
            """, (stop_id, int(hour), bunching_rate))
            
            # 2. Update by_day
            cur.execute("""
                INSERT INTO bunching_by_day (stop_id, day_of_week, avg_bunching_rate, total_count)
                VALUES (%s, %s, %s, 1)
                ON CONFLICT (stop_id, day_of_week) 
                DO UPDATE SET 
                    avg_bunching_rate = (
                        bunching_by_day.avg_bunching_rate * bunching_by_day.total_count + EXCLUDED.avg_bunching_rate
                    ) / (bunching_by_day.total_count + 1),
                    total_count = bunching_by_day.total_count + 1,
                    last_updated = NOW()
            """, (stop_id, int(day_of_week), bunching_rate))
            
            # 3. Update by_hour_day
            cur.execute("""
                INSERT INTO bunching_by_hour_day (stop_id, hour_of_day, day_of_week, avg_bunching_rate, total_count)
                VALUES (%s, %s, %s, %s, 1)
                ON CONFLICT (stop_id, hour_of_day, day_of_week) 
                DO UPDATE SET 
                    avg_bunching_rate = (
                        bunching_by_hour_day.avg_bunching_rate * bunching_by_hour_day.total_count + EXCLUDED.avg_bunching_rate
                    ) / (bunching_by_hour_day.total_count + 1),
                    total_count = bunching_by_hour_day.total_count + 1,
                    last_updated = NOW()
            """, (stop_id, int(hour), int(day_of_week), bunching_rate))
            
            # 4. Update by_month
            cur.execute("""
                INSERT INTO bunching_by_month (stop_id, month, avg_bunching_rate, total_count)
                VALUES (%s, %s, %s, 1)
                ON CONFLICT (stop_id, month) 
                DO UPDATE SET 
                    avg_bunching_rate = (
                        bunching_by_month.avg_bunching_rate * bunching_by_month.total_count + EXCLUDED.avg_bunching_rate
                    ) / (bunching_by_month.total_count + 1),
                    total_count = bunching_by_month.total_count + 1,
                    last_updated = NOW()
            """, (stop_id, int(month), bunching_rate))
            
            # 5. Update by_stop (overall)
            cur.execute("""
                INSERT INTO bunching_by_stop (stop_id, stop_name, avg_bunching_rate, total_count)
                VALUES (%s, %s, %s, 1)
                ON CONFLICT (stop_id) 
                DO UPDATE SET 
                    avg_bunching_rate = (
                        bunching_by_stop.avg_bunching_rate * bunching_by_stop.total_count + EXCLUDED.avg_bunching_rate
                    ) / (bunching_by_stop.total_count + 1),
                    total_count = bunching_by_stop.total_count + 1,
                    last_updated = NOW()
            """, (stop_id, stop_name, bunching_rate))
            
            aggregated += 1
        
        conn.commit()
        
        print(f"SUCCESS: Aggregated {aggregated} scores into pattern tables")
        
        # Now delete old bunching_scores (keep only last hour for debugging)
        cur.execute("""
            DELETE FROM bunching_scores
            WHERE analysis_timestamp < NOW() - INTERVAL '1 hour'
        """)
        
        deleted = cur.rowcount
        conn.commit()
        
        print(f"Deleted {deleted} old bunching_scores (kept last 1 hour)")
        
        # Show summary
        cur.execute("SELECT COUNT(*) FROM bunching_by_stop")
        stop_count = cur.fetchone()[0]
        
        cur.execute("SELECT pg_size_pretty(pg_total_relation_size('bunching_scores'))")
        scores_size = cur.fetchone()[0]
        
        print(f"\nCurrent state:")
        print(f"  Stops tracked: {stop_count}")
        print(f"  bunching_scores size: {scores_size}")
        
    except Exception as e:
        print(f"Error during aggregation: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    aggregate_scores()
