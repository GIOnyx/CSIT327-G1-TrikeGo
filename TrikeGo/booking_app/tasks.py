from celery import shared_task
from .services import RoutingService
from .models import Booking
from django.core.cache import cache
import os


@shared_task
def compute_and_cache_route(booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
        routing_service = RoutingService()

        # If no driver assigned, compute pickup->destination; otherwise compute driver->pickup
        if not booking.driver:
            start = (float(booking.pickup_longitude), float(booking.pickup_latitude))
            end = (float(booking.destination_longitude), float(booking.destination_latitude))
            route_info = routing_service.calculate_route(start, end)
        else:
            try:
                from booking_app.models import DriverLocation
                dl = DriverLocation.objects.filter(driver=booking.driver).first()
                if dl:
                    start = (float(dl.longitude), float(dl.latitude))
                    end = (float(booking.pickup_longitude), float(booking.pickup_latitude))
                    route_info = routing_service.calculate_route(start, end)
                else:
                    route_info = None
            except Exception:
                route_info = None

        if route_info:
            # Save snapshot for history and quick retrieval
            try:
                routing_service.save_route_snapshot(booking, route_info)
            except Exception:
                pass

            payload = {
                'status': 'success',
                'route_payload': {
                    'route_data': route_info.get('route_data'),
                    'distance': route_info.get('distance'),
                    'duration': route_info.get('duration')
                }
            }
            cache_key = f'route_info_{booking_id}_{booking.status}_{booking.driver_id or "none"}'
            cache.set(cache_key, payload, timeout=int(os.environ.get('ROUTE_CACHE_TTL', 15)))
            return True
    except Booking.DoesNotExist:
        return False
    except Exception:
        return False

    return False
