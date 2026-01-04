"""
Create stop_schedule table - Memory-efficient version with Operating Period support
Processes TransXChange files directly without loading full JSON
"""

import xml.etree.ElementTree as ET
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timedelta
import re
from collections import defaultdict

load_dotenv()

# Paths - use /tmp on GitHub Actions, local path otherwise
if os.getenv('GITHUB_ACTIONS'):
    BASE_DIR = Path("/tmp/txc_monthly")
else:
    BASE_DIR = Path(__file__).parent

EXTRACT_DIR = BASE_DIR / "extracted"

# Database connection - use env vars from GitHub Actions secrets
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '141.147.106.59'),
    'port': '5432',
    'database': os.getenv('DB_NAME', 'pt_analytics_schedules'),
    'user': os.getenv('DB_USER', 'pt_api'),
    'password': os.getenv('DB_PASSWORD') or os.getenv('ORACLE_VM2_PASSWORD')
}

# TransXChange namespace
NS = {'txc': 'http://www.transxchange.org.uk/'}

def parse_iso_duration(duration_str):
    """Convert ISO 8601 duration to minutes"""
    if not duration_str:
        return 0
    duration_str = duration_str.replace('PT', '')
    minutes = 0
    seconds = 0
    m_match = re.search(r'(\d+)M', duration_str)
    if m_match:
        minutes = int(m_match.group(1))
    s_match = re.search(r'(\d+)S', duration_str)
    if s_match:
        seconds = int(s_match.group(1))
    return minutes + (seconds / 60.0)

def parse_journey_pattern_section(section_elem):
    """Extract stops from section"""
    stops = []
    cumulative_time = 0
    
    for link in section_elem.findall('txc:JourneyPatternTimingLink', NS):
        from_elem = link.find('txc:From', NS)
        to_elem = link.find('txc:To', NS)
        runtime_elem = link.find('txc:RunTime', NS)
        
        if from_elem is not None:
            stop_ref_elem = from_elem.find('txc:StopPointRef', NS)
            if stop_ref_elem is not None:
                stops.append({
                    'naptan_id': stop_ref_elem.text,
                    'cumulative_minutes': cumulative_time
                })
        
        if runtime_elem is not None:
            runtime_minutes = parse_iso_duration(runtime_elem.text)
            cumulative_time += runtime_minutes
    
    if to_elem is not None:
        stop_ref_elem = to_elem.find('txc:StopPointRef', NS)
        if stop_ref_elem is not None:
            stops.append({
                'naptan_id': stop_ref_elem.text,
                'cumulative_minutes': cumulative_time
            })
    
    return stops

print("=" * 80)
print("CREATE STOP_SCHEDULE TABLE - WITH OPERATING PERIODS")
print("=" * 80)

# Connect to database
print("\nConnecting to database...")
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# Load existing patterns
print("Loading database patterns...")
cur.execute("""
    SELECT 
        pattern_id,
        service_code,
        direction,
        operator_name
    FROM txc_route_patterns
""")

db_patterns = cur.fetchall()
pattern_lookup = {}
for pattern_id, service_code, direction, operator in db_patterns:
    key = (service_code, direction, operator)
    pattern_lookup[key] = pattern_id

print(f"✓ Loaded {len(db_patterns):,} Merseyside patterns")

# Prepare table
print("\nPreparing stop_schedule table...")
print("  Truncating existing data...")
cur.execute("TRUNCATE TABLE stop_schedule")
conn.commit()
print("✓ Table ready")

# Process XMLs and build schedules
print("\nProcessing TransXChange files...")

xml_files = list(EXTRACT_DIR.rglob("*.xml"))
print(f"Found {len(xml_files):,} XML files\n")

# Accumulator: [naptan_id][pattern_id][validity_key][day][hour] = [times]
# validity_key = "YYYY-MM-DD_YYYY-MM-DD"
stop_schedules = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))))

files_processed = 0
matched_trips = 0
skipped_trips = 0

