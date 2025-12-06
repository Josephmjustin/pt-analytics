"""
Get Database Schema
Outputs table structures for README documentation
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

def get_schema():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Get all tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cur.fetchall()]
    
    print("\n" + "="*60)
    print("DATABASE SCHEMA")
    print("="*60 + "\n")
    
    for table in tables:
        print(f"### {table}")
        print("```sql")
        
        # Get columns
        cur.execute("""
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table,))
        
        columns = cur.fetchall()
        
        print(f"{table} (")
        for col in columns:
            col_name, data_type, max_len, nullable = col
            
            # Format type
            if max_len:
                type_str = f"{data_type.upper()}({max_len})"
            else:
                type_str = data_type.upper()
            
            # Check for geometry type
            if data_type == 'USER-DEFINED':
                cur.execute("""
                    SELECT udt_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = %s
                """, (table, col_name))
                udt = cur.fetchone()[0]
                type_str = udt.upper()
            
            nullable_str = "NULL" if nullable == "YES" else "NOT NULL"
            
            print(f"    {col_name:<30} {type_str:<20} {nullable_str}")
        
        print(")")
        print("```\n")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    get_schema()
