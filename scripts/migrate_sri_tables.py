#!/usr/bin/env python3
"""
Database Migration: Create separate SRI tables
Run this to create the new table structure
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

MIGRATION_SQL = """
-- Migration: Separate SRI tables by time dimension
-- Fresh creation without data migration

BEGIN;

-- Drop old tables if they exist (to start fresh)
DROP TABLE IF EXISTS service_reliability_index CASCADE;
DROP TABLE IF EXISTS network_reliability_index CASCADE;

-- ============================================================================
-- ROUTE-LEVEL SRI TABLES
-- ============================================================================

-- Route SRI - Hourly (most granular)
CREATE TABLE service_reliability_index_hourly (
    id SERIAL PRIMARY KEY,
    route_name VARCHAR(50) NOT NULL,
    direction VARCHAR(20) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    
    headway_consistency_score DECIMAL(5,2),
    schedule_adherence_score DECIMAL(5,2),
    journey_time_consistency_score DECIMAL(5,2),
    service_delivery_score DECIMAL(5,2),
    
    headway_weight DECIMAL(3,2),
    schedule_weight DECIMAL(3,2),
    journey_time_weight DECIMAL(3,2),
    service_delivery_weight DECIMAL(3,2),
    
    sri_score DECIMAL(5,2) NOT NULL,
    sri_grade CHAR(1) NOT NULL,
    
    observation_count INTEGER DEFAULT 0,
    data_completeness DECIMAL(5,2),
    calculation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_service_sri_hourly UNIQUE (route_name, direction, operator, year, month, day_of_week, hour),
    CONSTRAINT valid_hour CHECK (hour >= 0 AND hour <= 23),
    CONSTRAINT valid_day CHECK (day_of_week >= 0 AND day_of_week <= 6),
    CONSTRAINT valid_month CHECK (month >= 1 AND month <= 12),
    CONSTRAINT valid_sri_score CHECK (sri_score >= 0 AND sri_score <= 100),
    CONSTRAINT valid_grade CHECK (sri_grade IN ('A', 'B', 'C', 'D', 'F'))
);

CREATE INDEX idx_service_sri_hourly_route ON service_reliability_index_hourly(route_name, operator);
CREATE INDEX idx_service_sri_hourly_time ON service_reliability_index_hourly(year, month, day_of_week, hour);
CREATE INDEX idx_service_sri_hourly_score ON service_reliability_index_hourly(sri_score DESC);

-- Route SRI - Daily
CREATE TABLE service_reliability_index_daily (
    id SERIAL PRIMARY KEY,
    route_name VARCHAR(50) NOT NULL,
    direction VARCHAR(20) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    
    headway_consistency_score DECIMAL(5,2),
    schedule_adherence_score DECIMAL(5,2),
    journey_time_consistency_score DECIMAL(5,2),
    service_delivery_score DECIMAL(5,2),
    
    headway_weight DECIMAL(3,2),
    schedule_weight DECIMAL(3,2),
    journey_time_weight DECIMAL(3,2),
    service_delivery_weight DECIMAL(3,2),
    
    sri_score DECIMAL(5,2) NOT NULL,
    sri_grade CHAR(1) NOT NULL,
    
    observation_count INTEGER DEFAULT 0,
    data_completeness DECIMAL(5,2),
    calculation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_service_sri_daily UNIQUE (route_name, direction, operator, year, month, day_of_week),
    CONSTRAINT valid_day_daily CHECK (day_of_week >= 0 AND day_of_week <= 6),
    CONSTRAINT valid_month_daily CHECK (month >= 1 AND month <= 12),
    CONSTRAINT valid_sri_score_daily CHECK (sri_score >= 0 AND sri_score <= 100),
    CONSTRAINT valid_grade_daily CHECK (sri_grade IN ('A', 'B', 'C', 'D', 'F'))
);

CREATE INDEX idx_service_sri_daily_route ON service_reliability_index_daily(route_name, operator);
CREATE INDEX idx_service_sri_daily_time ON service_reliability_index_daily(year, month, day_of_week);

