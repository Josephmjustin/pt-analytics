--
-- PostgreSQL database dump
--

-- Dumped from database version 15.8 (Debian 15.8-1.pgdg110+1)
-- Dumped by pg_dump version 15.8 (Debian 15.8-1.pgdg110+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
--

CREATE SCHEMA tiger;



--
--

CREATE SCHEMA tiger_data;



--
--

CREATE SCHEMA topology;



--
--

COMMENT ON SCHEMA topology IS 'PostGIS Topology schema';


--
-- Name: fuzzystrmatch; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS fuzzystrmatch WITH SCHEMA public;


--
-- Name: EXTENSION fuzzystrmatch; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION fuzzystrmatch IS 'determine similarities and distance between strings';


--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: postgis_tiger_geocoder; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder WITH SCHEMA tiger;


--
-- Name: EXTENSION postgis_tiger_geocoder; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis_tiger_geocoder IS 'PostGIS tiger geocoder and reverse geocoder';


--
-- Name: postgis_topology; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis_topology WITH SCHEMA topology;


--
-- Name: EXTENSION postgis_topology; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis_topology IS 'PostGIS topology spatial types and functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
--

CREATE TABLE public.bunching_by_day (
    stop_id text NOT NULL,
    day_of_week integer NOT NULL,
    avg_bunching_rate numeric,
    total_count integer,
    last_updated timestamp without time zone DEFAULT now()
);



--
--

CREATE TABLE public.bunching_by_hour (
    stop_id text NOT NULL,
    hour_of_day integer NOT NULL,
    avg_bunching_rate numeric,
    total_count integer,
    last_updated timestamp without time zone DEFAULT now()
);



--
--

CREATE TABLE public.bunching_by_hour_day (
    stop_id text NOT NULL,
    hour_of_day integer NOT NULL,
    day_of_week integer NOT NULL,
    avg_bunching_rate numeric,
    total_count integer,
    last_updated timestamp without time zone DEFAULT now()
);



--
--

CREATE TABLE public.bunching_by_month (
    stop_id text NOT NULL,
    month integer NOT NULL,
    avg_bunching_rate numeric,
    total_count integer,
    last_updated timestamp without time zone DEFAULT now()
);



--
--

CREATE TABLE public.bunching_by_stop (
    stop_id text NOT NULL,
    stop_name text,
    avg_bunching_rate numeric,
    total_count integer,
    last_updated timestamp without time zone DEFAULT now()
);



--
--

CREATE TABLE public.bunching_scores (
    id integer NOT NULL,
    stop_id text NOT NULL,
    stop_name text NOT NULL,
    analysis_timestamp timestamp without time zone DEFAULT now() NOT NULL,
    total_arrivals integer NOT NULL,
    bunched_count integer NOT NULL,
    bunching_rate_pct numeric(5,2) NOT NULL,
    avg_headway_minutes numeric(10,2),
    min_headway_minutes numeric(10,2),
    max_headway_minutes numeric(10,2),
    data_window_start timestamp without time zone NOT NULL,
    data_window_end timestamp without time zone NOT NULL
);



--
--

CREATE SEQUENCE public.bunching_scores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



--
--

ALTER SEQUENCE public.bunching_scores_id_seq OWNED BY public.bunching_scores.id;


--
--

CREATE TABLE public.gtfs_routes (
    route_id text NOT NULL,
    agency_id text,
    route_short_name text,
    route_long_name text,
    route_type integer
);



--
--

CREATE TABLE public.gtfs_stops (
    stop_id text NOT NULL,
    stop_code text,
    stop_name text NOT NULL,
    stop_lat double precision NOT NULL,
    stop_lon double precision NOT NULL,
    location public.geometry(Point,4326),
    wheelchair_boarding integer,
    location_type integer,
    parent_station text,
    platform_code text
);



--
--

CREATE TABLE public.gtfs_trips (
    trip_id text NOT NULL,
    route_id text,
    service_id text,
    trip_headsign text,
    direction_id integer,
    block_id text,
    shape_id text,
    wheelchair_accessible integer,
    vehicle_journey_code text
);



--
--

CREATE TABLE public.osm_stops (
    osm_id bigint NOT NULL,
    name text,
    latitude double precision NOT NULL,
    longitude double precision NOT NULL,
    location public.geography(Point,4326),
    tags jsonb,
    created_at timestamp without time zone DEFAULT now()
);



--
--

CREATE TABLE public.vehicle_positions (
    id integer NOT NULL,
    vehicle_id text NOT NULL,
    latitude double precision NOT NULL,
    longitude double precision NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    route_id text,
    trip_id text,
    bearing integer,
    geom public.geometry(Point,4326)
);



--
--

CREATE SEQUENCE public.vehicle_positions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



--
--

ALTER SEQUENCE public.vehicle_positions_id_seq OWNED BY public.vehicle_positions.id;


--
--

ALTER TABLE ONLY public.bunching_scores ALTER COLUMN id SET DEFAULT nextval('public.bunching_scores_id_seq'::regclass);


--
--

ALTER TABLE ONLY public.vehicle_positions ALTER COLUMN id SET DEFAULT nextval('public.vehicle_positions_id_seq'::regclass);


--
--

ALTER TABLE ONLY public.bunching_by_day
    ADD CONSTRAINT bunching_by_day_pkey PRIMARY KEY (stop_id, day_of_week);


--
--

ALTER TABLE ONLY public.bunching_by_hour_day
    ADD CONSTRAINT bunching_by_hour_day_pkey PRIMARY KEY (stop_id, hour_of_day, day_of_week);


--
--

ALTER TABLE ONLY public.bunching_by_hour
    ADD CONSTRAINT bunching_by_hour_pkey PRIMARY KEY (stop_id, hour_of_day);


--
--

ALTER TABLE ONLY public.bunching_by_month
    ADD CONSTRAINT bunching_by_month_pkey PRIMARY KEY (stop_id, month);


--
--

ALTER TABLE ONLY public.bunching_by_stop
    ADD CONSTRAINT bunching_by_stop_pkey PRIMARY KEY (stop_id);


--
--

ALTER TABLE ONLY public.bunching_scores
    ADD CONSTRAINT bunching_scores_pkey PRIMARY KEY (id);


--
--

ALTER TABLE ONLY public.gtfs_routes
    ADD CONSTRAINT gtfs_routes_pkey PRIMARY KEY (route_id);


--
--

ALTER TABLE ONLY public.gtfs_stops
    ADD CONSTRAINT gtfs_stops_pkey PRIMARY KEY (stop_id);


--
--

ALTER TABLE ONLY public.gtfs_trips
    ADD CONSTRAINT gtfs_trips_pkey PRIMARY KEY (trip_id);


--
--

ALTER TABLE ONLY public.osm_stops
    ADD CONSTRAINT osm_stops_pkey PRIMARY KEY (osm_id);


--
--

ALTER TABLE ONLY public.bunching_scores
    ADD CONSTRAINT unique_stop_analysis UNIQUE (stop_id, analysis_timestamp);


--
--

ALTER TABLE ONLY public.vehicle_positions
    ADD CONSTRAINT unique_vehicle_timestamp UNIQUE (vehicle_id, "timestamp");


--
--

ALTER TABLE ONLY public.vehicle_positions
    ADD CONSTRAINT vehicle_positions_pkey PRIMARY KEY (id);


--
--

CREATE INDEX idx_bunching_scores_stop ON public.bunching_scores USING btree (stop_id);


--
--

CREATE INDEX idx_bunching_scores_timestamp ON public.bunching_scores USING btree (analysis_timestamp);


--
--

CREATE INDEX idx_day ON public.bunching_by_day USING btree (day_of_week);


--
--

CREATE INDEX idx_gtfs_stops_location ON public.gtfs_stops USING gist (location);


--
--

CREATE INDEX idx_gtfs_trips_route_id ON public.gtfs_trips USING btree (route_id);


--
--

CREATE INDEX idx_hour ON public.bunching_by_hour USING btree (hour_of_day);


--
--

CREATE INDEX idx_hour_day ON public.bunching_by_hour_day USING btree (hour_of_day, day_of_week);


--
--

CREATE INDEX idx_month ON public.bunching_by_month USING btree (month);


--
--

CREATE INDEX idx_osm_stops_location ON public.osm_stops USING gist (location);


--
--

CREATE INDEX idx_route_id ON public.vehicle_positions USING btree (route_id);


--
--

CREATE INDEX idx_timestamp ON public.vehicle_positions USING btree ("timestamp");


--
--

CREATE INDEX idx_vehicle_id ON public.vehicle_positions USING btree (vehicle_id);


--
--

CREATE INDEX idx_vehicle_positions_geom ON public.vehicle_positions USING gist (geom);


--
--

ALTER TABLE ONLY public.gtfs_trips
    ADD CONSTRAINT gtfs_trips_route_id_fkey FOREIGN KEY (route_id) REFERENCES public.gtfs_routes(route_id);


--
-- PostgreSQL database dump complete
--

