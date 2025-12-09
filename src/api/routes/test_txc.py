"""
Test endpoint to verify TransXChange data loading
"""
from fastapi import APIRouter
from src.api.transxchange_loader import (
    get_stop_info,
    get_routes_at_stop,
    get_all_stops_for_route,
    STOPS,
    ROUTE_STOPS
)

router = APIRouter(prefix="/test-txc", tags=["test"])

@router.get("/status")
def txc_status():
    """Check if TransXChange data is loaded"""
    from src.api import transxchange_loader
    # Force load if not loaded
    transxchange_loader.ensure_data_loaded()
    return {
        "loaded": len(transxchange_loader.STOPS) > 0,
        "total_stops": len(transxchange_loader.STOPS),
        "total_routes": len(transxchange_loader.ROUTE_STOPS),
        "sample_routes": list(transxchange_loader.ROUTE_STOPS.keys())[:5]
    }

@router.get("/stop/{naptan_id}")
def test_stop(naptan_id: str):
    """Test getting stop info"""
    stop = get_stop_info(naptan_id)
    if not stop:
        return {"error": "Stop not found"}
    
    routes = get_routes_at_stop(naptan_id)
    
    return {
        "stop": stop,
        "routes": routes
    }

@router.get("/route/{route_name}/stops")
def test_route_stops(route_name: str):
    """Test getting stops for a route"""
    stops = get_all_stops_for_route(route_name)
    
    if not stops:
        return {"error": "Route not found"}
    
    # Check if our test stop is in there
    test_stop = "2800S42023F"
    has_test_stop = test_stop in stops
    
    return {
        "route": route_name,
        "stop_count": len(stops),
        "stops": list(stops)[:10],  # First 10 for brevity
        "has_queen_square_stand_5": has_test_stop
    }

@router.get("/debug/route-variants/{route_name}")
def debug_route_variants(route_name: str):
    """Debug: Show all variants of a route"""
    from src.api import transxchange_loader
    transxchange_loader.ensure_data_loaded()
    
    variants = []
    for op_name, op_data in transxchange_loader.TXC_DATA['operators'].items():
        for route in op_data['routes']:
            if route['route_name'] == route_name:
                variants.append({
                    'operator': op_name,
                    'service_code': route['service_code'],
                    'direction': route.get('direction'),
                    'description': route.get('description'),
                    'stop_count': len(route['stops']),
                    'first_stops': route['stops'][:5],
                    'has_stand_5': '2800S42023F' in route['stops']
                })
    
    return {
        'route_name': route_name,
        'total_variants': len(variants),
        'variants': variants
    }
