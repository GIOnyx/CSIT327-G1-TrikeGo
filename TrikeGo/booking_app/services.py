import openrouteservice
from django.conf import settings
from .models import RouteSnapshot, DriverLocation
from decimal import Decimal
import math
import requests

class RoutingService:
    def __init__(self):
        self.api_key = settings.OPENROUTESERVICE_API_KEY
        self.client = openrouteservice.Client(key=self.api_key)
        self.base_url = 'https://api.openrouteservice.org'
    
    def geocode_address(self, query, focus_point=None):
        """
        Geocode an address using ORS Geocoding API
        
        Args:
            query: Address string to geocode
            focus_point: tuple (lon, lat) to bias results (optional)
        
        Returns:
            list of results with formatted address, lat, lon
        """
        try:
            url = f"{self.base_url}/geocode/search"
            params = {
                'api_key': self.api_key,
                'text': query,
                'size': 10,  # Increased from 5 to get more results
                'boundary.country': 'PH',  # Limit to Philippines only, no city bias
            }
            
            # Only apply focus if explicitly provided
            if focus_point:
                params['focus.point.lon'] = focus_point[0]
                params['focus.point.lat'] = focus_point[1]
            
            response = requests.get(url, params=params)
            data = response.json()
            
            results = []
            for feature in data.get('features', []):
                props = feature['properties']
                coords = feature['geometry']['coordinates']
                results.append({
                    'formatted': props.get('label', ''),
                    'name': props.get('name', ''),
                    'lat': coords[1],
                    'lon': coords[0]
                })
            
            return results
        except Exception as e:
            print(f"Geocoding error: {e}")
            return []
    
    def reverse_geocode(self, lat, lon):
        """
        Reverse geocode coordinates to address
        
        Args:
            lat: Latitude
            lon: Longitude
        
        Returns:
            dict with formatted address
        """
        try:
            url = f"{self.base_url}/geocode/reverse"
            params = {
                'api_key': self.api_key,
                'point.lon': lon,
                'point.lat': lat,
                'size': 1
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            if data.get('features'):
                props = data['features'][0]['properties']
                return {
                    'formatted': props.get('label', ''),
                    'name': props.get('name', ''),
                    'lat': lat,
                    'lon': lon
                }
            return None
        except Exception as e:
            print(f"Reverse geocoding error: {e}")
            return None
    
    def calculate_distance(self, coord1, coord2):
        """
        Calculate distance between two coordinates in kilometers
        
        Args:
            coord1: tuple (lon, lat)
            coord2: tuple (lon, lat)
        
        Returns:
            distance in kilometers
        """
        return self._haversine_distance(coord1[1], coord1[0], coord2[1], coord2[0]) / 1000
    
    def calculate_route(self, start_coords, end_coords, profile='driving-car'):
        """
        Calculate route between two points with traffic consideration
        
        Args:
            start_coords: tuple (longitude, latitude)
            end_coords: tuple (longitude, latitude)
            profile: 'driving-car', 'cycling-regular', 'foot-walking'
        
        Returns:
            dict with route_data, distance (km), duration (seconds)
        """
        try:
            # Check if points are too close (less than 50 meters)
            distance_m = self._haversine_distance(
                start_coords[1], start_coords[0],
                end_coords[1], end_coords[0]
            )
            
            if distance_m < 50:
                print(f"Points too close: {distance_m}m")
                return {
                    'route_data': None,
                    'distance': round(distance_m / 1000, 2),
                    'duration': int(distance_m / 1.4),  # Walking speed ~1.4 m/s
                    'too_close': True
                }
            
            coords = [start_coords, end_coords]
            
            # Request route with traffic consideration
            route = self.client.directions(
                coordinates=coords,
                profile=profile,
                format='geojson',
                geometry='true',
                instructions='true',
                elevation='false',
                # Note: Real-time traffic requires premium ORS subscription
                # For now, we use standard routing which considers typical traffic patterns
            )
            
            # Extract route information
            distance = route['features'][0]['properties']['segments'][0]['distance'] / 1000
            duration = route['features'][0]['properties']['segments'][0]['duration']
            
            return {
                'route_data': route,
                'distance': round(distance, 2),
                'duration': int(duration),
                'too_close': False
            }
        except Exception as e:
            print(f"Routing error: {e}")
            return None
    
    def save_route_snapshot(self, booking, route_info):
        """Save route snapshot to database"""
        if route_info and not route_info.get('too_close'):
            # Deactivate previous routes
            RouteSnapshot.objects.filter(booking=booking, is_active=True).update(is_active=False)
            
            # Create new route snapshot
            snapshot = RouteSnapshot.objects.create(
                booking=booking,
                route_data=route_info['route_data'],
                distance=Decimal(str(route_info['distance'])),
                duration=route_info['duration'],
                is_active=True
            )
            return snapshot
        return None
    
    def should_reroute(self, driver_location, current_route, threshold_meters=100):
        """
        Determine if rerouting is needed based on driver's deviation from route
        
        Args:
            driver_location: DriverLocation object
            current_route: RouteSnapshot object
            threshold_meters: deviation threshold in meters (default 100m)
        
        Returns:
            bool: True if rerouting is needed
        """
        if not current_route or not current_route.route_data:
            return True
        
        try:
            # Get route coordinates
            route_coords = current_route.route_data['features'][0]['geometry']['coordinates']
            driver_point = (float(driver_location.longitude), float(driver_location.latitude))
            
            # Find minimum distance to route
            min_distance = float('inf')
            for coord in route_coords:
                distance = self._haversine_distance(
                    driver_point[1], driver_point[0],
                    coord[1], coord[0]
                )
                min_distance = min(min_distance, distance)
            
            return min_distance > threshold_meters
        except Exception as e:
            print(f"Error checking route deviation: {e}")
            return False
    
    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in meters"""
        R = 6371000  # Earth's radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def get_eta(self, driver_location, destination_coords):
        """
        Calculate estimated time of arrival from driver's current location
        
        Returns:
            int: ETA in seconds, or None if calculation fails
        """
        driver_coords = (float(driver_location.longitude), float(driver_location.latitude))
        route_info = self.calculate_route(driver_coords, destination_coords)
        
        if route_info and not route_info.get('too_close'):
            return route_info['duration']
        elif route_info and route_info.get('too_close'):
            # If very close, return the calculated duration for short distance
            return route_info['duration']
        return None