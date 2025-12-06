# PT Analytics

Real-time public transport analytics system for detecting bus bunching patterns in UK transit networks. Built as a portfolio project demonstrating backend engineering capabilities for mobility/geospatial roles.

## Overview

PT Analytics monitors service quality by analyzing when multiple buses on the same route cluster together ("bunching"), reducing service reliability. The system processes real-time vehicle positions from the UK Bus Open Data Service (BODS) and calculates bunching patterns across the stops in Liverpool's bus network.

**Live Demo:** [pt-analytics.onrender.com](https://pt-analytics.onrender.com)

## Key Innovation: OSM-Based Spatial Matching

Eliminated dependency on GTFS Static schedule data by implementing spatial matching with OpenStreetMap stops:

- **Problem:** GTFS Static trip_id mismatch (3.4% match rate → only 37 stops)
- **Solution:** OSM spatial proximity matching (within 100m)
- **Result:** 6.5x improvement (240 stops analyzed)

This approach works with any transit agency data without requiring schedule reconciliation.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  UK Bus Open Data Service (BODS) - GTFS-RT Feed         │
│  Liverpool Region (53.35-53.48, -3.05--2.80)            │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  PREFECT CLOUD ORCHESTRATION                            │
│  ┌────────────────────────────────────────────────┐     │
│  │ Ingestion Flow (60s)    - Polls BODS API       │     │
│  │ Analysis Flow (5min)    - Spatial matching     │     │
│  │ Aggregation Flow (10min)- Pattern learning     │     │
│  │ Cleanup Flow (15min)    - Data management      │     │
│  └────────────────────────────────────────────────┘     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  SUPABASE - PostgreSQL + PostGIS                        │
│  • vehicle_positions (3M+ records)                      │
│  • osm_stops (370 stops with spatial index)             │                      
│  • bunching_events (detected incidents)                 │
│  • Aggregation tables (5 pattern views)                 │
│  • Storage: ~80MB (optimized from 1.8GB)                │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  ORACLE CLOUD VM - FastAPI Backend                      │
│  • /health - Health check                               │
│  • /stops - All stops with bunching scores              │
│  • /stops/all-osm - stops sync with osm                 │
│  • /stops/stats - Overall statistics of stops           │
│  • /stops/headways - summary of route headway baselines │
│  • /stops/{stop_id}/routes - stops in route             │
│  • /stops/{stop_id} - Stop-level analytics              │
│  • /routes/ - Get all routes                            │
│  • /routes/{route_id} - Get route details               │
│  • /routes/{route_id}/csv - Download csv for route      │
│  • /vehicles/live/ - Current positions                  │
│  HTTPS via Cloudflare Tunnel                            │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  RENDER - React Dashboard                               │
│  • Interactive map (Leaflet + OSM tiles)                │
│  • Real-time vehicle positions                          │
│  • Color-coded bunching severity                        │
│  • Stop and route analytics views                       │
└─────────────────────────────────────────────────────────┘
```

## Technology Stack

### Backend
- **Language:** Python 3.x
- **Database:** PostgreSQL 15 + PostGIS 3.4
- **API Framework:** FastAPI + Uvicorn
- **Orchestration:** Prefect Cloud
- **Data Processing:** psycopg2, GeoPandas, Shapely

### Infrastructure
- **Database:** Supabase (managed PostgreSQL)
- **API Hosting:** Oracle Cloud VM (Always Free tier)
- **Frontend Hosting:** Render (static site)
- **Security:** Cloudflare Tunnel (HTTPS)
- **Orchestration:** Prefect Cloud (free tier)

### Frontend
- **Framework:** React (Vite)
- **Mapping:** Leaflet + OpenStreetMap
- **UI:** TailwindCSS (planned upgrade to shadcn/ui)

## Data Pipeline

### 1. Ingestion (60-second intervals)
- Polls BODS GTFS-RT API for Liverpool region
- Extracts vehicle positions with spatial geometry
- Batch inserts with duplicate prevention
- ~3M+ vehicle positions collected

### 2. Spatial Analysis (5-minute intervals)
- Matches vehicle positions to OSM stops (100m radius)
- Creates stop arrival events
- Calculates headways between consecutive buses
- Detects bunching using route-aware thresholds

### 3. Aggregation (10-minute intervals)
- Updates running averages across time dimensions
- Calculates route-specific median headways
- Builds pattern tables (hourly/daily/stop-level)
- Optimizes storage (180MB from 1.7GB raw data)

### 4. Cleanup (15-minute intervals)
- Removes vehicle positions older than 10 minutes
- Maintains 30-day historical aggregations
- Preserves pattern data indefinitely

## Bunching Detection Algorithm

Route-aware detection using dynamic thresholds based on learned patterns:

1. **Calculate route baseline** from `route_headway_baselines` table (median headway per route/stop)
2. **Bunching threshold:** `max(route_baseline * 0.5, 2.0)` minutes
3. **Fallback:** If no baseline exists, use 2.0 minutes fixed threshold
4. **Bunching event:** Two consecutive buses arrive closer than threshold

**The 2-minute floor prevents false positives on very high-frequency routes.**

Example thresholds:
- Route baseline: 10 min → threshold = max(5, 2) = **5 min**
- Route baseline: 4 min → threshold = max(2, 2) = **2 min**
- Route baseline: 3 min → threshold = max(1.5, 2) = **2 min** (floor applied)
- No baseline data → threshold = **2 min** (fallback)

This approach differentiates between legitimate high-frequency service and actual bunching while learning route-specific patterns over time.

## Key Features

### Spatial Matching
- OpenStreetMap stop locations (500+ stops)
- PostGIS spatial indexing for performance
- 100m proximity matching radius
- 98% stop coverage 

### Pattern Analysis
- Hourly bunching patterns
- Daily service quality trends
- Monthly quality trends
- Stop-level performance metrics
- Route-level aggregations

### Performance Optimizations
- Batch inserts with `psycopg2.extras.execute_values`
- Spatial indexes on geometry columns
- Running average aggregations (preserves patterns, discards raw data)
- Efficient route-level analysis (avoids expensive spatial joins)

## Database Schema

### bunching_by_day
```sql
bunching_by_day (
    stop_id                        TEXT                 NOT NULL
    day_of_week                    INTEGER              NOT NULL
    avg_bunching_rate              NUMERIC              NULL
    total_count                    INTEGER              NULL
    last_updated                   TIMESTAMP WITHOUT TIME ZONE NULL
)
```

### bunching_by_hour
```sql
bunching_by_hour (
    stop_id                        TEXT                 NOT NULL
    hour_of_day                    INTEGER              NOT NULL
    avg_bunching_rate              NUMERIC              NULL
    total_count                    INTEGER              NULL
    last_updated                   TIMESTAMP WITHOUT TIME ZONE NULL
)
```

### bunching_by_hour_day
```sql
bunching_by_hour_day (
    stop_id                        TEXT                 NOT NULL
    hour_of_day                    INTEGER              NOT NULL
    day_of_week                    INTEGER              NOT NULL
    avg_bunching_rate              NUMERIC              NULL
    total_count                    INTEGER              NULL
    last_updated                   TIMESTAMP WITHOUT TIME ZONE NULL
)
```

### bunching_by_month
```sql
bunching_by_month (
    stop_id                        TEXT                 NOT NULL
    month                          INTEGER              NOT NULL
    avg_bunching_rate              NUMERIC              NULL
    total_count                    INTEGER              NULL
    last_updated                   TIMESTAMP WITHOUT TIME ZONE NULL
)
```

### bunching_by_stop
```sql
bunching_by_stop (
    stop_id                        TEXT                 NOT NULL
    stop_name                      TEXT                 NULL
    avg_bunching_rate              NUMERIC              NULL
    total_count                    INTEGER              NULL
    last_updated                   TIMESTAMP WITHOUT TIME ZONE NULL
)
```

### bunching_scores
```sql
bunching_scores (
    id                             INTEGER              NOT NULL
    stop_id                        TEXT                 NOT NULL
    stop_name                      TEXT                 NOT NULL
    analysis_timestamp             TIMESTAMP WITHOUT TIME ZONE NOT NULL
    total_arrivals                 INTEGER              NOT NULL
    bunched_count                  INTEGER              NOT NULL
    bunching_rate_pct              NUMERIC              NOT NULL
    avg_headway_minutes            NUMERIC              NULL
    min_headway_minutes            NUMERIC              NULL
    max_headway_minutes            NUMERIC              NULL
    data_window_start              TIMESTAMP WITHOUT TIME ZONE NOT NULL
    data_window_end                TIMESTAMP WITHOUT TIME ZONE NOT NULL
)
```

### gtfs_routes
```sql
gtfs_routes (
    route_id                       TEXT                 NOT NULL
    agency_id                      TEXT                 NULL
    route_short_name               TEXT                 NULL
    route_long_name                TEXT                 NULL
    route_type                     INTEGER              NULL
)
```

### gtfs_stops
```sql
gtfs_stops (
    stop_id                        TEXT                 NOT NULL
    stop_code                      TEXT                 NULL
    stop_name                      TEXT                 NOT NULL
    stop_lat                       DOUBLE PRECISION     NOT NULL
    stop_lon                       DOUBLE PRECISION     NOT NULL
    location                       GEOMETRY             NULL
    wheelchair_boarding            INTEGER              NULL
    location_type                  INTEGER              NULL
    parent_station                 TEXT                 NULL
    platform_code                  TEXT                 NULL
)
```

### gtfs_trips
```sql
gtfs_trips (
    trip_id                        TEXT                 NOT NULL
    route_id                       TEXT                 NULL
    service_id                     TEXT                 NULL
    trip_headsign                  TEXT                 NULL
    direction_id                   INTEGER              NULL
    block_id                       TEXT                 NULL
    shape_id                       TEXT                 NULL
    wheelchair_accessible          INTEGER              NULL
    vehicle_journey_code           TEXT                 NULL
)
```

### osm_stops
```sql
osm_stops (
    osm_id                         BIGINT               NOT NULL
    name                           TEXT                 NULL
    latitude                       DOUBLE PRECISION     NOT NULL
    longitude                      DOUBLE PRECISION     NOT NULL
    location                       GEOGRAPHY            NULL
    tags                           JSONB                NULL
    created_at                     TIMESTAMP WITHOUT TIME ZONE NULL
)
```

### route_headway_baselines
```sql
route_headway_baselines (
    route_id                       TEXT                 NOT NULL
    stop_id                        TEXT                 NOT NULL
    stop_name                      TEXT                 NULL
    median_headway_minutes         NUMERIC              NULL
    avg_headway_minutes            NUMERIC              NULL
    observation_count              INTEGER              NULL
    last_updated                   TIMESTAMP WITHOUT TIME ZONE NULL
)
```

### vehicle_positions
```sql
vehicle_positions (
    id                             INTEGER              NOT NULL
    vehicle_id                     TEXT                 NOT NULL
    latitude                       DOUBLE PRECISION     NOT NULL
    longitude                      DOUBLE PRECISION     NOT NULL
    timestamp                      TIMESTAMP WITHOUT TIME ZONE NOT NULL
    route_id                       TEXT                 NULL
    trip_id                        TEXT                 NULL
    bearing                        INTEGER              NULL
    geom                           GEOMETRY             NULL
)
```

### Aggregation Tables
- `bunching_by_hour` - Hourly bunching rates per stop
- `bunching_by_day` - Daily service quality metrics
- `bunching_by_hour_day` - Combined hourly/daily patterns
- `bunching_by_month` - Monthly service trends
- `bunching_by_stop` - Long-term stop performance
- `route_headway_baselines` - Dynamic headway thresholds per route


## Setup & Deployment

### Prerequisites
- Python 3.8+
- PostgreSQL 15+ with PostGIS
- BODS API key (free from data.bus-data.dft.gov.uk)
- Prefect Cloud account (free tier)

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
# Edit .env with your credentials
```

5. **Initialize database:**
```bash
python scripts/setup_database.py
python scripts/load_osm_stops.py
```

6. **Run Prefect flows:**
```bash
cd flows
python deploy_pipeline.py
```

### Cloud Deployment

**Database (Supabase):**
1. Create Supabase project
2. Enable PostGIS extension
3. Run migration scripts
4. Update connection strings in `.env`

**API (Oracle Cloud VM):**
1. Provision Always Free VM (AMD or ARM)
2. Install Docker or Python runtime
3. Deploy API with uvicorn
4. Setup Cloudflare Tunnel for HTTPS

**Orchestration (Prefect Cloud):**
1. Create Prefect Cloud workspace
2. Deploy flows: `python flows/deploy_pipeline.py`
3. Flows auto-schedule on defined intervals

## Performance Metrics

- **Data Volume:** 3M+ vehicle positions analyzed
- **Coverage:** 500+ stops across Liverpool
- **Latency:** Real-time updates within 60 seconds
- **Storage:** 180MB (vs 1.8GB raw data)
- **Uptime:** Continuous operation since deployment
- **API Response:** <100ms average

## Project Evolution

### Phase 1: GTFS Static Approach (Failed)
- Loaded 179,875 scheduled trips
- 3.4% match rate with real-time data
- Only 37 stops operational
- **Decision:** Pivot to spatial matching

### Phase 2: OSM Integration (Success)
- Downloaded 251 OSM stops
- Implemented spatial proximity matching
- Achieved 240 stops (6.5x improvement)
- Eliminated GTFS Static dependency

### Phase 3: Storage Optimization
- Initial: 1.7GB raw data
- Implemented running average aggregation
- Final: 18MB with full analytical capability
- Enabled cloud deployment viability

### Phase 4: Production Deployment
- Multi-cloud architecture
- HTTPS security via Cloudflare
- Continuous orchestration via Prefect
- Professional React dashboard

### Phase 5: Update bounding box for more coverage
- Updated the bounding box in ingestion pipeline
- Re-imported to the Oracle VM via git

## Lessons Learned

1. **Data reconciliation is hard:** GTFS Static/RT identifier mismatch is common in transit data
2. **Spatial approaches are robust:** Geographic proximity more reliable than schedule matching
3. **Storage matters in cloud:** Aggregation strategies crucial for free-tier viability
4. **Portfolio focus:** Balance complexity with deliverable outcomes
5. **Domain knowledge:** Transport modeling background informed design decisions

## Future Enhancements

- [ ] Multi-region support (extend beyond Liverpool)
- [ ] Machine learning for bunching prediction
- [ ] Real-time alerts via webhook/email
- [ ] Mobile application (React Native)
- [ ] Advanced visualizations (heatmaps, time series)
- [ ] Integration with operator APIs for feedback loop

## Known Limitations

- **Schedule comparison:** No GTFS Static integration (by design)
- **Historical data:** Only data agregation for average 
- **UK-specific:** BODS API only covers UK transit
- **Cloudflare Tunnel:** URL changes on restart (temporary solution)

## Contributing

This is a portfolio project not currently accepting contributions. However, feel free to fork and adapt for your own use cases.

## License

Apache License 2.0 - See LICENSE file for details

## Contact

**Justin Joseph** - Liverpool, England, UK
- Portfolio project for mobility/geospatial expertise
- Background: Transport modeling, backend engineering

## Acknowledgments

- UK Bus Open Data Service (BODS) for real-time transit data
- OpenStreetMap contributors for stop location data
- Prefect for workflow orchestration
- Supabase for managed PostgreSQL + PostGIS
