# What is LLD?

Suppose we’re building a Task Management application like Todoist. A user should be able to create tasks, update them, delete them, and retrieve them. How would you design it? 

```python
def create_task():
    pass

def update_task():
    pass

def delete_task():
    pass

def get_task():
    pass
```

In short, <b>Low-Level Design is the process of translating software requirements into concrete implementation structures,</b> including classes, objects, methods, interfaces, and their interactions.

High-Level Design focuses on the system’s overall architecture. Low-Level Design focuses on how individual components are structured and collaborate.

For example, in the Task Management application.

| HLD | LLD |
| --- | --- |
| Use Django for the backend | Defining classes inside the Django app for handling the logic |
| Use PostgreSQL | Design the Task model and its fields |
| Expose a REST API | Define request validation and response behavior |
| Deploy using multiple services | Decide which class owns each responsibility |

## Identify the classes and their responsibilities

1. Model - Represents the data and its relationships
2. Repository - Handles data persistence and retrieval (We didn't create this)
3. Service - Contains the business logic (Our Views and Serializers contain this)
4. Controller/Resource - Handles the request and response (Our Views & urls.py contain this)
5. Middleware - Handles checks needed for the request
**** Non-Mandatory *****
6. Utils - Contains helper functions 
7. Serializer - Handles the serialization and deserialization of the data (Our Serializers contain this)
8. ErrorHandler - Handles the errors and returns the appropriate response 
9. Mapper - Handles the mapping of the data between two different classes [Usually done in Java/C#]

## DRY and KISS Principles

#### DRY (Don't Repeat Yourself) - Avoid duplicating code.

```python
class TaskService:

    def validate_title(self, title):
        if not title or not title.strip():
            raise ValueError("Title is required")
        return title.strip()

    def create_task(self, title):
        title = self.validate_title(title)
        print(f"Creating task: {title}")

    def update_task(self, task_id, title):
        title = self.validate_title(title)
        print(f"Updating task {task_id}: {title}")

    def duplicate_task(self, task_id, title):
        title = self.validate_title(title)
        print(f"Duplicating task {task_id}: {title}")
```
#### KISS (Keep It Simple, Stupid) - Avoid complex code.

```python
class TaskRepository:

    def __init__(self):
        self.tasks = {}

    def save(self, task):
        self.tasks[task.id] = task

    def get_by_id(self, task_id):
        return self.tasks.get(task_id)


repository = TaskRepository()
repository.save(Task(id=1, title="Buy groceries"))
task = repository.get_by_id(1)
```

Example of Complex Code:
```python
class TaskRepositoryInterface(ABC):

    @abstractmethod
    def save(self, task: Task) -> None:
        pass

    @abstractmethod
    def get_by_id(self, task_id: int) -> Optional[Task]:
        pass

class TaskRepository(TaskRepositoryInterface):

    def __init__(
        self,
        validator
    ):
        self._tasks: Dict[int, Task] = {}
        self._validator = validator

    def save(self, task: Task) -> None:
        if self._validator.validate(task):
            self._tasks[task.id] = task
            
    def get_by_id(self, task_id: int) -> Optional[Task]:
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"Task with ID {task_id} not found")
        return task

class TaskRepositoryFactory:

    @staticmethod
    def create_repository() -> TaskRepositoryInterface:
        validator = TaskValidator()
        return TaskRepository(
            validator=validator,
        )


repository = TaskRepositoryFactory.create_repository()
repository.save(Task(id=1, title="Buy groceries"))
task = repository.get_by_id(1)
```



## Single Responsibility Principle (SRP):
The SRP is one of the SOLID Principles.

Definition: A class should have only one responsibility and should only have one reason to change.

This doesn't mean that a class should have only one method. It means that its methods should contribute to one cohesive responsibility.

Example:
```python
class TaskManager:

    def create_task(self, title, user):
        # Validate task title
        if not title or len(title) > 100:
            raise ValueError("Invalid task title")

        # Save task to database
        task = {
            "title": title,
            "user": user,
            "status": "PENDING"
        }

        # Imagine saving to the database here

        # Send email notification
        print(f"Email sent to {user}")

        # Log the operation
        print(f"Task created: {title}")

        return task
```

Corrct way is:
```python
class TaskValidator:

    def validate_title(self, title):
        if not title or len(title) > 100:
            raise ValueError("Invalid task title")


class TaskRepository:

    def save(self, task):
        # Save task to the database
        print(f"Saving task: {task['title']}")
        return task


class NotificationService:

    def send_task_created_notification(self, user, task):
        print(f"Email sent to {user} for task {task['title']}")


class AuditLogger:

    def log_task_created(self, task):
        print(f"Task created: {task['title']}")


class TaskService:

    def __init__(
        self,
        validator,
        repository,
        notification_service,
        audit_logger
    ):
        self.validator = validator
        self.repository = repository
        self.audit_logger = audit_logger
        self.notification_service = notification_service

    def create_task(self, title, user):
        self.validator.validate_title(title)
        task = {
            "title": title,
            "user": user,
            "status": "PENDING"
        }
        task = self.repository.save(task)

        self.notification_service.send_task_created_notification(
            user, task
        )

        self.audit_logger.log_task_created(task)

        return task
```

## Separation of Concerns (SoC):

Defination: SoC is a design principle taht encourages us to organize software so that different aspects of the syste, are handled independently.

Bad Example:
```python
def create_order(request):
    # Read HTTP request
    items = request.data["items"]

    # Validate items
    if not items:
        return Response(
            {"error": "No items provided"},
            status=400
        )

    # Calculate price
    total = sum(item["price"] * item["quantity"] for item in items)

    # Apply business rule
    if total < 100:
        return Response(
            {"error": "Minimum order is 100"},
            status=400
        )

    # Save to database
    order = Order.objects.create(total=total)

    # Process payment
    payment_gateway.charge(request.user, total)

    # Send confirmation
    send_email(request.user.email, "Order placed")

    # Return HTTP response
    return Response(
        {"order_id": order.id},
        status=201
    )
```

Right way is:
<b> views.py - Handle the request and response </b>

```python
def create_order(request):
    serializer = OrderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    order = OrderService.create_order(
        user=request.user,
        items=serializer.validated_data["items"]
    )
    return Response(
        {"order_id": order.id},
        status=201
    )

class OrderService:

    @staticmethod
    def create_order(user, items):
        total = PricingService.calculate_total(items)

        if total < 100:
            raise ValueError("Minimum order is 100")

        order = Order.objects.create(
            user=user,
            total=total
        )
        PaymentService.process_payment(user, order)
        NotificationService.send_order_confirmation(user, order)
        return order

class PricingService:

    @staticmethod
    def calculate_total(items):
        return sum(
            item["price"] * item["quantity"]
            for item in items
        )

class PaymentService:

    @staticmethod
    def process_payment(user, order):
        # Integrate with payment gateway
        pass

class NotificationService:

    @staticmethod
    def send_order_confirmation(user, order):
        # Send email notification
        pass

    @staticmethod
    def send_payment_failed_notification(user, order):
        # Send email notification
        pass
``` 

