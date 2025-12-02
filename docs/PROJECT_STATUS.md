# PT Analytics - Project Status

## Current State (as of 2025-12-01)

### Completed Features
- BODS GTFS-RT API integration
- PostgreSQL + PostGIS database (Docker)
- Live data ingestion pipeline
- Continuous polling (60s intervals)
- Duplicate prevention
- Batch inserts optimized
- GTFS Static data loaded (stops, routes, trips, stop_times)
- PostGIS spatial indexing on stops and vehicle positions
- Trip_id linkage between RT and Static data working
- Route-level headway calculation query developed

### Database
- **Table:** vehicle_positions - 94,944 rows
- **Table:** gtfs_stop_times - 8M+ rows (1.7GB)
- **Table:** gtfs_trips - 16,477 trips
- **Table:** gtfs_stops - 247 stops in Liverpool scope
- **Table:** gtfs_routes - 20+ routes tracked
- **Time range:** 2025-11-21 22:40 to 2025-11-22 23:08
- **Region:** Liverpool bounding box (53.418-53.441, -2.976--2.876)

### Tech Stack
- Python 3.x
- PostgreSQL 15 + PostGIS 3.4
- Docker + Docker Compose
- Libraries: psycopg2, gtfs-realtime-bindings, requests, python-dotenv

### Data Quality Findings
- **Match rate:** 3.4% (3,266 out of 94,944 positions)
- **Root cause:** Different identifier schemes between GTFS-RT and GTFS Static
- **Working dataset:** 3,266 matched positions across 20+ routes, 762 vehicles
- **Strategy:** Focus analysis on matched data, reconciliation layer planned for Phase 2

### Current Analysis Capability
- Route-level headway calculations working
- Bunching patterns visible in data (6-15 second gaps observed)
- Limitation: Current query shows GPS polling intervals, not actual stop arrivals

### Known Limitations
- RT/Static match rate: 3.4% (reconciliation needed)
- Spatial queries on stop-level analysis are slow (gtfs_stop_times 1.7GB)
- Data sparsity: insufficient density at individual stops for headway analysis
- GPS polling intervals (60s) captured instead of stop arrival events

### Next Session Priorities
1. Filter headway calculations to stop arrivals only (not every GPS ping)
2. Identify stop arrival events from continuous GPS stream
3. Calculate actual vs scheduled headways at stops
4. Design bunching detection metrics
5. Build REST API (FastAPI)
6. Create simple dashboard

### Configuration
- **API:** BODS GTFS-RT endpoint
- **Region:** Liverpool (53.418-53.441, -2.976--2.876)
- **Poll interval:** 60 seconds
- **Data retention:** Manual cleanup (30 days planned)

### Key Decisions Made
- Self-hosted tool + public demo (two-tier approach)
- Focus on service quality vs driver behavior
- Liverpool first, then multi-region
- Depth before breadth strategy
- Analyze matched data only (defer reconciliation to Phase 2)
- Optimize for portfolio showcase over production perfection