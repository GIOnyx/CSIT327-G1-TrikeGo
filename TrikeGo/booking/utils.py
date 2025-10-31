from typing import Dict, List, Optional, Tuple

from django.utils import timezone

try:
    from fare_estimation.distance import calculate_distance
except ModuleNotFoundError:
    import math

    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Fallback haversine calculation in kilometers."""
        radius = 6371.0
        ph1, ph2 = math.radians(lat1), math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)
        a = math.sin(d_phi / 2) ** 2 + math.cos(ph1) * math.cos(ph2) * math.sin(d_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return radius * c

from .models import Booking, BookingStop, DriverLocation
from .services import RoutingService
from user.models import Driver, Tricycle


def seats_available(driver_user, additional_seats: int = 1) -> bool:
    """Return True if driver has capacity for additional seats based on their tricycle's max capacity."""
    active_bookings = Booking.objects.filter(
        driver=driver_user,
        status__in=['accepted', 'on_the_way', 'started']
    )

    active_seats = 0
    for booking in active_bookings:
        active_seats += int(getattr(booking, 'passengers', 1) or 1)

    driver_profile = Driver.objects.filter(user=driver_user).first()
    if not driver_profile:
        return False

    trike = Tricycle.objects.filter(driver=driver_profile).first()
    max_capacity = int(getattr(trike, 'max_capacity', 1) or 1)

    return (active_seats + int(additional_seats or 1)) <= max_capacity


def pickup_within_detour(driver_user, pickup_lat: float, pickup_lon: float, max_km: float = 0.5) -> bool:
    """Simple option A detour check: return True if pickup is within `max_km` of any point on the driver's
    current route approximation (driver current location + active bookings' pickup/destination points).
    """
    driver_profile = Driver.objects.filter(user=driver_user).first()
    points = []  # list of (lat, lon)

    if driver_profile:
        if driver_profile.current_latitude is not None and driver_profile.current_longitude is not None:
            try:
                points.append((float(driver_profile.current_latitude), float(driver_profile.current_longitude)))
            except Exception:
                pass

    # include active bookings' waypoints
    active_bookings = Booking.objects.filter(driver=driver_user, status__in=['accepted', 'on_the_way', 'started'])
    for b in active_bookings:
        if b.pickup_latitude is not None and b.pickup_longitude is not None:
            try:
                points.append((float(b.pickup_latitude), float(b.pickup_longitude)))
            except Exception:
                pass
        if b.destination_latitude is not None and b.destination_longitude is not None:
            try:
                points.append((float(b.destination_latitude), float(b.destination_longitude)))
            except Exception:
                pass

    # if we have no points to check against (no current location, no active bookings), allow by default
    if not points:
        return True

    for pt_lat, pt_lon in points:
        try:
            d = calculate_distance(pt_lat, pt_lon, float(pickup_lat), float(pickup_lon))
            if d <= float(max_km):
                return True
        except Exception:
            continue

    return False


# ---- Multi-stop itinerary helpers ----

def ensure_booking_stops(booking: Booking) -> None:
    """Ensure the booking has pickup and dropoff BookingStop entries."""
    stops = {stop.stop_type: stop for stop in booking.stops.all()}

    driver_user = booking.driver
    next_sequence_values = []
    if driver_user:
        next_sequence_values = driver_user.driver_bookings.filter(
            status__in=['accepted', 'on_the_way', 'started']
        ).values_list('stops__sequence', flat=True)
    seq = max([s for s in next_sequence_values if s is not None], default=0) + 1

    created = False

    if 'PICKUP' not in stops:
        BookingStop.objects.create(
            booking=booking,
            sequence=seq,
            stop_type='PICKUP',
            status='UPCOMING',
            passenger_count=int(getattr(booking, 'passengers', 1) or 1),
            address=booking.pickup_address,
            latitude=booking.pickup_latitude,
            longitude=booking.pickup_longitude,
        )
        created = True
        seq += 1

    if 'DROPOFF' not in stops:
        BookingStop.objects.create(
            booking=booking,
            sequence=seq,
            stop_type='DROPOFF',
            status='UPCOMING',
            passenger_count=int(getattr(booking, 'passengers', 1) or 1),
            address=booking.destination_address,
            latitude=booking.destination_latitude,
            longitude=booking.destination_longitude,
        )
        created = True

    if created and booking.driver:
        resequence_driver_stops(booking.driver)


