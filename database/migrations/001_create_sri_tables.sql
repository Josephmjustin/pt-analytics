-- Migration: Create SRI (Service Reliability Index) Tables
-- Version: 1.0
-- Date: 2024-12-22

BEGIN;

-- ============================================================================
-- PATTERN AGGREGATION TABLES
-- ============================================================================

-- Headway patterns aggregation
CREATE TABLE IF NOT EXISTS headway_patterns (
    id BIGSERIAL PRIMARY KEY,
    route_name VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    stop_id VARCHAR(50) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day_of_week INT,  -- 0=Monday, 6=Sunday, NULL for monthly aggregate
    hour INT,         -- 0-23, NULL for daily/monthly aggregate
    
    -- Aggregated metrics
    median_headway_minutes DECIMAL(6,2),
    avg_headway_minutes DECIMAL(6,2),
    std_headway_minutes DECIMAL(6,2),
    min_headway_minutes DECIMAL(6,2),
    max_headway_minutes DECIMAL(6,2),
    coefficient_of_variation DECIMAL(6,4),
    bunching_rate DECIMAL(5,2),  -- % of headways < 50% of median
    observation_count INT DEFAULT 0,
    
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_headway_pattern UNIQUE(route_name, direction, operator, stop_id, year, month, day_of_week, hour)
);

CREATE INDEX idx_headway_patterns_route ON headway_patterns(route_name, direction, year, month);
CREATE INDEX idx_headway_patterns_time ON headway_patterns(year, month, day_of_week, hour);
CREATE INDEX idx_headway_patterns_stop ON headway_patterns(stop_id, year, month);

-- Schedule adherence patterns
CREATE TABLE IF NOT EXISTS schedule_adherence_patterns (
    id BIGSERIAL PRIMARY KEY,
    route_name VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    stop_id VARCHAR(50) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day_of_week INT,
    hour INT,
    
    -- Aggregated metrics
    avg_deviation_minutes DECIMAL(6,2),     -- positive=late, negative=early
    std_deviation_minutes DECIMAL(6,2),
    median_deviation_minutes DECIMAL(6,2),
    on_time_count INT DEFAULT 0,            -- within ±2 min
    early_count INT DEFAULT 0,              -- > 2 min early
    late_count INT DEFAULT 0,               -- > 2 min late
    on_time_percentage DECIMAL(5,2),
    observation_count INT DEFAULT 0,
    
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_schedule_pattern UNIQUE(route_name, direction, operator, stop_id, year, month, day_of_week, hour)
);

CREATE INDEX idx_schedule_patterns_route ON schedule_adherence_patterns(route_name, direction, year, month);
CREATE INDEX idx_schedule_patterns_time ON schedule_adherence_patterns(year, month, day_of_week, hour);
CREATE INDEX idx_schedule_patterns_stop ON schedule_adherence_patterns(stop_id, year, month);

-- Journey time patterns (stop-to-stop)
CREATE TABLE IF NOT EXISTS journey_time_patterns (
    id BIGSERIAL PRIMARY KEY,
    route_name VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    origin_stop_id VARCHAR(50) NOT NULL,
    destination_stop_id VARCHAR(50) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day_of_week INT,
    hour INT,
    
    -- Aggregated metrics
    avg_journey_minutes DECIMAL(6,2),
    std_journey_minutes DECIMAL(6,2),
    median_journey_minutes DECIMAL(6,2),
    coefficient_of_variation DECIMAL(6,4),
    percentile_85_minutes DECIMAL(6,2),
    observation_count INT DEFAULT 0,
    
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_journey_pattern UNIQUE(route_name, direction, operator, origin_stop_id, destination_stop_id, 
                                             year, month, day_of_week, hour)
);

CREATE INDEX idx_journey_patterns_route ON journey_time_patterns(route_name, direction, year, month);
CREATE INDEX idx_journey_patterns_time ON journey_time_patterns(year, month, day_of_week, hour);
CREATE INDEX idx_journey_patterns_stops ON journey_time_patterns(origin_stop_id, destination_stop_id);

-- Dwell time patterns
CREATE TABLE IF NOT EXISTS dwell_time_patterns (
    id BIGSERIAL PRIMARY KEY,
    route_name VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    stop_id VARCHAR(50) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day_of_week INT,
    hour INT,
    
    -- Aggregated metrics
    avg_dwell_seconds DECIMAL(6,2),
    std_dwell_seconds DECIMAL(6,2),
    median_dwell_seconds DECIMAL(6,2),
    coefficient_of_variation DECIMAL(6,4),
    observation_count INT DEFAULT 0,
    
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_dwell_pattern UNIQUE(route_name, direction, operator, stop_id, year, month, day_of_week, hour)
);

