import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("ledger_app")

# Load task modules from all registered Django app configs.
# Read config settings for Celery from Django settings.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed Django apps.

# autodiscover_tasks: Discover and load all tasks defined in Django apps.
app.autodiscover_tasks()