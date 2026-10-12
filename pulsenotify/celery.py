import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()  # reads .env so DJANGO_SETTINGS_MODULE and secrets are available to celery CLI
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pulsenotify.settings.local')

app = Celery('pulsenotify')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
