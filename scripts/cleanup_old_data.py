"""
Data Retention: Clean up old vehicle positions after analysis
Deletes all data before the last analysis run
Keeps only data since last analysis for next run
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

def cleanup_old_data():
    """Delete vehicle positions older than last analysis"""
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Check current size
        cur.execute("SELECT COUNT(*) FROM vehicle_positions")
        before_count = cur.fetchone()[0]
        
        # Get last analysis end time
        cur.execute("""
            SELECT MAX(data_window_end) 
            FROM bunching_scores
        """)
        last_analysis = cur.fetchone()[0]
        
        if not last_analysis:
            print("No analysis runs found yet - skipping cleanup")
            return
        
        print(f"Last analysis ended at: {last_analysis}")
        
        # Delete old data
        cur.execute("""
            DELETE FROM vehicle_positions 
            WHERE timestamp < %s
        """, (last_analysis,))
        
        deleted = cur.rowcount
        conn.commit()
        
        after_count = before_count - deleted
        
        print(f"Data cleanup complete:")
        print(f"  Before: {before_count:,} positions")
        print(f"  Deleted: {deleted:,} positions")
        print(f"  Kept: {after_count:,} positions (since last analysis)")
        
        # Show new size
        cur.execute("""
            SELECT pg_size_pretty(pg_total_relation_size('vehicle_positions'))
        """)
        size = cur.fetchone()[0]
        print(f"  Table size: {size}")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    cleanup_old_data()
