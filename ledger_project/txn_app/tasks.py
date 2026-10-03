# This file contains the tasks for the txn_app.
# Consume messages from the ledger_app and process them.

from celery import shared_task
import time
import random
import logging
import asyncio

logger = logging.getLogger(__name__)


# ****** Async Tasks Start ******


async def _send_sms(phone_number: str, message: str) -> None:
    print(f"Sending SMS to {phone_number} with message: {message}")
    # Waiting for 2 seconds to mimic Mailchimp or Twilio API call
    await asyncio.sleep(2)
    # Return a random success or failure
    if random.random() < 0.2:  # 20% chance of failure
        raise Exception("SMS failed to send")
    print(f"SMS sent to {phone_number} with message: {message}")


async def _send_email(email_address: str, message: str) -> None:
    subject = "Transaction Notification"
    print(
        f"Sending email to {email_address} with subject: {subject} and message: {message}"
    )
    # Waiting for 2 seconds to mimic Mailchimp or SendGrid API call
    await asyncio.sleep(2)
    # Return a random success or failure
    if random.random() < 0.2:  # 20% chance of failure
        raise Exception("Email failed to send")
    print(
        f"Email sent to {email_address} with subject: {subject} and message: {message}"
    )


# ****** Async Tasks End ******

# ****** Celery Tasks Start ******


@shared_task(autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def send_notification_sms(phone_number: str, message: str) -> None:
    # Calling the async task inside the celery task.
    asyncio.run(_send_sms(phone_number, message))


@shared_task(autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def send_notification_email(email_address: str, message: str) -> None:
    asyncio.run(_send_email(email_address, message))


# ****** Celery Tasks End ******


async def _send_both(phone_number: str, email_address: str, message: str):
    # This is a async function that will send both the SMS and the email concurrently.
    return await asyncio.gather(
        _send_sms(phone_number, message), _send_email(email_address, message)
    )


@shared_task
def send_transaction_notification(
    phone_number: str, email_address: str, message: str
) -> None:
    # This is a celery task that will send both the SMS and the email concurrently.
    # asyncio.run is used to run the async function in the main thread.
    sms_result, email_result = asyncio.run(
        _send_both(phone_number, email_address, message)
    )
    # If the SMS fails, send the SMS again.
    if isinstance(sms_result, Exception):
        logger.warning("op=send_transaction_notifications sms failed: %s", sms_result)
        send_notification_sms.delay(phone_number, message)
    # If the email fails, send the email again.
    if isinstance(email_result, Exception):
        logger.warning(
            "op=send_transaction_notifications email failed: %s", email_result
        )
        send_notification_email.delay(email_address, message)


# @app.task vs @shared_task
# @app.task is the old way of defining tasks.
# @shared_task is the new way of defining tasks.
# @shared_task is a decorator that is used to define a task that can be shared between multiple processes.
# @app.task is a decorator that is used to define a task that can only be used in the current process.
# @shared_task is better because it can be used in multiple processes.
# @app.task is deprecated and will be removed in the future.
# @shared_task is the preferred way to define tasks.
