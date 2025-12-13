"""
Create optimized TransXChange schema
Uses pattern_id as surrogate key for cleaner relationships
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT", 5432)
)
cur = conn.cursor()

print("Creating optimized TransXChange schema...")
print("="*80)

# Drop existing tables if they exist
print("\nDropping existing tables (if any)...")
cur.execute("DROP TABLE IF EXISTS txc_pattern_stops CASCADE")
cur.execute("DROP TABLE IF EXISTS txc_route_patterns CASCADE")
cur.execute("DROP TABLE IF EXISTS txc_stops CASCADE")
conn.commit()
print("   ✓ Cleaned up")

# Table 1: Stops
print("\n1. Creating txc_stops...")
cur.execute("""
    CREATE TABLE txc_stops (
        naptan_id TEXT PRIMARY KEY,
        stop_name TEXT NOT NULL,
        latitude DOUBLE PRECISION,
        longitude DOUBLE PRECISION,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
cur.execute("CREATE INDEX idx_txc_stops_location ON txc_stops(latitude, longitude)")
print("   ✓ Created with PRIMARY KEY on naptan_id")

# Table 2: Route patterns with pattern_id
print("\n2. Creating txc_route_patterns...")
cur.execute("""
    CREATE TABLE txc_route_patterns (
        pattern_id SERIAL PRIMARY KEY,
        service_code TEXT NOT NULL,
        operator_name TEXT,
        operator_noc TEXT,
        route_name TEXT NOT NULL,
        direction TEXT,
        origin TEXT,
        destination TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (service_code, direction)
    )
""")
cur.execute("CREATE INDEX idx_txc_patterns_route ON txc_route_patterns(route_name)")
cur.execute("CREATE INDEX idx_txc_patterns_service ON txc_route_patterns(service_code)")
cur.execute("CREATE INDEX idx_txc_patterns_direction ON txc_route_patterns(direction)")
print("   ✓ Created with pattern_id PRIMARY KEY")
print("   ✓ UNIQUE constraint on (service_code, direction)")

# Table 3: Pattern stops
print("\n3. Creating txc_pattern_stops...")
cur.execute("""
    CREATE TABLE txc_pattern_stops (
        pattern_id INTEGER NOT NULL REFERENCES txc_route_patterns(pattern_id) ON DELETE CASCADE,
        naptan_id TEXT NOT NULL REFERENCES txc_stops(naptan_id) ON DELETE CASCADE,
        stop_sequence INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (pattern_id, stop_sequence)
    )
""")
cur.execute("CREATE INDEX idx_txc_pattern_stops_naptan ON txc_pattern_stops(naptan_id)")
print("   ✓ Created with composite PRIMARY KEY (pattern_id, stop_sequence)")
print("   ✓ Foreign keys to txc_route_patterns and txc_stops")

conn.commit()

print("\n" + "="*80)
print("SCHEMA SUMMARY")
print("="*80)
print("\ntxc_stops:")
print("  - PRIMARY KEY: naptan_id")
print("  - Indexes: location (lat, lon)")

print("\ntxc_route_patterns:")
print("  - PRIMARY KEY: pattern_id (auto-increment)")
print("  - UNIQUE: (service_code, direction)")
print("  - Indexes: route_name, service_code, direction")

print("\ntxc_pattern_stops:")
print("  - PRIMARY KEY: (pattern_id, stop_sequence)")
print("  - Foreign keys: pattern_id → txc_route_patterns, naptan_id → txc_stops")
print("  - Index: naptan_id")

cur.close()
conn.close()

print("\n✓ Schema created successfully!")