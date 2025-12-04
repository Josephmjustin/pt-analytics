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
-- Name: tiger; Type: SCHEMA; Schema: -; Owner: ptqueryer
--

CREATE SCHEMA tiger;


ALTER SCHEMA tiger OWNER TO ptqueryer;

--
-- Name: tiger_data; Type: SCHEMA; Schema: -; Owner: ptqueryer
--

CREATE SCHEMA tiger_data;


ALTER SCHEMA tiger_data OWNER TO ptqueryer;

--
-- Name: topology; Type: SCHEMA; Schema: -; Owner: ptqueryer
--

CREATE SCHEMA topology;


ALTER SCHEMA topology OWNER TO ptqueryer;

--
-- Name: SCHEMA topology; Type: COMMENT; Schema: -; Owner: ptqueryer
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
-- Name: bunching_by_day; Type: TABLE; Schema: public; Owner: ptqueryer
--

CREATE TABLE public.bunching_by_day (
    stop_id text NOT NULL,
    day_of_week integer NOT NULL,
    avg_bunching_rate numeric,
    total_count integer,
    last_updated timestamp without time zone DEFAULT now()
);


ALTER TABLE public.bunching_by_day OWNER TO ptqueryer;

--
-- Name: bunching_by_hour; Type: TABLE; Schema: public; Owner: ptqueryer
--

CREATE TABLE public.bunching_by_hour (
    stop_id text NOT NULL,
    hour_of_day integer NOT NULL,
    avg_bunching_rate numeric,
    total_count integer,
    last_updated timestamp without time zone DEFAULT now()
);


ALTER TABLE public.bunching_by_hour OWNER TO ptqueryer;

--
-- Name: bunching_by_hour_day; Type: TABLE; Schema: public; Owner: ptqueryer
--

CREATE TABLE public.bunching_by_hour_day (
    stop_id text NOT NULL,
    hour_of_day integer NOT NULL,
    day_of_week integer NOT NULL,
    avg_bunching_rate numeric,
    total_count integer,
    last_updated timestamp without time zone DEFAULT now()
);


ALTER TABLE public.bunching_by_hour_day OWNER TO ptqueryer;

--
-- Name: bunching_by_month; Type: TABLE; Schema: public; Owner: ptqueryer
--

CREATE TABLE public.bunching_by_month (
    stop_id text NOT NULL,
    month integer NOT NULL,
    avg_bunching_rate numeric,
    total_count integer,
    last_updated timestamp without time zone DEFAULT now()
);


ALTER TABLE public.bunching_by_month OWNER TO ptqueryer;

--
-- Name: bunching_by_stop; Type: TABLE; Schema: public; Owner: ptqueryer
--

CREATE TABLE public.bunching_by_stop (
    stop_id text NOT NULL,
    stop_name text,
    avg_bunching_rate numeric,
    total_count integer,
    last_updated timestamp without time zone DEFAULT now()
);


ALTER TABLE public.bunching_by_stop OWNER TO ptqueryer;

--
-- Name: bunching_scores; Type: TABLE; Schema: public; Owner: ptqueryer
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


ALTER TABLE public.bunching_scores OWNER TO ptqueryer;

--
-- Name: bunching_scores_id_seq; Type: SEQUENCE; Schema: public; Owner: ptqueryer
--

CREATE SEQUENCE public.bunching_scores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.bunching_scores_id_seq OWNER TO ptqueryer;

--
-- Name: bunching_scores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ptqueryer
--

ALTER SEQUENCE public.bunching_scores_id_seq OWNED BY public.bunching_scores.id;


--
-- Name: gtfs_routes; Type: TABLE; Schema: public; Owner: ptqueryer
--

CREATE TABLE public.gtfs_routes (
    route_id text NOT NULL,
    agency_id text,
    route_short_name text,
    route_long_name text,
    route_type integer
);


ALTER TABLE public.gtfs_routes OWNER TO ptqueryer;

--
-- Name: gtfs_stops; Type: TABLE; Schema: public; Owner: ptqueryer
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


ALTER TABLE public.gtfs_stops OWNER TO ptqueryer;

--
-- Name: gtfs_trips; Type: TABLE; Schema: public; Owner: ptqueryer
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


ALTER TABLE public.gtfs_trips OWNER TO ptqueryer;

--
-- Name: osm_stops; Type: TABLE; Schema: public; Owner: ptqueryer
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


ALTER TABLE public.osm_stops OWNER TO ptqueryer;

--
-- Name: vehicle_positions; Type: TABLE; Schema: public; Owner: ptqueryer
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


ALTER TABLE public.vehicle_positions OWNER TO ptqueryer;

--
-- Name: vehicle_positions_id_seq; Type: SEQUENCE; Schema: public; Owner: ptqueryer
--

CREATE SEQUENCE public.vehicle_positions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.vehicle_positions_id_seq OWNER TO ptqueryer;

--
-- Name: vehicle_positions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ptqueryer
--

ALTER SEQUENCE public.vehicle_positions_id_seq OWNED BY public.vehicle_positions.id;


--
-- Name: bunching_scores id; Type: DEFAULT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.bunching_scores ALTER COLUMN id SET DEFAULT nextval('public.bunching_scores_id_seq'::regclass);


--
-- Name: vehicle_positions id; Type: DEFAULT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.vehicle_positions ALTER COLUMN id SET DEFAULT nextval('public.vehicle_positions_id_seq'::regclass);


--
-- Name: bunching_by_day bunching_by_day_pkey; Type: CONSTRAINT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.bunching_by_day
    ADD CONSTRAINT bunching_by_day_pkey PRIMARY KEY (stop_id, day_of_week);


