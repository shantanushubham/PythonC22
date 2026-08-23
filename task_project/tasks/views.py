from rest_framework import status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from tasks.models import Task, User
from tasks.serializers import LoginSerializer, TaskSerializer, UserSerializer

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

    # Fetch tasks by user id - GET /users/<id>/tasks/
    @action(detail=True, methods=["GET"])
    def tasks(self, request: Request, pk=None) -> Response:
        user = self.get_object()
        serializer = TaskSerializer(user.tasks.all(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


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


class TaskPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class TaskViewSet(ModelViewSet):

    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    pagination_class = TaskPagination

    filterset_fields = ["user", "completed"]

    search_fields = ["title", "description"]

    ordering_fields = ["title", "created_at", "updated_at", "due_date"]

    ordering = ["-created_at"]
