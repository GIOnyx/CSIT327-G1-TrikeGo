"""
URL configuration for trikeGo project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# In trikeGo/trikeGo/urls.py

# In trikeGo/trikeGo/urls.py

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
import os
from django.views.static import serve

urlpatterns = [
    # Core Django URLs
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),

    # Your App URLs
    path('booking/', include('booking.urls')),  # Handles all URLs starting with /booking/
    path('', include('user.urls')),  # Handles user-related URLs like login, dashboards, etc.
    # Chat API and views
    path('chat/', include('chat.urls')),
    path('wallet/', include('wallet.urls')),
]

# Development helper: serve static files directly from the `static/` dirs when
# DEBUG=True or when the environment variable SERVE_STATIC_ALWAYS=true. This
# avoids running `collectstatic` for quick local testing. Do NOT enable this
# in production.
if settings.DEBUG or os.environ.get('SERVE_STATIC_ALWAYS', '').lower() == 'true':
    # Prefer STATICFILES_DIRS if available, else fallback to STATIC_ROOT
    docroot = settings.STATICFILES_DIRS[0] if getattr(settings, 'STATICFILES_DIRS', None) else settings.STATIC_ROOT
    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': docroot}),
    ]