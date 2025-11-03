"""Thin tracking API wrappers that delegate to the existing booking implementations.
This preserves DB models and logic while moving the public API surface to a focused app.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

# Import the logic from booking.api_views to avoid duplicating complex logic
from booking import api_views as booking_api


# Expose the same endpoints via tracking app to start the refactor
update_driver_location = booking_api.update_driver_location
get_driver_location = booking_api.get_driver_location
get_current_route = booking_api.get_current_route
manual_reroute = booking_api.manual_reroute
driver_itinerary = booking_api.driver_itinerary
complete_itinerary_stop = booking_api.complete_itinerary_stop