def resequence_driver_stops(driver_user) -> None:
    """Normalize the sequence numbers for a driver's active stops."""
    stops = BookingStop.objects.filter(
        booking__driver=driver_user,
        booking__status__in=['accepted', 'on_the_way', 'started']
    ).order_by('created_at')

    for idx, stop in enumerate(stops, start=1):
        if stop.sequence != idx:
            stop.sequence = idx
            stop.save(update_fields=['sequence'])


def _driver_start_location(driver_user) -> Optional[Tuple[float, float]]:
    try:
        location = DriverLocation.objects.get(driver=driver_user)
        return (float(location.latitude), float(location.longitude))
    except DriverLocation.DoesNotExist:
        pass

    driver_profile = Driver.objects.filter(user=driver_user).first()
    if driver_profile and driver_profile.current_latitude and driver_profile.current_longitude:
        return (float(driver_profile.current_latitude), float(driver_profile.current_longitude))

    return None


def _stop_coordinates(stop: BookingStop) -> Optional[Tuple[float, float]]:
    if stop.latitude is None or stop.longitude is None:
        return None
    return (float(stop.latitude), float(stop.longitude))


def _append_unique_point(polyline: List[List[float]], lat: float, lon: float, epsilon: float = 1e-6) -> None:
    """Append point to polyline only if it differs from the previous point."""
    if lat is None or lon is None:
        return

    lat_f = float(lat)
    lon_f = float(lon)

    if not polyline:
        polyline.append([lat_f, lon_f])
        return

    last_lat, last_lon = polyline[-1]
    if abs(last_lat - lat_f) > epsilon or abs(last_lon - lon_f) > epsilon:
        polyline.append([lat_f, lon_f])


def _segment_route(
    start: Tuple[float, float],
    end: Tuple[float, float],
    routing_service: Optional[RoutingService],
    cache: Dict[Tuple[float, float, float, float], Tuple[Optional[List[List[float]]], bool]],
) -> Tuple[Optional[List[List[float]]], bool]:
    """Return route points for a segment along with a flag indicating if ORS provided geometry."""

    if routing_service is None:
        return None, False

    key = (
        round(start[0], 5),
        round(start[1], 5),
        round(end[0], 5),
        round(end[1], 5),
    )

    if key in cache:
        return cache[key]

    try:
        route_info = routing_service.calculate_route(
            (start[1], start[0]),
            (end[1], end[0]),
            profile='driving-car'
        )
    except Exception:
        cache[key] = (None, False)
        return cache[key]

    if not route_info:
        cache[key] = (None, False)
        return cache[key]

    if route_info.get('too_close'):
        segment = [[float(start[0]), float(start[1])], [float(end[0]), float(end[1])]]
        cache[key] = (segment, False)
        return cache[key]

    route_data = route_info.get('route_data') or {}
    features = route_data.get('features') or []
    if not features:
        cache[key] = (None, False)
        return cache[key]

    geometry = features[0].get('geometry') or {}
    coordinates = geometry.get('coordinates') or []
    if len(coordinates) < 2:
        cache[key] = (None, False)
        return cache[key]

    segment = [[float(coord[1]), float(coord[0])] for coord in coordinates]
    cache[key] = (segment, True)
    return cache[key]