--
-- Name: bunching_by_hour_day bunching_by_hour_day_pkey; Type: CONSTRAINT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.bunching_by_hour_day
    ADD CONSTRAINT bunching_by_hour_day_pkey PRIMARY KEY (stop_id, hour_of_day, day_of_week);


--
-- Name: bunching_by_hour bunching_by_hour_pkey; Type: CONSTRAINT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.bunching_by_hour
    ADD CONSTRAINT bunching_by_hour_pkey PRIMARY KEY (stop_id, hour_of_day);


--
-- Name: bunching_by_month bunching_by_month_pkey; Type: CONSTRAINT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.bunching_by_month
    ADD CONSTRAINT bunching_by_month_pkey PRIMARY KEY (stop_id, month);


--
-- Name: bunching_by_stop bunching_by_stop_pkey; Type: CONSTRAINT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.bunching_by_stop
    ADD CONSTRAINT bunching_by_stop_pkey PRIMARY KEY (stop_id);


--
-- Name: bunching_scores bunching_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.bunching_scores
    ADD CONSTRAINT bunching_scores_pkey PRIMARY KEY (id);


--
-- Name: gtfs_routes gtfs_routes_pkey; Type: CONSTRAINT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.gtfs_routes
    ADD CONSTRAINT gtfs_routes_pkey PRIMARY KEY (route_id);


--
-- Name: gtfs_stops gtfs_stops_pkey; Type: CONSTRAINT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.gtfs_stops
    ADD CONSTRAINT gtfs_stops_pkey PRIMARY KEY (stop_id);


--
-- Name: gtfs_trips gtfs_trips_pkey; Type: CONSTRAINT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.gtfs_trips
    ADD CONSTRAINT gtfs_trips_pkey PRIMARY KEY (trip_id);


--
-- Name: osm_stops osm_stops_pkey; Type: CONSTRAINT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.osm_stops
    ADD CONSTRAINT osm_stops_pkey PRIMARY KEY (osm_id);


--
-- Name: bunching_scores unique_stop_analysis; Type: CONSTRAINT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.bunching_scores
    ADD CONSTRAINT unique_stop_analysis UNIQUE (stop_id, analysis_timestamp);


--
-- Name: vehicle_positions unique_vehicle_timestamp; Type: CONSTRAINT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.vehicle_positions
    ADD CONSTRAINT unique_vehicle_timestamp UNIQUE (vehicle_id, "timestamp");


--
-- Name: vehicle_positions vehicle_positions_pkey; Type: CONSTRAINT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.vehicle_positions
    ADD CONSTRAINT vehicle_positions_pkey PRIMARY KEY (id);


--
-- Name: idx_bunching_scores_stop; Type: INDEX; Schema: public; Owner: ptqueryer
--

CREATE INDEX idx_bunching_scores_stop ON public.bunching_scores USING btree (stop_id);


--
-- Name: idx_bunching_scores_timestamp; Type: INDEX; Schema: public; Owner: ptqueryer
--

CREATE INDEX idx_bunching_scores_timestamp ON public.bunching_scores USING btree (analysis_timestamp);


--
-- Name: idx_day; Type: INDEX; Schema: public; Owner: ptqueryer
--

CREATE INDEX idx_day ON public.bunching_by_day USING btree (day_of_week);


--
-- Name: idx_gtfs_stops_location; Type: INDEX; Schema: public; Owner: ptqueryer
--

CREATE INDEX idx_gtfs_stops_location ON public.gtfs_stops USING gist (location);


--
-- Name: idx_gtfs_trips_route_id; Type: INDEX; Schema: public; Owner: ptqueryer
--

CREATE INDEX idx_gtfs_trips_route_id ON public.gtfs_trips USING btree (route_id);


--
-- Name: idx_hour; Type: INDEX; Schema: public; Owner: ptqueryer
--

CREATE INDEX idx_hour ON public.bunching_by_hour USING btree (hour_of_day);


--
-- Name: idx_hour_day; Type: INDEX; Schema: public; Owner: ptqueryer
--

CREATE INDEX idx_hour_day ON public.bunching_by_hour_day USING btree (hour_of_day, day_of_week);


--
-- Name: idx_month; Type: INDEX; Schema: public; Owner: ptqueryer
--

CREATE INDEX idx_month ON public.bunching_by_month USING btree (month);


--
-- Name: idx_osm_stops_location; Type: INDEX; Schema: public; Owner: ptqueryer
--

CREATE INDEX idx_osm_stops_location ON public.osm_stops USING gist (location);


--
-- Name: idx_route_id; Type: INDEX; Schema: public; Owner: ptqueryer
--

CREATE INDEX idx_route_id ON public.vehicle_positions USING btree (route_id);


--
-- Name: idx_timestamp; Type: INDEX; Schema: public; Owner: ptqueryer
--

CREATE INDEX idx_timestamp ON public.vehicle_positions USING btree ("timestamp");


--
-- Name: idx_vehicle_id; Type: INDEX; Schema: public; Owner: ptqueryer
--

CREATE INDEX idx_vehicle_id ON public.vehicle_positions USING btree (vehicle_id);


--
-- Name: idx_vehicle_positions_geom; Type: INDEX; Schema: public; Owner: ptqueryer
--

CREATE INDEX idx_vehicle_positions_geom ON public.vehicle_positions USING gist (geom);


--
-- Name: gtfs_trips gtfs_trips_route_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ptqueryer
--

ALTER TABLE ONLY public.gtfs_trips
    ADD CONSTRAINT gtfs_trips_route_id_fkey FOREIGN KEY (route_id) REFERENCES public.gtfs_routes(route_id);


--
-- PostgreSQL database dump complete
--

