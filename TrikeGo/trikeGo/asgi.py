"""
ASGI config for trikeGo project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trikeGo.settings')

try:
	# Channels-specific ASGI application setup
	from channels.routing import ProtocolTypeRouter, URLRouter
	from channels.auth import AuthMiddlewareStack
	import booking_app.routing as booking_routing
	import chat_app.routing as chat_routing

	application = ProtocolTypeRouter({
		"http": get_asgi_application(),
		"websocket": AuthMiddlewareStack(
			URLRouter(
				booking_routing.websocket_urlpatterns + chat_routing.websocket_urlpatterns
			)
		),
	})
except Exception:
	# Fallback to default ASGI application if Channels isn't configured or routing modules missing.
	application = get_asgi_application()
