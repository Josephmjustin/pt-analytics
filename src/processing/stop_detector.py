"""
Stop Event Detector
Finds stop events from vehicle position history
A stop event = vehicle at same location for 2+ consecutive timestamps
"""

def find_stop_events(vehicle_positions):
    """
    Find stop events from vehicle position history
    A stop event = vehicle at same location (lat/lon) for 2+ consecutive timestamps
    
    Args:
        vehicle_positions: List of dicts with vehicle_id, timestamp, lat, lon, route_id
    
    Returns:
        List of stop events with dwell time
    """
    if not vehicle_positions:
        return []
    
    stops = []
    
    # Group by vehicle
    by_vehicle = {}
    for pos in vehicle_positions:
        vid = pos['vehicle_id']
        if vid not in by_vehicle:
            by_vehicle[vid] = []
        by_vehicle[vid].append(pos)
    
    # Process each vehicle's timeline
    for vehicle_id, positions in by_vehicle.items():
        # Sort by timestamp
        positions.sort(key=lambda x: x['timestamp'])
        
        i = 0
        while i < len(positions):
            current_lat = positions[i]['latitude']
            current_lon = positions[i]['longitude']
            current_ts = positions[i]['timestamp']
            route_id = positions[i].get('route_id')
            
            # Count consecutive positions at SAME location (within 5 meters)
            dwell_count = 1
            j = i + 1
            
            while j < len(positions):
                # Check if vehicle still at same location (within 5m tolerance)
                lat_diff = abs(positions[j]['latitude'] - current_lat)
                lon_diff = abs(positions[j]['longitude'] - current_lon)
                
                # Roughly 0.00005 degrees = ~5 meters
                if lat_diff < 0.00005 and lon_diff < 0.00005:
                    dwell_count += 1
                    j += 1
                else:
                    # Vehicle moved - stop event ended
                    break
            
            # If stopped for 2+ polls (20+ seconds), it's a stop event
            if dwell_count >= 2:
                stops.append({
                    'vehicle_id': vehicle_id,
                    'route_id': route_id,
                    'latitude': current_lat,
                    'longitude': current_lon,
                    'stop_timestamp': current_ts,  # First timestamp of stop
                    'dwell_time_seconds': dwell_count * 10,
                    'poll_count': dwell_count
                })
            
            # Skip to next different location
            i = j if j > i + 1 else i + 1
    
    return stops
