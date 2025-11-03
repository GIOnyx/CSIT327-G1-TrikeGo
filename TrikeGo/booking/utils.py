from typing import Dict, List, Optional, Tuple

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from datetime import timedelta
import random
import math


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two points in kilometers.

    Parameters are latitude and longitude in decimal degrees: (lat1, lon1, lat2, lon2).
    Returns distance in kilometers as a float.
    """
    # Earth radius in kilometers
    radius = 6371.0
    ph1 = math.radians(lat1)
    ph2 = math.radians(lat2)
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
    cache: Dict[Tuple[float, float, float, float], Tuple[Optional[List[List[float]]], bool, Dict[str, float]]],
) -> Tuple[Optional[List[List[float]]], bool, Dict[str, float]]:
    """Return route points for a segment and capture distance/ETA metadata."""

    def _fallback_meta() -> Dict[str, float]:
        distance_km = float(calculate_distance(start[0], start[1], end[0], end[1]))
        # Assume 20 km/h average speed for fallback ETA estimates
        duration_sec = 0
        if distance_km > 0:
            duration_sec = int(max(60, (distance_km / 20.0) * 3600))
        return {'distanceKm': distance_km, 'durationSec': float(duration_sec)}

    if routing_service is None:
        meta = _fallback_meta()
        return None, False, meta

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
        meta = _fallback_meta()
        cache[key] = (None, False, meta)
        return cache[key]

    if not route_info:
        meta = _fallback_meta()
        cache[key] = (None, False, meta)
        return cache[key]

    if route_info.get('too_close'):
        segment = [[float(start[0]), float(start[1])], [float(end[0]), float(end[1])]]
        meta = {
            'distanceKm': float(route_info.get('distance') or 0.0),
            'durationSec': float(route_info.get('duration') or 0.0)
        }
        cache[key] = (segment, False, meta)
        return cache[key]

    route_data = route_info.get('route_data') or {}
    features = route_data.get('features') or []
    if not features:
        meta = _fallback_meta()
        cache[key] = (None, False, meta)
        return cache[key]

    geometry = features[0].get('geometry') or {}
    coordinates = geometry.get('coordinates') or []
    if len(coordinates) < 2:
        meta = _fallback_meta()
        cache[key] = (None, False, meta)
        return cache[key]

    segment = [[float(coord[1]), float(coord[0])] for coord in coordinates]
    meta = {
        'distanceKm': float(route_info.get('distance') or 0.0),
        'durationSec': float(route_info.get('duration') or 0.0)
    }
    cache[key] = (segment, True, meta)
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

    segment_cache: Dict[Tuple[float, float, float, float], Tuple[Optional[List[List[float]]], bool, Dict[str, float]]] = {}

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

        segment, precise, meta = _segment_route(previous_coord, next_coord, routing_service, segment_cache)
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
            meta = meta or {'distanceKm': 0.0, 'durationSec': 0.0}

        if segment_points:
            segments.append({
                'type': stop.stop_type,
                'points': segment_points,
                'precise': precise,
                'bookingId': stop.booking_id,
                'stopId': str(stop.stop_uid),
                'distanceKm': float(meta.get('distanceKm', 0.0)),
                'durationSec': float(meta.get('durationSec', 0.0)),
            })

        previous_coord = next_coord

    if not polyline and start_coord:
        _append_unique_point(polyline, start_coord[0], start_coord[1])

    return polyline, used_precise_route, segments


def plan_driver_stops(driver_user) -> List[BookingStop]:
    """
    Generate an optimized ordered list of stops for the driver's active bookings.
    Uses a greedy algorithm that considers complete trips (pickup + dropoff together)
    to minimize total travel distance.
    """
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

    # Track which pickups have been completed
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

    # Group pending stops by booking
    pending_by_booking = {}
    for stop in pending:
        if stop.booking_id not in pending_by_booking:
            pending_by_booking[stop.booking_id] = {'pickup': None, 'dropoff': None}
        if stop.stop_type == 'PICKUP':
            pending_by_booking[stop.booking_id]['pickup'] = stop
        else:
            pending_by_booking[stop.booking_id]['dropoff'] = stop

    # Separate bookings that still need pickup vs those already picked up
    needs_pickup = []
    needs_dropoff_only = []
    
    for booking_id, pair in pending_by_booking.items():
        if booking_id in completed_pickups:
            # Already picked up, just need dropoff
            if pair['dropoff']:
                needs_dropoff_only.append(pair['dropoff'])
        else:
            # Still needs pickup
            if pair['pickup']:
                needs_pickup.append(pair)

    # Optimize route using greedy nearest-neighbor with trip completion preference
    pending_work = needs_pickup.copy()
    pending_dropoffs = needs_dropoff_only.copy()

    while pending_work or pending_dropoffs:
        candidates = []
        
        # For bookings we haven't picked up yet, consider the full trip cost
        for pair in pending_work:
            pickup = pair['pickup']
            dropoff = pair['dropoff']
            if pickup is None:
                continue
                
            pickup_coord = _stop_coordinates(pickup)
            if pickup_coord is None:
                continue
            
            # Calculate: current -> pickup -> dropoff
            if current_location:
                dist_to_pickup = calculate_distance(
                    current_location[0], current_location[1],
                    pickup_coord[0], pickup_coord[1]
                )
            else:
                dist_to_pickup = 0
            
            # If we have a dropoff, include its distance too
            if dropoff:
                dropoff_coord = _stop_coordinates(dropoff)
                if dropoff_coord:
                    dist_pickup_to_dropoff = calculate_distance(
                        pickup_coord[0], pickup_coord[1],
                        dropoff_coord[0], dropoff_coord[1]
                    )
                    # Prefer completing full trips
                    total_cost = dist_to_pickup + (dist_pickup_to_dropoff * 0.5)
                else:
                    total_cost = dist_to_pickup
            else:
                total_cost = dist_to_pickup
            
            candidates.append(('pickup_pair', pair, total_cost, pickup_coord))
        
        # Also consider dropoffs for already-picked-up passengers
        for dropoff in pending_dropoffs:
            dropoff_coord = _stop_coordinates(dropoff)
            if dropoff_coord is None:
                continue
            
            if current_location:
                dist = calculate_distance(
                    current_location[0], current_location[1],
                    dropoff_coord[0], dropoff_coord[1]
                )
            else:
                dist = 0
            
            # Prioritize dropoffs (passengers already in vehicle)
            candidates.append(('dropoff', dropoff, dist * 0.8, dropoff_coord))
        
        if not candidates:
            # No valid candidates with coordinates, just add remaining stops
            for pair in pending_work:
                if pair['pickup']:
                    order.append(pair['pickup'])
                    if pair['dropoff']:
                        order.append(pair['dropoff'])
            for dropoff in pending_dropoffs:
                order.append(dropoff)
            break
        
        # Pick the best candidate (lowest cost)
        candidates.sort(key=lambda x: x[2])
        best_type, best_item, best_cost, best_coord = candidates[0]
        
        if best_type == 'pickup_pair':
            # Add pickup, then immediately add its dropoff if available
            pair = best_item
            order.append(pair['pickup'])
            completed_pickups.add(pair['pickup'].booking_id)
            
            if pair['dropoff']:
                order.append(pair['dropoff'])
                pending_dropoffs = [d for d in pending_dropoffs if d.id != pair['dropoff'].id]
            
            pending_work.remove(pair)
            current_location = _stop_coordinates(pair['dropoff']) if pair['dropoff'] else _stop_coordinates(pair['pickup'])
        else:
            # Add dropoff
            dropoff = best_item
            order.append(dropoff)
            pending_dropoffs.remove(dropoff)
            current_location = best_coord

    # Update sequences and statuses
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
    """
    Compute the current passenger load in the vehicle.
    This is the number of passengers currently in the tricycle after all COMPLETED stops.
    """
    capacity = 0
    
    for stop in stops:
        if stop.status == 'COMPLETED':
            if stop.stop_type == 'PICKUP':
                # Passenger got in
                capacity += stop.passenger_count
            elif stop.stop_type == 'DROPOFF':
                # Passenger got out
                capacity = max(capacity - stop.passenger_count, 0)
    
    return capacity


def _safe_decimal(value) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _format_currency(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    try:
        quantized = value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return f"₱{quantized}"
    except (InvalidOperation, TypeError, ValueError):
        return None


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
    unique_booking_ids = []
    for stop in ordered_stops:
        if stop.booking_id not in unique_booking_ids:
            unique_booking_ids.append(stop.booking_id)

    driver_profile = Driver.objects.filter(user=driver_user).first()
    trike = Tricycle.objects.filter(driver=driver_profile).first() if driver_profile else None
    max_capacity = int(getattr(trike, 'max_capacity', 1) or 1) if trike else 1

    total_earnings = Decimal('0.00')
    booking_fares: Dict[int, Optional[Decimal]] = {}
    booking_passengers: Dict[int, int] = {}
    total_passengers = 0  # Total passengers across all bookings

    for booking_id, booking in bookings.items():
        fare_decimal = _safe_decimal(getattr(booking, 'fare', None))
        booking_fares[booking_id] = fare_decimal
        if fare_decimal is not None:
            total_earnings += fare_decimal

        passenger_total = 0
        for stop in ordered_stops:
            if stop.booking_id == booking_id and stop.stop_type == 'PICKUP':
                passenger_total += int(getattr(stop, 'passenger_count', 1) or 1)
        passenger_count = passenger_total or int(getattr(booking, 'passengers', 1) or 1)
        booking_passengers[booking_id] = passenger_count
        total_passengers += passenger_count

    current_capacity = compute_current_capacity(ordered_stops)

    current_stop_index = None
    stops_payload: List[Dict[str, object]] = []
    first_stop_seen: Dict[int, bool] = {}
    for idx, stop in enumerate(ordered_stops, start=1):
        is_first_for_booking = not first_stop_seen.get(stop.booking_id, False)
        if is_first_for_booking:
            first_stop_seen[stop.booking_id] = True

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
            'bookingStatus': stop.booking.status,
            'isFirstForBooking': is_first_for_booking,
        }
        coord = _stop_coordinates(stop)
        if coord:
            payload['coordinates'] = [coord[0], coord[1]]
        fare_decimal = booking_fares.get(stop.booking_id)
        if fare_decimal is not None:
            try:
                quantized = fare_decimal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                payload['bookingFare'] = float(quantized)
                fare_display = _format_currency(quantized)
            except (InvalidOperation, TypeError, ValueError):
                payload['bookingFare'] = float(round(float(fare_decimal), 2))
                fare_display = _format_currency(fare_decimal)
            if fare_display:
                payload['bookingFareDisplay'] = fare_display
        if stop.status == 'CURRENT' and current_stop_index is None:
            current_stop_index = idx - 1
        stops_payload.append(payload)

    if current_stop_index is None:
        # All stops completed or no status marked as current; default to last
        current_stop_index = next((i for i, stop in enumerate(ordered_stops) if stop.status != 'COMPLETED'), len(ordered_stops) - 1)

    start_coord = _driver_start_location(driver_user)
    polyline, has_precise_route, segment_routes = _build_route_polyline(start_coord, ordered_stops)

    stop_status_lookup = {stop['stopId']: stop.get('status', 'UPCOMING') for stop in stops_payload}
    total_distance_km = 0.0
    total_duration_sec = 0.0
    completed_distance_km = 0.0
    completed_duration_sec = 0.0
    cumulative_distance_km = 0.0
    cumulative_duration_sec = 0.0
    booking_remaining_distance: Dict[int, float] = {}
    booking_remaining_duration: Dict[int, float] = {}

    for segment in segment_routes:
        distance_km = float(segment.get('distanceKm') or 0.0)
        duration_sec = float(segment.get('durationSec') or 0.0)

        total_distance_km += distance_km
        total_duration_sec += duration_sec

        stop_id = str(segment.get('stopId')) if segment.get('stopId') is not None else None
        if stop_id and stop_status_lookup.get(stop_id) == 'COMPLETED':
            completed_distance_km += distance_km
            completed_duration_sec += duration_sec

        cumulative_distance_km += distance_km
        cumulative_duration_sec += duration_sec

        if segment.get('type') == 'DROPOFF' and segment.get('bookingId') is not None:
            booking_id = int(segment['bookingId'])
            remaining_distance = max(0.0, cumulative_distance_km - completed_distance_km)
            remaining_duration = max(0.0, cumulative_duration_sec - completed_duration_sec)
            booking_remaining_distance[booking_id] = remaining_distance
            booking_remaining_duration[booking_id] = remaining_duration

    remaining_distance_km = max(0.0, total_distance_km - completed_distance_km)
    remaining_duration_sec = max(0.0, total_duration_sec - completed_duration_sec)

    total_distance_km = float(round(max(0.0, total_distance_km), 3))
    remaining_distance_km = float(round(remaining_distance_km, 3))
    total_duration_sec = float(max(0.0, total_duration_sec))
    remaining_duration_sec = float(max(0.0, remaining_duration_sec))

    booking_summaries: List[Dict[str, object]] = []
    for booking_id in unique_booking_ids:
        booking = bookings.get(booking_id)
        fare_decimal = booking_fares.get(booking_id)
        try:
            quantized = fare_decimal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if fare_decimal is not None else None
        except (InvalidOperation, TypeError, ValueError):
            quantized = None
        fare_display = _format_currency(quantized or fare_decimal)

        remaining_distance = booking_remaining_distance.get(booking_id)
        remaining_duration = booking_remaining_duration.get(booking_id)

        if remaining_distance is None and getattr(booking, 'estimated_distance', None) is not None:
            try:
                remaining_distance = float(booking.estimated_distance)
            except (TypeError, ValueError, InvalidOperation):
                remaining_distance = None

        if remaining_duration is None and getattr(booking, 'estimated_duration', None) is not None:
            try:
                remaining_duration = float(booking.estimated_duration) * 60.0
            except (TypeError, ValueError):
                remaining_duration = None

        remaining_minutes = None
        remaining_duration_value = None
        if remaining_duration is not None:
            remaining_duration_value = float(max(0.0, remaining_duration))
            remaining_minutes = int(max(0, math.ceil(remaining_duration_value / 60.0)))

        remaining_distance_value = None
        if remaining_distance is not None:
            remaining_distance_value = float(round(max(0.0, remaining_distance), 3))

        distance_display = None
        if remaining_distance_value is not None:
            distance_display = f"{remaining_distance_value:.1f} km"

        duration_display = None
        if remaining_minutes is not None:
            duration_display = f"ETA ~{remaining_minutes} min"

        booking_summaries.append({
            'bookingId': booking_id,
            'status': booking.status,
            'riderName': booking.rider.get_full_name() or booking.rider.username,
            'fare': float(quantized) if quantized is not None else (float(fare_decimal) if fare_decimal is not None else None),
            'fareDisplay': fare_display,
            'passengers': booking_passengers.get(booking_id, int(getattr(booking, 'passengers', 1) or 1)),
            'remainingDistanceKm': remaining_distance_value,
            'remainingDistanceDisplay': distance_display,
            'remainingDurationSec': remaining_duration_value,
            'remainingDurationMinutes': remaining_minutes,
            'remainingDurationDisplay': duration_display,
        })

    itinerary = {
        'totalEarnings': float(total_earnings.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)) if total_earnings is not None else 0.0,
        'totalBookings': len(unique_booking_ids),
        'maxCapacity': max_capacity,
        'currentCapacity': current_capacity,
        'totalPassengers': total_passengers,  # Total passengers across all accepted bookings
        'stops': stops_payload,
        'currentStopIndex': current_stop_index,
        'fullRoutePolyline': polyline,
        'fullRouteIsPrecise': has_precise_route,
        'fullRouteSegments': segment_routes,
        'driverStartCoordinate': [start_coord[0], start_coord[1]] if start_coord else None,
        'bookingSummaries': booking_summaries,
        'totalDistanceKm': total_distance_km,
        'totalDurationSec': total_duration_sec,
        'remainingDistanceKm': remaining_distance_km,
        'remainingDurationSec': remaining_duration_sec,
    }

    return {
        'status': 'success',
        'itinerary': itinerary,
    }


# ============================================================================
# Payment PIN Verification Utilities
# ============================================================================

def generate_payment_pin() -> str:
    """
    Generate a random 4-digit PIN for payment verification.
    Returns the PIN as a string (e.g., "1234").
    """
    return f"{random.randint(0, 9999):04d}"


def hash_payment_pin(pin: str) -> str:
    """
    Hash the payment PIN using Django's password hasher.
    
    Args:
        pin: 4-digit PIN as a string
        
    Returns:
        Hashed PIN string
    """
    return make_password(pin)


def verify_payment_pin(pin: str, pin_hash: str) -> bool:
    """
    Verify a payment PIN against its hash.
    
    Args:
        pin: The PIN to verify (4-digit string)
        pin_hash: The stored hashed PIN
        
    Returns:
        True if PIN matches, False otherwise
    """
    return check_password(pin, pin_hash)


def get_pin_expiry_time(minutes: int = 5) -> timezone.datetime:
    """
    Get the expiry time for a payment PIN.
    
    Args:
        minutes: Number of minutes until expiry (default 5)
        
    Returns:
        DateTime object representing expiry time
    """
    return timezone.now() + timedelta(minutes=minutes)


