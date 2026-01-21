# PT Analytics - Real-Time Demand Analysis for Public Transport

Passenger demand analytics platform for Liverpool bus network using dwell time patterns. Processes real-time GPS data from 400+ buses to identify high-demand stops, peak hours, and route capacity requirements.

**Live API:** [api.heyico.work](https://api.heyico.work/docs)

---

## Overview

PT Analytics transforms raw vehicle position data into actionable transit demand insights. The system processes GPS feeds from the UK Bus Open Data Service and calculates dwell time patterns—the duration buses spend at stops—as a validated proxy for passenger activity.

**Current Coverage:**
- 137 routes across Liverpool City Region
- 1,000+ stops with demand data
- 11 transit operators monitored
- Real-time updates every 10 minutes

**Key Applications:**
- Infrastructure investment prioritization
- Schedule frequency optimization
- Route capacity planning
- Peak hour demand analysis

---

## Architecture
```
┌─────────────────────────────────────────────────────────────┐
│  UK Bus Open Data Service (BODS) - Government API           │
│  Real-time GPS positions for 400+ buses                     │
└───────────────────────┬─────────────────────────────────────┘
                        │ Poll every 10 seconds
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  VM#1 - Data Processing Pipeline (1GB RAM)                  │
│  ┌───────────────────────────────────────────────────┐      │
│  │ Cron-Scheduled Jobs:                              │      │
│  │  • Ingestion:    Every 10s  → Collect positions   │      │
│  │  • Analysis:     Every 10m  → Detect stop events  │      │
│  │  • Aggregation:  Every 10m  → Calculate averages  │      │
│  │  • Cleanup:      Every 10m  → Maintain 10m window │      │
│  └───────────────────────────────────────────────────┘      │
│  ┌───────────────────────────────────────────────────┐      │
│  │ FastAPI + nginx (api.heyico.work)                 │      │
│  │  • Dwell time analytics endpoints                 │      │
│  │  • HTTPS via Let's Encrypt                        │      │
│  └───────────────────────────────────────────────────┘      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  VM#2 - PostgreSQL 14 + PostGIS (1GB RAM)                   │
│                                                             │
│  Raw Data (10-min retention):                               │
│   • vehicle_positions    ~5MB (rolling window)              │
│   • vehicle_arrivals     temporary (deleted after agg)      │
│                                                             │
│  Static Data:                                               │
│   • txc_stops            6,395 stops with coordinates       │
│   • txc_route_patterns   556 route variants                 │
│   • txc_pattern_stops    21,130 route-stop mappings         │
│                                                             │
│  Analytics (permanent, fixed-size):                         │
│   • dwell_time_analysis  Running averages by:               │
│     stop × route × direction × operator × day × hour        │
│                                                             │
│  Total Size: <50MB (stable)                                 │
└─────────────────────────────────────────────────────────────┘
```

**Infrastructure:** Oracle Cloud Always Free tier (2× VMs), self-hosted PostgreSQL, nginx reverse proxy with Let's Encrypt SSL

---

## Technical Implementation

### Data Pipeline

**1. Ingestion (Every 10 seconds)**
- Poll UK government BODS API for Liverpool region
- Parse SIRI-VM XML vehicle positions
- Batch insert to `vehicle_positions` table
- Mark all as `analyzed = false`

**Throughput:** ~450 positions per minute

---

**2. Analysis (Every 10 minutes)**

Stop detection algorithm:
```python
# Identify stop events from GPS patterns
for vehicle in unanalyzed_positions:
    if stationary_for(vehicle, duration=20s):
        stop_event = {
            'dwell_time': count_stationary_seconds(vehicle),
            'location': vehicle.lat_lon,
            'route': vehicle.route_name
        }
```

Spatial matching optimization:
```python
class StopMatcher:
    def __init__(self):
        # Load 6,395 stops once into memory
        # Index: {route → direction → [stops with coords]}
        self.route_stops = build_stop_index()
    
    def match(self, stop_event):
        # In-memory haversine distance calculation
        # 100x faster than database queries per event
        candidates = self.route_stops[event.route][event.direction]
        return find_nearest(candidates, event.lat, event.lon, radius=30m)
```

**Performance:** Processes 100+ stop events in <5 seconds

---

**3. Aggregation (Every 10 minutes)**

Running average calculation:
```sql
INSERT INTO dwell_time_analysis 
  (stop_id, route, direction, operator, day_of_week, hour_of_day, 
   avg_dwell, stddev_dwell, sample_count)
SELECT ...
FROM vehicle_arrivals
GROUP BY stop_id, route, direction, operator, day_of_week, hour_of_day
ON CONFLICT (stop_id, route, direction, operator, day_of_week, hour_of_day)
DO UPDATE SET
  avg_dwell = (old.avg × old.count + new.sum) / (old.count + new.count),
  sample_count = old.count + new.count,
  stddev_dwell = calculate_stddev(new_values);
```

**Result:** Fixed-size table (~500K rows max) regardless of data volume

---

**4. Cleanup (Every 10 minutes)**
- Delete `vehicle_positions` older than 10 minutes
- Delete `vehicle_arrivals` after aggregation
- Run PostgreSQL VACUUM to reclaim space

**Outcome:** Database remains <50MB indefinitely

---

### Database Schema

**Operational Tables (10-min retention):**
```sql
CREATE TABLE vehicle_positions (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT,
    route_name TEXT,
    direction TEXT,
    operator TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    timestamp TIMESTAMP,
    analyzed BOOLEAN DEFAULT false
);
```

**Analytics Table (permanent, fixed-size):**
```sql
CREATE TABLE dwell_time_analysis (
    naptan_id VARCHAR(20),
    route_name VARCHAR(20),
    direction VARCHAR(20),
    operator VARCHAR(50),
    day_of_week INTEGER,      -- 0=Monday, 6=Sunday
    hour_of_day INTEGER,      -- 0-23
    avg_dwell_seconds REAL,
    stddev_dwell_seconds REAL,
    sample_count INTEGER,
    last_updated TIMESTAMP,
    PRIMARY KEY (naptan_id, route_name, direction, operator, day_of_week, hour_of_day)
);

CREATE INDEX idx_high_demand ON dwell_time_analysis(avg_dwell_seconds DESC);
```

**Storage Strategy:**
- Raw data: Aggressive cleanup (10-min window)
- Aggregates: Permanent retention (running averages)
- Static data: One-time load from TransXChange files

---

## API Endpoints

**Base URL:** `https://api.heyico.work`

### High-Demand Stops
```http
GET /dwell-time/hotspots?min_samples=10&limit=20
```

Identifies stops with highest passenger activity based on average dwell time.

**Response:**
```json
{
  "hotspots": [
    {
      "naptan_id": "2800S40020D",
      "stop_name": "Queen Square Bus Station",
      "latitude": 53.4094,
      "longitude": -2.9886,
      "routes_count": 15,
      "overall_avg_dwell": 45.2,
      "total_samples": 1247
    }
  ],
  "count": 20
}
```

**Use Case:** Infrastructure investment prioritization

---

### Route Comparison
```http
GET /dwell-time/routes
```

Ranks all routes by passenger activity levels.

**Response:**
```json
{
  "routes": [
    {
      "route_name": "14",
      "operators": "Arriva, Stagecoach",
      "stops_with_data": 32,
      "avg_dwell": 28.9,
      "total_samples": 4601
    }
  ],
  "count": 137
}
```

**Use Case:** Route capacity planning, frequency optimization

---

### Temporal Demand Patterns
```http
GET /dwell-time/heatmap?route_name=14&direction=inbound&operator=Arriva
```

Returns stop-by-hour demand matrix for visualization.

**Response:**
```json
{
  "route_name": "14",
  "stops": ["Stop A", "Stop B", "Stop C"],
  "hours": [0, 1, 2, ..., 23],
  "data": [
    [19.1, 22.5, 25.3, 42.1, ...],  // Stop A by hour
    [15.6, 17.6, 18.7, 38.9, ...],  // Stop B by hour
    [15.1, 25.4, 31.2, 55.4, ...]   // Stop C by hour
  ]
}
```

**Use Case:** Peak hour identification, schedule adjustment

---

### Additional Endpoints
```http
GET /dwell-time/stats                    # Network-wide statistics
GET /dwell-time/stop/{id}/pattern       # Temporal patterns for specific stop
GET /dwell-time/route/{route}/stops     # All stops on route with filters
GET /dwell-time/filters                 # Available operators and directions
```

**Documentation:** [api.heyico.work/docs](https://api.heyico.work/docs) (OpenAPI/Swagger)

---

## Key Engineering Decisions

### Fixed-Size Analytics Table

**Challenge:** Unbounded data growth on free-tier storage constraints (500MB limit initially)

**Solution:** Running average aggregation with conflict resolution eliminates need for raw historical data

**Implementation:** SQL `ON CONFLICT DO UPDATE` merges new samples into existing averages

**Result:** Table size remains constant (~500K rows) regardless of months/years of operation

**Alternative Considered:** Time-series database (rejected due to complexity and resource overhead)

---

### In-Memory Spatial Matching

**Challenge:** Spatial queries matching 100+ stop events to 6,395 stops via database = 10+ minutes per cycle

**Solution:** Load stop topology into Python dictionary at startup, indexed by route and direction

**Result:** 100x performance improvement (10 minutes → 5 seconds per analysis cycle)

**Tradeoff:** 50MB memory footprint vs 10 minutes of CPU time per cycle

---

### 10-Minute Rolling Window

**Challenge:** 1GB RAM constraint on free-tier VM requires minimizing database size

**Solution:** Aggressive cleanup of raw positions after 10 minutes, keeping only aggregated results

**Result:** Database stable at <50MB with full analytical capability preserved

**Alternative Considered:** Longer retention windows (rejected due to RAM constraints during PostgreSQL operations)

---

### TransXChange Integration

**Challenge:** UK transit data uses TransXChange (native) vs GTFS (international standard)

**Solution:** Built XML parser for TransXChange files, loaded 6,395 stops and 556 route patterns

**Result:** Native data format eliminates reconciliation issues common with GTFS in UK

**Learning:** Domain research revealed UK transit industry's data standards differ from US

---

## Performance Metrics

**Pipeline Efficiency:**
- 450 positions/minute ingested
- <5 seconds analysis latency for 100+ events
- <100ms API response time (p95)
- 99%+ uptime via systemd auto-restart

**Resource Utilization:**
- 1GB RAM constraint met on both VMs
- <50MB database size maintained
- Zero external service dependencies
- $0/month operational cost

**Data Coverage:**
- 100+ routes monitored 
- 11 transit operators
- 50,000+ dwell time samples collected
- 1,000+ stops with demand data

---

## Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Database** | PostgreSQL 14 + PostGIS | Geospatial queries, ACID compliance, free |
| **Backend** | Python 3.12 + FastAPI | Async I/O, type hints, auto-generated docs |
| **Orchestration** | Cron + systemd | Zero dependencies, reliable, lightweight |
| **Infrastructure** | Oracle Cloud (Always Free) | 2× VMs with 1GB RAM each, ARM architecture |
| **SSL/TLS** | Let's Encrypt + nginx | Free certificates with auto-renewal |
| **Data Source** | UK Bus Open Data Service | Government API, real-time GPS, free access |

**Key Libraries:**
- `psycopg2` - PostgreSQL driver
- `lxml` - TransXChange XML parsing
- `shapely` - Geospatial calculations
- `numpy` - Statistical operations

---

## Challenges & Solutions

### Challenge 1: Storage Growth
**Initial Approach:** Store all raw vehicle positions for historical analysis

**Problem:** 1.8GB accumulated in 2 weeks, exceeding Supabase free tier (500MB)

**Solution:** Migrated to self-hosted PostgreSQL with 10-minute rolling window

**Outcome:** Database size stable at <50MB with full analytical capability

---

### Challenge 2: Spatial Query Performance
**Initial Approach:** Database spatial queries for each stop event match

**Problem:** 10+ minutes per analysis cycle with 100+ events

**Solution:** Load stop topology into memory once, perform matching in application layer

**Outcome:** 100x speedup, 5-second analysis cycles

---

### Challenge 3: RAM Constraints
**Challenge:** 1GB RAM insufficient for holding full dataset

**Solution:** Streaming processing, indexed queries, aggressive cleanup

**Outcome:** Demonstrated optimization for constrained environments

---

### Challenge 4: UK Data Standards
**Initial Approach:** GTFS Static + GTFS-RT (international standard)

**Problem:** 3.4% trip_id match rate in UK data, only 37 stops operational

**Solution:** Pivoted to TransXChange (UK native format), 6.5x stop coverage improvement

**Outcome:** 6,395 stops loaded, 98% theoretical match capability

---

## Dwell Time Methodology

### Academic Basis

**Research Foundation:**
- Tirachini (2013): "Dwell time positively correlates with passenger load in bus systems"
- Transit Capacity and Quality of Service Manual (TCRP): Standard metric for demand estimation
- Practitioners: Transport for London, MBTA Boston, WMATA Washington DC

**Validation Approach:**
- Compare patterns with known high-demand locations (stadiums, universities, hospitals)
- Verify peak vs off-peak hourly patterns align with commuter behavior
- Check directional asymmetry (inbound morning rush, outbound evening rush)

---

### Advantages Over Traditional Methods

**Traditional:** Manual passenger counts, expensive APC (Automatic Passenger Counter) hardware

**Dwell Time Approach:**
- No additional hardware beyond existing GPS
- Real-time updates vs quarterly surveys
- City-wide coverage vs sample-based counts
- Continuous 24/7 data collection

---

### Known Limitations

- Cannot distinguish boarding vs alighting activity
- Weather and traffic incidents affect accuracy
- Assumes constant boarding/alighting speed across all stops
- Does not capture denied boardings (bus too full)

---

## Project Evolution

**November 2025:** Initial development with GTFS Static approach  
→ Abandoned due to data quality issues in UK (3.4% match rate)

**December 2025:** Migrated to TransXChange (UK native format)  
→ 6.5x improvement in stop coverage (37 → 240 stops)

**December 2025:** Pivoted from complex Service Reliability Index to focused dwell time analysis  
→ Simplified metric with clearer business value

**December 2025 - January 2026:** Production hardening  
→ SSL deployment, systemd management, aggressive optimization for 1GB RAM constraints

**Key Learning:** Iterative refinement based on real-world operational constraints

---

## Use Cases

### 1. Infrastructure Planning
**Question:** Where should the city invest in bus shelter upgrades?

**Solution:** Query `/dwell-time/hotspots` to identify top 20 highest-demand stops

**Impact:** Data-driven capital investment decisions

---

### 2. Schedule Optimization
**Question:** Should Route 14 increase frequency during morning peak?

**Solution:** Query `/dwell-time/heatmap` to analyze hourly demand patterns

**Impact:** Right-sized service levels, reduced overcrowding

---

### 3. Operator Benchmarking
**Question:** How does Arriva's performance compare to Stagecoach on Route 14?

**Solution:** Filter `/dwell-time/routes` by operator

**Impact:** Performance-based service contracts

---

### 4. Demand-Responsive Transit
**Question:** When should on-demand services operate in low-demand areas?

**Solution:** Identify time periods with low average dwell times

**Impact:** Cost-effective hybrid fixed-route/on-demand systems

---

## Setup Requirements

**Infrastructure:**
- 2× Linux VMs with 1GB RAM each (Oracle Cloud Always Free tier)
- PostgreSQL 14 + PostGIS
- Python 3.12+
- nginx + Let's Encrypt for SSL

**Data Sources:**
- UK Bus Open Data Service API key (free registration)
- TransXChange XML timetable files for Liverpool region

**Deployment:**
- FastAPI as systemd service
- Cron-scheduled data pipeline
- nginx reverse proxy with SSL termination

*Note: Detailed deployment procedures are proprietary*

---

## Contact

**API Demo:** [api.heyico.work/docs](https://api.heyico.work/docs)  
**GitHub:** [josephmjustin/pt-analytics](https://github.com/josephmjustin/pt-analytics)  
**LinkedIn:** [[josephmjustin](https://www.linkedin.com/in/josephmjustin/)]

---

**Real-time demand analytics for public transport. Zero operational cost. Production-ready architecture.**