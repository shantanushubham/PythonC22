# This file contains the tasks for the txn_app.
# Consume messages from the ledger_app and process them.

from celery import shared_task
import time
import random


# @app.task(autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
# def send_notification_sms(phone_number, message):
#     print(f"Sending SMS to {phone_number} with message: {message}")
#     # Waiting for 2 seconds to mimic Mailchimp or Twilio API call
#     time.sleep(2)
#     # Return a random success or failure
#     if random.random() < 0.2: # 20% chance of failure
#         raise Exception("SMS failed to send")
#     print(f"SMS sent to {phone_number} with message: {message}")


@shared_task(autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def send_notification_sms(phone_number: str, message: str) -> None:
    print(f"Sending SMS to {phone_number} with message: {message}")
    # Waiting for 2 seconds to mimic Mailchimp or Twilio API call
    time.sleep(2)
    # Return a random success or failure
    if random.random() < 0.2:  # 20% chance of failure
        raise Exception("SMS failed to send")
    print(f"SMS sent to {phone_number} with message: {message}")


@shared_task(autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def send_notification_email(email_address: str, message: str) -> None:
    subject = "Transaction Notification"
    print(
        f"Sending email to {email_address} with subject: {subject} and message: {message}"
    )
    # Waiting for 2 seconds to mimic Mailchimp or SendGrid API call
    time.sleep(2)
    # Return a random success or failure
    if random.random() < 0.2:  # 20% chance of failure
        raise Exception("Email failed to send")
    print(
        f"Email sent to {email_address} with subject: {subject} and message: {message}"
    )


# @app.task vs @shared_task
# @app.task is the old way of defining tasks.
# @shared_task is the new way of defining tasks.
# @shared_task is a decorator that is used to define a task that can be shared between multiple processes.
# @app.task is a decorator that is used to define a task that can only be used in the current process.
# @shared_task is better because it can be used in multiple processes.
# @app.task is deprecated and will be removed in the future.
# @shared_task is the preferred way to define tasks.