for xml_file in xml_files:
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Parse sections
        sections = {}
        for section in root.findall('.//txc:JourneyPatternSection', NS):
            section_id = section.get('id')
            stops = parse_journey_pattern_section(section)
            sections[section_id] = stops
        
        # Parse patterns
        patterns = {}
        for jp in root.findall('.//txc:JourneyPattern', NS):
            jp_id = jp.get('id')
            direction_elem = jp.find('txc:Direction', NS)
            section_ref_elem = jp.find('txc:JourneyPatternSectionRefs', NS)
            
            if section_ref_elem is not None:
                section_id = section_ref_elem.text
                if section_id in sections:
                    patterns[jp_id] = {
                        'direction': direction_elem.text if direction_elem is not None else 'outbound',
                        'stops': sections[section_id]
                    }
        
        # Get operator
        operator_elem = root.find('.//txc:Operator/txc:OperatorShortName', NS)
        operator = operator_elem.text if operator_elem is not None else "Unknown"
        
        # Get operating period (validity dates)
        operating_period = root.find('.//txc:OperatingPeriod', NS)
        valid_from = None
        valid_to = None
        
        if operating_period is not None:
            start_date_elem = operating_period.find('txc:StartDate', NS)
            end_date_elem = operating_period.find('txc:EndDate', NS)
            
            if start_date_elem is not None and start_date_elem.text:
                try:
                    valid_from = datetime.strptime(start_date_elem.text, '%Y-%m-%d').date()
                except:
                    pass
            
            if end_date_elem is not None and end_date_elem.text:
                try:
                    valid_to = datetime.strptime(end_date_elem.text, '%Y-%m-%d').date()
                except:
                    pass
        
        # Default to current year if not specified
        if valid_from is None:
            valid_from = datetime(2026, 1, 1).date()
        if valid_to is None:
            valid_to = datetime(2026, 12, 31).date()
        
        # Create validity key for this file
        validity_key = f"{valid_from}_{valid_to}"
        
        # Parse vehicle journeys
        for vj in root.findall('.//txc:VehicleJourney', NS):
            vj_code_elem = vj.find('txc:VehicleJourneyCode', NS)
            departure_elem = vj.find('txc:DepartureTime', NS)
            jp_ref_elem = vj.find('txc:JourneyPatternRef', NS)
            service_ref_elem = vj.find('txc:ServiceRef', NS)
            
            if not all([x is not None for x in [vj_code_elem, departure_elem, jp_ref_elem, service_ref_elem]]):
                continue
            
            jp_ref = jp_ref_elem.text
            pattern = patterns.get(jp_ref)
            if not pattern:
                continue
            
            service_code = service_ref_elem.text
            direction = pattern['direction']
            
            # Match to database pattern
            key = (service_code, direction, operator)
            pattern_id = pattern_lookup.get(key)
            
            if not pattern_id:
                skipped_trips += 1
                continue
            
            matched_trips += 1
            
            # Get days of week (simplified - use all days for now)
            days_of_week = [0, 1, 2, 3, 4, 5, 6]
            
            # Process stops
            departure_time = datetime.strptime(departure_elem.text, '%H:%M:%S')
            
            for stop_info in pattern['stops']:
                naptan_id = stop_info['naptan_id']
                cumulative_mins = stop_info['cumulative_minutes']
                arrival_time = departure_time + timedelta(minutes=cumulative_mins)
                
                hour = arrival_time.hour
                time_str = arrival_time.strftime('%H:%M')
                
                for day in days_of_week:
                    stop_schedules[naptan_id][pattern_id][validity_key][day][hour].append(time_str)
        
        files_processed += 1
        if files_processed % 500 == 0:
            print(f"  Processed {files_processed:,} / {len(xml_files):,} files...")
            print(f"    Matched trips: {matched_trips:,}, Skipped: {skipped_trips:,}")
    
    except Exception as e:
        continue

print(f"\n✓ Processed all files")
print(f"  Matched trips: {matched_trips:,}")
print(f"  Skipped trips: {skipped_trips:,}")
print(f"  Unique stops: {len(stop_schedules):,}")

# Convert to database records
print("\nBuilding database records...")
db_records = []

for naptan_id, patterns in stop_schedules.items():
    for pattern_id, validity_periods in patterns.items():
        for validity_key, days in validity_periods.items():
            # Parse validity dates from key
            vf_str, vt_str = validity_key.split('_')
            vf = datetime.strptime(vf_str, '%Y-%m-%d').date()
            vt = datetime.strptime(vt_str, '%Y-%m-%d').date()
            
            for day, hours in days.items():
                for hour, times in hours.items():
                    sorted_times = sorted(set(times))
                    trips = len(sorted_times)
                    first = sorted_times[0] if sorted_times else None
                    last = sorted_times[-1] if sorted_times else None
                    
                    # Calc headway
                    headway = None
                    if len(sorted_times) > 1:
                        time_objs = [datetime.strptime(t, '%H:%M') for t in sorted_times]
                        gaps = [(time_objs[i+1] - time_objs[i]).total_seconds() / 60 
                               for i in range(len(time_objs)-1)]
                        headway = int(sum(gaps) / len(gaps)) if gaps else None
                    
                    times_str = '{' + ','.join(sorted_times) + '}'
                    
                    db_records.append((
                        naptan_id, pattern_id, day, hour,
                        times_str, trips, headway, first, last,
                        vf, vt
                    ))

print(f"✓ Built {len(db_records):,} database records")

# Insert in batches
print("\nInserting to database...")
batch_size = 10000
for i in range(0, len(db_records), batch_size):
    batch = db_records[i:i+batch_size]
    
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO stop_schedule (
            naptan_id, pattern_id, day_of_week, hour,
            scheduled_arrivals, trips_per_hour, avg_headway_minutes,
            first_arrival, last_arrival,
            valid_from, valid_to
        ) VALUES %s
        """,
        batch
    )
    
    if (i + batch_size) % 100000 == 0:
        progress = ((i + batch_size) / len(db_records)) * 100
        print(f"  Progress: {min(i + batch_size, len(db_records)):,} / {len(db_records):,} ({progress:.1f}%)")

conn.commit()

print(f"\n✓ Inserted {len(db_records):,} records")

# Summary
cur.execute("""
    SELECT 
        COUNT(DISTINCT naptan_id) as stops,
        COUNT(DISTINCT pattern_id) as patterns,
        COUNT(DISTINCT (valid_from, valid_to)) as validity_periods,
        COUNT(*) as records,
        pg_size_pretty(pg_total_relation_size('stop_schedule')) as size
    FROM stop_schedule
""")

stats = cur.fetchone()
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Stops: {stats[0]:,}")
print(f"Patterns: {stats[1]:,}")
print(f"Validity periods: {stats[2]:,}")
print(f"Records: {stats[3]:,}")
print(f"Table size: {stats[4]}")

cur.close()
conn.close()

print("\n✓ Complete!")
