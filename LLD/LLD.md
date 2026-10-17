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

## SOLID Principles
### 1. S - Single Responsibility Principle (SRP)

Refers to the SRP section.

### 2. O - Open/Closed Principle (OCP)

Definition: A class should be open for extension but closed for modification.

This means that we should be able to add new functionality to a class without modifying its existing code.

Bad Example:
```python
class NotificationService:

    def send(self, notification_type, message):
        if notification_type == "email":
            print(f"Sending email: {message}")
        elif notification_type == "sms":
            print(f"Sending SMS: {message}")
        elif notification_type == "push":
            print(f"Sending push notification: {message}")
        elif notification_type == "WhatsApp":
            print(f"Sending WhatsApp: {message}")
```

Right way is:
```python

from abc import ABC, abstractmethod

class NotificationService(ABC):

    @abstractmethod
    def send(self, message):
        pass

class EmailNotificationService(NotificationService):

    def send(self, message):
        print(f"Sending email: {message}")

class SMSNotificationService(NotificationService):

    def send(self, message):
        print(f"Sending SMS: {message}")

class PushNotificationService(NotificationService):

    def send(self, message):
        print(f"Sending push notification: {message}")


class WhatsAppNotificationService(NotificationService):

    def send(self, message):
        print(f"Sending WhatsApp: {message}")


class OrderService:

    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service

    def create_order(self, user, items):
        # Code to create an order
        self.notification_service.send(f"Order created for {user} with items {items}")


class OrderViewSet(ViewSet):

    def create(self, request):
        order_service = OrderService(
            notification_service=EmailNotificationService()
        )
        order_service.create_order(
            user=request.user,
            items=request.data["items"]
        )
        return Response(status=201)
```

### 3. L - Liskov Substitution Principle (LSP)

Defination: Objects of a child class should be usable wherever objects of the parent class are expected, without breaking the correctness of the program.

Bad Example:
```python
from abc import ABC, abstractmethod


class PaymentMethod(ABC):

    @abstractmethod
    def pay(self, amount):
        pass


class CreditCardPayment(PaymentMethod):

    def pay(self, amount):
        print(f"Paid ₹{amount} using credit card")


class FreePayment(PaymentMethod):

    def pay(self, amount):
        raise NotImplementedError(
            "Free payments cannot process transactions"
        )

def checkout(payment_method, amount):
    payment_method.pay(amount)
    print("Order completed successfully")

checkout(CreditCardPayment(), 100)
checkout(FreePayment(), 100)
```

Right way is: keep `PaymentMethod` only for types that can actually pay. Paid and free orders share a contract both can fulfill, so either one can be passed to `checkout`.

```python
from abc import ABC, abstractmethod


class PaymentMethod(ABC):

    @abstractmethod
    def pay(self, amount):
        pass


class CreditCardPayment(PaymentMethod):

    def pay(self, amount):
        print(f"Paid ₹{amount} using credit card")


class OrderProcessor(ABC):

    @abstractmethod
    def process(self, amount):
        pass


class PaidOrderProcessor(OrderProcessor):

    def __init__(self, payment_method: PaymentMethod):
        self.payment_method = payment_method

    def process(self, amount):
        self.payment_method.pay(amount)
        print("Paid order processed")


class FreeOrderProcessor(OrderProcessor):

    def process(self, amount):
        print("Free order processed")


def checkout(order_processor: OrderProcessor, amount):
    order_processor.process(amount)
    print("Order completed successfully")


checkout(PaidOrderProcessor(CreditCardPayment()), 100)
checkout(FreeOrderProcessor(), 0)
```

### 4. I - Interface Segregation Principle (ISP)

Definition: A client should not be forced to depend on interfaces it does not use.

Bad Example:
```python
from abc import ABC, abstractmethod

class Worker(ABC):

    @abstractmethod
    def work(self):
        pass

    @abstractmethod
    def eat(self):
        pass

    @abstractmethod
    def attend_meeting(self):
        pass

class HumanWorker(Worker):

    def work(self):
        print("Human is working")

    def eat(self):
        print("Human is eating")

    def attend_meeting(self):
        print("Human is attending a meeting")

class RobotWorker(Worker):

    def work(self):
        print("Robot is working")

    def eat(self):
        raise NotImplementedError("Robots cannot eat")

    def attend_meeting(self):
        print("Robot is attending a meeting")

class Activity:

    def __init__(self,name, worker):
        self.name = name
        self.worker = worker

    def perform(self):
        for _ in range(10):
            self.worker.work()
        
        self.worker.eat()

        self.worker.attend_meeting()

activity = Activity("Make Financial Report", HumanWorker())
activity.perform()

activity = Activity("Assemble Parts", RobotWorker())
activity.perform() # This will raise an error
```

Right way is:

```python
from abc import ABC, abstractmethod

class Workable(ABC):

    @abstractmethod
    def work(self):
        pass

class Eatable(ABC):

    @abstractmethod
    def eat(self):
        pass

class Attendable(ABC):

    @abstractmethod
    def attend_meeting(self):
        pass

class Flier(ABC):

    @abstractmethod
    def fly(self):
        pass

class HumanWorker(Workable, Eatable, Attendable):

    def work(self):
        print("Human is working")

    def eat(self):
        print("Human is eating")

    def attend_meeting(self):
        print("Human is attending a meeting")

class RobotWorker(Workable, Attendable):

    def work(self):
        print("Robot is working")

    def attend_meeting(self):
        print("Robot is attending a meeting")


class SuperHumanWorker(Workable, Eatable, Attendable, Flier):

    def fly(self):
        print("Super Human is flying")

    def work(self):
        print("Super Human is working")

    def eat(self):
        print("Super Human is eating")

    def attend_meeting(self):
        print("Super Human is attending a meeting")

class Activity:

    # worker has to be a child of Workable, Eatable, Attendable
    def __init__(self,name, worker):
        self.name = name
        self.worker = worker

    def perform(self):
        for _ in range(10):
            self.worker.work()
        
        self.worker.eat()

        self.worker.attend_meeting()

activity = Activity("Make Financial Report", HumanWorker())
activity.perform()

activity = Activity("Assemble Parts", RobotWorker()) # This will stop the code from running
activity.perform() 
```

### 5. D - Dependency Inversion Principle (DIP)

Defination:
1. High-level modules should not depend on low-level modules. Both should depend on abstractions.
2. Abstractions should not depend on details. Details should depend on abstractions.

In simpler terms, business logic should not be tightly coupled to specific technical implementations.

This principle is particularly useful in backend engineering.

Bad Example:
```python
class PostgreSQLOrderRepository:

    def save(self, order):
        print(f"Saving order {order} to PostgreSQL")


class OrderService:

    def __init__(self):
        self.repository = PostgreSQLOrderRepository()

    def place_order(self, order):
        self.repository.save(order)
        print("Order placed successfully")
```

Right way is:
```python

class OrderRepository(ABC):

    @abstractmethod
    def save(self, order):
        pass

class MySQLOrderRepository(OrderRepository):

    def save(self, order):
        print(f"Saving order {order} to MySQL")

class PostgreSQLOrderRepository(OrderRepository):

    def save(self, order):
        print(f"Saving order {order} to PostgreSQL")

class OrderService:

    def __init__(self, repository: OrderRepository):
        self.repository = repository

    def place_order(self, order):
        self.repository.save(order)
        print("Order placed successfully")


def checkout(order):
    order_service = OrderService(
        repository=MySQLOrderRepository()
    )
    order_service.place_order(order)
    print("Order placed successfully")
```