CREATE INDEX idx_dwell_patterns_route ON dwell_time_patterns(route_name, direction, year, month);
CREATE INDEX idx_dwell_patterns_time ON dwell_time_patterns(year, month, day_of_week, hour);
CREATE INDEX idx_dwell_patterns_stop ON dwell_time_patterns(stop_id, year, month);

-- Service delivery tracking
CREATE TABLE IF NOT EXISTS service_delivery_patterns (
    id BIGSERIAL PRIMARY KEY,
    route_name VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day_of_week INT,
    hour INT,
    
    -- Service delivery metrics
    scheduled_trips INT DEFAULT 0,
    completed_trips INT DEFAULT 0,
    cancelled_trips INT DEFAULT 0,
    partial_trips INT DEFAULT 0,              -- started but not completed
    service_delivery_rate DECIMAL(5,2),  -- completed/scheduled * 100
    
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_service_delivery UNIQUE(route_name, direction, operator, year, month, day_of_week, hour)
);

CREATE INDEX idx_service_delivery_route ON service_delivery_patterns(route_name, direction, year, month);
CREATE INDEX idx_service_delivery_time ON service_delivery_patterns(year, month, day_of_week, hour);

-- ============================================================================
-- COMPONENT SCORE TABLES
-- ============================================================================

-- Headway consistency component scores
CREATE TABLE IF NOT EXISTS headway_consistency_scores (
    id BIGSERIAL PRIMARY KEY,
    route_name VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day_of_week INT,
    hour INT,
    
    -- Raw component metrics
    coefficient_of_variation DECIMAL(6,4),
    bunching_rate DECIMAL(5,2),
    avg_headway_deviation DECIMAL(6,2),
    
    -- Normalized score (0-100)
    score DECIMAL(5,2),
    grade VARCHAR(1),  -- A, B, C, D, F
    
    -- Metadata
    observation_count INT DEFAULT 0,
    data_quality_flag VARCHAR(20) DEFAULT 'sufficient',
    calculation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_hc_score UNIQUE(route_name, direction, operator, year, month, day_of_week, hour)
);

CREATE INDEX idx_hc_scores_route ON headway_consistency_scores(route_name, direction, year, month);
CREATE INDEX idx_hc_scores_time ON headway_consistency_scores(year, month, score DESC);

-- Schedule adherence component scores
CREATE TABLE IF NOT EXISTS schedule_adherence_scores (
    id BIGSERIAL PRIMARY KEY,
    route_name VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day_of_week INT,
    hour INT,
    
    -- Raw component metrics
    on_time_percentage DECIMAL(5,2),
    avg_deviation_minutes DECIMAL(6,2),
    std_deviation_minutes DECIMAL(6,2),
    
    -- Normalized score (0-100)
    score DECIMAL(5,2),
    grade VARCHAR(1),
    
    -- Metadata
    observation_count INT DEFAULT 0,
    data_quality_flag VARCHAR(20) DEFAULT 'sufficient',
    calculation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_sa_score UNIQUE(route_name, direction, operator, year, month, day_of_week, hour)
);

CREATE INDEX idx_sa_scores_route ON schedule_adherence_scores(route_name, direction, year, month);
CREATE INDEX idx_sa_scores_time ON schedule_adherence_scores(year, month, score DESC);

-- Journey time consistency component scores
CREATE TABLE IF NOT EXISTS journey_time_consistency_scores (
    id BIGSERIAL PRIMARY KEY,
    route_name VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day_of_week INT,
    hour INT,
    
    -- Raw component metrics
    coefficient_of_variation DECIMAL(6,4),
    percentile_85_ratio DECIMAL(6,4),  -- P85 / median
    avg_journey_minutes DECIMAL(6,2),
    
    -- Normalized score (0-100)
    score DECIMAL(5,2),
    grade VARCHAR(1),
    
    -- Metadata
    observation_count INT DEFAULT 0,
    data_quality_flag VARCHAR(20) DEFAULT 'sufficient',
    calculation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_jt_score UNIQUE(route_name, direction, operator, year, month, day_of_week, hour)
);

CREATE INDEX idx_jt_scores_route ON journey_time_consistency_scores(route_name, direction, year, month);
CREATE INDEX idx_jt_scores_time ON journey_time_consistency_scores(year, month, score DESC);