def _build_route_polyline(
    start_coord: Optional[Tuple[float, float]],
    stops: List[BookingStop]
) -> Tuple[List[List[float]], bool, List[Dict[str, object]]]:
    """Construct a polyline for the full itinerary using ORS routes when possible."""

    polyline: List[List[float]] = []
    used_precise_route = False
    segments: List[Dict[str, object]] = []

    try:
        routing_service = RoutingService()
    except Exception:
        routing_service = None

    segment_cache: Dict[Tuple[float, float, float, float], Tuple[Optional[List[List[float]]], bool]] = {}

    previous_coord = start_coord if start_coord else None
    if start_coord:
        _append_unique_point(polyline, start_coord[0], start_coord[1])

    for stop in stops:
        next_coord = _stop_coordinates(stop)
        if next_coord is None:
            # Skip stops without coordinates, but preserve the last known point
            continue

        if previous_coord is None:
            _append_unique_point(polyline, next_coord[0], next_coord[1])
            previous_coord = next_coord
            continue

        segment, precise = _segment_route(previous_coord, next_coord, routing_service, segment_cache)
        used_precise_route = used_precise_route or precise
        segment_points: Optional[List[List[float]]] = None
        if segment:
            segment_points = [[float(lat), float(lon)] for lat, lon in segment]
            for lat, lon in segment_points:
                _append_unique_point(polyline, lat, lon)
        else:
            fallback_segment = [
                [float(previous_coord[0]), float(previous_coord[1])],
                [float(next_coord[0]), float(next_coord[1])],
            ]
            for lat, lon in fallback_segment:
                _append_unique_point(polyline, lat, lon)
            segment_points = fallback_segment
            precise = False

        if segment_points:
            segments.append({
                'type': stop.stop_type,
                'points': segment_points,
                'precise': precise,
            })

        previous_coord = next_coord

    if not polyline and start_coord:
        _append_unique_point(polyline, start_coord[0], start_coord[1])

    return polyline, used_precise_route, segments


def plan_driver_stops(driver_user) -> List[BookingStop]:
    """Generate an ordered list of stops for the driver's active bookings."""
    stops = list(
        BookingStop.objects.filter(
            booking__driver=driver_user,
            booking__status__in=['accepted', 'on_the_way', 'started']
        ).select_related('booking')
    )

    if not stops:
        return []

    completed = [s for s in stops if s.status == 'COMPLETED']
    pending = [s for s in stops if s.status != 'COMPLETED']

    ordered_completed = sorted(
        completed,
        key=lambda s: (s.completed_at or timezone.now(), s.sequence, s.id)
    )

    order: List[BookingStop] = ordered_completed.copy()

    # Prepare lookup for pickup completion to gate drop-offs
    completed_pickups = {
        stop.booking_id
        for stop in ordered_completed
        if stop.stop_type == 'PICKUP'
    }

    current_location = _driver_start_location(driver_user)
    if current_location is None and ordered_completed:
        coord = _stop_coordinates(ordered_completed[-1])
        if coord:
            current_location = coord

    pending_work = pending.copy()
    while pending_work:
        candidates = []
        for stop in pending_work:
            if stop.stop_type == 'DROPOFF' and stop.booking_id not in completed_pickups:
                continue
            candidates.append(stop)

        if not candidates:
            candidates = pending_work.copy()

        best_stop = None
        best_distance = None

        for stop in candidates:
            coord = _stop_coordinates(stop)
            if coord is None:
                # Prefer stops with coordinates missing last to avoid blocking others
                if best_stop is None:
                    best_stop = stop
                    best_distance = None
                continue

            if current_location is None:
                best_stop = stop
                best_distance = 0
                break

            dist = calculate_distance(current_location[0], current_location[1], coord[0], coord[1])
            if best_distance is None or dist < best_distance:
                best_distance = dist
                best_stop = stop

        if best_stop is None:
            best_stop = pending_work[0]

        order.append(best_stop)
        pending_work.remove(best_stop)

        if best_stop.stop_type == 'PICKUP':
            completed_pickups.add(best_stop.booking_id)

        coord = _stop_coordinates(best_stop)
        if coord:
            current_location = coord

    # Update sequences and statuses (current/upcoming)
    first_incomplete_found = False
    for idx, stop in enumerate(order, start=1):
        updates = []
        if stop.sequence != idx:
            stop.sequence = idx
            updates.append('sequence')

        if stop.status != 'COMPLETED':
            desired_status = 'CURRENT' if not first_incomplete_found else 'UPCOMING'
            if stop.status != desired_status:
                stop.status = desired_status
                updates.append('status')
            first_incomplete_found = True

        if updates:
            update_fields = list(set(updates + ['updated_at']))
            stop.save(update_fields=update_fields)

    return order


