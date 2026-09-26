from consumer import add

# We call the add task function and pass the arguments 22 and 33.
# We store the result in the result variable.
# delay() is a method that tells Celery to send the message to the queue.
# It returns a result object that contains the task ID.
result = add.delay(22, 33)

# We print the message and the task ID.
print("Message sent to the queue")
print(f"Task ID: {result.id}")