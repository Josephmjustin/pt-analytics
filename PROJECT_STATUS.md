# PT Analytics - Project Status

## Current State (as of 2025-12-01)

### Completed Features
- ✅ BODS GTFS-RT API integration
- ✅ PostgreSQL + PostGIS database (Docker)
- ✅ Live data ingestion pipeline
- ✅ Continuous polling via Prefect (60s intervals)
- ✅ Duplicate prevention
- ✅ Batch inserts optimized
- ✅ GTFS Static data loaded (stops, routes, trips, stop_times)
- ✅ PostGIS spatial indexing on stops and vehicle positions
- ✅ Trip_id linkage between RT and Static data working
- ✅ Stop arrival detection (< 100m threshold)
- ✅ Headway calculation queries
- ✅ Bunching detection algorithm (< 5min threshold)
- ✅ Bunching scores table (aggregated metrics)
- ✅ Automated analysis pipeline via Prefect (5min intervals)
- ✅ Prefect Cloud orchestration and monitoring

### Database
- **Table:** vehicle_positions - 123,859 rows (growing continuously)
- **Table:** gtfs_stop_times - 8M+ rows (1.7GB)
- **Table:** gtfs_trips - 16,477 trips
- **Table:** gtfs_stops - 247 stops in Liverpool scope
- **Table:** gtfs_routes - 20+ routes tracked
- **Table:** bunching_scores - 185 records (37 stops × 5 analysis runs)
- **Time range:** 2025-11-21 22:40 to present (continuously updating)
- **Region:** Liverpool bounding box (53.418-53.441, -2.976--2.876)

### Tech Stack
- Python 3.x
- PostgreSQL 15 + PostGIS 3.4
- Docker + Docker Compose
- Prefect Cloud (orchestration)
- Libraries: psycopg2, gtfs-realtime-bindings, requests, python-dotenv, prefect

### Architecture
**Data Pipeline:**
```
BODS API → Prefect (60s) → PostgreSQL → Prefect (5min) → Bunching Scores
```

**Two Prefect Flows:**
1. **Ingestion Flow:** Polls BODS API every 60 seconds, stores raw vehicle positions
2. **Analysis Flow:** Runs bunching detection every 5 minutes, stores aggregated scores

**Key Design Decision:**
- Store aggregated scores (bunching_scores table) instead of running expensive queries on raw data
- Enables fast dashboard queries and trend analysis
- Raw data kept for 30 days (retention policy to be implemented)

### Data Quality Findings
- **Match rate:** 3.4% (3,266 out of 94,944 positions from initial load)
- **Root cause:** Different identifier schemes between GTFS-RT and GTFS Static
- **Working dataset:** Growing continuously with matched positions across 20+ routes
- **Strategy:** Focus analysis on matched data, reconciliation layer planned for Phase 2

### Current Analysis Capability
- ✅ Stop arrival detection (spatial join + trip_id matching)
- ✅ Actual vs scheduled headway comparison
- ✅ Bunching rate calculation by stop
- ✅ Time-series of bunching scores
- ✅ Top bunching problem stops identified:
  - Friendship Inn: 80.0% bunching rate
  - Renshaw Street: 50.0% bunching rate
  - Stockport Interchange: 48.2% bunching rate

### SQL Queries Developed
1. `01_stop_arrivals.sql` - Detect bus arrivals at stops
2. `02_headway_calculation.sql` - Calculate time between arrivals
3. `03_bunching_detection.sql` - Identify bunched buses
4. `04_bunching_summary.sql` - Aggregate statistics by stop
5. `05_scheduled_vs_actual.sql` - Compare actual vs scheduled times

### Known Limitations
- RT/Static match rate: 3.4% (reconciliation needed in Phase 2)
- Data sparsity: Only 8 stops have 3+ arrivals for analysis
- No data retention policy yet (raw data accumulating)
- Dashboard not yet built

### Next Session Priorities
1. Implement data retention policy (delete data > 30 days)
2. Build simple dashboard (Streamlit)
   - Live bunching scores by stop
   - Trend charts over time
   - Top problem stops
3. Deploy dashboard to Streamlit Cloud (free)
4. Move database to Neon (free PostgreSQL cloud)
5. Update README with architecture diagrams

### Configuration
- **API:** BODS GTFS-RT endpoint
- **Region:** Liverpool (53.418-53.441, -2.976--2.876)
- **Poll interval:** 60 seconds (Prefect scheduled)
- **Analysis interval:** 5 minutes (Prefect scheduled)
- **Data retention:** Manual cleanup (30 days policy planned)
- **Orchestration:** Prefect Cloud (free tier)

### Project Structure
```
pt-analytics/
├── flows/
│   ├── ingestion_flow.py       # Data ingestion Prefect flow
│   ├── analysis_flow.py        # Analysis Prefect flow
│   └── deploy_pipeline.py      # Deployment configuration
├── scripts/
│   ├── continuous_poller.py    # BODS API polling logic
│   ├── calculate_bunching_scores.py  # Bunching analysis
│   ├── load_gtfs_static.py     # GTFS Static data loader
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

### Key Decisions Made
- Self-hosted tool + public demo (two-tier approach)
- Focus on service quality vs driver behavior
- Liverpool first, then multi-region
- Depth before breadth strategy
- Analyze matched data only (defer reconciliation to Phase 2)
- Optimize for portfolio showcase over production perfection
- Use Prefect Cloud for reliable orchestration
- Store aggregated scores instead of querying raw data repeatedly

### Portfolio Readiness
**Completed:**
- ✅ Working data pipeline
- ✅ Production-style orchestration (Prefect Cloud)
- ✅ Spatial data analysis (PostGIS)
- ✅ Time-series analysis
- ✅ Clean project structure

**In Progress:**
- ⏳ Dashboard for visualization
- ⏳ Cloud deployment (database + dashboard)
- ⏳ Documentation (README, architecture diagrams)

**Timeline:**
- Current: 2-3 sessions to complete dashboard + deployment
- Target: Portfolio-ready in 1 week