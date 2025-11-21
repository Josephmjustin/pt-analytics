CREATE TABLE vehicle_positions (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    route_id TEXT,
    trip_id TEXT,
    bearing INTEGER
);

-- Indexes for common queries
CREATE INDEX idx_vehicle_id ON vehicle_positions(vehicle_id);
CREATE INDEX idx_timestamp ON vehicle_positions(timestamp);
CREATE INDEX idx_route_id ON vehicle_positions(route_id);