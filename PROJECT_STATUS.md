# PT Analytics - Project Status

## Current State (as of 2025-12-02)

### Completed Features
- ✅ BODS GTFS-RT API integration
- ✅ PostgreSQL + PostGIS database (Docker)
- ✅ Live data ingestion pipeline with geom population
- ✅ Continuous polling via Prefect Cloud (60s intervals)
- ✅ Duplicate prevention
- ✅ Batch inserts optimized
- ✅ **OpenStreetMap stops integration (251 stops)**
- ✅ PostGIS spatial indexing on stops and vehicle positions
- ✅ **OSM-based stop arrival detection (no GTFS Static dependency)**
- ✅ Headway calculation queries
- ✅ Bunching detection algorithm (< 5min threshold)
- ✅ Bunching scores table (aggregated metrics)
- ✅ Automated analysis pipeline via Prefect Cloud (5min intervals)
- ✅ **Production-grade spatial matching (7.2M position-stop matches)**

### Architecture Breakthrough
**Problem Solved:** GTFS Static data sync issues eliminated

**Old Approach (Failed):**
```
GTFS-RT → trip_id matching → GTFS Static → 3.4% match rate → 37 stops
```

**New OSM Approach (Working):**
```
GTFS-RT → OSM spatial matching → 251 stops → 240 stops analyzed
```

**Key Innovation:**
- Spatial proximity matching only (within 100m of OSM stop)
- No dependency on GTFS Static trip schedules
- Works with any transit agency data
- Always current (OSM updates continuously)

### Database
- **Table:** vehicle_positions - 3.4M+ rows (continuously growing)
- **Table:** osm_stops - 251 Liverpool bus stops
- **Table:** bunching_scores - 720+ records (240 stops × 3+ analysis runs)
- **Spatial matches:** 7.2M position-stop proximity matches
- **Time range:** 2025-11-21 to present (11 days continuous)
- **Region:** Liverpool bounding box (53.418-53.441, -2.976--2.876)
- **Coverage:** 246 of 251 stops (98%) have vehicle arrivals

### Tech Stack
- Python 3.x
- PostgreSQL 15 + PostGIS 3.4
- Docker + Docker Compose
- Prefect Cloud (orchestration & monitoring)
- OpenStreetMap Overpass API
- Libraries: psycopg2, gtfs-realtime-bindings, requests, python-dotenv, prefect

### Architecture
**Data Pipeline:**
```
BODS API → Prefect (60s) → PostgreSQL + geom → Prefect (5min) → OSM Matching → Bunching Scores
```

**Two Prefect Flows:**
1. **Ingestion Flow:** Polls BODS API every 60 seconds, stores positions with spatial geometry
2. **Analysis Flow:** Runs OSM-based bunching detection every 5 minutes, analyzes 240 stops

**Spatial Matching Logic:**
```sql
-- Simple, reliable, no trip_id needed
ST_DWithin(vehicle.geom, osm_stop.location, 100m)
```

### Performance Metrics
- **Data ingested:** 3.4M+ vehicle positions over 11 days
- **Vehicles tracked:** 20,833 unique vehicles
- **Routes covered:** 6,006 unique routes
- **Stops analyzed:** 240 stops (6.5x improvement over old method)
- **Analysis speed:** 5 seconds for full bunching calculation
- **Match rate:** 98% of OSM stops have vehicle arrivals

### Current Analysis Results
**Top Problem Stops (Dec 2 data):**
- EVERTON VALLEY/ST DOMINGO ROAD: 80.3% bunching rate
- ROCKY LANE/LOWER BRECK ROAD: 80.0% bunching rate
- WALTON BRECK ROAD/BLESSINGTON ROAD: 79.7% bunching rate
- EAST PRESCOT RD/FINCH LANE: 79.4% bunching rate
- SHEIL ROAD/WEST DERBY ROAD: 79.0% bunching rate

**Average bunching rate across network:** 39.4%

### SQL Queries Developed
1. `01_stop_arrivals.sql` - Detect bus arrivals at stops (GTFS-based, deprecated)
2. `02_headway_calculation.sql` - Calculate time between arrivals
3. `03_bunching_detection.sql` - Identify bunched buses
4. `04_bunching_summary.sql` - Aggregate statistics by stop
5. `05_scheduled_vs_actual.sql` - Compare actual vs scheduled times
6. **NEW:** OSM-based spatial matching queries (in calculate_bunching_scores_osm.py)

### Scripts
- `load_osm_stops.py` - Fetch and load OpenStreetMap bus stops
- `calculate_bunching_scores_osm.py` - OSM-based bunching analysis (production)
- `calculate_bunching_scores.py` - GTFS-based analysis (deprecated)
- `continuous_poller.py` - BODS API polling with geom population
- `load_gtfs_static.py` - GTFS Static loader (kept for reference/scheduled data)

