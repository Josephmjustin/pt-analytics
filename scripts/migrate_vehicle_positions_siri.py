"""
One-time migration: Add SIRI-VM columns to vehicle_positions table
Run this ONCE before switching to SIRI-VM poller
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

print("Adding SIRI-VM columns to vehicle_positions table...")
print("="*80)

# Add new columns
cur.execute("""
    ALTER TABLE vehicle_positions 
    ADD COLUMN IF NOT EXISTS route_name TEXT,
    ADD COLUMN IF NOT EXISTS direction TEXT,
    ADD COLUMN IF NOT EXISTS operator TEXT,
    ADD COLUMN IF NOT EXISTS origin TEXT,
    ADD COLUMN IF NOT EXISTS destination TEXT
""")

# Create indexes for efficient querying
print("\nCreating indexes...")
cur.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_positions_route_direction ON vehicle_positions(route_name, direction)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_positions_direction ON vehicle_positions(direction)")

conn.commit()

# Verify columns exist
print("\nVerifying columns...")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'vehicle_positions'
    ORDER BY ordinal_position
""")

print("\nvehicle_positions columns:")
for row in cur.fetchall():
    print(f"  - {row[0]} ({row[1]})")

cur.close()
conn.close()

print("\n" + "="*80)
print("✓ Migration complete!")
print("You can now use the SIRI-VM poller")