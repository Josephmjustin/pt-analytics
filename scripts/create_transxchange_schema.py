"""
Create TransXChange database tables
Run this first to set up the schema
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Connect to database
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT", 5432)
)
conn.autocommit = True
cur = conn.cursor()

print("Creating TransXChange tables...")
print("="*80)

# Enable PostGIS extension
print("\n0. Enabling PostGIS extension...")
cur.execute("""
    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE EXTENSION IF NOT EXISTS cube;
    CREATE EXTENSION IF NOT EXISTS earthdistance;
""")
print("   ✓ PostGIS extensions enabled")

# Table 1: Stops with coordinates
print("\n1. Creating txc_stops table...")
cur.execute("""
    DROP TABLE IF EXISTS txc_pattern_stops CASCADE;
    DROP TABLE IF EXISTS txc_route_patterns CASCADE;
    DROP TABLE IF EXISTS txc_stops CASCADE;
    
    CREATE TABLE txc_stops (
        naptan_id TEXT PRIMARY KEY,
        stop_name TEXT NOT NULL,
        latitude DOUBLE PRECISION NOT NULL,
        longitude DOUBLE PRECISION NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Add spatial index for proximity queries
    CREATE INDEX idx_txc_stops_location ON txc_stops USING gist(
        ll_to_earth(latitude, longitude)
    );
    
    COMMENT ON TABLE txc_stops IS 'TransXChange stops with coordinates (replaces OSM stops)';
""")
print("   ✓ txc_stops created")

# Table 2: Route patterns
print("\n2. Creating txc_route_patterns table...")
cur.execute("""
    CREATE TABLE txc_route_patterns (
        service_code TEXT PRIMARY KEY,
        operator_name TEXT NOT NULL,
        operator_noc TEXT,
        route_name TEXT NOT NULL,
        direction TEXT,
        origin TEXT,
        destination TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX idx_patterns_route_name ON txc_route_patterns(route_name);
    CREATE INDEX idx_patterns_operator ON txc_route_patterns(operator_name);
    
    COMMENT ON TABLE txc_route_patterns IS 'TransXChange route patterns (unique service codes with direction)';
""")
print("   ✓ txc_route_patterns created")

# Table 3: Stop sequences
print("\n3. Creating txc_pattern_stops table...")
cur.execute("""
    CREATE TABLE txc_pattern_stops (
        id SERIAL PRIMARY KEY,
        service_code TEXT NOT NULL REFERENCES txc_route_patterns(service_code) ON DELETE CASCADE,
        naptan_id TEXT NOT NULL REFERENCES txc_stops(naptan_id),
        stop_sequence INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(service_code, stop_sequence),
        CHECK(stop_sequence > 0)
    );
    
    CREATE INDEX idx_pattern_stops_naptan ON txc_pattern_stops(naptan_id);
    CREATE INDEX idx_pattern_stops_service ON txc_pattern_stops(service_code);
    CREATE INDEX idx_pattern_stops_lookup ON txc_pattern_stops(service_code, naptan_id);
    
    COMMENT ON TABLE txc_pattern_stops IS 'Stop sequences for each route pattern';
""")
print("   ✓ txc_pattern_stops created")

# Verify tables
print("\n" + "="*80)
print("VERIFICATION")
print("="*80)

cur.execute("""
    SELECT 
        tablename,
        pg_size_pretty(pg_total_relation_size('public.'||tablename)) as size
    FROM pg_tables
    WHERE schemaname = 'public'
    AND tablename LIKE 'txc_%'
    ORDER BY tablename
""")

print("\nCreated tables:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n✓ Schema created successfully!")
print("\nNext step: Run load_transxchange_data.py to populate tables")

cur.close()
conn.close()
