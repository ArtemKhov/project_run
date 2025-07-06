import sys

from .base import *

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

INTERNAL_IPS = ["127.0.0.1"]


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

ENABLE_DEBUG_TOOLBAR = DEBUG and "test" not in sys.argv
if ENABLE_DEBUG_TOOLBAR:
    INSTALLED_APPS += [
        "debug_toolbar",
    ]
    MIDDLEWARE += [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    ]
    # Customize the config to support turbo and htmx boosting.
    DEBUG_TOOLBAR_CONFIG = {"ROOT_TAG_EXTRA_ATTRS": "data-turbo-permanent hx-preserve"}