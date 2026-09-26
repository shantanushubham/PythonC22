from celery import Celery

app = Celery(
    "demo",
    broker="redis://localhost:6379/0", # I am using Redis to manage my RAM
)