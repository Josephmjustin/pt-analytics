"""
Add PostGIS geography column and spatial index to txc_stops
This enables ultra-fast spatial queries for stop matching
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

print("Setting up PostGIS for fast spatial matching...")
print("="*80)

# 1. Enable PostGIS extension
print("\n1. Enabling PostGIS extension...")
cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
conn.commit()
print("   ✓ PostGIS enabled")

# 2. Add geography column
print("\n2. Adding geography column to txc_stops...")
cur.execute("""
    ALTER TABLE txc_stops 
    ADD COLUMN IF NOT EXISTS geog geography(Point, 4326)
""")
conn.commit()
print("   ✓ Geography column added")

# 3. Populate geography from lat/lon
print("\n3. Populating geography from latitude/longitude...")
cur.execute("""
    UPDATE txc_stops 
    SET geog = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
""")
updated = cur.rowcount
conn.commit()
print(f"   ✓ Updated {updated} stops with geography")

# 4. Create spatial index (GIST)
print("\n4. Creating spatial index...")
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_txc_stops_geog 
    ON txc_stops USING GIST(geog)
""")
conn.commit()
print("   ✓ Spatial index created")

# 5. Verify
print("\n" + "="*80)
print("VERIFICATION")
print("="*80)

cur.execute("""
    SELECT 
        COUNT(*) as total_stops,
        COUNT(*) FILTER (WHERE geog IS NOT NULL) as stops_with_geog
    FROM txc_stops
""")

result = cur.fetchone()
print(f"\nStops: {result[0]} total, {result[1]} with geography")

# Test query performance
print("\nTesting spatial query performance...")
cur.execute("""
    EXPLAIN ANALYZE
    SELECT naptan_id, stop_name
    FROM txc_stops
    WHERE ST_DWithin(
        geog,
        ST_SetSRID(ST_MakePoint(-3.0, 53.4), 4326)::geography,
        30
    )
    LIMIT 5
""")

print("Query plan:")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()

print("\n" + "="*80)
print("✓ PostGIS setup complete!")
print("")
print("Next: Update vehicle_matcher.py to use PostGIS queries")