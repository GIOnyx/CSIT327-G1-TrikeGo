"""
Django settings for trikeGo project.
"""

from dotenv import load_dotenv
load_dotenv()
import os
from supabase import create_client
from pathlib import Path
import dj_database_url
from django.urls import reverse_lazy

BASE_DIR = Path(__file__).resolve().parent.parent
\
SECRET_KEY = os.environ.get('SECRET_KEY')

# Set to 'False' by default, Render will set this env var to 'False'
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# In Render, set an env var 'ALLOWED_HOSTS' to your .onrender.com URL
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')
# Add 'localhost' and '127.0.0.1' if you still want local dev to work
if DEBUG:
    ALLOWED_HOSTS.extend(['localhost', '127.0.0.1'])

INSTALLED_APPS = [
    'channels',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework', 
    'user_app',
    'booking_app',
    'chat_app',
    'wallet_app',
    # New focused apps (feature split)
    'payments_app',
    'tracking_app',
    'ratings_app',
    'drivers_app',
    'notifications_app',
    'discount_codes_app',
    'driver_statistics_app.apps.DriverStatisticsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'trikeGo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'trikeGo.wsgi.application'

# ASGI app for Channels
ASGI_APPLICATION = 'trikeGo.asgi.application'

os.environ["PGOPTIONS"] = "-c inet_family=inet"

DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=int(os.environ.get('CONN_MAX_AGE', 0)),
        ssl_require=True  # ensures SSL when connecting to Supabase
    )
}


# Ensure it respects Supabase/Render's SSL requirements if any
if 'DATABASE_URL' in os.environ:
    DATABASES['default']['OPTIONS'] = {'sslmode': 'require'}
# Set CONN_MAX_AGE to 0 to prevent connection pool exhaustion on Supabase pooler (Session Mode)
# Connections will be closed after each request instead of being reused
DATABASES['default']['CONN_MAX_AGE'] = int(os.environ.get('CONN_MAX_AGE', 0))

# In DEBUG mode try a quick connectivity probe to the configured DATABASE_URL.
# If it fails (e.g. Supabase credentials/tenant issue), fall back to a local
# SQLite database so development can continue without the remote DB.
if DEBUG:
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        try:
            # Try a minimal connection using psycopg2. If psycopg2 isn't installed
            # or the connection fails, catch the exception and use SQLite.
            import psycopg2
            conn = psycopg2.connect(db_url, sslmode='require')
            conn.close()
        except Exception as _err:
            import logging
            logging.getLogger(__name__).warning(
                'Database connectivity check failed; falling back to SQLite for DEBUG. Error: %s', _err
            )
            DATABASES = {
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': str(BASE_DIR / 'db.sqlite3'),
                }
            }

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# Web push configuration
WEBPUSH_VAPID_PUBLIC_KEY = os.environ.get('WEBPUSH_VAPID_PUBLIC_KEY', '')
WEBPUSH_VAPID_PRIVATE_KEY = os.environ.get('WEBPUSH_VAPID_PRIVATE_KEY', '')
WEBPUSH_VAPID_CLAIM_EMAIL = os.environ.get('WEBPUSH_VAPID_CLAIM_EMAIL', '')

PUSH_NOTIFICATIONS_ENABLED = bool(WEBPUSH_VAPID_PUBLIC_KEY and WEBPUSH_VAPID_PRIVATE_KEY)

WEBPUSH_SETTINGS = {
    'VAPID_PUBLIC_KEY': WEBPUSH_VAPID_PUBLIC_KEY,
    'VAPID_PRIVATE_KEY': WEBPUSH_VAPID_PRIVATE_KEY,
    'VAPID_ADMIN_EMAIL': WEBPUSH_VAPID_CLAIM_EMAIL,
}

PUSH_NOTIFICATION_DEFAULT_ICON = os.environ.get(
    'PUSH_NOTIFICATION_DEFAULT_ICON',
    'https://trikego-static.s3.amazonaws.com/icons/trikego-bell.png',
)

PUSH_NOTIFICATION_SITE_NAME = os.environ.get('PUSH_NOTIFICATION_SITE_NAME', 'TrikeGo')

PUSH_NOTIFICATION_DEEPLINK_BASE = os.environ.get(
    'PUSH_NOTIFICATION_DEEPLINK_BASE',
    os.environ.get('SITE_URL', 'https://trikego.app'),
)

# OpenRouteService API Configuration
OPENROUTESERVICE_API_KEY = os.environ.get('OPENROUTESERVICE_API_KEY', 'eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImIyOThlMTFhZDk5MzRmOGVhY2NmOTAxMGQzM2ZlYWJhIiwiaCI6Im11cm11cjY0In0=')

# Caching: prefer Redis when a cache location is provided (e.g., in Render/production).
# Fallback to LocMemCache for local development.
if os.environ.get('DJANGO_CACHE_LOCATION') or os.environ.get('REDIS_URL'):
    CACHE_LOC = os.environ.get('DJANGO_CACHE_LOCATION') or os.environ.get('REDIS_URL')
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': CACHE_LOC,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                # Don't raise exceptions on cache failures in production; degrade gracefully
                'IGNORE_EXCEPTIONS': True,
            }
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': os.environ.get('DJANGO_CACHE_BACKEND', 'django.core.cache.backends.locmem.LocMemCache'),
            'LOCATION': os.environ.get('DJANGO_CACHE_LOCATION', 'unique-snowflake'),
        }
    }

# If Redis is available, prefer cached DB-backed sessions and configure Channels to use it.
REDIS_URL = os.environ.get('DJANGO_CACHE_LOCATION') or os.environ.get('REDIS_URL')
if REDIS_URL:
    # Use cached DB sessions so session data is fast and persistent across workers
    SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

    # Channels: configure Redis channel layer if Channels is installed
    try:
        CHANNEL_LAYERS = {
            'default': {
                'BACKEND': 'channels_redis.core.RedisChannelLayer',
                'CONFIG': {
                    'hosts': [REDIS_URL],
                },
            },
        }
    except Exception:
        # If channels_redis isn't available in the environment, do nothing.
        CHANNEL_LAYERS = {}

# Celery broker: prefer explicit env var, otherwise use Redis URL when available
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or REDIS_URL or 'redis://localhost:6379/0'

# In local development we default Celery to eager mode so push notifications fire
# immediately without a worker. In production set CELERY_TASK_ALWAYS_EAGER=false.
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', '').lower() == 'true'
if DEBUG and 'CELERY_TASK_ALWAYS_EAGER' not in os.environ:
    CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

AUTH_USER_MODEL = "user.CustomUser"
LOGIN_URL = 'user:landing'
LOGIN_REDIRECT_URL = reverse_lazy('user:logged_in_redirect')

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'  
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Use WhiteNoise compressed manifest storage in production for far-future caching and compression
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Basic logging configuration to ensure request access logs show in the console
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '[%(asctime)s] %(levelname)s %(name)s: %(message)s',
            'datefmt': '%d/%b/%Y %H:%M:%S'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.server': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'daphne': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
