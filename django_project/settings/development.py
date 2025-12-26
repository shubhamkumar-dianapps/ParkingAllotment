# In django_project/settings/development.py

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".ngrok-free.app"]

# Development-specific email backend
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
