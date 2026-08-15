from datetime import datetime, timezone

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from tasks.services.json_util import read_json, write_json

USERS = "users.json"
TASKS = "tasks.json"

#  -------------
#  USERS
#  -------------


# List All Users
@api_view(["GET"])
def users(request: Request) -> Response:
    users = read_json(USERS)
    return Response(users)


# Get User by User Id
@api_view(["GET"])
def user_detail(request: Request, user_id: int) -> Response:
    users = read_json(USERS)

    user = None
    for u in users:
        if u["id"] == user_id:
            user = u
            break

    if user is None:
        return Response(
            {"error": f"User with id: {user_id} was not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(user)


# Get Tasks by User Id
@api_view(["GET"])
def user_tasks(request: Request, user_id: int) -> Response:
    if not _user_exists(user_id):
        return Response(
            {"error": f"User with id: {user_id} was not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    tasks = read_json(TASKS)
    filtered_tasks = []
    for t in tasks:
        if t["user_id"] == user_id:
            filtered_tasks.append(t)

    return Response(filtered_tasks)


# Create a new User.
@api_view(["POST"])
def create_user(request) -> Response:
    users: list = read_json(USERS)

    username = request.data.get("username")
    email = request.data.get("email")

    if not username or not email:
        return Response(
            {"error": "username and email are required fields"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user_name_set: set[str] = set()
    email_set: set[str] = set()

    max_id = 0
    for u in users:
        max_id = max(max_id, u["id"])
        user_name_set.add(u["username"])
        email_set.add(u["email"])

    if username in user_name_set:
        return Response(
            {"error": f"{username} is already taken."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if email in email_set:
        return Response(
            {"error": f"{email} is already taken."}, status=status.HTTP_400_BAD_REQUEST
        )

    new_id = max_id + 1

    created_user = {"id": new_id, "username": username, "email": email}

    users.append(created_user)

    write_json(USERS, users)

    return Response(created_user, status=status.HTTP_201_CREATED)


# Login using username only.
@api_view(["POST"])
def login(request) -> Response:
    username = request.data.get("username")

    if not username:
        return Response(
            {"error": "username is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    users = read_json(USERS)
    for u in users:
        if u["username"] == username:
            return Response(u)

    return Response(
        {"error": f"User '{username}' was not found."},
        status=status.HTTP_404_NOT_FOUND,
    )


#  -------------
#  TASKS
#  -------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _user_exists(user_id: int) -> bool:
    users = read_json(USERS)
    for u in users:
        if u["id"] == user_id:
            return True
    return False


# List All Tasks
@api_view(["GET"])
def tasks(request: Request) -> Response:
    tasks = read_json(TASKS)
    return Response(tasks)


# Get Task by Task Id
@api_view(["GET"])
def task_detail(request: Request, task_id: int) -> Response:
    tasks = read_json(TASKS)

    task = None
    for t in tasks:
        if t["id"] == task_id:
            task = t
            break

    if task is None:
        return Response(
            {"error": f"Task with id: {task_id} was not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(task)


# Create a new Task.
@api_view(["POST"])
def create_task(request) -> Response:
    tasks: list = read_json(TASKS)

    user_id = request.data.get("user_id")
    title = request.data.get("title")
    description = request.data.get("description", "")
    completed = request.data.get("completed", False)
    due_date = request.data.get("due_date")

    if not user_id or not title:
        return Response(
            {"error": "user_id and title are required fields"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not _user_exists(user_id):
        return Response(
            {"error": f"User with id: {user_id} was not found."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    max_id = 0
    for t in tasks:
        max_id = max(max_id, t["id"])

    now = _utc_now()
    created_task = {
        "id": max_id + 1,
        "user_id": user_id,
        "title": title,
        "description": description,
        "completed": completed,
        "created_at": now,
        "updated_at": now,
        "due_date": due_date,
    }

    tasks.append(created_task)

    write_json(TASKS, tasks)

    return Response(created_task, status=status.HTTP_201_CREATED)


# Update an existing Task.
@api_view(["PUT"])
def update_task(request, task_id: int) -> Response:
    tasks: list = read_json(TASKS)

    task = None
    for t in tasks:
        if t["id"] == task_id:
            task = t
            break

    if task is None:
        return Response(
            {"error": f"Task with id: {task_id} was not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    user_id = request.data.get("user_id", task["user_id"])
    title = request.data.get("title", task["title"])
    description = request.data.get("description", task["description"])
    completed = request.data.get("completed", task["completed"])
    due_date = request.data.get("due_date", task["due_date"])

    if not user_id or not title:
        return Response(
            {"error": "user_id and title are required fields"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not _user_exists(user_id):
        return Response(
            {"error": f"User with id: {user_id} was not found."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    task["user_id"] = user_id
    task["title"] = title
    task["description"] = description
    task["completed"] = completed
    task["due_date"] = due_date
    task["updated_at"] = _utc_now()

    write_json(TASKS, tasks)

    return Response(task)


# Delete an existing Task.
@api_view(["DELETE"])
def delete_task(request, task_id: int) -> Response:
    tasks: list = read_json(TASKS)

    task = None
    for t in tasks:
        if t["id"] == task_id:
            task = t
            break

    if task is None:
        return Response(
            {"error": f"Task with id: {task_id} was not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    tasks.remove(task)
    write_json(TASKS, tasks)

    return Response(
        {"message": f"Task with id: {task_id} was deleted."},
        status=status.HTTP_200_OK,
    )

