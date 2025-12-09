"""
Data Retention: Clean up analyzed vehicle positions
Deletes:
1. Positions marked as analyzed=true
2. Positions older than 15 minutes (safety cleanup)
Keeps:
- Unanalyzed positions (waiting for next analysis cycle)
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
    """Delete analyzed vehicle positions and old data"""
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Check current size
        cur.execute("SELECT COUNT(*) FROM vehicle_positions")
        before_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM vehicle_positions WHERE analyzed = true")
        analyzed_count = cur.fetchone()[0]
        
        print(f"Current state: {before_count:,} total, {analyzed_count:,} analyzed")
        
        # Delete analyzed positions
        cur.execute("""
            DELETE FROM vehicle_positions 
            WHERE analyzed = true
        """)
        deleted_analyzed = cur.rowcount
        
        # Safety cleanup: delete positions older than 15 minutes (should be analyzed by now)
        cur.execute("""
            DELETE FROM vehicle_positions 
            WHERE timestamp < NOW() - INTERVAL '15 minutes'
        """)
        deleted_old = cur.rowcount
        
        conn.commit()
        
        total_deleted = deleted_analyzed + deleted_old
        after_count = before_count - total_deleted
        
        print(f"Cleanup complete:")
        print(f"  Deleted {deleted_analyzed:,} analyzed positions")
        print(f"  Deleted {deleted_old:,} old (>15min) positions")
        print(f"  Total deleted: {total_deleted:,}")
        print(f"  Remaining: {after_count:,} positions (unanalyzed)")
        
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
