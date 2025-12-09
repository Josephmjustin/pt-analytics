"""
Vehicle Matcher - Match GTFS-RT vehicles to TransXChange stops
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.api.transxchange_loader import find_nearest_stop, ensure_data_loaded
from src.api.database import get_db_connection

ROUTE_CACHE = {}

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

def match_vehicle_to_stop(vehicle_position: dict) -> dict:
    """Match vehicle to nearest valid stop for its route"""
    ensure_data_loaded()
    
    vehicle_id = vehicle_position['vehicle_id']
    route_id = vehicle_position.get('route_id')
    lat = vehicle_position['latitude']
    lon = vehicle_position['longitude']
    timestamp = vehicle_position['timestamp']
    
    route_name = get_route_name(route_id) if route_id else None
    
    if not route_name:
        return {
            'vehicle_id': vehicle_id,
            'route_name': None,
            'naptan_id': None,
            'timestamp': timestamp,
            'matched': False
        }
    
    nearest = find_nearest_stop(lat, lon, route_name=route_name, radius_m=10)
    
    if not nearest:
        return {
            'vehicle_id': vehicle_id,
            'route_name': route_name,
            'naptan_id': None,
            'timestamp': timestamp,
            'matched': False
        }
    
    naptan_id, stop_data, distance = nearest
    
    return {
        'vehicle_id': vehicle_id,
        'route_name': route_name,
        'naptan_id': naptan_id,
        'stop_name': stop_data['name'],
        'distance_m': round(distance, 1),
        'timestamp': timestamp,
        'matched': True
    }
