"""
Smart Data Retention with Running Averages
Cleans only tables that actually grow:
- vehicle_positions (grows constantly - clean old analyzed data)
- vehicle_arrivals (grows constantly - clean old arrivals)

SRI tables use running averages - they stay FIXED SIZE and never need cleaning!
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
    Clean up tables that grow indefinitely
    SRI tables (service_reliability_index, etc) use running averages - no cleanup needed!
    """
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        print(f"[{datetime.now()}] Starting cleanup...")
        print("="*60)
        
        # ========================================================================
        # 1. VEHICLE POSITIONS - Keep only recent unanalyzed
        # ========================================================================
        print("\n1. Cleaning vehicle_positions...")
        
        cur.execute("SELECT COUNT(*) FROM vehicle_positions")
        before_positions = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM vehicle_positions WHERE analyzed = true")
        total_analyzed = cur.fetchone()[0]
        
        print(f"   Before: {before_positions:,} positions ({total_analyzed:,} analyzed)")
        
        # Count what will be deleted
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
        
        # Delete old data
        cur.execute("""
            DELETE FROM vehicle_positions
            WHERE (analyzed = true AND timestamp < NOW() - INTERVAL '15 minutes')
               OR (analyzed = false AND timestamp < NOW() - INTERVAL '30 minutes')
        """)
        
        total_deleted = cur.rowcount
        conn.commit()
        
        print(f"   Deleted: {analyzed_to_delete:,} analyzed (>15min)")
        if unanalyzed_to_delete > 0:
            print(f"   ⚠ WARNING: Deleted {unanalyzed_to_delete:,} unanalyzed (>30min)")
            print(f"      Analysis falling behind!")
        print(f"   After: {before_positions - total_deleted:,} positions")
        
        # ========================================================================
        # 2. VEHICLE ARRIVALS - Delete after aggregation into dwell_time_analysis
        # ========================================================================
        print("\n2. Cleaning vehicle_arrivals...")
        
        cur.execute("SELECT COUNT(*) FROM vehicle_arrivals")
        old_arrivals = cur.fetchone()[0]
        
        if old_arrivals > 0:
            # These should already be aggregated by aggregate_dwell_times.py
            # This is a safety cleanup for any stragglers
            cur.execute("DELETE FROM vehicle_arrivals WHERE timestamp < NOW() - INTERVAL '1 hour'")
            deleted = cur.rowcount
            conn.commit()
            print(f"   Deleted: {deleted:,} arrivals (>1 hour)")
        else:
            print(f"   No old arrivals to clean")
        
        # ========================================================================
        # 3. DWELL TIME ANALYSIS - Fixed size, no cleanup needed
        # ========================================================================
        print("\n3. Dwell time analysis (fixed size - no cleanup needed)...")
        
        cur.execute("SELECT COUNT(*) FROM dwell_time_analysis")
        dwell_rows = cur.fetchone()[0]
        
        if dwell_rows > 0:
            cur.execute("""
                SELECT 
                    COUNT(DISTINCT route_name) as routes,
                    COUNT(DISTINCT naptan_id) as stops,
                    SUM(sample_count) as total_samples
                FROM dwell_time_analysis
            """)
            stats = cur.fetchone()
            print(f"   {dwell_rows:,} aggregated records")
            print(f"   {stats[0]} routes, {stats[1]} stops, {stats[2]:,} samples")
            print(f"   ✓ FIXED SIZE - updates existing rows only")
        
        # ========================================================================
        # VACUUM to reclaim disk space
        # ========================================================================
        print("\n" + "="*60)
        print("Running VACUUM to reclaim disk space...")
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Reconnect with autocommit for VACUUM
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        cur.execute("VACUUM vehicle_positions")
        cur.execute("VACUUM vehicle_arrivals")
        cur.execute("VACUUM dwell_time_analysis")
        
        # Check final sizes
        cur.execute("""
            SELECT 
                pg_size_pretty(pg_total_relation_size('vehicle_positions')) as vp_size,
                pg_size_pretty(pg_total_relation_size('vehicle_arrivals')) as va_size
        """)
        sizes = cur.fetchone()
        
        print(f"   vehicle_positions: {sizes[0]}")
        print(f"   vehicle_arrivals: {sizes[1]}")
        
        print("\n" + "="*60)
        print("✓ Cleanup complete")
        print("="*60)
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
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
    cleanup_old_data()