-- Service delivery component scores
CREATE TABLE IF NOT EXISTS service_delivery_scores (
    id BIGSERIAL PRIMARY KEY,
    route_name VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day_of_week INT,
    hour INT,
    
    -- Raw component metrics
    service_delivery_rate DECIMAL(5,2),
    cancelled_trip_rate DECIMAL(5,2),
    completed_trips INT DEFAULT 0,
    scheduled_trips INT DEFAULT 0,
    
    -- Normalized score (0-100)
    score DECIMAL(5,2),
    grade VARCHAR(1),
    
    -- Metadata
    observation_count INT DEFAULT 0,
    data_quality_flag VARCHAR(20) DEFAULT 'sufficient',
    calculation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_sd_score UNIQUE(route_name, direction, operator, year, month, day_of_week, hour)
);

CREATE INDEX idx_sd_scores_route ON service_delivery_scores(route_name, direction, year, month);
CREATE INDEX idx_sd_scores_time ON service_delivery_scores(year, month, score DESC);

-- ============================================================================
-- MASTER SRI SCORE TABLES
-- ============================================================================

-- Service Reliability Index (SRI) - Master scores
CREATE TABLE IF NOT EXISTS service_reliability_index (
    id BIGSERIAL PRIMARY KEY,
    route_name VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day_of_week INT,
    hour INT,
    
    -- Component scores (0-100 each)
    headway_consistency_score DECIMAL(5,2),
    schedule_adherence_score DECIMAL(5,2),
    journey_time_consistency_score DECIMAL(5,2),
    service_delivery_score DECIMAL(5,2),
    
    -- Component weights (sum to 1.0)
    headway_weight DECIMAL(3,2) DEFAULT 0.40,
    schedule_weight DECIMAL(3,2) DEFAULT 0.30,
    journey_time_weight DECIMAL(3,2) DEFAULT 0.20,
    service_delivery_weight DECIMAL(3,2) DEFAULT 0.10,
    
    -- Final SRI score (0-100)
    sri_score DECIMAL(5,2),
    sri_grade VARCHAR(1),  -- A, B, C, D, F
    
    -- Comparative metrics
    percentile_rank INT,
    network_avg_sri DECIMAL(5,2),
    month_over_month_change DECIMAL(5,2),
    
    -- Data quality
    observation_count INT DEFAULT 0,
    data_completeness DECIMAL(5,2),
    calculation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_sri UNIQUE(route_name, direction, operator, year, month, day_of_week, hour)
);

CREATE INDEX idx_sri_route ON service_reliability_index(route_name, direction, year, month);
CREATE INDEX idx_sri_score ON service_reliability_index(sri_score DESC, year, month);
CREATE INDEX idx_sri_operator ON service_reliability_index(operator, year, month);
CREATE INDEX idx_sri_time ON service_reliability_index(year, month, day_of_week, hour);

-- Network-level SRI aggregates
CREATE TABLE IF NOT EXISTS network_reliability_index (
    id BIGSERIAL PRIMARY KEY,
    network_name VARCHAR(100) DEFAULT 'Merseyside',
    year INT NOT NULL,
    month INT NOT NULL,
    day_of_week INT,
    hour INT,
    
    -- Network-wide scores
    network_sri_score DECIMAL(5,2),
    network_grade VARCHAR(1),
    
    -- Statistics
    total_routes INT DEFAULT 0,
    routes_grade_a INT DEFAULT 0,
    routes_grade_b INT DEFAULT 0,
    routes_grade_c INT DEFAULT 0,
    routes_grade_d INT DEFAULT 0,
    routes_grade_f INT DEFAULT 0,
    
    -- Component averages
    avg_headway_score DECIMAL(5,2),
    avg_schedule_score DECIMAL(5,2),
    avg_journey_time_score DECIMAL(5,2),
    avg_service_delivery_score DECIMAL(5,2),
    
    -- Trends
    month_over_month_change DECIMAL(5,2),
    best_performing_route VARCHAR(50),
    worst_performing_route VARCHAR(50),
    
    calculation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_network_sri UNIQUE(network_name, year, month, day_of_week, hour)
);

CREATE INDEX idx_network_sri_time ON network_reliability_index(year, month);

-- ============================================================================
-- HOTSPOT & ANALYSIS TABLES
-- ============================================================================

