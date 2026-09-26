from app import app

# We use the @app.task decorator to tell Celery that this function is a task.
# We name the task function add.
# We define the task function as a function that takes two arguments, a and b.
# We return the sum of a and b.
@app.task # naming the task function
def add(a, b): # this is the task function
    print(f"Adding {a} and {b}")
    return a + b

# We run the task function by calling the task function.