def compute_current_capacity(stops: List[BookingStop]) -> int:
    capacity = 0
    pickups_completed = set()
    dropoffs_completed = set()

    for stop in stops:
        if stop.stop_type == 'PICKUP' and stop.status == 'COMPLETED':
            pickups_completed.add(stop.booking_id)
            capacity += stop.passenger_count
        if stop.stop_type == 'DROPOFF' and stop.status == 'COMPLETED':
            dropoffs_completed.add(stop.booking_id)
            capacity = max(capacity - stop.passenger_count, 0)

    # Any bookings with pickup completed but dropoff pending contribute to current load
    active_booking_ids = pickups_completed - dropoffs_completed
    total = 0
    for stop in stops:
        if stop.booking_id in active_booking_ids and stop.stop_type == 'PICKUP':
            total += stop.passenger_count
    return total


def build_driver_itinerary(driver_user) -> Dict[str, object]:
    """Construct the itinerary payload for the given driver."""
    ordered_stops = plan_driver_stops(driver_user)

    if not ordered_stops:
        return {
            'status': 'success',
            'itinerary': {
                'totalEarnings': 0.0,
                'totalBookings': 0,
                'maxCapacity': 0,
                'currentCapacity': 0,
                'stops': [],
                'fullRoutePolyline': [],
                'fullRouteIsPrecise': False,
                'fullRouteSegments': [],
                'driverStartCoordinate': None,
            }
        }

    bookings = {stop.booking_id: stop.booking for stop in ordered_stops}
    unique_booking_ids = list(bookings.keys())

    driver_profile = Driver.objects.filter(user=driver_user).first()
    trike = Tricycle.objects.filter(driver=driver_profile).first() if driver_profile else None
    max_capacity = int(getattr(trike, 'max_capacity', 1) or 1) if trike else 1

    total_earnings = 0.0
    for booking in bookings.values():
        if booking.fare:
            total_earnings += float(booking.fare)

    current_capacity = compute_current_capacity(ordered_stops)

    current_stop_index = None
    stops_payload: List[Dict[str, object]] = []
    for idx, stop in enumerate(ordered_stops, start=1):
        payload = {
            'stopId': str(stop.stop_uid),
            'type': stop.stop_type,
            'status': stop.status,
            'passengerName': stop.booking.rider.get_full_name() or stop.booking.rider.username,
            'passengerCount': stop.passenger_count,
            'address': stop.address,
            'note': stop.note,
            'bookingId': stop.booking_id,
            'sequence': idx,
        }
        coord = _stop_coordinates(stop)
        if coord:
            payload['coordinates'] = [coord[0], coord[1]]
        if stop.status == 'CURRENT' and current_stop_index is None:
            current_stop_index = idx - 1
        stops_payload.append(payload)

    if current_stop_index is None:
        # All stops completed or no status marked as current; default to last
        current_stop_index = next((i for i, stop in enumerate(ordered_stops) if stop.status != 'COMPLETED'), len(ordered_stops) - 1)

    start_coord = _driver_start_location(driver_user)
    polyline, has_precise_route, segment_routes = _build_route_polyline(start_coord, ordered_stops)

    itinerary = {
        'totalEarnings': round(total_earnings, 2),
        'totalBookings': len(unique_booking_ids),
        'maxCapacity': max_capacity,
        'currentCapacity': current_capacity,
        'stops': stops_payload,
        'currentStopIndex': current_stop_index,
        'fullRoutePolyline': polyline,
        'fullRouteIsPrecise': has_precise_route,
        'fullRouteSegments': segment_routes,
        'driverStartCoordinate': [start_coord[0], start_coord[1]] if start_coord else None,
    }

    return {
        'status': 'success',
        'itinerary': itinerary,
    }

