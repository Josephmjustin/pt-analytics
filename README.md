# PT Analytics - Service Reliability Index Platform

Real-time transit service reliability analytics for UK bus networks. Transforms raw vehicle position data into actionable Service Reliability Index (SRI) scores that quantify transit service quality across multiple dimensions.

**Live Demo:** [ptstat.onrender.com](https://ptstat.onrender.com)

## Overview

PT Analytics is a production-grade transit analytics platform that calculates Service Reliability Index (SRI) scores for every route on Liverpool/Merseyside's bus network. The system processes real-time vehicle positions from the UK Bus Open Data Service (BODS) and generates weighted reliability scores across four key dimensions:

- **Headway Consistency (40%)** - Measures regularity of service intervals
- **Schedule Adherence (30%)** - Tracks on-time performance vs historical patterns  
- **Journey Time Consistency (20%)** - Evaluates travel time reliability
- **Service Delivery (10%)** - Monitors trip completion rates

**Current Network Performance:** 53.7/100 (Grade: F)
- 294 services analyzed across 78 routes
- 900 stops monitored with spatial precision
- Real-time updates every 10 minutes

## Key Innovation: TransXChange + Spatial Matching

PT Analytics uses UK-native TransXChange timetable data combined with spatial matching to achieve high-accuracy stop detection:

- **Data Source:** TransXChange XML (native UK transit format)
- **Stop Coverage:** 18,993 stops across 290 routes loaded into database
- **Spatial Matching:** In-memory route-aware stop matching (30m radius)
- **Match Rate:** 38.7% stop events matched to valid stops
- **Performance:** 100x faster than per-event database queries

This approach eliminates GTFS Static/RT mismatch issues while maintaining compatibility with UK transit data standards.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  UK Bus Open Data Service (BODS) - SIRI-VM Feed                  │
│  Merseyside Region Real-Time Vehicle Positions                   │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  ORACLE CLOUD VM - Data Processing (Always Free Tier)            │
│  ┌────────────────────────────────────────────────────────┐      │
│  │ Ingestion (10s)    → BODS SIRI-VM polling              │      │
│  │ Analysis (10min)   → Stop detection + matching         │      │
│  │ SRI Pipeline (10min) → 4-component score calculation   │      │
│  │ Cleanup (10min)    → 15-minute rolling window          │      │
│  └────────────────────────────────────────────────────────┘      │
│  Cron-based orchestration • Zero external dependencies           │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  SUPABASE - PostgreSQL 15 + PostGIS 3.4                          │
│  ┌────────────────────────────────────────────────────────┐      │
│  │ Real-time Layer:                                       │      │
│  │  • vehicle_positions (15-min rolling window)           │      │
│  │  • vehicle_arrivals (1-hour retention)                 │      │
│  │                                                        │      │
│  │ TransXChange Static Data:                              │      │
│  │  • txc_stops (18,993 stops with coordinates)           │      │
│  │  • txc_route_patterns (290 routes, all directions)     │      │
│  │  • txc_pattern_stops (route-stop associations)         │      │
│  │                                                        │      │
│  │ SRI Analytics Tables:                                  │      │
│  │  • headway_patterns (consistency metrics)              │      │
│  │  • schedule_adherence_patterns (historical baseline)   │      │
│  │  • journey_time_patterns (stop-to-stop reliability)    │      │
│  │  • service_delivery_patterns (trip volumes)            │      │
│  │  • [component]_scores (0-100 normalized scores)        │      │
│  │  • service_reliability_index (final weighted SRI)      │      │
│  │  • network_reliability_index (network aggregates)      │      │
│  │                                                        │      │
│  │ Storage: 142 MB (optimized with cleanup)               │      │
│  └────────────────────────────────────────────────────────┘      │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  GOOGLE CLOUD RUN - FastAPI Backend (Containerized)              │
│  ┌────────────────────────────────────────────────────────┐      │
│  │ Health & Status:                                       │      │
│  │  • GET /health                                         │      │
│  │  • GET /stops/stats                                    │      │
│  │                                                        │      │
│  │ Stop Analytics:                                        │      │
│  │  • GET /stops                    (all stops + scores)  │      │
│  │  • GET /stops/{id}               (stop details)        │      │
│  │  • GET /stops/{id}/routes        (routes at stop)      │      │
│  │                                                        │      │
│  │ Route Analytics:                                       │      │
│  │  • GET /routes                   (all routes)          │      │
│  │  • GET /routes/{id}              (route details)       │      │
│  │  • GET /routes/{id}/csv          (export data)         │      │
│  │                                                        │      │
│  │ Real-Time Data:                                        │      │
│  │  • GET /vehicles/live            (current positions)   │      │
│  │                                                        │      │
│  │ SRI Endpoints (Future):                                │      │
│  │  • GET /sri/network              (overall score)       │      │
│  │  • GET /sri/routes/{id}          (route SRI)           │      │
│  │  • GET /sri/hotspots             (problem areas)       │      │
│  │                                                        │      │
│  │ HTTPS via Cloudflare Tunnel                            │      │
│  └────────────────────────────────────────────────────────┘      │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  RENDER - React Dashboard (Static Hosting)                       │
│  • Interactive Leaflet map with OSM tiles                        │
│  • Real-time vehicle tracking (10s refresh)                      │
│  • Color-coded stop markers (bunching severity)                  │
│  • Route and stop analytics views                                │
│  • SRI dashboard (planned): scores, grades, trends               │
└──────────────────────────────────────────────────────────────────┘
```

## Service Reliability Index (SRI) Methodology

### Scoring Framework

PT Analytics calculates a comprehensive 0-100 reliability score for every route-direction-operator service using four weighted components:

#### 1. Headway Consistency (40% weight)
**Measures:** Regularity of time intervals between buses at stops

**Metrics:**
- Coefficient of Variation (CV) of headways
- Bunching rate (% of headways < 50% of median)
- Average headway deviation

**Scoring:**
- Excellent: CV ≤ 0.20 → 100 points
- Poor: CV ≥ 0.60 → 0 points
- Linear interpolation between thresholds

**Current Performance:** 9.8/100 average (high variability detected)

#### 2. Schedule Adherence (30% weight)
**Measures:** On-time performance relative to expected patterns

**Methodology:**
- **Baseline:** 30-day historical median arrival time per stop/hour
- **On-time window:** ±2 minutes of baseline
- **Tracks:** Early arrivals, on-time, late arrivals

**Scoring:**
- Excellent: ≥95% on-time → 100 points
- Poor: ≤60% on-time → 0 points

**Current Performance:** 100.0/100 (insufficient baseline data - will stabilize over time)

**Note:** Uses historical pattern baseline rather than published schedules. Can be enhanced with TransXChange scheduled times for absolute punctuality measurement.

#### 3. Journey Time Consistency (20% weight)
**Measures:** Reliability of stop-to-stop travel times

**Metrics:**
- CV of journey times between consecutive stops
- 85th percentile journey time
- Journey time variability patterns

**Scoring:**
- Excellent: CV ≤ 0.15 → 100 points
- Poor: CV ≥ 0.50 → 0 points

**Current Performance:** 46.0/100 (moderate variability)

#### 4. Service Delivery (10% weight)
**Measures:** Trip completion rates and service availability

**Metrics:**
- Observed trip volumes per route/hour
- Service delivery rate (placeholder: 100%)

**Scoring:**
- Excellent: ≥98% delivery → 100 points
- Poor: ≤80% delivery → 0 points

**Current Performance:** 100.0/100

**Enhancement Opportunity:** Integrate TransXChange VehicleJourney data to detect actual cancellations and partial trips.

### Final SRI Calculation

```
SRI = (Headway × 0.40) + (Schedule × 0.30) + (Journey × 0.20) + (Service × 0.10)
```

**Letter Grades:**
- A: 90-100 (Excellent)
- B: 80-89 (Good)
- C: 70-79 (Satisfactory)
- D: 60-69 (Poor)
- F: 0-59 (Failing)

### Network-Level Aggregation

**Network SRI:** Average of all route-level SRI scores
- Current: 53.7/100 (Grade: F)
- 294 services analyzed
- Grade distribution: 1.7% B, 2.0% C, 3.4% D, 92.9% F

**Interpretation:** Low scores driven primarily by headway inconsistency (21.4% average bunching rate), indicating systemic service reliability issues across the network.

## Technology Stack

### Backend
- **Language:** Python 3.12
- **Database:** PostgreSQL 15 + PostGIS 3.4
- **API Framework:** FastAPI 0.104+ with Uvicorn
- **Data Processing:** 
  - psycopg2 (database connectivity)
  - GeoPandas + Shapely (spatial operations)
  - lxml (TransXChange XML parsing)
  - NumPy/Pandas (statistical analysis)

### Infrastructure
- **Database:** Supabase (managed PostgreSQL with PostGIS)
- **Compute:** Oracle Cloud VM Always Free tier (ARM or AMD)
- **API Hosting:** Google Cloud Run (containerized FastAPI)
- **Frontend Hosting:** Render (static site)
- **Security:** Cloudflare Tunnel (HTTPS without exposing VM IP)
- **Orchestration:** Cron (lightweight, no external dependencies)

### Frontend
- **Framework:** React 18 with Vite
- **Mapping:** Leaflet + OpenStreetMap tiles
- **UI:** TailwindCSS (planned: shadcn/ui migration)
- **State Management:** React hooks

## Data Pipeline Architecture

### 1. Ingestion Layer (10-second intervals)
**Purpose:** Continuous real-time vehicle position collection

**Process:**
1. Poll BODS SIRI-VM API for Merseyside region
2. Parse XML vehicle position updates
3. Extract: vehicle_id, route, direction, operator, lat/lon, timestamp
4. Batch insert to `vehicle_positions` table
5. Mark all as `analyzed = false`

**Output:** ~1,000 positions per minute

### 2. Analysis Layer (10-minute intervals)
**Purpose:** Stop detection and arrival event generation

**Optimized In-Memory Approach:**
1. Load all 18,993 stops from `txc_stops` into memory (one-time per run)
2. Build route-indexed stop dictionary: `{route → direction → [stops]}`
3. Detect stop events from unanalyzed positions using movement patterns
4. Match each stop event to nearest valid stop on that route (30m radius)
5. Bulk insert matched arrivals to `vehicle_arrivals`
6. Mark positions as `analyzed = true`

**Performance:** Processes 2,400+ events in 30 seconds (100x faster than per-event DB queries)

**Output:** ~50-100 vehicle arrivals per run

### 3. SRI Calculation Pipeline (10-minute intervals)
**Purpose:** Multi-stage reliability score computation

**Phase 1: Pattern Aggregation**
- `aggregate_headway_patterns.py` → Calculate headway statistics
- `aggregate_schedule_adherence_patterns.py` → Historical baseline comparison
- `aggregate_journey_time_patterns.py` → Stop-to-stop journey times
- `aggregate_service_delivery_patterns.py` → Trip volume tracking

**Phase 2: Component Scoring**
- `calculate_component_scores.py` → Normalize patterns to 0-100 scores using config thresholds

**Phase 3: Final SRI**
- `calculate_sri_scores.py` → Weighted combination + letter grades
- Generate network-level aggregates

**Output:** 
- 294 route-level SRI scores
- Network SRI: 53.7/100
- Grade distribution and rankings

### 4. Cleanup Layer (10-minute intervals)
**Purpose:** Storage optimization and data lifecycle management

**Process:**
1. Delete `vehicle_positions` older than 15 minutes (analyzed only)
2. Delete `vehicle_arrivals` older than 1 hour
3. Run PostgreSQL VACUUM to reclaim disk space
4. Maintain stable 142MB database size

**Result:** Continuous operation without storage growth

## Database Schema

### Real-Time Tables

#### vehicle_positions
```sql
CREATE TABLE vehicle_positions (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    route_name TEXT,
    direction TEXT,
    operator TEXT,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    analyzed BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_positions_analyzed ON vehicle_positions(analyzed);
CREATE INDEX idx_positions_timestamp ON vehicle_positions(timestamp);
```

#### vehicle_arrivals
```sql
CREATE TABLE vehicle_arrivals (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    route_name TEXT NOT NULL,
    direction TEXT,
    operator TEXT,
    naptan_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    distance_m FLOAT,
    dwell_time_seconds INT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_arrivals_route_stop ON vehicle_arrivals(route_name, naptan_id, timestamp);
CREATE INDEX idx_arrivals_direction ON vehicle_arrivals(direction);
CREATE INDEX idx_arrivals_operator ON vehicle_arrivals(operator);
```

### TransXChange Static Data

#### txc_stops
```sql
CREATE TABLE txc_stops (
    naptan_id TEXT PRIMARY KEY,
    stop_name TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    locality TEXT,
    indicator TEXT
);
CREATE INDEX idx_txc_stops_location ON txc_stops USING GIST(
    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
);
```

#### txc_route_patterns
```sql
CREATE TABLE txc_route_patterns (
    pattern_id TEXT PRIMARY KEY,
    route_name TEXT NOT NULL,
    direction TEXT NOT NULL,
    description TEXT
);
CREATE INDEX idx_patterns_route ON txc_route_patterns(route_name, direction);
```

### SRI Analytics Tables

#### headway_patterns
```sql
CREATE TABLE headway_patterns (
    route_name TEXT NOT NULL,
    direction TEXT NOT NULL,
    operator TEXT NOT NULL,
    stop_id TEXT NOT NULL,
    year INT, month INT, day_of_week INT, hour INT,
    median_headway_minutes NUMERIC,
    avg_headway_minutes NUMERIC,
    std_headway_minutes NUMERIC,
    coefficient_of_variation NUMERIC,
    bunching_rate NUMERIC,
    observation_count INT,
    last_updated TIMESTAMP,
    PRIMARY KEY (route_name, direction, operator, stop_id, year, month, day_of_week, hour)
);
```

#### service_reliability_index
```sql
CREATE TABLE service_reliability_index (
    route_name TEXT NOT NULL,
    direction TEXT NOT NULL,
    operator TEXT NOT NULL,
    year INT, month INT, day_of_week INT, hour INT,
    headway_consistency_score NUMERIC,
    schedule_adherence_score NUMERIC,
    journey_time_consistency_score NUMERIC,
    service_delivery_score NUMERIC,
    headway_weight NUMERIC,
    schedule_weight NUMERIC,
    journey_time_weight NUMERIC,
    service_delivery_weight NUMERIC,
    sri_score NUMERIC NOT NULL,
    sri_grade CHAR(1) NOT NULL,
    observation_count INT,
    data_completeness NUMERIC,
    calculation_timestamp TIMESTAMP,
    PRIMARY KEY (route_name, direction, operator, year, month, day_of_week, hour)
);
```

#### sri_config
```sql
CREATE TABLE sri_config (
    id SERIAL PRIMARY KEY,
    config_version NUMERIC NOT NULL,
    effective_date DATE NOT NULL,
    headway_weight NUMERIC DEFAULT 0.40,
    schedule_weight NUMERIC DEFAULT 0.30,
    journey_time_weight NUMERIC DEFAULT 0.20,
    service_delivery_weight NUMERIC DEFAULT 0.10,
    headway_cv_excellent NUMERIC DEFAULT 0.20,
    headway_cv_poor NUMERIC DEFAULT 0.60,
    schedule_on_time_excellent NUMERIC DEFAULT 95.0,
    schedule_on_time_poor NUMERIC DEFAULT 60.0,
    journey_cv_excellent NUMERIC DEFAULT 0.15,
    journey_cv_poor NUMERIC DEFAULT 0.50,
    service_delivery_excellent NUMERIC DEFAULT 98.0,
    service_delivery_poor NUMERIC DEFAULT 80.0,
    grade_a_threshold NUMERIC DEFAULT 90.0,
    grade_b_threshold NUMERIC DEFAULT 80.0,
    grade_c_threshold NUMERIC DEFAULT 70.0,
    grade_d_threshold NUMERIC DEFAULT 60.0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Setup & Deployment

### Prerequisites
- Python 3.12+
- PostgreSQL 15+ with PostGIS 3.4
- BODS API key (free registration: data.bus-data.dft.gov.uk)
- Oracle Cloud account (Always Free tier)
- Supabase account (free tier)

### Local Development

1. **Clone repository:**
```bash
git clone https://github.com/Josephmjustin/pt-analytics.git
cd pt-analytics
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your credentials:
# - BODS_API_KEY
# - DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
```

5. **Initialize database:**
```bash
# Create TransXChange schema and load data
python scripts/create_txc_schema_optimized.py
python scripts/load_txc_data.py

# Create SRI tables
python scripts/create_sri_schema.py

# Initialize config
INSERT INTO sri_config (config_version, effective_date) 
VALUES (1.0, '2024-01-01');
```

6. **Test pipeline locally:**
```bash
# Test ingestion
python cron_scripts/ingest_bods.py

# Test analysis
python cron_scripts/run_analysis.py

# Verify data
psql $DATABASE_URL -c "SELECT COUNT(*) FROM vehicle_positions;"
psql $DATABASE_URL -c "SELECT * FROM service_reliability_index LIMIT 5;"
```

### Production Deployment

#### 1. Database (Supabase)

```bash
# 1. Create Supabase project at supabase.com
# 2. Enable PostGIS extension in SQL Editor:
CREATE EXTENSION IF NOT EXISTS postgis;

# 3. Run all schema creation scripts via Supabase SQL Editor:
# - create_txc_schema_optimized.sql
# - create_sri_schema.sql

# 4. Load TransXChange data (from local machine):
python scripts/load_txc_data.py

# 5. Note connection string from Supabase Settings > Database
```

#### 2. Compute (Oracle Cloud VM)

```bash
# SSH to Oracle Cloud VM
ssh ubuntu@your-vm-ip

# Install dependencies
sudo apt update
sudo apt install python3-pip python3-venv git -y

# Clone repository
git clone https://github.com/Josephmjustin/pt-analytics.git
cd pt-analytics

# Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
nano .env
# Add your database credentials and BODS API key

# Setup cron jobs
crontab -e
# Add these lines:
*/1 * * * * cd ~/pt-analytics && /home/ubuntu/pt-analytics/venv/bin/python cron_scripts/ingest_bods.py >> logs/ingestion.log 2>&1
*/10 * * * * cd ~/pt-analytics && /home/ubuntu/pt-analytics/venv/bin/python cron_scripts/run_analysis.py >> logs/analysis.log 2>&1

# Create log directory
mkdir -p logs

# Test execution
python cron_scripts/ingest_bods.py
python cron_scripts/run_analysis.py
```

#### 3. API (Google Cloud Run)

```bash
# 1. Containerize FastAPI app
cd api
docker build -t pt-analytics-api .

# 2. Push to Google Container Registry
gcloud auth configure-docker
docker tag pt-analytics-api gcr.io/YOUR-PROJECT/pt-analytics-api
docker push gcr.io/YOUR-PROJECT/pt-analytics-api

# 3. Deploy to Cloud Run
gcloud run deploy pt-analytics-api \
  --image gcr.io/YOUR-PROJECT/pt-analytics-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DB_HOST=...,DB_PORT=...
```

#### 4. Frontend (Render)

```bash
# 1. Push React app to GitHub
cd frontend
git add .
git commit -m "Deploy frontend"
git push origin main

# 2. Create Static Site on Render.com
# - Connect GitHub repository
# - Build command: npm run build
# - Publish directory: dist
# - Add environment variable: VITE_API_URL=https://your-api.run.app

# 3. Deploy automatically triggers on git push
```

## Performance Metrics

### Current Production Statistics
- **Data Volume:** 3M+ vehicle positions processed
- **Stop Coverage:** 18,993 stops loaded, 900+ actively monitored
- **Route Coverage:** 290 routes, 294 analyzed services
- **Analysis Latency:** 30 seconds for 2,400 stop events
- **Storage:** 142 MB stable (with 15-min rolling window)
- **Uptime:** Continuous operation via cron
- **API Response:** <100ms average (Cloud Run)

### SRI Calculation Performance
- **Pattern Aggregation:** 4 scripts, ~5 seconds total
- **Component Scoring:** 4 scores, ~2 seconds total
- **Final SRI:** 294 services, ~1 second
- **Total Pipeline:** <10 seconds end-to-end

### Cost Efficiency
**Total Monthly Cost: $0**
- Supabase: Free tier (500MB database, 2GB bandwidth)
- Oracle Cloud: Always Free tier (ARM VM, 24GB RAM)
- Google Cloud Run: Free tier (2M requests/month)
- Render: Free tier (static sites)
- Cloudflare Tunnel: Free

## Project Evolution

### Phase 1: GTFS Static Approach (Dec 2024)
- Attempted GTFS Static + GTFS-RT integration
- **Challenge:** trip_id mismatch (3.4% match rate)
- **Result:** Only 37 stops operational
- **Decision:** Abandon GTFS Static, pivot to spatial matching

### Phase 2: OpenStreetMap Integration (Dec 2024)
- Downloaded 251 OSM stops via Overpass API
- Implemented spatial proximity matching (100m radius)
- **Result:** 240 stops (6.5x improvement)
- **Insight:** Geographic approach more robust than schedule reconciliation

### Phase 3: TransXChange Migration (Dec 2024)
- Recognized TransXChange as UK-native standard
- Built XML parser for stops and route patterns
- Loaded 18,993 stops across 290 routes
- **Result:** 98% stop matching capability
- **Benefit:** Domain expertise demonstration for target employers

### Phase 4: Storage Optimization (Dec 2024)
- **Problem:** 1.8GB raw data growth unsustainable on free tier
- **Solution:** Running average aggregation + rolling cleanup
- Implemented 15-minute retention window for raw positions
- **Result:** 142MB stable storage, full analytical capability preserved

### Phase 5: SRI Platform Development (Dec 2024)
- Designed 4-component weighted scoring methodology
- Implemented pattern aggregation pipeline
- Built component score normalization
- Developed final SRI calculation engine
- **Result:** Production-ready reliability scoring system

### Phase 6: Production Deployment (Dec 2024)
- Multi-cloud architecture (Supabase + Oracle + GCP + Render)
- Replaced Prefect with lightweight cron orchestration
- Implemented Cloudflare Tunnel for secure API access
- Optimized analysis with in-memory stop matching (100x speedup)
- **Result:** Zero-cost, continuously operational platform

## Key Technical Achievements

### 1. In-Memory Spatial Matching
- **Problem:** Database queries for 2,400 stop events taking 10+ minutes
- **Solution:** Load all stops into Python dictionary indexed by route
- **Result:** 30 seconds for complete analysis (100x improvement)
- **Code:**
```python
class StopMatcher:
    def __init__(self, conn):
        # Load 18,993 stops once
        self.route_stops = {}  # {route → direction → [stops]}
        
    def match(self, stop_event, radius_m=30.0):
        # In-memory haversine calculation
        candidates = self.route_stops[route][direction]
        return find_nearest(candidates, lat, lon, radius_m)
```

### 2. Connection Pool Management
- **Problem:** Supabase free tier limited to 8 concurrent connections
- **Solution:** Try/finally blocks + single connection per script run
- **Result:** Zero connection leaks, stable operation

### 3. Historical Pattern Baseline
- **Problem:** TransXChange scheduled times require complex parsing
- **Solution:** Use 30-day historical median as "expected" arrival time
- **Result:** Real deviation measurement without schedule integration
- **Commercial Value:** Measures reliability vs actual operations, not outdated schedules

### 4. Deduplication in Component Scoring
- **Problem:** Pattern tables contained duplicates causing constraint violations
- **Solution:** GROUP BY deduplication CTEs before scoring
- **Result:** Robust scoring pipeline handling data quirks gracefully

### 5. Zero-Cost Cloud Architecture
- **Achievement:** Production platform running 24/7 on free tiers
- **Strategy:** Storage optimization + efficient cleanup + lightweight orchestration
- **Business Value:** Demonstrates cloud architecture skills without budget requirements

## API Endpoints (Current)

### Health & Monitoring
```
GET /health
→ Returns API status and database connectivity

GET /stops/stats  
→ Overall network statistics (stops count, routes, coverage)
```

### Stop Analytics
```
GET /stops
→ All stops with bunching scores and coordinates

GET /stops/{stop_id}
→ Detailed stop analytics (bunching patterns, routes serving stop)

GET /stops/{stop_id}/routes
→ All routes serving a specific stop
```

### Route Analytics
```
GET /routes
→ All routes in the network

GET /routes/{route_id}
→ Route details (stops, bunching rates, headway baselines)

GET /routes/{route_id}/csv
→ Export route data as CSV
```

### Real-Time Data
```
GET /vehicles/live
→ Current vehicle positions (last 5 minutes)
```

### Future SRI Endpoints (Planned)
```
GET /sri/network
→ Network-level SRI summary (current: 53.7/100)

GET /sri/routes
→ All route-level SRI scores with grades

GET /sri/routes/{route_id}
→ Detailed SRI breakdown for specific route

GET /sri/hotspots
→ Routes/stops with lowest reliability scores

GET /sri/trends
→ Historical SRI trends over time
```

## Current Performance Analysis

### Network Overview
- **Overall SRI:** 53.7/100 (Grade: F)
- **Services Analyzed:** 294
- **Routes Monitored:** 78 unique routes
- **Grade Distribution:**
  - A (90-100): 0 services (0%)
  - B (80-89): 5 services (1.7%)
  - C (70-79): 6 services (2.0%)
  - D (60-69): 10 services (3.4%)
  - F (<60): 273 services (92.9%)

### Component Performance
1. **Headway Consistency: 9.8/100** ⚠️ CRITICAL
   - Only 10.3% of services passing (score ≥60)
   - Average CV: 0.974 (poor threshold: 0.60)
   - Average bunching rate: 21.4%
   - **Interpretation:** Severe service irregularity across network

2. **Schedule Adherence: 100.0/100** ✅
   - All routes currently 100% on-time vs historical baseline
   - **Note:** Insufficient baseline data (needs 30+ days to stabilize)

3. **Journey Time Consistency: 46.0/100** ⚠️
   - 44% of services passing
   - Average CV: 0.376
   - **Interpretation:** Moderate travel time variability

4. **Service Delivery: 100.0/100** ✅
   - All observed trips completing
   - 5,247 trips tracked
   - **Note:** Placeholder metric (no cancellation detection yet)

### Best Performing Routes
1. Route 411 (outbound) - Unknown: **87.2/100** (Grade: B)
2. Route 409 (outbound) - Unknown: **84.9/100** (Grade: B)
3. Route 471 (inbound) - Unknown: **83.1/100** (Grade: B)
4. Route 76 (outbound) - Unknown: **70.1/100** (Grade: B)
5. Route X2 (inbound) - Unknown: **70.0/100** (Grade: C)

### Problem Routes (Sample)
Multiple routes scoring exactly 35/100 (Grade: F):
- Routes 41, 12, 10B, 17, 410
- **Common issue:** Very high headway variability
- **Actionable insight:** These routes need operational intervention

### Key Findings

**Primary Driver of Low Scores:** Headway inconsistency
- Weighted at 40%, this component dominates overall SRI
- 21.4% average bunching rate indicates systemic issues
- Routes with CV > 0.60 automatically score near 0/100 on headway component

**Secondary Factor:** Journey time variability
- 46/100 average shows moderate reliability issues
- Some routes have CV > 0.50 (poor threshold)

**Strengths:**
- Service delivery is consistent (100% of observed trips run)
- No major cancellation issues detected
- Best routes achieving B grades demonstrate achievable targets

## Known Limitations

### Data Limitations
- **Operator identification:** Many records show "Unknown" operator
- **Historical baseline:** Requires 30+ days for schedule adherence to stabilize
- **Cancellation detection:** No scheduled trip data for comparison
- **Direction matching:** Some stop events lack direction information

### Technical Limitations
- **Stop matching:** 38.7% match rate (vs 100% theoretical maximum)
  - Cause: Stop events detected between stops or vehicles in deadheading
  - Acceptable for reliability scoring (captures active service)
- **UK-specific:** BODS API only covers UK transit networks
- **Single region:** Currently limited to Merseyside/Liverpool area

### Operational Limitations
- **No real-time alerts:** SRI calculated every 10 minutes (not instant)
- **No predictive capability:** Scores reflect past performance only
- **Manual threshold tuning:** SRI thresholds set via database config

### Infrastructure Limitations
- **Free tier constraints:** 
  - Supabase: 500MB storage, 2GB bandwidth/month
  - Oracle: 24GB RAM, ARM architecture
  - Cloud Run: 2M requests/month
- **Cloudflare Tunnel:** URL changes on VM restart (not production-ready for public API)

## Future Enhancements

### Phase 2A: API Development
- [ ] Implement SRI-specific endpoints (`/sri/network`, `/sri/routes/{id}`)
- [ ] Add filtering, sorting, pagination to list endpoints
- [ ] Implement caching layer (Redis) for frequently accessed scores
- [ ] Add WebSocket support for real-time SRI updates
- [ ] Generate API documentation (OpenAPI/Swagger)

### Phase 2B: Dashboard Enhancement
- [ ] SRI scorecard widget (network summary)
- [ ] Route comparison tool (side-by-side SRI breakdown)
- [ ] Trend visualization (SRI over time with Chart.js)
- [ ] Hotspot heatmap (color-coded by SRI grade)
- [ ] Export functionality (CSV, PDF reports)

### Phase 3: Advanced Analytics
- [ ] Machine learning for bunching prediction (LSTM/GRU models)
- [ ] Anomaly detection (sudden SRI drops)
- [ ] Causal analysis (weather, events, time-of-day impacts)
- [ ] What-if scenarios (simulate service changes)

### Phase 4: TransXChange Schedule Integration
- [ ] Parse VehicleJourney scheduled arrival times
- [ ] Calculate absolute schedule adherence (vs published times)
- [ ] Detect actual cancellations (scheduled but not observed)
- [ ] Track partial trips (started but incomplete)
- [ ] Improve service delivery component accuracy

### Phase 5: Multi-Region Expansion
- [ ] Extend to Greater Manchester, West Midlands, etc.
- [ ] Comparative network analysis (cross-region benchmarking)
- [ ] Nationwide SRI leaderboard

### Phase 6: Operator Integration
- [ ] Alerts/notifications for operators (SRI drops, hotspots)
- [ ] API access for transit agencies (white-label SRI scoring)
- [ ] Feedback loop (operator interventions → SRI improvements)

## Acknowledgments

- **UK Department for Transport** - Bus Open Data Service (BODS) API
- **OpenStreetMap contributors** - Stop location reference data
- **TransXChange standard** - UK transit data specification
- **Supabase** - Managed PostgreSQL with PostGIS
- **Oracle Cloud** - Always Free tier compute
- **Open source community** - FastAPI, Leaflet, React, PostGIS

---

**Built with UK transit data standards. Ready for production deployment.**
