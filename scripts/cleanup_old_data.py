"""
Smart Data Retention: Clean up vehicle positions safely
Deletes:
1. Analyzed positions older than 15 minutes (normal cleanup)
2. Unanalyzed positions older than 30 minutes (safety net - should not happen)
Keeps:
- Recent unanalyzed positions (waiting for analysis)
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
    """
    Smart cleanup with safety checks
    - Analyzed data >15 min old (normal cleanup)
    - Unanalyzed data >30 min old (safety net - logs warning if any found)
    """
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Check current size
        cur.execute("SELECT COUNT(*) FROM vehicle_positions")
        before_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM vehicle_positions WHERE analyzed = true")
        total_analyzed = cur.fetchone()[0]
        
        print(f"Current state: {before_count:,} total, {total_analyzed:,} analyzed")
        
        # Count what will be deleted (with breakdown)
        cur.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE analyzed = true) as analyzed_count,
                COUNT(*) FILTER (WHERE analyzed = false) as unanalyzed_count
            FROM vehicle_positions
            WHERE (analyzed = true AND timestamp < NOW() - INTERVAL '15 minutes')
               OR (analyzed = false AND timestamp < NOW() - INTERVAL '30 minutes')
        """)
        
        result = cur.fetchone()
        analyzed_to_delete = result[0] if result else 0
        unanalyzed_to_delete = result[1] if result else 0
        
        # Smart deletion
        cur.execute("""
            DELETE FROM vehicle_positions
            WHERE (analyzed = true AND timestamp < NOW() - INTERVAL '15 minutes')
               OR (analyzed = false AND timestamp < NOW() - INTERVAL '30 minutes')
        """)
        
        total_deleted = cur.rowcount
        conn.commit()
        
        after_count = before_count - total_deleted
        
        print(f"Cleanup complete:")
        print(f"  Deleted {analyzed_to_delete:,} analyzed positions (>15min)")
        
        if unanalyzed_to_delete > 0:
            print(f"  ⚠ WARNING: Deleted {unanalyzed_to_delete:,} unanalyzed positions (>30min)")
            print(f"     Analysis is falling behind! Investigate performance issues.")
        else:
            print(f"  Deleted {unanalyzed_to_delete:,} unanalyzed positions (>30min) ✓")
        
        print(f"  Total deleted: {total_deleted:,}")
        print(f"  Remaining: {after_count:,} positions")
        
        # Show table size
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