-- Route SRI - Monthly (API primary table)
CREATE TABLE service_reliability_index_monthly (
    id SERIAL PRIMARY KEY,
    route_name VARCHAR(50) NOT NULL,
    direction VARCHAR(20) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    
    headway_consistency_score DECIMAL(5,2),
    schedule_adherence_score DECIMAL(5,2),
    journey_time_consistency_score DECIMAL(5,2),
    service_delivery_score DECIMAL(5,2),
    
    headway_weight DECIMAL(3,2),
    schedule_weight DECIMAL(3,2),
    journey_time_weight DECIMAL(3,2),
    service_delivery_weight DECIMAL(3,2),
    
    sri_score DECIMAL(5,2) NOT NULL,
    sri_grade CHAR(1) NOT NULL,
    
    observation_count INTEGER DEFAULT 0,
    data_completeness DECIMAL(5,2),
    calculation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_service_sri_monthly UNIQUE (route_name, direction, operator, year, month),
    CONSTRAINT valid_month_monthly CHECK (month >= 1 AND month <= 12),
    CONSTRAINT valid_sri_score_monthly CHECK (sri_score >= 0 AND sri_score <= 100),
    CONSTRAINT valid_grade_monthly CHECK (sri_grade IN ('A', 'B', 'C', 'D', 'F'))
);

CREATE INDEX idx_service_sri_monthly_route ON service_reliability_index_monthly(route_name, operator);
CREATE INDEX idx_service_sri_monthly_time ON service_reliability_index_monthly(year, month);
CREATE INDEX idx_service_sri_monthly_score ON service_reliability_index_monthly(sri_score DESC);
CREATE INDEX idx_service_sri_monthly_operator ON service_reliability_index_monthly(operator);

-- ============================================================================
-- NETWORK-LEVEL SRI TABLES
-- ============================================================================

-- Network SRI - Hourly
CREATE TABLE network_reliability_index_hourly (
    id SERIAL PRIMARY KEY,
    network_name VARCHAR(100) NOT NULL DEFAULT 'Merseyside',
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    
    network_sri_score DECIMAL(5,2) NOT NULL,
    network_grade CHAR(1) NOT NULL,
    total_routes INTEGER DEFAULT 0,
    
    routes_grade_a INTEGER DEFAULT 0,
    routes_grade_b INTEGER DEFAULT 0,
    routes_grade_c INTEGER DEFAULT 0,
    routes_grade_d INTEGER DEFAULT 0,
    routes_grade_f INTEGER DEFAULT 0,
    
    avg_headway_score DECIMAL(5,2),
    avg_schedule_score DECIMAL(5,2),
    avg_journey_time_score DECIMAL(5,2),
    avg_service_delivery_score DECIMAL(5,2),
    
    calculation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_network_sri_hourly UNIQUE (network_name, year, month, day_of_week, hour),
    CONSTRAINT valid_hour_net CHECK (hour >= 0 AND hour <= 23),
    CONSTRAINT valid_day_net CHECK (day_of_week >= 0 AND day_of_week <= 6),
    CONSTRAINT valid_month_net CHECK (month >= 1 AND month <= 12),
    CONSTRAINT valid_network_score CHECK (network_sri_score >= 0 AND network_sri_score <= 100),
    CONSTRAINT valid_network_grade CHECK (network_grade IN ('A', 'B', 'C', 'D', 'F'))
);

CREATE INDEX idx_network_sri_hourly_time ON network_reliability_index_hourly(year, month, day_of_week, hour);

