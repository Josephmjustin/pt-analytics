# PT Analytics - Project Status

## Current State (as of 2025-11-22)

### Completed Features
- BODS GTFS-RT API integration
- PostgreSQL + PostGIS database (Docker)
- Live data ingestion pipeline
- Continuous polling (60s intervals)
- Duplicate prevention
- Batch inserts optimized
- GTFS Static data loaded (stops, routes, trips, stop_times)
- PostGIS spatial indexing on stops
- 8M+ scheduled stop times for North West England
- 247 stops, 16,477 trips in Liverpool scope

### Database
- **Table:** vehicle_positions
- **Records:** 94,944 rows
- **Time range:** 2025-11-21 22:40 to 2025-11-22 23:08
- **Region:** Liverpool bounding box

### Tech Stack
- Python 3.x
- PostgreSQL 15 + PostGIS 3.4
- Docker + Docker Compose
- Libraries: psycopg2, gtfs-realtime-bindings, requests, python-dotenv

### Project Structure
```
pt-analytics/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env (not in git)
├── .gitignore
├── docs/
│   ├── schema.md
│   └── PROJECT_STATUS.md
├── scripts/
│   ├── ingest_gtfs_to_db.py
│   ├── continuous_poller.py
│   └── test_db_connection.py
├── src/
│   ├── __init__.py
│   ├── analytics/
│   ├── api/
│   ├── ingestion/
│   ├── models/
│   └── utils/
└── tests/
```

### Next Session Priorities
1. Design bunching detection algorithm
2. Calculate service quality metrics
3. Build REST API (FastAPI)
4. Create simple dashboard
5. Match vehicle positions to routes
6. Spatial matching of vehicles to stops
7. Calculate actual vs scheduled headways

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

