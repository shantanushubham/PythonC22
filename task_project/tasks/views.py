from datetime import datetime, timezone

from rest_framework import status
from rest_framework.decorators import action, api_view
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ViewSet

from tasks.models import Task, User
from tasks.serializers import LoginSerializer, TaskSerializer, UserSerializer
from tasks.services.json_util import read_json, write_json

USERS = "users.json"
TASKS = "tasks.json"

#  -------------
#  USERS
#  -------------

# ViewSet
# 1. Listing all the entities of a certain type
# 2. Get an entity by ID
# 3. Create an entity in DB
# 4. DELETE
# 5. UPDATE

# CRUD operations
#  C - Create | R - Retrieve/Read | U - Update | D - Delete/Destroy


class UserViewSet(ModelViewSet):

    queryset = User.objects.all()
    serializer_class = UserSerializer

    # Fetch By Username - GET username/<username>
    @action(detail=False, methods=["GET"], url_path=r"username/(?P<username>[\w.@+-]+)")
    def by_username(self, request: Request, username: str) -> Response:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"error": f"User with username: {username} doesn't exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="create")
    def create_user(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    # Fetch tasks by user id - GET /users/<id>/tasks/
    @action(detail=True, methods=["GET"])
    def tasks(self, request: Request, pk=None) -> Response:
        user = self.get_object()
        serializer = TaskSerializer(user.tasks.all(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# class UserViewSet(ViewSet):

#     # list() - GET users + /
#     def list(self, request: Request) -> Response:
#         users = User.objects.all()

#         outgoing_data = UserSerializer(users, many=True).data
#         return Response(data=outgoing_data, status=200)

#     # retrieve() - GET /users/<id>/
#     def retrieve(self, request: Request, pk=None) -> Response:
#         try:
#             user = User.objects.get(id=pk)
#         except User.DoesNotExist:
#             return Response(
#                 {"error": f"User with id: {pk} was not found."},
#                 status=status.HTTP_404_NOT_FOUND,
#             )

#         outgoing_data = UserSerializer(user).data
#         return Response(data=outgoing_data, status=status.HTTP_200_OK)

#     # create() - POST /users/
#     def create(self, request: Request) -> Response:
#         serializer = UserSerializer(data=request.data)

#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#         validated_data = serializer.validated_data

#         user = User.objects.create(
#             username=validated_data["username"],
#             email=validated_data["email"],
#             name=validated_data["name"],
#         )

#         outgoing_data = UserSerializer(user).data
#         return Response(data=outgoing_data, status=status.HTTP_201_CREATED)

#     # update() - PUT /users/<id>/
#     def update(self, request: Request, pk=None) -> Response:
#         try:
#             user = User.objects.get(id=pk)
#         except User.DoesNotExist:
#             return Response(
#                 {"error": f"User with id: {pk} was not found."},
#                 status=status.HTTP_404_NOT_FOUND,
#             )

#         serializer = UserSerializer(data=request.data)

#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#         validated_data = serializer.validated_data
#         user.username = validated_data["username"]
#         user.email = validated_data["email"]
#         user.name = validated_data["name"]
#         user.save()
#         return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

#     # destroy() - DELETE /users/<id>/
#     def destroy(self, request: Request, pk=None) -> Response:
#         try:
#             user = User.objects.get(id=pk)
#         except User.DoesNotExist:
#             return Response(
#                 {"error": f"User with id: {pk} was not found."},
#                 status=status.HTTP_404_NOT_FOUND,
#             )

#         user.delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)

# Fetch By Username - GET username/<username>
# @action(detail=False, methods=["GET"], url_path=r"username/(?P<username>[\w.@+-]+)")
# def by_username(self, request: Request, username: str) -> Response:
#     try:
#         user = User.objects.get(username=username)
#     except User.DoesNotExist:
#         return Response(
#             {"error": f"User with username: {username} doesn't exist."},
#             status=status.HTTP_404_NOT_FOUND,
#         )

#     return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


# Login using username only.
# @api_view(["POST"])
# def login(request) -> Response:

#     serializer = LoginSerializer(data=request.data)

#     if not serializer.is_valid():
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     username = serializer.validated_data["username"]

#     try:
#         user = User.objects.get(username=username)
#     except User.DoesNotExist:
#         return Response(
#             {"error": f"User '{username}' was not found."},
#             status=status.HTTP_404_NOT_FOUND,
#         )

#     return Response(UserSerializer(user).data)

class LoginView(APIView):

    def post(self, request) -> Response:

        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        username = serializer.validated_data["username"]

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"error": f"User '{username}' was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(UserSerializer(user).data)


# # Get Tasks by User Id
# @api_view(["GET"])
# def user_tasks(request: Request, user_id: int) -> Response:
#     if not _user_exists(user_id):
#         return Response(
#             {"error": f"User with id: {user_id} was not found."},
#             status=status.HTTP_404_NOT_FOUND,
#         )

#     tasks = read_json(TASKS)
#     filtered_tasks = []
#     for t in tasks:
#         if t["user_id"] == user_id:
#             filtered_tasks.append(t)

#     return Response(filtered_tasks)


#  -------------
#  TASKS
#  -------------


# def _utc_now() -> str:
#     return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# def _user_exists(user_id: int) -> bool:
#     users = read_json(USERS)
#     for u in users:
#         if u["id"] == user_id:
#             return True
#     return False


# # List All Tasks
# @api_view(["GET"])
# def tasks(request: Request) -> Response:
#     tasks = read_json(TASKS)
#     return Response(tasks)


# # Get Task by Task Id
# @api_view(["GET"])
# def task_detail(request: Request, task_id: int) -> Response:
#     tasks = read_json(TASKS)

#     task = None
#     for t in tasks:
#         if t["id"] == task_id:
#             task = t
#             break

#     if task is None:
#         return Response(
#             {"error": f"Task with id: {task_id} was not found."},
#             status=status.HTTP_404_NOT_FOUND,
#         )

#     return Response(task)


# # Create a new Task.
# @api_view(["POST"])
# def create_task(request) -> Response:
#     tasks: list = read_json(TASKS)

#     user_id = request.data.get("user_id")
#     title = request.data.get("title")
#     description = request.data.get("description", "")
#     completed = request.data.get("completed", False)
#     due_date = request.data.get("due_date")

#     if not user_id or not title:
#         return Response(
#             {"error": "user_id and title are required fields"},
#             status=status.HTTP_400_BAD_REQUEST,
#         )

#     if not _user_exists(user_id):
#         return Response(
#             {"error": f"User with id: {user_id} was not found."},
#             status=status.HTTP_400_BAD_REQUEST,
#         )

#     max_id = 0
#     for t in tasks:
#         max_id = max(max_id, t["id"])

#     now = _utc_now()
#     created_task = {
#         "id": max_id + 1,
#         "user_id": user_id,
#         "title": title,
#         "description": description,
#         "completed": completed,
#         "created_at": now,
#         "updated_at": now,
#         "due_date": due_date,
#     }

#     tasks.append(created_task)

#     write_json(TASKS, tasks)

#     return Response(created_task, status=status.HTTP_201_CREATED)


# # Update an existing Task.
# @api_view(["PUT"])
# def update_task(request, task_id: int) -> Response:
#     tasks: list = read_json(TASKS)

#     task = None
#     for t in tasks:
#         if t["id"] == task_id:
#             task = t
#             break

#     if task is None:
#         return Response(
#             {"error": f"Task with id: {task_id} was not found."},
#             status=status.HTTP_404_NOT_FOUND,
#         )

#     user_id = request.data.get("user_id", task["user_id"])
#     title = request.data.get("title", task["title"])
#     description = request.data.get("description", task["description"])
#     completed = request.data.get("completed", task["completed"])
#     due_date = request.data.get("due_date", task["due_date"])

#     if not user_id or not title:
#         return Response(
#             {"error": "user_id and title are required fields"},
#             status=status.HTTP_400_BAD_REQUEST,
#         )

#     if not _user_exists(user_id):
#         return Response(
#             {"error": f"User with id: {user_id} was not found."},
#             status=status.HTTP_400_BAD_REQUEST,
#         )

#     task["user_id"] = user_id
#     task["title"] = title
#     task["description"] = description
#     task["completed"] = completed
#     task["due_date"] = due_date
#     task["updated_at"] = _utc_now()

#     write_json(TASKS, tasks)

#     return Response(task)


# # Delete an existing Task.
# @api_view(["DELETE"])
# def delete_task(request, task_id: int) -> Response:
#     tasks: list = read_json(TASKS)

#     task = None
#     for t in tasks:
#         if t["id"] == task_id:
#             task = t
#             break

#     if task is None:
#         return Response(
#             {"error": f"Task with id: {task_id} was not found."},
#             status=status.HTTP_404_NOT_FOUND,
#         )

#     tasks.remove(task)
#     write_json(TASKS, tasks)

#     return Response(
#         {"message": f"Task with id: {task_id} was deleted."}, status=status.HTTP_200_OK
#     )

class TaskViewSet(ModelViewSet):

    queryset = Task.objects.all()
    serializer_class = TaskSerializer

    @action(detail=False, methods=["post"], url_path="create")
    def create_task(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    @action(detail=True, methods=["put", "patch"], url_path="update")
    def update_task(self, request, *args, **kwargs):
        if request.method.lower() == "patch":
            return self.partial_update(request, *args, **kwargs)
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=["delete"], url_path="delete")
    def delete_task(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)