-- Network SRI - Daily
CREATE TABLE network_reliability_index_daily (
    id SERIAL PRIMARY KEY,
    network_name VARCHAR(100) NOT NULL DEFAULT 'Merseyside',
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    
    network_sri_score DECIMAL(5,2) NOT NULL,
    network_grade CHAR(1) NOT NULL,
    total_routes INTEGER DEFAULT 0,
    
    routes_grade_a INTEGER DEFAULT 0,
    routes_grade_b INTEGER DEFAULT 0,
    routes_grade_c INTEGER DEFAULT 0,
    routes_grade_d INTEGER DEFAULT 0,
    routes_grade_f INTEGER DEFAULT 0,
    
    avg_headway_score DECIMAL(5,2),
    avg_schedule_score DECIMAL(5,2),
    avg_journey_time_score DECIMAL(5,2),
    avg_service_delivery_score DECIMAL(5,2),
    
    calculation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_network_sri_daily UNIQUE (network_name, year, month, day_of_week),
    CONSTRAINT valid_day_net_daily CHECK (day_of_week >= 0 AND day_of_week <= 6),
    CONSTRAINT valid_month_net_daily CHECK (month >= 1 AND month <= 12),
    CONSTRAINT valid_network_score_daily CHECK (network_sri_score >= 0 AND network_sri_score <= 100),
    CONSTRAINT valid_network_grade_daily CHECK (network_grade IN ('A', 'B', 'C', 'D', 'F'))
);

CREATE INDEX idx_network_sri_daily_time ON network_reliability_index_daily(year, month, day_of_week);

-- Network SRI - Monthly (API primary table)
CREATE TABLE network_reliability_index_monthly (
    id SERIAL PRIMARY KEY,
    network_name VARCHAR(100) NOT NULL DEFAULT 'Merseyside',
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    
    network_sri_score DECIMAL(5,2) NOT NULL,
    network_grade CHAR(1) NOT NULL,
    total_routes INTEGER DEFAULT 0,
    
    routes_grade_a INTEGER DEFAULT 0,
    routes_grade_b INTEGER DEFAULT 0,
    routes_grade_c INTEGER DEFAULT 0,
    routes_grade_d INTEGER DEFAULT 0,
    routes_grade_f INTEGER DEFAULT 0,
    
    avg_headway_score DECIMAL(5,2),
    avg_schedule_score DECIMAL(5,2),
    avg_journey_time_score DECIMAL(5,2),
    avg_service_delivery_score DECIMAL(5,2),
    
    calculation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_network_sri_monthly UNIQUE (network_name, year, month),
    CONSTRAINT valid_month_net_monthly CHECK (month >= 1 AND month <= 12),
    CONSTRAINT valid_network_score_monthly CHECK (network_sri_score >= 0 AND network_sri_score <= 100),
    CONSTRAINT valid_network_grade_monthly CHECK (network_grade IN ('A', 'B', 'C', 'D', 'F'))
);

CREATE INDEX idx_network_sri_monthly_time ON network_reliability_index_monthly(year, month);
CREATE INDEX idx_network_sri_monthly_score ON network_reliability_index_monthly(network_sri_score DESC);

COMMIT;
"""

def run_migration():
    """Run the database migration"""
    print("="*80)
    print("DATABASE MIGRATION: Separate SRI Tables")
    print("="*80)
    
    print("\nConnecting to database...")
    print(f"Host: {DB_CONFIG['host']}")
    print(f"Database: {DB_CONFIG['database']}")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False  # Use transactions
        cur = conn.cursor()
        
        print("\n⚠️  WARNING: This will DROP existing service_reliability_index and network_reliability_index tables!")
        print("Continue? (yes/no): ", end='')
        response = input().strip().lower()
        
        if response != 'yes':
            print("\nMigration cancelled.")
            return
        
        print("\nRunning migration...")
        cur.execute(MIGRATION_SQL)
        conn.commit()
        
        print("✓ Migration completed successfully!")
        
        # Verify tables created
        print("\nVerifying new tables...")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
              AND (table_name LIKE '%_monthly' 
                   OR table_name LIKE '%_daily'
                   OR table_name LIKE '%_hourly')
            ORDER BY table_name
        """)
        
        tables = cur.fetchall()
        print(f"\n✓ Created {len(tables)} new tables:")
        for table in tables:
            print(f"  - {table[0]}")
        
        cur.close()
        conn.close()
        
        print("\n" + "="*80)
        print("NEXT STEPS:")
        print("="*80)
        print("1. Replace calculate_sri_scores.py with the new version")
        print("2. Replace src/api/routes/sri.py with the new version")
        print("3. Run: python scripts/calculate_sri_scores.py")
        print("4. Test API: curl http://localhost:8000/sri/network")
        print("="*80)
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    run_migration()