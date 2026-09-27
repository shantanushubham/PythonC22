from .celery import app as celery_app

# This is a tuple of the celery app.
# This means that when we import * from config, we will get the celery app.
# This is needed because we are using Celery in a Django project.
# If we don't do this, we will get an error when we try to use the celery app.
# The error will be "AttributeError: module 'config' has no attribute 'celery_app'".
# This is because the celery app is not a module, it is an instance of the Celery class.

# By adding it to the __all__ tuple, we can import it like this:
# from config import celery_app
# celery_app.send_notification_sms.delay("1234567890", "Hello, world!")
# This will work because celery_app is a module that contains the celery app.
__all__ = ("celery_app",)