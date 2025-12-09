"""
Stop Event Detector
Finds stop events from vehicle position history
A stop event = vehicle at same location for 2+ consecutive timestamps
"""

def find_stop_events(vehicle_positions):
    """
    Find stop events from vehicle position history
    
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
            current_ts = positions[i]['timestamp']
            current_lat = positions[i]['latitude']
            current_lon = positions[i]['longitude']
            route_id = positions[i].get('route_id')
            
            # Count consecutive same timestamps
            dwell_count = 1
            j = i + 1
            while j < len(positions) and positions[j]['timestamp'] == current_ts:
                dwell_count += 1
                j += 1
            
            # If stopped for 2+ polls (20+ seconds), it's a stop event
            if dwell_count >= 2:
                stops.append({
                    'vehicle_id': vehicle_id,
                    'route_id': route_id,
                    'latitude': current_lat,
                    'longitude': current_lon,
                    'stop_timestamp': current_ts,
                    'dwell_time_seconds': dwell_count * 10,
                    'poll_count': dwell_count
                })
            
            # Skip to next different timestamp
            i = j
    
    return stops
