from app import app
import random


# We use the @app.task decorator to tell Celery that this function is a task.
# We name the task function add.
# We define the task function as a function that takes two arguments, a and b.
# We return the sum of a and b.
@app.task(
    # Resilience
    autoretry_for=(ZeroDivisionError,),  # This is the tuple of exceptions to retry on
    max_retries=3,  # This is the maximum number of retries
    retry_backoff=True,  # this is the backoff strategy
    # Backoff strategy is the time to wait before retrying the task.
    # backoff = true means the time to wait before retrying the task will be exponential.
    # The first retry happens after 1 second, the second retry happens after 2 seconds, the third retry happens after 4 seconds.
    # The total time to retry is 1 + 2 + 4 = 7 seconds.
)  # naming the task function
def add(a, b):
    try:  # this is the task function
        print(f"Adding {a} and {b}")
        sum = a + b
        # Create a 25% failure rate
        if random.random() < 0.25:
            raise ZeroDivisionError("Failed to add")
        return sum
    except Exception as e:
        print(f"Error: {e}")
        return None


# We run the task function by calling the task function.


@app.task(
    max_retries=3,
    bind=True,  # this is the bind parameter, which is used to pass the task instance to the task function.
)
def multiply(self, a, b):
    try:
        print(f"Multiplying {a} and {b}")
        if random.random() < 0.25:
            raise ZeroDivisionError("Failed to multiply")
        return a * b
    except ZeroDivisionError:
        print("Retrying task...")
        self.retry(countdown=2)


@app.task
def subtract(a, b):
    print(f"Subtracting {a} and {b}")
    return a - b


@app.task
def divide(a, b):
    print(f"Dividing {a} and {b}")
    return a / b
