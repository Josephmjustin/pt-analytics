"""
Add analyzed column to vehicle_positions table
This tracks which positions have been processed for stop detection
"""

import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT", 5432)
)
conn.autocommit = True
cur = conn.cursor()

print("Adding analyzed column to vehicle_positions...")

# Add analyzed column
cur.execute("""
    ALTER TABLE vehicle_positions 
    ADD COLUMN IF NOT EXISTS analyzed BOOLEAN DEFAULT false;
""")
print("✓ Added analyzed column")

# Create index for efficient querying
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_vehicle_positions_unanalyzed 
    ON vehicle_positions(analyzed, timestamp) 
    WHERE analyzed = false;
""")
print("✓ Created index on unanalyzed positions")

# Update cleanup logic - don't delete unanalyzed data
cur.execute("""
    -- Update existing cleanup to only delete analyzed data
    COMMENT ON TABLE vehicle_positions IS 
    'Staging table: Delete records where analyzed=true OR timestamp < NOW() - 15 minutes';
""")
print("✓ Updated cleanup policy")

cur.close()
conn.close()

print("\n✓ Database schema updated!")
print("\nNext steps:")
print("1. Update cleanup_flow.py to respect analyzed flag")
print("2. Implement stop detection in analysis_flow.py")
print("3. Test stop event detection")
