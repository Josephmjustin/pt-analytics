"""
Vehicle Matcher - Match GTFS-RT vehicles to TransXChange stops
Uses PostgreSQL database instead of loading JSON into memory
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.api.database import get_db_connection
from math import radians, cos, sin, asin, sqrt

ROUTE_CACHE = {}

def haversine(lon1, lat1, lon2, lat2):
    """Calculate distance between two points in meters"""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    m = 6371000 * c
    return m

def get_route_name(route_id: str) -> str:
    """Get route_short_name from gtfs_routes (cached)"""
    if route_id in ROUTE_CACHE:
        return ROUTE_CACHE[route_id]
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT route_short_name FROM gtfs_routes WHERE route_id = %s", (route_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    if result:
        route_name = result['route_short_name']
        ROUTE_CACHE[route_id] = route_name
        return route_name
    return None

def find_nearest_stop_for_route(lat: float, lon: float, route_name: str, radius_m: float = 10.0):
    """
    Find nearest stop for a specific route within radius
    Queries database instead of loading JSON
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Query stops that are on this route's patterns
    cur.execute("""
        SELECT DISTINCT
            s.naptan_id,
            s.stop_name,
            s.latitude,
            s.longitude
        FROM txc_stops s
        JOIN txc_pattern_stops ps ON s.naptan_id = ps.naptan_id
        JOIN txc_route_patterns rp ON ps.pattern_id = rp.pattern_id
        WHERE rp.route_name = %s
    """, (route_name,))
    
    stops = cur.fetchall()
    cur.close()
    conn.close()
    
    if not stops:
        return None
    
    # Find nearest stop within radius
    nearest = None
    min_distance = float('inf')
    
    for stop in stops:
        distance = haversine(lon, lat, stop['longitude'], stop['latitude'])
        if distance <= radius_m and distance < min_distance:
            min_distance = distance
            nearest = (stop['naptan_id'], stop['stop_name'], distance)
    
    return nearest

def match_vehicle_to_stop(vehicle_position: dict) -> dict:
    """Match vehicle to nearest valid stop for its route"""
    
    vehicle_id = vehicle_position['vehicle_id']
    route_id = vehicle_position.get('route_id')
    lat = vehicle_position['latitude']
    lon = vehicle_position['longitude']
    # Handle both 'timestamp' and 'stop_timestamp' keys
    timestamp = vehicle_position.get('timestamp') or vehicle_position.get('stop_timestamp')
    # Get direction from SIRI-VM data
    direction = vehicle_position.get('direction')
    
    route_name = get_route_name(route_id) if route_id else None
    
    if not route_name:
        return {
            'vehicle_id': vehicle_id,
            'route_name': None,
            'direction': direction,
            'naptan_id': None,
            'timestamp': timestamp,
            'matched': False
        }
    
    nearest = find_nearest_stop_for_route(lat, lon, route_name, radius_m=30.0)
    
    if not nearest:
        return {
            'vehicle_id': vehicle_id,
            'route_name': route_name,
            'direction': direction,
            'naptan_id': None,
            'timestamp': timestamp,
            'matched': False
        }
    
    naptan_id, stop_name, distance = nearest
    
    return {
        'vehicle_id': vehicle_id,
        'route_name': route_name,
        'direction': direction,
        'naptan_id': naptan_id,
        'stop_name': stop_name,
        'distance_m': round(distance, 1),
        'timestamp': timestamp,
        'matched': True
    }