-- Problem hotspots identification
CREATE TABLE IF NOT EXISTS performance_hotspots (
    id BIGSERIAL PRIMARY KEY,
    hotspot_type VARCHAR(50) NOT NULL,  -- 'stop', 'route_segment', 'time_period'
    severity VARCHAR(20) NOT NULL,      -- 'critical', 'high', 'medium', 'low'
    
    -- Location
    route_name VARCHAR(50),
    direction VARCHAR(50),
    operator VARCHAR(100),
    stop_id VARCHAR(50),
    stop_name VARCHAR(200),
    
    -- Time context
    year INT NOT NULL,
    month INT NOT NULL,
    day_of_week INT,
    hour INT,
    
    -- Problem description
    primary_issue VARCHAR(100) NOT NULL,
    issue_score DECIMAL(5,2),
    affected_metric VARCHAR(50),
    
    -- Impact
    affected_passengers_estimate INT,
    sri_impact DECIMAL(5,2),
    
    -- Trend
    trend VARCHAR(20) DEFAULT 'stable',
    first_detected TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_hotspot UNIQUE(hotspot_type, route_name, direction, stop_id, 
                                    year, month, day_of_week, hour, primary_issue)
);

CREATE INDEX idx_hotspots_severity ON performance_hotspots(severity, issue_score DESC);
CREATE INDEX idx_hotspots_route ON performance_hotspots(route_name, direction, year, month);
CREATE INDEX idx_hotspots_time ON performance_hotspots(year, month, day_of_week, hour);

-- ============================================================================
-- CONFIGURATION TABLES
-- ============================================================================

-- SRI calculation configuration
CREATE TABLE IF NOT EXISTS sri_config (
    id SERIAL PRIMARY KEY,
    config_version VARCHAR(20) NOT NULL,
    effective_date DATE NOT NULL,
    
    -- Component weights
    headway_weight DECIMAL(3,2) DEFAULT 0.40,
    schedule_weight DECIMAL(3,2) DEFAULT 0.30,
    journey_time_weight DECIMAL(3,2) DEFAULT 0.20,
    service_delivery_weight DECIMAL(3,2) DEFAULT 0.10,
    
    -- Scoring thresholds - Headway
    headway_cv_excellent DECIMAL(4,2) DEFAULT 0.20,
    headway_cv_poor DECIMAL(4,2) DEFAULT 0.60,
    
    -- Scoring thresholds - Schedule
    schedule_on_time_excellent DECIMAL(5,2) DEFAULT 95.0,
    schedule_on_time_poor DECIMAL(5,2) DEFAULT 60.0,
    
    -- Scoring thresholds - Journey Time
    journey_cv_excellent DECIMAL(4,2) DEFAULT 0.15,
    journey_cv_poor DECIMAL(4,2) DEFAULT 0.50,
    
    -- Scoring thresholds - Service Delivery
    service_delivery_excellent DECIMAL(5,2) DEFAULT 98.0,
    service_delivery_poor DECIMAL(5,2) DEFAULT 80.0,
    
    -- Grade boundaries
    grade_a_threshold DECIMAL(5,2) DEFAULT 90.0,
    grade_b_threshold DECIMAL(5,2) DEFAULT 80.0,
    grade_c_threshold DECIMAL(5,2) DEFAULT 70.0,
    grade_d_threshold DECIMAL(5,2) DEFAULT 60.0,
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Route classification
CREATE TABLE IF NOT EXISTS route_classification (
    id SERIAL PRIMARY KEY,
    route_name VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    
    -- Service characteristics
    avg_frequency_per_hour DECIMAL(5,2),
    service_type VARCHAR(20),  -- 'high_frequency', 'timetabled', 'mixed'
    route_length_km DECIMAL(6,2),
    avg_journey_minutes DECIMAL(6,2),
    
    -- Custom weights (NULL = use default)
    custom_headway_weight DECIMAL(3,2),
    custom_schedule_weight DECIMAL(3,2),
    custom_journey_weight DECIMAL(3,2),
    custom_service_weight DECIMAL(3,2),
    
    classification_date DATE,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_route_class UNIQUE(route_name, direction, operator)
);

CREATE INDEX idx_route_class_type ON route_classification(service_type);

-- ============================================================================
-- INSERT DEFAULT CONFIGURATION
-- ============================================================================

INSERT INTO sri_config (
    config_version,
    effective_date,
    is_active
) VALUES (
    '1.0',
    '2024-01-01',
    TRUE
) ON CONFLICT DO NOTHING;

COMMIT;