### Known Limitations & Solutions
- ~~RT/Static match rate: 3.4%~~ ✅ **SOLVED with OSM**
- ~~Data sparsity: Only 8 stops~~ ✅ **SOLVED: 240 stops**
- ~~Spatial queries too slow~~ ✅ **SOLVED: 5 second analysis**
- ~~Missing geom in new data~~ ✅ **SOLVED: Auto-populated in poller**
- No data retention policy yet (raw data accumulating - 3.4M rows)
- Dashboard not yet built
- Not deployed to cloud yet

### Next Session Priorities
1. Implement data retention policy (delete data > 30 days)
2. Build Streamlit dashboard:
   - Live bunching scores by stop
   - Trend charts over time
   - Top problem stops heatmap
   - Route-level analysis
3. Deploy to cloud:
   - Database: Neon (free PostgreSQL)
   - Dashboard: Streamlit Cloud (free)
4. Update README with architecture diagrams
5. Create demo video/screenshots for portfolio

### Configuration
- **API:** BODS GTFS-RT endpoint
- **OSM:** Overpass API for stop locations
- **Region:** Liverpool (53.418-53.441, -2.976--2.876)
- **Poll interval:** 60 seconds (Prefect scheduled)
- **Analysis interval:** 5 minutes (Prefect scheduled)
- **Spatial threshold:** 100 meters for stop proximity
- **Bunching threshold:** < 5 minutes headway
- **Min arrivals for analysis:** 3+ per stop
- **Data retention:** Manual cleanup (30 days policy planned)
- **Orchestration:** Prefect Cloud (free tier)

### Project Structure
```
pt-analytics/
├── flows/
│   ├── ingestion_flow.py       # Data ingestion Prefect flow
│   ├── analysis_flow.py        # OSM-based analysis flow
│   └── deploy_pipeline.py      # Deployment configuration
├── scripts/
│   ├── continuous_poller.py    # BODS API polling with geom
│   ├── calculate_bunching_scores_osm.py  # OSM bunching analysis (ACTIVE)
│   ├── calculate_bunching_scores.py      # GTFS analysis (deprecated)
│   ├── load_osm_stops.py       # OSM stop loader
│   ├── load_gtfs_static.py     # GTFS Static loader
│   └── setup_db.py             # Database initialization
├── analysis/
│   ├── 01_stop_arrivals.sql
│   ├── 02_headway_calculation.sql
│   ├── 03_bunching_detection.sql
│   ├── 04_bunching_summary.sql
│   └── 05_scheduled_vs_actual.sql
├── docker-compose.yml          # PostgreSQL + PostGIS
└── requirements.txt
```

### Key Technical Decisions
- **OSM over GTFS Static:** Eliminates data sync issues, always current
- **Spatial matching over trip_id:** More reliable, works with incomplete data
- **Prefect Cloud over local:** Better scheduling, monitoring, logging
- **100m threshold:** Industry standard for stop proximity
- **5min bunching threshold:** Conservative definition for portfolio
- **Store aggregated scores:** Fast queries, enables trend analysis
- **Local development, cloud deployment:** Iterate fast, deploy when ready

### Lessons Learned
1. **GTFS-RT and GTFS Static sync is hard:** Real-world data has mismatches
2. **OSM is more reliable than agency data:** Always current, well-maintained
3. **Spatial queries need geom column:** lat/lon alone isn't enough
4. **Prefect Cloud > Prefect Local:** Scheduling actually works
5. **Portfolio value > Production perfection:** OSM approach is simpler AND better

### Portfolio Readiness
**Completed:**
- ✅ Production-scale data pipeline (3.4M+ records)
- ✅ Real-world problem solving (GTFS sync → OSM pivot)
- ✅ Spatial data analysis at scale (7.2M matches)
- ✅ Orchestration with industry tools (Prefect Cloud)
- ✅ Clean, documented codebase on GitHub
- ✅ 11 days of continuous operation

**In Progress:**
- ⏳ Dashboard for visualization (1-2 sessions)
- ⏳ Cloud deployment (1 session)
- ⏳ Documentation (README, architecture diagrams)

**Timeline:**
- Current: 2-3 sessions to complete dashboard + deployment
- Target: Portfolio-ready by end of week

### What Makes This Portfolio-Strong
1. **Real problem solved:** GTFS Static sync → OSM innovation
2. **Production scale:** 3.4M records, 20K vehicles, 240 stops
3. **Modern stack:** Prefect, PostGIS, OSM, cloud-native design
4. **Complete pipeline:** Ingestion → Analysis → Scoring → (Dashboard next)
5. **Demonstrates learning:** Pivoted approach when original failed
6. **Domain expertise:** Transit operations + spatial analysis + backend engineering