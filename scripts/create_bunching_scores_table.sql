-- Bunching scores table: stores aggregated metrics over time
-- This is what we keep long-term (raw data gets deleted)

CREATE TABLE IF NOT EXISTS bunching_scores (
    id SERIAL PRIMARY KEY,
    stop_id TEXT NOT NULL,
    stop_name TEXT NOT NULL,
    analysis_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    total_arrivals INTEGER NOT NULL,
    bunched_count INTEGER NOT NULL,
    bunching_rate_pct NUMERIC(5,2) NOT NULL,
    avg_headway_minutes NUMERIC(10,2),
    min_headway_minutes NUMERIC(10,2),
    max_headway_minutes NUMERIC(10,2),
    data_window_start TIMESTAMP NOT NULL,
    data_window_end TIMESTAMP NOT NULL,
    CONSTRAINT unique_stop_analysis UNIQUE (stop_id, analysis_timestamp)
);

CREATE INDEX idx_bunching_scores_stop ON bunching_scores(stop_id);
CREATE INDEX idx_bunching_scores_timestamp ON bunching_scores(analysis_timestamp);
