"""Production settings (DEBUG off). Switch with DJANGO_SETTINGS_MODULE=pulsenotify.settings.production"""
import os

from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = [h for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if h]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['PROD_POSTGRES_DB'],
        'USER': os.environ['PROD_POSTGRES_USER'],
        'PASSWORD': os.environ['PROD_POSTGRES_PASSWORD'],
        'HOST': os.environ['PROD_POSTGRES_HOST'],
        'PORT': os.environ.get('PROD_POSTGRES_PORT', '5432'),
    }
}

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
