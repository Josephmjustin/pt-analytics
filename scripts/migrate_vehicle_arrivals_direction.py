"""
One-time migration: Add direction column to vehicle_arrivals table
Run this ONCE after switching to SIRI-VM
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

print("Adding direction column to vehicle_arrivals table...")
print("="*80)

# Add direction column
cur.execute("""
    ALTER TABLE vehicle_arrivals 
    ADD COLUMN IF NOT EXISTS direction TEXT
""")

# Create index for direction-based queries
print("\nCreating indexes...")
cur.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_arrivals_direction ON vehicle_arrivals(direction)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_arrivals_route_dir ON vehicle_arrivals(route_name, direction)")

conn.commit()

# Verify columns exist
print("\nVerifying columns...")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'vehicle_arrivals'
    ORDER BY ordinal_position
""")

print("\nvehicle_arrivals columns:")
for row in cur.fetchall():
    print(f"  - {row[0]} ({row[1]})")

cur.close()
conn.close()

print("\n" + "="*80)
print("✓ Migration complete!")