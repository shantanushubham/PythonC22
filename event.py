# Write code in python for event production in a flight booking system to send notification
# to the user when the flight is confirmed or cancelled.

import time
import random

queue = []

def book_flight(flight_id, user_id):
    print(f"Booking flight {flight_id} for user {user_id}")
    # Flight Booking Happening here...
    send_notification(user_id, f"Flight {flight_id} is confirmed")
    print(f"Flight {flight_id} is confirmed")

# Producing events
def send_notification(user_id, message):
    print(f"Sending notification to user {user_id}: {message}")
    queue.append(message) # This is the event producer
    print(f"Notification queued for user {user_id}: {message}")


# In a completely different process, the events are consumed

# Consumer function
def consume_events():
    while True:
        if len(queue) > 0:
            event = queue.pop(0) # Consuming the event from the queue
            print(f"Consuming event: {event}")
            send_email(event)

def send_email(event):
    print(f"Sending email to user: {event}")
    time.sleep(random.randint(1, 10))